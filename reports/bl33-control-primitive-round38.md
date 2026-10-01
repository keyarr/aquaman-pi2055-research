# BL33 round 38: corrective audit of the `ddr_test_copy` -> `cmd_tbl` chain

date: 2026-09-30, round 38. offline only. no USB, no device, no command issued.
image: `reports/round14-bl33-persist/bl33-37e18000.bin` (sha256 `664fb34a...`).
page table + live DRAM: `reports/round12-reloc/mread_37800000_00800000.bin`
(also copied under `reports/round13-reloc-verify/`).
tool: `tools/bl33_ctrl.py` (`prim`, `dump`, `collateral`, `reach`) and
`tools/bl33_prov.py`, plus one-off capstone windows quoted below.
tests: `TestBl33Round38` in `tools/run_tests.py`.
reference: `.src/u-boot-khadas/include/command.h:30`, `common/command.c:85,117,489,499`.

**verdict: D - no compatible consumer was found. the round 37 chain is
invalid as stated, and no <=10 char sink composes a clean primitive.**

round 37 said B. that was wrong. the consumer loads 64 bits, the
primitive stores 32 bits x4, and `0x10200000 x4` is not `0x10200000`.
everything else in round 37 that depended on that equality falls with it.

---

## 0. answer block

```text
consumer             0x37e5f6e8 ldr x4, [x19, #0x10] ; 64-bit, then blr x4 @0x37e5f6fc
                     x19 = find_cmd return = entry pointer, no transform between
width                64, not 32. report table row "yes, 32-bit" was wrong
struct               U-Boot cmd_tbl_s, stride 0x30, base 0x37f60eb0, end 0x37f62470
                     116 entries, all named here (0..115), not 112
0x37f60ec0           entry0 +0x10 = cmd, func pointer 64-bit, proven below
0x37f60eb0           first valid entry (aml_sysrecovery), not sentinel/NULL
collateral           dst=0x37f5cec0 size=0x1000 -> L=0x4000
                     fill [0x37f5cec0,0x37f60ec0), tail [0x37f60ec0,0x37f60ed0)
tail value           W=0x10200000 -> u64 0x1020000010200000, top16=0x1020, non-canonical
any repeated W       no 32-bit W repeated x4 gives a canonical host-buffer pointer
                     small W gives canonical but not host bytes (see sect 4)
alternatives         A/B/C/D/E all fail with proof in sect 5
entry 1              index 1 zero-based (amlmmc @0x37f60ee0), not a sentinel slot
sinks <=10           none gives host-bytes + host-dst + host-len without the 16 KiB + tail shape
exit                 D
```

---

## 1. consumer width, with dataflow

bytes at the site (`bl33-37e18000.bin`, base `0x37e18000`):

```text
0x37e5f6e8: 64 0a 40 f9  ldr x4, [x19, #0x10]
0x37e5f6fc: 80 00 3f d6  blr x4
0x37e5f6b4: 00 08 40 b9  ldr w0, [x0, #8]
0x37e5f718: 60 0e 40 b9  ldr w0, [x19, #0xc]
```

`x4` means 64-bit. `w0` at the other two sites means 32-bit. that contrast
is the whole point. capstone agrees: first operand `x4`, second operand
`[x19, #0x10]`.

full path in `call_cmd 0x37e5f664`:

```text
0x37e5f690 bl 0x37e5ee9c        ; sconv -> find_cmd, x0 = argv[0] string
0x37e5f694 mov x19, x0          ; x19 = entry pointer (or 0)
0x37e5f698 cbnz x0, #0x37e5f6b4 ; NULL check
0x37e5f6b4 ldr w0, [x0, #8]     ; maxargs, 32-bit
0x37e5f6b8 cmp w22, w0          ; w22 = argc
0x37e5f6d8 cbz x20, #0x37e5f6e8 ; x20 = repeatable ptr, NULL on run_command path
0x37e5f6e8 ldr x4, [x19, #0x10] ; cmd, 64-bit
0x37e5f6fc blr x4               ; no and/movz/ubfx between, just movs of x0/w1/w2/x3
```

so:

```text
consumer address: 0x37e5f6e8
load instruction: ldr x4, [x19, #0x10]
load width: 64 bits
source address: [x19 + 0x10], x19 = matched cmd_tbl entry
register: x4
dataflow: memory -> ldr x4 -> blr x4, no transform
```

caller `0x37e23c00 bl 0x37e5f664` passes `x4 = NULL` (no `;` in input),
`x0 = (w2 != 0)`, `x1 = argc`, `x2 = argv`, `x3 = argv`, so the repeatable
dance is skipped and the branch above is the only gate besides maxargs.

