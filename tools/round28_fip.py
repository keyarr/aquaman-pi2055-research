#!/usr/bin/env python3
"""round28: offline FIP / firmware-pipeline reconstruction.

Everything here is derived from bytes already in the repo plus static
analysis of the two not-stripped vendor tools that ship inside the
reference tree:

  .src/u-boot-khadas/fip/fip_create          (ELF64, not stripped)
  .src/u-boot-khadas/fip/gxl/aml_encrypt_gxl (ELF64 static, debug_info)

The FIP ToC layout, the UUID table and the bl31.img header were confirmed by
*running* fip_create on the family artifacts and reading its own --dump
output plus the produced bytes. The crypto contract (AES-256-CBC, zero IV,
0xC000 window, key = last 32 bytes of the key package) was read out of
aml_bl2_enc_file / aml_file_aes in aml_encrypt_gxl.

No device I/O. No writes.
"""
import collections
import math
import os
import struct
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- FIP ToC --
# fip_create --dump + the bytes it produces. see reports/round28-fip/02.
TOC_MAGIC = 0xAA640001
TOC_VERSION = 0x12345678
TOC_HDR = 0x10                 # bytes before the first entry
TOC_ENTRY = 0x28               # uuid[16] + u64 offset + u64 size + u64 flags

# fip_create .data @0x6030a0 (toc_entry_lookup_list). These are the canonical
# Amlogic/TF-A fip UUIDs.
FIP_UUIDS = {
    "5ff9ec0b4d223e4da544c39d81c73f0a": "TOC",
    "9766fd3d89bee849ae5d78a140608213": "BL2",
    "ddccbbaacdabefefabcd12345678abcd": "BL301",
    "47d4086d4cfe98469b952950cbbd5a00": "BL30",
    "05d0e18953dc13478d2b500a4b7a3e38": "BL31",
    "d6d0eea7fcead54b97829934f234b6e4": "BL32",
}

# fip_create orders payloads BL2, BL30, BL31, BL32, BL33 but stamps each ToC
# entry with the *predecessor's* uuid, so searching UUID_X yields the payload
# of the component after X. verified against a 5-component package.
PRED_OF_PAYLOAD = ["TOC", "BL2", "BL30", "BL31", "BL32"]

UUID_OF_NAME = {v: k for k, v in FIP_UUIDS.items()}


def parse_toc(buf):
    """Parse a plaintext Amlogic FIP ToC.

    +0x00 u32 magic 0xaa640001
    +0x04 u32 0x12345678
    +0x08 u64 0
    entry[i] @ 0x10 + 0x28*i : uuid[16], u64 offset, u64 size, u64 flags
    terminator: null uuid, offset == end of image data
    """
    if len(buf) < TOC_HDR + TOC_ENTRY:
        raise ValueError("buffer too small for a ToC")
    magic, version = struct.unpack_from("<II", buf, 0)
    if magic != TOC_MAGIC:
        raise ValueError("not a FIP ToC (magic %#010x)" % magic)
    entries = []
    off = TOC_HDR
    while off + TOC_ENTRY <= len(buf):
        uuid = buf[off:off + 16].hex()
        offset, size, flags = struct.unpack_from("<QQQ", buf, off + 0x10)
        entries.append({"uuid": uuid, "name": FIP_UUIDS.get(uuid),
                        "offset": offset, "size": size, "flags": flags})
        if uuid == "0" * 32:
            break
        off += TOC_ENTRY
    return {"version": version, "entries": entries}


def payload_name(entry):
    """The entry's uuid identifies its predecessor; the payload is the next."""
    return entry.get("name")


def bl31_uuid():
    return UUID_OF_NAME["BL31"]


# ------------------------------------------------------- AML control block --
# aml_ctrl_blk_check @0x4022ee in aml_encrypt_gxl. 0x200 bytes, "AMLC" at both
# +0x0c and +0xfc, block size 0x200 at +0x02/+0x14/+0xfa, version <= 1 at +0x06.
CTRL_BLK = 0x200
CTRL_MAGIC = 0x434C4D41          # 'AMLC'


