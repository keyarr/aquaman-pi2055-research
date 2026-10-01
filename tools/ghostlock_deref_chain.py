#!/usr/bin/env python3
"""ghostlock_deref_chain.py - deref chain of a task->pi_blocked_on consumer.

Everything is read out of the lab image (build-aq/vmlinux) so the numbers are
the compiler's, not a note in a report. Offline only.

usage:
  ghostlock_deref_chain.py <vmlinux> [consumer ...]
  ghostlock_deref_chain.py build-aq/vmlinux pi_waiters_root
  ghostlock_deref_chain.py build-aq/vmlinux --all      # every function touching +0x7f0

Each consumer is one function that reads pi_blocked_on (task+0x7f0). The tool
follows the loads from that root and prints, per hop, the instruction that did
the deref, so you can count the words a fake object has to survive.

The chain is a dataflow walk, not pretty printing: x28 = pi_blocked_on, and a
load whose base register is the previous hop's destination becomes the next
hop. Everything else (base = task, base = a constant) is listed as "not chained"
so it cannot be mistaken for part of the primitive.

NOTE: LAB != STOCK. Lab VAs/frames are OFFLINE_ONLY. The retired lab-absolute
spill window (SP0-0x278) is superseded by tools/ghostlock_h16_search.py.
Read-only disclosure inventory lives in tools/ghostlock_disclosure.py
(--proc/--copy/--stack-flow/--heap); this file adds --disclosure
(disclosed-target -> known-consumer ruler, FASE 12, no memory touched)
and --target (H16 destination+value bidirectional taint ruler, FASE 7,
paired with tools/ghostlock_h16_target_search.py, no memory touched).
"""
import re
import subprocess
import sys

OBJDUMP = ("/home/erick/Android/Sdk/ndk/29.0.14206865/toolchains/llvm/"
           "prebuilt/linux-x86_64/bin/llvm-objdump")
ADDR2LINE_CANDIDATES = [
    ("/home/erick/Android/Sdk/ndk/29.0.14206865/toolchains/llvm/"
     "prebuilt/linux-x86_64/bin/llvm-addr2line"),
    "/usr/bin/addr2line",
]

PI_BLOCKED_ON = 0x7f0
PI_WAITERS = 0x7e0
PI_WAITERS_LEFT = 0x7e8
PRI_LOCK = 0x7d4
PRI0 = 0x68

# offset -> (struct, field). keeps the report readable without lying about numbers
FIELD = {
    PI_BLOCKED_ON: "task_struct.pi_blocked_on   (rt_mutex_waiter *)",
    PI_WAITERS: "task_struct.pi_waiters.rb_node",
    PI_WAITERS_LEFT: "task_struct.pi_waiters_leftmost",
    PRI_LOCK: "task_struct.pi_lock",
    PRI0: "task_struct.prio",
    0x30: "rt_mutex_waiter.task",
    0x38: "rt_mutex_waiter.lock",
    0x40: "rt_mutex_waiter.prio",
    0x48: "rt_mutex_waiter.deadline",
    0x18: "rt_mutex.owner",
    0x08: "rt_mutex.waiters.rb_node",
    0x10: "rt_mutex.waiters_leftmost",
    0x00: "rt_mutex.wait_lock (raw_spinlock_t)",
    0x28: "task_struct.usage (refcount_t)",
}

# name -> (why you would reach it from userspace, pseudocode body)
PSEUDO = {
    "task_blocks_on_rt_mutex": (
        "FUTEX_LOCK_PI on a futex the stale task still owns",
        """lock = pi_state1->pi_mutex            # owner == stale task
owner = lock->owner
if (owner == current) return -EDEADLK    # task_blocks_on_rt_mutex
spin_lock(&task->pi_lock)
waiter->task = task; waiter->lock = lock  # NEW waiter, ours
waiter->prio = task->prio
rt_mutex_enqueue(lock, waiter)
task->pi_blocked_on = waiter             # only place a victim gets it
spin_unlock(&task->pi_lock)
spin_lock(&owner->pi_lock)
if (waiter == rt_mutex_top_waiter(lock)) {
        rt_mutex_enqueue_pi(owner, waiter) # owner->pi_waiters = waiter
        __rt_mutex_adjust_prio(owner)      # owner->prio = waiter->prio
        if (owner->pi_blocked_on)          # <<< READS THE STALE POINTER
                chain_walk = 1
}
next_lock = owner->pi_blocked_on->lock    # <<< FIRST DEREF OF THE FAKE
if (chain_walk && next_lock)
        rt_mutex_adjust_prio_chain(owner, FULL_CHAINWALK,
                                   lock, next_lock, waiter, task)"""),

    "rt_mutex_adjust_prio": (
        "sched_setscheduler()/sched_setattr() on the stale task (any fair policy)",
        """spin_lock_irqsave(&task->pi_lock)
waiter = task->pi_blocked_on              # <<< stale
if (!waiter) return
if (waiter->prio == task->prio) return    # +0x40 only, safe fast path
next_lock = waiter->lock                  # +0x38
spin_unlock
rt_mutex_adjust_prio_chain(task, MIN_CHAINWALK, NULL, next_lock, NULL, task)"""),

    "rt_mutex_adjust_prio_chain": (
        "tail of the two above; walks the fake lock",
        """spin_lock_irq(&task->pi_lock)
waiter = task->pi_blocked_on              # <<< stale
if (!waiter) return 0
if (orig_waiter && !rt_mutex_owner(orig_lock)) return 0
if (next_lock != waiter->lock) return 0   # +0x38 again
if (top_waiter && !task_has_pi_waiters(task)) return 0
if (waiter->prio == task->prio) return 0  # +0x40 again, MIN only
lock = waiter->lock
if (!raw_spin_trylock(&lock->wait_lock)) { retry; }   # <<< ARBITRARY cmpxchg
if (lock == orig_lock || rt_mutex_owner(lock) == top_task) return -EDEADLK
put_task_struct(task)
if (!rt_mutex_owner(lock)) return 0
task = rt_mutex_owner(lock)
get_task_struct(task)                     # <<< atomic inc at owner+0x28
spin_lock(&task->pi_lock)                 # <<< cmpxchg at owner+0x7d4
next_lock = task->pi_blocked_on->lock     # <<< recurse"""),

    "remove_waiter": (
        "kernel-only (rt_mutex rollback). This is the site that leaks the pointer",
        """spin_lock(&current->pi_lock)          # current, NOT waiter->task
rt_mutex_dequeue(lock, waiter)
current->pi_blocked_on = NULL             # <<< THE BUG
spin_unlock(&current->pi_lock)
next_lock = task_blocked_on_lock(owner)   # owner->pi_blocked_on->lock
rt_mutex_adjust_prio_chain(owner, MIN_CHAINWALK, lock, next_lock, NULL, current)"""),

}


def disassemble(vmlinux, syms):
    """llvm-objdump the requested symbols, return {sym: [(addr, text, mnem, ops)]}"""
    out = subprocess.run(
        [OBJDUMP, "-d", "--disassemble-symbols=" + ",".join(syms), vmlinux],
        capture_output=True, text=True, check=True).stdout
    funcs, cur = {}, None
    for line in out.splitlines():
        m = re.match(r"^([0-9a-f]{16}) <([^>]+)>:", line)
        if m:
            cur = m.group(2)
            funcs[cur] = []
            continue
        m = re.match(r"^([0-9a-f]{16}):\s+[0-9a-f ]+?\s\s(\S+)\s+(.*)$", line)
        if m and cur:
            funcs[cur].append((int(m.group(1), 16), m.group(2), m.group(3).strip()))
    return funcs


MEM = re.compile(r"^\[\s*(x\d+|sp|xzr|wz\d+)\s*(?:,\s*#(0x[0-9a-f]+)\s*)?\]")
DST = re.compile(r"^(x\d+|w\d+)")


def parse(rest):
    """-> ((dst_reg,) or None, (base_reg, imm_or_None) or None)"""
    d = DST.match(rest)
    mem = MEM.match(rest[d.end():].lstrip(" ,\t")) if d else None
    return ((d.group(1),) if d else None,
            (mem.group(1), int(mem.group(2), 16) if mem.group(2) else None)
            if mem else None)


def scan_all(vmlinux, imm):
    """every function with a load/store at the given unsigned imm12/imm"""
    out = subprocess.run([OBJDUMP, "-d", "--no-show-raw-insn", vmlinux],
                         capture_output=True, text=True, check=True).stdout
    hits, cur = {}, None
    for line in out.splitlines():
        m = re.match(r"^([0-9a-f]{16}) <([^>]+)>:", line)
        if m:
            cur = m.group(2)
            continue
        m = re.match(r"^([0-9a-f]{16}):\s+(\S+)\s+(.*)$", line)
        if m and cur:
            mnem, rest = m.group(2), m.group(3)
            if mnem in ("ldr", "ldrh", "ldrb", "str", "strh", "strb",
                        "ldrsw", "ldp", "stp", "ldur", "stur", "ldxr", "stxr"):
                for off in re.findall(r"#(0x[0-9a-f]+)", rest):
                    if int(off, 16) == imm:
                        hits.setdefault(cur, []).append(
                            (int(m.group(1), 16), mnem, rest.strip()))
    return hits


