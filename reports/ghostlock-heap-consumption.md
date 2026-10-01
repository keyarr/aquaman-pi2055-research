# ghostlock heap consumption — first heap word past waiter->lock

Date: 2026-10-01. Stock: Xiaomi Mi TV Stick 1080p (aquaman, S805Y/GXL,
Android 9, PI.2055, 4.9.113 arm64). Lab: build-aq/vmlinux + .src/linux-amlogic
(rtmutex.c, rtmutex_common.h, sched.h). No fake, no stamper, no spill, no
stack geometry in this phase. Natural f_target.pi_mutex only.

Tool: `tools/ghostlock_deref_chain.py --heap-chain` (new this round, H0-H20,
one line per access). `tools/ghostlock_chain.c` unchanged in logic; header
comment only (N0-N2 matrix + H4/H16/owner+0x28 map).

## 1. Objective

Close one question: starting at natural `waiter->lock` (= `&f_target.pi_mutex`,
heap, owner O), which is the first heap word consumed, which is the first
heap-dependent predicate that can be flipped by a legitimate state change,
and which side effect proves it on stock without corrupting anything.

## 2. Natural rt_mutex Layout

DWARF `rt_mutex` (die 0x0076ce98), size 0x20, from lab image (OFFLINE_ONLY;
offsets build-invariant, no DEBUG_RT_MUTEXES on stock path):

```
+0x00 wait_lock         raw_spinlock_t (4B)
+0x08 waiters           struct rb_root (8B, rb_node *)
+0x10 waiters_leftmost  struct rb_node * (8B, top waiter)
+0x18 owner             struct task_struct * (8B, bit0 = HAS_WAITERS)
```

`+0x20/+0x28/+0x30/+0x38/+0x40` are NOT members (OOB, object ends at 0x20).
No load on the FULL !requeue path touches them. Anything claiming
`lock+0x28` as a lock field is wrong; `owner+0x28` is a task field (sec. 6).

`rt_mutex_waiter` (stack, for reference): `+0x38 lock`, `+0x40 prio`,
`+0x48 deadline`. `task_struct`: `+0x28 usage (atomic_t)`, `+0x7d4 pi_lock`,
`+0x7e0 pi_waiters`, `+0x7e8 pi_waiters_leftmost`, `+0x7f0 pi_blocked_on`
(all OFFLINE_ONLY via DWARF/source; stock vendor hunk unclosed but path is
textually upstream).

Per-field natural assessment (FULL !requeue, iter1 task=W):

- `lock+0x00`: free spinlock at entry (O holds the mutex but wait_lock is
  only held briefly). Writer: `_raw_spin_trylock` (RMW, H4) / unlock.
  Stable: yes. NULL (0) -> trylock succeeds; locked -> spin at H5
  (`cpu_relax` retry), observable only as delay. Branch H5, no WARN.
- `lock+0x08`: rb_root. N0 NULL/empty, N1/N2 non-NULL. Writer:
  enqueue/dequeue under wait_lock. Stable during walk (lock held).
  Effect in !requeue: NONE, not read (only reached inside
  enqueue/dequeue, both skipped when w24=0). No branch on it here.
- `lock+0x10`: leftmost. N0 NULL, N1 occ ptr, N2 occ1 ptr. Writer:
  enqueue/dequeue. Stable. NULL -> OFFLINE predicts fault at H18
  (read 0x38); stock gives TIMEOUT, zero panic (HARDWARE_REFUTED panic,
  HARDWARE_REPRODUCED gate). Non-NULL -> walk continues. Branch H19
  (`cmp` + `brk #0x800`). This is the alterable predicate.
- `lock+0x18`: owner raw. Always O|bit in N0/N1/N2 (O holds f_target).
  Writer: fixup/take paths under wait_lock. Stable. NULL -> bail at H11
  (`tst`/`b.eq` to return 0, TIMEOUT). Non-NULL -> owner RMWs. Branch H11.
  Not alterable without releasing f_target (destroys graph).
- `lock+0x20..0x40`: OOB. No insn, no branch, no WARN. STOCK UNKNOWN
  beyond "not part of object"; do not use.

## 3. Post-lock Dataflow

`--heap-chain` H0-H20, FULL !requeue, iter1 task=W lock=f_target.
Base `rt_mutex_adjust_prio_chain` = 0xffffff8009104d68 (OFFLINE_ONLY VAs):

