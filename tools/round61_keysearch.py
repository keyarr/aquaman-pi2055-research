#!/usr/bin/env python3
"""round61: offline keyman-blob -> AES key search against firmware images.

Read-only. No device I/O. Candidates follow the brief: key=blob,
key=SHA256(blob), and (key=blob[0:0x20], iv=blob[0:0x30]) key_info layout
(round28-fip/05). The Amlogic reference tail32 (round29 sec 3) is included as
an explicit cross-check.

Target windows and expected plaintexts are taken from round28/05 and round29:
bootloader.img [0,0xC000) and [0xC000] FIP ToC, [0x20000] BL31 stream;
boot.img [0x800] amlKernel and [0x959800] amlDTB ciphertext (parse_amlsecu.py).

Usage: python3 tools/round61_keysearch.py
"""
import hashlib
import json
import os
import struct
import sys

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOBS = "/tmp/blobs"
REF_TAIL32 = bytes.fromhex(
    "02bc96a283e26fb38be4c0872a6e913dcbf7976192d3daabf7ba3b2ee7cae6ee")

MAGICS = [
    ("@AML", b"@AML"),
    ("AMLSECU!", b"AMLSECU!"),
    ("AMLC", b"AMLC"),
    ("ARMd", b"ARMd"),
    ("ANDROID!", b"ANDROID!"),
    ("FDT", bytes.fromhex("d00dfeed")),
    ("BL31HDR", bytes.fromhex("65873412")),
    ("FIP", bytes.fromhex("010064aa78563412")),
]

TARGETS = [
    # (file, offset, label, expected size field description)
    ("firmware/bootloader.img", 0x00000, "bl2enc stage1", "FIP ToC version word"),
    ("firmware/bootloader.img", 0x0C000, "bootmk header", "FIP ToC version word"),
    ("firmware/bootloader.img", 0x20000, "BL31 stream", "BL31 header / object"),
    ("firmware/boot.img", 0x00800, "amlKernel", "arm64 Image size @+8"),
    ("firmware/boot.img", 0x959800, "amlDTB", "FDT totalsize @+4 (BE)"),
]


def cbc_first(key, iv, ct16):
    return Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor().update(ct16)


def ecb_first(key, ct16):
    return Cipher(algorithms.AES(key), modes.ECB()).decryptor().update(ct16)


def candidates():
    out = []
    for fn in sorted(os.listdir(BLOBS)):
        if not fn.endswith(".bin"):
            continue
        blob = open(os.path.join(BLOBS, fn), "rb").read()
        if not blob:
            continue
        tag = fn[:-4]
        # key=blob, exactly when it is 32 bytes; padded/truncated variants are
        # labelled as such and kept cheap for completeness.
        if len(blob) == 32:
            out.append(("%s:blob32" % tag, blob, b"\0" * 16))
        elif len(blob) > 32:
            out.append(("%s:blob[:32]" % tag, blob[:32], b"\0" * 16))
        else:
            out.append(("%s:blob+zeropad" % tag,
                        blob + b"\0" * (32 - len(blob)), b"\0" * 16))
        out.append(("%s:sha256" % tag, hashlib.sha256(blob).digest(), b"\0" * 16))
        if len(blob) >= 0x30:
            out.append(("%s:key_info" % tag, blob[0:0x20], blob[0x20:0x30]))
    out.append(("ref_tail32:direct", REF_TAIL32, b"\0" * 16))
    out.append(("ref_tail32:sha256", hashlib.sha256(REF_TAIL32).digest(), b"\0" * 16))
    return out


def coherent(label, plain):
    """Cheap size sanity on the first decrypted block."""
    if label == "BL31 stream" or label == "bl2enc stage1" or label == "bootmk header":
        return struct.unpack_from("<I", plain, 4)[0] in (0x12345678, 0x00030001)
    if label == "amlKernel":
        sz = struct.unpack_from("<Q", plain, 8)[0]
        return 0x1000 < sz < 0x10000000
    if label == "amlDTB":
        sz = struct.unpack_from(">I", plain, 4)[0]
        return 0x1000 < sz < 0x100000
    return False


def main():
    blobs = {}
    for fn in sorted(os.listdir(BLOBS)):
        if fn.endswith(".bin"):
            b = open(os.path.join(BLOBS, fn), "rb").read()
            if b:
                blobs[fn[:-4]] = {"len": len(b), "sha256": hashlib.sha256(b).hexdigest()}
    print("blobs:", json.dumps(blobs, indent=2))

    imgs = {}
    for path, off, label, _ in TARGETS:
        p = os.path.join(REPO, path)
        with open(p, "rb") as f:
            f.seek(off)
            imgs[(path, off)] = f.read(16)

    cands = candidates()
    rejected = []
    hits = []
    for tag, key, iv in cands:
        kh = hashlib.sha256(key).hexdigest()
        for path, off, label, _ in TARGETS:
            ct = imgs[(path, off)]
            outs = [("cbc", cbc_first(key, iv, ct)),
                    ("ecb", ecb_first(key, ct))]
            for mname, plain in outs:
                named = [n for n, m in MAGICS if plain.startswith(m)]
                inside = [n for n, m in MAGICS if m in plain]
                good = bool(named) and coherent(label, plain)
                rec = {"candidate": tag, "key_sha256": kh,
                       "iv": iv.hex(), "mode": mname, "file": path,
                       "offset": hex(off), "target": label,
                       "plain": plain.hex(" "), "magic_at0": named,
                       "magic_inside": inside, "size_ok": coherent(label, plain)}
                (hits if good else rejected).append(rec)

    print("candidates=%d, tests=%d, hits=%d" % (len(cands), len(rejected) + len(hits), len(hits)))
    for h in hits:
        print("HIT", json.dumps(h))
    # Every candidate gets one sha256 line in the report, regardless of target.
    print("rejected candidate keys (sha256):")
    seen = set()
    for tag, key, iv in cands:
        kh = hashlib.sha256(key).hexdigest()
        k = (tag, kh)
        if k in seen:
            continue
        seen.add(k)
        print("  %-28s key_sha256=%s iv=%s" % (tag, kh, iv.hex()))
    # Show the first block for the most informative target of each candidate.
    print("first-block samples (BL31 stream, CBC):")
    for tag, key, iv in cands:
        plain = cbc_first(key, iv, imgs[("firmware/bootloader.img", 0x20000)])
        print("  %-28s %s" % (tag, plain.hex(" ")))
    return 0 if hits else 1


if __name__ == "__main__":
    sys.exit(main())
