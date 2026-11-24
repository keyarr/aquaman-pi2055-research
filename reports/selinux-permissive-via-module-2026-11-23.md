# SELinux permissive via kernel module (2026-11-23)

Device: Xiaomi Mi TV Stick 1080p, aquaman, Android 9 PI.2055, kernel 4.9.113.
Status: HARDWARE_REPRODUCED. Current device state: Permissive. No boot,
vbmeta, system, vendor, efuse, BL31 or SMC change was used.

## Result

```
$ adb shell getenforce
Permissive
$ adb shell cat /sys/fs/selinux/enforce
0
$ adb forward tcp:4444 tcp:4444; nc 127.0.0.1 4444
uid=0(root) gid=0(root) groups=0(root) context=u:r:dumpstate:s0
getprop debug.root_service -> RUNNING
```

`lsmod` shows `seflip 16384 0 - Live ... (O)`. The root service still works.

## Why the obvious paths fail

This is the boundary recorded in `root-read-surface-2026-11-23.md` and in the
user's 2026-11-23 analysis:

- `setenforce 0` and writes to `/sys/fs/selinux/enforce` need
  `security:setenforce` in the caller's domain. No domain in the loaded policy
  allows it. Root in `u:r:dumpstate:s0` also cannot read selinuxfs.
- `androidboot.selinux=permissive` is ignored: `ALLOW_PERMISSIVE_SELINUX` is 0
 in this user build, and the cmdline field never reached Linux in the boot
  experiments anyway.
- No domain has `security:load_policy`, so a new policy cannot be loaded from
  `/sys/fs/selinux/load`.
- There are 0 permissive types to transition into, and no kernel R/W surface
  from `dumpstate`.

## What works

The kernel accepts unsigned modules and resolves symbols through kallsyms:

```
CONFIG_MODULES=y
CONFIG_MODVERSIONS=y
CONFIG_KALLSYMS_ALL=y
# CONFIG_MODULE_SIG is not set
CONFIG_SECURITY_SELINUX_DEVELOP=y
```

`selinux_enforcing` is a plain global `int` in
`security/selinux/hooks.c:102`. `security/selinux/avc.c:989` reads it when
deciding whether a denied permission is fatal. Writing 0 to that variable from
kernel mode has the same effect as `setenforce 0` and never reaches an SELinux
permission check.

The module cannot be loaded from the `dumpstate` root shell. That domain has
neither `sys_module` nor `system:module_load` in the policy. The ODM rc file
is imported by `u:r:vendor_init:s0`, which does have both, but only on
`vendor_file`:

```
allow vendor_init self:capability { ... sys_module ... };
allow vendor_init vendor_file:system { module_load };
allow vendor_init vendor_file_type:file { ioctl read getattr lock map execute open };
```

So the `insmod` runs from the ODM rc service, with the module labelled
`u:object_r:vendor_file:s0`.

First attempt used `system_file:s0` and failed. Exact denial:

```
avc: denied { module_load } for comm="init" path="/odm/seflip.ko" ino=23
scontext=u:r:vendor_init:s0 tcontext=u:object_r:system_file:s0 tclass=system permissive=0
```

Changing only the label to `vendor_file:s0` fixed it. No boot-chain component
was involved in either attempt.

## Module

Source and binary are in `/tmp/opencode/seflip/` (ephemeral):

```c
#include <linux/module.h>
#include <linux/kallsyms.h>

static int __init seflip_init(void)
{
    int *enforcing = (int *)kallsyms_lookup_name("selinux_enforcing");

    if (enforcing)
        *enforcing = 0;
    return enforcing ? 0 : -ENOENT;
}

static void __exit seflip_exit(void) {}

module_init(seflip_init);
module_exit(seflip_exit);
MODULE_LICENSE("GPL");
```

Build:

```sh
make -C .src/linux-amlogic ARCH=arm64 \
  CROSS_COMPILE=$PWD/.src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu- \
  HOSTCFLAGS=-fcommon O=$PWD/build-aq M=/tmp/opencode/seflip modules
```

Vermagic is `4.9.y SMP preempt mod_unload modversions aarch64`, identical to
the stock vendor modules. `__versions` contains only `module_layout` and
`kallsyms_lookup_name`; the `module_layout` CRC matches `mali.ko` stock. No
`disagrees about version` or `Unknown symbol` appeared on the device.

## ODM image

Built from `odm/odm20_root7.img` into
`odm/odm20_root9.img`. Only two changes:

- `/odm/seflip.ko`: mode 0644 root:root, xattr
  `security.selinux = u:object_r:vendor_file:s0` with trailing NUL.
- `/odm/etc/init/root.rc`, still labelled `init_exec:s0`:

```
service rootsh /odm/sh /odm/root.sh
    class main
    user root
    group root

on property:sys.boot_completed=1
    insmod /odm/seflip.ko
    setprop debug.root_service RUNNING
    start rootsh
```

Flash, same path as the ODM root work:

```sh
adb reboot fastboot
python3 tools/fb_raw.py download odm/odm20_root9.img
python3 tools/fb_raw.py cmd 'set_active:;store write odm 10200000 0 1400000' 20000
python3 tools/fb_raw.py cmd reboot 10000
```

## Rollback and limits

Reboot alone does not restore enforcing; the module is loaded from ODM on
every boot. Reflash stock ODM:

```sh
adb reboot fastboot
python3 tools/fb_raw.py download odm/odm20_stock.img
python3 tools/fb_raw.py cmd 'set_active:;store write odm 10200000 0 1400000' 20000
python3 tools/fb_raw.py cmd reboot 10000
```

`setenforce 1` remains denied to shell and `dumpstate` even while permissive.
Returning to enforcing at runtime needs another module doing the inverse, or a
reboot with a modified ODM.

Permissive is global. Combined with the root listener bound to all interfaces
on TCP 4444, any host with network access can get root. Use an isolated
network or remove the listener.
