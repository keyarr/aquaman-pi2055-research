# INVALIDATED_HYPOTHESES - closed leads, do not reopen without new evidence

History is preserved. These entries exist so nobody re-spends a session on a
refuted path. Each entry: original hypothesis, why it looked plausible,
refuting evidence, current document, final state.

> Root context (2026-11-23): persistent root now exists via the ODM init
> service (`reports/root-via-odm-2026-11-23.md`). Rows saying "no root" or
> "root unchanged" are scoped to the path named in that row, not to the
> device. The root read surface is recorded in
> `reports/root-read-surface-2026-11-23.md`.
>
> SELinux context (2026-11-23): the device is now Permissive through a kernel
> module loaded from the ODM rc file
> (`reports/selinux-permissive-via-module-2026-11-23.md`). The rows below that
> refute `androidboot.selinux=permissive` via U-Boot cmdline stay REFUTED for
> that transport; they do not contradict the module path.

## 1. test payload really executed via `fastboot boot`

- Original: 4096-byte plaintext boot.img was accepted, stub ran, device returned in ~30s.
- Plausible because: USB drop + delayed adb return looked like execution.
- Refuted by: `reports/_archive/fastboot-boot-verdict.md` M1a 16-21s no-delay return = rejection; E7a vs E7b vs E7c identical timing for plaintext/INVALID.
- Current: `reports/fastboot-memory-flow.md` sec 6, `reports/_archive/buffer-equals-loadaddr-proof.md` E7.
- Final: REFUTED. Unsigned legs die at SMC before format check.

## 2. `download != boot source`

- Original: download buffer and `bootm` source are disjoint; that explains all failures.
- Plausible because: khadas headers show BUF=0x10200000 vs loadaddr=0x1080000, and early probes at wrong addresses failed.
- Refuted by: E5 vs E6 - same `bootm(Y)`, different outcome depending only on prior download; download changed bytes `bootm(Y)` read.
- Current: `reports/fastboot-memory-flow.md` sec 4, `reports/CURRENT_STATE.md` (overlap proven).
- Final: REFUTED. Overlap proven; exact equality not proven.

## 3. download buffer is `0x10200000`

- Original: `X = 0x10200000` is a device fact from `include/g_dnl.h:18`.
- Plausible because: closest public tree says so.
- Refuted by: device U-Boot is encrypted; reference value never measured on this build; E5/E6 compatible with range of BUF values.
- Current: `reports/fastboot-memory-flow.md` sec 2, `reports/_archive/buffer-equals-loadaddr-proof.md` header note.
- Final: REFUTED as device fact. Reference-tree derivation only.

## 4. `max-download-size` proves buffer position

- Original: `max-download-size 0x08000000` is incompatible with buffer at 0x1080000, proves X != Y.
- Plausible because: formula `ddr_size_usable` looked discriminative.
- Refuted by: arithmetic - neither 0x10200000 (0x22E00000) nor 0x1080000 (0x31F80000) yields 0x08000000; inverse gives BUF=0x2B000000.
- Current: `reports/fastboot-memory-flow.md` sec 3, `tools/fastboot_addr.py`.
- Final: REFUTED. Number cannot discriminate hypotheses.

## 5. `X = 0x10200000` is device fact

- Same as 3, kept separate because it appears in `reports/_archive/bootm-test-image.md` / `reports/_archive/set-active-sink.md` gate analysis.
- Refuted by: same as 3.
- Current: banners in both files + `reports/fastboot-memory-flow.md`.
- Final: REFUTED as device fact. Injection address for those analyses is 0x1080000 (overlap), operative gate is SMC.

## 6. vermagic `4.9.y` proves module origin

- Original: `4.9.y` != `4.9.113` so modules came from different build.
- Plausible because: normally vermagic pins sublevel.
- Refuted by: repo's own build produces identical `4.9.y`; Amlogic `Makefile:1221` flattens stamp via `UTS_RELEASEY`.
- Current: `reports/vendor-modules.md` sec 2.
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
- Current: `reports/_archive/rebuilt-kernel.md` sec 7, `reports/repo-state.md`.
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
- Current: `reports/bl33-offline-round10.md` sec 4.
- Final: REFUTED. Strong U-Boot/Amlogic fragment; base/entrypoint still unproven.

## 11. old SMC count is correct

- Original: 11 SMC sites (round8 sec 5).
- Plausible because: opcode constant looked right.
- Refuted by: compared against `0xD4000000`, not valid `svc`/`hvc`/`smc`; 5 real in code window, 15 `smc #0` in full image.
- Current: `reports/bl33-offline-round10.md` sec 3, round14 census.
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
- Current: `reports/ghostlock-h16-source-control.md` sec 7, sec 10.
- Final: REFUTED. No free/reuse inside window; alive proven.

