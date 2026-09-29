#!/usr/bin/env python3
"""bl33_offline.py - hunt BL33 in RAM dumps that already exist on disk.

No USB, no device, no writes. Everything here runs on the .bin files under
reports/. Round 6 read 64 MiB and threw it away, so the question this answers
is "what do we actually have, and does it contain U-Boot at all".

  python3 tools/bl33_offline.py inventory
  python3 tools/bl33_offline.py strings reports/round6-mread/mread_20000000_100000.bin 0x20000000
  python3 tools/bl33_offline.py classify reports/round6-mread/mread_20000000_100000.bin 0x20000000
  python3 tools/bl33_offline.py start FILE BASE   # u-boot _start fingerprint
  python3 tools/bl33_offline.py xref FILE BASE   # ADRP/BL targets that stay inside [BASE,BASE+size)
  python3 tools/bl33_offline.py regions FILE BASE # what is actually in each run
  python3 tools/bl33_offline.py smc FILE BASE     # smc #0 sites and their argument setup

MARKERS are split in two. STRONG hits mean something: they only exist in a
U-Boot/Optimus image. WEAK ones ("ddr", "aml_") hit the Android heap all the
time, and treating them as evidence is exactly how round 6 ended up calling a
"ro.bootmode" a bootm hit.
"""
import hashlib
import math
import os
import re
import struct
import sys
from collections import Counter

# only ever in a u-boot/optimus image, zero hits in the android heap.
# cmd_tbl names carry their NUL: that is what separates U-Boot "bootm" from
# android "ro.bootmode" and u-boot "BL2" from a base64 blob.
STRONG = [
    b"U-Boot",
    b"u-boot",
    b"2015.01",
    b"g7ac5df7677",
    b"aml log : Sig Check",
    b"aml_sec_boot_check",
    b"Optimus",
    b"usb_pcd",
    b"usb_burning",
    b"set_usb_boot",
    b"do_bootm",
    b"gd->",
    b"optimus_working",
    b"optimus_buf_manager",
    b"loadaddr=",
    b"dtb_mem_addr=",
    b"boot_delay",
    b"bootm\0",
    b"setenv\0",
    b"fastboot\0",
    b"bl33\0",
    b"BL33\0",
    b"BL2\0",
    b"Amlogic",
    b"CMD_BUFF_SIZE",
    b"OPTIMUS_DOWNLOAD",
]

# hit constantly in android userspace, never evidence on their own
WEAK = [b"ddr", b"aml_", b"boot", b"log", b"bootm", b"BL2", b"bl33"]

# u-boot 2015.01 arm64 start.S, see arch/arm/cpu/armv8/start.S:22
#   _start: b reset
#   .align 3
#   _TEXT_BASE: .quad CONFIG_SYS_TEXT_BASE
# CONFIG_SYS_TEXT_BASE for gxl is 0x01000000 (arch/arm/include/asm/arch-gxl/cpu.h:41)
# so the quad at BASE+8 is BASE itself. self referential, one read proves it.
TEXT_BASE_CONST = 0x01000000


def load(path, base):
    data = open(path, "rb").read()
    return data, int(base, 0)


def entropy(blob):
    c = Counter(blob)
    n = len(blob)
    return -sum(v / n * math.log2(v / n) for v in c.values())


def inventory():
    """every *.bin under reports/, plus the nesting relations between them."""
    rows = []
    for root, _dirs, files in os.walk("reports"):
        for f in sorted(files):
            if not f.endswith(".bin"):
                continue
            p = os.path.join(root, f)
            d = open(p, "rb").read()
            m = re.search(r"_([0-9a-f]{8})_", f)
            base = int(m.group(1), 16) if m else None
            rows.append(dict(path=p, size=len(d), base=base,
                             sha=hashlib.sha256(d).hexdigest()))

    for r in rows:
        print("%-58s %9d  %s..%s" % (
            r["path"], r["size"],
            "?" if r["base"] is None else "0x%08x" % r["base"],
            "?" if r["base"] is None else "0x%08x" % (r["base"] + r["size"] - 1)))
        print("%58s  sha256 %s" % ("", r["sha"]))

    # a prefix of another file is zero new information, say so out loud
    print("\nnesting (smaller file is a byte exact prefix of the bigger one):")
    found = False
    for a in rows:
        da = open(a["path"], "rb").read()
        for b in rows:
            if a is b or b["size"] <= a["size"] or a["base"] != b["base"]:
                continue
            db = open(b["path"], "rb").read()
            if db[:a["size"]] == da:
                found = True
                print("  %s (%d) is a prefix of %s (%d)"
                      % (os.path.basename(a["path"]), a["size"],
                         os.path.basename(b["path"]), b["size"]))
    if not found:
        print("  none")
    return rows


