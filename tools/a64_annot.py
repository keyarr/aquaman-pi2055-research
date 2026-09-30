#!/usr/bin/env python3
"""annotated dump of an address range, resolving every movz/movk-built address
so AO register accesses are readable inline.

usage: a64_annot.py <bin> <start> <end> [pin_addr ...]
"""
import os, sys, struct
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN

MD = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
MD.skipdata = True

PIN = {}
for a in sys.argv[4:]:
    PIN[int(a, 0)] = True


def main():
    path, start, end = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0)
    base = int(os.environ.get("A64_BASE", "0"), 0)
    data = open(path, "rb").read()
    ins = list(MD.disasm(data[start - base:end - base], start))
    vals = {}
    out = []
    for i in ins:
        ops = [p.strip() for p in i.op_str.split(",")] if i.op_str else []
        note = ""
        if i.mnemonic in ("movz", "movn", "mov") and len(ops) >= 2 and ops[1].startswith("#"):
            v = int(ops[1].lstrip("#"), 0)
            vals[ops[0]] = v
            note = f"   ; = 0x{v:x}"
        elif i.mnemonic == "movk" and len(ops) >= 2 and ops[1].startswith("#"):
            lsl = 0
            for p in ops[2:]:
                if p.startswith("lsl"):
                    lsl = int(p.lstrip("lsl #"), 0)
            if ops[0] in vals:
                vals[ops[0]] = (vals[ops[0]] & ~(0xFFFF << lsl)) | (int(ops[1].lstrip("#"), 0) << lsl)
                note = f"   ; = 0x{vals[ops[0]]:x}"
        if i.mnemonic in ("ldr", "str", "ldrb", "strb", "ldrh", "strh") and "[" in i.op_str:
            base = i.op_str.split("[")[1].split("]")[0].strip().split(",")[0].strip()
            if base in vals:
                note += f"   ; {i.mnemonic} @ 0x{vals[base]:x}"
                if vals[base] in PIN:
                    note += "  <<<PIN"
        star = "*" if i.address in PIN else " "
        out.append(f" {star}0x{i.address:06x}  {i.mnemonic:8s} {i.op_str}{note}")
    print("\n".join(out))


if __name__ == "__main__":
    main()
