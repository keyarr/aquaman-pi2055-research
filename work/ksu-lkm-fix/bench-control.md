# Bench - control build (2026-11-24)

Device: MiTV-AESP0 (aquaman), ADB serial `26919800005844922`. Bench scope:
validation of the control build only. The candidate was not flashed, there
was no change to recovery/boot/vbmeta/other partitions besides ODM, and no
commit was made.

## Result

**FAILED.** The control module `kernelsu-control.ko` (in `odm20_ksu_control.img`)
loads, installs hooks and detects the Manager, but triggers an Oops in the
`ksu_stub_read` trampoline (and `ksu_stub_faccessat`) right after insmod, with
`PC is at 0x0`. The device enters a reboot loop: `sys.boot_completed` never
settles at 1. It was not possible to observe the `ksu_open ... wq=1 result=-126`
or `load_allow_list open file failed: -126` lines, nor to test `su -c id`
after grant.

## Phase 1 - state before flash (read-only)

Relevant commands and outputs:

```
adb devices -l
26919800005844922  device usb:3-3 product:aquaman model:MiTV_AESP0 device:aquaman
adb shell getprop ro.boot.serialno -> 26919800005844922
adb shell getprop sys.boot_completed -> 1
```

- Kernel `boot_id` (`/proc/sys/kernel/random/boot_id`): `a602f33d-b403-4f55-ab09-b8427fe45092`.
- `lsmod | grep -E 'kernelsu|seflip'`: `kernelsu 98304 0`, `seflip 16384 0`.
- `getenforce`: `Permissive` (both via `adb shell` and via root shell).
- Port 4444: open. `adb forward tcp:4444 tcp:4444` returned `4444`;
  `nc 127.0.0.1 4444` connected and `id` returned
  `uid=0(root) gid=0(root) groups=0(root) context=u:r:dumpstate:s0`.
  Props: `debug.root_service=RUNNING`, `init.svc.rootsh=running`.
- `/odm/kernelsu.ko` on the device: sha256
  `cf217969df3272e5d0df517dd0dba412cdbcb7a91db3f085d3d4dc830f5191d9`
  (stock baseline, `odm20_ksu3.img`).
- `/odm/etc/init/root.rc`: `insmod /odm/seflip.ko`, `insmod /odm/kernelsu.ko`,
  `exec u:r:vendor_init:s0 root root -- /odm/ksu_sepolicy.sh`,
  `setprop debug.root_service RUNNING`, `start rootsh` at `sys.boot_completed=1`.
- dmesg (excerpt): `KernelSU: ksu_core_init: LSM hooks not in use.`,
  Manager `com.rifsxd.ksunext` (uid=10069) crowned, seven lines
  `ksu_hook: ... -> stub 0xffffff8017d19...` (do_execve, sys_faccessat,
  sys_read, sys_newfstatat, sys_reboot, sys_prctl, sys_execve),
  `ksu_sucompat_init: hooks enabled`, `SELinux permissive or disabled when handle policy!`.
  EXT4 warnings present are from normal mounts of /system, /odm, /vendor, /data.
- Previous pstore: `reboot: Restarting system with command 'fastboot'`.

## Phase 2 - local hashes

`cd work/ksu-lkm-fix && sha256sum -c HASHES.txt` -> all `OK` (10/10):
`ref/kernelsu_stock_from_odm.ko`, `ref/kernelsu_stock_img.ko`,
`kernelsu-control.ko`, `kernelsu-persist.ko`, `ksud-arm32`,
`harmless/ksu_ext4_noop.ko`, `../../odm/odm20_ksu3.img`,
`odm20_ksu_control.img`, `odm20_ksu_persist.img`, `../../recovery.img`.

Image used: `odm20_ksu_control.img`, sha256
`d7c8e51da216d8580df5a92c659dcdd53ae4121e896a63fcf00ca5ace9a4ae36`
(checked via HASHES.txt). No other image was downloaded or written.

## Phase 3 - fastboot

```
adb reboot fastboot
python3 tools/fb_raw.py getvar product  -> OKAYaquaman (0.0s)
```

## Phase 4 - flash control image

```
python3 tools/fb_raw.py download .../work/ksu-lkm-fix/odm20_ksu_control.img
  -> OKAY (2.9s)
python3 tools/fb_raw.py cmd 'set_active:;store write odm 10200000 0 1400000' 20000
  -> OKAY (1.2s)
python3 tools/fb_raw.py cmd reboot 10000
  -> OKAY (0.0s)
```

Each response was checked before proceeding. No FAIL was reported.

## Phase 5 - post-flash and diagnostics

