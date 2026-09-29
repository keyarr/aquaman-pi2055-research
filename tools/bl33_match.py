#!/usr/bin/env python3
"""bl33_match.py - match the 0x01040000..0x0107ffff window against U-Boot/Amlogic.

Offline only, reads the round 8 dump from disk. Two questions:

  1. is that window really AArch64, and are the SMC sites in it real instructions
     or data that happens to decode?
  2. do the SMC function ids inside it match drivers/securestorage/securestorage.c
     from the khadas u-boot tree?

  python3 tools/bl33_match.py reports/round8-bl33-read/mread_01000000_01000000.bin

Everything printed is derived from the dump, no hardcoded addresses beyond the
reference id table at the bottom, which comes from
.src/u-boot-khadas/arch/arm/include/asm/arch-gxl/bl31_apis.h:34-82.
"""
import re
import struct
import sys
from collections import Counter

try:
    from capstone import CS_ARCH_ARM64, CS_MODE_ARM, Cs
except ImportError:
    sys.exit("capstone is required: pip install capstone")

DUMP = "reports/round8-bl33-read/mread_01000000_01000000.bin"
BASE = 0x01000000
WIN = (0x01040000, 0x01080000)

# arch/arm/include/asm/arch-gxl/bl31_apis.h:34-82
BL31_IDS = {
    0x82000023: "GET_SHARE_STORAGE_IN_BASE",
    0x82000024: "GET_SHARE_STORAGE_OUT_BASE",
    0x82000025: "GET_SHARE_STORAGE_BLOCK_BASE",
    0x82000026: "GET_SHARE_STORAGE_MESSAGE_BASE",
    0x82000027: "GET_SHARE_STORAGE_BLOCK_SIZE",
    0x82000028: "SET_STORAGE_INFO",
    0x82000060: "SECURITY_KEY_QUERY",
    0x82000061: "SECURITY_KEY_READ",
    0x82000062: "SECURITY_KEY_WRITE",
    0x82000063: "SECURITY_KEY_TELL",
    0x82000064: "SECURITY_KEY_VERIFY",
    0x82000065: "SECURITY_KEY_STATUS",
    0x82000066: "SECURITY_KEY_NOTIFY",
    0x82000067: "SECURITY_KEY_LIST",
    0x82000068: "SECURITY_KEY_REMOVE",
    0x82000069: "SECURITY_KEY_NOTIFY_EX",
    0x8200006A: "SECURITY_KEY_SET_ENCTYPE",
    0x8200006B: "SECURITY_KEY_GET_ENCTYPE",
    0x8200006C: "SECURITY_KEY_VERSION",
    0x820000FF: "AML_DATA_PROCESS",
}

# SVC/HVC/SMC share one encoding: 1101 0100 000 imm16 00 opc. opc 1/2/3.
SUP = {0xD4000001: "svc", 0xD4000002: "hvc", 0xD4000003: "smc"}


def disassemble(data, start, end):
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.skipdata = True
    insns = list(md.disasm(data[start - BASE:end - BASE], start))
    return insns, md


def decode_rate(data, start, end):
    """how much of the window decodes without falling into .byte."""
    insns, _ = disassemble(data, start, end)
    slots = (end - start) // 4
    skipped = sum(1 for i in insns if i.mnemonic == ".byte")
    return slots, len(insns) - skipped, skipped


def sup_sites(data, lo, hi, label):
    """every svc/hvc/smc in [lo,hi), as an aligned word match plus a decode."""
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    rows = []
    for off in range(lo - BASE, hi - BASE, 4):
        w = struct.unpack_from("<I", data, off)[0]
        op = w & 0xFFE0001F
        if op not in SUP:
            continue
        pc = BASE + off
        ins = list(md.disasm(data[off:off + 4], pc))
        rows.append((pc, SUP[op], (w >> 5) & 0xFFFF, bool(ins)))
    print("\n%s  0x%08x..0x%08x: %d supervisor-call word(s)"
          % (label, lo, hi - 1, len(rows)))
    for pc, op, imm, dec in rows:
        print("  0x%08x  %s #0x%04x   decode=%s" % (pc, op, imm, "ok" if dec else "FAIL"))
    return rows


