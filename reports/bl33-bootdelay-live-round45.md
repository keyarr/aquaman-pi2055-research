# BL33 round 45: bootdelay poke live, with restore

date: 2026-10-02. live, stage 16 (TPL/BL33). entry via
`adb reboot fastboot` + `fastboot oem update 5000` -> `1b8e:c003`.
exit via bulkcmd `reboot` (normal PSCI, not `reset`) -> `2717:4e40`
in ~18 s, adb present. no flash/eMMC/efuse, nothing persistent.

## oracle (10/10, revalidated at start and between each step)

failed: `false`, `test 1 = 2`, `test`, `env print foo`, `run foo1234`.
success: `true`, `test 1 = 1`, `echo`, `version`, `help`.

## map (hunt 0x33e18000 32k, sha 1c5e262d...)

- live env `bootdelay` value `0x33e1daa0` = `1`
- `bootcmd` value `0x33e1da88` = `run storeboot`
- `stored_bootdelay` `0x37f723d8` = `0` on this entry (correction to
  round44: value is path-dependent; `1` is the normal-boot default,
  `0` is residue from burning entry; code target is OFFLINE_ONLY,
  value measured)
- gate `0x37e24500 cmn` + `0x37e24504 b.eq`, dispatcher
  `0x37e5f6e8 ldr` + `0x37e5f6fc blr`, slots `test 0x37f62180`,
  `false`, `run` all live==offline

## writes (all with immediate restore, live oracle between steps)

1. arena `0x37800000` FILL `0 -> a5a55a5a -> 0`. PASS.
2. `stored 0x37f723d8` FILL `0 -> ffffffff -> 0`, mread `0x200`
   checking. PASS. clean target, no neighbour.
3. env `0x33e1daa0` WRITE `1 -> -1 -> 1`, byte-exact restore.
   PASS with caveat: the mid state ate 1 neighbour byte
   (`bootup_offset` -> `ootup_offset`). `-1` does not fit cleanly in that
   string; a clean 1:1 swap would be `1`->`0`. FILL here would be worse (4B).

## measured limit

RAM poke does not survive the reset needed to observe the
boot effect (reset clears heap+BSS before `bootdelay_process`
re-reads). writability + restore + liveness: HARDWARE_REPRODUCED in-window.
boot deviation observed post-reset: NOT PROVEN, stays PROBABLE
via code + mode-7 precedent (round35).

## rest

exp B/C/D read-only, see session. `test->true` not repeated as
proof, slot verified intact. final check: arena zero,
original slots, env restored, stored 0, oracle 5/5.
