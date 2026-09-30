# BL31 exact round 18: acquisition without execution

date: 2026-09-30. strictly offline: no USB, no device, no 0x05, no bootm,
no SMC injection, no RAM patch, no eMMC write. every number below is read
from persisted artifacts with tools/bl33_round18.py (detail in
reports/round18-bl31/01..06). prior state: round 17 closed E3 on the BL33
side (no validation at do_bootm site 0x37e24cf0) and left BL31 validation
UNKNOWN (exact aquaman BL31 absent, reference handler not isolated).

## 1. artifact inventory (01)

| artifact | class | note |
|---|---|---|
| bootloader.img (0x148200) | EXACT AQUAMAN image | encrypted at rest; TOC frag at 0x4bebe, no FIP ToC magic (01 00 64 AA absent), no plaintext BL31/AMLSECU/FIP/AMLOGIC |
| boot.img (0x1000000) | EXACT AQUAMAN image | AMLSECU! 0x0905 container at 0x800 (ts 2022090612544443; kernel nRaw 0x9589d1/nTotal 0x959000; dtb nRaw 0xe820); payloads encrypted |
| recovery.img (0x1800000) | EXACT AQUAMAN image | same container shape (ts 2022090613082318 + ramdisk block); payloads encrypted |
| dt.img (0xe820) | EXACT AQUAMAN image | encrypted at rest; no FDT magic, no AMLSECU magic |
| artifacts/aquaman.dtb | EXACT AQUAMAN runtime | decrypted runtime DTB from 0x01000000 (sha b00adab...); secmon/secos/psci/partitions nodes |
| bl33-37e18000.bin (0x1d8000) | EXACT AQUAMAN BL33 | DRAM copy 0x37e18000..0x37ff0000 (sha 664fb34a...); SMC caller side only |
| gxl/bl31.bin (0x2c3a8), gxb/bl31.bin (0x16120) + .img wrappers | FAMILY GXL/GXB | reference only; AMLSECU present, no 0x820000ff word, no smc #0, 2 eret each |
| bl31_apis.h, cmd_rsvmem.c | GENERIC/FAMILY | caller-side constants + rsvmem source; not BL31 behavior |

No EXACT AQUAMAN BL31 binary, dump, symbol, map, or objdump exists in the repo.
The at-rest BL31 (inside bootloader.img FIP) is encrypted; the runtime BL31 was
never captured to a file. TOC/FIP ASCII hits inside boot.img/recovery.img
payloads (0x2cd2a4/0x882cf4, 0xadf7f0/0x1ee212) have no FIP ToC magic and differ
between the two images: coincidental ciphertext bytes, not containers.

## 2. BL33 handoff (02)

BL33 contains no BL31 image/header parser, loader, load address, entry point,
relocation, or magic. What it contains is the resident-world protocol:

- rsvmem strings (0x37ed40d6..0x37ed4804): bl31/bl32 start/size prints, fdt get/set
  command templates for /reserved-memory/linux,secmon (reg/size/alloc-ranges),
  /secmon reserve_mem_size, /reserved-memory/linux,secos (status/reg), clear_range.
- source match: .src/u-boot-khadas/common/cmd_rsvmem.c. do_rsvmem_check reads
  P_AO_SEC_GP_CFG3 (sizes) + CFG5/CFG4 (starts), gets fdtaddr env, checks
  linux,secmon compatible (shared-dma-pool vs amlogic, aml_secmon_memory), then
  patches the DTB via run_command "fdt set ...". do_rsvmem_dump prints the four
  values. BL33 therefore learns the BL31 location from HW registers, not from a
  header, and publishes it to the kernel via DTB.
- sharemem bases come from BL31 at runtime via SMC 0x82000020/0x82000021
  (get_sharemem_info), consumed by the efuse path; no static address exists.
- DTB address: fdtaddr/dtb_mem_addr default 0x1000000 (env + `store dtb read` strings).

So: BL31 is resident before BL33 runs (loaded by BL2 from the eMMC FIP), and the
only BL33->DTB pointers to it are the patched reserved-memory properties.

## 3. DTB secure memory (03, runtime blob)

| property | address/range | meaning | evidence | confidence |
|---|---|---|---|---|
| linux,usable-memory | [0x100000,0x40000000) | DRAM usable to kernel | memory@00000000 node, verbatim | HIGH |
| linux,secmon alloc-ranges/size | [0x5000000,0x5400000), 4 MiB | secmon CMA window, /secmon memory-region target (phandle 0xf) | reserved-memory/linux,secmon + /secmon nodes, verbatim | HIGH as values; MEDIUM as BL31 location (CMA, reusable, kernel-reused after boot) |
| /secmon reserve_mem_size | 0x300000 (3 MiB) | BL31-reported reserve size | /secmon node, verbatim | HIGH as value; mismatch vs 4 MiB size noted, not resolved |
| linux,secos reg | [0x5300000,0x7300000), 32 MiB, no-map, status=disable | BL32 slot (overlaps secmon window tail) | reserved-memory/linux,secos, verbatim | HIGH as values; LOW as live content (disabled) |
| memreserve map | empty | no static bootloader reservations in this blob | FDT header parse | HIGH |
| /psci method=smc, compatible arm,psci-0.2 | n/a (call convention) | EL3 entered via SMC, not via a DTB address | /psci node | HIGH |
| /partitions/tee size 0x2000000 | eMMC, not RAM | secure OS partition (OP-TEE), not BL31 | /partitions/tee | HIGH (and: not a BL31 source) |
| SMC ids in DTB | 0x82000020/21 (secmon), 0x82000060-68/6a-6c (securitykey), 0x82000030/31/33 (efuse), 0x82000044 (cpuinfo), 0x84000009/08 (reboot) | corroborate the BL33 id census; 0x820000ff appears in neither DTB nor as a literal in any image | nodes verbatim + word census | HIGH |
| BL31 code address/entry/magic in DTB | absent | DTB carries ranges + ids only | full node dump | HIGH (absence) |

