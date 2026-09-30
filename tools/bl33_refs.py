#!/usr/bin/env python3
"""bl33_refs.py - ask the surviving code where it thinks it lives.

Round 10 named some functions in the 0x01040000 window and stopped, because
everything it needs to go further lives in pages the window points at and the
dump no longer has. This tool measures the footprint of those pointers, which
is the only thing in the dump that still describes the rest of the image:

  python3 tools/bl33_refs.py footprint FILE BASE WIN_LO WIN_HI
  python3 tools/bl33_refs.py reloc     FILE BASE WIN_LO WIN_HI
  python3 tools/bl33_refs.py start     FILE
  python3 tools/bl33_refs.py ids       FILE BASE

`reloc` is the one that needed care. AArch64 is PC-relative everywhere except
ADR and ADRP, so a relocated copy keeps every BL and every load/store offset
bit-identical and only ADR/ADRP immediates move. Round 10 searched on BL
offsets alone and got 47413 candidate deltas, which is not a result. Matching
with ADR/ADRP wildcarded is a real match, and the negative is worth nothing
unless the matcher is proven to find a copy that is there, so `reloc` plants
one, checks it is found, and only then reports the real count.
"""
import struct
import sys
from collections import Counter

MIN_RUN = 128  # bytes that must agree before a hit is called a copy


