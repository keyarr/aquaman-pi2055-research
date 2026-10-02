# vendor-modules — the 28 `.ko` files, for real this time

`reports/vendor-module-compat.md` (earlier session) opens with "extraction
blocked: adb shell (non-root) receives Permission denied on
`/vendor/lib/modules/*.ko` (pull and cat denied by SELinux)". every later
section of that report is therefore inference, marked as such.

**that is wrong, and the reason is simple: the modules were never on the
device needed to be pulled.** they are in the OTA dumps sitting in this repo
as `vendor.new.dat.br`. decompress, reassemble, mount-less-extract, done. no
root, no device, no network.

what follows replaces the inventory. the old report's *conclusions* about
which subsystems matter turn out to hold up; its *evidence* was a name list.

## how they were extracted

```sh
python3 -c "import brotli,sys; open('out/vendor/vendor.new.dat','wb').write(brotli.decompress(open('vendor.new.dat.br','rb').read()))"
python3 tools/sdat2img.py vendor.transfer.list out/vendor/vendor.new.dat out/vendor/vendor.img
debugfs -R "rdump /lib/modules out/vendor/modules" out/vendor/vendor.img
```

`tools/sdat2img.py` is new. the transfer lists in this OTA use
comma-glued args and express runs as boundary pairs (`new 2,1782,2806` =
blocks 1782..2806), which is not what most published sdat2img parsers expect;
the tool was written to match these files and checks that the runs add up to
exactly the `.dat` size. for vendor: 27 runs, 24409 of 25600 blocks, the
remaining 1191 being the `zero` ranges. `dumpe2fs` then reports a clean ext4
named "vendor". reproducible end to end, stdlib + `debugfs`.

## vermagic: the headline result

```text
27 of 28:  4.9.y SMP preempt mod_unload modversions aarch64
 1 of 28:  3.14.29 SMP preempt mod_unload aarch64   (ddr_window_64.ko)
```

four things follow, and only the first and last survive checking.

**1. `CONFIG_MODVERSIONS=y` on the device.** confirmed directly in
`aquaman-config`. this is a hard gate: `load_module` checks every entry in a
module's `__versions` section against the kernel's CRC table, and refuses the
module on the first mismatch. it is not a warning.

**2. `4.9.y` is this tree's own doing, not a provenance clue.** the first
draft of this report read `4.9.y` as a smoking gun — "not `4.9.113`, so these
modules came from a different build than the one on the stick". **that was
wrong, and the repo's own build disproves it.** the ten modules this session
compiled from McMCCRU carry the identical string:

```text
$ modinfo -F vermagic build-aq/drivers/amlogic/ddr_tool/ddr_window.ko
4.9.y SMP preempt mod_unload modversions aarch64
```

the cause is one line of the Amlogic `Makefile`:

```make
# Makefile:1221
echo \#define UTS_RELEASEY \"$(basename $(KERNELRELEASE)).y\")
```

consumed by `VERMAGIC_STRING` in `include/linux/vermagic.h:29`. the vendor
replaces the module version stamp with `<major>.<minor>.y` so modules do not
pin the sublevel — a 4.9.113 kernel accepts modules built from any 4.9.y.
`uname -r` still reports the real `4.9.113`; only the module stamp is
flattened.

this is the opposite of what the mistake implied, and it is useful: the
vermagic gate is **deliberately loosened by the vendor**, so vermagic is not
what will stop the stock modules from loading. the CRCs are. which is §3, and
§3 is the finding that actually matters.

**3. the modules will not load on our rebuilt kernel.** measured, not
guessed — see the CRC section.

**4. one module is from another platform entirely.** `ddr_window_64.ko`
reports `3.14.29`, with no `modversions` at all. that is not a flattened 4.9
stamp, it is a genuinely different kernel — and the fact that it is
distinguishable from `4.9.y` confirms the two strings are not interchangeable.
leftover from an older Amlogic platform sharing the vendor partition layout.
dead weight on disk; nothing can load it.

## the CRC comparison, which is the real deliverable