def check_ctrl_blk(buf):
    """Reimplementation of aml_ctrl_blk_check. Returns (ok, [failures])."""
    f = []
    if len(buf) < CTRL_BLK:
        return False, ["short buffer"]
    if struct.unpack_from("<I", buf, 0x0C)[0] != CTRL_MAGIC:
        f.append("+0x0c != AMLC")
    if struct.unpack_from("<I", buf, 0xFC)[0] != CTRL_MAGIC:
        f.append("+0xfc != AMLC")
    if struct.unpack_from("<H", buf, 0x06)[0] > 1:
        f.append("+0x06 version > 1")
    if struct.unpack_from("<H", buf, 0x02)[0] != CTRL_BLK:
        f.append("+0x02 != 0x200")
    if struct.unpack_from("<H", buf, 0xFA)[0] != CTRL_BLK:
        f.append("+0xfa != 0x200")
    if struct.unpack_from("<I", buf, 0x14)[0] != CTRL_BLK:
        f.append("+0x14 != 0x200")
    return not f, f


# ---------------------------------------------------------- crypto contract --
# aml_encrypt_gxl:
#   aml_file_aes()        @0x40159e  AES, aes_setkey_enc/dec(.., 0x100) = 256 bit,
#                                   aes_crypt_cbc(), requires (len & 0xf)==0
#   aml_bl2_enc_file()    @0x40d2a6  key_info is bzero()ed, then exactly the
#                                   last 0x20 bytes of the key package are read
#                                   into ki[0:0x20]. ki[0x20:0x30] is therefore
#                                   ZERO -> IV = 16 * 0x00.
#                                   aml_file_aes(fp, 0xC000, &ki, enc=1) and fp
#                                   was just fopen()ed -> encrypts [0, 0xC000).
#   aml_bl3_enc_file()    @0x40d57c  per-object: ki fully filled with rand()
#                                   (32B key + 16B IV) and exported as
#                                   "%s.key.pxp" ("AES key for PXP").
AES_BITS = 256
AES_BLOCK = 16
IV = b"\x00" * 16
BL2_ENC_WINDOW = 0xC000
KEY_PACKAGE_SIZES = (0x20, 0x1B40)   # aml_bl2_enc_file accepted key-file sizes
BL31_IMG_MAGIC = 0x12348765          # aml_bl3_enc_file: presence of the bl31.img
                                     # header sets the encryption offset to 0x200

# ---------------------------------------------------- AMLSECU! container --
# Android-9 AMLSECU! (0x0905) images: full header in tools/parse_amlsecu.py and
# reports/amlsecu-structure.md. Here only what the payload map needs. The
# magic sits at file offset 0x800 (AmlSecureBootImg9Header, reserve 2048) and
# the three t_aml_enc_blk descriptors follow at +0x20/+0x80/+0xE0.
AMLSECU_MAGIC = b"AMLSECU!"
AMLSECU_VERSION = 0x0905
AMLSECU_HDR_OFF = 0x800
AMLSECU_DESC = {"kernel": 0x20, "ramdisk": 0x80, "dtb": 0xE0}
AMLSECU_DESC_SZ = 0x60
AMLSECU_KEYID_OFF = 0x40          # szSHA2KeyID inside t_aml_enc_blk


def amlsecu_block(buf, which):
    """(nOffset, nRawLength, nTotalLength, keyid32) for one descriptor of an
    AMLSECU! image whose magic sits at AMLSECU_HDR_OFF."""
    base = AMLSECU_HDR_OFF + AMLSECU_DESC[which]
    noff, nraw, nsig, nalgn, ntot = struct.unpack_from("<5I", buf, base)
    keyid = bytes(buf[base + AMLSECU_KEYID_OFF:base + AMLSECU_KEYID_OFF + 32])
    return noff, nraw, ntot, keyid


