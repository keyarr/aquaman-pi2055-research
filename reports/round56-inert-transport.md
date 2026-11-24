# round56 inert FDT identity (hardware run, 2026-10-02)

## Objective

Case B of round55: test FDT identity, not SELinux. Change an inert field
that currently agrees (`androidboot.wificountrycode` US->ZZ, same
length, no boot effect) via `setenv`+`run storeargs`, verify via
fresh-ptr htab + oracle, then the E4 pair `imgread`+`bootm`, oracle
`getprop ro.boot.*`.

## Result

```text
REFUTED for transport, PROVEN for identity: inert ZZ reverted to US (whole-string revert, not selective)
```

Pre-boot (fresh boot via `fastboot oem update 5000`, re-hunted, nothing reused):
htab obj `0x37ee7278` table `0x33e2d650` size `0x209` filled `0x4a`.
`test 1=1 -> success`, `1=2 -> failed:`, `test ${wifi_ccode}=US -> success`.
Baseline htab `bootargs` 832 B sha `c5a4b5e3` (`enforcing`/`US`/`fastboot`).
`setenv wifi_ccode ZZ -> success`, `test ZZ -> success`, `test US -> failed:`.
`run storeargs -> success`, fresh entry514 data moved
`0x33e0baf0 -> 0x33e0e4b0`, 832 B sha `e1e32443` with
`androidboot.wificountrycode=ZZ`, `androidboot.selinux=enforcing`,
`androidboot.reboot_mode=fastboot`. Assert ZZ+enforcing PASS.

`imgread kernel boot 0x1080000 -> success` (checked BEFORE, would abort otherwise).
`bootm 0x1080000 -> USBError(19)` disconnect (E4 signature). Session ended
by design.

Android returned to stock. Oracle: `ro.boot.wificountrycode=US`,
`ro.boot.selinux=enforcing`, `ro.boot.reboot_mode=normal`,
`getenforce=Enforcing`. Full `getprop | grep ro.boot` saved.

Reading: the inert one reverted together with `fastboot->normal`. It was not a
selective selinux rewrite. It was the whole string / lost-substituted FDT.
Stop testing selinux; the problem is blob identity, not a field filter.

## Artifacts

* `reports/round56-inert-transport/session_run.log`
* `htab_bootargs_baseline_832.bin` (c5a4b5e3, stock)
* `htab_bootargs_ZZ_832.bin` (e1e32443, what bootm received)
* `table_baseline.bin` (a1576484), `table_after_setenv.bin`, `table_after_storeargs.bin`
* `htab_obj_37ee7278.bin`
* `getprop_ro_boot.txt`, `getprop_ro_boot_wificountrycode.txt`, `getprop_ro_boot_selinux.txt`, `getprop_ro_boot_reboot_mode.txt`, `getenforce.txt`

RAM-only, no saveenv/flash/erase/update/recovery. Marker died with bootm.
Device healthy stock Android.

## Validation

* `python3 tools/run_tests.py` -> `126 tests, OK`.
* `git diff --check` clean.
