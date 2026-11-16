# CURRENT_STATE — single source of truth (2026-10-02)

Read this first. It is the epistemological index. History is preserved in
individual reports; this file states what is currently believed and why.
Statuses only: PROVEN, HARDWARE_REPRODUCED, HARDWARE_OBSERVED, OFFLINE_ONLY,
PROBABLE, INCONCLUSIVE, REFUTED, SUPERSEDED. CONFIRMED is not used.

## Kernel provenance

| Claim | Status | Evidence | Scope | Supersedes |
| ----- | ------ | -------- | ----- | ---------- |
| McMCCRU `3d4ab79e` is ancestor / close family, not exact source | PROBABLE | same SUBLEVEL 113, same Amlogic base, 805Y package id; zero aquaman strings, zero aquaman DTS, 3 years older than 2022-09-06 build | source-tree comparison, offline | — |
| no exact source found in searched public material | HARDWARE_OBSERVED | MiCode dangal/machuca/venom checked, MiBox issue #11 open since 2025-01, no aquaman tree, fingerprint `c5-mitv-cm-build06.bj` zero hits | scope: searched public material only | — |
| this does not prove source does not exist publicly | PROVEN | negative search cannot prove non-existence | logic, scope guard | corrects `provenance.md` absolute wording |
| `aquaman-config` is 4447 options | PROVEN | `tools/config_fingerprint.py` parses to 4447; pinned in `tools/run_tests.py` | offline artifact | — |
| low config similarity vs defconfig does not mean low functional similarity | PROVEN | raw defconfig is minimum vs expanded device config: 14.05% raw, 98.10% expanded | offline arithmetic | — |
| vendor modules give better ABI fingerprint than config similarity | PROBABLE | 2507 versioned imports, CRC comparison vs Module.symvers | offline comparison | — |
| 190 CRCs different is upper bound, not proof 190 are source-level | PROVEN | config-derived CRCs (`kmalloc_caches`, `dev_err`) move with config; split not measured per-symbol | offline, `reports/vendor-modules.md` | corrects over-read of 190 |
| 13 missing symbols include real structural gaps | PROVEN | W1 Wi-Fi stack, `pstore_io_save` absent from tree entirely | offline, source + symvers | — |
| current build is reproducible approximation of ancestral tree with adaptations | OFFLINE_ONLY | `tools/build_aquaman_kernel.sh` + `tools/validate_artifacts.py`; 3 deltas documented | offline build, reproducible | supersedes `baseline compiles` |

## Fastboot

| Claim | Status | Evidence | Scope | Supersedes |
| ----- | ------ | -------- | ----- | ---------- |
| `loadaddr` live = `0x1080000` | HARDWARE_OBSERVED | live env `loadaddr=1080000` at `0x33e1e0ef` (round46 hunt); reference tree default same | live RAM read, one boot | — |
| download alters region read by `bootm` | HARDWARE_REPRODUCED | E5 (stock `fastboot boot boot.img` boots) vs E6 (raw `boot` no download FAILs), same `bootm(Y)` | hardware, RAM-only | — |
| this proves overlap between download buffer and region consumed by `bootm` | HARDWARE_REPRODUCED | E5/E6 differential | hardware | supersedes `download != boot source` |
| `BUF == Y` as exact equality | INCONCLUSIVE | overlap of 16 MiB image compatible with range of BUF values incl. just below Y | logic | corrects `buffer-equals-loadaddr-proof.md` title |
| exact `BUF` remains unknown | INCONCLUSIVE | device U-Boot encrypted, per-board constants unknown | — | — |
| `max-download-size=0x08000000` does not discriminate address hypotheses | PROVEN | `ddr_size_usable` arithmetic: neither 0x10200000 nor 0x1080000 yields 0x08000000; `tools/fastboot_addr.py` | offline arithmetic | supersedes `fastboot-boot-verdict.md` root cause |
| operational blocker is SMC / secure world, not address | HARDWARE_REPRODUCED | E7a stock passes, E7b plaintext same Y rejected, E7c INVALID same timing | hardware | — |

