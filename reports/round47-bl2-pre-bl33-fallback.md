# round47: BL2 pre-BL33, eMMC-failure USB/BootROM fallback does not exist

date 2026-10-02. **static only, no device I/O.** everything below comes from
`.src/u-boot-khadas/fip/gxl/bl2.bin` (38336 B, AArch64, plaintext, build
`gxl gb5491d8 Nov 3 2017`) via `tools/family_stage_dump.py` +
`tools/a64_callers.py`, plus `u-boot-khadas` source (`common/cmd_reboot.c`,
`arch/arm/cpu/armv8/gxl/bl31_apis.c`, `drivers/usb/gadget/v2_burning/aml_v2_burning.c`,
`arch/arm/include/asm/arch-gxl/{bl31_apis.h,romboot.h,reboot.h,secure_apb.h}`).

limit: aquaman BL2/BL30/BL31 are unrecoverable. `bootloader.img`
(0x148200, sha256 c7b8ee...) is uniform ciphertext, no magic, no ToC
(see `reports/round28-fip/01-bootloader-layout.md`). the BL2 here is the
family build, proxy, not the device one. where the BL31 setter lives
(`0x05100000`) is still missing on all 6 SoCs (round36 §3, index `0x42`
for `0x82000043`).

## 0. answer block

```text
eMMC-failure USB fallback          DOES NOT EXIST in BL2
set_usb_boot 2 = BootROM USB         NOT. it is decision selection in BL2.
dev 6                                "forced USB" override, from 0x820, not error
BootROM reached                    NOT PROVEN, no handoff in BL2
BL2 USB                              mailbox SRAM 0xd900c000, no enumeration
why it vanishes                      BL2 USB expects handshake no host
                                     speaks + dev 6 loses eMMC init; wedge until
                                     power-cycle (AO SRAM without battery wipes)
clean test                           E1 round36 (read 0xc810001c / SMC / read)
```

## 1. BL2 call graph (gxl family addresses)

```text
0x793c main:
  bl 0x5488  pinmux/clk (0xc88344c8/444c/4448, 0xc8100014)
  bl 0x80ac
  bl 0x78d4  banner + "Built : 16:32:58, Nov 3 2017."
  bl 0x7920  blr x0, x0=0xd900b400 (content NOT PROVEN, do not classify)
  bl 0x7cdc
  bl 0x79b4  USB GATE, only boot decision
  bl 0x5598  crash check (RTI[15:12]==8 -> "Enter Crash Dump!")
  mov w0,#1; bl 0x5418
  bl 0x1e0   -> b 0x850 storage init dispatch
  bl 0x73e0  FIP check
  "NEVER BE HERE" (0x8abb); b . spin
```

AO state readers in BL2 (all safe alias `0xda10`, never `0xc810023c`):

```text
0x820  bl2_get_boot_device:
  if (([0xda10001c]>>12 & 0xf)==2) return 6
  return [0xda100240] & 0xf          // GP_CFG0[3:0]
0x79bc gate: w19=[0xda10001c]; dev=bl 0x820; w20=[15:12]
0x7c58 skip: clear [11:8], set bit13, str [0xda10001c]
0x5598 crash: ldr [0xda100008] + [0xda10001c], cmp #8
0x72d0: bl 0x820; cmp #5 (log only "USB mode!")
0x7424/0x7624: ldr [0xc8100228] (FIP verify, not decision)
0x544c/0x7ab0: [0xda10025c] GP_CFG7 (helper + set bit31, never decision)
```

`0xc810023c` (SD_CFG15) is never read by BL2 on any decision path.
it is written by BL30 (`0x10001cb8`: `SD_CFG15[15:12]=RTI[3:0]`) and read by
BL33 (`do_get_rebootmode`, `cmd_reboot.c:37`). `0xc810001c` is the state;
`0xda10001c` is the alias BL2 uses.

## 2. eMMC init