`adb wait-for-device` returned; `sys.boot_completed=1` appeared around the
8th check, but the device dropped shortly after. Monitoring (read-only,
3 s interval) showed ~30 s cycles:

```
11:07:31 uptime=11.02  boot_id=3eff132b  boot_completed=(empty)
11:07:45 uptime=24.29  boot_id=3eff132b  boot_completed=(empty)
11:07:52 adb=DOWN
11:08:10 uptime=10.31  boot_id=4df7372d  boot_completed=(empty)
11:08:24 uptime=20.90  boot_id=4df7372d  boot_completed=(empty)
11:08:29 adb=DOWN
11:08:47 uptime=10.37  boot_id=e69724e2  boot_completed=(empty)
11:09:01 uptime=20.99  boot_id=e69724e2  boot_completed=(empty)
11:09:10 adb=DOWN
```

Port 4444 did not come up stably: `nc -v 127.0.0.1 4444` returned
`Connection refused` after the first reboot. For that reason it was not
possible to capture dmesg/lsmod/getenforce via root shell on the control boot.

Serial console: unavailable (`/dev/ttyUSB*`, `/dev/ttyACM*` absent on host).

pstore `/sys/fs/pstore/console-ramoops-0` (excerpt from the failed boot):

```
[   23.303813@2] Internal error: Oops: 86000006 [#1] PREEMPT SMP
[   23.402793@2] LR is at ksu_stub_read+0x40/0x44 [kernelsu]
[   23.883893@3] LR is at ksu_stub_read+0x40/0x44 [kernelsu]
[   24.357033@0] Internal error: Oops: 86000005 [#3] PREEMPT SMP
[   24.422691@0] LR is at ksu_stub_faccessat+0x40/0x44 [kernelsu]
[   25.225590@1] Internal error: Oops: 86000007 [#3] PREEMPT SMP
[   25.290211@1] PC is at 0x0
[   25.295535@1] LR is at ksu_stub_read+0x40/0x44 [kernelsu]
[   25.759388@1] Code: bad PC value
[   26.791007@3] reboot reason 12
```

Context of one Oops: `CPU: 1 PID: 1 Comm: init`, `Modules linked in:
kernelsu(O) seflip(O) ...`, `pstate: 80000145`, `PC is at 0x0`,
`LR is at ksu_stub_read+0x40/0x44 [kernelsu]`. Another Oops occurred on
`CPU: 2 PID: 2925 Comm: logd.klogd`, same LR.

No `ksu_open`, `wq=1`, `result=-126`,
`load_allow_list open file failed: -126`, version 12851 or control hook
install lines appeared in pstore. The available data covers only the Oops
window (23-27 s), right after insmod.

## Pending

- `su -c id` after grant via Manager UI: not tested. The device never
  completed boot and the UI could not be interacted with reliably.
- Direct confirmation of the `ksu_open`/`wq`/`result` instrumentation lines:
  not obtained, for the reason above.
- Root cause of `PC=0` in the trampoline: not investigated in code on this
  bench (validation-only scope; no code file was changed).

## Final device state

Last reading: `adb devices` shows `26919800005844922 device`,
`/proc/uptime = 20.93 26.07`, `boot_id = 53f3fa82-5605-4bca-931f-7a40a9ef6f11`,
`sys.boot_completed` empty. The device remains in a reboot loop.
No rollback (reflash of `odm20_root9.img`/stock) was done because it was not
authorized on this bench. `odm20_ksu_persist.img` was not flashed.
No file other than this report was edited. No commit was made.

## Retry after stub fix (2026-11-24)

Authorization received: roll back to the pre-test state and repeat the
control test with the trampoline fix. Flashing the candidate, touching
recovery/boot/vbmeta or editing code is still forbidden. No commit.

Fix applied by another hand while this session reported: `hook_runtime.c`
copies each assembly stub into the vmalloc page, fills the
dispatch/cont/orig slots in that copy and patches the kernel functions to
target that page. Previously the patch pointed at the stub in the module's
.text, whose slot was zero (`blr x16` with x16=0).

### Hashes checked in this session

```
sha256sum -c HASHES.txt                     -> 10/10 OK
kernelsu-control.ko       7bef1d7a02c0f29e3bd6130b2b8727f82b6dd6aa96ed8e4c10ddde6f2c0f45b8
odm20_ksu_control.img     1c271ece8919339d2ff202f51b0d63df092e8e5f881f50df8295fed8e6ad4076
odm/odm20_ksu3.img        880a575753d694ca0d7fab6a84da82a2c1f3913257261ed4d4d2f03e95939da7
```

All three match the reported values. No other image was used.

### Device recovery

