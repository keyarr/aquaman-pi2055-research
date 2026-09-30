# round32: set_usb_boot / cold_boot, as a controlled experiment

date 2026-09-30. **F1 executed, C0 and F2 still to run.** §0 is the live
result. the rest is the runbook, kept because C0 and F2 depend on it.

## 0. answer block

```text
  GP_CFG7[31] after set_usb_boot 2   = 0 -> 0. NO OBSERVABLE CHANGE   TESTED
  set_usb_boot 1 (CLEAR) as control  = 0 -> 0, byte-identical         TESTED
  GP_CFG7 live value                 = 0x00400007, stable across both
  GP_CFG0 live value                 = 0x04000331, [3:0] = 1 (not 5)
  SD_CFG15 live value                = 0x03b04200, [15:12] = 4
  BL33 answered the whole time       = stage 16, identify OK at +90 s
  reboot cold_boot baseline          = UNKNOWN, C0 not run yet
  "three resets, one outcome"        = DEAD, 2 of 3 were do_reset stubs
  bus watcher script in the repo     = DID NOT EXIST. tools/usb_watch.py now
  set_usb_boot 2 then read 0xc810025c from a *second* session
                                    = SELF-DEFEATING, the burn-check clears
                                      the flag on the way in
```

**COMPROVADO PELO TESTE:** `set_usb_boot 2` does not move `GP_CFG7[31]`, and
neither does `set_usb_boot 1`. The read is a real read: `0x02` returns four
coherent bytes whose fields match the static map (bit 22 = `rpmb_state`, set;
`[7:0]` = `0x07` boot field, the one BL31 family code clears on reset). Not a
failed transfer, not a dead gadget, not a wrong stage. The whole measurement
took **21 ms** inside one burning window, with the command straddled by the two
reads. `GP_CFG0[3:0]` reads 1, so the flag was not redundant and the test was
meaningful. `reports/f1/flagtest-2.txt` has the raw output.

**the control is what makes this a result and not a null.** `set_usb_boot 1`
is `CLEAR_USB_BOOT` — the one mode the burn-check path is known to actually
send. It also produced `0 -> 0` with byte-identical register values. So the
register is not merely failing to move for mode 2: nothing in this build
touches `GP_CFG7` at all through this SMC. That kills the "BL31 sets it and
something clears it in the 21 ms window" reading, which was the most charitable
one available.

**still HIPÓTESE, do not promote:** that BL31 "ignored" `0x82000043`. The
wrapper at `0x37e19efc` discards the return value, so there is no success
signal, and `GP_CFG7` is only the register the *public* family implementation
is documented to use. A BL31 that sets some other bit, or that routes through
a different register, is not excluded by this test. What is excluded is the
specific claim the round-31 tree was leaning on.

**consequence for the runbook:** the runbook's own §8 row for `0->0` fires.
The SMC question is closed as an observable, the FORCE_USB_BOOT line of
investigation is not worth more device time on this stick, and **C0 becomes
the primary test**, not the sanity check it was written to be. If `cold_boot`
is itself broken, that is the finding, and the flag was never the variable.

**incident, unrelated to the result:** the first F1 attempt died at the
`fastboot oem update 5000` step with `FAILED (Status read failed)` followed by
a 20 s `< waiting for any device >` hang inside `optimus_enter.sh`. The host
sees a failure there even on a clean entry, because the stick drops the
fastboot link while switching to optimus; the retry then found fastboot absent
entirely. `adb` was on the TCP endpoint `192.168.0.11:5555` at that point and
came back as USB `26919800005844922` after the user re-plugged. F1 was rerun
by hand, step by step, instead of through `optimus_enter.sh`: `adb reboot
fastboot` (2 s to `18d1:0d02`) -> `oem update 5000` -> `1b8e:c003` at ~200 ms.
`optimus_enter.sh` is fine for a healthy adb-over-USB path, but it hides which
step failed and this box has an adb transport that drops. **run the three
steps manually when adb is not on USB.**

