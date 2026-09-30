#!/usr/bin/env python3
"""bl33_round18.py - exact-aquaman BL31 acquisition, offline only.

Reads persisted artifacts, never touches a device. No USB, no SMC,
no RAM/eMMC reads, no execution.

  inventory   classify every BL31-related artifact (EXACT/FAMILY/OTHER/GENERIC)
  handoff     BL33->BL31 handoff refs in the persisted BL33 image
  dtb         secure-memory properties from artifacts/aquaman.dtb
  emmc        eMMC candidate regions from BL33 strings + DTB partitions
  bl31ref     reference BL31 scan (SMC/dispatcher/0xff evidence, comparative)
  all         everything, in report order
"""
import os
import re
import struct
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BL33 = os.path.join(REPO, "reports/round14-bl33-persist/bl33-37e18000.bin")
BASE = 0x37e18000
DTB = os.path.join(REPO, "artifacts/aquaman.dtb")


def load(path):
    return open(path, "rb").read()


def strings(data, minlen=4):
    out = []
    for m in re.finditer(rb"[ -~]{%d,}" % minlen, data):
        out.append((m.start(), m.group().decode()))
    return out


def sha256(path):
    import hashlib
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


# ---------------------------------------------------------------- inventory

# (relpath, class, why) - class assigned by provenance, not by content guess.
INVENTORY = [
    ("bootloader.img", "EXACT AQUAMAN image",
     "xiaomi aquaman bootloader (1.3 MiB); encrypted at rest, TOC frag at 0x4bebe, no FIP magic, no plaintext BL31"),
    ("boot.img", "EXACT AQUAMAN image",
     "aquaman boot.img; AMLSECU! 0x0905 container at 0x800 (kernel+dtb, xiaomi ts 2022090612544443); payloads encrypted"),
    ("recovery.img", "EXACT AQUAMAN image",
     "aquaman recovery.img; same AMLSECU! shape (kernel+ramdisk+dtb, ts 2022090613082318); payloads encrypted"),
    ("dt.img", "EXACT AQUAMAN image",
     "aquaman dt partition (59424 B); encrypted at rest, no FDT magic, no AMLSECU magic"),
    ("artifacts/aquaman.dtb", "EXACT AQUAMAN runtime",
     "decrypted runtime DTB recovered at 0x01000000 (secmon/secos/psci/partitions nodes, see dtb verb)"),
    ("artifacts/aquaman.dts", "EXACT AQUAMAN runtime",
     "text reconstruction of the runtime DTB"),
    ("reports/round14-bl33-persist/bl33-37e18000.bin", "EXACT AQUAMAN BL33",
     "relocated BL33 DRAM copy 0x37e18000..0x37ff0000; caller side of 0x820000ff, not a BL31 source"),
    (".src/u-boot-khadas/fip/gxl/bl31.bin", "FAMILY GXL/GXB",
     "khadas GXL reference BL31 (0x2c3a8); AMLSECU/secureboot strings, no 0x820000ff word, no smc #0"),
    (".src/u-boot-khadas/fip/gxl/bl31.img", "FAMILY GXL/GXB",
     "FIP wrapper around the GXL reference"),
    (".src/u-boot-khadas/fip/gxb/bl31.bin", "FAMILY GXL/GXB",
     "khadas GXB reference BL31 (0x16120); same shape + DMA SHA2/AES neighbor strings"),
    (".src/u-boot-khadas/fip/gxb/bl31.img", "FAMILY GXL/GXB",
     "FIP wrapper around the GXB reference"),
    (".src/u-boot-khadas/fip/gxl/bl2.bin", "FAMILY GXL/GXB",
     "reference BL2 (loads FIP, not aquaman behavior)"),
    (".src/u-boot-khadas/fip/gxl/bl30.bin", "FAMILY GXL/GXB",
     "reference SCPI/bl30 (not BL31)"),
    (".src/u-boot-khadas/fip/gxb/bl2.bin", "FAMILY GXL/GXB",
     "reference BL2"),
    (".src/u-boot-khadas/fip/gxb/bl30.bin", "FAMILY GXL/GXB",
     "reference SCPI/bl30"),
    (".src/u-boot-khadas/arch/arm/include/asm/arch-gxl/bl31_apis.h", "GENERIC/FAMILY header",
     "caller-side SMC id + type constants (AML_DATA_PROCESS 0x820000ff); not BL31 behavior"),
    (".src/u-boot-khadas/common/cmd_rsvmem.c", "GENERIC/FAMILY source",
     "BL33 rsvmem source matching the image strings; reads HW regs, patches DTB"),
]


