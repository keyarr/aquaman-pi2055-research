# R1 kexec - fire plan compat32 + pivot_root (preparation only, 2026-11-27)

Status: PREPARATION ONLY. I executed nothing on the device during this
preparation. There was no fire, push, insmod with fire=1, flash, USB DL,
tracked-file write, report edit, commit or power-cycle. Every command below is a
text proposal. I have not run any push, insmod (including crumb/sentinel ones)
or fire.

Goal: two discriminating fires, one per hypothesis, with the same clean Image
and module as always. Fire A tests whether EL0 compat works. Fire B tests
whether the mount/chroot path (rather than the compat tables) explains the real
init's SIGBUS.

## Verified artifacts and hashes

| Artifact (host) | sha256 | bytes | State on device |
| --- | --- | --- | --- |
| `out/r1-device/Image.clean` | `6c30b16ee7bdc99d62c08c86ef5c2212b736e7e6dab7bfaa1b1033e86e8ca045` | 27.308.544 | `/data/local/tmp/r1/Image` already matches |
| `out/r1-device/r1_kexec.ko.936aa4b7` | `936aa4b7d0ac987dcb6104f726c2075b4e428612e2c49e90497a0bbf80bd0eae` | 313.520 | `/data/local/tmp/r1/r1_kexec.ko` already matches |
| `work/r1-kexec/aquaman-r1-initrd-console.dtb` | `733d20f53bf5b4b18781633a9b7cfc360666c43f6c372b933775c39af940e41c` | 60.053 | already matches (the `aquaman-r1.dtb` name on the device has the same hash) |
| `work/r1-kexec/android-probe/initrd-compat32.cpio.gz` | `c15eeb16209d7b6aa78086f47b495d359a376dc901fdb014bbae68e5c17e9e14` | 456 | not staged; needs push |
| `work/r1-kexec/android-probe/initrd-pivot2.cpio.gz` | `630027e8b9b052dbb97420c743bbb754d78117fa545c33c75b4e71092c6bf265` | 1.156 | not staged; needs push |

Do not use: `Image-notrace` or any instrumented Image, module `202cbd51...`,
`initrd-pivot.cpio.gz` (`efe959b6...`, old version) or `initrd.cpio.gz`
(`c12eeb52...`) staged on the device. The file named `Image.clean` on the device
has `09e0016f...` (old) and is not the Image for these fires; always use
`/data/local/tmp/r1/Image`.

Content checked on the host:

- `initrd-compat32.cpio.gz`: a single `init` member, mode 0755, 33.240 B, sha256
  `7544123e4cb6f0b8231cc7ebbfea0e410f122e876d10eb01553d078bb4d2ecc0`.
  Static ELF32 ARM EABI5, entry `0x8000`, one RWE PT_LOAD at `0x8000`
  (filesz/memsz `0x65`). Code: `write(1,"R1_COMPAT32_EL0_A7C3F19D\n",25)`,
  `reboot(0xfee1dead,0x28121969,0x01234567)` and `exit(42)`. The marker sits in
  the file at `0x804c`; a write to `/dev/console` does not reach printk, so do
  not expect the string in pstore. Oracles: `exitcode=0x0000002a00`, or a clean
  reboot back to stock if the reboot syscall wins first. Current `compat32.S`
  produces a different binary (`R1_EVIDENCE_5A31C0DE`): do not recompile this
  initrd.
- `initrd-pivot2.cpio.gz`: a single `init` member, mode 0755, 67.792 B, sha256
  `2750261367935c9d80f56a9a09c5160d1f21c7d43e241b9ef3f35717ce300f13`.
  Static ELF64 AArch64, entry `0x400000`, one R E PT_LOAD (offset `0x10000`,
  filesz/memsz `0x20c`). Strings and flow checked against `pivot-root.S`:
  `mkdirat("/root")`, nanosleep 4 s, `mknodat` of `mmcblk0p18` (179:18),
  `mount("/dev/block/dm-0")` with fallback to `mmcblk0p18`, `chdir("/root")`,
  `pivot_root(".",".")`, `umount2(".",MNT_DETACH)`, `chdir("/")`,
  `execve("/init")`. No clone, wait4, kill or reboot: it has no watchdog of its
  own.

Device I verified on 2026-11-27 (read-only): serial `26919800005844922`,
`uname -r 4.9.113`, `getenforce Enforcing`, `sys.boot_completed=1`,
`/sys/fs/pstore/` empty, `dmesg` via `/odm/bin/su` readable. The three
already-staged artifacts match the hashes above.

## Pre-flight (read-only)

