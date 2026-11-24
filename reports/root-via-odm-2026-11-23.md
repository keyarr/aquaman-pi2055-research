# Root via ODM init service (2026-11-23)

Device: Xiaomi Mi TV Stick 1080p, aquaman, Android 9 PI.2055, kernel 4.9.113.
Status: HARDWARE_REPRODUCED. Root survives reboot. No boot-chain or SMC
bypass was used.

> The ODM service was later extended to load a kernel module that switches
> SELinux to Permissive; see
> `reports/selinux-permissive-via-module-2026-11-23.md`. The root construction
> below is unchanged.

## Result

```
adb forward tcp:4444 tcp:4444
nc 127.0.0.1 4444
> id
uid=0(root) gid=0(root) groups=0(root) context=u:r:dumpstate:s0
```

`debug.root_service=RUNNING`, `init.svc.rootsh=running`,
`sys.boot_completed=1`. The service is started by an ODM rc script on every
boot.

Persistent image: `odm/odm20_root7.img`.
Stock ODM backup: `odm/odm20_stock.img`.

The listener runs in a loop, so repeated connections work without a reboot.
There is a ~1 s window after each disconnect while `nc` rebinds the port; a
connection attempted inside that window is refused.

## Chain

1. Download the 20 MB ODM image to `0x10200000`.
2. `set_active:;store write odm 10200000 0 1400000` writes it to the ODM
   partition. The first Hush command dies on argc=1 without touching storage;
   the second runs. The host sees FAIL even on success.
3. Android 9 init parses `/odm/etc/init/root.rc` after `mount_all`. ODM is
   outside `vbmeta.parts` and has no `avb`/`verify` flag in the fstab.
4. `/odm/sh` is labelled `u:object_r:dumpstate_exec:s0`. With no `seclabel`
 in the service, init performs `type_transition init dumpstate_exec:process
   dumpstate`. The service process lands in `u:r:dumpstate:s0` with uid 0.
5. `dumpstate` has `dac_override`, `execute_no_trans` on `shell_exec`, and TCP
   bind permissions. `/odm/toybox` (`shell_exec:s0`) runs
   `nc -l -p 4444 /system/bin/sh` inside that domain. The final shell stays
 in `u:r:dumpstate:s0` as uid 0.

## Image contents

Built from `odm/odm20_stock.img` (stock ODM expanded to `0x1400000` bytes,
`e2fsck` clean). All new files are mode `0100755`.

`/etc/init/root.rc`, label `init_exec:s0`:

```
service rootsh /odm/sh /odm/root.sh
    class main
    user root
    group root

on property:sys.boot_completed=1
    setprop debug.root_service RUNNING
    start rootsh
```

`/odm/sh`: copy of `/system/bin/sh` (236272 B), label `dumpstate_exec:s0`.

`/odm/toybox`: copy of `/system/bin/toybox` (348464 B, pulled via
`adb shell cat` because `adb pull` is denied), label `shell_exec:s0`.

`/odm/root.sh`, label `shell_exec:s0`:

```
#!/system/bin/sh
while true; do
  /odm/toybox nc -l -p 4444 /system/bin/sh
  sleep 1
done
```

SELinux xattrs include the trailing NUL (`ea_set -f selinux_val.bin`).
No new directory is created: `adbd`/`dumpstate` cannot search a `debugfs
mkdir` directory because it is `unlabeled:s0`. Files live in the ODM root.
`/etc/init` is unlabeled but init can traverse it.

## Device commands

```
adb reboot fastboot
python3 tools/fb_raw.py download odm/odm20_root7.img
python3 tools/fb_raw.py cmd 'set_active:;store write odm 10200000 0 1400000' 20000
python3 tools/fb_raw.py cmd reboot 10000
```

`tools/fb_raw.py` avoids a redundant `set_configuration()` that wedges this
2015.01 gadget. `max-download-size=0x08000000`, so 20 MB fits.

## Why the earlier attempts failed

| Attempt | Exec label / domain | Failure | Cause |
| ------- | ------------------- | ------- | ----- |
| 1-2 | `init_exec` / forced `u:r:init:s0` | `execute_no_trans` on `/system/bin/sh` | init has no `execute_no_trans` on any file; it can only exec through a domain transition |
| 3 | `adbd_exec` / `u:r:adbd:s0` | `search` denied on `/odm/bin` (`unlabeled:s0`) | `debugfs mkdir` leaves the directory unlabelled; init does not care, adbd does |
| 4 | `adbd_exec` / `u:r:adbd:s0` | `dac_override` denied on file create | adbd lacks the capability, so root cannot write `/data/local/tmp` |
| 5 | `adbd_exec` / `u:r:adbd:s0` | same, from mksh startup | no file writes in the script did not help |
| 6 | `dumpstate_exec` / `u:r:dumpstate:s0` | success | policy supplies all three permissions |

Policy extracted from `/etc/selinux/precompiled_sepolicy` in the stock ODM:

```
type_transition init dumpstate_exec : process dumpstate;
allow init dumpstate_exec : file { read getattr map execute open };
allow dumpstate dumpstate_exec : file { read getattr map execute entrypoint open };
allow dumpstate shell_exec : file { ... execute_no_trans ... };
allow dumpstate port_type : tcp_socket { name_bind };
```

## Risk and restore

The listener binds all interfaces on port 4444. On a shared network any host
can connect and get root. Restrict or remove it before leaving the device in
a non-isolated network.

To restore stock ODM:

```
adb reboot fastboot
python3 tools/fb_raw.py download odm/odm20_stock.img
python3 tools/fb_raw.py cmd 'set_active:;store write odm 10200000 0 1400000' 20000
python3 tools/fb_raw.py cmd reboot 10000
```

An OTA that replaces ODM removes the service. Only ODM was written. No flash,
erase, `saveenv`, efuse, boot, system, vendor or vbmeta write was performed.
The experiments did not change repository files. Later read-only probing with
the resulting root shell is documented in
`reports/root-read-surface-2026-11-23.md`, which is also where the indexes
were updated.
