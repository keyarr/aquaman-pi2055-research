# BL33 offline, round 10: the 256 KiB window is U-Boot, matched on secure storage

> **refined by `reports/bl33-offline-round11.md`.** §5's relocation question is
> answered: there is no second copy in the dump and no `0x40000` delta. the
> window is the middle of a `0x01000000`-based load copy, and the §9 model line
> "0x01040000 is the base/entrypoint" becomes "base is 0x01000000, the window is
> at +0x40000". every measurement in this file stands.

date: 2026-09-29, round 10. offline only. no usb, no device, no write, no 0x05,
no eMMC, no reset. the input is the round 8 dump that was already on disk and was
not re-read.

headline: **the 256 KiB at `0x01040000..0x0107ffff` is not "a C library blob"
anymore. it matches `drivers/securestorage/securestorage.c` from the khadas
U-Boot tree function for function, and every SMC id it materialises is an id
from `bl31_apis.h`.** that is the first real code anchor for BL33 in this
research. it is still not a base address, still not proven to be the whole of
BL33, and it does not touch the secure boot blocker.

three things this round retracts outright, they are corrected in
`bl33-offline-round8.md` and not left to coexist:

| round 8 claim | status |
|---|---|
| "second copy of the whole tree" at `+0x80000` | **REFUTED.** one FDT in 16 MiB, `d00dfeed` occurs once, and `0x01080000` is `AML_RES!`. already retracted in round 9, now marked in round 8 too |
| "SMC sites, 11 in total" | **REFUTED**. the opcode constant was wrong. 5 real in the code window, 4 real `svc #0` in the kernel, 16 words matched |
| `0x01040000..0x01080000` "ARM64 code, unidentified", "if it is a C library it should be matchable against something" | **OBSOLETE**, matched |
| "the kernel in RAM is the device's own stock kernel" | **REFUTED as worded.** the banner is `-dirty`, so the build tree was modified |
| "BL33 base candidate = none" | **OBSOLETE**, there is a fragment |

## 1. what was analysed

```
file      reports/round8-bl33-read/mread_01000000_01000000.bin
size      16777216 bytes
sha256    f5e20c9e7952f73320819a13f474ac35d97882b46fbe0fc9d1d1d8d4830c3361
base      0x01000000
read at   2026-09-29 19:04, device 1b8e:c003, cross checked against AM_REQ_READ_MEM
```

same bytes round 8 pulled. nothing was re-read from the stick, so nothing in
this round depends on the device still being in the same state.

## 2. region map

`reports/round10-bl33-match/02_region_map.txt`. derived from the dump, all
figures reproducible.

| range | size | what | label |
|---|---|---|---|
| `0x01000000..0x0100e3a7` | 58280 | DTB / FDT, `totalsize` from the header itself | PROVEN |
| `0x0100e3a8..0x0100e3ff` | 88 | zero | PROVEN |
| `0x0100e400..0x0100e7ff` | 1024 | high-entropy blob, entropy 7.82, unexplained | NOT IDENTIFIED |
| `0x0100e800..0x0103ffff` | 202752 | stale bitmap pixels, see §7 | INFERRED |
| **`0x01040000..0x0107ffff`** | **262144** | **AArch64 code, secure storage matched** | **STRONG EVIDENCE** |
| `0x01080000..0x01139fff` | 761856 | `AML_RES!` resource image, 8 items | PROVEN |
| `0x0169e000..0x01ffffff` | 9838592 | kernel region | PROVEN |

**do not call `0x0169e000` the kernel start.** it is where the non-zero run
begins at 1 KiB granularity. the first non-zero byte at or after `0x01600000`
is `0x0169e8bb`, and the bytes before that are zero. "kernel region" is the
honest label; the actual load address is not measured by this dump.

`AML_RES!` header at `0x01080008`, `AmlResImgHead_t`: crc `0x3755c7a4`,
version 2, `imgSz` `0xdfb80` (916352), 8 items, align 16, declared end
`0x0115fb80`, last non-zero byte `0x0113906b`. `0x01080000` is
`GXB_IMG_LOAD_ADDR` (`bl31_apis.h:118`), round 8 already had this right.

