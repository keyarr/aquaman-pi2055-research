#!/usr/bin/env python3
"""find direct bl/b call sites of a target function inside a flat AArch64 blob"""
import sys, os
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN

MD = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
MD.skipdata = True


def main():
    path = sys.argv[1]
    base = int(os.environ.get("A64_BASE", "0"), 0)
    targets = [int(a, 0) for a in sys.argv[2:]]
    data = open(path, "rb").read()
    for i in MD.disasm(data, 0):
        if i.mnemonic not in ("bl", "b"):
            continue
        if not i.op_str.startswith("#"):
            continue
        dst = base + int(i.op_str.lstrip("#"), 0)
        if dst in targets:
            print(f"  0x{base + i.address:08x}  {i.mnemonic:3s} -> 0x{dst:08x}")


if __name__ == "__main__":
    main()