`0x850` dispatch (always returns 0, error ignored):

```text
bl 0x820; cmp #1 -> bl 0x720 (eMMC); cmp #2 -> "NAND init"+bl 0x66c4; else ret 0
dev 6 -> else -> NOTHING initialized. CONFIRMED.
```

`0x720` eMMC init (base `0xd0074000` = `0x4000+movk 0xd007`):

```text
setup x1=0x200, x2=0x1800000, bl 0x5d8; touches [0xd0074044];
bl 0x3cc x2; bl 0x6b0; if w0!=0 second pass. no error to caller.
```

`0x5d8` reader (x0=1 eMMC `0xd0074000`, x0=4 SD `0xd0072000`):

```text
x0!=1 && x0!=4 -> "sd/emmc boot device error" (0x8476), ret 0
else: tuning [0xda100244], bl 0x400
```

`0x400` low-level: builds CMD on stack, `bl 0x8100`, programs `0x50/54/58`.
on failure: `"sd/emmc read data error: ret=" (0x8458)` + `bl 0x823c`, returns
`w19!=0`. `0x5d8` propagates, but `0x890` discards (`b 0xa40`, `mov x0,#0`
always).

first point declaring eMMC invalid: `0x400:0x5a0` (`cbz w19`).
nobody branches to USB because of it.

## 3. FIP validation (`0x73e0`)

```text
bl 0x890 load "fip header" (0x1400000, 0x4000); memcpy ->0x1700000
w25=[0xc8100228] & 0x10; bl 0x735c verify; bl 0x7070; bl 0x5688
loop 0x7470: magics 0x434c4d41 (double, 0x76e0), types
  0x3dfd6697 / 0x6d08d447 / 0xa7eed0d6 / 0xaabbcddd / 0x89e1d005
  mismatch -> 0x75d4 next entry, never USB
sig 0x7610-0x78b4: on failure -> w20 = 0xbf/0x55/0x5f/0x6a/0xdc/0xe7, ret w20
caller 0x793c ignores -> "NEVER BE HERE" spin
```

order: `dev 6` (before touching eMMC) -> header `0x1400000` ->
magic `0x434c4d41` -> entry -> sha/sig. any failure = error/spin.

## 4. error fallbacks

| Failure | Function | Branch | Next | USB? | BootROM? |
|---|---|---|---|---|---|
| dev!=1,2 init | `0x850:0x868 b.ne 0x884` | ret 0 | `0x73e0` | no | no |
| read err | `0x400:0x5a0` | print `0x8458`, ret w19 | `0x890` discards | no | no |
| invalid dev reader | `0x5d8:0x5fc/0x604` | print `0x8476` | ret 0 | no | no |
| FIP/sig | `0x73e0:0x76f0/0x78b4` | ret w20 | spin `0x7970` | no | no |
| verify wrapper | `0x735c:0x738c` | print + `bl 0x72c8` | log only, ret err | log only | no |
| DDR | `0x882a/0x8887` | reset | watchdog `0xa90` | no | no |
| RTI==8 | `0x5598:0x55cc` | crash dump + `bl 0x7254` | — | no | no |

## 5. only USB handoff (`0x79b4`)

```text
dev==5 (GP_CFG0==5, BOOT_ID_USB, romboot.h:69) -> 0x79e4 "BL2 USB "
RTI[15:12]==2 -> 0x79e4 "BL2 USB "
RTI[15:12]==1 -> 0x7c44 "Skip usb!", clear [11:8], set bit13 (3), bl 0x7254
else (cold 0) -> ret 0, proceeds to eMMC the same
```

`0x79e4` is SRAM mailbox, no controller. `bl2.bin` contains no
`DWC/gadget/descriptor/VID/PID/EP0/optimus/burning`:

