#!/usr/bin/env python3
"""ghostlock_h16_search.py - stock-relative targeted stack rewrite search for H16.

H16 = [W_waiter + 0x38] = waiter->lock, 8 bytes, born once via
task_blocks_on_rt_mutex (pi_state->pi_mutex) as &f_target.pi_mutex.

This tool replaces the lab-absolute spill search (SP0-0x278) with a
stock-relative search:

  dest_rel = SP0 - sum(frames on call path) + local_off
  delta    = dest_rel - H16_REL

H16_REL defaults to 0x290 (stock conjecture: rt_waiter = SP0-0x2c8,
waiter->lock = SP0-0x290). Use --h16 to override (--lab selects 0x278
for comparison with the old search).

LAB != STOCK: every VA/frame below is OFFLINE_ONLY (build-aq/vmlinux).
Stock geometry is INCONCLUSIVE until probed on PI.2055.

Value classes (FASE 4), priority KERNEL_POINTER:
  KERNEL_POINTER, USER_POINTER, INTEGER, KERNEL_DERIVED_INTEGER, UNKNOWN

A store is a HIT only if: 8 bytes, delta == 0, value class can carry an
rt_mutex * (KERNEL_POINTER preferred, USER_POINTER needs a leak).
Window +-0x40 is listed for geometry, not accepted as success.

Usage:
  h16_search.py <vmlinux> --frames
  h16_search.py <vmlinux> --func <fn> [--h16 0x290]
  h16_search.py <vmlinux> --chain <SyS_root> [--h16 0x290] [--depth 3]
  h16_search.py <vmlinux> --all [--h16 0x290] [--depth 3]
  h16_search.py <vmlinux> --rtmutex
  h16_search.py <vmlinux> --memcpy [--h16 0x290]
  h16_search.py <vmlinux> --verify
"""
import re
import subprocess
import sys

OD = ("/home/erick/Android/Sdk/ndk/29.0.14206865/toolchains/llvm/"
      "prebuilt/linux-x86_64/bin/llvm-objdump")
NM = ("/home/erick/Android/Sdk/ndk/29.0.14206865/toolchains/llvm/"
      "prebuilt/linux-x86_64/bin/llvm-nm")

H16_STOCK = 0x290  # conjecture: SP0-0x2c8 waiter + 0x38
H16_LAB = 0x278    # old lab: SP0-0x2b0 waiter + 0x38
WIN = 0x40

_disasm_cache = {}
_frame_cache = {}
_full_cache = None
FULL_ASM = "/tmp/opencode/aq_full.asm"

COPY_FNS = {"__arch_copy_from_user", "_copy_from_user", "__copy_from_user",
            "copy_from_user", "copyin", "_copy_to_user", "__copy_to_user",
            "copy_to_user", "memcpy", "memmove", "__memcpy", "__memmove",
            "memset", "__memset", "strcpy", "strncpy", "strlcpy"}
INT_RETURNS = {"memset", "__memset", "memcpy", "__memcpy", "memmove",
               "printk", "warn_alloc", "_mcount", "__might_fault",
               "__check_object_size", "sched_clock", "fput", "kfree",
               "spin_lock", "spin_unlock", "_raw_spin_lock",
               "_raw_spin_unlock", "up", "down", "mutex_lock",
               "mutex_unlock", "poll_schedule_timeout", "poll_freewait",
               "select_estimate_accuracy.part.2"}
PTR_RETURNS = {"__kmalloc", "kmem_cache_alloc", "kmalloc", "alloc_pi_state",
               "get_file", "fget", "__fdget", "__fget", "filp_open",
               "sock_from_file", "sock_alloc", "alloc_task_struct",
               "get_task_struct", "find_task_by_vpid", "pid_task",
               "current", "kmalloc_node", "__get_free_pages",
               "alloc_pages", "get_page_from_freelist",
               "__alloc_pages_nodemask", "vmalloc", "ioremap"}


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
    sz, _ = frame_of(f.get(sym, []))
    _frame_cache[sym] = sz
    return sz