def words(data):
    return struct.unpack_from("<%dI" % (len(data) // 4), data, 0)


def is_posdep(x):
    """ADR and ADRP are the only position-dependent encodings in AArch64."""
    return (x & 0x9F000000) in (0x10000000, 0x90000000)


def refs(w, base, lo, hi):
    """every address the window points at, split by how it points at it.

    BL and B are rel32, so their targets are calls. ADRP followed by ADD is a
    data reference. Splitting them matters: a call target that is now a bitmap
    means code was overwritten, a data target that is now zero means rodata was
    cleared, and those are different failures.
    """
    calls, datas = Counter(), set()
    for i in range((lo - base) // 4, (hi - base) // 4):
        w_ = w[i]
        pc = base + i * 4
        if (w_ >> 26) == 0x25 or ((w_ & 0xFC000000) == 0x14000000
                                 and (w_ >> 26) == 0x05):
            imm = w_ & 0x03FFFFFF
            if imm & 0x02000000:
                imm -= 0x04000000
            calls[pc + (imm << 2)] += 1
        if (w_ & 0x9F000000) != 0x90000000 or i + 1 >= len(w):
            continue
        nxt = w[i + 1]
        if (nxt & 0xFFC00000) != 0x91000000 or (nxt & 0x1F) != (w_ & 0x1F):
            continue
        imm = (w_ >> 5) & 0x7FFFF
        if imm & 0x40000:
            imm -= 0x80000
        page = (pc & ~0xFFF) + (imm << 12)
        sh = (nxt >> 22) & 3
        if sh == 0:
            addr = page + (((nxt >> 10) & 0xFFF) << 2)
        elif sh == 1:
            addr = page + (nxt & 0xFFF)
        else:
            addr = page + (nxt & 0xFFF) * 4096
        datas.add(addr)
    return calls, datas


def footprint(path, base, lo, hi):
    d = open(path, "rb").read()
    w = words(d)
    calls, datas = refs(w, base, lo, hi)
    every = sorted(set(calls) | datas)
    print("dump %s  %d bytes, base 0x%08x" % (path, len(d), base))
    print("window 0x%08x..0x%08x" % (lo, hi - 1))
    print("\nreferenced address range: 0x%08x .. 0x%08x  (%d KiB)"
          % (every[0], every[-1], (every[-1] - every[0]) >> 10))
    print("  call targets  %d distinct, 0x%08x .. 0x%08x"
          % (len(calls), min(calls), max(calls)))
    print("  data targets  %d distinct, 0x%08x .. 0x%08x"
          % (len(datas), min(datas), max(datas)))
    print("  lowest reference is 0x%x bytes above 0x01000000"
          % (every[0] - 0x01000000))

    print("\n%s %9s %9s %8s %s" % ("64 KiB", "call-ref", "data-ref",
                                   "zero now", "state"))
    for b in range(every[0] & ~0xFFFF, every[-1] + 0x10000, 0x10000):
        blk = d[b - base:b - base + 0x10000]
        if len(blk) < 0x10000:
            break
        z = blk.count(0)
        c = sum(1 for a in calls if b <= a < b + 0x10000)
        t = sum(1 for a in datas if b <= a < b + 0x10000)
        if not c and not t:
            continue
        state = "CLEARED" if z == 0x10000 else ("overwritten" if z else "intact")
        print("%08x %9d %9d %7.1f%% %s"
              % (b, c, t, 100.0 * z / 0x10000, state))

    hot = Counter({a: n for a, n in calls.items() if not lo <= a < hi})
    print("\nhottest call targets outside the window:")
    for a, n in hot.most_common(10):
        print("  0x%08x  %d call(s)" % (a, n))


def find_copies(d, base, lo, hi):
    """matches with ADR/ADRP wildcarded, then extends both ways."""
    w = words(d)
    off = (lo - base) // 4
    win = w[off:off + (hi - lo) // 4]

    runs, i = [], 0
    while i < len(win):
        if is_posdep(win[i]):
            i += 1
            continue
        j = i
        while j < len(win) and not is_posdep(win[j]):
            j += 1
        if j - i >= 12:
            runs.append((i, j))
        i = j + 1
    anchors = set()
    for (i, j) in runs:
        anchors.add(j - 12)
        for k in range(i, j - 12, max(1, (j - i - 12) // 8)):
            anchors.add(k)

    found = set()
    for a in sorted(anchors):
        pat = struct.pack("<12I", *win[a:a + 12])
        o = 0
        while True:
            o = d.find(pat, o)
            if o < 0:
                break
            if o % 4 == 0:
                found.add((o // 4, a))
            o += 4

    def walk(k, a, step):
        n = 0
        while True:
            kk, aa = k + step * n, a + step * n
            if not (0 <= kk < len(w)) or not (0 <= aa < len(win)):
                break
            x, y = w[kk], win[aa]
            if x == y or (is_posdep(x) and is_posdep(y)):
                n += 1
            else:
                break
        return n

    hits = []
    for (k, a) in sorted(found):
        addr = base + k * 4
        if lo <= addr < hi:
            continue
        left = walk(k - 1, a - 1, -1) * 4
        right = walk(k + 12, a + 12, 1) * 4
        if left + right >= MIN_RUN:
            hits.append((addr, left, right))
    return len(runs), len(anchors), len(found), hits


def plant(d, base, lo, hi, at, delta):
    """a copy at `at`: byte identical, and one with ADR/ADRP moved by delta."""
    win = d[lo - base:hi - base]
    made = []
    for off, dl in ((0, 0), (len(win), delta)):
        buf = bytearray(win)
        for i in range(0, len(buf), 4):
            x = struct.unpack_from("<I", buf, i)[0]
            if (x & 0x9F000000) == 0x90000000:
                imm = (((x >> 5) & 0x7FFFF) + dl // 0x1000) & 0x7FFFF
            elif (x & 0x9F000000) == 0x10000000:
                imm = (((x >> 5) & 0x7FFFF) + dl // 4) & 0x7FFFF
            else:
                continue
            struct.pack_into("<I", buf, i, (x & ~(0x7FFFF << 5)) | (imm << 5))
        # addresses are absolute, the buffer starts at base
        o = at + off - base
        if o < 0 or o + len(buf) > len(d):
            sys.exit("control does not fit in the dump")
        d[o:o + len(buf)] = bytes(buf)
        made.append(at + off)
    return made


def merge(hits):
    """one anchor word inside a copy is one hit per word. collapse to runs."""
    out = []
    for addr, left, right in sorted(hits):
        start, end = addr - left, addr + 12 + right
        if out and start <= out[-1][1]:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return [(a, b - a) for (a, b) in out]


def reloc(path, base, lo, hi):
    d = open(path, "rb").read()

    # positive control first, on a scratch copy. a negative from a matcher that
    # cannot find a copy that is definitely there is worth nothing.
    scratch = bytearray(d)
    planted = plant(scratch, base, lo, hi, lo + 0x100000, 0x100000)
    ctl = merge(find_copies(bytes(scratch), base, lo, hi)[3])
    print("positive control: planted a byte identical copy at 0x%08x" % planted[0])
    print("               and an ADR/ADRP-shifted copy at 0x%08x (+0x100000)"
          % planted[1])
    for a, n in ctl:
        print("  matcher: 0x%08x  %d bytes" % (a, n))
    if not any(a == p for p in planted for a, _ in ctl):
        sys.exit("control failed, the negative below would be meaningless")

    runs, anchors, raw, hits = find_copies(d, base, lo, hi)
    print("\nreal search over %s" % path)
    print("  invariant runs >=12 words: %d, anchors %d, raw hits %d"
          % (runs, anchors, raw))
    print("  copies of the window (>=%d B matched): %d" % (MIN_RUN, len(merge(hits))))
    for a, n in merge(hits)[:25]:
        print("    0x%08x  %d bytes" % (a, n))
    if not hits:
        print("    none. no relocated copy of this window inside the dump.")


def start(path):
    """_start scan at 4-byte granularity.

    round 7 and round 8 stepped in 64-byte strides, which cannot miss anything
    in a real image but wastes the check on a stride nobody justified.
    """
    d = open(path, "rb").read()
    base = 0x01000000
    n = len(d) // 4
    hits = 0
    for i in range(n - 2):
        w0 = struct.unpack_from("<I", d, i * 4)[0]
        if (w0 & 0xFC000000) != 0x14000000 or (w0 >> 26) != 0x05:
            continue
        quad = struct.unpack_from("<Q", d, (i + 2) * 4)[0]
        addr = base + i * 4
        if quad == addr or 0x01000000 <= quad <= 0x08000000:
            hits += 1
            print("0x%08x  b %+d  quad(+8)=0x%016x" % (addr, (w0 & 0x3FFFFFF) << 2, quad))
    if not hits:
        print("no b <label> + plausible _TEXT_BASE quad in the dump")
    print("the scan above does not require the quad to match, only to look sane.")


def ids(path, base):
    """0x82xxxxxx materialised by movz+movk, plus the packed-literal form.

    round 8 searched for the packed literal and found nothing and called it a
    negative. round 10 searched movz+movk and called that the real negative.
    both are needed: bl31_apis.c uses the register form, a literal pool is
    what a different compiler or an -O0 build would emit. AML_DATA_PROCESS
    0x820000ff has to be checked by exact value in both, otherwise the top
    half 0x8200 matches any word that starts that way.
    """
    d = open(path, "rb").read()
    w = words(d)
    movz = {}
    for i, x in enumerate(w):
        if (x & 0xFF800000) == 0xD2800000:
            movz[(i, x & 0x1F)] = (x >> 5) & 0xFFFF
    found = {}
    for i, x in enumerate(w):
        if (x & 0xFF800000) != 0xF2800000 or ((x >> 21) & 3) != 1:
            continue
        lo = movz.get((i - 1, x & 0x1F))
        if lo is None:
            continue
        v = (((x >> 5) & 0xFFFF) << 16) | lo
        if 0x82000000 <= v < 0x83000000:
            found.setdefault(v, []).append(base + i * 4)
    lit = [base + i * 4 for i, x in enumerate(w) if x == 0x820000FF]

    print("movz+movk pairs building 0x82xxxxxx, whole dump")
    for v in sorted(found):
        print("  0x%08x  %d site(s)  %s"
              % (v, len(found[v]), " ".join("0x%08x" % a for a in found[v][:6])))
    print("\nAML_DATA_PROCESS 0x820000ff")
    both = found.get(0x820000FF, []) + lit
    print("  as a movz+movk pair: %s"
          % (" ".join("0x%08x" % a for a in found.get(0x820000FF, [])) or "none"))
    print("  as a packed literal: %s"
          % (" ".join("0x%08x" % a for a in lit) or "none"))
    print("  => %s" % ("present" if both else "NOT in this dump"))


def mmio(path, base, header, lo=0x01040000, hi=0x01080000):
    """Amlogic register accesses built with movz+movk inside the window.

    this is corroboration that does not depend on a single source file. round 10
    matched securestorage.c, one translation unit. if the same window also
    pokes AO_SEC_GP_CFG*, AO_CEC_GEN_CNTL and the CBUS block, it is Amlogic
    GXL code by a second and unrelated route.
    """
    import re
    d = open(path, "rb").read()
    w = words(d)
    names = {}
    txt = open(header, encoding="latin-1").read()
    for m in re.finditer(r"#define\s+(?:P_)?([A-Z][A-Z0-9_]+)\s+\(?(0x[0-9a-fA-F]+)"
                         r"\s*\+\s*\(?(0x[0-9a-fA-F]+)\s*<<\s*2", txt):
        names[(int(m.group(2), 16), int(m.group(3), 16))] = m.group(1)

    movz = {}
    for i, x in enumerate(w):
        if (x & 0xFF800000) == 0xD2800000:
            movz[(i, x & 0x1F)] = (x >> 5) & 0xFFFF
    hits = {}
    for i, x in enumerate(w):
        if (x & 0xFF800000) != 0xF2800000 or ((x >> 21) & 3) != 1:
            continue
        lo16 = movz.get((i - 1, x & 0x1F))
        if lo16 is None:
            continue
        v = (((x >> 5) & 0xFFFF) << 16) | lo16
        if not 0xC0000000 <= v <= 0xEFFFFFFF:
            continue
        addr = base + i * 4
        if not lo <= addr < hi:
            continue
        hits.setdefault(v, []).append((addr, i))

    print("register values in 0xc0000000..0xefffffff built inside"
          " 0x%08x..0x%08x" % (lo, hi - 1))
    real = total = 0
    for v in sorted(hits):
        confirmed = 0
        for _addr, i in hits[v]:
            # a movz+movk pair can be two unrelated 16-bit immediates. the pair
            # is an MMIO access only if the register is then loaded or stored.
            rd = w[i] & 0x1F
            for k in range(i + 1, min(i + 5, len(w))):
                y = w[k]
                if ((y & 0xFFC00000) in (0xB9000000, 0xB9400000,
                                         0xF9000000, 0xF9400000)
                        and (y & 0x1F) == rd):
                    confirmed += 1
                    break
        if not confirmed:
            continue
        real += confirmed
        total += len(hits[v])
        tag = ""
        if 0xc8100000 <= v < 0xc8200000 and (v - 0xc8100000) % 4 == 0:
            tag = names.get((0xc8100000, (v - 0xc8100000) // 4)) \
                or "AO block, not named in this header"
        elif (v >> 20) == 0xc91:
            tag = "USB port B aperture (M8_USBPORT_BASE_B)"
        elif (v >> 20) == 0xc11:
            tag = "CBUS aperture (IO_CBUS_BASE)"
        elif (v >> 20) == 0xd01:
            tag = "VCBUS/VPU aperture (IO_VPU_BUS_BASE)"
        print("  0x%08x  %3d of %d site(s)  %s" % (v, confirmed, len(hits[v]), tag))
    print("\n%d MMIO accesses confirmed by a following load/store off the same"
          " register, out of %d values in the band" % (real, total))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    verb = sys.argv[1]
    if verb == "start":
        start(sys.argv[2])
    elif verb == "ids":
        ids(sys.argv[2], int(sys.argv[3], 0))
    elif verb == "mmio":
        mmio(sys.argv[2], int(sys.argv[3], 0), sys.argv[4])
    elif verb in ("footprint", "reloc"):
        (footprint if verb == "footprint" else reloc)(
            sys.argv[2], *[int(x, 0) for x in sys.argv[3:]])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