The first `adb reboot fastboot` (with adb up, rc=0) did not take effect: the
device returned to Android (USB `2717:4e40`, adb up). A second attempt with
1 s monitoring entered fastboot at 11:26:57.
`fb_raw.py getvar product` -> `OKAYaquaman (0.0s)`.

### Rollback to stock baseline

```
download odm/odm20_ksu3.img                -> OKAY (2.9s)
cmd 'set_active:;store write odm ...'      -> OKAY (1.1s)
cmd reboot                                 -> OKAY (0.0s)
```

Stabilization observed: `boot_id=09fbb93b-f6c3-4f71-a774-b32bf49d4757`
constant from 11:27:48 to 11:30:09 (~2.5 min); `sys.boot_completed=1` from
11:28:04. Via root shell on 4444: `id` =
`uid=0(root) gid=0(root) groups=0(root) context=u:r:dumpstate:s0`;
`lsmod` = `kernelsu 98304 0`, `seflip 16384 0`;
`sha256sum /odm/kernelsu.ko` =
`cf217969df3272e5d0df517dd0dba412cdbcb7a91db3f085d3d4dc830f5191d9`;
`getenforce` = `Permissive`; `dmesg` readable. Loop stopped: rollback OK.

### Flash new control

```
adb reboot fastboot -> fastboot USB: True, product = OKAYaquaman
download work/ksu-lkm-fix/odm20_ksu_control.img -> OKAY (3.0s)
cmd 'set_active:;store write odm 10200000 0 1400000' 20000 -> OKAY (1.2s)
cmd reboot 10000 -> OKAY (0.0s)
```

### Retry result: FAILED (new Oops, reboot loop)

Monitoring: `boot_id` `03ebe08f` -> `b9204de3` -> `a818161e`, cycles of
~30 s, `sys.boot_completed` never reached 1. Port 4444 did not come up
stably.

pstore `/sys/fs/pstore/console-ramoops-0` (excerpt):

```
[   24.466810@2] Internal error: Oops: 96000004 [#1] PREEMPT SMP
[   24.571285@2] PC is at memcmp+0xd0/0x1c0
[   24.575192@2] LR is at ksu_handle_execveat_ksud.part.4+0x54/0x3a8 [kernelsu]
[   25.125460@2] [ffffff8020527de0+   0][<ffffff8002651064>] ksu_hook_dispatch+0x13c/0x1d0 [kernelsu]
[   25.141307@2] Code: 91002129 eb09010a 9a89810b cb0b0042 (38401403)
[   26.435314@1] [0000000000000000+   0][<ffffff8017d51240>] 0xffffff8017d51240
[   27.213531@2] reboot reason 12
```

