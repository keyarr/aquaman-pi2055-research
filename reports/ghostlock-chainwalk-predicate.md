# ghostlock chainwalk predicate — occupancy gates EDEADLK

Date: 2026-10-01. Device: Xiaomi Mi TV Stick 1080p (aquaman, S805Y/GXL,
Android 9, PI.2055, 4.9.113 arm64, PREEMPT=y, shell uid=2000, no root,
no dmesg). Lab authority: build-aq/vmlinux + .src/MiTV_OpenSource
(rtmutex.c / rtmutex_common.h / futex.c, textually upstream for the PI
path). Hardware runs this round: 12 (trg_inwin, occ_tgt x3, occ_base x2,
occ2_tgt x3, occ2_base x2, pos_cycle), one uptime window, zero panics,
zero reboots, adb never dropped. Prior history (17 runs, GhostLock
EDEADLK, stale walk H1-A) is preserved, not rewritten.

Stage 3 (fake rt_mutex, stamper, R/W, cred, root) stayed frozen. No
injected data, no stack corruption, no new stamper. Only natural
occupancy of f_target was varied.

## 1. Objective

Prove exactly which predicate inside the chainwalk decides the
consumer result, by varying only f_target occupancy:

same GhostLock + different f_target occupancy -> different predicate.

Consumer is always FUTEX_LOCK_PI(f_chain) (natural, timed +3s ABS).
No pthread scheduler, no pselect/poll/spill consumer. `HARDWARE_OBSERVED`
for the method; per-conclusion labels below.

## 2. Binary Predicate

Tool: `tools/ghostlock_deref_chain.py --predicate` (fixed this round:
FULL entry VA typo corrected, occupancy hops A/B/C added).
`--verify` = 30 entries, 0 mismatches. `OFFLINE_ONLY` for all VAs;
offsets build-invariant (rtmutex frames 0x90/0x50/0x40, no canary).

Original hypothesis: `rt_mutex_top_waiter(f_target)` BUG_ON fault.
Actual predicate: f_target non-empty (hop A) AND O has waiters (hop B).
Existence gate, minimum 1 waiter. See hops C/prio for why count and
prio do not matter.

Dataflow f_target -> register -> compare -> branch -> consequence:

hop 0 task_blocks stale root `OFFLINE_ONLY`
- VA 0xffffff80091052f0 `ldr x0, [x22, #0x7f0]`
- reg x22=W task -> x0=pi_blocked_on, off +0x7f0
- origem W task_struct, destino x0, cond sempre (sob pi_lock)
- branch 0xffffff80091052f8 `cbz x0, +0x188`: NULL -> return 0
  (TIMEOUT path), non-NULL -> continue. Efeito: walk starts only if
  stale != NULL. `HARDWARE_REPRODUCED` (occ_base NULL->TIMEOUT vs
  occ_tgt non-NULL->EDEADLK, sec. 6).

hop 1 first stale deref `OFFLINE_ONLY`
- VA 0xffffff80091052fc `ldr x25, [x0, #0x38]`
- reg x0=stale waiter -> x25=next_lock, off +0x38
- origem waiter->lock, destino x25, cond stale != NULL
- branch 0xffffff800910530c `cmp x25,#0` + 0x5318 `cbz w23`:
  NULL -> return 0, non-NULL -> chain. Efeito: next_lock=&f_target
  heap (owner O), walk not abandoned. Natural, valid, no fault.

hop 2 FULL entry `OFFLINE_ONLY`
- VA 0xffffff8009105378 `bl rt_mutex_adjust_prio_chain`
- reg x0=W x1=1 FULL x2=f_chain x3=next_lock x4=C_waiter x5=C
- cond chain_walk && next_lock (both true when stale). Efeito:
  FULL removes MIN prio early-return; walk proceeds whatever prio.

hop 3 walk root `OFFLINE_ONLY`
- VA 0xffffff8009104e60 `ldr x28, [x19, #0x7f0]`
- reg x19=W -> x28=stale waiter, off +0x7f0, cond cbnz passes.
- Efeito: same stale word re-read.

