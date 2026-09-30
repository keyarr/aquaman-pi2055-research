# BL33 offline, round 11: the 256 KiB is the middle of an 832 KiB image, and the rest of it was overwritten on purpose

date: 2026-09-29, round 11. offline only. no usb, no device, no write, no 0x05,
no eMMC, no reset, nothing below 0x00800000. the stick was not touched at all this
round: the input is the round 8 dump that is already on disk. every figure below
comes from `tools/bl33_refs.py` and the raw output is in
`reports/round11-bl33-refs/`.

headline: **the surviving code at `0x01040000..0x0107ffff` is not a blob, it is
the middle of an image that starts at `0x01000000` and runs to at least
`0x010cbf80`: 811 KiB of referenced footprint, of which exactly 256 KiB
survived.** two thirds of that image was overwritten while the device ran: the
device tree was staged at `0x01000000`, the boot resource image at
`0x01080000`, and the tail was zeroed. `CONFIG_DTB_MEM_ADDR` and
`CONFIG_SYS_TEXT_BASE` are **the same address** in the vendor's own reference
config (`arch/arm/include/asm/arch-gxl/cpu.h:41` and `:57`, both `0x1000000`), so
the clobbering is not a coincidence, it is what Amlogic configured.

this also explains, and for the first time gives a mechanism for, the two things
rounds 8 and 10 could only report as absence: **the missing U-Boot strings and
the missing `aml_sec_boot_check`.** they were not missing, their pages were
stolen.

and one negative is now a real negative: **there is no relocated copy of this
window anywhere in the dump.** round 10 got "47413 candidate deltas" by matching
BL offsets alone. this round matches with ADR/ADRP wildcarded, which is the
correct criterion, and validates the matcher by planting a copy that is provably
there before reporting the zero.

## 1. what was analysed, and re-verification of the read

```
file      reports/round8-bl33-read/mread_01000000_01000000.bin
base      0x01000000
size      16777216 bytes
sha256    f5e20c9e7952f73320819a13f474ac35d97882b46fbe0fc9d1d1d8d4830c3361
read      round 8, 2026-09-29 19:04, device 1b8e:c003, 256 chunks of 64 KiB,
          1.095 s, 14.61 MiB/s
```

the ladder from round 8 was re-checked against the files rather than trusted:
`read02_01000000_64.bin` (the `AM_REQ_READ_MEM` 64-byte read) is byte-identical
to `dump[0:64]`, and `mread_01000000_000200.bin`, `_001000.bin` and `_010000.bin`
are exact byte prefixes of the 16 MiB dump. same session, same burning window,
the two read paths agree. nothing was re-read, so nothing in this round depends
on the stick being in the state it was.

## 2. the reference footprint, the main result

`reports/round11-bl33-refs/01_footprint.txt`. every address the window points at,
by how it points at it: `BL`/`B` are rel32 calls, `ADRP` followed by `ADD` is a
data reference. the split matters, a call target that is now a bitmap means code
was overwritten, a data target that is now zero means rodata was cleared.

```
referenced address range  0x0100130c .. 0x010cbf80   (811 KiB)
  8443 call instructions (5489 BL + 2954 B), 2763 distinct targets
                                          0x0100130c .. 0x0109b00c
  2413 ADRP+ADD data references, 1729 distinct targets
                                          0x01041de0 .. 0x010cbf80
lowest reference is 0x130c bytes above 0x01000000
```

```
64 KiB  call-ref  data-ref  zero now  state
01000000        43         0    45.4%  overwritten   FDT + bitmap
01010000        21         0    48.3%  overwritten   stale resource copy
01030000         1         0    48.0%  overwritten
01040000      729        18    15.2%  <- the surviving window
01050000      651        46    16.3%  <- the surviving window
01060000      607       514    15.0%  <- the surviving window
01070000      633       485    15.7%  <- the surviving window
01080000       27       435    50.2%  overwritten   AML_RES! image
01090000       51       122    48.3%  overwritten   bitmaps
010a0000         0        44    47.4%  overwritten   bitmaps
010b0000         0        30   100.0%  CLEARED
010c0000         0        35   100.0%  CLEARED
```

read that table as the memory map of an image that is mostly gone:

| what | evidence |
|---|---|
| `.text` starts at `0x01000000` | the lowest of 8443 call instructions lands at `0x0100130c`, 4.9 KiB in. `start.S` puts `_start`, `reset` and `low_init` in the first few KiB. nothing anywhere in the 256 KiB points below `0x0100130c` |
| `.text` runs to about `0x0109c000` | the highest call target is `0x0109b00c`; the data references leave the window at exactly `0x01080000`, where the resource image sits |
| `.rodata`/`.data` sit above it, to at least `0x010cbf80` | data references continue past the end of the call targets by 203 KiB and stop at `0x010cbf80` |
| total image | `0x01000000..0x010cc000`, 816 KiB, of which 811 KiB is referenced from this one window |

this is a normal `.text` then `.rodata` layout and it is what a 2015.01 GXL BL33
with fastboot, optimus and vendor commands would look like. `0x01020000` has no
reference from the window at all, which is fine, an alignment hole or a large
table inside `.text`.

**the low edge is the load address claim.** a fragment that happened to sit
anywhere in memory would not have all 8443 of its call instructions and 2413 of
its data references packed inside one 811 KiB window whose bottom edge is 4.9 KiB
above `0x01000000`. that is a base, not an offset. round 8 refuted
`CONFIG_SYS_TEXT_BASE = 0x01000000` as an *entry point* and it was right: the
address holds a device tree. it was not a refutation of `0x01000000` as the
*load address of the image*, which is what the footprint says, and it never
tested that either.

### 2.1 what clobbered what, and who told the vendor to do it

| agent | address | why it is there |
|---|---|---|
| the device tree | `0x01000000`, 58280 bytes | `CONFIG_DTB_MEM_ADDR 0x1000000` (`cpu.h:57`). **the same address as `CONFIG_SYS_TEXT_BASE` (`cpu.h:41`)**. Amlogic stages the DTB on top of U-Boot's own first 256 KiB |
| the boot resource image | `0x01080000`, `AML_RES!`, 916352 bytes | `GXB_IMG_LOAD_ADDR (0x1080000)` (`bl31_apis.h:119`), the `bootm` image buffer |
| an older copy of the same resource image | `0x01010000..0x0102bffff` | byte identical to `0x01090000..0x010abfff` for **114688 bytes**, re-measured here. `0x01090000` is `GXB_IMG_LOAD_ADDR + 0x10000`, so this copy was staged with base `0x01000000`. the same buffer was written at `0x01000000` first and at `0x01080000` later |
| zeros | `0x010b0000..0x010cffff`, 128 KiB | cleared, not overwritten with anything. the highest data reference, `0x010cbf80`, is inside this range |

the ordering is not measured and does not matter for the question at hand. what
matters is that all three agents wrote to addresses the vendor's own reference
config names, and that all three landed inside the footprint the surviving code
claims for its image.

### 2.2 the hottest targets, and where they went

```
0x01092cac  251 calls    now a bitmap pixel run      (00 01 00 00 00 00 40 00 ... ff ff ...)
0x01092e84  152 calls    same region
0x0109453c  124 calls    same region
0x01092eec  121 calls
0x0109421c  120 calls
0x01092d30  107 calls
0x0100176c   99 calls
0x010931c8   73 calls
0x0100a324   24 calls    now FDT struct block bytes (6f 6b 00 00 ... 0e 53 74 72 75 65 = "true")
```

round 8 already called `0x010413c8` a varargs collector, "the hottest call target
in the region at 1772 call sites, saves x0-x7 plus q0-q7". that is still the best
reading and it is now in context: the libc-ish tail of `.text` was at
`0x01090000..0x0109b000` and it is now bitmap pixels. `0x01092cac`, called 251
times, is the hottest function in the image and we have its address, not its
code.

`0x0100a324` is the interesting one. it is 24 calls deep below the window and it
currently contains `ok` / `true` inside the FDT struct block. so the window calls
*into the device tree*, which means the window and the device tree were never
meant to coexist. the tree landed on top of code that is still calling there.

## 3. what the code is, second route

round 10 matched `drivers/securestorage/securestorage.c`, which is one
translation unit and one source file, and `securestorage.c` has no string
literals so the match is structural and silent. this round adds evidence that
does not come from any source file at all.

`reports/round11-bl33-refs/06_mmio.txt`. `bl31_refs.py mmio` collects every value
in `0xc0000000..0xefffffff` built with `movz`+`movk` inside the window, and then
requires the same register to be loaded from or stored to within four
instructions, because a `movz`+`movk` pair can also just be two unrelated 16-bit
immediates.

**207 confirmed MMIO accesses.** the top of the list, with names resolved
against `.src/u-boot-khadas/arch/arm/cpu/armv8/gxl/firmware/bl21/secure_apb.h`:

```
0xc1104040   6    CBUS aperture (IO_CBUS_BASE)              io.h:28
0xc1107d4c  13    CBUS aperture
0xc81000c0   2    AO_IR_BLASTER_ADDR0
0xc81000e8   2    AO_RTI_GEN_PWR_SLEEP0
0xc8100228   1    AO_SEC_SD_CFG10
0xc8100240   1    AO_SEC_GP_CFG0
0xc9100010   7    USB port B aperture (M8_USBPORT_BASE_B)
0xc9101000   8    USB port B aperture
0xd0107498   5    VCBUS/VPU aperture (IO_VPU_BUS_BASE)     io.h:33
0xd010757c   4    VCBUS/VPU aperture
```

`AO_SEC_GP_CFG*` and `AO_SEC_SD_CFG*` are Amlogic's secure general purpose and
secure SD configuration registers. the window drives them, reads the CBUS, reads
and writes the USB port B aperture, and reads VCBUS. that is Amlogic GXL
bootloader code by a route that has nothing to do with secure storage.

together with round 10 this is four independent signals: 100% AArch64 decode with
818 stack prologues, 13 BL31 ids in source order from `securestorage.c`, 207
Amlogic MMIO accesses, and an 811 KiB self-consistent footprint. **the window is
Amlogic GXL U-Boot-family code. that part is not in doubt any more.**

what it is still not shown to be: the entrypoint, and the whole of BL33.

## 4. relocation: closed for this dump

round 10 §5 reported a "relocation smell" and a delta hint, and explicitly said
`0x40000` is NOT PROVEN with 47413 candidates. that method was wrong and this
round replaces it.

AArch64 is PC-relative everywhere except `ADR` and `ADRP`. a relocated copy
therefore keeps every `BL`, every load/store offset and every branch bit
identical, and only the `ADR`/`ADRP` immediates move. matching must wildcard
those two and keep everything else. round 10 matched `BL` offsets alone, which is
why 47413 deltas all "worked".

`bl33_refs.py reloc` first plants a copy it knows is there, at `0x01140000`
byte-identical and at `0x01180000` with the `ADR`/`ADRP` immediates moved by
`+0x100000`, and refuses to report a negative if the matcher cannot find both:

```
positive control: planted a byte identical copy at 0x01140000
               and an ADR/ADRP-shifted copy at 0x01180000 (+0x100000)
  matcher: 0x01140000  262108 bytes
  matcher: 0x01180000  262108 bytes

real search over reports/round8-bl33-read/mread_01000000_01000000.bin
  invariant runs >=12 words: 1319, anchors 10479, raw hits 10830
  copies of the window (>=128 B matched): 0
    none. no relocated copy of this window inside the dump.
```

the first version of this search returned zero too, and it was worth nothing: the
same code, with a control, did not find the byte-identical copy. a negative from
a matcher that cannot find a copy that is definitely there is not a result. that
is why the control is in the tool and not in a footnote.

**so: no relocated copy in `0x01000000..0x01ffffff`.** if U-Boot did relocate
itself (`CONFIG_NEEDS_MANUAL_RELOC` on this platform), the copy it is executing
from is outside the 16 MiB this dump covers and its address cannot be recovered
from RAM alone.

one exclusion that does follow, and a better one than expected. the whole 16 MiB
has exactly one region that is bootloader-shaped:

| range | content |
|---|---|
| `0x01000000..0x0103ffff` | FDT + a stale resource copy, no code |
| **`0x01040000..0x0107ffff`** | **the surviving window** |
| `0x01080000..0x01139fff` | `AML_RES!` image + bitmaps |
| `0x0113906c..0x01391fff` | zero, 2403 KiB |
| `0x01392000..0x013e7291` | the 12-byte-pattern table of round 8 §3.4, entropy 0.28, no code |
| `0x013e7292..0x0168dfff` | zero, 2779 KiB |
| `0x0169e000..0x01ffffff` | intact, uncompressed Linux 4.9.113 |

`0x0169e000..0x01ffffff` holds a whole kernel with its banner string and nothing
in the burning flow restores it, so it was not written during this session.
U-Boot's relocation is a memcpy of the whole image, so **the live BL33 is not at
`0x0169e000` or above.** and the 5.2 MiB of zeros at `0x0113906c..0x0168dfff`
rules out everything between the resource image and the kernel. that leaves the
live copy above `0x01ffffff` or below `0x01000000`, and the first one is what
§11 proposes to read. the second one is off limits.

## 5. do_bootm, aml_sec_boot_check, the SMC

`reports/round11-bl33-refs/03_ids.txt`.