`d00dfeed` occurs **once** in the whole 16 MiB, at `0x01000000`. there is no
second DTB. round 8 §3.1 said otherwise and is corrected.

## 3. SMC census, and why round 8 got 11

`reports/round10-bl33-match/00_bl33_match.txt`.

round 8's `smc` verb matched `(w & 0xFFE0001F) == 0xD4000000`. that is the
wrong constant. `svc`/`hvc`/`smc` share one encoding, `1101 0100 000 imm16
00opc`, with `opc` in the low 2 bits, so the mask must be compared against
`0xD4000001` (svc), `0xD4000002` (hvc) or `0xD4000003` (smc). matching
`0xD4000000` matches nothing real and picks up data words whose top bits
happen to look like the opcode. every one of the 11 round 8 hits is that.

the correct census, opcode-exact and 4-byte aligned:

| window | count | sites |
|---|---|---|
| candidate window `0x01040000..0x0107ffff` | **5** | `0x0104b5a0`, `0x01073ba0`, `0x01073ba8`, `0x01073bb0`, `0x01074144` |
| kernel region `0x0169e000..0x01ffffff` | **11** | 7 with nonzero immediates (data), **4 real `svc #0`** |
| whole dump | 16 | the union |

the four kernel sites are real instructions and they are Linux syscalls, not
Amlogic:

| address | instruction | x8 syscall number |
|---|---|---|
| `0x01dc7394` | `svc #0` | 169 (`mov x8, #0xa9` at `0x01dc7390`) |
| `0x01dc7644` | `svc #0` | 113 (`mov x8, #0x71`) |
| `0x01dc768c` | `svc #0` | 114 (`mov x8, #0x72`) |
| `0x01dc76c4` | `svc #0` | 139 (`mov x8, #0x8b`) |

each is `mov x8, #nr` / `svc #0` / `ret`, a two-instruction syscall wrapper.
the other seven in that range have immediates like `0x966c` and `0x4537`,
which is not a thing anyone calls, and capstone decodes them but they sit in
data. **no SMC in this dump belongs to `aml_sec_boot_check`, and none belongs
to PSCI.** the kernel banner region has no `psci` call site in the 16 MiB we
have.

## 4. the function matching

this is the actual result. `reports/round10-bl33-match/01_securestorage_trace.txt`.

the reference is `.src/u-boot-khadas/drivers/securestorage/securestorage.c`
(U-Boot 2015.01, Amlogic GXL) and the id table in
`arch/arm/include/asm/arch-gxl/bl31_apis.h:34-82`. that tree is a **family
reference, not this firmware**; a structural match against it is evidence
about the family, and only evidence about the family.

### 4.1 the three stubs

```
0x01073ba0  smc #0    ret      bl31_storage_ops
0x01073ba8  smc #0    ret      bl31_storage_ops2
0x01073bb0  smc #0    ret      bl31_storage_ops3
```

three two-instruction stubs, one supervisor call each, no register
manipulation. that is exactly what `securestorage.c:13-44` compiles to: the
function id goes in `x0` and the other args in `x1`/`x2`, then `smc #0`.

BL callers of each stub, from anywhere in the 16 MiB:

| stub | callers |
|---|---|
| `0x01073ba0` | **11** |
| `0x01073ba8` | 1 |
| `0x01073bb0` | 0 in this dump (one tail-`b` at `0x01073d0c`, which capstone does not count as a `bl`) |

caller counts for every matched function, all callers in-window:

| function | callers |
|---|---|
| `secure_storage_init` `0x01073bb8` | 7 |
| `secure_storage_getbuffer` `0x01073c84` | 2 |
| `bl31_storage_write` / `_read` / `_query` / `_status` / `_tell` | 1 each |
| `bl31_storage_verify` `0x01074084` | 0 |
| `secure_storage_set_info` `0x01074138` | 1 |
| `secure_storage_set_enctype` `0x0107414c` | 1 |

every single caller is inside the window. the window holds the storage module
and nothing in it that *uses* storage, which is the first concrete thing to fix
in the next round.

### 4.2 `secure_storage_init` at `0x01073bb8`

