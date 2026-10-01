# ghostlock targeted write — H16 8B stock-relative search

Date: 2026-10-01. Authority: PI.2055 hardware decides runtime.
Lab (build-aq/vmlinux + .src/linux-amlogic) is OFFLINE_ONLY:
reduces candidates, proves nothing about stock.

Tools, this phase:
`tools/ghostlock_h16_target_search.py` (new: --stack/--same-task/--store8/
--stp/--atomic/--carrier/--rtmutex/--current/--frame-reuse/--ioctl/--syscall/
--verify/--all, per-candidate SYSCALL/FUNCTION/STORE_VA/STORE_INSTR/
DESTINATION/DEST_DELTA_FROM_FWRQ/VALUE_REGISTER/VALUE_ORIGIN/VALUE_CLASS/
LIFETIME/SIDE_EFFECTS/STOCK_STATUS) +
`tools/ghostlock_deref_chain.py --target` (new: FASE 7 destination x value
ruler, --disclosure/--emit preserved) +
`tools/ghostlock_chain.c` (header-only delta, P0-P8 unchanged, no new mode,
no memory touched).

Closed, not reopened: GhostLock trigger, stale task->pi_blocked_on, stale
waiter traversal, FUTEX_LOCK_PI(f_chain), FULL_CHAINWALK natural, f_target
has_waiters, leftmost predicate, natural heap consumption, pos_cycle, H16
static baseline, H16 natural immutability, f_alt.pi_mutex legitimacy, f_target
vs f_alt, Mali GET/QUERY read-only (HARDWARE_REFUTED for disclosure), emit
census, depth >3 for audited emit callers, pointer disclosure NONE AVAILABLE,
H16 natural control IMPOSSIBLE. Old lab-absolute SP0-0x278 window retired;
old poll geometry kept as lab data point only.

## 1. Objective

One targeted 8B store: `[W_waiter + 0x38] = &f_alt.pi_mutex`, live W FWRQ
frame, stable across H16.4 + H16.7, consumer FUTEX_LOCK_PI(f_chain) FULL.
First prize C/D: H16 carries &f_alt and the walk follows f_alt. No arbitrary
read/write, cred, root, code exec in scope. EVIDENCE: OFFLINE_ONLY (spec).

## 2. H16 Exact Lifetime

Birth H16.0 `0xffffff800910527c stp x20,x19,[x21,#0x30]` in
task_blocks_on_rt_mutex (`[x21,#0x38]=lock=x19=pi_state->pi_mutex`).
Exactly 1 natural writer (source grep `waiter->lock =` = 1 hit, rtmutex.c:998).
In-window readers H16.4 `0x52fc ldr x25,[x0,#0x38]` (next_lock as x3) and
H16.7 `0x4df0 ldr x0,[x28,#0x38]` + `cmp x20,x0 @0x4df4 / b.ne out` (first
value branch). Both read the same 8 bytes; stability across both required.
Consumer re-reads at H16.10/H16.11/H16.12. Size 8, dest `[W_waiter+0x38]`,
live H16.4->H16.7. EVIDENCE: OFFLINE_ONLY (--verify 6/6 this phase).

## 3. Stock Stack Model

Lab frames (OFFLINE_ONLY): SyS_futex 0x70 + do_futex 0x120 + FWRQ 0x1a0 =
0x330; rt_waiter x29+0x80 = SP0-0x2b0; H16 = SP0-0x278 (H16_LAB).
Stock conjecture: waiter SP0-0x2c8, H16 SP0-0x290 (H16_REL=0x290, 0x18 deeper).
Normalization: `dest_rel = SP0 - sumF + local_off`, `delta = dest_rel -
H16_REL`. stp counts as two 8B words. Window H16+-0x40 is geometry, HIT only
if w==8 and delta==0. Stock absolute offsets INCONCLUSIVE (no stock frame
dump; KASLR slides VAs). Prior pollA `sp_futex==sp_poll dist=0` (same task,
same page/SP base) re-cited, not re-run. EVIDENCE: OFFLINE_ONLY (frames) +
HARDWARE_OBSERVED (prior dist 0) + INCONCLUSIVE (stock absolute).

## 4. Destination Search

`--stack/--store8/--stp/--syscall` (OFFLINE_ONLY, depth<=3, 303 SyS roots):
stock window 8B in window 411 (UNKNOWN 170, KPTR 154, INTEGER 40, UPTR 29,
DERIVED 18); lab window 513 (KPTR 197, UPTR 35) for comparison; stp words in
window 114; per-syscall top: init_module 48, io_setup 43, finit_module 41,
swapon 35, mincore 34. EXACT_H16 (delta==0,w==8): 33 total = 9 KPTR, 0 UPTR,
2 INTEGER, 1 DERIVED, 21 UNKNOWN. No UPTR at exact: userspace-literal
`&f_alt` cannot be placed (no leak, not invented). EVIDENCE: OFFLINE_ONLY.

