# KernelSU Next persistence on aquaman PI.2055 (local work, 2026-11-24)

Scope: MiTV-AESP0 (aquaman), Android 9, 4.9.113-g963f962d046a-dirty, ARM64
kernel with 32-bit userspace. Everything below was built and checked on the
host. Nothing was flashed, rebooted or changed on the device. Recovery image
is untouched.

## Source and configuration

Closest available source: `upstream/` at tag `v1.1.1` (commit `0d6bdc6`), the
non-GKI kernel tree with the `< 4.14` keyring workaround. The exact tree that
produced `kernelsu_stock_img.ko` was not recovered. The local tree
`ksu-skeleton/` is that tag plus 4.9 compatibility patches already present in
`ksu-skeleton.patch` (manual text hooks via `aarch64_insn_patch_text`, runtime
symbol lookups). The stock module disassembly in `ref/` was used to confirm
the keyring and ext4 paths.

Documented difference: the control module exports 10 functions that are not
separate symbols in the stock module (seven trampoline stubs, three kprobe
helpers). There are no stock-only functions. Static symbol/CRC compatibility
is a separate check from runtime equivalence; only the former was done here.

Two pre-existing local reference files are kept: `ref/kernelsu_stock_img.ko`
(byte-different from the image, same function/string set, left untouched) and
`ref/kernelsu_stock_from_odm.ko` extracted from `odm20_ksu3.img`, sha
`cf217969...`, which is the authoritative baseline.

## Control build

`build-variants.sh` builds `kernelsu-control.ko` with no new functional flags:
upstream keyring rule restored (install only the captured
`init_session_keyring`; no `init_task` fallback, because `init_task` is PID 0
swapper and Android init is PID 1), stock ext4 sysfs nuke intact, kernel
workqueue still does the file I/O. The only additions are `pr_info` open/event
instrumentation with `jiffies`, pid, comm, worker flag, keyring presence and
open result. Trigger remains `sys.boot_completed=1` in `/odm/etc/init/root.rc`.

## Candidate build

`kernelsu-persist.ko` is the same source with
`KSU_ALLOWLIST_IO_VIA_KSUD=1 KSU_NO_EXT4_SYSFS_NUKE=1`.

- `CMD_ALLOWLIST_IO` (17) with `struct allowlist_ioctl { op, reply }` at arg5
  makes the protocol identical for 32-bit and 64-bit callers. Ops: get size,
  read blob, write blob, pending flag, probe open. Only uid 0 is accepted.
- File format is unchanged: magic `0x7f4b5355`, version 3, then fixed-size
  `struct app_profile` records (776 bytes on arm64, locked by BUILD_BUG_ON).
  Existing valid files remain readable.
- Write validates magic, version, exact record framing, profile version,
  groups count, SELinux domain, key termination and uid range for **every**
  record before swapping the list. The swap is atomic under the allowlist
  mutex and rebuilds bitmap/array/default profiles from the validated list.
  On rejection the previous list, including the empty/deny-all state, stays.
- Grant/revoke still goes through the manager's `CMD_SET_APP_PROFILE`; the
  kernel sets a dirty flag instead of opening the file. The 32-bit ksud saves
  through `.allowlist.tmp` + `fsync` + `rename`, so a failed write leaves the
  last valid copy. Save can be retried indefinitely.
- `allowlist load` can be repeated after a transient error. It does not call
  `on_post_data_fs()`, so scripts and mounts run once only.
- `nuke_ext4_sysfs()` returns immediately. This is an independent change from
  the keyring/protocol change.

Userspace: `upstream/userspace/ksud_magic/src/allowlist.rs`, built as
`ksud-arm32` (ELF32 ARM, interpreter `/system/bin/linker`). New subcommands:
`allowlist probe|load|save|daemon`. `on_post_data_fs()` calls probe and load
in the same boot phase as the kernel notification. `on_boot_completed()`
forks the save loop, so no extra init service or SELinux transition is needed.

## Candidate ODM image

`odm20_ksu_persist.img` is `odm20_ksu3.img` with: kernelsu.ko replaced,
`/odm/ksud32` installed, root.rc rewritten to keep only `insmod` at
`sys.boot_completed=1`, `ksu_sepolicy.sh` (`permissive su;` only), allowlist
probe/load and `ksud32 boot-completed`. `seflip.ko` (global permissive) and
`root.sh` (TCP 4444 listener) are removed. No root service on 4444 remains in
the image. Recovery image is unchanged.

## Verified locally

- Both kernel variants and the harmless module build clean with the stock
  Module.symvers; `check-static.py` = PASS (no missing symbols, no CRC
  mismatch, protocol symbols present, no kernel file I/O in the candidate).
- `cargo test` in `allowlist-tests/`: 5/5 pass (existing valid file and
  repeated write, truncated file, failed write keeping last valid copy,
  missing/truncated read, bad magic/version).
