# R1 preparation - steps 0/1 (2026-11-27)

Final state: instrumented build and matching module completed. No fire,
push, flash, USB DL, device write, source edit, report edit or commit was
made.

## Device and scope

Serial 26919800005844922, baseline OK. Only read-only `adb pull` on the device
and local writes in `out/` and `build-aq/`. `.src/linux-amlogic` still has the
same five instrumentation edits, neither edited nor reverted by this work.

## Why the first base failed

`build-aq/.config.old` (saved as `out/r1-instr/clean.config`,
`3bb7b283...72b6`, 4469 options, 98.06% match) is a pre-`olddefconfig`
artifact. It sets `CONFIG_TRACEPOINTS=y` while `TRACING` is `not set` and
`GENERIC_TRACER` has no root select. In `.src/linux-amlogic/init/Kconfig:2018`,
`TRACEPOINTS` is a promptless bool with no default, selected only by `TRACING`.
`olddefconfig` therefore dropped it and all dependent tracing options, giving
back the notrace config (97.25%, 4434 options). The Image was not relinked and
stayed at `d1406478d2256b645cd17c0a1df8104feb715eb72128a51992986c742eb24c2d`,
22,493,696 B. That config is kept as evidence only.

## Second base: live_config, make failed

`work/ksu-lkm-fix/live_config` (`65e182bebdc5e5a18f19ac593f04a30afcd428e5cd6e1c0c1430b0263c1583ac`,
146,536 B) is 100.00% identical to `aquaman-config` (4447/4447, differ=0) and
has `TRACING`, `FTRACE`, `FUNCTION_TRACER` and `TRACEPOINTS` all `=y`.
Tracing survived `olddefconfig`, but `make` failed:

```
.../frame_provider/decoder/vp9/vvp9.c:6894:3: error: 'gvs' undeclared
.../frame_provider/decoder/vp9/vvp9.c:7820:22: error: 'gvs' undeclared
make[7]: *** [.../vp9/vvp9.o] Error 1
make: *** [Makefile:152: sub-make] Error 2
```

The build script's three `sed` deltas assume a `meson64_defconfig`-derived
config. Neither `live_config` nor `aquaman-config` has a `VDEC_VP9` or
`VIDEOSYNC` line, so the `sed` expressions matched nothing. `VDEC_VP9` has
`default y` in `drivers/amlogic/media/frame_provider/Kconfig:132-134`, so
`olddefconfig` re-enabled a decoder that does not compile at this tip.

## Final base and config-only adjustment

```
cp work/ksu-lkm-fix/live_config build-aq/.config
printf '%s\n' '# CONFIG_AMLOGIC_MEDIA_VDEC_VP9 is not set' \
              'CONFIG_AMLOGIC_VIDEOSYNC=y' >> build-aq/.config
sh tools/build_aquaman_kernel.sh
sh work/r1-kexec/build.sh
```

Config after build (`build-aq/.config`,
`894288cef98d675c2d1481cd40d29b4c104912118a8cfb59259dd1ca3aedb042`):

