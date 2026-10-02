# INVALIDATED_HYPOTHESES — closed leads, do not reopen without new evidence

History is preserved. These entries exist so nobody re-spends a session on a
refuted path. Each entry: original hypothesis, why it looked plausible,
refuting evidence, current document, final state.

## 1. test payload really executed via `fastboot boot`

- Original: 4096-byte plaintext boot.img was accepted, stub ran, device returned in ~30s.
- Plausible because: USB drop + delayed adb return looked like execution.
- Refuted by: `fastboot-boot-verdict.md` M1a 16-21s no-delay return = rejection; E7a vs E7b vs E7c identical timing for plaintext/INVALID.
- Current: `reports/fastboot-memory-flow.md` §6, `reports/buffer-equals-loadaddr-proof.md` E7.
- Final: REFUTED. Unsigned legs die at SMC before format check.

## 2. `download != boot source`

- Original: download buffer and `bootm` source are disjoint; that explains all failures.
- Plausible because: khadas headers show BUF=0x10200000 vs loadaddr=0x1080000, and early probes at wrong addresses failed.
- Refuted by: E5 vs E6 — same `bootm(Y)`, different outcome depending only on prior download; download changed bytes `bootm(Y)` read.
- Current: `reports/fastboot-memory-flow.md` §4, `reports/CURRENT_STATE.md` (overlap proven).
- Final: REFUTED. Overlap proven; exact equality not proven.

## 3. download buffer is `0x10200000`

- Original: `X = 0x10200000` is a device fact from `include/g_dnl.h:18`.
- Plausible because: closest public tree says so.
- Refuted by: device U-Boot is encrypted; reference value never measured on this build; E5/E6 compatible with range of BUF values.
- Current: `reports/fastboot-memory-flow.md` §2, `reports/buffer-equals-loadaddr-proof.md` header note.
- Final: REFUTED as device fact. Reference-tree derivation only.

## 4. `max-download-size` proves buffer position

- Original: `max-download-size 0x08000000` is incompatible with buffer at 0x1080000, proves X != Y.
- Plausible because: formula `ddr_size_usable` looked discriminative.
- Refuted by: arithmetic — neither 0x10200000 (0x22E00000) nor 0x1080000 (0x31F80000) yields 0x08000000; inverse gives BUF=0x2B000000.
- Current: `reports/fastboot-memory-flow.md` §3, `tools/fastboot_addr.py`.
- Final: REFUTED. Number cannot discriminate hypotheses.

## 5. `X = 0x10200000` is device fact

- Same as 3, kept separate because it appears in `bootm-test-image.md` / `set-active-sink.md` gate analysis.
- Refuted by: same as 3.
- Current: banners in both files + `reports/fastboot-memory-flow.md`.
- Final: REFUTED as device fact. Injection address for those analyses is 0x1080000 (overlap), operative gate is SMC.

## 6. vermagic `4.9.y` proves module origin

- Original: `4.9.y` != `4.9.113` so modules came from different build.
- Plausible because: normally vermagic pins sublevel.
- Refuted by: repo's own build produces identical `4.9.y`; Amlogic `Makefile:1221` flattens stamp via `UTS_RELEASEY`.
- Current: `reports/vendor-modules.md` §2.
- Final: REFUTED. Vermagic gate deliberately loosened; CRCs are the real gate.

## 7. modules need to be extracted from device

- Original: extraction blocked, requires root (SELinux denies pull/cat).
- Plausible because: `/vendor/lib/modules` unreadable over adb shell.
- Refuted by: modules are in OTA dumps already in repo (`vendor.new.dat.br`); decompress + `tools/sdat2img.py` + `debugfs`, no root/device/network.
- Current: `reports/vendor-modules.md`.
- Final: REFUTED. Presence proven from OTA.

## 8. baseline kernel compiles with `CONFIG_AMLOGIC_DVB=y`

- Original: baseline compiles EXIT=0.
- Plausible because: earlier tree compiled.
- Refuted by: McMCCRU HEAD `3d4ab79e` backported DVB driver without matching UAPI (`CA_CW_DES_EVEN`, `struct ca_descr_ex.mode` missing); 15 errors in `aml_dvb.c`.
- Current: `reports/rebuilt-kernel.md` §7, `reports/repo-state.md`.
- Final: REFUTED at HEAD. `CONFIG_AMLOGIC_DVB=n` required; parent `17cef223` or newer tree untried.

## 9. Aquaman DTB is inaccessible

- Original: board DTB sealed in `dt.img`, unavailable.
- Plausible because: `dt.img` encrypted, no vendor DTS public.
- Refuted by: DTB recovered from DRAM at 0x01000000, 58280 B, valid FDT, `artifacts/aquaman.dtb`.
- Current: `reports/aquaman-dtb-extraction.md`, `reports/CURRENT_STATE.md` (three-way split).
- Final: SUPERSEDED. Blob available; vendor `.dts` source still missing; Linux-receipt unconfirmed.

## 10. `0x01040000..0x01080000` contains no U-Boot