No reserved-memory marking is interpreted as BL31 beyond the secmon/secos ranges
above, and even those are ranges, not code proof.

## 4. RAM candidates (04, read-only plan, no live read this round)

| candidate | location | source | evidence | exact-aquaman | confidence |
|---|---|---|---|---|---|
| C1 secmon window | 0x5000000 len 0x400000 (0x300000 per reserve_mem_size) | runtime DTB + rsvmem CMA path | alloc-ranges + fdt set templates | range exact, content unproven | MEDIUM/LOW |
| C2 secos slot | 0x5300000 len 0x2000000 | runtime DTB (disabled) | reg + rsvmem BL32 path | range exact, content unproven | LOW |
| C3 sharemem in/out | runtime SMC 0x82000020/21 bases | BL33 efuse callers | get_sharemem_info flow | exact only if read live | LOW |
| C4 DTB @0x1000000 | calibration only, not BL31 | env + store strings + blob | known-good pointer | YES (DTB itself) | HIGH/NIL |
| C5 below 0x800000 | FORBIDDEN (round-14 floor) | prior instruction | BootROM/FIP risk | n/a | forbidden |

Strong-candidate bar (code, not strings alone): AArch64 density, vectors + eret,
PSCI/opteed strings, SMC table with 0x820000ff, SCR_EL3/SPSR_EL3/ELR_EL3/VBAR_EL3
traffic, AMLSECU/secureboot linkage. 64 KiB probes first, full interval only on a
strong hit. Nothing was probed or saved this round.

## 5. eMMC candidates (05, read-only, no dump this round)

- boot0/boot1 hw partitions <- bootloader.img (FIP with BL2/BL30/BL31/BL33 at rest,
  encrypted): the only eMMC region that can contain the exact BL31. Not dumped:
  ciphertext at rest answers nothing about the SMC handler; only a live mapping does.
- user-area GPT (DTB /partitions, 17 entries) + BL33 store/mmc/amlmmc/gpt vocabulary
  (mmc dev/part, amlmmc switch boot0/boot1/user, bootloader-boot0/1 table names):
  tee partition (0x2000000) is the secure OS, not BL31; dt/logo/misc/param have no
  BL31 evidence.
- mmc read is the demonstrated eMMC->RAM path, but using it is execution: out of
  scope for this round by section 9.

## 6. headers/containers + dispatcher (06)

Magic census (offset or absent): bootloader.img AMLSECU/FIP/FDT absent, TOC frag
0x4bebe only; boot/recovery.img AMLSECU! at 0x800, ANDROID! at 0x0, no FDT magic,
no FIP magic; dt.img all-absent (ciphertext head ef8996bd...); BL33 AMLSECU! at
0xaeaf6 = imgread-side string, ANDROID!/AMLOGIC = format strings, no FDT magic
(expected: 0x1000000 holds the DTB, not BL33); gxl BL31 AMLSECU! at 0x2587c;
runtime DTB FDT magic at 0x0. No magic was called BL31 without code corroboration.

Reference BL31 (comparative only): 0x820000ff words 0, smc #0 words 0 (it receives),
eret 2, in both gxl and gxb. AMLSECU/secureboot code present (RSA-key fail,
module v0.3/v0.4, flash/storage size errors, DMA SHA2/AES length errors on gxb),
dispatcher table-driven with no isolated 0x820000ff compare and no call edge into
that code. Neighbor checks stay unlinked and are not cited as handler validation.

## 7. result

```text
candidate | location | source | evidence | exact-aquaman | confidence
C1 secmon window | 0x5000000/0x400000 | runtime DTB + rsvmem | alloc-ranges, fdt set | range exact | MEDIUM/LOW
C2 secos slot | 0x5300000/0x2000000 | runtime DTB (disable) | reg, BL32 path | range exact | LOW
C3 sharemem | SMC 0x82000020/21 live | BL33 efuse callers | sharemem flow | live-only | LOW
eMMC boot0/boot1 | FIP at rest | bootloader.img | TOC frag, encrypted | at-rest exact, unreadable | MEDIUM as container, NIL as code
eMMC tee | user GPT 0x2000000 | DTB partitions | pname/size | NO (secure OS) | HIGH as non-BL31
```

```text
BL31 exact image found      NO (at-rest copy encrypted in bootloader.img FIP; no plaintext in repo)
BL31 runtime copy found     NO (ranges located, no live read this round)
SMC dispatcher found        NO (reference table-driven, handler not isolated; exact absent)
0x820000ff handler found    NO
AML_DATA_PROCESS checks     UNKNOWN (no exact handler to examine; reference unlinked)
```

```text
E3 = UNKNOWN
```

BL33 validation stays ABSENT (round 17, site 0x37e24cf0, HIGH); BL31 validation
stays UNKNOWN by rule: no generic-BL31 inference was used as a substitute. The
round removes the structural uncertainty it could remove offline (where the exact
BL31 lives at rest, how BL33 learns its range, which DTB ranges are real, which
eMMC regions are worth probing, what a strong candidate must show) and leaves the
one question only a live read-only probe can answer: the bytes at C1 (then C2/C3).
