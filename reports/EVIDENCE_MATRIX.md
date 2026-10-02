# EVIDENCE_MATRIX — what backs what, by subsystem

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
| HZ/stackprotector/panic deltas unapplied | source comparison | PROVEN | `reports/rebuilt-kernel.md` §2 | config-only fix, not applied for comparability |
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
| overlap BUF ∩ Y | hardware experiment | HARDWARE_REPRODUCED | E5 vs E6 differential | exact BUF unknown |
| `max-download-size` non-discriminative | derived arithmetic | PROVEN | `tools/fastboot_addr.py` | per-board constants unknown |
| SMC is blocker | hardware experiment | HARDWARE_REPRODUCED | E7a pass / E7b+E7c reject, same Y | — |
| `booti`/`go` absent | hardware experiment | PROBABLE | E8 instant FAIL on valid Image | single-method inference, `help` broken oracle |

## BL33

| Item | Evidence type | Status | Strongest artifact | Main caveat |
| ---- | ------------- | ------ | ------------------ | ----------- |
| image extent + hash | offline carve | PROVEN | `reports/round14-bl33-persist/bl33-37e18000.bin`, sha `664fb34a…` | pinned in `tools/run_tests.py` |
| 15 SMC sites / 22 ids | offline disassembly | PROVEN | `tools/bl33_audit.py` census | static only |
| cmd_tbl 116 + consumer | offline + live read | HARDWARE_OBSERVED | live==offline 0 diffs, `ldr x4,[x19,#0x10]`+`blr x4` | — |
| WRITE/FILL + redirects | hardware experiment | HARDWARE_REPRODUCED | round42/43/44/46 oracles + restore | Optimus stage 16 only, reboot clears |
| live env writable | hardware experiment | HARDWARE_REPRODUCED | `0x33e18000` hunt, 1:1 WRITE + readback | semantic consumption not demonstrated |
| page-table descriptors | offline + live dump | PROBABLE | `0x37ff0000` 8192 descriptors, XN=0 | descriptor-compatible with RWX; active MMU state not demonstrated |
| boot-decision scripts | offline disassembly | OFFLINE_ONLY | `bootdelay_process`, `autoboot`, `storeboot`, `switch_bootmode` | poke post-reset not proven (RAM volatile) |

## Secure boot / BL31

| Item | Evidence type | Status | Strongest artifact | Main caveat |
| ---- | ------------- | ------ | ------------------ | ----------- |
| unsigned rejected pre-kernel | hardware experiment | HARDWARE_REPRODUCED | M1a/M1b/E1/CTRL/E7 identical reject timing | — |
| `aml_sec_boot_check` wrapper | offline disassembly | OFFLINE_ONLY | `0x37e19ea8` `mov x0,#0x820000ff` + `smc #0` | BL31 internals closed |
| BL31 exact binary | negative search | INCONCLUSIVE | absent in 6 SoC generations, `0x05100000` blob | family `bl31.bin` present, exact absent |
| no bypass demonstrated | negative, scoped | PROVEN | E1/E3/E8 matrix | scoped to tested RAM-only surface |

## GhostLock

| Item | Evidence type | Status | Strongest artifact | Main caveat |
| ---- | ------------- | ------ | ------------------ | ----------- |
| trigger -> EDEADLK | hardware experiment | HARDWARE_REPRODUCED | LEVEL_2 matrix, BOOT_ID 3ec336a5 | — |
| consumer walk differential | hardware experiment | HARDWARE_REPRODUCED | `FUTEX_LOCK_PI` occ gating | — |
| f_target/f_alt fidelity | hardware experiment | HARDWARE_REPRODUCED | `alt_tgt` vs `alt_only` | semantic fields, not bytes |
| H16 birth/readers | offline disassembly | OFFLINE_ONLY | H16.0/H16.4/H16.7 VAs + source | KASLR slides VAs |
| H16 live-retarget | negative, scoped | INCONCLUSIVE | 411/33/0 census, BFS depth<=3 | audited surface only |
| post-free reuse hypothesis | comparative | PROBABLE | 5 external ports, all OBJECT_REUSE | not demonstrated on Aquaman |

## Disclosure

| Item | Evidence type | Status | Strongest artifact | Main caveat |
| ---- | ------------- | ------ | ------------------ | ----------- |
| proc/sys/net/futex sample | hardware experiment | PROBABLE | 22 tests, POINTER_BYTES_FOUND 0 | audited surface only |
| PI path zero copies | source + binary | OFFLINE_ONLY | `copy_to_user` 0 hits in futex.c+rtmutex.c | — |
| /dev beyond C1-C3, f_op depth>3 | unaudited | INCONCLUSIVE | explicitly not covered | blind ioctl prohibited without source |
| mali stateful | hardware + offline | PROBABLE | 34 handlers BOUNDED_COPY/NO_EMIT | blind ioctl not executed |

## Reclaim

| Item | Evidence type | Status | Strongest artifact | Main caveat |
| ---- | ------------- | ------ | ------------------ | ----------- |
| order-2 capture with verifier | hardware experiment | INCONCLUSIVE | `mm_reclaim_probe` FAIL `hits=0` | plumbing 512/512 passes, not reclaim |
| MSG_PEEK | hardware experiment | REFUTED as proof | same probe | plumbing only |
| slab/buddy diagnostics | blocked | INCONCLUSIVE | errno 13 / absent / 0400 | shell unreachable |
