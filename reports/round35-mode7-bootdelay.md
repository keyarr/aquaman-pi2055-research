# round35: `reboot bootloader` (mode 7) is `setenv bootdelay -1`. it is not a failure, it is a stop

date 2026-09-30. **offline, no device.** every address is out of
`reports/round14-bl33-persist/bl33-37e18000.bin` (the exact aquaman BL33, base
`0x37e18000`, sha-verified in round 13/14) and
`.src/u-boot-khadas/fip/gxl/bl31.bin` (family GXL reference, marked as family
every single time). no USB, no SMC, no reset, no execution of device code.

## 0. answer block

```text
  "logo aparece, USB nao aparece"                    = BY DESIGN, not a hang
  mode 7 means, in this build                        = stay in the U-Boot prompt
  the whole mechanism                                = setenv bootdelay -1
  set in                                             = do_get_rebootmode, 0x37e60618
  consumed by                                        = autoboot_command, 0x37e24500
                                                      cmn w19,#1 ; b.eq  (== -1)
  bootcmd ("run storeboot") ever runs on mode 7      = NO
  fastboot/USB entered on mode 7                     = NO, and it is never asked
  switch_bootmode has a branch for "bootloader"      = NO (6 branches, none is it)
  init_display has a branch for "bootloader"         = NO (same, it draws the logo)
  the logo is drawn BEFORE the gate                  = YES, init_display is inside
                                                      preboot, preboot runs first
  the 7 in the mode table is                         = 0x37e60730, mov w1,#7
  pre-SMC work specific to mode 7                    = NONE. literally none
  x1/x2/x3 at the SMC                                = 7 / 0 / 0, every mode
  AO_SEC_SD_CFG15[15:12] == 7 read by                = BL33 do_get_rebootmode
                                                      0x37e604a4, 15-entry table
                                                      at 0x37ebe910, decoded in full
  family BL31 special case for 7                     = NONE. only old-mode==8
                                                      triggers the usb-flag clear
  the aquaman BL31                                   = still UNAVAILABLE
  interaction with set_usb_boot 2 (0x82000043)       = NO EVIDENCE, and the
                                                      experiment is uninformative
  prior live test that already agrees                = round19 02-c2.md:25,
                                                      "adb reboot bootloader: device
                                                      left ADB, no fastboot appeared"
                                                      vs "adb reboot fastboot ->
                                                      18d1:0d02 back"
```

## 1. the mode 7 path, end to end, with the addresses

```text
  host            fastboot oem reboot bootloader
                  (also reachable: adb reboot bootloader -> kernel
                   drivers/amlogic/reboot/reboot.c:56 -> MESON_BOOTLOADER_REBOOT
                   -> smc 0x84000009 x1=7, identical call)

  BL33 0x37e60654 do_reboot                        13 strcmp, one chain
        0x37e60724 adrp/add 0x37ec62e9 = "bootloader"
        0x37e6072c bl strcmp
        0x37e60730 mov w1, #7          <-- the constant
        0x37e60734 cbz w0, 0x37e607c0
        ...every other case jumps into the same 0x37e607c0...

  BL33 0x37e607c0 THE TAIL, identical for all 13 modes, no branch at all:
        0x37e607c0 mov  x2, #0
        0x37e607c4 mov  x0, #9
        0x37e607c8 and  x1, x1, #0xf
        0x37e607cc mov  x3, x2
        0x37e607d0 movk x0, #0x8400, lsl #16     ; 0x84000009
        0x37e607d4 bl   0x37e19e98               ; aml_reboot
        0x37e607d8 mov  w0, #0                   ; return value discarded
        0x37e607e4 ret
```

**there is no pre-SMC work specific to mode 7.** not an AO write, not an RTC
poke, not a sticky register, not shared memory, not a delay. `x1` is masked
with `&0xf` and handed over. the only thing that differs between mode 0 and
mode 7 inside BL33 is the integer in `w1`. that answers §1 of the question
completely: mode 7 is literally `PSCI_SYSTEM_RESET(x1=7)` and nothing else.

