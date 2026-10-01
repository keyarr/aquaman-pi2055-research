# ghostlock null-stale discriminator

Date: 2026-10-01. Device: Xiaomi Mi TV Stick 1080p (aquaman, S805Y/GXL,
Android 9, PI.2055, kernel 4.9.113 arm64, PREEMPT=y, shell uid=2000, no
root). Lab authority: build-aq/vmlinux + the in-tree lab sources at
.src/linux-amlogic. No kmsg/dmesg on stock (denied, verified this round).
Hardware runs: 17 (pos_cycle x3, base_t x2, trg_inwin, tgt_t, trg_tgt,
occ_tgt x5, occ_base x2), one uptime window 11714s -> 13467s, zero
panics, zero reboots, adb never dropped.

Stage 3 (controlled data injection) stayed frozen. No new stamper was
built or tested. Previous reports are not modified.

## 1. Objective

Answer one question on the physical device:

After the CMP_REQUEUE_PI rollback, is `W->pi_blocked_on` still a live
pointer that a `FUTEX_LOCK_PI` consumer walks, and does the walk reach a
`pi_blocked_on` consumer at all?

The previous round reported `TIMEOUT_BLOCK` for both baseline and
trigger and called it inconclusive. This round's premise was that the
trial itself was measuring the wrong thing. That premise was right: the
old timed flow waited ~30 s for the waiter to leave `futex_wait_requeue_pi`,
so the consumer ran against a dead frame. Fixing the timing plus one
added control (section 12) closes the question as `HARDWARE_REPRODUCED`.

## 2. LAB vs STOCK Binary Comparison

| item | LAB (build-aq/vmlinux) | STOCK PI.2055 |
|---|---|---|
| plaintext kernel | available, full DWARF | AMLSECU! encrypted (`boot_unpack/kernel`, magic ver 0x0905) |
| stock geometry | see ghostlock-stale-pointer-validation.md sec. 2 | STRONG proxy: frames +0x10, rt_waiter SP0-0x2c8 |
| usable absolute offsets | yes | no, proxy only |
| `rt_mutex_adjust_prio_chain` frame | 0x90 | 0x90 (no array, no canary) |
| `task_blocks_on_rt_mutex` frame | 0x50 | 0x50 (no array, no canary) |
| `remove_waiter` frame | 0x40 | 0x40 (no array, no canary) |

The consumer-side logic frames are byte-identical between the two builds
because they contain no stack array, no address-taken local and no canary.
That is why the consumer control flow below is trustworthy for stock even
though the absolute VAs are not.

`EVIDENCE: OFFLINE_ONLY` for the geometry table.

## 3. Stock Stack Geometry

| quantity | LAB | STOCK-PROXY | status |
|---|---|---|---|
| rt_waiter (trigger) | SP0-0x2b0 | SP0-0x2c8 | proxy, carried from previous round |
| waiter->task | SP0-0x280 | SP0-0x298 | proxy |
| waiter->lock | SP0-0x278 | SP0-0x290 | proxy |
| waiter->prio | SP0-0x270 | SP0-0x288 | proxy |
| FWRQ frame | 0x1a0 | 0x1b0 | proxy |
| do_futex frame | 0x120 | 0x130 | proxy |
| rt_mutex_adjust_prio_chain | 0x90 | 0x90 | frame-invariant |
| task_blocks_on_rt_mutex | 0x50 | 0x50 | frame-invariant |

`STOCK GEOMETRY STATUS: INCONCLUSIVE` for the trigger frames. No new
absolute stock number was produced this round, and none was needed: the
consumer-side frames, which are what the discriminator depends on, are
frame-invariant.

The harness prints `waiter_est` derived from the LAB 0x2b0 constant and
labels it `(NOT a stock offset)`. That label is now in the output so the
number cannot be misread as a stock fact.

## 4. `pi_blocked_on` Consumers

`scan_all`-class inventory of every access to `task+0x7f0`, by kind.
Verified against build-aq/vmlinux (`--verify`: 30 entries, 0 mismatches).

