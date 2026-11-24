# EVIDENCE_MATRIX - what backs what, by subsystem

Second-review index. Read `reports/CURRENT_STATE.md` for verdicts,
`reports/INVALIDATED_HYPOTHESES.md` for closed paths. This file maps
evidence type to strongest artifact and main caveat.

## Provenance

| Item | Evidence type | Status | Strongest artifact | Main caveat |
| ---- | ------------- | ------ | ------------------ | ----------- |
| McMCCRU 3d4ab79e ancestral | source-tree comparison | PROBABLE | `reports/provenance.md`, SUBLEVEL 113 + 805Y id | 3-year gap, zero aquaman strings |
| no exact source in searched public material | negative search | HARDWARE_OBSERVED | MiCode check + issue #11 + fingerprint zero hits | scoped to searched material only |
| aquaman-config 4447 opts | offline artifact | PROVEN | `aquaman-config`, `tools/run_tests.py` pin | none |
| config similarity 14% raw / 98.1% expanded | derived arithmetic | PROVEN | `tools/config_fingerprint.py` | expanded match still leaves 49 diffs |

## Kernel build

| Item | Evidence type | Status | Strongest artifact | Main caveat |
| ---- | ------------- | ------ | ------------------ | ----------- |
| reproducible Image+dtb+modules | offline build | HARDWARE_OBSERVED | `tools/build_aquaman_kernel.sh`, `tools/validate_artifacts.py` | DVB dropped, 3 deltas unapplied |
| 26 MiB vs ~9.3 MiB container | observed difference | PROBABLE | `arch/arm64/boot/Image` vs `boot.img` `nTotalLength 0x959000` | 9.3 MiB is container size per AMLSECU, not normalised decompressed Image size |
| HZ/stackprotector/panic deltas unapplied | source comparison | PROVEN | `reports/_archive/rebuilt-kernel.md` sec 2 | config-only fix, not applied for comparability |
| McMCCRU HEAD DVB breakage | offline build failure | PROVEN | `aml_dvb.c` 15 errors, missing UAPI | parent `17cef223` untried |

## Vendor modules

| Item | Evidence type | Status | Strongest artifact | Main caveat |
| ---- | ------------- | ------ | ------------------ | ----------- |
| 28 `.ko` from OTA | offline extraction | PROVEN | `out/vendor/modules`, `tools/sdat2img.py` | presence only, see below |
| presence vs runtime usage | metadata audit | PROVEN | `modules.dep`, `srcversion` (only 2 modules) | no `/proc/modules` / init logs collected |
| vermagic `4.9.y` flattened | source + build | PROVEN | `Makefile:1221`, own build identical string | not a provenance clue |
| 190 CRC differ / 13 missing | offline disassembly | PROVEN | `tools/ko_versions.py` vs Module.symvers | 190 is upper bound; split unmeasured |
| `ddr_window_64.ko` legacy | offline metadata | PROVEN | `3.14.29`, no modversions | dead weight on disk |

## DTB

| Item | Evidence type | Status | Strongest artifact | Main caveat |
| ---- | ------------- | ------ | ------------------ | ----------- |
| blob recovered from RAM | hardware experiment | HARDWARE_REPRODUCED | `artifacts/aquaman.dtb` 58280 B at 0x01000000 | single 16 MiB read, cross-checked via second path |
| blob valid | offline validation | PROVEN | `dtc` zero errors, 376 nodes / 1798 props | 47 style warnings, none parse failures |
| vendor DTS source | negative search | INCONCLUSIVE | `dt.img` still encrypted | decompilation has no include/label layer |
| DTB Linux received | missing confirmation | INCONCLUSIVE | `/proc/device-tree` never read | RAM blob != receipt proof |

## Fastboot

| Item | Evidence type | Status | Strongest artifact | Main caveat |
| ---- | ------------- | ------ | ------------------ | ----------- |
| static chain download->bootm->SMC | source-tree comparison | OFFLINE_ONLY | khadas `f_fastboot.c`, `cmd_bootm.c`, `bl31_apis.c` | reference tree, not device binary |
| overlap BUF intersect Y | hardware experiment | HARDWARE_REPRODUCED | E5 vs E6 differential | exact BUF unknown |
| `max-download-size` non-discriminative | derived arithmetic | PROVEN | `tools/fastboot_addr.py` | per-board constants unknown |
| SMC is blocker | hardware experiment | HARDWARE_REPRODUCED | E7a pass / E7b+E7c reject, same Y | - |
| `booti`/`go` absent | hardware experiment | PROBABLE | E8 instant FAIL on valid Image | single-method inference, `help` broken oracle |

## BL33

