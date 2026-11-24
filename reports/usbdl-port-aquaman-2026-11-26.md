# amlogic-usbdl port to aquaman PI.2055 (study, 2026-11-26)

Scope: analysis + implementation of a USB loader for the aquaman, following the
logic of `frederic/amlogic-usbdl` and the fork `Raxone/amlogic-usbdl_s905x3`.
No flash, erase, saveenv, persistent setenv, efuse, BootROM or `0x05`
was run this round. The device is in Android, outside the burning window.
The tool `tools/aq_usbdl.py` was written and validated offline; I then ran it
on hardware in the rounds below.

## 1. What the original exploit does

`amlogic-usbdl` attacks the **BootROM (BL1)**, not U-Boot. The target is the
USB download interface that requires a signed bootloader. Two bugs combine:

1. `AM_REQ_WR_LARGE_MEM` (`0x11`) receives the size in two ways:
   `dldata.size` (checked) and `wValue * wIndex` (`wIndex` is not checked).
2. The download buffer pointer advances `wValue` bytes after each bulk
   transfer, even when the transfer came in empty.

With empty transfers the host walks the pointer from `0xfffa0000` up to the
BootROM stack (e.g. `0xfffe3000`) and, on the last transfer, overwrites the
return address with `0xfffa0000`, where the payload was placed. When the
handler returns, the ROM executes unsigned code **before** the signature
check, in Secure World. Each SoC has a different `ra_ptr`: `0xfffe3688`
(S905D3), `0xfffe3678` (S905D2); the S905X3 fork reuses `0xfffe3688`.

The payload is a raw AArch64 binary. The examples dump the ROM, reboot, or
open a "new world cup" fastboot. The key point is: **write unsigned code
via `0x11` and divert the flow before the signature gate**.

## 2. What changed on the aquaman

The aquaman is GXL/S805Y, AArch64, Android 9, U-Boot `2015.01-g7ac5df7677-dirty`.
Entering burning mode (`adb reboot fastboot` + `fastboot oem update 5000`)
enumerates `1b8e:c003` with `identify = 00 07 00 10`, **stage 16 = TPL/BL33**, not
BL1. Entering stage 0/8 has never been demonstrated on this device; the
`set_usb_boot 2` + real reset attempt hangs the chip without enumerating
anything (`reports/round34-setusbboot-realreset.md`, `round36-force-usb-boot-state.md`).

The firmware runs the **v2** stack (`v2_burning/v2_usb_tool/usb_pcd.c`), not the
`aml_tiny_usbtool` used as a reference by the post. Consequences:

| Item | BootROM / tiny | aquaman (v2, stage 16) |
|---|---|---|
| `wValue`/`wIndex` in `0x11` | `wIndex` unchecked, exploitable | **discarded**: `do_vendor_out_complete` recomputes `bulk_len`/`bulk_num` from `bulk_data_len` (`usb_pcd.c:645-646`) |
| buffer pointer | advances even on an empty transfer | advances `bulk_len`, no empty-transfer bug |
| `0x05 RUN_IN_ADDR` | calls `fp()` | calls `dwc_otg_power_off_phy()` **before** `fp()`, with no KEEP_POWER flag (`usb_pcd.c:626-629`) |
| password | `need_password` comes from efuse | `identify` answers `need_password=0`; `0x01`/`0x11` with arbitrary destination already reproduced (`reports/PRIMITIVE_INVENTORY_CONSOLIDATED_2026-11-19.md`, P15) |
| boot gate | signature in ROM | `do_bootm -> aml_sec_boot_check(0x37e19ea8) -> SMC 0x820000ff -> BL31` |

The "wedge" of `RUN_IN_ADDR` in `reports/bl33-campaign-round43.md` T7/T8 is
consistent with the deliberate PHY power-down, not a failure of the jump. Even
so, `0x05` is not needed for the port described here.

## 3. Proposed port

The same idea (write an unsigned image and skip the gate) is achieved without
exploiting the overflow and without `0x05`:

1. `0x11 WR_LARGE_MEM` writes a `boot.img` with a **plaintext** ARM64 kernel to
   RAM (`0x1080000`). This is already a primitive reproduced on hardware; the
   size is limited by `bulk_data_len`, not by 64 B. The device re-arms bulk in
   `0x1000`-byte blocks and, for the remainder, in `0x200`/residual blocks
   (`DWC_BLK_*`).