hop 4 lock-match gate `OFFLINE_ONLY`
- VA 0xffffff8009104df0 `ldr x0, [x28, #0x38]`
- VA 0xffffff8009104df4 `cmp x20, x0`
- VA 0xffffff8009104df8 `b.ne out`
- reg x20=next_lock vs x0=waiter->lock, off +0x38
- origem stale waiter, destino x0, cond != -> bail, == -> continue.
- Efeito: passes on natural bytes (same heap word twice, stable).

hop 5 has_waiters(W) `OFFLINE_ONLY`
- VA 0xffffff8009104e00 `ldr x0, [x19, #0x7e0]`
- VA 0xffffff8009104e04 `cbz x0, out`
- reg x19=W, off +0x7e0 (pi_waiters root), cond EMPTY->ret 0.
- Efeito: W holds O_waiter (O blocked on f_chain, enqueue_pi), so
  non-empty, no bail. Same for O0/O1/O2.

hop 6 task_top(W) + FULL `OFFLINE_ONLY`
- VA 0xffffff8009104e08 `ldr x0, [x19, #0x7e8]`, 0x4e0c `sub #0x18`,
  0x4e10 `cmp x22, x0`, 0x4e14 `b.eq`, 0x4e18 `cmp w23,#1`,
  0x4e1c `b.ne out`, 0x4e20 `mov w24,#0`
- reg x22=C_waiter vs x0=task_top(W)=O_waiter, off +0x7e8-0x18
- cond != + FULL -> requeue=false, continue (DEADLOCK-DETECT-ONLY).
- Efeito: first iteration takes !requeue path in all configs.

hop 7 prio gate `OFFLINE_ONLY`
- VA 0xffffff8009104e28 `ldr w1, [x28, #0x40]`, 0x4e2c `cmp w1,w0`,
  0x4e30 `b.ne`, 0x4e34 `cmp w23,#1`, 0x4e38 `b.ne out`
- reg x28 prio vs task prio ~120, off +0x40
- cond FULL -> requeue=false + CONTINUE whatever prio.
- Efeito: prio never decides on FULL. FASE 4 closed without prio var.

hop A occupancy top(f_target), first !requeue tail `OFFLINE_ONLY` VAs,
`HARDWARE_REPRODUCED` divergence
- VA 0xffffff800910508c `ldr x2, [x20, #0x10]`
- reg x20=f_target lock -> x2=waiters_leftmost, off +0x10
- origem f_target.pi_mutex, destino x2=top_waiter
- O0: x2=NULL. O1/O2: x2=occ_waiter (first parked, prio 120).
- VA 0xffffff8009105094 `ldr x0, [x2, #0x38]` (BUG_ON w->lock!=lock)
- reg x2 -> x0=top->lock, off +0x38, cond cmp x20,x0 else brk 0x5114
- O1/O2: x0=&f_target, cmp passes, goto again.
- O0 offline predicted read at 0x38 (fault). Stock gives TIMEOUT_BLOCK
  3000ms, zero panics: fault prediction `HARDWARE_REFUTED`, existence
  gate `HARDWARE_REPRODUCED`. The branch is real; the panic is not.

hop B has_waiters(O), second-iteration head `OFFLINE_ONLY` VAs,
`HARDWARE_REPRODUCED` effect
- VA 0xffffff8009104e00 `ldr x0, [x19, #0x7e0]` (x19=O now)
- VA 0xffffff8009104e04 `cbz -> out (ret 0, TIMEOUT)`
- O0: O empty (sole W dequeued via is_top path) -> would bail.
- O1/O2: O non-empty (occ; plus stale W retained when W not top,
  remove_waiter early-return) -> passes to lock==orig EDEADLK.
- Efeito: O0 TIMEOUT vs O1/O2 EDEADLK. Minimum 1, O2 stable.

