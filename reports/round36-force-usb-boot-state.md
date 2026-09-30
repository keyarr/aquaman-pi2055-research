# round36: the FORCE_USB_BOOT state is `AO_RTI_STATUS_REG3`, consumed by BL2

date 2026-09-30. **static only, no device I/O.** every address below is read out
of `.src/u-boot-khadas/fip/gxl/{bl2,bl30}.bin` and `fip/{gxl,gxb,axg,txl,txlx}/bl31.*`,
which are **plaintext, unstripped** family binaries that this repo already had on
disk and that nobody had opened. `fip/gxl/bl2.bin` is AArch64 with full printf
strings. `fip/gxl/bl30.bin` is Thumb Cortex-M3, an RTOS, with full strings. that
is the whole reason this round exists: round 31 called the BL31 side
"cryptographically closed" and then went no further, while the two plaintext
siblings that sit either side of it were never disassembled.

new tool: `tools/family_stage_dump.py` (annotated dump of bl2/bl30/bl31, resolves
literal pools and string refs).

## 0. answer block

```text
  the real FORCE_USB_BOOT state   = AO_RTI_STATUS_REG3   0xc810001c / 0xda10001c
  the "usb flag" field            = [11:8]               named by the vendor's own
                                                          string: "bl31 clear usb flag"
  the boot-decision field         = [15:12]              value 2 == force usb boot,
                                                          hardcoded in BL2
  the boot-mode field             = [3:0]                0 cold, 1 normal, 7 bootloader
  who writes it                   = BL31, on the SMC 0x82000043          setter not
                                                          recoverable, see §3
  who clears it                   = BL31 reset hook, BL2 "Skip usb!", BL30 pre-reset
  who CONSUMES it                 = BL2, 0x79b4 and 0x820                FIRST consumer
  the other consumer              = BL30, moves [3:0] -> SD_CFG15[15:12]
  GP_CFG7[31]                     = gpio pad 23 output state. not a boot flag.
                                    that is why F1 read 0.  CLOSED, wrongly suspected
  GP_CFG0[3:0]                    = the real ROM boot-device id (1=eMMC).
                                    romboot.h's "[31:28]" comment is stale  CORRECTED
  the aquaman's own bl30/bl2      = unrecoverable. bootloader.img is H=8.00 uniformly
  force-usb-boot into USB         = BL2 dev 5 or RTI[15:12]==2 -> "BL2 USB" branch
  and it ALSO kills the eMMC path = bl2_get_boot_device() returns 6, which matches
                                    neither 1 nor 2 at 0x850. no storage is inited.
```

## 1. the finding that made the rest possible

`fip/gxl/bl2.bin` and `fip/gxl/bl30.bin` have been sitting in `.src/u-boot-khadas/fip/`
since round 7 and were only ever stat'd and hashed. they are not encrypted:

```text
  fip/gxl/bl2.bin    38336 B   99 strings   "USB mode!"  "Skip usb!"  "BL2 USB "
                                           "STICKY_REG0: 0x"  "fip header"
                                           "aml log : SIG CHK : "
  fip/gxl/bl30.bin   38788 B  287 strings   "system cmd  %d."  "cfg15 %x "
                                           "mb receive secure interrupt 0x%x"
                                           "write stick mem bad index=%d!"
```

BL2 is the code the BootROM jumps to. it is the closest thing to the ROM that
exists in plaintext anywhere, and it contains the boot-source decision verbatim.

## 2. `AO_RTI_STATUS_REG3` decoded, from three independent binaries

### 2.1 BL31 writes it, and names the field

`fip/gxl/bl31.bin`, the PSCI system-reset hook at `0x18ddc`. x0 = new mode:

