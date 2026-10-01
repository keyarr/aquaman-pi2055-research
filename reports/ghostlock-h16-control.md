# ghostlock h16 control — waiter->lock address selection

Date: 2026-10-01. Stock: Xiaomi Mi TV Stick 1080p (aquaman, S805Y/GXL,
Android 9, PI.2055, 4.9.113 arm64). Lab: build-aq/vmlinux +
.src/linux-amlogic (rtmutex.c, rtmutex_common.h, futex.c, sched.h).
No fake, no stamper, no spill, no stack spray, no poll/pselect stamp in
this phase. Second legitimate rt_mutex only.

Tool: `tools/ghostlock_deref_chain.py --h16` (new: H16.0-H16.12, every
waiter->lock load/store on the PI path). `tools/ghostlock_chain.c`
extended minimally: f_alt + holder + 1 parked waiter, modes alt_tgt /
alt_only / alt_base, P4 ALT_ARMED + P7 alt_parked. Trigger, f_chain,
stale waiter, consumer, occupancy discipline, prio, affinity, timeout,
P0-P8 unchanged.

## 1. Objective

Close one question: can the stale `waiter->lock` (H16) be steered to a
second legitimate rt_mutex without a fake object and without stack
corruption, such that the chainwalk consumes f_alt instead of f_target
with a distinguishable result.

## 2. H16 Binary Dataflow

`--h16` output, FULL consumer, natural stale. VAs lab-absolute
(OFFLINE_ONLY); offsets build-invariant.

```
H16.0  STORE  0x527c (+0x54)  stp x20,x19,[x21,#0x30]  BIRTH, only store
H16.1  LOAD   0x52a0 (+0x78)  ldr x0,[x0,#0x38]        top->lock, NOT stale
H16.2  LOAD   0x52d8 (+0xb0)  ldr x1,[x0,#0x38]        top->lock, NOT stale
H16.3  LOAD   0x52f0 (+0xc8)  ldr x0,[x22,#0x7f0]      stale ROOT (+0x53e8 2nd)
H16.4  LOAD   0x52fc (+0xd4)  ldr x25,[x0,#0x38]       FIRST STALE DEREF
H16.5  CALL   0x5378 (+0x150) bl adjust_prio_chain     x3=x25 carried
H16.6  LOAD   0x4e60 (+0xf8)  ldr x28,[x19,#0x7f0]     same word re-read
H16.7  LOAD   0x4df0 (+0x88)  ldr x0,[x28,#0x38]       re-read + gate
H16.8  RMW    0x4e44 (+0xdc)  bl _raw_spin_trylock     [Xn,#0x00] first heap
H16.9  LOAD   0x508c (+0x324) ldr x2,[x20,#0x10]       leftmost
H16.10 LOAD   0x4ff8 (+0x190) ldr x20,[x0,#0x38]       iter2 next (also 0x5090)
H16.11 LOAD   0x54d0 (rmw+0xd0) ldr x21,[x0,#0x38]     MIN-tail reader
H16.12 LOAD   0x5784 (adj+0x64) ldr x21,[x2,#0x38]     sched reader
```

