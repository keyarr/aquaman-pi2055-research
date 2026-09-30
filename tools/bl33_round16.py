#!/usr/bin/env python3
"""bl33_round16.py - static audit of update + ddr_test_copy + mmc read.

Offline only. Reads the persisted BL33 image, never touches a device.

  buffers   fastboot download base + burning transfer base evidence
  update    update handler arg parsing (no address control)
  ddrcopy   ddr_test_copy parser + clamps + copy-loop semantics
  copyloop  the 0x37e3aea0 loop in isolation (4x factor proof)
  mmc       mmc read parser + length mask
  all       everything, in report order

Pure helpers (no image needed) carry the arithmetic the tests pin:
  ddr_size_clamp, ddr_effective_bytes, mmc_effective_bytes, oem_fits.
"""
import struct
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN

BASE_DEFAULT = 0x37e18000

# handlers / routines established in round 15, re-pinned here
UPDATE = 0x37e78ff8
UPDATE_MAIN = 0x37e78f94
BUF_INIT = 0x37e7bbe0
DDR_COPY = 0x37e3d1b0
COPY_LOOP = 0x37e3aea0
DDR_STRTOUL = 0x37e3cbb0
SIMPLE_STRTOUL = 0x37eac21c
MMC_READ = 0x37e2d890
MMC_WRITE = 0x37e2d764
CB_DOWNLOAD = 0x37e95408
RX_HANDLER = 0x37e95274
DDR_USABLE = 0x37e953e4

# host-data buffers, image-proven (see buffers verb)
FASTBOOT_BUF = 0x10200000
FASTBOOT_BUF_MAX = 0x8000000  # cap in ddr_size_usable 0x37e953e4
BURN_BUF = 0x7700000
BURN_BUF_SZ = 0x4000000  # 64M, optimus_download.h

DDR_MIN_SIZE = 0x1000
DDR_DEFAULT_SIZE = 0x2000000


def ddr_size_clamp(size):
    """Parser clamp at 0x37e3d26c..0x37e3d274: size<0x1000 -> 0x2000000.

    Input is the 32-bit strtoul result (w20). Python ints are masked to 32
    first so overflow wrap matches the device's madd w21,w21,w20,w0.
    """
    s = size & 0xFFFFFFFF
    if s < DDR_MIN_SIZE:
        return DDR_DEFAULT_SIZE
    return s


def ddr_effective_bytes(size, loop=1):
    """Bytes the copy loop (0x37e3aea0) and the fill loop actually touch.

    Both do N = (clamped>>2) iterations of 16 bytes, repeated `loop` times:
    total = N*16*loop = (clamped & ~3)*4*loop. The 4x factor is the point:
    the handler copies 4x the requested size, then overwrites it with pattern.
    """
    c = ddr_size_clamp(size)
    n = (c >> 2)
    return (n * 16 * (loop & 0xFFFFFFFF)) & 0xFFFFFFFFFFFFFFFF


def mmc_effective_bytes(cnt):
    """Bytes mmc read touches: cnt*512 with the ubfiz mask at 0x37e2d93c.

    ubfiz x1,x19,#9,#0x17 keeps only the low 23 bits of cnt, so the top 9
    bits are silently dropped: length = (cnt & 0x7FFFFF)*512.
    """
    return ((cnt & 0x7FFFFF) * 512) & 0xFFFFFFFFFFFFFFFF


def oem_fits(cmd):
    """OEM/run_command budget from round 15: 31 chars after 'oem '."""
    return len(cmd) <= 31


def fastboot_buf_range():
    return (FASTBOOT_BUF, FASTBOOT_BUF + FASTBOOT_BUF_MAX)


def burn_buf_range():
    return (BURN_BUF, BURN_BUF + BURN_BUF_SZ)


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

    def func_end(self, f):
        for s in self.starts:
            if s > f:
                return s
        return self.base + len(self.data)

    def bls(self, f):
        stop = self.func_end(f)
        return [(i.address, i.operands[0].imm) for i in self.insns
                if f <= i.address < stop and i.mnemonic == "bl" and i.operands]


def _dump(img, f, limit=0):
    md2 = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    md2.detail = False
    stop = img.func_end(f)
    data = img.data[f - img.base:stop - img.base]
    n = 0
    for ins in md2.disasm(data, f):
        print("  0x%08x  %-10s %s" % (ins.address, ins.mnemonic, ins.op_str))
        n += 1
        if limit and n >= limit:
            break