- ODM candidate: extracted kernelsu.ko matches `kernelsu-persist.ko`; rc has
  no `4444`; ksud32 present. `sha256sum -c HASHES.txt` = PASS for all nine
  artifacts.
- `harmless/ksu_ext4_noop.ko` builds; runtime load is a bench item.

## Bench procedure (not executed)

1. Flash the rebuilt control ODM (`odm20_ksu_control.img`, sha in HASHES.txt)
   first. It is `odm20_ksu3.img` with only `kernelsu-control.ko`
   swapped, so seflip/root.rc stay as in the original. Confirm the module
   loads, `su` works after an in-UI grant, and dmesg shows the `ksu_open` line
   from the workqueue with `wq=1` and `result=-126`.
2. Flash `odm20_ksu_persist.img`. At boot, capture `ksu_open ... wq=0` from
   `allowlist probe`, `allowlist probe: ... data=0 open=-126` from the kernel,
   and the ksud log line with the same result. Confirm no `-126` remains on
   the allowlist load path.
3. Grant root in the Manager, reboot, then power off and boot again: the
   permission must survive. Revoke and repeat. An ungranted app must still
   get `su: Permission denied`.
4. `insmod /harmless/ksu_ext4_noop.ko`: no ext4 sysfs warning. Check
   `getenforce` = Enforcing and that port 4444 is closed (`nc` fails).
5. On a reboot loop, capture serial console if available and collect pstore
   as soon as the device comes back.

## Bench result (control, before stub fix) - FAILED

`bench-control.md`: the first control image loaded the module but produced
`PC is at 0x0`, `LR is at ksu_stub_read+0x40`/`ksu_stub_faccessat+0x40` about
23 s after insmod, then a reboot loop. No allowlist instrumentation was
reachable. Static inspection confirmed the cause: the trampoline jumps to the
assembled stub in module `.text`, whose dispatch literal is `.quad 0`;
`ksu_hook_init` filled only the unused vmalloc copy. Fixed in
`hook_runtime.c` by copying each stub into the vmalloc page, filling its
slots there and patching the kernel functions to that page. Both control and
candidate were rebuilt; static checks and all hashes were regenerated after
the fix. The device was left in the reboot loop; rollback needs authorization.

## Bench retry - FAILED again, second root cause found and fixed

After the dispatch fix the `PC=0` Oops disappeared, but the device looped with
`PC at memcmp+0xd0`, `LR at ksu_handle_execveat_ksud.part.4`, called through
`ksu_handle_execveat` from dispatch case 0. Two additional reconstruction bugs
were confirmed:

- every assembled stub passed `w0 = 0`, so all hooked functions dispatched to
  case 0; `hook_stubs.S` now takes an explicit per-stub id (1..6);
- case 0 mapped `do_execve`'s argv (`x1`) as `struct filename **`. The
  `do_execve` hook was removed; `sys_execve` (case 6) covers the su path.

Both modules and both ODM images were rebuilt; static check and all hashes
were regenerated. The device is again in a reboot loop from the previous
control image; a further rollback needs authorization.

## Bench candidate attempt - FAILED on SELinux label, fixed

Control passed on the third attempt: stable boot, module loaded, six hooks, no
Oops, `wq=1 result=-126` lines absent because `on_post_fs_data` never fires on
this firmware (the workqueue load path is not exercised here); `su -c id`
through the Manager UI stayed pending.

The first candidate booted stably and was Enforcing with 4444 closed, but the
module did not load. Cause: `debugfs rm`+`write` created unlabelled inodes for
`kernelsu.ko`, `ksud32` and `etc/init/root.rc`; with seflip removed there was
no global permissive to hide the denial. `label_odm_candidate.sh` restores
`vendor_file` on the module and ksud and `init_exec` on root.rc, matching the
base image. Candidate ODM rebuilt and rehashed.

## Bench persistence diagnostic - core logic works, Manager not crowned

`bench-persistence.md`: with the diagnostic image (seflip + 4444 restored),
dmesg showed `ksu_open ... wq=0 keyring=1 result=0`, `allowlist probe open=0`,
`allowlist: applied 1 validated records`, no Oops and no module EXT4 warning.
Repeated loads stayed idempotent, a truncated file was rejected with the
previous state preserved, and the list survived a normal reboot. The harmless
module loaded cleanly. The Manager was still not crowned, so grant/revoke was
not reachable.

Root cause: removing the `do_execve` hook also removed the only call to
`track_throne()`, which crowns the Manager. `ksu_handle_execve_ksud` (the
`const char __user *` adapter) is now wired into the `sys_execve` dispatch
case 6 alongside `ksu_handle_execve_sucompat`. Both modules and images were
rebuilt and rehashed.

## Bench persistence diagnostic 2 - still no Manager, third cause found

The `sys_execve` adapter did not crown the Manager either: `track_throne()` is
called only from the absent `vfs_rename` hook, and
`ksu_throne_tracker_init()` is a no-op in v1.1.1. `track_throne()` is now also
called from `EVENT_BOOT_COMPLETED`, which runs in the root ksud32 context with
`/data` mounted and a valid keyring. All artifacts rebuilt and rehashed.