- `CONFIG_TRACEPOINTS=y`, `CONFIG_TRACING=y`, `CONFIG_FTRACE=y`
- `CONFIG_AMLOGIC_MEDIA_VDEC_VP9` not set, `CONFIG_AMLOGIC_VIDEOSYNC=y`
- `CONFIG_AMLOGIC_DVB` not set (the script's DVB sed applied)
- fingerprint: 4460 options, 99.40%, differ=2:
  `CONFIG_AMLOGIC_DVB` (A=y B=n, deliberate script delta) and
  `CONFIG_CC_STACKPROTECTOR` (A not set, B=y; both still have
  `CONFIG_CC_STACKPROTECTOR_STRONG=y`, so this is a hidden Kconfig symbol
  written by `olddefconfig`, not a stack-protector change).
  plus 6 options only in the device config and 19 only here.

`validate_artifacts.py` passed Image magic `0x644d5241`, text_offset
`0x1080000`, image_size `0x1c47000` and vmlinux ELF. It still reports the
known, non-blocking `FAIL dtb built: 0 found` / `RESULT: FAIL`.

## Hashes and sizes, before and after

| Artifact | Before | After |
| --- | --- | --- |
| `build-aq/arch/arm64/boot/Image` | `d1406478...24c2d`, 22,493,696 B | `c9b4220d5384ad2506eb899248aadff760b9c4312b8354464012a367b964efc2`, 27,695,616 B |
| `build-aq/System.map` | `db79d751...` (`r1_mark_phys` present) | `56d1bbffd707b7022a3120ea20befdc7e8d85633961ff95296905e906b9e3752` (`r1_mark_phys` present, 1 hit) |
| `build-aq/Module.symvers` | `2c82b7a5...` (9987 exports) | `53d711903516f46c6e8950118942e381dec386f7dc0a2a7c0b9e1597b6114b75` (10142 exports) |
| `work/r1-kexec/modules/r1_kexec.ko` | `936aa4b7d0ac987dcb6104f726c2075b4e428612e2c49e90497a0bbf80bd0eae` | `202cbd513e3acd1aae74ce810170912ebad8e7251e00f6d80adb5f28d4c639f2`, 314,080 B |

Module rebuild passed: vermagic `4.9.y SMP preempt mod_unload modversions
aarch64`; all undefined symbols resolve in the new `Module.symvers` (including
the new `_mcount`, `__stack_chk_fail` and `__stack_chk_guard`, expected with
ftrace and stack protector); four helper symbols present.

## Pinned artifacts

| File | sha256 | Size |
| --- | --- | --- |
| `out/r1-device/Image.clean` | `6c30b16ee7bdc99d62c08c86ef5c2212b736e7e6dab7bfaa1b1033e86e8ca045` | 27,308,544 B |
| `out/r1-device/r1_kexec.ko.936aa4b7` | `936aa4b7d0ac987dcb6104f726c2075b4e428612e2c49e90497a0bbf80bd0eae` | 313,520 B |
| `out/r1-instr/Image.instr.c9b4220d` | `c9b4220d5384ad2506eb899248aadff760b9c4312b8354464012a367b964efc2` | 27,695,616 B |
| `out/r1-instr/r1_kexec.ko.202cbd51` | `202cbd513e3acd1aae74ce810170912ebad8e7251e00f6d80adb5f28d4c639f2` | 314,080 B |
| `out/r1-instr/notrace.config` | `7772d16cdd582a2f5f69bacdbfa02dc737d5a7e6f9681a78cac671b1e4699c4e` | 146,667 B |
| `out/r1-instr/clean.config` | `3bb7b283c84178138aec1d0b2f19429cc4913a836aa97537a397040d91c072b6` | 147,766 B |
| `out/r1-instr/instrumentation.patch` | `c282aa1769426d57c786265f5dd4df7e918bc80c78f0efcc934fb8999aadea50` | 186 lines, 5 files |

`out/r1-device/Image.clean` was pulled from the device and verified against
`6c30b16e...` and 27,308,544 B. The old module backup was verified against
`936aa4b7...`.

## Which artifacts to use

- (a) Clean fire comparable with rounds 7/8: `out/r1-device/Image.clean`
  (`6c30b16e...`) with `out/r1-device/r1_kexec.ko.936aa4b7`. This is the
  stock-sized Image and the module used in those rounds.
- (b) Instrumented PTE-capture fire: `out/r1-instr/Image.instr.c9b4220d`
  (`c9b4220d...`) with `out/r1-instr/r1_kexec.ko.202cbd51`. The module is newly
  rebuilt against the new `Module.symvers` and must not be mixed with the
  clean Image or with the old `d1406478...` Image.

Comparability with the clean 27.3 MB Image: partially. The new Image restores
the full tracing config that rounds 7/8 had, unlike the 22.5 MB notrace build,
and its size is close (27,695,616 B vs 27,308,544 B, 387,072 B larger). It is
NOT byte-identical and NOT an exact rebuild of the device Image: fingerprint
is 99.40% rather than 100%, `CONFIG_AMLOGIC_DVB` is off by the build script's
design, the hidden `CONFIG_CC_STACKPROTECTOR` line differs while the STRONG
choice matches, and the five instrumentation edits add code. Treat it as a
tracing-compatible instrumented build, not as the clean reference. Use
`Image.clean` for any A/B comparison against rounds 7/8 and this Image only
for PTE capture.