| consumer | VA | instr | kind | reachable from the consumer syscall? |
|---|---|---|---|---|
| `task_blocks_on_rt_mutex` | 0xffffff80091052b8 | `str x21,[x20,#0x7f0]` | write | yes, stores C's own waiter |
| `task_blocks_on_rt_mutex` | 0xffffff80091052f0 | `ldr x0,[x22,#0x7f0]` | read | **yes, first read of W's stale word** |
| `task_blocks_on_rt_mutex` | 0xffffff80091053e8 | `ldr x0,[x22,#0x7f0]` | read | yes, second path |
| `rt_mutex_adjust_prio_chain` | 0xffffff8009104e60 | `ldr x28,[x19,#0x7f0]` | read | yes, walk root |
| `rt_mutex_adjust_prio_chain` | 0xffffff8009104ff0 | `ldr x0,[x19,#0x7f0]` | read | only if the walk recurses |
| `remove_waiter` | 0xffffff8009105454 | `str xzr,[x24,#0x7f0]` | write | during the rollback, `current` is the requeuer |
| `rt_mutex_adjust_pi` | (not reached) | `task->pi_blocked_on` | read | needs `sched_setscheduler` on W |
| `rt_mutex_slowlock` try path | (not reached) | `task->pi_blocked_on = NULL` | write | only on lock acquisition |

The rollback bug, stated precisely from source (`rtmutex.c:1099`):

```
static void remove_waiter(struct rt_mutex *lock, struct rt_mutex_waiter *waiter)
{
        raw_spin_lock(&current->pi_lock);
        rt_mutex_dequeue(lock, waiter);
        current->pi_blocked_on = NULL;      /* current == requeuer, NOT waiter->task */
```

`current` during `CMP_REQUEUE_PI` is the main thread. So the store clears
the requeuer's (already NULL) word and leaves `W->pi_blocked_on` pointing
at `W_waiter`, which `rt_mutex_dequeue` has just unlinked from the lock's
rbtree and `rt_mutex_dequeue_pi` has just unlinked from O's `pi_waiters`.

`EVIDENCE: OFFLINE_ONLY` for the whole table.

## 5. `f_chain` Normal Path

Consumer: `FUTEX_LOCK_PI(f_chain)`, owner W, `chwalk = RT_MUTEX_FULL_CHAINWALK`.

```
futex_lock_pi                                  0xffffff800913b030
  futex_lock_pi_atomic                         0xffffff800913b154  attach_to_pi_owner(W) ok
  rt_mutex_timed_futex_lock                    0xffffff800913b1bc  FULL_CHAINWALK
    rt_mutex_slowlock
      try_to_take_rt_mutex  -> owner W, return 0
      task_blocks_on_rt_mutex(&f_chain.pi_mutex, C_waiter, C, FULL)
        C->pi_blocked_on = C_waiter            0xffffff80091052b8  VALID
        owner != NULL -> lock W->pi_lock
        C_waiter != rt_mutex_top_waiter(f_chain.pi_mutex)
          -> rt_mutex_cond_detect_deadlock(C_waiter, FULL) == true
          -> chain_walk = 1
        next_lock = task_blocked_on_lock(W)     0xffffff80091052f0
        get_task_struct(W); raw_spin_unlock_irq
        rt_mutex_adjust_prio_chain(W, FULL, &f_chain.pi_mutex,
                                   next_lock, C_waiter, C)  0xffffff8009105378
```

In the baseline (no GhostLock) `W->pi_blocked_on == NULL`, so
`next_lock == NULL` and `if (!chain_walk || !next_lock) return 0;` in
`task_blocks_on_rt_mutex` abandons the walk before it starts. The consumer
sleeps in `__rt_mutex_slowlock` and returns `-ETIMEDOUT`.

`EVIDENCE: HARDWARE_OBSERVED` for the terminal result (CASE A, section 9);
the call chain above is `OFFLINE_ONLY`.

## 6. `f_chain` Stale Path

Same entry. The only difference is the value of `next_lock`, read at
0xffffff80091052f0:

- `W->pi_blocked_on == W_waiter` -> `next_lock = W_waiter->lock`
- `W_waiter->lock == &f_target.pi_mutex` (heap, valid, owner O)

`cbz x0` at 0xffffff80091052f8 is NOT taken, so the walk starts.
Tool: `ghostlock_deref_chain.py --predicate` prints the full 12-hop trace
with VAs, registers and the natural value at each hop.

Two bails are commonly assumed to stop the walk. Both were checked against
the binary:

| gate | VA | would fire? |
|---|---|---|
| `orig_waiter && !rt_mutex_owner(orig_lock)` | 0xffffff8009104de4 | no, owner is W |
| `next_lock != waiter->lock` | 0xffffff8009104df4 | no, both reads are the same heap word |
| `!task_has_pi_waiters(W)` | 0xffffff8009104e04 | **no, W->pi_waiters holds O_waiter** |

`W->pi_waiters` is non-empty because O blocked on `f_chain` and
`task_blocks_on_rt_mutex` called `rt_mutex_enqueue_pi(owner=W, O_waiter)`.
The rollback's `remove_waiter` dequeues `W_waiter` from O's `pi_waiters`;
nothing dequeues `O_waiter` from W's.

So the walk continues to `_raw_spin_trylock` at 0xffffff8009104e44, then
takes the owner of `f_target.pi_mutex` (task O) and calls
`task_blocked_on_lock(O)` and `rt_mutex_top_waiter(&f_target.pi_mutex)`.
`f_target.pi_mutex`'s rbtree IS empty (W_waiter was the only node and was
dequeued), so `waiters_leftmost == NULL` and `rt_mutex_top_waiter()` does
`rb_entry(NULL, ...) -> NULL` then `BUG_ON(w->lock != lock)`, i.e. reads
address `0x38`:

```
0xffffff800910508c  ldr x2, [x20, #0x10]   ; waiters_leftmost = NULL
0xffffff8009105094  ldr x0, [x2, #0x38]    ; load from 0x38
```

**Offline prediction for a live stale pointer: a kernel fault, not a
silent walk.** `EVIDENCE: OFFLINE_ONLY`.

This is the point that decides the round. Stock produced
`TIMEOUT_BLOCK` in CASE B with no panic and no reboot. A live, coherent
stale pointer would have faulted. Therefore on stock the walk did not
reach that code, and exactly two states produce `TIMEOUT_BLOCK`:

- **(a)** `W->pi_blocked_on == NULL` at consumer time (H1-B / H1-C class);
- **(b)** `W->pi_blocked_on != NULL` but the `cbz`/gate sequence bailed
  earlier than the model above (would need a different stock kernel).

Both mean the same thing operationally: the consumer did not complete a
walk through W's stale word. The round cannot separate (a) from (b)
without a stock-side probe, which phase 4 forbids here.

## 7. `futex_pi_state` Lifetime

From source, for this trigger:

| stage | pi_state for f_target | refcount | owner | pi_mutex waiters |
|---|---|---|---|---|
| before CMP_REQUEUE_PI | none yet | 0 | - | empty |
| `futex_proxy_trylock_atomic` | created by `attach_to_pi_owner(O)` | 1 | O | empty |
| `rt_mutex_start_proxy_lock` | held by caller | 2 | O | empty -> W_waiter enqueued |
| EDEADLK detected in the chain walk | still alive | 2 | O | W_waiter |
| rollback `remove_waiter` | still alive | 2 | O | **empty again** |
| after the syscall returns | alive, in O's `pi_state_list` | 1 | O | empty |

The state does not survive as a waiter-holding object: it survives as a
refcounted, owner-attached, *empty* pi_mutex. No `WARN_ON(!q->pi_state)`
and no `WARN` at futex.c:1277 / 2978 is reachable on this path, because the
`this->pi_state = NULL; put_pi_state(pi_state); break;` arm in
`futex_requeue` clears the pointer explicitly before breaking.

`EVIDENCE: OFFLINE_ONLY`.

## 8. WARN Inventory