| Item | Evidence type | Status | Strongest artifact | Main caveat |
| ---- | ------------- | ------ | ------------------ | ----------- |
| image extent + hash | offline carve | PROVEN | `reports/round14-bl33-persist/bl33-37e18000.bin`, sha `664fb34a...` | pinned in `tools/run_tests.py` |
| 15 SMC sites / 22 ids | offline disassembly | PROVEN | `tools/bl33_audit.py` census | static only |
| cmd_tbl 116 + consumer | offline + live read | HARDWARE_OBSERVED | live==offline 0 diffs, `ldr x4,[x19,#0x10]`+`blr x4` | - |
| WRITE/FILL + redirects | hardware experiment | HARDWARE_REPRODUCED | round42/43/44/46 oracles + restore | Optimus stage 16 only, reboot clears |
| live env writable | hardware experiment | HARDWARE_REPRODUCED | `0x33e18000` hunt, 1:1 WRITE + readback | semantic consumption not demonstrated |
| E1 direct bootargs-value poke -> cmdline | hardware experiment, RAM-only | REFUTED for this form | `reports/round48-bootargs-selinux.md` + hunt bin | verbatim string not consumed (2 fields differ explained: stale arena + `preboot -> run storeargs` rebuilder read live round52); htab-value transport still untested |
| WRITE htab data -> `env_get` | hardware oracle | HARDWARE_REPRODUCED | `reports/round52-write-htab-template.md` phase A (WRITE @ data ptr flips `test`, arena untouched) | host bytes -> authoritative store -> parser; kernel leg still open |
| template `EnableSelinux -> storeargs -> htab bootargs` | hardware, fresh-pointer reads | HARDWARE_REPRODUCED | `reports/round52-write-htab-template.md` A/B (832 B `df6c9576` vs `c5a4b5e3`, single-field diff, pointer moves) | parser-side proven; kernel transport tested round53 and REFUTED |
| transport htab `bootargs` -> kernel cmdline | hardware boot + offline follow-up | REFUTED for this form | `reports/round53-htab-transport.md` + `reports/round54-offline-fdt-path.md` (9/9 consumers env-based; eret entry; running config bootloader-only) + `reports/round55-fdt-identity-chain.md` (arg and `x2` both `[images+0x100]` structurally; error paths hang; no BL33 `enforcing`/`normal` emitter) + `reports/round56-inert-transport.md` (inert `ZZ->US` whole-string revert, Case B) + `reports/round57-fdt-final-identity.md` (reloc `0x37e5bda4` before fixup so not the fork; post-fixup in-place only; no `/chosen` rewriter; `SAME_OBJECT_UNKNOWN_BYTES`, no static fork found) | one run + full static map + inert discriminator; E2 moot |
| inert `boardid` 3->7 -> kernel cmdline | hardware experiment, RAM-only | REFUTED (whole-string revert) | `reports/round58-boardid-transport.md` (832 B `a69c9f7d` `boardid=7` handed to `imgread`+`bootm`; Android `ro.boot.boardid=3`) | second inert field, independent env source, same revert as round56; no in-kernel oracle for shell, but as root `/proc/cmdline` and dmesg's cmdline are readable and identical (`reports/root-read-surface-2026-11-23.md`); the DT node stays denied and no marker boot was re-run, so BL33-delivered vs Linux-re-derived UNKNOWN |
| env authority = htab `0x37ee7278`, arena = stale heap copy | hardware oracle + offline disassembly | HARDWARE_OBSERVED (oracle chain) / OFFLINE_ONLY (code) | `reports/round51-env-htab-oracle.md` (setenv flips `test`, WRITE arena does not; entry 0x33e2ff40 data 0x33e32910 vs arena 0x33e1d6c4) + `reports/round50-env-authoritative-source.md` | get/set share one htab (device VAs); `setenv` reallocates (same-size reuse observed); round49 oracle read a freed address; effective htab `bootargs` leg UNKNOWN, verdicts unchanged |
| page-table descriptors | offline + live dump | PROBABLE | `0x37ff0000` 8192 descriptors, XN=0 | descriptor-compatible with RWX; active MMU state not demonstrated |
| boot-decision scripts | offline disassembly | OFFLINE_ONLY | `bootdelay_process`, `autoboot`, `storeboot`, `switch_bootmode` | poke post-reset not proven (RAM volatile) |
| `bootm` Hush command census | offline call graph | OFFLINE_ONLY | `tools/bootm_env_closure.py`, `reports/root-final-analysis/01-bootm-env-closure.txt` | 12 lines, none rebuilds env; `blr` not followed |
| no defenv re-import on the boot path | offline call graph | OFFLINE_ONLY (scoped negative) | 3 `himport_r` callers, none in bootm's 236-fn or imgread's 28-fn closure | indirect edges not followed |
| `fdt_chosen` callable in-session | offline disassembly | OFFLINE_ONLY | `reports/root-final-analysis/03-fdt-chosen-path.txt`, 2 callers only | never executed; `fdt` subcommands unaudited on device |
| kernel cmdline source | device config + ancestral source | PROVEN (config) / OFFLINE_ONLY (source) | `reports/root-final-analysis/05-kernel-cmdline-source.txt` | AOSP `property_init` hop is EXTERNAL |
| cmd_tbl slot re-verification | live dump | HARDWARE_OBSERVED | `reports/root-final-analysis/04-cmdtbl-slots.txt` | layout +0x00/+0x08/+0x10 re-derived from the round46 dump |