## 5. Value Carrier Search

`--carrier` (OFFLINE_ONLY): KPTR 8B in window 154, EXACT 9. Finer value
classes (FASE 7): TARGET_RT_MUTEX (pi_mutex/+0x10/rt_mutex 8B kptr) = 0 at
EXACT; OTHER_KERNEL_POINTER = 9 at EXACT (all heavy/privileged/transient,
sec. 9); USER_POINTER 0 at EXACT; rest INTEGER/UNKNOWN. So no exact store
carries an rt_mutex *; the 9 exact KPTR carry task/heap/code words in MM/
module/exit/audit/vmalloc paths. Without a leak, only a kernel carrier can
supply `&f_alt`; none is paired with EXACT dest. EVIDENCE: OFFLINE_ONLY.

## 6. Same-Task Frame Reuse

`--same-task/--frame-reuse` (OFFLINE_ONLY): fast-syscall 8B in window 62
(poll/select/read/write/sendmsg/recvmsg/ioctl/futex). Ranked by same task +
same page + near H16 + KPTR + low side effects: do_sys_poll table/current
(`0xbb8 stp table`, `0xbd0 str x0 current`, delta +32/+8 lab, KPTR, path
SyS_poll>do_sys_poll, USER_COPY/IO, no alloc/sleep) is the only exact-overlap
family in a fast unprivileged graph-safe syscall. Value is task/code *, not
rt_mutex, so geometry probe ONLY, never retarget. Ideal composition
(FWRQ return -> same-thread small syscall -> new frame reuses region -> kptr
store hits H16 -> consumer) has destination-near support (poll) but no value
support (no rt_mutex carrier). EVIDENCE: OFFLINE_ONLY + HARDWARE_OBSERVED
(prior pollA/B HANG, no panic, safety only).

## 7. PI Carrier Paths

`--rtmutex` (OFFLINE_ONLY): LEAs verified: attach_to_pi_owner `0x9614 add
x0,x20,#0x10`; futex_requeue `0xabe4 add x0,x0,#0x10` (+ ldr +0x10 sites);
futex_lock_pi `0xb1b8/0xb238/0xb2a0`; wait_requeue_pi
`0xb574/0xb58c/0xb628/0xb6d0/0xb7cc`; task_blocks `0x5298/0x52d4 ldr +0x10`.
Forward-spill check in the same bodies: attach/task_blocks/start_proxy/
init_proxy ZERO KPTR stack spills; futex_requeue/futex_lock_pi spill only
code/current, never the +0x10 lock reg. Lock reg dies in regs/epilogue, never
lands on a reusable slot. `f_alt -> PI helper -> live reg -> stamper spill ->
H16` has no binary support. EVIDENCE: OFFLINE_ONLY.

## 8. Current/Stack Derived Targets

`--current` (OFFLINE_ONLY): CURRENT 8B in window 9, EXACT 1
(`congestion_wait 0xdb8b8 stp x4,[x29,#0x50]`, mrs SP_EL0, MM sleep path).
`--atomic` (OFFLINE_ONLY): 0 atomic stack stores total, 0 in window; PI RMWs
are heap-fixed (trylock/pi_lock/usage INC/enqueue). `current->stack`/frame-
pointer arithmetic proves kptr movement, not H16 control (value is task, not
rt_mutex; dest is the MM sleep frame, not a fast reuse frame).
EVIDENCE: OFFLINE_ONLY.

## 9. Candidate Matrix

Bidirectional gate (`--target` ruler): EXACT_H16 + (TARGET_RT_MUTEX |
OTHER_KERNEL_POINTER) only. Exact 33, each REJECTED as stamper:

* kobject_add (finit/init_module, heap): privileged module load. REJECT.
* get_page_from_freelist x3 (mincore/io_setup, heap): MM allocator, sleeps. REJECT.
* congestion_wait (io_setup, current): MM sleep, schedules. REJECT.
* __slab_free x2 (reboot>do_exit>kfree, heap): process-exit, destructive. REJECT.
* printk/audit paths (renameat2, heap): error formatting, transient. REJECT.
* __vmalloc_node_range `[sp]` (select>core_sys_select>vmalloc, `ldr
  x2,[x20,#0x38]` heap, `str x2,[sp]` recursion arg at 0x1fa39c): hand-verified
  transient call-arg, wrong value type, heavy. REJECT (nearest exact KPTR).
