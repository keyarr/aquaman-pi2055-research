# GhostLock risk + offline validation (Phase 11 + Phase 12)

## Risk of on-device testing

- Real GhostLock = stack UAF with probabilistic reclaim. Clean failure
  rate vs panic: in hazel, "can fail cleanly or panic and reboot".
  Without UART, panic = frozen display until physical power cycle.
- What DOES NOT corrupt: Phase 10 probe (no real waiter), dnlid --dry-run
  and --race (stop at EDEADLK, halting before corruption).
- What CAN panic: any attempt to complete rollback with a divergent
  waiter (real trigger), even without reclaim.
- Mitigations without UART: pstore/last_kmsg for post-mortem diagnostics
  (check /sys/fs/pstore after reboot); bootreason; maintain observation
  window via adb (if adb disconnects = reboot or hang).

## Proposed testing progression (stop at first red light)

1. reachability 7/7 (risk ~0). GREEN on device 2026-09-29.
2. dnlid --dry-run/--race: EDEADLK statistics (risk ~0, only proves
   rollback is reached reliably). GREEN on device 2026-09-29:
   tools/ghostlock_race_stats.c, 5/5 EDEADLK, device healthy, no reboot.
3. Real trigger without reclaim (single run, without shell-readable pstore:
   diagnostic = adb alive/dead + uptime). PENDING hardware owner decision.
   Note: pstore denied to shell reduces post-mortem fidelity; recheck
   as root later.
4. Reclaim + read-only validation (reading back the fake fops itself,
   as hazel does) prior to any write. PENDING offsets.
5. Write to cred only after step 4 is green and repeatable.

## Phase 11 (offline lab)

Not executed here: no ARM64 QEMU configured in this workspace. Options,
ordered by cost:
a) Userspace harness for futex trio (waiter/owner/CMP) against a local
   4.9.113 Amlogic kernel compiled with KASAN + DEBUG_RT_MUTEXES in an
   ARM64 virt QEMU — proves logical UAF with sanitizer report.
b) Compilation of dangal with aquaman-config for pahole (also serves
   Phase 3 and initial profile construction).
Neither requires the physical device. Recommended before step 3 above.

## Classification for this phase

- Reachability dispatch: PROBABLE (confirmed by running the binary).
- EDEADLK race: INFERRED (code confirms path; actual rate on hardware).
- Reclaim/stack-stamp on aquaman: NOT PROVEN.
- Panic without UART: real risk, mitigable via progression ladder + pstore.
