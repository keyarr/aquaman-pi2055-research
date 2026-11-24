# Consolidated inventory of primitives - rounds 1-65 (2026-11-19)

Scope: Xiaomi Mi TV Stick 1080p (MiTV-AESP0, aquaman, S805Y/GXL), Android 9
PI.2055, kernel 4.9.113. USB gadget `1b8e:c003` bcdDevice 0x0007, stage 16
(TPL/BL33-U-Boot), RAM-only. Nothing here is persistent.

Primary sources: `reports/PRIMITIVE_INVENTORY_2026-11-19.md` (P1-P14),
`reports/CURRENT_STATE.md`, `reports/EVIDENCE_MATRIX.md`,
`reports/round65-2026-11-19-consolidation.md`, `reports/INVALIDATED_HYPOTHESES.md`.
This file does not replace any of them; it merely consolidates them into a
single entry point for resumption.

Status: HARDWARE_REPRODUCED (2+ sessions or oracle + restore),
HARDWARE_OBSERVED (one session), OFFLINE_ONLY, REFUTED, INCONCLUSIVE.

## 1. Demonstrated primitives

| # | Primitive | Evidence | Status | Real limitation |
| - | --------- | -------- | ------ | --------------- |
| P1 | WRITE_MEM 0x01 / FILL_MEM 0x03: RAM write at chosen address and bytes | rounds 39/43/46 | REPRODUCED | 32-bit address; non-Secure RAM; volatile |
| P2 | cmd_tbl handler redirect (`ldr x4,[x19,#0x10]; blr x4`), same-cycle, reversible | rounds 42/46 | REPRODUCED | only points to existing code |
| P3 | execution of host bytes INSIDE BL33: stub `mov w0,#0;ret` at 0x37800000 via redirected `false` handler; `false: failed -> success`; clean restore | plan-smc-gate..., Phase 1 GO | REPRODUCED | dcache flush used; icache flush (idx 60) never combined |
| P3b | hook at 0x37e265fc (`blr x4` in do_bootm_linux wrapper): stub writes to decompressed image, returns via `blr x4` + `br 0x37e26600` | exec-toctou v1/v2 | REPRODUCED | hook executes and boot occurs, but bytes do not reach the executed kernel |
| P4 | cmd_tbl mapped: 116 entries, base 0x37f60eb0, stride 0x30, handler at +0x10; live == offline | root-final-analysis/04, round46 | OBSERVED | stable across boots; htab is not |
| P5 | bulk download 0x32 armed by `bulkcmd "download mem ... normal ..."`; 16 MiB at 0x1080000 in 0.8 s with sha256 read back | plan-smc-gate..., download_mem.py | REPRODUCED | 64 KiB/chunk payload, `OK!!` reply |
| P6 | bulkcmd 0x34 as oracle (`false -> failed:`, `true -> success`); mread 0x33 reads RAM | optimus.py, all BL33 rounds | REPRODUCED | `fastboot oem` only returns OKAY; `help` broken |
| P7 | `imgread kernel boot 0x1080000` + `bootm 0x1080000` boots stock in-session; USB drops ~4.7 s | buffer-equals-loadaddr-proof E4/E5 | REPRODUCED | still goes through the SMC |
| P8 | RAM read via MREAD 0x02 and 0x33/0x34 with host-chosen address | optimus.py, rdlarge-bulk-read | REPRODUCED | 0x12 RD_LARGE_MEM dead; MREAD of 0x05100000 drops the gadget |
| P9 | wrapper 0x37e19ea8 (`mov x0,#0x820000ff; smc #0`) with site1 args returns x0=0 and leaves plaintext kernel at 0x1080000 (`ANDROID!`, 0x959000), without eret | plan-smc-gate..., kernel-ram-patch-v2 section 9.2 | OBSERVED (2 sessions) | worked once; repeating froze; likely cause `bl 0x37e19310` at 0x37e19ee8 without icache flush |
| P10 | authoritative env htab 0x37ee7278: setenv and WRITE to data pointer reach the parser; `run storeargs` rebuilds 832 B bootargs | rounds 51/52 | REPRODUCED | entry pointer changes on every rebuild; arena 0x33e18000 is stale shadow |
| P11 | DTB of 58,280 B at 0x01000000, d00dfeed, clean dtc round-trip, 376 nodes/1798 props | aquaman-dtb-extraction, artifacts/aquaman.dtb | REPRODUCED | pre-fixup blob, without /chosen; delivery to Linux not confirmed |
| P12 | GhostLock: FWRQ/FCRQ trigger -> EDEADLK 5/5; FUTEX_LOCK_PI consumer with differential; f_target/f_alt fidelity | CURRENT_STATE | REPRODUCED | zero VA bytes; reclaim FAIL; H16 write 0/33 |
| P13 | `keyman read` returns 3 ASCII blobs (sn2, bt_rc_mac, netflix_mgkid) in host-chosen RAM | round61 Phase A | OBSERVED | not AES keys for bootloader.img/boot.img (0 hits/90 tests) |
| P14 | `read_raw_img <part> <addr> <off> <size>` brings real eMMC bytes into host-chosen RAM; `boot` -> `ANDROID!` | round65 | REPRODUCED | bootloader ciphertext only; 0 FIP magic in 15 windows |
| P15 | `0x11 WR_LARGE_MEM`: control OUT `0x40/0x11` with `<u32 addr><u32 len>` + bulk OUT EP `0x02`, no reply/denylist/64 B cap | `wr_large_mem_test.py`: `0x37800000 <- ABCD`, readback `41424344`, restore zero | REPRODUCED (resumed 2026-11-19) | declaring len > bytes sent traps the gadget in `do_bulk_complete` (wedge) |