```
H0  LOAD   0x4df0 (+0x88)  ldr x0,[x28,#0x38]   waiter->lock -> x0
H1  BRANCH 0x4df4 (+0x8c)  cmp x20,x0 / b.ne out  stability gate
H2  LOAD   0x4e28 (+0xc0)  ldr w1,[x28,#0x40]   waiter->prio
H3  BRANCH 0x4e30 (+0xc8)  FULL: match -> w24=0 CONTINUE (MIN would bail)
H4  RMW    0x4e44 (+0xdc)  bl _raw_spin_trylock  [lock+0x00] FIRST heap touch
H5  BRANCH 0x4e48 (+0xe0)  cbnz w0 -> continue else spin
H6  BRANCH 0x4f10 (+0x1a8) cmp x20,x26 / b.eq EDEADLK  lock==orig?
H7  LOAD   0x4f18 (+0x1b0)  ldr x0,[x20,#0x18]   [lock+0x18] owner
H8  BRANCH 0x4f24 (+0x1bc) cmp owner,top_task / b.eq EDEADLK
H9  BRANCH 0x4f2c (+0x1c4) cbz w24 -> tail 0x5024 (!requeue)
H10 LOAD   0x504c (+0x2e4)  ldr x0,[x20,#0x18]   owner re-read
H11 BRANCH 0x5050 (+0x2e8)  tst / b.eq 0x50f4     NULL -> ret 0
H12 RMW    0x5068 (+0x300)  ldxr/add/stxr [x21]   [owner+0x28] INC
H13 RMW    0x5080 (+0x318)  bl _raw_spin_lock     [owner+0x7d4]
H14 LOAD   0x5084 (+0x31c)  ldr x0,[x19,#0x7f0]   owner->pi_blocked_on
H15 BRANCH 0x5088 (+0x320)  cbz -> 0x51bc
H16 LOAD   0x508c (+0x324)  ldr x2,[x20,#0x10]   [lock+0x10] leftmost
H17 LOAD   0x5090 (+0x328)  ldr x28,[x0,#0x38]    next_lock (&f_chain)
H18 LOAD   0x5094 (+0x32c)  ldr x0,[x2,#0x38]     top->lock (BUG_ON)
H19 BRANCH 0x5098 (+0x330)  cmp x20,x0 / b.ne brk #0x800 (0x5114)
H20 BRANCH 0x50b4 (+0x34c)  cbz x28 -> out else again task=O
```

Answer: first heap word is `lock+0x00` (H4 RMW, no value branch beyond
free/locked). `lock+0x08` is untouched here. First heap-VALUE branches are
H6/H8 (identity, not state). First heap-STATE branch alterable naturally is
H16 (sec. 4).

## 4. HEAP_PREDICATE_0

`lock+0x10 waiters_leftmost` at H16 (0x508c `ldr x2,[x20,#0x10]`), checked
at H18/H19 (0x5094 `ldr x0,[x2,#0x38]` + 0x5098 `cmp x20,x0` / `b.ne brk`).

- N0: x2=NULL. OFFLINE predicts fault at 0x38; stock gives TIMEOUT_BLOCK
  3000ms, zero panic (fault HARDWARE_REFUTED, gate HARDWARE_REPRODUCED).
- N1/N2: x2=occ ptr (prio 120, lock=&f_target, valid). cmp passes, walk
  goes to again, iter2 closes at `lock==orig` EDEADLK (0x4f10/0x5124).
- Natural control: park 1 thread on f_target (`occ_fn` LOCK_PI, ordinary
  PI usage, no injected data). Minimum 1; N2 stable (sec. 7).
- Instruction that decides: 0x5098 cmp + 0x509c b.ne (with 0x5094 load as
  the deref). Semantically the gate is "leftmost NULL vs occ".

## 5. HEAP_PREDICATE_1

`lock+0x18 owner` NULL check at H11 (0x5050 `tst` / 0x5054 `b.eq 0x50f4`).

- Natural: always O (non-NULL) in N0/N1/N2, so both sides continue to H12.
  Does NOT diverge on occupancy; not the observed gate.
- NULL would return 0 (end of chain, TIMEOUT) without touching owner.
- Not naturally alterable: clearing owner means releasing f_target, which
  destroys the W->O edge the walk needs. Documented so nobody mistakes the
  owner check for the occupancy gate. OFFLINE_ONLY; no hardware variable
  attempted (would break graph).

Further heap-identity branches H6 (lock==orig) / H8 (owner==top_task) are
EDEADLK verdicts, not state predicates: natural f_target!=f_chain and
O!=C, so they pass in iter1 and fire in iter2 (lock==orig). Not alterable
naturally.

## 6. Owner Consumption

`owner` at H12/H13 is O (f_target owner, heap task_struct, blocked on
f_chain, pi_blocked_on valid). Field at `owner+0x28` is
`task_struct.usage` (atomic_t refcount, sched.h:1635).