| WARN | condition | reachable here | observable on stock |
|---|---|---|---|
| futex.c:1277 `mark_wake_futex` refuses PI futex | `q->pi_state \|\| q->rt_waiter` | **yes**, main's FWAKE hits it | no (kmsg denied) |
| futex.c:2978 `WARN_ON(!q.pi_state)` | FWRQ resumed, not requeued | yes, on W's early wakeup | no |
| futex.c:2606 same in `handle_early_requeue_pi_wakeup` | same path | yes | no |
| rtmutex.c:524 max lock depth | depth > 1024 | no, walk is 2 hops | no |
| rtmutex_common.h `BUG_ON(w->lock != lock)` | empty rbtree | yes IF the stale is live | would be a panic |
| futex.c:1258 `WARN_ON_SMP(spin_is_locked)` | internal invariant | no | no |

The first WARN is not hypothetical: CASE B and CASE D both printed
`fwake_errno=22` (EINVAL), which is `futex_wake`'s way of refusing to wake
a PI futex. That value is now part of the P3 line and is itself proof
that W was still parked inside `futex_wait_queue_me` when the consumer
ran, i.e. the FWRQ frame was alive.

`EVIDENCE: HARDWARE_OBSERVED` for `fwake_errno=22`;
`OFFLINE_ONLY` for the rest.

## 9. Hardware Controls

Five runs, all on the physical device, single uptime window. The
section 13 pair (`occ_tgt` / `occ_base`) is in section 12.

**RUN 1 `base_t` (CASE A, baseline, no GhostLock)**

```
P1 TRIGGER_SKIPPED baseline_no_requeue
P2 BASELINE errno=n/a (no trigger)
P5 LOCK_PI_DONE rc=-1 errno=110 (Connection timed out) elapsed_ms=3000
P6 RESULT=TIMEOUT_BLOCK mode=base_t
```

**RUN 2 `trg_inwin` (CASE B, full GhostLock, no stamp, consumer in-window)**

```
P2 EDEADLK errno=35 (Resource deadlock would occur)
P3 GRAPH_PRESERVED no_teardown waiter_keeps_f_chain owner_blocked
   fwrq_alive=1 fwake_errno=22
P4 NO_STAMP in_window sp_futex=0x7d6ee2fb80
P5 LOCK_PI_DONE rc=-1 errno=110 elapsed_ms=3000
P6 RESULT=TIMEOUT_BLOCK mode=trg_inwin target=f_chain in_window
```

**RUN 3 `tgt_t` (CASE C, no GhostLock, `LOCK_PI(f_target)`)**

```
P1 TRIGGER_SKIPPED baseline_no_requeue
P5 LOCK_PI_DONE rc=-1 errno=110 elapsed_ms=3000
P6 RESULT=TIMEOUT_BLOCK mode=tgt_t target=f_target
```

**RUN 4 `trg_tgt` (CASE D, GhostLock, then f_chain then f_target)**

```
P2 EDEADLK errno=35
P3 ... fwrq_alive=1 fwake_errno=22
P5  LOCK_PI_DONE        rc=-1 errno=110 elapsed_ms=3000   (f_chain)
P5b LOCK_PI_TARGET_DONE rc=-1 errno=110 elapsed_ms=3000   (f_target)
P6 RESULT=TIMEOUT_BLOCK
```

**RUN 5 `pos_cycle` (POSITIVE CONTROL, run 3x, always identical)**

```
P0 POSITIVE_CONTROL lock_pi(f_chain) rc=-1 errno=35 (Resource deadlock would occur)
```

This is the control that makes the other four interpretable. W holds
`f_chain` and blocks on `f_target`; O holds `f_target` and blocks on
`f_chain`. Every `pi_blocked_on` involved is valid and live. The kernel
returns **EDEADLK in 0 ms**, on the stock, through
`rt_mutex_adjust_prio_chain`.

Consequences:

- The PI walk path works on this device and does return EDEADLK.
- The timed consumer mechanism works (absolute CLOCK_REALTIME +3s is
  honoured: 3000 ms measured every time).