def strings(data, base):
    for p in STRONG + WEAK:
        off = 0
        while True:
            i = data.find(p, off)
            if i < 0:
                break
            tag = "STRONG" if p in STRONG else "weak "
            print("\n[%s] %-16r abs 0x%08x  off 0x%06x  align %d (%s)"
                  % (tag, p.decode(), base + i, i, (base + i) % 4,
                     "4B" if (base + i) % 4 == 0 else "unaligned"))
            ctx = data[max(0, i - 128):i + len(p) + 128]
            cbase = base + max(0, i - 128)
            for off2 in range(0, len(ctx), 16):
                row = ctx[off2:off2 + 16]
                mark = "  <<<" if off2 == 128 else ""
                print("    %08x  %-47s |%s|%s"
                      % (cbase + off2, " ".join("%02x" % b for b in row),
                         "".join(chr(b) if 32 <= b < 127 else "." for b in row),
                         mark))
            # nearest printable neighbours, that is what tells code from heap
            lo = max(0, i - 4096)
            nb = [m for m in re.finditer(rb"[\x20-\x7e]{4,}", data[lo:i])
                  if p not in m.group()]
            if nb:
                print("    prev strings: %s"
                      % " | ".join(m.group().decode() for m in nb[-3:]))
            off = i + 1