- H12 exact: 0x5060 `add x21,x19,#0x28`; 0x5068 `ldxr w0,[x21]` /
  0x506c `add w0,#1` / 0x5070 `stxr` (+ retry loop). Type: RMW atomic INC
  = `get_task_struct(O)`. Unconditional once H11 passes.
- Mirror DEC exists on the put path (0x4e7c `ldxr/sub/stxr` at
  `x21=x19+0x28` for the previous task; 0x4f78 tail equivalent).
  Net refcount change over a full iteration: balanced (get + put), zero
  leak by design.
- H13 exact: 0x5078 `add x22,x19,#0x7d4`; 0x5080 `bl _raw_spin_lock`.
  Type: RMW cmpxchg at `owner+0x7d4` = `task_struct.pi_lock`.
- Reached on stock? EDEADLK in N1/N2 proves H11 passed and H12/H13 ran
  (they dominate H16 on the taken path): walk cannot reach leftmost load
  without first inc'ing O and locking O pi_lock. No userspace-visible
  counter for it (heap task), so the verdict itself is the confirmation.
  HARDWARE_REPRODUCED as path consequence, not as isolated write.

## 7. Natural State Matrix

Same trigger/graph/consumer/timeout; only f_target occupancy varies.
No stamper/fake/spill/poll/pselect/stack spray. P-protocol P0-P8.

| cfg | owner | has_waiters (task) | top_waiter (lock+0x10) | lock fields | consumer result |
|-----|-------|--------------------|------------------------|-------------|-----------------|
| N0 trg_inwin occ_n=0, f_target livre (O holds, empty) | O | W non-empty (O_waiter); O empty-ish | NULL | +0x00 free, +0x10 NULL, +0x18 O | TIMEOUT_BLOCK 3000ms HARDWARE_REPRODUCED |
| N1 occ_tgt occ_n=1, 1 waiter parked | O | W non-empty; O non-empty (occ) | occ (prio 120) | +0x00 free, +0x10 occ, +0x18 O | EDEADLK_CYCLE 0ms HARDWARE_REPRODUCED |
| N2 occ2_tgt occ_n=2, 2 waiters parked | O | W non-empty; O non-empty | occ1 (top stable) | +0x00 free, +0x10 occ1, +0x18 O | EDEADLK_CYCLE 0ms HARDWARE_REPRODUCED |
| N3 | - | not needed | - | - | not run: prio/owner never varied, FULL ignores prio (H3) |

N3 omitted deliberately: predicate uses only existence, prio identical
(~120) in all runs and H3 proves FULL continues regardless.

## 8. Hardware Experiment

One boot window, uptime 4:40, zero panic/reboot, adb stable.
`adb shell /data/local/tmp/ghostlock_chain 0x0 B <mode>`:

- N0 trg_inwin HARDWARE_REPRODUCED: P1 TRIGGER_ENTER, P2 EDEADLK 35,
  P3 GRAPH_PRESERVED fwrq_alive=1 fwake_errno=22, P4 OCCUPANCY_ARMED
  occ_n=0, P5 DONE errno=110 elapsed 3000ms, P6 RESULT=TIMEOUT_BLOCK,
  P7 occ_n=0 errno=110, P8 END.
- N1 occ_tgt HARDWARE_REPRODUCED: P1 TRIGGER_ENTER (occupied), P2 EDEADLK,
  P3 occ_n=1 fwake_errno=22, P4 occ_n=1, P5 DONE errno=35 elapsed 0ms,
  P6 RESULT=EDEADLK_CYCLE, P7 occ_n=1 errno=35, P8 END.
- N2 occ2_tgt HARDWARE_REPRODUCED: same as N1 with occ_n=2 occ2_parked=1,
  P5 DONE errno=35 0ms, P6 EDEADLK_CYCLE.
- Control occ_base HARDWARE_REPRODUCED: P1 TRIGGER_SKIPPED occ_n=1,
  P5 DONE errno=110 3000ms, P6 TIMEOUT_BLOCK. Occupied f_target alone
  does not create EDEADLK.
- pos_cycle HARDWARE_REPRODUCED: P0 LOCK_PI(f_chain) rc=-1 errno=35 during
  arming (valid cycle, no stale). See sec. 10.

Protocol respected: P0 READY, P1 TRIGGER_ENTER, P2 EDEADLK, P3
GRAPH_PRESERVED, P4 NATURAL_STATE_ARMED (OCCUPANCY_ARMED, no stamp),
P5 LOCK_PI_ENTER, P6 RESULT, P7 OBSERVED_STATE (TARGET_STATE),
P8 END. No stamper/fake/spill/poll/pselect/stack spray.

## 9. Observable Side Effects

