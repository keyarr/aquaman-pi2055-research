# Bench - persistent candidate (2026-11-24)

Continuation of the control bench (which PASSED on the third attempt; see
`bench-control.md`, section "Third control test"). I moved on to the candidate
only after the control passed.

Device: MiTV-AESP0 (aquaman), ADB serial `26919800005844922`.

## Result

**FAILED.** The `kernelsu-persist.ko` module does NOT load on the candidate
boot. There is no `kernelsu` in `/proc/modules`, the Manager reports
"KernelSU Next v2 signature not found in kernel", and there is no root via
`su` or via port 4444 (it is closed, as expected). Stable boot, no Oops and
no reboot loop.

Likely cause, verified by read-only inspection of the local image:
`kernelsu.ko` and `ksud32` are UNLABELED in the candidate image
(`getfattr` returns "No such attribute"), while `ksu_sepolicy.sh` has
`u:object_r:vendor_file:s0`. The candidate removes `seflip.ko`, so the system
stays `Enforcing`. In the control, `seflip.ko` made the system
`Permissive` before insmod, and dmesg recorded:

```
avc: denied { module_load } ... comm="init" path="/odm/kernelsu.ko"
scontext=u:r:vendor_init:s0 tcontext=u:object_r:unlabeled:s0
tclass=system permissive=1
```

Under Enforcing, the same `module_load` is denied and `insmod` fails. Without
the module there are no prctl/sys_execve/faccessat hooks, so the Manager does
not detect the signature and the root service cannot obtain root.

## Hashes checked in this session

```
sha256sum -c HASHES.txt                     -> 10/10 OK
odm/odm20_ksu3.img        880a575753d694ca0d7fab6a84da82a2c1f3913257261ed4d4d2f03e95939da7
odm20_ksu_control.img     0493c34a69b307944972eed45bc3e82c1003067f6083a7ee99b857f9d33c923d
odm20_ksu_persist.img     ce67bf7cfcc18a912f072b95645d6d8baf431580e87ee04de63bf974aedc0721
```

Content extracted from the candidate image (loop mount, read-only):

```
sha256sum kernelsu.ko  bcf5987d3b69a141197e5af1db80872f7d669fed38df0a1fad762492621d84c2
sha256sum ksud32       f21b373468b806d63b17e89022ccb50346aaa3b733da48afe7432f879e9aae01
```

## Commands executed

```
adb reboot fastboot
python3 tools/fb_raw.py devices                 -> fastboot USB: True
python3 tools/fb_raw.py getvar product          -> OKAYaquaman
python3 tools/fb_raw.py download .../odm20_ksu_persist.img  -> OKAY (2.9s)
python3 tools/fb_raw.py cmd 'set_active:;store write odm 10200000 0 1400000' 20000
                                                  -> OKAY (2.0s)
python3 tools/fb_raw.py cmd reboot 10000         -> OKAY (0.0s)
```

## Boot and observed state

Monitoring (5 s): `boot_id=d9593272-...` constant from 11:50:22 to
11:52:54 (~2.7 min), `sys.boot_completed=1` from 11:50:39.
No loop, no Oops, no reboot.

```
adb shell getenforce                -> Enforcing
nc -v 127.0.0.1 4444 (after forward) -> Ncat: Connection refused
adb shell su -c id                   -> /system/bin/sh: su: not found
adb shell cat /proc/modules | grep -i kernelsu -> (empty)
adb shell cat /proc/modules | grep -i seflip   -> (empty)
adb shell dmesg                      -> dmesg: klogctl: Operation not permitted
```

Port 4444 closed and `getenforce=Enforcing` are expected behaviors of the
candidate. The missing module is not.

## Manager

`am start -n com.rifsxd.ksunext/.ui.MainActivity` opened the UI (worked).
Readable screencap (unlike older reports). The screen shows:

> KernelSU Next v2 signature not found in kernel! [ !KSU_NEXT || != size/hash ]
> Ask your kernel developer to integrate KernelSU Next!
> Manager version: v1.1.1 (12851)

There is no Superuser list in the UI, so grant/revoke was not possible.
The Manager logcat shows the root service
`com.rifsxd.ksunext:root:0` starting and ending with `System.exit called,
status: 0`, but without the module loaded this produces no usable root: `su`
does not exist in PATH and port 4444 does not exist.

## Unvalidated items (pending)

- `ext4 sysfs nuke disabled`: not checkable without dmesg/root.
- `allowlist probe` / `allowlist load` from ksud32 and the kernel: not
  checkable; the module did not load and no dmesg is accessible.
- `grant/revoke surviving reboot and full power-off`: not tested; the Manager
  UI has no Superuser list.
- Unauthorized app without `su`: not tested.
- `insmod /harmless/ksu_ext4_noop.ko`: not tested; no root.
- Presence of the control instrumentation line: see `bench-control.md`
  (it did not emit because `on_post_fs_data` never fires on this firmware).

## Final device state

