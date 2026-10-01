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


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__ + "\nadd --graph for the curated chain graph, "
                 "--verify to check VAs against the binary")
    vmlinux = sys.argv[1]
    args = sys.argv[2:]
    if args[0] == "--graph":
        graph(vmlinux)
        return
    if args[0] == "--verify":
        raise SystemExit(verify(vmlinux))
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