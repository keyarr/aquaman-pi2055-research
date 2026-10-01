#!/usr/bin/env python3
"""bl33_ctrl.py - turn ddr_test_copy into a control-flow question.

Offline. Reads reports/round14-bl33-persist/bl33-37e18000.bin and, when asked,
reports/round12-reloc/mread_37800000_00800000.bin for the live page table.

  prim        model of the ddr_test_copy end state, from the binary
  indirect    every br/blr site, with the provenance of the target register
  w32         the subset of indirect sites fed by a 32-bit load
  ptrtab      code pointers stored in the image, clustered into tables
  collateral  16 KiB-below check for a chosen address
  pgtable     decode the live page table (perms, XN, attr index)
"""
import struct
import sys
from collections import defaultdict

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN

IMG = "reports/round14-bl33-persist/bl33-37e18000.bin"
PT = "reports/round12-reloc/mread_37800000_00800000.bin"
BASE = 0x37e18000
DST = 0x37ff0000
PTABLE = 0x37ff0000
PAT_FILL = 0x12345678

MD = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
MD.detail = True
MD.skipdata = True


def load_img(path=IMG, base=BASE):
    d = open(path, "rb").read()
    ins = list(MD.disasm(d, base))
    return d, ins


def func_starts(ins, d):
    st = {BASE}
    for i, x in enumerate(ins):
        if x.mnemonic == "stp" and x.op_str.startswith("x29, x30, [sp, #-"):
            st.add(x.address)
        if i and ins[i - 1].mnemonic in ("ret", "brk"):
            st.add(x.address)
    return sorted(st)


def func_of(starts, a):
    lo, hi, best = 0, len(starts) - 1, starts[0]
    while lo <= hi:
        m = (lo + hi) // 2
        if starts[m] <= a:
            best, lo = starts[m], m + 1
        else:
            hi = m - 1
    return best


# ---------------------------------------------------------------- primitive


def prim_model(size, loop=1, src=0x10200000, dst=0x37E00000):
    n = size >> 2
    bodies = (n + 7) // 8
    stride = ((n & 0x7FFFFFF) << 4)
    total = stride * loop
    wordoff = 4 * bodies
    return dict(N=n, bodies=bodies, stride=stride, L=total, srcoff=wordoff,
                A=dst + total, Woff=src + wordoff,
                fill=(dst, dst + total), tail=(dst + total, dst + total + 16))


def verb_prim(ins, d):
    print("== ddr_test_copy end state, from 0x37e3d1b0 ==")
    print("fill  0x37e3d3d8..0x37e3d434  str 0x12345678, x4 = dst + k*(N<<4), k in [0,loop)")
    print("      ubfiz x0,x22,#4,#0x1e at 0x37e3d3d0  -> stride = (N & 0x7ffffff)<<4")
    print("      x27 = loop*stride at 0x37e3d440")
    print("read  0x37e3d498..0x37e3d4b4  w19=N; subs w19,w19,#8; ldr w1,[x3,#4]!; b.ne")
    print("      iterations = ceil(N/8); x3 ends at src + 4*iterations")
    print("tail  0x37e3d4b8 str w1,[x23,x27]      dst+L   = W")
    print("      0x37e3d4c4 str w0,[x24,#4]      dst+L+4 = W   (w0 = *x3, same word)")
    print("      0x37e3d4d0 str w0,[x24,#8]      dst+L+8 = W")
    print("      0x37e3d4d8 str w0,[x24,#0xc]    dst+L+12= W")
    print("      x24 = x23 + x27 = dst + L")
    print("cache no flush_cache / no dcache op anywhere in 0x37e3d1b0..0x37e3d52c")
    print()
    print("model: N = size>>2 ; L = ((N & 0x7ffffff)<<4) * loop ; min size 0x1000 -> L>=0x4000")
    print("       A = dst + L  ->  4 x uint32 W, W = *(uint32*)(src + 4*ceil(N/8))")
    print("       [dst, A)     ->  0x12345678 repeated")
    for size, loop in ((0x1000, 1), (0x1000, 2), (0x2000000, 1), (0x10000, 1)):
        m = prim_model(size, loop)
        print("   size=%#-10x loop=%d  N=%#-8x L=%#-10x  A=dst+%#x  W=src+%#x" %
              (size, loop, m["N"], m["L"], m["L"], m["srcoff"]))


