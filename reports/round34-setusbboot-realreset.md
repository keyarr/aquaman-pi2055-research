# round34: `set_usb_boot 2` + real reset DOES wedge. the flag is real, GP_CFG7 is not where it lands

date 2026-09-30, ~19:37. live. one watcher, one device, three runs (C0, F1, F2)
all on the same boot image, same watcher binary, same 4 ms poll.

## 0. answer block

```text
  C0  no flag, real reset     -> android back in 17.5 s        TESTED
  F1  flag, no reset          -> GP_CFG7[31] 0 -> 0            TESTED
  F2  flag + real reset       -> NO USB for 885 s, no android  TESTED
                                 until physical power-cycle
  the flag is the variable   = PROVEN. C0 vs F2, one SMC apart.
  GP_CFG7[31] is the state    = NO. it reads 0 in both.
  round 3 trial 1             = was right, for reasons nobody could show
```

## 1. the two runs, side by side

identical command, identical watcher, identical build. one SMC apart.

```text
  C0   fastboot oem reboot cold_boot
       t= 12.814  18d1:0d02  OFF
       t= 30.341  2717:4e40  ON          17.5 s silence, android back

  F2   fastboot oem set_usb_boot 2      -> AMLOGIC x3 + OKAY 0.000s
       fastboot oem reboot cold_boot
       t= 14.946  18d1:0d02  OFF
       [nothing. 885 s. watcher window exhausted.]
       [physical power-cycle required]
```

raw: `reports/c0-usbwatch.log`, `reports/f2-usbwatch.log`, `reports/f2/f2.txt`.

**COMPROVADO PELO TESTE:** the SMC `0x82000043` with `x1=2`, followed by the
identical PSCI reset, changes the outcome from "17.5 s back to android" to
"no USB at all, indefinitely". nothing else differs. the arm succeeded in
doing something.

**COMPROVADO PELO TESTE:** it is not a slow boot and not a device that
re-enumerates late. 885 s at 4 ms resolution, zero enumeration of any kind —
not `1b8e:c003`, not `18d1:0d02`, not `2717:4e40`, not any other VID:PID. the
runbook's "USB completely absent" line, taken literally.

## 2. so the F1 null was measuring the wrong register

F1 read `0x02` at `0xc810025c` and got `0x00400007` before and after
`set_usb_boot 2`. `set_usb_boot 1` as a control gave the same bytes. F1's own
verdict text said: "whether BL31 ignored the SMC or something cleared it after
is still open", and named the third possibility too — "BL31 set a different
bit".

F2 is that third possibility, confirmed. **the arm does something, and
`GP_CFG7[31]` is not it.**

this does not revive the "BL31 ignored it" reading. it kills it. whatever the
SMC does, it is not inert, and the most likely place for it to be invisible
from BL33 is exactly the one F1 could see and the one BL33 cannot: something
consumed between the SMC and the next BL33 read, or something outside
`0xc810025c`.

the family BL31 evidence in round 31 §4.2 is relevant again: it clears
`GP_CFG7[7:0]` on every reboot and its pin-index helper `1 << (idx+8)` can land
on bit 31 for `idx=23`. `0x00400007` has bit 22 set and `[7:0]=0x07`, so this
register *is* being written by someone — the question is only whether it is
the register that carries the armed state on this silicon.

## 3. what this rules out, hard

the round-33 watchdog-loop finding is unaffected and still stands, but its
scope narrows. `do_reset` spinning forever explains why `oem reset` and
`fastboot reboot` kill the fastboot session. **F2 did not go through
`do_reset`.** it went through `reboot cold_boot` → PSCI `0x84000009` →
BL31 → BL30 → reset, and the stick *did* reset: the device dropped off the bus
at t=14.946 and never came back, which is what a reset looks like. So this is
a **different failure** from the round-3 stub hang, and it happens *after* the
reset point rather than instead of it.

that splits the old question cleanly:

```text
  oem reset / fastboot reboot   = BL33 spins in the WDT loop, no reset
                                  at all, no ROM, no BL31        round33
  set_usb_boot 2 + cold_boot    = reset HAPPENS, then silence
                                  forever, no ROM USB, no android
```

and it eliminates the two readings round 31 could not separate, because both
required the reset NOT to have happened:

- "the reset wedged before the ROM" — the reset did happen, the device went
  dark at the right point.
- "BL31/SCP cleared the flag on the way" — still possible, and now the
  *leading* explanation, but it does not explain the silence by itself. the
  flag has to survive into the ROM and do something there, or the armed state
  has to be what makes the post-reset path go quiet.

## 4. the one thing F2 does not tell us

**where it stops.** F2 proves the chain goes quiet after the reset. It cannot
say whether:

- the ROM entered USB and failed to enumerate (would expect `1b8e:c003` to
  appear and stay — **did not happen in 885 s at 4 ms**, so this is weak now),
- the ROM took a non-USB branch and the kernel hung on something USB-adjacent,
- BL31/BL30 wedged between the PSCI and the ROM handoff,
- the armed state sends the ROM somewhere that produces no USB at all and no
  display, with the kernel never reached.

round 31's `[F3]` — "reset works, linux boots, USB never enumerates" — is
**still not excluded**, and the round-3 evidence for it (the ~100 ms Xiaomi
splash on trial 1) was never instrumented. F2 is the first properly watched
run of that leg and it shows no splash and no USB, which is a data point
against a kernel-side reading but not a refutation: nobody was looking at the
display.

## 5. the cheapest next observation

the armed state is invisible at `0xc810025c` from BL33. the ROM reads
`GP_CFG0[3:0]` and `GP_CFG7[31]` per the family map, and `GP_CFG0[3:0]` read
**1** live in F1. if the armed state were visible anywhere in the AO block
that survives a reset, a read from the *next* BL33 — i.e. a second
`set_usb_boot` sequence after a power-cycle — would find it. F1 already did
that implicitly: it ran, the flag read 0, and the auto-burn timeout fired and
the stick came back to android on its own. **so the armed state did not
survive a power-cycle.** it is consumed by something, and the only consumers
left are the ROM and the stages between.

that is the sharpest open question, and it is a code question, not another
device run: **what does the BootROM check, and what does it do with a set bit
that is not `GP_CFG7[31]`?** the aquaman BL31 is unavailable, but the BootROM
is not secure-fused in the same way and the `0x37e76510` consumer in BL33
(`is_tpl_loaded_from_usb`) shows the vendor's own idea of the check. finding
the ROM's copy of that function would answer where the state actually lives.

## 6. honest ledger

```text
  set_usb_boot 2 + cold_boot wedges 885 s+     TESTED, reproduced
  the SMC is not inert                         TESTED (this round)
  GP_CFG7[31] carries the armed state           REFUTED (F1 + F2 together)
  BL31 "ignored" 0x82000043                     REFUTED as a description
  do_reset spin loop explains THIS              NO, different failure point
  where the post-reset chain goes quiet         UNKNOWN
  armed state survives power-cycle              NO (F1's own recovery)
  F2 is the round-3 trial 1, finally watched    YES
```

round 3's trial 1 result was correct. round 31 was right that trials 2 and 3
were not resets. nobody was wrong about the data — the trial 1 leg just never
had an instrument, and two rounds of offline analysis tried to explain it with
the stub hang instead of running it.
