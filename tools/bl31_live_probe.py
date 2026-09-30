#!/usr/bin/env python3
"""bl31_live_probe.py - offline classifier for round19 live RAM probes.

Read-only, no device, no USB, no execution. Takes a saved .bin dump
(C1/C2/C3 64K probes) and prints the evidence the round19 brief asks for.

  classifier <bin> [base]

Checks: sha256, zero ratio, AArch64 decode density (capstone, if present),
eret / smc#0 counts, EL3 register traffic (VBAR_EL3/SCR_EL3/SPSR_EL3/ELR_EL3
via mrs/msr), SMC id words 0x820000xx, 0xb2000016, PSCI strings, AMLSECU/aml/
secure/secmon strings.

Classification (brief section 6):
  NOT_PRESENT / DATA_ONLY / CODE_LIKE / SECURE_MONITOR_LIKE / BL31_STRONG_CANDIDATE

A single string hit is never enough for HIGH. Strong needs control flow +
one of: vector/eret, dispatcher table, EL3 regs, SMC ids including 0x820000ff.
"""
import hashlib
import os
import re
import struct
import sys


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def try_disasm(d, base):
    try:
        from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
    except ImportError:
        return None
    md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    md.skipdata = True
    md.detail = False
    n_insn = 0
    n_branch = 0
    n_eret = 0
    n_smc = 0
    n_msr_el3 = 0
    total = 0
    for ins in md.disasm(d, base):
        total += 1
        n_insn += 1
        m = ins.mnemonic
        if m in ("b", "bl", "blr", "br", "ret", "cbz", "cbnz", "tbz", "tbnz"):
            n_branch += 1
        if m == "eret":
            n_eret += 1
        if m == "smc":
            n_smc += 1
        if m in ("msr", "mrs") and "EL3" in ins.op_str.upper().replace(" ", ""):
            n_msr_el3 += 1
    # density = decodable 4B slots that capstone accepted as insn
    density = total / max(len(d) // 4, 1)
    return {"insn": n_insn, "branch": n_branch, "eret": n_eret,
            "smc": n_smc, "el3reg": n_msr_el3, "density": density}


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: bl31_live_probe.py <bin> [base_hex]")
    path = sys.argv[1]
    base = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
    d = open(path, "rb").read()
    n = len(d)
    nz = sum(1 for b in d if b != 0)
    print("file %s" % path)
    print("size 0x%x (%d)" % (n, n))
    print("sha256 %s" % sha256(path))
    print("nonzero %d/%d (%.3f)" % (nz, n, nz / max(n, 1)))
    if n == 0 or nz == 0:
        print("classification NOT_PRESENT (empty/zero)")
        return 0
    words = struct.unpack("<%dI" % (n // 4), d[:n // 4 * 4])
    eret_w = sum(1 for w in words if w == 0xD69F03E0)
    smc_w = sum(1 for w in words if w == 0xD4000003)
    ff = sum(1 for w in words if w == 0x820000ff)
    b2000016 = sum(1 for w in words if w == 0xB2000016)
    ids = sorted({w for w in words if (w & 0xFFFF0000) == 0x82000000})
    print("eret_words %d smc#0_words %d 0x820000ff_words %d 0xb2000016_words %d" % (
        eret_w, smc_w, ff, b2000016))
    print("0x820000xx distinct %d %s" % (
        len(ids), " ".join("0x%08x" % w for w in ids[:32])))
    dis = try_disasm(d, base)
    if dis is None:
        print("capstone missing, disasm skipped")
    else:
        print("disasm insn=%d branch=%d eret=%d smc=%d el3reg=%d density=%.3f" % (
            dis["insn"], dis["branch"], dis["eret"], dis["smc"],
            dis["el3reg"], dis["density"]))
    strs = {}
    for needle in [b"AMLSECU", b"aml", b"secure", b"secmon", b"bl31",
                   b"opteed", b"PSCI", b"psci", b"tee", b"SMC"]:
        c = len(re.findall(needle, d))
        if c:
            strs[needle.decode()] = c
    print("strings %s" % (strs if strs else "none"))
    # verdict skeleton, human confirms
    if eret_w or (dis and dis["el3reg"]):
        print("verdict needs-human: EL3/vector signal present, check dispatcher + ids")
    elif dis and dis["density"] > 0.5 and dis["branch"] > 10:
        print("verdict needs-human: CODE_LIKE density, check EL3/SMC linkage")
    else:
        print("verdict needs-human: DATA_ONLY unless strings+structure say otherwise")
    print("classification <fill per brief s6: NOT_PRESENT/DATA_ONLY/CODE_LIKE/SECURE_MONITOR_LIKE/BL31_STRONG_CANDIDATE>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