## 1. the trap in the original phase 1 plan

## 1. the trap in the original phase 1 plan

the plan was: fastboot -> optimus -> read -> `set_usb_boot 2` -> read again.
that does not work, and it would have produced a false null every time.

the only read primitive is `AM_REQ_READ_MEM 0x02` inside the optimus gadget
(`usb_pcd.c:435`, no parser, no `run_command()`). the fastboot `oem` channel
reaches `run_command()` but cannot read. so the two halves live in different
USB modes and you have to leave optimus to issue the command.

and leaving optimus is destructive to the measurement. `update 5000` runs the
v2 burning entry, whose control-request path calls
`aml_burn_check_is_ready_for_burn` (`0x37e765d8`) -> `is_tpl_loaded_from_usb()`
(`0x37e76510`) -> if `GP_CFG7[31]` is set it calls `set_usb_boot_function(1)`,
**CLEAR_USB_BOOT**, over the same SMC, and enters optimus produce
(`round31-usbboot-reset-path.md` §3.3). the flag is cleared by the act of
going back to look at it.

**COMPROVADO PELO CÓDIGO:** the clear path, its caller chain, and the gating on
`PREG_STICKY_REG2` holding `0x1b8ec003`/`0x1b8ec004`.
**INFERÊNCIA FORTE:** the entry sequence used by `optimus_enter.sh` goes
through that caller. it was never disassembled end to end for this round.

consequence: **phase 1 must be one process, one window**, read straddling the
command. `tools/flagtest.py` exists for exactly that.

phase 2 does not have this problem. `fastboot oem set_usb_boot 2` and
`fastboot oem reboot cold_boot` both go through the fastboot `oem` handler
(`0x37e95630`, a host-driven `run_command()`), so arm and reset happen in the
same USB mode with no burn-check in between. **phase 2 never enters optimus.**
that also means phase 2 cannot read GP_CFG7, and does not need to: phase 1 owns
the register question, phase 2 owns the behaviour question.

## 2. tools added

`tools/usb_watch.py` — polls `/sys/bus/usb/devices` every 4 ms, no root, no
`lsusb` fork. logs every VID:PID change with `bcdDevice`/`speed`/class on
appearance, and marks the intervals with no Aquaman device on the bus. the
round-3 watcher that produced the 168.9 s figure was an ad-hoc loop and was
never committed, which is how "three resets, one outcome" ended up in the
report with no instrument behind it. `bcdDevice` is logged specifically because
`1b8e:c003` is **not** a BootROM signature on this stick: round 3 §2.5 captured
it as BL33 optimus, and `update 5000` reproduces it.

**no sudo, and the 4 ms interval is not aspirational.** verified on this host:
`/sys/bus/usb/devices/*/{idVendor,idProduct,bcdDevice,speed,bDeviceClass}` are
all world-readable, so there is no `udev` event latency and no `lsusb` fork in
the loop. a full 21-entry snapshot costs **0.211 ms**, so 4 ms leaves 3.8 ms of
headroom; at 200 snapshots back to back the whole run is 77 ms. `journalctl
-kf` is also readable without root here, so the descriptor sidecar needs no
credentials either. the password belongs to `optimus_enter.sh` only, which
does need it to claim `1b8e:c003` for pyusb.

`tools/flagtest.py` — identify, then read `GP_CFG7`/`GP_CFG0`/`SD_CFG15`, then
`set_usb_boot 2` over bulkcmd `0x34`, then read again, in one process.
`GP_CFG0` is read because `is_tpl_loaded_from_usb()` is
`GP_CFG0[3:0]==5 || GP_CFG7[31]`: if `GP_CFG0` already reads 5 the flag is
redundant and the test means nothing. `0x34/0x33` is used rather than
`0x30/0x31` because round 6 proved the bulk path live on this stick; both land
in `optimus_working()`, which falls through to `run_command()` for a command
not on its whitelist. the reply is worthless either way, `optimus_working()`
answers `"success"` unconditionally and the console is invisible.

