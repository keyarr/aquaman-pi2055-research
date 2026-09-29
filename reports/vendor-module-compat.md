# vendor-module-compat — stock .ko vs custom kernel (v1, non-root)

> **Extraction was never blocked.** This file opens by stating that
> root is required because SELinux denies `cat /vendor/lib/modules/*.ko`.
> Truth: the modules **were not exclusively on the device** — they were in the OTA dumps
> already stored in this repository, such as `vendor.new.dat.br`. brotli →
> `tools/sdat2img.py` → `debugfs rdump`, without root, without device, without
> network. All 28 `.ko` files are now in `out/vendor/modules/`.
>
> The inventory below (by name) remains accurate as a list. What it lacked,
> and the replacement now provides: actual `vermagic`, `modules.dep`, `modules.alias`,
> and the CRC diff against the reconstructed kernel.
>
> **Read `reports/vendor-modules.md`** — that is the comprehensive report, containing
> the blocker preventing reuse: 13 missing symbols and 190 diverging CRCs
> against our `Module.symvers`, preventing vendor `.ko` binaries from loading on
> a kernel compiled from McMCCRU.
>
> The "blocked until root or decrypted dump" note at the end is resolved.
> What actually blocks loading is CRC verification, not file access.

extraction completed: `vendor.new.dat.br` was in the repository all along.

## inventory (`ls -R /vendor/lib/modules`, names via SELinux error — 28+1)

- decode/vpu: `amvdec_avs/av2/h264/h264mvc/h265/mh264/mjpeg/mmjpeg/mmpeg12/
  mmpeg4/mpeg12/mpeg4/real/vc1/vp9`, `decoder_common`, `encoder`,
  `stream_input`, `firmware`, `media_clock`, `vpu`, `aml_hardware_dmx`
- gpu: `mali`
- connectivity: `rtl8821cs` (SDIO Wi-Fi), `aml_sdio`, `sdio_bt` (BT on uart_A)
- misc: `ddr_window_64`, `w1`
- outside modules/: `/vendor/lib/optee.ko` (TEE)

## what this explains

aquaman-config contains NO `AMLOGIC_MEDIA_VDEC_*` options (see `kernel-baseline.md`):
because all decoding is handled by vendor modules, not built-in drivers. A custom kernel for M5
requires at minimum: `ION` + compatible CMA/reserved-memory, `VIDEOBUF2`,
`SYNC`/`SW_SYNC`, `AMLOGIC_MEDIA_VIDEO/PROCESSOR`, v4l2-core, and identical
vermagic (`4.9.113 SMP preempt mod_unload aarch64` + empty LOCALVERSION).
Wi-Fi/BT likewise: `CFG80211`, `BT`, `TTY`, SDIO stack + `MMC`.

## minimum feature set (to validate when root is available)

1. `uname -r` = `4.9.113` (empty LOCALVERSION + AUTO=n in our build, or exact stock suffix);
2. `SMP PREEMPT` identical (stock: `#1 SMP PREEMPT`);
3. ~~`MODULE_UNLOAD`, `MODVERSIONS=n` (stock almost certainly without modversions)~~
   **INCORRECT: `MODVERSIONS=y`**, confirmed in `aquaman-config` and within
   the binaries themselves. The real `vermagic` is
   `4.9.y SMP preempt mod_unload modversions aarch64` — matching across 27 of 28
   modules. `ddr_window_64.ko` is the sole outlier (`3.14.29`, without modversions),
   a legacy artifact from another platform. See `reports/vendor-modules.md`.
4. Identical `ION`, `DMA_SHARED_BUFFER`, `SYNC` from baseline;
5. Mali: kernel driver version must match userspace (`/vendor/lib/egl/*`);
   a mismatch here results in lack of accelerated display even with a booting kernel.

## ~~blocked until root or decrypted dump~~ — resolved

Exact vermagic, `depends`, and `modules.dep`: **obtained** via dump extraction.
Symbols: `Module.symvers` exists in the build objdir, and the full diff was
generated. What genuinely remains open is the `mali`/`optee` ABI, which
requires `/vendor/lib/egl/*` — and that has not yet been extracted.

### key correction: vermagic is NOT the blocker

Item 3 above was incorrect and stops being the primary obstacle. `4.9.y` is not
`4.9.113` because `Makefile:1221` in McMCCRU flattens the module stamp to
`<major>.<minor>.y` **by design**, so modules do not lock to a specific sublevel. The
10 modules compiled from McMCCRU in this session generate identical strings.
In other words: the vermagic gate was intentionally loosened by the vendor, and the
actual barrier is `MODVERSIONS` CRCs. Details in `reports/vendor-modules.md` §2.