```text
  0x018df0  bl  0x18b70                 ; scp ready?
  ...                                     ; 0xda834650..5c / 0xc8834710..1c = -1 or 0
  0x018dfc  bl  0x18944 ; cmp w0,#0x21   ; spin until chip id reads back
  0x018ea4  x0 = 0xda10025c             ; SEC_AO_SEC_GP_CFG7
  0x018eb0  and  w19, x22, #0xf         ; w19 = new_mode & 0xf
  0x018ec0  and  w1, w1, #0xffff00ff    ; GP_CFG7[7:0] = 0
  0x018ec4  str  w1, [x0]
  0x018ec8  x0 = 0xda10001c             ; SEC_AO_RTI_STATUS_REG3
  0x018ed0  ldr  w20, [x0]
  0x018ed4  printf("bl31 reboot reason: 0x%x", w20)
  0x018ee0  and  w2, w20, #0xfffffff0   ; keep [31:4] as-is
  0x018ee4  ubfx x20, x20, #0xc, #4     ; reason = [15:12]
  0x018ee8  cmp  w20, #8
  0x018eec  orr  w19, w19, w2           ; w19 = mode | (old & ~0xf)
  0x018ef0  b.ne 0x18f0c
  0x018ef4  cmp  x22, #0xc              ; new_mode != 12 (kernel_panic)?
  0x018ef8  b.eq  0x18f0c
  0x018f00  and  w19, w19, #0xffff0fff  ; <<<< CLEAR [11:8]
  0x018f04  add  x0, x0, #0x3f2
  0x018f08  bl   printf                 ; prints "bl31 clear usb flag"
  0x018f18  x0 = 0xda10001c
  0x018f24  str  w19, [x0]              ; <<<< the only write
```

the sibling system-off hook at `0x18c74` is the same code with the mask
`mov w1, #-0xf010` / `and w19, w21, w1`, i.e. it clears `[3:0]` **and** `[11:8]`
and then forces `[3:0] = 8`. identical in gxb, at `0x4d0` and `0x528`, so this
is not a gxl quirk.

**`[11:8]` is the field the vendor calls the "usb flag". that is the vendor's own
word for it, in a string literal, in two SoC generations.** this is the closest
thing to a proof you can get without the setter.

### 2.2 BL30 moves `[3:0]` into the ROM register, and clears `[11:8]`

`fip/gxl/bl30.bin`, the boot-mode handoff at `0x10001cb8`:

```text
  0x10001cb8  ldr  r3, =0xc8100120 ; bic #0x2040000 ; str      ; clear [25:22]+[21]
  0x10001cc2  r3 = 0xda10001c      ; SEC_AO_RTI_STATUS_REG3
  0x10001cc4  r2 = 0xda10023c      ; SEC_AO_SEC_SD_CFG15
  0x10001cca  and  r1, r1, #0xf                    ; RTI[3:0]
  0x10001cce  bic  r0, r0, #0xf000                 ; SD_CFG15[15:12] = 0
  0x10001cd2  orr  r1, r0, r1, lsl #12            ; SD_CFG15[15:12] = RTI[3:0]
  0x10001cd6  str  r1, [r2]
  0x10001cda  bic  r2, r2, #0xf ; str              ; RTI[3:0] = 0
  0x10001ce2  orr  r2, r2, #0xd ; str              ; RTI[3:0] = 0xd  (consumed)
```

three independent pool resolutions land on real registers at `0x10001cec`,
`0x10001cf0` and `0x10001cf4`, so the alignment is not a guess.

this closes round 35's open item. **`SD_CFG15[15:12]`, the 15-entry reboot-mode
table that BL33's `do_get_rebootmode` decodes, is written by BL30, and its source
is `RTI_STATUS_REG3[3:0]`.** the three-hop handoff round 31 described
(`BL33 -> BL31 -> BL30 -> SD_CFG15`) is real, and the BL31->BL30 leg is the
`RTI[3:0]` field.

two more BL30 writes, both in the pre-reset sequence:

```text
  0x100054ca  cfg15 = *SD_CFG15
  0x100054da  SD_CFG15 &= ~0xf0000000
  0x100054e4  SD_CFG15 |=  r8 << 28          ; r8 = *0x1000d600, the reboot reason
                                             ; handed over by BL31 in shared RAM
  0x10005550  RTI_STATUS_REG3 &= ~0xf00      ; <<<< clears the usb flag before reset
  0x1000555c  bl 0x100035c0                  ; the real reset
```

so **`SD_CFG15[31:28]` is the reboot reason** and **`SD_CFG15[15:12]` is the boot
mode**, both stamped by BL30 immediately before it resets the chip. that is the
complete `SD_CFG15` map, and it explains why round 35's `[15:12]` table decoded
cleanly.

