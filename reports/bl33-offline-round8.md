# BL33 offline, round 8: 0x01000000 is not U-Boot, it is the kernel's DTB and the logo partition

> **PARTIALLY SUPERSEDED by `reports/bl33-offline-round10.md` (same dump, later
> analysis).** three conclusions in this file are wrong and are corrected in
> place below, marked REFUTED / OBSOLETE:
> - §3.1 "a second copy of the whole tree" at `+0x80000` — **REFUTED**
> - §5 "SMC sites, 11 in total" — **REFUTED**, wrong opcode mask
> - §3.2 "`0x01040000..0x01080000`, ARM64 code, unidentified" — **OBSOLETE**,
>   it matched U-Boot secure storage
> - §7 "BL33 base candidate = none" — **OBSOLETE**, there is now a fragment
> The read itself, its hash and the DTB finding all stand.

date: 2026-09-29, round 8. read only, no write, no 0x05, no eMMC, no reset, no
ghostlock, no bootrom, nothing below 0x00800000. the stick was already sitting in
fastboot (`18d1:0d02`), so the session was `fastboot oem update 5000` and nothing
else. 16 MiB came out, all of it is on disk this time.

headline: **`CONFIG_SYS_TEXT_BASE = 0x01000000` is refuted for this board, and
BL33 is not in 0x01000000..0x02000000 at all.** the first four bytes at that
address are `d0 0d fe ed`, the FDT magic. it is a device tree, and the device
tree says `gxl_aquaman_1g`. 16 MiB later there is the running Linux kernel, not
a bootloader. zero of 11 target strings from the brief are present.

## 1. what the read produced

session log `reports/round8-bl33-read/00_session.txt`. entry to
`1b8e:c003` took **186 ms** after `fastboot oem update 5000` (482.087 -> 482.475),
in line with the 370-490 ms of round 3.

| item | value |
|---|---|
| identify | `00 07 00 10`, version 0.7, **stage 16 (TPL/BL33-u-boot)** |
| address | `0x01000000` |
| size asked | `0x01000000` (16777216) |
| size on file | 16777216, exact |
| chunks | 256 upload transfers of 64 KiB |
| time | 1.095 s |
| throughput | 14.61 MiB/s |
| **sha256** | `f5e20c9e7952f73320819a13f474ac35d97882b46fbe0fc9d1d1d8d4830c3361` |
| file | `reports/round8-bl33-read/mread_01000000_01000000.bin` |

ladder, same session, all four steps `0x02` cross-checked byte for byte:

| step | bytes | transfers | sha256 | 0x02 cross-check |
|---|---|---|---|---|
| `0x02` direct | 64 | 1 ctrl | `7b095e976b615a25…` | n/a, is the reference |
| mread `0x200` | 512 | 1 | `14066b8b113927b9…` | **MATCH**, 8 reads |
| mread `0x1000` | 4096 | 1 | `1809328aa1f729df…` | **MATCH**, 64 reads |
| mread `0x10000` | 65536 | 1 | `083968ca586ada44…` | **MATCH**, 1024 reads |
| mread `0x1000000` | 16777216 | 256 | `f5e20c9e7952f733…` | **MATCH** on the first 64 |

the three small reads are exact byte prefixes of the big one, which is what makes
the 16 MiB trustworthy: `0x200` and `0x1000` and `0x10000` were taken in the same
burning window as the dump and they agree. gadget alive after every step,
`identify=00 07 00 10`, and `1b8e:c003` still enumerated when the session ended.

**0x01000000 is mapped and readable.** no unmapped result, no adaptive scan, no
other low address tried.

## 2. the first 64 bytes kill the hypothesis