the mode table, decoded from the strcmp chain (every entry confirmed by
reading the string at the adrp/add pair):

| argv[1] | x1 | string addr |
|---|---|---|
| `cold_boot` | 0 | 0x37ed24e4 |
| `normal` / no arg / unknown | 1 | 0x37ec028c |
| `recovery`, `factory_reset` | 2 | 0x37ec2a22, 0x37ec01b5 |
| `update` | 3 | 0x37ed9a19 |
| `fastboot` | 4 | 0x37edecfb |
| `suspend_off` | 5 | 0x37ed24ee |
| `hibernate` | 6 | 0x37ed24fa |
| **`bootloader`** | **7** | **0x37ec62e9** |
| `rpmbp` | 9 | 0x37ed253c |
| `crash_dump` | 11 | 0x37ed2514 |
| `kernel_panic` | 12 | 0x37ed251f |

matches `.src/u-boot-khadas/common/cmd_reboot.c:130-153` plus `rpmbp`, which
is the Xiaomi addition. 8, 10, 13, 14 are reachable on the read side only,
see §3.

## 2. what BL31 does with x1=7 (family, and the one thing it does not do)

`plat_psci_system_reset_hook` in `.src/u-boot-khadas/fip/gxl/bl31.bin` at file
offset `0x18ddc`:

```text
  0x018ddc  stp x29,x30,[sp,#-0x30]!
  0x018dec  mov x22, x0                 ; x22 = new_mode = 7
  0x018df0  bl  0x18b70                 ; is_bl30_started?
  ...clears HIU_MAILBOX_SET_0..3 and PREG_STICKY_REG2..5 (0xda834650..,
     0xc8834710..) when BL30 is not up yet. mode-independent...
  0x018ea4  mov x0,#0x25c ; movk x0,#0xda10,lsl#16   ; SEC_AO_SEC_GP_CFG7
  0x018eb0  and w19, w22, #0xf          ; <<<< the ONLY use of new_mode
  0x018eb4  ldr w1,[x0]
  0x018ec0  and w1,w1,#0xffff00ff       ; GP_CFG7[7:0] = 0
  0x018ec4  str w1,[x0]                 ; <<<< bit 31 NOT touched
  0x018ec8  mov x0,#0x1c ; movk x0,#0xda10,lsl#16   ; SEC_AO_RTI_STATUS_REG3
  0x018ed0  ldr w20,[x0]
  0x018ee4  ubfx x20,x20,#0xc,#4        ; old_mode = RTI_STATUS_REG3[15:12]
  0x018ee8  cmp w20,#8                  ; old_mode == 8 ?
  0x018eec  orr w19,w19,w2              ; w19 = (mode&0xf) | (old & ~0xf)
  0x018ef0  b.ne 0x018f0c
  0x018ef4  cmp x22,#0xc                 ; new_mode == 12 (kernel_panic) ?
  0x018ef8  b.eq 0x018f0c
  0x018f00  and w19,w19,#0xffff0fff      ; <<<< "bl31 clear usb flag"
  0x018f04  add x0,x0,#0x3f2 ; bl 0x23208
  0x018f24  str w19,[0xda10001c]        ; *** RTI_STATUS_REG3 = new mode ***
```

**no special case for 7.** the only conditional in the whole function is on
the *previous* mode being 8 and the *new* mode not being 12. mode 8 is
`shutdown_reboot` in the BL33 decode table (§3), so the semantics of the
"clear usb flag" branch are: coming out of a clean shutdown, wipe the low 12
bits of the reboot-reason register. mode 7 goes straight through.

`GP_CFG7[7:0]` is cleared, which is the ROM boot-device field. `GP_CFG7[31]`,
the FORCE_USB_BOOT bit, is **not** cleared here. that is the whole of the
AO-side work, and it is identical for modes 0, 4 and 7.