def verb_buffers(img):
    print("== fastboot download buffer (host bytes, fixed address) ==")
    print("rx_handler_dl_image 0x%08x:" % RX_HANDLER)
    _dump(img, RX_HANDLER, 0)
    print("key lines: mov x1,#0x10200000 / add x0,x1,w0,uxtw / bl memcpy")
    print("  base = 0x%08x max 0x%x range [0x%08x,0x%08x)" % (
        FASTBOOT_BUF, FASTBOOT_BUF_MAX, FASTBOOT_BUF, FASTBOOT_BUF + FASTBOOT_BUF_MAX))
    print("cb_download 0x%08x: simple_strtoul size, ddr_size_usable gate" % CB_DOWNLOAD)
    print("ddr_size_usable 0x%08x: usable = min(dram-0x0d000000-addr, 0x8000000)" % DDR_USABLE)
    print()
    print("== burning transfer buffer (update path, fixed address) ==")
    print("optimus_buf_manager_init 0x%08x:" % BUF_INIT)
    _dump(img, BUF_INIT, 0)
    print("key line: mov x3,#0x7700000 ; cmp x2,x3 (transferBuf must equal it)")
    print("  base = 0x%08x sz 0x%x range [0x%08x,0x%08x)" % (
        BURN_BUF, BURN_BUF_SZ, BURN_BUF, BURN_BUF + BURN_BUF_SZ))
    print("  source: optimus_download.h: DDR_MEM_ADDR_START=0x073<<20 +2M+2M")


def verb_update(img):
    print("== update handler 0x%08x (maxargs 3, no address arg) ==" % UPDATE)
    _dump(img, UPDATE, 0)
    print("argv[1] -> w20 (timeout/ms, stored via 0x37e7b8e4 path, not an address)")
    print("argv[2] -> w19 (identifyWaitTime string selector, not an address)")
    print("no adrp/mov of a host address into a buffer register; both buffers fixed")
    print("address control by host: NO")


def verb_ddrcopy(img):
    print("== do_ddr_test_copy 0x%08x parser ==" % DDR_COPY)
    bls = img.bls(DDR_COPY)
    for a, t in bls:
        print("  bl 0x%08x -> 0x%08x" % (a, t))
    print("argv[1] -> 0x%08x (strtoul32) -> w24 src" % DDR_STRTOUL)
    print("argv[2] -> 0x%08x (strtoul32) -> w25 dst" % DDR_STRTOUL)
    print("argv[3] -> 0x%08x (strtoul32) -> w20 size; cmp w20,#0xfff / csel -> 0x2000000 floor" % DDR_STRTOUL)
    print("argv[4] -> loop w21 (default 1); argv[5] -> print w22 (default 1)")
    print("width: w regs (32-bit) zero-extended to x for use; overflow wraps")
    print("range/align clamp on src/dst: none found (no and/lsr/mask/cmp/base-add)")
    print("copy call: 0x37e3d348 bl 0x%08x with x0=dst x1=src w2=size" % COPY_LOOP)


def verb_copyloop(img):
    print("== copy loop 0x%08x (also the fill shape) ==" % COPY_LOOP)
    _dump(img, COPY_LOOP, 0)
    print("lsr w2,w2,#2 -> N=size>>2; sub/cmp loop runs N iters; 16 B/iter")
    print("effective bytes = N*16 = (size&~3)*4 : 4x the requested size")
    print("same shape reappears inline at 0x37e3d3d8 (0x12345678 fill over dst)")


def verb_mmc(img):
    print("== do_mmc_read 0x%08x (eMMC->RAM, dst controllable, data not host) ==" % MMC_READ)
    _dump(img, MMC_READ, 0)
    print("argv[1]->x22 dst (64-bit simple_strtoul, no clamp)")
    print("argv[2]->x21 blk, argv[3]->x19 cnt (w truncation at call)")
    print("blr x4 = blk_dread(dev,blk,cnt,buf); ubfiz x1,x19,#9,#0x17 masks cnt to 23 bits")


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    verb, path, base = sys.argv[1], sys.argv[2], int(sys.argv[3], 0)
    img = Img(path, base)
    if verb == "buffers":
        verb_buffers(img)
    elif verb == "update":
        verb_update(img)
    elif verb == "ddrcopy":
        verb_ddrcopy(img)
    elif verb == "copyloop":
        verb_copyloop(img)
    elif verb == "mmc":
        verb_mmc(img)
    elif verb == "all":
        for f in (verb_buffers, verb_update, verb_ddrcopy, verb_copyloop, verb_mmc):
            f(img)
            print()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