Full chain: rt_waiter (W FWRQ stack) -> [slot+0x38] -> H16.4 x25 ->
H16.5 x3 -> H16.7 cmp x20,x0 at 0x4df4 / b.ne out (FIRST branch on the
value) -> H16.8 [Xn,#0x00] trylock -> [Xn,#0x18] owner -> H16.9
[Xn,#0x10] leftmost -> top->lock at 0x5094 -> cmp x20,x0 / b.ne brk at
0x5098 -> iter2 task=O via H16.10 -> lock==orig EDEADLK at 0x4f10/0x5124.
EVIDENCE: OFFLINE_ONLY.

remove_waiter entry check (0x5424/0x5428, 0x54a8/0x54ac: top->lock +
brk) reads the lock's CURRENT top, never the stale pointer. Not a
control surface. EVIDENCE: OFFLINE_ONLY.

## 3. Natural rt_mutex Inventory

Every PI futex with an owner/waiter owns a heap `futex_pi_state ->
pi_mutex` (valid, kernel heap, created by lookup_pi_state / proxy
trylock on demand). The harness reaches all of them indirectly:

1. f_chain.pi_mutex (owner W, consumer entry lock). EVIDENCE:
   HARDWARE_REPRODUCED (every consumer attaches to it).
2. f_target.pi_mutex (owner O, stale lock value). EVIDENCE:
   HARDWARE_REPRODUCED (N1/N2 EDEADLK path consumes it).
3. f_alt.pi_mutex (owner A, new this round, holder + 1 waiter).
   EVIDENCE: HARDWARE_REPRODUCED (alt_base TIMEOUT + ALT_ARMED lines).
4. f_ctrl.pi_mutex (uncontended control). EVIDENCE: HARDWARE_REPRODUCED
   (prior ctrl_t ACQUIRED history, unchanged).
5. Transient waiter stacks (W/O/C/occ/altocc rt_waiter, each with
   waiter->lock = the futex they block on). EVIDENCE: OFFLINE_ONLY
   layout, HARDWARE_OBSERVED effect (arming + parked flags).

Geometry controllable per object via ordinary syscalls: owner (whoever
LOCK_PI first), waiters (parked LOCK_PI threads), leftmost (first
parked, prio equal so FIFO). No memory write needed. EVIDENCE:
HARDWARE_REPRODUCED (occ_n=1/2 + alt_parked=1 lines).

## 4. f_target State

Unchanged from prior reports. GhostLock W stale waiter->lock =
&f_target.pi_mutex (heap, owner O blocked on f_chain, wait_lock free).
Occupancy variable: occ_n=0 (empty, leftmost NULL) vs occ_n>=1 (occ
waiter, prio 120, lock=&f_target). Consumer verdict follows exactly:
empty -> TIMEOUT_BLOCK 3000ms, occupied -> EDEADLK_CYCLE 0ms.
EVIDENCE: HARDWARE_REPRODUCED.

## 5. f_alt State

f_alt is a second private futex, same process, same creation path as
f_target (plain u32, no flags beyond PRIVATE). Owner A acquires once
and holds by spinning (never blocks, never releases, no chain edge).
One altocc thread parks LOCK_PI(f_alt): f_alt.pi_mutex has exactly 1
live waiter (prio 120, waiter->lock=&f_alt.pi_mutex, valid O-stack
object). Distinguishing fields vs f_target: owner task ptr (A != O),
waiters_leftmost (altocc waiter != occ waiter), uaddr. wait_lock free
in both, size/class identical (same allocator path). EVIDENCE:
HARDWARE_OBSERVED (a_armed=1 alt_parked=1 every alt run); structural
offsets OFFLINE_ONLY.

Direct probe alt_base (no trigger, consumer timed LOCK_PI(f_alt)):
TIMEOUT_BLOCK 3000ms. f_alt is a real contended mutex, consumer path
healthy, no cycle (nothing links A into W->O->W). EVIDENCE:
HARDWARE_REPRODUCED (1x; direction predicted offline).

## 6. H16 Mutation Analysis

Source grep over kernel/locking + futex.c for `waiter->lock =`: exactly
1 hit, rtmutex.c:998 inside task_blocks_on_rt_mutex (`waiter->lock =
lock`, binary stp at 0x527c, H16.0). Callers bind the value at waiter
birth: requeue path lock = pi_state->pi_mutex of the TARGET futex,
slowlock path lock = the futex being taken. After that:

* requeue/dequeue/enqueue (both trees) never store waiter->lock.
* remove_waiter stores current->pi_blocked_on only, never waiter->lock.
* adjust_prio_chain requeue path re-enqueues the SAME waiter on the
  SAME lock (no lock field update exists on that path).
* adjust_pi / deboost / fixup / try_to_take never store waiter->lock.
* Stack frame death recycles bytes, but that is not a store to the
  field and the harness keeps the FWRQ frame alive (fwake_errno=22).

So `waiter->lock` is: E. sobrescrito somente por corrupcao externa
(and A. immutable after creation by any legitimate syscall — both
hold; E is the operative one). No B/C/D path exists in 4.9.113:
not alterable by syscall, not derived from another mutable field,
not copied from a second kernel object after birth. EVIDENCE:
OFFLINE_ONLY (source + binary); no contrary store found.

## 7. Natural Control Possibilities

Exhausted before any corruption attempt:

* Requeue to f_alt? Requeue targets the futex named in the CMP_REQUEUE
  syscall (f_target here); pointing it at f_alt would move the whole
  GhostLock graph, not H16 alone, and the stale slot would still be
  born f_target. Rejected: changes the experiment, not the pointer.
* Rollback updating waiter->lock? remove_waiter never touches it
  (binary 0x5400-0x554c has no str to +0x38). Rejected offline.
* Lifetime reuse / alias? The stale slot is W's own FWRQ frame, alive
  (W never returns, hrtimer is the only exit). No second writer maps
  that stack. Rejected offline.
* Sched/deboost rewriting it? adjust_pi only READS (H16.12), deboost
  only touches prio/deadline (+0x40/+0x48). Rejected offline.
* Second waiter substituting the reference? pi_blocked_on still points
  at W_waiter (the bug preserves exactly that slot); occ/altocc
  waiters live on other stacks and are never referenced by W.
  Rejected by alt_only hardware result below.

EVIDENCE: OFFLINE_ONLY for code paths; HARDWARE_REPRODUCED for the
last item (sec. 8).

## 8. Hardware Matrix

One boot window, uptime 4:49 monotonic at last check, zero panic,
zero reboot, adb stable. `ghostlock_chain 0x0 B <mode>`:

* CASE0 occ_tgt HARDWARE_REPRODUCED (1x this round + 7x history):
  EDEADLK_CYCLE errno=35 0ms. H16=f_target, 1 waiter.
* alt_tgt HARDWARE_REPRODUCED (1x): occ_n=1 + ALT_ARMED a_armed=1
  alt_parked=1, EDEADLK_CYCLE errno=35 0ms. f_target occupied decides;
  f_alt occupied does not disturb.
* alt_only HARDWARE_REPRODUCED (2x): occ_n=0 + ALT_ARMED a_armed=1
  alt_parked=1, TIMEOUT_BLOCK errno=110 3000ms. f_alt occupied is
  IGNORED by the walk; f_target empty decides. This is the FASE 8
  negative control: two legit mutexes in deliberately different states
  (f_target empty, f_alt occupied), H16 still f_target, result follows
  f_target.
* alt_base HARDWARE_REPRODUCED (1x): no trigger, consumer f_alt timed,
  TIMEOUT_BLOCK errno=110 3000ms. f_alt valid + contended; CASE3
  control.

CASE1 (H16=f_alt walk) NOT executed: no natural mechanism exists
(sec. 6), and fabricating it would be a fake-address experiment,
explicitly out of scope. Documented as impossible, not skipped.

## 9. H16 Result

SUCESSO B. NATURAL H16 CONTROL = HARDWARE_REFUTED (no legitimate
syscall sequence retargets the stale waiter->lock; single birth store
H16.0, zero post-creation writers). ADDRESS SELECTION stays
INCONCLUSIVE as a hardware claim (never demonstrated, by design).
What IS hardware-proven instead: address FIDELITY — with two live
legitimate rt_mutexes in opposite states, the walk deterministically
consumes f_target (the birth value) and ignores f_alt (alt_tgt
EDEADLK vs alt_only TIMEOUT, 1x/2x, zero panic). EVIDENCE:
HARDWARE_REPRODUCED for fidelity; HARDWARE_REFUTED for natural
retarget.

## 10. Downstream Heap Consumption

Unchanged from heap-consumption report, confirmed as the path the
faithful H16 value drives: first heap word lock+0x00 RMW trylock
(H16.8/0x4e44), first alterable predicate lock+0x10 leftmost
(H16.9/0x508c + 0x5094/0x5098 cmp/b.ne), owner+0x28 refcount INC +
owner+0x7d4 pi_lock as necessary path consequence. lock+0x08 untouched
in !requeue; +0x20.. OOB (object size 0x20). A future H16=f_alt would
replay exactly these offsets on f_alt's heap object (same struct, same
function, same VAs) — but the pointer switch itself is the unsolved
step, so no claim is made about f_alt downstream behavior. EVIDENCE:
HARDWARE_REPRODUCED for f_target path; INCONCLUSIVE for f_alt path.

## 11. What Is Proven

* H16.0-H16.12 exact loads/stores/branches with VA+reg+origin.
  EVIDENCE: OFFLINE_ONLY (verify 30/30 covers the chain entries; H16.1/
  H16.2/H16.11/H16.12 VAs read straight from objdump above).
* Exactly one legitimate store to waiter->lock (rtmutex.c:998).
  EVIDENCE: OFFLINE_ONLY.
* Second legitimate rt_mutex (f_alt, owner A + 1 waiter) built via
  syscalls only, with state opposite to f_target on demand. EVIDENCE:
  HARDWARE_REPRODUCED.
* Walk consumes f_target and ignores f_alt (alt_tgt EDEADLK vs alt_only
  TIMEOUT). EVIDENCE: HARDWARE_REPRODUCED.
* f_alt is a valid contended mutex (alt_base TIMEOUT). EVIDENCE:
  HARDWARE_REPRODUCED.
* Prior proofs untouched (stale gate, FULL natural, leftmost
  predicate, pos_cycle). Not reopened.

## 12. What Is Not Proven

* H16 pointing at f_alt (or anything else) on stock. INCONCLUSIVE by
  design (requires the corruption in sec. 13, not attempted).
* f_target vs f_alt downstream signature difference under the walk
  (both direct probes TIMEOUT identically; structural fields differ
  but no walk has consumed f_alt). INCONCLUSIVE.
* Absolute stock VAs/KASLR slide, vendor hunk status for these
  structs. OFFLINE_ONLY / INCONCLUSIVE as before.
* Any fake object, stamper, spill, R/W, cred, root. Not attempted.

## 13. Minimum Artificial Control

First corruption point: the 8-byte slot [W_waiter,#0x38] (W FWRQ frame,
SP0-0x2b0+0x38 lab-relative; stock offset STOCK UNKNOWN, frame alive
while W sleeps). Minimum: one stable 8-byte write of
&f_alt.pi_mutex (heap address, must be learned, not guessed) landing
between trigger return and consumer walk, stable across BOTH H16.4
(x25) and H16.7 (cmp at 0x4df4). Constraints the write must also
satisfy (all OFFLINE_ONLY): H16.12 BUG_ON (top->lock of f_alt must
equal f_alt, true iff f_alt occupied by a consistent waiter);
H16.8 trylock on f_alt+0x00 must succeed or the walk spins; owner A
must stay blocked-or-held consistently or H11 bails. No stack
overwrite beyond those 8 bytes is needed for ADDRESS selection; value
control of anything else (prio, tree) is a separate later step.

## 14. Next Bottleneck

Exactly one: a durable 8-byte write primitive to the live W FWRQ slot
[waiter,#0x38] that keeps H16.4 == H16.7 == &f_alt.pi_mutex while the
frame is alive. Everything downstream (H16.8-H16.12, heap offsets,
owner handling, EDEADLK verdict) is already mapped and needs no new
research. Do not build fake objects, do not chase R/W, do not touch
cred: solve only the 8-byte slot write with a legitimate-looking
stomper, then rerun alt_tgt-vs-alt_only as L0-vs-L1.
