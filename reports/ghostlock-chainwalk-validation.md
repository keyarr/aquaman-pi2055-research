# GhostLock chainwalk validation (hardware phase)

Date: 2026-10-01. Device: Xiaomi Mi TV Stick 1080p (aquaman, S805Y/GXL,
Android 9, PI.2055, 4.9.113, arm64, PREEMPT=y). Lab authority:
build-aq/vmlinux + DWARF. Six hardware trials today, zero panics.

Status: success criteria 1-4 NOT met on hardware. Chain breaks at the
stamp. Everything below says exactly where, with binary proof.

## 1. Executive Summary

Preserved graph is safe: waiter keeps f_chain (no FUPI), owner stays
blocked, pi_state2 stays allocated. EDEADLK reproduces 6/6, consumer
FUTEX_LOCK_PI(f_chain) enters 6/6, device survives 6/6. No writes to the
fake page in any VAR (A/B/C) or mode (immediate/busy/nostamp). Owner
page +0x28 stays 0, proving the refcount inc never ran.

Root cause (binary, not timing): pselect stamper cannot reach the waiter
slot. Fixed kernel frames put stack_fds at top-0x190 and the waiter at
top-0x2b0. No user PAD moves kernel frames, so the PAD sweep is a fixed
miss, not a clobber. Stamp and nostamp modes are identical from the
kernel's view, which is why all 6 runs HANG the same way.

## 2. Exact Binary Chain

Verified 2026-10-01: `python3 tools/ghostlock_deref_chain.py
build-aq/vmlinux --verify` = 30 entries, 0 mismatches. Graph:
`--graph` emits CALLER -> FUNCTION -> LOAD/STORE -> REGISTER DATAFLOW ->
MEMORY TARGET with addr2line + symbol offset + DWARF field per hop.

