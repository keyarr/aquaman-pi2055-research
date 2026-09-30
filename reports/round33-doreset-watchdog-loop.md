# round33: what `do_reset` actually does, and why the round-3 legs hung

date 2026-09-30. offline, no device I/O in this round. C0 and F1 were run
earlier today and are in `reports/round32-controlled-experiment.md` §0.

## 0. answer block

```text
  reboot cold_boot, no flag, with watcher    = WORKS. 17.5 s, back to android
  set_usb_boot 2 -> GP_CFG7[31]              = 0 -> 0. flag is never set
  set_usb_boot 1 (CLEAR) as control          = 0 -> 0. nothing writes GP_CFG7
  oem reset / fastboot reboot  "hang"        = NOT the flag. NEVER WERE resets
  the round-3 168.9 s silence                = BL33 SPINNING IN A WATCHDOG
                                                ENABLE LOOP, explained below
  do_reset is a "13 instruction stub"        = WRONG. it is 13 instructions
                                                that never return
```

## 1. the two live results change the target

C0 first, because it is the one that retires the whole investigation:

```text
  adb reboot fastboot              -> 18d1:0d02 in 5.6 s
  fastboot oem reboot cold_boot    -> PSCI 0x84000009, REAL reset
  t= 12.814  18d1:0d02  OFF
  t= 30.341  2717:4e40  android    ON
```

**COMPROVADO PELO TESTE:** `reboot cold_boot` is fine on this build. 17.5 s of
silence, android comes back, and **nothing enumerates in between** — no
`1b8e:c003`, no second Amlogic VID:PID, at 4 ms resolution over the whole gap.
raw: `reports/c0-usbwatch.log`, `reports/c0/c0.txt`.

F1 already established that `set_usb_boot 2` does not move `GP_CFG7[31]`, and
that `set_usb_boot 1` — the mode the burn-check path is known to send — does
not either.

Put together: **the flag was never the variable, and the real reset was never
broken.** Both halves of the round-3 observation have a mundane explanation
now, and neither one is FORCE_USB_BOOT.

## 2. `do_reset` does not return

round 31 called `do_reset` (`0x37e21684`) "a 13 instruction stub" and left it
there. the 13 instructions are real and the disassembly was right. what was
missed is the last one:

```text
 *0x37e21684  stp  x29,x30,[sp,#-0x10]!
 0x37e2168c  adrp x0,#0x37ebf000 ; "resetting ...\n"
 0x37e21694  bl   0x37e593c8                    ; printf
 0x37e21698  mov  x0,#0xc350
 0x37e2169c  bl   0x37eab1c8                    ; udelay(50000)
 0x37e216a0  bl   0x37e2147c                    ; no-op
 0x37e216a4  bl   0x37e21680                    ; ret (tail of the fn above)
 0x37e216a8  mov  x0,#0
 0x37e216ac  bl   0x37e1a0c0                    ; <-- this one
 0x37e216b0  mov  w0,#0
 0x37e216b4  ldp  x29,x30,[sp],#0x10
 0x37e216b8  ret
```

`0x37e1a0c0` is three instructions:

```text
 0x37e1a0c0  stp  x29,x30,[sp,#-0x10]!
 0x37e1a0c8  bl   0x37e1a058
 0x37e1a0cc  ldr  w0,[x0]      ; dead, the callee never returns
 0x37e1a0d4  ret
```

and `0x37e1a058` has no exit:

```text
 0x37e1a060  mov  w0,#0x2710
 0x37e1a064  bl   0x37e2017c                  ; udelay(10000), once, pre-loop
 0x37e1a068  mov  x0,#0x98d0 ; movk x0,#0xc110,lsl#16   -> 0xc11098d0
 0x37e1a06c  mov  w1,#3     ; movk w1,#0x7a0,lsl#16     -> 0x07a00003
 0x37e1a078  str  w1,[x0]                        ; WDT CTRL  = clk_en|clkdiv|
                                                     ; ee_reset|div|EN
 0x37e1a07c  mov  x0,#0x98dc ; movk x0,#0xc110,lsl#16   -> 0xc11098dc
 0x37e1a084  str  wzr,[x0]                       ; WDT RESET = kick
 0x37e1a088  ldr  w1,[0xc11098d0]
 0x37e1a094  orr  w1,w1,#0x40000                 ; BIT(18) = WDT_CTRL_EN
 0x37e1a0a0  str  w1,[0xc11098d0]
 0x37e1a0a4  mov  w0,#0x64                       ; 100
 0x37e1a0a8  ldr  w1,[x1]                        ; spin
 0x37e1a0b4  subs w0,w0,#1
 0x37e1a0b8  b.ne 0x37e1a0a8
 0x37e1a0bc  b    0x37e1a068                      ; UNCONDITIONAL, no exit
```

**COMPROVADO PELO CÓDIGO:** `b 0x37e1a068` is an unconditional back-edge with
no compare, no timeout, no re-arm guard. `do_reset` cannot return. Any caller
of it is stuck in BL33 forever, with the watchdog re-armed and re-kicked on
every pass.

the register decode is not guesswork, the exact driver is in the tree
(`.src/linux-amlogic/drivers/watchdog/meson_gxbb_wdt.c`, and the amlogic fork
`drivers/amlogic/watchdog/meson_wdt_v3.c` is byte-identical in the defines):

```text
  0xc11098d0  MESON_WDT_CTRL_REG  (offset 0)   BIT(24) CLK_EN
                                             BIT(25) CLKDIV_EN
                                             BIT(21) EE_RESET
                                             BIT(18) EN        <- 0x40000
                                             BIT(17:0) DIV_MASK
  0xc11098dc  MESON_WDT_RSET_REG  (offset 0xc) write 0 = keepalive
```

