# kernel-build-env — reproducible 4.9.113 build environment

> **rewritten, 2026-09-29.** Two items on this page were incorrect:
> 1. Ephemeral `/tmp/` paths no longer exist. `/tmp` is tmpfs and the
>    prior session state was lost. Source trees were re-cloned into `.src/`
>    (gitignored), which is the permanent local location.
> 2. **"baseline compiles, EXIT=0" is no longer true as originally stated.** `3d4ab79e` does
>    not compile out of the box. See the "McMCCRU HEAD does not compile" section below. The residual
>    `build-aq/` had an 8-byte (empty) `built-in.o` in `hw_demux`, which is
>    the signature of an interrupted build, not a successful one.
>
> The reproducible script is now `tools/build_aquaman_kernel.sh`, which
> validates commit, sublevel, toolchain, and artifacts. Use it instead of the manual
> commands on this page. Report: `reports/rebuilt-kernel.md`.

## trees (read-only, none modified)

| role | path | version | HEAD |
|---|---|---|---|
| ancestor base | `.src/linux-amlogic` | 4.9.113 | 3d4ab79e 2019-06-27 |
| official Xiaomi ref (different device) | `.src/MiTV_OpenSource` (branch dangal-p-oss) | 4.9.113 | 2019-07-11 |
| U-Boot 2015.01 ref (family) | `.src/u-boot-khadas` (khadas-vims-nougat) | 2015.01 | 4c6694f |
| toolchain | `.src/MiTV_OpenSource/cross_compile_tool` | Linaro 6.3-2017.02, gcc 6.3.1 20170109 | — |

Previously placed in ephemeral `/tmp/` directories. Being tmpfs, they disappear upon reboot, and earlier commands broke. The three trees above were re-cloned during this session from the exact commits; `linux-amlogic` has a clean `git status`, **zero patches** — all build deltas live in `.config`, not the tree.

gcc 6.3.1 matches the stock build banner precisely (`jenkins@c5-mitv-cm-build06.bj`, gcc Linaro 6.3-2017.02). No global toolchain installed; `CROSS_COMPILE` points to the vendored binary. System `dtc` 1.7.2 is used for inspection only; the build uses the in-tree `scripts/dtc`.

## objdir (out of tree)

`./build-aq/` (gitignored). Built with `O=`, sources untouched:

```sh
sh tools/build_aquaman_kernel.sh          # validates, configures, compiles, validates artifacts
sh tools/build_aquaman_kernel.sh --clean  # starts from scratch
```

The script is the canonical workflow. It verifies dependencies, checks the exact commit (`3d4ab79ea3638850a736bf2f7f65e55cb47368c4`) and `SUBLEVEL=113`, applies the 3 config deltas, executes `olddefconfig`, compiles `Image dtbs modules`, and finishes with `tools/validate_artifacts.py`. No `sudo`, no network, no `|| true` — failures are fatal by design; in research builds hiding errors is worse than not building. Logs in `out/build-logs/`.

## two environment fixes (outside kernel tree, documented)

1. `HOSTCFLAGS="-fcommon"`: 4.9 dtc does not link with host gcc ≥ 10 (`multiple definition of yylloc`). Command-line flag, zero patches.
2. symlink created in vendored toolchain (research copy, not upstream): `cross_compile_tool/libexec/gcc/aarch64-linux-gnu/6.3.1/liblto_plugin.so -> liblto_plugin.so.0.0.0`. The gcc driver looks for `liblto_plugin.so` during vdso linking, and the archive lacked this symlink. Without it: `fatal error: -fuse-linker-plugin, but liblto_plugin.so not found`. The script creates this automatically, idempotently.

## McMCCRU HEAD does not compile

`3d4ab79e "Update hw decode drivers."` backported the DVB/CAM driver without the UAPI headers it requires. 15 errors in `drivers/amlogic/media/stream_input/parser/hw_demux/aml_dvb.c`:

```text
error: 'CA_CW_DES_EVEN' undeclared      (and CA_CW_DES_ODD, CA_CW_SM4_*)
error: 'struct ca_descr_ex' has no member named 'mode'
error: 'CA_DSC_IDSA' undeclared
```

These symbols should originate from `include/uapi/linux/dvb/ca.h`, which contains a `CONFIG_AMLOGIC_DVB_COMPAT` block — but inside it `enum ca_cw_type` only has 6 values and `struct ca_descr_ex` lacks `mode`. `-DCONFIG_AMLOGIC_DVB_COMPAT` does not fix it: the values simply do not exist in the header.

Options considered, and selection:

1. Write missing values into a public UAPI struct without ground truth → fabrication. **Rejected.**
2. `CONFIG_AMLOGIC_DVB=n` → **Selected.** Omits the demux/CAM module, which is an optional module irrelevant to booting.
3. Build parent commit `17cef223` (2019-06-04), before the broken backport.
4. Find an Amlogic tree with matching UAPI.

Total of 3 deltas, all in `.config`:

| delta | direction | reason |
|---|---|---|
| `AMLOGIC_MEDIA_VDEC_VP9=n` | toward device | does not compile on tip (`gvs` undeclared) |
| `AMLOGIC_VIDEOSYNC=y` | against device | `video_sink/video.c:6566` calls without `#ifdef`; link fails |
| `AMLOGIC_DVB=n` | **against device** | HEAD does not compile. Device has `=y` |

## result (re-verified 2026-09-29)

`build-aq/arch/arm64/boot/Image`, 27308544 bytes (26.0 MiB), `4.9.113`, ELF via Linaro 6.3.1, valid ARM64 header (`magic 0x644d5241 @0x38`, `text_offset 0x1080000`, `image_size 0x1bef000`), 1 DTB (`gxl_p241_1g.dtb`), 10 `.ko`, 10150 exports in `Module.symvers`. `EXIT=0`, zero compilation errors.

config: 98.10% match with `aquaman-config`. The `.config` generated from scratch is byte-for-byte identical to the objdir, except for the 3 deltas above — meaning the build is truly reproducible. Details and full list of differences in `reports/rebuilt-kernel.md`.

## caveats

- `/tmp` is tmpfs (7.7 GB): ~3 GB objdir exhausted disk space mid-link (`final link failed: No space left`). Objdir lives in `build-aq/`, and source trees in `.src/`, both outside tmpfs.
- `.config` has 3 deviations from expanded `meson64_defconfig`, listed above.