# ---------------------------------------------------------------- indirect


def reg_of(txt):
    return txt.strip()


def verb_indirect(ins, d, want32=False):
    starts = func_starts(ins, d)
    by_addr = {x.address: n for n, x in enumerate(ins)}
    idx_of = {}
    for n, x in enumerate(ins):
        idx_of[x.address] = n
    rows = []
    for n, x in enumerate(ins):
        if x.mnemonic not in ("blr", "br"):
            continue
        tgt = x.op_str.split(",")[-1].strip()
        if not tgt.startswith("x"):
            continue
        # walk back up to 24 insns for the defining load
        defn = None
        for m in range(n - 1, max(n - 25, -1), -1):
            y = ins[m]
            if not y.op_str.strip().startswith(tgt + ",") and \
               not y.op_str.strip().startswith(tgt + " "):
                continue
            if y.mnemonic in ("ldr", "ldrsw", "ldrb", "ldrh", "ldurb", "ldur",
                              "ldar", "ldaxr", "ldp", "ldrsb", "ldrsh", "add",
                              "mov", "movz", "movk", "adrp", "orr", "lsl",
                              "lsr", "ubfiz", "sub", "and", "eor", "madd",
                              "mul", "csel", "csinc", "adr", "movn", "sxtw",
                              "uxtw", "bfi", "ubfx", "sbfx", "tbz", "tbnz",
                              "ccmp", "csel"):
                defn = y
                break
            if y.mnemonic in ("bl", "ret", "b", "blr", "br", "str", "stp",
                              "stur", "strb", "strh", "cbz", "cbnz", "b.eq",
                              "b.ne", "b.hi", "b.lo", "b.mi", "b.pl", "b.ge",
                              "b.lt", "b.gt", "b.le", "b.hs", "b.ls", "brk",
                              "svc", "dsb", "isb", "nop", "smc", "cmp",
                              "cmn", "tst", "ldp"):
                continue
        w32 = bool(defn and defn.mnemonic in ("ldr",) and
                   defn.op_str.split(",")[0].strip().startswith("w") and
                   ", x" not in defn.op_str and "[x" in defn.op_str)
        if want32 and not w32:
            continue
        rows.append((x.address, func_of(starts, x.address), x.mnemonic, tgt,
                     defn.mnemonic if defn else "-",
                     defn.op_str if defn else "-", defn.address if defn else 0))
    print("%-10s %-10s %-6s %-5s %-8s %-40s def@%s" %
          ("site", "func", "mn", "tgt", "defmn", "defop", "addr"))
    for r in rows:
        print("0x%08x 0x%08x %-6s %-5s %-8s %-40s 0x%08x" % r)
    print("\ntotal indirect sites: %d ; fed by 32-bit ldr: %d" %
          (len([1 for x in ins if x.mnemonic in ("blr", "br")]), len(rows)))


# ---------------------------------------------------------------- ptrtab