# Exact binary chain, verified 2026-10-01 against build-aq/vmlinux by
# disassembling each function and matching VA+mnemonic+operands.
# Each entry: va, symbol, mnemonic, operands, base_reg, offset, reg_origin,
# control_cond, kind, dwarf_field, note.
# kind: read | branch | rmw | store | call
# Lab text base is 0xffffff8008000000 (no KASLR in objdir); stock slides it.
EXACT = [
    # --- trigger: futex_wait_requeue_pi leaves rt_waiter on stack ---
    dict(va=0xffffff800913b398, sym="futex_wait_requeue_pi.constprop.8",
         insn="stp x29, x30, [sp, #-0x1a0]!", base="sp", off=-0x1a0,
         origin="frame alloc", cond="always", kind="read",
         field="frame futex_wait_requeue_pi 0x1a0",
         note="FWRQ frame; rt_waiter at x29+0x80"),
    dict(va=0xffffff800913b454, sym="futex_wait_requeue_pi.constprop.8",
         insn="add x21, x29, #0x80", base="x29", off=0x80,
         origin="frame pointer", cond="always", kind="read",
         field="rt_mutex_waiter (stack slot)",
         note="x21=&rt_waiter; passed to proxy lock + stored to q.rt_waiter"),
    # --- rollback: remove_waiter clears the wrong task (the bug) ---
    dict(va=0xffffff8009105454, sym="remove_waiter",
         insn="str xzr, [x24, #0x7f0]", base="x24", off=0x7f0,
         origin="x24=SP_EL0 (current, requeuer)", cond="always", kind="store",
         field="task_struct.pi_blocked_on",
         note="STORE current, not waiter->task: victim pi_blocked_on dangles"),
    dict(va=0xffffff80091054d0, sym="remove_waiter",
         insn="ldr x21, [x0, #0x38]", base="x0", off=0x38,
         origin="x0=owner->pi_blocked_on (stale allowed)", cond="owner->pi_blocked_on != NULL",
         kind="read", field="rt_mutex_waiter.lock",
         note="first stale deref on MIN_CHAINWALK tail"),
    dict(va=0xffffff8009105518, sym="remove_waiter",
         insn="bl rt_mutex_adjust_prio_chain", base="-", off=None,
         origin="-", cond="next_lock != NULL", kind="call",
         field="-", note="MIN_CHAINWALK tail, w1=0"),
    # --- entry: FUTEX_LOCK_PI consumer ---
    dict(va=0xffffff800913b030, sym="futex_lock_pi",
         insn="futex_lock_pi (entry)", base="-", off=None,
         origin="syscall FUTEX_LOCK_PI|PRIVATE f_chain", cond="always", kind="call",
         field="-", note="4th thread consumer entry; only unprivileged 1-syscall path to FULL walk"),
    dict(va=0xffffff800913b1bc, sym="futex_lock_pi",
         insn="bl rt_mutex_timed_futex_lock", base="-", off=None,
         origin="pi_state->pi_mutex", cond="futex_lock_pi_atomic==0 (have pi_state)",
         kind="call", field="futex_pi_state.pi_mutex",
         note="reached only when key matches owner chain"),
    dict(va=0xffffff80091057d8, sym="rt_mutex_timed_futex_lock",
         insn="rt_mutex_timed_futex_lock (entry, chwalk=1)", base="-", off=None,
         origin="w3=1 FULL_CHAINWALK", cond="always", kind="call",
         field="-", note="FULL passed to rt_mutex_timed_fastlock->rt_mutex_slowlock"),
    dict(va=0xffffff8009df97e0, sym="rt_mutex_slowlock",
         insn="rt_mutex_slowlock (entry)", base="-", off=None,
         origin="chwalk forwarded", cond="fastlock failed", kind="call",
         field="-", note="calls task_blocks_on_rt_mutex then __rt_mutex_slowlock"),
    # --- task_blocks_on_rt_mutex: stores victim pointer, then reads stale ---
    dict(va=0xffffff80091052b8, sym="task_blocks_on_rt_mutex",
         insn="str x21, [x20, #0x7f0]", base="x20", off=0x7f0,
         origin="x20=new waiter task, x21=new waiter", cond="new waiter is top waiter path",
         kind="store", field="task_struct.pi_blocked_on",
         note="STORE: only place a victim gets the pointer"),
    dict(va=0xffffff80091052f0, sym="task_blocks_on_rt_mutex",
         insn="ldr x0, [x22, #0x7f0]", base="x22", off=0x7f0,
         origin="x22=owner (waiter_task, stale holder)", cond="owner->pi_lock held; both branches converge here",
         kind="read", field="task_struct.pi_blocked_on",
         note="LOAD stale pi_blocked_on; cbz NULL at +0x52f8 stops walk"),
    dict(va=0xffffff80091052f8, sym="task_blocks_on_rt_mutex",
         insn="cbz x0, task_blocks_on_rt_mutex+0x188", base="x0", off=None,
         origin="stale pointer", cond="NULL -> return 0, no walk", kind="branch",
         field="-", note="FULL avoids early return only if stale != NULL"),
    dict(va=0xffffff80091052fc, sym="task_blocks_on_rt_mutex",
         insn="ldr x25, [x0, #0x38]", base="x0", off=0x38,
         origin="x0=owner->pi_blocked_on (attacker stale)", cond="stale != NULL",
         kind="read", field="rt_mutex_waiter.lock",
         note="FIRST DEREF of fake waiter->lock into x25=next_lock"),
    dict(va=0xffffff80091053e8, sym="task_blocks_on_rt_mutex",
         insn="ldr x0, [x22, #0x7f0]", base="x22", off=0x7f0,
         origin="x22=owner (2nd path: newcomer not top)", cond="enqueue_pi path",
         kind="read", field="task_struct.pi_blocked_on",
         note="2nd stale LOAD, same deref follows at +0x52f8"),
    dict(va=0xffffff8009105378, sym="task_blocks_on_rt_mutex",
         insn="bl rt_mutex_adjust_prio_chain", base="-", off=None,
         origin="x0=owner x1=w24(FULL) x2=lock x3=x25 x4=x21 x5=x20",
         cond="chain_walk && next_lock", kind="call",
         field="-", note="FULL_CHAINWALK entry: w1=1 removes prio early-return"),
    # --- rt_mutex_adjust_prio_chain: the fake walk, all derefs + first writes ---
    dict(va=0xffffff8009104e60, sym="rt_mutex_adjust_prio_chain",
         insn="ldr x28, [x19, #0x7f0]", base="x19", off=0x7f0,
         origin="x19=task (owner, stale holder)", cond="after pi_lock; cbnz at +0x4e64",
         kind="read", field="task_struct.pi_blocked_on",
         note="waiter=x28 stale; root of fake walk"),
    dict(va=0xffffff8009104df0, sym="rt_mutex_adjust_prio_chain",
         insn="ldr x0, [x28, #0x38]", base="x28", off=0x38,
         origin="x28=stale waiter", cond="x25(orig_waiter)==NULL or owner check passed",
         kind="read", field="rt_mutex_waiter.lock",
         note="waiter->lock; cmp x20,x0 at +0x4df4 bails if != next_lock"),
    dict(va=0xffffff8009104df4, sym="rt_mutex_adjust_prio_chain",
         insn="cmp x20, x0", base="x20", off=None,
         origin="x20=next_lock (== stale lock bytes)", cond="next_lock != waiter->lock -> bail +0x4e68",
         kind="branch", field="-",
         note="attacker must keep fake lock word stable across both reads"),
    dict(va=0xffffff8009104e28, sym="rt_mutex_adjust_prio_chain",
         insn="ldr w1, [x28, #0x40]", base="x28", off=0x40,
         origin="x28=stale waiter", cond="reached when top_waiter checks pass",
         kind="read", field="rt_mutex_waiter.prio",
         note="waiter->prio; FULL continues regardless (requeue=false), MIN returns if == task->prio"),
    dict(va=0xffffff8009104e30, sym="rt_mutex_adjust_prio_chain",
         insn="b.ne rt_mutex_adjust_prio_chain+0xd8", base="-", off=None,
         origin="w1 vs w0=task->prio", cond="FULL: prio==prio sets requeue=false and CONTINUES; MIN: goto out_unlock_pi",
         kind="branch", field="-",
         note="THIS is the MIN vs FULL split: FULL reaches trylock whatever prio is"),
    dict(va=0xffffff8009104e44, sym="rt_mutex_adjust_prio_chain",
         insn="bl _raw_spin_trylock", base="x20", off=0x0,
         origin="x0=x20=fake lock", cond="prio gate passed (FULL always)",
         kind="rmw", field="rt_mutex.wait_lock",
         note="ARBITRARY cmpxchg at lock+0x00: first controlled-address RMW"),
    dict(va=0xffffff8009104f48, sym="rt_mutex_adjust_prio_chain",
         insn="bl rt_mutex_dequeue", base="x20/x28", off=0x00,
         origin="x0=lock x1=x28", cond="after prio/owner checks", kind="call",
         field="rt_mutex_waiter.tree_entry",
         note="RB_EMPTY_NODE check at +0x00..0x17; RB_CLEAR_NODE self-ptr bails early"),
    dict(va=0xffffff8009104f54, sym="rt_mutex_adjust_prio_chain",
         insn="str w0, [x28, #0x40]", base="x28", off=0x40,
         origin="w0=task->prio", cond="always after dequeue", kind="store",
         field="rt_mutex_waiter.prio",
         note="FIRST WRITE: task->prio into fake waiter+0x40 (observable from user page)"),
    dict(va=0xffffff8009104f60, sym="rt_mutex_adjust_prio_chain",
         insn="str x3, [x28, #0x48]", base="x28", off=0x48,
         origin="x3=task->dl.deadline", cond="always", kind="store",
         field="rt_mutex_waiter.deadline",
         note="2nd WRITE: deadline into fake waiter+0x48"),
    dict(va=0xffffff8009104f64, sym="rt_mutex_adjust_prio_chain",
         insn="bl rt_mutex_enqueue", base="x20/x28", off=None,
         origin="x0=lock x1=x28", cond="always", kind="call",
         field="rt_mutex.waiters.rb_node / waiters_leftmost",
         note="WRITES &waiter->tree_entry to lock+0x08 and lock+0x10 (user-page observable)"),
    dict(va=0xffffff8009104f9c, sym="rt_mutex_adjust_prio_chain",
         insn="ldr x19, [x20, #0x18]", base="x20", off=0x18,
         origin="x20=fake lock", cond="after enqueue, owner check passed",
         kind="read", field="rt_mutex.owner",
         note="lock->owner into x19; 0 -> walk returns 0, no recursion (VAR B terminator)"),
    dict(va=0xffffff8009104fac, sym="rt_mutex_adjust_prio_chain",
         insn="ldxr w0, [x21] / add #1 / stxr", base="x21", off=0x28,
         origin="x21=x19+0x28 (owner+0x28)", cond="owner != NULL",
         kind="rmw", field="task_struct.usage (refcount)",
         note="atomic INC at owner+0x28 == lock+0x18+0x28: refcount primitive if owner controlled"),
    dict(va=0xffffff8009104fc8, sym="rt_mutex_adjust_prio_chain",
         insn="bl _raw_spin_lock", base="x19", off=0x7d4,
         origin="x0=x19+0x7d4 (owner+0x7d4)", cond="after get_task_struct",
         kind="rmw", field="task_struct.pi_lock",
         note="cmpxchg at owner+0x7d4 == lock+0x18+0x7d4"),
    dict(va=0xffffff8009104ff0, sym="rt_mutex_adjust_prio_chain",
         insn="ldr x0, [x19, #0x7f0]", base="x19", off=0x7f0,
         origin="x19=lock->owner", cond="owner != NULL", kind="read",
         field="task_struct.pi_blocked_on",
         note="recursion: owner->pi_blocked_on; then ldr x20,[x0,#0x38] at +0x4ff8 = ARBITRARY READ via owner"),
    dict(va=0xffffff8009104ff8, sym="rt_mutex_adjust_prio_chain",
         insn="ldr x20, [x0, #0x38]", base="x0", off=0x38,
         origin="x0=owner->pi_blocked_on", cond="owner->pi_blocked_on != NULL",
         kind="read", field="rt_mutex_waiter.lock",
         note="2nd-order deref: arbitrary read if owner points at controlled waiter"),
]


def addr2line(vmlinux, va):
    for tool in ADDR2LINE_CANDIDATES:
        import os
        if not (tool.startswith("/") and os.path.exists(tool)):
            continue
        try:
            out = subprocess.run([tool, "-e", vmlinux, "-f", "-C",
                                  "%x" % va],
                                 capture_output=True, text=True,
                                 timeout=10).stdout.splitlines()
            if len(out) >= 2:
                return out[0].strip(), out[1].strip()
        except Exception:
            continue
    return "?", "?"


def func_base(vmlinux):
    """symbol -> base VA from llvm-nm or System.map fallback."""
    import os
    bases = {}
    try:
        nm = OBJDUMP.replace("llvm-objdump", "llvm-nm")
        if not os.path.exists(nm):
            nm = "nm"
        out = subprocess.run([nm, vmlinux], capture_output=True,
                             text=True, check=False, timeout=120).stdout
        for line in out.splitlines():
            m = re.match(r"^([0-9a-f]+) [tTwW] (\S+)", line)
            if m:
                bases[m.group(2)] = int(m.group(1), 16)
    except Exception:
        pass
    return bases


def verify(vmlinux):
    """check every EXACT VA against the binary; report OK/MISMATCH."""
    funcs = disassemble(vmlinux, sorted(set(e["sym"] for e in EXACT
                                            if "constprop" not in e["sym"]
                                            or True)))
    # disassemble() handles constprop names fine via --disassemble-symbols
    flat = {}
    for sym, insns in funcs.items():
        for addr, mnem, rest in insns:
            flat[addr] = (sym, mnem, rest)
    bad = 0
    for e in EXACT:
        va = e["va"]
        if "entry" in e["insn"] and "bl " not in e["insn"] and "ldr" not in e["insn"] \
                and "str" not in e["insn"] and "stp" not in e["insn"] \
                and "add" not in e["insn"] and "cmp" not in e["insn"] \
                and "b." not in e["insn"] and "cbz" not in e["insn"]:
            print("ENTRY  0x%x %-42s %s" % (va, e["sym"], e["note"]))
            continue
        hit = flat.get(va)
        if not hit:
            print("MISS   0x%x %-42s expected %s (no insn disassembled)"
                  % (va, e["sym"], e["insn"]))
            bad += 1
            continue
        sym, mnem, rest = hit
        want_mnem = e["insn"].split()[0]
        ok = (mnem == want_mnem) or (want_mnem in ("b.ne", "cbz", "b.eq")
                                     and mnem in ("b.ne", "b.eq", "cbz", "cbnz", "b"))
        mark = "OK  " if ok else "DIFF"
        if not ok:
            bad += 1
        print("%s 0x%x %-42s %-6s %-28s | want: %s"
              % (mark, va, e["sym"], mnem, rest[:28], e["insn"][:60]))
    print("\nverify: %d entries, %d mismatches" % (len(EXACT), bad))
    return bad


def graph(vmlinux):
    """CALLER -> FUNCTION -> LOAD/STORE -> REGISTER DATAFLOW -> MEMORY TARGET."""
    bases = func_base(vmlinux)
    print("=" * 72)
    print("GhostLock exact binary chain -> graph (build-aq/vmlinux)")
    print("text is VA39 unslid; stock adds KASLR slide to every VA")
    print("=" * 72)
    for e in EXACT:
        va = e["va"]
        fn, line = addr2line(vmlinux, va)
        base = bases.get(e["sym"])
        off_in_sym = ("+0x%x" % (va - base)) if base else "?"

        def fmt_off(o):
            if o is None:
                return "-"
            return "+0x%x" % o if o >= 0 else "-0x%x" % (-o)
        print("")
        print("%s" % e["field"])
        print("  |")
        print("  v  %s %s  [0x%x %s]" % (e["sym"], off_in_sym, va, e["kind"]))
        if e["base"] != "-":
            loc = "[base %s %s]" % (e["base"], fmt_off(e["off"]))
        else:
            loc = "[control/call]"
        print("  %s %s" % (e["insn"], loc))
        print("  reg-origin: %s | control: %s" % (e["origin"], e["cond"]))
        print("  addr2line: %s @ %s" % (fn, line))
        print("  note: %s" % e["note"])
    print("")
    print("first controlled write path (shortest):")
    print("  waiter->lock [fake +0x38 = &fake_lock]")
    print("  -> x25/x20 (next_lock)")
    print("  -> rt_mutex_adjust_prio_chain x28=waiter x20=lock")
    print("  -> ldr w1,[x28,#0x40] (prio, FULL ignores match)")
    print("  -> bl _raw_spin_trylock @0xffffff8009104e44 [lock+0x00 RMW]")
    print("  -> bl rt_mutex_dequeue (RB_CLEAR_NODE bails if tree_entry=self)")
    print("  -> str w0,[x28,#0x40] @0xffffff8009104f54 FIRST STORE (user-visible)")
    print("  -> str x3,[x28,#0x48] @0xffffff8009104f60 2nd STORE")
    print("  -> bl rt_mutex_enqueue @0xffffff8009104f64 STORES waiter ptr to lock+0x08/+0x10")
    print("  -> ldr x19,[x20,#0x18] lock->owner; 0 stops, nonzero recurses")
    print("")


def chain(funcs, sym):
    """walk loads from the pi_blocked_on root through the fake object"""
    insns = funcs.get(sym, [])
    print("=" * 72)
    why, pseudo = PSEUDO.get(sym, ("", ""))
    if why:
        print("%s\nreachable: %s" % (sym, why))
    else:
        print(sym)
    print("=" * 72)

    # a linear walk: register reuse means one pass is an over-approximation.
    # restart at every root so the chains are not merged across the body.
    roots = []
    for addr, mnem, rest in insns:
        d, mem = parse(rest)
        if mnem.startswith("st") or not (d and mem):
            continue
        if mem[1] == PI_BLOCKED_ON:
            roots.append((addr, d[0]))
    if not roots:
        print("\nno pi_blocked_on load in this function body")
        return

    total = 0
    for raddr, rreg in roots:
        cur, hops = rreg, []
        for addr, mnem, rest in insns:
            if addr <= raddr:
                continue
            d, mem = parse(rest)
            if mnem.startswith("st") or not (d and mem):
                continue
            if mem[0] != cur or not mem[1]:
                continue
            hops.append((addr, mem[1], cur, d[0], mnem, rest))
            cur = d[0]
        if not hops:
            continue
        total += len(hops)
        print("\nroot  pi_blocked_on -> %s @0x%x" % (rreg, raddr))
        for addr, off, base, dst, mnem, rest in hops:
            print("  +0x%-4x via %-4s -> %-4s   %s" %
                  (off, base, dst, FIELD.get(off, "?")))
            print("        0x%x: %s %s" % (addr, mnem, rest))
    print("\nchained loads from pi_blocked_on (linear walk, over-approximates "
          "register reuse): %d" % total)
    if pseudo:
        print("\n-- pseudocode --")
        print(pseudo)
    print()