```text
0x820000ff  AML_DATA_PROCESS, bl31_apis.h:109
  as a movz+movk pair: none
  as a packed literal: none
  => NOT in this dump
```

`bl31_apis.c:255` builds it with `movz`/`movk` into `x0`, and `bl31_apis.c:255-308`
then does the `smc #0` with `x0..x4` set. the search covers both encodings this
time, register and literal pool. `0x82000023/24/25/27/28/60/61/62/63/64/65/69/6a`
all do appear, so the search works on this dump and on this window.

**`aml_sec_boot_check` is not in these 16 MiB.** that is a real negative now, and
round 10's §4.3 already had it right.

**`do_bootm` is not in these 16 MiB either**, and there is finally a reason
instead of a shrug. `do_bootm` in `bl31_apis.c` prints `aml log : Sig Check %d`.
that string is in `.rodata`. the window's data references reach
`0x010a0000..0x010cb000` and those pages are now bitmap pixels or zero, with
`0x010b0000..0x010cffff` 100% cleared. if this image's rodata was in that range
it is gone. its text could equally have been in `0x01000000..0x0103ffff`, which
is the FDT and a stale bitmap copy. **both places where `do_bootm` could be are
places something else was written after the fact.**

that is an explanation for the absence, not a location. `do_bootm` is not found.

**SMC sites.** the 5 real ones in the window, all matched in round 10 to
`securestorage.c` / `bl31_apis.h`, stand and are not re-litigated here:
`0x01073ba0`, `0x01073ba8`, `0x01073bb0` (the three `smc #0` stubs),
`0x01074138` (inlined in `secure_storage_set_info`), `0x0104b5a0` (a `0xb2000016`
hex setter, still unidentified). **no SMC site in this dump belongs to an
`aml_sec_boot_check` path.** round 8's count of 11 was a wrong opcode constant
and round 10 corrected it; nothing here changes that correction.

## 6. _start

`reports/round11-bl33-refs/02_start.txt`. rounds 7 and 8 stepped in 64-byte
strides. this round scans every 4-byte slot in all 16777216 bytes for
`b <label>` with a quad at `+8` that at least looks like a link address. 6 hits,
all false positives, quads `0x08000000`, `0x03000000`, `0x0202020b`, `0x068bffff`,
`0x04b00780`, `0x202020b`. none equals its own address, none equals `0x01000000`.

**`_start` is not in the dump, and §2 says why it cannot be**: `start.S:22-29`
puts `_start` at offset 0 of the image, and offset 0 of this image is now the
aquaman's device tree. the signature was overwritten before anyone looked for it.

## 7. is the copy in the dump the one that is running right now

probably not, and this is the biggest open item.

the FDT at `0x01000000` and the decompressed Linux 4.9.113 at `0x0169e000` are
both things U-Boot does when it boots Linux, which the burning flow does not do.
so this window is most likely a **leftover from the Android boot that preceded
`fastboot oem update 5000`**, and the Optimus/U-Boot serving the current session
is somewhere else entirely. **INFERRED, not measured:** no Android device is
attached to read `/proc/uptime`, and nothing inside the 16 MiB settles it. what
would settle it: a kernel command line with a KASLR seed in it, which this repo
cannot get offline.

two supporting facts, both already in the repo: round 6 found a **Java heap** at
`0x20000000` with `com/youtubei/`, `com/yuliskov/SmartTube`, `android/icu` class
paths, during a burning session. userspace memory from a completed Android boot
survived into the burning window. and the stick was sitting in `18d1:0d02`,
Android fastboot, before round 8 entered burning mode, which means Android had
run.

if that is right then round 8 §3.5's "the running Linux kernel" is wrong wording,
and this round does not repeat it: there is a Linux kernel in RAM, from a boot
that already finished.

## 8. model

```text
surviving BL33/U-Boot fragment   0x01040000..0x0107ffff, 256 KiB
provenance                       Amlogic GXL, HIGH confidence
                                 securestorage.c match + 13 BL31 ids (round 10)
                                 207 confirmed Amlogic MMIO accesses (this round)
image footprint                  0x0100130c .. 0x010cbf80 referenced, 816 KiB
image load / link base           0x01000000, MEDIUM
                                 lowest reference 4.9 KiB in, and both
                                 CONFIG_SYS_TEXT_BASE and CONFIG_DTB_MEM_ADDR
                                 are 0x1000000 in the reference tree
entrypoint / _TEXT_BASE          not found, offset 0 is the FDT
live relocated base              NOT FOUND. no second copy in 0x01000000..0x01ffffff,
                                 validated matcher. not in 0x0113906c..0x01ffffff
                                 either: 5.2 MiB of zeros then an intact kernel
do_bootm                         NOT FOUND. its rodata pages are zero or bitmaps
aml_sec_boot_check               NOT FOUND. AML_DATA_PROCESS 0x820000ff absent as
                                 movz+movk and as a literal
SMC in this dump                 5 sites, all secure storage. none in a
                                 aml_sec_boot_check path
whole of BL33 present            NOT PROVEN, 256 KiB of 816 KiB survived
secure boot bypass               NOT DEMONSTRATED, unchanged
```

