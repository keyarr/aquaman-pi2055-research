#!/usr/bin/env python3
"""bl33_persist.py - round 14: cut the relocated BL33 image out of a DRAM band.

Offline only. Round 13 left an 8 MiB band (0x37800000..0x38000000) that contains
the relocated U-Boot at 0x37e18000. This carves the image out of that band, so
the image exists on disk as an artifact instead of "an offset inside a dump":

  python3 tools/bl33_persist.py reports/round13-reloc-verify/mread_37800000_00800000.bin \
      0x37800000 0x37e18000 0x37ff0000 reports/round14-bl33-persist/bl33-37e18000.bin

why 0x37ff0000 and not 0x37f80000: the image end is a fixed computation, not a
guess. arch/arm/lib/board.c:255-437 (setup_dest_addr):

    gd->mon_len = &__bss_end - _start;
    addr  = CONFIG_SYS_SDRAM_BASE + get_effective_memsize();   /* ram top */
    addr -= PGTABLE_SIZE;  addr &= ~0xffff;                    /* TLB table */
    addr -= gd->mon_len;   addr &= ~0xfff;                     /* relocaddr  */

with PGTABLE_SIZE = 0x10000 (arch/arm/include/asm/system.h:17), the observed
relocaddr = 0x37e18000 pins ram top = 0x38000000 and mon_len in
(0x1d7000, 0x1d8000], i.e. image end in (0x37fef000, 0x37ff0000]. the 64 KiB
above it is the page table, and it is there in the dump: 0x37ff0000 starts with
0x...0411 / 0x...0401 block descriptors.

printer, no writes: it hashes what it reads, classifies every 4 KiB page, and
never touches a device.
"""
import hashlib
import struct
import sys

IMAGE = 0x37E18000
LOG2 = 0x01000000          # CONFIG_SYS_TEXT_BASE, the link address
TLB_LO, TLB_HI = 0x37FF0000, 0x38000000


def pages(data, base, lo, hi, size=0x1000):
    """classify every page: code / strings / data / zero."""
    out = []
    for a in range(lo, hi, size):
        p = data[a - base:a - base + size]
        if not p:
            break
        w = struct.unpack_from("<%dI" % (len(p) // 4), p, 0)
        code = 0
        for x in w:
            if (x >> 26) == 0x25 or (x >> 26) == 0x05:
                code += 1
        z = p.count(0)
        strs = 0
        i = 0
        while True:
            i = p.find(b"\0", i)
            if i < 0:
                break
            j = i
            while j > 0 and 0x20 <= p[j - 1] < 0x7F:
                j -= 1
            if i - j >= 6:
                strs += 1
            i += 1
        if z == len(p):
            kind = "zero"
        elif code >= 64:
            kind = "code"
        elif strs >= 4:
            kind = "rodata/strings"
        else:
            kind = "data"
        out.append((a, kind, code, strs))
    return out


def runs(rows):
    out = []
    for a, kind, _c, _s in rows:
        if out and out[-1][0] == kind and out[-1][2] == a:
            out[-1][2] = a + 0x1000
        else:
            out.append([kind, a, a + 0x1000])
    return out


def main():
    if len(sys.argv) < 6:
        sys.exit(__doc__)
    band, base = sys.argv[1], int(sys.argv[2], 0)
    lo, hi = int(sys.argv[3], 0), int(sys.argv[4], 0)
    out_path = sys.argv[5]
    d = open(band, "rb").read()
    print("band      %s" % band)
    print("band size 0x%x   base 0x%08x" % (len(d), base))
    print("band sha256 %s" % hashlib.sha256(d).hexdigest())
    if not (base <= lo < hi <= base + len(d)):
        sys.exit("image window 0x%08x..0x%08x is outside the band" % (lo, hi))

    img = d[lo - base:hi - base]
    open(out_path, "wb").write(img)
    print("\nimage     %s" % out_path)
    print("image     load 0x%08x  base 0x%08x  size 0x%x (%d bytes)"
          % (LOG2, lo, len(img), len(img)))
    print("image sha256 %s" % hashlib.sha256(img).hexdigest())
    print("reloc_off 0x%x   (= 0x%08x - 0x%08x)" % (lo - LOG2, lo, LOG2))
    print("mon_len   0x%x   (derived, see the docstring)" % (len(img),))

    # does the tail look like the page table board.c reserved?
    pte = 0
    for i in range(0, TLB_HI - TLB_LO, 8):
        w = struct.unpack_from("<Q", d, TLB_LO - base + i)[0]
        if w and (w & 3) == 1:
            pte += 1
    print("\npage table 0x%08x..0x%08x: %d descriptor-shaped words"
          % (TLB_LO, TLB_HI, pte))

    rows = pages(d, base, lo, hi)
    print("\npage map (4 KiB pages, contiguous runs)\n")
    print("%-16s %-15s %s" % ("range", "kind", "pages"))
    for kind, a, b in runs(rows):
        print("0x%08x..0x%08x %-15s %4d" % (a, b - 1, kind, (b - a) >> 12))

    last = len(img)
    while last > 0 and img[last - 1] == 0:
        last -= 1
    print("\nhighest non-zero byte inside the image: 0x%08x" % (lo + last - 1))
    print("tail from there to 0x%08x is zero: the relocated .bss" % hi)

    # the page table above the image, dumped so the bound is evidence
    print("\nfirst 16 descriptors at 0x%08x:" % TLB_LO)
    for i in range(16):
        w = struct.unpack_from("<Q", d, TLB_LO - base + i * 8)[0]
        print("  0x%08x 0x%016x" % (TLB_LO + i * 8, w))


if __name__ == "__main__":
    main()