```
01000000  d0 0d fe ed 00 00 e3 a8 00 00 00 38 00 00 ca a4  |...........8....|
01000010  00 00 00 28 00 00 00 11 00 00 00 10 00 00 00 00  |...(............|
01000020  00 00 19 04 00 00 ca 6c 00 00 00 00 00 00 00 00  |.......l........|
01000030  00 00 00 00 00 00 00 00 00 00 00 01 00 00 00 00  |................|
01000040  00 00 00 03 00 00 00 08 00 00 00 00 41 6d 6c 6f  |............Amlo|
01000050  67 69 63 00 00 00 00 03 00 00 00 0f 00 00 00 06  |gic.............|
01000060  67 78 6c 5f 61 71 75 61 6d 61 6e 5f 31 67 00 00  |gxl_aquaman_1g..|
```

`d00dfeed` is the flattened device tree magic, big-endian `0xd00dfeed`. parsed as
an FDT header, big-endian, it is entirely self-consistent:

| field | value | check |
|---|---|---|
| magic | `d00dfeed` | ok |
| totalsize | 58280 (0xe3a8) | spans 0x01000000..0x0100e3a7 |
| off_dt_struct | 0x38 | ok |
| off_dt_strings | 0xcaa4 | ok |
| off_mem_rsvmap | 0x28 | ok |
| version / last_comp_version | 17 / 16 | ok, v17 last is v16 |
| size_dt_strings / size_dt_struct | 0x1904 / 0xca6c | ok |

and the strings are the aquaman's own device tree: `gxl_aquaman_1g`,
`amlogic, Gxl`, `mali@d00c0000`, `arm,mali-450`, `io_hiu_base`, `cpu_info`,
`/thermal-zones/soc_thermal/trips/trip-point@0..3`, `tx_hpd`, `aocec`,
`MBox Meson Ref`. `Amlogic` appears 3 times, at 0x0100004c, 0x01008a44 and
0x01088a44.

this is the strongest single result of the round and it is a negative one.
round 7 §3.2 derived 0x01000000 from `CONFIG_SYS_TEXT_BASE 0x01000000 /*16MB
rsv*/` in the khadas tree and called it DERIVED, medium, unmeasured. it is now
measured, and on the aquaman that address holds a DTB. the `/*16MB rsv*/` comment
in the reference tree means "16 MiB reserved", i.e. the region 0x00000000..0x00ffffff,
not "U-Boot is linked at 0x01000000". round 7 read the comment as a base address.
it is not one.

## 3. what the 16 MiB actually contains

`reports/round8-bl33-read/01_regions.txt`, from the new `regions` verb. four
occupied runs, 11063296 of 16777216 bytes (65.9%) non-zero.

### 3.1 0x01000000..0x01080fff, 528 KiB: the device tree

> **REFUTED, see `bl33-offline-round10.md` §7.** the claim in this subsection
> that there is a second copy of the tree at `+0x80000` is wrong. `d00dfeed`
> occurs **once** in the whole 16 MiB. `0x01080000` is an `AML_RES!` resource
> image, and `0x01010000..0x0102bfff` is a stale byte-identical copy of part of
> that same resource image from an earlier staging at `0x01000000`. the string
> collision that produced this claim was one duplicated path name, which is not
> a copy. `aquaman-dtb-extraction.md` §3 already retracted it; this file had
> not been updated.

FDT totalsize is 58280, ending at 0x0100e3a7, but the run continues to 0x01080fff.
one DTB, staged at `CONFIG_DTB_MEM_ADDR 0x1000000`, with the run beyond
`totalsize` belonging to something else entirely.

### 3.2 0x01040000..0x0107ffff, 256 KiB: ARM64 code, unidentified

> **OBSOLETE.** this region was matched in `bl33-offline-round10.md` §4 against
> `drivers/securestorage/securestorage.c` from the khadas U-Boot tree:
> `bl31_storage_ops*`, `secure_storage_init`, the six `bl31_storage_*` wrappers
> and `secure_storage_set_info`/`_set_enctype`, with 13 distinct BL31 ids
> materialised by `movz`/`movk`. it is a U-Boot/Amlogic fragment.
>
> the measurements below stand. the reasoning that rejected it does not: the
> "no strings" argument is void, because `securestorage.c` has no string
> literals and its ids are immediates, not strings. the `strtod`-shaped parser
> at `0x01040200` and the hex parser at `0x0104b568` are both real U-Boot code,
> they are just not in this one source file. the "khadas has no `strtod`"
> argument was reasoning from a sibling file's contents, which proves nothing
> about a different file.