```text
str 0x7856efab->[0xd900c000]; requires [0xd900c004]==0x200 and magic 0x3412cdab
else str 0xe2->[0xd900c00c]
sub-cmd [0xd900c008]-0xc000-0xde (0..3), jump 0x7a68:
  0: 0xe4; 1: bl 0x5418+0xa58, str->[0xd900c018], 0xe5/0
  2: set GP_CFG7 bit31; ==1 -> [0xd900c01c]->[0x9540]; bl 0x1e0; bl 0x73e0
     ==2 -> blr [0xd900c01c]; else 0xe9. ONLY ==1 continues boot.
  3: checksum vs [0xd900c024], 0xe6/0/e8
always: str status->[0xd900c00c], chip [0xd904050c] vs
  0x940004fe/0x940018cc/0x52800022 -> bl 0x7254
```

`"USB mode!" (0x72dc)` at `0x72c8` (called by `0x735c:0x73c8` on error):
only `if dev==5 print + bl 0x7254`, else print + `b 0xa90`. log, not fallback.

load `0x890` (called by `0x7410/0x74a0`): log
`Rsv/eMMC/NAND/SPI/SD/USB/UNKNOWN` (dev 0..6, tables `0x8448/0x8450`),
handlers: dev1 (`mov x0,#1; b 0xa1c` falls into `0xa18` tail) and dev4
share `bl 0x5d8`; dev5 and dev6 share `bl 0x7980` (memcpy from
`[0x9540]`, filled by USB branch `0x7b08`). dev1 `0x9e4` skips the
`mov x0,#4` and reuses the tail with x0=1. `0x8150` is the byte-by-byte memcpy.

## 6. classification

```text
BootROM              NOT PROVEN. no binary, no VID/PID, no descriptor.
                     BL2 never returns to ROM in disasm.
BL2 USB (0x79e4)     CONFIRMED. mailbox, status 0xe2-0xe9, no enumeration.
"USB mode!" (0x72dc) CONFIRMED as log.
BL30                 transport only (0x10001cb8, 0x10005550, reset
                     0x100035c0; dispatch 0x100026bc with no USB command).
BL33 optimus         CONFIRMED by source (aml_v2_burning.c:72-80:
                     GP_CFG0==5 || GP_CFG7[31]; 1b8e:c003) + F2 885 s.
                     GP_CFG7[31] is dead code on gxl (gpio pad 23, bl30
                     0x10004680). romboot.h "[31:28]" is stale; real is [3:0]
                     (BL2 0x844 + BL33 _get_romcode_boot_id).
```

## 7. `set_usb_boot 2`

BL33 (`cmd_reboot.c:165-175`, `gxl/bl31_apis.c:310-321`):

```text
set_usb_boot 2 -> set_usb_boot_function(2) -> x0=0x82000043, x1=2, smc #0
```

setter BL31 (`0x05100000`, index `0x42`): NOT PROVEN, blob missing.
clear/transport PROVEN: BL31 `0x18ddc` (`RTI[3:0]=mode`, preserves `[31:4]`,
`[15:12]==8 && mode!=12` clear `[11:8]` + `"bl31 clear usb flag"` at `0x18f00`);
BL30 `0x10001cb8` + `0x10005550` (`&=~0xf00`) before `0x100035c0`.

consumer CONFIRMED: `0x820` + `0x79dc cmp w20,#2` hardcoded.
`2 == FORCE_USB_BOOT` (`bl31_apis.h:64`, `cmd_reboot.c:161`).
`2` only selects decision in BL2; does not enable PHY/USB/BootROM.
side effect: `6` does not match in `0x850`, loses eMMC init in the same run.

## 8. `dev 6`

```text
origin 0x820:0x82c-0x838 (mov 6; ubfx [15:12]; cmp #2; b.eq)
callers 0x850:0x858, 0x890:0x8b4, 0x72d0, 0x5520/0x5560
init: 0x85c/0x864, b.ne 0x884 -> nothing. load: log UNKNOWN (0x84bd),
  handler 0xa30 = same as USB (bl 0x7980). "forced USB override".
  CONFIRMED. not error, physical device, enumerated USB, or BootROM.
```

