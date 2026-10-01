#!/usr/bin/env python3
"""ghostlock_spill_search.py - find user-pointer spills reaching SP0-0x278.

SP0 = SP at SyS_ entry (same thread/stack page => same absolute addr).
Target: waiter->lock slot = SP0-0x278 (window SP0-0x288..SP0-0x268).

Method:
  1. disassemble functions (llvm-objdump), parse frame size from first
     sub/stp, parse stores (str/stp/stur), parse mov/add/ldr dataflow.
  2. forward taint: x0-x5 = DIRECT_USER_ARG at function entry (withheld per
     callsite when analyzing callees in chain context).
  3. call graph via bl targets; for each SyS_ root BFS to depth 4,
     cumulative frame sum; each store normalized to SP0-relative:
       dest = SP0 - sumF + local_off   (local_off = x29/sp-relative imm)
     stp writes two consecutive 8B words.
  4. filter dest in window, classify origin, print dataflow + verdict.

Usage:
  spill_search.py <vmlinux> --frames              # all SyS_ frames sorted
  spill_search.py <vmlinux> --deep                # all funcs w/ frame>=0x100 sorted
  spill_search.py <vmlinux> --chain SyS_poll      # call chain + stores near target
  spill_search.py <vmlinux> --all                 # every SyS_ root, BFS, candidates
  spill_search.py <vmlinux> --func <fn>           # intra-function taint + stores
  spill_search.py <vmlinux> --verify              # re-check curated candidates
"""
import re
import subprocess
import sys

OD = ("/home/erick/Android/Sdk/ndk/29.0.14206865/toolchains/llvm/"
      "prebuilt/linux-x86_64/bin/llvm-objdump")
NM = ("/home/erick/Android/Sdk/ndk/29.0.14206865/toolchains/llvm/"
      "prebuilt/linux-x86_64/bin/llvm-nm")

TARGET = 0x278
WIN_LO, WIN_HI = 0x268, 0x288  # dest in [SP0-WIN_HI, SP0-WIN_LO]

_disasm_cache = {}
_frame_cache = {}
_full_cache = None
FULL_ASM = "/tmp/opencode/aq_full.asm"


def _load_full():
    global _full_cache
    if _full_cache is not None:
        return _full_cache
    import os
    if not os.path.exists(FULL_ASM):
        return None
    funcs, cur = {}, None
    with open(FULL_ASM) as f:
        for line in f:
            m = re.match(r"^([0-9a-f]{16}) <([^>]+)>:", line)
            if m:
                cur = m.group(2)
                funcs[cur] = []
                continue
            m = re.match(r"^([0-9a-f]{16}):\s+(\S+)\s+(.*)$", line)
            if m and cur:
                funcs[cur].append((int(m.group(1), 16), m.group(2),
                                   m.group(3).strip()))
    _full_cache = funcs
    return funcs


def run(args, timeout=180):
    return subprocess.run(args, capture_output=True, text=True,
                          timeout=timeout).stdout


def disasm(vmlinux, syms):
    full = _load_full()
    if full is not None:
        out = {}
        for s in syms:
            if s in full:
                out[s] = full[s]
                continue
            alt = None
            if s.startswith("SyS_"):
                alt = "sys_" + s[4:]
            elif s.startswith("sys_"):
                alt = "SyS_" + s[4:]
            if alt and alt in full:
                out[s] = full[alt]
        return out
    key = tuple(sorted(syms))
    if key in _disasm_cache:
        return _disasm_cache[key]
    out = run([OD, "-d", "--no-show-raw-insn",
               "--disassemble-symbols=" + ",".join(syms), vmlinux])
    funcs, cur = {}, None
    for line in out.splitlines():
        m = re.match(r"^([0-9a-f]{16}) <([^>]+)>:", line)
        if m:
            cur = m.group(2)
            funcs[cur] = []
            continue
        m = re.match(r"^([0-9a-f]{16}):\s+(\S+)\s+(.*)$", line)
        if m and cur:
            funcs[cur].append((int(m.group(1), 16), m.group(2),
                               m.group(3).strip()))
    _disasm_cache[key] = funcs
    return funcs