smoke tested: both compile. `usb_watch.py` ran live against the real host bus
and correctly logged the stick at `2717:4e40` with `bcdDevice=0223 speed=480`,
plus the ON/OFF/no-target-banner paths were exercised against a synthetic
sysfs tree, since no real transition can be provoked without rebooting the
stick. `flagtest.py` parses and resolves the optimus symbols but **has not been
run against the device.** no sudo password is required by either tool; only
`optimus_enter.sh` needs one, to hand `1b8e:c003` to pyusb.

## 3. preconditions

| phase | required state |
|---|---|
| F1 | power-cycle, boot to Android, `adb devices` shows the stick |
| C0 | power-cycle, boot to Android, `adb devices` shows the stick |
| F2 | power-cycle, boot to Android, `adb devices` shows the stick |

power-cycle, not `adb reboot`. the point is a known-clean `GP_CFG7`, and
`adb reboot` is a reset whose mode behaviour is itself the thing under test in
C0. a dirty flag from a previous F1 makes every later reading ambiguous, and
`flagtest.py` refuses to interpret `1 -> 1` anyway.

fresh boot also clears the burning window. the observed one was 77 s
(`optimus-ram-read.md` §5) with a much shorter clean part, so do not dawdle
between `update 5000` and the flagtest output.

## 4. phase 1

terminal 1, nothing else running:

```
cd ~/Downloads/aquaman_9_PI_2055
export OPTIMUS_PW='<sudo password>'
export OPTIMUS_OUT=out/logs/f1.log
OPTIMUS_PY=tools/flagtest.py tools/optimus_enter.sh
```

`optimus_enter.sh` does `adb reboot fastboot` -> `fastboot oem update 5000` ->
waits for `1b8e:c003` -> runs `flagtest.py` under a warm sudo. no watcher
needed, nothing reboots.

read off `out/logs/f1.log`: `GP_CFG7` full value before and after, `GP_CFG7[31]`
transition, `GP_CFG0[3:0]`, `SD_CFG15[15:12]`, and whether either other
register moved.

classification, per the brief:

```text
GP_CFG7[31]  0 -> 1   strong evidence the SMC produced the expected state
GP_CFG7[31]  0 -> 0   no observable change in the expected state
```

a `0 -> 0` result is a **real null, not a failed read**: `flagtest.py` reads
`0x02` and prints the raw bytes, so if the register answers at all, the answer
is trustworthy. but it does **not** license "BL31 ignored the SMC". the SMC
return value is discarded by the wrapper and there is no other observable.
mark it HIPÓTESE, leave it open.

a `1 -> 1` result means the flag was already armed at entry, the run is void,
power-cycle and repeat.

do **not** run phase 1 twice in a row without a power-cycle in between. the
second run enters optimus through a path that may clear the flag, so `before`
is not trustworthy.

## 5. control C0

**now the primary test, not the sanity check.** F1 came back `0 -> 0`, so the
flag was never the variable. What is left is whether `reboot cold_boot` works
at all on this stick, and round 31 §8 item 3 predicted exactly this: if the
baseline is also broken, the reset is the problem and FORCE_USB_BOOT was
noise all along.

precondition changed: the stick is currently sitting in optimus `1b8e:c003`
and **did not** self-recover after 300 s, which is longer than the 77 s
burning window recorded in `optimus-ram-read.md` §5. Confirm whether that is
the F1 probes holding the window open (the auto-burn timer is reset by
`AM_REQ_IDENTIFY_HOST`, `usb_pcd.c`, and F1 called `identify` twice) or a
genuine wedge. **power-cycle before C0 regardless**; C0 wants a clean boot.

terminal 1, start first, leave running. **no sudo, no password:**

```
cd ~/Downloads/aquaman_9_PI_2055
python3 tools/usb_watch.py out/logs/c0.log 600
```

terminal 2:

```
adb reboot fastboot
fastboot devices            # confirm 18d1:0d02
fastboot oem reboot cold_boot
```