Best (and only) natural user-visible effect: return code + timing of the
timed consumer.

- N0: ETIMEDOUT 110 after ~3000ms (slept, no cycle).
- N1/N2: EDEADLK 35 after ~0ms (cycle closed, no sleep).
- Deterministic across runs (N1 7x total counting prior, N2 3x, N0 2x
  counting trig_t/trg_inwin, bases 4x/2x). No WARN claimed (dmesg denied).
- Rejected as side channels: waiter+0x40/+0x48 stores land in W kernel
  stack (invisible); enqueue would write to heap lock (invisible, and
  skipped in !requeue anyway); owner+0x28 inc/dec balanced (net zero);
  priority unchanged (FULL !requeue does no boost). EDEADLK vs TIMEOUT is
  the effect directly tied to H16 dataflow.

## 10. pos_cycle Comparison

pos_cycle builds a VALID cycle (W holds f_chain blocks f_target; O holds
f_target blocks f_chain; O LOCK_PI(f_chain) returns EDEADLK during arming).
Same function (`rt_mutex_adjust_prio_chain`), same verdict site
(0x5124 `mov w22,#-0x23`), same code 35, same immediacy (0ms).
HARDWARE_REPRODUCED.

Divergence: pos_cycle root is a live valid waiter (no stale, no
0x52f0/0x4df0 stale loads); GhostLock root is the stale W_waiter
(0x52f0 -> 0x52fc -> 0x4e60 -> 0x4df0). Both converge at H4 trylock and
take the same !requeue tail; iter2 `lock==orig` fires in both. Pair with
occ_base proves EDEADLK is not "any occupied lock" (occupied alone
TIMEOUT) and not "broken syscall" (valid cycle EDEADLK works).

## 11. First Controllable Natural Field

`lock+0x10 waiters_leftmost`: NULL -> occ ptr, flipped by parking exactly
1 thread on f_target before the trigger. Dataflow clear (H16-H19),
natural change (ordinary LOCK_PI park), low risk (no corruption, graph
intact), result observable (TIMEOUT 3000ms vs EDEADLK 0ms).
HARDWARE_REPRODUCED. Stopped here; no write primitive attempted this round.

## 12. What Is Proven

- First heap touch past waiter stack is `lock+0x00` RMW trylock (H4).
  OFFLINE_ONLY VAs, HARDWARE_REPRODUCED as path (EDEADLK cannot happen
  without passing it).
- First naturally-alterable heap predicate is HEAP_PREDICATE_0
  (`lock+0x10`, H16-H19). HARDWARE_REPRODUCED (N0 vs N1/N2).
- `lock+0x08` untouched in !requeue; `+0x20..` OOB. OFFLINE_ONLY.
- HEAP_PREDICATE_1 (owner NULL, H11) exists but does not diverge on
  N0/N1. OFFLINE_ONLY.
- `owner+0x28` is `task_struct.usage` INC (get_task_struct(O) at 0x5068,
  RMW) + `owner+0x7d4` pi_lock cmpxchg (0x5080), reached as a necessary
  consequence of the EDEADLK path. HARDWARE_REPRODUCED as consequence.
- Natural FULL_CHAINWALK stale->heap->verdict on stock.
  HARDWARE_REPRODUCED. Stale pointer + FULL_CHAINWALK stays closed
  (not reopened).

## 13. What Is Not Proven

- Empty-case micro-branch before/at H18 on stock (why N0 TIMEOUT instead
  of fault): fault prediction HARDWARE_REFUTED, exact bail point
  INCONCLUSIVE. Does not affect existence conclusion.
- Attacker-chosen lock walk, fake rt_mutex, stack stamper, spill, cred,
  arbitrary R/W, root: not attempted, INCONCLUSIVE by design.
- Absolute trigger geometry (SP0-0x2b0 etc): STOCK UNKNOWN, unused.
- DWARF offsets on stock: OFFLINE_ONLY (vendor hunk unclosed for these
  structs, though path is upstream-identical and VAs verified 30/30 lab).

## 14. Next Bottleneck

Exactly one: the first heap write that could carry attacker bytes AFTER
the H16 gate is the requeue-path enqueue (`lock+0x08/+0x10` stores) and
the `waiter+0x40/+0x48` stores, but !requeue skips them, and the reached
RMWs (`lock+0x00`, `owner+0x28`, `owner+0x7d4`) are on fixed natural
addresses with balanced effects. So no natural write is both reached AND
attacker-valued today. The minimum artificial control point is a stable
`waiter->lock` pointing at a controlled page while keeping H16 non-NULL
(i.e. solve stale-pointer value control, not occupancy). Do not build it
yet; this report is the stop line.