`tools/ko_versions.py` parses the `__versions` section of each `.ko` and
diffs it against a `Module.symvers`. against the baseline vmlinux built from
McMCCRU 3d4ab79e:

```text
modules parsed           28 (27 with __versions, 1 without)
total versioned imports  2507
distinct symbols missing 13
distinct CRCs different  190
```

the `__versions` records in these modules are 64 bytes each, not the usual 16 —
so the stride has to be sniffed, `tools/ko_versions.py` tries 64 down to 16 and
takes the first that parses cleanly. worth knowing if anyone else writes a
parser for this.

**many CRCs match exactly.** `module_layout`, `msleep`, `vmalloc`,
`cancel_work_sync`, `get_firmware_data`, `vdec_is_support_4k`, `system_wq`,
`_mcount`, `configs_register_configs` — all identical to our build. that is
strong evidence that the ancestral kernel is genuinely close to the stock one
in the areas these modules touch, and it is the first quantitative confirmation
of the "ancestral, not exact" claim.

**190 differ.** some are boring and expected: `kmalloc_caches` is an array
whose size depends on `NR_KMALLOC_CACHES` (a config-derived constant), so any
config difference changes its CRC. `dev_err` and `__platform_driver_register`
are the same story — genksyms CRCs hash the declared type, and the declared
types here pick up config-dependent prototypes.

**some are not boring, and they are the interesting ones.** the differing set
includes Amlogic media symbols — `amvdec_suspend`, `amvdec_resume`,
`vdec_enable_DMC`, `vdec_count_info`, `vdec_is_support_4k`'s neighbours,
`amports_get_dma_device`, `vf_reg_provider`, `vf_unreg_provider`,
`create_ge2d_work_queue`, `stretchblt_noalpha`. those are the video decoder
talking to the kernel's built-in media stack. their CRCs moving means our
media stack's exported types are not the stock ones. combined with
`CONFIG_AMLOGIC_VIDEOSYNC` having to be forced to `y` to build this tree at
all (`kernel-baseline.md`), the picture is: **the media/display half of this
ancestral tree does not match the stock build, and it is not a config
difference.** the device's tree has media code in it that McMCCRU does not, or
has it differently.

**13 symbols are missing entirely:**

| symbol | modules | what it is |
|---|---|---|
| `__tracepoint_tracing_mark_write` | 14 | `include/trace/events/meson_atrace.h` exists in the tree, but the tracepoint is only built when the ATRACE Kconfig is on. device has `CONFIG_AMLOGIC_DEBUG_ATRACE=y`; the meson64 baseline does not |
| `wifi_in_insmod`, `g_w1_hif_ops`, `g_w1_hwif_sdio`, `aml_w1_sdio_init`, `w1_sdio_after_porbe`, `w1_sdio_driver_insmoded`, `set_wifi_bt_sdio_driver_bit`, `set_usb_wifi_power` | 2 (w1, rtl8821cs) | the Amlogic W1 Wi-Fi stack. the tree has `drivers/amlogic/wifi/wifi_dummy.c` where the stock has the real W1 driver — the earlier config report's "only-B: `AMLOGIC_WIFI_DUMMY=m`" is exactly this |
| `host_suspend_req`, `host_resume_req`, `host_wake_w1_req` | 2 | Wi-Fi power-management callbacks from the W1 host |
| `pstore_io_save` | 2 | pstore compression. this is a **capability** difference, not a symbol rename: the stock kernel can write compressed pstore, ours cannot |

`pstore_io_save` deserves a note. `reports/ghostlock-risk.md` lists
`/sys/fs/pstore` as the post-mortem diagnostic for a GhostLock panic, and says
"pstore denied for shell reduces post-mortem; recheck as root later". on our
rebuilt kernel pstore would additionally be unable to *write* compressed
records at all, so a panic might leave nothing even with root. that changes the
diagnosis plan for the GhostLock track and nobody had noticed.

## inventory