def stock_predicate():
    """What the binary says about the state AFTER the CMP_REQUEUE_PI rollback.

    The decisive offline question is not "does the walk deref the stale waiter"
    but "what is walking, and what is it standing on". This walks the real
    control flow of the consumer path and prints the first point where a
    NATURAL (unstamped) stale pointer stops the walk.

    Nothing here is a hardware claim. EVIDENCE: OFFLINE_ONLY.
    """
    print("=" * 72)
    print("STOCK PREDICATE: consumer LOCK_PI(f_chain) with a live stale waiter")
    print("EVIDENCE: OFFLINE_ONLY (build-aq/vmlinux + source; see report sec. 5-6)")
    print("=" * 72)
    rows = [
        ("futex_lock_pi -> pi_state of f_chain (owner W)",
         "futex_lock_pi+0x124", 0xffffff800913b154,
         "bl futex_lock_pi_atomic", "u32/futex uaddr",
         "-", "attach_to_pi_owner(W) ok, pi_state owner = W, valid",
         "consumer reaches the rt_mutex, no EFAULT"),
        ("queue_me(C_q) then slowlock",
         "futex_lock_pi+0x18c", 0xffffff800913b1bc,
         "bl rt_mutex_timed_futex_lock", "pi_state->pi_mutex (= f_chain pi_mutex)",
         "-", "rt_mutex_slowlock(FULL_CHAINWALK), C_waiter on C stack",
         "arm the walk; C_waiter->lock = &f_chain.pi_mutex, owner W"),
        ("task_blocks_on_rt_mutex: store victim waiter",
         "task_blocks_on_rt_mutex+0x90", 0xffffff80091052b8,
         "str x21, [x20, #0x7f0]", "task_struct.pi_blocked_on",
         "x20=C task, x21=C_waiter", "C->pi_blocked_on = C_waiter (VALID, C stack)",
         "only place a task gets pi_blocked_on; C's own is fine"),
        ("FIRST consumer of the STALE word",
         "task_blocks_on_rt_mutex+0xc8", 0xffffff80091052f0,
         "ldr x0, [x22, #0x7f0]", "task_struct.pi_blocked_on",
         "x22=owner=W, x0=W->pi_blocked_on",
         "W->pi_blocked_on == W_waiter (stale) -> x0 != NULL",
         "cbz at +0xd0 is NOT taken: walk proceeds"),
        ("first deref of the stale waiter",
         "task_blocks_on_rt_mutex+0xd4", 0xffffff80091052fc,
         "ldr x25, [x0, #0x38]", "rt_mutex_waiter.lock",
         "x0=stale waiter, x25=next_lock",
         "next_lock = &f_target.pi_mutex (HEAP, valid, owner O)",
         "next_lock != NULL, so the walk is NOT abandoned here"),
        ("FULL chainwalk entry",
         "task_blocks_on_rt_mutex+0x150", 0xffffff8009105378,
         "bl rt_mutex_adjust_prio_chain", "-",
         "x0=W x1=FULL x2=&f_chain x3=next_lock x4=C_waiter x5=C",
         "w24 = chwalk FULL; top_waiter=C_waiter != NULL",
         "C_waiter is NOT task_top_pi_waiter(W) (O's waiter is) -> "
         "chain_walk=1 via detect_deadlock; chain later sets requeue=false"),
        ("walk [2] read",
         "rt_mutex_adjust_prio_chain+0xf8", 0xffffff8009104e60,
         "ldr x28, [x19, #0x7f0]", "task_struct.pi_blocked_on",
         "x19=W, x28=stale waiter", "same stale word re-read",
         "cbnz at +0x100 passes"),
        ("orig_lock owner check",
         "rt_mutex_adjust_prio_chain+0x78", 0xffffff8009104de4,
         "ldr x0, [x26, #0x18]", "rt_mutex.owner",
         "x26=&f_chain.pi_mutex, x0=W",
         "orig_waiter=C_waiter != NULL, owner=W != NULL -> pass",
         "the 'owner released the lock' bail does NOT fire"),
        ("chain-change gate",
         "rt_mutex_adjust_prio_chain+0x88", 0xffffff8009104df4,
         "cmp x20, x0", "rt_mutex_waiter.lock",
         "x20=next_lock, x0=waiter->lock",
         "next_lock == waiter->lock == &f_target.pi_mutex",
         "the attacker lock-must-be-stable gate PASSES on natural bytes"),
        ("top_waiter gate",
         "rt_mutex_adjust_prio_chain+0x9c", 0xffffff8009104e04,
         "cbz x0", "task_struct.pi_waiters (rb_root)",
         "x0=W->pi_waiters", "W has O_waiter in pi_waiters -> non-empty",
         "task_has_pi_waiters(W) passes, no bail"),
        ("top_waiter != task_top_pi_waiter",
         "rt_mutex_adjust_prio_chain+0xbc", 0xffffff8009104e1c,
         "cmp w23, #1", "enum rtmutex_chainwalk",
         "w23=chwalk=FULL", "FULL -> w24=0 (requeue=false)",
         "walk continues in DEADLOCK-DETECTION-ONLY mode (!requeue)"),
        ("trylock",
         "rt_mutex_adjust_prio_chain+0xdc", 0xffffff8009104e44,
         "bl _raw_spin_trylock", "rt_mutex.wait_lock",
         "x20=&f_target.pi_mutex",
         "f_target wait_lock is free -> trylock SUCCEEDS",
         "RMW at f_target+0x00: heap, valid, no fault"),
        ("cycle verdict",
         "rt_mutex_adjust_prio_chain+0x3bc", 0xffffff8009105124,
         "mov w22, #-0x23", "-", "-",
         "ret = -EDEADLK (-35)",
         "cycle closes only if lock==orig_lock or owner==top_task"),
    ]
    for i, (step, sym, va, insn, field, regs, val, cons) in enumerate(rows):
        print("")
        print("hop %d: %s" % (i, step))
        print("  where : %s [0x%x]" % (sym, va))
        print("  insn  : %s" % insn)
        print("  field : %s" % field)
        print("  regs  : %s" % regs)
        print("  natural: %s" % val)
        print("  effect: %s" % cons)
    print("")
    print("=" * 72)
    print("OCCUPANCY PREDICATE: f_target -> top_waiter -> branch (OFFLINE_ONLY)")
    print("=" * 72)
    print("")
    print("f_target.pi_mutex.waiters_leftmost @ lock+0x10 decides the walk.")
    print("rt_mutex_top_waiter() inlines to ldr + ldr + cmp + b.ne brk.")
    print("All VAs lab-absolute; offsets build-invariant (rtmutex frames 0x90/0x50/0x40).")
    print("")
    print("hop A [first !requeue tail, task=W lock=f_target]:")
    print("  VA   : 0xffffff800910508c  ldr x2, [x20, #0x10]")
    print("  reg  : x20=f_target lock -> x2=waiters_leftmost")
    print("  off  : +0x10  origin: f_target.pi_mutex  destino: x2=top_waiter")
    print("  O0   : x2=NULL (empty, W dequeued, sole node)")
    print("  O1/O2: x2=occ_waiter (first parked waiter, prio 120, valid heap stack obj)")
    print("  VA   : 0xffffff8009105094  ldr x0, [x2, #0x38]  (BUG_ON w->lock != lock)")
    print("  reg  : x2 -> x0  off +0x38  origin: top_waiter  destino: x0=top->lock")
    print("  cond : x0 must equal x20 else brk #0x800 at 0xffffff8009105114")
    print("  O0   : read at 0x38 (OFFLINE fault prediction, NOT observed as panic)")
    print("  O1/O2: x0=&f_target.pi_mutex, cmp passes, walk continues to again")
    print("  effect: O0 TIMEOUT_BLOCK 3000ms vs O1/O2 EDEADLK 0ms (HARDWARE_REPRODUCED)")
    print("")
    print("hop B [second-iteration head, task=O lock=f_chain]:")
    print("  VA   : 0xffffff8009104e00  ldr x0, [x19, #0x7e0] (O->pi_waiters root)")
    print("  VA   : 0xffffff8009104e04  cbz x0, out (ret 0, TIMEOUT)")
    print("  reg  : x19=O  off +0x7e0  cond: EMPTY -> bail, NON-EMPTY -> continue")
    print("  O0   : O->pi_waiters EMPTY (W dequeued, sole, is_top path removed it)")
    print("  O1/O2: O->pi_waiters NON-EMPTY (occ (+stale W when W not top, early return))")
    print("  effect: O0 bails here IF the walk ever reaches iteration 2;")
    print("          O1/O2 passes and reaches lock==orig EDEADLK at 0x4f10/0x5124")
    print("")
    print("hop C [second-iteration top compare, task=O]:")
    print("  VA   : 0xffffff8009104e08  ldr x0, [x19, #0x7e8] (O leftmost)")
    print("  VA   : 0xffffff8009104e0c  sub x0, x0, #0x18 (task_top, pi_entry+0x18)")
    print("  VA   : 0xffffff8009104e10  cmp x22, x0 / 0x4e14 b.eq")
    print("  reg  : x22=top(f_target) vs x0=task_top(O)")
    print("  O1   : occ == occ -> equal, requeue stays false(!), prio gate then EDEADLK")
    print("  O2   : occ1 == occ1 -> equal (2nd waiter right, top still 1st), same EDEADLK")
    print("  effect: O1 vs O2 STABLE (count does not matter, only existence)")
    print("")
    print("priority gate (same for O0/O1/O2, no prio variable needed):")
    print("  VA   : 0xffffff8009104e28  ldr w1, [x28, #0x40] (waiter prio)")
    print("  VA   : 0xffffff8009104e2c  cmp w1, w0 (vs task prio ~120)")
    print("  VA   : 0xffffff8009104e30  b.ne +0xd8 / 0x4e34 cmp w23,#1 / 0x4e38 b.ne out")
    print("  all threads SCHED_OTHER prio 120, FULL sets requeue=false and CONTINUES")
    print("  => prio never bails on FULL; existence alone decides (FASE 4 closed)")
    print("")
    print("EVIDENCE: OFFLINE_ONLY for VAs/insns; HARDWARE_REPRODUCED for O0 vs O1/O2")
    print("divergence; HARDWARE_REFUTED for the offline-only panic prediction")
    print("(O0 gives TIMEOUT_BLOCK 3000ms, zero panics, not a fault).")
    print("Actual predicate = f_target non-empty (hop A) AND O has waiters (hop B);")
    print("minimum is 1 waiter, O2 stable. Original hypothesis (top_waiter fault)")
    print("is narrowed to this existence gate.")
    print("")
    print("=" * 72)
    print("THE BAIL THAT ACTUALLY FIRES: task_has_pi_waiters(W) at +0xe04")
    print("=" * 72)
    print("")
    print("rt_mutex_adjust_prio_chain+0xe00 (0xffffff8009104e00):")
    print("  ldr x0, [x19, #0x7e0]      ; task_struct.pi_waiters.rb_root (W)")
    print("  cbz x0, 0xffffff8009104e68  ; EMPTY -> out_unlock_pi, ret 0, NO EDEADLK")
    print("")
    print("HARD PREDICTION (OFFLINE_ONLY, verified against build-aq/vmlinux):")
    print("  W->pi_waiters holds O_waiter (O is blocked on f_chain, owner W).")
    print("  O_waiter is enqueued by rt_mutex_enqueue_pi(owner=W, ...) inside")
    print("  task_blocks_on_rt_mutex when O blocked on f_chain. Nothing in the")
    print("  CMP_REQUEUE_PI rollback removes it: remove_waiter() dequeues")
    print("  W_waiter from O's pi_waiters, not O_waiter from W's.")
    print("  => W->pi_waiters is NON-EMPTY -> the cbz does NOT fire.")
    print("  => the walk reaches +0xe44 trylock and continues.")
    print("")
    print("SECOND HOP, reached only if the first hop continues:")
    print("  task = rt_mutex_owner(&f_target.pi_mutex) = O   (+0xf90)")
    print("  next_lock = task_blocked_on_lock(O)            (+0x454)")
    print("  O->pi_blocked_on == O_waiter (VALID) -> next_lock = &f_chain.pi_mutex")
    print("  top_waiter = rt_mutex_top_waiter(&f_target.pi_mutex)  (+0x454)")
    print("")
    print("  rt_mutex_top_waiter() on an EMPTY tree:")
    print("    w = rb_entry(lock->waiters_leftmost=NULL, ...) = NULL")
    print("    BUG_ON(w->lock != lock) reads NULL->lock  == address 0x38")
    print("")
    print("  build-aq/vmlinux rt_mutex_adjust_prio_chain+0x320:")
    print("    0xffffff800910508c  ldr x2, [x20, #0x10]   ; waiters_leftmost = NULL")
    print("    0xffffff8009105094  ldr x0, [x2, #0x38]    ; read at 0x38  <-- FAULT")
    print("")
    print("  EVIDENCE: OFFLINE_ONLY. The prediction is a kernel fault, NOT a")
    print("  silent walk. Stock observed TIMEOUT_BLOCK instead, so on stock the")
    print("  walk did NOT get this far. See report sec. 6 for the two states")
    print("  that produce exactly that.")
    print("")


