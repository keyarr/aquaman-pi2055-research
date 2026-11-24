# TOCTOU delivery to the kernel - consolidated copy of /tmp (2026-11-19)

Original files: /tmp/exec-toctou-2026-11-19.md,
/tmp/exec-toctou-v2-2026-11-19.md, /tmp/diag-toctou-2026-11-19.md.
Full copy, unedited, preserved here because the evidence that the hook
0x37e265fc delivers bytes to the decompressed kernel existed only outside the repo.

---

# TOCTOU execution - 2026-11-19

## Result

REFUTED. The hook at 0x37e265fc ran (bootm dropped USB, boot_id changed, Android came up), but the patch did not produce uid=0. `su` failed with `setgid: Operation not permitted`.

## Identification

- serial: 26919800005844922
- fingerprint: Xiaomi/aquaman/aquaman:9/PI/2055:user/release-keys
- BOOT_ID before: b28f1912-76c9-4d82-84ad-86cfec896d8b
- BOOT_ID after bootm: 67be423d-d790-4523-becd-e07c22c8839c
- BOOT_ID after cleanup reboot: 796dde78-aa8a-4424-9708-15057af91919
- kernel: Linux version 4.9.113 (jenkins@c5-mitv-cm-build06.bj) #1 SMP PREEMPT Tue Sep 6 12:53:43 CST 2022
- NDK: r28c (28.2.13676358), clang 19.0.1, aarch64-linux-android28

## Entry into optimus

1. `adb reboot fastboot` -> `fastboot devices`: 1234567890 Android Fastboot
2. `lsusb`: 18d1:0d02 Google Inc. (confirmed)
3. `fastboot oem update 5000` -> `FAILED (Status read failed (No such device))` (expected, not repeated)
4. `lsusb`: 1b8e:c003 Amlogic (t=1s), identify = 00 07 00 10 -> version 0.7 stage 16 (TPL/BL33-u-boot)
5. `adb devices` authorized, local uid 1000(erick), passwordless sudo available

## Baseline and writes

- oracle: false=b'failed:' true=b'success' (passed)
- 0x37e265fc stock: 80003fd6 (passed)
- 0x37800000 before: NOT COLLECTED (the script does not read the address before the download - deviation)
- `imgread kernel boot 0x1080000`: b'success'
- stub: /tmp/stub/kernel_patch.bin, 128 B, sha256 8929af8a90a55cf18ea26e33144b7bf4325c15fd016745b1d6e52d9628f9eb16 (checked)
- download 0x37800000: arm b'success', 1 chunk, readback identical to the stub (stub ok)
- patch 0x37e265fc: poke 8166e717, readback 8166e717 (hook patch ok)
- `dcache flush`: b'success'
- SMC sites 0x37e24cf0 / 0x37e24f90 untouched; image delivered to SMC = stock via imgread

## bootm and USB timeline

- `bootm 0x1080000`: no reply, exception `USBError(19, 'No such device (it may have been disconnected)')`
- usb_watch (/tmp/toctou_usb.log):
  - t=0.000 start 1b8e:c003 optimus/TPL/BL33 bcdDevice=0007 speed=480
  - t=5.239 OFF 1b8e:c003 / no Aquaman device on the bus / target up -> down
  - t=24.535 ON 2717:4e40 android bcdDevice=0223 speed=480 / target down -> up
- Android: sys.boot_completed=1, boot_id changed (67be423d...), boot took ~19s after the OFF

## Root verification

- `adb shell id`: uid=2000(shell) gid=2000(shell) ... context=u:r:shell:s0 (root did NOT come from adb)
- su installed: /data/local/tmp/su, -rwxr-xr-x 1 shell shell 2139168, ELF 64-bit ARM aarch64 statically linked (NDK r28c)
- `su -c id` stdout: (empty)
- `su -c id` stderr: `setgid: Operation not permitted`
- `su -c "grep -E ^Uid /proc/self/status"` stderr: `setgid: Operation not permitted`
- no `uid=0(root)` in any output

## Post-failure diagnostics