### 2.3 BL2 is the consumer, and the gate is `[15:12] == 2`

`fip/gxl/bl2.bin`, `0x820`:

```c
uint32_t bl2_get_boot_device(void)                 // 0x820
{
    if (((*(volatile u32 *)0xda10001c >> 12) & 0xf) == 2)
        return 6;                                  // <<<< override
    return *(volatile u32 *)0xda100240 & 0xf;      // SEC_AO_SEC_GP_CFG0[3:0]
}
```

`fip/gxl/bl2.bin`, `0x79b4`, the USB gate:

```text
  0x000079bc  x0 = 0xda10001c ; ldr w19, [x0]     ; RTI_STATUS_REG3
  0x000079cc  bl  0x820                           ; boot_device
  0x000079d0  cmp x0, #5
  0x000079d4  ubfx x20, w19, #0xc, #4             ; RTI[15:12]
  0x000079d8  b.eq 0x79e4                         ; dev == 5 -> usb
  0x000079dc  cmp w20, #2
  0x000079e0  b.ne 0x7c44                         ; <<<< RTI[15:12] != 2 -> skip
  0x000079e4  printf("BL2 USB \n")
```

and the skip path, `0x7c44`:

```text
  0x00007c44  cmp  w20, #1          ; RTI[15:12] == 1 (the normal value)?
  0x00007c48  b.ne 0x7ccc
  0x00007c4c  printf("Skip usb!\n")
  0x00007c58  and  w19, w19, #0xffff0fff   ; clear the usb flag [11:8]
  0x00007c64  orr  w19, w19, #0x2000       ; set bit 13 -> reason 1|2 = 3
  0x00007c68  str  w19, [0xda10001c]       ; "tried usb, did not take"
```

`BL2 USB `, `Skip usb!`, and a hardcoded `cmp w20, #2` against
`RTI_STATUS_REG3[15:12]`, in the same function, in plaintext. **the vendor's
`FORCE_USB_BOOT = 2` enum value and the reason value BL2 tests for are the same
number 2, and the field BL2 reads is the field BL31 stamps on reset.**

## 3. the one thing that is still not recoverable, stated exactly

the FID class map and the Amlogic handler bodies are **not in any bl31 file in
the tree, for any of the six SoC generations present.** this is now measured, not
assumed:

```text
  file            dispatcher  handler table  class map   the 4 handlers
  axg/bl31.img    0x0d3a8     0x12a50        0xb6730 OUT  0x05100340 0x051099ac
                                                            0x0510b39c 0x0510b39c
  gxb/bl31.bin    0x0f9d4     0x13068        0xbbd80 OUT  0x05101008 0x0510c1c4
                                                            0x0510da9c 0x0510da9c
  gxl/bl31.bin    0x24cac     0x2a2c8        0xcb040 OUT  0x05119d78 0x05121418
                                                            0x05122d4c 0x05122d4c
  gxtvbb/bl31.bin  == gxb byte identical
  txl/bl31.bin    0x24be4     0x2a1e0        0xcb040 OUT  0x05119db4 0x05121354
                                                            0x05122c88 0x05122c88
  txlx/bl31.bin   0x0ea20     0x14188        0xb7590 OUT  0x05100340 0x0510b220
                                                            0x0510cc10 0x0510cc10
```

every one points into a second blob at `0x05100000` that no `fip/*/bl31.*` file
contains, and every class map is past EOF. the dispatcher itself is fully
recovered from gxb, and it is plain TF-A:

```text
  0x0f9ac  ubfx x16, x0, #0x18, #6    ; FID[29:24]
  0x0f9b0  ubfx x15, x0, #0x1f, #1    ; FID[31]
  0x0f9b4  orr  x16, x16, x15, lsl #6 ; index = FID[29:24] | FID[31]<<6
  0x0f9b8  adr  x11, #0x13068          ; 4-entry handler table
  0x0f9bc  adr  x14, #0xbbd80          ; 128-byte FID class map   <-- MISSING
  0x0f9c0  ldrb w15, [x14, x16]
  0x0f9c8  tbnz w15, #7, #0xfa1c       ; class >= 0x80 -> return -1
  0x0f9d4  ldr  x15, [x11, w15, lsl #5]
  0x0f9f4  blr  x15
```