## BL31 / secure boot

| Claim | Status | Evidence | Scope | Supersedes |
| ----- | ------ | -------- | ----- | ---------- |
| unsigned payload passes normal path and is rejected before kernel execution | HARDWARE_REPRODUCED | E7/M1a/M1b/E1/CTRL all return to Android 15-21s empty bootreason; E4/E5 signed pass | hardware | — |
| `getvar secure:no` must not be read as absence of secure-boot eFuse | PROBABLE | orange/unlocked flashing coexists with fused verify (E7); lock state vs fuse are different signals | hardware + source | — |
| `booti` / `go` not available in this build | PROBABLE | E8 instant FAIL on valid ARM64 Image, device stays in fastboot; `help` broken oracle noted | hardware, single method | — |
| no secure-boot bypass demonstrated | PROVEN | no bypass path executed; `bootm` always SMCs, `imgread` eMMC-only, `autoscr` same gate | negative, scoped to tested surface | — |

## DTB

| Claim | Status | Evidence | Scope | Supersedes |
| ----- | ------ | -------- | ----- | ---------- |
| DTB Aquaman recovered from RAM | HARDWARE_REPRODUCED | 16 MiB read at 0x01000000, `artifacts/aquaman.dtb` 58280 B | hardware read | supersedes `DTB unavailable` |
| blob exists and is valid | PROVEN | magic `d00dfeed`, `dtc` round-trip zero errors, 376 nodes / 1798 props | offline validation | — |
| original DTS source still not available | INCONCLUSIVE | `dt.img` still encrypted, recovered blob is decompilation with no include/label structure | — | — |
| recovered blob does not equal original DTS source automatically | PROVEN | decompilation loses `#include` / `&label` / comments | logic | — |
| distinguish `DTB present in RAM` vs `DTB Linux received` | PROVEN | `/proc/device-tree` confirmation never collected; RAM blob is not receipt proof | scope guard | — |

Three things kept separate: (1) DTB stored in firmware (`dt.img`, encrypted),
(2) DTB recovered from RAM (`artifacts/aquaman.dtb`), (3) DTB effectively
consumed by Linux (unconfirmed, would need `/proc/device-tree`).

## Vendor modules

| Claim | Status | Evidence | Scope | Supersedes |
| ----- | ------ | -------- | ----- | ---------- |
| 28 `.ko` extracted from OTA | PROVEN | `vendor.new.dat.br` + `tools/sdat2img.py` + `debugfs`, `out/vendor/modules` | offline, reproducible | supersedes `vendor-module-compat.md` root-blocked |
| presence in OTA does not prove all were loaded at boot | PROVEN | OTA presence vs `insmod` are different facts | scope guard | — |
| vermagic `4.9.y` is not strong fingerprint | PROVEN | vendor Makefile flattens stamp to `<major>.<minor>.y`; own build produces identical string | offline, `Makefile:1221` | corrects early misread |
| CRC mismatch is real barrier for reuse vs rebuilt kernel | PROVEN | 13 missing, 190 differ vs McMCCRU Module.symvers | offline measurement | — |
| `ddr_window_64.ko` is other generation / legacy | PROVEN | `3.14.29`, no modversions, distinguishable from `4.9.y` | offline | — |

## BL33