`0x07a00003` = `CLKDIV_EN | CLK_EN | EE_RESET | DIV=3 | EN`, and the loop then
ORs `EN` in again on every iteration. so the loop is "enable the watchdog,
kick it, wait 100 reads, do it again, forever". that is a **watchdog
enabling loop, not a watchdog feeding loop** — it is the shape of code that is
*supposed* to be followed by a reset that never comes, because the reset path
was compiled out of this build.

the `reg` matches the DTB exactly: `artifacts/aquaman.dts:322-324`,
`compatible = "amlogic, meson-wdt"`, `reg = <0x0 0xc11098d0 0x0 0x10>`.

## 3. that is the round-3 hang, and it needed no flag

round 3 trials 2 and 3 were `oem reset` and `fastboot reboot`. round 31
already proved both tail-branch into this same `do_reset`:

```text
  0x37e94e58  b  0x37e21684   ; fastboot "reboot"
  0x37e94e6c  b  0x37e21684   ; fastboot "reboot-bootloader"
  0x37e25fac  bl 0x37e21684   ; fallback when "fastboot boot" is rejected
  0x37e94f84  bl 0x37e21684
  0x37eac66c  bl 0x37e21684   ; wipe 0x186a0 then b .
```

so: fastboot command arrives, BL33 enters `do_reset`, spins forever, never
services USB again, the gadget drops off the bus, the host sees a dead device.
**COMPROVADO PELO CÓDIGO** for the reachability, **INFERÊNCIA FORTE** for the
causal chain, because round 3 never ran with a watcher on legs 2 and 3.

the read-only corroboration is that the other direct caller of the same loop
sits in a function called `Burn Reboot...` and is immediately followed by
`[MSG]stop here as poweroff and powerkey not supported in pla[tform]`:

```text
 0x37e7ba2c  adrp x0,#0x37ed9000 ; add x0,x0,#0xf8   ; "Burn Reboot...\n"
 0x37e7ba34  bl   0x37e593c8                        ; printf
 0x37e7ba38  mov  x0,#0
 0x37e7ba3c  bl   0x37e1a0c0                        ; the same non-returning loop
 0x37e7ba40  ldp  x29,x30,[sp],#0x70                ; dead
 0x37e7ba44  ret
```

"stop here" is the vendor telling you it gives up at that point. the code after
the spin is unreachable, which is the same conclusion the disassembly reaches.

`0x37e1a0c0` has exactly two callers, `do_reset` and that burn path. nothing
in the boot path touches it.

## 4. why the watchdog never fired, twice over

the loop kicks `MESON_WDT_RSET_REG` on every pass, so the counter is reset
before it can expire and no watchdog reset happens. that is why C0-style
spontaneous recovery was never observed on the `reset` legs. and it is also why
the silence looked like a crash: BL33 is not dead, it is spinning, burning CPU,
and never answering USB.

this retires the round-3 "power cycle needed" evidence completely, in the
opposite direction from how it was read. it was not "the flag survived the power
cycle". it was "BL33 never came back because it was in a loop, and the only
exit was the physical plug".

## 5. what this does and does not settle

```text
  why did oem reset hang fastboot     = BL33 spins in the WDT enable loop   CODE
  why did fastboot reboot hang        = same function, same loop             CODE
  is reboot cold_boot broken          = NO. 17.5 s baseline, tested          TEST
  does set_usb_boot 2 do anything     = NO observable effect, tested         TEST
  does set_usb_boot 2 reach BL31      = unknown, and now uninteresting
  is the flag "FORCE_USB_BOOT"        = the enum says so, nothing implements it
```

**HIPÓTESE, explicitly not promoted:** that the intended design was "arm the
watchdog, then reset", and that the reset half is what got compiled out of
this build. the shape fits — a non-returning enable loop guarded by nothing, in
a function that prints "stop here". but nothing in the artifact states intent,
and the aquaman BL31 is still unavailable (rounds 18/26/27/28/29/30), so
whether some earlier stage was supposed to catch this is not knowable here.

**the one thing this predicts that is worth testing:** if `do_reset` really
spins forever, then `fastboot reboot` and `oem reset` should produce a *silent
bus, then nothing, indefinitely* — not a slow return to android. the round-3
40.3 s and 168.9 s gaps are both explicable as the user giving up and pulling
the plug, but they were not watched, so it is untested. it is also the one
prediction that costs a power cycle to check, which is why it was not run today.

## 6. status against the round-32 runbook

```text
run | set_usb_boot | GP_CFG7[31] before | after | reboot real? | USB observed | android back? | power-cycle?
----+---------------+-------------------+-------+--------------+---------------+---------------+-------------
C0  | no            | n/a               | n/a   | yes          | nothing       | yes, 17.5 s   | no
F1  | yes, no reset | 0                 | 0     | no           | 1b8e:c003     | n/a           | yes
F2  | yes           | n/a               | n/a   | yes          | NOTHING 885 s | NO            | YES
```

F2 was cancelled at this point. **that was a mistake**, and round 34 corrects
it. I argued the F1 null plus the C0 baseline meant F2 could only produce a
null. That conflated the register named in the public enum with the observable
behaviour. If BL31 arms some other bit or some other state, F1 reads `0 -> 0`
and the device can still wedge — F1's own verdict text said exactly that and I
did not carry it forward. F2 was also the only leg of the round-3 experiment
that had never actually been run with a watcher. It wedges.
`reports/round34-setusbboot-realreset.md`.
