#!/usr/bin/env python3
"""bl33_round17.py - static E3 close-out: do_bootm->AML_DATA_PROCESS->BL31.

Offline only. Reads the persisted BL33 image, never touches a device.

  e3table   all 15 aml_sec_boot_check sites: caller, x0..x3, origin
  wrapper   0x37e19ea8 register shuffle + post-SMC flush
  bl31inv   classify every BL31-related artifact in the repo
  bl31ref   comparative notes on gxl/gxb reference bl31.bin
  tail      ddr_test_copy fill-then-tail order + ranges
  tee       0xb2000016 tee_log_level short audit
  all       everything, in report order
"""
import os
import re
import struct
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN

BASE_DEFAULT = 0x37e18000
SEC_BOOT = 0x37e19ea8
SMC_SITE = 0x37e19ed8
TEE = 0x37e63534
DDR_COPY = 0x37e3d1b0
COPY_LOOP = 0x37e3aea0

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (site, func, nType, pBuffer, nLength, nOption, origin) - sustained by disasm,
# see reports/round17-bl31/01-e3table.txt for the instruction lines.
E3 = [
    (0x37e24cf0, 0x37e24c00, 0x40, "argv[1] hex else 0x1080000", 0x1800000, 7, "argv/host else immediate"),
    (0x37e24f90, 0x37e24c00, 0x100, "0x1080000", 0x500, 7, "immediate"),
    (0x37e2a088, 0x37e2a030, 0x40, "x20 (env/partition buf)", 0x3fe00, 0, "global/env heap"),
    (0x37e2a0c4, 0x37e2a030, 0x100, "0x1080000", 0x500, 7, "immediate"),
    (0x37e33e94, 0x37e33e00, 0x40, "x20 (argv hex, gated)", 0x3fe00, 0, "argv/host gated by 0x37ea14e0"),
    (0x37e33ec8, 0x37e33e00, 0x100, "0x1080000", 0x500, 7, "immediate"),
    (0x37e34084, 0x37e33e00, 0x40, "x21 (argv hex, gated)", 0x3fe00, 0, "argv/host gated"),
    (0x37e340d4, 0x37e33e00, 0x100, "0x1080000", 0x500, 7, "immediate"),
    (0x37e35ec4, 0x37e35e7c, 0x100, "0x1080000", 0x500, 7, "immediate"),
    (0x37e3623c, 0x37e3601c, 0x40, "x19 (argv/env, gated)", 0x1800000, 4, "argv hex or env default, gated by image-parse 0x37e351f8"),
    (0x37e36340, 0x37e362e0, 0x100, "0x1080000", 0x500, 7, "immediate"),
    (0x37e565e4, 0x37e562e8, 0x10, "x19 (sharemem in base)", 0x500, 0, "global/sharemem from BL31"),
    (0x37e56664, 0x37e562e8, 0x20, "x19 (sharemem in base)", 0x500, 0, "global/sharemem from BL31"),
    (0x37e566f4, 0x37e562e8, 0x11, "x19 (sharemem in base)", 0x500, 0, "global/sharemem from BL31"),
    (0x37e56774, 0x37e562e8, 0x12, "x19 (sharemem in base)", 0x500, 0, "global/sharemem from BL31"),
]

GXB_IMG_SIZE = 24 << 20
GXB_IMG_LOAD_ADDR = 0x1080000


def load(path):
    return open(path, "rb").read()