# aml_check_root_key_sha2_with_efuse @0x4064ce. Three 32-byte SHA-2 digests
# built byte-by-byte on the stack; a memcmp against the candidate root key
# digest returns 0 on the first match. These are the digests the vendor tool
# will accept as an Amlogic master/root key.
ROOT_KEY_SHA2 = (
    bytes.fromhex("02bc96a283e26fb38be4c0872a6e913dcbf7976192d3daabf7ba3b2ee7cae6ee"),
    bytes.fromhex("557eecbd90829f8ed64faf63eb3c3b558d72f0a5505863b8b6c2398c583945eb"),
    bytes.fromhex("33fbf3b3bc07c3c9b67d0fab0c52dfdea7b2c13005257087d10d33de6cf8debb"),
)


# ------------------------------------------------------------- measurements --
def chi2(block):
    """Pearson chi2 of byte values against uniform. df=255."""
    if not block:
        return 0.0
    c = collections.Counter(block)
    e = len(block) / 256.0
    return sum((c.get(i, 0) - e) ** 2 / e for i in range(256))


def entropy(block):
    if not block:
        return 0.0
    c = collections.Counter(block)
    n = len(block)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def census(buf, blk=4096):
    """Per-block chi2/entropy. Expected value df=255; >340 over 4 KiB blocks
    would be a real deviation from uniform."""
    return [(o, chi2(buf[o:o + blk]), entropy(buf[o:o + blk]))
            for o in range(0, len(buf), blk)]


def repeats(buf, bs=16, aligned=True):
    """16-byte blocks occurring more than once. Uniform data gives ~0 hits;
    a hit means ECB, a fixed-IV-per-object scheme, or a literal constant."""
    step = bs if aligned else 1
    c = collections.Counter()
    where = collections.defaultdict(list)
    for i in range(0, len(buf) - bs + 1, step):
        k = buf[i:i + bs]
        c[k] += 1
        where[k].append(i)
    return {k: v for k, v in c.items() if v > 1}, where


def common_run(buf, offs):
    """Maximal byte range, relative to offs[0], over which every offset in
    offs holds identical bytes. Returns (start, end) relative to offs[0]."""
    lo = 0
    while all(buf[o - lo - 1] == buf[offs[0] - lo - 1] for o in offs) and offs[0] - lo - 1 >= 0:
        lo += 1
    hi = 0
    n = len(buf)
    while all(buf[o + hi] == buf[offs[0] + hi] for o in offs) and offs[0] + hi < n:
        hi += 1
    return -lo, hi


def search_blocks(plain, ct, bs=16):
    """Known-plaintext: any ciphertext block equal to a plaintext block?
    Zero hits refutes ECB for that object."""
    idx = {}
    for i in range(0, len(plain) - bs + 1, bs):
        idx.setdefault(plain[i:i + bs], i)
    hits = []
    for o in range(0, len(ct) - bs + 1):
        j = idx.get(ct[o:o + bs])
        if j is not None:
            hits.append((o, j))
    return hits


def cbc_decrypt_block0(key, ct):
    """AES-256-CBC, IV=0: first plaintext block = D(C[0]) xor 0. Needs only the
    first ciphertext block, so it is a valid oracle for a candidate key
    against the known FIP ToC plaintext prefix."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    return Cipher(algorithms.AES(key), modes.CBC(IV)).decryptor().update(ct[:16])


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "bootloader.img")
    buf = open(path, "rb").read()
    print("# %s  %d bytes (0x%x)" % (path, len(buf), len(buf)))
    print("whole-file chi2 = %.1f (df=255, 99.9%% crit ~ 310)" % chi2(buf))
    rows = census(buf)
    worst = sorted(rows, key=lambda r: -r[1])[:3]
    print("worst 4K blocks: " + ", ".join("0x%x chi2=%.1f" % (o, c) for o, c, _ in worst))
    dup, where = repeats(buf)
    print("repeated 16B blocks: %d distinct" % len(dup))
    for k, v in sorted(dup.items(), key=lambda kv: -kv[1])[:8]:
        print("  x%d %s @ %s" % (v, k.hex(), [hex(x) for x in where[k]]))