2. Write 8 bytes at `0x37e19ea8`, the `aml_sec_boot_check` entry:

   ```
   00 00 80 52 c0 03 5f d6   ; mov w0,#0 ; ret
   ```

   The 15 callers now see `w0 == 0` and follow the success path. The
   original bytes in the dump are `fd 7b be a9 ...` (`stp x29,x30,[sp,#-0x20]!`).
3. `dcache flush` + `icache flush` via `AM_REQ_BULKCMD (0x34)` - the
   `icache`/`dcache` commands exist in the cmd_tbl (`common/cmd_cache.c`) and
   land in `run_command` of `optimus_working`. This solves patch visibility:
   writes over USB go through the D-cache, execution through the I-cache.
4. `bootm 0x1080000` via `AM_REQ_TPL_CMD (0x30, wIndex=1)`. The v2 handler
   disconnects USB when the command starts with `bootm` and runs
   `optimus_working -> run_command`. `do_bootm` no longer calls the SMC;
   `bootm_load_os` ACCEPTS `ANDROID!` with a plaintext kernel as long as there
   is `0x644d5241` (`ARMd`) at `Image+0x38`.

The DTB is U-Boot's own (`gd->fdt_blob`/`dtb_mem_addr`), so it does not need
to be packaged. The ramdisk can be the one in `patched_unpack/ramdisk` or omitted.

### Addresses and sources

| Value | Source |
|---|---|
| `0x37e18000` | BL33 base in RAM, `reports/round14-bl33-persist/bl33-37e18000.bin` |
| `0x37e19ea8` | `aml_sec_boot_check`, `reports/bl33-offline-round13.md` |
| `0x37e24cf0` | call in `do_bootm`, same dump |
| `0x37e19310` | `flush_dcache_range`, called in the wrapper tail |
| `0x1080000` | `GXB_IMG_LOAD_ADDR`, `common/cmd_bootm.c` |
| `0x820000ff` | `AML_DATA_PROCESS`, SMC at `0x37e19ed8` |

`0x11` and `0x34` are in `v2_usb_tool/usb_pcd.c`; same for `0x30`. The
framing pattern of `0x11` is the same as Frederic's: `ctrl OUT 0x40/0x11`
with 16 bytes `<u32 addr><u32 len><u32 0><u32 0>` and data on bulk OUT `0x02`.

## 4. Tool

`tools/aq_usbdl.py` implements: `identify`, `read`, `write`, `cmd`, `tpl`,
`patch-secboot`, `boot` and `mkimg`. `--dry-run` prints the transactions without
touching the device. Writing requires `--yes`; `boot` requires `--yes --boot`.
The tool has no flash/erase/saveenv/efuse/reset and does not send `0x05` (the
`run` subcommand, if used, is explicit and warns about the PHY).

Suggested verification sequence, not yet run:

```
# 1. offline
python3 tools/aq_usbdl.py --dry-run boot imagem-aq.img

# 2. enter burning (procedure already documented in the repo)
adb reboot fastboot
fastboot oem update 5000

# 3. observe
sudo python3 tools/aq_usbdl.py identify

# 4. write RAM
sudo python3 tools/aq_usbdl.py --yes --boot boot imagem-aq.img
```

UART-free oracle: change the `linux_banner` in the plaintext kernel before
generating the image (`4.9.113-g963f962d046a` -> own marker) and check
`/proc/version` after Android comes back. The banner is at
`artifacts/kernel_image.bin` offset `0xd40080`.

### Live verification (2026-11-26)

I ran only the non-destructive part. `adb reboot fastboot` +
`fastboot oem update 5000` -> `1b8e:c003`. `aq_usbdl.py identify` answered
`00 07 00 10`, stage 16. `write 0x37800000` with 4 bytes `41 42 43 44` and
an identical readback; the rest written with zeros and readback `00 00 00 00`.
No patch, cache flush, bootm, 0x05, flash or env was sent. The device
stayed enumerated as `1b8e:c003` until the end of the session.

### Test boot (2026-11-26)

I booted `kernel-banner.bin` (plaintext Image with a modified `linux_banner`)
and the ramdisk from `patched_unpack/`. The full chain ran: write
of 26,988,544 bytes at `0x1080000`, an 8-byte patch at `0x37e19ea8` with readback
`00 00 80 52 c0 03 5f d6`, `dcache flush`/`icache flush` with `success`, and
`bootm 0x1080000` via both `0x30` and `0x34`. The gadget disappeared in both
cases, as expected when the kernel takes over the machine.