| Claim | Status | Evidence | Scope | Supersedes |
| ----- | ------ | -------- | ----- | ---------- |
| `cmd_tbl`, handlers, consumers strongly mapped | HARDWARE_OBSERVED | 116 cmds, live==offline 0 diffs, consumer `ldr x4,[x19,#0x10]` + `blr x4` | offline disasm + live read | — |
| WRITE / FILL and redirects in RAM demonstrated | HARDWARE_REPRODUCED | WRITE 8/16/64B, FILL scattered, `false->true`, `test->true`, env-print `->true` + restore, same-cycle oracle | hardware, Optimus stage 16 | — |
| live env located and writability in RAM demonstrated | HARDWARE_REPRODUCED | env hunt `0x33e18000` 32k, `bootdelay` / `avb2` WRITE 1:1 + readback + restore, neighbour intact | hardware | — |
| env mutation equals proof relevant script consumed new value | INCONCLUSIVE | no safe script trigger observes mutated env via return code; tails are destructive (`bootm`/`update`/`recovery`/`fastboot`) | scope guard | corrects `env mutation alters boot` |
| E1 direct bootargs-value poke reaches Linux cmdline | REFUTED for this form | round48: 9 B `enforcing`->`permissiv` @ `0x33e1d825` with readback, `imgread` success, `bootm` booted stock, but `ro.boot.selinux=enforcing` and `reboot_mode normal` vs written `fastboot` | hardware, RAM-only, one run | arena is the wrong object (round51 SHADOW_COPY); boot-time rebuilder is `preboot -> run storeargs` (round52 live read); transport of the *htab* value to Linux still untested |
| authoritative env store is htab @ `0x37ee7278`, not the `0x33e18000` arena | HARDWARE_OBSERVED | round51: `test ${EnableSelinux}` oracle calibrates (`enforcing` success / `permissiv` failed:), `setenv permissiv` flips oracle to `permissiv`, restore flips back, WRITE arena `permissiv` with readback leaves oracle at `enforcing`; entry 262 @ `0x33e2ff40` data `0x33e32910` vs arena `0x33e1d6c4` | device binary + hardware oracle, RAM-only, restored | round51 promotes round50 SHADOW_COPY from OFFLINE_ONLY to hardware-observed; E1 stays REFUTED for arena poke, round49 stale-oracle caveat confirmed (effective htab leg UNKNOWN, not claimed) |
| WRITE to live htab data reaches `env_get`/Hush | HARDWARE_REPRODUCED | round52 phase A: WRITE 9 B `permissiv` @ htab data `0x33e32910` with readback (NUL + tail intact, arena untouched) flips oracle to `permissiv`; `setenv enforcing` restores | hardware oracle, RAM-only, restored, same boot | proves host bytes -> authoritative store -> parser; transport to kernel still open |
| template leg `EnableSelinux -> storeargs -> htab bootargs` | HARDWARE_REPRODUCED | round52 A/B: `setenv permissiv` + `run storeargs` -> fresh-ptr htab `bootargs` 832 B sha `df6c9576` (`permissiv`); `setenv enforcing` + `run storeargs` -> 832 B sha `c5a4b5e3` (`enforcing`); single-field diff, pointer moves each rebuild; controlled-A bytes equal round49's leftover product | hardware, fresh-pointer reads + oracle, RAM-only, left coherent | parser consumption proven; kernel transport tested round53 and REFUTED (see next row) |
| transport `htab bootargs -> kernel cmdline` | REFUTED for this form | round53: verified htab 832 B `df6c9576` (`permissiv`+`fastboot`) handed to `imgread` success + `bootm`, Android returned stock in ~15 s, but `ro.boot.selinux=enforcing` + `reboot_mode normal` (E1 double-field signature vs authoritative bytes) | hardware, one run, E1/E4 shape with fixed oracle | round54 offline: 9/9 consumers use env string; entry is eret not SMC; running kernel is bootloader-cmdline-only; one link left (fixup ran+succeeded?); round55 offline: `fdt_chosen` arg and `x2` both proven as `[images+0x100]` structurally, error paths hang so boot implies fixup success (INFERRED), no BL33 emitter of `enforcing`/`normal`, stock Image encrypted (UNKNOWN), dump DTB has no `/chosen`; divergence stays UNKNOWN with narrowed boundary, no promotion without hardware |
| FDT identity `fdt_chosen` arg vs `x2` | OFFLINE_ONLY (structural) | round55: `0x37e5c344` passes `[images+0x100]` to `fdt_chosen`, `0x37e21284` passes `[images+0x100]` as `x2` to `0x37e19264` eret; `ft_addr=0x100`/`ft_len=0x108` proven by FIT arithmetic; byte-equality UNKNOWN (reloc copy in `0x37e5bda4`, runtime `ft_len`/`fdt_setprop` return unknown). round57: `0x37e5bda4` reconstructed as `boot_relocate_fdt` (PROVEN shape, 3 callers, tail `str [x25]/[x24]` rewrites the field before fixup); pointer post-reloc PROVEN same field to `x2` with no store between; post-fixup tail in-place only, no second writer; `d00dfeed` 0 hits; classification `SAME_OBJECT_UNKNOWN_BYTES`, content still UNKNOWN, no promotion without hardware | device binary static only, no boot | — |
| inert `wificountrycode` ZZ -> kernel | REFUTED (whole-string revert) | round56: verified htab 832 B `e1e32443` (`ZZ`/`enforcing`/`fastboot`) handed to `imgread` success + `bootm`, Android returned `US`/`enforcing`/`normal`; inert reverted with `fastboot`, not selective | hardware, one run, E1/E4 shape with fixed oracle | Case B proven for this form; stop testing selinux, problem is blob identity not field filter |
| inert `androidboot.boardid` 3->7 -> kernel | REFUTED (whole-string revert, second inert field) | round58: fresh-pointer htab 832 B `a69c9f7d` with `androidboot.boardid=7` (`selinux=enforcing`, `reboot_mode=fastboot`, single-byte diff vs baseline `c5a4b5e3` at offset 681) handed to `imgread` success + `bootm`, Android returned `ro.boot.boardid=3` / `selinux=enforcing` / `reboot_mode=normal` / `wificountrycode=US`, `getenforce=Enforcing` | hardware, one run, E1/E4 shape, boardid has independent env source (htab idx 57) | second inert field reverts identically to round56; signature is whole-string/whole-object, not field-specific. No in-kernel oracle on this build (`/proc/device-tree/chosen/bootargs` and `/proc/cmdline` both Permission denied for `u:r:shell:s0`, avc recorded), so BL33-delivered vs Linux-re-derived stays UNKNOWN; no further boot justified |

