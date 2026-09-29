# rebuilt-kernel — what the build actually produced, and how far it is from stock

build re-run from scratch this session, same source, same toolchain as the
documented baseline. full log in `out/build-logs/`.

```sh
sh tools/build_aquaman_kernel.sh
```

```text
== source commit: 3d4ab79ea3638850a736bf2f7f65e55cb47368c4
== kernel sublevel: 113
== olddefconfig
== building Image + dtb + modules (-j12)
```

result: `EXIT=0`, zero compiler errors. first run failed — see §7, that is a
real finding, not a rerun.

## artifacts

| artifact | value | check |
|---|---|---|
| `arch/arm64/boot/Image` | 27308544 bytes (26.0 MiB) | PASS |
| arm64 magic at 0x38 | `0x644d5241` | PASS |
| `text_offset` | `0x1080000` | PASS, **matches the stock convention** |
| `image_size` | `0x1bef000` | PASS |
| `vmlinux` | ELF, machine `0xb7` (aarch64) | PASS |
| `Module.symvers` | 10150 vmlinux exports | PASS |
| dtb | `gxl_p241_1g.dtb`, magic `0xd00dfeed` | PASS |
| modules | 10 `.ko` | PASS |

stock kernel for size reference: the encrypted kernel block inside `boot.img`
has `nTotalLength 0x959000` = 9801728 bytes ≈ 9.3 MiB. **our Image is 2.8× the
stock kernel.** that is the single largest measurable difference and it is
worth stating plainly: a 26 MiB image against a ~9.3 MiB stock kernel means
the baseline carries a great deal the device does not, or the device's kernel
was stripped, or both. `text_offset` matching at `0x1080000` is a good sign for
the U-Boot handoff specifically.

## config: 49 differences against the device

```text
A: aquaman-config (4447 opts)
B: build-aq/.config  (4469 opts)
union 4476  match 4391 (98.10%)  differ 49  only-A 7  only-B 29
```

98.10%, so the 98.12% previously reported reproduces to within one option (the
new `AMLOGIC_DVB=n` delta accounts for the difference). the bulk of the 49 is
the same 31-option `USB_*` tail as before.

### the differences that are ours, not noise

| option | device | ours | classification |
|---|---|---|---|
| `AMLOGIC_DVB` | y | **n** | **blocking**, and new. see §7 |
| `AMLOGIC_VIDEOSYNC` | (absent) | y | known, build-required, device has no such option |
| `AMLOGIC_MEDIA_VDEC_VP9` | (absent) | n | known, build-required |
| `HZ` / `HZ_300` / `HZ_250` | 300 / y / n | 250 / n / y | **expected and should be fixed** |
| `CC_STACKPROTECTOR_STRONG` / `_NONE` | y / n | n / y | **expected and should be fixed** |
| `PANIC_TIMEOUT` | 1 | 5 | **expected and should be fixed** |
| `SLUB_DEBUG` / `SLUB_DEBUG_ON` | n | y | expected |
| `AMLOGIC_PINCTRL_MESON_TL1` | n | y | known, TL1 is a different chip |
| `AMLOGIC_SND_CODEC_TL1_ACODEC` | n | y | known, same |
| `AMLOGIC_SND_SOC_TAS5805` | n | y | known, same |
| `EXFAT_FS`, `NTFS_FS` (+8 sub-options) | n | y | known |
| `SLABINFO` | (absent) | y | known |
| 19 `AMLOGIC_MEDIA_VDEC_*` / `VENC_*` | (absent) | y | **expected — see §5, the device has these as modules** |
| `AMLOGIC_WIFI_DUMMY` | (absent) | m | known, replaces the real W1 stack |
| 31 `USB_*`, `HID_APPLE`, `KSM`, `NLS_UTF8`, `CRYPTO_LZ4`, `PSTORE_FTRACE` | y | n | known, TV profile, present in all meson64 baselines |
| `LZ4_COMPRESS` | y | (absent) | known, only-A |
| `AMLOGIC_DEBUG_ATRACE`, `AMLOGIC_DEBUG_FTRACE_PSTORE`, `AMLOGIC_WATCHPOINT`, `AMREMOTE_BUTTONSLIGHT`, `BT_WAKE_CONTROL` | y | (absent) | known, only-A |

