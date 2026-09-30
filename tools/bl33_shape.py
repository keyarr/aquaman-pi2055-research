#!/usr/bin/env python3
"""bl33_shape.py - round 11: shape searches, not string hunting.

Offline only, reads a RAM dump from disk. This answers the questions round 10
left open and the ones the brief asks for explicitly (TAREFAS 3-6):

  strings    the brief's exact marker list, with location and region
  census     AArch64 opcode census per 64 KiB: b / bl / ret / brk / adrp /
             ldr-literal / prologue, so "dense code" is a number, not a vibe
  start      the u-boot _start fingerprint, scanned at every 8-byte offset,
             both the self-referential quad and the CONFIG_SYS_TEXT_BASE quad
  dupes      is there a SECOND copy of the secure-storage window (relocation)?
             page-level and 64-byte-level hashes, window vs the rest of the dump
  ids        every materialisation of a BL31 function id by ANY encoding:
             movz+movk (any order, up to 4 instructions apart), and a raw
             little-endian 32-bit literal in the dump
  consts     the same for GXB_IMG_LOAD_ADDR (0x01080000)
  cmd_tbl    pointer tables whose slots point at NUL-terminated names
  smc        opcode-exact svc/hvc/smc over the whole dump, with the x0 arg setup
  ptrtab     dump and classify an absolute pointer table (round 8 found one at
             0x01f00000 pointing into 0x0008xxxx, outside the dump)

  python3 tools/bl33_shape.py DUMP.bin [BASE]
  python3 tools/bl33_shape.py reports/round11-bl33-read/mread_01000000_01000000.bin
"""
import hashlib
import re
import struct
import sys
from collections import Counter, defaultdict

BASE = 0x01000000
CODE_WIN = (0x01040000, 0x01080000)

# the brief's exact list, verbatim. region hits are noise, see the report.
BRIEF = [
    b"U-Boot", b"2015.01", b"g7ac5df7677", b"aml log : Sig Check",
    b"aml_sec_boot_check", b"Optimus", b"fastboot", b"do_bootm", b"bootm",
    b"set_usb_boot", b"usb_pcd", b"Wrong Image Format", b"reset", b"reboot",
]

# arch/arm/include/asm/arch-gxl/bl31_apis.h
IDS = {
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
    0x820000FF: "AML_DATA_PROCESS",   # x0 of the secure-boot SMC
}
GXB_IMG_LOAD_ADDR = 0x01080000


def load(path):
    data = open(path, "rb").read()
    return data


def run_extent(data, base, off):
    """where does the non-zero run that contains `off` start and end (1 KiB grid)?"""
    lo = off
    while lo >= 0x1000 and data[lo - 0x1000:lo].count(0) < 0x1000:
        lo -= 0x1000
    hi = off
    while hi + 0x1000 <= len(data) and data[hi:hi + 0x1000].count(0) < 0x1000:
        hi += 0x1000
    return base + lo, base + hi


# --------------------------------------------------------------------------- #
def strings(data, base):
    print("brief marker list over 0x%08x..0x%08x (%d bytes)\n"
          % (base, base + len(data) - 1, len(data)))
    for p in BRIEF:
        hits = []
        i = 0
        while True:
            i = data.find(p, i)
            if i < 0:
                break
            hits.append(i)
            i += 1
        verdict = "ABSENT" if not hits else "%d hit(s)" % len(hits)
        print("%-22r %s" % (p, verdict))
        for i in hits[:12]:
            a, b = run_extent(data, base, i)
            print("      abs 0x%08x  in run 0x%08x..0x%08x  align %d"
                  % (base + i, a, b, (base + i) % 4))
        if len(hits) > 12:
            print("      ... %d more" % (len(hits) - 12))
    print()


