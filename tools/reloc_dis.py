#!/usr/bin/env python3
"""reloc_dis.py - offline disassembly of named addresses inside a DRAM band.

Round 13. Pure offline: no USB, no device, no writes. Round 12 located the
relocated BL33 at 0x37e18000 and named the boot-path functions; this is the
tiny viewer used to re-print those addresses (and their neighbours) from any
dump, so a re-read can be pinned to the same evidence without re-running the
whole shape analyzer.

  tools/reloc_dis.py FILE BASE NAME=ADDR:LEN[,NAME=ADDR:LEN,...]

  tools/reloc_dis.py reports/round13-reloc-verify/mread_37800000_00800000.bin \
      0x37800000 do_bootm=0x37e24c00:0x120 aml_sec_boot_check=0x37e19ea8:0x58

The file is read from disk only; nothing here opens a USB device even if one is
plugged in.
"""
import hashlib
import os
import struct
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN


def dis(data, base, addr, length):
    md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    off = addr - base
    if off < 0 or off + length > len(data):
        print("  0x%08x..0x%08x is outside the band [0x%08x,0x%08x)"
              % (addr, addr + length, base, base + len(data)))
        return
    for ins in md.disasm(data[off:off + length], addr):
        print("  0x%08x  %-8s %s" % (ins.address, ins.mnemonic, ins.op_str))


def scan_quad(data, base, addr):
    """The u-boot `_start`: `b <reset>` followed by the raw .quad CONST."""
    off = addr - base
    if off < 0 or off + 16 > len(data):
        print("  0x%08x outside band" % addr)
        return
    b = data[off:off + 4]
    quad = struct.unpack_from("<Q", data, off + 8)[0]
    imm = struct.unpack_from("<i", b, 0)[0] & 0x03FFFFFF
    if imm & (1 << 25):
        imm -= (1 << 26)
    print("  0x%08x  b+0x%x  quad=0x%016x" % (addr, imm * 4, quad))


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    path, base = sys.argv[1], int(sys.argv[2], 0)
    data = open(path, "rb").read()
    print("file   %s" % path)
    print("size   %d bytes (0x%x)" % (len(data), len(data)))
    print("base   0x%08x   top 0x%08x" % (base, base + len(data)))
    print("sha256 %s" % hashlib.sha256(data).hexdigest())

    if "--vs" in sys.argv:
        other = open(sys.argv[sys.argv.index("--vs") + 1], "rb").read()
        print("\ncompare vs %s" % sys.argv[sys.argv.index("--vs") + 1])
        print("  sha256 %s" % hashlib.sha256(other).hexdigest())
        if len(other) != len(data):
            print("  LENGTH DIFFERS: %d vs %d" % (len(data), len(other)))
            return 1
        diffs = [i for i in range(len(data)) if data[i] != other[i]]
        print("  identical: %s   differing bytes: %d" % (not diffs, len(diffs)))
        for i in diffs[:16]:
            print("    0x%08x  %02x != %02x" % (base + i, data[i], other[i]))

    args = []
    skip = False
    for x in sys.argv[3:]:
        if skip:
            skip = False
            continue
        if x == "--vs":
            skip = True
            continue
        args.append(x)
    for spec in args:
        name, _, rng = spec.partition("=")
        raddr, _, rlen = rng.partition(":")
        addr = int(raddr, 0)
        length = int(rlen, 0) if rlen else 0x40
        print("\n=== %s  0x%08x  (%d bytes) ===" % (name, addr, length))
        if "start" in name:
            scan_quad(data, base, addr)
        dis(data, base, addr, length)
    return 0


if __name__ == "__main__":
    sys.exit(main())