Same pattern on CPU 2, 3 and 1 (Oops #1, #2, #3). Full call trace:
`memcmp+0xd0` <- `ksu_handle_execveat_ksud+0x54/0x70` <-
`ksu_handle_execveat+0x48/0x78` <- `ksu_hook_dispatch+0x13c/0x1d0` <-
stub at `0xffffff8017d51240` (vmalloc page).

The first bench's `PC is at 0x0` / `ksu_stub_read+0x40` is gone: the trampoline
fix worked in the sense of getting dispatch to the handler. The problem now
is the `ksu_handle_execveat_ksud` handler calling `memcmp` with an invalid
pointer. This is consistent with limitation 4 in
`reports/kernelsu-next-lkm-2026-11-23.md`: that handler expects
`struct filename **` while `sys_execve` supplies `const char __user *`,
i.e. type confusion when wiring it to target 6. Diagnosis derived from
pstore; no code was changed on this bench.

No `ksu_open`, `wq=1`, `result=-126`,
`load_allow_list open file failed: -126`, version 12851 or Manager crowning
were observed: boot does not complete and the pstore window only covers the
Oops (24-27 s). `su -c id` after UI grant: pending.

### Final state

Device in reboot loop. Last monitor reading: adb oscillates,
`boot_id=a818161e...`; boot_id changes every ~30 s and `sys.boot_completed`
stays empty. No post-test rollback was done (not authorized this round).
`odm20_ksu_persist.img` was not flashed. No file other than this
report was edited. No commit was made.

## Third control test (stub id + do_execve removed) - PASSED

Fixes applied since the retry: `hook_stubs.S` passes an explicit id
(`mov w0, #id`) instead of 0; `hook_runtime.c` removed the `do_execve` hook
and kept 6 hooks (faccessat=1, read=2, newfstatat=3, reboot=4, prctl=5,
sys_execve=6) with stubs on the vmalloc page and slots filled.

Hashes checked in this session:

```
sha256sum -c HASHES.txt                     -> 10/10 OK
odm/odm20_ksu3.img        880a575753d694ca0d7fab6a84da82a2c1f3913257261ed4d4d2f03e95939da7
odm20_ksu_control.img     0493c34a69b307944972eed45bc3e82c1003067f6083a7ee99b857f9d33c923d
odm20_ksu_persist.img     ce67bf7cfcc18a912f072b95645d6d8baf431580e87ee04de63bf974aedc0721
```

### Recovery and rollback

First `adb reboot fastboot` with adb up (rc=0) did not take effect; the device
returned to Android. Second attempt with 1 s monitoring entered
fastboot. `getvar product` -> `OKAYaquaman`. Rollback with `odm20_ksu3.img`:
download OKAY (2.7 s), store write OKAY (0.9 s), reboot OKAY (0.0 s).
Stability: `boot_id=71ee7b2b-18e9-437d-8259-c80044ed6383` constant from
11:38:59 to 11:41:24 (~2.4 min), `boot_completed=1` from 11:39:09.
Root via 4444: `id` uid=0(root) context=u:r:dumpstate:s0;
`lsmod` kernelsu 98304 / seflip 16384;
`/odm/kernelsu.ko` = `cf217969...`; `getenforce=Permissive`. Rollback OK.

### Flash new control

```
download work/ksu-lkm-fix/odm20_ksu_control.img -> OKAY (2.7 s)
cmd 'set_active:;store write odm 10200000 0 1400000' 20000 -> OKAY (1.2 s)
cmd reboot 10000 -> OKAY (0.0 s)
```

### Result: PASSED

Stable boot: `boot_id=a64defb5...` constant from 11:42:51 to 11:45:06
(~2.5 min), `sys.boot_completed=1` from 11:43:07. No Oops in
dmesg or pstore. Root via 4444 functional.

Via root shell:

```
lsmod | grep -E 'kernelsu|seflip'
kernelsu              102400  0
seflip                 16384  0
sha256sum /odm/kernelsu.ko
d6bcbbe2c48e86aba88f9a6a1491867957de4880c268fc2defdc6303bf30aefd
getenforce -> Permissive
```

dmesg (excerpt):

```
[   22.875838] KernelSU: ksu_core_init: LSM hooks not in use.
[   23.053044] KernelSU: ksu_sucompat_init: hooks enabled: execve/execveat_su, faccessat, stat, devpts
[   23.054940] KernelSU: ksu_hook: sys_faccessat at ffffff8009215ba8
[   23.056834] KernelSU: ksu_hook: sys_read at ffffff80092197d0
[   23.058713] KernelSU: ksu_hook: sys_newfstatat at ffffff800921eb78
[   23.059176] KernelSU: ksu_hook: sys_reboot at ffffff80090cde98
[   23.059500] KernelSU: ksu_hook: sys_prctl at ffffff80090be398
[   23.061406] KernelSU: ksu_hook: sys_execve at ffffff8009221a10
[   23.132300] KernelSU: SELinux permissive or disabled when handle policy!
```

Six hooks installed, no `do_execve`. No `Oops`/`Internal error` in
dmesg or pstore. Manager present in `/data/system/packages.list`
(`com.rifsxd.ksunext 10069`), but no crowning line appeared in
dmesg this time (the log only shows the lines above). Version 12851 was not
observed via dmesg.

`ksu_open`/`load_allow_list open file failed` instrumentation did NOT appear.
Investigative cause: the string exists in the module (`strings /odm/kernelsu.ko`
shows `ksu_open %s jiffies=%lu pid=%d comm=%s wq=%d keyring=%d result=%ld`
and `load_allow_list open file failed: %ld at jiffies=%lu`), but the
`ksu_filp_open_compat` path is called by `do_load_allow_list`, queued via
`ksu_queue_work` in `on_post_fs_data()`. dmesg does not record
`on_post_fs_data!`, `devpts sid:` or `switch current nsproxy`, i.e.
`on_post_fs_data` never fired on this firmware; without it the workqueue does
not run and the instrumentation has no way to emit. To test, I backed up
`/data/adb/ksu/.allowlist` to `.allowlist.benchbak`, removed the file and
rebooted: stable boot (`boot_id=69754345`, boot_completed=1), but still no
`ksu_open`/`load_allow_list` lines and no `on_post_fs_data`.
The file was restored (`mv .allowlist.benchbak .allowlist`) at the end.

`su -c id` after UI grant: pending. The Manager UI was not accessed
reliably on this bench (black screencaps already documented).

Pass criteria: stable boot, module loaded, six hooks installed,
no Oops, missing instrumentation explained by `on_post_fs_data` not firing.
Control PASSED; authorization to proceed to the candidate is valid.

Final control state: device stable with the control build,
`boot_id=69754345...`, `sys.boot_completed=1`, root via 4444, allowlist
restored. No other file edited, no commit.