this is the one region I cannot name, and it is the only thing in this dump that
could still be bootloader code.

evidence it is code and not data:

| test | 0x01040000..0x01080000 | 0x016a0000 (kernel text) | 0x01010000 (dtb) |
|---|---|---|---|
| capstone ARM64 linear decode | **100.0%** (65535/65536) | 100.0% | 48.5% |
| entropy per 64K | 6.31 / 6.33 / 6.41 / 6.33 | 6.5-6.7 | 1.33 |
| `stp x29,x30,[sp,#-N]!` | 818 in 65536 slots | thousands | 0 |
| `nop` / `ret` per 64K | 0 / 309, 0 / 192, 0 / 190, 0 / 278 | hundreds each | 0 / 0 |
| BL targets inside itself | 3922 of 5489 | yes | no |
| `brk` | **0** | 0 | 0 |

the 100% decode rate is the discriminator. random or encrypted bytes decode to
`udf #0` in a few percent of slots, the DTB gets 48.5%, real compiled AArch64
gets 100%. 256 KiB of it, with proper prologues and 3922 internal calls.

evidence it is **not** U-Boot (**this reasoning is REFUTED, kept for the record**):

- **no strings.** 214 printable runs of 5+ chars in 256 KiB, and every one of
  them is instruction bytes that happen to land in the printable range
  (`` `h!8! ``, `T`bja8`, `aFP9`BP9 `). there is no `U-Boot`, no `2015.01`, no
  `bootm`, no format string, no `printf` literal. a 256 KiB slice of U-Boot 2015.01
  without a single rodata string is not a thing.
- **zero `brk` (0xd4200000)** in the whole region. U-Boot's `PANIC`/`hang` and
  every `printf` path use `brk #N` for the debug register, round 7 §2 already
  used "0 brk in 1 MiB" to reject the java heap. same test, same verdict here.
- the 0.0169e000 kernel run also has 0 brk, so this test separates U-Boot from
  *other code*, not code from data. it is the missing strings that reject it.

**why all three fail.** `brk` is a debug-register convention, absent from any
`-O2` build of this vintage; the 4.9 kernel in the same dump has zero too.
absence of `brk` therefore says nothing about provenance. absence of rodata is
expected when the window holds one translation unit's text and the strings live
on pages outside the dump. and the "khadas has no `strtod`" argument compared
one source file against another file's code, which cannot work: U-Boot 2015.01
GXL has a libc, and `securestorage.c` compiling into a window with no strings
is completely normal.

what it looks like instead (**REFUTED**): a big C library blob. `0x01040200` is a `strtod`-shaped
parser, it walks the format string looking for `0x2d` ('-') then `0x61` ('a') or
`0x66` ('f') and sets `w22 = 0xa` for the hex-float case. `0x010413c8`, the
hottest call target in the region at 1772 call sites, allocates `sp - 0x320` and
saves x0-x7 plus q0-q7, that is a varargs collector. the khadas tree has no
`strtod`, so this is not that u-boot either.

the 1567 BL calls that leave the region do **not** all land in the DTB
(**REFUTED**, the bucket counts were not taken in this round). measured by
`tools/bl33_match.py`: `0x01090000..` 1208, `0x01080000..` 118, `0x01000000..`
201, `0x01010000..` 40. the `0x01090000` majority lands inside the resource
image and the DTB-copy area, i.e. where the code's data used to be, which is a
relocation signature rather than a "linked against the wrong table" one. see
`bl33-offline-round10.md` §5, and note that the delta is **NOT PROVEN** there.

### 3.3 0x01080000..0x01139fff: the logo / upgrade resource image

`a4c7 5537` then `AML_RES!` at +8, which is
`AmlResImgHead_t` from `common/cmd_imgread.c:307`:

| field | value |
|---|---|
| crc | `0x3755c7a4` |
| version | 2 (`AML_RES_IMG_VERSION_V2`) |
| magic | `AML_RES!` |
| imgSz | 0xdfb80 (916352) |
| imgItemNum | 8 |
| alignSz | 16 |

the 8 items walk cleanly via the `next` chain, `AmlResItemHead_t` from
`cmd_imgread.c:392`, all `magic=0x27051956`, all `nums=8` (AArch64):

| # | offset | name | size | data at |
|---|---|---|---|---|
| 0 | 0x40 | `upgrade_success` | 0x2bf68 | 0x240 |
| 1 | 0x80 | `bootup` | 0x3a8f | 0x2c1b0 |
| 2 | 0xc0 | `upgrade_error` | 0x2bf68 | 0x2fc40 |
| 3 | 0x100 | `upgrade_fail` | 0x2bf68 | 0x5bbb0 |
| 4 | 0x140 | `upgrade_upgrading` | 0x2bf68 | 0x87b20 |
| 5 | 0x180 | `upgrade_bar` | 0xb8 | 0xb3a90 |
| 6 | 0x1c0 | `upgrade_logo` | 0x2bf68 | 0xb3b50 |
| 7 | 0x200 | `upgrade_unfocus` | 0xb8 | 0xdfac0 |

`0x2bf68` is 180 KB of raw bitmap, five of them, these are the boot and upgrade
screens. `upgrade_success` at data offset 0x240 is where the rest of the
0x01010000..0x01080fff run lives too.

**this is the single most useful discovery of the round and it is not about
U-Boot at all: `0x01080000` is `GXB_IMG_LOAD_ADDR`.** `bl31_apis.h:118` puts
`GXB_IMG_LOAD_ADDR` at `0x1080000`, and 0x01080000 is exactly that address.
the 24 MiB window `GXB_IMG_SIZE = 24<<20` runs 0x01080000..0x0287ffff, and the
first 916352 bytes of it are currently holding the resource image. round 7 §3.4
predicted this address from the tree; it is now measured, and it is occupied.

### 3.4 0x01392000..0x013e7fff, 344 KiB: an unidentifiable table

entropy 0.28, 85021 of 87040 words are zero, and the non-zero ones repeat
`0x1e221c1e / 0x1c1e221c / 0x221c1e22` in a 3-cycle, 844 and 817 and 756
occurrences. zero `ret`, zero `nop`, zero `brk`, zero BL, and **not** decodable as
code. looks like a sparse table with a fixed 12-byte pattern, possibly a
pixel-format or stride descriptor. no strings at all. not identified.

### 3.5 0x0169e000..0x01ffffff, 9.4 MiB: the running Linux kernel

| evidence | value |
|---|---|
| banner at 0x01dc0080 | `Linux version 4.9.113-g963f962d046a-dirty (jenkins@c5-mitv-cm-build06.bj) (gcc version 6.3.1 20170109 (Linaro GCC 6.3-2017.02) )` |
| banner template at 0x01dc0010 | `%s version %s (jenkins@c5-mitv-cm-build06.bj) (gcc version 6.3.1 20170109 (Linaro GCC 6.3-2017.02) ) %s` |
| `nop` sleds | 51827, incl. 510/461/279/339/363 per 64K from 0x016a0000 |
| `ret` | 29782 |
| tracepoint docs at 0x01dd5xxx | `set_ftrace_filter`, `traceoff:3`, `events/block/block_unplug/trigger` |
| ctype tables at 0x01df0230 | the toupper/tolower 256-byte ladders, 8 copies |
| `smc` sites | **REFUTED below**, the three listed here were not instructions |

the 4.9.113 baseline is what this repo has been building all along
(`reports/kernel-baseline.md`), so the kernel in RAM is the device's own
kernel, the one it booted, at 0x0169e000. **do not call it "stock"**: the
banner is `4.9.113-g963f962d046a-dirty`, and `-dirty` means the build tree had
uncommitted modifications. it is the vendor's build of an unknown tree, not a
pristine one.

`0x0169e000` is the start of the non-zero run at 1 KiB granularity, **not a
measured load address.** the first non-zero byte at or after `0x01600000` is
`0x0169e8bb`. call it "kernel region".

`boot_unpack/kernel` cannot be compared byte for byte: it is `AMLSECU!`
encrypted (entropy 7.99988 per round 7), 9801728 bytes, no `ARM\x64` magic, no
`Linux version` string. the in-RAM copy is post-decompression and post-relocation,
so a diff is not meaningful and I did not attempt one.

### 3.6 0x01f00000: a pointer table into 0x0008xxxx

113 words pointing into 0x00089cf0..0x0008b760, then continuing at 0x00090020,
0x000900c8, 0x00090180, 0x00090288, 0x00090310, 0x00090370, 0x00090410, 0x000904b0.
monotonically increasing, never repeating. this is a relocation or init array
whose targets are in the **first 0x00100000 of DRAM**, which is the region round 6
proved unmapped from TPL (`18_scan_low.txt`, device left the bus at 0x00000000).
this is a real, useful, unexplained lead and it is the only pointer evidence in
this dump that points outside it.

## 4. the signature search, 0 for 11

the brief's list, searched over all 16777216 bytes:

| string | hits |
|---|---|
| `U-Boot` | **0** |
| `u-boot` | **0** |
| `2015.01` | **0** |
| `g7ac5df7677` | **0** |
| `aml log : Sig Check` | **0** |
| `aml_sec_boot_check` | **0** |
| `Optimus` | **0** |
| `usb_pcd` | **0** |
| `usb_burning` | **0** |
| `set_usb_boot` | **0** |
| `do_bootm` | **0** |

plus, from `bl33_offline.py STRONG` (27 markers): `bootm\0` 0, `fastboot\0` 0,
`setenv\0` 0, `bl33\0` 0, `BL33\0` 0, `BL2\0` 0, `CMD_BUFF_SIZE` 0,
`OPTIMUS_DOWNLOAD` 0, `gd->` 0, `loadaddr=` 0, `dtb_mem_addr=` 0, `boot_delay` 0.
the only STRONG marker that hit at all is `Amlogic`, 3 times, all inside the DTB.

numeric anchors, packed little-endian:

| constant | value | hits in dump | verdict |
|---|---|---|---|
| `GXB_IMG_LOAD_ADDR` | `0x01080000` | 8 | 0x01080000 is an AML_RES image, see §3.3 |
| `AML_DATA_PROCESS` | `0x820000FF` | **0** | this is the `x0` of the SMC. zero hits anywhere in 16 MiB |
| `COUNTER_FREQUENCY` | `0x01800000` | 25 | coincides numerically with `GXB_IMG_SIZE`, both are 24 MiB. not a discriminator |
| `GXB_IMG_SIZE` | `0x01800000` | 25 | same collision |
| `AML_D_P_IMG_DECRYPT` | `0x40` | 975 | 0x40 is a 4-byte-aligned constant, useless alone |
| `GXB_IMG_DEC_ALL` | `0x07` | 573 | same |

`AML_DATA_PROCESS = 0x820000FF` is the one that matters. `bl31_apis.c:255-308`
builds it with a `movz`/`movk` pair into x0 immediately before `smc #0`, so it
would not be stored as a literal word anyway. its absence proves nothing and I am
not counting it as evidence either way.

## 5. `_start`, the SMC sites, and do_bootm

**`_start`: not found.** `bl33_offline.py start` scanned all 16777216 bytes at
64-byte boundaries for `b reset` with a plausible `_TEXT_BASE` quad. one hit,
0x01136240, and it is a false positive: the quad reads `0x202020b` and the
surrounding bytes are `17 28 28 28 0b 0b 17 17`, a repeating pattern inside the
unidentified table of §3.4, not a literal pool. no candidate, no false negative
to argue about: the test found nothing real.

**SMC sites, 11 in total** — **REFUTED, the count and the table are wrong.**

`reports/round8-bl33-read/02_smc.txt` and this subsection both come from a bug
in `tools/bl33_offline.py smc`: it matched `(w & 0xFFE0001F) == 0xD4000000`.
`svc`/`hvc`/`smc` share the encoding `1101 0100 000 imm16 00opc`, so the low two
bits are the opcode and the correct comparison is against `0xD4000001`/`02`/`03`.
`0xD4000000` matches no real instruction, only data words that look like one.
**all 11 entries below are artefacts.** the file is left in place as the record
of the wrong run; the correct census is in
`reports/round10-bl33-match/00_bl33_match.txt`:

| address | imm | where |
|---|---|---|
| 0x01005320 | 0 | DTB |
| 0x010053e8 | 0x1c8 | DTB |
| 0x01009580 | 0 | DTB |
| 0x01009ae4 | 0x6800 | DTB |
| 0x01085320 | 0 | inside `AML_RES!` item 0 |
| 0x010853e8 | 0x1c8 | same, +0x80000 |
| 0x01089580 | 0 | same |
| 0x01089ae4 | 0x6800 | same |
| 0x0178fee0 | 0x23c0 | kernel |
| 0x01e02608 | 0 | kernel |
| 0x01e0454c | 0 | kernel |

what is actually there, opcode-exact and 4-byte aligned:

| range | count | what |
|---|---|---|
| `0x01040000..0x0107ffff` | **5** | `smc #0`, 3 of them the `bl31_storage_ops*` stubs, all matched |
| `0x0169e000..0x01ffffff` | **4 real** | `svc #0` Linux syscall wrappers, `x8` = 169/113/114/139 |
| whole dump | 16 | the 5 above plus the 4 above plus 7 data false positives with nonzero immediates |

**no SMC in this dump belongs to `aml_sec_boot_check`**, and that statement now
rests on the corrected scan rather than on the broken one. `0x820000ff`
(`AML_DATA_PROCESS`) is built with `movz`/`movk` nowhere in the 16 MiB, and the
`movz`+`movk` search does find the 13 secure-storage ids that are there. the
negative is real this time.

**do_bootm: not located.** cannot be, from this dump. the two things that would
anchor it are `aml log : Sig Check %d` and the `0x1080000` literal, and §4 shows
the string is absent while the only `0x1080000` is a resource image. I am not
going to call the 256 KiB blob of §3.2 `do_bootm` on the strength of one
`strtod`-shaped function.

## 6. relocation

> still open, but the shape of the answer changed. round 10 measured that a
> constant delta maps 1326 of the 1567 out-of-window `BL` targets back into
> `0x01040000..0x0107ffff`, which is a relocation signature. **the delta is
> NOT PROVEN**: 47413 different values reach the same count. see
> `bl33-offline-round10.md` §5.

**not determinable from this dump, and here is the reason, which is worth
recording.**

round 7 §6 predicted two copies, one at `CONFIG_SYS_TEXT_BASE` and one at
`gd->relocaddr`. both would carry the `_TEXT_BASE` quad, and the quad test would
find both. that prediction is now falsified in its first half: 0x01000000 is a DTB,
so on this board `CONFIG_SYS_TEXT_BASE` either is not 0x01000000, or U-Boot's
text was never loaded there. either way there is no anchor at 0x01000000 to
compute a `reloc_off` from.

the second half is untestable without the first. distinguishing link address from
relocated copy needs two internally consistent copies to compare; there is one
candidate (§3.2) and it has no partner. §3.6's pointer table at 0x01f00000
points into 0x0008xxxx, which is below every address U-Boot could plausibly be
running from in a flat 1 GiB map with `CONFIG_SYS_TEXT_BASE` at 16 MiB, so if
those pointers are a U-Boot relocation table the U-Boot base would be very low.
that is a hypothesis with one data point and no confirmation, and I am not
promoting it.

## 7. verdict

```text
BL33 base candidate = none. 0x01000000 refuted, it is an FDT.
relocated base       = undetermined, no anchor exists in this dump
do_bootm             = not found
aml_sec_boot_check   = not found
SMC site             = 11 sites, none in an aml_sec_boot_check path
confidence            = high (that it is not here), n/a (where it is)
```

> **§7 verdict is superseded by `bl33-offline-round10.md` §9.** "BL33 base
> candidate = none" is obsolete: there is a U-Boot/Amlogic fragment at
> `0x01040000..0x0107ffff`. "11 sites" is refuted, see §5. "not found at
> 0x02000000" was never tested by this round and remains untested.
>
> what survives: `0x01000000` is an FDT, not U-Boot; `do_bootm` and
> `aml_sec_boot_check` are still not located; no Amlogic SMC in this dump.

high confidence that BL33 is not **at 0x01000000**. the FDT magic, the
zero of eleven target strings, the 9.4 MiB of the device's own 4.9.113 kernel
and the `AML_RES!` container at `GXB_IMG_LOAD_ADDR` are four independent lines
and they all agree. that is a statement about one address, and it does not
imply "not in 0x01000000..0x02000000", which round 10 disproved.

## 8. what was written

- `tools/bl33_read.py`, new. one burning window, probe then dump, every mread
  cross-checked against `0x02`, the 16 MiB written to disk and re-read from disk
  before the sha256 is computed, so the hash describes the file and not the buffer
  that is about to be freed. round 6 lost 64 MiB that way.
- `tools/bl33_offline.py`, two verbs added, `regions` and `smc`. `regions` answers
  "what is in this run", which `classify` per-64K could not, and it prints the
  first bytes and the longest strings of each occupied run. `smc` lists every
  `smc #imm` with the `movz`/`movk` that built x0..x4 in the 12 instructions
  before it. nothing existing was changed.
  **`smc` is broken and was left broken on purpose.** its opcode constant is
  wrong (§5), and `tools/bl33_match.py` supersedes it rather than patching it,
  so the wrong output stays reproducible as evidence of the bug. do not trust
  `bl33_offline.py smc`.
- `tools/optimus_enter.sh`, one line: `OPTIMUS_PY` env so the entry wrapper can
  run a different python. it was still unusable as-is because the stick was in
  fastboot and not Android, `adb reboot fastboot` has nothing to talk to.
- `reports/round8-bl33-read/`, `00_session.txt`, `01_regions.txt`, `02_smc.txt`,
  `03_start_shape.txt`, `04_xref.txt` and the five `.bin`. the `.bin` are
  gitignored, the four logs are not.

## 9. next step, and it is offline first

`0x01000000` did not fail, but it is the wrong address, so the round 8 brief's
§8 rule about not guessing does not directly apply. still, the honest reading of
§8 is: do not scan the whole RAM, do not go below 0x00800000. I did neither.

what the evidence says to try next, in order:

1. **the region above the kernel, 0x02000000..0x03000000.** `GXB_IMG_SIZE` runs
   the bootm window to 0x0287ffff and we only have 16 MiB of it. 16 MiB more at
   the same 14.6 MiB/s is 1.1 s. this is the one continuation the tree already
   argues for, in round 7 §9, and it is a single fixed read, not a scan.
2. **re-examine 0x01040000..0x01080000 offline.** 256 KiB of 100%-decodable
   ARM64 with no strings and no `brk`. if it is a C library it should be
   matchable against something; if it is a stripped or obfuscated build of
   something it will say so under a different analysis. this costs no device
   time and is the only unfinished piece of this round.
   **done, item 2 answered, see `bl33-offline-round10.md` §4: it is U-Boot
   secure storage.**
3. **do not go below 0x00800000.** round 6 proved 0x00000000 drops the device
   off the bus and the recovery is a power cycle. §3.6's pointers into
   0x0008xxxx are interesting precisely because that region has never been read,
   and precisely because reading it wrong costs the stick.

explicitly **not** done this round: `0x05`, any write verb, any `setenv`,
`saveenv`, `flash`, `erase`, `burn`, `reset`, any eMMC access, ghostlock, bootrom,
no address below 0x00800000. the `upload mem` used is the read half of the
burning protocol, `isUpload` keeps `nextWriteBackSlot` at 0 so nothing is written
back (`optimus_buffer_manager.c:149`), which is the same invariant round 6
established.
