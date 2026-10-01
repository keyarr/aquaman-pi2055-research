# magisk boot test — signed kernel + patched ramdisk rejected (2026-10-01)

Date: 2026-10-01. Device: Xiaomi Mi TV Stick 1080p (aquaman, S805Y/GXL,
Android 9 PI.2055, 4.9.113). Bootloader: `unlocked: yes`, `secure: no`
(U-Boot env only, BL31 still secure-fused). Method: RAM-only
`fastboot boot`, no flash, no saveenv, no persist.

Image: `magisk_patched-30700_X0fyo.img` (16384 KB, sent as `boot.img`).

## 1. Image layout (offline, verified this round)

```text
outer ANDROID! v0, page 2048, kernel_addr 0x1080000
  stock:   kernel 9801728, ramdisk 0,      second 61440
  magisk:  kernel 9801728, ramdisk 376988, second 61440
  kernel sha256 both: 3ebb0b282294c7bebe7626b430467d58a8bbed6e1e26688245b4316ce18f22cf
  ramdisk magisk: valid SVR4 cpio, .backup, init, overlay.d/sbin/magisk.xz + stub.xz
inner AMLSECU! ver 0x905, nblk 3, ts 2022090612544443 (identical both)
  blk0 off 0x800 raw 0x9589d1 tot 0x959000 (kernel, encrypted)
  blk1 off 0x0 raw 0x0 tot 0x0 (empty both)
  blk2 off 0x959800 raw 0xe820 tot 0xf000 (dtb)
```

Patch is structurally sound: kernel byte-identical, ramdisk is a real
Magisk overlay. Outer `ramdisk_size 0 -> 376988` is the only material
change; inner header untouched.

## 2. Hardware run (single boot, timed)

```text
T0 send:  fastboot boot magisk_patched-30700_X0fyo.img
  Sending 'boot.img' (16384 KB) OKAY [0.717s], Booting OKAY [0.000s]
  Total 0.745s
USB (tools/usb_watch.py, out/logs/magisk_boot_test.log):
  t=0.000  18d1:0d02 fastboot BL33 present
  t=4.260  18d1:0d02 OFF, no Aquaman device on bus
  t=21.901 2717:4e40 android ON (bcdDevice=0223)
ADB poll (5s grain):
  +5s/+10s: no fastboot, no adb
  +15s: adb 26919800005844922 device (first appearance)
  +20s..+90s: adb stable, fastboot absent
Post-boot (adb, ~1 min uptime):
  sys.boot.reason = reboot,fareboot (identical to stock + M1/M2 baseline)
  ro.build.fingerprint = Xiaomi/aquaman/aquaman:9/PI/2055:user/release-keys
  ls /sbin/su, /sbin/magisk, /system/bin/su: No such file
  which su / su -c id: not found
  logcat -d | grep -i magisk/avb/verity/Sig: empty
  getprop init.svc.magiskd: empty
```

## 3. Verdict

```text
REJECTED. No bytes executed.
```

21.9s bus return + `reboot,fareboot` matches the M1a/CTRL/M1b/M2
rejection band (15-21s), not a Magisk boot (30s+ first boot or daemon
traces). Absence of `/sbin/su`, empty logcat, empty `init.svc.magiskd`
confirm silent fallback to stock Android.

Scope note: kernel-identical was not sufficient. BL31 `DEC_ALL` over the
24 MiB window covers bytes beyond blk0, so changing outer ramdisk alone
breaks the check before `do_bootm` parses format. `fastboot boot` with
any modified ramdisk is dead on this build regardless of kernel sig.

## 4. What not to repeat

Do not re-run `fastboot boot` on ramdisk-modified AMLSECU images: outcome
is invariant (rejection timing + fareboot + no su). Next step for this
vector is not another boot but vbmeta/verity state from inside running
Android, or abandon fastboot path for disclosure + GhostLock.