def all_syms(vmlinux):
    out = run([NM, vmlinux], timeout=120)
    syms = []
    for line in out.splitlines():
        m = re.match(r"^([0-9a-f]+) [tT] (\S+)", line)
        if m:
            syms.append(m.group(2))
    return syms


def frame_of(insns):
    """frame size from first sub/stp. returns (size, kind)."""
    if not insns:
        return (0, "none")
    for addr, mnem, rest in insns[:4]:
        m = re.search(r"sp,\s*sp,\s*#(-?0x[0-9a-f]+|\d+)", rest)
        if m and mnem == "sub":
            return (int(m.group(1), 0), "sub")
        m = re.search(r"\[sp,\s*#(-?0x[0-9a-f]+|\d+)\]!", rest)
        if m and mnem in ("stp", "str"):
            return (abs(int(m.group(1), 0)), "stp!/str!")
    return (0, "none")


def get_frame(vmlinux, sym):
    if sym in _frame_cache:
        return _frame_cache[sym]
    f = disasm(vmlinux, [sym])
    sz, kind = frame_of(f.get(sym, []))
    _frame_cache[sym] = sz
    return sz


# ---- intra-function taint ----

REG = r"[xw](?:\d+|zr|sp)"


def reg_base(r):
    r = r.strip()
    if r.startswith("w"):
        n = r[1:]
        return ("x" + n) if n not in ("zr", "sp") else r
    return r


def parse_mem(op):
    """'[x29, #0x88]' -> (base, off). '[sp]' -> (base, 0). None if not mem."""
    m = re.search(r"\[\s*(\w+)(?:\s*,\s*#(0x[0-9a-f]+|\d+))?\s*\]", op)
    if not m:
        return None
    base = m.group(1)
    off = int(m.group(2), 0) if m.group(2) else 0
    return (base, off)


