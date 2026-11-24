# Incident: infinite loop at hook 0x37e265fc - 2026-11-19

## What was attempted

Experiment to locate copies of the Linux image in RAM at the hook point
`0x37e265fc` (post-decrypt, pre-eret). Motivation: the consumption oracle with
`marker.bin` proved that the kernel that boots is stock (`/proc/version` with
`4.9.113`), despite the hook executing and the decompressed image being at
`0x1080000` with `ARMd`. Hypothesis: the kernel executes from a relocated copy.

Stub `/tmp/stub/scan_armd.bin` (136 B, sha
`b806b3bb482fa7bba4f9079b0163f4fdaa5eba17782a4cefec8229b413ccf211`): scans
`0x01000000..0x04000000` looking for `ARMd` (`0x644d5241`), saves up to 16 hits
at `0x37900000`, and ends with `b .` (infinite loop in BL33) to allow MREAD of
the scratch without issuing the `eret`. Script: `/tmp/scan_try.py`.

Phase 0 PASS: identify 0, oracle `failed:`/`success`, stock hook `80003fd6`,
`imgread -> success`, stub and hook with readback OK, `dcache flush` and
`icache flush` OK.

## Result

`bulkcmd "bootm 0x1080000"` locked up as expected (USBTimeoutError 110), but the
subsequent MREAD also locked up (110): the infinite loop prevented the firmware
from serving SET_ADDRESS. `dev.reset()` failed with
`USBError(2, Entity not found)` because the device had already left the bus.

Passive monitoring for 150 s: none of `1b8e:c003`, `18d1:0d02`, or `2717:4e40`
reappeared. `dmesg` shows `usb 3-3: USB disconnect`, followed by multiple
enumeration attempts with `device descriptor read/64, error -110` and
`Device not responding to setup address` / `error -71`. The device is
electrically connected, but the SoC does not respond - BL33 phase in a loop.

## Recovery

Section 9 of `USB_RECOVERY_WITHOUT_POWER_CYCLE.md` covers exactly this case: a device
off the bus / BL33 in a loop cannot be recovered by `dev.reset()`; it requires a
power cycle (interrupt and reconnect USB power) or a physical reboot. I did
not do either. **Not executed.**

Current state: device offline. No writes to flash/erase/saveenv/efuse/BootROM.
Nothing persistent was modified - the lockup is volatile, but without power
there is no way to restart the SoC via USB.

## Error and derived rule

An infinite loop in BL33 is equivalent, for recovery purposes, to
`RUN_IN_ADDR 0x05` and the `do_reset` loop: the gadget drops off the bus and USB
reset does not recover it. Do not repeat. To observe the state at the hook point
without boot, use a stub that **returns** to the flow (`blr x4` +
`br 0x37e26600`) and an oracle that survives the reboot - not a loop that
depends on a later MREAD. Alternative: write the result to a RAM carveout that
the next
Android boot can read (if it survives the SoC reset, which is doubtful), or use
the `bootargs`/DTB property as an output channel.

## Pending

A power cycle / physical reconnection before any new hardware experiment,
which I left for the next session.