`stp x29, x30, [sp, #-0x30]!` prologue, then four ids in source order, each
result stored to a distinct global via `adrp`/`add`:

```
0x01073bc0  movz x0, #0x23 / movk x0, #0x8200, lsl #16   0x01073bd0  bl 0x01073ba0   -> 0x82000023
0x01073be4  movz x0, #0x24 / movk ...                     0x01073bec  bl 0x01073ba0   -> 0x82000024
0x01073c00  movz x0, #0x25 / movk ...                     0x01073c08  bl 0x01073ba0   -> 0x82000025
0x01073c1c  movz x0, #0x27 / movk ...                     0x01073c24  bl 0x01073ba0   -> 0x82000027
```

against `securestorage.c:195-206`:

| id | name (`bl31_apis.h`) | source |
|---|---|---|
| `0x82000023` | `GET_SHARE_STORAGE_IN_BASE` | :198 |
| `0x82000024` | `GET_SHARE_STORAGE_OUT_BASE` | :200 |
| `0x82000025` | `GET_SHARE_STORAGE_BLOCK_BASE` | :202 |
| `0x82000027` | `GET_SHARE_STORAGE_BLOCK_SIZE` | :204 |

**four for four, same order, same function.** that is the strongest single
match in the window.

### 4.3 the secure-storage wrappers

| id | name | movz site | wrapper | source |
|---|---|---|---|---|
| `0x82000062` | `SECURITY_KEY_WRITE` | `0x01073da8` | `0x01073d10` | :61 |
| `0x82000061` | `SECURITY_KEY_READ` | `0x01073e54` | `0x01073dc8` | :78 |
| `0x82000060` | `SECURITY_KEY_QUERY` | `0x01073f14` | `0x01073e98` | :99 |
| `0x82000065` | `SECURITY_KEY_STATUS` | `0x01073fb8` | `0x01073f3c` | :117 |
| `0x82000063` | `SECURITY_KEY_TELL` | `0x0107405c` | `0x01073fe0` | :134 |
| `0x82000064` | `SECURITY_KEY_VERIFY` | `0x01074100` | `0x01074084` | :152 |
| `0x82000069` | `SECURITY_KEY_NOTIFY_EX` | `0x01073d04` | `0x01073c84` | :225 |
| `0x8200006a` | `SECURITY_KEY_SET_ENCTYPE` | `0x01074158` | `0x0107414c` | :326 |
| `0x82000028` | `SET_STORAGE_INFO` | `0x0107413c` | `0x01074138` | :311 |

`0x01073c84` also re-issues `GET_SHARE_STORAGE_BLOCK_SIZE` before the notify,
which is what `secure_storage_getbuffer` at :208-217 does. `0x01074138` inlines
its own `smc #0` instead of calling a stub, one instruction, and it is the only
`smc` in the window outside the three stubs.

ids that are **absent**: `0x82000026` `MESSAGE_BASE`, `0x82000066` `NOTIFY`,
`0x82000067` `LIST`, `0x82000068` `REMOVE`, `0x8200006b` `GET_ENCTYPE`,
`0x8200006c` `VERSION`. that is consistent with a linker dropping unused
static functions and, for the non-static ones, with this firmware simply not
using them. **it is not evidence that the vendor build is smaller**, do not
read a size into it.

`AML_DATA_PROCESS` (`0x820000ff`) is built nowhere in the dump, same as round
8 found. `bl31_apis.c` builds it with a `movz`/`movk` pair too, so this search
method would have found it. **this is a real negative result now**, unlike
round 8's, because round 8 searched for a packed literal.

### 4.4 what the round 8 "no strings" observation actually meant

round 8 rejected this window as "not U-Boot" partly because 256 KiB of it has
no printable rodata. that reasoning does not survive contact with the source:
the ids are `movz`/`movk` immediates, not strings, and `securestorage.c`
itself contains no string literals. the absence of rodata is a **property of
the matched code**, not evidence against it. the `adrp`/`add` pairs in the
window point at pages inside `0x01080000..0x010d0000`, which is where the
resource image and then zeros sit — the string data this window's code refers
to is not in the 16 MiB we have.