why the 463-site walk missed nothing but the label was still wrong:
re-ran it to function start with `x0-x18` killed at `bl`, plus a chase
through `mov/sxtw/uxtw/add`:

```text
463 br/blr total, 455 with an x def before them in-function,
8 with no def in-function, 0 with a w def, even through moves
```

round 37 counted the same 0 and then still wrote "yes, 32-bit,
unaligned window is harmless" for this `x` site. that row is the bug.
four `str w` (round 37 sect 1, `0x37e3d4b8..0x37e3d4d8`, no 64-bit store
in `0x37e3d1b0..0x37e3d52c`) cannot feed an `ldr x` with one word.

---

## 2. struct cmd_tbl, from source + image

source `.src/u-boot-khadas/include/command.h:30`, both options on
(`config_distro_defaults.h:47,49`):

```text
offset | field      | width
0x00   | name       | 64 (char *)
0x08   | maxargs    | 32 (int)
0x0c   | repeatable | 32 (int)
0x10   | cmd        | 64 (func *)
0x18   | usage      | 64 (char *, LONGHELP)
0x20   | help       | 64 (char *, LONGHELP)
0x28   | complete   | 64 (func *, AUTO_COMPLETE)
stride 0x30
```

image proof, all in dispatch code:

```text
+0x00 name:  0x37e5ee40 ldr x1, [x19] / 0x37e5ee54 ldr x0, [x19]
+0x08 maxargs: 0x37e5f6b4 ldr w0, [x0, #8] + cmp w22,w0
+0x0c repeatable: 0x37e5f718 ldr w0, [x19, #0xc] + and w0,w1,w0 + str w0,[x23]
+0x10 cmd: 0x37e5f6e8 ldr x4, [x19, #0x10] -> 0x37e5f6fc blr x4
+0x18 usage: 0x37e5eed8 ldr x2, [x19, #0x18] (printf name + usage)
+0x20 help: 0x37e5eef8 ldr x0, [x19, #0x20]
+0x28 complete: only 3 entries nonzero in this build:
  printenv 0x37f61cc0, run 0x37f61e70, setenv 0x37f61fc0 = 0x37e5f0d0
```

`sconv 0x37e5ee9c` materialises `base 0x37f60eb0`, `end 0x37f62470`,
`find_cmd_tbl 0x37e5eddc` steps `add x19, x19, #0x30` (`0x37e5ee6c`) from
`smaddl x24, w21, 0x30, x19` (`0x37e5ee28`). `(0x62470-0x60eb0)/0x30 = 116`
entries, `0..115`, all with valid name pointers here. round 37 wrote
"112 named" and "count 1044 slots scanned"; the scan math in `sconv`
(`sub/asr/mul` magic for `/3`) gives 116, and the dump shows 116 named.

field at `0x37f60ec0` is `entry0.cmd`, 64-bit func pointer. the name
`cmd` is earned by the header plus the `ldr x4` above, not assumed.

`0x37f60eb0` is entry 0, valid:

```text
name=0x37ed9a05 aml_sysrecovery, maxargs=3, repeatable=0,
cmd=0x37e8387c, usage=0x37edbed5, help=0x37edbf14, complete=0
```

bytes before it (`0x37f60e80: 0x40`, `0x37f60e88: 0xffffffff00000001`,
`0x37f60e90..a8: 0xffffffffffffffff`) do not decode as entries and sit
below `sconv` base. no sentinel slot 0.

---

## 3. collateral for dst=0x37f5cec0 size=0x1000

`N = 0x400`, `L = ((N & 0x7ffffff) << 4) * loop = 0x4000`, from
`0x37e3d3d0 ubfiz` + `0x37e3d440 mul`:

```text
fill start 0x37f5cec0
fill end   0x37f60ec0
tail start 0x37f60ec0
tail end   0x37f60ed0
```

`python3 tools/bl33_ctrl.py collateral 0x37f60ec0` + direct dump:

```text
fill len 0x4000, 8753/16384 bytes zero, 154 qwords point into [0x37e18000,0x37ff0000)
tail target 16 B at 0x37f60ec0, currently cmd + usage of entry 0
```

concrete subranges inside `[0x37f5cec0,0x37f60ecf)`, not hand-waving:

```text
0x37f5e478..0x37f5e5d8 cipher ops + 0x37edfbed strings
  [0x37f5e478]->0x37e75e44 etc., the 0x37f5e478/80/b8/c0 slots consumed at 0x37e73730/50/ec
0x37f5fd48..0x37f5fd60 ->0x37e8b014,0x37e8aecc,0x37e8ade0 (storage glue)
0x37f605d0..0x37f60648 ->0x37e8cacc,0x37e8c624... (storage ops)
0x37f60658..0x37f60a40 16 printable runs: pattern, Umagic, random, DNAR,
  bootloader, reserved, cache, bootloader-boot0/boot1, AML_TABLE,
  fastboot_context, magic, uart_ao, 1234567890
0x37f60a50..0x37f60e70 usb/fastboot/partition pointers:
  0x37f60a50->0x37e934e4, 0x37f60b00->0x37e948a8, 0x37f60c30->0x37e96bbc,
  0x37f60cc0->0x37e9dbf4, 0x37f60e70->0x37eba1e0
```

