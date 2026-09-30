#!/usr/bin/env python3
"""family_stage_dump.py - annotated disassembly of the plaintext Amlogic stage binaries.

round36 found that fip/gxl/bl30.bin and fip/gxl/bl2.bin are plaintext, unstripped
Cortex-M3 / AArch64 images with full symbol strings, and that the answer to "where
does FORCE_USB_BOOT live" was sitting in them the whole time. this dumps a
window of either one with literal-pool and string annotations resolved.

    tools/family_stage_dump.py bl30 0x10001cb0 0x10001cf0
    tools/family_stage_dump.py bl2  0x79b4 0x7cc0
    tools/family_stage_dump.py bl31 0x18ddc 0x18f40

bl30 is Thumb at base 0x10000000, bl2/bl31 are AArch64 at base 0. addresses are
absolute, not offsets, because that is how the strings and the disassembly read.
"""
import os
import re
import struct
import sys

from capstone import Cs, CS_ARCH_ARM, CS_ARCH_ARM64, CS_MODE_ARM, CS_MODE_THUMB

FIP = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", ".src", "u-boot-khadas", "fip")

STAGES = {
    # name: (file, base, arch, mode)
    "bl30": ("gxl/bl30.bin", 0x10000000, CS_ARCH_ARM, CS_MODE_THUMB),
    "bl2": ("gxl/bl2.bin", 0, CS_ARCH_ARM64, CS_MODE_ARM),
    "bl31": ("gxl/bl31.bin", 0, CS_ARCH_ARM64, CS_MODE_ARM),
    "bl31gxb": ("gxb/bl31.bin", 0, CS_ARCH_ARM64, CS_MODE_ARM),
}

# registers worth naming. GP_CFG7[8:] is a gpio pad array on gxl, not a boot
# flag, which is the whole reason round 34's GP_CFG7[31] read came back 0.
NAMES = {
    0xc8100000: "AO_RTI_STATUS_REG0",
    0xc810001c: "AO_RTI_STATUS_REG3",
    0xc810023c: "AO_SEC_SD_CFG15",
    0xc8100240: "AO_SEC_GP_CFG0",
    0xc810025c: "AO_SEC_GP_CFG7",
    0xda10001c: "SEC_AO_RTI_STATUS_REG3",
    0xda10023c: "SEC_AO_SEC_SD_CFG15",
    0xda100240: "SEC_AO_SEC_GP_CFG0",
    0xda10025c: "SEC_AO_SEC_GP_CFG7",
    0xda100220: "SEC_AO_SD_CFG4",
}


def load(stage):
    path, base, arch, mode = STAGES[stage]
    data = open(os.path.join(FIP, path), "rb").read()
    md = Cs(arch, mode)
    strs = {}
    for m in re.finditer(rb"[ -~]{4,}", data):
        strs.setdefault(base + m.start(), m.group().decode(errors="replace"))
    return data, len(data), base, md, strs


def adrp_page(data, at):
    """absolute page for an aarch64 adrp at `at`, and its destination reg."""
    word = struct.unpack_from("<I", data, at)[0]
    imm = (((word >> 5) & 0x7FFFF) << 2) | ((word >> 29) & 3)
    imm <<= 12
    if imm & (1 << 32):
        imm -= 1 << 33
    return (at & ~0xFFF) + imm, word & 0x1F


def thumb_pool(addr):
    return ((addr + 4) & ~3)


def dump(stage, start, end):
    data, n, base, md, strs = load(stage)
    a = start - base
    while a < end - base:
        insn = None
        for i in md.disasm(data[a:a + 4], base + a):
            insn = i
            break
        if insn is None:
            a += 2
            continue
        ann = ""
        ops = insn.op_str
        if insn.mnemonic == "adrp":
            page, rd = adrp_page(data, a)
            for b in range(a + 4, min(a + 32, n), 4):
                w2 = struct.unpack_from("<I", data, b)[0]
                if (w2 & 0xFF800000) == 0x91000000 and (w2 & 0x1F) == rd:
                    imm = (w2 >> 10) & 0xFFF
                    val = page + (imm << (12 if (w2 >> 22) & 1 else 0))
                    if val in strs:
                        ann = '   ; "%s"' % strs[val][:44]
                    elif val in NAMES:
                        ann = "   ; %s" % NAMES[val]
        elif insn.mnemonic.startswith("ldr") and "pc" in ops.lower():
            m = re.search(r"#(-?0x[0-9a-f]+|\d+)", ops)
            if m:
                imm = int(m.group(1), 0)
                if imm & 0x80000000:
                    imm -= 1 << 32
                lit = thumb_pool(insn.address) + imm - base
                if 0 <= lit <= n - 4:
                    val = struct.unpack_from("<I", data, lit)[0]
                    if val in NAMES:
                        ann = "   ; =0x%08x %s" % (val, NAMES[val])
                    elif val in strs:
                        ann = '   ; "%s"' % strs[val][:52]
                    else:
                        ann = "   ; =0x%08x" % val
        print("0x%08x  %-9s %-26s%s"
              % (insn.address, insn.mnemonic, ops, ann))
        a += insn.size


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    stage = sys.argv[1]
    if stage not in STAGES:
        sys.exit("stages: %s" % ", ".join(sorted(STAGES)))
    dump(stage, int(sys.argv[2], 0), int(sys.argv[3], 0))


if __name__ == "__main__":
    main()
