# repo-state — audit of the repo as found, 2026-09-29

technical map, not a summary of the README. everything here was verified
against the files, the git history, or a run in this session. where a prior
report contradicts what is in the repo, both are listed and the newer
evidence wins.

## files

```text
aquaman-config              146 KB  kernel config extracted from the device (4447 opts)
firmware/                   boot.img, bootloader.img, dt.img, dtbo.img, vbmeta.img + SHA256SUMS.txt
firmware/bootloader.img     1.3 MB  encrypted, entropy 7.9999, zero strings
firmware/dt.img             59 KB   encrypted DTB payload (no d00dfeed magic)
boot_unpack/ patched_unpack/ recovery_unpack/   unpacked boot/magisk/recovery
*.new.dat.br                OTA sparse-data for system/vendor/product/odm + transfer lists
out/                        ghostlock C binaries, asm dumps, logs
out/vendor/                 NEW: reassembled vendor partition + the 28 .ko
src/                        EMPTY. was where the source was meant to live
build-aq/                   objdir, gitignored. held a vmlinux/Image from a tree that no longer exists
tools/                      17 scripts, mostly ghostlock C plus the boot/fastboot parsers
reports/                    40 reports
```

### tools that exist and work

| tool | what it does | state |
|---|---|---|
| `analyze_android_boot.py` | boot image header dump | works |
| `parse_amlsecu.py` | AMLSECU 0x0905 header parse, offline | works |
| `config_fingerprint.py` | config union/match/only/differ, `--rank` | works, used this session |
| `inspect_test_image.py` | simulates bootm's validators on a test image offline | works, **its `X_DEFAULT` comment is now corrected but the khadas `X_REF` is still hardcoded** |
| `fastboot_probe.py` | read-only fastboot getvar/oem | works, device-side only |
| `fb_raw.py` | raw fastboot wire bytes via pyusb | works, device-side only |
| `mk_m1_boot.py` | builds the ANDROID! delay-stub images | works |
| `dwarf_offsets.py`, `ghostlock_*.c` | ghostlock tooling | work, out of scope this session |
| `sdat2img.py` | **NEW** reassembles a partition from `.new.dat` + `.transfer.list` | works, verified byte-exact on vendor |
| `ko_inventory.py` | **NEW** modinfo + ELF arch + srcversion per `.ko` | works |
| `ko_versions.py` | **NEW** parses `__versions` CRCs, diffs vs `Module.symvers` | works |
| `fastboot_addr.py` | **NEW** inverts `ddr_size_usable` for the fastboot buffer address | works |
| `validate_artifacts.py` | **NEW** checks Image/vmlinux/dtb/modules after a build | works |
| `build_aquaman_kernel.sh` | **NEW** the reproducible build | see below |

## kernel source, exact commit

```text
McMCCRU/linux-amlogic
  HEAD  3d4ab79ea3638850a736bf2f7f65e55cb47368c4  "Update hw decode drivers."
  date  2019-06-27
  tree  shallow clone (--depth 1), 8 commits in the real history, root 17cef223 2019-06-04
  Makefile  VERSION=4 PATCHLEVEL=9 SUBLEVEL=113 NAME=Roaring Lionus
  configs  arch/arm64/configs/{defconfig,meson64_defconfig,meson64_smarthome_defconfig,ranchu64_defconfig}
```

cloned this session into `.src/linux-amlogic`. `git status` clean, **zero
patches applied to the tree**. all build deltas live in the `.config`.

classification unchanged and still correct: **ANCESTRAL, not the exact
source**. no aquaman strings, no aquaman DTS, three years older than the
2022-09-06 build. `reports/provenance.md` and `reports/exact-source.txt`
stand.

reference trees also cloned this session, read-only, for the fastboot work:

```text
MiCode/MiTV_OpenSource @ dangal-p-oss  (Xiaomi official, wrong device, carries the toolchain)
khadas/u-boot @ khadas-vims-nougat     4c6694f, U-Boot 2015.01, Amlogic GXL
```

## toolchain