after that, `0x18d3c` is the GIC + SCP mailbox sender
(`0xc4302000`, then `mpidr_el1` into `0x19740` with `w1=3`), the same for
every mode. BL30/SCP performs the actual reset.

family evidence only. **the aquaman BL31 is still unavailable** (rounds
18/26/27/28/29/30, unchanged) and nothing above should be read as a claim
about the aquaman binary.

## 3. the read side, decoded: who consumes 7, and where

`AO_SEC_SD_CFG15` is `0xc810023c` (`secure_apb.h:1599`, `0x8f<<2`).
`AO_RTI_STATUS_REG3` is a *different* register, `0xc810001c`
(`secure_apb.h:1283`, `0x07<<2`). BL31 writes the new mode into
`RTI_STATUS_REG3`; BL33 reads it back from `SD_CFG15`. the copy between them
is still unlocated.

**correction to round 31 §4.3**: the claim that BL31 "polls SD_CFG15 at
0x1886c" and that therefore "BL30/SCP writes it" is wrong about what the poll
is. `0x1886c` is:

```text
  0x01886c  mov x0,#0x23c ; movk x0,#0xda10,lsl#16   ; SEC_AO_SEC_SD_CFG15
  0x018874  ldr w0,[x0]
  0x018878  ubfx x0,x0,#0x14,#2         ; [17:16]
  0x01887c  cmp w0,#3
  0x018880  b.ne 0x01886c               ; SPINS until == 3
```

that is a **BL30-ready handshake on [17:16]**, not the reboot mode. and
`SD_CFG15[15:12]` has no writer in any artifact we hold. RTI_STATUS_REG3 has a
writer (BL31). the bridge is still open, it just is not the one round 31
described.

BL33's reader is `do_get_rebootmode`, cmd_tbl at `0x37e60478`, and this is the
first time the decode table has been read out. the mode is a 4-bit field
expanded by a 15-byte jump table at `0x37ebe910`:

```text
  0x37e604a4  mov x0,#0x23c ; movk x0,#0xc810,lsl#16   ; AO_SEC_SD_CFG15
  0x37e604ac  ldr w20,[x0]
  0x37e604b0  ubfx x20,x20,#0xc,#4      ; [15:12]
  0x37e604b4  cmp w20,#0xe
  0x37e604b8  b.hi 0x37e605dc            ; >14 -> "charging"
  0x37e604bc  adrp x0,#0x37ebe000 ; add x0,#0x910
  0x37e604c4  ldrb w1,[x0,w20,uxtw]     ; 15 signed byte offsets
  0x37e604cc  add x1,x2,w1,sxtb #2 ; br x1
```

| SD_CFG15[15:12] | string | set into env `reboot_mode` |
|---|---|---|
| 0 | `cold_boot` | 0x37ed24e4 |
| 1 | `normal` | 0x37ec028c |
| 2 | `factory_reset` | 0x37ec01b5 |
| 3 | `update` | 0x37ed9a19 |
| 4 | `fastboot` | 0x37edecfb |
| 5 | `suspend_off` | 0x37ed24ee |
| 6 | `hibernate` | 0x37ed24fa |
| **7** | **`bootloader`** | 0x37ec62e9 |
| 8 | `shutdown_reboot` | 0x37ed2504 |
| 9 | `rpmbp` | 0x37ed253c |
| 10 | `recovery_quiescent` | 0x37ed2542 |
| 11 | `crash_dump` | 0x37ed2514 |
| 12 | `kernel_panic` | 0x37ed251f |
| 13 | `watchdog_reboot` | 0x37ed252c |
| 14 | `recovery_quiescent` | 0x37ed2542 |
| >14 | `charging` | 0x37ed2555 |

this is the full 15-entry answer to "what can be written into [15:12]", and
it is a strict superset of what the write side can produce. it also corrects
the family header: `arch/arm/include/asm/reboot.h:41-53` in the tree has
no 8, 10, 13, 14, and the aquaman build adds 9 (`rpmbp`) and 13
(`watchdog_reboot`).