POLL_CHAIN = [
    # function | VA | frame | SP delta from SP0 (syscall entry) | local object
    # | size | userspace-controlled? | write primitive | notes
    # SP0 = SP at SyS_ entry (same absolute addr every syscall, same thread).
    dict(fn="SyS_futex", va=0xffffff800913ca30, frame=0x70,
         sp="SP0-0x70..SP0", obj="saved regs + args spill",
         size=0x70, user=False, prim="spill (kernel ptrs)",
         note="entry frame; calls do_futex"),
    dict(fn="do_futex", va=0xffffff800913bec0, frame=0x120,
         sp="SP0-0x190..SP0-0x70", obj="saved regs, no user array",
         size=0x120, user=False, prim="none",
         note="calls futex_wait_requeue_pi.constprop.8"),
    dict(fn="futex_wait_requeue_pi.constprop.8", va=0xffffff800913b398,
         frame=0x1a0, sp="SP0-0x330..SP0-0x190",
         obj="rt_waiter at x29+0x80 (DWARF futex.c:2858 fbreg-288)",
         size=0x50, user=False, prim="none (victim slot)",
         note="WAITERTARGET [SP0-0x2b0,SP0-0x260): task+0x30 lock+0x38 prio+0x40"),
    dict(fn="sys_pselect6", va=0xffffff8009230770, frame=0x90,
         sp="SP0-0x90..SP0", obj="saved regs + timeout spill",
         size=0x90, user=False, prim="spill",
         note="pselect entry; calls core_sys_select"),
    dict(fn="core_sys_select", va=0xffffff8009230260, frame=0x190,
         sp="SP0-0x220..SP0-0x90",
         obj="stack_fds at x29+0x90 (DWARF select.c:561 fbreg-256, long[32])",
         size=0xf0, user=True, prim="copy_from_user x3 slots + memset x3 slots",
         note="STACK_FDS [SP0-0x190,SP0-0xa0): rin/out/ex user, res_* zeroed. MISSES waiter by 0x120 gap"),
    dict(fn="do_select", va=0xffffff800922fc78, frame=0x3a0,
         sp="SP0-0x5c0..SP0-0x220",
         obj="locals at x29+0x68..0x158 only; waiter equiv x29+0x310 = NO STORE (gap)",
         size=0x3a0, user=False, prim="none at waiter (VAR-independent stale)",
         note="deep but EMPTY at waiter: explains 6/6 identical HANG (VARs cannot diverge)"),
    dict(fn="sys_poll", va=0xffffff8009230f88, frame=0x40,
         sp="SP0-0x40..SP0", obj="saved regs + timespec spill",
         size=0x40, user=False, prim="spill",
         note="poll entry; calls do_sys_poll. ppoll variant frame 0x80 shifts table -0x40 (worse)"),
    dict(fn="sys_ppoll", va=0xffffff8009231098, frame=0x80,
         sp="SP0-0x80..SP0", obj="saved regs + ksigmask + timeout",
         size=0x80, user=False, prim="spill",
         note="ppoll entry; table=SP0-0x2f0 (0x40 deeper, entries gap 0x44). NOT recommended"),
    dict(fn="do_sys_poll/head", va=0xffffff8009230a50, frame=0x410,
         sp="SP0-0x3b0..SP0-0x2b0 (via sys_poll)",
         obj="stack_pps at x29+0xa0 (DWARF fbreg-880, long[32]=256B); entries at +0xc, max 30x8",
         size=0x100, user=True, prim="copy_from_user entries (user fd/events) + kernel revents",
         note="ENTRIES [SP0-0x3a4,SP0-0x2b4) max: user bytes, MISSES waiter by 4B structural (256-252)"),
    dict(fn="do_sys_poll/table", va=0xffffff8009230a50, frame=0x410,
         sp="SP0-0x2b0..SP0-0x40 (via sys_poll)",
         obj="poll_wqueues at x29+0x1a0 (DWARF fbreg-624, 624B: pt 16 + table 8 + task 8 + ints + 9x64 entries)",
         size=0x270, user="partial",
         prim="init: __pollwait/~0/NULL/current/0s; per-fd: _key=events|0x18, entry0={filp,key,wait}",
         note="TABLE==WAITER exactly: +0x38=entry0.key(small, FAULT if reached=reach proof); +0x40=flags(0). NO pointer control"),
    dict(fn="poll_initwait", va=0xffffff800922f5e0, frame=0x20,
         sp="below table (call frame)", obj="header init (inlined stores in do_sys_poll at x29+0x1a0..0x1c8)",
         size=0x20, user=False, prim="stp __pollwait/~0, NULL/current, 0/0/0",
         note="always runs: waiter+0x00..0x28 clobbered even with nfds=0 (tree_entry smashed, lock stale)"),
    dict(fn="__pollwait", va=0xffffff800922f628, frame=0x30,
         sp="below table (call frame)", obj="entry0 written to table+0x30..0x70 (filp/key/wait)",
         size=0x40, user="indirect",
         prim="entry->filp=get_file(heap); key=_key(small); wait.private=pwq(stack); func=pollwake",
         note="runs once per valid fd with poll op: filp=heap, key=events|0x18(small), wait.private=pwq(stack addr)"),
]


def poll_chain(vmlinux):
    """POLL STACK CHAIN: verify frames in binary, print table + comparison."""
    import os
    want = {
        "SyS_futex": 0x70, "do_futex": 0x120,
        "futex_wait_requeue_pi.constprop.8": 0x1a0,
        "sys_pselect6": 0x90, "core_sys_select": 0x190,
        "sys_poll": 0x40, "sys_ppoll": 0x80,
        "do_sys_poll": 0x410, "do_select": 0x3a0,
    }
    syms = sorted(set(["SyS_futex", "do_futex", "sys_pselect6",
                        "core_sys_select", "sys_poll", "sys_ppoll",
                        "do_sys_poll", "do_select"] +
                       ["futex_wait_requeue_pi.constprop.8"]))
    try:
        funcs = disassemble(vmlinux, syms)
    except Exception as e:
        print("disassemble failed: %s" % e)
        funcs = {}
    print("=" * 72)
    print("POLL STACK CHAIN (build-aq/vmlinux, SP0 = syscall-entry SP)")
    print("=" * 72)
    for e in POLL_CHAIN:
        print("")
        print("%s @0x%x frame=0x%x" % (e["fn"], e["va"], e["frame"]))
        print("  SP range : %s" % e["sp"])
        print("  local    : %s [%s]" % (e["obj"], ("0x%x" % e["size"]) if isinstance(e["size"], int) else e["size"]))
        print("  user?    : %s" % e["user"])
        print("  writes   : %s" % e["prim"])
        print("  note     : %s" % e["note"])
    print("")
    print("-" * 72)
    print("frame check vs binary first-insn (OK/MISMATCH):")
    bad = 0
    for sym, sz in sorted(want.items()):
        insns = funcs.get(sym, [])
        if not insns:
            print("  MISS %-38s (no disasm)" % sym)
            bad += 1
            continue
        addr, mnem, rest = insns[0]
        ok = ("0x%x" % sz) in rest.replace(" ", "")
        print("  %s %-38s first: %s %s (want 0x%x)" %
              ("OK  " if ok else "DIFF", sym, mnem, rest[:40], sz))
        if not ok:
            bad += 1
    print("frame check: %d/%d ok" % (len(want) - bad, len(want)))
    print("")
    print("pselect vs poll vs rt_waiter (same SP0 base, sys_poll path):")
    print("  waiter    [SP0-0x2b0, SP0-0x260)  0x50 victim (lock+0x38 prio+0x40)")
    print("  pselect   [SP0-0x190, SP0-0xa0)   0xf0 user+zero  GAP 0x120, do_select gap no-store")
    print("  poll entr [SP0-0x3a4, SP0-0x2b4)  0xf0 user max  MISS by 4B")
    print("  poll tabl [SP0-0x2b0, SP0-0x40)   0x270 mixed    EXACT overlap, +0x38=key(small)")
    print("  verdict: pselect cannot diverge VARs (gap+no-store); poll reaches")
    print("  (table==waiter) with small-int lock => panic-if-reached, not pointer.")
    print("")


def natural_path(vmlinux):
    """NATURAL WAITER PATH: no stamper, no fake. Every hop lists VA,
    instruction, field, source/destination registers, offset, the expected
    NATURAL value after a preserved GhostLock trigger, and the consequence.

    Natural values (source-derived, McMCCRU 4.9.113 == upstream for these
    files; vendor hunks: none found in PI path):
      W = waiter thread (FWRQ, holds f_chain, stale holder)
      O = owner thread (holds f_target, blocked on f_chain)
      C = consumer thread (4th, LOCK_PI f_chain)
      f_target pi_mutex = heap (pi_state->pi_mutex, valid, owner O)
      f_chain pi_mutex = heap (owner W)
      W->pi_blocked_on = &W stack rt_waiter (stale, dequeued but intact)
      W waiter->lock = &f_target pi_mutex, ->task = W, ->prio = W prio (~120)
      O->pi_blocked_on = &O stack waiter (valid, lock = &f_chain pi_mutex)
    First operation touching memory outside the waiter stack is the trylock
    RMW at lock+0x00 (heap f_target wait_lock), reached on FULL regardless
    of prio. Invisible from userspace (heap), then the walk sleeps normally:
    TIMEOUT_BLOCK, not a panic. EDEADLK would require completing the full
    W->O->W cycle; a bail anywhere before it (NULL stale, lock mismatch at
    +0x4df4, top_waiter checks) also yields TIMEOUT_BLOCK, which is why the
    timed consumer reports the CODE, not the hang.
    """
    print("=" * 72)
    print("NATURAL WAITER PATH (no stamp, no fake; build-aq/vmlinux VAs)")
    print("consumer C: FUTEX_LOCK_PI(f_chain), FULL_CHAINWALK")
    print("=" * 72)
    rows = [
        ("C blocks on f_chain",
         "task_blocks_on_rt_mutex+0xd0", 0xffffff80091052f0,
         "ldr x0, [x22, #0x7f0]", "task_struct.pi_blocked_on", "x22", "x0",
         "+0x7f0", "W task ptr (stale holder, heap task_struct)",
         "root of stale walk; cbz at +0x52f8 returns 0 if NULL (no walk)"),
        ("first deref of stale waiter",
         "task_blocks_on_rt_mutex+0xd4", 0xffffff80091052fc,
         "ldr x25, [x0, #0x38]", "rt_mutex_waiter.lock", "x0", "x25",
         "+0x38", "&f_target pi_mutex (heap, VALID, owner O)",
         "next_lock=x25; natural lock is heap-valid so no fault here"),
        ("FULL entry",
         "task_blocks_on_rt_mutex+0x150", 0xffffff8009105378,
         "bl rt_mutex_adjust_prio_chain", "-", "-", "-",
         "-", "x0=W x1=1(FULL) x2=f_chain x3=x25 x4=C_waiter x5=C",
         "FULL removes MIN prio early-return; walk proceeds whatever prio"),
        ("walk root re-read",
         "rt_mutex_adjust_prio_chain+0xf8", 0xffffff8009104e60,
         "ldr x28, [x19, #0x7f0]", "task_struct.pi_blocked_on", "x19", "x28",
         "+0x7f0", "&W stack rt_waiter (same stale object)",
         "x28=stale waiter; cbnz guards NULL"),
        ("waiter->lock re-read + match gate",
         "rt_mutex_adjust_prio_chain+0x88", 0xffffff8009104df0,
         "ldr x0, [x28, #0x38]", "rt_mutex_waiter.lock", "x28", "x0",
         "+0x38", "&f_target pi_mutex (must equal x25)",
         "cmp x20,x0 at +0x4df4 bails to +0x4e68 on mismatch; natural "
         "passes (same heap word read twice, stable without stamp)"),
        ("waiter->prio read (FULL ignores match)",
         "rt_mutex_adjust_prio_chain+0xc0", 0xffffff8009104e28,
         "ldr w1, [x28, #0x40]", "rt_mutex_waiter.prio", "x28", "w1",
         "+0x40", "W prio (~120, natural)",
         "FULL sets requeue=false on match and CONTINUES; MIN would bail"),
        ("FIRST op outside waiter stack",
         "rt_mutex_adjust_prio_chain+0xdc", 0xffffff8009104e44,
         "bl _raw_spin_trylock", "rt_mutex.wait_lock", "x20", "-",
         "+0x00", "f_target->wait_lock (heap spinlock, valid)",
         "ARBITRARY-addr RMW but natural addr is heap: succeeds or spins "
         "in cpu_relax loop at +0x4e4c; user-invisible either way"),
        ("dequeue (no-op on dequeued stale)",
         "rt_mutex_adjust_prio_chain+0xe0", 0xffffff8009104f48,
         "bl rt_mutex_dequeue", "rt_mutex_waiter.tree_entry", "x20/x28", "-",
         "+0x00..0x17", "stale waiter already dequeued by remove_waiter",
         "RB_EMPTY/CLEAR checks bail early; no user-visible effect"),
        ("FIRST WRITE (stack, invisible)",
         "rt_mutex_adjust_prio_chain+0xec", 0xffffff8009104f54,
         "str w0, [x28, #0x40]", "rt_mutex_waiter.prio", "w0", "x28",
         "+0x40", "W task prio -> W stack waiter+0x40",
         "lands in W kernel stack, not in any user page: unobservable"),
        ("2nd WRITE (stack, invisible)",
         "rt_mutex_adjust_prio_chain+0xf8", 0xffffff8009104f60,
         "str x3, [x28, #0x48]", "rt_mutex_waiter.deadline", "x3", "x28",
         "+0x48", "deadline -> W stack waiter+0x48",
         "same: kernel stack only"),
        ("enqueue writes waiter ptr to HEAP lock",
         "rt_mutex_adjust_prio_chain+0xfc", 0xffffff8009104f64,
         "bl rt_mutex_enqueue", "rt_mutex.waiters rb_node/leftmost", "x20/x28", "-",
         "+0x08/+0x10", "&W stack waiter -> f_target+0x08/+0x10 (heap)",
         "kernel-heap corruption of f_target waiters (valid ptr, no fault); "
         "still user-invisible, device stays stable"),
        ("lock->owner decides recursion vs stop",
         "rt_mutex_adjust_prio_chain+0x134", 0xffffff8009104f9c,
         "ldr x19, [x20, #0x18]", "rt_mutex.owner", "x20", "x19",
         "+0x18", "O task ptr (f_target owner, heap)",
         "0 stops walk (returns 0, then C sleeps: TIMEOUT_BLOCK); nonzero "
         "recurses via +0x4ff0 ldr x0,[x19,#0x7f0] (O->pi_blocked_on)"),
        ("recursion dispatches on O waiter",
         "rt_mutex_adjust_prio_chain+0x188", 0xffffff8009104ff0,
         "ldr x0, [x19, #0x7f0]", "task_struct.pi_blocked_on", "x19", "x0",
         "+0x7f0", "&O stack waiter (valid, lock=&f_chain pi_mutex)",
         "then ldr x20,[x0,#0x38] at +0x4ff8 reads f_chain; "
         "lock==orig_lock at next iteration returns -EDEADLK (fast) if "
         "the full cycle completes"),
    ]
    for i, (step, sym, va, insn, field, src, dst, off, nat, cons) in enumerate(rows):
        print("")
        print("hop %d: %s" % (i, step))
        print("  where : %s [0x%x]" % (sym, va))
        print("  insn  : %s" % insn)
        print("  field : %s" % field)
        print("  regs  : %s -> %s  off %s" % (src, dst, off))
        print("  natural: %s" % nat)
        print("  consequence: %s" % cons)
    print("")
    print("net: natural walk touches heap+peer stacks only, never the fake")
    print("page; all stores are user-invisible, so the timed consumer is the")
    print("only discriminator: EDEADLK fast = cycle completed (H1 proof),")
    print("TIMEOUT_BLOCK = slept with no cycle (bail or normal block).")
    print("")


