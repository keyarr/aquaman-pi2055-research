# GhostLock reachability (Phase 10)

Probe: tools/ghostlock_reachability.c. Benign by construction: only tests
dispatch and argument validation, never sets up a PI pair, never attempts
deadlock, never touches another task's waiter.

## What each check proves

1. WAIT_REQUEUE_PI uaddr==uaddr2 -> EINVAL: handler exists (otherwise ENOSYS)
   and initial barrier of futex_wait_requeue_pi reached.
2. CMP_REQUEUE_PI uaddr1==uaddr2 -> EINVAL: requeue_pi barrier of
   futex_requeue reached.
3. CMP_REQUEUE_PI cmpval mismatch -> EAGAIN: get_futex_key on both sides
   + comparison succeed (path reaches hash bucket).
4. CMP_REQUEUE_PI invalid uaddr -> EFAULT: no crash on fault.
5. WAIT_REQUEUE_PI val mismatch -> EAGAIN: futex_wait_setup reached.
6-7. Self LOCK_PI/UNLOCK_PI -> 0: rt_mutex PI operational.

## Host validation

Compiled with gcc and run on kernel 7.0.9 x86_64 (patched):
7/7 PASS. Expected: these checks are pre-corruption, identical on vulnerable
and patched kernels. The probe DOES NOT distinguish vulnerable from patched —
it merely confirms "path reachable from shell". The distinction derives from Phase 1
(source analysis) + EDEADLK race test below.

## Device test run (2026-09-29, adb, static ARM64 API 28)

Kernel: 4.9.113 #1 SMP PREEMPT Tue Sep 6 12:53:43 CST 2022 armv8l
(gcc Linaro 6.3.1 20170109, jenkins@c5-mitv-cm-build06.bj).
Result: 7/7 PASS, exit 0. Device remains healthy.
Status: PATH REACHABLE — CONFIRMED ON AQUAMAN KERNEL.

## Race EDEADLK (tools/ghostlock_race_stats.c, step 2 of progression)

5 rounds, 5x errno=35 (EDEADLK). Every round entered
rt_mutex_start_proxy_lock via CMP_REQUEUE_PI and returned through the
remove_waiter rollback with waiter->task != current. Device healthy, uptime
continuous, no reboot. Equivalent to --race/--dry-run in dnlid.
Status: ROLLBACK REACHABLE — CONFIRMED ON AQUAMAN KERNEL.
Next: offline lab (Phase 11) before any trigger with reclaim.

## Risk

Negligible. No call creates a real PI waiter (mismatched values,
zero timeouts, anonymous private futexes). Can run via adb shell without
panic risk. Leaves no persistent state: no lingering threads, no open fds.

## Next step on device (when authorized)

adb push + run, capture output. 7/7 PASS => PATH REACHABLE
(CONFIRMED ON AQUAMAN KERNEL for dispatch; vulnerability itself remains
INFERRED until Phase 12).
Any ENOSYS => PATH UNREACHABLE, abort everything.