| `bootm` runs 12 Hush command lines, none of them env-rebuilding | OFFLINE_ONLY | `tools/bootm_env_closure.py`: `get_avb_mode;`, `setenv bootargs ${bootargs} defendkey=%x,%x,`, `store dtb decrypt ${dtb_mem_addr}`, `get_valid_slot;`, `store size`/`store read`, `setenv dtbo_mem_addr`, `dtbo_start`, `fdt apply`, `rsvmem check`. `preboot`/`storeargs`/`bootcmd` absent | device binary static only, no boot | new; closes the "bootm re-runs storeargs" explanation |
| no defenv re-import on the tested path | OFFLINE_ONLY (scoped negative) | `himport_r 0x37eaa264` has exactly 3 callers image-wide; none inside `bootm`'s 236-function `bl` closure or `imgread`'s 28-function closure, and `imgread` touches no env function at all. `env_relocate 0x37e58d94` has one caller, `0x37e24ad8`, a zero-direct-caller late-init function reached from the init function-pointer table before the burning session attaches | call graph over direct `bl` only; `blr` counted not followed, OS dispatch into fixup is an indirect table edge | new; indirect edges remain the open scope |
| `fdt_chosen` reachable from a command, in-session | OFFLINE_ONLY | exactly 2 callers image-wide: `0x37e5c344` (`image_setup_libfdt`, bootm path) and `0x37e293e4`, the `fdt chosen` subcommand (`memcmp argv[0],"cho",3`), blob from global `0x37f72a90` set by `fdt addr`; `reports/root-final-analysis/03-fdt-chosen-path.txt` | device binary static only, never executed | new; the cheapest untested oracle for the transport question |
| board DTB is decrypted by `bootm` itself, not parsed out of the boot image | OFFLINE_ONLY | `bootm` runs `store dtb decrypt ${dtb_mem_addr}` with defenv `dtb_mem_addr=0x1000000`; explains why the `0x01000000` dump has no `/chosen` | device binary static + defenv | new; corrects round57 FDT-A row for the DTB leg |
| `/proc/cmdline` on this build is the DT `/chosen/bootargs` verbatim | PROVEN (config) / OFFLINE_ONLY (source) | running `/proc/config.gz` 5691 lines: `CONFIG_CMDLINE=""`, no `CONFIG_CMDLINE_EXTEND`, no `CONFIG_CMDLINE_FORCE`; ancestral arm64 `early_init_dt_scan_chosen` (`drivers/of/fdt.c:1089`) `strlcpy`s the DT property into `boot_command_line` (`init/main.c:124`); `reports/root-final-analysis/05-kernel-cmdline-source.txt` | device config artifact + ancestral source tree | new; leaves only the AOSP `property_init` `androidboot.X`->`ro.boot.X` hop as EXTERNAL, so "Linux re-derived" is narrowed, not closed |