then just watch terminal 1. do not touch the stick. 600 s covers the observed
168.9 s worst case with room; if it is still silent at 600 s the watcher stops
logging and you have to note that yourself.

optional third terminal, descriptors, does not disturb the poll loop and does
not need root on this host:

```
journalctl -kf | grep -iE "usb 3-"
```

what to record from `c0.log`:

- the `t=` at which `18d1:0d02` disappears
- the first VID:PID after that, and its `bcdDevice`
- elapsed time to each subsequent transition
- total silence duration (the watcher marks it explicitly)
- whether a power-cycle was needed, and if so at what `t=`

this is the **baseline**. every phase-2 number is read against it. a C0 that
takes 170 s to come back is a completely different investigation from a C0 that
takes 18 s, and the difference has to be established before, not after.

## 6. phase 2

same shape as C0, plus the flag. clean boot, no leftovers from C0.

terminal 1, same as C0, no sudo:

```
python3 tools/usb_watch.py out/logs/f2.log 600
```

terminal 2:

```
adb reboot fastboot
fastboot devices                        # confirm 18d1:0d02
fastboot oem set_usb_boot 2             # expect AMLOGIC x3 + OKAY
fastboot oem reboot cold_boot
```

`set_usb_boot 2` and `reboot cold_boot` are both fastboot `oem` commands here,
both `run_command()`, same USB mode, no optimus in between. **do not use
`fastboot reboot`, `oem reset`, or `reboot-bootloader`**: all three tail-branch
into `do_reset` (`0x37e21684`), a 13-instruction stub with no SMC, no AO
write, no PSCI (`round31` §1). they are not resets and using them produces
exactly the confusion this round exists to remove.

accept of `set_usb_boot 2` is worth exactly as much as the round-3 evidence:
`AMLOGIC x3` in 97 ms from a channel whose reply is a constant. the host
reply is **not** confirmation the flag was set. only phase 1's register read
is. treat the phase-2 command as "issued", never as "applied".

## 7. results table

one row per run. `GP_CFG7` before/after only exists for F1; C0 and F2 have no
register reading by design.

```text
run | set_usb_boot | GP_CFG7[31] before | after | reboot real? | USB observed | android back? | power-cycle?
----+---------------+-------------------+-------+--------------+---------------+---------------+-------------
C0  | no            | n/a               | n/a   | yes (PSCI)   | NOT RUN       | NOT RUN       | NOT RUN
F1  | yes, no reset | 0                 | 0     | no           | 1b8e:c003      | n/a           | yes
F2  | yes           | n/a               | n/a   | yes (PSCI)   | NOT RUN       | NOT RUN       | NOT RUN
```

F1's `power-cycle` column is a pending item, not a result: the stick was still
in optimus at the end of the watch window. whether it self-recovers or needs the
plug pulled is itself worth a line in C0's log.

"reboot real?" for F2 is `yes` **only if** the command was
`oem reboot cold_boot`. if anything else was used, mark it and discard the row.

## 8. how to read the combinations