def heap_chain():
    """POST-LOCK DATAFLOW: every load/store/branch downstream of waiter->lock.

    Starts at waiter->lock (x20 = next_lock = &f_target.pi_mutex) in
    rt_mutex_adjust_prio_chain FULL !requeue (requeue=false, w24=0),
    iteration 1 task=W. One line per access, no aggregation.
    VAs are build-aq/vmlinux absolute; offsets are function-relative
    (base rt_mutex_adjust_prio_chain = 0xffffff8009104d68).
    EVIDENCE: OFFLINE_ONLY (disassembly + source).
    """
    print("=" * 72)
    print("HEAP CHAIN: waiter->lock -> first heap word -> branch/store")
    print("EVIDENCE: OFFLINE_ONLY (build-aq/vmlinux + rtmutex.c/rtmutex_common.h)")
    print("scope: FULL !requeue, iter1 task=W lock=f_target.pi_mutex (natural)")
    print("=" * 72)
    rows = [
        ("H0", 0xffffff8009104df0, "rt_mutex_adjust_prio_chain+0x88",
         "ldr x0, [x28, #0x38]", "x28", 0x38,
         "stale waiter (stack)", "x0=lock",
         "x25(orig_waiter)==NULL or owner check passed", "LOAD",
         "rt_mutex_waiter.lock",
         "re-read of waiter->lock; must equal x20 or bail at H1"),
        ("H1", 0xffffff8009104df4, "rt_mutex_adjust_prio_chain+0x8c",
         "cmp x20, x0", "x20", None,
         "x20=next_lock, x0=H0", "flags",
         "next_lock != waiter->lock -> b.ne out_unlock_pi (+0x4df8)",
         "BRANCH", "-",
         "lock-stability gate; natural passes (same heap word twice)"),
        ("H2", 0xffffff8009104e28, "rt_mutex_adjust_prio_chain+0xc0",
         "ldr w1, [x28, #0x40]", "x28", 0x40,
         "stale waiter (stack)", "w1=prio",
         "reached when top_waiter checks pass (FULL)", "LOAD",
         "rt_mutex_waiter.prio",
         "waiter->prio; FULL sets requeue=false and CONTINUES on match"),
        ("H3", 0xffffff8009104e30, "rt_mutex_adjust_prio_chain+0xc8",
         "b.ne +0xd8 / cmp w23,#1 / b.ne out", "-", None,
         "w1 vs w0=task->prio, w23=FULL", "w24=requeue flag",
         "FULL: match -> w24=0 CONTINUES; MIN: match -> out", "BRANCH",
         "-",
         "MIN vs FULL split; natural prio ~120 either way continues"),
        ("H4", 0xffffff8009104e44, "rt_mutex_adjust_prio_chain+0xdc",
         "bl _raw_spin_trylock (x0=x20)", "x20", 0x00,
         "x20=f_target.pi_mutex (heap)", "-",
         "wait_lock free -> success; locked -> fail", "RMW",
         "rt_mutex.wait_lock",
         "FIRST heap touch past waiter stack; cmpxchg at lock+0x00"),
        ("H5", 0xffffff8009104e48, "rt_mutex_adjust_prio_chain+0xe0",
         "cbnz w0, +0x1a8", "w0", None,
         "trylock result", "pc",
         "0 -> unlock+cpu_relax+retry (+0x4e4c); !=0 -> +0x4f10", "BRANCH",
         "-",
         "natural wait_lock free -> continues; contended -> spins here"),
        ("H6", 0xffffff8009104f10, "rt_mutex_adjust_prio_chain+0x1a8",
         "cmp x20, x26", "x20", None,
         "x20=lock, x26=orig_lock=&f_chain", "flags",
         "equal -> EDEADLK at +0x3bc (0x5124)", "BRANCH",
         "-",
         "deadlock check 1; natural f_target != f_chain -> continue"),
        ("H7", 0xffffff8009104f18, "rt_mutex_adjust_prio_chain+0x1b0",
         "ldr x0, [x20, #0x18]", "x20", 0x18,
         "f_target.pi_mutex (heap)", "x0=owner raw",
         "after H6 pass, lock still held", "LOAD",
         "rt_mutex.owner",
         "lock->owner (low bit = HAS_WAITERS); masked next"),
        ("H8", 0xffffff8009104f24, "rt_mutex_adjust_prio_chain+0x1bc",
         "cmp x1, x0 (masked) / b.eq EDEADLK", "x0", None,
         "x0=owner masked, x1=top_task=C", "flags",
         "owner == top_task -> EDEADLK at +0x3bc", "BRANCH",
         "-",
         "deadlock check 2; natural O != C -> continue"),
        ("H9", 0xffffff8009104f2c, "rt_mutex_adjust_prio_chain+0x1c4",
         "cbz w24, +0x2bc (!requeue tail)", "w24", None,
         "w24=requeue flag (0 here)", "pc",
         "0 -> tail at +0x5024; 1 -> requeue path +0x4f30", "BRANCH",
         "-",
         "FULL first iter always 0 (top mismatch + prio path); tail next"),
        ("H10", 0xffffff800910504c, "rt_mutex_adjust_prio_chain+0x2e4",
         "ldr x0, [x20, #0x18]", "x20", 0x18,
         "f_target.pi_mutex (heap, 2nd read)", "x0=owner raw",
         "!requeue tail, lock held", "LOAD",
         "rt_mutex.owner",
         "owner re-read; same word as H7, still O"),
        ("H11", 0xffffff8009105050, "rt_mutex_adjust_prio_chain+0x2e8",
         "tst x0, #~1 / b.eq +0x38c (0x50f4)", "x0", None,
         "x0=owner masked", "flags",
         "NULL -> return 0 (end of chain); !=NULL -> continue", "BRANCH",
         "-",
         "HEAP_PREDICATE_1 (owner NULL?); natural O -> continues both N0/N1"),
        ("H12", 0xffffff8009105068, "rt_mutex_adjust_prio_chain+0x300",
         "ldxr w0,[x21] / add #1 / stxr (x21=x19+0x28)", "x21", 0x28,
         "x19=owner=O (heap task_struct)", "mem [O+0x28]",
         "owner != NULL (H11 passed)", "RMW",
         "task_struct.usage (refcount_t)",
         "get_task_struct(O): atomic INC at owner+0x28; unconditional here"),
        ("H13", 0xffffff8009105080, "rt_mutex_adjust_prio_chain+0x318",
         "bl _raw_spin_lock (x0=x22=x19+0x7d4)", "x19", 0x7d4,
         "x19=owner=O", "mem [O+0x7d4]",
         "after H12 inc", "RMW",
         "task_struct.pi_lock",
         "cmpxchg at owner+0x7d4; then owner pi_lock held"),
        ("H14", 0xffffff8009105084, "rt_mutex_adjust_prio_chain+0x31c",
         "ldr x0, [x19, #0x7f0]", "x19", 0x7f0,
         "owner task O (heap)", "x0=O->pi_blocked_on",
         "owner pi_lock held", "LOAD",
         "task_struct.pi_blocked_on",
         "O waiter (valid, lock=&f_chain); NULL would bail next"),
        ("H15", 0xffffff8009105088, "rt_mutex_adjust_prio_chain+0x320",
         "cbz x0, +0x454 (0x51bc)", "x0", None,
         "x0=O->pi_blocked_on", "pc",
         "NULL -> goto 0x51bc path; !=NULL -> H16", "BRANCH",
         "-",
         "owner-blocked gate; natural O blocked -> continues"),
        ("H16", 0xffffff800910508c, "rt_mutex_adjust_prio_chain+0x324",
         "ldr x2, [x20, #0x10]", "x20", 0x10,
         "f_target.pi_mutex (heap)", "x2=leftmost",
         "lock held, owner held", "LOAD",
         "rt_mutex.waiters_leftmost",
         "HEAP_PREDICATE_0 load: N0 NULL vs N1/N2 occ ptr"),
        ("H17", 0xffffff8009105090, "rt_mutex_adjust_prio_chain+0x328",
         "ldr x28, [x0, #0x38]", "x0", 0x38,
         "O->pi_blocked_on (O stack waiter)", "x28=next_lock",
         "H15 passed (x0 != NULL)", "LOAD",
         "rt_mutex_waiter.lock",
         "next lock for iter2: natural &f_chain.pi_mutex"),
        ("H18", 0xffffff8009105094, "rt_mutex_adjust_prio_chain+0x32c",
         "ldr x0, [x2, #0x38]", "x2", 0x38,
         "top_waiter (occ stack or NULL)", "x0=top->lock",
         "x2=H16 (must be non-NULL to deref)", "LOAD",
         "rt_mutex_waiter.lock (BUG_ON w->lock != lock)",
         "N1/N2: &f_target, passes; N0 OFFLINE predicts fault at 0x38"),
        ("H19", 0xffffff8009105098, "rt_mutex_adjust_prio_chain+0x330",
         "cmp x20, x0 / b.ne brk #0x800 (0x5114)", "x20", None,
         "x20=lock, x0=H18", "flags",
         "!= -> BRK panic; == -> continue to unlocks", "BRANCH",
         "-",
         "BUG_ON: natural occ passes; N0 would fault IF reached"),
        ("H20", 0xffffff80091050b4, "rt_mutex_adjust_prio_chain+0x34c",
         "cbz x28, +0x47c (0x51e4)", "x28", None,
         "x28=next_lock (H17)", "pc",
         "NULL -> out (ret 0); !=NULL -> again task=O lock=f_chain",
         "BRANCH", "-",
         "end-of-chain gate; natural f_chain != NULL -> iter2"),
    ]
    for h, va, sym, insn, base, off, orig, dst, cond, kind, field, note in rows:
        if off is None:
            loc = "[control]"
        else:
            loc = "[base %s +0x%x]" % (base, off)
        print("")
        print("%s %s %s [0x%x %s]" % (h, sym, kind, va, loc))
        print("  insn  : %s" % insn)
        print("  field : %s" % field)
        print("  origin: %s -> destino: %s" % (orig, dst))
        print("  cond  : %s" % cond)
        print("  note  : %s" % note)
    print("")
    print("first heap word: lock+0x00 RMW (H4) -- no branch on its VALUE")
    print("  beyond stability; first heap-VALUE branch is H6/H8 (lock/owner")
    print("  identity), first heap-STATE branch alterable naturally is H16")
    print("  (leftmost NULL vs occ). lock+0x08 is NOT touched in !requeue")
    print("  (only inside enqueue/dequeue, skipped here). +0x20.. are OOB")
    print("  (rt_mutex size 0x20, DWARF); no load exists for them on this path.")
    print("")