## 14. H16 live-retarget is natural / principal memory-control mechanism

- Original: direct 8B write to live `[W_waiter+0x38]` from another thread is the path.
- Plausible because: slot is the exact word consumer reads twice (H16.4/H16.7).
- Refuted by: zero precedent in 5 external ports; all replace whole object after waiter return; Aquaman census finds zero usable carriers (heavy/priv/transient only, PI +0x10 LEA register-only).
- Current: `reports/ghostlock-reference-comparison-2026-10-01.md` sec 4-5, `reports/CURRENT_STATE.md`.
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
- Current: `reports/ghostlock-h16-targeted-write.md` sec 2.
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
- Current: `reports/_archive/rebuilt-kernel.md` sec 6 verdict.
- Final: REFUTED. Approximation with quantified gap, not reproduction.

## 20. `190 CRCs different` means 190 independent source differences

- Original: each CRC = independent source divergence.
- Plausible because: count is large.
- Refuted by: some CRCs are config-derived (`kmalloc_caches`, `dev_err`); split not measured per-symbol; 190 is upper bound on what config could recover.
- Current: `reports/vendor-modules.md` sec 3 caveat, `reports/_archive/rebuilt-kernel.md` sec 4.
- Final: SUPERSEDED. Upper bound only.

## 21. template-side `EnableSelinux` reaches Linux via `storeargs`

- Original: poking the final `bootargs` failed (E1 round48), but the template var `EnableSelinux` plus `run storeargs` rebuilds `bootargs` with the marker, since `storeargs` text holds `androidboot.selinux=${EnableSelinux}`.
- Plausible because: the reference is literally in the live script, and the 9 B WRITE reads back with neighbors intact.
- Refuted by: round49 hardware run. WRITE `enforcing`->`permissiv` @ `0x33e1d6c4` with readback, pre-storeargs state `EnableSelinux=permissiv` / `bootargs` still `enforcing`, `run storeargs` -> `success` yet `bootargs` 832 B byte-identical `enforcing`. Functional control (`setenv EnableSelinux permissiv` + `run storeargs`, both `success`) also left `bootargs` identical, so it is not a WRITE-visibility artifact. No boot run: nothing new to transport.
- Round51 correction: both round49 observations read the stale arena (`0x33e1d6c4` / `0x33e1d73f`), never the htab. Round51 hardware oracle proves `setenv` flips `test ${EnableSelinux}` while WRITE to the arena does not, with entry `0x33e2ff40` data `0x33e32910` vs arena `0x33e1d6c4`. So: the previous experiments did not reach the authoritative runtime object; their verdicts on the consumption of the value must be reinterpreted according to the new oracle.
- Round52 overturn: the htab `bootargs` with `permissiv` produced by round49's control run was still present at round52 entry (832 B sha `df6c9576`, single-field diff vs arena), and round52 re-ran the leg controlled both directions (`df6c9576` byte-identical rebuild + `c5a4b5e3` restore, pointer moves each rebuild). Live `preboot` contains `run storeargs`, the boot-time rebuilder. `0x33e18000` is a stale/shadow copy observed experimentally and must not be used as oracle post-`setenv`.
- Current: `reports/round49-bootargs-template-selinux.md`, `reports/round51-env-htab-oracle.md`, `reports/round52-write-htab-template.md`.
- Final: REFUTED for the stale-oracle observation; REPRODUCED through the htab (`setenv`/WRITE -> htab -> `storeargs` -> htab `bootargs`). Kernel transport tested round53 and REFUTED for every env form tried (arena direct, arena template-stale, htab authoritative); no cmdline-to-Linux demonstrated; root unchanged.

## 22. htab `bootargs` reaches Linux verbatim via `bootm`

