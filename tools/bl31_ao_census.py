#!/usr/bin/env python3
"""census of every 32-bit MMIO constant a blob builds, mapped to Amlogic
GXL register names from secure_apb.h.

raw movz/movk encoding scan (no flow analysis): for each 16-bit half of a
candidate we would need the pair, so instead we walk the disassembly and
reconstruct movz+movk chains only for pairs that are adjacent in the stream
and land in an MMIO range. good enough to enumerate, precise enough to cite.
"""
import re, struct, sys, glob
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN

MD = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
MD.skipdata = True

HDR = ".src/u-boot-khadas/arch/arm/include/asm/arch-gxl/secure_apb.h"


def regmap():
    m = {}
    t = open(HDR, errors="ignore").read()
    for mm in re.finditer(r"#define\s+(\w+)\s+\(?(0x[0-9a-fA-F]+)\s*\+\s*\(0x([0-9a-fA-F]+)\s*<<\s*2\)\)?", t):
        name = mm.group(1)
        v = int(mm.group(2), 16) + (int(mm.group(3), 16) << 2)
        if name.startswith("P_"):
            continue
        m.setdefault(v, name)
    return m


def main():
    path = sys.argv[1]
    data = open(path, "rb").read()
    ins = list(MD.disasm(data, 0))
    names = regmap()
    seen = {}
    for n, i in enumerate(ins):
        if i.mnemonic not in ("movz", "mov") or not i.op_str:
            continue
        ops = [p.strip() for p in i.op_str.split(",")]
        if len(ops) < 2 or not ops[1].startswith("#"):
            continue
        reg = ops[0]
        val = int(ops[1].lstrip("#"), 0)
        for m2 in ins[n + 1:n + 5]:
            if m2.mnemonic == "movk":
                o2 = [p.strip() for p in m2.op_str.split(",")]
                if o2[0] != reg:
                    continue
                lsl = 0
                for p in o2[2:]:
                    if p.startswith("lsl"):
                        lsl = int(p.lstrip("lsl #"), 0)
                val = (val & ~(0xFFFF << lsl)) | (int(o2[1].lstrip("#"), 0) << lsl)
            else:
                break
        if 0xC8000000 <= val <= 0xC8FFFFFF or 0xDA000000 <= val <= 0xDAFFFFFF:
            seen.setdefault(val, []).append(i.address)
    for v in sorted(seen):
        tag = names.get(v, "")
        if v >= 0xDA000000:
            tag = "(secure alias) " + tag.replace("SEC_", "")
        print(f"  0x{v:08x}  x{len(seen[v]):<3d}  {tag}")


if __name__ == "__main__":
    main()
