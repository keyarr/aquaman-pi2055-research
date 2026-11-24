# KernelSU Next as an LKM on aquaman PI.2055 (2026-11-23)

Scope: Xiaomi Mi TV Stick 1080p (MiTV-AESP0, aquaman, S805Y/GXL), Android 9
PI.2055, kernel `4.9.113-g963f962d046a-dirty`, U-Boot 2015.01. One device, one
firmware build. BOOT_ID was not captured in these sessions.

Status: HARDWARE_REPRODUCED for load, hook installation, manager detection,
sepolicy injection and `su`. OFFLINE_ONLY for the static checks and for the
`rmmod` fix. No boot.img, vbmeta, efuse, BL31 or SMC component was changed.

This report supersedes `reports/kernelsu-next.md` on one point only: the
question "can KernelSU Next reach this kernel?" is now answered without a
kernel source rebuild. The BL31 statement in that older report still holds for
every boot-image route.

## Result

KernelSU Next `v1.1.1` (`0d6bdc6`, legacy branch, non-GKI) runs as an unsigned
loadable module loaded from `/odm` at `sys.boot_completed`. Root is delivered by
kernel hooks; no patched ramdisk and no custom kernel image are involved.

Observed on device:

```
lsmod | grep -E 'kernelsu|seflip'
kernelsu               98304  0
seflip                 16384  0

prctl(0xDEADBEEF, CMD_GET_VERSION=2, ...)   -> version=12851, flags=0x1
prctl(0xDEADBEEF, CMD_GET_MANAGER_UID=16,...) -> 10069
su -c id  (uid 2000, after grant) -> uid=0(root) context=u:r:su:s0
```

`dmesg` records manager crowning, the seven hook installations, the root
profile for `com.android.shell` (uid 2000) and `sys_execve su found`. The
manager root service `:root:0` ends with `System.exit status: 0`.

## Boot chain actually used

1. ODM is written from fastboot with `fb_raw.py`, as in the ODM root work.
   ODM is outside `vbmeta.parts` and has no `avb`/`verify` flag in the fstab.
2. Android 9 init imports `/odm/etc/init/root.rc`.
3. On `sys.boot_completed=1`: `insmod /odm/seflip.ko`,
   `insmod /odm/kernelsu.ko`, `exec u:r:vendor_init:s0 root root --
   /odm/ksu_sepolicy.sh`, then `start rootsh`.
4. `ksu_sepolicy.sh` runs
   `/data/adb/ksud sepolicy patch "permissive su;"`. Without it the manager
   root service dies with an NPE: `u:r:su:s0` gets `find` denied on
   `package_service` and `display_service` with `permissive=0`, even while the
   global `selinux_enforcing` is 0.
5. `rootsh` keeps the TCP 4444 root listener. Nothing about this chain changes
   BL31 or the signature gate.

## Build and artifacts

The module was built against the exact decrypted stock Image
(`artifacts/kernel_image.bin`, sha `3c3522d8...dca8`; ELF produced with
`vmlinux-to-elf`), not against `build-aq`. `build-aq/System.map` is from a
rebuild with a different `.config` and diverges on `commit_creds`,
`sys_call_table` and `selinux_enforcing`; it was discarded.

`Module.symvers` from `build-aq` diverged from stock on 3990 symbols, five of
them imported by the module. The stock CRCs were recovered by crossing the
synthetic `__kcrctab_<name>` symbols in the stock ELF with `.rela.dyn` addends.
The original is kept as `Module.symvers.build-aq`.

| Artifact | sha256 |
| --- | --- |
| `kernelsu.ko` (3,758,560 B) | `cf217969df3272e5d0df517dd0dba412cdbcb7a91db3f085d3d4dc830f5191d9` |
| `odm20_ksu3.img` | `880a575753d694ca0d7fab6a84da82a2c1f3913257261ed4d4d2f03e95939da7` |
| manager `KernelSU_Next_v1.1.1_12851-release.apk` | `988dae93c17b5477b8b97952cc5bca6809a386bbbba55940ce45aecc90cacb80` |
| `ksud_magic-aarch64-linux-android` (3,392,200 B) | installed by the manager at `/data/adb/ksud` |

Manager negotiates `>= 12797`; `11998` from a plain `v1.1.1` build was rejected.
`KSU_VERSION` is pinned to `12851` and `flags & 0x1` marks the LKM build.

HEAD of the `legacy` branch was not used: its module path requires kernel
>= 4.17. Only the `v1.1.1` tag treats `< 4.14` explicitly and keeps the five
manual hook sites.

## Hook layer

`CONFIG_KPROBES` is off in this firmware, so the automatic kprobe integration
is unavailable. Hooks use `aarch64_insn_patch_text` resolved through
`kallsyms_lookup_name`; it performs its own `stop_machine` and writes through
the arm64 fixmap, so kernel RO text is patched without `set_memory_rw` (which
on 4.9 arm64 only accepts vmalloc ranges). The syscall table is not patched.
No virtual address is hardcoded; every symbol is resolved at module init.

Each target gets a 24-byte trampoline `ldr x16,#8 ; br x16 ; .quad stub`. The
stub saves the original 24 bytes, runs the handler through `blr x16` with a
local `b restore`, replays the original bytes and branches to `original+24`.
Stubs live on one vmalloc page with `set_memory_x`. `ksu_hook_exit` restores all
seven targets through the same patch helper before freeing the page. The
`blr` (not `br`) is essential: with `br`, the handler's `ret` bypasses the
restore and leaves SP unbalanced. That bug was found by static validation and
fixed before any device load.