The boot did not end in Android. The next round's pstore holds
`Kernel panic - not syncing: Attempted to kill init! exitcode=0x00000100`,
followed by `Rebooting in 1 seconds`, and the device returned to the stock kernel.
That is: the gate was passed and the written kernel did execute; the failure is
in the boot image (kernel from another build / ramdisk), not in the USB chain.
There was no `aqusbdl=1` in `/proc/cmdline` after the reboot, because the panic
restarted into stock.

Repetitions with `artifacts/aquaman-linux-fdt.dtb` as `second` (magic
`d00dfeed`, instead of `boot_unpack/second`, whose magic is `4db07057`):
with an empty ramdisk the panic changes to `Requested init /init failed (error -2)`;
with `patched_unpack/ramdisk` it goes back to `Attempted to kill init! exitcode=0x00000100`.
The wrong DTB was not the only cause. The dmesg-ramoops shows a normal boot up to
`Freeing unused kernel memory`; there are no init messages because the stock
cmdline carries `loglevel=1`.

Env oracle found: `env export -t 0x37800000 4096 bootargs`
dumps the value to RAM and `0x02` reads it back. This proved that
`setenv bootargs "$bootargs ..."` works and that `env import -t` with 1646
bytes drops the gadget, while import in 63 chunks of 26 bytes via
`importbootargs` works and reproduces the full stock cmdline. Even so,
the control test with the full cmdline, `skip_initramfs`, plaintext kernel and
compiled DTB froze on a black screen and required a power-cycle. Three live
rounds ended in power-cycles; boot experiments were suspended.

Remaining hypothesis: the `mov w0,#0 ; ret` patch at the `aml_sec_boot_check`
entry removes side effects of the call (the SMC decrypt and `flush_dcache_range`
in the tail), not just the gate. The next patch to try is narrower: let the
whole wrapper run and turn the `cbz w0, success` right after `bl 0x37e19ea8`
into `b success`, preserving the SMC and the flush.

#### Offline confirmation and implementation (2026-11-26, no hardware)

The gate address was corrected from the BL33 dump
(`reports/round14-bl33-persist/bl33-37e18000.bin`, disasm via `a64_annot.py`):

| Address | Bytes | Instruction |
|---|---|---|
| `0x37e24cf0` | `6e d4 ff 97` | `bl 0x37e19ea8` (call to `aml_sec_boot_check`) |
| `0x37e24cf4` | `f4 03 00 aa` | `mov x20, x0` (saved return value) |
| `0x37e24cf8` | `c0 00 00 34` | `cbz w0, 0x37e24d10` (gate) |
| `0x37e24d10` | `f6 04 00 90` | start of the success path (`get_avb_mode`/`avb2`) |

The earlier guess of `0x37e24d00` was wrong: that holds `mov w1, w20`, and the
`cbz` target is `0x37e24d10`, not `0x37e24d18`. The fallback (w0 != 0) prints
`aml log : Sig Check %d` at `0x37ec0000+0xd3`. The patch is to replace the 4 bytes at
`0x37e24cf8` with `06 00 00 14` (`b 0x37e24d10`), without touching the 8 bytes
at the wrapper entry.

Implemented in `tools/aq_usbdl.py`: the `patch-cbz` verb and the
`--patch cbz` option on `boot`/`bootm`. The mode reads the 4 bytes at `0x37e24cf8`,
verifies they are `cbz w0`, derives the target, requires `0x37e24d10`, writes the `b`,
does `dcache flush`/`icache flush` and performs a readback. Validated with
`--dry-run` and `py_compile` before going to hardware.

#### Hardware test with the narrow patch (2026-11-26)

I booted the unmodified stock `boot.img`
(sha256 `7797e3dfbaa403167a8bc5105e239f124d94b8bbcdf34378d582d1b7fc000aad`).
Entry into optimus via `adb reboot fastboot` + `fastboot oem update 5000`
(expected failure), `identify = 00 07 00 10`, stage 16. Before the patch, a live
read confirmed `0x37e24cf8 = c0 00 00 34` and the wrapper entry
`0x37e19ea8 = fd 7b be a9 fd 03 00 91` (original, not patched).

Command: `sudo python3 tools/aq_usbdl.py --yes --boot --patch cbz boot boot.img`.

- 16,777,216 bytes written at `0x1080000` via `0x11`.
- Patch at `0x37e24cf8`: `c0 00 00 34` -> `06 00 00 14` (`b 0x37e24d10`),
  identical readback. The `aml_sec_boot_check` wrapper is intact.
