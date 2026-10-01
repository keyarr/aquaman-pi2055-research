# ghostlock consumer FUTEX_LOCK_PI(f_chain) — stale pi_blocked_on differential

Date: 2026-10-01. Device: Xiaomi Mi TV Stick 1080p (aquaman, S805Y/GXL,
Android 9, PI.2055, 4.9.113 arm64, PREEMPT=y, shell uid=2000, Enforcing).
Lab authority: build-aq/vmlinux + .src/linux-amlogic
(kernel/locking/rtmutex.c, kernel/futex.c, kernel/sched/core.c) +
tools/ghostlock_deref_chain.py (--verify 30/30, --predicate, --heap-chain,
--h16). Harness: tools/ghostlock_chain.c reused as-is (no new tool, rebuild
only for stale binary). Raw log:
out/logs/ghostlock_consumer_boot3ec336a5.log (single boot, zero reboot).

## 1. Hypothesis

After the GhostLock trigger (FWRQ + FCRQ -> EDEADLK, remove_waiter clears
current->pi_blocked_on instead of the waiter task), task W keeps
task->pi_blocked_on dangling into its own live FWRQ frame
(W_waiter, waiter->lock == &f_target.pi_mutex). A later
FUTEX_LOCK_PI(f_chain) from a 4th thread C reaches that stale word via
task_blocks_on_rt_mutex -> rt_mutex_adjust_prio_chain and consumes the
pointed rt_mutex (trylock at lock+0x00, leftmost at lock+0x10,
owner at lock+0x18, close at lock==orig -> EDEADLK). The claim is ONLY
the consumer walk, not R/W, not cred, not root.

## 2. Static chain

Classification: STATIC_CONFIRMED (verify 30/30, 0 mismatches, lab VAs
OFFLINE_ONLY, offsets build-invariant).

FUTEX_LOCK_PI path (source + binary):

- futex.c:3249/3273 FUTEX_LOCK_PI -> futex_lock_pi 0xffffff800913b030
  (ENTRY, only unpriv 1-syscall path to FULL walk).
- futex.c:2572 futex_lock_pi_atomic 0x913b154 (attach_to_pi_owner(W) ok,
  pi_state owner=W) -> futex.c:2611 rt_mutex_timed_futex_lock
  0x913b1bc (bl 0x91057d8).
- rtmutex.c:1523 rt_mutex_timed_futex_lock 0x91057d8 ->
  rt_mutex_timed_fastlock(FULL) -> rtmutex.c:1255 rt_mutex_slowlock
  0x9df97e0 -> rtmutex.c:1289 task_blocks_on_rt_mutex.
- rtmutex.c:1007 task_blocks_on_rt_mutex 0x91052b8
  str x21,[x20,#0x7f0]: C->pi_blocked_on=C_waiter (only victim site,
  valid, C stack). Field: task_struct.pi_blocked_on +0x7f0.