## 9-11. scenarios

A (RTI==1, GP_CFG0==1): Skip -> eMMC init -> FIP -> BL30/31/33. CONFIRMED.
B (dead eMMC): no edge to USB/ROM. tries, ignores error, dies in
verify/spin/crash/watchdog. dead end. CONFIRMED by absence of branches.

```text
eMMC failure -> 0x850 ret 0 -> 0x890 ret 0 -> 0x73e0 err -> spin. No USB.
set_usb_boot 2 -> 0x820=6 -> 0x79e4 mailbox + 0x850 nothing + 0x890 UNKNOWN/memcpy
  -> silent wedge. Different branches, similar symptom, opposite mechanism.
```

## 12. USB window

`tools/usb_watch.py` (4 ms, `/sys/bus/usb/devices`) captures real enumeration,
but BL2-USB does not enumerate. F2 round34 (885 s without `1b8e:c003`) proves
absence of optimus, not of BootROM nor of a sub-4 ms window of another VID/PID.
to close: run `usb_watch.py` logging ANY `(vid,pid)` + `journalctl -kf` during
`set_usb_boot 2` + real PSCI reset. timings not invented; with no gadget in
the binary, enumeration is UNLIKELY, not refuted.

persistence note (corrects round36 §7 "battery-backed"): RTI is AO SRAM,
survives reset (masks only `[3:0]`/`[11:8]`), but loses on physical
power-cycle (no battery in the stick). wedge until unplug + return after unplug
is the expected behavior of the armed state, not a contradiction.

## 13. timeline + answers

```text
T0 reset PSCI 0x84000009 (BL31 0x18ddc -> BL30 0x100035c0; do_reset 0x37e21684 never resets)
T1 BL2 0x793c
T2 AO read 0x79bc/0x820
T3 0x850/0x720 eMMC or nothing (dev 6)
T4 0x73e0 load via 0x890
T5 verify 0x735c/0x7610
T6 gates 0x79d0/0x79dc/0x7c44
T7 USB only 0x79e4 (d900c000, e2-e9, 0x7254), never post-failure
T8 0x1e0+0x73e0 + spin/crash/reset
```

P1 what does `set_usb_boot 2` do in BL2? selects `RTI[15:12]==2` -> dev 6 ->
BL2-USB branch + loses eMMC. (consumer CONFIRMED, setter NOT PROVEN).
P2 what abandons eMMC? only `dev!=1` in `0x850` (in practice dev 6).
eMMC failure does not abandon. CONFIRMED.
P3 BootROM fallback? none in BL2. NOT PROVEN.
P4 pre-BL33 USB fallback? one: BL2-USB mailbox, only by prior decision, never
by failure. CONFIRMED. `"USB mode!"` is log.
P5 dead eMMC == flag? no. distinct branches/handlers. NO.
P6 clean test? E1 round36 (read `0xc810001c` / `set_usb_boot 2` / read /
`set_usb_boot 1` / read, one session, `tools/flagtest.py` as model) +
generic `usb_watch.py`. without touching eMMC.

## 14. ledger

```text
CONFIRMED: 0x820==6, gate 0x79dc==2, 0x850 only 1/2, 0x890 dev5/6->0x7980,
  mailbox d900c000/e2-e9, no DWC/VID/PID in BL2, no failure->USB edge,
  BL30 carries [3:0] and clears [11:8], GP_CFG7[8:31]=gpio, GP_CFG0[3:0]=boot id,
  BL33 SMC 0x82000043 with x1=2, bootloader.img ciphertext (proxy needed)
LIKELY: flag 2 writes RTI[15:12] and/or [11:8] (enum matches constant, setter missing);
  silence = BL2 in mailbox no host speaks (terminal not read to the end)
NOT PROVEN: exact setter, BootROM reached, short USB window, 0xd900b400 content
```