def inventory():
    lines = []
    for rel, cls, why in INVENTORY:
        p = os.path.join(REPO, rel)
        if os.path.exists(p):
            sz = os.path.getsize(p)
            lines.append("%-58s %-22s 0x%x  %s" % (rel, cls, sz, why))
        else:
            lines.append("%-58s %-22s MISSING  %s" % (rel, cls, why))
    lines.append("")
    lines.append("EXACT AQUAMAN BL31 binary/dump/map/objdump: ABSENT (no file above is one).")
    return "\n".join(lines)


# ---------------------------------------------------------------- handoff

HANDOFF_PATS = ["bl31", "secmon", "rsvmem", "shared-dma-pool", "sharemem",
                "get_sharemem", "bl32", "secos", "secure", "trustzone",
                "fdt set /reserved-memory", "fdt set /secmon",
                "fdt get value", "fdtaddr", "reserve_mem_size",
                "alloc-ranges", "memory-region", "clear_range"]


def handoff():
    d = load(BL33)
    strs = strings(d)
    lines = []
    for pat in HANDOFF_PATS:
        hits = [(a, s) for a, s in strs if pat.lower() in s.lower()]
        lines.append("== %s (%d)" % (pat, len(hits)))
        for a, s in hits[:14]:
            lines.append("  0x%x  %s" % (BASE + a, s[:120]))
    lines.append("")
    lines.append("reading: BL33 holds no BL31 image parser/loader/header/entry.")
    lines.append("handoff is HW-reg + SMC + DTB: cmd_rsvmem reads P_AO_SEC_GP_CFG3/4/5,")
    lines.append("sharemem bases come from SMC 0x82000020/0x82000021, DTB is patched")
    lines.append("via run_command fdt set (secmon reg/size/alloc-ranges, secmon")
    lines.append("reserve_mem_size, secos reg/status). BL31 is resident before BL33.")
    return "\n".join(lines)


# ---------------------------------------------------------------- dtb

def _parse_dtb(blob):
    (magic, tot, off_struct, off_strings, off_rsv, ver, lcv, cpu,
     sz_strings, sz_struct) = struct.unpack(">10I", blob[:40])
    assert magic == 0xD00DFEED, "bad fdt magic"
    st = blob[off_struct:off_struct + sz_struct]
    stx = blob[off_strings:off_strings + sz_strings]

    def name_at(o):
        return stx[o:stx.index(b"\0", o)].decode("ascii")

    nodes, stack, p = [], [], 0
    while p < len(st):
        tok = struct.unpack(">I", st[p:p + 4])[0]
        p += 4
        if tok == 1:
            e = st.index(b"\0", p)
            stack.append(st[p:e].decode("ascii"))
            p = (e + 4) & ~3
        elif tok == 2:
            stack.pop()
        elif tok == 3:
            ln, no = struct.unpack(">II", st[p:p + 8])
            p += 8
            val = st[p:p + ln]
            p = (p + ln + 3) & ~3
            nodes.append(("/" + "/".join(x for x in stack if x), name_at(no), val))
        elif tok == 4:
            continue
        elif tok == 9:
            break
        else:
            raise ValueError("bad token %d" % tok)
    rsv = []
    q = off_rsv
    while True:
        addr, sz = struct.unpack(">2Q", blob[q:q + 16])
        q += 16
        if addr == 0 and sz == 0:
            break
        rsv.append((addr, sz))
        if len(rsv) > 8:
            break
    return nodes, rsv