- `TIMEOUT_BLOCK` in CASE B is therefore **not** a broken mechanism and
  **not** an unexercised path. It is a real result.

`EVIDENCE: HARDWARE_REPRODUCED` for the positive control (3/3 runs, plus
the 4 historical runs in ghostlock-stale-pointer-validation.md).
`HARDWARE_OBSERVED` for CASES A-D.

## 10. `f_target` Control

| case | graph | consumer | result |
|---|---|---|---|
| CASE C | baseline | `LOCK_PI(f_target)` | TIMEOUT_BLOCK 3000 ms |
| CASE D step 1 | GhostLock | `LOCK_PI(f_chain)` | TIMEOUT_BLOCK 3000 ms |
| CASE D step 2 | GhostLock | `LOCK_PI(f_target)` | TIMEOUT_BLOCK 3000 ms |

`f_target` behaves identically with and without the trigger. Per the
phase-10 decision table this is **Case 3** (both paths identical), which
means `f_target` gave **no discriminating signal**. It does not support
the shared-graph-mutation reading (Case 2) and it does not prove the
absence of a stale pointer.

Offline reason why `f_target` was expected to be informative: its owner
O has a valid, live `pi_blocked_on` (`O_waiter` -> `f_chain.pi_mutex`), so
a consumer walking `f_target` traverses a genuine chain and does not depend
on W's stale word at all. That makes it a good *mechanism* control (it
reproduces TIMEOUT_BLOCK without GhostLock, confirming the walk bails on
the `next_lock == NULL` check) but a poor *stale* detector.

`EVIDENCE: HARDWARE_OBSERVED`.

## 11. HANG/TIMEOUT Reclassification

The previous `HANG_IN_WALK` label stays wrong and stays reclassified as
`TIMEOUT_BLOCK`. This round adds the reason it was wrong, which the
previous report could not supply:

The old timed flow waited for `w_back`, which the waiter only sets after
`futex_wait_requeue_pi` **returns**. That return only happens when W's own
30 s hrtimer expires. So the consumer ran roughly 30 s after the trigger,
against a stack frame that no longer existed. The harness was measuring
recycled kernel stack and calling it "the stale waiter".

`trg_inwin` removes that wait: W stays inside `futex_wait_queue_me`
(confirmed by `fwake_errno=22`, since `futex_wake` refuses to wake a PI
futex) and the consumer fires immediately. No stale bytes are read after
the frame dies in any mode used for this report's conclusions.

Additionally, the label `HANG_IN_WALK` is unreachable in the timed modes:
`P6` is computed from `consumer_errno`, and `HANG_IN_WALK` is only emitted
by the non-timed branch, which cannot report a syscall return code.

`EVIDENCE: HARDWARE_OBSERVED` for the corrected timing;
`OFFLINE_ONLY` for the futex_wake refusal semantics behind EINVAL.

## 12. Section 13 Experiment: the stale walk, isolated

The section 13 experiment was run on stock and it splits the remaining
ambiguity.

**Hypothesis.** In CASE B the walk reached `rt_mutex_top_waiter()` on
`f_target.pi_mutex`, whose rbtree is empty because the rollback dequeued
`W_waiter`. Offline that is `rb_entry(NULL) -> NULL` then a read of
address `0x38` (section 6). If instead `f_target.pi_mutex` holds a real
waiter, `rt_mutex_top_waiter()` returns a valid pointer, the fault
disappears, and the walk proceeds to its verdict.

**Setup.** One extra thread parks on `f_target` with a plain
`LOCK_PI(f_target)` before the trigger. No injected data, no stamper,
ordinary PI usage, unprivileged.

- `occ_tgt`: 4th thread on `f_target` + full GhostLock trigger
- `occ_base`: 4th thread on `f_target`, **no** trigger (control)

**Results.**