the `HZ=300`, `CC_STACKPROTECTOR_STRONG` and `PANIC_TIMEOUT=1` items are
**not** build-required — they are the baseline failing to apply three deltas it
should have applied. `kernel-baseline.md` lists them as known but they were
never applied. fixing them is a config-only change and would take the match
from 98.10% to about 98.8%. not applied this session, to keep the baseline
comparable to the previously measured one; flagged here as the highest-value
next delta.

## symbols: the comparison that actually matters

not "compare symbol names" — the useful comparison is **CRC equality against
the stock modules**, because `CONFIG_MODVERSIONS=y` means that is the gate a
kernel has to pass to be usable with the stock `.ko` set.

full detail in `reports/vendor-modules.md`. summary against our own
`Module.symvers`:

```text
2507 versioned imports across the 28 stock modules
13 symbols absent from our vmlinux
190 CRCs differ
many identical (module_layout, msleep, vmalloc, cancel_work_sync,
               get_firmware_data, vdec_is_support_4k, system_wq, _mcount)
```

the identical ones are the strongest positive evidence in the whole project
that McMCCRU is genuinely close to the stock kernel in the areas these
modules touch. the differing ones cluster in two places:

1. **config-derived** (`kmalloc_caches`, `dev_err`, `__platform_driver_register`):
   genksyms CRCs hash declared types, and these prototypes depend on config.
   closable in principle.
2. **genuinely different source** — the Amlogic media symbols:
   `amvdec_suspend`, `amvdec_resume`, `vdec_enable_DMC`, `vdec_count_info`,
   `amports_get_dma_device`, `vf_reg_provider`, `vf_unreg_provider`,
   `create_ge2d_work_queue`, `stretchblt_noalpha`. these are the video
   decoder calling into the kernel's built-in media stack, and their CRCs
   moving means the exported types differ. no config change fixes that.
   corroboration: `AMLOGIC_VIDEOSYNC` has to be forced `y` to link at all.

**our own 10 modules are self-consistent** — `wifi_dummy.ko`, `ddr_window.ko`,
`amvdec_ports.ko` etc. all resolve against our `Module.symvers` with zero
missing symbols, which is what a working build should look like. it is only
the cross-comparison against Xiaomi's build that fails.

## version strings

| | device | ours |
|---|---|---|
| `uname -r` | `4.9.113` | `4.9.113` |
| `uname -v` | `#1 SMP PREEMPT Tue Sep 6 12:53:43 CST 2022` | `#1 SMP PREEMPT` (no date/host) |
| module vermagic | `4.9.y SMP preempt mod_unload modversions aarch64` | **identical** |
| `LOCALVERSION` | `""` | `""` |
| compiler | Linaro 6.3.1 20170109 | **identical** |

the vermagic match is exact and was not designed to be — see
`reports/vendor-modules.md` §2, the Amlogic tree flattens the stamp to
`<major>.<minor>.y` on purpose, so this is expected rather than lucky.
`uname -v` differs because the build environment string is not set here;
cosmetic, and it can be matched with `KBUILD_BUILD_*` if it ever matters.

## classification of every difference

| # | difference | class | note |
|---|---|---|---|
| 1 | Image 26.0 MiB vs stock ~9.3 MiB | **unknown** | 2.8×. unknown cause, largest single gap |
| 2 | `AMLOGIC_DVB=n` vs device `y` | **blocking** | HEAD commit does not compile, §7 |
| 3 | 190 CRC diffs, of which the Amlogic media set | **blocking** | different source, no config fix |
| 4 | 13 missing symbols (W1 Wi-Fi, pstore compression) | **blocking** | tree lacks the code entirely |
| 5 | `HZ=250` vs 300 | expected | never applied, 3-line fix |
| 6 | `CC_STACKPROTECTOR_NONE` vs STRONG | expected | never applied, 1-line fix |
| 7 | `PANIC_TIMEOUT=5` vs 1 | expected | never applied, 1-line fix |
| 8 | 19 `AMLOGIC_MEDIA_VDEC_*` built in vs modules | expected | device moved decode to modules, §5 |
| 9 | `AMLOGIC_VIDEOSYNC=y` | known | build-required, device has no such option |
| 10 | `AMLOGIC_MEDIA_VDEC_VP9=n` | known | build-required, device has no VP9 |
| 11 | TL1 pinctrl / TL1 acodec / TAS5805 | known | different chip, correctly excluded on the device |
| 12 | `EXFAT_FS`, `NTFS_FS`, `SLABINFO`, `SLUB_DEBUG` | known | meson64 extras |
| 13 | 31 `USB_*` + `KSM`, `HID_APPLE`, `NLS_UTF8`, `CRYPTO_LZ4`, `PSTORE_FTRACE` | known | TV profile absent from every defconfig |
| 14 | 7 only-A (`AMLOGIC_DEBUG_ATRACE`, `AMLOGIC_WATCHPOINT`, …) | known | device-only debug features |
| 15 | `uname -v` lacks build date/host | expected | cosmetic |
| 16 | dtb is `gxl_p241_1g`, not aquaman | **blocking for a real boot** | **OBSOLETE as stated.** the aquaman DTB was recovered from RAM at `0x01000000`, see `aquaman-dtb-extraction.md` and `artifacts/aquaman.dtb`. this row is now "we ship the wrong dtb and the right one exists", not "we have no way to get it". the vendor's .dts source is still unavailable and `dt.img` is still encrypted |

