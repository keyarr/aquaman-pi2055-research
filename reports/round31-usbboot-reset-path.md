# round31: what happens AFTER `0x82000043` (offline, no device)

date 2026-09-30. **zero device I/O.** every number is read out of
`reports/round14-bl33-persist/bl33-37e18000.bin` (the exact aquaman BL33, base
`0x37e18000`) and `.src/u-boot-khadas/fip/gxl/bl31.bin` (family GXL reference
BL31, 181160 bytes). no USB, no SMC, no reset, no `oem`, no execution of device
code. tools: `tools/a64_annot.py` (annotated dump, resolves movz/movk into
addresses, honours `A64_BASE`), `tools/a64_ctx.py` (code around every site that
carries the high half of a constant), `tools/a64_callers.py` (direct bl/b
callers of a target list), `tools/bl31_ao_census.py` (MMIO census by register
name). none of this is test-pinned yet.

this round exists because the previous answer to "why does `set_usb_boot 2` hang
the box" was built on a premise that turns out to be false. see §1.

## 0. answer block

```text
oem reset / fastboot reboot  = DO NOT RESET. do_reset 0x37e21684 is a 13
                               instruction stub, no smc, no AO write, no PSCI
                               CONFIRMED
fastboot reboot-bootloader  = same stub (0x37e94e6c)                  CONFIRMED
reboot <mode>               = the ONLY real reset: smc #0 x0=0x84000009
                               x1=mode&0xf  (0x37e607d4 -> 0x37e19e98)  CONFIRMED
of the 3 reset variants tried in round 3, 2 were not resets at all
set_usb_boot 2              = smc #0 x0=0x82000043 x1=2, x2=0x10 not
                               zeroed, return value discarded            CONFIRMED
BL33 writes GP_CFG7         = ZERO. 3 refs, all ldr                     CONFIRMED
is_tpl_loaded_from_usb()    = compiled into BL33 at 0x37e76510, reads
                               GP_CFG0[3:0]==5 || GP_CFG7[31]           CONFIRMED
FORCE_USB_BOOT armed by     = NOWHERE. the wrapper has exactly 2 callers
optimus in this build         and neither passes 2                     CONFIRMED
setkeys calls               = DOES NOT. it is mac/sn2 env provisioning
set_usb_boot_function(1)      (round25 already had this right)         REFUTED
ROM entered USB and failed  = REFUTED. 4 ms poll, 600 s, zero 1b8e:c003
BL31/reset transition stuck = PLAUSIBLE, but only for the one real reset,
                               which has no bus watcher and no log
the aquaman BL31            = still UNAVAILABLE, unchanged
the family gxl bl31.bin     = a PARTIAL image. it references 0xc5000,
                               0xc5ec0 and 0xcb040; the file ends at 0x2c3a8
```

## 1. the premise that was wrong

`usb-entry-aquaman.md:373-375` concluded "wrong reset mode -> REFUTADO ...
three different reset paths, one outcome". two of those three paths do not
reset the chip.

`do_reset`, cmd_tbl `reset` at `0x37e21684` (`04_cmds.txt:56`):

```text
0x37e21684  stp  x29,x30,[sp,#-0x10]!
0x37e2168c  adrp x0,#0x37ebf000 ; add x0,x0,#0x612     ; "resetting ...\n"
0x37e21694  bl   0x37e593c8                           ; printf
0x37e21698  mov  x0,#0xc350
0x37e2169c  bl   0x37eab1c8                           ; udelay(0xc350)
0x37e216a0  bl   0x37e2147c                           ; mov w0,#0 ; ret (no-op)
0x37e216a4  bl   0x37e21680                           ; ret; tail of the function
                                                       ; at 0x37e21650 that prints
                                                       ; "Resetting CPU ...\n"
0x37e216a8  mov  x0,#0
0x37e216ac  bl   0x37e1a0c0                           ; aml_watchdog_read_reg(0)
0x37e216b0  mov  w0,#0
0x37e216b4  ret
```

thirteen instructions. **no `smc #0`, no AO access, no branch to the PSCI
wrapper.** the slot the family fills with `reset_cpu()` holds a stub.

what the two live calls actually are, so nobody has to re-derive them:

