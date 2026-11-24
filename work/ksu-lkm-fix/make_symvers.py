#!/usr/bin/env python3
"""Rebuild Module.symvers from the synthetic stock vmlinux ELF.

The CRC bytes live in .rela.dyn addends: vmlinux-to-elf zeroes the
__kcrctab_* slots while relocating the kernel image, so the value has to be
read from the RELA entry whose r_offset matches the __kcrctab_* address.
"""
import sys
from elftools.elf.elffile import ELFFile

elf_path, out_path = sys.argv[1], sys.argv[2]

with open(elf_path, "rb") as f:
    elf = ELFFile(f)
    addends = {}
    for rel in elf.get_section_by_name(".rela.dyn").iter_relocations():
        addends[rel["r_offset"]] = rel["r_addend"] & 0xFFFFFFFF

    syms = elf.get_section_by_name(".symtab")
    rows = []
    for s in syms.iter_symbols():
        name = s.name
        if not name.startswith("__kcrctab_"):
            continue
        symbol = name[len("__kcrctab_"):]
        if not symbol:
            continue
        if s["st_value"] not in addends:
            raise ValueError("no RELA entry for %s" % name)
        rows.append((symbol, addends[s["st_value"]]))

with open(out_path, "w") as out:
    for symbol, crc in sorted(rows):
        out.write("%08x\t%s\tvmlinux\tEXPORT_SYMBOL\n" % (crc, symbol))

print("wrote %d symbols to %s" % (len(rows), out_path))
