# R1 secmon A/B fire - prepared plan, not executed

Status: PREPARATION ONLY. I did no push, insmod, fire, flash, fastboot, USB DL,
tracked-file edit, report edit or commit for this package. Every command below
is a proposal I wrote and have not executed. Device: `26919800005844922`.

The hypothesis under test is secmon under-reservation. The package keeps the
Image, module and initrd fixed; between the control fire and the test fire only
the DTB changes.

## Prepared package

| Artifact | sha256 |
| --- | --- |
| `out/r1-prep/secmon/aquaman-r1-secmon-fix.dtb` | `56e286c3ce7aad12fec3734cac003f40f864aa87f70687139f01796036014eba` |
| `out/r1-device/Image.clean` | `6c30b16ee7bdc99d62c08c86ef5c2212b736e7e6dab7bfaa1b1033e86e8ca045` |
| `out/r1-device/r1_kexec.ko.936aa4b7` | `936aa4b7d0ac987dcb6104f726c2075b4e428612e2c49e90497a0bbf80bd0eae` |
| `work/r1-kexec/android-probe/initrd-realinit-timeout.cpio.gz` | `1d2ac52ae0a9c740c38d9fa7e509584c75703677151f62a241ea196e80785e14` |
| Control DTB `work/r1-kexec/aquaman-r1-initrd-console.dtb` | `733d20f53bf5b4b18781633a9b7cfc360666c43f6c372b933775c39af940e41c` |

I regenerated the DTB offline with `work/r1-kexec/patch_dtb.sh` (current
version, with the secmon sed), 60053 bytes. Secmon values in the DTB:
`reserve_mem_size = <0x2300000>`, `size = <0x00 0x2400000>`,
`alloc-ranges = <0x00 0x5000000 0x00 0x2400000>`. initrd placeholders:
`linux,initrd-start = 0x2c87e000`, `linux,initrd-end = 0x2c8da09c`; the module
rewrites both with the real physical addresses at load. `skip_initramfs` is
absent; `dm=`, `root=/dev/dm-0` and `r1probe=DEADBEEF` are present.

Exact regeneration command (used, no fire):

```
cd /home/erick/Documentos/projetos/aquaman_9_PI_2055
CMDLINE="$(sed -e 's/loglevel=1/loglevel=8 ignore_loglevel/' -e 's/ramoops.console_size=0x4000/ramoops.console_size=0x20000/' work/r1-kexec/live-cmdline-r1.txt)" \
INITRD_START=0x2c87e000 INITRD_END=0x2c8da09c \
OUT_DTB=out/r1-prep/secmon/aquaman-r1-secmon-fix.dtb \
sh work/r1-kexec/patch_dtb.sh
sha256sum out/r1-prep/secmon/aquaman-r1-secmon-fix.dtb
dtc -f -I dtb -O dtb -o /dev/null out/r1-prep/secmon/aquaman-r1-secmon-fix.dtb
```

The hash matches `56e286c3...` and the `dtb -> dtb` round-trip is byte-identical
(the `node_name_not_empty` error at `/@c1108d80` is pre-existing in the stock
DTB with `-f`). Important: plain `CMDLINE="$(cat work/r1-kexec/live-cmdline-r1.txt)"`
does not reproduce the hash. The candidate's correct cmdline differs from that
file in two places: `loglevel=1` -> `loglevel=8 ignore_loglevel` and
`ramoops.console_size=0x4000` -> `0x20000`. I investigated this by comparing the
`bootargs` embedded in the candidate DTB with the file; with those two edits
the regenerated DTB is identical to the candidate. I used no other DTB.

Not to use in this package: recompiled module `202cbd51`, instrumented Image
`c9b4220d`, host DTB `work/r1-kexec/aquaman-r1.dtb` (`35985354...`, old secmon),
DTB `aquaman-r1-live-secmon.dtb` (`3f50b0cd...`, variant without initrd).

