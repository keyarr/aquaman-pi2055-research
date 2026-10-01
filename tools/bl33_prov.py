#!/usr/bin/env python3
"""bl33_prov.py - forward dataflow over each BL33 function to resolve where
every indirect branch (br/blr) gets its target from.

symbolic value per register:
  ('imm', v)          constant built with mov/movz/movk/adr/adrp+add
  ('mem', base, off)  loaded from [base + off]   (base itself symbolic)
  ('opaque',)         anything else

caller-saved registers (x0..x18) are invalidated at every bl/blr/br/ret,
which is what the AAPCS64 gives us for free.
"""
import re
import struct
import sys
from collections import defaultdict

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN

IMG = "reports/round14-bl33-persist/bl33-37e18000.bin"
BASE = 0x37E18000
DST = 0x37FF0000
GD_REG = "x18"          # this build keeps &global_data in x18 (see 0x37e19354)

MD = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
MD.detail = True
MD.skipdata = True

REGS = ["x%d" % i for i in range(31)] + ["w%d" % i for i in range(31)]
W = set("w%d" % i for i in range(31))
CLobber = set("x%d" % i for i in range(19)) | {"v0", "v1", "v2", "v3"}


def main():
    d = open(IMG, "rb").read()
    ins = list(MD.disasm(d, BASE))
    starts = {BASE}
    for n, x in enumerate(ins):
        if x.mnemonic == "stp" and x.op_str.startswith("x29, x30, [sp, #-"):
            starts.add(x.address)
        if n and ins[n - 1].mnemonic in ("ret", "brk"):
            starts.add(x.address)
    starts = sorted(starts)
    idx = {x.address: n for n, x in enumerate(ins)}

    def func_of(a):
        lo, hi, best = 0, len(starts) - 1, starts[0]
        while lo <= hi:
            m = (lo + hi) // 2
            if starts[m] <= a:
                best, lo = starts[m], m + 1
            else:
                hi = m - 1
        return best

    byfunc = defaultdict(list)
    for n, x in enumerate(ins):
        byfunc[func_of(x.address)].append(x)

    def num(tok):
        tok = tok.strip()
        try:
            return int(tok, 0)
        except ValueError:
            return None

    def split_ops(s):
        out, depth, cur = [], 0, ""
        for ch in s:
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
            if ch == "," and depth == 0:
                out.append(cur)
                cur = ""
            else:
                cur += ch
        out.append(cur)
        return [p.strip() for p in out]

    def mem_of(op):
        m = re.match(r"\[([a-z0-9]+)(?:,\s*#?(-?(?:0x)?[0-9a-f]+))?"
                     r"(?:,\s*(lsl|uxtw|sxtw|sxtb|sxth|uxth)(?:\s*#(\d+))?)?\]", op)
        if not m:
            return None
        b = m.group(1)
        off = int(m.group(2), 0) if m.group(2) else 0
        if m.group(4):
            off += int(m.group(4)) << 0
        return b, off

    results = []
    for f, body in byfunc.items():
        sym = {}
        page = {}
        for x in body:
            mn, ops = x.mnemonic, split_ops(x.op_str)
            if mn in ("bl", "blr", "br", "ret", "brk", "svc", "smc"):
                if mn in ("br", "blr"):
                    t = ops[0]
                    results.append((x.address, f, mn, t, sym.get(t)))
                for r in CLobber:
                    sym.pop(r, None)
                    sym.pop("w" + r[1:], None)
                continue
            if mn in ("b", "b.eq", "b.ne", "b.hi", "b.lo", "b.mi", "b.pl", "b.ge",
                      "b.lt", "b.gt", "b.le", "b.hs", "b.ls", "cbz", "cbnz",
                      "tbz", "tbnz", "b.cond", "csel", "csinc", "csinv",
                      "ccmp", "cset", "csetm", "cinc", "cneg", "cadd"):
                if mn in ("csel", "csinc", "csinv", "ccmp", "cset", "csetm",
                          "cinc", "cneg", "cadd"):
                    for o in ops[1:]:
                        r = o.split(",")[0].strip()
                        if r in REGS:
                            sym[r] = ("opaque",)
                continue
            if mn in ("cmp", "cmn", "tst", "cmpb", "cmph", "cmpb", "ccmp",
                      "ccmn", "fcmp", "nge", "lsl", "lsr", "asr", "ror",
                      "clz", "cls", "rev", "rev16", "rev32", "sxtb", "sxth",
                      "sxtw", "uxtb", "uxth", "nop", "isb", "dsb", "dmb",
                      "wfe", "wfi", "sev", "sevl", "yield", "hint", "bti"):
                continue
            d0 = ops[0] if ops else ""
            if d0 not in REGS:
                continue
            dw = d0 in W
            dr = "x" + d0[1:] if dw else d0
            if mn == "adrp":
                page[dr] = int(ops[1].split("#")[1], 0)
            elif mn == "adr":
                sym[dr] = ("imm", int(ops[1].split("#")[1], 0))
            elif mn in ("mov", "movz", "movn", "movk"):
                v = num(ops[1].split("#")[1].split(",")[0]) if "#" in ops[1] else None
                if v is None:
                    src = ops[1].strip()
                    sym[dr] = ("opaque",) if not dw else ("opaque",)
                else:
                    if mn == "movk" and dr in sym and sym[dr][0] == "imm":
                        sh = 0
                        if "lsl" in x.op_str:
                            sh = int(x.op_str.split("lsl #")[1], 0)
                        sym[dr] = ("imm", (sym[dr][1] & ~(0xFFFF << sh)) | (v << sh))
                    else:
                        sym[dr] = ("imm", v if mn != "movn" else (~v) & 0xFFFFFFFFFFFFFFFF)
            elif mn == "add":
                imm = num(ops[2].split("#")[1].split(",")[0]) if "#" in ops[2] else None
                a = sym.get(ops[1].strip())
                if imm is not None and dr in page and ops[1].strip() == dr:
                    sym[dr] = ("imm", page[dr] + imm)
                elif imm is not None and a and a[0] == "imm":
                    sym[dr] = ("imm", a[1] + imm)
                elif imm is not None and ops[1].strip() == "sp":
                    sym[dr] = ("stack", imm)
                elif imm == 0 and a:
                    sym[dr] = a
                else:
                    sym[dr] = ("opaque",)
            elif mn in ("ldr", "ldur", "ldrsw", "ldrb", "ldrh", "ldurb", "ldarh",
                        "ldarb", "ldarsw"):
                m = mem_of(ops[1]) if len(ops) > 1 else None
                if not m:
                    sym[dr] = ("opaque",)
                else:
                    b, off = m
                    if b == "sp":
                        sym[dr] = ("stack", off)
                    elif b == "x29":
                        sym[dr] = ("stack29", off)
                    elif b in sym and sym[b][0] == "imm":
                        sym[dr] = ("mem", sym[b][1] + off)
                    elif b in sym and sym[b][0] == "mem":
                        sym[dr] = ("mem2", sym[b][1], off)
                    else:
                        sym[dr] = ("memreg", b, off)
                    if dw:
                        sym[dr] = sym[dr] + ("w",)
            elif mn == "ldp":
                m1 = mem_of(ops[1]) if len(ops) > 1 else None
                if m1:
                    b, off = m1
                    for j, o in enumerate(ops[1:]):
                        r = o.split(",")[0].strip()
                        if r in REGS and r.startswith("x"):
                            sym[r] = ("stack" if b == "sp" else "stack29", off + 8 * j)
            else:
                sym[dr] = ("opaque",)

    # report
    static = defaultdict(list)
    other = defaultdict(list)
    for a, f, mn, t, s in results:
        if s is None:
            other["unknown"].append((a, f, mn, t, None))
        elif s[0] == "imm":
            if BASE <= s[1] < DST:
                static[s[1]].append((a, f, mn, t))
            else:
                other["imm-outside-%08x" % s[1]].append((a, f, mn, t, s))
        elif s[0] == "mem":
            base = s[1]
            if BASE <= base < DST:
                static[base].append((a, f, mn, t, s))
            else:
                other["mem@%08x" % base].append((a, f, mn, t, s))
        elif s[0] == "mem2":
            other["mem2@%08x+%#x" % (s[1], s[2])].append((a, f, mn, t, s))
        else:
            other[s[0]].append((a, f, mn, t, s))

    print("== target read from a static image address (candidate pointer slots) ==")
    for k in sorted(static):
        v = static[k]
        print("SLOT 0x%08x  n=%-3d  %s" %
              (k, len(v), " ".join("0x%x(%s %s)" % (a, m, t) for a, f, m, t, *rest in v[:8])))
    print("\n== everything else ==")
    for k in sorted(other, key=str):
        v = other[k]
        print("%-18s n=%-4d %s" % (k, len(v),
                                   " ".join("0x%x" % a for a, f, m, t, *rest in v[:10])))
    print("\ntotal indirect sites: %d" % len(results))


if __name__ == "__main__":
    main()
