# Persistence bench - diagnostic image (2026-11-24)

Goal: isolate the allowlist persistence logic with the same module and
ksud32 as the candidate, but with seflip.ko and the port 4444 listener added
back, to have a root shell and dmesg. After the tests, the Enforcing
candidate image was restored.

Device: MiTV-AESP0 (aquaman), ADB serial `26919800005844922`.

## Hashes checked

```
sha256sum -c HASHES.txt                     -> 10/10 OK
odm20_ksu_persist_diag.img  57bc52fe6f69e6a92646578083b77e1ad727c3540ca06851dfa269c50d870e91
odm20_ksu_persist.img       25b80d52ea462a5005b6dc8e2b42b54df83cd23e3030b8ad0e64eb610f71ffdd
harmless/ksu_ext4_noop.ko   a18aae7ff9fc9d44591f1743e48a0fc2cac459a6af135a90e0d8d10e248ee5f0
```

`odm20_ksu_persist_diag.img` is not in HASHES.txt; hash checked directly.

## Flash commands

Diagnostic:

```
adb reboot fastboot
python3 tools/fb_raw.py getvar product -> OKAYaquaman
python3 tools/fb_raw.py download .../odm20_ksu_persist_diag.img -> OKAY (2.7s)
python3 tools/fb_raw.py cmd 'set_active:;store write odm 10200000 0 1400000' 20000 -> OKAY (1.8s)
python3 tools/fb_raw.py cmd reboot 10000 -> OKAY (0.0s)
```

Restore at the end:

```
adb reboot fastboot
python3 tools/fb_raw.py getvar product -> OKAYaquaman
python3 tools/fb_raw.py download .../odm20_ksu_persist.img -> OKAY (3.0s)
python3 tools/fb_raw.py cmd 'set_active:;store write odm 10200000 0 1400000' 20000 -> OKAY (0.9s)
python3 tools/fb_raw.py cmd reboot 10000 -> OKAY (0.0s)
```

## Boot of the diagnostic image

`boot_id=9e53ade3-...` constant, `sys.boot_completed=1` from
12:28:11. No loop and no Oops. Root via 4444:

```
id -> uid=0(root) gid=0(root) groups=0(root) context=u:r:dumpstate:s0
lsmod -> kernelsu 102400 0 / seflip 16384 0
getenforce -> Permissive
```

dmesg (excerpt):

```
[   23.829728] KernelSU: ksu_core_init: LSM hooks not in use.
[   24.008112] KernelSU: ksu_sucompat_init: hooks enabled: execve/execveat_su, faccessat, stat, devpts
[   24.010171] KernelSU: ksu_hook: sys_faccessat at ffffff8009215ba8
[   24.012024] KernelSU: ksu_hook: sys_read at ffffff80092197d0
[   24.013984] KernelSU: ksu_hook: sys_newfstatat at ffffff800921eb78
[   24.014758] KernelSU: ksu_hook: sys_reboot at ffffff80090cde98
[   24.015082] KernelSU: ksu_hook: sys_prctl at ffffff80090be398
[   24.017248] KernelSU: ksu_hook: sys_execve at ffffff8009221a10
[   24.075235] KernelSU: SELinux permissive or disabled when handle policy!
[   24.131651] KernelSU: ksu_open /data/adb/ksu/.allowlist jiffies=4294884520 pid=3697 comm=ksud32 wq=0 keyring=1 result=0
[   24.131665] KernelSU: allowlist probe: jiffies=4294884520 pid=3697 comm=ksud32 data=0 open=0 wq=0
[   24.158036] KernelSU: allowlist: applied 1 validated records at jiffies=4294884528
[   24.178905] KernelSU: boot_complete triggered at jiffies=4294884534
[   24.182835] KernelSU: stop input_hook
```

- The candidate path worked: `ksu_open ... wq=0 keyring=1 result=0`
  (ksud32, not a workqueue), `allowlist probe ... open=0`, and one validated
  write applied. The old control's `result=-126` did not appear.
- `ext4 sysfs nuke disabled` did not appear in dmesg. There was also no EXT4
  warning attributable to the module: only the normal root/odm/vendor/data
  mounts.
- No Manager-crowned line. `/odm/ksud32 debug version` returned
  `Kernel Version: 12851` (via prctl).

## Manager

The Manager was opened (`com.rifsxd.ksunext/.ui.MainActivity`) even in
Permissive. The screen **still** shows "KernelSU Next v2 signature not found
in kernel! [ !KSU_NEXT || != size/hash ]" and "Manager version
v1.1.1 (12851)". In other words, the hypothesis that crowning failed only
because SELinux denied reading `/data/system/packages.list` **was not
confirmed**. Without detection, the UI does not show a Superuser list and
there is no way to grant/revoke through it.

Attempting crowning via `/odm/ksud32 debug set-manager com.rifsxd.ksunext`
failed with `Error: No such file or directory (os error 2)`; the subcommand's
own help warns that it requires `CONFIG_KSU_DEBUG`.

## Persistence tests via root shell

Initial file: `/data/adb/ksu/.allowlist`, sha
`473c02f2be150da95b35c8741955cbd30908f7226a37f1b514eac39712d16ac7`,
1 record (`com.android.shell`).

### Repeated load

```
/odm/ksud32 allowlist load  -> Error: allowlist ioctl syscall failed: -1
/odm/ksud32 allowlist load  -> Error: allowlist ioctl syscall failed: -1
```