# --------------------------------------------------------------------------- #
def census(data, base, block=0x10000):
    """opcode census. dense code has prologues + bl + adrp; a kernel region has
    nop sleds and ret; a DTB has none of it."""
    print("opcode census per 64 KiB  (b/bl/adrp are unaligned-word counts)\n")
    print("%-10s %6s %6s %6s %6s %6s %6s %6s"
          % ("addr", "b", "bl", "ret", "brk", "adrp", "ldrlit", "stp"))
    for off in range(0, len(data), block):
        b = data[off:off + block]
        n = len(b) // 4
        w = struct.unpack_from("<%dI" % n, b, 0)
        cnt = Counter()
        for x in w:
            top = x >> 26
            if top == 0x05 and (x & 3) == 0:
                cnt["b"] += 1
            elif top == 0x25:
                cnt["bl"] += 1
            if x == 0xD65F03C0:
                cnt["ret"] += 1
            if (x & 0xFFE0001F) == 0xD4200000:
                cnt["brk"] += 1
            if (x & 0x9F000000) == 0x90000000:
                cnt["adrp"] += 1
            if x & 0x3B000000 == 0x18000000:
                cnt["ldrlit"] += 1
            if (x & 0xFFC003FF) == 0xA9B007FD or (x & 0xFFC003FF) == 0xA9BF07FD:
                cnt["stp"] += 1
        print("0x%08x %6d %6d %6d %6d %6d %6d %6d"
              % (base + off, cnt["b"], cnt["bl"], cnt["ret"], cnt["brk"],
                 cnt["adrp"], cnt["ldrlit"], cnt["stp"]))
    print()


# --------------------------------------------------------------------------- #
def start(data, base):
    """u-boot arm64 _start: `b reset` then, 8 bytes later, a .quad.

    the quad is a raw literal so it survives relocation. a self-referential
    quad (quad == its own address) means BASE == link address.
    """
    print("_start fingerprint, every 8 bytes\n")
    n = 0
    for off in range(0, len(data) - 0x40, 8):
        w0 = struct.unpack_from("<I", data, off)[0]
        if (w0 & 0xFC000000) != 0x14000000:
            continue
        quad = struct.unpack_from("<Q", data, off + 8)[0]
        a = base + off
        tags = []
        if quad == a:
            tags.append("QUAD==BASE self-referential STRONG")
        if quad == BASE:
            tags.append("QUAD==CONFIG_SYS_TEXT_BASE STRONG")
        if 0x100000 <= quad <= 0x8000000:
            tags.append("QUAD=0x%x plausible _end/_bss offset" % quad)
        if not tags:
            continue
        n += 1
        print("0x%08x  b+0x%x  quad=0x%016x  %s"
              % (a, ((w0 & 0x03FFFFFF) << 2), quad, "; ".join(tags)))
    print("  %d candidate(s)\n" % n)


# --------------------------------------------------------------------------- #
def dupes(data, base):
    """is the secure-storage window duplicated anywhere? that is relocation."""
    lo, hi = CODE_WIN
    win = data[lo - base:hi - base]
    print("second-copy search for 0x%08x..0x%08x (%d KiB)\n"
          % (lo, hi, len(win) >> 10))

    # 1. page hashes: is any 4 KiB page of the window byte-identical to a page
    #    outside the window?
    pages = defaultdict(list)
    for off in range(0, len(data) - 0xFFF, 0x1000):
        pages[hashlib.blake2b(data[off:off + 0x1000], digest_size=8).digest()].append(off)
    outside = 0
    for off in range(lo - base, hi - base, 0x1000):
        h = hashlib.blake2b(data[off:off + 0x1000], digest_size=8).digest()
        others = [o for o in pages[h] if not (lo - base <= o < hi - base)]
        if others:
            outside += 1
            print("  page 0x%08x identical to %s"
                  % (base + off, " ".join("0x%08x" % (base + o) for o in others[:4])))
    print("  %d of %d window pages have an identical page outside the window"
          % (outside, (hi - lo) >> 12))

    # 2. 64-byte block hashes at 4-byte alignment: find the longest shared block.
    def blocks(lo2, hi2):
        d = defaultdict(list)
        for off in range(lo2, hi2 - 0x40, 4):
            d[hashlib.blake2b(data[off:off + 0x40], digest_size=8).digest()].append(off)
        return d
    winb = blocks(lo - base, hi - base)
    rest = blocks(0, len(data) - 0x40)
    shared = 0
    examples = []
    for h, offs in winb.items():
        others = [o for o in rest.get(h, []) if not (lo - base <= o < hi - base)]
        if others:
            shared += 1
            if len(examples) < 8:
                examples.append((base + offs[0], base + others[0]))
    print("  %d distinct 64-byte window blocks also occur outside the window" % shared)
    for a, b in examples:
        print("      window 0x%08x  ==  outside 0x%08x   delta 0x%x" % (a, b, (b - a) & 0xFFFFFFFFFFFFFFFF))
    if not shared:
        print("  NO second copy of the window in this dump")
    print()