```text
.src/MiTV_OpenSource/cross_compile_tool
  aarch64-linux-gnu-gcc (Linaro GCC 6.3-2017.02) 6.3.1 20170109
```

this is the exact gcc in the stock build string. no global cross toolchain is
installed and none is needed. the build script creates the one missing
`liblto_plugin.so` symlink inside the vendored copy (research clone, not
upstream). host `dtc` 1.7.2 is used only for inspection, never in the build.

## config, and the baseline

`aquaman-config` is the device's own expanded config, 4447 options. the
baseline is `meson64_defconfig` from McMCCRU, expanded, plus 3 deltas.

comparison reproduced this session with `tools/config_fingerprint.py`:

```text
aquaman-config vs meson64_defconfig (raw, unextended):
  union 4447  match 625  differ 6  only-A 3816  only-B 0   → 14.05%

build-aq/.config (expanded) vs aquaman-config:
  → 98.12% match, 48 differ, 7 only-A, 29 only-B
```

the 14.05% is the honest number for the raw defconfig (a defconfig is a
minimum, the device config is fully expanded). the 98.12% is the meaningful
one. both were re-derived and both reproduce. `reports/kernel-baseline.md`
is accurate.

### the three build deltas, and why there are three now

| delta | direction | reason |
|---|---|---|
| `AMLOGIC_MEDIA_VDEC_VP9=n` | toward device | `gvs` undeclared at vvp9.c:6894/7820. does not compile at this tip. device has no VP9 either |
| `AMLOGIC_VIDEOSYNC=y` | away from device | `video_sink/video.c:6566` calls `videosync_pcrscr_update` with no `#ifdef`; link fails without it. device has neither — Xiaomi reorganised the media Kconfig |
| `AMLOGIC_DVB=n` | **away from device, new** | see below |

the third one is new and it is the most important finding of this audit.

**McMCCRU HEAD does not compile.** the last commit, `3d4ab79e "Update hw
decode drivers."`, backported the DVB/CAM *driver* side without the *UAPI* it
depends on. `drivers/amlogic/media/stream_input/parser/hw_demux/aml_dvb.c`
uses `CA_CW_DES_EVEN`, `CA_CW_DES_ODD`, `CA_CW_SM4_EVEN/ODD/EVEN_IV/ODD_IV`,
`CA_DSC_IDSA`, and a `mode` member on `struct ca_descr_ex`. none of those
exist in this tree's `include/uapi/linux/dvb/ca.h`. the `enum ca_cw_type` in
the header has only 6 values and `struct ca_descr_ex` has no `mode`, and the
whole block sits behind `#ifdef CONFIG_AMLOGIC_DVB_COMPAT`, which
`aml_dvb.h` reaches via a direct `#include <linux/dvb/ca.h>` that never sees
`autoconf.h`.

a `-DCONFIG_AMLOGIC_DVB_COMPAT` on the command line does **not** fix it: the
enum values and the struct member are absent from the header even inside that
guard. fixing it properly means writing values into a public UAPI struct
without any ground truth for what they should be. that is inventing, so it
was not done. the module is dropped instead.

this is a real regression in McMCCRU HEAD, and it means:

- the earlier "baseline compiles, Image 26 MB" claim was made against a tree
  that no longer exists and that was demonstrably not this commit;
- `CONFIG_AMLOGIC_DVB=y` is **not** achievable from this tree. the device has
  it. so this baseline is one more config option away from the device than the
  previous one, in a subsystem (DVB demux / CAM descrambling) that is a
  module and irrelevant to booting;
- anyone who wants the DVB demux module must take McMCCRU's parent commit
  (`17cef223`) or a newer Amlogic tree that carries the matching UAPI.

## firmware artifacts

| artifact | what it is | usable |
|---|---|---|
| `boot.img` 16 MiB | stock boot, **AMLSECU 0x0905 encrypted**, 3 blocks, entropy ~8.0 | no, key missing |
| `recovery.img` 25 MiB | same scheme, different payload | no |
| `bootloader.img` 1.3 MB | encrypted, zero strings | no |
| `dt.img` 59 KB | encrypted DTB payload, **the board DTB is in here** | no |
| `dtbo.img` 8 MiB | valid Android sparse header but 320 bytes non-zero in 8 MiB; empty overlay | effectively no |
| `vbmeta.img` 4 KB | AVB, locked as far as we know | no |
| `*.new.dat.br` | **system/vendor/product/odm sparse data + transfer lists** | **YES — this is where the real content is** |

