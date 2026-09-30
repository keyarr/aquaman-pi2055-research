#!/usr/bin/env python3
"""round29: reproducible crypto oracle for the aml_encrypt_gxl pipeline.

Everything in here is read OUT OF the not-stripped vendor binary
(.src/u-boot-khadas/fip/gxl/aml_encrypt_gxl, ELF64 x86-64, Apr 25 2017,
"AMLOGIC-GXL-GXM-TXL-SIG-module : Ver-1.3") or measured from the at-rest
images. No device, no live code, no brute force: `check_key` answers ONE
AES-256 ECB block decryption per call and is intended for candidates whose
provenance is demonstrated elsewhere.

Key facts encoded here (with the disassembly sites that prove them):

  aml_bl2_enc_file  0x40d2a6  package size in {0x20, 0x1b40}; key =
                              package tail 32B -> key_info[0:0x20];
                              key_info[0x20:0x30] stays ZERO (IV=0);
                              aml_file_aes(fp, 0xC000, ...) on the copy.
  aml_boot_make     0x41c9dd  file = BL2[0,0xC000) + header@0xC000 +
                              payloads[0x10000..]; header window encrypted
                              [0xC000, 0xFE00) under a RANDOM key whose
                              key+IV are stored PLAINTEXT at ctrl+0x40;
                              ctrl written at 0xC000 AND 0xFE00.
  aml_boot_make_v3  0x41d860  header[0xC000,0x10000) = 0x4000 bytes;
                              entries 0x20B at +0x10, uuids at +0xC0;
                              encrypted with package tail 32B as key and
                              IV = package[0:16] (userkey[0:0x20] = key+IV).
  aml_bl3_enc_file  0x40d57c  per-object random key: ctrl(+0x40)=rand 48B
                              plaintext, ctrl(+0x88)=timestamp; encrypt
                              [0x200, 0x200+size) IV=ctrl[0:16]; also
                              writes ctrl+0x1c00.. and tail copy@0x1c00
                              when userkey given; LZ4 wrapper writes
                              "LZ4C" + SHA + compressed payload.
  aml_key_bnd       0x40af24  package PRODUCER: rootkeymax <=0x1248 ||
                              pad 0x1248, then ukey <=0x8D8, then the
                              LAST 32B of the --aeskey file verbatim.
  bl31.img header   (fixture) 0x200 PLAINTEXT: 12348765, size 0x4e20,
                              load 0x05100000, rsv 0x05000000+0x300000,
                              secure 0x05100000+0x200000.
"""
import hashlib
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --------------------------------------------------------------- constants

AES_BITS = 256
IV_ZERO = b"\x00" * 16
BL2_ENC_WINDOW = 0xC000
BOOTMK_HDR_START = 0xC000
BOOTMK_HDR_V1_END = 0xFE00          # v1 encrypts [0xC000, 0xFE00)
BOOTMK_HDR_V3_END = 0x10000         # v3 encrypts [0xC000, 0x10000)
BL31_IMG_MAGIC = 0x12348765
CTRL_MAGIC_A = 0x434C4D41           # "AMLC" at ctrl+0x0c and +0xfc
LZ4C_MAGIC = 0x43345A4C             # "LZ4C" at lz4 wrapper +0x00

TOC_MAGIC = 0xAA640001              # FIP ToC header word (header@0xC000)
TOC_VERSION = 0x12345678            # v1 / fip_create
TOC_VERSION_V3 = 0x00030001         # v3 header word @0xC004

# TF-A uuid table, aml_encrypt_gxl .data 0x716700 (v1 4-entry, low half) and
# the boot_sig_file comparator words at 0x4114f0..0x411524 (0xa7eed0d6 = BL33)
UUID_BL2 = "0becf95f224d4d3ea544c39d81c73f0a"
UUID_BL30 = "3dfd6697be8949e8ae5d78a140608213"
UUID_BL32 = "6d08d447fe4c46989b952950cbbd5a00"
UUID_BL31 = "05d0e18953dc13478d2b500a4b7a3e38"
UUID_BL33 = "a7eed0d6fcead54b97829934f234b6e4"
FIP_UUIDS = (UUID_BL2, UUID_BL30, UUID_BL32, UUID_BL31)

# known plaintext block 0 of the FIP ToC (read from fip_create output and
# pinned in round 28): header word, version word, 8 zero bytes, first entry
# bytes 8..15 (null uuid tail of entry 0)
TOC_FIRST_BLOCK = bytes.fromhex("010064aa785634120000000000000000")

# the vendor's three accepted root-key SHA-2 fingerprints. Source of truth is
# round28_fip.ROOT_KEY_SHA2 (read out of 0x4064ce in round 28 and pinned by
# TestRound28Fip); round 29 imports rather than re-derives them.
ROOT_KEY_SHA2 = None


def _load_root_key_sha2():
    from round28_fip import ROOT_KEY_SHA2 as R28
    return R28

# package format (from aml_key_bnd 0x40af24 and consumers)
PKG_SIZE_SMALL = 0x20               # bare 32B key
PKG_SIZE_FULL = 0x1B40              # rootkeymax + ukey + aeskey tail
PKG_ROOTKEYMAX_MAX = 0x1248
PKG_UKEY_MAX = 0x8D8
PKG_AESKEY_TAIL = 0x20