def verb_ptrtab(ins, d):
    lo, hi = BASE, DST
    hits = defaultdict(list)
    q = struct.unpack_from("<%dQ" % ((hi - lo) // 8), d, 0)
    for i, v in enumerate(q):
        a = lo + i * 8
        if lo <= v < hi:
            hits[v].append(a)
    total = sum(len(v) for v in hits.values())
    print("code-pointer words pointing into [0x%x,0x%x): %d slots, %d distinct targets"
          % (lo, hi, total, len(hits)))
    # cluster slots that are adjacent (same table) and share stride
    slots = sorted(a for v in hits.values() for a in v)
    tables = []
    cur = [slots[0]]
    for a in slots[1:]:
        if a - cur[-1] <= 0x40:
            cur.append(a)
        else:
            tables.append(cur)
            cur = [a]
    tables.append(cur)
    tables = [t for t in tables if len(t) >= 2]
    print("clusters of >=2 adjacent slots: %d\n" % len(tables))
    for t in tables:
        vals = [struct.unpack_from("<Q", d, a - lo)[0] for a in t]
        uniq = sorted(set(vals))
        inside = [v for v in uniq if lo <= v < hi]
        print("  0x%08x..0x%08x  n=%-4d uniq=%-4d in-image=%-4d  first=%s" %
              (t[0], t[-1], len(t), len(uniq), len(inside),
               " ".join("%x:%08x" % (a, v) for a, v in list(zip(t, vals))[:4])))


# ---------------------------------------------------------------- page table


def verb_pgtable():
    d = open(PT, "rb").read()
    off = PTABLE - 0x37800000
    q = struct.unpack("<8192Q", d[off:off + 0x10000])

    def f(v):
        return dict(va=(v >> 21) << 21, t=v & 3, px=(v >> 59) & 1,
                    attr=(v >> 2 & 1) | ((v >> 5) & 1) << 1 | ((v >> 7) & 1) << 2,
                    af=(v >> 10) & 1, ap=(((v >> 4) & 1) << 1) | ((v >> 8) & 1),
                    sh=(v >> 6) & 1, ns=(v >> 3) & 1,
                    xn=(v >> 54) & 1, nt=(v >> 63) & 1)
    print("== live page table at 0x%x (8192 x 2MiB block descriptors) ==" % PTABLE)
    print("MAIR_EL1 = 0xff440c0400 (image 0x37e19450..5c): "
          "attr0=0x00 Device-nGnRnE  attr1=0x04 Normal-NC  attr7=0xff Normal-WB")
    print("SCTLR_EL1 = 0x300004516 (image 0x37e193f0..f8): M=0 A=1 C=1 I=0  -> D-cache ON, I-cache OFF")
    print()
    print("blk  VA_start          VA_end            type AP SH NS AF AttrIdx XN nT")
    for i in list(range(0, 3)) + [8, 59, 129, 256, 447, 448, 511, 512, 1023]:
        x = f(q[i])
        print("%4d 0x%012x 0x%012x  %d    %d  %d  %d  %d   %d     %d  %d" %
              (i, x["va"], x["va"] + 0x1FFFFF, x["t"], x["ap"], x["sh"],
               x["ns"], x["af"], x["attr"], x["xn"], x["nt"]))
    print()
    aps = set(f(v)["ap"] for v in q)
    xns = set(f(v)["xn"] for v in q)
    attrs = set(f(v)["attr"] for v in q)
    print("distinct AP values across 8192 blocks :", aps, "(0=EL1 RW, 2=EL1 RO)")
    print("distinct XN values                    :", xns, "(0=executable)")
    print("distinct AttrIdx values               :", attrs)
    print("blocks covering 0x10200000 (fb buf)  : idx", 0x10200000 >> 21)
    print("blocks covering 0x37e18000 (BL33)     : idx", 0x37e18000 >> 21)
    print("blocks covering 0x37ff0000 (pg table) : idx", 0x37ff0000 >> 21)


def verb_collateral(ins, d, addr):
    a = int(addr, 0)
    for L in (0x4000,):
        s = a - L
        chunk = d[s - BASE:a - BASE] if BASE <= s and a <= DST else None
        if chunk is None:
            print("0x%08x: 16 KiB-below is OUTSIDE the image (0x%08x)" % (a, s))
        else:
            z = chunk.count(0)
            print("0x%08x: [0x%08x,0x%08x)  %d/%d bytes zero" %
                  (a, s, a, z, len(chunk)))
        print("   target slot 16 B at 0x%08x: %s" % (a, d[a - BASE:a - BASE + 16].hex()))


NAME = "ddr_test_copy"          # 12 chars, cmd_tbl index 17
TOKEN_MAX = 28                  # strnlen(cmd,32)+1 = 33 copied bytes, "oem " = 4
A_CMD = 0x37F60EC0              # cmd_tbl[0].cmd  (entry 0x37f60eb0 + 0x10)
A_STACK = 0x37E17F00            # inside the gd/stack area just under the image


def verb_reach():
    """Exhaustive check that no single fastboot `oem` token can express the write.

    cb_oem 0x37e95630 copies strnlen(cmd,32)+1 = 33 bytes, 4 of which are the
    literal "oem ", so the token handed to run_command is at most 28 chars and is
    always NUL terminated.  The token is  "ddr_test_copy <src> <dst> <size>".
    """
    free = TOKEN_MAX - len(NAME) - 3          # chars left for src+dst+size
    print("== can one fastboot `oem` express the write? ==")
    print("token budget            : %d chars  (33 copied bytes - 4 for \"oem \")"
          % TOKEN_MAX)
    print("fixed part              : %d + 3 separators = %d"
          % (len(NAME), len(NAME) + 3))
    print("left for src+dst+size   : %d chars" % free)
    print()
    print("A) surgical fill, size >= 0x1000  (L = 4*size, minimum 0x4000)")
    print("   size needs >= 4 hex digits, so src+dst <= %d" % (free - 4))
    print("   any control address in BL33 is 0x37xxxxxx and dst = A - L is 8 digits")
    print("   => len(dst) = 8 leaves len(src) = %d : no room for src at all"
          % (free - 4 - 8))
    print("   with a 1-digit src (impossible) W would be *(u32*)(src+0x200), i.e. the")
    print("   SoC low region at AP=EL1-RO, never host data")
    print()
    print("B) any 1-3 digit size -> handler floor 0x37e3d26c forces 0x2000000")
    m = prim_model(0x2000000)
    print("   size = %#x  N = %#x  L = %#x  W at src+%#x  A = dst+%#x"
          % (0x2000000, m["N"], m["L"], m["srcoff"], m["L"]))
    print("   with a 1-digit size, src+dst <= %d, len(dst)=8 => len(src) <= %d"
          % (free - 1, free - 1 - 8))
    print("   src <= 0xfff => W from VA 0x400000..0x400fff (unused low DRAM, unproven)")
    print("   and dst is pinned to A - 0x8000000, so the fill is 128 MiB:")
    for a, what in ((A_CMD, "cmd_tbl[0].cmd"),
                    (A_STACK, "gd/stack area under the image")):
        lo = a - 0x8000000
        print("   A=%#010x (%-28s) fill %#010x..%#010x  %s"
              % (a, what, lo, a,
                 "DESTROYS ALL OF BL33 -> self-lethal" if lo < 0x37E18000 < a
                 else "stays below the image -> survivable"))
    print()
    print("C) two calls do compose for a 64-bit slot: A1=P/W1 then A2=P+4/W2 leaves")
    print("   [P..P+3]=W1 and [P+4..P+7]=W2, and A2's fill stops at P+4 so it cannot")
    print("   undo call 1.  But that does not fix the budget: even the *first* call")
    print("   needs 13 + 8 (dst) + 4 (size) = 25 chars of the 28, leaving 3 for src,")
    print("   and a src long enough to name host data does not exist in 3 chars.")
    print("   It also needs W2 = 0, and W2 is read from unproven low DRAM.")
    print()
    print("verdict: no single-call oem form both spares BL33 and writes a host-chosen")
    print("         32-bit value to a host-chosen control address.")


def main():
    verb = sys.argv[1]
    d, ins = load_img()
    if verb == "prim":
        verb_prim(ins, d)
    elif verb == "indirect":
        verb_indirect(ins, d)
    elif verb == "w32":
        verb_indirect(ins, d, want32=True)
    elif verb == "ptrtab":
        verb_ptrtab(ins, d)
    elif verb == "pgtable":
        verb_pgtable()
    elif verb == "collateral":
        verb_collateral(ins, d, sys.argv[2])
    elif verb == "reach":
        verb_reach()
    elif verb == "dump":
        for a in sys.argv[2:]:
            ad = int(a, 0)
            print("\n--- 0x%08x .. 0x%08x ---" % (ad - 0x40, ad + 0x80))
            for x in range(ad - 0x40, ad + 0x80, 8):
                if not (BASE <= x and x + 8 <= DST):
                    continue
                v = struct.unpack_from("<Q", d, x - BASE)[0]
                extra = ""
                if BASE <= v < DST:
                    extra = "code? 0x%x" % v
                    s0 = d[v - BASE:v - BASE + 24]
                    k = s0.find(b"\0")
                    if 0 < k < 24 and all(32 <= c < 127 for c in s0[:k]):
                        extra += " %r" % s0[:k]
                elif BASE <= v < DST + 0x1000000:
                    try:
                        s0 = d[v - BASE:v - BASE + 32]
                        k = s0.find(b"\0")
                        if 0 < k < 32 and all(32 <= c < 127 for c in s0[:k]):
                            extra = "str %r" % s0[:k]
                    except Exception:
                        pass
                print("  0x%08x : 0x%016x  %s" % (x, v, extra))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
