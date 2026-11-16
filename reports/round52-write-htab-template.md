# round52 WRITE htab data + template leg (hardware run, 2026-10-02)

## Objective

Close the two legs round51 left open: prove a host WRITE to the live htab data pointer reaches `env_get`, and prove the template leg `setenv -> storeargs -> htab bootargs` through fresh htab pointers.

## Result

```text
WRITE htab data -> env_get: HARDWARE_REPRODUCED (oracle flips, arena untouched)
template leg both directions: HARDWARE_REPRODUCED (fresh-ptr reads, pointer moves, single-field diffs)
```

## Phase A: WRITE to the live data pointer

Re-hunted this session (same boot as round51: table sha8 `d519af19`, hunt sha8 `a846264a` at entry).

```text
baseline: test enforcing -> success / test permissiv -> failed:
WRITE 0x01 9B permissiv @ 0x33e32910 (htab EnableSelinux data, NUL preserved)
readback: permissiv + identical heap tail, arena 0x33e1d6c4 still enforcing
test permissiv -> success / test enforcing -> failed:
restore: setenv enforcing -> test enforcing -> success
```

Host bytes in the authoritative store are consumed by the parser. The write primitive now has a proven consumer short of the kernel.

## Surprise: round49's product was still in the htab

Fresh entry514 read showed htab `bootargs` (832 B, sha8 `df6c9576`) with `androidboot.selinux=permissiv` while htab `EnableSelinux` was `enforcing` and the arena said `enforcing`. Single-field diff at +230. Saved before touching anything.

Live `preboot` (htab idx8, 152 B) reads:

```text
run cmdline_keys;run bcb_cmd; run factory_reset_poweroff_protect;run upgrade_check;run init_display;run storeargs;bcb uboot-command;run switch_bootmode;
```

So `storeargs` runs at every boot via `preboot` (the boot-time rebuilder behind E1's `reboot_mode` divergence), and the only `storeargs`-with-`permissiv` event in this boot is round49's control run. Round49 measured the arena instead of the htab: its `REFUTED` template verdict is overturned by its own product, still present. No reboot since round49 is inferred from pointer/sha continuity, but the controlled A/B below does not depend on it.

## Controlled mirror + A/B (no archaeology needed)

```text
run storeargs (enforcing held) -> success, ptr 0x33e35bd0 -> 0x33e13990, value enforcing (c5a4b5e3)
A: setenv permissiv + run storeargs -> ptr 0x33e10960, 832 B df6c9576 == archaeological sha (byte-identical)
B: setenv enforcing + run storeargs -> ptr 0x33e10960 (same-size reuse), 832 B c5a4b5e3
A vs B: one field differs at +230, 823 other bytes identical
```

`setenv` and WRITE are interchangeable inputs to the htab; `storeargs` deterministically rebuilds htab `bootargs` from htab inputs with pointer moves on every rebuild.

## Heap-churn self-demonstration

After 3x `storeargs`, entry262's data pointer moved `0x33e32910 -> 0x33e0d0e0` (key stable). A hardcoded read of the old address returned allocator bytes while the oracle stayed correct. Fixed-address reads go stale; fresh-pointer + oracle reads do not. Final coherent state: htab `enforcing`/`enforcing`, arena `enforcing`/`enforcing`, oracle sane, `env_id` 65.

## Round48 / Round49 correction

> os experimentos anteriores nao atingiram o objeto runtime autoritativo; seus vereditos sobre o consumo do valor devem ser reinterpretados conforme o novo oracle.

Concretely: round49's template `REFUTED` becomes `REFUTED-for-stale-oracle, REPRODUCED-through-htab`. Round48's direct-arena-poke `REFUTED` stands (wrong object), and E1's double-field divergence is now triple-explained (stale arena + preboot rebuilder + htab authority). Transport `htab bootargs -> kernel` remains the single open leg; nothing here boots, roots, or touches Linux.

## Next experiment (not executed)

`imgread kernel boot 0x1080000` + `bootm 0x1080000` with htab `bootargs` carrying a behaviourally inert marker built via `setenv`+`storeargs` (never arena poke), oracle `getprop ro.boot.*` after adb returns. That is the E1 shape with the oracle fixed; it costs one reboot and is a separate session by rule.

## Artifacts

* `reports/round52-write-htab-template/session_run.log`
* `htab_bootargs_permissiv_832.bin` (df6c9576, archaeological) == `htab_bootargs_A_permissiv.bin` (controlled)
* `htab_bootargs_B_enforcing.bin` / `htab_bootargs_enforcing_832.bin` / `htab_bootargs_final_832.bin` (c5a4b5e3)
* `arena_bootargs_enforcing_832.bin` (8bd04170, shadow unchanged throughout)
* `htab_preboot_value.bin` (152 B), `htab_obj_37ee7278.bin`, `htab_EnableSelinux_final.bin`
* `hunt_33e18000_32k.bin` (def5f352), `table_{pre,post,final,final2}.bin`

RAM-only, restored coherent; residue dies with reboot.

## Validation

* `python3 tools/run_tests.py` -> `126 tests, OK`.
* `git diff --check` clean.
