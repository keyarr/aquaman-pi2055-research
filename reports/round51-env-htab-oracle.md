# round51 env htab oracle (hardware run, 2026-10-02)

## Objective

Prove in hardware whether `0x33e18000` is the authoritative env store or a stale shadow copy, using `test ${EnableSelinux}` as the htab-reading oracle.

## Known architecture

```text
0x33e18000 = shadow/stale arena (CONFIRMED_SHADOW_COPY this round, hardware)
env_htab @ 0x37ee7278 (table 0x33e2d650, size 0x209) = runtime authoritative structure
```

`env_get` (`0x37e58920`, FIND) and `env_set` (`0x37e58294`, ENTER) share the same htab object via `hsearch_r` (`0x37ea9a58`). `test ${VAR}` expands via `env_get`, so it observes the htab, not the arena.

## Hardware proof

Entry: already at `1b8e:c003`, identify ver 0.7 stage 16. No `adb reboot`, no boot.

Baseline (no mutation):

```text
bulkcmd "test ${EnableSelinux} = enforcing" -> success
bulkcmd "test ${EnableSelinux} = permissiv" -> failed:
```

Oracle functional. `test 1 = 1 -> success`, `test 1 = 2 -> failed:`.

setenv -> htab -> env_get:

```text
bulkcmd "setenv EnableSelinux permissiv" -> success
bulkcmd "test ${EnableSelinux} = permissiv" -> success
bulkcmd "test ${EnableSelinux} = enforcing" -> failed:
```

Arena at `0x33e1d6c4` still `enforcing` while htab data at `0x33e32910` is `permissiv`. So `setenv` reaches the parser without touching the arena.

Restore:

```text
bulkcmd "setenv EnableSelinux enforcing" -> success
bulkcmd "test ${EnableSelinux} = enforcing" -> success
```

WRITE stale arena:

```text
WRITE 0x01 9B `permissiv` @ 0x33e1d6c4, readback `permissiv\0active_slot\0normal\0avb` OK
htab 0x33e32910 still `enforcing`
bulkcmd "test ${EnableSelinux} = permissiv" -> failed:
bulkcmd "test ${EnableSelinux} = enforcing" -> success
```

Then restored arena with WRITE `enforcing`, readback verified, final oracle sane. No reboot issued.

Result: `CONFIRMED_SHADOW_COPY`.

```text
WRITE to the stale arena -> does not change env_htab -> env_get keeps seeing enforcing
```

## Pointer correlation

Live, read-only first, re-hunted this session:

```text
htab obj @ 0x37ee7278: table=0x33e2d650 size=0x209 filled=0x4a
table @ 0x33e2d650, 521 entries * 0x28, 74 used, sha8 d519af19
EnableSelinux: idx 262 entry=0x33e2ff40 key=0x33e328f0 data=0x33e32910 flags=0x0 value=enforcing
bootargs: idx 514 entry=0x33e326a0 key=0x33e32ac0 data=0x33e35bd0 flags=0x0
initargs: idx 11 entry=0x33e2d808 key=0x33e338b0 data=0x33e338d0
storeargs: idx 151 entry=0x33e2ede8 key=0x33e343b0 data=0x33e343d0
storeboot: idx 234 entry=0x33e2fae0 key=0x33e347a0 data=0x33e347c0
arena EnableSelinux: name@0x33e1d6b6 val@0x33e1d6c4 len 9
arena bootargs: val@0x33e1d73f len 832
```

Authoritative answer to the session question:

```text
EnableSelinux htab entry = 0x33e2ff40
data pointer = 0x33e32910
value = enforcing (restored, clean)
```

Note: after `setenv permissiv` + `setenv enforcing` the data pointer stayed `0x33e32910`. Same-length free+strdup reused the same chunk, so the stale-vs-live split was observed as content divergence (htab `permissiv` vs arena `enforcing`), not as a pointer move. Allocator churn is visible as 94 changed bytes in `0x33e18780-0x33e188db` heap-header region with zero diffs in the env-string region.