so for `0x82000043` the index is `(0x82 & 0x3f) | (1 << 6)` = **`0x42`**, and
`0x84000009` (PSCI) lands on `0x44`. **if the class-map blob at `0x05100000`
ever becomes available, one byte at index 0x42 names the handler and closes this
completely.** nothing else is missing on the dispatch side.

**the setter, `x1 = 2 -> which bits`, is inside that blob and is therefore not
in this report.** no handler was invented. what is in this report is the clear
path, the cross-stage transport, and the consumer, all in plaintext.

## 4. `GP_CFG7[31]` is a gpio pad, and that is the whole F1 null

`fip/gxl/bl30.bin`, `0x10004680` and `0x100048fc`/`0x10004904`, the AO pin
drivers:

```text
  0x100046a2  and  ip, ip, #0xff        ; ip = pin index
  0x100046ae  add  r7, ip, #0x10
  0x100046b2  add  r6, ip, #8
  0x100046bc  lsls r0, r5               ; r0 = 1 << (pin+1)
  0x100046be  lsl  ip, r5, ip           ; ip = 1 << pin
  0x10004712  0xc8834664 |= 1 << (pin+0x10)
  0x1000471a  0xc810025c  = *0xc810025c | (1 << (pin+8))     <<<< GP_CFG7[8+pin]
  ...
  0x1000476e  0xc810025c  = *0xc810025c & ~(1 << (pin+8))
```

`GP_CFG7[8:31]` is a 24-entry gpio output-state array. `GP_CFG7[31]` is pad 23's
output latch. it is written by the pinmux driver and by nothing else in the whole
of BL30, and the only other uses in BL30 are two `tst #0x40000000` assertions,
i.e. `GP_CFG7[30]` as the efuse-burned flag (`0x10000e08`, `0x10004b2c`).

this is why round 34's F1 read 0, and it also means **BL33's
`is_tpl_loaded_from_usb()` at `0x37e76510` is half wrong on gxl**: its
`GP_CFG0[3:0] == 5` half is the real check, its `GP_CFG7[31]` half reads a gpio
latch. round 31 already saw that the bl31 bit-set helper writes `1 << (idx+8)`
and speculated `idx = 23`; that is confirmed to be the pin array, so bl31 writing
bit 31 through that helper would be immediately undone by the next pinmux
operation on pad 23. **the vendor's own "force usb boot" read path is dead code
on this silicon.** that is a defect in Amlogic's u-boot, not a lead.

correction to `romboot.h`, whose comment says `GP_CFG0[31:28] = boot device id`:
on gxl the boot device is `GP_CFG0[3:0]`, confirmed by BL2 `0x844` and by
BL33 `_get_romcode_boot_id()`, and confirmed live: F1 read `GP_CFG0[3:0] == 1`,
`BOOT_ID_EMMC`, and the stick boots from eMMC. the header comment is stale.

## 5. the full reset chain, both modes

```text
  BL33  reboot <mode>                       0x37e607d4
   |  SMC 0x84000009  x1 = mode & 0xf       cold 0  normal 1  recovery 2  update 3
   v                                        fastboot 4  bootloader 7  panic 12
  BL31  psci_system_reset_hook(mode)        gxl bl31 0x18ddc
   |  GP_CFG7[7:0]   = 0
   |  RTI[3:0]       = mode
   |  RTI[31:4]      = preserved
   |  if (RTI[15:12] == 8 && mode != 12) RTI[11:8] = 0    "bl31 clear usb flag"
   v
  BL31 -> BL30  HIU secure mailbox, cmd 0x08 sub 1     bl30 0x100026bc dispatch
   |  gpio all low, pin 1 high                         bl30 0x100038c8
   v
  BL30  bl30_enter_suspend(mode)                      bl30 0x100053d8
   |  SD_CFG15[15:12] = RTI[3:0]                      0x10001cb8
   |  SD_CFG15[31:28] = *0x1000d600   (reason)       0x100054ca
   |  RTI &= ~0xf00                                  0x10005550
   |  real reset                                     0x100035c0
   v
  BootROM -> BL2  bl2 main                           bl2 0x793c
   |  bl 0x79b4  usb gate
   |      dev = (RTI[15:12]==2) ? 6 : GP_CFG0[3:0]    0x820
   |      if (dev == 5 || RTI[15:12] == 2) -> "BL2 USB"
   |      else if (RTI[15:12] == 1) -> "Skip usb!", RTI[11:8]=0, reason=3
   |  bl 0x5598
   |  bl 0x1e0 -> 0x850  storage dispatch
   |      dev == 1 -> eMMC
   |      dev == 2 -> NAND
   |      anything else -> return 0, NOTHING INITIALISED
   |  bl 0x73e0  fip check
   |  "NEVER BE HERE" ; b .
   v
```