def sup_callers(data, s, e):
    """who calls the supervisor-call stubs, from anywhere in the dump.

    the stubs themselves take no arguments, so a caller that reaches them is
    where the smc function id has to be. that is the whole point of the window.
    """
    words = struct.unpack_from("<%dI" % (len(data) // 4), data, 0)
    stubs = set()
    for off in range(s - BASE, e - BASE, 4):
        w = struct.unpack_from("<I", data, off)[0]
        if (w & 0xFFE0001F) == 0xD4000003:
            stubs.add(BASE + off)
    callers = {t: [] for t in stubs}
    for i, w in enumerate(words):
        if (w >> 26) != 0x25:
            continue
        imm = w & 0x03FFFFFF
        if imm & 0x02000000:
            imm -= 0x04000000
        t = BASE + i * 4 + (imm << 2)
        if t in callers:
            callers[t].append(BASE + i * 4)
    print("\nBL callers of each supervisor-call stub, whole dump")
    for t in sorted(callers):
        n = callers[t]
        print("  0x%08x  %d caller(s)  %s"
              % (t, len(n), " ".join("0x%08x" % x for x in n[:6])))


def stale_copy(data):
    """round 8 §3.1 read a duplicate DTB at +0x80000. it is a stale bitmap copy.

    0x01010000 is byte identical to 0x01090000 for 114688 bytes, and
    0x01090000 is GXB_IMG_LOAD_ADDR + 0x10000, so the resource image was staged
    once at 0x01000000 and once at 0x01080000.
    """
    a, b = 0x01010000, 0x01090000
    best = (0, 0)
    for off in range(0, 0x30000, 0x1000):
        n = 0
        while (a + off + n - BASE < 0x01040000 and a + off + n - BASE < len(data)
               and data[a + off + n - BASE] == data[b + off + n - BASE]):
            n += 1
        if n > best[0]:
            best = (n, off)
    n, off = best
    lo, hi = a + off, b + off
    print("\nlongest byte-identical stretch 0x%08x+X vs 0x%08x+X" % (a, b))
    print("  %d bytes: 0x%08x..0x%08x == 0x%08x..0x%08x"
          % (n, lo, lo + n - 1, hi, hi + n - 1))
    print("  offset inside the AML_RES image: 0x%x, implied staging base 0x%08x"
          % (hi - 0x01080000, lo - (hi - 0x01080000)))


def bl31_ids(data):
    """movz + movk lsl#16 pairs, the only way these 32-bit ids get materialised.

    round 8 searched for the packed literal and found 0 hits, which is correct:
    bl31_apis.c builds them with movz/movk, never with a literal pool.
    """
    words = struct.unpack_from("<%dI" % (len(data) // 4), data, 0)
    movz = {}
    for i, w in enumerate(words):
        if (w & 0xFF800000) == 0xD2800000:
            movz[(i, w & 0x1F)] = (w >> 5) & 0xFFFF
    found = {}
    for i, w in enumerate(words):
        if (w & 0xFF800000) != 0xF2800000 or ((w >> 21) & 3) != 1:
            continue
        lo = movz.get((i - 1, w & 0x1F))
        if lo is None:
            continue
        found.setdefault(((w >> 5) & 0xFFFF) << 16 | lo, []).append(BASE + (i - 1) * 4)
    return found


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DUMP
    data = open(path, "rb").read()

    print("dump %s" % path)
    print("size %d, base 0x%08x" % (len(data), BASE))

    s, e = WIN
    slots, ok, bad = decode_rate(data, s, e)
    print("\nwindow 0x%08x..0x%08x  %d slots, %d decoded, %d undecodable (%.2f%%)"
          % (s, e - 1, slots, ok, bad, 100.0 * bad / slots))

    sup_sites(data, BASE, BASE + len(data), "whole dump")
    sup_sites(data, 0x0169E000, 0x02000000, "kernel region")
    sup_sites(data, s, e, "candidate window")

    ids = bl31_ids(data)
    sup_callers(data, s, e)

    print("\nBL31 share-storage / secure-key ids built with movz+movk, whole dump")
    print("%-10s %-30s %s" % ("id", "name", "sites"))
    for tid in sorted(BL31_IDS):
        sites = ids.get(tid, [])
        print("0x%08x  %-30s %s"
              % (tid, BL31_IDS[tid], " ".join("0x%08x" % x for x in sites) or "-"))

    print("\nBL targets leaving the window, by 64 KiB bucket")
    words = struct.unpack_from("<%dI" % ((e - s) // 4), data, s - BASE)
    out = Counter()
    for i, w in enumerate(words):
        if (w >> 26) != 0x25:
            continue
        imm = w & 0x03FFFFFF
        if imm & 0x02000000:
            imm -= 0x04000000
        t = s + i * 4 + (imm << 2)
        if not s <= t < e:
            out[t >> 16] += 1
    for k, v in sorted(out.items()):
        print("  0x%08x..  %d" % (k << 16, v))

    print("\nconstant delta that maps out-of-window BL targets back inside")
    tg = []
    for i, w in enumerate(words):
        if (w >> 26) != 0x25:
            continue
        imm = w & 0x03FFFFFF
        if imm & 0x02000000:
            imm -= 0x04000000
        t = s + i * 4 + (imm << 2)
        if not s <= t < e:
            tg.append(t)
    hits = [(dd, sum(1 for t in tg if s <= t - dd < e))
            for dd in range(0, 0x100001, 4)]
    top = max(n for _, n in hits)
    good = [dd for dd, n in hits if n == top]
    print("  best count %d of %d, reached by %d different deltas 0x%06x..0x%06x"
          % (top, len(tg), len(good), good[0], good[-1]))
    print("  NOT PROVEN: the count does not pick a unique delta, so this is a")
    print("  relocation smell, not a measured reloc offset. see the report.")

    # the "second copy of the tree" of round 8. it is not one, and this is why.
    stale_copy(data)

    print("\nd00dfeed occurrences in the whole dump")
    i = 0
    hits = []
    while True:
        i = data.find(b"\xd0\x0d\xfe\xed", i)
        if i < 0:
            break
        hits.append(BASE + i)
        i += 1
    for h in hits:
        print("  0x%08x" % h)
    print("  %d total. round 8 claimed two. see the report." % len(hits))


if __name__ == "__main__":
    main()
