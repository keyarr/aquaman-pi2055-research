# BL33 round 46: same-cycle WRITE -> dispatch -> decision -> observable

date: 2026-10-02. live, one Optimus session (`1b8e:c003`, stage 16).
entry: `fastboot oem update 5000` from fastboot (the `FAILED (Status
read failed)` is expected, the gadget switches mode). exit: session alive at end,
`1b8e:c003` still enumerated. no flash/eMMC/efuse/saveenv/reset/reboot,
no RUN/MODIFY, no `bootm`, no script trigger with destructive tail.
all with save/restore/verify. logs and bins in
`reports/round46-same-cycle/`, script in `session_run.py`.

base: `reports/round14-bl33-persist/bl33-37e18000.bin` (base `0x37e18000`).
context: round44 (decision map), round45 (bootdelay poke with restore, post-reset
effect NOT PROVEN due to volatile RAM).

## baseline (revalidated at start and end, 5/5 + 6/6)

failed:: `false`, `test 1 = 2`, `test`, `env print foo`, `run foo1234`.
success: `true`, `test 1 = 1`, `echo`, `version`, `help`.
note: `fastboot oem <cmd>` on this build returns only `AMLOGIC`+`OKAY` for everything,
no discrimination. `failed:/success` oracle only exists in Optimus bulkcmd
(`0x34`). `mmc info` FLAKY, do not use. mread size 8 flaky, cross-check with
`0x02` or `>=0x40`. full command only + drain `0x33`.

## Exp1: FILL 1 pair test->true, with restore (PASS)

target `0x37f62180` (test idx100 +0x10). high 4B already zero, 1 FILL pair is enough.

```text
SAVE    slot = 74 67 e3 37 00 00 00 00 (=0x37e36774)
FILL    (0x37f62180, 0x37e3676c) -> MID = 6c 67 e3 37 00 00 00 00
TRIGGER `test 1 = 2` -> success (was failed:); `test 1 = 1` -> success
RESTORE FILL (0x37f62180, 0x37e36774) -> 74 67 e3 37 00 00 00 00
RE-TRIGGER `test 1 = 2` -> failed:
```

closed chain without reboot: FILL -> `cmd_tbl[i].cmd` -> legit handler ->
different branch -> bulkcmd reply. every `if test` in
storeboot/switch/init changes together, before the first `bl aml_sec_boot_check`.

## Exp2: WRITE 1B avb2 1->0, no trigger, with restore (PASS)

dynamic hunt this session: `mread 0x33e18000 32k`, pattern
`active_slot normal avb2 1 baudrate` -> val @ `0x33e1d6e6` (same address as
round43; hunt sha `1c5e262d...` identical, deterministic layout on this boot).

```text
SAVE    live 8B = 31 00 62 61 75 64 72 61 ('1' + start of 'baudrate')
WRITE   0x01 1B <- 0x30 -> MID = 30 00 62 61 75 64 72 61, neighbour intact
RESTORE 0x01 1B <- 0x31 -> 31 00 62 61 75 64 72 61, oracle alive (test 1 = 2 -> failed:)
```

env writability proven by readback with neighbour intact. decision via
script (`run storeboot`, `run upgrade_check` with step=3, `run switch_bootmode`
outside cold_boot) NOT triggered: all have destructive tails
(`bootm`/`update`/`recovery`/`fastboot`). safe trigger for arbitrary var
stays PROBABLE, not proven. `test`/`itest` via bulkcmd do no getenv
(`${}` expansion only in script parser), so they are no direct oracle
for env value.

## Exp3: read-only dumps (PASS)

* `cmdtbl_37f60eb0.bin` 5568B live==offline, 0 diffs.
* slots `false/run/fdt/get_rebootmode` at originals (`64 67 e3 37`,
  `04 ea e5 37`, `2c 85 e2 37`, `78 04 e6 37`).
* `stored_bootdelay 0x37f723d8` = 0 (burning-entry residue; `1` is
  normal-boot default, round44 corrected by round45).
* live env: `bootdelay=1` @`0x33e1daa0`, `bootcmd=run storeboot` @`0x33e1da88`,
  `active_slot=normal` @`0x33e1d6da`, `boot_part=boot` @`0x33e1d731`,
  `loadaddr=1080000` @`0x33e1e0ef`, `upgrade_step=2` @`0x33e1f1d8`,
  `reboot_mode=fastboot` @`0x33e1e1df`.
* `dtb_header_01000000.bin`: magic `d00dfeed`, totalsize 58280. DTB readable
  in RAM, never poked. own validation exists in code (`0x37e2a030`:
  `Decrypt dtb: Sig Check`, `check_valid_dts`).

## verdict

HARDWARE_REPRODUCED this session: same-cycle redirect with oracle (Exp1);
1:1 env WRITE/FILL with restore and intact neighbour (Exp2); live==offline map
(Exp3). NOT PROVEN: safe script trigger that observes env mutation via
return code (destructive tails block it); any bypass of
`SMC 0x820000ff` (15 sites, fixed type per call site: kernel
`0x100,0x1080000,0x500,7`, boot head `0x40,...,0x1800000,7`, dtb/store
`0x40,...,0x3fe00`, query/efuse `0x10/0x11/0x12/0x20`); `go`/`booti`/`autoscr`
absent from cmd_tbl (116 checked, `autoscr` only in
`recovery_from_udisk` string, dead branch); `usbboot` print only.
Live env storage is writable; semantic consumption of the mutation by a
relevant script is not demonstrated.

## rest

honest next: find a script (or fragment via `run` + argv) that
branches on mutable env and returns a distinct code WITHOUT falling into
bootm/update/recovery/fastboot; or accept that env oracle goes via
redirect, not script trigger. do not repeat blind `run storeboot`, do not
repeat post-reset bootdelay poke as novelty, do not touch DTB before
mapping which `fdt` subcommands BL31 covers.
