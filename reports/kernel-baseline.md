# kernel-baseline — meson64 → aquaman (4.9.113)

base: `meson64_defconfig` from `.src/linux-amlogic` (McMCCRU, ancestor,
NOT exact source — see `reports/provenance.md`). Comparison performed against the
expanded `.config` (`build-aq/.config`, 4469 opts) vs `aquaman-config`
(4447 opts): **98.12% match, 48 differs, 7 only-A, 29 only-B**.
(The older comparison against the raw defconfig file, 14.05%, measured something else:
defconfig is minimal, device `.config` is fully expanded. The honest figure is this one.)

## reconstructed config

`meson64_defconfig` + 2 local adjustments (in objdir `build-aq/.config` only):

| adjustment | reason |
|---|---|
| `AMLOGIC_MEDIA_VDEC_VP9=n` | tip 3d4ab79e broke the driver (`gvs` undeclared in vvp9.c:6894/7820); fails to compile |
| `AMLOGIC_VIDEOSYNC=y` | `video_sink/video.c:6566` calls `videosync_pcrscr_update` without `#ifdef`; without it link fails |

Both adjustments trend IN THE DIRECTION of aquaman (which lacks VP9 and VIDEOSYNC —
the Xiaomi tree has a different media Kconfig layout; see "unknowns").

## 48 real differs (A=device, B=meson64 expanded)

- Wrong SoC/board in meson64 (A=n B=y, strip): `PINCTRL_MESON_TL1`,
  `SND_CODEC_TL1_ACODEC`, `SND_SOC_TAS5805` (TL1 is a different chip), `EXFAT_FS`,
  `NTFS_FS`, `SLUB_DEBUG`.
- Device TV profile (A=y B=n, keep/add): 31 `USB_*` (USB networking, 3G, cdc…),
  `HID_APPLE`, `KSM`, `NLS_UTF8`, `CRYPTO_LZ4`, `PSTORE_FTRACE`.
- Scalars: `HZ` 300 vs 250, `PANIC_TIMEOUT` 1 vs 5 (faster reboot on stock),
  `CC_STACKPROTECTOR_STRONG` A=y / `NONE` B=y (meson64 resolved to NONE;
  set STRONG in ours).
- Remainder is `=n` expansion noise (symbols present in one .config and absent in the other).

## only-A (7, all to preserve)

`AMLOGIC_DEBUG_ATRACE`, `AMLOGIC_DEBUG_FTRACE_PSTORE`, `AMLOGIC_WATCHPOINT`,
`AMREMOTE_BUTTONSLIGHT`, `BT_WAKE_CONTROL`, `LZ4_COMPRESS`,
`CC_STACKPROTECTOR_STRONG_AMLOGIC=n`.

## only-B with real value (20, tree deltas, aquaman DOES NOT have)

15 drivers `AMLOGIC_MEDIA_VDEC_*` (AVS/AVS2/H264×3/H265/MJPEG/MPEG12/MPEG2_MULTI/
MPEG4×2/REAL/VC1) + `VENC_H264/H265` =y, `AMLOGIC_WIFI_DUMMY=m`, `SLABINFO=y`
(EXFAT_* remainder is consequence of EXFAT=n). The device has `MEDIA_VIDEO=y` and
`MEDIA_VIDEO_PROCESSOR=y` + `ENHANCEMENT/VECM/DOLBYVISION`, but zero VDEC/VENC
and zero VIDEO_SINK in Kconfig.

**resolved: stock video decode is 100% vendor modules.** The 14 `amvdec_*.ko` were
extracted from `vendor.new.dat.br` (`reports/vendor-modules.md`). Xiaomi did not
remove the subtree — they moved decoding entirely into `.ko` modules. Consequence: these
19 `VDEC_*`/`VENC_*` options here are dead weight, contributing to our 26 MiB Image
compared to the ~9.3 MiB of the stock kernel. Disabling them is a straightforward,
understood optimization; left as-is for now to keep the baseline comparable.

## unknowns / risks

1. ~~where stock video decode comes from~~ **RESOLVED.** 14 `amvdec_*.ko` modules +
   `decoder_common`/`stream_input`/`media_clock`/`firmware`/`vpu`, extracted
   from `vendor.new.dat.br` without root. See `reports/vendor-modules.md`. The hypothesis
   "Xiaomi removed the subtree" below was wrong: not removed, moved to modules.
   The 19 `VDEC_*`/`VENC_*` in baseline are dead weight.
2. `HZ=300` + `PREEMPT`? Verified: check `PREEMPT*` in both prior to M4.
3. Empty `LOCALVERSION` in both; `vermagic` of vendor `.ko` dictates the rest
   (Phase 9, **completed**): `4.9.y SMP preempt mod_unload modversions aarch64`.
   The `4.9.y` is Amlogic's own `Makefile:1221` flattening the stamp, not a build
   divergence. The deciding factor is the `MODVERSIONS` CRC — where 190 divergences
   exist. See `reports/vendor-modules.md`.
4. `ARCH_MESON=n / MESON_SM=n` on device with `AMLOGIC_MESON64_VERSION=y`:
   vendor fork, not upstream. Leave as-is, do not "modernize".
5. **NEW: McMCCRU HEAD fails to compile.** `AMLOGIC_DVB=y` breaks the build
   (driver lacks UAPI). Baseline requires `AMLOGIC_DVB=n`, an *additional* divergence
   relative to the device. See `reports/kernel-build-env.md`.

## Phase 3 verdict

baseline = meson64 + TV/DVB/CEC/CMA + USB/HID tail + HZ 300 + PANIC 1 −
(TL1, TAS5805, EXFAT, NTFS) − VDEC/VENC (absent on device) + build fixes above.
Compiles (`Image` 26 MB valid ARM64). It is NOT the exact source and does not
pretend to be: it is the closest ancestor that compiles with the correct gcc.