- `0x37eab1c8(0xc350)` is a **timer**, not an allocator. `0x37eab150` reads
  `cntfrq_el0` (`0x37e192dc`) and `cntpct_el0` (`0x37e192e4`), multiplies by the
  argument, rounds to a 1 MB boundary and spins a counter to the target. this is
  the shape of `udelay()`/`mdelay()`, and it is the single most common callee in
  the image (150+ call sites), so the argument is a duration, not a page count.
  **this is a delay, and it is not evidence of corruption.**
- `0x37e1a0c0(0)` is `aml_watchdog_read_reg(0)`: it calls `0x37e1a058`, which
  busy-waits on the **watchdog** block at `0xc11098d0` — the exact `reg` of the
  DTB `/watchdog` node (`artifacts/aquaman.dts:323`,
  `compatible = "amlogic, meson-wdt"`) — sets `bit 0x40000`, spins 100 times,
  then reads the register back through `0x37e1a0c0`, whose setter twin
  `0x37e1a0d8` (`str w1,[x0]`) has ~200 call sites.

so `do_reset` is: print, delay, two no-ops, poke the watchdog, return 0. it may
well stop feeding or reconfigure the watchdog. **whether that alone kills the
fastboot session is UNKNOWN** — but note that a watchdog-driven reset would
reboot the SoC, and no reboot was observed, so the box did not simply wedge
silently for a watchdog reason either. legs 2 and 3 end with the device gone
from the bus and the log silent, which is consistent with a BL33 that stopped
answering, not with a reset that happened.

and the fastboot uses the same stub. the family's `run_command("reboot fastboot")`
(`f_fastboot.c:366-369`) is not in this build:

```text
0x37e94e58  b  0x37e21684   ; compl_do_reset
0x37e94e6c  b  0x37e21684   ; compl_do_reboot_bootloader
0x37e25fac  bl 0x37e21684   ; fallback when "fastboot boot" is rejected
0x37eac66c  bl 0x37e21684   ; wipe 0x186a0 then b . (factory die path)
```

consequence, per round 3's own three trials:

| trial | command | what it really does | reset issued? |
|---|---|---|---|
| 1 | `oem reboot cold_boot` | SMC `0x84000009` x1=0 | **yes** |
| 2 | `oem reset` | `do_reset` stub | **no** |
| 3 | `fastboot reboot` | `do_reset` stub | **no** |

trials 2 and 3 are the same experiment: arm the flag, do not reset. the device
stayed in BL33 both times and stopped answering the host. no reset was issued,
so the BootROM, BL2/BL30/BL31 and the AO domain were never re-entered, and the
flag could not have been consumed by anyone. what stopped BL33 from answering
is not established by static evidence; the watchdog poke in `do_reset` is the
obvious candidate and is not proven.

**the "3 resets, 1 outcome" evidence is 1 reset and 2 crashes.** the reset-mode
hypothesis was never tested.

## 2. the only real reset

`reboot [mode]`, cmd_tbl at `0x37e60654`, single site `0x37e607d4`:

```text
0x37e607c0  mov  x2, #0
0x37e607c4  mov  x0, #9
0x37e607c8  and  x1, x1, #0xf
0x37e607cc  mov  x3, x2
0x37e607d0  movk x0, #0x8400, lsl #16        ; 0x84000009 = PSCI_SYSTEM_RESET
0x37e607d4  bl   0x37e19e98                  ; aml_reboot -> smc #0
```

wrapper `0x37e19e98`:

```text
0x37e19e98  mov  x4, x0
0x37e19e9c  smc  #0
0x37e19ea0  mov  w0, w4
0x37e19ea4  ret
```

mode table, decoded from the aquaman strings (`0x37ed24e4` onward) and the
`and #0xf`:

| argv[1] | x1 | | argv[1] | x1 |
|---|---|---|---|---|
| `cold_boot` | 0 | | `bootloader` | 7 |
| `normal` | 1 | | `hibernate` | 6 |
| `recovery` / `factory_reset` | 2 | | `suspend_off` | 5 |
| `update` | 3 | | `crash_dump` | 11 |
| `fastboot` | 4 | | `kernel_panic` | 12 |
| default / no argument | 1 | | `rpmbp` | 9 (Xiaomi-only) |

identical to `cmd_reboot.c:120-158` + `reboot.h:41-53`, plus `rpmbp`.