# --------------------------------------------------------------------------- #
def ids(data, base, targets):
    """every way a 32-bit constant can be materialised, not just movz+movk."""
    n = len(data) // 4
    w = struct.unpack_from("<%dI" % n, data, 0)
    found = defaultdict(list)

    def val16(x):   # movz/movk payload
        return (x >> 5) & 0xFFFF

    for i, x in enumerate(w):
        # movz/movk, any order, same rd, up to 4 instructions apart
        if (x & 0xFF800000) not in (0xD2800000, 0xF2800000):
            continue
        rd = x & 0x1F
        acc = 0
        for j in range(i, min(i + 5, n)):
            y = w[j]
            if (y & 0xFF800000) not in (0xD2800000, 0xF2800000):
                break
            if (y & 0x1F) != rd:
                break
            if (y & 0xFF800000) == 0xD2800000:
                acc = 0  # a movz resets the register
            hw = (y >> 21) & 3
            mask = 0xFFFF << (hw * 16)
            acc = (acc & ~mask) | (val16(y) << (hw * 16))
            if acc in targets:
                found[acc].append(("%08x..%08x" % (base + i * 4, base + j * 4)))
        # raw 32-bit literal in the dump
        if x in targets:
            found[x].append("literal at 0x%08x" % (base + i * 4))
        # orr-immediate into a zero register (a 64-bit "mov" of a bitmask imm)
        if (x & 0x7F800000) == 0x32000000:
            pass  # 0x820000ff / 0x01080000 are not bitmask-immediates

    print("materialisation of constants by movz/movk (any order) or literal\n")
    for t in sorted(targets):
        name = IDS.get(t, "GXB_IMG_LOAD_ADDR" if t == GXB_IMG_LOAD_ADDR else "")
        sites = found.get(t, [])
        print("0x%08x  %-31s %s"
              % (t, name, ("%d: " % len(sites)) + " ".join(sites[:8]) if sites else "ABSENT"))
        if len(sites) > 8:
            print("           ... %d more" % (len(sites) - 8))
    print()


# --------------------------------------------------------------------------- #
def cmd_tbl(data, base):
    """look for a u-boot command table by shape: a run of slots where slot+0x00
    and slot+0x20 are pointers to NUL-terminated names and slot+0x10 points
    into dense code. gives gd->reloc_off if found (cmd_bootm.c:97)."""
    n = len(data) // 8
    q = struct.unpack_from("<%dQ" % n, data, 0)

    def is_str_ptr(v):
        if not base <= v < base + len(data):
            return False
        o = v - base
        e = data.find(b"\0", o, o + 64)
        if e < 0 or e == o:
            return False
        return all(32 <= c < 127 for c in data[o:e]) and e - o >= 3

    cands = 0
    for i in range(n - 8):
        v = q[i]
        if not is_str_ptr(v):
            continue
        # cmd_tbl_s: name, maxargs(int), repeatable(int), cmd(ptr), usage(ptr), help(ptr)
        name_ptr = v
        maxargs, repeat = q[i + 1] & 0xFFFFFFFF, (q[i + 1] >> 32) & 0xFFFFFFFF
        cmd_ptr = q[i + 2]
        usage, help_ = q[i + 3], q[i + 4]
        if maxargs > 7 or repeat > 2:
            continue
        if not (is_str_ptr(usage) or is_str_ptr(help_)):
            continue
        if not base <= cmd_ptr < base + len(data):
            continue
        cands += 1
        nm = data[name_ptr - base:data.find(b"\0", name_ptr - base)].decode()
        print("  slot 0x%08x  name=%-14r cmd=0x%08x usage=%s help=%s"
              % (base + i * 8, nm, cmd_ptr,
                 "0x%08x" % usage if is_str_ptr(usage) else "-",
                 "0x%08x" % help_ if is_str_ptr(help_) else "-"))
        if cands >= 25:
            break
    print("  %d cmd_tbl-shaped slot(s)%s\n"
          % (cands, "" if cands else " -> no gd->reloc_off recoverable this way"))


