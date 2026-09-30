#!/usr/bin/env python3
"""bl33_round15.py - static OEM/run_command + AML_DATA_PROCESS audit.

Offline only. Reads the persisted BL33 image, never touches a device.

  cmdsurface  per-command handler table with callee/strings/flags evidence
  handlers    full disasm + bl list + strings for chosen handlers
  memscan     aggressive search for memory-write / control-flow primitives
  oemframe    precise E2 frame analysis of cb_oem
  e3          E3 reconstruction: do_bootm -> aml_sec_boot_check register flow
  bl31ref     analyze reference GXL BL31 binary for 0x820000ff handling
  pagemap     page-table / range evidence from round14 artifacts (no new claims)
"""
import struct
import sys
import re
from collections import defaultdict

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN

BASE_DEFAULT = 0x37e18000
RUN_COMMAND = 0x37e5e968
AML_SEC_BOOT_CHECK = 0x37e19ea8
CB_OEM = 0x37e95630
TEE_LOG_LEVEL = 0x37e63534

# helpers identified in round14 (confidence noted in report)
HELPERS = {
    0x37e5e968: "run_command",
    0x37e19ea8: "aml_sec_boot_check",
    0x37eaaeec: "memcpy?",
    0x37eaada0: "strnlen?",
    0x37eaae44: "strsep?",
    0x37eac21c: "simple_strtoul?",
    0x37e58920: "getenv?",
    0x37e5848c: "setenv_backend?",
    0x37e59f28: "malloc?",
    0x37e59cd4: "free?",
    0x37eaae84: "strncpy/strnlen2?",
    0x37eaacac: "strcmp?",
    0x37eac53c: "sprintf/snprintf?",
    0x37e593c8: "printf?",
    0x37e5eddc: "find_cmd?",
    0x37e19310: "flush_dcache_range?",
    0x37e19efc: "set_usb_boot_function",
    0x37e5eec4: "run_command_flag?",
}


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
        if ins.mnemonic == "sub" and ins.op_str.startswith("sp, sp, #") \
                and (i == 0 or insns[i - 1].mnemonic in ("ret", "brk", "b", "nop")):
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
        self.cmd_of = cmd_table(self)

    def func_of(self, addr):
        lo, hi = 0, len(self.starts) - 1
        best = self.starts[0]
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

    def callers(self, target):
        return [(i.address, self.func_of(i.address)) for i in self.insns
                if i.mnemonic == "bl" and i.operands
                and i.operands[0].type == 2 and i.operands[0].imm == target]