Chosen initrd: `/data/local/tmp/r1/initrd-realinit-timeout.cpio.gz`. This is the
wrapper I verified on the device: it mounts the root, clones the real `/init` and
waits 45 s with `wait4`; on a hang PID 1 exits with 107 and the kernel panics,
leaving a record in pstore. I have no other wrapper with a timeout mechanism
verified on the device. The round-11 wrapper (`aa7b1ec1...`) is no longer present
with that hash, so the comparison with round 11 is only contextual, not a strict
A/B.

## Pre-flight (read-only)

Baseline I observed on 2026-11-27, before this plan: serial
`26919800005844922`, `getenforce=Enforcing`, `sys.boot_completed=1`, root
`/odm/bin/su` with context `u:r:su:s0`, `/sys/fs/pstore/` empty, boot_id
`5371e603-0840-4911-a025-883be0b02baf`. Repeat before any action:

```
adb devices -l
adb -s 26919800005844922 shell 'getenforce; getprop sys.boot_completed; cat /proc/sys/kernel/random/boot_id'
adb -s 26919800005844922 shell /odm/bin/su -c "id; ls -la /sys/fs/pstore/"
adb -s 26919800005844922 shell 'cd /data/local/tmp/r1 && sha256sum Image r1_kexec.ko aquaman-r1-secmon-fix.dtb aquaman-r1-initrd-console.dtb initrd-realinit-timeout.cpio.gz'
sha256sum out/r1-device/Image.clean out/r1-device/r1_kexec.ko.936aa4b7 out/r1-prep/secmon/aquaman-r1-secmon-fix.dtb work/r1-kexec/android-probe/initrd-realinit-timeout.cpio.gz
```

Expected on the device: `Image = 6c30b16e...`, `r1_kexec.ko = 936aa4b7...`,
`aquaman-r1-secmon-fix.dtb = 56e286c3...`,
`aquaman-r1-initrd-console.dtb = 733d20f5...`,
`initrd-realinit-timeout.cpio.gz = 1d2ac52a...`. If any hash diverges, stop and
do not fire.

## Single sentinel

This round's unique value: `0x5244D301` = `1380242177` decimal. Physical address
`0x075fb000`, inside the retained ramoops region. I write and read it back
before the fire; if the readback is not `1380242177`, I abort without firing.

Write (not executed):

```
adb -s 26919800005844922 shell /odm/bin/su -c "/system/bin/rmmod r1_kexec 2>/dev/null; /system/bin/insmod /data/local/tmp/r1/r1_kexec.ko write_crumb=0x075fb000 write_val=0x5244D301; /system/bin/dmesg | grep -i 'wrote crumb' | tail -2; /system/bin/rmmod r1_kexec 2>/dev/null"
```

Readback (not executed):

```
adb -s 26919800005844922 shell /odm/bin/su -c "/system/bin/rmmod r1_kexec 2>/dev/null; /system/bin/insmod /data/local/tmp/r1/r1_kexec.ko read_crumb=0x075fb000; /system/bin/dmesg | grep -i 'crumb@' | tail -3; /system/bin/rmmod r1_kexec 2>/dev/null"
```

The expected line is `r1_kexec: crumb@0x75fb000 = 1380242177`. The module prints
the value in decimal.

## Fire (not executed)

Fire B (secmon test), after the sentinel is confirmed:

```
timeout 12 adb -s 26919800005844922 shell /odm/bin/su -c "insmod /data/local/tmp/r1/r1_kexec.ko image_path=/data/local/tmp/r1/Image dtb_path=/data/local/tmp/r1/aquaman-r1-secmon-fix.dtb cma_phys=0x2ac00000 initrd_path=/data/local/tmp/r1/initrd-realinit-timeout.cpio.gz fire=1"
```

Fire A (control), if I run the A/B pair; identical, only the DTB changes:

```
timeout 12 adb -s 26919800005844922 shell /odm/bin/su -c "insmod /data/local/tmp/r1/r1_kexec.ko image_path=/data/local/tmp/r1/Image dtb_path=/data/local/tmp/r1/aquaman-r1-initrd-console.dtb cma_phys=0x2ac00000 initrd_path=/data/local/tmp/r1/initrd-realinit-timeout.cpio.gz fire=1"
```

`rc=255` from insmod is the expected abrupt handoff, not a load failure. There
is no return to the old kernel. One fire per hypothesis; do not repeat an
identical payload.

## Reading after the fire (only if the serial returns)

Crumbs (not executed):

```
adb -s 26919800005844922 shell /odm/bin/su -c "/system/bin/rmmod r1_kexec 2>/dev/null; /system/bin/insmod /data/local/tmp/r1/r1_kexec.ko read_crumb=0x075fb000; /system/bin/dmesg | grep -i 'crumb@' | tail -3; /system/bin/rmmod r1_kexec 2>/dev/null"
adb -s 26919800005844922 shell /odm/bin/su -c "/system/bin/rmmod r1_kexec 2>/dev/null; /system/bin/insmod /data/local/tmp/r1/r1_kexec.ko read_crumb=0x07501000; /system/bin/dmesg | grep -i 'crumb@' | tail -3; /system/bin/rmmod r1_kexec 2>/dev/null"
```

`0x075fb000` should still read `1380242177`; `0x07501000` is the boot crumb
(earlier values: `0x5254` = console_init, `0x5260` = head.S marker before
enabling the MMU).

Pstore (not executed):

```
adb -s 26919800005844922 shell /odm/bin/su -c "ls -l /sys/fs/pstore/"
adb -s 26919800005844922 shell /odm/bin/su -c "cat /sys/fs/pstore/console-ramoops-0"
adb -s 26919800005844922 shell /odm/bin/su -c "cat /sys/fs/pstore/dmesg-ramoops-0"
adb -s 26919800005844922 shell /odm/bin/su -c "grep -E 'Linux version|r1probe|Unhandled fault|Attempted to kill init|EXT4-fs|49104|82000010' /sys/fs/pstore/console-ramoops-0"
```

If the names change, use the `ls` listing and change only the exact path. Under
SELinux Enforcing, `/proc/cmdline`, `/sys/firmware/fdt` and `/proc/kmsg` are not
reliable; `dmesg` via `/odm/bin/su -c` worked in the baseline.

## Criteria

Round-11 reference (DTB with old secmon): ext4 mount of `mmcblk0p18`,
`Unhandled fault: synchronous external abort (0x82000010) at
0x0000000000049104`, panic `Attempted to kill init! exitcode=0x00000007`.

- SUPPORT: with the same Image/module/initrd, fire B produces new evidence
  attributable to the DTB, for example readable pstore showing a new banner or
  `r1probe=DEADBEEF` or `sys.boot_completed=1` with zygote, or a boot crumb
  advancing past `0x5260`, or a changed fault signature (32-bit init moves past
  `0x49104` / no more IABT with `0x82000010`). Always compare with fire A. New
  evidence without a valid sentinel does not count.
- REFUTATION: a valid sentinel in both fires and readable pstore in fire B
  reproducing the same round-11 signature (`0x82000010` at `0x49104`,
  `exitcode=0x00000007`) with crumbs matching control A. In that case increasing
  the secmon reservation neither explains nor fixes the failure in this
  configuration.
- INCONCLUSIVE: no serial; empty, compressed or unreadable pstore; a corrupted
  sentinel or one different from `1380242177`; inconsistent crumbs; a panic
  caused by a wrapper mount failure (`exit 122`/`124`) before the real init; any
  result that does not allow comparing A and B. Do not turn missing data into a
  refutation.

## Stop rule

After each fire, check `adb devices -l` every 5 s. If the serial
`26919800005844922` does not return within 180-300 s, stop immediately: do not
repeat the payload, do not try another fire, do not power-cycle, flash, use
fastboot or USB DL. I will record the round as INCONCLUSIVE and leave the device
for recovery. I decide on each command in this plan separately before running it.