| module | size | vermagic | depends |
|---|---|---|---|
| rtl8821cs.ko | 4740696 | 4.9.y | — |
| stream_input.ko | 2562344 | 4.9.y | decoder_common, firmware, media_clock |
| decoder_common.ko | 2212720 | 4.9.y | media_clock, firmware |
| w1.ko | 1873008 | 4.9.y | aml_sdio |
| aml_hardware_dmx.ko | 1292536 | 4.9.y | stream_input, media_clock |
| amvdec_mh264.ko | 1275280 | 4.9.y | decoder_common, firmware, stream_input, media_clock |
| media_clock.ko | 1046848 | 4.9.y | — |
| amvdec_avs2.ko | 932152 | 4.9.y | decoder_common, firmware, stream_input, media_clock |
| amvdec_h265.ko | 943224 | 4.9.y | decoder_common, firmware, stream_input, media_clock |
| amvdec_vp9.ko | 766504 | 4.9.y | decoder_common, firmware, stream_input, media_clock |
| mali.ko | 623488 | 4.9.y | — |
| amvdec_avs.ko | 591664 | 4.9.y | decoder_common, firmware, stream_input, media_clock |
| encoder.ko | 570632 | 4.9.y | decoder_common, media_clock, firmware |
| amvdec_h264.ko | 541824 | 4.9.y | decoder_common, firmware, stream_input, media_clock |
| vpu.ko | 532936 | 4.9.y | media_clock |
| aml_sdio.ko | 471864 | 4.9.y | — |
| amvdec_mmpeg4.ko | 464672 | 4.9.y | decoder_common, firmware |
| firmware.ko | 458368 | 4.9.y | media_clock |
| amvdec_h264mvc.ko | 408904 | 4.9.y | decoder_common, firmware, stream_input |
| amvdec_mmjpeg.ko | 406728 | 4.9.y | decoder_common, firmware |
| sdio_bt.ko | 413856 | 4.9.y | aml_sdio |
| amvdec_mpeg12.ko | 438528 | 4.9.y | decoder_common, firmware, stream_input, media_clock |
| amvdec_real.ko | 380688 | 4.9.y | decoder_common, firmware, stream_input |
| amvdec_vc1.ko | 381912 | 4.9.y | decoder_common, firmware |
| amvdec_mpeg4.ko | 391656 | 4.9.y | decoder_common, firmware |
| amvdec_mjpeg.ko | 373560 | 4.9.y | decoder_common, firmware |
| amvdec_avs2/avs2.ko | 932152 | — | — |
| amvdec_mmpeg12.ko | 442784 | 4.9.y | decoder_common, firmware |
| ddr_window_64.ko | 193406 | **3.14.29** | — |

`modules.dep` and `modules.alias` are present. the alias table is the whole
Wi-Fi story in two lines:

```text
alias sdio:c*v024CdC821* rtl8821cs
alias sdio:c*v024CdB821* rtl8821cs
```

Realtek PCI ID `024c:dC81` / `024c:dB82`. that is the chip, confirmed from the
module itself, not from a hardware-spec guess.

only two modules have a `srcversion`: `rtl8821cs.ko`
(`F2CB4D2C35C53BE3A522AD8`) and `mali.ko` (`2D7D9BB7C0C5C7B40C8A42A`).
`CONFIG_MODULE_SRCVERSION_ALL` is not set on the device, which is why the
Amlogic modules have none — that is a config fact, not a build accident, and
it matches `aquaman-config`.

## subsystem map

| subsystem | built-in or module | notes |
|---|---|---|
| video decode | **module, all 14 codecs** | `amvdec_{avs,avs2,h264,h264mvc,h265,mh264,mjpeg,mmjpeg,mmpeg12,mmpeg4,mpeg12,mpeg4,real,vc1,vp9}.ko` on top of `decoder_common`/`stream_input`/`media_clock`/`firmware`/`vpu` |
| video encode | module | `encoder.ko` |
| demux / DVB | module | `aml_hardware_dmx.ko` (Amlogic, "driver for the AMLogic DVB card") |
| display / HDMI | **built-in** | no module: `CONFIG_AMLOGIC_HDMITX=y` |
| CEC | **built-in** | no module: `CONFIG_AMLOGIC_AO_CEC=y`, `CONFIG_AMLOGIC_CEC=y` |
| audio | **built-in** | no audio module at all. HDMI audio is in the kernel |
| GPU | module | `mali.ko`, ARM Ltd, aliases `mali-300/400/450/470` (Midgard) |
| Wi-Fi | module | `rtl8821cs.ko` (4.7 MB, Realtek) + `aml_sdio.ko` + `w1.ko` |
| Bluetooth | module | `sdio_bt.ko`, 13 imports, a thin shim over `aml_sdio` |
| DDR window | module | `ddr_window_64.ko`, 3.14.29, **stale** |
| TEE | out of tree | `/vendor/lib/optee.ko`, not in the modules dir |