* warn_alloc/__alloc_pages (io_setup/madvise, int/derived): scalars. REJECT.
* 21 UNKNOWN (`str xN,[sp,#..]` callee-saved spills in tiny leaves incl.
  SyS_futex PI-path `get_futex_value_locked/put_pi_state/start_proxy/
  ___might_sleep` at EXACT): untainted regs, deep/heavy or PI-internal,
  none is a kptr carrier. REJECT (not pointers).
* SyS_ioctl chain (depth 4): 1 near 8B (`locks_mandatory_area`, delta -48),
  0 exact; vendor f_op past depth 4 INCONCLUSIVE (not claimed covered).
* No FASE 16 fixed-value 8B at EXACT that is a legitimate kptr with a fast
  lifetime (fixed values at EXACT are ints/derived). EVIDENCE: OFFLINE_ONLY.

## 10. Hardware Geometry Probe

Not run this session (no adb in this environment). Protocol ready, no write:
same-thread FWRQ (fwrq 2s) -> `pollA` (pad 0x0, timeout 0, nfds<=30
stack-only) -> P4 `sp_futex/sp_poll/dist` + P6 HANG_IN_WALK. Prior dist 0 +
HANG with zero panic re-cited as page/SP reuse proof; absolute waiter offset
stays INCONCLUSIVE. Running it with current/task value must never be thrown
at H16 for retarget (wrong type, garbage trylock risk). First non-corruptive
bar: CANDIDATE GEOMETRY = HARDWARE_REPRODUCED for dist/page only, not for H16
absolute. EVIDENCE: INCONCLUSIVE (not run here) + HARDWARE_OBSERVED (history).

## 11. First H16 Write

Not attempted (no EXACT+TARGET carrier exists). Rule when one appears:
WRITE8(H16, legitimate kptr) single word, frame-alive (W in FWRQ, stable
across H16.4+H16.7), f_target+f_alt valid, no fake/cred/code, one experimental
delta; prove `H16 changed from natural value` with any legitimate kptr first,
then substitute `&f_alt`. No `&f_alt` guess (address undisclosed).
EVIDENCE: INCONCLUSIVE (by design, no candidate).

## 12. f_alt Retarget

Not executed. Pre-registered: f_target owner O + occ_n; f_alt owner A + 1
parked waiter; alt_base TIMEOUT proves contended-valid (HARDWARE_REPRODUCED,
history). CASE A (H16=&f_target) vs CASE B (H16=&f_alt): consumer must differ
by f_alt owner/leftmost/has_waiters, never timing alone. If carrier is not
f_alt, accept any legitimate kptr the walk can follow without panic as
address-selection proof first, then hunt f_alt carrier. EVIDENCE:
INCONCLUSIVE (no retarget) + HARDWARE_REPRODUCED (fidelity: walk follows
f_target, ignores f_alt).

## 13. Downstream Consumer

Consumer stays FUTEX_LOCK_PI(f_chain) FULL (no scheduler swap, no second
consumer until retarget proves). Mapped downstream (OFFLINE_ONLY): H16.8
trylock `[Xn,#0x00]`, H16.9 leftmost `[Xn,#0x10]` + BUG_ON, owner `[Xn,#0x18]`
+ usage INC + pi_lock, iter2/top/sched readers. Under H16=&f_alt the same
offsets replay on f_alt's object; first observed field localizes there, not
assumed. EVIDENCE: OFFLINE_ONLY (mapping) + INCONCLUSIVE (f_alt path).

## 14. Reproducibility

Offline: `--verify` 6/6 OK; `--all` stock 411/154/29, lab 513/197/35, exact
33 = 9/0/2/1/21, TARGET 0; `--rtmutex` LEAs + zero spills; `--atomic` 0/0;
`--ioctl` 1 near/0 exact; `--syscall` census above; `--target` ruler runs.
Hardware this session: 0 runs (no device). History re-cited, not re-proven:
h16_static TIMEOUT+TIMEOUT, pollA dist 0 + HANG, alt_tgt EDEADLK / alt_only
TIMEOUT / alt_base TIMEOUT, zero panic. EVIDENCE: OFFLINE_ONLY (this phase)
+ HARDWARE_* (history, as marked).

## 15. What Is Proven

* H16 birth/readers/window/gate exact (H16.0/H16.4/H16.7 + poll geometry).
  EVIDENCE: OFFLINE_ONLY.