## 4. THE ANSWER: 7 is not a stage selector, it is a countdown killer

this is the part nobody had looked at. `common/cmd_reboot.c:105-116` in the
family has a second `switch` under `CONFIG_CMD_FASTBOOT`, and it is compiled
into the aquaman BL33:

```text
  0x037e605dc  (mode > 14, so not us, but the block is shared)
  0x37e605ec  cmp w20, #4
  0x37e605f0  b.eq 0x37e60600
  0x37e605f4  cmp w20, #7
  0x37e605f8  b.eq 0x37e60610           ; <<<<<< MODE 7 LANDS HERE
  0x37e605fc  b   0x37e60624
  0x37e60600  adrp x1,#0x37ede000 ; add x1,#0xcfb     ; "fastboot"
  0x37e60608  add x0,reboot_mode ; b 0x37e60620        ; redundant setenv
  0x37e60610  adrp x0,#0x37ebf000
  0x37e60618  add x0,x0,#0xfbb                          ; "bootdelay"
  0x37e6061c  add x1,x1,#0x55e                          ; "-1"
  0x37e60620  bl  0x37e5848c                            ; setenv("bootdelay","-1")
  0x37e60624  adrp x0,#0x37ed0000 ; add x0,#0x22e       ; "rpmb_state"
  0x37e60630  bl  0x37e5e968                            ; run_command("rpmb_state",0)
  0x37e6063c  str w0(=1),[0x37f88330]                   ; "already resolved" flag
```

strings confirmed at those addresses: `0x37ebffbb` = `bootdelay`,
`0x37ed255e` = `-1`. the `bootdelay` string has exactly two xrefs in the
whole image: `0x37e60618`, which writes it, and `0x37e2448c`, which reads
it. nothing else in BL33 can override it between the two.

**`mode 7 == setenv bootdelay -1`.** that is the entire semantic. `mode 4`
just re-sets `reboot_mode`, it does not touch `bootdelay`.

### 4.1 who reads it, and when

the read side is `main_loop`, and it is in the image at `0x37e22328`:

```text
  0x37e22328  stp x29,x30,[sp,#-0x10]!              ; main_loop
  0x37e22330  mov w0,#0xa2 ; bl 0x37e22324
  0x37e22338  bl 0x37e5ea98                          ; cli_init()
  0x37e2233c  adrp x0,#0x37ebf000 ; add x0,#0xd1a     ; "preboot"
  0x37e22344  bl 0x37e58920                          ; env_get("preboot")
  0x37e22348  cbz x0, 0x37e22358
  0x37e22354  bl 0x37e5e980                          ; run_command_list(preboot)
  0x37e22358  bl 0x37e24480                          ; bootdelay_process()
  0x37e2235c  bl 0x37e244dc                          ; autoboot_command()
  0x37e22364  b  0x37e5ea88                          ; cli_loop()
```

**`preboot` runs BEFORE `bootdelay_process()`.** that ordering is the whole
trick, and it is byte for byte `common/main.c:73-118` in the family tree, so
it is not a Xiaomi change.

`bootdelay_process`, `0x37e24480`:

```text
  0x37e2448c  add x0,x0,#0xfbb                       ; "bootdelay"
  0x37e24494  bl 0x37e58920                          ; env_get
  0x37e24498  cbz x0, 0x37e244b0
  0x37e244a0  mov w2,#0xa
  0x37e244a4  bl 0x37eac374                          ; simple_strtoul(base 10)
  0x37e244b0  mov w19,#1                             ; default
  0x37e244b4  add x0,x0,#0xfc5                       ; "bootcmd"
  0x37e244bc  bl 0x37e58920
  0x37e244c4  adrp x1,#0x37f72000 ; add x1,#0x3d8
  0x37e244cc  str w19,[x1]                           ; stored_bootdelay = -1
```

