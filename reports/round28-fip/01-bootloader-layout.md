# round28 s1: bootloader.img inventory and at-rest character

date 2026-09-30. offline round. no device I/O, no writes, no execution of
device code. tools `tools/round28_fip.py`, tests `TestRound28Fip`.

## 1. the exact-aquaman artifact

```text
path        bootloader.img  (and firmware/bootloader.img, byte-identical)
size        1344000  = 0x148200
sha256      c7b8eea624f2931cd5d78a513dff407b3ccde4f42202763b32b4758551ef3424
alignment   0x200-aligned, NOT 0x4000-aligned
```

`0x148200` is not a multiple of 0x4000. That matters: `aml_boot_sig_file`
finishes by calling `aml_file_boom(dst, 0x4000, 0)` to pad the image to a
16 KiB boundary, so `bootloader.img` is **not** the output of
`aml_encrypt_gxl --bootsig`.

## 2. at-rest census: uniform ciphertext, everywhere

```text
whole-file chi2 vs uniform   = 226.6   (df=255, 99.9% critical ~ 310)
per-4KiB chi2  n=329         min 200.0  median 253.9  max 314.9
blocks above the 0.1% point  = 0 / 329
```

No 4 KiB block anywhere deviates from uniform. There is therefore:

* no plaintext header (not even an Amlogic `@AML` / `AMLC` control block)
* no plaintext FIP ToC
* no plaintext BL2, BL30, BL31, BL32 or BL33
* no padding, no zero/0xff fill, no constant 1 KiB block
* no length field, no IV-like prefix

Corroborating measurements:

```text
entropy, 4 KiB blocks        7.90 .. 8.00 (one block at 7.55, within sampling noise)
byte-value histogram         5177 zeros / 5166 0xff out of 1344000 (expected 5250 each)
aligned 0000/ffff runs >=64B  0
constant 1 KiB blocks        0
all-zero 16B blocks          0
```

An earlier note in this session flagged the final 4 KiB block as
chi2=3170. That was a bug in the analysis script (the expected count was
hardcoded to 4096/256 for a 512-byte tail block). Recomputed correctly the
same range scores 277. There is no tail anomaly. The whole file is uniform.

## 3. magic census (negative)

Searched for every magic recovered from the vendor toolchain in s2-s5:

```text
0xaa640001  FIP ToC magic          0 hits
0x12345678  ToC version word       0 hits
0x12348765  bl31.img magic         0 hits
"AMLC"      control block          0 hits
"@AML"      image item             0 hits
5ff9ec0b / 9766fd3d / ddccbbaa /    0 hits each (all six FIP UUID first words)
47d4086d / 05d0e189 / d6d0eea7
"ANDROID!"                        0 hits
```

## 4. the one structural finding: a 128-byte record five times

Repeated 16-byte blocks in 1344000 bytes of uniform data are impossible by
chance (expected count ~0). There are exactly eight, and they are the eight
consecutive 16-byte slices of a single 128-byte record:

```text
record = 7903307770ddfd655 0dad979a1f39256
         af05d1b9a5a0e6a7 dbacade960a273fe
         e2a8b8b45f5fa735 2a1c4f1e5b1df341
         675b7d50f7455ca4 2fad47c6d130994b
         867a8e79e8cabdff 98b1d90311962707
         028f153ca11264df 70995e59da7ce68f
         9f5ce83b9304b0a3 5322ffd89c4cccd9
         56f11c85a53d89ab 5d858c8f740f0637
```

occurring at

```text
0x0000c080   0x00010080   0x00020080   0x0004c080   0x0008c080
```

All five sites share the byte range `[site, site+0x80)` exactly, and the bytes
immediately before and immediately after that range differ at every site.
An unaligned sweep of all 16-byte windows in the file finds no other repeated
value, so this record is the file's only non-random structure.

Every site is `0x80` mod `0x10000`. See s2 for what that implies.

## 5. ECB refuted for the BL33 object

Known plaintext exists for BL33: `reports/round14-bl33-persist/bl33-37e18000.bin`
is the live u-boot image, 0x1d8000 bytes, dumped from RAM in round 14. All
79601 distinct 16-byte plaintext blocks were searched at every one of the
1344000 ciphertext byte offsets.

```text
hits = 0
```

So the BL33 payload is not stored under AES-ECB (nor under any fixed
key-independent block permutation). Whatever the container is, the payloads
are not ECB.

## 6. classification

```text
bootloader.img  0x148200  ciphertext, uniform, no structure except one
                            128-byte record at five fixed offsets
aquaman BL31 bytes recovered   NO
container format identified   NO (see s2, s8)
```

Cross-checks: the device reports `unlocked: yes / secure: no`
(`reports/bootloader_unlock.md`), so the at-rest encryption is not the
device's current secure-boot state. It is a property of how the factory
image was produced.

## 7. the AMLSECU! sibling artifacts: payload maps (delta, same round)

The boot-family images expose what the bootloader images hide, because their
headers are plaintext. All numbers measured, byte-pinned in
`TestRound28Fip.test_boot_img_payload_map` / `.test_dt_img_is_keyid_plus_ciphertext`:

```text
boot.img (0x1000000, sha256 7797e3df…00aad)
  [0x000, 0x800)     Android boot header (ANDROID!)
  [0x800, 0x1000)    AMLSECU! 0x0905 header (ts 2022090612544443)
  [0x1000, 0x95a000) kernel object   (nTotal 0x959000, ciphertext)
  [0x95a000,0x969000) dtb object     (nTotal 0x00F000, ciphertext)
  [0x969000,0x96a000) AVB hash block (low entropy, unsigned hashes)
  [0x96a000,0x96b000) vbmeta ("AVB0", algorithm 0 = unsigned)
  [0x96b000,0xFFFFC0) zeros
  [0xFFFFC0,0x1000000) AVB footer "AVBf": vendor deviation, the three
                     payload fields are BE u32 at +0x10/+0x18/+0x20
                     (0x969200 content size, 0x96A000 vbmeta offset,
                     0x200 vbmeta size) each followed by a zero u32
```

`dt.img` is the same DTB object packaged standalone:

```text
dt.img (0xE820, sha256 ea2f4c65…a993)
  [0x00, 0x20)  szSHA2KeyID, PLAINTEXT: ef8996bd5ce1740a…47601492
  [0x20, 0xE820) 0xE800 ciphertext, entropy 7.997, longest zero run 1
```

Corollaries:

```text
- the KeyID is byte-identical in all four AMLSECU! descriptors
  (boot kernel/dtb, recovery kernel/dtb) and equals the dt.img plaintext
  prefix. One firmware key identity across the whole PI.2055 set.
- the encrypted objects inside boot.img do NOT carry the KeyID prefix; the
  prefix exists only on the standalone dt partition image.
- dt.img's ciphertext differs byte-for-byte from boot.img's dtb object
  (203/59424 bytes coincide by chance) although both wrap the same 59424-
  byte plaintext: consistent with the vendor per-object random key/IV
  scheme of s5 (aml_bl3_enc_file rand()), now corroborated on two
  independently packaged copies of the same input.
- the bootloader.img 128-byte record is NOT this KeyID in any 16-byte
  slice (test-pinned); no link between the two containers' metadata.
```