and exactly:

```text
0x37f60eb0..0x37f60ecf:
  0x37f60eb0 q=0x37ed9a05 name
  0x37f60eb8 q=0x0000000000000003 maxargs/repeatable
  0x37f60ec0 q=0x37e8387c cmd (tail overwrites all 8 B)
  0x37f60ec8 q=0x37edbed5 usage (tail overwrites all 8 B)
```

so a 16 B tail at `A` kills `cmd` and `usage` together. round 37 drew it
as one slot; it is two fields.

---

## 4. pointer value

for `W = 0x10200000`:

```text
A+0x00 00 00 20 10
A+0x04 00 00 20 10
A+0x08 00 00 20 10
A+0x0c 00 00 20 10
u32 @A = 0x10200000
u64 @A = 0x1020000010200000
u64 @A+8 = 0x1020000010200000
as pointer: top16 = 0x1020, not canonical for 48-bit VA, translation fault
```

is there any 32-bit `W` repeated x4 that lands canonical + executable?
checked, not assumed:

```text
W=0x10200000 -> 0x1020000010200000 top16=0x1020 OOB
W=0x37e8387c -> 0x37e8387c37e8387c top16=0x37e8 OOB
W=0x12345678 -> 0x1234567812345678 top16=0x1234 OOB
W=0xffffffff -> 0xffffffffffffffff top16=0xffff canonical but not mapped code
W=1..0x3ff -> canonical (top16=0) and inside the 4 TiB identity map,
  but VA = W<<32|W is not the download buffer, bytes there are not host
```

host buffer needs `W` in `0x10200000..0x18200000`, which forces
`top16 != 0`. image scan: `0` qwords with `hi == lo` outside `0`/`ffffffff`
whose `lo` is in-image; legit pointers are `0x0000000037xxxxxx` (`hi=0`,
2597 of them). so no `D`-style slot exists either.

page table note, because round 37 got the details wrong while the
headline (RWX where it matters) happens to hold: live table at
`0x37ff0000` is `8192 x 512 MB` (`OA = i << 29` from the builder at
`0x37e19364..74`), identity, `TCR 0x300004516` (`T0SZ=22`, 42-bit),
`MAIR 0xff440c0400`. `idx0,1` (`0..1 GiB`, covers `0x10200000` and BL33)
are `AttrIdx=4` Normal-WB, rest `AttrIdx=0` Device. `AP=0/XN=0` everywhere
in the dump. `2 MB` blocks, `AP=RO low`, `same AttrIdx as .text`, and
`SCTLR=0x300004516` in round 37 sect 2 are misreads: `0x37e193f0..f8`
are `mov x0,#0x4516 / movk` for `TCR`, not an `SCTLR` value. `C=1/I=0`
is unproven offline. `XN=0` where it matters is proven.

---

## 5. the five outs if the callback is 64-bit

A. consumer with `ldr wN`: `0` of 463, even chasing through
   `mov/sxtw/uxtw/add` to the ultimate load. proven, not sampled.
B. 32-bit field used as function address: same `0`. `br/blr` take `x`.
C. later transform turning `0xWW` into something useful
   (`and #ffffffff`, `movz/movk`, `ubfx`, `uxtw` clearing high):
   `0` mask-like steps in any `load -> blr` chain; this consumer has none.
D. target whose legit value already has `hi == lo`: `0` in-image outside
   null/`ffffffff`. all code pointers have `hi=0`.
E. straddle the tail so `lo=W` and `hi` stays `0`: only `A = P-12` does it
   (`tail [P-12,P+4)`), e.g. `P=0x37f60ec0 A=0x37f60eb4` gives
   `cmd = 0x00000000_W`. but the same tail then sets
   `name = (W << 32) | 0x37ed9a05`. for `W=0x10200000` that name is
   `0x1020000037ed9a05`, non-canonical, `find_cmd` faults on entry 0
   before reaching entry 1. small `W` keeps the name canonical but puts
   `cmd < 0x10000` (SoC low, not host bytes). fill-straddle gives
   `hi=0x12345678`, also non-canonical. no layout saves it.

---

## 6. entry 1

zero-based. `base + 0x10` with stride `0x30` is entry 0, not entry 1.

