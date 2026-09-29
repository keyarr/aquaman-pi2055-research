# GhostLock ashmem + configfs on aquaman (Phase 6 + Phase 7)

## Compiled in (aquaman-config) — CONFIRMED

- CONFIG_ASHMEM=y (staging android)
- CONFIG_CONFIGFS_FS=y
- CONFIG_UNIX=y, CONFIG_UNIX_DIAG=y
- CONFIG_NET=y, CONFIG_IPV6=y (required for hazel's stack stamper)
- PIPE: implicit (always present; used as Plan B)

## Runtime (unprivileged shell) — CONFIRMED 2026-09-29 via adb

- /dev/ashmem: crw-rw-rw- root root 10,61. Shell opens successfully. CONFIRMED.
- /proc/filesystems lists configfs (nodev configfs). CONFIRMED.
- configfs mounted on /sys/kernel/config and /config (rw). CONFIRMED.
- `ls /sys/kernel/config`: Permission denied (directory listing denied; creating
  own subdir not yet tested).
- /proc/cmdline and /sys/fs/pstore: Permission denied for shell.
  Without readable pstore, post-mortem panic diagnosis is limited to adb
  observation (process died = reboot/hang) and bootreason if exposed.
  Risk recorded; without UART, physical power cycle remains fallback.

## Fragile point: dentry on configfs path via ashmem fd

Hazel reuses the `/dev/ashmem` fd itself with f_op swapped to the
fake fops (.read/.write = configfs_read/write_file). Does not require
mounting configfs. However, configfs_read_file calls to_attr(dentry) and
to_item(parent) on file->f_path.dentry — with a `/dev/ashmem` dentry
this in theory fails. Read fs/configfs/file.c:69-130 before assuming: hazel
passed hardware testing, so the path is tolerant in practice, but it is the
most fragile aspect of the port and requires careful verification against
aquaman's real dentry layout.

## ashmem implementation in tree — CONFIRMED (drivers/staging/android)

- struct ashmem_area { name[ASHMEM_FULL_NAME_LEN]; unpinned_list;
  file; size; prot_mask } (ashmem.c:54-60). ASHMEM_FULL_NAME_LEN: check
  ashmem.h — hazel's blob assumes "/dev/ashmem/" prefix (11 chars,
  ASHMEM_NAME_PREFIX_LEN) as the first word of area. If 4.9 Amlogic's LEN
  matches upstream, the large count trick holds; if vendor modified name layout,
  it breaks.
- ashmem_fops + ashmem_misc (.fops = &ashmem_fops, minor MISC_DYNAMIC)
  + misc_register (lines 823-862). The `/dev/ashmem` surface exists if the
  driver probed successfully — on Android TV sticks, ashmem is almost always
  present (used by SurfaceFlinger/heap). INFERRED present, confirmed via ls.
- ASHMEM_SET_NAME via ioctl: copies name to area->name. Hazel
  writes blob in slices around zeroes (set_name_zero_at).
  Ioctl-level mechanism, version-independent; identical.

## ARM32 -> ARM64 difference in blob — DIRECTLY INCOMPATIBLE

See `ghostlock-structs-4.9-arm64.md`: mutex at +0x18 becomes +0x20, 8-byte
pointers, page/ops shifted. Hazel's 96B payload must be regenerated for
LP64. Additionally, the fault-write trick (target-1 + EFAULT cleanup) depends
on vendor copy_from_user implementation; hazel's comment notes "vendor ARM
copy_from_user walks from high end" — on ARM64 Amlogic behavior may differ;
test primitive on harmless target first (e.g., reading back the fake fops
itself, as hazel does in the "preloaded read slot" step).

## Ready alternative (Plan B)

Aresin's pipe route (pipe_buffer + physmap) does not require
ashmem/configfs. If `/dev/ashmem` is not accessible to shell or configfs dentry
is intolerant, migrate to pipe. Both spray surfaces (AF_UNIX, pipe) exist on
aquaman by config.

## Runtime checklist — EXECUTED 2026-09-29 (shell uid 2000)

1. ls -l /dev/ashmem -> crw-rw-rw- root root 10,61. OK.
2. /proc/filesystems -> nodev configfs. OK.
3. mount -> configfs on /sys/kernel/config and /config (rw). OK.
   ls /sys/kernel/config -> Permission denied (noted above).
4. id shell u:r:shell:s0; getenforce Enforcing; /proc/version 4.9.113
   Linaro gcc 6.3.1 jenkins@c5-mitv-cm-build06.bj. OK.
   getprop: fingerprint Xiaomi/aquaman/aquaman:9/PI/2055:user/release-keys,
   incremental 2055, cpu abi armeabi-v7a (32-bit userspace, 64-bit kernel).
5. /dev/socket not checked (AF_UNIX proven by usage: sockets function;
   spend a cycle here when spray calibration is tested).