- `dcache flush` and `icache flush`: `success`.
- `bootm 0x1080000` via `0x30`; USB disconnected with `Input/Output Error`,
  as expected.

The device came back to Android on its own, **without a power-cycle**. The next
round's pstore (`console-ramoops-0`) records:

```
[    1.784882@3] Kernel panic - not syncing: Requested init /init failed (error -2).
[    1.786716@3] CPU: 3 PID: 1 Comm: swapper/0 Not tainted 4.9.113 #1
[    1.842859@3] SMP: stopping secondary CPUs
[    1.861578@3] Rebooting in 1 seconds..
[    2.861648@3] reboot reason 1
```

The current boot is stock (dmesg with the full banner
`4.9.113-g963f962d046a-dirty`, `root=/dev/dm-0` with dm-verity).

Reading: the narrow patch **worked** - the `AMLSECU!` kernel from `boot.img`
was decrypted by the preserved SMC and ran up to `kernel_init`. The failure is no
longer the gate or the decryption: it is the image. The stock `boot.img` header has
`ramdisk_size = 0` and a cmdline of only `androidboot.dtbo_idx=0 otg_device=1
buildvariant=user`, with no `root=`/`skip_initramfs`; hence there is no `/init`.
This reproduces the "no ramdisk" failure mode already catalogued above, so the
RAM boot line was stopped here, without repeating old variants or asking for
another power-cycle.

**Provisional conclusion at that point:** the signature gate at stage 16 had
been bypassed and the chain up to `bootm` proven, but the image still did not boot
due to the missing rootfs/cmdline.

#### Successful boot (2026-11-26, round 2)

Offline research on two parallel fronts closed both gaps:

1. `aml_sec_boot_check` calls `SMC 0x820000ff` with `nType=0x40`,
   `pBuffer=0x1080000`, `nLength=0x1800000`, `nOption=7`
   (`GXB_IMG_DEC_KNL|RMD|DTB`): BL31 decrypts the three `AMLSECU!` blocks in
   place, including the DTB. The `boot.img` `second` is **not** used by
   `bootm`; `bootm_find_fdt` runs `store dtb decrypt ${dtb_mem_addr}`
   (`0x37e2510c`) with `dtb_mem_addr=0x1000000`. That is why passing a compiled
   DTB as `second` never made a difference.
2. `do_bootm` rebuilds `bootargs` as `env + header cmdline +
   verifiedbootstate` (`0x37e24e64`) and `fdt_chosen` writes the final value to
   `/chosen/bootargs`. Rounds 53/56/58 did not measure `/proc/cmdline` of a
   custom kernel (permission denied for the shell; only `getprop` after a stock
   reboot), so "transport refuted" was not conclusive.

Defect found in `importbootargs` itself: the old command
`setenv bootargs "$bootargs <chunk>"` inserted a leading space in each 26-byte
chunk. This broke tokens at chunk boundaries
(`skip _initramfs`, `androidboot.veritymode=enf orcing`, `aqus bdl=cbzok`).
Fixed in `tools/aq_usbdl.py` to
`setenv bootargs "${bootargs}<chunk>"`, with the original space inside the
chunk. Verified with `env export -t 0x37800000 4096 bootargs`: a 1647-byte
cmdline reproduced with all tokens intact (only a trailing `\n`).

Round 2: same stock `boot.img`, narrow patch, full cmdline with
the `aqusbdl=cbzok` marker injected before bootm. Result:

- `adb shell` came back without a power-cycle.
- `/proc/cmdline` (root) contains `skip_initramfs`, `root=/dev/dm-0`,
  `androidboot.veritymode=enforcing` and **`aqusbdl=cbzok`**: the injected
  cmdline reached the kernel.
- `sys.boot_completed=1`, zygote `running`, `/dev/root on / type ext4 (ro)`.
- pstore of the round: only `reboot: Restarting system with command 'fastboot'`
  (no panic).

That is: **a boot.img loaded over USB into RAM, with the gate bypassed and the
full cmdline, boots Android up to boot_completed**. Root is the usual
dm-verity setup (`/dev/mmcblk0p18`), with no flash and no ramdisk. The kernel
is still the encrypted stock one; booting a modified kernel remains to be shown.

#### Modified kernel boot (2026-11-26, round 3) - goal completed

Image prepared only in `/tmp/opencode` (no new artifacts in the repo):