`autoboot_command`, `0x37e244dc`, the gate:

```text
  0x37e244f8  ldr w19,[0x37f723d8]                   ; stored_bootdelay
  0x37e24500  cmn w19, #1                            ; == -1 ?
  0x37e24504  b.eq 0x37e245f4                         ; YES -> skip bootcmd
  0x37e24508  cbz x21, 0x37e245f4                    ; bootcmd missing -> skip
  ...                                            ; else abortboot() countdown
```

byte for byte `common/autoboot.c:291`:
`if (stored_bootdelay != -1 && s && !abortboot(stored_bootdelay))`.

so on mode 7, `run storeboot` **never executes**. `main_loop` falls into
`cli_loop()`: the U-Boot prompt, forever, no gadget, no kernel, no Android.

### 4.2 why the logo is on screen while this happens

the default env in the image (this is the compiled `env`, and the whole
string is at `0x37eb65d2`):

```
preboot=run cmdline_keys;run bcb_cmd; run factory_reset_poweroff_protect;
run upgrade_check;run init_display;run storeargs;bcb uboot-command;
run switch_bootmode;
```

and `init_display` (0x37eb7aa9), which is called from inside preboot, i.e.
**before** the `cmn` gate:

```
init_display=get_rebootmode;echo reboot_mode:::: ${reboot_mode};
  if test ${reboot_mode} = quiescent; then ...
  else if test ${reboot_mode} = recovery_quiescent; then ...
  else setenv reboot_mode_android normal;run storeargs;
       osd open;osd clear;imgread pic logo bootup $loadaddr;
       bmp display $bootup_offset;bmp scale; fi;fi;
```

`init_display` calls `get_rebootmode` first (that is where `bootdelay=-1` is
set), then blits the `logo` partition's `bootup` image to the framebuffer.
`logo.img` is a real 916352 byte partition in this repo. so the sequence the
operator sees is:

1. reset really happens (PSCI, mode 7)
2. BL33 boots, runs preboot
3. `get_rebootmode` sees `SD_CFG15[15:12] == 7`, sets `reboot_mode` and
   `bootdelay=-1`
4. `init_display` paints the boot logo
5. preboot finishes
6. `bootdelay_process` reads `-1`
7. `autoboot_command` skips `bootcmd`
8. U-Boot prompt, no USB gadget, no Android

**the logo is not evidence that the kernel ran.** it is evidence that BL33
ran, which is a different claim, and it is drawn before the gate that stops
the boot.

### 4.3 the "no USB" is structural, not a USB bug

three things start a USB gadget in this image, and none of them runs on
mode 7:

| entry point | what it gives | runs on mode 7 |
|---|---|---|
| `fastboot` cmd, 0x37e3a840 -> 0x37e94a04 | `18d1:0d02` | only from `switch_bootmode` mode 4 |
| `usb start 0` in `factory_reset_poweroff_protect` / `update` | udisk recovery | no, those are mode 2/3 or `wipe_*=failed` |
| v2 burning control request, gated on `PREG_STICKY_REG2` (0xc88345c8) == `0x1b8ec003`/`0x1b8ec004` -> `aml_burn_check_is_ready_for_burn` 0x37e765d8 -> `is_tpl_loaded_from_usb` 0x37e76510 | `1b8e:c003` | no, never reached without `bootcmd` |

and `switch_bootmode` (0x37eb6eab), which is the script that decides the next
stage, has exactly these branches:

```
switch_bootmode=get_rebootmode;
  if   reboot_mode = factory_reset         -> storeargs; recovery_from_flash
  elif reboot_mode = update                -> storeargs; update
  elif reboot_mode = quiescent             -> storeargs; androidboot.quiescent=1
  elif reboot_mode = recovery_quiescent    -> storeargs; quiescent; recovery_from_flash
  elif reboot_mode = cold_boot             -> storeargs
  elif reboot_mode = fastboot              -> storeargs; fastboot
  fi;fi;fi;fi;fi;fi;
  if monitor_bt_cmdline; then run update; fi;
```