against round 10: the relocation question moves from "hint, 47413 candidates"
to "no copy in this dump, here is the matcher that proves it". against round 8:
"BL33 base candidate = none" is now wrong twice over. there is a candidate
fragment and it is the middle of an image whose base is 0x01000000.

## 9. ambiguities, stated plainly

- **`0x01000000` as the load base is medium, not high.** the footprint argument
  is strong and the config corroboration is strong, but both are consistent with
  a base of `0x01000000 - delta` for some `delta`. nothing in this dump
  constrains `delta`.
- **is the copy in the dump the live one?** probably not (§7). if it is not, the
  BL33 that is answering our USB requests has never been dumped.
- **U-Boot vs Optimus.** everything here is consistent with either. the window
  holds `secure storage` and Amlogic MMIO code; `do_bootm`, `fastboot`, `reset`
  and the `cmd_tbl` table are all still absent, and all of those live in U-Boot
  proper rather than in the burning agent. **not distinguished.**
- **the 1 KiB at `0x0100e400..0x0100e7ff`, entropy 7.82** (round 10 §7) is still
  unexplained and sits inside the FDT's `totalsize` margin.
- **`0x0104b5a0`, the `0xb2000016` SMC**, is still unidentified.
- **the current blob at `0x0100a324` and the 39-target libc cluster at
  `0x01092000..0x01095000` are addresses we know and bytes we do not have.**
  recovering them needs a read from a moment when they were not overwritten,
  which means a different boot path, not a bigger dump of the same window.

## 10. files

- `tools/bl33_refs.py`, new, offline. four verbs: `footprint` (call and data
  reference ranges, per-64 KiB table, hottest out-of-window targets), `reloc`
  (ADR/ADRP-wildcarded copy search with a mandatory positive control), `start`
  (`_start` at 4-byte granularity), `ids` (BL31 id census incl. the literal
  form), `mmio` (Amlogic register accesses confirmed by a following load/store,
  named against the reference header). every number in this report comes out of
  it.
- `reports/round11-bl33-refs/01_footprint.txt`, `02_start.txt`, `03_ids.txt`,
  `04_reloc.txt`, `05_clobber.txt`, `06_mmio.txt`.
- nothing else was touched. `reports/bl33-offline-round8.md` and
  `-round10.md` are left as they are; this round supersedes round 10 §5 only.

## 11. next step, and it is a decision not an analysis

there is no more offline work that can move `do_bootm` or
`aml_sec_boot_check`, because their pages were written over before the dump
existed. the 811 KiB footprint says exactly which pages, and they are gone.

the options, in the order I would take them:

1. **`0x02000000..0x03000000`, one fixed 16 MiB read.** it is above the kernel
   (`0x0169e000..`, so U-Boot never relocated there), it is inside
   `GXB_IMG_SIZE` (`0x01800000`, the bootm window runs to `0x0287ffff`), and it
   is the only large unexamined region between the dump and the top of the
   `GXB_IMG_LOAD_ADDR` arena. 1.1 s at the measured 14.6 MiB/s. this is the one
   continuation the reference config already argues for and it is a single fixed
   read, not a scan.
2. **catch the other boot path.** the live BL33 is probably not in this dump at
   all. a read taken from the Android-boot state instead of the burning state
   would be a different memory map, and `0x01000000` would then hold U-Boot text
   instead of the FDT.
3. **do not** go below `0x00800000`. round 6 proved `0x00000000` drops the device
   off the bus and recovery is a power cycle. §4's exclusion (`>= 0x0169e000`) is
   a deduction, not permission to probe.

option 1 is a device read and needs the stick in fastboot and a fresh
`fastboot oem update 5000`. **not done this round**: the brief for this round was
`0x01000000..0x02000000`, that dump already existed and was verified, and
nothing here needed new hardware. nothing was written to the stick and no
dangerous verb was run.