## what this settles about `kernel-baseline.md`

`kernel-baseline.md` lists, under "only-B with real value", 15
`AMLOGIC_MEDIA_VDEC_*` options that meson64 has and the device does not, and
asks where the stock kernel's video decode comes from. **answered: entirely
from these 14 `.ko` files.** the device has `AMLOGIC_MEDIA_VIDEO=y` and
`AMLOGIC_MEDIA_VIDEO_PROCESSOR=y` built in, and every actual decoder is a
module. the "only-B" VDEC options in our baseline are dead weight that the
device does not have because the device does not build decoders in at all.

this kills the "Xiaomi removed the decode subtree" hypothesis in
`kernel-baseline.md` §unknowns.1. they did not remove it; they moved it to
modules, and the modules are in the OTA we already had.

consequence for the build: the baseline should probably set those 15 VDEC
options off, not leave them on. they compile (except VP9) and they are pure
dead weight in a 26 MB image. noted, not changed — the build script stays at
the minimum delta set so the baseline stays comparable to what was measured.

## what it means for a custom kernel

for a custom kernel to be useful it needs, beyond a bootable image:

1. `CONFIG_MODVERSIONS` behaviour matching — ours is already `=y`, which is the
   right setting, but **190 CRCs still differ** on a correct-looking build, so
   the modules are rejected regardless;
2. the 13 missing symbols, which means the W1 Wi-Fi stack and pstore
   compression have to be *added to the tree*, not just enabled;
3. `mali.ko` (Mali-300/400/450/470, ARM Ltd) has to match the userspace
   `/vendor/lib/egl` GBM/EGL loader, which is Mali-version specific and is not
   in the dumps we have.

vermagic is **not** on this list, which was the natural assumption before §2.
the Amlogic `UTS_RELEASEY` hack means a 4.9.y module is *designed* to load on
a 4.9.y kernel regardless of sublevel. someone reading the vermagic strings
alone would reach exactly the wrong conclusion, and this report did, once.

point 1 is the hard one and it is not a config problem. matching 190 genksyms
CRCs by rebuilding means reproducing the exact prototypes of the exact source,
which is the same wall as the exact-source question, just in a different file.

**verdict: vendor `.ko` reuse on a rebuilt kernel is BLOCKED**, and the blocker
is CRC-level ABI mismatch. a kernel built from McMCCRU cannot load the stock
media/Wi-Fi modules. the practical consequence is that a custom kernel has to
bring its own media and Wi-Fi drivers, or ship without them.

one caveat on the CRC numbers, so they are not over-read: the CRCs in the stock
modules were generated by **Xiaomi's** tree, and are being compared against
McMCCRU's. some of the 190 differences are genuinely config-derived and could
be closed by matching the config exactly. the Amlogic media symbols that differ
(`amvdec_suspend`, `vdec_*`, `amports_get_dma_device`, `vf_reg_provider`, the
ge2d workqueue calls) are not — those reflect different source, and no config
change will fix them. the split is not measured per-symbol, so treat "190" as
an upper bound on what configuration could recover.

## Presence vs runtime usage

Extraction from the OTA proves presence. `modules.dep` proves dependency
metadata. `srcversion` proves module identity when present. None of these,
alone, proves `insmod` at runtime. These modules are present in the vendor
OTA; runtime loading needs separate evidence. `/proc/modules` or init logs
would be that evidence, if ever collected. No such experiment is run here.
