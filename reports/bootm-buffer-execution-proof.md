# bootm-buffer-execution-proof — FILL AFTER the device test (do NOT fill offline)

status: PENDING (no bytes executed yet; this file is a template)

## run log (append one row per run, times measured T0=injection send)

| run | image | size | outer | returned after | host reply | bootreason after | notes |
|---|---|---|---|---|---|---|---|
| control | INVALID 4 KiB | 4096 | n/a (reject baseline) | ? | FAIL (expected) | ? | establishes reject timing |
| A | m1_boot.img | 4096 | 0x0FA0 | ? | FAIL (expected, ignore) | ? | short delay + PSCI reset |
| B | m1b_boot.img | 4096 | 0xEA60 (15x) | ? | FAIL (expected, ignore) | ? | long delay + PSCI reset |

## execution criteria (ALL must hold for PROVEN)

1. control returns in T_reject (prior baseline 15-20 s; re-measure).
2. A returns in T_reject + delay_A (clearly above control, outside USB/watchdog jitter).
3. B returns in T_reject + ~15x delay_A (clearly above A).
4. B - A difference is large (tens of seconds), impossible to explain by
   reject/reset jitter, USB timeout, watchdog, or bootm timeout.
5. no flash/env/misc touched: `fastboot getvar` table unchanged,
   bootreason == plain reboot reason (prior: `reboot,fareboot`),
   device boots Android normally afterwards.

## fixed parameters (already proven offline)

- X = 0x10200000 (CONFIG_USB_FASTBOOT_BUF_ADDR, include/g_dnl.h:18)
- format = ANDROID! v0, page 2048, kernel 112 B, COMP_NONE
- kload/entry = 0x1080000, ARM64 magic 0x644d5241 at kernel+0x38
- sink = `set_active:;bootm 0x10200000` → `set_active_slot ;bootm 0x10200000`
  (see reports/set-active-sink.md; first command dies on argc pre-storage)
- stub = delay loop + PSCI SYSTEM_RESET 0x84000009, no eMMC/env/UART/Linux

## if PROVEN, record here

- timing A: ___, timing B: ___, control: ___
- observable after: ___
- verdict: EXECUTION PROVEN / NOT PROVEN
- next step (only if proven): size a real kernel under 24 MiB for the X path.
