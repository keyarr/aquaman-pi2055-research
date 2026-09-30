#!/usr/bin/env python3
"""dump the code around every movk that carries bits16-31 of a target constant

raw-encoding scan (no flow analysis) so nothing is lost to symbolic execution.
prints the neighbourhood and reconstructs the value the base register holds,
so a movk 0xda10 is only reported when the low half really is 0x025c.
"""
import sys, struct
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN

MD = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
MD.skipdata = True


def disasm(data, start, n):
    return list(MD.disasm(data[start:start + n * 4], start))


def reg_at(insns, upto, reg):
    """value `reg` holds just before insns[upto], following movz/movk back"""
    val = None
    for ins in insns[:upto]:
        if not ins.op_str:
            continue
        ops = [p.strip() for p in ins.op_str.split(",")]
        if ins.mnemonic in ("movz", "movn", "mov") and len(ops) >= 2 and ops[0] == reg and ops[1].startswith("#"):
            val = int(ops[1].lstrip("#"), 0)
        elif ins.mnemonic == "movk" and len(ops) >= 2 and ops[0] == reg and ops[1].startswith("#"):
            lsl = 0
            for p in ops[2:]:
                if p.startswith("lsl"):
                    lsl = int(p.lstrip("lsl #"), 0)
            if val is None:
                return None
            val = (val & ~(0xFFFF << lsl)) | (int(ops[1].lstrip("#"), 0) << lsl)
    return val


def hits_for(data, value):
    hi = (value >> 16) & 0xFFFF
    pat = struct.pack("<I", 0xF2800000 | (1 << 21) | (hi << 5))
    out, i = [], 0
    while True:
        i = data.find(pat, i)
        if i < 0:
            break
        out.append(i)
        i += 4
    return out


def main():
    path, value = sys.argv[1], int(sys.argv[2], 0)
    before = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    after = int(sys.argv[4]) if len(sys.argv) > 4 else 20
    data = open(path, "rb").read()
    for h in hits_for(data, value):
        lo = max(0, h - before * 4)
        ins = disasm(data, lo, before + after + 1)
        # which register carries the hi half, and does it hold the full value?
        n = [k for k, i in enumerate(ins) if i.address == h][0]
        rd = [p.strip() for p in ins[n].op_str.split(",")][0]
        held = reg_at(ins, n, rd)
        tag = "MATCH" if held == value else f"low=0x{held & 0xffff:04x}"
        print(f"---- site 0x{h:x}  {tag}  (reg {rd}) ----")
        for k in ins:
            mark = ">>" if k.address == h else "  "
            print(f"  {mark} 0x{k.address:06x}  {k.mnemonic:8s} {k.op_str}")
        print()


if __name__ == "__main__":
    main()
