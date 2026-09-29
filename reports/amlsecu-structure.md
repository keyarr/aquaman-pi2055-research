# amlsecu-structure — formal layout of container 0x0905

tool: `tools/parse_amlsecu.py` (read-only). Outputs verified against `boot_unpack/kernel` and `recovery_unpack/kernel`.

## global header (offset relative to start of kernel slice, LE)

| offset | size | field | endian | boot | recovery |
|---|---|---|---|---|---|
| +0x00 | 8 | magic `AMLSECU!` | ascii | `414d4c5345435521` | same |
| +0x08 | 4 | version | u32 LE | `0x0905` | same |
| +0x0C | 4 | nBlkCnt | u32 LE | 3 | 3 |
| +0x10 | 16 | szTimeStamp | ascii | `2022090612544443` | `2022090613082318` |
| +0x20 | 96 | amlKernel (t_aml_enc_blk) | — | see below | see below |
| +0x80 | 96 | amlRamdisk (t_aml_enc_blk) | — | all zeroes | see below |
| +0xE0 | 96 | amlDTB (t_aml_enc_blk) | — | see below | see below |
| +0x140 | 1088 | reserved | — | zeroes | zeroes |
| +0x600 | 512 | image signature | opaque | `6f3a5499...` | `60735030...` (different) |
| +0x800 | — | start of blk0 payload | — | ciphertext | ciphertext (differs from boot from byte 0) |

total header `0x800`. For Android 9, U-Boot uses base 4096 and places the info at +2048 (`(secureKernelImgSz>>1)`), with `reserve4ImgHdr[2048]`. `COMPILE_TYPE_ASSERT(2048 >= sizeof(...))` in pre-9 sources became 4096 in the 9 variant. The magic at file offset `0x800` (after the Android header page) is a direct consequence of this, not a coincidence.

## descriptor per block (96 = 0x60 bytes, u32 LE)

| +off | size | field (source) | boot blk0 | boot blk2 | rec blk1 | rec blk2 |
|---|---|---|---|---|---|---|
| +0x00 | 4 | nOffset | `0x800` | `0x959800` | `0x959800` | `0xfab000` |
| +0x04 | 4 | nRawLength | 9800145 | 59424 | 6623797 | 59424 |
| +0x08 | 4 | nSigLength | 9801728 | 61440 | 6625280 | 61440 |
| +0x0C | 4 | nAlignment | 2048 | 2048 | 2048 | 2048 |
| +0x10 | 4 | nTotalLength | 9801728 | 61440 | 6625280 | 61440 |
| +0x14 | 12 | szPad | zeroes | zeroes | zeroes | zeroes |
| +0x20 | 32 | szSHA2IMG | zeroes | zeroes | zeroes | zeroes |
| +0x40 | 32 | szSHA2KeyID | `ef8996bd...1492` | same | same | same |

boot blk1 is 96 zeroed bytes (no ramdisk).

## derived rules (all verified)

* `nTotalLength = ALIGN_UP(nRawLength, 2048)`:
  9800145->9801728, 59424->61440, 6623797->6625280. Alignment is by page/flash boundary, not AES block (16).
* In this firmware, `nSigLength == nTotalLength` always. The name suggests "signed size", but it cannot be distinguished from "encrypted size"; treat as opaque.
* `nOffset` is file/flash offset of the slice: blk0 `0x800` (= start of kernel slice), blk1 `0x959800` (`0x800+9801728`, start of ramdisk slice), blk2 boot `0x959800` (empty ramdisk, second attached right after kernel), blk2 recovery `0xfab000` (`0x800+9801728+6625280`, start of second). Matches `kernel_size`/`ramdisk_size`/`second_size` from Android header.
* Total secure size (Android 9):
  `4096 + sum(nTotalLength)`. Boot: 4096+9801728+0+61440 = 9867264 (`0x969000`); AVB at 9871360 (+4096). Recovery: 4096+9801728+6625280+61440 = 16492544 (`0xfba800`); AVB at 16494592 (+2048). Matches the loop in `_aml_get_secure_boot_kernel_size`.
* `szSHA2IMG` is zeroed across all blocks in both images: the image hash field is not used in this flow (or is only populated during in-memory verification). It is not a per-block hash.
* `szSHA2KeyID` is identical (`ef8996bd...`) across the 5 non-empty blocks in both images, zeroed in the empty block. It is a key identifier, not a content hash. See `amlsecu-key-path.md`.
* The 512-byte signature at +0x600 differs between boot and recovery (timestamps 14 min apart). Covers header + payloads; without the user-key, it is not reproducible.

## field classification

* Constants: magic, version, nAlignment (2048), szPad, szSHA2IMG (zero).
* Per-firmware (identical in boot+recovery): nRaw/nSig/nTotal of kernel and DTB, szSHA2KeyID.
* Per-image: timestamp, payloads, 512 B signature, present blocks (ramdisk only in recovery).
* Per-block: nOffset, nRawLength, nTotalLength.