Candidate `odm20_ksu_persist.img` written to ODM. Stable boot,
`boot_id=d9593272...`, `sys.boot_completed=1`, Enforcing, port 4444 closed,
no KernelSU module loaded, Manager without signature detection.
No post-test rollback was done (out of scope for this round).
recovery/boot/vbmeta were not changed. No file other than `bench-control.md`
and this report was edited. No commit was made.

## Second candidate test (SELinux labels fixed) - MODULE LOADED, VALIDATION INCOMPLETE

Fix applied: `label_odm_candidate.sh` restores
`security.selinux=u:object_r:vendor_file:s0` on `kernelsu.ko` and `ksud32` and
`u:object_r:init_exec:s0` on `etc/init/root.rc`. `make_odm_candidate.py`
now calls that script.

### Hashes checked in this session

```
sha256sum -c HASHES.txt                     -> 10/10 OK
odm20_ksu_persist.img     25b80d52ea462a5005b6dc8e2b42b54df83cd23e3030b8ad0e64eb610f71ffdd
ksud-arm32                f21b373468b806d63b17e89022ccb50346aaa3b733da48afe7432f879e9aae01
```

Inspection of the image via read-only loop mount, before flashing:

```
getfattr -n security.selinux kernelsu.ko
  -> u:object_r:vendor_file:s0
getfattr -n security.selinux ksud32
  -> u:object_r:vendor_file:s0
getfattr -n security.selinux etc/init/root.rc
  -> u:object_r:init_exec:s0
sha256sum kernelsu.ko -> bcf5987d3b69a141197e5af1db80872f7d669fed38df0a1fad762492621d84c2
sha256sum ksud32      -> f21b373468b806d63b17e89022ccb50346aaa3b733da48afe7432f879e9aae01
```

### Commands executed

```
adb reboot fastboot
python3 tools/fb_raw.py devices                 -> fastboot USB: True
python3 tools/fb_raw.py getvar product          -> OKAYaquaman
python3 tools/fb_raw.py download .../odm20_ksu_persist.img  -> OKAY (2.9s)
python3 tools/fb_raw.py cmd 'set_active:;store write odm 10200000 0 1400000' 20000
                                                  -> OKAY (2.1s)
python3 tools/fb_raw.py cmd reboot 10000         -> OKAY (0.0s)
```

### Result

Stable boot: `boot_id=05b2ad35-...` constant from 12:06:14 to 12:08:50
(~2.7 min), `sys.boot_completed=1` from 12:06:30. No loop and no Oops.
Unlike the previous test, the module loaded:

```
adb shell cat /proc/modules | grep -i kernelsu
kernelsu 102400 0 - Live 0x0000000000000000 (O)
adb shell getenforce -> Enforcing
nc -v 127.0.0.1 4444 -> Ncat: Connection refused (port closed, expected)
```

Port 4444 closed and `getenforce=Enforcing` are correct for the candidate.
No module-related EXT4 warning was observable because `dmesg` requires root
(`klogctl: Operation not permitted`) and `/sys/fs/pstore/` is
`Permission denied` for the shell user.

The Manager (`com.rifsxd.ksunext/.ui.MainActivity`) opened and the screencap
was readable. The screen still shows "KernelSU Next v2 signature not found in
kernel! [ !KSU_NEXT || != size/hash ]" and manager version v1.1.1
(12851). The same behavior occurred on the control, so this is not
a regression introduced by the label fix. Without detection, the UI does not
show the Superuser list, so grant/revoke cannot be done via adb.

`adb shell su -c id` -> `/system/bin/sh: su: not found`. The Manager root
service appears in logcat (`com.rifsxd.ksunext:root:0`, `System.exit called,
status: 0`), but there is no usable root shell for the shell user. The
Manager's "Export logs" / "Save logs" options produced no accessible file
in `/sdcard` during the attempt.

### Pending in this round

- `ext4 sysfs nuke disabled`, `allowlist probe`, `allowlist load`,
  `ksu_open`, ksud32 logs and absence of module EXT4 warnings: not
  checkable without dmesg/pstore/root.
- Version 12851 via prctl: not checked by any available tool; the UI only
  shows the manager version.
- Manager grant/revoke and survival across reboot/full power-off:
  not tested. The UI does not show a Superuser list because the kernel
  signature is not detected, and `su` is unavailable to the shell user.
- Unauthorized app without `su`: not tested, for the same reason.
- `insmod /harmless/ksu_ext4_noop.ko`: not tested; no root.

### Final state

Candidate `odm20_ksu_persist.img` (25b80d52...) written to ODM. Stable boot,
`boot_id=05b2ad35...`, `sys.boot_completed=1`, `kernelsu` present
in `/proc/modules`, Enforcing, port 4444 closed, no seflip module.
No post-test rollback. No other file edited, no commit.

## Final update (2026-11-24)

The final round of this same task is in `bench-persistence.md` ("Final round -
SUCCESS"). The items previously marked pending were verified on image
`odm20_ksu_persist.img` = `bae7e9e3...`: the Manager crowns and shows
12851, `su -c id` gives uid=0(root) via the `compat_sys_execve` hook, UI
grant/revoke survives reboot, the allowlist is idempotent and rejects
truncation, Enforcing, port 4444 closed and stable boot for over 4 min.