Despite the error reported by the CLI, dmesg recorded two new
`allowlist: applied 1 validated records` lines (jiffies 4294946430 and 4294946443).
There was no duplication: the number of applied records stayed 1 on all
loads. The ioctl returning `-1` after application is a CLI/kernel divergence
worth investigating, but it caused no duplication or error in the allowlist
state.

### Truncated file

Procedure with backup and restore:

```
cp .allowlist .allowlist.diagbak  -> sha equal to original
: > .allowlist                    -> 0 bytes
/odm/ksud32 allowlist load        -> Error: allowlist truncated: 0 bytes
dmesg                             -> no new "applied" line
cp .allowlist.diagbak .allowlist  -> sha 473c02f2... (restored)
rm .allowlist.diagbak
```

Result: the truncated file was rejected before reaching the kernel and the
previous state (1 record) remained. Restoration checked by hash.

### Persistence across normal reboot

Before reboot the file had sha `473c02f2...`. After `adb reboot`:

```
boot_id=d3e237a9..., sys.boot_completed=1
sha256sum /data/adb/ksu/.allowlist -> 473c02f2... (unchanged)
dmesg:
[   30.451081] KernelSU: ksu_open /data/adb/ksu/.allowlist ... wq=0 keyring=1 result=0
[   30.451093] KernelSU: allowlist probe: ... open=0 wq=0
[   30.476745] KernelSU: allowlist: applied 1 validated records ...
[   30.502033] KernelSU: boot_complete triggered ...
```

The allowlist survived the reboot and was reapplied on the next boot.

### Harmless module

```
adb push work/ksu-lkm-fix/harmless/ksu_ext4_noop.ko /data/local/tmp/
sha256sum /data/local/tmp/ksu_ext4_noop.ko -> a18aae7f... (matches)
insmod /data/local/tmp/ksu_ext4_noop.ko -> INSMOD_OK
lsmod -> ksu_ext4_noop 16384 0 / kernelsu 102400 0 / seflip 16384 0
dmesg -> [  285.646256] ksu_ext4_noop: loaded, no sysfs or ext4 changes
```

Loaded without ext4/sysfs warning. The only avc is `module_load` with
`permissive=1`, expected for insmod from the root shell.

## Untested items and reason

- `grant/revoke via UI`, `su -c id = uid=0 after grant`, and `unauthorized
  app without su`: not testable. The Manager does not detect the kernel
  signature even in Permissive, so there is no Superuser list. `su` also
  does not exist in PATH (`su: not found`) and `/odm/ksud32 debug su`
  returns `Error: Operation not permitted (os error 1)`.
- `survive full power-off + boot`: not tested. No physical access to the
  power button on this bench; `reboot -p` would leave the device off with no
  way to turn it back on via adb.
- `revoke removes access`: not tested, for the same reason as grant.

## Final state

Enforcing candidate image `odm20_ksu_persist.img` (25b80d52...) restored.
Stable boot: `boot_id=e92f793c-3a1c-4fe0-a63f-c2acf69e5c28`,
`sys.boot_completed=1`, `getenforce=Enforcing`, `kernelsu` present in
`/proc/modules`, port 4444 closed. No other file edited. No commit.

## execve_ksud / track_throne adapter test (2026-11-24)

Reported fix: with the removal of the do_execve hook, the only caller of
`track_throne()` was lost; the `ksu_handle_execve_ksud` adapter was changed
to be called in case 6 (sys_execve) together with `ksu_handle_execve_sucompat`.
Modules and images rebuilt, check-static PASS.

Hashes checked (`sha256sum -c HASHES.txt` -> 11/11 OK):

```
odm20_ksu_persist.img        cdc4cc8048a5df3613bbbe67de4f62ca164fd38f632fdf1df16121ab1f69e14f
odm20_ksu_persist_diag.img   d13e06b02482b5fef49811bc3aab62ad09b5fbf31f883f076136cbe6a30621d1
harmless/ksu_ext4_noop.ko    a18aae7ff9fc9d44591f1743e48a0fc2cac459a6af135a90e0d8d10e248ee5f0
```

### Enforcing candidate (cdc4cc80...)

Flash via fb_raw.py: getvar `OKAYaquaman`, download `OKAY (2.9s)`, store
write `OKAY (0.9s)`, reboot `OKAY (0.0s)`. Stable boot,
`boot_id=6429c4df...`, `sys.boot_completed=1`. `getenforce=Enforcing`,
`kernelsu` in `/proc/modules`, port 4444 closed.

Manager opened via `am start -n com.rifsxd.ksunext/.ui.MainActivity`.
Readable screencap: **the "KernelSU Next v2 signature not found in kernel"
message is still present**, no Superuser list appeared. The fix did not
resolve detection on the Enforcing candidate.

### Diagnostic image (d13e06b0...)

Flash: getvar `OKAYaquaman`, download `OKAY (2.8s)`, store write
`OKAY (0.8s)`, reboot `OKAY (0.0s)`. Stable boot,
`boot_id=35d780da...`, `sys.boot_completed=1`. Root via 4444:

```
id -> uid=0(root) gid=0(root) groups=0(root) context=u:r:dumpstate:s0
lsmod -> kernelsu 102400 0 / seflip 16384 0
```

Manager opened: **still shows the v2 signature not found message**, no
Superuser list. The grant/revoke tests below could not be done on this image
for that reason.

dmesg (excerpt):