| id | target | VA (stock) | role |
| -- | ------ | ---------- | ---- |
| 0 | `do_execve` | `ffffff8009221790` | retained; dead on the syscall path |
| 1 | `sys_faccessat` | `ffffff8009215ba8` | sucompat `su -> sh` visibility |
| 2 | `sys_read` | `ffffff80092197d0` | su rc injection path |
| 3 | `sys_newfstatat` | `ffffff800921eb78` | sucompat stat redirect |
| 4 | `sys_reboot` | `ffffff80090cde98` | mechanism proof only |
| 5 | `sys_prctl` | `ffffff80090be398` | manager channel, version, profiles |
| 6 | `sys_execve` | `ffffff8009221a10` | real `su` redirect and `escape_to_root` |

Targets 0-5 were installed first. `su` still failed with ENOENT because
`SyS_execve` calls `do_execveat_common.isra.15` (`ffffff8009221108`) directly,
never `do_execve`. Target 6 was added, wired to
`ksu_handle_execve_sucompat` with write-back of `x0`. `dmesg` then showed
`sys_execve su found` and `su -c id` returned uid 0.

## Limitations

1. **Allowlist does not persist.** The grant is held in memory only.
   `save_allow_list create file failed: -126` (ENOKEY) prevents writing
   `/data/adb/ksu/.allowlist`. Cause: `init_session_keyring` is never captured
   because the LSM `key_permission` hook is absent. Every reboot requires
   granting root to the shell/app again in the manager UI.

2. **No LSM hooks.** `security_hook_heads` is untouched: `task_prctl`,
   `inode_rename`, `task_fix_setuid`, `inode_permission` and `key_permission`
   are missing. Consequences include the allowlist failure above, weaker app
   profile enforcement and incomplete hide/safe-mode behaviour.

3. **Manager detection is one-shot.** `ksu_throne_tracker_init` scans
   `/data/system/packages.list` once at module init. The `vfs_rename` hook that
   normally notices later APK installs is absent. An APK installed after module
   load is not crowned until the module is reloaded.

4. **Partial hook coverage.** `input_event` (volume keys) and direct `vfs_read`
   are not hooked; `sys_read` covers the su rc injection path. `sys_reboot` is a
   mechanism proof only because v1.1.1 has no reboot handler.
   `ksu_handle_execveat_ksud` is not wired to target 6: it expects
   `struct filename **` while `sys_execve` supplies `const char __user *`, so
   wiring it would be a type confusion.

5. **`ksud` is not embedded.** `ksud_size = 0` in this tag and the symbol is
   unused. The manager installs `/data/adb/ksud` from its own assets. That step
   requires the manager root service to work, which requires the persistent
   sepolicy patch from the ODM rc.

6. **No safe `rmmod` guarantee.** An earlier build panicked in
   `sysfs_remove_group -> kernfs_find_ns` during `free_module` because init
   called `kobject_del(&THIS_MODULE->mkobj.kobj)`. That call was removed and the
   fix passed static validation, but `rmmod` was not re-tested on silicon. Use
   reboot or reflash ODM to roll back.

7. **Boot chain unchanged.** BL31 still rejects unsigned images; `fastboot
   boot`/`flash` of a Magisk or KernelPatch `boot.img` remains blocked. The
   orange unlock only opens the flashing lock, not the signature check. This
   route does not deliver a custom kernel or ROM.

8. **Symbol fidelity is offline-derived.** KASLR `N=0` is inferred, not read
   from the device in these rounds. The 24-byte PC-relative check was done on
   `stock_vmlinux.elf`, and CRCs came from that ELF, not from a live cross-check.
   A firmware change invalidates both; revalidate before loading the module.

9. **Ephemeral tooling.** The build tree, probes, APK, ksud zip and stock ELF
   live under `/tmp/opencode/ksu-lkm/` and `/data/local/tmp/`. They are not part
   of the repository and do not survive a host reboot or cleanup.

10. **Exposure.** The root listener binds all interfaces on TCP 4444 and
    SELinux is globally permissive. Any host with network access gets root.
    Use an isolated network or remove the listener.

## Rollback

Reflash `odm20_root9.img`, which contains root plus seflip but no KernelSU:

```sh
adb reboot fastboot
python3 tools/fb_raw.py download /tmp/opencode/odm_probe/odm20_root9.img
python3 tools/fb_raw.py cmd 'set_active:;store write odm 10200000 0 1400000' 20000
python3 tools/fb_raw.py cmd reboot 10000
```

Do not rely on `rmmod`. Do not reflash stock ODM if the existing root shell is
to be kept.

## Next work

- Capture `init_session_keyring` (or replace `ksu_filp_open_compat` with a
  direct `filp_open` in the local copy) so the allowlist survives reboot.
- Add the missing LSM-equivalent hooks for rename, setuid, prctl and
  inode_permission if app profiles and hide rules are needed.
- Re-test `rmmod` only if module unloading is required; otherwise keep reboot
  as rollback.
- Revalidate the manager UI state visually; `screencap` returned a black frame
  on this HDMI output.