## 5. the VDEC built-ins are dead weight, and now provably so

`kernel-baseline.md` §unknowns.1 asks where the stock kernel's video decode
comes from. answered: from the 14 `amvdec_*.ko` modules, extracted this
session from `vendor.new.dat.br` with no root and no device
(`reports/vendor-modules.md`).

so the 19 `AMLOGIC_MEDIA_VDEC_*` / `VENC_*` options that meson64 enables and
the device does not are not a mystery and not a Xiaomi removal. the device
simply does not build decoders into the kernel at all. our baseline does, which
is both a fidelity difference and, given the 2.8× size gap, a plausible
contributor to it. switching them off would be a small, well-understood
improvement. not done this session, for the comparability reason in §2.

## 6. verdict

```text
BUILD:    PASS  (Image + dtb + modules, valid ARM64, reproducible from a script)
CONFIG:   98.10% match, 3 deltas known-not-applied, 1 new blocking delta
SYMBOLS:  not usable with the stock .ko set (190 CRCs, 13 missing)
KERNEL:   NOT a reproduction. an approximation with a documented, quantified gap.
```

"the kernel builds" is not "the kernel is reproduced", and the gap is
specifically: wrong DTB, no DVB module, a media stack whose exported types
differ from the stock one, and 2.8× the stock size.

## 7. the build did not work the first time, and that matters

first run: **failed**, 15 errors, all in
`drivers/amlogic/media/stream_input/parser/hw_demux/aml_dvb.c`:

```text
error: 'CA_CW_DES_EVEN' undeclared
error: 'CA_CW_SM4_EVEN' undeclared        (and DES_ODD, SM4_ODD, *_IV)
error: 'struct ca_descr_ex' has no member named 'mode'
error: 'CA_DSC_IDSA' undeclared
```

those symbols are supposed to come from `include/uapi/linux/dvb/ca.h`, and
that header does have a `CONFIG_AMLOGIC_DVB_COMPAT` block — but inside it
`enum ca_cw_type` has only 6 values and `struct ca_descr_ex` has no `mode`.
the driver is written against a **newer dvb-ca API** than this kernel tree
provides. `-DCONFIG_AMLOGIC_DVB_COMPAT` does not help; the values are simply
not in the header.

root cause: commit `3d4ab79e "Update hw decode drivers."` — the tip of
McMCCRU — backported the DVB/CAM **driver** without the **UAPI** it depends
on. **McMCCRU HEAD does not compile.**

the only ways forward:

1. write the missing enum values and the `mode` member into a public UAPI
   struct with no ground truth for the correct values → inventing. rejected.
2. `CONFIG_AMLOGIC_DVB=n` → chosen. costs the DVB demux/CAM module, which is a
   module and irrelevant to booting.
3. build McMCCRU's parent commit `17cef223` (2019-06-04), which predates the
   broken backport. not tried; would lose the hw decode driver updates.
4. find an Amlogic tree that has the matching UAPI. not searched.

**this also invalidates the "baseline compiles" claim in
`kernel-build-env.md` and `kernel-smoke-test.md`.** the tree those reports were
built from no longer exists, and demonstrably was not a tree where
`3d4ab79e` compiled — `build-aq/` contained a `vmlinux` with a
`built-in.o` of 8 bytes (empty) for `hw_demux`, which is what a partial or
interrupted build leaves behind. the previous session's clone had a
`fetch-pack: unexpected disconnect` in its log.

so: the earlier "compiles, EXIT=0, 26 MB" is not reproducible, and the reason
is a real defect in the upstream tip, not a local environment problem.