* Exactly one natural writer; natural retarget HARDWARE_REFUTED; source
  control NATURALLY IMPOSSIBLE. EVIDENCE: OFFLINE_ONLY + HARDWARE_REPRODUCED.
* Stock-relative 8B census + per-class exact counts + zero TARGET_RT_MUTEX
  at EXACT + zero UPTR at EXACT + zero atomic at H16 + ioctl 1-near/0-exact.
  EVIDENCE: OFFLINE_ONLY.
* PI +0x10 carrier register-only (zero stack spills). EVIDENCE: OFFLINE_ONLY.
* Poll table/current is H16_RELATIVE with OTHER_KERNEL_POINTER: geometry
  probe only. EVIDENCE: OFFLINE_ONLY + HARDWARE_OBSERVED (safety history).
* No EXACT_H16+TARGET_RT_MUTEX in audited surface (depth<=3, all SyS roots).
  EVIDENCE: OFFLINE_ONLY.
* Harness/header ready, no write performed. EVIDENCE: OFFLINE_ONLY.

## 16. What Is Not Proven

* Stock absolute waiter/lock offsets (0x2c8/0x290 conjecture).
  EVIDENCE: INCONCLUSIVE.
* Any durable 8B H16 write, targeted or general. EVIDENCE: INCONCLUSIVE.
* f_alt downstream signature under the walk. EVIDENCE: INCONCLUSIVE.
* Arbitrary R/W, cred, root, fops, code exec. EVIDENCE: INCONCLUSIVE (out
  of scope until H16 moves).
* Paths deeper than BFS 3 / indirect f_op past depth 4 / unaudited vendor
  ioctls / Mali beyond open (explicitly not covered). EVIDENCE: INCONCLUSIVE.
* Stock VAs/KASLR slide. EVIDENCE: OFFLINE_ONLY/INCONCLUSIVE.

## 17. Remaining Primitive

Exactly one, closed spec:

```text
SIZE: 8 bytes (single word [W_waiter+0x38], wider risks frame)
DEST: live kernel stack, H16 (stock addr unknown; learn via safe SP/dist
      probe, not lab constant; same-task reuse preferred)
VALUE: valid kernel pointer (&f_alt.pi_mutex; learn via heap disclosure,
       never guess; any legitimate kptr accepted as first address proof)
WINDOW: H16.4 (0x52fc x25) -> H16.7 (0x4df0/cmp 0x4df4), frame alive (W in FWRQ)
CONSUMER: FUTEX_LOCK_PI(f_chain) FULL_CHAINWALK
MECHANISM: any existing path with EXACT_H16 dest + TARGET_RT_MUTEX value
           (none in audited surface; new syscall family, new driver,
           heap+stack disclosure, or stack-derived dest needed; do not
           repeat the same window as-is)
```

First dimension impossible today: VALUE (0 TARGET_RT_MUTEX at EXACT;
only register-only LEA exists). Second: DESTINATION with a fast lifetime
(9 exact KPTR all heavy/privileged/transient; only poll near-miss is fast).
`H16 targeted write = NOT FOUND (audited surface)`. Next: stock disclosure
(stack+heap) before any new stamp attempt, then rerun alt_tgt-vs-alt_only as
L0-vs-L1. STOP after both addresses confirm still stands.

---
BOTTOM LINE:

* stock-relative H16? conjecture SP0-0x290 (waiter SP0-0x2c8), STOCK INCONCLUSIVE; page/SP reuse history dist 0, not re-run here.
* syscall/frame touching H16? 411 8B in window; 33 EXACT (9 KPTR, 0 UPTR, 2 INT, 1 DERIVED, 21 UNKNOWN); poll table/current (+8/+20) only fast geometry probe.
* kernel-pointer carrier? 154 KPTR in window but 0 TARGET_RT_MUTEX at EXACT; PI +0x10 LEA register-only, zero spills.
* legitimate rt_mutex* loadable as value? f_alt valid (history) but no store carries it; VALUE = first impossible dimension.
* lowest-risk candidate? poll table/current for GEOMETRY ONLY, never for retarget (wrong value type).
* probe run on stock? no (this session offline only); history h16_static/pollA/alt_* re-cited, zero new hardware claims.
* H16 changed? no (never attempted, no carrier).
* f_alt downstream observed? no (fidelity only).
* targeted vs general? neither demonstrated (only natural walk fidelity).
* single next bottleneck? 8B WRITE8(H16,&f_alt) spec above; first need stock stack+heap disclosure, then a fresh dest+value path outside the closed surface.