def cmd_table(img):
    d, base, out, starts = img.data, img.base, {}, set(img.starts)

    def sptr(v):
        if not base <= v < base + len(d):
            return None
        o = v - base
        e = d.find(b"\0", o, o + 40)
        if e <= o or e - o < 2:
            return None
        if not all(32 <= c < 127 for c in d[o:e]):
            return None
        return d[o:e].decode()

    q = struct.unpack_from("<%dQ" % (len(d) // 8), d, 0)
    for i in range(len(q) - 6):
        nm = sptr(q[i])
        if not nm:
            continue
        if len(nm) > 18 or " " in nm:
            continue
        maxargs, repeat = q[i + 1] & 0xFFFFFFFF, (q[i + 1] >> 32) & 0xFFFFFFFF
        if maxargs > 64 or repeat > 4:
            continue
        cmd = q[i + 2]
        if not base <= cmd < base + len(d):
            continue
        if cmd not in starts:
            continue
        if not (sptr(q[i + 3]) or sptr(q[i + 4])):
            continue
        out[cmd] = nm
    return out


def func_strings(img, f):
    d, base = img.data, img.base
    stop = img.func_end(f)
    out = []
    seen = set()
    for ins in img.insns:
        if not (f <= ins.address < stop) or ins.mnemonic != "adrp":
            continue
        rd = ins.operands[0].reg
        for k in range(1, 5):
            nx = img.by_addr.get(ins.address + k * 4)
            if not nx or nx.mnemonic != "add" or nx.operands[0].reg != rd:
                continue
            a = ins.operands[1].imm + nx.operands[-1].imm
            if base <= a < base + len(d):
                e = d.find(b"\0", a - base, a - base + 96)
                if e > a - base and all(32 <= c < 127 for c in d[a - base:e]):
                    t = d[a - base:e].decode()
                    if len(t) >= 4 and t not in seen:
                        seen.add(t)
                        out.append((a, t[:80]))
            break
    return out


def func_bls(img, f):
    stop = img.func_end(f)
    out = []
    for ins in img.insns:
        if f <= ins.address < stop and ins.mnemonic == "bl" and ins.operands:
            t = ins.operands[0].imm
            out.append((ins.address, t))
    return out


def func_indirect(img, f):
    stop = img.func_end(f)
    out = []
    for ins in img.insns:
        if f <= ins.address < stop and ins.mnemonic in ("br", "blr", "ret"):
            # ret at end of function is normal epilogue; keep but mark
            out.append((ins.address, ins.mnemonic, ins.op_str))
    return out


def verb_cmdsurface(img):
    print("image base 0x%08x size 0x%x  cmds %d" % (img.base, len(img.data), len(img.cmd_of)))
    print()
    print("handler      command          bl_count  calls_run  calls_secboot  calls_smc_wrap  indirect  strings_n  top_strings/callees")
    for f in sorted(img.cmd_of, key=lambda a: img.cmd_of[a]):
        nm = img.cmd_of[f]
        bls = func_bls(img, f)
        targets = [t for _, t in bls]
        calls_run = RUN_COMMAND in targets
        calls_sec = AML_SEC_BOOT_CHECK in targets
        smc_wraps = [t for t in targets if t in (0x37e19ea8, 0x37e19efc, 0x37e19e98, 0x37e63534,
                                                 0x37e8bbb8, 0x37e8bc84, 0x37e8bd10, 0x37e8bdc8,
                                                 0x37e8be98, 0x37e8bf3c, 0x37e8bfe0, 0x37e8c084,
                                                 0x37e8c138, 0x37e8c14c)]
        ind = func_indirect(img, f)
        # filter trailing ret
        ind_nb = [(a, m, o) for (a, m, o) in ind if m in ("br", "blr")]
        strs = func_strings(img, f)
        callee_names = []
        for _, t in bls[:14]:
            callee_names.append(HELPERS.get(t, "0x%08x" % t))
        print("0x%08x  %-14s  %3d      %d          %d             %d              %d         %d        %s | %s" % (
            f, nm, len(bls), int(calls_run), int(calls_sec), len(smc_wraps),
            len(ind_nb), len(strs),
            ",".join(callee_names[:8]),
            ";".join(s for _, s in strs[:3])))


def verb_handlers(img, addrs):
    md2 = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    md2.detail = False
    for f in addrs:
        stop = img.func_end(f)
        nm = img.cmd_of.get(f, "?")
        print("\n=== handler 0x%08x (%s) .. 0x%08x ===" % (f, nm, stop))
        for ins in md2.disasm(img.data[f - img.base:stop - img.base], f):
            print("  0x%08x  %-10s %s" % (ins.address, ins.mnemonic, ins.op_str))
        print("  -- bl targets --")
        for a, t in func_bls(img, f):
            print("    0x%08x -> 0x%08x %s (in %s)" % (a, t, HELPERS.get(t, img.cmd_of.get(t, "")), "0x%08x" % img.func_of(t) if img.base <= t < img.base + len(img.data) else "outside"))
        print("  -- indirect --")
        for a, m, o in func_indirect(img, f):
            print("    0x%08x  %s %s" % (a, m, o))
        print("  -- strings --")
        for a, s in func_strings(img, f):
            print("    0x%08x %r" % (a, s))


def verb_memscan(img):
    # 1. absence proof: search image strings for classic memory-command names/usages
    probes = [b"memory display", b"memory write", b"memory copy", b"memory compare",
              b"checksum calculation", b"print or set address offset",
              b"->run_cmd", b"go - start", b"booti -", b"source -"]
    print("== string absence probes ==")
    for p in probes:
        print("  %-24r %s" % (p, "FOUND@%s" % ",".join("0x%x" % i for i in range(len(img.data)) if img.data.startswith(p, i) and i < 5) if p in img.data else "absent"))
    # 2. exact command-name strings that would back md/mw/cp/go/source/booti
    print("== command-name string probes (null-terminated words) ==")
    for w in [b"\x00md\x00", b"\x00mw\x00", b"\x00cp\x00", b"\x00go\x00", b"\x00source\x00", b"\x00booti\x00", b"\x00crc32\x00", b"\x00base\x00", b"\x00loadb\x00"]:
        print("  %-14r %s" % (w, "FOUND" if w in img.data else "absent"))
    # 3. handlers containing indirect control flow
    print("== handlers with br/blr (non-ret) ==")
    for f in sorted(img.cmd_of, key=lambda a: img.cmd_of[a]):
        ind = [(a, m, o) for (a, m, o) in func_indirect(img, f) if m in ("br", "blr")]
        if ind:
            print("  0x%08x %-14s %s" % (f, img.cmd_of[f], "; ".join("0x%08x %s %s" % x for x in ind[:6])))
    # 4. handlers calling run_command (script/chain execution)
    print("== handlers calling run_command 0x37e5e968 ==")
    for c, cf in img.callers(RUN_COMMAND):
        print("  0x%08x in 0x%08x %-14s" % (c, cf, img.cmd_of.get(cf, "")))
    # 5. handlers reaching aml_sec_boot_check
    print("== callers of aml_sec_boot_check 0x37e19ea8 ==")
    for c, cf in img.callers(AML_SEC_BOOT_CHECK):
        print("  0x%08x in 0x%08x %-14s" % (c, cf, img.cmd_of.get(cf, "")))
    # 6. store/mmc/env callees per handler (top memory-touching candidates)
    print("== per-handler env/mmc/store/memcpy-ish callees ==")
    interesting = {0x37e5848c, 0x37e58920, 0x37eaaeec, 0x37eac21c, 0x37e5e968, 0x37e19ea8}
    for f in sorted(img.cmd_of, key=lambda a: img.cmd_of[a]):
        bls = func_bls(img, f)
        hits = [(a, t) for a, t in bls if t in interesting]
        if hits:
            print("  0x%08x %-14s %s" % (f, img.cmd_of[f], " ".join("0x%08x->%s" % (a, HELPERS.get(t, hex(t))) for a, t in hits)))


def verb_oemframe(img):
    # precise E2: disassemble cb_oem, parse frame and copy
    print("== cb_oem 0x37e95630 frame/copy analysis ==")
    md2 = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    md2.detail = True
    f = CB_OEM
    stop = img.func_end(f)
    for ins in md2.disasm(img.data[f - img.base:stop - img.base], f):
        print("  0x%08x  %-10s %s" % (ins.address, ins.mnemonic, ins.op_str))
        if ins.address >= f + 0xc0:
            break
    print()
    print("frame: stp x29,x30,[sp,#-0x50]! => 0x50 = 80 bytes; x29=sp.")
    print("x19 spill at [sp,#0x10]; cmd ptr saved at [x29,#0x48].")
    print("local buffer = x29+0x20; bytes from x29+0x20 to frame end (x29+0x50) = 0x30 = 48.")
    print("copy: strnlen(cmd,32)->x0; x2=x0+1 (n=1..33); memcpy(x29+0x20, cmd, n).")
    print("max copy 33 bytes into 48-byte area: no linear overflow of the frame.")
    print("unterminated case: len>=32 => n=33, byte[32]=cmd[32]; if cmd[32]!=0 no NUL in 33 copied bytes.")
    print("strsep(&p at x29+0x48, ' ') then scans from x29+0x20 for ' ' or NUL.")
    print("scan bound: nearest NUL or space in stack garbage after the 33 bytes; stays inside the 48-byte")
    print("frame only if a NUL/space lands within bytes 33..47, else reads past frame into caller stack.")
    print("write effect: none (memcpy length clamped, destination fixed).")


def verb_e3(img):
    print("== E3: do_bootm -> aml_sec_boot_check -> SMC register flow ==")
    print("source: .src/u-boot-khadas/common/cmd_bootm.c + arch/arm/cpu/armv8/gxl/bl31_apis.c")
    print("  nLoadAddr default GXB_IMG_LOAD_ADDR 0x1080000; len GXB_IMG_SIZE (24<<20)=0x1800000; opt GXB_IMG_DEC_ALL=7")
    print()
    print("-- image call site 1: 0x37e24cf0 in do_bootm 0x37e24c00 --")
    md2 = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    md2.detail = False
    for ins in md2.disasm(img.data[0x37e24cc8 - img.base:0x37e24cf8 - img.base], 0x37e24cc8):
        print("  0x%08x  %-10s %s" % (ins.address, ins.mnemonic, ins.op_str))
    print("-- image call site 2: 0x37e24f90 (second check, nType 0x100) --")
    for ins in md2.disasm(img.data[0x37e24f64 - img.base:0x37e24f98 - img.base], 0x37e24f64):
        print("  0x%08x  %-10s %s" % (ins.address, ins.mnemonic, ins.op_str))
    print("-- wrapper aml_sec_boot_check 0x37e19ea8 --")
    for ins in md2.disasm(img.data[0x37e19ea8 - img.base:0x37e19efc - img.base], 0x37e19ea8):
        print("  0x%08x  %-10s %s" % (ins.address, ins.mnemonic, ins.op_str))
    print()
    print("mapping (System V AArch64 at BL, SMC per gxl/bl31_apis.c aml_sec_boot_check):")
    print("  do_bootm: x0=nType(0x40), x1=pBuffer(user addr or 0x1080000), x2=nLength(0x1800000), x3=nOption(7)")
    print("  wrapper: x7=x0(nType), x6=x1(pBuffer), x5=x2(nLength), x4=x3(nOption preserved);")
    print("           x0=0x820000ff; x1=x7; x2=x6; x3=x5; (x4 untouched); smc #0")
    print("  => SMC: X0=0x820000ff X1=0x40 X2=user_addr X3=0x1800000 X4=7")
    print("  post-SMC: wrapper does flush_dcache_range(pBuffer, pBuffer+nLength) then returns SMC X0.")
    print("  BL33 validation of addr: none found (no compare against RAM top/DTB/header before 0x37e24cf0).")


def verb_bl31ref():
    import os
    for cand in [".src/u-boot-khadas/fip/gxl/bl31.bin",
                 ".src/u-boot-khadas/fip/gxb/bl31.bin"]:
        if not os.path.exists(cand):
            print("%s missing" % cand)
            continue
        d = open(cand, "rb").read()
        print("\n== %s size 0x%x ==" % (cand, len(d)))
        # find 0x820000ff materialisation: movz/movk patterns for 0x00ff + 0x8200
        # search words
        words = struct.unpack("<%dI" % (len(d) // 4), d[:len(d) // 4 * 4])
        hits = []
        for i, w in enumerate(words):
            # movz x?,#0xff ; movk x?,#0x8200,lsl#16  -> 0xD2801FE0|rd , 0xF2B04000|rd
            if (w & 0xFFE0001F) == 0xD2800000 | 0x1FE0 and False:
                pass
            if w == 0xD2801FE0 or (w & 0xFFFFFC1F) == 0xD2801FE0:
                # movz x?, #0xff  (any rd) - record
                hits.append((i * 4, w, "movz_ff"))
        print("  movz-ff-shaped words: %d (first 10: %s)" % (len(hits), [(hex(a), hex(w)) for a, w, _ in hits[:10]]))
        # direct byte pattern for AMLSECU / secureboot strings
        for needle in [b"AMLSECU", b"secureboot", b"sig", b"decrypt", b"0x820000ff", b"R%d"]:
            idxs = []
            s = 0
            while True:
                s = d.find(needle, s)
                if s < 0:
                    break
                idxs.append(hex(s))
                s += 1
                if len(idxs) > 8:
                    break
            if idxs:
                print("  %-14r at %s" % (needle, ",".join(idxs)))
        # ascii strings of interest
        strs = re.findall(rb"[ -~]{8,}", d)
        keep = []
        for s in strs:
            ls = s.lower()
            if any(k in ls for k in [b"verify", b"decrypt", b"signature", b"aml log", b"no key", b"rsa key", b"flash size", b"storage size", b"tee size", b"efuse"]):
                keep.append(s[:100])
        for s in keep[:30]:
            print("  str: %r" % (s,))
        # disassemble around SMC sites in bl31: find smc opcode 0xD4000003
        smcs = [i for i, w in enumerate(words) if w == 0xD4000003]
        print("  smc #0 count: %d offsets %s" % (len(smcs), [hex(i * 4) for i in smcs[:16]]))


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    verb, path, base = sys.argv[1], sys.argv[2], int(sys.argv[3], 0)
    img = Img(path, base)
    rest = sys.argv[4:]
    if verb == "cmdsurface":
        verb_cmdsurface(img)
    elif verb == "handlers":
        verb_handlers(img, [int(a, 0) for a in rest])
    elif verb == "memscan":
        verb_memscan(img)
    elif verb == "oemframe":
        verb_oemframe(img)
    elif verb == "e3":
        verb_e3(img)
    elif verb == "bl31ref":
        verb_bl31ref()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