## 3. the SMC 0x82000043 surface, exact

### 3.1 the wrapper

```text
0x37e19efc  mov  x1, x0
0x37e19f00  mov  x0, #0x43
0x37e19f04  movk x0, #0x8200, lsl #16
0x37e19f08  smc  #0
0x37e19f0c  ret
```

- x1 = mode, raw, unvalidated, unmasked. `0` is not in the family enum
  (`bl31_apis.h:63-66`: 1 CLEAR, 2 FORCE, 3 RUN_COMD, 4 PANIC_DUMP).
- **x2 is not zeroed.** the command handler leaves `mov w2,#0x10`
  (`0x37e60818`) live into the SMC. x3..x7 are caller garbage.
- the return value is discarded; the caller does `mov w0,#0` right after.

command handler `0x37e607e8`: `simple_strtoul(argv[1], NULL, 0x10)` at
`0x37e6081c` (**base 16**, same as `cmd_reboot.c:165`), then `bl 0x37e19efc`.

### 3.2 BL33 never writes GP_CFG7

`tools/bl31_ao_census.py` over the exact BL33, all `AO_SEC_GP_CFG7`
(`0xc810025c`) references, all three of them loads:

| addr | use |
|---|---|
| `0x37e57bc0` | `rpmb_state`: `ubfx x3,x3,#0x16,#1` -> `androidboot.rpmb_state` |
| `0x37e57c08` | `rpmb_state`: `and w1,w1,#0x400000` (bit 22) |
| `0x37e7651c` | `is_tpl_loaded_from_usb()` -> bit 31 |

same for `GP_CFG0` (2 refs, both ldr), `AO_SEC_SD_CFG15` (`0x37e604a4`, ldr) and
`AO_SEC_SD_CFG10` (`0x37e72790`, ldr). GP_CFG7 is multi-purpose in this SoC:
`[7:0]` boot field cleared on reset, bit 22 = rpmb state, bit 31 = force usb
boot, bits 8+ indexed pin flags (§4.2).

### 3.3 the flag consumer is in BL33, and it CLEARS

`is_tpl_loaded_from_usb()` compiled at `0x37e76510`:

```text
0x37e76510  mov  x0,#0x240 ; movk x0,#0xc810,lsl#16   ; P_AO_SEC_GP_CFG0
0x37e76518  ldr  w2, [x0]
0x37e7651c  mov  x0,#0x25c ; movk x0,#0xc810,lsl#16   ; P_AO_SEC_GP_CFG7
0x37e76524  ldr  w1, [x0]
0x37e76528  and  w0, w2, #0xf
0x37e7652c  cmp  w0, #5                              ; BOOT_DEVICE_USB
0x37e76530  cset w0, eq
0x37e76534  orr  w0, w0, w1, lsr #31
0x37e76538  ret
```

byte for byte `aml_v2_burning.c:64-79`; `BOOT_DEVICE_USB = 5` from
`aml_v2_burning.c:20`.