- ro.boot.selinux: enforcing
- ro.boot.verifiedbootstate: orange
- dmesg: `dmesg: klogctl: Operation not permitted` (denied)
- logcat -d -b all (tail 200): only normal Android services (BOOT_COMPLETED, GMS, WorkManager, aurora/wholphin/nuvio). No patch, kernel or capability lines. Nothing indicates capability/SELinux neutralization.

## Rollback

- No writes to flash/env/efuse. All writes were RAM-only (download 0x37800000 and poke 0x37e265fc).
- bootm itself already rebooted the device and discarded the RAM state.
- Additionally: `adb reboot`, boot_completed=1 in 14s, boot_id 796dde78..., `adb shell id` = uid=2000(shell). Clean state.
- I did not run erase, flash, saveenv, setenv or byte restoration.

## Deviations

1. USB permission: the first run of /tmp/exec_toctou.py failed in optimus.find() with `USBError: [Errno 13] Access denied (insufficient permissions)`. No writes occurred. Re-run with `sudo env PATH="$PATH" python3 /tmp/exec_toctou.py` (passwordless sudo, pyusb available for root). Second run completed.
2. 0x37800000 was not read before the download: the provided script does not include that read, so there is no baseline of the stub region.
3. Physical power cycle (unplug/replug cable) not performed: no physical access to the device. bootm already rebooted and discarded RAM; I complemented with `adb reboot`.
4. `file /tmp/su`: ELF 64-bit LSB executable, ARM aarch64, statically linked, for Android 28, built by NDK r28c, with debug_info, not stripped (as expected).
5. No edits in the repo. Scripts, logs and report in /tmp. No commit/push/rebase/amend.

---

# TOCTOU execution v2 - 2026-11-19

## Result

REFUTED. The hook at 0x37e265fc ran (bootm dropped USB, boot_id changed,
Android came up in ~20.5s after the OFF), but the v2 patch did not produce uid=0.
`su -c id` failed with `setgid: Operation not permitted`, the same result as
the v1 round. No uid=0(root) in any output.

## Identification

- serial: 26919800005844922
- fingerprint: Xiaomi/aquaman/aquaman:9/PI/2055:user/release-keys
- BOOT_ID before: c52ff260-d92c-47ee-8931-3ef4d106b403
- BOOT_ID after bootm: 608638fe-f5ea-47fa-879f-68a7317bcda6
- kernel: Linux version 4.9.113 (jenkins@c5-mitv-cm-build06.bj) (gcc version 6.3.1 20170109 (Linaro GCC 6.3-2017.02) ) #1 SMP PREEMPT Tue Sep 6 12:53:43 CST 2022
- ro.boot.selinux (before/after): enforcing / enforcing
- ro.boot.verifiedbootstate (after): orange

## Entry into optimus

1. `adb reboot fastboot` -> `fastboot devices`: 1234567890 Android Fastboot (18d1:0d02)
2. `fastboot oem update 5000` -> `FAILED (Status read failed (No such device))` (expected, not repeated)
3. `lsusb`: 1b8e:c003 Amlogic, Inc.
4. identify: raw `00 07 00 10`, version 0.7, stage 16 (TPL/BL33-u-boot), return 0
5. oracle: false=b'failed:' true=b'success' (passed)
6. USB access: optimus script run with `sudo env PATH="$PATH" python3` (pyusb requires root)

## Baseline and writes (RAM-only)

- hook @0x37e265fc before: `80003fd6` (stock, passed)
- stub region @0x37800000 before: 172 B, sha256 58f218aeb259309eeb545345a8f5c715987967b0ec724806d448394da578d0b0
- `imgread kernel boot 0x1080000`: b'success'
- stub: /tmp/stub/kernel_patch_v2.bin, 172 B (0xac), sha256 a0ed172252caaf9a7d33bb6d00d1e8fe9e88ab6424e2a917be35f4f0d0974285 (checked, matches expected)
- download 0x37800000: arm b'success', 1 chunk; readback of the 172 B identical to the stub, sha256 a0ed172252caaf9a7d33bb6d00d1e8fe9e88ab6424e2a917be35f4f0d0974285
- poke @0x37e265fc: `8166e717`; readback `8166e717` (passed)
- `dcache flush`: b'success'
- SMC sites 0x37e24cf0 / 0x37e24f90 untouched; image delivered to SMC = stock via imgread
- stamp verification (diag_patchverify.bin, 220 B): NOT performed in this round (OPTIONAL). Already validated in the previous round (/tmp/patchverify_result.json, "LANDEDOU": five sites written); avoided mixing the two stubs at 0x37800000.