### 4.5 `0x0104b5a0`, the fifth supervisor call

not secure storage. `mov w0, #0x16` / `movk w0, #0xb200, lsl #16` / `smc #0`,
so a 32-bit id `0xb2000016`, with `w1` carrying a value the function just
parsed out of a string, digit by digit, `-` and `a`/`f` aware. that is a
hex-value setter of some kind. `0xb20000xx` is not in the khadas
`bl31_apis.h`. **unidentified, recorded so it is not re-found later.**

## 5. the relocation question, still open

round 8 could not tell link address from relocated copy and had no anchor. now
there is one problem and one hint.

**the problem:** 1567 `BL` instructions in the window land outside it. by
bucket: `0x01090000..` 1208, `0x01080000..` 118, `0x01000000..` 201,
`0x01010000..` 40. `0x01090000` is inside the DTB/resource area, so most of
them are calls into whatever used to be there.

**the hint:** subtracting a constant from those out-of-window targets maps
1326 of 1567 back inside the window. `tools/bl33_match.py` reports the
achieving range as `0x01b010..0x0494e0`, 47413 values, so the count does not
pick a unique delta. **`0x40000` is inside that range and is the natural
candidate** (the window is exactly 256 KiB below `0x01080000`), but it is
**NOT PROVEN** and the report does not claim it.

what would settle it: `gd->reloc_off` shows up in `cmd_tbl` name pointers
after `CONFIG_NEEDS_MANUAL_RELOC` (`cmd_bootm.c:97-110`, `board_r.c:892`). no
`cmd_tbl` is visible in this window yet. that is the thing to look for.

## 6. what this does not change

- **secure boot is untouched.** `aml_sec_boot_check` is `x0 = AML_DATA_PROCESS
  (0x820000ff)`, and that id is not in this dump. the flow
  `fastboot boot -> bootm -> aml_sec_boot_check -> SMC -> BL31` is unchanged
  and still blocking. finding BL33 does not bypass anything.
- **no key was found.** `secure_storage_*` is the *interface*, not the key.
  `amlsecu-key-path.md` already says the plaintext key never appears in
  U-Boot; nothing here contradicts it and nothing here supports unlocking
  BL31.
- **`0x01040000` is not proven to be the base or the entrypoint.** it is
  proven to contain code that calls the Amlogic secure-storage API.
- **the whole of BL33 is not proven to be present.** 256 KiB is a fragment.
  U-Boot 2015.01 GXL with fastboot, optimus and vendor commands does not fit
  in 256 KiB of text.
- **the `download != boot source` hypothesis stays dead.**
  `fastboot-memory-flow.md` §8 refuted it on device; nothing here revives it.

## 7. an extra: a stale resource-image copy below the window

`0x01010000..0x0102bfff` is **byte identical** to `0x01090000..0x010abfff`,
114688 bytes, zero differences. `0x01090000` is `GXB_IMG_LOAD_ADDR + 0x10000`,
so the implied staging base for that copy is `0x01010000 - 0x10000 =
0x01000000`, exactly where the FDT now is.

separately, `0x0100e400..0x0100e7ff` is 1024 bytes at entropy 7.82, sitting
immediately above the FDT's `totalsize` end. **not identified.** one KiB of
high-entropy bytes adjacent to a device tree is worth keeping an eye on, but
one KiB is not a finding and no claim is made about it.

**INFERRED:** the resource image was staged at `0x01000000` at some earlier
point and later at `0x01080000`, and other things were written over the older
copy. **NOT PROVEN** — no ordering, no proof of which load wrote what, and it
does not matter for the secure boot question either way.

on the "second copy of the tree": there is **one** FDT in this dump.
`d00dfeed` occurs once. the bytes at `0x01082000..0x0108e3a7` do happen to
equal the bytes at `0x01002000..0x0100e3a7` — the struct block from `+0x1fc8`
onward, and the whole 6404-byte strings block, are byte-identical, which
`aquaman-dtb-extraction.md` §3 measured and documented — but that is leftover
DTB data sitting under a region that now begins with `AML_RES!`, not a second
tree. `fdtdump` on those 58280 bytes returns `FATAL ERROR: header is not
valid`. **do not describe a second DTB copy.**