def analyze_func(insns, entry_taint=None):
    """Forward taint over one function body.

    entry_taint: {xreg: (origin, detail)} at entry. Default x0-x5 DIRECT.
    Returns (stores, callsites):
      stores: list of dict(addr,mnem,dst_reg,base,off,origin,detail,transform)
      callsites: list of dict(addr,target,argsnap {x0..x7:(origin,detail)})
    Taint values: (origin, detail) where origin in DIRECT_USER_ARG,
    USER_BUFFER_DERIVED, COPY_FROM_USER, MOV_DERIVED, ADD_DERIVED, LOAD_DERIVED,
    RETURN_UNKNOWN, STACK_SPILL.
    """
    if entry_taint is None:
        entry_taint = {("x%d" % i): ("DIRECT_USER_ARG", "syscall arg %d" % i)
                       for i in range(6)}
    taint = dict(entry_taint)
    # stack slots holding tainted values: (base,off)->(origin,detail,srcreg)
    # base normalized: x29 or sp (sp==x29 after prologue in these funcs)
    mem = {}
    stores = []
    callsites = []
    for addr, mnem, rest in insns:
        ops = [o.strip() for o in rest.split(",")]
        if mnem in ("mov", "movz", "movn", "movk", "movn"):
            if len(ops) >= 2:
                d, s = reg_base(ops[0].split()[0] if " " in ops[0] else ops[0]), ops[1]
                # mov Xd, Xm
                m = re.match(r"^([xw]\d+)$", s)
                if m:
                    s = reg_base(m.group(1))
                    if s in taint:
                        o, dt = taint[s]
                        taint[d] = (o, dt + " >mov> " + d)
                    elif d in taint:
                        del taint[d]
                else:
                    # immediate: kills taint (NULL/small const)
                    d2 = reg_base(ops[0])
                    if d2 in taint:
                        del taint[d2]
        elif mnem in ("add", "sub", "lsl", "lsr", "and", "orr", "bic", "eor",
                      "sxtw", "uxtw", "sbfiz", "ubfiz", "asr", "uxtb", "uxth",
                      "sxtb", "sxth", "csel", "csinc", "csinv", "csneg",
                      "cset", "csetm", "lsr", "ror", "adc", "sbc", "ngc",
                      "smull", "umull", "msub", "madd", "udiv", "sdiv",
                      "mul", "lslv", "lsrv", "asrv", "rorv", "extr",
                      "ubfx", "sbfx", "bfxil", "bfi", "sbfm", "ubfm"):
            if len(ops) >= 2:
                d = reg_base(ops[0].split()[0])
                if not re.match(r"^[xw]\d+$", ops[0].split()[0]) and \
                        not re.match(r"^sp$", ops[0].split()[0]):
                    pass  # dest not a plain reg (e.g. cset flag-only); skip
                else:
                    d = reg_base(ops[0].split()[0])
                    srcs = []
                    for o in ops[1:]:
                        mm = re.match(r"^([xw]\d+|sp|xzr|wzr)", o)
                        if mm:
                            srcs.append(reg_base(mm.group(1)))
                    hit = [(s, taint[s]) for s in srcs if s in taint]
                    if hit:
                        s, (o, dt) = hit[0]
                        taint[d] = (o, dt + " >%s> %s" % (mnem, d))
                    # else: untainted computation; loads never kill and
                    # neither do ALU ops here (conservative: keep old taint?
                    # NO - ALU overwrites kill. but we cannot tell dest-write
                    # from flag-only; cset always writes. kill on no-hit:)
                    elif d in taint and d not in srcs:
                        # overwritten by untainted computation -> kill, EXCEPT
                        # keep it: path-insensitivity means the tainted value
                        # may still be live on the taken path. false positives
                        # are manually filtered; false negatives are not.
                        pass
        elif mnem in ("ldr", "ldrh", "ldrb", "ldrsw", "ldp", "ldur"):
            if mnem == "ldp" and len(ops) >= 3:
                d1 = reg_base(ops[0])
                d2 = reg_base(ops[1])
                mm = parse_mem(rest)
                if mm:
                    base, off = mm
                    for i, d in enumerate((d1, d2)):
                        o2 = off + i * 8
                        if (base, o2) in mem:
                            o, dt = mem[(base, o2)]
                            if o is not None:
                                taint[d] = (o, dt + " >ldp> " + d)
                        elif base in taint and base not in ("x29", "sp"):
                            o, dt = taint[base]
                            taint[d] = ("USER_BUFFER_DERIVED",
                                        dt + " >ldr [%s+%x]> %s" % (base, o2, d))
                        # loads never kill: epilogue restores on a not-taken
                        # path must not erase taint (false negatives cost more;
                        # candidates are manually verified anyway)
            else:
                d = reg_base(ops[0])
                mm = parse_mem(rest)
                if mm:
                    base, off = mm
                    if (base, off) in mem:
                        o, dt = mem[(base, off)]
                        if o is not None:
                            taint[d] = (o, dt + " >ldr> " + d)
                    elif base in taint and base not in ("x29", "sp"):
                        o, dt = taint[base]
                        # ldr from tainted pointer = user buffer derived
                        taint[d] = ("USER_BUFFER_DERIVED",
                                    dt + " >ldr [%s+%x]> %s" % (base, off, d))
                    # (no kill on unknown load: see above)
        elif mnem in ("str", "strb", "strh", "stur", "stp"):
            if mnem == "stp" and len(ops) >= 3:
                r1 = reg_base(ops[0])
                r2 = reg_base(ops[1])
                mm = parse_mem(rest)
                if mm:
                    base, off = mm
                    for i, r in enumerate((r1, r2)):
                        o2 = off + i * 8
                        if r in taint:
                            o, dt = taint[r]
                            stores.append(dict(addr=addr, mnem="stp[%d]" % i,
                                               src=r, base=base, off=o2,
                                               origin=o, detail=dt,
                                               transform="pair"))
                            if base in ("x29", "sp"):
                                mem[(base, o2)] = (o, dt)
                        else:
                            if (base, o2) in mem:
                                del mem[(base, o2)]
            else:
                s = reg_base(ops[0]) if ops else "?"
                mm = parse_mem(rest)
                if mm and re.match(r"^[xw]\d+$", s):
                    base, off = mm
                    if s in taint:
                        o, dt = taint[s]
                        tr = "direct" if ">" not in dt else dt.split(">")[-1]
                        stores.append(dict(addr=addr, mnem=mnem, src=s,
                                           base=base, off=off, origin=o,
                                           detail=dt, transform=tr))
                        if base in ("x29", "sp"):
                            mem[(base, off)] = (o, dt)
                    else:
                        if (base, off) in mem:
                            del mem[(base, off)]
        elif mnem == "bl":
            m = re.search(r"<([^>]+)>", rest)
            tgt = m.group(1) if m else rest.split()[-1]
            snap = {}
            for i in range(8):
                r = "x%d" % i
                if r in taint:
                    snap[r] = taint[r]
            callsites.append(dict(addr=addr, target=tgt, snap=snap))
            # return value: kill x0 taint unless callee known to return tainted?
            # conservative: x0 becomes RETURN_UNKNOWN (untainted for our filter)
            if "x0" in taint:
                del taint["x0"]
            # clobber x8-x15? keep simple: they rarely carry args across bl
        elif mnem in ("blx", "blr"):
            snap = {}
            for i in range(8):
                r = "x%d" % i
                if r in taint:
                    snap[r] = taint[r]
            callsites.append(dict(addr=addr, target="INDIRECT:" + rest,
                                  snap=snap))
            if "x0" in taint:
                del taint["x0"]
    return (stores, callsites)