```text
entry 0 0x37f60eb0 name=aml_sysrecovery max=3 rep=0 cmd=0x37e8387c
  usage=0x37edbed5 help=0x37edbf14
entry 1 0x37f60ee0 name=amlmmc max=6 rep=1 cmd=0x37e2f064
  usage=AMLMMC sub system help=read <partition> ram_addr ...
entry 2 0x37f60f10 name=avb max=2 rep=0 cmd=0x37e63a64 usage=avb
```

`find_cmd match entry 1` in round 37 means the second entry (`amlmmc`),
reached only after skipping a corrupted entry 0. no sentinel exists.

---

## 7. sinks <= 10 chars, offline

`cb_oem 0x37e95630`: `strnlen(cmd,32)`, `n = +1`, `memcpy([x29,#0x20],cmd,n)`,
one `strsep`, then `run_command 0x37e5e968` (`0x37e956a0`). `oem ` eats 4,
token budget is 28. `mmc read <addr> <blk> <cnt>` needs 21 minimum so it
fits; that does not make it a host-bytes write.

```text
command: mmc read (mmc 0x37e2ca3c -> do_mmc_read 0x37e2d890, common/cmd_mmc.c:284)
budget: fits (3+1+4+1+8+1+1+1+1=21 with 1-digit blk/cnt)
src: eMMC blocks, not host bytes. dst: host (argv[1] addr, 64-bit simple_strtoul)
len: host (cnt*512, (cnt&0x7fffff)<<9 at 0x37e2d93c)
semantics: block_read(curr, blk, cnt, addr) + flush_cache(addr, cnt*512)
cache: yes, cleaner than ddr_test_copy. side effects: needs a prior mmc write
  of host bytes to some blk, which burns eMMC. not a standalone host write.

command: amlmmc 0x37e2f064 (dispatcher, table 0x37ee5f60-ish)
budget: name fits, subcommand pushes it over for useful forms
src/dst/len: no direct write, just ldr x4,[x5,#0x10]; blr to subcommand
cache: n/a. side effects: none by itself.

command: bmp 0x37e277f0 (3 subs at 0x37ee4e98: info/display/scale)
budget: fits but subs read a bmp header already in RAM, no host-bytes store
src/dst/len: addr is a read source, not a write dst. cache: n/a.

command: ddrtest 0x37e3d540 / ddrft 0x37e3abf4 / ddr_test_cmd 0x37e56170
budget: ddrft/ddrtest fit, ddr_test_cmd (12) does not help the 28 math
src/dst/len: patterns + MMIO 0xc88345c4, defaults src 0x1080000-ish, no
  argv->mem host-bytes store. cache: none. dead for this purpose.

command: ext4load/fatload 0x37e28124/3c -> 0x37e9b5b0 (common/cmd_ext4.c-ish)
budget: useful spelling exceeds 28 once interface + file + addr are named
src: file on eMMC, not host bytes. dst: host addr. len: file size.
cache: file path, no clean flush story here. needs a planted file.

command: store read (store 0x37e33900 dispatcher)
budget: same problem, plus partition-name arg
src: storage partition. dst: host. len: host. not host bytes.

others <=10 (loadb/loadx/loady 0x37e2c1a0 need serial, update 0x37e78ff8
writes fixed 0x7700000, usb/fdt/gpio/run/setenv do not do argv->mem host writes)
budget: some fit, semantics: none is (host src, host dst, host len) RAM write.
cache/side effects: moot.
```

so: no sink with `name <= 10` writes controllable host bytes to a
controllable dst with controllable len minus the `16 KiB + tail` shape.
`mmc read` is the closest and it still needs an eMMC round trip.

---

## 8. exit + what round 37 got wrong

```text
D. callback is 64-bit and the prior chain is invalid; no compatible consumer found
```

not A (no undocumented detail saves `0x1020000010200000`),
not B (load is `x`, proven by bytes + capstone),
not C (0 w-consumers, 0 masking transforms, 0 hi==lo slots),
not E (table above).

round 37 corrections in one place: consumer row `32-bit` -> `64-bit`;
`112 entries` -> `116`; `+0x28 next` -> `+0x28 complete` (only
printenv/run/setenv nonzero); `2 MiB blocks / AP RO low / same AttrIdx /
SCTLR 0x300004516` -> `512 MB blocks, idx0,1 Attr4, rest Attr0, AP=0/XN=0,
SCTLR unproven offline`; `count 1044` -> `116`; tail is `cmd + usage`,
not one slot; `0x12345678` as safe `name` assumed a `w` load, invalid
under the real `x` load.

not established: no device command issued, no RAM written, no payload.
28-char budget is from `cb_oem` copy/`strsep`, not observed truncation.
low DRAM contents, `gd`/stack exact value, cache state, and anything
behind `smc #0` remain unproven. do not spend a reboot proving a chain
whose load width is now closed.