```
adb devices -l
adb -s 26919800005844922 shell '/odm/bin/su -c "getenforce; getprop sys.boot_completed; uname -a; id"'
adb -s 26919800005844922 shell '/odm/bin/su -c "cd /data/local/tmp/r1 && ls -la Image r1_kexec.ko aquaman-r1-initrd-console.dtb initrd-compat32.cpio.gz initrd-pivot2.cpio.gz 2>&1; sha256sum Image r1_kexec.ko aquaman-r1-initrd-console.dtb 2>&1"'
adb -s 26919800005844922 shell '/odm/bin/su -c "ls -la /sys/fs/pstore/ 2>&1"'
adb -s 26919800005844922 shell '/odm/bin/su -c "lsmod | grep r1_kexec || echo no-r1-module-loaded"'
sha256sum out/r1-device/Image.clean out/r1-device/r1_kexec.ko.936aa4b7 work/r1-kexec/aquaman-r1-initrd-console.dtb work/r1-kexec/android-probe/initrd-compat32.cpio.gz work/r1-kexec/android-probe/initrd-pivot2.cpio.gz
```

Conditions to proceed: serial present, `boot_completed=1`, local hashes equal to
the table, no r1_kexec module loaded, pstore empty at the start. If the serial is
missing or pstore is not empty, stop and report.

## Proposed push (not executed)

Only the two initrds need to be pushed. The other three commands are listed for
reproducibility and should only be used if the pre-flight shows a divergence;
overwriting `Image` on the device is a state change I have not made.

```
adb -s 26919800005844922 push work/r1-kexec/android-probe/initrd-compat32.cpio.gz /data/local/tmp/r1/initrd-compat32.cpio.gz
adb -s 26919800005844922 push work/r1-kexec/android-probe/initrd-pivot2.cpio.gz /data/local/tmp/r1/initrd-pivot2.cpio.gz
# optional, only if pre-flight diverges:
adb -s 26919800005844922 push out/r1-device/Image.clean /data/local/tmp/r1/Image
adb -s 26919800005844922 push out/r1-device/r1_kexec.ko.936aa4b7 /data/local/tmp/r1/r1_kexec.ko
adb -s 26919800005844922 push work/r1-kexec/aquaman-r1-initrd-console.dtb /data/local/tmp/r1/aquaman-r1-initrd-console.dtb
adb -s 26919800005844922 shell '/odm/bin/su -c "cd /data/local/tmp/r1 && sha256sum Image r1_kexec.ko aquaman-r1-initrd-console.dtb initrd-compat32.cpio.gz initrd-pivot2.cpio.gz"'
```

I executed none of this. No push touches the boot chain.

## Sentinels (insmod not executed)

Single slot per round at `0x075fb000`, inside the retained ramoops region:

- Fire A (compat32): `0x52444331` = 1380205361.
- Fire B (pivot): `0x52444332` = 1380205362.

Write and confirmation before each fire (proposed, not executed):

```
adb -s 26919800005844922 shell '/odm/bin/su -c "insmod /data/local/tmp/r1/r1_kexec.ko write_crumb=0x075fb000 write_val=0x52444331"'
adb -s 26919800005844922 shell '/odm/bin/su -c "dmesg | grep wrote.crumb"'
adb -s 26919800005844922 shell '/odm/bin/su -c "rmmod r1_kexec"'
adb -s 26919800005844922 shell '/odm/bin/su -c "insmod /data/local/tmp/r1/r1_kexec.ko read_crumb=0x075fb000"'
adb -s 26919800005844922 shell '/odm/bin/su -c "dmesg | grep crumb@"'
adb -s 26919800005844922 shell '/odm/bin/su -c "rmmod r1_kexec"'
```

For fire B, change `write_val=0x52444332`. Expect `crumb@0x75fb000 =
1380205361` (A) or `1380205362` (B). If the value is corrupted or different, do
not interpret any other slot and do not repeat the fire.

## Fire A - compat32 (not executed)

```
timeout 12 adb -s 26919800005844922 shell /odm/bin/su -c "insmod /data/local/tmp/r1/r1_kexec.ko image_path=/data/local/tmp/r1/Image dtb_path=/data/local/tmp/r1/aquaman-r1-initrd-console.dtb cma_phys=0x2ac00000 initrd_path=/data/local/tmp/r1/initrd-compat32.cpio.gz fire=1"
```

`rc=255` from `insmod` is expected (abrupt handoff). The payload has no
watchdog: if it hangs there is no pstore of its own; if the reboot succeeds the
device returns to stock without pstore. Watch the serial for 180-300 s. Do not
repeat this payload.

## Fire B - pivot_root (not executed)

```
timeout 12 adb -s 26919800005844922 shell /odm/bin/su -c "insmod /data/local/tmp/r1/r1_kexec.ko image_path=/data/local/tmp/r1/Image dtb_path=/data/local/tmp/r1/aquaman-r1-initrd-console.dtb cma_phys=0x2ac00000 initrd_path=/data/local/tmp/r1/initrd-pivot2.cpio.gz fire=1"
```