**cold vs normal, statically, as asked in §8: the mode lands in `RTI[3:0]` and
`SD_CFG15[15:12]`, and BL2's two gates read `[15:12]` and `GP_CFG0[3:0]`. neither
gate looks at `[3:0]` or at `SD_CFG15`. so `cold_boot` and `normal` should behave
identically once the flag is armed.** that is a falsifiable prediction and it is
the basis of experiment 3.

## 6. bl30 / scp: the mailbox command sets, for the record

`bl30` receives commands from BL31 over the HIU mailbox. command = low byte of
the status register. full sets, decoded from the two dispatchers:

```text
  secure, *0xda83c42c, dispatcher 0x100026bc
     0x04 0x08 0x15 0x30 0x31 0xc0 0xc1 0xc2 0xc3 0xc6 0xc8 0xe0 0xf0 0xf1 0xf2
     0x08 sub 1 -> gpio off + enter suspend + real reset
     0x31      -> SD_CFG15 &= ~0xf0000000
  low, *0xda83c438, dispatcher 0x1000243c
     0x0d 0x1a 0x1b 0x1c 0x20 0x21 0x42 0xb0 0xb1 0xb2 0xb3 0xc4 0xc5
     -> dvfs, cpu freq, oren/doren reset. nothing boot-source related.
```

there is **no** usb-boot command in either set. so on this generation BL30 is not
the component that arms the flag; it is only the component that transports the
mode and clears the flag on the way down. consistent with §3: the arming is done
inside bl31, before BL30 is ever involved.

## 7. persistence, classified

from the code, not assumed:

```text
  RTI_STATUS_REG3[11:8]  survives PSCI reset (bl31 masks only [3:0] and [15:12]).
                         cleared by BL30 immediately before the hardware reset,
                         and by BL2 on "Skip usb!".  AO domain, battery-backed:
                         survives a power-cycle too.  NOT a candidate for the
                         power-cycle-cleared property.
  RTI_STATUS_REG3[15:12] same, plus BL2 rewrites it 1 -> 3 on the skip path.
  GP_CFG7[8:31]         gpio latches. rewritten by pinmux, not boot state.
  GP_CFG0[3:0]          written by the BootROM itself, at power-on, to say where
                         it is loading from.  not an arming target.
  SD_CFG15[15:12]/[31:28] written by BL30 on every reset, so it never carries
                         anything across a reset.
```

**important consequence: the armed state as reconstructed does NOT explain the
power-cycle recovery.** `RTI_STATUS_REG3` lives in the always-on domain and is
not cleared by losing power in any way visible in this code. so either

* the arming is in a second place that *is* power-cycle cleared, or
* the F1 "it came back after a power-cycle" reading is wrong. F1 never issued a
  reset. the flag was read as 0, the auto-burn path ran, and the stick came back
  on its own or after the plug. round 34 §5 already leaned on F1's implicit
  recovery; that inference is **not** supported, because no reset separated F1
  from the recovery.

this is the weakest joint in the chain and experiment 1 is designed to break it.

## 8. what is proved, inferred and hypothesised

**PROVED BY CODE, in plaintext family binaries**

```text
  AO_RTI_STATUS_REG3[11:8] is cleared by a path the vendor labels "usb flag"
  AO_RTI_STATUS_REG3[15:12] is read by BL2 and compared against 2 to enter USB
  AO_RTI_STATUS_REG3[3:0] is the boot mode, and BL30 copies it to SD_CFG15[15:12]
  SD_CFG15[31:28] is the reboot reason, stamped by BL30 from BL31 shared RAM
  BL2 with a boot device other than 1 or 2 initialises no storage at all
  GP_CFG7[8:31] is a gpio pad array, so GP_CFG7[31] is not a boot flag
  GP_CFG0[3:0] is the ROM boot-device id
  the bl31 FID handlers are at 0x05100000 in a blob absent from every tree file
```