the last row is the one the repo had been missing. `vendor.new.dat.br` alone
contained the 28 vendor kernel modules, extractable with no root, no device
and no network. see `reports/vendor-modules.md`.

## what is proven

1. the device is a Xiaomi Mi TV Stick 1080p, `aquaman` / PI.2055 / MiTV-AESP0,
   S805Y on GXL, 1 GiB, Android 9, kernel 4.9.113 built 2022-09-06
   12:53:43 CST by `jenkins@c5-mitv-cm-build06.bj` with Linaro 6.3.1-2017.02.
2. no exact public source exists. McMCCRU is ancestral. GPL request
   (MiBox_Kernel_OpenSource#11) open since 2025-01.
3. the baseline compiles and produces a valid ARM64 `Image`
   (see `reports/rebuilt-kernel.md` for this session's numbers).
4. the fastboot memory flow is mapped end to end
   (`reports/fastboot-memory-flow.md`).
5. `fastboot boot` does not execute unsigned payloads on this build, because
   BL31 is secure-fused and `aml_sec_boot_check` rejects them before any
   format check (`fastboot-memory-flow.md` §6, from E1-E8).
6. the download buffer overlaps the address `bootm` reads (E5 vs E6). the
   exact value is not provable from an encrypted U-Boot.
7. video decode, encode, GPU, Wi-Fi, Bluetooth and the Amlogic DVB demux are
   **vendor modules**; HDMI, CEC and audio are built-in. 28 `.ko`, extracted
   (`reports/vendor-modules.md`).
8. the vendor modules carry `vermagic 4.9.y`. **this is this tree's own
   doing, not a provenance clue**: `Makefile:1221` replaces the module version
   stamp with `<major>.<minor>.y` so modules do not pin the sublevel. got this
   wrong on the first pass and the repo's own build disproved it — see
   `reports/vendor-modules.md` §2. `ddr_window_64.ko` really is foreign
   (`3.14.29`).
9. the vendor modules will not load on a kernel built from McMCCRU: 13
   symbols missing, 190 CRCs differ.

## what is still hypothesis

1. **which of the 190 CRC differences are config-derived and which are
   different source.** not measured per-symbol. the config-derived ones could
   in principle be closed by matching the device config exactly; the Amlogic
   media symbol ones cannot. 190 is an upper bound on what config could
   recover.
2. the true `CONFIG_USB_FASTBOOT_BUF_ADDR` and `loadaddr` on this build. the
   reference tree's values are the best guess; `bootloader.img` is encrypted.
3. the aquaman DTS. sealed in `dt.img`. the port map is written
   (`reports/aquaman-dts-port.md`) but a dozen nodes are TODO.
4. the AMLSECU packing format and the `aml-user-key.sig`. parser understood,
   packer closed, key never published.
5. everything in the GhostLock track. dispatch and rollback reached on device,
   exploitability not demonstrated, and the 2026-09-29 commit says
   "dead end documented, six panics for nothing".

## blockers, ranked

1. **BL31 rejects unsigned images.** every RAM-only path funnels through
   `do_bootm` → SMC. `booti` and `go` are not compiled in (E8). this blocks
   execution, and it is the reason to stop spending time on address hunting.
2. **no exact source.** so no exact config, no exact DTS, and — as just
   measured — no CRC-compatible kernel.
3. **the board DTB is encrypted.** without it the DTS port cannot be finished.
4. **`/proc/device-tree` has never been read off the stock device.** this is the
   cheapest untried thing on the list and it would replace half the DTS TODO
   column with ground truth. read-only, probably no root needed.

## reproducibility notes

the three source trees live in `.src/` (gitignored), not `/tmp`. `/tmp` is
tmpfs and the previous session's clones did not survive; the references to
temporary `/tmp/` paths in older reports were stale paths. the three that mattered
for building are fixed in `reports/kernel-build-env.md`:
`.src/linux-amlogic` (3d4ab79e), `.src/MiTV_OpenSource` (dangal-p-oss,
carries the Linaro toolchain), `.src/u-boot-khadas` (khadas-vims-nougat,
for the fastboot work). `reports/bootm-test-image.md` and
`reports/aquaman-dts-port.md` also got their paths corrected.

test suite: `python3 tools/run_tests.py`, 32 tests, no network, no device.
`tools/build_aquaman_kernel.sh` regenerates everything from a clean tree and
ends in `tools/validate_artifacts.py`.

## GhostLock, deliberately untouched

the exploit track was left alone this session, per the task rules. the last
commit in this repo calls it a dead end ("six panics for nothing"). two
things worth carrying into it, both found incidentally here:

- `pstore_io_save` is missing from the rebuilt kernel, so a custom kernel
  could not write compressed pstore records even with root. that weakens the
  post-mortem plan in `ghostlock-risk.md` step 2, which assumes pstore is
  usable for diagnosis.
- the W1 Wi-Fi symbols are missing from the tree entirely, which is a separate
  gap from the missing `amvdec_*` CRCs and needs the same treatment.

## contradictions found between old and new reports

listed, not fixed. the task said to enumerate first.

| # | file | claim | status |
|---|---|---|---|
| 1 | `amlsecu-open-questions.md` §9 | "4096-byte plaintext boot.img was **accepted** via fastboot boot, executed the stub, returned to Android in ~30s" — labelled CONFIRMED | **WRONG.** revoked by `fastboot-boot-verdict.md` (M1a returned in 16-21 s with no delay = rejection). the same file's §10 builds on it, so §10 is wrong too |
| 2 | `amlsecu-open-questions.md` §10 | "the real blocker is not AMLSECU packaging... what is missing is a functional kernel/DTB" | **superseded.** `buffer-equals-loadaddr-proof.md` shows BL31 is the blocker |
| 3 | `bootm-test-image.md` §0, `bootm-buffer-execution-proof.md` | `X = 0x10200000` from khadas `include/g_dnl.h:18` | **REFUTED as a device fact.** never measured on this build. `inspect_test_image.py` already has a corrected comment; `bootm-test-image.md` still states it as fact |
| 4 | `fastboot-boot-verdict.md` §root cause | "`max-download-size` 0x08000000 is incompatible with buffer at 0x1080000, which would leave ~900 MB free" | **ARITHMETICALLY VOID.** see below |
| 5 | `bootm-buffer-execution-proof.md` | whole file, "status: PENDING", template not filled | **superseded** by `buffer-equals-loadaddr-proof.md`, which ran the experiment. leaving an unfilled template next to a completed one is a trap |
| 6 | `vendor-module-compat.md` | "extraction blocked... requires root" | **WRONG.** the modules are in the OTA dumps in this repo |
| 7 | `kernel-build-env.md` | "baseline compiles, EXIT=0" | **no longer true at HEAD.** `3d4ab79e` does not compile; see the `AMLOGIC_DVB` delta |
| 8 | `kernel-baseline.md` §unknowns.1 | "video decode in stock is unknown (vendor modules?)" | **answered**, yes, 14 `.ko`. `reports/vendor-modules.md` |

on #4 specifically, because it is the one that carried a root cause:

```text
ddr_size_usable(addr) = DRAM - 16M - addr - 64M - 128M

BUF=0x10200000  →  max-download-size 0x22E00000 (558 MiB)
BUF=0x01080000  →  max-download-size 0x31F80000 (799 MiB)
device reported  →  0x08000000         (128 MiB)
```

the reported number is produced by neither candidate. inverting gives
`BUF = 0x2B000000`, which is neither. so the number cannot discriminate
between the two hypotheses it was cited for, and the root cause built on it
was unfounded. `reports/fastboot-memory-flow.md` §3 works this through.
reproduce with `python3 tools/fastboot_addr.py`.