def h16_chain():
    """H16: every load/store of rt_mutex_waiter.lock (+0x38) on the PI path.

    Birth, lifetime, readers, first deref / RMW / branch downstream.
    VAs are build-aq/vmlinux absolute (base rt_mutex_adjust_prio_chain =
    0xffffff8009104d68). EVIDENCE: OFFLINE_ONLY (binary + rtmutex.c).
    Stock slides every VA by KASLR; offsets are build-invariant.
    """
    print("=" * 72)
    print("H16: waiter->lock (+0x38) birth -> readers -> heap consumption")
    print("EVIDENCE: OFFLINE_ONLY (build-aq/vmlinux + .src/linux-amlogic)")
    print("scope: 4.9.113 arm64, CONFIG_DEBUG_RT_MUTEXES=n path")
    print("=" * 72)
    rows = [
        ("H16.0 BIRTH (only store in the tree)",
         0xffffff800910527c, "task_blocks_on_rt_mutex+0x54",
         "stp x20, x19, [x21, #0x30]", "x21", 0x30,
         "x21=new waiter (caller stack) x20=task x19=lock",
         "x21=new waiter, [x21,#0x30]=task [x21,#0x38]=lock",
         "under lock->wait_lock + task->pi_lock", "STORE",
         "rt_mutex_waiter.task/lock",
         "rtmutex.c:997-998 waiter->task=task waiter->lock=lock. "
         "ONLY store to waiter->lock in kernel/locking + futex.c "
         "(grep waiter->lock= : 1 hit). Callers: rt_mutex_start_proxy_lock "
         "(requeue: lock=pi_state->pi_mutex, waiter=this->rt_waiter on the "
         "sleepers own FWRQ stack) and rt_mutex_slowlock (lock=target, "
         "waiter=local in slowlock frame). Field is written ONCE, never "
         "updated: no requeue/rollback/dequeue/enqueue/deboost/sched path "
         "stores it again."),
        ("H16.1 top->lock check, enqueue path (NOT stale)",
         0xffffff80091052a0, "task_blocks_on_rt_mutex+0x78",
         "ldr x0, [x0, #0x38]", "x0", 0x38,
         "x0=lock+0x10 leftmost (0x5298 ldr x0,[x19,#0x10])",
         "x0=top_waiter->lock",
         "rt_mutex_has_waiters(lock) true", "LOAD",
         "rt_mutex_waiter.lock (rt_mutex_top_waiter BUG_ON)",
         "cmp x19,x0 at +0x7c, b.ne brk #0x800 (+0x180). Reads the CURRENT "
         "top waiter of the lock being taken, not any stale pointer."),
        ("H16.2 top->lock check, owner path (NOT stale)",
         0xffffff80091052d8, "task_blocks_on_rt_mutex+0xb0",
         "ldr x1, [x0, #0x38]", "x0", 0x38,
         "x0=lock+0x10 leftmost (0x52d4, under owner->pi_lock)",
         "x1=top_waiter->lock",
         "owner pi_lock held, 2nd path", "LOAD",
         "rt_mutex_waiter.lock (top check)",
         "cmp x19,x1 at +0xb4, b.ne brk. Same object class as H16.1."),
        ("H16.3 STALE ROOT load (GhostLock gate input)",
         0xffffff80091052f0, "task_blocks_on_rt_mutex+0xc8",
         "ldr x0, [x22, #0x7f0]", "x22", 0x7f0,
         "x22=owner=W (stale holder, heap task_struct)",
         "x0=W->pi_blocked_on (stale W_waiter, W FWRQ stack)",
         "owner->pi_lock held; both enqueue paths converge", "LOAD",
         "task_struct.pi_blocked_on",
         "2nd encoding at +0x1c0 (0x53e8, enqueue_pi path). "
         "cbz x0 at +0xd0: NULL -> return 0 (no walk). "
         "Lifetime: W_waiter bytes live while W sleeps in FWRQ "
         "(frame 0x1a0 at x29+0x80 = SP0-0x2b0); remove_waiter dequeued it "
         "but cleared current->pi_blocked_on (wrong task), so the slot "
         "keeps lock=&f_target.pi_mutex."),
        ("H16.4 FIRST STALE DEREF -> next_lock",
         0xffffff80091052fc, "task_blocks_on_rt_mutex+0xd4",
         "ldr x25, [x0, #0x38]", "x0", 0x38,
         "x0=stale waiter (H16.3)",
         "x25=next_lock=&f_target.pi_mutex (heap, owner O)",
         "stale != NULL", "LOAD",
         "rt_mutex_waiter.lock",
         "First use of attacker-relevant bytes. Branch: cmp x25,#0 at "
         "+0xe4 + cbz w23 at +0xf0: NULL -> return 0, non-NULL -> chain. "
         "Passed as x3 to the walk; NEVER dereferenced here beyond the "
         "comparison (comment: only used for comparison to detect lock "
         "chain changes)."),
        ("H16.5 FULL entry (value carried, not loaded)",
         0xffffff8009105378, "task_blocks_on_rt_mutex+0x150",
         "bl rt_mutex_adjust_prio_chain", "-", None,
         "x0=W x1=FULL x2=&f_chain.pi_mutex x3=x25 x4=C_waiter x5=C",
         "walk args",
         "chain_walk && next_lock", "CALL",
         "-",
         "x20=next_lock(H16.4) vs later re-read must stay equal (H16.7)."),
        ("H16.6 walk root re-read (same stale word)",
         0xffffff8009104e60, "rt_mutex_adjust_prio_chain+0xf8",
         "ldr x28, [x19, #0x7f0]", "x19", 0x7f0,
         "x19=W (task, ref held)",
         "x28=stale waiter (same object as H16.3)",
         "after task->pi_lock; cbnz passes", "LOAD",
         "task_struct.pi_blocked_on",
         "Stability requirement: H16.4 and H16.7 read the same stack slot "
         "twice; any stamp must keep it stable across both."),
        ("H16.7 waiter->lock re-read + stability gate",
         0xffffff8009104df0, "rt_mutex_adjust_prio_chain+0x88",
         "ldr x0, [x28, #0x38]", "x28", 0x38,
         "x28=stale waiter (H16.6)",
         "x0=waiter->lock",
         "orig_waiter==NULL or owner check passed", "LOAD",
         "rt_mutex_waiter.lock",
         "cmp x20,x0 at +0x8c (0x4df4), b.ne out_unlock_pi (+0x4df8): "
         "mismatch -> bail ret 0. FIRST branch dependent on waiter->lock "
         "VALUE. Natural passes (same heap word twice)."),
        ("H16.8 lock consumed: FIRST RMW past the waiter",
         0xffffff8009104e44, "rt_mutex_adjust_prio_chain+0xdc",
         "bl _raw_spin_trylock (x0=x20)", "x20", 0x00,
         "x20=lock=&f_target.pi_mutex (heap)",
         "-",
         "prio gate passed (FULL always continues)", "RMW",
         "rt_mutex.wait_lock",
         "cmpxchg at [Xn,#0x00]. FIRST dereference of Xn contents; first "
         "heap word consumed. No value branch beyond free/locked."),
        ("H16.9 lock consumed: owner + leftmost",
         0xffffff800910508c, "rt_mutex_adjust_prio_chain+0x324",
         "ldr x2, [x20, #0x10]", "x20", 0x10,
         "x20=lock (heap)",
         "x2=waiters_leftmost (top waiter)",
         "lock held, owner held", "LOAD",
         "rt_mutex.waiters_leftmost",
         "Then 0x5090 ldr x28,[x0,#0x38] (H16.10: O waiter->lock = next, "
         "&f_chain) and 0x5094 ldr x0,[x2,#0x38] (H16.11: top->lock) + "
         "0x5098 cmp x20,x0 / b.ne brk #0x800 (H16.12, BUG_ON). First "
         "heap-VALUE branch alterable naturally (leftmost NULL vs occ)."),
        ("H16.10 next iteration lock (task_blocked_on_lock inline)",
         0xffffff8009104ff8, "rt_mutex_adjust_prio_chain+0x190",
         "ldr x20, [x0, #0x38]", "x0", 0x38,
         "x0=owner->pi_blocked_on (0x4ff0 ldr x0,[x19,#0x7f0])",
         "x20=next_lock for iter2",
         "owner->pi_blocked_on != NULL", "LOAD",
         "rt_mutex_waiter.lock",
         "Natural: O->pi_blocked_on=O_waiter (valid, O stack), "
         "x20=&f_chain.pi_mutex -> iter2 lock==orig EDEADLK. Same inline "
         "pattern at 0x5090 (x28 variant, !requeue tail)."),
        ("H16.11 MIN-tail stale reader (rollback path)",
         0xffffff80091054d0, "remove_waiter+0xd0",
         "ldr x21, [x0, #0x38]", "x0", 0x38,
         "x0=owner->pi_blocked_on (0x54c8, x20=owner)",
         "x21=next_lock (MIN_CHAINWALK)",
         "owner blocked; cbz x21 bails", "LOAD",
         "rt_mutex_waiter.lock",
         "GhostLock rollback tail: owner=O valid here, so next_lock = "
         "&f_chain.pi_mutex;bl chain at +0x118 MIN. Not the consumer path."),
        ("H16.12 sched reader (setscheduler tiebreaker)",
         0xffffff8009105784, "rt_mutex_adjust_pi+0x64",
         "ldr x21, [x2, #0x38]", "x2", 0x38,
         "x2=task->pi_blocked_on (0x5748, x19=task)",
         "x21=next_lock (MIN_CHAINWALK)",
         "waiter->prio != task->prio", "LOAD",
         "rt_mutex_waiter.lock",
         "sched_setscheduler(waiter_tid) path; schedA P5b used it as "
         "MIN tiebreaker (rc=0, no panic, HANG kept)."),
    ]
    for t, va, sym, insn, base, off, orig, dst, cond, kind, field, note in rows:
        if off is None:
            loc = "[control/call]"
        else:
            loc = "[base %s +0x%x]" % (base, off)
        print("")
        print("%s [%s %s]" % (t, kind, loc))
        print("  va    : 0x%x %s" % (va, sym))
        print("  insn  : %s" % insn)
        print("  field : %s" % field)
        print("  origin: %s" % orig)
        print("  ->    : %s" % dst)
        print("  cond  : %s" % cond)
        print("  note  : %s" % note)
    print("")
    print("dataflow summary (FULL consumer, natural stale):")
    print("  rt_waiter (W FWRQ stack, SP0-0x2b0) -> [slot+0x38]=&f_target")
    print("  -> H16.4 x25 (next_lock) -> H16.5 x3 -> H16.7 cmp vs x20")
    print("  -> H16.8 [Xn,#0x00] trylock RMW -> [Xn,#0x18] owner (x19=O)")
    print("  -> H16.9 [Xn,#0x10] leftmost -> H16.11 top->lock")
    print("  -> H16.12 cmp x20,x0 / b.ne brk -> iter2 task=O, H16.10 next")
    print("  -> lock==orig EDEADLK at 0x4f10/0x5124")
    print("")
    print("mutation answer: exactly ONE store (H16.0, rtmutex.c:998); zero")
    print("  post-creation writers in 4.9.113 (requeue/dequeue/enqueue/")
    print("  rollback/deboost/adjust_pi never store waiter->lock).")
    print("  => E: overwrite-only by external corruption. First corruption")
    print("  point = the 8B slot [W_waiter,#0x38] itself (W FWRQ frame,")
    print("  alive while W sleeps, ~30s hrtimer window in harness).")
    print("")