- rtmutex.c:548 task->pi_blocked_on read, binary 0x91052f0
  ldr x0,[x22,#0x7f0] (x22=W): stale ROOT. Branch 0x91052f8 cbz:
  NULL -> return 0 (TIMEOUT path), non-NULL -> continue.
- rtmutex.c:548-620 first deref 0x91052fc ldr x25,[x0,#0x38]:
  waiter->lock +0x38 -> next_lock. Branch 0x910530c cmp + 0x9105318
  cbz: NULL -> return 0, non-NULL -> chain. Natural: &f_target.pi_mutex.
- rtmutex.c:1047 bl adjust 0x9105378 with w1=1 FULL (x0=W, x2=f_chain,
  x3=next_lock, x4=C_waiter, x5=C). FULL is the only deterministic path:
  FUTEX_TRYLOCK_PI goes to slowtrylock (never task_blocks),
  MIN bails at 0x4e1c/0x4e38 on prio match.
- rtmutex.c:548 re-read 0x9104e60 ldr x28,[x19,#0x7f0] (x19=W, same
  stale word). Stability requirement: H16.4 == H16.7.
- rtmutex.c:578 gate 0x9104df0 ldr x0,[x28,#0x38] + 0x9104df4
  cmp x20,x0 + 0x9104df8 b.ne out: next_lock must equal waiter->lock
  or bail ret 0. First branch on waiter->lock VALUE.
- rtmutex.c:587 has_waiters(W) 0x9104e00 ldr + 0x9104e04 cbz -> out.
  W holds O_waiter (O blocked on f_chain) so non-empty, passes.
- rtmutex.c:595-599 top check 0x9104e08/0x4e1c: FULL -> w24=requeue=0,
  continue in DEADLOCK-DETECT-ONLY (!requeue). Prio gate 0x9104e28
  ldr w1,[x28,#0x40] (waiter->prio +0x40) + 0x9104e30 b.ne: FULL
  continues whatever prio.
- rtmutex.c:620 lock=waiter->lock; 0x9104e44 bl _raw_spin_trylock
  [lock+0x00]: FIRST heap touch (RMW wait_lock). Free -> continue,
  locked -> spin at 0x4e48/0x4e4c.
- rtmutex.c:641 cycle checks 0x9104f10 cmp x20,x26 (lock==orig f_chain)
  / 0x9104f24 owner==top_task: either -> 0x9105124 mov w22,#-0x23
  ret -EDEADLK. Natural iter1 f_target!=f_chain, O!=C -> pass.
- !requeue tail (w24=0): 0x9105024 -> 0x910504c ldr owner [lock+0x18],
  0x9105068 ldxr/add/stxr [owner+0x28] get_task_struct(O) INC,
  0x9105080 bl spin_lock [owner+0x7d4] pi_lock, 0x9105084 ldr
  owner->pi_blocked_on [+0x7f0], 0x910508c ldr x2,[x20,#0x10]
  leftmost, 0x9105090 ldr next_lock, 0x9105094 ldr top->lock
  [x2,#0x38], 0x9105098 cmp x20,x0 / b.ne brk #0x800 (BUG_ON),
  0x9104ff0/0x9104ff8 recursion read. Iter2 task=O closes at
  lock==orig -> EDEADLK 0ms.

Trigger (dangling creation, DERIVED STATICALLY, not re-observed here):

- futex_wait_requeue_pi.constprop.8 0x913b398 stp [sp,#-0x1a0],
  waiter at x29+0x80 (0x913b454): W FWRQ frame, rt_waiter at SP0-0x2b0
  lab-relative, waiter->lock=&f_target.pi_mutex at birth (rtmutex.c:998).
- FCRQ dispatch -> EDEADLK path -> remove_waiter 0x9105454
  str xzr,[x24,#0x7f0] with x24=current (not waiter->task):
  clears the wrong pi_blocked_on, victim W slot dangles.
  rtmutex.c:1099-1111.

Discarded consumer:

- core.c:4295 policy==p->policy early return (schedA rc=0 HANG was
  predicted); rtmutex.c:349-356 get_effective_prio reads only
  pi_waiters/prio, never pi_blocked_on; rtmutex.c:1157-1178
  rt_mutex_adjust_pi reads waiter->lock but with MIN_CHAINWALK and
  prio-equal bail at 1166. Not reopened, no new binary evidence.

Who reads task->pi_blocked_on on the consumer: 0x52f0 (task_blocks,
x22=W), 0x53e8 (2nd encoding), 0x4e60 (adjust head, x19=W).
Which field: rt_mutex_waiter.lock +0x38 (0x52fc -> x25, 0x4df0 gate),
prio +0x40 (0x4e28). Where f_target alters behavior: lock+0x00
trylock outcome, lock+0x10 leftmost NULL vs occ (hop A), lock+0x18
owner NULL bail (hop B, H11 0x5050). Normal termination: any bail
above -> return 0 (TIMEOUT 3000ms sleep). EDEADLK conditions:
lock==orig or owner==top_task at 0x4f10/0x4f24 -> 0x5124.

## 3. Live consumer control

pos_cycle: valid PI cycle, no requeue, no stale. W holds f_chain blocks
f_target; O holds f_target blocks f_chain; O LOCK_PI(f_chain) during
arming. Every pi_blocked_on live. Same function, same verdict site
0x5124, same code 35, same immediacy.

Hardware this boot (3ec336a5): 4x EDEADLK errno=35
(main_pid 15625 old-binary run + 15818/15823/15828, P0 POSITIVE_CONTROL
rc=-1 errno=35) + 1x flake rc=0 (15749, W_DID_NOT_BLOCK arming race:
W acquired f_target instead of blocking, so O found f_chain free;
walk never ran, not a walk failure). 4/5 EDEADLK proves the device
executes the FULL chainwalk and the EDEADLK mechanism is healthy.
LEVEL_1 met. Flake retained in log, not hidden.

Path health: ctrl_t (trigger, consumer f_ctrl uncontended, fwrq 4s):
ACQUIRED rc=0 errno=0 0ms. Timed-syscall mechanism healthy.
alt_base (no trigger, consumer f_alt held+occupied): TIMEOUT 3000ms.
f_alt is a valid contended rt_mutex.

## 4. GhostLock trigger

Same trio/graph/consumer/timeout, no stamper/fake/spill, in-window
(W stays in FWRQ, fwake_errno=22 EINVAL every run proves frame alive).

- trg_inwin: P1 TRIGGER_ENTER, P2 EDEADLK 35, P3 GRAPH_PRESERVED
  fwrq_alive=1 fwake_errno=22.
- occ_tgt / alt_tgt: same with (f_target occupied), P2 EDEADLK 35.
- occ_base / alt_base: P1 TRIGGER_SKIPPED, P2 BASELINE (control).
GHOSTLOCK_TRIGGER: PASS (EDEADLK 5/5 where attempted: trg_inwin,
occ_tgt, alt_only, alt_tgt, ctrl_t arming).

## 5. Differential matrix

Expectation derived offline BEFORE run (predicate hops A/B):
L0 TIMEOUT (no stale, cbz 0x52f8 bails), L1 TIMEOUT (occupancy alone
insufficient, same bail), U0 TIMEOUT (stale + empty gate bails at
0x508c/0x4e00), U1 EDEADLK 0ms (stale + occupied closes at 0x4f10).
Consumer always timed FUTEX_LOCK_PI(f_chain) ABS +3s. Same boot
3ec336a5, up 6:50, zero panic/reboot.

| cell | trigger | f_target | consumer | result (this boot) |
|------|---------|----------|----------|--------------------|
| L0 base_t | none | empty occ_n=0 | f_chain | TIMEOUT_BLOCK 110 3000ms |
| L1 occ_base | none | occupied occ_n=1 | f_chain | TIMEOUT_BLOCK 110 3000ms |
| U0 trg_inwin | EDEADLK | empty occ_n=0 | f_chain | TIMEOUT_BLOCK 110 3000ms |
| U1 occ_tgt | EDEADLK | occupied occ_n=1 | f_chain | EDEADLK_CYCLE 35 0ms |
| NEG alt_only | EDEADLK | empty + f_alt held+occ | f_chain | TIMEOUT_BLOCK 110 3000ms |
| NEG alt_tgt | EDEADLK | occupied + f_alt held+occ | f_chain | EDEADLK_CYCLE 35 0ms |

L1==TIMEOUT proves occupied f_target alone does not create EDEADLK.
U0==TIMEOUT proves stale alone does not create EDEADLK. Only the AND
(U1) gives EDEADLK 0ms. alt_only vs alt_tgt with f_alt held constant:
result follows f_target, f_alt ignored — walk consumes the birth value
&f_target.pi_mutex (H16 fidelity), not any occupied mutex. No cell
assumed; direction matched the offline predicate.

## 6. Hardware evidence

BOOT_ID 3ec336a5-439f-497f-b9f7-08fd7441b174 (same boot all runs).
KERNEL Linux localhost 4.9.113 #1 SMP PREEMPT 2022-09-06 armv8l.
Binary out/ghostlock_chain rebuilt 16:32 (source 15:48, prior device
binary stale lacked alt_* strings), pushed to /data/local/tmp/.
base_t/ctrl_t run with fwrq 4s (argv6) else they wait 30s for W return;
inwin modes need no wait (consumer fires while W in FWRQ).

Raw (out/logs/ghostlock_consumer_boot3ec336a5.log):

- pos_cycle x4: P0 POSITIVE_CONTROL rc=-1 errno=35; 1x flake rc=0.
- base_t: P5 DONE rc=-1 errno=110 elapsed 3000ms, P6 TIMEOUT_BLOCK.
- occ_base: P5 DONE errno=110 3000ms, P6 TIMEOUT_BLOCK, P7 occ_n=1.
- trg_inwin: P2 EDEADLK 35, P5 DONE errno=110 3000ms, P6 TIMEOUT_BLOCK.
- occ_tgt: P2 EDEADLK 35, P5 DONE errno=35 0ms, P6 EDEADLK_CYCLE.
- alt_only: P4 ALT_ARMED alt_parked=1, P5 DONE errno=110 3000ms,
  P6 TIMEOUT_BLOCK (f_alt ignored).
- alt_tgt: ALT_ARMED alt_parked=1, P5 DONE errno=35 0ms,
  P6 EDEADLK_CYCLE (follows f_target).
- alt_base: consumer f_alt, P5 DONE errno=110 3000ms, TIMEOUT_BLOCK.
- ctrl_t: consumer f_ctrl, P5 DONE rc=0 errno=0 0ms, ACQUIRED.
- Boot check after: same BOOT_ID, up 6:50, load ~2. No residual
  processes (one-shot per exec, no persist, no flash writes).

Futex addresses (P0 win/fake per run, uaddrs private per process):
win=0x2780c0 all rebuilt runs, fake per-mmap (e.g. occ_tgt
0x7f7b494000, alt_only 0x7f8d443000). f_alt u32 values logged
(alt_only 2147499426, alt_tgt 2147499433, alt_base 2147499441).
sp_futex + waiter_est_lab printed per run (lab-relative only, NOT
stock offsets). Elapsed: EDEADLK 0ms vs TIMEOUT 3000ms; code is the
proof, timing only fast-vs-sleep.

## 7. Signal classification

| signal | class | reason |
|---|---|---|
| EDEADLK 35 0ms in U1/alt_tgt only (vs TIMEOUT in L0/L1/U0/alt_only) | PROOF (as differential, never alone) | predicted offline (lock==orig 0x4f10->0x5124), only AND cell fires, negatives hold topology constant |
| TIMEOUT 110 3000ms in L0/L1/U0/alt_only/alt_base | PROOF (as differential member) | bail/sleep result with bounded walk (hops 0-7 pass, hop A/B gate decides); occupied-alone TIMEOUT excludes occupancy confound |
| pos_cycle EDEADLK 35 | PROOF (LIVE_CONTROL) | valid cycle through same function/site, mechanism healthy |
| ctrl_t ACQUIRED 0 / alt_base TIMEOUT | AUXILIARY | path/syscall health, not chain evidence |
| single EDEADLK or TIMEOUT or HANG alone | FALSE_POSITIVE | explicitly excluded per spec; only negative-vs-stale delta counts |
| reboot/crash | FAIL (never success) | zero this boot; any would be FAIL |
| MSG_PEEK / buddyinfo / slabinfo / sysfs / isolated timing / small timeout delta / "device estranho" | BLOCKED or FALSE_POSITIVE | unused here; timing only fast-vs-sleep, code decides |
| owner+0x28 INC / owner+0x7d4 lock / lock+0x00 RMW | AUXILIARY | necessary path consequence of EDEADLK (dominate H16), no userspace counter |
| absolute SP0-0x2b0 geometry / DWARF offsets on stock / vendor hunk | OFFLINE_ONLY, not PROOF | lab-relative, unused for verdict |

## 8. Verdict

LEVEL_2

LEVEL_1 met (live FULL walk via pos_cycle 4x). LEVEL_2 met (trigger +
stale consumer differential U1 vs L0/L1/U0 + alt_only negative, all
predicted offline, reproduced single-boot). LEVEL_3 not attempted
(no slot write, no fake consumed, no pointer controlled).

## 9. Next bottleneck

Exactly one: a durable 8-byte write primitive to the live W FWRQ slot
[W_waiter+0x38] that keeps H16.4 (0x52fc) == H16.7 (0x4df0/cmp 0x4df4)
== &f_alt.pi_mutex while the frame is alive (W in FWRQ,
fwake_errno=22), with f_alt held+occupied so H16.8 trylock succeeds
and H16.12 BUG_ON passes; then rerun alt_tgt-vs-alt_only as the
LEVEL_3 discriminator. No fake objects, no R/W, no cred before that
slot write exists.