REG = r"[xw](?:\d+|zr|sp)"


def reg_base(r):
    r = r.strip().split()[0].rstrip(",")
    if r.startswith("w"):
        n = r[1:]
        return ("x" + n) if n not in ("zr", "sp") else r
    return r


def is_wreg(tok):
    tok = tok.strip().split()[0]
    return tok.startswith("w") and tok not in ("wzr",)


def parse_mem(op):
    m = re.search(r"\[\s*(\w+)(?:\s*,\s*#(0x[0-9a-f]+|\d+))?\s*\]", op)
    if not m:
        return None
    base = m.group(1)
    off = int(m.group(2), 0) if m.group(2) else 0
    return (base, off)


def classify_store_width(mnem, src_tok):
    """bytes written by this store op for one word."""
    if mnem in ("strb",):
        return 1
    if mnem in ("strh",):
        return 2
    if mnem.startswith("stp"):
        return 8
    if mnem in ("str", "stur"):
        return 4 if is_wreg(src_tok) else 8
    if mnem in ("stxr", "stlxr"):
        return 4 if is_wreg(src_tok) else 8
    return 8


def value_class(origin, is_ptr, width):
    """Map internal origin + width to FASE-4 public class."""
    if width != 8:
        if origin.startswith("KERNEL"):
            return "KERNEL_DERIVED_INTEGER"
        if origin.startswith("USER"):
            return "INTEGER"
        return "INTEGER"
    if origin.startswith("USER"):
        return "USER_POINTER" if is_ptr else "INTEGER"
    if origin.startswith("KERNEL"):
        return "KERNEL_POINTER" if is_ptr else "KERNEL_DERIVED_INTEGER"
    if origin in ("ZERO", "IMMEDIATE"):
        return "INTEGER"
    return "UNKNOWN"


