# GhostLock source check — aquaman 4.9.113 (Phase 1)

Date: 2026-09-29. Offline analysis, without touching device.

## Tree analyzed

`.src/linux-amlogic` (McMCCRU/linux-amlogic, HEAD 3d4ab79e,
base 2019-06). Makefile: VERSION=4 PATCHLEVEL=9 SUBLEVEL=113.

PROVENANCE WARNING: Not the exact aquaman source. See
`reports/exact-source.txt`: no exact source was found; the closest
to official Xiaomi is dangal-p-oss (different device, same 4.9.113).
Everything below applies to an "adjacent Amlogic 4.9.113 kernel", not
to the exact PI.2055 binary byte-for-byte.

## Phase 1 questions

1. Does remove_waiter() use current? YES.
   kernel/locking/rtmutex.c:1099-1111:
   raw_spin_lock(&current->pi_lock); rt_mutex_dequeue(lock, waiter);
   current->pi_blocked_on = NULL; raw_spin_unlock(&current->pi_lock);
   And at the tail: rt_mutex_adjust_prio_chain(..., NULL, current) (line 1146).
   This is the exact pattern replaced by waiter->task in patch 3bfdc63936dd.

2. Does waiter->task exist? YES. kernel/locking/rtmutex_common.h:28,
   `struct task_struct *task`, populated in task_blocks_on_rt_mutex
   (rtmutex.c:997, waiter->task = task).

3. Does rt_mutex_start_proxy_lock() receive a separate task? YES. rtmutex.c:1691,
   (lock, waiter, task). Calls task_blocks_on_rt_mutex(lock, waiter, task,
   FULL_CHAINWALK) and on error invokes remove_waiter(lock, waiter) (line 1718).
   On this path, waiter->task (waiting victim) != current (requeuer).
   CVE condition is present.

4. Does rollback with remove_waiter() exist? YES, two sites:
   rt_mutex_start_proxy_lock (1719) and rt_mutex_finish_proxy_lock (1777).
   The former is the GhostLock trigger via futex_requeue().

5. Is FUTEX_CMP_REQUEUE_PI implemented? YES. futex.c:3283-3284, dispatches to
   futex_requeue(..., requeue_pi=1). futex_requeue executes proxy trylock +
   rt_mutex_start_proxy_lock with this->task of the victim (lines 1955-1957).
   Full requeue_pi chain present.

6. Is FUTEX_WAIT_REQUEUE_PI implemented? YES. futex.c:2853
   futex_wait_requeue_pi(), waiter on caller's stack (local rt_waiter,
   line 2858), classic stack-UAF scenario following corrupted rollback.

7. Is CONFIG_FUTEX_PI enabled in real config? YES by construction.
   4.9 lacks a separate CONFIG_FUTEX_PI symbol (only CONFIG_HAVE_FUTEX_CMPXCHG exists);
   PI support stems from CONFIG_FUTEX=y + CONFIG_RT_MUTEXES=y, both =y in
   aquaman-config, plus CONFIG_PREEMPT=y. init/Kconfig: FUTEX select RT_MUTEXES.
   futex.c in this tree contains no #ifdef excluding the PI path.

8. Vendor patches modifying the path? NOT FOUND in this tree.
   rtmutex.c and futex.c show no Amlogic/Xiaomi hunks in the PI path
   (textually matches upstream 4.9.113 in this file). The config contains
   CONFIG_AMLOGIC_SLUB_DEBUG (unset), irrelevant for rtmutex.
   Caveat remains: exact PI.2055 binary may contain vendor patches invisible
   without exact source or vmlinux.

## Phase 1 classification

VULNERABILITY PRESENT (in analyzed 4.9.113 tree; exact aquaman binary =
INFERRED, pending confirmation via runtime kernel disassembly or official source).

Conclusion not based on version string alone: bodies of remove_waiter,
proxy lock, and requeue were read and compared with the upstream patch diff
(current -> waiter_task across the three sites).