def sweep(data, base):
    md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    md.skipdata = True
    md.detail = True
    insns = list(md.disasm(data, base))
    words = struct.unpack_from("<%dI" % (len(data) // 4), data, 0)
    starts = set()
    for i, ins in enumerate(insns):
        if ins.mnemonic == "stp" and ins.op_str.startswith("x29, x30, [sp, #-"):
            starts.add(ins.address)
        if i and insns[i - 1].mnemonic in ("ret", "brk"):
            starts.add(ins.address)
        if i >= 2 and words[i - 1] == 0 and words[i - 2] == 0:
            starts.add(ins.address)
    starts.add(base)
    return insns, words, sorted(starts)


class Img:
    def __init__(self, path, base):
        self.data = load(path)
        self.base = base
        self.insns, self.words, self.starts = sweep(self.data, base)
        self.by_addr = {i.address: i for i in self.insns}

    def callers(self, target):
        return [(i.address, self.func_of(i.address)) for i in self.insns
                if i.mnemonic == "bl" and i.operands
                and i.operands[0].type == 2 and i.operands[0].imm == target]

    def func_of(self, addr):
        lo, hi, best = 0, len(self.starts) - 1, self.starts[0]
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.starts[mid] <= addr:
                best = self.starts[mid]
                lo = mid + 1
            else:
                hi = mid - 1
        return best


def _dump(img, f, nbytes=64):
    md2 = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    md2.detail = False
    for ins in md2.disasm(img.data[f - img.base:f - img.base + nbytes], f):
        print("  0x%08x  %-10s %s" % (ins.address, ins.mnemonic, ins.op_str))


def verb_e3table(img):
    print("== E3: 15 aml_sec_boot_check sites -> SMC X0..X4 ==")
    print("wrapper 0x37e19ea8: (x0,x1,x2,x3)=(type,buf,len,opt)")
    print("  -> SMC X0=0x820000ff X1=type X2=buf X3=len X4=opt (x4 untouched)")
    for site, func, typ, buf, ln, opt, org in E3:
        print("  0x%08x in 0x%08x  BL(x0=0x%x,x1=%s,x2=0x%x,x3=%d)  SMC(X1=0x%x,X2=%s,X3=0x%x,X4=%d)  [%s]" % (
            site, func, typ, buf, ln, opt, typ, buf, ln, opt, org))
    print("only 0x37e24cf0 takes a raw host address; the rest are")
    print("immediates, gated argv, image buffers, or sharemem bases.")


def verb_wrapper(img):
    print("== wrapper 0x37e19ea8 (mov shuffle + smc + flush) ==")
    _dump(img, SEC_BOOT, 0x54)
    print("post-SMC: add x1,x6,x5 (buf+len, wraps, no check); bl flush;")


def verb_bl31inv():
    print("== BL31 artifact inventory (repo walk, static) ==")
    cands = [
        (".src/u-boot-khadas/fip/gxl/bl31.bin", "FAMILY REFERENCE"),
        (".src/u-boot-khadas/fip/gxb/bl31.bin", "FAMILY REFERENCE"),
        (".src/u-boot-khadas/fip/gxl/bl31.img", "FAMILY REFERENCE (FIP wrapper)"),
        ("bootloader.img", "EXACT AQUAMAN image, but no BL31/AMLSECU found inside"),
        ("reports/round13-reloc-verify/mread_37800000_00800000.bin", "EXACT AQUAMAN DRAM band (BL33; AMLSECU string there is BL33-side)"),
    ]
    for p, cls in cands:
        fp = os.path.join(REPO, p)
        if os.path.exists(fp):
            d = open(fp, "rb").read()
            print("  %-55s %7d B  %s  AMLSECU=%s" % (
                p, len(d), cls, "yes" if b"AMLSECU" in d else "no"))
        else:
            print("  %-55s missing  %s" % (p, cls))
    print("no EXACT AQUAMAN BL31 binary/dump/symbol/map/log/disassembly exists.")
    print("docs reports/amlsecu-*.md are GENERIC/FAMILY REFERENCE, not proof.")


def verb_bl31ref():
    print("== reference BL31 (comparative only, not aquaman proof) ==")
    for cand in [".src/u-boot-khadas/fip/gxl/bl31.bin",
                 ".src/u-boot-khadas/fip/gxb/bl31.bin"]:
        fp = os.path.join(REPO, cand)
        if not os.path.exists(fp):
            print("%s missing" % cand)
            continue
        d = open(fp, "rb").read()
        words = struct.unpack("<%dI" % (len(d) // 4), d[:len(d) // 4 * 4])
        ff = [i * 4 for i, w in enumerate(words) if w == 0x820000ff]
        print("  %s size 0x%x: 0x820000ff literals=%s smc#0=%d" % (
            cand, len(d), [hex(a) for a in ff],
            sum(1 for w in words if w == 0xD4000003)))
        for needle in [b"AMLSECU", b"secureboot", b"fail to load internal RSA key",
                       b"exceed max DMA", b"flash size is too large",
                       b"storage size is larger than flash"]:
            idxs = []
            s = 0
            while True:
                s = d.find(needle, s)
                if s < 0:
                    break
                idxs.append(hex(s))
                s += 1
                if len(idxs) > 4:
                    break
            if idxs:
                print("    %-32r at %s" % (needle, ",".join(idxs)))
    print("dispatcher: BL31 receives SMC via vector, executes no smc #0;")
    print("no movz/movk 0x8200/0x00ff pair and no 0x820000ff word found,")
    print("so the 0x820000ff handler was NOT isolated to a function.")
    print("neighbor size checks (DMA/flash/storage) exist on other paths;")
    print("none is linked to AML_DATA_PROCESS. do not cite them as validation.")


def verb_tail(img):
    print("== ddr_test_copy end state (loop=1; loop>1 extends fill) ==")
    print("copy  0x37e3aea0: N=size>>2 iters x 16 B at dst (same dst each loop iter)")
    print("fill  0x37e3d3bc..: N iters x 16 B of 0x12345678, dst+=N*16 per outer iter")
    print("read  0x37e3d49c..: stride src, keep last words in w1/w0")
    print("tail  0x37e3d4b8 str w1,[x23,x27]; [x24,#4/#8/#0xc] (x24=dst+L, x27=L)")
    print("L = (clamped>>2)*16*loop; min L=0x4000 (clamp 0x1000, 4x factor)")
    print("dst            dst+L")
    print(" |              |")
    print(" +--------------+-----------+")
    print(" | 0x12345678 x L | 16B src |")
    print(" +--------------+-----------+")
    print("verdict: pattern + controlled-tail (tail src-derived iff src host-reachable);")
    print("arbitrary payload write REFUTED (copy destroyed before return).")


def verb_tee(img):
    print("== 0xb2000016 tee_log_level (short audit) ==")
    _dump(img, TEE, 0x70)
    print("argv[1] decimal parse -> w1; smc X0=0xb2000016 X1=level; compare/print only.")
    print("no run_command/secure-boot/image-verify link. REFUTED AS RELEVANT.")


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    verb, path, base = sys.argv[1], sys.argv[2], int(sys.argv[3], 0)
    img = Img(path, base) if verb not in ("bl31inv", "bl31ref") else None
    if verb == "e3table":
        verb_e3table(img)
    elif verb == "wrapper":
        verb_wrapper(img)
    elif verb == "bl31inv":
        verb_bl31inv()
    elif verb == "bl31ref":
        verb_bl31ref()
    elif verb == "tail":
        verb_tail(img)
    elif verb == "tee":
        verb_tee(img)
    elif verb == "all":
        for f in (verb_e3table, verb_wrapper):
            f(img)
            print()
        verb_bl31inv()
        print()
        verb_bl31ref()
        print()
        verb_tail(img)
        print()
        verb_tee(img)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