- Original: ARM64 code, unidentified, rejected as U-Boot (no strings, no `brk`).
- Plausible because: string/opcode heuristics.
- Refuted by: matches `securestorage.c` structurally + 13 BL31 ids materialised by `movz`/`movk`.
- Current: `reports/bl33-offline-round10.md` §4.
- Final: REFUTED. Strong U-Boot/Amlogic fragment; base/entrypoint still unproven.

## 11. old SMC count is correct

- Original: 11 SMC sites (round8 §5).
- Plausible because: opcode constant looked right.
- Refuted by: compared against `0xD4000000`, not valid `svc`/`hvc`/`smc`; 5 real in code window, 15 `smc #0` in full image.
- Current: `reports/bl33-offline-round10.md` §3, round14 census.
- Final: REFUTED. 15 sites, 22 ids.

## 12. GhostLock waiter necessarily needs scheduler consumer from early attempts

- Original: consumer must be scheduler path used first.
- Plausible because: canonical ports use `sched_setattr` walk.
- Refuted by: `FUTEX_LOCK_PI` timed walk reaches same `rt_mutex_adjust_prio_chain` family and shows differential EDEADLK vs TIMEOUT.
- Current: `reports/ghostlock-consumer-futex-lock-pi-2026-10-01.md`, `reports/ghostlock-reference-comparison-2026-10-01.md`.
- Final: REFUTED. Consumer family confirmed, variant accepted.

## 13. freeing `f_chain` before consumer preserves `pi_blocked_on` path

- Original: teardown order trick keeps stale path.
- Plausible because: lifetime reasoning.
- Refuted by: graph-preservation requires no teardown; `h16_static` double probe + P3 `fwrq_alive=1` shows frame must stay alive; free breaks window.
- Current: `reports/ghostlock-h16-source-control.md` §7, §10.
- Final: REFUTED. No free/reuse inside window; alive proven.

## 14. H16 live-retarget is natural / principal memory-control mechanism

- Original: direct 8B write to live `[W_waiter+0x38]` from another thread is the path.
- Plausible because: slot is the exact word consumer reads twice (H16.4/H16.7).
- Refuted by: zero precedent in 5 external ports; all replace whole object after waiter return; Aquaman census finds zero usable carriers (heavy/priv/transient only, PI +0x10 LEA register-only).
- Current: `reports/ghostlock-reference-comparison-2026-10-01.md` §4-5, `reports/CURRENT_STATE.md`.
- Final: SUPERSEDED. Demoted to secondary; principal is post-free stack reuse + disclosure (not yet demonstrated on Aquaman).

## 15. `MSG_PEEK` plumbing proves reclaim

- Original: `sends_ok` + peek sentinel = reclaim.
- Plausible because: plumbing passed 512/512.
- Refuted by: `mm_reclaim_probe` A/B/control FAIL `reclaim_hits=0`; peek is plumbing, not order-2 capture; no verifier.
- Current: `reports/mm-reclaim-probe-2026-10-01.md`.
- Final: REFUTED as proof. Plumbing only.

## 16. `dist=0` proves absolute waiter offset on stack

- Original: SP equality gives absolute waiter address.
- Plausible because: `sp_futex == sp_poll` looks like layout.
- Refuted by: proves same stack page / SP base reuse only; absolute waiter offset (lab SP0-0x2b0 vs stock conjecture SP0-0x2c8) still unknown; KASLR + config shift frames.
- Current: `reports/ghostlock-h16-targeted-write.md` §2.
- Final: REFUTED as absolute proof. Relative relation only.

## 17. reconstructed page table automatically proves current MMU state

- Original: table bytes = active permissions.
- Plausible because: descriptors decode RW/XN.
- Refuted by: reconstruction shows descriptors compatible with RWX for those regions; effectively active state at execution point not demonstrated (SCTLR, live enable, timing).
- Current: `reports/bl33-control-primitive-round37.md` + round38 correction.
- Final: SUPERSEDED. Downgraded to descriptor-compatible wording.

## 18. module presence in vendor proves runtime usage

- Original: 28 `.ko` present means in use.
- Plausible because: vendor ships what it loads.
- Refuted by: presence vs `insmod` are different facts; `modules.dep` is metadata, `srcversion` is identity; `/proc/modules` / init logs never collected.
- Current: `reports/vendor-modules.md` (Presence vs runtime usage), `reports/CURRENT_STATE.md`.
- Final: REFUTED as usage proof. Presence only.

## 19. `98% config match` equals reproduction

- Original: 98.10% match means kernel reproduced.
- Plausible because: number is high.
- Refuted by: 2.8x size gap (26 MiB vs ~9.3 MiB container), 190 CRC diffs, 13 missing symbols, wrong DTB, DVB dropped, media stack differs.
- Current: `reports/rebuilt-kernel.md` §6 verdict.
- Final: REFUTED. Approximation with quantified gap, not reproduction.

## 20. `190 CRCs different` means 190 independent source differences

- Original: each CRC = independent source divergence.
- Plausible because: count is large.
- Refuted by: some CRCs are config-derived (`kmalloc_caches`, `dev_err`); split not measured per-symbol; 190 is upper bound on what config could recover.
- Current: `reports/vendor-modules.md` §3 caveat, `reports/rebuilt-kernel.md` §4.
- Final: SUPERSEDED. Upper bound only.