BOARD_KEY_DIR = os.path.join(REPO, ".src/u-boot-khadas/board/amlogic")
VENDOR_BIN = os.path.join(REPO, ".src/u-boot-khadas/fip/gxl/aml_encrypt_gxl")


ROOT_KEY_SHA2 = _load_root_key_sha2()


# --------------------------------------------------------------- fixtures

def user_key_fixtures():
    """The 32 board aml-user-key.sig fixtures shipped in the vendor tree.

    These are real build inputs of the reference tree (the Makefile passes
    $(BOARDDIR)/aml-user-key.sig to --bootsig/--imgsig/--efsgen), so they
    are exactly the 'candidates whose origin is demonstrated' the oracle
    is allowed to test.
    """
    out = []
    if not os.path.isdir(BOARD_KEY_DIR):
        return out
    for board in sorted(os.listdir(BOARD_KEY_DIR)):
        p = os.path.join(BOARD_KEY_DIR, board, "aml-user-key.sig")
        if os.path.isfile(p):
            out.append((board, p, open(p, "rb").read()))
    return out


# ----------------------------------------------------------------- oracle

def ecb_decrypt_block(key32, ct16):
    """One AES-256 ECB block decryption. Callers compose CBC with a known
    IV themselves (IV=0 means the first CBC block IS this ECB result)."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    d = Cipher(algorithms.AES(bytes(key32)), modes.ECB()).decryptor()
    return d.update(bytes(ct16)) + d.finalize()


def check_key(key32, ct16, expected_pt16):
    """FIRST-BLOCK ORACLE. True iff AES-256-ECB-decrypt(ct16, key32) ==
    expected_pt16. With IV=0 this is exactly the first CBC block test.
    One call == one AES block: this is a verifier, not a search."""
    if len(key32) != 32 or len(ct16) != 16 or len(expected_pt16) != 16:
        raise ValueError("oracle takes a 32B key and 16B blocks")
    return ecb_decrypt_block(key32, ct16) == expected_pt16


def negative_log():
    """Candidates already tested and refuted against the ToC first block
    (bootloader.img ct[0:16] and ct[0xC000:0xC010], IV=0). Pinned so nobody
    repeats them. round28 tested the string hashes; round29 adds the
    structurally-derived candidates that were still live after round 28."""
    cands = [("00" * 32, "no-userkey build variant (key_info all zero)"),
             ("ff" * 32, "all-ones")]
    for board, _, blob in user_key_fixtures():
        cands.append((blob[-32:].hex(), "aml-user-key.sig tail32 (%s)" % board))
        cands.append((blob[:32].hex(), "aml-user-key.sig head32 (%s)" % board))
    uniq = {}
    for h, why in cands:
        uniq.setdefault(h, why)
    return uniq


# ------------------------------------------------------------ measurement

def bootloader_stats():
    """Measured properties of the at-rest bootloader.img that this round's
    verdict rests on. All pure functions of the bytes."""
    p = os.path.join(REPO, "bootloader.img")
    if not os.path.exists(p):
        return None
    bl = open(p, "rb").read()
    st = {
        "size": len(bl),
        "sha256": hashlib.sha256(bl).hexdigest(),
        "ctrl_copy_0xC000_eq_0xFE00": bl[0xC000:0xC200] == bl[0xFE00:0x10000],
        "record_sites": [0xC080, 0x10080, 0x20080, 0x4C080, 0x8C080],
    }
    rec = bl[0xC080:0xC080 + 0x80]
    st["record_128_equal_at_all_sites"] = all(
        bl[s:s + 0x80] == rec for s in st["record_sites"])
    # tail arithmetic
    st["tail_arith"] = {"0x8C000+0xBC200": 0x8C000 + 0xBC200 == len(bl)}
    return st


def family_fixtures():
    """The in-tree gxl family artifacts that double as format fixtures."""
    base = os.path.join(REPO, ".src/u-boot-khadas/fip/gxl")
    out = {}
    for name in ("bl2.bin", "bl30.bin", "bl31.bin", "bl31.img"):
        p = os.path.join(base, name)
        if os.path.exists(p):
            out[name] = open(p, "rb").read()
    return out


def parse_bl31_img_header(blob):
    """The 0x200 PLAINTEXT header of a --bl3sig-wrapped bl31.img."""
    import struct
    h = blob[:0x200]
    magic, size, load = struct.unpack_from("<IIQ", h, 0)
    rsv_start, rsv_size = struct.unpack_from("<QQ", h, 0x10)
    sec_start, sec_size = struct.unpack_from("<QQ", h, 0x20)
    return {"magic": magic, "size": size, "load": load,
            "rsv_start": rsv_start, "rsv_size": rsv_size,
            "secure_start": sec_start, "secure_size": sec_size}


if __name__ == "__main__":
    import sys
    st = bootloader_stats()
    print("bootloader.img:", st)
    fx = user_key_fixtures()
    print("user-key fixtures:", len(fx), "boards,",
          len({b[-32:] for _, _, b in fx}), "unique tail32")
    print("root key fingerprints:", len(ROOT_KEY_SHA2))
