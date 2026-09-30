#!/usr/bin/env python3
"""reloc_analyze.py - is the relocated BL33 inside this band?

Round 12. offline only. whatever band gets read (round 11 derived the relocated
U-Boot to ~0x37d90000..0x37e10000), this answers "is this it, and where exactly":

  - the brief's marker strings, with location
  - the secure-storage stub triple  smc #0 ; ret  (the fragment's signature)
  - the 13 BL31 share-storage / secure-key ids as movz+movk
  - AML_DATA_PROCESS 0x820000ff, every encoding
  - the u-boot _start fingerprint (b reset + a self-referential quad)
  - opcode census per 64 KiB: code vs data vs zero
  - cmd_tbl shape, and an opcode-exact svc/hvc/smc census

  python3 tools/reloc_analyze.py reports/round12-reloc/mread_37800000_00800000.bin 0x37800000
"""
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bl33_shape import (census, cmd_tbl, ids, smc, start, strings,  # noqa
                        IDS, GXB_IMG_LOAD_ADDR)

# smc #0 ; ret  -- exactly what the three secure-storage stubs are
STUB = bytes.fromhex("030000d4c0035fd6")


def stub_scan(data, base, gap=0x20000):
    """every `smc #0` immediately followed by `ret`, clustered.

    a single one is a stub; three inside 32 bytes is bl31_storage_ops*; a run of
    them near the u-boot ids is the secure-storage module. this is the cheapest
    fingerprint that says "the fragment is here too".
    """
    hits = []
    i = 0
    while True:
        i = data.find(STUB, i)
        if i < 0:
            break
        hits.append(i)
        i += 4
    print("\nsecure-storage stub triple (`smc #0 ; ret`), %d hit(s)" % len(hits))
    clusters = []
    for h in hits:
        if clusters and h - clusters[-1][-1] < gap:
            clusters[-1].append(h)
        else:
            clusters.append([h])
    for c in clusters:
        print("  cluster 0x%08x..0x%08x  %d stub(s): %s"
              % (base + c[0], base + c[-1], len(c),
                 " ".join("0x%08x" % (base + x) for x in c[:8])))
    if not hits:
        print("  none -> this band is not the secure-storage module")
    return hits


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    path, base = sys.argv[1], int(sys.argv[2], 0)
    data = open(path, "rb").read()
    print("dump %s\nsize %d  base 0x%08x\n" % (path, len(data), base))

    strings(data, base)
    census(data, base)
    start(data, base)
    stub_scan(data, base)
    ids(data, base, set(IDS) | {GXB_IMG_LOAD_ADDR})
    cmd_tbl(data, base)
    smc(data, base)


if __name__ == "__main__":
    main()
