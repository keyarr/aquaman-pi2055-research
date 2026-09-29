#!/usr/bin/env python3
"""Offline AMLSECU 0x0905 header parser. Read-only, never writes dumps."""
import struct
import sys

MAGIC = b"AMLSECU!"
VERSION = 0x0905
DESC_SIZE = 0x60
SIG_OFF = 0x600
SIG_SIZE = 0x200
HDR_SIZE = 0x800


def parse_block(buf, base, name):
    nOffset, nRaw, nSig, nAlign, nTotal = struct.unpack("<IIIII", buf[base:base + 20])
    pad = buf[base + 20:base + 32]
    sha_img = buf[base + 32:base + 64]
    sha_key = buf[base + 64:base + 96]
    return {
        "name": name,
        "off": base,
        "nOffset": nOffset,
        "nRawLength": nRaw,
        "nSigLength": nSig,
        "nAlignment": nAlign,
        "nTotalLength": nTotal,
        "pad_zero": set(pad) == {0},
        "sha2img_zero": set(sha_img) == {0},
        "sha2img": sha_img.hex(),
        "sha2keyid": sha_key.hex(),
    }


def parse(path):
    d = open(path, "rb").read()
    idx = d.find(MAGIC)
    if idx < 0:
        print("%s: no AMLSECU magic" % path)
        return 1
    ver, nblk = struct.unpack("<II", d[idx + 8:idx + 16])
    ts = d[idx + 16:idx + 32]
    print("file: %s (len %d, magic at 0x%x)" % (path, len(d), idx))
    print("  version: 0x%04x %s" % (ver, "OK" if ver == VERSION else "MISMATCH"))
    print("  nblk: %d" % nblk)
    try:
        print("  timestamp: %s" % ts.decode("ascii"))
    except UnicodeDecodeError:
        print("  timestamp raw: %s" % ts.hex())
    total = 4096
    for i, name in enumerate(("amlKernel", "amlRamdisk", "amlDTB")):
        b = parse_block(d, idx + 0x20 + i * DESC_SIZE, name)
        print("  blk%d %s @+0x%x:" % (i, b["name"], 0x20 + i * DESC_SIZE))
        print("    nOffset=0x%x nRaw=0x%x(%d) nSig=0x%x nAlign=0x%x nTotal=0x%x(%d)"
              % (b["nOffset"], b["nRawLength"], b["nRawLength"],
                 b["nSigLength"], b["nAlignment"], b["nTotalLength"], b["nTotalLength"]))
        print("    pad_zero=%s sha2img_zero=%s" % (b["pad_zero"], b["sha2img_zero"]))
        print("    sha2keyid=%s" % b["sha2keyid"])
        total += b["nTotalLength"]
    print("  computed secure size: 4096 + sum(nTotal) = %d (0x%x)" % (total, total))
    sig = d[idx + SIG_OFF:idx + SIG_OFF + SIG_SIZE]
    print("  sig @+0x600 len %d, allzero=%s head=%s" % (len(sig), set(sig) == {0}, sig[:16].hex()))
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: parse_amlsecu.py <file> [file...]")
        sys.exit(2)
    rc = 0
    for p in sys.argv[1:]:
        rc |= parse(p)
    sys.exit(rc)