Direction after these rows: the store is proven, the parser is proven, the
template rebuild is proven, the FDT pointer identity is proven, and the kernel
cmdline source has no alternative, yet three inert fields revert whole-string.
The remaining break is inside `bootm`'s window, past the htab, before or at
`fdt_chosen`. `fdt_chosen` has never been executed by us.

## GhostLock

| Claim | Status | Evidence | Scope | Supersedes |
| ----- | ------ | -------- | ----- | ---------- |
| trigger / requeue path reached | HARDWARE_REPRODUCED | FWRQ/FCRQ trio -> EDEADLK 5/5, LEVEL_2 matrix, BOOT_ID 3ec336a5 | hardware | — |
| consumer `FUTEX_LOCK_PI` shows differential behaviour | HARDWARE_REPRODUCED | occupied+stale=EDEADLK vs else TIMEOUT, alt negatives, pos_cycle control | hardware | — |
| `f_target` and `f_alt` distinguished by occupancy / fidelity | HARDWARE_REPRODUCED | `alt_tgt` EDEADLK, `alt_only` TIMEOUT, walk follows birth `f_target` | hardware | — |
| H16 live-retarget demonstrated | INCONCLUSIVE | no durable 8B `[W_waiter+0x38]` write ever landed; census empty of usable carriers | audited surface only | — |
| `NO_EXACT_WRITER_FOUND` | PROBABLE | 411 8B stores in window, 33 exact, 0 TARGET_RT_MUTEX producer; BFS depth<=3, all SyS roots | scope: audited surface, not whole kernel | corrects `NO_EXACT_WRITER` global |
| `NO_DISCLOSURE_FOUND` | PROBABLE | POINTER_BYTES_FOUND 0, 22 tests, proc/sys/net/futex/vendor sample | scope: audited surface | corrects `no disclosure path exists` global |
| post-free stack reuse is main comparative hypothesis | PROBABLE | every external port (canonical x86, Hazel, 5.10, OPPO 4.14, Shield 4.9) replaces whole object after waiter return, never live 8B retarget | comparative, offline | reclassifies GhostLock direction |
| disclosure is real bottleneck | PROBABLE | forging needs valid kernel VAs; none disclosed as bytes | — | — |
| reclaim proven | INCONCLUSIVE | `mm_reclaim_probe` FAIL `reclaim_hits=0`; MSG_PEEK is plumbing only | hardware | — |
| arbitrary R/W / root demonstrated | INCONCLUSIVE | out of scope until slot moves; never attempted, never claimed | — | — |

Direction: principal `post-free stack reuse + disclosure`; secondary `H16
live retarget`; closed: reclaim without verifier, audited live H16 writer
search, fake object, arbitrary R/W, cred/root. Post-free reuse is not
demonstrated on Aquaman. Live-retarget was audited and not demonstrated.
Future work prioritises reuse formulation, conditioned first on reproducible
disclosure and overlap.