- `kernel-aqusbtest.bin`: copy of `artifacts/kernel_image.bin` with the suffix
  `-g963f962d046a` changed to `-gAQUSBTEST123` at `Image+0xd40095`
  (same length, no shift). Size 26,544,640 bytes.
- `aq-custom.img`: `tools/aq_usbdl.py mkimg` with that kernel, no ramdisk and
  no `second`, `ANDROID!` header with an empty cmdline. 26,548,224 bytes,
  sha256 `eeb6f4897b868d54bf750f5280a9e70ea5257e3ba3728f81377beda4a56c443a`.

I ran the round: entry into optimus, `importbootargs` with the
complete (fixed) cmdline, write at `0x1080000`, the **entry** patch
(`00 00 80 52 c0 03 5f d6` at `0x37e19ea8`, readback checked) and `bootm
0x1080000` via `0x30`. For a plaintext kernel the SMC has nothing to decrypt,
so the entry patch is the right path; the narrow patch remains the path for the
encrypted stock `boot.img`.

Result:

- `dmesg`: `Linux version 4.9.113-gAQUSBTEST123-dirty (...)` - the modified
  kernel really executed (`/proc/version` omits the suffix due to behavior
  already documented; dmesg is the oracle).
- `/proc/cmdline` contains `skip_initramfs`, `root=/dev/dm-0` and
  `aqusbdl=cbzok` - injected cmdline intact.
- `sys.boot_completed=1`, zygote `running`, `/dev/root` ext4 ro, root
  `/odm/bin/su` functional.
- pstore of the round: only `reboot: Restarting system with command 'fastboot'`;
  no panic, no power-cycle.

**Final conclusion:** the USB chain at stage 16 is complete. The gate is
bypassed in RAM in two modes (entry, for plaintext `Image`; narrow, for the
stock `AMLSECU!` container, preserving the SMC), the full cmdline can be
injected via `importbootargs` without breaking tokens, and **a modified kernel
boots Android up to boot_completed without flash, without saveenv and without a
power-cycle**. What remains for a permanent ROM is outside this path: repackage
the kernel with the correct signature or keep loading over USB on every boot.

#### Magisk via initramfs (2026-11-26)

First attempt with the Magisk ramdisk and `skip_initramfs` removed: magiskinit
ran (`RootFS Init`) but aborted with `Cannot find preinit userdata, abort!`,
followed by `Attempted to kill init! exitcode=0x00000100`. Cause: the
`PREINITDEVICE` field in `/.backup/.magisk` said `userdata`, but the partition is
`data` (`PARTNAME=data`, 179:20).

Second attempt: I rebuilt the ramdisk with
`PREINITDEVICE=data` and fstabs added to the cpio; cmdline with
`skip_initramfs=1` (the kernel `__setup` ignores a non-empty value, so the
initrd is unpacked, while Magisk enters `Legacy SAR Init`).
Result: `sys.boot_completed=1`, zygote `running`, `magiskd` PID 2942,
`magisk -v` = `30.7:MAGISK:R`, `/sbin/su -c id` = uid 0 with
`context=u:r:magisk:s0`. dmesg: `magiskinit: Legacy SAR Init`, no panic.
Marker `aqusbdl=magiskfstab` in `/proc/cmdline`. No power-cycle.

Note: the fstab was not the cause; `magiskinit` does not read fstab, it reads
`PREINITDEVICE`. The files were kept in the cpio, but what unblocked it was
the partition name and the value of `skip_initramfs`.

#### Kernel with built-in KernelSU (2026-11-26, build)

I compiled `Image` with `CONFIG_KERNELSU=y` (not `=m`) from
`work/ksu-lkm-fix/kernel-obj` + sources from `work/ksu-lkm-fix/upstream/kernel`:

- `/tmp/opencode/kernel-ksu-builtin.bin`: 27,046,400 bytes, `ARMd` at +0x38,
  sha256 `b7854dad616deab3ff95fe4a83df965494a86fa1084d6a2179462c3c5b55ab7e`.
- `/tmp/opencode/aq-ksu-builtin.img`: 27,049,984 bytes.
- Banner `-gKSUBUILTIN1---` at `Image+0xd90085` (shifted because the KSU
  text landed before `.rodata`); symbols `kernelsu_init`, `ksu_core_init`
  etc. resolved as `T` in vmlinux.
