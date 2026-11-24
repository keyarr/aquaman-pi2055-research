# KernelSU Next LKM, persistent and Enforcing (2026-11-24)

Scope: Xiaomi Mi TV Stick 1080p (MiTV-AESP0, aquaman, S805Y/GXL), Android 9
PI.2055, kernel `4.9.113-g963f962d046a-dirty`, 32-bit userspace on arm64. One
device, one firmware build. This is the current state of the root track. It
supersedes `reports/kernelsu-next-lkm-2026-11-23.md` on persistence, SELinux
mode, Manager crowning, `su` path and network exposure. The BL31 and
custom-kernel conclusions in `reports/CURRENT_STATE.md` are unchanged.

Status: HARDWARE_REPRODUCED for the device measurements below, OFFLINE_ONLY
for the build and static checks. No boot.img, vbmeta, efuse, BL31 or SMC
component was changed. Recovery is untouched.

The detailed lab log, rebuild recipe, bench history and intermediate failures
are in `work/ksu-lkm-fix/PERSISTENCE.md` (local work tree, not committed).

## Result

The final ODM image loads KernelSU Next v1.1.1 (tag `v1.1.1`, commit `0d6bdc6`,
legacy non-GKI branch) as an unsigned loadable module from `/odm` at
`sys.boot_completed`. Root comes from kernel hooks and the Manager grant; no
patched ramdisk, no custom kernel image and no network root listener are
involved.

Measured on the device with the final image, Enforcing:

- `getenforce` = `Enforcing`; `seflip` absent; no global Permissive module.
- Manager v1.1.1: "Em execucao", version `12851`, "SuperUsuario 1", no
  signature error. `dmesg` logs `Crowning manager: com.rifsxd.ksunext(uid=10069)`.
- `su -c id` -> `uid=0(root) ... context=u:r:su:s0`, including from a normal
  adb shell through the static aarch64 front-end at `/odm/bin/su`.
- UI revoke -> `su` rc 127; UI grant -> uid 0 again. The grant survives a
  normal reboot.
- `allowlist load` repeated 3x: `applied 1 validated records` every time,
  `.allowlist` sha unchanged. A truncated file (100 B) is rejected, the
  previous in-memory state stays, and a valid file is reapplied after reboot.
- Port 4444 closed: no `:115c` in `/proc/net/tcp*`, `nc` refused.
- No Oops, panic or EXT4 warning for >4 min; no reboot loop.

## What changed from the 2026-11-23 build

| Item | 2026-11-23 build | 2026-11-24 final image |
| ---- | ---------------- | ---------------------- |
| Root delivery | ODM `rootsh`, TCP 4444 in `u:r:dumpstate:s0` | KernelSU hooks, Manager grant, `u:r:su:s0` |
| SELinux | global Permissive via `seflip.ko` | Enforcing; KernelSU applies its own sepolicy at module load |
| sepolicy | `/odm/ksu_sepolicy.sh` exec with `permissive su;` | applied from `kernelsu_init()` before Manager discovery; no exec line |
| Allowlist | in memory only, `ENOKEY` on save | 32-bit ksud saves through tmp + fsync + rename; survives reboot |
| Manager | one-shot scan, not crowned on this firmware | crowned at module init from committed `packages.list` |
| `su` path | 64-bit `sys_execve` hook | native + `compat_sys_execve` hooks (32-bit userspace) |
| Network | listener on all interfaces, TCP 4444 | no listener |

The KernelSU sepolicy grants `vendor_init` read on `system_data_file`,
`apk_data_file` and `adb_data_file`, plus `init` execute on
`shell_exec`/`vendor_init_exec`, and resets the AVC cache. Without this the
Manager was never crowned: `filp_open("/data/system/packages.list")` from
`vendor_init` was denied with EACCES in Enforcing. The init-script route was a
dead end because `exec` of `/odm/ksu_sepolicy.sh` is itself denied before any
patch can be applied.

## Build and artifacts

The module is built against the exact decrypted stock Image
(`artifacts/kernel_image.bin`), not against `build-aq`. `build-aq/System.map`
diverges on `commit_creds`, `sys_call_table` and `selinux_enforcing`; stock CRCs
were recovered from synthetic `__kcrctab_*` symbols crossed with `.rela.dyn`
addends in the stock ELF. KASLR `N=0` remains inferred, not read live.

| Artifact | sha256 |
| -------- | ------ |
| `work/ksu-lkm-fix/kernelsu-persist.ko` (final module) | `297593726f34dc30062cddd6f5d2394a42975cc12b3b5a14752c1e2b7dc61240` |
| `work/ksu-lkm-fix/ksud-arm32` | `75e6b99d97943838db2a70d1675efc6ffee89607bbebbab069087ed261ad9d46` |
| `work/ksu-lkm-fix/su-helper` (`/odm/bin/su`) | `262f7ec8484f2812aa2aa3089f0f8d03996f709cc224a2dbade8510bd5d1dceb` |
| `work/ksu-lkm-fix/odm20_ksu_persist.img` (final ODM) | `bae7e9e3b8458c064385bc54fa3963b8d81f8dcf8bf1fa90448577a3d0c44e2b` |
| Manager `KernelSU_Next_v1.1.1_12851-release.apk` | `988dae93c17b5477b8b97952cc5bca6809a386bbbba55940ce45aecc90cacb80` |

Full list in `work/ksu-lkm-fix/HASHES.txt`. The final ODM is `odm20_ksu3.img`
with the module replaced, ksud32 and `/odm/bin/su` installed, and `root.rc`
reduced to the `insmod` at `sys.boot_completed`. `seflip.ko` and `root.sh` are
gone from the image.

## Limitations

1. The control build is source-close, not byte-identical: the exact original
   source tree was not recovered. Static symbol/CRC compatibility passed;
   runtime equivalence and ENOKEY context comparison were not re-run after the
   final fix.
2. LSM hooks (`vfs_rename`, `task_fix_setuid`, `inode_permission`,
   `key_permission`) are absent. Hide and safe-mode behaviour is weaker than
   an in-kernel KernelSU build; manager discovery is a one-shot scan at init.
3. Symbol fidelity is offline-derived. A firmware change invalidates the
   addresses and CRCs; revalidate before loading the module.
4. `rmmod` is not a validated rollback. The final image has no 4444 listener,
   so the exposure from the 2026-11-23 build is gone, but granted apps still
   have root.

## Rollback

Reflash stock ODM to remove KernelSU and root:

```sh
adb reboot fastboot
python3 tools/fb_raw.py download odm/odm20_stock.img
python3 tools/fb_raw.py cmd 'set_active:;store write odm 10200000 0 1400000' 20000
python3 tools/fb_raw.py cmd reboot 10000
```

`odm/odm20_root9.img` restores the older 2026-11-23 root-plus-seflip build
(TCP 4444 and global Permissive) if that is wanted. Do not rely on `rmmod`.