## 2. Vulnerabilities vs anomalies

Proven vulnerabilities (real attack primitive):
- P1/P3/P3b: arbitrary code execution in BL33 context (outside the gate's trust
  chain). It is the most powerful primitive obtained to date.
- P10: write to the authoritative source of the boot environment (htab), with
  consumption observable by the parser. State vulnerability, not memory.
- P12: PI futex use-after-free with trigger and consumer reproduced on hardware.
  Real kernel vulnerability, without an exploitation weapon.
- P14: raw partition read via diagnostic interface.

Unexplained anomalies / refutations:
- P3b executes and changes BOOT_ID, but the kernel that boots is stock. It is
  not an "ignored patch": it is an "unknown executed copy". Classified as an
  anomaly, not a vulnerability failure.
- P9 returns plaintext once and freezes on the second. State behavior
  (cache/TLB), not a proven EL3 barrier.
- Whole-string revert of 3 androidboot.* fields (rounds 53/56/58): the value
  returns to stock after passing through bootm. Transport anomaly, not a
  demonstrated security implementation.
- `fastboot boot` ignores the sent file (round65): identical signature for
  stock, 2 flips and XXXXXXXX header. This invalidates conclusions based on
  "payload rejected by the gate", but does not prove the gate does not exist.

## 3. Chains and missing links

| Chain | Status | Critical missing link |
| ----- | ------ | --------------------- |
| A: P3b -> patched kernel -> uid=0 | REFUTED in the 3 tested forms (commit_creds/marker/spray) | find where the executed kernel is copied from; BL33 -> Android output channel |
| B: P10 -> cmdline -> root | REFUTED at the observable arrow (fdt chosen NO-GO, 3 fields revert) | observe env_get -> fdt_setprop; real transport to kernel |
| C: P12 -> disclosure -> R/W -> cred | OPEN at the disclosure bottleneck | first kernel VA anchor |
| D: P9/P14 -> custom boot | NOT TESTED in useful form | repeatable P9 + reachable executed copy |

## 4. Limitations preventing promotion of primitives

- SMC 0x820000ff is a content-check in BL31; stock image passes. Bypass is not
  necessary if the intervention is post-decrypt.
- MREAD of Secure memory (0x05100000) drops the gadget. Draw no conclusions
  about SMC from that drop.
- RUN_IN_ADDR 0x05 and MODIFY 0x04 kill the session; clear_halt fails errno 75.
- Infinite loop in BL33 (ARMd scan) takes the device off the bus and required an
  authorized power cycle. Do not repeat.
- Handoff instrumentation: only `cbz 0x37e24cf8` is abort-safe; x25 is unstable;
  later points drop the gadget (rounds 62-64).
- No root: uid=2000, Enforcing, /proc/cmdline and
  /proc/device-tree/chosen/bootargs denied to shell.

## 5. Surfaces not yet sufficiently investigated

1. Locating the executed copy of the kernel (post-decrypt, pre-eret): cache,
   relocate, second buffer, copy in Secure memory. Output channel via DTB
   (`androidboot.scan` -> `getprop ro.boot.scan`) avoids post-freeze MREAD.
2. 0x820000ff command matrix with real GO + NOP of bl 0x37e19310 + icache
   flush, one cmd per session.
3. Hook at points later than 0x37e265fc, or patch of page tables / do_eret.
4. Kernel disclosure from uid=2000 outside cgroupfs/BPF/proc.
5. 0x11 WR_LARGE_MEM and USB command parsing (usb_pcd.c).
6. Reuse of P3 with oracles that survive reboot.

## 6. Inventory of evidence to confirm before new experiments

- `/tmp/` contains unconsolidated artifacts: exec-toctou*.md,
  diag-toctou*.md, v2/tramp_v2.bin, v2/trigger, stub/kernel_patch_v3.bin.
- `reports/round59-*`, `round60`, `round61`, `round62-64`, `round65`,
  Offline analysis reports have not yet entered CURRENT_STATE.md (which dates from
  2026-10-02). This file is the provisional index until official consolidation.

Updated 2026-11-19 (resumption). No new primitive demonstrated in this
resumption so far.