```
[   29.809695] KernelSU: ksu_core_init: LSM hooks not in use.
[   29.987105] KernelSU: ksu_sucompat_init: hooks enabled: execve/execveat_su, faccessat, stat, devpts
[   29.989071] KernelSU: ksu_hook: sys_faccessat at ffffff8009215ba8
[   29.990899] KernelSU: ksu_hook: sys_read at ffffff80092197d0
[   29.992806] KernelSU: ksu_hook: sys_newfstatat at ffffff800921eb78
[   29.993228] KernelSU: ksu_hook: sys_reboot at ffffff80090cde98
[   29.993551] KernelSU: ksu_hook: sys_prctl at ffffff80090be398
[   29.995419] KernelSU: ksu_hook: sys_execve at ffffff8009221a10
[   30.044958] KernelSU: SELinux permissive or disabled when handle policy!
[   30.101406] KernelSU: ksu_open /data/adb/ksu/.allowlist ... wq=0 keyring=1 result=0
[   30.101419] KernelSU: allowlist probe: ... open=0 wq=0
[   30.121090] KernelSU: allowlist: applied 1 validated records ...
[   30.139462] KernelSU: boot_complete triggered ...
```

- `allowlist: applied` present; `ext4 sysfs nuke disabled` **absent**;
  no Oops/Internal error.
- `manager crowned` / `track_throne` **absent** from dmesg.
- `/odm/ksud32 debug set-manager com.rifsxd.ksunext` -> `Error: No such
  file or directory (os error 2)`, as in the previous round.

Read-only inspection of the local code explains why the problem persists:
`ksu-skeleton/throne_tracker.c:461` defines
`ksu_throne_tracker_init()` as "nothing to do", so module init does not call
`track_throne()`. The only remaining caller is the rename handler at
`core_hook.c:234`, which depends on the `vfs_rename` hook (absent in this
build, per limitation 3 in report
`kernelsu-next-lkm-2026-11-23.md`). The adapter added to case 6 calls
`ksu_handle_execveat_ksud`, which does not call `track_throne()`. The
reported hypothesis for the fix does not match the current code.

### Pending

Grant/revoke, `su -c id` after grant, survival across reboot and
full power-off, and unauthorized app without `su`: not tested because the
Manager UI shows no Superuser list in either image.

### Final state

Enforcing candidate `cdc4cc80...` restored. Stable boot,
`boot_id=dcf54e9a-8127-41f4-9bbe-af8ccd17be73`, `sys.boot_completed=1`,
`getenforce=Enforcing`, `kernelsu` in `/proc/modules`, port 4444
closed. No other file edited, no commit.

## track_throne() at boot_completed test (2026-11-24) - FAILED WITH PANIC

Reported fix: `track_throne()` was changed to be called in the
`EVENT_BOOT_COMPLETED` handler, triggered by `/odm/ksud32 boot-completed`
from the rc.

Hashes checked:

```
sha256sum -c HASHES.txt -> 11/11 OK
odm20_ksu_persist.img        fc972f820b0092a94863dea325b9febb4c1b0eef3380d19152728503ba6502e5
odm20_ksu_persist_diag.img   9d99357b7ff84dfe8eb0cd157e4f06d288b5120cf39a3cc9f2114d0d9cd023e7
kernelsu.ko inside the candidate (read-only loop mount)
                             774232da17736f05e2003e1554972f03450079d815923452e02b0c9f3fac563c
```

### Enforcing candidate (fc972f82...)

Flash: getvar `OKAYaquaman`, download `OKAY (3.0s)`, store write
`OKAY (1.1s)`, reboot `OKAY (0.0s)`. Stable boot,
`boot_id=f4e0a7c5...`, `sys.boot_completed=1`, `getenforce=Enforcing`,
`kernelsu` in `/proc/modules`, port 4444 closed.

Manager opened via am start. **The "KernelSU Next v2 signature not found in
kernel" message is still present** and no Superuser list appeared. The fix
did not work on Enforcing.

### Diagnostic image (9d99357b...)

Flash: download `OKAY (2.8s)`, store write `OKAY (1.2s)`, reboot `OKAY
(0.0s)`. The first boot came up (`boot_id=91463d90`, boot_completed=1) and
root via 4444 worked, but dmesg already showed
`androidboot.reboot_mode=kernel_panic`. Then the device entered
**a reboot loop with kernel panic**: boot_id `e30394a1` -> `b0381335`,
with `sys.boot_completed=1` around 30 s and a drop right after.

pstore `/sys/fs/pstore/console-ramoops-0` (excerpt):

```
[   31.616801@1] Internal error: Oops: 96000005 [#1] PREEMPT SMP
[   31.673584@1] PC is at vfs_read+0x2c/0x150
[   31.677633@1] LR is at kernel_read+0x60/0xa8
[   32.460039@1] [ffffff802048f8c0+  64][<ffffff8002651180>] ksu_kernel_read_compat+0x48/0xa0 [kernelsu]
[   32.469183@1] [ffffff802048f900+ 400][<ffffff800264eb18>] track_throne+0xb0/0x398 [kernelsu]
[   32.477541@1] [ffffff802048fa90+ 848][<ffffff800264f994>] ksu_handle_prctl+0x6b4/0xb10 [kernelsu]
[   32.492647@1] [ffffff802048fde0+   0][<ffffff80026516f8>] ksu_hook_dispatch+0xb8/0x1d8 [kernelsu]
[   32.508394@1] Code: aa1e03e0 aa0203f3 aa0303f7 d503201f (b9404680)
[   32.527858@1] Kernel panic - not syncing: Fatal exception
[   33.546543@1] reboot reason 12
```