def callees_of(vmlinux, sym):
    f = disasm(vmlinux, [sym])
    insns = f.get(sym, [])
    _, cs = analyze_func(insns)
    out = []
    for c in cs:
        t = c["target"]
        # skip instrumentation
        if t in ("_mcount",):
            continue
        out.append(c)
    return out


def chain_search(vmlinux, root, max_depth=3):
    """BFS from root. Returns list of (path, sumF, store, local_off)."""
    frames = {}

    def fr(s):
        if s not in frames:
            frames[s] = get_frame(vmlinux, s)
        return frames[s]

    fr(root)
    # queue: (func, path, sumF_before, snap_entry)
    # snap_entry maps x-regs at func entry
    results = []
    visited = set()
    queue = [(root, [root], 0, None)]
    while queue:
        func, path, sum_before, entry = queue.pop(0)
        if len(path) > max_depth + 1:
            continue
        f = disasm(vmlinux, [func])
        insns = f.get(func, [])
        if not insns:
            continue
        F = fr(func)
        sum_incl = sum_before + F
        if entry is None:
            stores, calls = analyze_func(insns)
        else:
            stores, calls = analyze_func(insns, entry_taint=entry)
        for s in stores:
            if s["base"] not in ("x29", "sp"):
                continue
            dest_rel = sum_incl - s["off"]  # SP0 - dest = sumF - off
            # dest = SP0 - dest_rel
            s2 = dict(s)
            s2["path"] = list(path)
            s2["func"] = func
            s2["sumF"] = sum_incl
            s2["dest_rel"] = dest_rel
            results.append(s2)
        if len(path) <= max_depth:
            for c in calls:
                t = c["target"]
                if t.startswith("INDIRECT"):
                    continue
                # map callsite x0-x7 snapshot to callee entry
                snap = c["snap"]
                if t in visited or any(q[0] == t for q in queue):
                    continue
                visited.add(t)
                queue.append((t, path + [t], sum_incl, dict(snap) if snap else {}))
    return results


def fmt_rel(r):
    return "SP0-0x%x" % r if r >= 0 else "SP0+0x%x" % (-r)