## Bench persistence diagnostic 3 - reverted

Calling `track_throne()` from `EVENT_BOOT_COMPLETED` (prctl context) panicked in
`vfs_read` (`track_throne+0xb0` from `ksu_handle_prctl`). That call was
reverted; the final candidate no longer contains it. Manager crowning stays a
known limitation of this reconstruction: `ksu_throne_tracker_init()` is a
no-op in v1.1.1 and the only other caller is the absent `vfs_rename` hook.
Grant/revoke through the Manager UI therefore remains unverified.

## Manager discovery restored at module init

`throne_tracker.c`: `track_throne()` starts with
`fp = ERR_PTR(-ENOENT)`, so the existing `IS_ERR(fp)` exit is taken when every
open attempt is skipped (this was the cause of the `vfs_read` panic when the
scan was called from the prctl path). `ksu_throne_tracker_init()` now calls
`track_throne()`; insmod runs at `sys.boot_completed`, so discovery happens
once at init. The upstream path `packages.list.tmp` only exists during a
package-manager rename, so at init it always returned ENOENT; the path is now
the committed `packages.list`.

`allowlist.c`: `allowlist_blob_size_locked()` assumes the mutex is held;
`ksu_allowlist_blob_read()` takes `allowlist_mutex` once. The old code called
`ksu_allowlist_blob_size()` while already holding it and deadlocked.

`ksud-arm32`: `kernel_io()` ignores the prctl return value (the real syscall
still answers EINVAL after the pre-hook) and uses the module's `ctl.reply`,
with a sentinel to detect a module that did not answer. All artifacts rebuilt
and rehashed.

## Enforcing fix and final bench (2026-11-24, DONE)

Root cause of the remaining Enforcing failure: `apply_kernelsu_rules()` is
normally called from the `/init` second-stage execve hook. On this firmware
the module is inserted at `sys.boot_completed`, long after that hook fired,
so no KernelSU sepolicy was ever applied. `track_throne()` then ran in the
`vendor_init` domain and its `filp_open("/data/system/packages.list")` was
denied with EACCES (AVC: `vendor_init` / `system_data_file` / `file` / read),
so the Manager was never crowned. The init-script route was a dead end:
`exec` of `/odm/ksu_sepolicy.sh` and `/odm/ksud32` is itself denied in
Enforcing before any patch can be applied.

Changes in `kernelsu-persist.ko` (see `persist.patch` addendum):

- `selinux/rules.c`: `apply_kernelsu_rules()` now grants `vendor_init` read
  access to `system_data_file`, `apk_data_file` and `adb_data_file`, plus
  `init` execute access to `shell_exec`/`vendor_init_exec`; it also resets
  the AVC cache after the rules are installed.
- `ksu.c`: call `apply_kernelsu_rules()` from `kernelsu_init()` right after
  `ksu_compat_syms_init()`, before `ksu_throne_tracker_init()`.
- `hook_runtime.c`: hook `compat_sys_execve` in addition to `sys_execve`.
  All userspace on this device is 32-bit, so without this the `su` path
  never reached `ksu_handle_execve_sucompat()`.

ODM final image (`odm20_ksu_persist.img`, sha `bae7e9e3...`) additionally:

- drops the `exec ... /odm/ksu_sepolicy.sh` line from `root.rc`;
- installs a static aarch64 `su` front-end at `/odm/bin/su` (label
  `shell_exec`, directory label `vendor_file`). `/odm/bin` is already on the
  default PATH, so `su -c id` works from a normal adb shell.

Measured on the device, Enforcing, final image:

- `getenforce` = Enforcing; `kernelsu` Live in `/proc/modules`; no loop and no
  Oops/panic/EXT4 warning for >4 min; recovery untouched; `seflip` absent.
- Port 4444 closed (`/proc/net/tcp*` has no `:115c`, `nc` refused).
- Manager v1.1.1: "Em execucao", "Versao: 12851", "SuperUsuario 1", no
  signature error. dmesg logs `Crowning manager: com.rifsxd.ksunext(uid=10069)`.
- `su -c id` -> `uid=0(root) ... context=u:r:su:s0`. UI revoke -> `su` rc=127
  (denied); UI grant -> uid=0 again; grant survives a normal reboot.
- `allowlist load` repeated 3x: `applied 1 validated records` every time,
  `.allowlist` sha unchanged (no duplicates). Truncating `.allowlist` to 100
  bytes and loading -> `allowlist truncated record: 100 bytes`, load rc=1,
  previous in-memory state preserved (`su` still root); valid file restored
  and reapplied after reboot.
- `target type vendor_init_exec does not exist` and `packages_list_file does
  not exist` are harmless informational messages from the policy tool.

## Remaining limitations

Runtime equivalence of the control build and ENOKEY context comparison were
not re-run after the final fix. No exact original source tree was available,
so the control build is source-close, not byte-identical.