# --------------------------------------------------------------------------- #
def smc(data, base):
    n = len(data) // 4
    w = struct.unpack_from("<%dI" % n, data, 0)
    sup = {0xD4000001: "svc", 0xD4000002: "hvc", 0xD4000003: "smc"}
    print("opcode-exact supervisor calls over the whole dump\n")
    total = 0
    for i, x in enumerate(w):
        if (x & 0xFFE0001F) not in sup:
            continue
        total += 1
        pc = base + i * 4
        args = []
        for k in range(max(0, i - 8), i):
            y = w[k]
            if (y & 0xFF800000) == 0xD2800000:
                args.append("movz x%d,#0x%x" % (y & 0x1F, (y >> 5) & 0xFFFF))
            elif (y & 0xFF800000) == 0xF2800000:
                args.append("movk x%d,#0x%x,lsl#%d"
                            % (y & 0x1F, (y >> 5) & 0xFFFF, ((y >> 21) & 3) * 16))
            elif (y & 0xFFC00000) == 0x91000000:
                args.append("add x%d,x%d,#0x%x"
                            % (y & 0x1F, (y >> 5) & 0x1F, (y >> 10) & 0xFFF))
        a, b = run_extent(data, base, i * 4)
        print("0x%08x  %s #0x%04x   run 0x%08x..0x%08x"
              % (pc, sup[x & 0xFFE0001F], (x >> 5) & 0xFFFF, a, b))
        if args:
            print("        %s" % " | ".join(args))
    print("  %d total\n" % total)


# --------------------------------------------------------------------------- #
def ptrtab(data, base, addr, count=176):
    off = addr - base
    print("pointer table at 0x%08x\n" % addr)
    prev = None
    for i in range(count):
        v = struct.unpack_from("<Q", data, off + i * 8)[0]
        if v == 0:
            continue
        inside = "in-dump" if base <= v < base + len(data) else "OUTSIDE"
        arrow = ""
        if prev is not None and v > prev:
            arrow = "+0x%x" % (v - prev)
        elif prev is not None:
            arrow = "-0x%x" % (prev - v)
        print("  +0x%03x 0x%016x  %-8s %s" % (i * 8, v, inside, arrow))
        prev = v
    print()


# --------------------------------------------------------------------------- #
def main():
    path = sys.argv[1] if len(sys.argv) > 1 else \
        "reports/round11-bl33-read/mread_01000000_01000000.bin"
    base = int(sys.argv[2], 0) if len(sys.argv) > 2 else BASE
    data = load(path)
    print("dump %s\nsize %d  base 0x%08x  sha256 %s\n"
          % (path, len(data), base, hashlib.sha256(data).hexdigest()))
    strings(data, base)
    census(data, base)
    start(data, base)
    dupes(data, base)
    ids(data, base, set(IDS) | {GXB_IMG_LOAD_ADDR})
    cmd_tbl(data, base)
    smc(data, base)
    ptrtab(data, base, 0x01F00000)


if __name__ == "__main__":
    main()