LOW priority: this is a second mount route, not a fix for the observed IABT.
With no internal watchdog, a hang produces no pstore. Only run it after fire A
has produced usable data. Watch the serial for 180-300 s.

## Reading pstore and crumbs after the fire (read-only; insmod not executed)

```
adb -s 26919800005844922 shell '/odm/bin/su -c "ls -la /sys/fs/pstore/ 2>&1"'
adb -s 26919800005844922 shell '/odm/bin/su -c "cat /sys/fs/pstore/console-ramoops-0"'
adb -s 26919800005844922 shell '/odm/bin/su -c "cat /sys/fs/pstore/dmesg-ramoops-0"'
adb -s 26919800005844922 shell '/odm/bin/su -c "dmesg | tail -200"'
adb -s 26919800005844922 shell '/odm/bin/su -c "insmod /data/local/tmp/r1/r1_kexec.ko read_crumb=0x075fb000; dmesg | grep crumb@; rmmod r1_kexec"'
```

Always read via the exact path; listing `/sys/fs/pstore/` worked in the
baseline, but in other rounds the directory was denied under SELinux Enforcing.
Save the full output in a new file under `out/r1-prep/compat/` before any reboot.
Search pstore for `Unhandled fault`, `synchronous external abort`, `exitcode=0x`,
`EXT4-fs`, `Freeing unused kernel memory` and the banner line of the new kernel.
`r1probe=DEADBEEF` only appears if the new kernel reaches user space with the
DTB cmdline; its absence is not confirmation of boot.

## Decision tree

1. Sentinel matches and `exitcode=0x0000002a00` (42 << 8): EL0 compat, execve of
   an ARM ELF32 and the `write`/`exit` syscalls work in the kexec'd kernel. The
   basic compat path is OK; the real init's SIGBUS is not a generic failure of
   the compat tables. Focus the cause on the specific `.text` mapping of the real
   init (target PTE/attributes) or on the file data, not on chroot. A clean
   return to stock via reboot, with no pstore and no exitcode, is an equivalent
   signal that the compat payload executed.
2. `Unhandled fault ... (0x82000010)` / SIGBUS (`exitcode=0x00000007`), EC 0x20
   (IABT from EL0), FSC 0x10 (external abort, EA/S1PTW clear):
   - In fire A, on a 0x65-byte `.text` payload: points to compat tables / a
     wrong PTE even for a minimal task; the compat hypothesis goes up.
   - In fire B, on the real init: missing modules/proc/sys are not the primary
     cause; see item 5.
3. `exitcode=0x000000NN00` with NN = 30+errno: mount failure. `dm-0` does not
   exist in this initrd, so the `mmcblk0p18` fallback is always the effective
   path. Examples: 32 = ENOENT, 43 = EACCES, 49 = ENODEV. Do not use as evidence
   against the compat tables; it is a device/root failure.
4. NN = 80+errno: `pivot_root(".",".")` failed; it reached the root mount but
   the switch_root idiom is not accepted here (e.g. 82 = EINVAL). NN =
   100+errno: `execve("/init")` failed after the pivot (102 = ENOENT, 108 =
   ENOEXEC, 113 = EACCES): the new root is correct, but the real init is not
   executable. Secondary codes: 10+errno `mkdirat`, 20+errno `mknodat`,
   70+errno `chdir("/root")`, 110+errno `umount2`, 90+errno `chdir("/")`.
5. The same SIGBUS at `0x49104` after the pivot: the failure follows the real
   init and reproduces with a different mount path. This rules out
   chroot/manual-mount as the cause and, if fire A produced 0x2a00, also weakens
   "compat tables broken in general". The remaining causes are the target PTE
   attributes of that page, memory overlap (e.g. an under-reserved secmon
   covering the PFN), or corrupted `.text` data. Do not run another fire with
   the same payload; compare the pstore with round 11 before deciding.
6. No serial in 180-300 s, no pstore and no reliable sentinel: inconclusive.
   Stop rule below. Do not conclude anything from a corrupted crumb.

## Stop rule

- One hypothesis per fire. Do not repeat an identical payload, and do not run
  fire B before reading fire A's sentinel, crumbs and pstore.
- If the serial does not return within 180-300 s, stop immediately: no second
  fire, no power-cycle, no USB DL.
- No flash, erase, saveenv, efuse, fastboot image, USB DL write, BL33 patch or
  ODM persistence in this package.
- If the pivot produces no usable data, end the pivot line; it is low priority
  and has no watchdog of its own.

## Status

Every command above is text. I executed none of it during this preparation. I
have not run any push, insmod (including sentinel/crumb ones) or `fire=1`. I
edited no tracked file or report and made no commit.