**INFERENCE, strong**

```text
  set_usb_boot 2 sets RTI_STATUS_REG3[15:12] = 2 and/or [11:8] = 2
  the BL31 reset hook preserves it because it masks only [3:0] and the
    reason==8 branch
  BL2 then takes the "BL2 USB" branch and simultaneously loses the eMMC path
```

the enum value matching the hardcoded constant is the weakest part of this, and
it is still an inference. it is exactly what experiment 1 measures.

**HYPOTHESIS**

```text
  the silence is BL2 sitting in the ROM-level USB-download path, which expects
  the Amlogic upgrade-tool handshake at 0xd900c000, not a fastboot or an optimus
  host, so nothing enumerates and nothing boots
```

not proved. BL2's USB branch was read but its terminal state was not, and
`bl2.bin` is the *family* build, not the aquaman's.

## 9. next experiments, three, read-only first

no MMIO writes, no `RUN_IN_ADDR`, no poke. all three are `oem` + a bus watcher.

**E1, do this first, read-only, one session.**
`oem read_mem 0x02` at `0xc810001c`, then `set_usb_boot 2`, then read
`0xc810001c` again, then `set_usb_boot 1`, then read again. round 26 proved
`READ_MEM 0x02` works on the `0xc81002xx` block and `0xc810001c` is the
non-secure alias BL30 itself uses, so it should read.
discriminates: if `[15:12]` goes 1 -> 2, or `[11:8]` becomes 2, the hypothesis is
confirmed and the address is confirmed. if nothing moves, the arming is in a
register BL33 cannot see at all and the whole `RTI_STATUS_REG3` line is wrong.
this is the test that settles it either way. copy the pattern from
`tools/flagtest.py`, it already does read / SMC / read in one burning window.

**E2, the control that isolates the setter from the transport.**
same session, `set_usb_boot 2`, then `reboot cold_boot`, then from the *next*
BL33 (re-enter fastboot via the hardware keys, not via a command that would
consume the flag) read `0xc810001c`.
discriminates: if `[11:8]` is already 0 at the next BL33, BL30 cleared it and the
ROM cannot have used it. if it is still 2, the state survives the reset and the
arm is still armed when BL2 runs.

**E3, cold vs normal, with the flag armed.**
`set_usb_boot 2` then `oem reboot normal`, with the 4 ms watcher running.
discriminates: §5 predicts the same wedge as `cold_boot`. if `normal` boots
android, the mode field matters somewhere this analysis missed, and the "BL2 USB
branch only" story is incomplete.

E1 is the one to run. it is read-only, it costs one burning window, and it
returns "yes" or "no" on the central claim.

## 10. ledger

```text
  set_usb_boot 2 + cold_boot wedges 885 s        TESTED (round 34)
  the SMC is not inert                            TESTED (round 34)
  GP_CFG7[31] carries the armed state              REFUTED, and now explained:
                                                  it is gpio pad 23
  GP_CFG0[3:0] == 1 == eMMC                       CONFIRMED, F1 + bl2 0x844
  the armed state is in the AO always-on domain   INFERENCE, testable with E1
  the consumer is BL2, not the BootROM, not BL33  STRONG, plaintext code
  BL31 writes RTI_STATUS_REG3 and names [11:8]
  the usb flag                                    CONFIRMED, plaintext code
  BL30 writes SD_CFG15[15:12] from RTI[3:0]       CONFIRMED, plaintext code
  the bl31 0x82000043 handler exists              CONFIRMED structurally, body absent
  the armed state is power-cycle cleared          NOT SUPPORTED. F1 never reset.
  where exactly in RTI_STATUS_REG3 the arm lands   UNKNOWN, needs E1
```

nothing in this report reopens `do_reset`, `fastboot reboot`,
`reboot-bootloader`, `reboot bootloader` mode 7, or the absence of a reset.
those stay closed.
