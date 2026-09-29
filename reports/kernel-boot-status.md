# kernel-boot-status — milestones (updated)

- M0 (fastboot boot delivers payload): REVOKED. 4 formats (raw, ANDROID!+stub,
  ANDROID!+stub 15×, 26 MB kernel, FIT+DTB) return in identical 15-21 s windows.
  Bytes delivered via `fastboot boot` do not enter the boot path on this build
  (see `fastboot-boot-verdict.md`). The earlier conclusion ("stub executed")
  was an artifact of reject-reset behavior.
- M1 (our payload executes): FAILED with evidence (M1b: 15× delay, zero shift).
- M2 (observable controlled reset): FAILED alongside M1 (M2 returned in 19 s; real
  kernel did not start — impossible in that window given panic-timeout 5).
- M3 (persistent/read-only signature): candidates: `ro.boot.bootreason`,
  `/sys/fs/pstore` (currently empty?), stock DTB ramoops. Pending M1.
- M4 (stock init/userspace): blocked on M1. Technical prerequisite mapped:
  kernel must accept U-Boot DTB + mount eMMC + match vermagic of the 28 .ko
  modules (`vendor-module-compat.md`).
- M5/M6: out of reach until M1. No KernelSU/APatch prior to this.

## first known failure (in build environment, not on device)

None on device (device untouched this session). In build: McMCCRU tip
had 2 drivers failing compilation/linking (`VDEC_VP9`, `VIDEOSYNC`), worked around in
local `.config` toward aquaman. Details in `kernel-build-env.md`.

## next smallest experiment

M1a: `adb reboot bootloader` → `oem printenv loadaddr` → `fastboot boot
m1_boot.img` timed → `adb wait-for-device` + bootreason. 1 reboot,
RAM-only, reversible by design. Fallback: if hung without returning, physical
power cycle.