def analyze_func_h16(insns, entry_taint=None):
    """Forward taint with kernel-pointer sources.

    Returns (stores, callsites, copies):
      stores: addr,mnem,src,base,off,width,origin,detail,is_ptr,vclass
      callsites: addr,target,snap
      copies: addr,target,dest_class,src_class,size_known
    """
    if entry_taint is None:
        entry_taint = {("x%d" % i): ("USER_ARG", "syscall arg %d" % i, True)
                       for i in range(6)}
    taint = dict(entry_taint)
    mem = {}
    stores = []
    callsites = []
    copies = []
    for addr, mnem, rest in insns:
        ops = [o.strip() for o in rest.split(",")]
        if mnem in ("mov", "movz", "movn", "movk"):
            if len(ops) >= 2:
                d = reg_base(ops[0])
                s = ops[1].strip()
                m = re.match(r"^([xw]\d+)$", s)
                if m:
                    s2 = reg_base(m.group(1))
                    if s2 in taint:
                        taint[d] = taint[s2]
                    elif d in taint:
                        del taint[d]
                elif re.match(r"^#(0x[0-9a-f]+|\d+)", s):
                    imm_tok = s[1:].split()[0].rstrip(",")
                    imm = int(imm_tok, 0)
                    if imm == 0:
                        taint[d] = ("ZERO", "mov #0", False)
                    else:
                        taint[d] = ("IMMEDIATE", "mov #%x" % imm, False)
                elif re.match(r"^[xw]zr$", s):
                    taint[d] = ("ZERO", "mov zr", False)
                else:
                    if d in taint:
                        del taint[d]
        elif mnem in ("adrp", "adr"):
            if ops:
                d = reg_base(ops[0])
                taint[d] = ("KERNEL_CODE", "adr code addr", True)
        elif mnem == "mrs":
            if ops:
                d = reg_base(ops[0])
                taint[d] = ("KERNEL_CURRENT", "mrs %s (current/task)" % rest, True)
        elif mnem in ("add", "sub"):
            if len(ops) >= 2:
                d = reg_base(ops[0].split()[0])
                srcs = []
                for o in ops[1:]:
                    mm = re.match(r"^([xw]\d+|sp|x29|xzr|wzr)", o)
                    if mm:
                        srcs.append(reg_base(mm.group(1)))
                hit = [(s, taint[s]) for s in srcs if s in taint]
                if hit:
                    s, (o, dt, p) = hit[0]
                    # stack address is itself a kernel pointer
                    if s in ("x29", "sp") and o.startswith("USER"):
                        taint[d] = (o, dt + " >%s> %s" % (mnem, d), p)
                    elif s in ("x29", "sp"):
                        taint[d] = ("KERNEL_STACK", "stack addr %s" % d, True)
                    else:
                        taint[d] = (o, dt + " >%s> %s" % (mnem, d), p)
        elif mnem in ("lsl", "lsr", "asr", "and", "orr", "eor", "bic",
                      "sxtw", "uxtw", "sbfiz", "ubfiz", "sxtb", "sxth",
                      "uxtb", "uxth", "csel", "csinc", "csinv", "cset",
                      "lslv", "lsrv", "ror", "extr", "ubfx", "sbfx",
                      "bfxil", "bfi", "sbfm", "ubfm", "madd", "msub",
                      "mul", "udiv", "sdiv", "smull", "umull"):
            if len(ops) >= 2:
                d = reg_base(ops[0].split()[0])
                srcs = []
                for o in ops[1:]:
                    mm = re.match(r"^([xw]\d+|sp|xzr|wzr)", o)
                    if mm:
                        srcs.append(reg_base(mm.group(1)))
                hit = [(s, taint[s]) for s in srcs if s in taint]
                if hit:
                    s, (o, dt, p) = hit[0]
                    # masking/shift destroys pointer nature
                    taint[d] = (o, dt + " >%s> %s" % (mnem, d), False)
        elif mnem in ("ldr", "ldrh", "ldrb", "ldrsw", "ldp", "ldur",
                      "ldxrh", "ldxr", "ldaxr"):
            if mnem == "ldp" and len(ops) >= 3:
                d1 = reg_base(ops[0])
                d2 = reg_base(ops[1])
                mm = parse_mem(rest)
                if mm:
                    base, off = mm
                    for i, d in enumerate((d1, d2)):
                        o2 = off + i * 8
                        if (base, o2) in mem:
                            taint[d] = mem[(base, o2)]
                        elif base in taint:
                            o, dt, p = taint[base]
                            if base in ("x29", "sp"):
                                pass  # unknown stack slot, do not invent
                            elif o.startswith("USER"):
                                taint[d] = ("USER_BUFFER_DERIVED",
                                            dt + " >ldr [%s+%x]> %s" % (base, o2, d), True)
                            else:
                                taint[d] = ("KERNEL_HEAP",
                                            dt + " >ldr [%s+%x]> %s" % (base, o2, d), True)
                        elif base not in ("x29", "sp"):
                            taint[d] = ("KERNEL_HEAP",
                                        "ldr [heap %s+%x]> %s" % (base, o2, d), True)
            else:
                d = reg_base(ops[0])
                mm = parse_mem(rest)
                if mm:
                    base, off = mm
                    if (base, off) in mem:
                        taint[d] = mem[(base, off)]
                    elif base in taint:
                        o, dt, p = taint[base]
                        if base in ("x29", "sp"):
                            pass
                        elif o.startswith("USER"):
                            taint[d] = ("USER_BUFFER_DERIVED",
                                        dt + " >ldr [%s+%x]> %s" % (base, off, d), True)
                        else:
                            taint[d] = ("KERNEL_HEAP",
                                        dt + " >ldr [%s+%x]> %s" % (base, off, d), True)
                    elif base not in ("x29", "sp"):
                        taint[d] = ("KERNEL_HEAP",
                                    "ldr [heap %s+%x]> %s" % (base, off, d), True)
        elif mnem in ("str", "strb", "strh", "stur", "stp", "stxr",
                      "stlxr", "stlr"):
            if mnem == "stp" and len(ops) >= 3:
                r1 = reg_base(ops[0])
                r2 = reg_base(ops[1])
                mm = parse_mem(rest)
                if mm:
                    base, off = mm
                    for i, r in enumerate((r1, r2)):
                        o2 = off + i * 8
                        if r in taint:
                            o, dt, p = taint[r]
                            vc = value_class(o, p, 8)
                            stores.append(dict(addr=addr, mnem="stp[%d]" % i,
                                               src=r, base=base, off=o2,
                                               width=8, origin=o, detail=dt,
                                               is_ptr=p, vclass=vc))
                            if base in ("x29", "sp"):
                                mem[(base, o2)] = (o, dt, p)
                        else:
                            if (base, o2) in mem:
                                del mem[(base, o2)]
            else:
                s = reg_base(ops[0]) if ops else "?"
                mm = parse_mem(rest)
                if mm and re.match(r"^[xw]\d+$", s):
                    base, off = mm
                    w = classify_store_width(mnem, ops[0])
                    if s in taint:
                        o, dt, p = taint[s]
                        vc = value_class(o, p, w)
                        stores.append(dict(addr=addr, mnem=mnem, src=s,
                                           base=base, off=off, width=w,
                                           origin=o, detail=dt, is_ptr=p,
                                           vclass=vc))
                        if base in ("x29", "sp"):
                            mem[(base, off)] = (o, dt, p)
                    else:
                        if (base, off) in mem:
                            del mem[(base, off)]
                        # untainted reg store: still record as UNKNOWN so
                        # kernel-fixed spills are visible (not filtered)
                        stores.append(dict(addr=addr, mnem=mnem, src=s,
                                           base=base, off=off, width=w,
                                           origin="UNKNOWN", detail="untainted reg",
                                           is_ptr=False, vclass="UNKNOWN"))
        elif mnem in ("bl", "blx", "blr"):
            m = re.search(r"<([^>]+)>", rest)
            tgt = m.group(1) if m else rest.split()[-1]
            if mnem == "bl" and tgt.startswith("INDIRECT"):
                pass
            snap = {}
            for i in range(8):
                r = "x%d" % i
                if r in taint:
                    snap[r] = taint[r]
            callsites.append(dict(addr=addr, target=tgt, snap=snap))
            short = tgt.split("+")[0].split(".")[0]
            if short in COPY_FNS:
                dest = snap.get("x0")
                src = snap.get("x1")
                copies.append(dict(addr=addr, target=tgt,
                                   dest=dest, src=src))
            if short in INT_RETURNS:
                if "x0" in taint:
                    del taint["x0"]
                taint["x0"] = ("INTEGER", "return %s (int)" % short, False)
            elif short in PTR_RETURNS or short.startswith("alloc") \
                    or short.startswith("get_") or short.startswith("filp") \
                    or short.startswith("sock") or short.startswith("find_") \
                    or short.startswith("lookup") or short.startswith("attach"):
                taint["x0"] = ("KERNEL_RETURN", "return %s (ptr)" % short, True)
            else:
                if "x0" in taint:
                    del taint["x0"]
                # unknown return: do not claim a pointer
    return (stores, callsites, copies)