six branches. **`bootloader` is not one of them.** neither is it in
`init_display`. mode 7 falls through all of them, and the only thing that
changes versus `cold_boot` is that `bootcmd` is then skipped.

`bootloader` has 20 code xrefs in BL33 and every one of them is either the
`bootloader` *partition* (`amlmmc erase bootloader`, `bootloader-boot0/1`) or
the fastboot getvar name (`version-bootloader`, `bootloader-version`,
`has-slot:bootloader`). there is no `reboot_mode == "bootloader"` test
anywhere in the image, in code or in script. the only code xref to the
`reboot_mode` string itself is `0x37e24eb8` in `do_bootm`, and that block
only appends `defendkey=%x,%x,` to bootargs for `recovery`, `update`,
`factory_reset` or `upgrade_step == 3`. `bootloader` is not in it.

**so, explicitly answering "should `reboot bootloader` give fastboot/USB in
this build?" — no. by design it should not.** `bootloader` means "drop to the
U-Boot prompt and wait for a human", which is why it coexists with
`bootdelay=-1`. the only bootloader this firmware expects here is the one on
the UART console (`console=ttyS0,115200`, `earlycon=aml_uart,0xc81004c0` in
`initargs`), and this stick has no UART header exposed. the stick has no
recovery button either (round 2 report:45), so mode 7 is close to a dead
end by design: it is the software equivalent of the physical button combo,
reachable with no way to use it.

## 5. mode 0 vs mode 4 vs mode 7, static comparison

| | mode 0 `cold_boot` | mode 4 `fastboot` | mode 7 `bootloader` |
|---|---|---|---|
| `x1` at `0x84000009` | 0 | 4 | 7 |
| `x2`, `x3` | 0, 0 | 0, 0 | 0, 0 |
| BL33 work before the SMC | none | none | none |
| BL31 `RTI_STATUS_REG3[15:12]` | 0 | 4 | 7 (family) |
| BL31 `GP_CFG7[7:0]` | -> 0 | -> 0 | -> 0 (family) |
| BL31 `GP_CFG7[31]` | untouched | untouched | untouched (family) |
| BL31 per-mode branch | none | none | **none** |
| BL30/SCP | mailbox, mode-agnostic | same | same |
| BootROM-visible mode | 0 | 4 | 7 |
| BL33 `reboot_mode` env | `cold_boot` | `fastboot` | `bootloader` |
| BL33 `bootdelay` env | `1` (default) | `1` (default) | **`-1`** |
| `switch_bootmode` branch | `storeargs` | `storeargs; fastboot` | **none** |
| gadget started | no | yes, `18d1:0d02` | no |
| `bootcmd` runs | yes | yes (fastboot never returns) | **no** |
| kernel reached | yes | no | no |
| USB seen by the host | `2717:4e40` after ~17.5 s | `18d1:0d02` in ~3-5 s | **nothing** |
| screen | logo, then Android | logo | **logo, forever** |

the *reset* half of the three is byte-identical. every difference in the
table lives in BL33 **after** the reset, in the countdown gate.

## 6. the experiment matrix, with only what is actually known

| | no `set_usb_boot 2` | with `set_usb_boot 2` |
|---|---|---|
| `cold_boot` (0) | **17.5 s -> `2717:4e40`** (C0, `reports/c0-usbwatch.log`) | **885 s, zero USB, power-cycle only** (F2, `reports/f2-usbwatch.log`) |
| `bootloader` (7) | **logo, no USB, no Android** (operator; consistent with round19 02-c2.md:25) | not tested, and see below |
| `fastboot` (4) | **`18d1:0d02` in 5.6 s** (C0 session, same watcher, same build) | not tested |
| `normal` (1) | not tested | not tested |

`adb reboot bootloader` (round19 02-c2.md:25) and `fastboot oem reboot
bootloader` (BL33) are the same PSCI call, so the first cell is covered by
two independent tests.