## Secure boot / BL31

| Item | Evidence type | Status | Strongest artifact | Main caveat |
| ---- | ------------- | ------ | ------------------ | ----------- |
| unsigned rejected pre-kernel | hardware experiment | HARDWARE_REPRODUCED | M1a/M1b/E1/CTRL/E7 identical reject timing | - |
| `aml_sec_boot_check` wrapper | offline disassembly | OFFLINE_ONLY | `0x37e19ea8` `mov x0,#0x820000ff` + `smc #0` | BL31 internals closed |
| BL31 exact binary | negative search | INCONCLUSIVE | absent in 6 SoC generations, `0x05100000` blob | family `bl31.bin` present, exact absent |
| no bypass demonstrated | negative, scoped | PROVEN | E1/E3/E8 matrix | scoped to tested RAM-only surface |

## GhostLock

| Item | Evidence type | Status | Strongest artifact | Main caveat |
| ---- | ------------- | ------ | ------------------ | ----------- |
| trigger -> EDEADLK | hardware experiment | HARDWARE_REPRODUCED | LEVEL_2 matrix, BOOT_ID 3ec336a5 | - |
| consumer walk differential | hardware experiment | HARDWARE_REPRODUCED | `FUTEX_LOCK_PI` occ gating | - |
| f_target/f_alt fidelity | hardware experiment | HARDWARE_REPRODUCED | `alt_tgt` vs `alt_only` | semantic fields, not bytes |
| H16 birth/readers | offline disassembly | OFFLINE_ONLY | H16.0/H16.4/H16.7 VAs + source | KASLR slides VAs |
| H16 live-retarget | negative, scoped | INCONCLUSIVE | 411/33/0 census, BFS depth<=3 | audited surface only |
| post-free reuse hypothesis | comparative | PROBABLE | 5 external ports, all OBJECT_REUSE | not demonstrated on Aquaman |

## Disclosure

| Item | Evidence type | Status | Strongest artifact | Main caveat |
| ---- | ------------- | ------ | ------------------ | ----------- |
| proc/sys/net/futex sample | hardware experiment | PROBABLE | 22 tests, POINTER_BYTES_FOUND 0 | audited surface only |
| PI path zero copies | source + binary | OFFLINE_ONLY | `copy_to_user` 0 hits in futex.c+rtmutex.c | - |
| /dev beyond C1-C3, f_op depth>3 | unaudited | INCONCLUSIVE | explicitly not covered | blind ioctl prohibited without source |
| mali stateful | hardware + offline | PROBABLE | 34 handlers BOUNDED_COPY/NO_EMIT | blind ioctl not executed |

## Reclaim

| Item | Evidence type | Status | Strongest artifact | Main caveat |
| ---- | ------------- | ------ | ------------------ | ----------- |
| order-2 capture with verifier | hardware experiment | INCONCLUSIVE | `mm_reclaim_probe` FAIL `hits=0` | plumbing 512/512 passes, not reclaim |
| MSG_PEEK | hardware experiment | REFUTED as proof | same probe | plumbing only |
| slab/buddy diagnostics | blocked | INCONCLUSIVE | errno 13 / absent / 0400 | shell unreachable; root adds buddyinfo but slab attrs stay denied |

## Root surface (2026-11-23)

| Item | Evidence type | Status | Strongest artifact | Main caveat |
| ---- | ------------- | ------ | ------------------ | ----------- |
| persistent uid 0 from ODM init service | hardware boot | HARDWARE_REPRODUCED | `reports/root-via-odm-2026-11-23.md` | shell on TCP 4444 in `u:r:dumpstate:s0`; not via boot chain or GhostLock |
| root reads kernel log and `/proc/cmdline` | hardware, one boot | HARDWARE_REPRODUCED | `reports/root-read-surface-2026-11-23.md` (dmesg cmdline identical to `/proc/cmdline`) | enforcing-only snapshot; DT node, `/proc/kallsyms`, slab attrs and debugfs were denied then |
| root reads dmesg VA layout and `-g963f962d046a-dirty` banner | hardware, one boot | HARDWARE_REPRODUCED | same report | no second boot, no KASLR re-check; `/proc/version` still omits the suffix |
| SELinux switched to Permissive from ODM rc | hardware boot + offline policy | HARDWARE_REPRODUCED | `reports/selinux-permissive-via-module-2026-11-23.md` | global enforcement only; `setenforce` still denied to shell and `dumpstate`, reboot does not revert |