def chain_search_h16(vmlinux, root, h16, max_depth=3):
    frames = {}

    def fr(s):
        if s not in frames:
            frames[s] = get_frame(vmlinux, s)
        return frames[s]

    fr(root)
    results = []
    copies_all = []
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
            stores, calls, copies = analyze_func_h16(insns)
        else:
            stores, calls, copies = analyze_func_h16(insns, entry_taint=entry)
        for c in copies:
            c2 = dict(c)
            c2["path"] = list(path)
            c2["func"] = func
            c2["sumF"] = sum_incl
            copies_all.append(c2)
        for s in stores:
            if s["base"] not in ("x29", "sp"):
                continue
            dest_rel = sum_incl - s["off"]
            s2 = dict(s)
            s2["path"] = list(path)
            s2["func"] = func
            s2["sumF"] = sum_incl
            s2["dest_rel"] = dest_rel
            s2["delta"] = dest_rel - h16
            s2["waiter_off"] = 0x38 + (dest_rel - h16)
            results.append(s2)
        if len(path) <= max_depth:
            for c in calls:
                t = c["target"]
                if t.startswith("INDIRECT"):
                    continue
                snap = {}
                for k, v in c["snap"].items():
                    # v is (origin, detail, is_ptr)
                    snap[k] = v
                if t in visited or any(q[0] == t for q in queue):
                    continue
                visited.add(t)
                queue.append((t, path + [t], sum_incl,
                              dict(snap) if snap else {}))
    return results, copies_all