def h16_write_surface(vmlinux):
    """FASE1+3+4+6: H16 slot table + 8B-store scan + PI-path composition.

    OFFLINE_ONLY (build-aq/vmlinux + .src/linux-amlogic). Prints:
    (a) exact H16 lifetime table (reader/writer | VA | insn | func |
        timing | source | dest), NATURAL vs POTENTIAL split;
    (b) every store with #0x38 in PI/futex/signal/poll/select/pipe/ioctl/
        workqueue paths (FASE3 narrowed scan);
    (c) PI-path RMW inventory (FASE6) with redirect verdict.
    Full-binary 8B-store census (str Xt / stp / stxr+stlxr) is printed as
    counts: exhaustive per-insn taint is out of scope for one round, the
    narrowed scan is the auditable surface.
    """
    import collections
    print("=" * 72)
    print("H16 WRITE SURFACE (FASE1+3+4+6)")
    print("EVIDENCE: OFFLINE_ONLY (build-aq/vmlinux + .src/linux-amlogic)")
    print("=" * 72)
    print("")
    print("FASE1: [W_waiter+0x38] lifetime (lab VAs, stock slides all VAs)")
    print("  birth: task_blocks_on_rt_mutex+0x54 0xffffff800910527c")
    print("    stp x20,x19,[x21,#0x30]  ([x21,#0x30]=task [x21,#0x38]=lock)")
    print("    before: bl __rt_mutex_adjust_prio @0x5278 (task prio fixup)")
    print("    after : ldr w0,[x20,#0x68] @0x5280 (task->prio) + str w0,[x21,#0x40]")
    print("    creator: task_blocks_on_rt_mutex (rtmutex.c:997-998)")
    print("    first writer: H16.0 itself (ONLY store, grep waiter->lock= : 1 hit)")
    print("    lifetime: W FWRQ frame alive while W sleeps (hrtimer ~30s in")
    print("      harness); slot stable between H16.4 (0x52fc) and H16.7 (0x4df0).")
    print("    last read before consumer: H16.4 ldr x25,[x0,#0x38] @0x52fc")
    print("      (next_lock, carried as x3 into the walk)")
    print("    last read after consumer entry: H16.7 ldr x0,[x28,#0x38] @0x4df0")
    print("      + cmp x20,x0 @0x4df4 / b.ne out (FIRST value branch on H16)")
    print("    xrefs to +0x38 on PI path: 0x52a0 H16.1 (NOT stale, top check),")
    print("      0x52d8 H16.2 (NOT stale, owner path), 0x52fc H16.4 (STALE first),")
    print("      0x4df0 H16.7 (STALE re-read), 0x4f34/0x4fd4/0x4ff8/0x5090/0x5094/")
    print("      0x50d8/0x5108/0x5168/0x5190/0x51c0 (iter2/tail, owner_or_top),")
    print("      0x5428/0x54ac/0x54d0 H16.11 (MIN-tail), 0x5784 H16.12 (sched).")
    print("")
    print("  reader/writer | VA | instruction | function | timing | source | dest")
    print("  NATURAL WRITERS (1):")
    print("    STORE | 0xffffff800910527c | stp x20,x19,[x21,#0x30] |")
    print("      task_blocks_on_rt_mutex | waiter birth (under wait_lock+pi_lock) |")
    print("      x19=lock(&f_target.pi_mutex) | [W_waiter,#0x38]")
    print("  NATURAL READERS (stale, in-window):")
    print("    LOAD | 0xffffff80091052fc | ldr x25,[x0,#0x38] | task_blocks |")
    print("      consumer entry (stale!=NULL) | W_waiter | x25=next_lock")
    print("    LOAD | 0xffffff8009104df0 | ldr x0,[x28,#0x38] | adjust_prio_chain |")
    print("      walk head (gate) | W_waiter | x0 (cmp x20,x0 @0x4df4)")
    print("  POTENTIAL CORRUPT WRITERS (FASE3 result): NONE FOUND (see below).")
    print("    3384 stores with #0x38 in full binary; 202 in futex/signal/poll/")
    print("    select/pipe/ioctl/workqueue subsys; 0 with dest=W FWRQ stack AND")
    print("    value=&f_alt.pi_mutex. Nearest clean pointer misses by 0x20")
    print("    (amstream_do_ioctl_old stp +0x48 -> SP0-0x258) + hw side effects.")
    print("")
    # narrowed scan, live from the binary so VAs are not hand-copied
    try:
        out = subprocess.run([OBJDUMP, "-d", "--no-show-raw-insn",
                              "--disassemble-symbols=task_blocks_on_rt_mutex,"
                              "rt_mutex_adjust_prio_chain,remove_waiter,"
                              "rt_mutex_adjust_pi,rt_mutex_enqueue,"
                              "rt_mutex_dequeue,futex_requeue,__pollwait,"
                              "do_sys_poll,complete_signal,process_one_work,"
                              "configfs_setattr",
                              vmlinux],
                             capture_output=True, text=True, check=True).stdout
        cur = None
        print("FASE3 narrowed: stores with #0x38 in PI-adjacent symbols (live):")
        n = 0
        for line in out.splitlines():
            m = re.match(r"^([0-9a-f]{16}) <([^>]+)>:", line)
            if m:
                cur = m.group(2)
                continue
            m = re.match(r"^([0-9a-f]{16}):\s+(\S+)\s+(.*)$", line)
            if m and cur and m.group(2) in ("str", "stp", "stur", "stxr",
                                            "stlxr", "stlr"):
                if "#0x38" in m.group(3):
                    print("  0x%s %-28s %-4s %s" % (m.group(1), cur,
                                                    m.group(2),
                                                    m.group(3).strip()))
                    n += 1
        print("  narrowed #0x38 stores above: %d" % n)
    except Exception as e:
        print("  narrowed scan failed: %s" % e)
    print("")
    print("FASE6 PI-path RMW inventory (all on FIXED natural addrs, none redirectable):")
    print("  0x4e44 bl _raw_spin_trylock [x20,#0x00] lock->wait_lock (heap f_target)")
    print("  0x4f54 str w0,[x28,#0x40] waiter->prio (W stack, value=task->prio ~120)")
    print("  0x4f60 str x3,[x28,#0x48] waiter->deadline (W stack, value=deadline)")
    print("  0x4f64 bl rt_mutex_enqueue -> lock+0x08/+0x10 (heap, value=&W_waiter)")
    print("  0x4fac ldxr/add/stxr [x21=x19+0x28] owner+0x28 usage INC (value=+1, fixed)")
    print("  0x4fc8 bl _raw_spin_lock [x19+0x7d4] owner+0x7d4 pi_lock (fixed)")
    print("  verdict: no PI-path store takes a user-controlled dest; all dests")
    print("    derive from x20=lock (H16 value) or x28=waiter (stale slot itself)")
    print("    or x19=owner (O task). owner+0x28 INC cannot be steered to")
    print("    [W_waiter,#0x38]: base is O task_struct (heap), off fixed 0x28,")
    print("    value fixed +1. enqueue dests are lock+0x08/+0x10 (heap f_target),")
    print("    not W stack. waiter+0x40/+0x48 dests ARE W stack but off != 0x38")
    print("    and values are prio/deadline, not &f_alt. COMPOSITION REFUTED offline.")
    print("")
    print("FASE4 taint classes for every candidate above:")
    print("  H16.0: KERNEL_ONLY (birth, lock=pi_state->pi_mutex heap).")
    print("  poll table+0x38: KERNEL_POINTER_WITH_USER_CONTROLLED_BASE rejected:")
    print("    base is own stack (fixed), value is events|0x18 small int (not ptr).")
    print("  spill-search 87 window cands: all KERNEL_ONLY or int/32b/masked after")
    print("    review (see ghostlock-spill-search.md sec.6). 0 DIRECT_USER_POINTER")
    print("    at SP0-0x278 with 64b pointer value. => no FASE4 survivor.")
    print("")
    print("FASE7 alias: W FWRQ frame alive (W never returns, hrtimer only exit);")
    print("  no second writer maps that stack; occ/altocc waiters live on OTHER")
    print("  stacks, never referenced by W->pi_blocked_on. No union/container_of/")
    print("  wrapper alias stores waiter->lock after birth. NONE FOUND.")
    print("FASE8 async: signal (complete_signal str x19,[x24,#0x38] is siginfo, not")
    print("  waiter); timers/hrtimer/task_work/completion/workqueue stores target")
    print("  own structs (pool/work/timer), none takes waiter ptr. futex wake/")
    print("  requeue helpers never store waiter->lock. sched_setscheduler path only")
    print("  READS (H16.12). NONE FOUND.")
    print("")


def pi_source_chain():
    """H16 SOURCE CONTROL: pi_state->pi_mutex origin, writers, requeue rebind.

    OFFLINE_ONLY (build-aq/vmlinux + .src/linux-amlogic futex.c/rtmutex.c).
    Answers: futex target -> key -> pi_state -> pi_mutex -> waiter->lock,
    per-hop VA/insn/reg/offset/source/transform/lifetime/control, full
    pi_mutex writer inventory, target-derivation verdict, requeue/rebind
    verdict. Stock VAs slide by KASLR; offsets build-invariant.
    """
    print("=" * 72)
    print("H16 SOURCE CONTROL: pi_state->pi_mutex -> waiter->lock")
    print("EVIDENCE: OFFLINE_ONLY (build-aq/vmlinux + .src/linux-amlogic)")
    print("=" * 72)
    print("")
    print("S0 STRUCT (futex.c:197-213): struct futex_pi_state { list 0x00(16);")
    print("  pi_mutex 0x10(32); owner 0x30(8); refcount 0x38(4); key 0x40(16); }.")
    print("  pi_mutex is INLINE: &pi_state->pi_mutex == pi_state + 0x10 (LEA,")
    print("  never a stored pointer). No memory word holds the pointer itself.")
    print("")
    print("S1 FUTEX TARGET -> KEY (get_futex_key futex.c:498-531, PRIVATE fast):")
    print("  VA   : source get_futex_key (no single LEA, key built on stack)")
    print("  insn : key->private.mm = current->mm; key->private.address =")
    print("    page-aligned uaddr; key->both.offset = uaddr % PAGE_SIZE")
    print("  reg  : uaddr = x0 (syscall arg: &f_target / &f_alt / &f_chain)")
    print("  off  : key+0x00 offset field, key+0x08 mm, key+0x10 address")
    print("  src  : userspace uaddr choice (which futex) + current->mm")
    print("  xform: page-align mask only; distinct uaddrs -> distinct keys")
    print("  life : key on requeue/lookup stack frame (futex_requeue x29+0xc0/")
    print("    0xd8; futex_wait_requeue_pi key2 x29+off; futex_lock_pi x29+0xd0)")
    print("  ctrl : userspace picks WHICH futex, not key bytes directly.")
    print("  f_target vs f_alt: different u32 addrs, same mm -> keys differ in")
    print("    address word; hash buckets may collide but keys never equal")
    print("    (match_futex compares full key). OFFLINE_ONLY.")
    print("")
    print("S2 KEY -> PI_STATE (lookup, futex_requeue+proxy_trylock path):")
    print("  VA   : futex_requeue 0xffffff800913a8d8 bl futex_top_waiter")
    print("    + 0xffffff800913abe4 add x0,x0,#0x10 (see S3) + proxy_trylock")
    print("    -> futex_lock_pi_atomic 0xffffff80091397b4 bl futex_top_waiter")
    print("    -> attach_to_pi_state 0xffffff80091397c8 OR attach_to_pi_owner")
    print("    0xffffff8009139874 bl attach_to_pi_owner")
    print("  insn : match = futex_top_waiter(hb2,key2); if (match) attach_to_")
    print("    pi_state(uval, match->pi_state) else attach_to_pi_owner(uval,key2)")
    print("  reg  : key2 (x29 stack) -> hb2 -> match (x0) -> pi_state (x19/x20)")
    print("  off  : futex_q.pi_state at q+0x50 (str x0,[x26,#0x50] @0xabe0)")
    print("  src  : existing pi_state for that key (reuse) or fresh slab object")
    print("  xform: reuse = refcount inc + validation (TID match, refcount!=0);")
    print("    fresh = alloc + init_proxy_locked + key copy + owner bind")
    print("  life : pi_state refcount>0 from attach until last put_pi_state;")
    print("    GhostLock window holds refs (no teardown, fwake -EINVAL keeps")
    print("    W frame + pi_state alive). No free/reuse inside window.")
    print("  ctrl : userspace selects key (target futex) + uval TID (owner);")
    print("    cannot pick heap address. OFFLINE_ONLY.")
    print("")
    print("S3 PI_STATE -> PI_MUTEX (LEA, the H16 value source):")
    print("  VA   : 0xffffff8009139614 add x0,x20,#0x10 (attach_to_pi_owner,")
    print("    x20=pi_state -> x0=&pi_mutex, then bl rt_mutex_init_proxy_locked)")
    print("  VA   : 0xffffff800913abe4 add x0,x0,#0x10 (futex_requeue, x0=pi_state")
    print("    from [x29,#0xa8] -> x0=&pi_mutex, then bl start_proxy_lock @0xabe8)")
    print("  VA   : 0xffffff800913b1b8 / 0xb238 / 0xb2a0 add x0,x0,#0x10")
    print("    (futex_lock_pi, x0=q.pi_state from [x29,#0x120] -> timed/trylock/unlock)")
    print("  insn : add x0,xN,#0x10 (LEA pi_state+0x10, no load/store)")
    print("  reg  : xN=pi_state base (heap slab) -> x0=pi_mutex (heap+0x10)")
    print("  off  : +0x10 == offsetof(futex_pi_state, pi_mutex) (list_head 16B)")
    print("  src  : pi_state slab base; dst: rt_mutex *lock arg")
    print("  xform: constant +0x10 only; no key/owner/TID mixed in")
    print("  life : valid while pi_state refcount>0 (covers whole GhostLock win)")
    print("  ctrl : NONE beyond pi_state selection (S2); address = slab addr+0x10,")
    print("    learned not chosen. OFFLINE_ONLY.")
    print("")
    print("S4 PI_MUTEX -> WAITER->LOCK (H16 birth, task_blocks_on_rt_mutex):")
    print("  VA   : 0xffffff800910527c stp x20,x19,[x21,#0x30] (+0x54, base 0x5228)")
    print("  insn : stp x20,x19,[x21,#0x30] ([x21,#0x30]=task=x20, [x21,#0x38]=lock=x19)")
    print("  reg  : x19=lock (from S3 x0) -> [x21,#0x38]; x21=waiter (stack slot)")
    print("  off  : waiter+0x38 == offsetof(rt_mutex_waiter, lock)")
    print("  src  : x19 == &pi_state->pi_mutex (S3), task == blocked task")
    print("  xform: none (mov chain x0->x19 across start_proxy_lock->task_blocks)")
    print("  life : W waiter = FWRQ stack slot SP0-0x2b0 (x29+0x80, frame alive")
    print("    while W sleeps, hrtimer only exit); C waiter = LOCK_PI stack slot")
    print("  ctrl : userspace target choice flows through S1-S3 only; no direct")
    print("    value injection. H16.0 is the ONLY store (grep waiter->lock= 1 hit,")
    print("    rtmutex.c:998; binary 30/30 verify). OFFLINE_ONLY.")
    print("")
    print("WRITERS of pi_state->pi_mutex-as-pointer: ZERO (it is an LEA, not a")
    print("  stored word). Writers of pi_mutex CONTENTS (not the address, listed")
    print("  so they cannot be mistaken for source control):")
    print("  NATURAL_WRITER (address): H16.0 only (stp @0x527c, birth).")
    print("  CONTENT writers (lock fields, address unchanged): rt_mutex_init_")
    print("    proxy_locked @0x5828 (wait_lock/waiters/owner init); enqueue/")
    print("    dequeue (waiters rb + leftmost); trylock RMW (wait_lock);")
    print("    fixup_pi_state_owner (owner handoff, futex.c:2219, owner only);")
    print("    put_pi_state proxy_unlock on free. None writes waiter->lock.")
    print("  REUSE_WRITER: NONE (requeue start_proxy reuses the SAME pi_state for")
    print("    the requeued waiter = same birth path, not a rewrite of live H16).")
    print("  LIFETIME_WRITER: NONE (put/free/cache never touches waiter->lock;")
    print("    frame alive so no recycle inside window).")
    print("  CORRUPTION_ONLY: any post-birth store to [W_waiter,#0x38]; none found")
    print("    (3384 #0x38 stores / 202 subsys / 7 PI-adjacent all KERNEL_ONLY or")
    print("    small-int; see --h16-write). OFFLINE_ONLY.")
    print("")
    print("TARGET DERIVATION: pi_mutex address = f(target key). f_target key !=")
    print("  f_alt key (different uaddr, same mm) -> different pi_state objects ->")
    print("  different pi_mutex addrs (each base+0x10). No alias: hash collision")
    print("  still keys-compared (match_futex); bucket reuse never merges states.")
    print("  pi_state->key written once at creation (stp x0,x1,[x20,#0x40] + str")
    print("  x0,[x20,#0x50] @0x961c-0x9630 from key stack); NO updater exists")
    print("  (fixup updates owner only, futex.c:2219; requeue_futex updates q->key,")
    print("  never pi_state->key). Same pi_state cannot represent another target.")
    print("  OFFLINE_ONLY.")
    print("")
    print("REQUEUE REBIND: futex_requeue obtains pi_state for key2 BEFORE the loop")
    print("  (proxy_trylock_atomic/lookup_pi_state), then per-waiter: this->pi_state")
    print("  = pi_state (str @0xabe0) + start_proxy_lock(&pi_state->pi_mutex,")
    print("  this->rt_waiter, this->task) which births waiter->lock (H16.0). No")
    print("  second store updates waiter->lock after birth (binary 0x5400-0x554c")
    print("  remove_waiter has no str to +0x38; enqueue/dequeue never touch +0x38).")
    print("  Rollback (start_proxy EDEADLK -> remove_waiter) dequeues but leaves")
    print("  waiter->lock intact. PI->PI requeue rejected: futex_requeue loop bails")
    print("  -EINVAL if this->pi_state || !this->rt_waiter mismatch (futex.c:1920-")
    print("  1925); f_wait(non-PI)->f_target(PI) ok once, f_target(PI)->f_alt(PI)")
    print("  refused. So no f_target->f_alt stale without a fresh birth on a fresh")
    print("  waiter (different stack slot / different graph). Pointing CMP_REQUEUE")
    print("  at f_alt births H16=f_alt but moves the WHOLE graph (owner A, key")
    print("  f_alt), not H16 alone. OFFLINE_ONLY; hardware alt_only (f_alt occupied")
    print("  ignored, TIMEOUT) confirms the walk follows the birth value.")
    print("")
    print("VERDICT: H16 SOURCE CONTROL = NATURALLY IMPOSSIBLE (OFFLINE_ONLY for")
    print("  structure; HARDWARE_REFUTED for natural retarget via alt_only).")
    print("  Minimum to move H16 remains one durable 8B store [W_waiter,#0x38] =")
    print("  &f_alt.pi_mutex stable across H16.4 (0x52fc) + H16.7 (0x4df0/cmp 0x4df4)")
    print("  while the FWRQ frame is alive. No existing primitive satisfies")
    print("  dest+value (see --h16-write: 0 survivors).")
    print("")