- Original: round52 proved parser consumption, so handing the verified htab value to the E4-proven `imgread`+`bootm` pair should surface the marker in `ro.boot.*`.
- Plausible because: the string was byte-verified (`df6c9576`) one step before `bootm`, and round50 disasm shows `bootm`/`fdt_chosen` reading the same htab.
- Refuted by: round53 hardware run. `imgread` success + `bootm`, stock Android return ~15 s, but `ro.boot.selinux=enforcing` + `reboot_mode normal` vs verified `permissiv`+`fastboot` (E1 double-field signature, now vs authoritative bytes).
- Round54 offline follow-up: 9/9 `bootargs`-name consumers re-derived, all BL33 writers use the env string (bootm/bootvx appends only); kernel entry is an EL2->EL1 eret (`x2`=FDT), no secure handoff at entry; running `/proc/config.gz` (5691 lines) says bootloader-cmdline-only; fixup target == handoff blob with room to spare. One link left: whether `fdt_chosen` ran+succeeded on this path.
- Current: `reports/round53-htab-transport.md`, `reports/round54-offline-fdt-path.md`.
- Final: REFUTED for this form, one run + full static map. No more boots until a static read predicts the pair.
- Side finding: `setenv` does not rewrite the `0x33e18000` blob (import image vs hash store); blob restored by WRITE, final verify stock-identical. `0x33e18000` is a stale/shadow copy observed experimentally and must not be used as oracle post-`setenv`.
- Current: `reports/round49-bootargs-template-selinux.md`, `reports/round51-env-htab-oracle.md`.
- Final: REFUTED for the stale-oracle observation on this build. No script-consumption of a mutated env value has ever been observed here.

## 23. `bootm` re-runs `storeargs`, which is why the marker reverts

- Original: `bootm` reaches the boot-decision script set and `preboot` contains `run storeargs`, so a rebuilt `bootargs` from the template would explain the whole-string revert seen in rounds 53/56/58.
- Plausible because: `bootm` demonstrably calls `parse_stream` and demonstrably mutates the env, and `storeargs` is the only thing that rebuilds `bootargs`.
- Refuted by: static census of every `parse_stream` call inside `bootm`'s direct-call closure. Twelve of them, and none is `preboot`, `storeargs` or `bootcmd`. Reproduce with `python3 tools/bootm_env_closure.py reports/round14-bl33-persist/bl33-37e18000.bin 0x37e18000`.
- Current: `reports/_archive/ROOT_FINAL_ANALYSIS.md` N1, `reports/root-final-analysis/01-bootm-env-closure.txt`, `reports/CURRENT_STATE.md` BL33 table.
- Final: REFUTED for the direct-call graph. Scoped negative, `blr` counted not followed.

## 24. the environment was silently re-imported from the default env between our verified read and `fdt_chosen`

- Original: round50 documented that `do_env_import` (`0x37e58c10`) and `set_default_env` (`0x37e58b24`) exist in the device binary and noted "a re-import path exists in-code", explicitly as a lead for a future round. Re-importing the compiled-in defenv would overwrite the whole htab with stock values, which is exactly the observed signature: every mutated field back to stock, including `boardid` back to `3` rather than the defenv `ff`.
- Plausible because: the observed revert is whole-string and whole-table, which is what `himport_r` of the defenv blob would do, and no other single mechanism accounts for all four fields at once.
- Refuted by: `himport_r` (`0x37eaa264`) has exactly three callers image-wide (`0x37e581a0`, `0x37e58b9c`, `0x37e58c9c`). `bootm`'s 236-function `bl` closure contains none of them, and `imgread`'s 28-function closure contains no env function at all. `env_relocate` (`0x37e58d94`, proven by its `!bad CRC` string and its `env_get("silent")` tail) has a single caller `0x37e24ad8`, inside a zero-direct-caller late-init function reached from the init function-pointer table, which runs before the burning session attaches.
- Current: `reports/_archive/ROOT_FINAL_ANALYSIS.md` N2, `reports/root-final-analysis/01-bootm-env-closure.txt`, `reports/CURRENT_STATE.md` BL33 table.
- Final: REFUTED for the direct-call graph of the tested path. Scoped: indirect `blr` edges and the indirect OS dispatch into the FDT fixup stage are not followed.

## 25. round57 FDT-A: the delivered FDT comes from the boot image header at `0x1080000`

- Original: round57's FDT candidate table lists FDT-A as "runtime, from image at `0x1080000` header parse", with `bootm_load_os` computing the address from the image header.
- Plausible because: `bootm_load_os` does parse a header and does store `ft_addr`/`ft_len`, and the ramdisk and dtbo candidates are read from partitions the same way.
- Refuted by: the DTB leg specifically. `bootm` executes the literal Hush command line `store dtb decrypt ${dtb_mem_addr}` at `0x37e25110`, and defenv has `dtb_mem_addr=0x1000000`. The board DTB is decrypted out of `dt.img` into RAM during `bootm`, which is also why the recovered dump at `0x01000000` has no `/chosen` node: it is the pre-fixup blob. This does not touch the ramdisk or dtbo legs, which are separate `store` invocations in the same sequence.
- Current: `reports/_archive/ROOT_FINAL_ANALYSIS.md` N4, `reports/root-final-analysis/01-bootm-env-closure.txt` and `02-defenv-scripts.txt`.
- Final: SUPERSEDED for the DTB row only. round57's pointer-identity conclusions are unaffected.