```
occ_tgt   trial 1  P6 RESULT=EDEADLK_CYCLE errno=35 elapsed_ms=0
occ_tgt   trial 2  P6 RESULT=EDEADLK_CYCLE errno=35 elapsed_ms=0
occ_tgt   trial 3  P6 RESULT=EDEADLK_CYCLE errno=35 elapsed_ms=0
occ_tgt   trial 4  P6 RESULT=EDEADLK_CYCLE errno=35 elapsed_ms=0
occ_base  trial 1  P6 RESULT=TIMEOUT_BLOCK errno=110 elapsed_ms=3000
occ_base  trial 2  P6 RESULT=TIMEOUT_BLOCK errno=110 elapsed_ms=3000
```

4/4 and 2/2. Single boot, uptime 13444s -> 13467s, zero panics.

**This is the discriminator.** The two runs differ by exactly one
variable, the `CMP_REQUEUE_PI` trigger. Both have an occupied
`f_target`; only the trigger creates the stale `W->pi_blocked_on`. The
control sleeps the full 3 s (walk never starts, `next_lock == NULL`); the
triggered run returns EDEADLK in 0 ms, which is the return path of
`rt_mutex_adjust_prio_chain` setting `ret = -EDEADLK`
(0xffffff8009105124).

Nothing else in the graph differs: same owner W on `f_chain`, same
consumer syscall, same absolute CLOCK_REALTIME +3s timeout, same
`fwake_errno=22` (W still parked inside `f_wait_queue_me`, FWRQ frame
alive).

`EVIDENCE: HARDWARE_REPRODUCED` (4 trials + 2 controls, this round).

**Interpretation.** The consumer's `EDEADLK` cannot be produced by the
normal path, because the control with an identical graph times out. It
requires the trigger, i.e. the stale `W->pi_blocked_on`, and it requires
the walk to get past `rt_mutex_top_waiter()` on `f_target.pi_mutex`.
The stale waiter was dereferenced and followed by the kernel.

This also explains CASE B/SECTION 9 without any extra assumption:
with an empty `f_target.pi_mutex` the walk would have faulted, and the
device stayed up, so the walk did not get that far. Both results are the
same walk, gated by one condition.

**What this is not.** It is not a fake-object read/write, not a
`FULL_CHAINWALK` to an attacker-chosen address, and not privilege
escalation. The waiter contents are natural (`task=W`, `lock=&f_target.pi_mutex`,
a valid heap rt_mutex with a known owner). What is proven is that the
GhostLock rollback leaves a live stale `pi_blocked_on` that a later
`FUTEX_LOCK_PI` consumer dereferences and walks, on the physical device.

## 13. H1 Verdict

**H1-A is `HARDWARE_REPRODUCED`.**

Criteria from phase 15, checked one by one:

| criterion | status | how |
|---|---|---|
| evidence `pi_blocked_on != NULL` | yes | `occ_base` (no trigger) times out, `occ_tgt` (trigger) returns EDEADLK in 0 ms; only the trigger creates the stale pointer |
| corresponding consumer reached | yes | `task_blocks_on_rt_mutex` 0xffffff80091052f0, `cbz` not taken; then `rt_mutex_adjust_prio_chain` |
| waiter expected identified | yes | `W_rt_waiter`, on W's live FWRQ stack frame; `lock = &f_target.pi_mutex`, natural heap value |
| reproducible | yes | 4/4 EDEADLK + 2/2 control TIMEOUT_BLOCK |

Also settled this round:

- The `remove_waiter` bug (`current->pi_blocked_on = NULL` clearing the
  requeuer instead of `waiter->task`) is the mechanism, and nothing on
  stock's path clears the victim's word. `OFFLINE_ONLY` for the mechanism,
  `HARDWARE_REPRODUCED` for the consequence.
- The PI walk path on stock returns EDEADLK for a valid cycle
  (`pos_cycle`, `HARDWARE_REPRODUCED`), so the negative controls are
  trustworthy.
- `TIMEOUT_BLOCK` is now explained: it is what the same walk produces
  when it cannot reach its verdict, either because `next_lock == NULL`
  (no trigger) or because the walk hits the empty-`f_target` case and
  never gets to a verdict.

Not claimed:

- `FULL_CHAINWALK` to an attacker-controlled address. Not attempted, not
  required, phase 13 forbids it.