## bootm and USB timeline

- `bootm 0x1080000`: no reply, exception `USBError(19, 'No such device (it may have been disconnected)')`, 4.777 s
- usb_watch (/tmp/toctou_v2_usb.log):
  - t=0.000  start 1b8e:c003 optimus/TPL/BL33 bcdDevice=0007 speed=480; target present: True
  - t=5.258  OFF 1b8e:c003 / no Aquaman device on the bus / target up -> down
  - t=25.737 ON 2717:4e40 android bcdDevice=0223 speed=480 / target down -> up
- USB DROPPED at bootm (OFF ~5.3s); Android ON ~20.5s later. sys.boot_completed=1.

## Root verification

- `adb shell id`: uid=2000(shell) gid=2000(shell) groups=2000(shell),1004(input),1007(log),1011(adb),1015(sdcard_rw),1028(sdcard_r),3001(net_bt_admin),3002(net_bt),3003(inet),3006(net_bw_stats),3009(readproc),3011(uhid) context=u:r:shell:s0
- static su: /tmp/su, push rc=0, chmod 755 rc=0, ELF 64-bit ARM aarch64 statically linked (NDK r28c)
- `su -c id` stdout: (empty)
- `su -c id` stderr: `setgid: Operation not permitted` (rc=1)
- `su -c "grep -E '^(Uid|CapEff)' /proc/self/status"` stdout: (empty), stderr: `setgid: Operation not permitted` (rc=1)
- Single success criterion (uid=0(root) in su output): NOT achieved.

## Post-failure diagnostics (step 10)

- ro.boot.selinux: enforcing
- /proc/version: Linux version 4.9.113 (jenkins@c5-mitv-cm-build06.bj) (gcc version 6.3.1 20170109 (Linaro GCC 6.3-2017.02) ) #1 SMP PREEMPT Tue Sep 6 12:53:43 CST 2022
- logcat -d -b all | tail -200: collected in /tmp/v2_run_result.json (field fail_diag.logcat_tail, 200 lines)
- No new addresses were tried in this round.

## Rollback

- No writes to flash/env/efuse. All writes were RAM-only (download 0x37800000 and poke 0x37e265fc).
- bootm itself rebooted the device and discarded the RAM state.
- I did not run erase, flash, saveenv, setenv or byte restoration. Nothing written to the eMMC.

## Deviations / limitations

1. Physical power cycle (unplug/replug cable) not performed: no physical access to the device. bootm already rebooted and discarded RAM; the hook baseline came back `80003fd6` (stock), confirming a clean state in the relevant region.
2. The v2 patch writes avd->allowed=w3, auditallow=0, auditdeny=0 before returning 0, fixing the cause attributed to v1. Even so the result was identical (setgid EPERM). This refutes the hypothesis that merely filling avd->allowed would unblock setgid on this target.
3. No edits in the repo. Scripts, logs and report in /tmp. No commit/push/rebase/amend.

## Evidence level

REFUTED. Hook executed, boot completed, SELinux remains enforcing and su did not obtain uid=0.

---

# TOCTOU diagnosis - 2026-11-19

Objective: find out why the patch at 0x13bbca8/0x13c5390/... did not reach the
running kernel. RAM-only, no kernel boot in this round.

## Entry and baseline

- entry: `adb reboot fastboot` -> fastboot 18d1:0d02 ->
  `fastboot oem update 5000` -> `FAILED (Status read failed (No such device))`
  (expected) -> 1b8e:c003 in ~1 s.
- identify: raw `00 07 00 10`, version 0.7, stage 16 (TPL/BL33-u-boot), rc=0.
- oracle: `false` -> `failed:`, `true` -> `success`.
- 0x37e265fc baseline: `80 00 3f d6` (`blr x4`), matches stock.
- 0x37800000 baseline (88 B): sha256
  `10eef285deef7a4b7c82b22aa53589b7833df29de3814649c772bbd5c832f365`.