hop C top compare(O) `OFFLINE_ONLY`
- VA 0xffffff8009104e08/0x4e0c/0x4e10/0x4e14 (x22=top(f_target) vs
  task_top(O)=occ)
- O1: occ==occ equal. O2: occ1==occ1 equal (2nd right, top still 1st).
- Efeito: O1 vs O2 identical EDEADLK. Count does not matter.

EDEADLK site `OFFLINE_ONLY` VA, `HARDWARE_REPRODUCED` result
- VA 0xffffff8009105124 `mov w22,#-0x23` (ret -35) via 0x4f10
  `cmp x20,x26` (lock==orig f_chain) or owner==top_task.
- Second iteration lock=f_chain==orig -> EDEADLK 0ms. Only path that
  returns 35 fast; TIMEOUT is 3000ms sleep. Timing only distinguishes
  fast vs sleep, code is the proof.

## 3. Natural f_target State

Source-derived, no stamp, preserved graph (W keeps f_chain, O holds
f_target blocked on f_chain). `OFFLINE_ONLY` for values;
`HARDWARE_OBSERVED` for terminal codes (sec. 5).

O0 = no additional waiter (trg_inwin)
- owner: O (pi_state alive, refcount held, empty mutex after rollback).
- waiters: EMPTY (sole W_waiter dequeued by remove_waiter is_top path).
- top waiter: NULL (leftmost NULL).
- PI mutex: heap valid, wait_lock free, owner O|HAS_WAITERS? bit cleared
  via fixup (empty). `OFFLINE_ONLY`.
- O->pi_waiters: EMPTY (W removed, no occ). `OFFLINE_ONLY`.

O1 = exactly 1 additional waiter (occ_tgt)
- owner: O (same).
- waiters: 1 (occ_waiter, enqueued before trigger, leftmost).
- top waiter: occ_waiter (prio 120, lock=&f_target, valid).
- PI mutex: non-empty rbtree, leftmost=occ. `OFFLINE_ONLY`.
- O->pi_waiters: NON-EMPTY (occ; W stale retained because W != top,
  remove_waiter early-return when occ is top). `OFFLINE_ONLY`.
- Minimum to change top NULL->non-NULL: 1. Determined offline first,
  confirmed on hardware (sec. 6). `HARDWARE_REPRODUCED`.

O2 = 2 waiters (occ2_tgt)
- owner: O. waiters: 2 (occ1 leftmost prio 120, occ2 right prio 120,
  ordered by enqueue; W dequeued, was rightmost).
- top waiter: occ1 (same as O1 top identity class, still non-NULL).
- O->pi_waiters: NON-EMPTY (occ1+occ2+retained W). `OFFLINE_ONLY`.
- Effect identical to O1 (sec. 6). Proves existence, not count/prio.

No five threads, no prio games. One variable: occupancy of f_target.
Trigger, f_chain, owner, consumer, timeout, affinity, no stamper, no
fake identical. `HARDWARE_OBSERVED` for the harness discipline
(fwake_errno=22 every run proves FWRQ frame alive).

## 4. Occupancy Model

O0: occ_n=0, trigger, consumer LOCK_PI(f_chain). Expect TIMEOUT
(empty gate bails, no verdict). `HARDWARE_REPRODUCED`.

O1: occ_n=1, trigger, same consumer. Expect EDEADLK 0ms (gate passes,
cycle W->O->W closes at lock==orig). `HARDWARE_REPRODUCED`.

O2: occ_n=2, trigger, same consumer. Expect EDEADLK 0ms stable (top
still 1st, existence unchanged). `HARDWARE_REPRODUCED`.

Controls O1-base/O2-base: same occupancy, NO trigger (W pi NULL),
same consumer. Expect TIMEOUT (next_lock NULL, walk never starts).
Proves occupied f_target alone does not create EDEADLK.
`HARDWARE_REPRODUCED`.