def _fmt(val):
    if len(val) == 0:
        return "(present)"
    if val[-1:] == b"\0" and all(32 <= c < 127 for c in val[:-1] if c):
        parts = val.split(b"\0")[:-1]
        if all(parts):
            return ", ".join('"%s"' % p.decode("ascii") for p in parts)
    if len(val) % 4 == 0 and len(val) <= 64:
        return "<" + " ".join("0x%x" % x for x in struct.unpack(">%dI" % (len(val) // 4), val)) + ">"
    return "[%d bytes %s]" % (len(val), val[:16].hex(" "))


WANT = ("/secmon", "/psci", "/memory@00000000", "/reserved-memory",
        "/reserved-memory/linux,secmon", "/reserved-memory/linux,secos",
        "/partitions/tee", "/securitykey", "/efuse", "/cpu_info",
        "/aml_reboot", "/ion_dev")


def dtb():
    blob = load(DTB)
    nodes, rsv = _parse_dtb(blob)
    lines = ["memreserve entries: %s" % (rsv if rsv else "none (empty map)")]
    for path, name, val in nodes:
        if path in WANT or path.startswith("/reserved-memory/"):
            lines.append("%-38s %-20s %s" % (path, name, _fmt(val)))
    lines.append("")
    lines.append("derived ranges (no interpretation beyond the values):")
    lines.append("  linux,usable-memory = <0x100000 0x3ff00000> -> [0x100000,0x40000000)")
    lines.append("  linux,secmon alloc-ranges <0x5000000 0x400000> -> [0x5000000,0x5400000)")
    lines.append("  linux,secos reg <0x5300000 0x2000000> status=disable -> [0x5300000,0x7300000)")
    lines.append("  /secmon reserve_mem_size <0x300000> (3 MiB) vs secmon size <0x400000> (4 MiB): mismatch noted, not resolved")
    lines.append("  partitions/tee size <0x2000000> (32 MiB eMMC, secure OS, not BL31)")
    lines.append("  DTB carries no BL31 code address/entry/magic; only reserved ranges + SMC ids.")
    return "\n".join(lines)


# ---------------------------------------------------------------- emmc

EMMC_PATS = ["mmc dev", "mmc part", "mmcinfo", "amlmmc switch", "boot0", "boot1",
             "gpt", "store ", "store_read", "store dtb", "partition",
             "partitions", "tee", "rsv", "dtb_mem_addr", "loadaddr",
             "bootloader-boot0", "bootloader-boot1"]


def emmc():
    d = load(BL33)
    strs = strings(d)
    lines = ["BL33 eMMC vocabulary (counts, first hits):"]
    for pat in EMMC_PATS:
        hits = [(a, s) for a, s in strs if pat.lower() in s.lower()]
        lines.append("== %s (%d)" % (pat, len(hits)))
        for a, s in hits[:8]:
            lines.append("  0x%x  %s" % (BASE + a, s[:110]))
    lines.append("")
    lines.append("at-rest layout (static, no dump performed):")
    lines.append("  boot0/boot1 eMMC hw partitions <- bootloader.img (1.3 MiB, encrypted FIP: BL2+BL30+BL31+BL33).")
    lines.append("  user area GPT <- DTB /partitions node (17 entries; tee 0x2000000, boot 0x1000000, recovery 0x1800000...).")
    lines.append("  BL33 reaches eMMC via store/mmc/amlmmc/gpt cmds; mmc read is the demonstrated eMMC->RAM path.")
    lines.append("  candidate eMMC ranges: (1) boot0/boot1 whole (FIP/BL31 at rest, encrypted);")
    lines.append("  (2) tee partition (secure OS, not BL31); (3) dt/logo/misc (no BL31 evidence).")
    lines.append("  no indiscriminate dump: at-rest BL31 is encrypted, only a live BL31 mapping answers E3.")
    return "\n".join(lines)


# ---------------------------------------------------------------- bl31ref

def bl31ref():
    lines = []
    for rel in (".src/u-boot-khadas/fip/gxl/bl31.bin",
                ".src/u-boot-khadas/fip/gxb/bl31.bin"):
        p = os.path.join(REPO, rel)
        d = load(p)
        words = struct.unpack("<%dI" % (len(d) // 4), d[:len(d) // 4 * 4])
        n_ff = words.count(0x820000FF)
        n_smc = words.count(0xD4000001)
        n_eret = words.count(0xD69F03E0)
        has = b"AMLSECU" in d
        lines.append("%s len=0x%x AMLSECU=%s 0x820000ff-words=%d smc#0=%d eret=%d"
                     % (rel, len(d), has, n_ff, n_smc, n_eret))
    lines.append("gxl strings: bl31 reboot reason / [BL31]: GXL CPU setup / teedata /")
    lines.append("  AMLSECU! / Amlogic-secure-boot-module-v0.4 / flash-too-large / storage-larger-than-flash /")
    lines.append("  opteed_std+opteed_fast / PSCI no-System-Off/Reset-hook errors.")
    lines.append("gxb adds: exceed max DMA SHA2/AES length (crypto helpers, unlinked).")
    lines.append("dispatcher: table-driven SiP/runtime-service; no literal 0x820000ff compare isolated,")
    lines.append("no call edge from a 0x820000ff dispatch to AMLSECU/secureboot code established.")
    lines.append("comparative only: must not be cited as aquaman BL31 behavior.")
    return "\n".join(lines)


VERBS = {"inventory": inventory, "handoff": handoff, "dtb": dtb,
         "emmc": emmc, "bl31ref": bl31ref}


def main():
    args = sys.argv[1:] or ["all"]
    if args == ["all"]:
        args = ["inventory", "handoff", "dtb", "emmc", "bl31ref"]
    rc = 0
    for a in args:
        fn = VERBS.get(a)
        if not fn:
            print("unknown verb %s" % a, file=sys.stderr)
            rc |= 2
            continue
        print("### %s" % a)
        print(fn())
        print()
    return rc


if __name__ == "__main__":
    sys.exit(main())