## Steps performed

| item | result |
| --- | --- |
| imgread | `imgread kernel boot 0x1080000` -> `success` |
| stub | `/tmp/diag_dump.bin`, 88 B, sha256 `f16135e2145044e5529198df8cfb2f0a34bc5bc5df601947ca38570c8fbce271` (matches) |
| download | `download mem 0x37800000 normal 0x58` -> arm `success`, 1 chunk; readback of the 88 B identical to the file |
| patch readback | poke 4 B at 0x37e265fc with `81 66 e7 17`; readback `81 66 e7 17` (checked) |
| dcache | `dcache flush` -> `success` |
| bootm | `bootm 0x1080000` -> `failed:` at 3.162 s, WITH reply. USB did NOT drop. |
| scratch | MREAD 0x37900000, 0x210 B, 528 B saved in `/tmp/diag_scratch.bin`, sha256 `4d5e03063c5c1623d72f23c077dce77047d28d1222959d2a8944b968223488d4` |

Stub: saves x4 at 0x37900000, copies 0x80 B from 0x1080000 to 0x37900010,
copies 0x100 B from 0x13bbc00 to 0x37900100, branches to 0x37e26624 via
`br x10`. It did not enter the kernel.

## Interpretation of the scratch

- entry (x4) = `0x0000000037e21378`.
- calculated delta (literal rule) = entry - 0x1080000 = `0x36da1378`
  (920261496).
- header at 0x37900010..0x37900090: magic `ARMd` at +0x38 (0x37900048),
  text_offset at +0x08 = `0x01080000`. Decompressed Image present and intact
  at the expected address.
- window at 0x37900100..0x37900200 (0x13bbc00..0x13bbd00): signature
  `fd7bbda9fd030091` (`stp x29,x30,[sp,#-16]! ; mov x29,sp`) found at
  offset `0xa8` of the window, i.e. 0x379001a8. Corresponding physical address:
  0x13bbc00 + 0xa8 = `0x13bbca8`. A single occurrence in the window.

Context at 0x379001a8:
`fd7bbda9 fd030091 f35301a9 f55b02a9 f40300aa f303022a e0031eaa f50301aa`

## Load-bearing caveat about the delta

The rule "if entry != 0x1080000, add the delta to all addresses" assumes
that x4 is the kernel entry point. It is not. At the hook point (0x37e265fc,
`blr x4`), x4 points to `0x37e21378`, which is the OS dispatch/do_bootm_linux of
BL33 itself (slot of the table 0x37eb5658, documented in
reports/round55-fdt-identity-chain and reports/round57-fdt-final-identity). The
real kernel entry is loaded at 0x37e21284 from `[x19+0xe8]` and delivered to the
`eret` via ELR_EL2, not via x4.

Therefore the delta `0x36da1378` is arithmetically correct, but must not be
applied to the stub addresses. Two independent pieces of evidence rule out
kernel relocation in this session:

1. Image text_offset = 0x1080000 (no physical slide).
2. cap_capable appears exactly at 0x13bbca8, the same address that
   `kernel_patch.S` uses, without offset.

Conclusion: the patch target addresses are correct. The cause of the previous failure
is not a load slide/KASLR. The production stub (`kernel_patch.bin`, 128 B)
would write `00 00 80 d2 c0 03 5f d6` (`mov w0,#0 ; ret`) at 0x13bbca8,
0x13c5390, 0x13c5488, 0x13c5610 and 0x13c5028, followed by `blr x4` and
`br 0x37e26600`. In this round the diagnostic stub only read: the window shows the
stock prologue, as expected before any patch.

## Final state

- No writes to flash, env, eMMC, efuse or BootROM. Nothing was written to
  persistent disk.
- Bytes not manually restored, as requested. The hook at 0x37e265fc
  remains `81 66 e7 17` and the stub remains at 0x37800000 until the next
  reboot.
- Post-read power cycle NOT performed: no relay/uhubctl/physical access to the
  cable on this host. No reboot was given before or after reading the
  scratch. Pending, if physical access is available.
- Repo not edited. Artifacts only in /tmp.