Priority: all threads SCHED_OTHER default (prio ~120). Hop 7 shows
FULL ignores prio match. No prio change was needed; existence alone
decides. FASE 4 closed with zero prio variable. `OFFLINE_ONLY` for
the gate, `HARDWARE_REPRODUCED` for stability O1==O2.

## 5. Hardware Matrix

One variable per run, P0-P8, minimal logging in critical path (main
only, no waiter/owner/consumer syscalls after trigger except the one
consumer svc; no sleeps for timing). Absolute CLOCK_REALTIME +3s.

O0 trg_inwin `HARDWARE_OBSERVED`
- P1 TRIGGER_ENTER, P2 EDEADLK 35, P3 GRAPH_PRESERVED fwrq_alive=1
  fwake_errno=22, P4 OCCUPANCY_ARMED occ_n=0,
  P5 LOCK_PI_DONE rc=-1 errno=110 elapsed 3000ms,
  P6 RESULT=TIMEOUT_BLOCK, P7 occ_n=0 errno=110, P8 END.

O1 occ_tgt `HARDWARE_REPRODUCED` (3x this round + 4x prior = 7x)
- P1 TRIGGER_ENTER (occupied), P2 EDEADLK 35,
  P3 GRAPH_PRESERVED occ_n=1 fwake_errno=22,
  P4 OCCUPANCY_ARMED occ_n=1, P5 DONE rc=-1 errno=35 elapsed 0ms,
  P6 RESULT=EDEADLK_CYCLE, P7 occ_n=1 errno=35, P8 END.

O1 occ_base control `HARDWARE_REPRODUCED` (2x)
- P1 TRIGGER_SKIPPED, P2 BASELINE, P3 BASELINE occ_n=1,
  P5 DONE errno=110 3000ms, P6 TIMEOUT_BLOCK.

O2 occ2_tgt `HARDWARE_REPRODUCED` (3x)
- P1 TRIGGER_ENTER (occupied), P2 EDEADLK 35,
  P3 occ_n=2 occ2_parked=1 fwake_errno=22, P4 occ_n=2,
  P5 DONE errno=35 0ms, P6 EDEADLK_CYCLE, P7 occ_n=2 errno=35.

O2 occ2_base control `HARDWARE_REPRODUCED` (2x)
- P1 SKIPPED occ_n=2, P5 DONE errno=110 3000ms, P6 TIMEOUT_BLOCK.

pos_cycle `HARDWARE_REPRODUCED` (valid PI cycle, no requeue/stale)
- O holds f_target blocks f_chain, W holds f_chain blocks f_target,
  O LOCK_PI(f_chain) rc=-1 errno=35 0ms. Proves walk path + EDEADLK
  mechanism healthy; TIMEOUTs are real, not broken syscalls.

Uptime monotonic across the 12 runs, zero panic, zero reboot, adb
attached. dmesg denied (klogctl EPERM), so no WARN claim. Timing only
distinguishes immediate (0ms) vs sleep (3000ms); code is the proof.

## 6. Predicate Divergence

CONFIG A (O0): top=NULL (hop A) + O empty (hop B) -> TIMEOUT_BLOCK.
CONFIG B (O1/O2): top=occ (hop A) + O non-empty (hop B) -> EDEADLK 0ms.
Single variable (occupancy), reproducible, direction predicted offline.

Branch same? Hops 0-7 identical across O0/O1/O2 (stale, W gates,
FULL, prio). Diverging branch is hop A/B existence gate. If branch
were same and result varied, sec. 2 hop-by-hop shows it is not same:
x2 NULL vs occ, O root EMPTY vs NON-EMPTY. `HARDWARE_REPRODUCED`.

Original hypothesis (top BUG_ON fault -> panic) `HARDWARE_REFUTED` as
a panic prediction (O0 TIMEOUT, not fault). Narrowed actual predicate
(existence gate -> EDEADLK vs TIMEOUT) `HARDWARE_REPRODUCED`. Report
states both so the hypothesis is replaced, not forced (FASE 12).