def emit_chain():
    """EMIT validation ruler (FASE 13): what a future disclosed pointer must
    satisfy before it is called a leak. Read-only, touches no memory.

    For any candidate u64 value reaching userspace, the claim
    DIRECT_KERNEL_PTR is accepted only when all five hold:
      1. FIELD: which struct field produced it (name + offset);
      2. LOAD: which instruction loaded it (VA + mnemonic + operands);
      3. COPY: which instruction copied it out (copy_to_user/put_user VA);
      4. USER: where userspace received it (syscall + output buffer + width);
      5. MASK: which transform applied (none/%pK/hash/truncate) + object
         identity (emitted == independently inferred address of same object).
    Anything less is SINGLE_SOURCE. Index/user-echo/scalar outputs
    (binder ptr zeros, ashmem name, ion heap id) fail step 5 by
    construction and stay NO_POINTER/USER_ECHO/INDEX.

    EVIDENCE: OFFLINE_ONLY (ruler). Stock C1/C2/C3 outputs to date:
    all zeros/scalars/indices, zero kptr hits (see emit-census report).
    """
    print("=" * 72)
    print("EMIT -> POINTER validation ruler (read-only, FASE 13)")
    print("EVIDENCE: OFFLINE_ONLY (ruler) + HARDWARE_* (C1/C2/C3 outputs).")
    print("=" * 72)
    print("")
    print("To promote a candidate u64 to DIRECT_KERNEL_PTR, show:")
    print("  1. FIELD: struct + offset (e.g. rt_mutex_waiter.lock +0x38)")
    print("  2. LOAD : VA + insn (e.g. 0x...4df0 ldr x0,[x28,#0x38])")
    print("  3. COPY : VA + bl copy_to_user/put_user (e.g. binder.c:4829)")
    print("  4. USER : syscall + buffer + width (e.g. ioctl BINDER_GET_NODE_DEBUG_INFO, 8B)")
    print("  5. MASK : transform (none vs %pK vs hash vs truncate) + identity")
    print("     (emitted == independently inferred address, two configs/paths)")
    print("")
    print("Stock scoreboard (this phase, shell, read-only):")
    print("  C1 binder VERSION=8 scalar; NODE_DEBUG ptr=0 cookie=0 x2 stable")
    print("     -> USER_ECHO zeros. HARDWARE_REPRODUCED (values).")
    print("  C2 ashmem GET_SIZE=0 scalar; GET_NAME=\"dev/ashmem\" user-string")
    print("     -> SCALAR/USER_ECHO. HARDWARE_REPRODUCED (values).")
    print("  C3 ion HEAP_QUERY cnt=3 scalar; heaps codec_mm_ion/5/5,")
    print("     cma_ion/4/4, vmalloc_ion/0/0 (rc=-EINVAL quirk, buffer filled)")
    print("     -> INDEX+SCALAR. HARDWARE_REPRODUCED (values).")
    print("  is_kptr hits across all C1/C2/C3 outputs: 0.")
    print("")
    print("Single next bottleneck: one read-only kernel-pointer source for")
    print("EITHER address that survives stock masking (unaudited /dev corners")
    print("past C1/C2/C3, or deeper EMIT walk past BFS depth 3).")
    print("")


def disclosure_chain():
    """READ/DISCLOSE consumer validation: disclosed addr -> known consumer.

    H16 consumer: rt_mutex_adjust_prio_chain H16.7
      0xffffff8009104df0 ldr x0,[x28,#0x38] + 0x4df4 cmp x20,x0 / b.ne out.
    Any disclosed H16_addr must equal the x28 base the walk loads here;
    any disclosed F_alt_addr must equal the x0 value compared against x20
    (next_lock) at +0x4df4. Until both disclosures are HARDWARE_REPRODUCED
    this mapping is a read-only ruler, not a write plan.

    FASE 12: DISCLOSED TARGET -> KNOWN CONSUMER (OFFLINE_ONLY until stock
    addresses exist). No memory is touched by this function.
    """
    print("=" * 72)
    print("DISCLOSURE -> CONSUMER validation (read-only ruler)")
    print("EVIDENCE: OFFLINE_ONLY (build-aq/vmlinux). No stock addresses yet.")
    print("=" * 72)
    print("")
    print("H16_addr (disclosed stack slot) must satisfy:")
    print("  H16_addr == x28 at 0xffffff8009104df0 (walk re-read base)")
    print("  [H16_addr] == x0 after ldr, == x20 (next_lock) at 0x4df4 cmp")
    print("  x20 itself == [stale waiter+0x38] read at H16.4 (0x52fc -> x25)")
    print("  both reads hit the SAME 8 bytes: stability across H16.4+H16.7")
    print("  is the acceptance test (mismatch bails at +0x4df8).")
    print("")
    print("F_alt_addr (disclosed heap rt_mutex) must satisfy:")
    print("  F_alt_addr == &f_alt.pi_mutex == pi_state_alt + 0x10 (LEA S3)")
    print("  [F_alt_addr+0x00] = free wait_lock (trylock at +0x4e44 succeeds)")
    print("  [F_alt_addr+0x10] = occ waiter (leftmost gate H16 passes)")
    print("  [F_alt_addr+0x18] = owner A (non-NULL, H11 passes)")
    print("  top->lock at [leftmost+0x38] == F_alt_addr (BUG_ON H18/H19 passes)")
    print("")
    print("Cross-check rule: H16_addr is validated by the STACK page temps")
    print("  (same page/SP base as FWRQ, dist 0); F_alt_addr is validated by")
    print("  TWO independent paths when possible (disclosure + occupancy")
    print("  verdict alt_base TIMEOUT proves the object is a valid contended")
    print("  rt_mutex). Single-source disclosure stays SINGLE_SOURCE.")
    print("")
    print("Future WRITE8(H16_addr, F_alt_addr) spec (NOT implemented):")
    print("  size 8B single word; align 8; H16 frame alive (W in FWRQ);")
    print("  value learned (both addrs disclosed), never guessed; window")
    print("  between trigger return and consumer walk; consumer stays")
    print("  FUTEX_LOCK_PI(f_chain) FULL. The harness accepts both values")
    print("  as parameters/telemetry only (see ghostlock_chain disclose modes).")
    print("")


def target_chain():
    """H16 TARGET ruler (FASE 7): bidirectional dataflow acceptance test.

    A candidate store passes only when BOTH hold:
      DESTINATION TAINT (store <- pointer base <- origin):
        EXACT_H16      delta==0, width 8, base x29/sp on same-task frame
        H16_RELATIVE   abs(delta)<=0x40, width 8 (geometry only, not success)
        STACK_SAME_PAGE abs(delta)<=0x400 (same page, not H16)
        UNRELATED      everything else (REJECT)
      VALUE TAINT (store <- value reg <- origin):
        TARGET_RT_MUTEX      8B kptr from pi_state->pi_mutex/+0x10 LEA/rt_mutex
        OTHER_KERNEL_POINTER 8B kptr of any other origin (task/heap/code/stack)
        USER_POINTER         8B user-derived (needs a leak; NONE AVAILABLE)
        INTEGER              scalar/zero/derived-int/str Wn (REJECT for retarget)
        UNKNOWN              untainted/unknown return (REJECT, not a pointer)
    Only EXACT_H16 + (TARGET_RT_MUTEX or OTHER_KERNEL_POINTER) continues
    to a stock geometry probe, and only with a legitimate kernel pointer,
    single-word, frame-alive, consumer FUTEX_LOCK_PI(f_chain).
    Paired tool: ghostlock_h16_target_search.py prints both classes per
    candidate. EVIDENCE: OFFLINE_ONLY (ruler). Current scoreboard:
    33 EXACT_H16 (9 KPTR, 0 UPTR, 2 INTEGER, 1 DERIVED, 21 UNKNOWN),
    0 TARGET_RT_MUTEX at EXACT (audited surface, depth<=3).
    """
    print("=" * 72)
    print("H16 TARGET ruler: destination x value (read-only, FASE 7)")
    print("EVIDENCE: OFFLINE_ONLY (ruler). Stock geometry INCONCLUSIVE.")
    print("=" * 72)
    print("")
    print("DESTINATION TAINT (store <- base <- origin):")
    print("  EXACT_H16       delta==0, w==8, x29/sp, same-task frame (ONLY pass)")
    print("  H16_RELATIVE    abs(delta)<=0x40, w==8 (geometry probe only)")
    print("  STACK_SAME_PAGE abs(delta)<=0x400 (same page, not H16)")
    print("  UNRELATED       else (REJECT)")
    print("")
    print("VALUE TAINT (store <- reg <- origin):")
    print("  TARGET_RT_MUTEX     pi_state->pi_mutex/+0x10/rt_mutex 8B kptr")
    print("  OTHER_KERNEL_POINTER task/heap/code/stack 8B kptr (geometry/value proof first)")
    print("  USER_POINTER        user-derived 8B (needs leak; NONE AVAILABLE)")
    print("  INTEGER             scalar/zero/derived/str Wn (REJECT for retarget)")
    print("  UNKNOWN             untainted/unknown (REJECT, not a pointer)")
    print("")
    print("GATE: EXACT_H16 + (TARGET_RT_MUTEX|OTHER_KERNEL_POINTER) only.")
    print("H16.4 0x52fc (x25) and H16.7 0x4df0/cmp 0x4df4 must read the SAME")
    print("8 bytes; mismatch bails at +0x4df8. Poll table/current spills are")
    print("H16_RELATIVE (+8/+20 lab) with OTHER_KERNEL_POINTER (task/code):")
    print("geometry probe ONLY, never a retarget value.")
    print("")


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__ + "\nadd --graph for the curated chain graph, "
                 "--verify to check VAs against the binary, "
                 "--poll for the poll stack chain, "
                 "--predicate for the post-rollback stock prediction, "
                 "--heap-chain for post-lock per-hop dataflow, "
                 "--natural for the unstamped natural waiter path, "
                 "--h16 for every waiter->lock load/store + dataflow, "
                  "--h16-write for FASE1 table + 8B-store scan, "
                  "--pi-source for pi_state->pi_mutex origin + rebind verdict, "
                  "--disclosure for disclosed-target -> known-consumer ruler, "
                  "--emit for emit -> pointer validation ruler (FASE 13), "
                  "--target for H16 destination+value taint ruler (FASE 7)")
    vmlinux = sys.argv[1]
    args = sys.argv[2:]
    if args[0] == "--graph":
        graph(vmlinux)
        return
    if args[0] == "--verify":
        raise SystemExit(verify(vmlinux))
    if args[0] == "--poll":
        poll_chain(vmlinux)
        return
    if args[0] == "--natural":
        natural_path(vmlinux)
        return
    if args[0] == "--predicate":
        stock_predicate()
        return
    if args[0] == "--heap-chain":
        heap_chain()
        return
    if args[0] == "--h16":
        h16_chain()
        return
    if args[0] == "--h16-write":
        h16_write_surface(vmlinux)
        return
    if args[0] in ("--pi-source", "--h16-source"):
        pi_source_chain()
        return
    if args[0] == "--disclosure":
        disclosure_chain()
        return
    if args[0] == "--emit":
        emit_chain()
        return
    if args[0] == "--target":
        target_chain()
        return
    if args[0] == "--all":
        for imm, label in ((PI_BLOCKED_ON, "pi_blocked_on"),
                           (PI_WAITERS, "pi_waiters"),
                           (PI_WAITERS_LEFT, "pi_waiters_leftmost")):
            print("\n### every function touching task+0x%x (%s)" % (imm, label))
            for sym, hits in sorted(scan_all(vmlinux, imm).items()):
                print("  %-40s %s" % (sym, "; ".join(
                    "%s %s @0x%x" % (m, r, a) for a, m, r in hits)))
        return
    funcs = disassemble(vmlinux, args)
    for sym in args:
        chain(funcs, sym)


if __name__ == "__main__":
    main()