def verdict_class(origin):
    if origin == "DIRECT_USER_ARG":
        return "KEEP"
    if origin in ("USER_BUFFER_DERIVED", "COPY_FROM_USER"):
        return "KEEP"
    return "DROP"


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    vmlinux = sys.argv[1]
    mode = sys.argv[2]
    if mode == "--frames":
        syms = [s for s in all_syms(vmlinux) if s.startswith("SyS_")]
        rows = []
        missing = [s for s in syms if s not in _disasm_cache]
        # batch disasm in chunks
        for i in range(0, len(syms), 64):
            d = disasm(vmlinux, syms[i:i + 64])
            for s, ins in d.items():
                sz, _ = frame_of(ins)
                rows.append((sz, s))
        rows.sort(reverse=True)
        print("SyS_ frames (top 60 by size):")
        for sz, s in rows[:60]:
            print("  0x%-4x %s" % (sz, s))
        print("total SyS_: %d" % len(rows))
    elif mode == "--deep":
        syms = all_syms(vmlinux)
        # only functions, batch through objdump full? use per-chunk
        rows = []
        for i in range(0, len(syms), 128):
            d = disasm(vmlinux, syms[i:i + 128])
            for s, ins in d.items():
                sz, _ = frame_of(ins)
                if sz >= 0x100:
                    rows.append((sz, s))
        rows.sort(reverse=True)
        print("functions with frame >= 0x100 (top 80):")
        for sz, s in rows[:80]:
            print("  0x%-4x %s" % (sz, s))
        print("count>=0x100: %d" % len(rows))
    elif mode == "--func":
        fn = sys.argv[3]
        f = disasm(vmlinux, [fn])
        ins = f.get(fn, [])
        sz, kind = frame_of(ins)
        print("%s frame=0x%x (%s) n_insn=%d" % (fn, sz, kind, len(ins)))
        stores, calls = analyze_func(ins)
        print("--- tainted stores (all stack, any depth) ---")
        for s in stores:
            if s["base"] in ("x29", "sp"):
                print("  0x%x: %s %s,[%s,#0x%x]  src=%s origin=%s\n"
                      "      detail: %s" %
                      (s["addr"], s["mnem"], s["src"], s["base"], s["off"],
                       s["src"], s["origin"], s["detail"]))
        print("--- calls with tainted args ---")
        for c in calls:
            if c["snap"]:
                print("  0x%x: bl %s  args=%s" %
                      (c["addr"], c["target"],
                       ", ".join("%s=%s" % (k, v[0]) for k, v in c["snap"].items())))
    elif mode == "--chain":
        root = sys.argv[3]
        depth = int(sys.argv[4]) if len(sys.argv) > 4 else 3
        res = chain_search(vmlinux, root, max_depth=depth)
        print("=" * 72)
        print("CHAIN %s depth<=%d: %d tainted stack stores" % (root, depth, len(res)))
        print("target window: [%s .. %s]" %
              (fmt_rel(WIN_HI), fmt_rel(WIN_LO)))
        print("=" * 72)
        near = [r for r in res
                if WIN_LO - 0x40 <= r["dest_rel"] <= WIN_HI + 0x40]
        print("--- stores within +-0x40 of window: %d ---" % len(near))
        for r in sorted(near, key=lambda x: abs(x["dest_rel"] - TARGET)):
            d = abs(r["dest_rel"] - TARGET)
            mark = "HIT" if WIN_LO <= r["dest_rel"] <= WIN_HI else "near+%x" % d
            print("\n[%s] %s 0x%x: %s %s,[%s,#0x%x] -> %s (sumF=0x%x path=%s)" %
                  (mark, r["func"], r["addr"], r["mnem"], r["src"],
                   r["base"], r["off"], fmt_rel(r["dest_rel"]), r["sumF"],
                   ">".join(r["path"])))
            print("  origin=%s\n  dataflow: %s" % (r["origin"], r["detail"]))
        # also show cumulative frames along top path
        print("\n--- frame sums along first-visit paths ---")
        seen = {}
        for r in res:
            p = ">".join(r["path"])
            if p not in seen:
                seen[p] = r["sumF"]
        for p, s in sorted(seen.items(), key=lambda kv: kv[1], reverse=True)[:20]:
            print("  sumF=0x%-4x %s" % (s, p))
    elif mode == "--all":
        syms = [s for s in all_syms(vmlinux) if s.startswith("SyS_")]
        print("scanning %d SyS_ roots (depth 3)..." % len(syms))
        hits = []
        for i, s in enumerate(syms):
            try:
                res = chain_search(vmlinux, s, max_depth=3)
            except Exception as e:
                print("  %s: ERROR %s" % (s, e))
                continue
            for r in res:
                if not (WIN_LO - 0x10 <= r["dest_rel"] <= WIN_HI + 0x10):
                    continue
                if r["origin"] not in ("DIRECT_USER_ARG", "USER_BUFFER_DERIVED",
                                       "COPY_FROM_USER"):
                    continue
                hits.append((s, r))
        print("=" * 72)
        print("CANDIDATES in [SP0-0x%x..SP0-0x%x] with user origin: %d" %
              (WIN_HI, WIN_LO, len(hits)))
        for s, r in sorted(hits, key=lambda x: abs(x[1]["dest_rel"] - TARGET)):
            print("\nCANDIDATE root=%s func=%s 0x%x: %s %s,[%s,#0x%x] -> %s "
                  "(sumF=0x%x)" %
                  (s, r["func"], r["addr"], r["mnem"], r["src"], r["base"],
                   r["off"], fmt_rel(r["dest_rel"]), r["sumF"]))
            print("  path: %s" % ">".join(r["path"]))
            print("  origin=%s\n  dataflow: %s" % (r["origin"], r["detail"]))
    elif mode == "--ioctl":
        # fixed chain SyS_ioctl>do_vfs_ioctl>vfs_ioctl>VENDOR (last hop is the
        # indirect f_op->unlocked_ioctl call). vendor entry: x0=file (kernel),
        # x1=cmd (user int), x2=arg (USER POINTER, fully controlled).
        vendor = sys.argv[3]
        chain = ["SyS_ioctl", "do_vfs_ioctl", "vfs_ioctl", vendor]
        sumF = 0
        entry = None
        print("=" * 72)
        print("IOCTL CHAIN -> %s  target window [%s..%s]" %
              (vendor, fmt_rel(WIN_HI), fmt_rel(WIN_LO)))
        for fn in chain:
            f = disasm(vmlinux, [fn])
            ins = f.get(fn, [])
            F = frame_of(ins)[0]
            if fn == vendor:
                entry = {"x1": ("DIRECT_USER_ARG", "ioctl cmd (int)"),
                         "x2": ("DIRECT_USER_ARG", "ioctl arg (user pointer)")}
            stores, calls = analyze_func(ins, entry_taint=entry)
            # next entry: propagate tainted x0-x2 through the direct call
            # (do_vfs_ioctl passes filp/cmd/arg down; approximate: keep x1,x2)
            entry = {}
            # find the bl to next in chain for precise snap
            for c in calls:
                if c["target"] == chain[chain.index(fn) + 1] if chain.index(fn) + 1 < len(chain) else None:
                    entry = dict(c["snap"])
                    break
            if not entry:
                # fallback: x1,x2 stay user-controlled down the ioctl chain
                entry = {"x1": ("DIRECT_USER_ARG", "cmd down"),
                         "x2": ("DIRECT_USER_ARG", "arg down")}
            sumF += F
            print("--- %s frame=0x%x cum=0x%x nstores=%d" % (fn, F, sumF, len(stores)))
            for s in stores:
                if s["base"] not in ("x29", "sp"):
                    continue
                rel = sumF - s["off"]
                mark = ""
                if WIN_LO <= rel <= WIN_HI:
                    mark = "  <<< HIT"
                elif WIN_LO - 0x10 <= rel <= WIN_HI + 0x10:
                    mark = "  <<< near"
                print("  0x%x: %s %s,[%s,#0x%x] -> %s origin=%s%s" %
                      (s["addr"], s["mnem"], s["src"], s["base"], s["off"],
                       fmt_rel(rel), s["origin"], mark))
                if mark:
                    print("      dataflow: %s" % s["detail"])
        print("=" * 72)
    elif mode == "--verify":
        # curated: re-check exact VAs claimed in report
        checks = [
            ("do_sys_poll", 0xffffff8009230bb8, "stp"),
            ("do_sys_poll", 0xffffff8009230bc8, "str"),
            ("do_sys_poll", 0xffffff8009230bd0, "str"),
        ]
        for sym, va, want in checks:
            f = disasm(vmlinux, [sym])
            hit = [x for x in f.get(sym, []) if x[0] == va]
            if not hit:
                print("MISS 0x%x %s (no insn)" % (va, sym))
            else:
                print("OK   0x%x %s: %s %s (want %s)" %
                      (va, sym, hit[0][1], hit[0][2][:50], want))
    else:
        sys.exit("unknown mode: %s" % mode)


if __name__ == "__main__":
    main()