its only consumer, `0x37e765d8` (the aquaman's `aml_burn_check_is_ready_for_burn`):

```text
0x37e765ec  bl   0x37e76510        ; is_tpl_loaded_from_usb()
0x37e765f0  cbz  w0, 0x37e76620    ; not from usb -> return 1
0x37e765f8  adrp x0,"[MSG]MMC init in usb\n"
0x37e7661c  b    0x37e76588        ; was from usb -> clear
```

`0x37e76588`:

```text
0x37e76590  mov  x0, #1
0x37e76594  bl   0x37e19efc        ; set_usb_boot_function(CLEAR_USB_BOOT)
0x37e76598  mov  w0, #0xefe6 ; bl 0x37e7b8e4
0x37e765a0  mov  w0, #0     ; bl 0x37e77210
0x37e765ac  mov  w0, #0x4e20 ; b 0x37e78f94    ; work mode USB_PRODUCE
```

callers of `0x37e765d8`: `0x37e21d24` and `0x37e22200`, both gated on
`PREG_STICKY_REG2` (`0xc88345c8`) holding `0x1b8ec003` or `0x1b8ec004`. that is
the v2 burning control-request path.

**this is the falsifiable prediction.** had the flag been armed and survived into
BL33, the sequence would be: BL33 sees `GP_CFG7[31]` -> clears it over SMC -> enters
optimus USB produce -> enumerates `1b8e:c003` **as BL33** (bcdDevice `0.07`, no
string descriptors, MaxPower 2 mA, the descriptor round 3 §2.5 already captured).
it never appeared, under a 4 ms poll over 600 s.

### 3.4 nothing in this build arms FORCE_USB_BOOT

`02_smc.txt`: 15 `smc #0` sites, wrapper `0x37e19efc` has exactly two callers
(`0x37e60838`, `0x37e76594`) and neither passes 2. the family's
`optimus_download.c:1350` call is behind `#if ROM_BOOT_SKIP_BOOT_ENABLED_4_USB`,
undefined. **`set_usb_boot 2` is the only way to arm the flag on this stick.**

## 4. BL31

### 4.1 the aquaman BL31 is still unavailable

unchanged from rounds 18/26/27/28/29/30: `[0x05100000,0x05300000)` is
secure-only, at-rest copy is AES-256-CBC with a zero IV under a key that lives
in the secure world. no implementation was invented.

### 4.2 the family reference BL31 is a partial image

new fact, and it limits what the family tree can ever answer here. the SMC
entry is `vbar+0x400` = `0x2ac00`, EC `0x13` -> `0x24c34`:

```text
0x024c84  ubfx x16, x0, #0x18, #6        ; FID bits 24..29 (+ bit31<<6)
0x024c90  adr  x11, #0x2a2c8            ; 4-entry handler table
0x024c94  adr  x14, #0xcb040            ; 128-byte FID class map   <-- MISSING
0x024c98  ldrb w15, [x14, x16]
0x024cac  ldr  x15, [x11, w15, lsl #5]
```

`0xcb040` and the `std_svc_table` at `0xc5000+0xec0` are past the end of the
file (`0x2c3a8`). the four surviving handlers are `0x19d78` (TF-A `handle_smc`),
`0x21418`, `0x22d4c`. **there is no `0x82000043` literal anywhere in the image
and no handler for it, so `0x82000043` semantics are UNKNOWN in every direction
and stay that way until the key exists.**

what the 181 KB of text does contain, named (`tools/bl31_ao_census.py`):

| addr | count | register |
|---|---|---|
| `0xda10025c` | 6 | `AO_SEC_GP_CFG7` (secure alias of `0xc810025c`) |
| `0xda10001c` | 5 | `AO_RTI_STATUS_REG3` |
| `0xda10023c` | 1 | `AO_SEC_SD_CFG15` — **read only** |
| `0xda100248` / `0xda100140` | 1 / 1 | `AO_SEC_GP_CFG2` / `AO_REG0` |
| `0xc8100228` | 2 | `AO_SEC_SD_CFG10` |
| `0xda83c408/428/42c` | 1/1/2 | `HIU_MAILBOX_STAT_0/SET_3/STAT_3` (SCP) |

all six GP_CFG7 accesses are read-modify-write and none sets bit 31 directly:

```text
0x018c5c, 0x018ea4   and w,#0xffff00ff ; str     ; clear [7:0]
0x019014             bic  w2,cur,(1<<(idx+8)) ; str ; clear flag idx
0x019184             orr  w4,cur,(1<<(idx+8)) ; str ; set   flag idx
```

`idx = 0x24a50(x) = (x&0xff) + ((x&0xff00)>>6)` — a **pin/pad index decoder**.
bits 8+ are pin state, not boot state.

`0x18ddc` is the reboot-reason writer, and it has an explicit usb clear:

```text
0x018dfc  bl   0x18944 ; cmp w0,#0x21           ; chip id
0x018ea4  mov  x0,#0x25c ; movk x0,#0xda10,lsl#16
0x018ec0  and  w1,w1,#0xffff00ff ; str         ; GP_CFG7[7:0] = 0
0x018ec8  mov  x0,#0x1c  ; movk x0,#0xda10,lsl#16    ; AO_RTI_STATUS_REG3
0x018ed4  add  x0,x21,#0x3d8 ; bl 0x23208           ; "bl31 reboot reason: 0x%x"
0x018ee4  ubfx x20, x20, #0xc, #4
0x018ee8  cmp  w20, #8
0x018ef4  cmp  x22, #0xc
0x018efc  adrp x0,#0x25000 ; add x0,x0,#0x3f2 ; bl 0x23208  ; "bl31 clear usb flag"
0x018f24  str  w19, [x0]                             ; new mode
```

family evidence only, but it is the only architectural handle on the clear path:
BL31 clears GP_CFG7[7:0] on every reboot and prints `bl31 clear usb flag` when
`AO_RTI_STATUS_REG3[15:12] == 8` and the new mode is not 12. bit 31 lives in
`[8:]` and the set helper writes `1 << (idx+8)`, so `idx = 23` would land exactly
on bit 31. whether that runs on the reset path is UNKNOWN.

### 4.3 PSCI system reset, family reference

the hook exists, otherwise `0x22b1c` would spin forever:

```text
0x022b08  ldr  x2, [x2, #0x40]         ; plat_psci_system_reset_hook
0x022b10  printf("ERROR:   Platform has not exported a PSCI System Reset hook.\n")
0x022b1c  bl   0x24fd4                 ; b . (infinite)
```

handler `0x18d3c(power_state)`:

```text
0x018d4c  mov  w0,#0x2000 ; movk w0,#0xc430,lsl#16   ; 0xc4302000
0x018d54  bl   0x194ec                                 ; GIC CPU interface write
0x018d70  bl   0x1f71c
0x018d7c  mov  w1, #3
0x018d84  bl   0x19740                                 ; SCP/BL30 mailbox message
```

`0xc4301000/0xc4302000` is the GIC (confirmed `mesongxl.dtsi:157-158` and
`artifacts/aquaman.dts:230`). `AO_SEC_SD_CFG15[15:12]` — the ROM-visible reboot
mode that BL33's `do_get_rebootmode` reads at `0x37e604a4` — is **read-only in
the family BL31** (polled at `0x1886c`). **BL30/SCP writes it, not BL31 and not
BL33.** the handoff `BL33 -> BL31 -> BL30 -> AO_SEC_SD_CFG15 -> BootROM` has
three hops and none of them is observable from BL33.

## 5. the log, re-read

`reports/round3-usb-entry/setusbboot_usbwatch.log`, t0 ~ 17:10:43.7:

```text
t=  0.000  2717:4e40   android
t=  5.341  android off
t=  8.697  18d1:0d02   fastboot (BL33)
t= 26.962  fastboot off        <-- set_usb_boot 2 + "reset"
t=195.822  2717:4e40   android       <-- 168.9 s of silence
t=199.382  android off
t=202.379  18d1:0d02   fastboot
t=232.715  fastboot off        <-- trial 3
t=273.057  2717:4e40   android       <-- 40.3 s
```

three things that were not in the round-3 reading:

1. **no reset baseline.** `adb reboot` from fastboot returns to android in
   15-20 s per round 2. neither trial 2 nor trial 3 did.
2. **trial 3's 40.3 s gap is anomalous.** if `fastboot reboot` had really gone
   through `reboot fastboot` (mode 4) the device would have come back as
   *fastboot*. it came back as android. consistent with the stub, and also
   consistent with a lost reboot mode.
3. **the logs cannot separate self-recovery from recovery after the user's
   power cycle** for trial 2. 168.9 s is a plausible human latency and a very
   unlikely spontaneous boot. not resolvable from the existing material.

**trial 1 has no bus watcher at all.** its only datum is the ~100 ms Xiaomi
splash, from memory. trial 1 is the only leg that involves the BootROM and it
is the only leg with no instrumentation.

## 6. hypothesis tree, re-graded

```text
set_usb_boot 2
  |
  +-- [A] BL33 builds x1=2 and issues the SMC                CONFIRMED
  |      return value discarded, no success signal            CONFIRMED
  |
  +-- [B] BL31 ignores 0x82000043                            no evidence
  |
  +-- [C] BL31 sets GP_CFG7[31]                              plausible
  |
  +-- [D] no reset happens
  |      [D1] 2 of 3 legs are stubs, not resets              CONFIRMED
  |
  +-- [E] reset happens, flag reaches the ROM
  |      [E1] ROM enters USB, handshake fails                REFUTED
  |      [E2] ROM ignores the flag                           plausible
  |
  +-- [F] reset happens, flag does not reach BL33
         [F1] BL31/SCP clear it on the way                   plausible
         [F2] reset/BL31 wedges before the ROM               plausible
         [F3] reset works, linux boots, USB never enumerates NOT CONSIDERED BEFORE
```

`[F3]` exists because the trial-1 splash means something with a display ran.
BL1 has no splash. if BL33 ran with the flag armed we would have seen
`1b8e:c003` (§3.3) and we did not; if BL33 ran with the flag clear, `cold_boot`
mode would have reached android in 15-20 s and it did not. a kernel-side splash
and a kernel-side USB hang is the remaining reading, and nobody ever looked,
because that leg had no monitor.

## 7. verdict on the original question

**"why does `set_usb_boot 2` seem to work but leave the stick dead?"**

it never worked, and there was no way to tell. the BL33 wrapper is
`mov x1,x0; mov x0,#0x82000043; smc #0; ret` with the return discarded, and the
`usb flag: 2` printf goes to a console proven invisible in
`usb-entry-aquaman.md` §2.2. "works" is the absence of a visible error on a path
that cannot produce one. zero evidence in either direction about whether BL31
answered.

**"ROM in USB and failing, or BL31/reset transition stuck?"**

for two of the three legs, neither: the chip was never reset. `do_reset` is a
stub, the box sat in BL33 until a power cycle, and the ROM was never entered. no
BootROM, no BL31, no reset. why BL33 stopped answering is not pinned.

for the one real reset, ROM-in-USB-then-fail is close to eliminated — a ROM
sitting in its USB window holds `1b8e:c003` indefinitely with a host present
(round 3 §2.4 measured exactly that behaviour on the BL33 path), and a 4 ms poll
missed nothing. BL31/reset transition stuck is then the stronger of the two
proposed readings, but by elimination only, with no artifact behind it. `[F3]`
is the third reading and it was never instrumented.

**the power-cycle argument breaks down on legs 2 and 3.** round 3 §2.6 used
"only a power cycle brings it back" as evidence that the flag had been set.
GP_CFG7 is cleared by whoever writes it, not by a power cycle, and with no reset
there is no clear. that argument only survives on leg 1, which has no bus
watcher.

## 8. what would settle it, ranked

1. **read `0xc810025c` and `0xc810023c` from inside BL33, before and after the
   SMC.** `READ_MEM 0x02` already worked on `0xc810024c/50/54` (round 26 §1,
   live). if `GP_CFG7` does not change after `set_usb_boot 2`, item B is closed
   and the rest of this file is moot. one `oem`, two reads, no reset, no risk.
   **cheapest and most decisive thing available and it has never been done.**
2. **a 4 ms bus watcher around `oem reboot cold_boot`** — the one leg that
   touches the ROM and the only one with no coverage.
3. **a `oem reboot cold_boot` baseline with no `set_usb_boot 2` first.** if the
   baseline is also slow, the problem is the reset and the FORCE_USB_BOOT
   question is noise.
4. **`fastboot oem reboot bootloader` instead of `fastboot reboot`.** mode 7 via
   PSCI, the shortest real reset reachable from BL33.
5. the FID class map at `0xcb040` and the `std_svc_table` at `0xc5ec0` of the
   real BL31. blocked on the key. not needed for the diagnosis, only to close
   §3.1.

## 9. continuity

```text
BL33  0x37e607e8  do_set_usb_boot        (simple_strtoul base 16)
   -> 0x37e19efc  smc #0 x0=0x82000043 x1=2 x2=0x10
      -> BL31  UNKNOWN, secure-only, no handler in any artifact
         -> GP_CFG7[31] ?  UNKNOWN
            -> reset:  reboot <mode> -> smc 0x84000009 x1=mode&0xf -> BL31
                       -> GIC 0xc4302000 + SCP mailbox -> BL30
                       -> BL30 writes AO_SEC_SD_CFG15[15:12]
                       -> BootROM reads GP_CFG0[3:0] and GP_CFG7[31]
                          -> 1b8e:c003 as BL1        REFUTED
            -> BL33 again: 0x37e76510 is_tpl_loaded_from_usb()
               -> 0x37e765d8 -> 0x37e76588 smc(1) CLEAR -> optimus USB produce
                  -> 1b8e:c003 as BL33              NEVER OBSERVED
```

stops at "BL31 handler for 0x82000043". that is a key problem, not an analysis
problem, and round 30 closed it.