- Config deviations forced by the local snapshot: VDEC off (build error in
  `vvp9.c`), `CONFIG_AMLOGIC_VIDEOSYNC=y` and derived
  `CONFIG_CC_STACKPROTECTOR=y`. May affect multimedia.

I booted with the full cmdline carrying the marker `aqusbdl=ksu`,
write of 27,049,984 bytes at `0x1080000`, entry patch with readback,
flush and `bootm 0x1080000` via `0x30` (expected USBError on disconnect).

**Result: did not boot.** After ~90 s there is no `adb devices` nor `1b8e:c003`
on the bus. There is no pstore access to tell whether there was a panic. The
device requires a power-cycle to come back, so the RAM boot line was stopped
here, without repeating variants.

Likely cause (not confirmed by a log): the config deviations of the local
build (VDEC off due to the error in `vvp9.c`, `VIDEOSYNC=y`, stack
protector) or the built-in KSU code itself prevented the kernel from reaching
userspace. The build is correct offline (`CONFIG_KERNELSU=y`, symbols `T` in
vmlinux), but this specific Image is not bootable on this device.

**Consolidated state:** the USB path is proven for the stock `boot.img`
(narrow patch) and for plaintext `Image` (entry patch), including functional
Magisk. The kernel with built-in KernelSU compiles, but the generated image
hangs boot and was not validated on hardware. There is no reason to attribute
this to the USB bypass: the same chain booted other Images minutes earlier.

`reboot` via `0x30` command `reset` works: `optimus_working` intercepts
`reset` and calls `optimus_reset`, returning to Android without a power-cycle. It was
tested once, with ADB back immediately afterward. U-Boot's `do_reset` stub is not
involved in this path.

## 5. Real limits and risks

- This is a **RAM, per-session** bypass. The wrapper goes back to the original on
  the next reset. It is not a bootloader unlock, does not change efuse, and does not
  enable permanent kernel flashing.
- `0x11` writes to RAM; a wrong address can corrupt the running BL33 and
  drop the session (recoverable via `libusb_reset_device`, `USB_RECOVERY.md`).
- Patching the wrapper disables `aml_sec_boot_check` for **all** 15
  callers while the session lasts; efuse commands that pass through it
  would be left unchecked. Do not use efuse in the same session.
- The kernel must be a valid ARM64 `Image`; a `boot.img` with an encrypted
  `AMLSECU!` kernel still depends on the SMC.
- The repo's kernel reconstruction (`McMCCRU/linux-amlogic`) is an
  approximation: 190 different CRCs, 13 missing symbols. This does not prevent
  boot, but stock modules do NOT load on that kernel.
- It was not tested whether `dcache flush`/`icache flush` via bulkcmd are sufficient
  in the presence of an active D-cache with an already dirty line. If the patch does not take,
  the alternative is a payload via `0x05` that does `flush_dcache_range` +
  icache invalidation and calls `bootm` directly - but then the PHY is already off
  and there is no longer any USB observer.
- Nothing here depends on `set_usb_boot 2` or the `RTI_STATUS_REG3` state; that
  path is closed and was not reopened.

## 6. Ledger

```
original amlogic-usbdl: 2 bugs in 0x11 in BootROM + ra_ptr per SoC   READ
same bug in aquaman v2: DOES NOT EXIST (wIndex recomputed)            READ
0x11 WR_LARGE_MEM to arbitrary RAM on aquaman                         REPRODUCED (P15)
0x05 RUN_IN_ADDR: PHY off before fp()                                 READ (code) / wedge measured
aml_sec_boot_check 0x37e19ea8 -> SMC 0x820000ff                       READ (offline) + refusal measured
patch mov w0,#0; ret + cache flush + bootm                            IMPLEMENTED, NOT TESTED ON HW
narrow patch cbz->b at 0x37e24cf8 (wrapper intact)                    TESTED ON HW: patch ok, SMC preserved
full cmdline via importbootargs (tokens intact)                       TESTED ON HW: marker in /proc/cmdline
stock boot.img via USB RAM + narrow patch + full cmdline               BOOT OK (boot_completed=1, no power-cycle)
custom plaintext kernel + entry patch + fixed cmdline                 BOOT OK (AQUSBTEST123 banner in dmesg)
```

Do not confuse with the hypotheses closed in `INVALIDATED_HYPOTHESES.md`:
`fastboot boot` with stub, `BUF == Y`, env->cmdline, GhostLock, KernelSU. This
port is a new path, in BL33 over USB, and does not reopen any of them.
