# R1 cross-route control over USB DL - preparation only (2026-11-27)

Status: OFFLINE ONLY. I executed nothing on the device. I made no optimus entry,
adb reboot, fastboot, importbootargs, RAM write, patch, boot, power-cycle, push
or commit in this preparation. Every command below is a proposal I wrote.

Goal: boot the SAME clean Image of R1 by the USB DL route, with the same stock
cmdline plus one unique marker. The result attributes the R1 fault to the
kexec handoff or to the kernel image itself.

## Artifacts (created offline, verified)

| Artifact | sha256 | bytes |
| --- | --- | --- |
| `out/r1-device/Image.clean` (kernel, ARMd at +0x38) | `6c30b16ee7bdc99d62c08c86ef5c2212b736e7e6dab7bfaa1b1033e86e8ca045` | 27,308,544 |
| `out/r1-prep/usbdl/cmdline-r1attr.txt` | `e811ca029094f56748dd45c804f652138bc15d6698d20139571ae63418a81ea4` | 1,658 |
| `out/r1-prep/usbdl/r1-attr.img` | `f8d6787b7b748b0cb3cb5e438340e45eb403dd5cd274e2ed9f6b8675f45eb3e5` | 27,312,128 |

Checks already done offline:

- cmdline = `work/r1-kexec/cmdline-live.txt` (1,643 B) with only
  ` aqusbdl=r1attr` inserted before the trailing newline; 78 -> 79 tokens,
  the only new token is the marker, `r1probe` is absent (0 occurrences).
- `dm="..."` keeps both quotes and all verity tokens; reassembly of the 64
  importbootargs chunks of 26 bytes reproduces the file exactly; the marker
  sits inside one chunk and is not split.
- `r1-attr.img`: `ANDROID!` header, kernel load `0x1080000`, `ARMd` at
  kernel +0x38, ramdisk and second empty, page 2048, header cmdline empty
  (cmdline comes from importbootargs, not from the image). Expected size
  2048 + align(kernel, 2048) = 27,312,128 B.

## Exact sequence

### 0. Pre-flight (offline, no device)

```
sha256sum out/r1-device/Image.clean out/r1-prep/usbdl/r1-attr.img out/r1-prep/usbdl/cmdline-r1attr.txt
python3 tools/aq_usbdl.py --dry-run identify
python3 tools/aq_usbdl.py --dry-run --yes importbootargs out/r1-prep/usbdl/cmdline-r1attr.txt
python3 tools/aq_usbdl.py --dry-run --yes patch-secboot
python3 tools/aq_usbdl.py --dry-run --yes --boot --patch entry boot out/r1-prep/usbdl/r1-attr.img
```

All four dry-runs were executed in preparation and returned 0. The `read`
verb has no `--dry-run` path: it always opens the device. Do not dry-run it.

### 1. Enter optimus (not executed)

```
adb reboot fastboot
fastboot oem update 5000
```

Expect USB `1b8e:c003`. Do not use `set_usb_boot`, `0x05`, fastboot flash or
any reset other than the two commands above.

### 2. identify (read-only)

```
sudo python3 tools/aq_usbdl.py identify
```

Expect raw `00 07 00 10`, stage 16 (TPL/BL33-U-Boot). Anything else: stop.

### 3. Pre-patch readback (read-only)

```
sudo python3 tools/aq_usbdl.py read 0x37e19ea8 8
```

Expect the original BL33 bytes `fd 7b be a9 fd 03 00 91`. If the entry is
already patched or unreadable, stop and report; do not write.

### 4. Dry-runs (safe at any point, no USB)

Repeat the four commands from step 0 as a final consistency check.

### 5. importbootargs (not executed, RAM only, no saveenv)

```
sudo python3 tools/aq_usbdl.py --yes importbootargs out/r1-prep/usbdl/cmdline-r1attr.txt
```

Expect `bootargs imported in 64 chunks (1657 bytes)`. No flash, no saveenv.
Optional read-only env check before the patch, if needed:
`sudo python3 tools/aq_usbdl.py cmd 'env export -t 0x37800000 4096 bootargs'`
followed by `sudo python3 tools/aq_usbdl.py read 0x37800000 64` (repeat with
increments of 64) to confirm `aqusbdl=r1attr` and the `dm=` token.

### 6. patch-secboot + readback (not executed)