## 8. next steps, in order, all offline

the investigation now has a real anchor, so the work is call-graph work, not
string hunting.

starting point:

```
0x01073ba0  bl31_storage_ops       11 callers, all in-window
0x01073ba8  bl31_storage_ops2       1 caller,  in-window
0x01073bb0  bl31_storage_ops3       0 bl callers, 1 tail-b
0x01073bb8  secure_storage_init     7 callers, all in-window
0x01073c84  secure_storage_getbuffer 2 callers
0x01073d10  bl31_storage_write      1
0x01073dc8  bl31_storage_read       1
0x01073e98  bl31_storage_query      1
0x01073f3c  bl31_storage_status     1
0x01073fe0  bl31_storage_tell       1
0x01074084  bl31_storage_verify     0
0x01074138  secure_storage_set_info 1
0x0107414c  secure_storage_set_enctype 1
```

1. **find the callers of `secure_storage_*` from outside the window.** right
   now every caller is inside it, which means the window holds the storage
   module and nothing that uses it yet. the users are the interesting part:
   `hdcp`, `efusekey`, `unifykey`, `/defendkey` all exist in the recovered DTB
   (`aquaman-dtb-extraction.md` §7).
2. **look for `aml_sec_boot_check` by its shape, not its strings.** the string
   `aml log : Sig Check %d` is still absent from 16 MiB, so it is either in
   another copy of BL33 or on a rodata page we do not have. `aml_sec_boot_check`
   is the one SMC site whose `x0` is built with a 16-bit `movk` of `0x8200`
   and whose `imm` is `0x7`, per `bl31_apis.h:118-123`.
3. **search for `0x820000ff` built by any instruction pair**, not just
   `movz`+`movk`. `tools/bl33_match.py` covers `movz`/`movk`; `orr`/`movn`
   variants are not covered.
4. **look for `cmd_tbl`** to get `gd->reloc_off`, §5.
5. **constants to grep for as raw literals**, they will appear in whatever
   copies we find next: `0x01080000` (`GXB_IMG_LOAD_ADDR`), `0x01800000`
   (`GXB_IMG_SIZE`), `0x820000ff`, `0x820000ff`'s `AML_D_P_IMG_DECRYPT = 0x40`,
   `GXB_IMG_DEC_ALL = 0x7`.
6. **fastboot / OEM handlers, `imgread`, `setenv`/`saveenv`.** all still zero
   hits in 16 MiB, all expected to live outside this window.

do not go below `0x00800000`: round 6 proved `0x00000000` drops the device off
the bus and recovery is a power cycle.

## 9. model, updated

```text
BL33/U-Boot candidate fragment   0x01040000..0x0107ffff
secure-storage function matching STRONG, 9 ids + 4 share-storage ids
whole window decodes as AArch64   65535 / 65536 slots
BL33 complete                     NOT PROVEN
0x01040000 is the base/entrypoint NOT PROVEN, and 0x820000ff is not here
relocation delta                  hint only, 47413 candidates, NOT PROVEN
secure boot bypass                NOT DEMONSTRATED, unchanged
```

before: BL33 was a black box and the 256 KiB was "unidentified AArch64".
now: named functions, real SMC ids, and a call graph that can be walked.

## 10. files

- `tools/bl33_match.py`, new, offline. decode rate, opcode-exact supervisor-call
  census over any range, BL callers of each stub, the `movz`+`movk` id search,
  and the relocation-delta check. every number in this report comes out of it.
- `reports/round10-bl33-match/00_bl33_match.txt`, raw tool output.
- `reports/round10-bl33-match/01_securestorage_trace.txt`, the per-instruction
  trace of `0x01073b80..0x01074300` with the resolved id on every stub call.
- `reports/round10-bl33-match/02_region_map.txt`, the region table, the FDT
  header fields, the `AML_RES!` header, kernel-region occupancy and the
  `d00dfeed` count.

nothing was written to the stick. the round 8 dump was read from disk and
still hashes to `f5e20c9e...`.