**the `bootloader` x `set_usb_boot 2` cell is worthless and should not be
run.** reason, from code: mode 7 stops at `0x37e24504` before `bootcmd`
runs, and the only BL33 consumer of `GP_CFG7[31]`
(`is_tpl_loaded_from_usb`, 0x37e76510) is reachable only from
`aml_burn_check_is_ready_for_burn` (0x37e765d8), which is reached only from
the two `PREG_STICKY_REG2` v2-burning sites at `0x37e21d24` and
`0x37e22200`. neither runs. so the flag cannot change the observable outcome
of mode 7 whether it lands in `GP_CFG7[31]` or not. it would reproduce
"logo, no USB" and teach us nothing.

## 7. relation with `set_usb_boot 2` (0x82000043)

**no evidence of interaction, and one positive argument against a
mechanical one.**

- the two never meet in BL33. `0x82000043` has exactly two callers
  (`0x37e60838`, the `set_usb_boot` handler, and `0x37e76594`, the CLEAR path
  inside the burning check) and neither is on the mode 7 path.
  `do_reboot` issues `0x84000009` and nothing else.
- the only BL31 code we hold, family, has no `0x82000043` literal at all, so
  there is no handler to compare against the reset hook. the aquaman BL31 is
  unavailable. **this is a key problem, not an analysis problem, and it
  stands.**
- in the family reset hook, mode 7 takes the identical path as mode 0 and
  mode 4. if `0x82000043` set some bit that the reset hook cleared, the hook
  clears `GP_CFG7[7:0]` only, and the RTI_STATUS_REG3 write is unconditional.
- the family *does* have a "clear usb flag" path, and mode 7 walks straight
  into it if the previous mode was 8: `0x18ef4` compares the new mode against
  12 only. 7 is not 12, so a `shutdown_reboot` -> `bootloader` transition
  would clear `RTI_STATUS_REG3[11:0]`. whether that state is the thing
  `set_usb_boot 2` sets is UNKNOWN and unknowable from here.

so: nothing in the static evidence ties `0x82000043(x1=2)` to
`0x84000009(x1=7)`, and the one experiment that would look for it is
confounded as shown in §6. drop it from the plan.

## 8. the logo-but-no-USB question, graded

| stage | verdict | basis |
|---|---|---|
| BootROM runs and falls into a stage with no USB | **REFUTED** | the logo is blitted by BL33 `init_display` (`imgread pic logo bootup`, `bmp display`), which is BL33-only. `round2 08_usb_journal` and round 3 already established `1b8e:c003` is BL33, not the ROM. |
| BL33 runs but does not init USB | **CONFIRMED, and deliberate** | `0x37e24500 cmn w19,#1 ; b.eq` skips `bootcmd`. no gadget init is requested. |
| some boot mode deliberately leaves USB off | **THIS IS THE ANSWER** | mode 7 -> `setenv bootdelay -1` at `0x37e60618` -> `stored_bootdelay == -1` -> no `bootcmd`. it is a designed stop, not an omission. |
| BL31/BL30 do the reset right but pick another path | **REFUTED for the visible part** | the family hook is mode-agnostic except the old-mode-8 usb clear. the mode does reach BL33 intact, since BL33 reads it back as 7. |
| Linux/Android runs and does not init USB | **REFUTED** | the kernel gets `androidboot.reboot_mode=bootloader` in bootargs but is never handed control. `bootcmd` did not run, so `bootm` did not run. |
| a bootloader routine is stuck before USB init | **REFUTED as a hang** | nothing is stuck. `cli_loop()` is a working prompt. |

and the classification the question asked for:

- **COMPROVADO PELO CÓDIGO**: mode 7 is `PSCI(x1=7)` with zero pre-work;
  `do_get_rebootmode` sets `bootdelay=-1` on mode 7; `main_loop` runs preboot
  before `bootdelay_process`; `autoboot_command` skips `bootcmd` on -1;
  `switch_bootmode` and `init_display` have no `bootloader` branch; the logo
  is drawn from inside preboot; the SD_CFG15[15:12] decode table including
  7 -> `bootloader`; the family BL31 hook has no special case for 7.