```
sudo python3 tools/aq_usbdl.py --yes patch-secboot
```

Writes 8 bytes at `0x37e19ea8`: `00 00 80 52 c0 03 5f d6`
(`mov w0,#0 ; ret`), then `dcache flush` and `icache flush` via `0x34`.
Readback must be exactly `00 00 80 52 c0 03 5f d6`. If it differs or any
flush reply is not `success`: stop, do not boot. No efuse operation in this
session (the patch disables `aml_sec_boot_check` for all 15 callers).

### 7. boot (not executed)

```
sudo python3 tools/aq_usbdl.py --yes --boot --patch entry boot out/r1-prep/usbdl/r1-attr.img
```

This writes 27,312,128 bytes at `0x1080000` via `0x11`, applies the entry
patch with flush and readback again, then sends `bootm 0x1080000` via `0x30`.
USB disconnect / `USBError` after bootm is expected. Use `--patch entry`,
NOT `--patch cbz`: the Image is plaintext, so there is no SMC decrypt to
preserve. Do not send `0x05`.

### 8. Oracles in the SAME boot (read-only; no reboot between checks)

After Android returns:

```
adb shell getprop sys.boot_completed
adb shell 'ps -A | grep zygote'
adb shell 'grep /dev/root /proc/mounts'
adb shell '/odm/bin/su -c id'
adb shell '/odm/bin/su -c "cat /proc/cmdline"'
adb shell '/odm/bin/su -c dmesg'
```

Expected: `sys.boot_completed=1`; zygote `running`; `/dev/root on / type ext4
(ro)`; `uid=0(root)` with `context=u:r:su:s0`; `aqusbdl=r1attr` in cmdline;
dmesg banner containing `Linux version 4.9.113-g3d4ab79e ... #64 SMP
PREEMPT Thu Nov 26 19:04:01 -03 2026` (banner at Image offset `0xd90070`).
`r1probe=DEADBEEF` must NOT appear: cmdline comes from importbootargs, not
from the R1 DTB. If dmesg is denied by SELinux, read
`/sys/fs/pstore/console-ramoops-0` by exact path as root instead. Preserve
the full outputs and the pstore of this round before any reboot.

## Decision tree

- Boots to `sys.boot_completed=1` with the same Image, marker and clean
  banner: the kernel build is fine; the fault is in the R1 handoff
  (inherited memory/GIC/DMA state, TTBR0/MAIR/SCTLR, load address).
- Same SIGBUS at `0x49104`, ESR `0x82000010` or same panic signature:
  the fault follows the kernel image/config; R1 is exonerated. Compare the
  pstore record with rounds 7/8 before drawing a conclusion.
- Banner appears but no `boot_completed`: check the marker first. Missing
  marker means importbootargs failed; marker present means cmdline/rootfs,
  not the R1 handoff. Do not repeat an identical payload.
- No adb, no `1b8e:c003`, no pstore: inconclusive. Do not repeat the same
  payload; I have not power-cycled.

## Risks

- efuse: the entry patch bypasses `aml_sec_boot_check` for every caller
  while BL33 is live. Never combine this session with efuse, flash, erase,
  saveenv or persistent env writes.
- FLUSH: USB writes land in D-cache, execution uses I-cache. The readback
  after `dcache flush` / `icache flush` is the only visibility check; a
  dirty line could still hide the patch. Stop if readback differs.
- USB: a wrong address can corrupt BL33 and drop the gadget; recovery is
  `libusb_reset_device` per `USB_RECOVERY.md`. The bulk write is ~6,668
  chunks; an interrupted transfer invalidates the run.
- `bootm` disconnects the gadget by design; a hang here needs a power-cycle,
  which I have not performed.

## Steps I have not executed

1. `adb reboot fastboot` and `fastboot oem update 5000` (optimus entry).
2. `importbootargs` (live RAM bootargs).
3. `patch-secboot` (BL33 code write + cache flush).
4. `boot --patch entry` (27 MB RAM write + `bootm`), including the dry-runs; I
   have not repeated them before any live run.
5. Any power-cycle, hardware reset or USB recovery after the boot.
6. Anything not listed as read-only here: efuse, flash, erase, saveenv,
   `0x05 run`, push, commit, edits to tracked files or reports.

I executed nothing in this package on the device.
