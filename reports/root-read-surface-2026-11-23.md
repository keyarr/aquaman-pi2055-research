# Root read surface (2026-11-23)

Scope: one live boot after the ODM root from
`reports/root-via-odm-2026-11-23.md`. Read-only commands through
`adb forward tcp:4444 tcp:4444` + `nc 127.0.0.1 4444`. No write, no reboot,
no boot-chain action.

```
BOOT_ID: 5639814c-0597-46a1-9650-4f191906f0bb
uid=0(root) gid=0(root) groups=0(root) context=u:r:dumpstate:s0
CapPrm/CapEff: 0000003fffffffff
date: Mon Nov 23 22:14:13 GMT 2026
```

Root here is uid 0 inside `u:r:dumpstate:s0`. SELinux still enforces in this
snapshot: uid 0 does not imply a general kernel read surface. This was an
enforcing-only boot through the earlier ODM listener. The device later became
Permissive via `seflip` and then Enforcing with KernelSU; current state:
`reports/kernelsu-persist-2026-11-24.md`.

## Newly readable versus shell

| Path | `u:r:shell:s0` | `u:r:dumpstate:s0` root |
| ---- | -------------- | ----------------------- |
| `/proc/cmdline` | Permission denied | READ_OK |
| kernel log via `dmesg` | `klogctl: Operation not permitted` | READ_OK (syscall path; `/dev/kmsg` itself is still SELinux-denied) |
| `/proc/buddyinfo` | Permission denied | READ_OK |
| `/proc/meminfo`, `/proc/sys/kernel/perf_event_paranoid` | READ_OK | READ_OK |
| `/sys/fs/pstore/console-ramoops-0` | Permission denied | READ_OK |
| `/proc/config.gz` | READ_OK | Permission denied |
| `/proc/device-tree/chosen/bootargs`, `/sys/firmware/fdt` | Permission denied | Permission denied |
| `/proc/kallsyms`, `/sys/kernel/slab/*` attrs, `/sys/kernel/debug` | Permission denied | Permission denied |
| `/sys/fs/selinux/policy`, `/vendor/lib/modules/mali.ko` | Permission denied | Permission denied |
| `/proc/pagetrace`, `/proc/sys/kernel/modprobe`, `core_pattern` | Permission denied | Permission denied |
| `/dev/mem`, `/dev/kmem`, `/proc/kcore` | absent | absent |

So the dumpstate domain is not a superset of shell. The gain is the kernel
log, `/proc/cmdline`, buddyinfo and pstore. The loss is `/proc/config.gz`.

## Facts obtained

1. `/proc/cmdline` is byte-identical to `Kernel command line:` in the live
   `dmesg` ring buffer: both are 1643 bytes and sha256
   `eabd9bc7f80c8db47ef9dd46fd71adeb3f89ee010f971db07a396dee0bc56523`. It
   contains `androidboot.boardid=3`, `androidboot.selinux=enforcing`,
   `androidboot.reboot_mode=watchdog_reboot`, `androidboot.wificountrycode=US`,
   `androidboot.verifiedbootstate=orange`, `androidboot.dtbo_idx=0`. The
   matching props read back the same values, including `watchdog_reboot`.
2. `dmesg` boot banner is
   `Linux version 4.9.113-g963f962d046a-dirty (jenkins@c5-mitv-cm-build06.bj) ...`
   while `/proc/version`, `/proc/sys/kernel/version` and `uname -a` show
   `4.9.113` with no git suffix. The running kernel's own log therefore
   carries the same `-g963f962d046a-dirty` suffix as the decrypted Image
   (`resume-2026-11-19-experiments.md` section 3). The discrepancy is in the
   userspace-visible version string, not in the Image identity.
3. `dmesg` gives the live virtual layout: `_text` `0xffffff8009080000`,
   `_etext` `0xffffff8009dc0000`, `.rodata` ends `0xffffff800a310000`,
   `.data` `0xffffff800a810000`, `.bss` ends `0xffffff800ab43264`,
   `modules` `0xffffff8000000000-0xffffff8008000000`. This matches the VA
   convention used in `kernel-ram-patch-v2-2026-11-19.md` and gives a
   runtime VA anchor without `/proc/kallsyms` or `/proc/pagetrace`.
4. pstore has one 67-byte record:
   `[  101.932502@0] reboot: Restarting system with command 'fastboot'`.

## Consequences for open questions

- The E2 oracle in `reports/_archive/ROOT_FINAL_ANALYSIS.md` now exists: `/proc/cmdline` and
  `Kernel command line:` are readable in one boot. The remaining experiment
  is to boot with a host-written htab marker and compare that string to
  `ro.boot.*`. No such boot was run here.
- `reports/resume-2026-11-19-experiments.md` section 3 no longer describes an
  unexplained Image/device banner mismatch; see fact 2.
- `reports/dev-read-surface-census-2026-10-01.md` remains valid for
  `u:r:shell:s0`; its `NO_READ_SURFACE_FOUND` is not a statement about the
  root domain.
- GhostLock disclosure tables that list dmesg, buddyinfo and pstore as
  blocked are shell-scoped. `/proc/kallsyms`, slab attrs and debugfs remain
  blocked under root, so the no-kernel-pointer result is unchanged.