## 7. pos_cycle Control

Preserved, unmodified graph main GhostLock intact. `HARDWARE_REPRODUCED`.
Proves EDEADLK is not any-occupied-lock: occ_base/occ2_base occupied
but TIMEOUT; pos_cycle valid cycle EDEADLK. EDEADLK requires the stale
+ occupied AND gate, not occupancy alone.

## 8. FULL_CHAINWALK Path

Exact sequence proven executed when EDEADLK 0ms returns
(`HARDWARE_REPRODUCED` for natural walk; fake address NOT claimed):

FUTEX_LOCK_PI(f_chain) [0xffffff800913b030 `OFFLINE_ONLY`]
-> attach_to_pi_owner(W) ok [0x913b154]
-> rt_mutex_timed_futex_lock FULL [0x913b1bc, chwalk=1]
-> rt_mutex_slowlock -> task_blocks_on_rt_mutex [0x9105228]
-> C->pi_blocked_on=C_waiter [0x52b8 store]
-> stale load W [0x52f0] cbz not taken + deref [0x52fc] next=f_target
-> adjust_prio_chain(W,FULL,f_chain,next,C_waiter,C) [0x5378]
-> re-read stale [0x4e60] + match [0x4df0/0x4df4] + has_waiters(W)
  [0x4e00/0x4e04 pass] + top!=task_top FULL [0x4e08-0x4e1c requeue=false]
  + prio FULL-continue [0x4e28-0x4e3c] + trylock f_target [0x4e44]
  + deadlock check not-yet [0x4f10/0x4f28] + !requeue tail [0x5024]
  top(f_target)=occ [0x508c/0x5094 pass] + O grab + next=f_chain
  + again task=O
-> iteration 2 has_waiters(O) pass [0x4e00] + top==task_top(O)=occ
  [0x4e08] + trylock f_chain + lock==orig f_chain [0x4f10 b.eq]
