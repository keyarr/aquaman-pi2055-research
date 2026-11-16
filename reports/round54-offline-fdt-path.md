# round54 offline FDT path (no hardware, 2026-10-02)

## Objective

Narrow round53's unexplained link with device-binary reads only: enumerate every
producer/consumer of `/chosen/bootargs` and kill competing-source candidates one
by one. No boot, no device state touched.

## Result

```text
9/9 consumers mapped; all BL33 writers use env_get (our string).
kernel entry = eret (no SMC). running kernel = bootloader-cmdline-only.
remaining gap: exactly one link (fixup ran+succeeded on our path?).
```

## Census (re-derived, ADRP+ADD to `0x37ebf453`)

| site | function | disposition |
|---|---|---|
| `0x37e21240` | linux-gate | env_get -> fixup stage `0x37e5b800` if `[images+0x108]` |
| `0x37e24dbc` | bootm | rebuild `"%s %s %s"` + setenv (append-only) |
| `0x37e24e88` | bootm | fresh env_get, defendkey gate (recovery-only) |
| `0x37e26284` | bootvx-dispatch | env read, strcpy leg, no FDT write |
| `0x37e26404` | bootvx-dispatch | env read, fallback string |
| `0x37e264d8` | do_bootvx_fdt | env -> `/chosen` write (same content) |
| `0x37e2980c` | fdt_chosen | env -> `fdt_setprop(/chosen,bootargs)` |
| `0x37e57b5c` | rpmb_state fixup | HW -> htab rewrite; dispatch-only, no callers, not on path |
| `0x37e5b9e0` | bootm_load_os | env + header-cmdline + setenv (append-only) |

## Killed candidates

* bootm `verifiedbootstate` append: orange/green only.
* defendkey: recovery/update/factory_reset/upgrade_step==3 only.
* imgread setenvs: `0x%x` addr/size bookkeeping.
* header-cmdline append: `dtbo_idx/otg/buildvariant`, no selinux/reboot_mode.
* SMC-at-entry: kernel entry is eret EL2->EL1 (`x2`=FDT); E7 gate is verify-time.
* kernel builtin: running `/proc/config.gz` says `CONFIG_CMDLINE=""`, bootloader-only.
* fdt nospace: target blob has 6404 free bytes; `dtb_mem_addr=0x1000000`.
* fake_battery/bootreason from BL33: zero hits (bootreason plausibly BCB->init).

## Open (one link)

Fixup target == handoff blob (same `[images+0x100]`), reachable via OS table
`0x37eb5658`, yet hardware shows the stock pair. Unproven micro-points:
`[images+0x108]` gate value on `bootm 0x1080000` path, ft-blob validity at fixup
time, decrypt-skip ordering (`0x37e25d0c`), images-struct identity
(global `0x37f723e8` vs passed-down). Next static reads are listed in
`session_run.log`; no boot until one predicts enforcing+normal.

## Artifacts

* `reports/round54-offline-fdt-path/session_run.log` (full trace notes)
* `reports/round54-offline-fdt-path/running_config.gz` (5691 lines, running kernel)

## Validation

* `python3 tools/run_tests.py` -> `126 tests, OK`.
* `git diff --check` clean.