| F1 register | C0 | F2 | reading |
|---|---|---|---|
| `0->1` | clean, fast | identical to C0 | SMC works, reset works, but arming changes nothing visible. the flag is consumed somewhere BL33 cannot see, or the ROM does not honour it. **INFERÊNCIA FORTE** on "SMC works", **HIPÓTESE** on the rest. |
| `0->1` | clean, fast | no USB at all, needs power-cycle | case C. flag armed, reset issued, nothing enumerates. does not separate ROM-in-USB-failing from the reset wedging, because a ROM holding USB with a host present would show `1b8e:c003` and a 4 ms poll would not miss it. **that half is REFUTED by the C0+F2 poll pair**, which is why the watcher is mandatory. |
| `0->1` | clean, fast | Amlogic stage, then BL33, then Android | case A. the flag did something and the chain completed. **COMPROVADO PELO TESTE.** |
| `0->0` | clean, fast | identical to C0 | case B. the observable expected state never appeared. this is the strongest single result, because it removes the whole SMC question without needing BL31. |
| `0->0` | clean, fast | no USB, needs power-cycle | the reset is broken independently of the flag. control C0 did not establish this, so re-run C0 and check. suspect the test, not the theory. |
| `0->1` | **slow or silent** | anything | **stop.** C0 failed. the baseline is broken and F2 says nothing until C0 is fixed. this is the single most likely outcome given the 168.9 s and 40.3 s gaps in `round3-usb-entry/setusbboot_usbwatch.log`, and the whole point of running C0 first. |
| `1->1` | — | — | F1 void. power-cycle, repeat. |
| `0->1` | clean, fast | Linux/Android returns, USB does not enumerate | case D. the flag forced a USB stage that something downstream could not complete, or the kernel-side USB path is wedged. distinguishes from the ROM only via the absence of any Amlogic VID:PID during the gap. |

`1b8e:c003` appearing in F2 is **not** by itself evidence the BootROM ran. on
this stick that ID is BL33 optimus, reproduced by `update 5000` (round 3 §2.5).
to claim BootROM you want an Amlogic device whose `bcdDevice`, descriptors and
MaxPower differ from the round-3 capture, and the log line that records it.

## 9. do not

```text
oem reset                     do_reset stub, no reset. round 3 trial 2.
fastboot reboot               same stub, b 0x37e21684. round 3 trial 3.
reboot-bootloader             same stub, b 0x37e21684.
set_usb_boot 1 / 3 / 4        different enum values, different question. phase 1
                              only needs 2; 1 clears, 3/4 are RUN_COMD/PANIC_DUMP.
optimus.py fill / poke        write primitives. --enable-write plus --write-ok.
                              phase 1 is read-only. no reason to arm them.
RUN_IN_ADDR / bootm / go      executes device code. out of scope.
update / flashall / download  destructive, and `update` denylisted in optimus.py.
anything in optimus.py DENY   the denylist is the only thing between you and a
                              flash. don't work around it.
```

also: do not run F1 twice without a power-cycle, and do not enter optimus
between arming and resetting in F2. both destroy the state being measured, and
the second one is the exact failure mode that made the round-3 evidence
worthless.

**added after F1:** do not sit in optimus probing. `AM_REQ_IDENTIFY_HOST` zeroes
`_auto_burn_time_out_base` (`usb_pcd.c`), so every `identify` restarts the
auto-burn timer. F1 called it twice and the stick was still in `1b8e:c003`
300 s later, well past the 77 s window round 4 measured. Get the reads and stop
touching it. `tools/optimus.py identify` costs device time on every call.

**added after F1:** when adb is not on the USB endpoint, do not trust
`optimus_enter.sh`. Its `fastboot oem update 5000` is wrapped in `timeout 20`
and then loops on `fastboot devices`, and a dropped adb transport turns that
into a 20 s `< waiting for any device >` hang with no indication of which step
actually failed. Run the three steps by hand.

## 10. what is not closed by any of this

`0x82000043` semantics in the real BL31. the aquaman BL31 is secure-only and
unavailable (rounds 18/26/27/28/29/30), the family reference is a partial
image with no handler for the id, and there is no `0x82000043` literal anywhere
in it. nothing in F1/F2/C0 changes that. a `0->0` result is compatible with
"BL31 has no handler for this id", with "BL31 handled it and declined", and
with "BL31 set a different bit". three live observations cannot separate those.
they can only tell you whether to keep chasing the SMC or go look at the reset
path instead.

**F1 already answered the question that mattered, in the negative.** the runbook
predicted the `0->0` row would hand the investigation to C0, and that is what
happened. what is now genuinely open is narrower and not a BL31 question at
all: does `reboot cold_boot` bring the stick back on this build, with no flag
involved. one run, one watcher, no optimus, no SMC. everything else in the
round-31 hypothesis tree was resting on a flag that does not get set.
