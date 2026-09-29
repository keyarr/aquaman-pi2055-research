# bootm-buffer-execution-proof — template, NEVER FILLED

> **Orphan file. The experiment was conducted, and the outcome is the opposite of what
> this template expected.** This file remained as a draft while the actual proof
> was recorded in `reports/buffer-equals-loadaddr-proof.md`. Preserved here for
> archival record, not as a source of truth.
>
> Outcome: **EXECUTION NOT PROVEN.** None of our bytes executed. M1b
> (15x delay) and M2 (real 26 MB kernel) returned in 18-19 s, identical to the
> INVALID control at 16 s. See `reports/fastboot-boot-verdict.md`.
>
> Two errors in this template that cost time:
> 1. `X = 0x10200000` ("fixed parameters" section) — refuted. Originated from the khadas
>    header, never measured on this build. The actual default is `loadaddr`.
> 2. The "PROVEN" criteria below assumed an unsuccessful `bootm` would
>    respond differently from a rejected one. It does not: a failing `do_bootm`
>    leads to `do_reset` (cmd_bootm.c:143-147 -> f_fastboot.c:580), yielding
>    the exact same reboot to the host. The two cases are indistinguishable
>    by timing alone, which is why the original M1 "proved" execution where none occurred.
>
> What actually distinguished execution from rejection was the correct criterion,
> recorded in `buffer-equals-loadaddr-proof.md` E7: the **same** pair
> (signed, plaintext) at the **same** address. That is where the SMC decides.

original status: PENDING (never populated; the experiment was conducted in another file)

## run log (never populated; T0=injection send)

| run | image | size | outer | returned after | bootreason | actual outcome |
|---|---|---|---|---|---|---|
| CTRL | INVALID 4 KiB | 4096 | n/a | 16 s | empty | rejected (baseline) |
| M1a | m1_boot.img | 4096 | 0x0FA0 | 17 s | empty | rejected |
| M1b | m1b_boot.img | 4096 | 0xEA60 (15x) | 18 s | empty | rejected, **zero shift** |
| M2 | real kernel 26 MB | 27246592 | n/a | 19 s | empty | rejected |

M1b with 15x delay exhibiting zero shift and M2 (real kernel) returning in normal boot
time are incompatible with execution. Sources: `reports/fastboot-boot-verdict.md`.

## execution criteria (ALL must hold for PROVEN)

1. control returns in T_reject (prior baseline 15-20 s; re-measure).
2. A returns in T_reject + delay_A (clearly above control, outside USB/watchdog jitter).
3. B returns in T_reject + ~15x delay_A (clearly above A).
4. B - A difference is large (tens of seconds), impossible to explain by
   reject/reset jitter, USB timeout, watchdog, or bootm timeout.
5. no flash/env/misc touched: `fastboot getvar` table unchanged,
   bootreason == plain reboot reason (prior: `reboot,fareboot`),
   device boots Android normally afterwards.

## fixed parameters

- X = 0x10200000 ~~(CONFIG_USB_FASTBOOT_BUF_ADDR, include/g_dnl.h:18)~~
  **REFUTED.** Was from the khadas reference tree header, not a measurement. The
  actual injection address is `loadaddr` (0x1080000). See
  `reports/fastboot-memory-flow.md` §2-4.
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