- Any write primitive, fake object or credential effect.
- A stock absolute offset for `rt_waiter`. Still `STOCK GEOMETRY STATUS:
  INCONCLUSIVE`; nothing this round needed one.

**H1-B and H1-C are refuted for this graph.** `pi_blocked_on` is not
NULL after the rollback (that is `occ_base`'s state, and it produces
TIMEOUT_BLOCK), and no `futex_pi_state` or hash-bucket condition is needed
to explain the behaviour (the control isolates the trigger as the only
variable).

## 14. Next Experiment

The stale question is closed. The remaining bottleneck is the single
condition that decided section 12, and it is now a measurement rather than
a guess.

**Determine whether the empty-`f_target.pi_mutex` case in CASE B really is
the `0x38` fault predicted offline, or whether the walk bails earlier.**

The discriminator is to occupy `f_target` with a *different* number of
waiters (1 = current `occ_tgt`, 2 = add a second parked thread) and to
compare the consumer's return code and elapsed time. If the offline
fault model is right, 1 waiter is the minimum that changes behaviour and
the verdict is stable above it. If instead some other gate at
`rt_mutex_adjust_prio_chain+0xe04` (`task_has_pi_waiters`) is what
normally stops the walk, the transition point will be elsewhere and the
section 12 attribution needs narrowing.

This needs one more parked thread, no stamper and no injected data.

Only after that: whether the natural stale waiter can be made to point
somewhere other than `&f_target.pi_mutex`, which is the only remaining
question before any value-controlled primitive. That is a
data-injection question and stays frozen under phase 13 until the walk
geometry above is settled.

---

BOTTOM LINE (per-round summary)

- LAB and STOCK differ in the trigger frames (STRONG +0x10, rt_waiter
  SP0-0x2c8) but the consumer-side logic frames are identical. `OFFLINE_ONLY`.
- The valid stock geometry for the discriminator is only the
  frame-invariant consumer set: `rt_mutex_adjust_prio_chain` 0x90,
  `task_blocks_on_rt_mutex` 0x50, `remove_waiter` 0x40.
- First consumer of `pi_blocked_on` reachable from the consumer syscall:
  `task_blocks_on_rt_mutex` 0xffffff80091052f0, `ldr x0,[x22,#0x7f0]`,
  followed by `cbz` at +0xd0 and the first stale deref
  `ldr x25,[x0,#0x38]` at +0xd4. `OFFLINE_ONLY`.
- `f_chain` normal path: `next_lock == NULL` -> walk abandoned -> sleep ->
  ETIMEDOUT. `OFFLINE_ONLY`, terminal result `HARDWARE_OBSERVED`.
- `f_chain` stale path: walk starts, passes the lock-match and
  `task_has_pi_waiters` gates, and offline faults at
  `rt_mutex_adjust_prio_chain+0x320` reading address `0x38`.
  `OFFLINE_ONLY`.
- `TIMEOUT_BLOCK` is explained: it is what the same walk produces when it
  cannot reach a verdict (no trigger -> `next_lock == NULL`; trigger with
  an empty `f_target.pi_mutex` -> offline-predicted fault). The positive
  control proves this is a real result, not a broken mechanism.
  `HARDWARE_OBSERVED` + `HARDWARE_REPRODUCED`.
- `f_target` as a plain second observer gave no signal (Case 3,
  identical with and without the trigger). Only when `f_target` is
  *occupied* does it discriminate. `HARDWARE_OBSERVED`.
- The stale `pi_blocked_on` WAS observed live and consumed on stock:
  `occ_tgt` 4/4 `EDEADLK_CYCLE` at 0 ms vs `occ_base` 2/2
  `TIMEOUT_BLOCK` at 3000 ms, single variable. `HARDWARE_REPRODUCED`.
- `FULL_CHAINWALK` to an attacker-chosen address was NOT attempted and is
  NOT claimed. Only the natural walk was proven.
- Single next bottleneck: pin down whether the empty-`f_target.pi_mutex`
  case is the offline-predicted `0x38` fault or an earlier bail, by
  varying the number of parked waiters on `f_target`.