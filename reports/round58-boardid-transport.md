# round58 boardid transport (hardware run, 2026-10-02)

## Objective

Round57 static round said `x2 == [images+0x100]` (same object) and closed every
post-`fdt_chosen` copy/swap, leaving content UNKNOWN at runtime. Round56 already
proved the whole string reverts (`ZZ->US` + `fastboot->normal`) but used a marker
that also existed stock. This round repeats the transport with a third inert
same-length field, `androidboot.boardid` (`3 -> 7`), that is present in the
storeargs template (`androidboot.boardid=${boardid}`), independent of
`selinux` and `wificountrycode`, and re-verifies with the same fresh-pointer htab
method plus the round56 control.

Result:

```text
REFUTED AGAIN for this form: inert androidboot.boardid=7 handed to bootm, ro.boot.boardid=3 in Android
```

## Run

Same shape as round52/53/56, RAM-only, no saveenv/flash/erase/update/recovery.

Pre-boot (fresh boot via `adb reboot fastboot` + `fastboot oem update 5000`,
re-hunted, nothing reused blind; stage 16 confirmed `raw 00 07 00 10`):

```text
htab obj table=0x33e2d650 size=0x209 filled=0x4a
entry bootargs: (514, key 0x33e2ac0, data 0x33e0baf0)
entry boardid:  (57,  key 0x33e1fb0, data 0x33e0d0b0)
baseline bootargs 832 B sha8 c5a4b5e3  androidboot.boardid=3 selinux=enforcing reboot_mode=fastboot
baseline bootargs byte-identical to round56 baseline sha8 c5a4b5e3
setenv boardid 7 -> success
test ${boardid} = 7 -> success / = 3 -> failed:
run storeargs -> success
fresh entry514 data 0x33e0baf0 -> 0x33e10750, 832 B sha8 a69c9f7d
  androidboot.boardid=7, androidboot.selinux=enforcing, androidboot.reboot_mode=fastboot
single-byte diff vs baseline at offset 681 ('3' -> '7'), all other 831 bytes identical
```

Boot (E4 pair, two separate bulkcmds, `imgread` reply checked before `bootm`):

```text
imgread kernel boot 0x1080000 -> success
bootm 0x1080000 -> USB drop (E4 signature)
```

Android returned stock. Oracle:

```text
ro.boot.boardid        = 3      (written 7, reverted)
ro.boot.selinux        = enforcing
ro.boot.reboot_mode    = normal
ro.boot.wificountrycode= US
getenforce             = Enforcing
```

Primary oracle `/proc/device-tree/chosen/bootargs` and `/proc/cmdline` are both
`Permission denied` for `u:r:shell:s0` on this build (already known, confirmed
again here, avc denials recorded in logcat). So this run has no in-kernel
oracle and cannot separate "BL33 delivered stock" from "Linux re-derived".

## Reading

The boardid marker reverted exactly like the round56 inert wifi marker, with
the rest of the string identical (single-byte diff in, whole-field revert out).
Nothing distinguishes selinux/wificountrycode/boardid: three different fields,
all revert, so the pattern is a whole-string or whole-object event, not a
field filter. Static analysis already removed every BL33 explanation for it
(round57: single field identity, no post-fixup copy, no BL33 literal emitter).
That leaves the pair left open after this run:

1. env/FDT content at `fdt_chosen` time is not the string we handed to `bootm`
   (some rebuilder between the verified htab read and `fdt_chosen`), or
2. the blob reaching EL1 is not the blob `fdt_chosen` wrote (pointer proven
   same field statically, runtime value unobserved), or
3. init/Linux does not consume `/chosen/bootargs` verbatim (no in-kernel oracle
   on this build, so untested).

Round58 does not move the boundary, it confirms the previous negative is not a
field-specific artifact and that the reproducible signature is: any inert
same-length `androidboot.*` field in the storeargs template reverts whole-string.
What it does add is a clean control: `boardid` has an independent env source
(`boardid` variable, distinct htab entry idx 57) and still reverts.

## Artifacts

* `reports/round58-boardid-transport/session_run.log`
* `htab_bootargs_baseline_832.bin` (c5a4b5e3, stock, == round56 baseline)
* `htab_bootargs_7_832.bin` (a69c9f7d, `androidboot.boardid=7`)
* `table_baseline.bin`, `table_after_setenv.bin`, `table_after_storeargs.bin`
* `htab_obj_37ee7278.bin`
* `logcat_kernel.txt` (987 lines, no `Command line:` line, SELinux avc denials
  for device-tree reads), `devicetree_chosen_bootargs.txt`,
  `proc_cmdline.txt` (both Permission denied)
* `getprop_ro_boot_boardid.txt`, `getprop_ro_boot_selinux.txt`,
  `getprop_ro_boot_reboot_mode.txt`, `getprop_ro_boot_wificountrycode.txt`,
  `getprop_all.txt`, `getenforce.txt`
* `cmdline_cmp.txt` (four-way comparison of r56/r58 cmdlines)

RAM-only, no saveenv/flash/erase/update/recovery, marker died with `bootm`.
Device healthy stock Android (`dev.bootcomplete=1`).

## Validation

* `python3 tools/run_tests.py` -> `126 tests, OK`.
* `git diff --check` clean.

## Next

Per round57 the only experiment with a real discriminator needs an in-kernel
oracle (device-tree or `/proc/cmdline`), which this build denies for shell.
The remaining cheap options are all Linux-side and unproven
(`CONFIG_CMDLINE` is empty; `init`/`ueventd` cmdline parsing was never
audited), so no further boot is justified on the evidence this round produced.