def classify(data, base, block=0x10000):
    """per block: entropy, zero ratio, and whether it smells like aarch64 code
    or like a pointer/descriptor table."""
    for off in range(0, len(data), block):
        b = data[off:off + block]
        e = entropy(b)
        zr = b.count(0) / len(b)
        nop = sum(1 for i in range(0, len(b) - 3, 4)
                  if b[i:i + 4] == b"\x1f\x20\x03\xd5")
        ret = sum(1 for i in range(0, len(b) - 3, 4)
                  if b[i:i + 4] == b"\xc0\x03\x5f\xd6")
        brk = sum(1 for i in range(0, len(b) - 3, 4)
                  if b[i:i + 4] == b"\x00\x00\x20\xd4")
        words = struct.unpack_from("<%dI" % (len(b) // 4), b, 0)
        ptr = sum(1 for w in words
                  if (w & 3) == 0 and 0x20000000 <= w < 0x40000000)
        img = sum(1 for w in words
                  if (w & 3) == 0 and 0x01000000 <= w < 0x11000000)
        print("0x%08x ent %5.2f zero %4.2f nop %4d ret %4d brk %3d "
              "ptr2xx %4d ptr01x %4d"
              % (base + off, e, zr, nop, ret, brk, ptr, img))


def start(data, base):
    """look for the u-boot arm64 _start shape at every 64 KiB boundary.

    nothing here assumes the image starts where the dump starts, that is the
    whole point of the exercise.
    """
    hits = 0
    for off in range(0, max(1, len(data) - 0x40), 0x40):
        a = base + off
        w0 = struct.unpack_from("<I", data, off)[0]
        quad = struct.unpack_from("<Q", data, off + 8)[0]
        # b reset: opcode 0b000101 top 6 bits -> (w0 >> 26) == 0x05
        if (w0 >> 26) != 0x05:
            continue
        rel = ((w0 & 0x03FFFFFF) << 2)
        if rel & 0x80000000:
            rel -= 1 << 30
        if (w0 & 0xFC000000) != 0x14000000:
            continue
        tag = []
        if quad == a:
            tag.append("QUAD==BASE (self referential, STRONG)")
        elif quad == TEXT_BASE_CONST:
            tag.append("QUAD==0x%08x (CONFIG_SYS_TEXT_BASE, STRONG)" % quad)
        elif quad and quad < 0x10000000:
            tag.append("QUAD=0x%x (plausible _end/_bss offset)" % quad)
        if not tag:
            continue
        hits += 1
        print("0x%08x  b %+d  quad(8)=0x%016x  %s"
              % (a, rel, quad, "; ".join(tag)))
        for k in range(0, 0x40, 4):
            print("    +0x%02x %08x" % (k, struct.unpack_from("<I", data, off + k)[0]))
    if not hits:
        print("no u-boot _start shape found in this dump")


def xref(data, base):
    """ADRP+ADD pairs and BL targets that stay inside the image.

    a real u-boot has hundreds. a heap region has none that line up.
    """
    img_end = base + len(data)
    adrp_ok = 0
    bl_ok = 0
    adrp = {}
    words = struct.unpack_from("<%dI" % (len(data) // 4), data, 0)
    for i, w in enumerate(words):
        pc = base + i * 4
        if (w & 0x9F000000) == 0x90000000:  # ADRP
            imm = (w >> 5) & 0x7FFFF
            if imm & 0x40000:
                imm -= 0x80000
            page = (pc & ~0xFFF) + (imm << 12)
            adrp[pc] = page
            if base <= page < img_end:
                adrp_ok += 1
        if (w >> 26) == 0x25:  # BL
            imm = w & 0x03FFFFFF
            if imm & 0x02000000:
                imm -= 0x04000000
            tgt = pc + (imm << 2)
            if base <= tgt < img_end:
                bl_ok += 1
    print("dump 0x%08x..0x%08x  (%d KiB)" % (base, img_end - 1, len(data) >> 10))
    print("  ADRP whose page is inside the dump: %d" % adrp_ok)
    print("  BL whose target is inside the dump:   %d" % bl_ok)
    if len(adrp) > 4:
        print("  sample ADRP pages: %s"
              % " ".join("0x%08x" % (p & 0xFFFFFFFF) for p in list(adrp.values())[:8]))


def regions(data, base, gap=0x20000, block=0x1000):
    """What is actually in each occupied run, not how many markers matched.

    A 16 MiB dump of the wrong band is not one blob, it is a handful of very
    different things, and the only way to tell them apart is to look at the
    first bytes of each. Anything shorter than `gap` of zeros is merged in, a
    1 KiB hole inside an image is not a boundary.
    """
    runs = []
    cur = None
    for off in range(0, len(data), block):
        if data[off:off + block].count(0) == block:
            if cur is not None:
                runs.append((cur, off))
                cur = None
        elif cur is None:
            cur = off
    if cur is not None:
        runs.append((cur, len(data)))

    merged = []
    for a, b in runs:
        if merged and a - merged[-1][1] < gap:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))

    print("dump 0x%08x..0x%08x (%d MiB), %d occupied runs"
          % (base, base + len(data) - 1, len(data) >> 20, len(merged)))
    for a, b in merged:
        size = b - a
        e = entropy(data[a:b])
        e0 = entropy(data[a:a + min(size, 0x10000)])
        nop = sum(1 for i in range(a, b - 3, 4)
                  if data[i:i + 4] == b"\x1f\x20\x03\xd5")
        ret = sum(1 for i in range(a, b - 3, 4)
                  if data[i:i + 4] == b"\xc0\x03\x5f\xd6")
        brk = sum(1 for i in range(a, b - 3, 4)
                  if data[i:i + 4] == b"\x00\x00\x20\xd4")
        smc = sum(1 for i in range(a, b - 3, 4)
                  if (struct.unpack_from("<I", data, i)[0] & 0xFFE0001F) == 0xD4000000)
        print("\n0x%08x..0x%08x  %9d bytes (%.2f MiB)"
              % (base + a, base + b - 1, size, size / (1 << 20)))
        print("  entropy %.2f (first 64K %.2f)  nop %5d ret %5d brk %4d smc %3d"
              % (e, e0, nop, ret, brk, smc))
        for off in (a,):
            for k in range(0, 64, 16):
                row = data[off + k:off + k + 16]
                if not any(row):
                    break
                print("    %08x  %-47s |%s|"
                      % (base + off + k, " ".join("%02x" % c for c in row),
                         "".join(chr(c) if 32 <= c < 127 else "." for c in row)))
        # the longest strings decide what a data region is for
        ss = [(base + a + m.start(), m.group())
              for m in re.finditer(rb"[\x20-\x7e]{12,}", data[a:b])]
        ss.sort(key=lambda t: -len(t[1]))
        for ad, s in ss[:6]:
            print("    str 0x%08x %r" % (ad, s[:88]))


def smc(data, base):
    """Every `smc #imm` and the argument setup in the 12 instructions before it.

    do_bootm -> aml_sec_boot_check -> smc #0 is the only SMC path this research
    cares about (bl31_apis.c:255-308), so the interesting thing is not the SMC
    itself but the x0..x4 that the AML_DATA_PROCESS wrapper sets up.
    """
    words = struct.unpack_from("<%dI" % (len(data) // 4), data, 0)
    n = 0
    for i, w in enumerate(words):
        if (w & 0xFFE0001F) != 0xD4000000:
            continue
        pc = base + i * 4
        imm = (w >> 5) & 0xFFFF
        print("0x%08x  smc #0x%x" % (pc, imm))
        for k in range(max(0, i - 12), i):
            kw = words[k]
            # movz/movk immediate, the only way x0..x4 get built
            if (kw & 0xFF800000) == 0xD2800000:
                rd = kw & 0x1F
                val = (kw >> 5) & 0xFFFF
                print("    0x%08x  movz x%d, #0x%x" % (base + k * 4, rd, val))
            elif (kw & 0xFF800000) == 0xF2800000:
                rd = kw & 0x1F
                val = (kw >> 5) & 0xFFFF
                sh = ((kw >> 21) & 3) * 16
                print("    0x%08x  movk x%d, #0x%x, lsl #%d"
                      % (base + k * 4, rd, val, sh))
        n += 1
    if not n:
        print("no smc in this dump")
    else:
        print("\n%d smc site(s)" % n)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    verb = sys.argv[1]
    if verb == "inventory":
        inventory()
    elif verb in ("strings", "classify", "start", "xref", "regions", "smc"):
        data, base = load(sys.argv[2], sys.argv[3])
        {"strings": strings, "classify": classify, "start": start,
         "xref": xref, "regions": regions, "smc": smc}[verb](data, base)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