Trigger: futex_wait_requeue_pi.constprop.8 0xffffff800913b398
stp [sp,#-0x1a0]!, waiter at x29+0x80 (0xffffff800913b454 add x21,x29,#0x80).
Rollback bug: remove_waiter 0xffffff8009105454 str xzr,[x24,#0x7f0]
(x24=SP_EL0=current, not waiter->task). Victim pi_blocked_on dangles.

Consumer entry: futex_lock_pi 0xffffff800913b030 ->
0xffffff800913b1bc bl rt_mutex_timed_futex_lock ->
rt_mutex_timed_futex_lock 0xffffff80091057d8 (chwalk=1 FULL) ->
rt_mutex_slowlock 0xffffff8009df97e0 -> task_blocks_on_rt_mutex
0xffffff8009105228.

task_blocks: STORE at 0xffffff80091052b8 (only victim site); stale LOADs
at 0xffffff80091052f0 and 0xffffff80091053e8 (both converge on 0x52f8);
cbz NULL at 0x52f8; FIRST DEREF ldr x25,[x0,#0x38] at 0x52fc;
bl adjust_prio_chain at 0x5378 with w1=1 FULL.

adjust_prio_chain 0xffffff8009104d68: ldr x28,[x19,#0x7f0] at 0x4e60;
ldr x0,[x28,#0x38] at 0x4df0; cmp x20,x0 at 0x4df4 (bail on mismatch);
ldr w1,[x28,#0x40] at 0x4e28; MIN/FULL split at 0x4e30 (FULL continues
whatever prio); trylock RMW at 0x4e44 (lock+0x00); dequeue call at 0x4f48
(RB_CLEAR_NODE self-ptr bails); FIRST STORE str w0,[x28,#0x40] at 0x4f54;
2nd STORE str x3,[x28,#0x48] at 0x4f60; enqueue call at 0x4f64 (writes
waiter ptr to lock+0x08/+0x10); ldr x19,[x20,#0x18] at 0x4f9c (0 stops);
ldxr/add/stxr at 0x4fac (owner+0x28 refcount inc); bl spin_lock at 0x4fc8
(owner+0x7d4); recursion ldr at 0x4ff0 + ldr x20,[x0,#0x38] at 0x4ff8.

FUTEX_TRYLOCK_PI excluded: goes to rt_mutex_trylock->slowtrylock, never
calls task_blocks. MIN excluded as consumer: b.ne at 0x4e1c/0x4e38
returns early on prio match; FULL (w1=1) is the only deterministic path.

## 3. Stack Geometry on Device

Same-boot SP probes (user SP at svc, same inline-asm probe both calls):

- A nostamp: sp_futex=0x7d879b9b80 waiter_est=0x7d879b98d0 page_off=0x18d0
- A immediate: sp_futex=0x7d8b6e6b80 sp_psel=0x7d8b6e6a60 dist=0x120
  implied_pad=0x120 waiter_est=0x7d8b6e68d0 page_off=0x28d0
- B immediate: dist=0x120 implied=0x120 page_off=0x38d0
- B busy: dist=0x120 implied=0x120 page_off=0x08d0
- B nostamp: waiter_est page_off=0x18d0
- C immediate: dist=0x120 implied=0x120 page_off=0x18d0

Task/lock/prio in window: task +0x30, lock +0x38, prio +0x40 (all inside
win[0x00..0xf0], window bytes 0x38/0x40 in stack_fds[0] readfds slot,
copy_from_user verbatim; memset(0) slots at +0x78 untouched by single
stamp, deep/shallow pair not needed).

Calibration converges attempt 0 every time, but it is tautological:
raw_psel does sub sp,pad so user dist==pad by construction. It proves
the probe moves user SP, not that kernel frames match. Kernel frames are
fixed (SyS_futex 0x70 + do_futex 0x120 + FWRQ 0x1a0 = 0x330; SyS_pselect6
0x90 + core_sys_select 0x190 = 0x220). stack_fds[0]=top-0x190,
waiter=top-0x2b0. Window [top-0x190,top-0xa0] vs waiter
[top-0x2b0,top-0x260]: no overlap, any PAD. That is why stamp==nostamp.

## 4. Trigger Preservation

Redesigned trigger kept in tools/ghostlock_chain.c: waiter FLPI(f_chain)
then FWRQ(f_wait->f_target, 30s); owner FLPI(f_target) then FLPI(f_chain)
(blocks, 2-deep); main FCRQ(f_wait,1,f_target) -> EDEADLK 6/6; FWAKE lets
waiter return to stamp; NO FUPI(f_chain), no unlock, no join, waiter parks
in yield loop, owner stays blocked. pi_state2 stays allocated (owner never
unlocks f_target), waiter stays out of hb1 trouble (q intact, no pi_state).

Proof: 6/6 survival with preservation vs 6 prior panics with FUPI + joins
+ setschedparam + /proc reads. Preservation removes the crash actor.

## 5. FUTEX_LOCK_PI Consumer

Fourth thread, prepared before trigger, spins on consumer_in (atomic, no
syscall), sets consumer_entered BEFORE svc so P5 prints even if walk
panics, then exactly one `xfutex(&f_chain, FLPI,0,0,0,0)`. No pthread
abstractions in critical, no printf/malloc/aux-futex/join/sleep/pselect
on waiter/owner/consumer after trigger. Main may usleep (own stack not
under test). Optional pin (argv pin) default off per breakthrough hard
constraint. Entered 6/6 (P5), never returned 6/6 (P5 PENDING).

## 6. FULL_CHAINWALK Proof

Not achieved on hardware. Offline binary proof is complete: FULL=1 comes
only from rt_mutex_timed_futex_lock (futex.c:2610) and proxy lock; MIN=0
from timed_lock/fastlock; split at adjust+0xc8 (0x4e30) verified in
disassembly. On device, VAR A (lock=NULL) was meant to stop at
next_lock==NULL (task_blocks returns 0) vs VAR B (lock=fake) to continue
to enqueue. Both HANG with zero writes, so the distinguisher never fired:
kernel never read our bytes. prio=1 (!=120) correctly removes the MIN
early-return variable, but the walk stops earlier (wrong slot).

Minimal FULL proof experiment (next boot): deep stamper that actually
covers top-0x2b0 (candidate do_sys_poll, frame 0x410 + copy_from_user to
stack, see section 13), then VAR A vs VAR B must diverge (A blocks
silent, B writes leftmost). Until then FULL-on-device is INFERRED from
binary, not OBSERVED.

## 7. Minimal Fake Object

VAR A: lock=0. VAR B: lock=fake zero page (wait_lock=0, waiters=0,
leftmost=0, owner=0) + waiter tree_entry=self (RB_CLEAR_NODE) + prio=1.
VAR C: B + owner=fake_owner page (observe +0x28). VAR D: C + owner+0x7f0
-> fake_waiter2 (tests recursion at 0x4ff0/0x4ff8). All mlock'd.

Result: first access outside original never observed. Fake +0x08/+0x10
stay 0 in all runs. Owner +0x28 stays 0 in VAR C. Two words (+0x38/+0x40)
are necessary but not sufficient until stamp is fixed; sufficiency
unproven.

## 8. First Controlled Read

Not demonstrated. Binary-identified first reads: task_blocks 0x52fc
(waiter->lock into x25) and adjust 0x4df0/0x4e28 (lock/prio). Device
shows no fake-page effect, so kernel read natural bytes (real mutex),
not our page. No page-observed read yet.

## 9. First Controlled Write

Not demonstrated. Binary-identified first writes: trylock RMW at 0x4e44
(lock+0x00), str prio at 0x4f54 (waiter+0x40, kernel stack, not directly
visible), str deadline at 0x4f60, enqueue stores at lock+0x08/+0x10
(user-visible HIT signal), refcount inc at owner+0x28 (0x4fac). Device:
all zero across 6 runs. Write-what-where still INFERRED.

## 10. Panic Discrimination

CASE A (pi_state survives) vs CASE B (waiter in bucket, pi_state NULL):
with preservation (owner never unlocks, waiter never FUPI), pi_state2
stays alive by design and q stays intact. 6/6 survival proves neither
case panics in this geometry. Prior 6 panics required teardown (FUPI +
zombie join + setschedparam + /proc + heartbeat). Last-event logs in
all runs: P5 LOCK_PI_ENTER then P6 HANG, consumer entered=1 done=0,
variant/mode logged in P5. No reboot, adb stayed attached, uptime
monotonic (6min->13min across runs).

## 11. PREEMPT / Stamp Analysis

Three modes, same result: immediate HANG, busy (200k iters) HANG,
nostamp HANG. No run shows partial writes, no run shows wrong-PAD-always
vs clobber-sometimes split because stamp never reaches. Distinguishers
for future deep stamper: wrong pad = miss every time; clobbered = same
PAD sometimes HIT sometimes MISS; never reached = all modes identical
(current state); reached but fake invalid = HANG with trylock spin
(cpu_relax loop at 0x4e4c) vs panic in enqueue/dequeue.

## 12. Reproducibility

6/6 EDEADLK, 6/6 P5 entered, 6/6 HANG, 0/6 HIT, 0/6 panic, single boot
(up 6min->13min, no reboot). Commands:
`adb push ghostlock_chain /data/local/tmp/`
`adb shell /data/local/tmp/ghostlock_chain 0x120 [A|B|C] [immediate|busy|nostamp]`.
Exit 1 = MISS/HANG (expected until stamp fixed), exit 0 = HIT_ENQUEUE
(leftmost==&win). Phases P0-P6 one line each, flushed, enough to
reconstruct after crash (last line before disconnect = death site).

## 13. Remaining Primitive

Binary chain to first RMW is fully mapped (section 2). Missing link is
solely the stamper depth. Candidate: do_sys_poll (frame 0x410, controlled
copy_from_user at 0x...b60 to stack buffer x28). Needs offline computation
of x28 offset vs top-0x2b0, then one hardware trial with VAR A vs VAR B
divergence as criterion. Fallback candidates: recvfrom (0x140+helpers),
sendto (0x130+helpers), setsockopt path (0x50+0x40+0x1e0=0x270, write at
+0xd8 => top-0x198, still shallow). pselect/select/poll/ppoll are
structurally too shallow, closed.

## 14. Next Exploit Step

1. Offline: compute do_sys_poll x28 stack offset (x29+? in 0x410 frame)
   and total depth from syscall entry; confirm window covers top-0x2b0
   with controlled pollfd bytes at +0x38/+0x40 positions.
2. One boot: replace raw_psel with raw_poll stamper, rerun VAR A (must
   block silent) vs VAR B (must HIT_ENQUEUE). If diverge, FULL proven,
   first write proven, proceed to VAR C refcount observation.
3. Only then: owner->task pivots toward cred/fops per binary chain
   (0x4ff0 recursion), never before.

BOTTOM LINE
- Proved: preserved graph (no FUPI) is safe 6/6; EDEADLK reproduces;
  consumer enters; pselect stamp never reaches waiter (fixed frames).
- Not proved: FULL walk on device, fake consumed, any controlled read/write.
- Real bottleneck: stamper depth, not PAD, not prio, not PREEMPT.
- Most informative next experiment: deep poll stamper VAR A vs VAR B
  divergence in one boot.
