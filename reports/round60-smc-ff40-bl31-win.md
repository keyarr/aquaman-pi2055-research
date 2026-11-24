# round60: SMC 0x820000ff @ 0x05100000 (ff40-bl31-win)

## Scope

One line: `sudo python3 tools/diag_smc_matrix.py run ff40-bl31-win`.
Question: with X0=0x820000ff, X1=0x40, X2=0x05100000, X3=0x10000, X4=7 in the SMC
(wrapper BL33 0x37e19ea8), does BL31 write the plaintext to Secure memory or give
an external abort/reset? Only locate the NS/EL3 barrier. This is not the A113X exploit.

No flash/erase/saveenv/persistent setenv/efuse/BootROM/RUN_IN_ADDR/MODIFY.
No blind ioctl. No second matrix line. site2 was not written.

## Device and preconditions

- Entry: `1b8e:c003` at 3-3, `bcdDevice=0007`, `speed=480`, `bDeviceClass=00`.
- `identify() == 0` -> stage 16 (TPL/BL33-u-boot), `raw 00 07 00 10`.
- The device was already in the target state; I did not re-run `adb reboot fastboot`
  or `fastboot oem update 5000`.
- USB access requires `sudo`.
- USB watcher active before any write:
  `tools/usb_watch.py /tmp/round60/logs/usb_watch_run.log 300`.

BOOT_ID: not collected. There was no Android boot until the trigger; after the drop the
device booted into Android (2717:4e40, bcdDevice=0223), with no session to
read properties.

## Phase 0

First attempt: scratch 0x37800000 did not come up zero (residual code from another
session: copy 0x01080000 -> 0x3790..., read of 0x013bbc00). Handler and sites
matched. Per the rule "if any one does not match, STOP", the trigger was not
run; I decided to clear the scratch with PWRITE 0x01 (0x40 zero bytes), revalidate and
proceed. The dump of the dirty scratch at `/tmp/round60/baseline/scratch.bin`
was overwritten by the clean dump.

After cleaning, the 4 dumps matched:

| dump | address | n | expected | read |
| ---- | ------- | - | -------- | ---- |
| handler_false.bin | 0x37f616d0 | 0x10 | `64 67 e3 37 00 00 00 00` | `64 67 e3 37 00 00 00 00` |
| site1.bin | 0x37e24cf0 | 0x08 | `6e d4 ff 97` | `6e d4 ff 97` |
| site2.bin | 0x37e24f90 | 0x08 | `c6 d3 ff 97` | `c6 d3 ff 97` |
| scratch.bin | 0x37800000 | 0x40 | zeros | zeros |

BASELINE PASS.

Oracle before: `false -> b'failed:'`, `true -> b'success'`.

## Execution

`TRIGGER_START/END 2026-11-19T23:04:40Z`. Output in
`/tmp/round60/run_ff40-bl31-win.log`:

```
dcache flush     -> b'success'
trigger false    -> b'failed:'
dcache flush pos -> b'success'
row ff40-bl31-win: expected OK raw EL3 write or reset
x0..x3 = 0x0 0x0 0x0 0x0
buf[0:0x20] MREAD -> usb.core.USBError: [Errno 19] No such device
finally: fill64 restore -> usb.core.USBError: [Errno 19] No such device
```

RESULT 0x37800800[0:0x20] was read successfully (40 zero bytes) before the drop.
`buf[0:0x20]` could not be read: the MREAD of 0x05100000 dropped the gadget.
The `finally` could not restore handler/scratch/RESULT; no useful effect,
since the device rebooted and BL33 RAM was reset.

## Timeline USB (watcher)

```
t=  0.000  start 1b8e:c003 bcdDevice=0007, target present: True
t= 16.938  OFF 1b8e:c003, "no Aquaman device on the bus", target up -> down
t= 34.050  ON 2717:4e40 android bcdDevice=0223, target down -> up
```

Trigger at 23:04:40.5Z = t~16.57. OFF at t=16.938 = 23:04:40.914Z, about
0.4 s after the trigger started and at the instant of the MREAD of buf 0x05100000.
Android appears 17.1 s later. Final state: 3-3 = 2717:4e40; no
1b8e:c003 on the bus. `find()` -> "no 1b8e:c003 on the bus", exit 2.

## Oracle after

Impossible: BL33 gadget left the bus. Per the rule, do not conclude anything
further. I did not do a power cycle or re-hunt of addresses; the line had already been executed and
that was the only objective; recovering the device would not change the observation.

## Evidence

HARDWARE_OBSERVED: drop of the 1b8e:c003 gadget followed by boot into Android,
observed by USB watcher and by USBError on the MREAD of 0x05100000. There is no
HARDWARE_REPRODUCED or REFUTED for the question about the write itself.

## Verdict

Do not conclude. The third interpretation rule applies: gadget drops / reset
-> firewall or abort, with no further conclusion about the NS/EL3 barrier.

Two caveats that prevent even choosing between "firewall at EL3" and
"logic gate":

1. The SMC did not drop the gadget. `dcache flush pos` and the RESULT read
   worked after `trigger false`. The first operation that failed was the
   hostile MREAD of 0x05100000, which is Secure and which
   `round59/04-diag-stub.md` itself marks as unreadable by MREAD. The reset is
   tied to that NS read of Secure memory, a knowingly invalid operation, not demonstrably to a write by BL31.
2. x0=0 is ambiguous, and there is an indication that the stub did not execute. RESULT was zeroed
   before the trigger and came back all zeros. `trigger false -> b'failed:'` is exactly
   the native value of the oracle; in `reports/plan-smc-gate-neutralize-magisk.md`
   Phase 1 the GO criterion for host code execution was precisely
   `false -> success` after injecting `mov w0,#0 ; ret` and pointing the handler to the
   stub. Here the result was the NO-GO criterion. Besides, the tool only does
   `dcache flush`, without `icache flush` (idx 60 exists, per `reports/kernel`),
   which is required for self-modifying code. Do not claim "SMC returned 0".

There is no evidence of plaintext written to 0x05100000 (MREAD failed, and the area
is Secure). There is no evidence of a logic gate (x0 was not confirmed as
the real SMC return). There is evidence of a reset. Question unanswered in this
session; do not promote anything in CURRENT_STATE.md.

## Files

- `/tmp/round60/baseline/*.bin` (4 dumps)
- `/tmp/round60/run_ff40-bl31-win.log` (tool output)
- `/tmp/round60/logs/usb_watch_run.log`, `usb_watch.log`
- `/tmp/round60/evidence.txt`