-> ret -EDEADLK [0x5124 mov w22,#-0x23] -> consumer errno=35 0ms.

EDEADLK is not accepted as FULL synonym alone; pos_cycle + occ_base
pair proves the code path (mechanism healthy, occupied-alone TIMEOUT,
stale+occupied EDEADLK). TIMEOUT not accepted as walk synonym; it is
the bail/sleep result with unlocated-but-bounded walk (hops 0-7 pass,
hop A/B gate decides). `HARDWARE_REPRODUCED` for natural FULL;
attacker-address FULL `INCONCLUSIVE` (not attempted, phase 13).

## 9. Stock Evidence

Per-conclusion labels:

- Binary VAs/insns/offsets/regs: `OFFLINE_ONLY` (lab image; rtmutex
  frames invariant, trigger frames proxy only).
- Trigger EDEADLK + graph preserved + fwake EINVAL(22) + in-window:
  `HARDWARE_OBSERVED` (every run P2/P3).
- O0 TIMEOUT, O1 EDEADLK, O2 EDEADLK, bases TIMEOUT, pos_cycle EDEADLK:
  `HARDWARE_REPRODUCED` (counts sec. 5/10).
- Empty-fault panic prediction: `HARDWARE_REFUTED` (O0 TIMEOUT, no panic).
- Absolute trigger geometry (SP0-0x2b0/0x2c8, waiter slots):
  `INCONCLUSIVE` (not needed, not used; consumer frames only).
- Struct offsets (+0x7f0/+0x38/+0x40/+0x18/+0x28/+0x7d4/+0x7e0/+0x7e8):
  `OFFLINE_ONLY` (DWARF; no config effect, vendor hunk unclosed).

No lab analysis called stock proof. No absolute offset reused.

## 10. Reproducibility

This round 12 runs, prior 4 occ_tgt + 2 occ_base + pos_cycle history
preserved. Totals: occ_tgt 7x EDEADLK 0ms, occ2_tgt 3x EDEADLK 0ms,
occ_base 4x TIMEOUT 3000ms (2 prior + 2 now), occ2_base 2x TIMEOUT,
trg_inwin TIMEOUT (1x now + prior), pos_cycle EDEADLK (3x prior + 1x
now). Single boot window for this round (uptime 4:31 monotonic),
zero panic/reboot. Commands:
`adb push out/ghostlock_chain /data/local/tmp/`
`adb shell /data/local/tmp/ghostlock_chain 0x0 B [trg_inwin|occ_tgt|occ_base|occ2_tgt|occ2_base|pos_cycle]`.
Exit 1 = EDEADLK/TIMEOUT verdict (timed modes); exit 0 only for fake
HIT (not used here). P0-P8 one line each, flushed.

## 11. What Is Proven

- Real predicate is f_target occupancy existence (hop A 0x508c/0x5094
  + hop B 0x4e00/0x4e04), minimum 1 waiter, O2 stable.
  `HARDWARE_REPRODUCED`.
- occ_base/occ2_base differ from occ_tgt/occ2_tgt by exactly the
  trigger (stale); trg_inwin differs from occ_tgt by exactly occupancy.
  AND gate. `HARDWARE_REPRODUCED`.
- pos_cycle valid as control (EDEADLK via same function).
  `HARDWARE_REPRODUCED`.
- Natural FULL_CHAINWALK (stale waiter -> natural heap rt_mutex ->
  verdict) executed on stock. `HARDWARE_REPRODUCED`.
- Prio does not decide on FULL; no prio variable needed. `OFFLINE_ONLY`
  gate + `HARDWARE_REPRODUCED` stability.
- No fake, no stamper, no R/W, no geometry needed. `HARDWARE_OBSERVED`
  discipline.

## 12. What Is Not Proven

- Attacker-chosen address FULL walk. Not attempted. `INCONCLUSIVE`.
- First controlled read/write (fake page). Zero fake writes by design
  (no stamper). `INCONCLUSIVE`.
- Whether O0 empty case avoids the 0x38 read via graceful bail vs
  mapped-zero vs vendor patch. Offline predicts fault, stock gives
  TIMEOUT with no panic. Fault part `HARDWARE_REFUTED`; exact
  micro-branch before/at hop A when empty `INCONCLUSIVE` (does not
  affect existence conclusion; needs no new stamper to close, only
  the O0/O1/O2 verdict already has).
- Absolute stock trigger geometry (SP0-0x2b0 vs 0x2c8). `INCONCLUSIVE`,
  unused.
- Any cred/root/stack effect. Explicitly not attempted.

## 13. Next Bottleneck

Single next bottleneck: first field of natural rt_mutex that could become
controllable AFTER the branch, i.e. f_target+0x00 wait_lock RMW at
0x4e44 (first off-stack op, heap, valid) and then lock+0x08/+0x10
enqueue writes + owner+0x28 refcount + owner+0x7d4 lock. All
`OFFLINE_ONLY` today. Do NOT build fake yet. First close which heap
word after hop A/B is the cheapest to observe without injection
(refcount at owner+0x28 is candidate, still natural O task). That is
the only next step; exploitation stays frozen until that word is
named with a hardware discriminator like this round.

---
BOTTOM LINE
- real predicate is waiter existence in f_target (0x508c/0x5094 + 0x4e00).
- in lab binary at adjust_prio_chain !requeue tail + second-iteration head.
- natural condition is f_target having >=1 waiter (occ parked, same prio 120).
- occ_base/occ2_base TIMEOUT vs occ_tgt/occ2_tgt EDEADLK, one variable.
- divergence reproduced 7x/3x vs TIMEOUTs, zero panic.
- pos_cycle valid EDEADLK, useful control.
- natural FULL reproduced (stale->heap->EDEADLK 0ms), fake not attempted.
- first field after branch is lock+0x00 trylock, then +0x08/+0x10 and owner+0x28.
- only next bottleneck is which post-branch heap word to observe without injection.