def fmt_rel(r):
    return "SP0-0x%x" % r if r >= 0 else "SP0+0x%x" % (-r)


def side_effects_of(path, vmlinux):
    tags = set()
    for fn in path:
        s = fn.lower()
        if any(k in s for k in ("sched", "sleep", "wait", "timeout",
                                "get_user_pages", "mm_access", "alloc_page",
                                "kmalloc", "vmalloc")):
            tags.add("SLEEPS/ALLOC")
        if any(k in s for k in ("ge2d", "amstream", "amvenc", "dvb", "osd",
                                "gdc", "mmc", "mtd", "hdmi", "v4l", "ion")):
            tags.add("HARDWARE_IO")
        if any(k in s for k in ("futex", "rt_mutex", "pi_state", "requeue")):
            tags.add("PI_PATH")
        if any(k in s for k in ("copy_from_user", "copy_to_user", "memcpy",
                                "memmove", "poll", "select", "sendmsg",
                                "recvmsg", "ioctl")):
            tags.add("USER_COPY/IO")
    if not tags:
        return "unknown-small"
    return ",".join(sorted(tags))


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
    rest = sys.argv[i:]

    if mode == "--frames":
        syms = [s for s in all_syms(vmlinux) if s.startswith("SyS_")]
        rows = []
        for j in range(0, len(syms), 64):
            d = disasm(vmlinux, syms[j:j + 64])
            for s, ins in d.items():
                sz, _ = frame_of(ins)
                rows.append((sz, s))
        rows.sort(reverse=True)
        print("SyS_ frames (top 60 by size):")
        for sz, s in rows[:60]:
            print("  0x%-4x %s" % (sz, s))
        print("total SyS_: %d" % len(rows))
        print("H16_REL=0x%x window=[%s..%s]" % (h16, fmt_rel(h16 + WIN), fmt_rel(h16 - WIN)))
    elif mode == "--func":
        fn = rest[0] if rest else sys.argv[3]
        f = disasm(vmlinux, [fn])
        ins = f.get(fn, [])
        sz, kind = frame_of(ins)
        print("%s frame=0x%x (%s) n_insn=%d H16_REL=0x%x" % (fn, sz, kind, len(ins), h16))
        stores, calls, copies = analyze_func_h16(ins)
        print("--- stack stores with H16 class (all origins) ---")
        for s in stores:
            if s["base"] in ("x29", "sp"):
                print("  0x%x: %s %s,[%s,#0x%x] w=%d class=%s origin=%s ptr=%s" %
                      (s["addr"], s["mnem"], s["src"], s["base"], s["off"],
                       s["width"], s["vclass"], s["origin"], s["is_ptr"]))
                print("      detail: %s" % s["detail"])
        print("--- copy/memcpy callsites ---")
        for c in copies:
            print("  0x%x: bl %s dest=%s src=%s" % (c["addr"], c["target"], c["dest"], c["src"]))
    elif mode == "--chain":
        root = rest[0] if rest else sys.argv[3]
        if len(rest) > 1 and rest[1].isdigit():
            depth = int(rest[1])
        res, copies = chain_search_h16(vmlinux, root, h16, max_depth=depth)
        print("=" * 72)
        print("CHAIN %s depth<=%d H16_REL=0x%x (%s) window +-0x%x: %d stack stores" %
              (root, depth, h16, fmt_rel(h16), WIN, len(res)))
        print("LAB != STOCK: lab-relative only, stock INCONCLUSIVE")
        print("=" * 72)
        near = [r for r in res if abs(r["delta"]) <= WIN]
        print("--- stores within H16+-0x40: %d ---" % len(near))
        pri = {"KERNEL_POINTER": 0, "USER_POINTER": 1, "UNKNOWN": 2,
               "KERNEL_DERIVED_INTEGER": 3, "INTEGER": 4}
        for r in sorted(near, key=lambda x: (pri.get(x["vclass"], 9), abs(x["delta"]))):
            mark = "HIT" if (r["delta"] == 0 and r["width"] == 8) else ("near%+x" % r["delta"])
            print("\n[%s w=%d class=%s] %s 0x%x: %s %s,[%s,#0x%x] -> %s (delta%+x waiter_off=%+x sumF=0x%x)" %
                  (mark, r["width"], r["vclass"], r["func"], r["addr"],
                   r["mnem"], r["src"], r["base"], r["off"],
                   fmt_rel(r["dest_rel"]), r["delta"], r["waiter_off"], r["sumF"]))
            print("  path: %s" % ">".join(r["path"]))
            print("  origin=%s ptr=%s se=%s\n  dataflow: %s" %
                  (r["origin"], r["is_ptr"],
                   side_effects_of(r["path"], vmlinux), r["detail"]))
        print("\n--- copy/memcpy in chain: %d ---" % len(copies))
        for c in copies[:20]:
            print("  0x%x %s: bl %s dest=%s src=%s path=%s" %
                  (c["addr"], c["func"], c["target"], c["dest"], c["src"],
                   ">".join(c["path"])))
    elif mode == "--all":
        syms = [s for s in all_syms(vmlinux) if s.startswith("SyS_")]
        print("scanning %d SyS_ roots (depth %d) H16_REL=0x%x window +-0x%x..." %
              (len(syms), depth, h16, WIN))
        print("LAB != STOCK: lab-relative only.")
        hits = []
        for s in syms:
            try:
                res, _ = chain_search_h16(vmlinux, s, h16, max_depth=depth)
            except Exception as e:
                print("  %s: ERROR %s" % (s, e))
                continue
            for r in res:
                if abs(r["delta"]) > WIN:
                    continue
                if r["width"] != 8:
                    continue
                hits.append((s, r))
        print("=" * 72)
        print("8B stores in [H16-0x%x..H16+0x%x]: %d" % (WIN, WIN, len(hits)))
        pri = {"KERNEL_POINTER": 0, "USER_POINTER": 1, "UNKNOWN": 2,
               "KERNEL_DERIVED_INTEGER": 3, "INTEGER": 4}
        khits = [h for h in hits if h[1]["vclass"] == "KERNEL_POINTER"]
        uhits = [h for h in hits if h[1]["vclass"] == "USER_POINTER"]
        print("KERNEL_POINTER 8B in window: %d" % len(khits))
        print("USER_POINTER 8B in window: %d" % len(uhits))
        for s, r in sorted(hits, key=lambda x: (pri.get(x[1]["vclass"], 9),
                                                abs(x[1]["delta"]))):
            print("\n[%s delta%+x w=%d] root=%s func=%s 0x%x: %s %s,[%s,#0x%x] -> %s (sumF=0x%x waiter_off=%+x)" %
                  (r["vclass"], r["delta"], r["width"], s, r["func"],
                   r["addr"], r["mnem"], r["src"], r["base"], r["off"],
                   fmt_rel(r["dest_rel"]), r["sumF"], r["waiter_off"]))
            print("  path: %s se=%s" % (">".join(r["path"]), side_effects_of(r["path"], vmlinux)))
            print("  origin=%s ptr=%s\n  dataflow: %s" % (r["origin"], r["is_ptr"], r["detail"]))
    elif mode == "--rtmutex":
        print("=" * 72)
        print("RT_MUTEX * CARRIERS: pi_state+0x10 LEAs + forward spills")
        print("EVIDENCE: OFFLINE_ONLY (build-aq/vmlinux). Stock slides VAs.")
        print("=" * 72)
        funcs = ["attach_to_pi_owner", "futex_requeue",
                 "futex_lock_pi", "futex_wait_requeue_pi.constprop.8",
                 "task_blocks_on_rt_mutex", "rt_mutex_start_proxy_lock",
                 "rt_mutex_init_proxy_locked"]
        d = disasm(vmlinux, funcs)
        for fn in funcs:
            ins = d.get(fn, [])
            if not ins:
                print("\n%s: no disasm" % fn)
                continue
            sz, _ = frame_of(ins)
            print("\n--- %s frame=0x%x ---" % (fn, sz))
            for addr, mnem, rest in ins:
                if re.search(r"#0x10\b", rest) and mnem in ("add", "mov", "ldr"):
                    print("  0x%x: %s %s" % (addr, mnem, rest))
            stores, calls, copies = analyze_func_h16(ins)
            n = 0
            for s in stores:
                if s["base"] in ("x29", "sp") and s["vclass"] == "KERNEL_POINTER":
                    print("  spill KPTR 0x%x: %s %s,[%s,#0x%x] origin=%s" %
                          (s["addr"], s["mnem"], s["src"], s["base"],
                           s["off"], s["origin"]))
                    print("      detail: %s" % s["detail"])
                    n += 1
            if n == 0:
                print("  no KERNEL_POINTER stack spills in this function body")
        print("\nnote: a carrier needs LEA-reg -> str/stp -> stack slot that")
        print("survives to H16 delta 0 on the SAME task stack page. None of the")
        print("above spills target the FWRQ frame by construction (different")
        print("syscall frames); composition requires a stamper syscall whose")
        print("frame overlaps H16 (see --all).")
    elif mode == "--memcpy":
        syms = [s for s in all_syms(vmlinux) if s.startswith("SyS_")]
        print("scanning memcpy/copy_from_user with stack dest near H16_REL=0x%x..." % h16)
        found = 0
        for s in syms:
            try:
                res, copies = chain_search_h16(vmlinux, s, h16, max_depth=depth)
            except Exception:
                continue
            for c in copies:
                # dest stack? check snapshot
                dest = c.get("dest")
                if dest is None:
                    continue
                o, dt, p = dest
                # only interesting if dest derives from stack
                if "stack" not in dt.lower() and "x29" not in dt and "sp" not in dt:
                    # snapshot rarely carries stack derivation; still list
                    # copies in deep frames for manual review, capped
                    pass
                found += 1
                if found <= 30:
                    print("  0x%x %s: bl %s dest=%s src=%s path=%s sumF=0x%x" %
                          (c["addr"], c["func"], c["target"], dest,
                           c.get("src"), ">".join(c["path"]), c["sumF"]))
        print("copy callsites listed (capped 30): %d total" % found)
        print("rule: count only when (1) src can carry kernel pointer,")
        print("(2) dest can reach H16, (3) size covers 8B, (4) frame live.")
    elif mode == "--verify":
        checks = [
            ("task_blocks_on_rt_mutex", 0xffffff800910527c, "stp"),
            ("rt_mutex_adjust_prio_chain", 0xffffff8009104df0, "ldr"),
            ("rt_mutex_adjust_prio_chain", 0xffffff8009104e44, "bl"),
            ("do_sys_poll", 0xffffff8009230bb8, "stp"),
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