No WRITE was done to the htab data pointer in this session, per rule.

## Round48 / Round49 correction

Round48 poked the expanded `bootargs` value inside the arena and round49 poked `EnableSelinux` in the arena plus a `setenv` control, but both observed via fixed arena addresses (`0x33e1d73f`, `0x33e1d6c4`). This session shows `setenv` does not rewrite the arena and the parser does not read the arena, so:

> the previous experiments did not reach the authoritative runtime object; their verdicts about value consumption must be reinterpreted according to the new oracle.

History preserved: round48 stays REFUTED for the direct-arena-poke form, round49 stays REFUTED for the stale-oracle observation, with the caveat that the effective htab leg (`setenv -> htab -> storeargs -> htab bootargs`) was never measured through an htab-reading oracle and remains open, not refuted. No claim is made about `bootargs` reaching Linux or about root.

## Next experiment (offline proposal only, not executed)

Target the htab live data pointer, never the arena:

1. `data` at `0x33e32910` points directly to a NUL-terminated string (`enforcing\0`), heap resident (adjacent chunk at `0x33e32930` is `active_slot` key, confirming heap packing).
2. Buffer is heap (dlmalloc chunk, `0x20`-spaced keys/data), not `.text`/`.rodata`.
3. Available size: current allocation holds 10 bytes (`9+NUL`); same-length overwrite (`enforcing`<->`permissiv`) fits with zero allocator risk. Longer strings need a new chunk and an entry pointer update, not an in-place WRITE.
4. Same-length direct byte WRITE to `0x33e32910` should be semantically equivalent to `setenv` for the `test` oracle, but this was NOT tested here.
5. Risk for same-length: low (no metadata touched, NUL preserved, neighbours are separate chunks). Risk for longer: high (chunk overflow into `active_slot` key).
6. Pointer stability: stable across two same-length `setenv` cycles this session (`0x33e32910` both times), but per-boot heap base must always be re-hunted; never hardcode.
7. `env_get` returns exactly this pointer for `EnableSelinux` on the FIND path (device disasm `ldr x0,[ENTRY,#8]` after `hsearch_r` FIND on the same htab).

Minimum next run (one session, RAM-only, no boot): re-hunt, baseline `test`, WRITE 9 B `permissiv` @ live htab data ptr (not arena), readback, `test permissiv -> success` as oracle, restore via `setenv enforcing`, final `test enforcing -> success`. If that passes, the follow-up is `setenv EnableSelinux permissiv + run storeargs + test ${bootargs}` shape to observe the template leg through the htab, still without `bootm`.

## Artifacts

* `reports/round51-env-htab-oracle/session_run.log` (baseline, setenv, test, restore, WRITE, oracle)
* `reports/round51-env-htab-oracle/hunt_33e18000_32k_initial.bin` (32768 B, sha8 `4ced8a1d`)
* `reports/round51-env-htab-oracle/hunt_33e18000_32k_final.bin` (32768 B, sha8 `a846264a`, header churn only)
* `reports/round51-env-htab-oracle/htab_table_33e2d650.bin` (20840 B, sha8 `d519af19`)
* `reports/round51-env-htab-oracle/htab_table_33e2d650_final.bin` (same sha)
* `reports/round51-env-htab-oracle/htab_obj_37ee7278.bin` (64 B)
* `reports/round51-env-htab-oracle/EnableSelinux_htab_33e32910.bin`, `EnableSelinux_arena_33e1d6c4.bin`

RAM-only run: no saveenv, flash, erase, update, storeboot, bootm, imgread, recovery, USB burning, GhostLock, H16, AVB, SMC, DTB change, .text patch, payload. Restored in-session; residue dies with reboot.

## Validation

* `python3 tools/run_tests.py` -> `126 tests, OK` (see session tail).
* `git diff --check` clean.