The chain shows `track_throne()` being called from inside
`ksu_handle_prctl` (via `EVENT_BOOT_COMPLETED` triggered by ksud32's prctl),
and `ksu_kernel_read_compat` reading with an invalid pointer in
`vfs_read`. Unlike previous rounds, here there is an Oops and panic, not
just missing crowning.

It was not possible to open the Manager UI on this diagnostic image before
the loop: the first access to 4444 failed with `Connection refused`
(during the reboot window) and, when root was obtained, the log already
indicated the panic. No grant/revoke test was done.

Serial console: unavailable (`/dev/ttyUSB*`, `/dev/ttyACM*` absent).

### Pending

Exact UI state on the diagnostic after the fix: not captured, because
the device entered a panic loop. Grant/revoke, `su -c id`, survival across
reboot/power-off and unauthorized app: not tested.

### Final state

Recovery from the loop: `adb reboot fastboot` in the first window where adb
came up, confirmed with `fb_raw.py devices -> True` and `product=OKAYaquaman`.
Enforcing candidate `fc972f82...` restored. Stable boot after 20 s of
observation: `boot_id=e9251a19-cbf0-444d-8f16-e9c591fe6ec4`,
`sys.boot_completed=1`, `getenforce=Enforcing`, `kernelsu` in
`/proc/modules`, port 4444 closed. No other file edited, no commit.
STOP as requested.

## Final chapter - candidate with track_throne reverted (2026-11-24)

The `track_throne()` call that caused the panic was reverted. Last
candidate rebuilt and flashed.

Hashes checked:

```
sha256sum -c HASHES.txt -> 11/11 OK
odm20_ksu_persist.img        701a7fd1b63c55b3ac81feae6f7b746a4576c7066c91c623fadd157d4eb6db6b
kernelsu.ko inside the image 191f7f4291523aef972c71e23ce371b603fb7bfd4e9b066038aa3ac69fe61083
```

Flash via fb_raw.py: `product=OKAYaquaman`, download `OKAY (3.2s)`,
store write `OKAY (1.8s)`, reboot `OKAY (0.0s)`.

Stability observed for 4 minutes (13:01:39 to 13:05:33):
`boot_id=85fe28d3-7ac4-46d7-853e-3fd0536d6cdd` constant,
`sys.boot_completed=1` from 13:02:00, `getenforce=Enforcing`,
`kernelsu` in `/proc/modules`, port 4444 with `Connection refused`.
No loop, no reboot and no observable Oops. `dmesg` requires root on this
image, so `reboot_mode` could not be read directly; the stable boot_id
rules out a recent panic.

Final state: Enforcing candidate `701a7fd1...` written, device
stable. Pending items unchanged from previous rounds: the Manager does not
detect the v2 signature and shows no Superuser list, so
grant/revoke, `su -c id`, persistence across reboot/power-off and
unauthorized app remain untested. No other file edited, no commit.

## track_throne + mutex + reply fix (2026-11-24) - CAUSE FOUND

Reported fixes: `track_throne()` starts with `fp = ERR_PTR(-ENOENT)` and
`ksu_throne_tracker_init()` calls `track_throne()`; allowlist export takes
`allowlist_mutex` once (`allowlist_blob_size_locked`); ksud32 uses `ctl.reply`
with a sentinel instead of the syscall return.

Hashes checked:

```
sha256sum -c HASHES.txt -> 11/11 OK
odm20_ksu_persist.img      899a1a877fb6a9e37686bdce8606774ad113fb0e377b4eba84653041d64e1f99
odm20_ksu_persist_diag.img 2629e947125b29eb0d7a46f0eefdade336c0ba0ade0f4cc3e7ed553590a7b1fd
```

### Enforcing candidate (899a1a87...)

Flash: getvar `OKAYaquaman`, download `OKAY (2.8s)`, store write
`OKAY (0.9s)`, reboot `OKAY (0.0s)`. Stable boot,
`boot_id=c380ff9c...`, `sys.boot_completed=1`, `getenforce=Enforcing`,
`kernelsu` in `/proc/modules`, port 4444 closed. Manager opened:
**still shows "KernelSU Next v2 signature not found in kernel"**, no
Superuser list.

### Diagnostic (2629e947...) - root cause

Flash: download `OKAY (2.8s)`, store write `OKAY (1.2s)`, reboot `OKAY
(0.0s)`. Stable boot `boot_id=3cde689b...`, root via 4444,
`kernelsu`+`seflip` loaded. Manager opened: also still no
detection, no Superuser list. Grant/revoke was not possible.

dmesg (excerpt):

```
[   29.712463] KernelSU: ksu_core_init: LSM hooks not in use.
[   29.888502] KernelSU: track_throne: waiting for /data/system/packages.list.tmp
   ... (10 attempts, 100 ms each) ...
[   30.952458] KernelSU: track_throne: open /data/system/packages.list.tmp failed: -2
[   30.952466] KernelSU: ksu_sucompat_init: hooks enabled: execve/execveat_su, faccessat, stat, devpts
[   31.230591] KernelSU: ksu_open /data/adb/ksu/.allowlist ... wq=0 keyring=1 result=0
[   31.270176] KernelSU: allowlist: applied 1 validated records ...
[   31.297425] KernelSU: boot_complete triggered ...
```

Root cause found by reading local code (read-only):
`ksu-skeleton/throne_tracker.c:18` defines
`#define SYSTEM_PACKAGES_LIST_PATH "/data/system/packages.list.tmp"`.
The real file on the device is `/data/system/packages.list` (no `.tmp`),
11668 bytes, `system:package_info`. The `.tmp` suffix is used by
Android only as a lock file during rewrite; since it does not exist at boot,
`is_lock_held()` returns true on all 10 attempts and the code never gets to
open the real packages.list. There is no AVC: dmesg only shows the
`track_throne` lines above, with no `avc:` for
`packages.list`. The `-2` is ENOENT for the `.tmp` file, not ENOKEY/EACCES.

No `Found new base.apk`, `is_manager: 1` or `Crowning
manager` lines in dmesg. `allowlist: applied` present; no Oops/panic
in this round (unlike the previous attempt).

It was not possible to obtain the AVC on the Enforcing candidate because it
has no root service and `dmesg`/`/sys/fs/pstore` require root. From the
diagnostic, there is no sign of a SELinux denial: the problem is the `.tmp`
path.

### Pending

Grant/revoke, `su -c id`, survival across reboot/power-off and
unauthorized app: not tested; the UI shows no Superuser in either image.
Fixing `SYSTEM_PACKAGES_LIST_PATH` is out of scope for this bench (no
code was changed).

### Final state

Enforcing candidate `899a1a87...` restored. Stable boot,
`boot_id=2186a835-4cec-4071-a69a-d78c907e8a0d`,
`sys.boot_completed=1`, `getenforce=Enforcing`, `kernelsu` in
`/proc/modules`, port 4444 closed. No other file edited, no commit.

## packages.list path fix (2026-11-24) - MANAGER CROWNED ON DIAGNOSTIC

Fix: `SYSTEM_PACKAGES_LIST_PATH` changed from
`/data/system/packages.list.tmp` to `/data/system/packages.list`,
because discovery now runs at init and `.tmp` only exists during
rename. Module and images rebuilt, check-static PASS.

Hashes checked:

```
sha256sum -c HASHES.txt -> 11/11 OK
odm20_ksu_persist.img       7812b288b7d45ea95d6da29183aa69f157bd356bf0e391baf7510c6c2f4354e7
odm20_ksu_persist_diag.img  880a69049aa0458f9419819c950ad885cf02047e451da48ac6aec8e950881541
kernelsu.ko inside the candidate
                            363c9f2d50210f97ddf16e9706365925f23c5c2bb1bcd580cc0faeb57ee0e78b
```

### Enforcing candidate (7812b288...)

Flash: getvar `OKAYaquaman`, download `OKAY (2.8s)`, store write
`OKAY (1.7s)`, reboot `OKAY (0.0s)`. Stable boot,
`boot_id=aefee3a0...`, `sys.boot_completed=1`, `getenforce=Enforcing`,
`kernelsu` in `/proc/modules`, port 4444 closed.

Manager opened: **still shows "KernelSU Next v2 signature not found
in kernel"** and shows no Superuser list. The path fix did not make the
Manager detect in Enforcing. The AVC could not be read because
the image has no root service and `dmesg`/pstore require root. Unconfirmed
hypothesis: in Enforcing the domain doing the insmod cannot
open `packages.list`; in Permissive diagnostic the same read
worked.

### Diagnostic (880a6904...)

Flash: download `OKAY (3.0s)`, store write `OKAY (1.7s)`, reboot `OKAY
(0.0s)`. Stable boot `boot_id=877ca388...`, root via 4444,
`kernelsu`+`seflip` loaded.

dmesg (excerpt):

```
[   28.731680] KernelSU: ksu_core_init: LSM hooks not in use.
[   28.907015] KernelSU: ksu_open /data/system/packages.list ... comm=init wq=0 keyring=1 result=0
[   28.907023] KernelSU: track_throne: /data/system/packages.list found!
[   28.918073] KernelSU: Searching manager...
[   28.918190] KernelSU: search_manager: dir: /data/app got magic! 0xef53
[   28.919852] KernelSU: Found new base.apk at path: .../com.mitv.tvhome.michannel.../base.apk, is_manager: 0
[   28.932762] KernelSU: Found new base.apk at path: .../com.rifsxd.ksunext.../base.apk, is_manager: 1
[   28.932771] KernelSU: manager pkg: com.rifsxd.ksunext
[   28.932779] KernelSU: Crowning manager: com.rifsxd.ksunext(uid=10069)
[   28.932786] KernelSU: Stop searching
[   28.932806] KernelSU: Search manager finished
[   28.932847] KernelSU: ksu_sucompat_init: hooks enabled: execve/execveat_su, faccessat, stat, devpts
   ... 6 ksu_hook lines ...
[   29.064536] KernelSU: ksu_open /data/adb/ksu/.allowlist ... comm=ksud32 wq=0 keyring=1 result=0
[   29.086351] KernelSU: allowlist: applied 1 validated records ...
```

No AVC/EACCES on packages.list; no Oops/panic. No `ext4 sysfs
nuke disabled` observed in this round.

**Manager UI on the diagnostic: functional.**
Home screen: "Running LEGACY, Version: 12851", Superuser 1,
Module 0. The Superuser list showed `Shell (com.android.shell)`
with a ROOT badge and other apps (Aurora Store, LocalSend, Nuvio,
PlayAutoInstalls) with UMUNT.

### Grant/revoke on the diagnostic

- Shell toggle OFF via UI -> allowlist changed from sha
  `473c02f2be150da95b35c8741955cbd30908f7226a37f1b514eac39712d16ac7`
  to `0861cd9ab035f1cbcb230cc28c24f8efcc383d5a8a65892ffb1f1699e26d941a`.
  The screen confirmed the toggle off. dmesg recorded ksud32
  writing `.allowlist.tmp` and renaming, with AVCs `permissive=1`
  on `u:r:su:s0` -> `adb_data_file` (expected because the diagnostic is
  Permissive).
- `adb reboot` -> `boot_id=4489d496`, allowlist stayed
  `0861cd9a...`; the Shell screen still had the toggle off.
  **Revoke survived the reboot.**
- Shell toggle ON via UI -> allowlist returned to sha
  `473c02f2...`.
- `adb reboot` -> `boot_id=11ff964e`, allowlist stayed
  `473c02f2...`, home screen "Running LEGACY" with Superuser 1.
  **Grant survived the reboot.**
- Unauthorized app: Aurora Store and the others appeared with toggle
  off and UMUNT badge, including after reboot. **`su` was not
  used to confirm the denial** (see pending).

### Pending

- `su -c id = uid=0` after grant: not tested. ksud32 installed
  `busybox`, `magiskboot`, `resetprop`, `susfsd` and a `ksud` symlink
  in `/data/adb/ksu/bin/`, but **there is no `su` binary** there or in PATH.
  `adb shell su -c id` -> `su: not found`, and `/odm/ksud32 debug su`
  -> `Error: Operation not permitted (os error 1)`. The UI confirms the
  allowlist state, but there is no `su` client to prove uid 0.
- Full power-off: not tested; no physical button on this bench,
  `reboot -p` would leave the device off with no way to turn it back on.
- AVC in Enforcing: not obtained due to lack of root service/dmesg.

### Final state

Enforcing candidate `7812b288...` restored. Stable boot,
`boot_id=0fca868d-229b-4855-a872-3280bf7a142a`,
`sys.boot_completed=1`, `getenforce=Enforcing`, `kernelsu` in
`/proc/modules`, port 4444 closed. No other file edited, no commit.

## AVC diagnostic in Enforcing (2026-11-24)

Image `odm20_ksu_avc.img` =
`1ef5755f3b25c6bcd19b7a99673ba81d0e382da7a95a67ad0aeb8070eb3aeeaa`,
hash checked directly. Keeps Enforcing (no seflip) and adds back
the port 4444 listener with `seclabel u:r:su:s0`, with `permissive su;` applied
by the rc before start.

Flash: getvar `OKAYaquaman`, download `OKAY (3.0s)`, store write
`OKAY (2.0s)`, reboot `OKAY (0.0s)`. Stable boot,
`boot_id=ac4016b9...`, `sys.boot_completed=1`, `getenforce=Enforcing`,
`kernelsu` in `/proc/modules`.

**The port 4444 listener did not come up.** `init.svc.rootsh` stayed in
`restarting` throughout observation and `nc 127.0.0.1 4444` connected but
received no output. Cause in logcat:

```
type=1400 audit(0.0:136): avc: denied { transition } for path="/odm/sh"
dev="mmcblk0p15" ino=20 scontext=u:r:init:s0 tcontext=u:r:su:s0
tclass=process permissive=0
```

Same AVC repeated every 5 s (audits 136-156). The service's `seclabel
u:r:su:s0` requires a transition that policy denies in
Enforcing; the rc's `permissive su;` does not cover `init`'s transition.
Read-only inspection of the local image confirmed the labels:
`/odm/sh` = `dumpstate_exec:s0`, `/odm/toybox` = `shell_exec:s0`,
`/odm/root.sh` = `shell_exec:s0`, `etc/init/root.rc` = `init_exec:s0`.

**There was no `packages.list` AVC.** Scan of 2000 logcat lines: no line
containing `packages.list`, no `track_throne`,
`Crowning` or `is_manager`. The only unique `avc: denied` in the log was
`{ transition }` for `/odm/sh`. It was not possible to read dmesg via 4444
because the listener did not work, and `/sys/fs/pstore` requires root.

Manager on this image: **still shows "KernelSU Next v2 signature not
found in kernel"**, no Superuser list.

Conclusion: the hypothesis of a SELinux denial when reading
`/data/system/packages.list` in Enforcing **was not confirmed**. The
only AVC observed is the `init -> su` transition for the listener,
unrelated to the module reading packages.list. The cause of
non-crowning in Enforcing remains unexplained in the logs.

Final state: Enforcing candidate `7812b288...` restored. Boot
stable, `boot_id=6fd76f32-d397-48ff-a969-dad414459a3a`,
`sys.boot_completed=1`, `getenforce=Enforcing`, `kernelsu` in
`/proc/modules`, port 4444 closed. No other file edited, no commit.

## AVC2 diagnostic - hypothesis CONFIRMED (2026-11-24)

Image `odm20_ksu_avc2.img` =
`0d13c877ab5fe0652d0913c9491156bdb1c9a9d84b0ebd366a3835fecbb7af97`,
hash checked. Enforcing without seflip, port 4444 listener added back
without the problematic `seclabel u:r:su:s0` (root.rc same as original).

Flash: getvar `OKAYaquaman`, download `OKAY (3.2s)`, store write
`OKAY (2.0s)`, reboot `OKAY (0.0s)`. Stable boot,
`boot_id=2aa6414c...`, `sys.boot_completed=1`,
`getenforce=Enforcing`, `kernelsu` in `/proc/modules`. This time
`init.svc.rootsh=running`, `debug.root_service=RUNNING`, and root via
4444 worked:

```
id -> uid=0(root) gid=0(root) groups=0(root) context=u:r:dumpstate:s0
```

Exact track_throne AVC (full line, no truncation):

```
[   30.346463@3] type=1400 audit(1795540230.370:110): avc: denied { read } for pid=2334 comm="init" name="packages.list" dev="mmcblk0p20" ino=3541 scontext=u:r:vendor_init:s0 tcontext=u:object_r:system_data_file:s0 tclass=file permissive=0
```

Correlated module lines:

```
[   30.346322@1] KernelSU: ksu_open /data/system/packages.list jiffies=4294886385 pid=2334 comm=init wq=0 keyring=1 result=-13
[   30.346330@1] KernelSU: track_throne: waiting for /data/system/packages.list
   ... 10 attempts, result=-13 on all ...
[   31.412094@3] KernelSU: track_throne: open /data/system/packages.list failed: -13
```

`-13` is EACCES, consistent with the AVC above. `vendor_init` does not have
`read` on `system_data_file`. Additional consequences in the same boot:

```
[   31.445140@3] init: cannot execve('/odm/ksu_sepolicy.sh'): Permission denied
[   31.450722@2] init: cannot execve('/odm/ksud32'): Permission denied
[   31.454877@2] init: cannot execve('/odm/ksud32'): Permission denied
[   31.460862@0] init: cannot execve('/odm/ksud32'): Permission denied
```

So in Enforcing `permissive su;` is never applied and
ksud32 never executes. There was no `Crowning manager` or `is_manager: 1`.
Manager still showed "KernelSU Next v2 signature not found".

Conclusion: the hypothesis is confirmed. Non-crowning on the Enforcing
candidate is caused by `avc: denied { read }` from `u:r:vendor_init:s0`
on `u:object_r:system_data_file:s0` (the `packages.list` file),
resulting in EACCES in `track_throne()`. The Permissive diagnostic
image crowned the Manager because there the denial is only logged.

Final state: Enforcing candidate `7812b288...` restored. Boot
stable, `boot_id=88f150ec-e242-45d5-9f82-105922957dce`,
`sys.boot_completed=1`, `getenforce=Enforcing`, `kernelsu` in
`/proc/modules`, port 4444 closed. No other file edited, no commit.

## sepolicy in Enforcing image with root for dmesg (2026-11-24)

Image `odm20_ksu_enforce_avc.img` =
`8e8ad3d454160fb70a6d59a987e2d78bb1d187906d7f8b00537bcfb7f6676997`,
hash checked. Same sepolicy/exec configuration as image
`c5edb962...`, but with original rootsh (no seclabel) to be able to read
dmesg in Enforcing.

Flash: getvar `OKAYaquaman`, download `OKAY (3.0s)`, store write
`OKAY (2.0s)`, reboot `OKAY (0.0s)`. Stable boot,
`boot_id=248031fe...`, `sys.boot_completed=1`, Enforcing, `kernelsu`
in `/proc/modules`. `init.svc.rootsh=running` and root via 4444
worked (`uid=0(root) context=u:r:dumpstate:s0`).

dmesg (exact lines, excerpt):

```
[   29.842882] init: cannot execve('/odm/ksu_sepolicy.sh'): Permission denied
[   29.882206] KernelSU: ksu_core_init: LSM hooks not in use.
[   30.058044] KernelSU: ksu_open /data/system/packages.list jiffies=4294886297 pid=2334 comm=init wq=0 keyring=1 result=-13
[   30.058053] KernelSU: track_throne: waiting for /data/system/packages.list
[   30.058185] type=1400 audit(1795541000.076:110): avc: denied { read } for pid=2334 comm="init" name="packages.list" dev="mmcblk0p20" ino=3300 scontext=u:r:vendor_init:s0 tcontext=u:object_r:system_data_file:s0 tclass=file permissive=0
   ... 10 attempts with result=-13 ...
[   31.123465] KernelSU: track_throne: open /data/systemackages.list failed: -13
```

(In the line above, the actual log text is
`open /data/system/packages.list failed: -13`.)

```
[   31.123499] KernelSU: ksu_sucompat_init: hooks enabled: execve/execveat_su, faccessat, stat, devpts
   ... 6 ksu_hook lines ...
[   31.161013] init: cannot execve('/odm/ksud32'): Permission denied
[   31.176571] init: cannot execve('/odm/ksud32'): Permission denied
[   31.183725] init: cannot execve('/odm/ksud32'): Permission denied
```

Conclusion: **the sepolicy patch was never applied**. Even with
the script placed before insmod and `ksud32`/`ksu_sepolicy.sh`
labeled `vendor_init_exec:s0`, `init` cannot execute
`/odm/ksu_sepolicy.sh` in Enforcing (`cannot execve`, Permission
denied). Direct consequence: the `allow vendor_init
system_data_file:file read;` rule never takes effect, `track_throne`
keeps failing with EACCES (`-13`) from the same AVC as before, and the
`ksud32` execs also fail. No patch-applied lines, `Crowning manager` or
`is_manager: 1` appeared. Manager still did not detect the v2 signature.

This also explains the result from image `c5edb962...`: logcat did not
show `cannot execve` because those messages come from init via
dmesg, not logcat.

Final state: Enforcing candidate `7812b288...` restored. Boot
stable, `boot_id=4424e218-a4b7-4a02-bf0f-89e84de3b089`,
`sys.boot_completed=1`, `getenforce=Enforcing`, `kernelsu` in
`/proc/modules`, port 4444 closed. No other file edited, no commit.

## enforce2 variant with execs in init domain (2026-11-24)

Image `odm20_ksu_enforce2.img` =
`63d05ef139572c28179f604e072340aaefa485e98e1f6d9e1c70d98150c84b17`,
hash checked. No seclabel on the execs (init domain, which worked
with rootsh): `exec root root -- /odm/ksu_sepolicy.sh`, insmod and
`exec root root -- /odm/ksud32 allowlist probe|load|boot-completed`.
The script applies `allow init system_data_file:file read;` and `permissive
su;` via `/odm/ksud32` before insmod. `ksud32` and `ksu_sepolicy.sh`
labeled `u:object_r:shell_exec:s0`.

Flash: getvar `OKAYaquaman`, download `OKAY (2.9s)`, store write
`OKAY (2.0s)`, reboot `OKAY (0.0s)`. Stable boot,
`boot_id=18b589f8...`, `sys.boot_completed=1`, Enforcing, `kernelsu`
in `/proc/modules`, port 4444 closed.

Manager opened: **still shows "KernelSU Next v2 signature not
found in kernel"**, no Superuser list.

logcat (3000 lines): no `cannot execve`, no `sepolicy` or
`ksud32`. The only visible `avc: denied` entries are three
`{ read }` on `u:object_r:system_prop:s0` by
`scontext=u:r:system_control:s0`, unrelated to packages.list. Since
init writes `cannot execve` to dmesg and this image has no root
service, it was not possible to confirm whether the execs failed.

Conclusion: the variant did not restore Manager detection in
Enforcing. No further variants were created, as requested.

Final state: Enforcing candidate `7812b288...` restored. Boot
stable, `boot_id=59810743-b3aa-4074-8b2e-31abb092fbda`,
`sys.boot_completed=1`, `getenforce=Enforcing`, `kernelsu` in
`/proc/modules`, port 4444 closed. No other file edited, no commit.

## Final round - SUCCESS (2026-11-24)

Final images (hash checked in HASHES.txt):

- `odm20_ksu_persist.img` = `bae7e9e3b8458c064385bc54fa3963b8d81f8dcf8bf1fa90448577a3d0c44e2b`
- `kernelsu-persist.ko`   = `297593726f34dc30062cddd6f5d2394a42975cc12b3b5a14752c1e2b7dc61240`
- `su-helper`             = `262f7ec8484f2812aa2aa3089f0f8d03996f709cc224a2dbade8510bd5d1dceb`
- diagnostic `odm20_ksu_avc2.img` = `f067bf6f27617f43808b6d238f5be2023a1375fc280d579616a057b197318b48`

Root cause fixed: `apply_kernelsu_rules()` was only called by the execve hook
of the second-stage `/init`, which had already passed by the time the module
is inserted at `sys.boot_completed`. Without it, `track_throne()` ran in
`vendor_init` and got EACCES on `/data/system/packages.list`. Now the rules
are applied in `kernelsu_init()` itself, and `compat_sys_execve` is also
hooked (all userspace is 32-bit).

Flash (fb_raw.py): `getvar product` -> `OKAYaquaman`, `download` -> OKAY,
`store write odm 10200000 0 1400000` -> OKAY, `reboot` -> OKAY.
Stable boot, `sys.boot_completed=1`, no loop.

Objective commands and outputs on the final image:

```
adb shell getenforce                       -> Enforcing
adb shell grep -i kernelsu /proc/modules   -> kernelsu 106496 0 - Live
adb shell su -c id                         -> uid=0(root) gid=0(root) groups=0(root) context=u:r:su:s0
adb shell grep -i 115c /proc/net/tcp*      -> (empty / port closed)
adb shell getprop init.svc.rootsh          -> (empty; service removed)
```

Stability monitor (15 s between samples, 14 samples): uptime from 53 s to
251 s, `boot=1`, `mod=1`, `su=uid=0(root)` in all. No `Oops`, `Kernel panic`,
`EXT4-fs error` or `EXT4-fs warning` in dmesg. The only `Call trace` is the
stock trace of `handle_vmap_fault`/`copy_mount_options` at 0.19 s, before the
module.

Manager v1.1.1 (screenshot): "Running", "Version: 12851", "Superuser 1",
"Manager version v1.1.1 (12851)", no missing-signature message.
dmesg: `Crowning manager: com.rifsxd.ksunext(uid=10069)` and
`ksu_hook: compat_sys_execve at ffffff8009221af0`.

Grant/revoke via UI (Shell user profile, uid 2000):

```
toggle OFF -> su -c id: rc=127 (denied)
toggle ON  -> su -c id: uid=0(root) ... context=u:r:su:s0
reboot     -> su -c id: uid=0(root) ... context=u:r:su:s0
toggle OFF -> su -c id: rc=127 (denied)
toggle ON  -> su -c id: uid=0(root) ... context=u:r:su:s0
```

`.allowlist` (784 bytes, sha `473c02f2be150da95b35c8741955cbd30908f7226a37f1b514eac39712d16ac7`):

```
3x /odm/ksud32 allowlist load -> 3x "allowlist: applied 1 validated records",
                                  sha unchanged, no .tmp left behind
truncate -s 100 .allowlist
/odm/ksud32 allowlist load     -> "Error: allowlist truncated record: 100 bytes", rc=1
su -c id                       -> uid=0(root) (previous state preserved)
restore from backup + reboot    -> "allowlist: applied 1 validated records" at boot,
                                  original sha, grant survived
```

Final state: image `bae7e9e3...` written to ODM, Enforcing, port 4444 closed,
grant active, recovery intact. No commit.

Additional test on the final image: `insmod /data/local/tmp/ksu_ext4_noop.ko`
(sha in HASHES.txt) -> `rc=0`, module Live, dmesg
`ksu_ext4_noop: loaded, no sysfs or ext4 changes`, no `EXT4-fs warning`.
`rmmod` right after, module unloaded.