- **COMPROVADO PELO TESTE**: mode 7 leaves the stick off the bus with no
  fastboot and no Android (operator, plus round19 02-c2.md:25);
  `adb reboot fastboot` -> `18d1:0d02` back (same session);
  `cold_boot` -> `17.5 s` -> `2717:4e40` (C0).
- **INFERÊNCIA FORTE**: the operator's "logo" is the U-Boot `init_display`
  blit, not the kernel splash. the two are near-identical on a Xiaomi stick
  and this is the one place where the distinction matters. the supporting
  fact is that the kernel is never reached at all, so the kernel splash
  cannot be what is on screen.
- **HIPÓTESE**: the live env partition matches the compiled default env
  (`preboot` contains `run init_display`, `bootdelay=1`, and a
  `switch_bootmode` without a `bootloader` branch). nothing in the image
  contradicts it and the behaviour fits it, but the env is writable and was
  not read. §9 closes it for one command.

## 9. next experiment, minimal, read-only where possible

three, in this order. none writes, none uses RUN_IN_ADDR, none is
destructive. all three are `fastboot oem`, which round 14 §3 established is a
host-driven `run_command` and is not lock-gated.

1. **`fastboot oem printenv preboot`** and **`fastboot oem printenv bootdelay`**
   and **`fastboot oem printenv switch_bootmode`**, from a clean cold boot.
   read-only, no reset. this is the only thing standing between the answer
   above and "COMPROVADO PELO TESTE" for the env half. expected: `bootdelay=1`,
   a `preboot` containing `run init_display`, and a `switch_bootmode` with six
   branches and no `bootloader`.
2. **`fastboot oem reboot fastboot` under `tools/usb_watch.py`.** expected
   `18d1:0d02` in 3-5 s. it is the direct A/B that separates "mode 7 is
   special" from "every reboot is silent", and the C0 session already shows
   the gadget coming up in 5.6 s in this exact build, so a failure here would
   be a real finding rather than a surprise.
3. **`fastboot oem reboot normal` under the watcher.** expected `17.5 s` ->
   `2717:4e40`, identical to `cold_boot`, because `switch_bootmode` has no
   `normal` branch either. that closes the "is it the mode or is it the reset
   path" question with a mode that shares mode 7's lack of a branch but not
   its `bootdelay` clobber.

skip entirely: `set_usb_boot 2` combined with mode 7 (§6, confounded), and
anything that touches AO registers, which is where the risk actually is.

## 10. ledger

```text
  mode 7 == "stay in the U-Boot prompt"                       CODE
  the mechanism is setenv bootdelay -1                         CODE
  it is not fastboot, and never was in this build              CODE
  the logo is the U-Boot init_display blit                     CODE + INFERENCE
  no USB is structural, three gadget entry points, none runs   CODE
  nothing before the PSCI differs between mode 0 and mode 7    CODE
  the family BL31 has no special case for 7                    FAMILY CODE
  the aquaman BL31's handling of 7                             UNAVAILABLE
  SD_CFG15[15:12] has no known writer, RTI_STATUS_REG3 does     (corrects r31 4.3)
  the SD_CFG15 <-> RTI_STATUS_REG3 copy                         UNKNOWN, still open
  0x82000043 and mode 7 interact                                NO EVIDENCE
  the live env matches the compiled default                     UNTESTED, 1 read closes it
  mode 7 is recoverable                                         INFERENCE: bootdelay is
                                                               volatile, not saved;
                                                               a power cycle restores 1
```

round 31's §8 item 4 ("`fastboot oem reboot bootloader`") was the right test
to run and the right way to run it. it just was not read against the boot
script, which is where the answer was sitting the whole time.
