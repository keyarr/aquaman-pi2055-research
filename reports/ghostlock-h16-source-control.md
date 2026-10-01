# ghostlock h16 source control — pi_state->pi_mutex origin

Date: 2026-10-01. Authority: Xiaomi Mi TV Stick 1080p (aquaman, S805Y/GXL,
Android 9, PI.2055, 4.9.113 arm64). Lab: build-aq/vmlinux +
.src/linux-amlogic (futex.c, rtmutex.c, rtmutex_common.h).
No fake, no stamper, no spill, no stack spray in the verdict path.
Second legitimate rt_mutex only (f_alt).

Tools: `tools/ghostlock_deref_chain.py --pi-source` (new this round:
S0-S4 + writers + rebind verdict, live from binary) + `--h16`/`--h16-write`
(unchanged). `tools/ghostlock_chain.c`: header notes h16_static
HARDWARE_REPRODUCED; no protocol change (P0-P8 identical).

Question: does a legitimate path exist to make the waiter birth value
`waiter->lock` (H16) carry `&f_alt.pi_mutex` instead of `&f_target.pi_mutex`
without writing `[W_waiter+0x38]` directly?

## 1. H16 Baseline on Stock

New harness mode `h16_static` (mode 22): same arming as alt_only
(occ_n=0, f_alt held by A + 1 parked altocc waiter), full GhostLock trigger,
in-window, consumer does TWO sequential timed LOCK_PI(f_chain) probes on the
SAME live frame (first via g_lock1, second repeats g_lock1, `g_second == 2`).
No corruption. Both TIMEOUT proves the slot stayed static across the
H16.4/H16.7 window and the consumer still reads the field after the window.

Run 1 (2026-10-01, uptime ~5:01, pad 0x0, VAR B):

```
P0 READY var=B mode=h16_static pad=0x0 fake=0x7f7ac22000 win=0x2740c0 pipe=3,4
P1 TRIGGER_ENTER cmp_requeue_pi f_wait->f_target
P2 EDEADLK errno=35 (Resource deadlock would occur)
P3 GRAPH_PRESERVED no_teardown waiter_keeps_f_chain owner_blocked fwrq_alive=1 fwake_errno=22
P4 NO_STAMP in_window sp_futex=0x7d68968b80 waiter_est_lab=0x7d689688d0 (NOT a stock offset)
P4 OCCUPANCY_ARMED occ_n=0 occ2_parked=0
P4 ALT_ARMED a_armed=1 alt_go=1 alt_parked=1 f_alt=2147496221
P5 LOCK_PI_ENTER var=B mode=h16_static target=f_chain timeout_abs3s in_window
P5 LOCK_PI_DONE rc=-1 errno=110 (Connection timed out) elapsed_ms=3000
P5b LOCK_PI_TARGET_DONE rc=-1 errno=110 (Connection timed out) elapsed_ms=3000
P6 RESULT=TIMEOUT_BLOCK mode=h16_static target=f_chain in_window done=1 rc=-1 errno=110 elapsed_ms=3000
P7 TARGET_STATE occ_n=0 f_target_occupied=0 occ2_parked=0 alt_parked=1 consumer_errno=110 elapsed_ms=3000
P8 END mode=h16_static (exit 1)
```

Run 2 (repeat, same boot): identical except
`sp_futex=0x7d8f350b80 f_alt=2147496229`, P5 3000ms/110 + P5b 3000ms/110,
P6 TIMEOUT_BLOCK. EVIDENCE: HARDWARE_REPRODUCED (2x, zero panic, zero reboot).

Controls same boot, same pad:

* `alt_only` (occ_n=0 + f_alt held+occupied): P5 DONE rc=-1 errno=110
  3000ms, P6 TIMEOUT_BLOCK, alt_parked=1. EVIDENCE: HARDWARE_REPRODUCED.
* `alt_tgt` (occ_n=1 + f_alt held+occupied): P5 DONE rc=-1 errno=35 0ms,
  P6 EDEADLK_CYCLE. EVIDENCE: HARDWARE_REPRODUCED.
* Prior `alt_base` (consumer f_alt timed, no trigger): TIMEOUT 3000ms
  (history, unchanged). EVIDENCE: HARDWARE_REPRODUCED.

No observable alteration between the two probes: timing identical to the
millisecond, same errno, same P6. This is baseline only, not a mutability
proof. EVIDENCE: HARDWARE_REPRODUCED for static baseline.

## 2. Exact H16 Birth

`task_blocks_on_rt_mutex` (base 0xffffff8009105228), lab VAs
(OFFLINE_ONLY, stock slides all VAs by KASLR; offsets build-invariant):

* `H16.0 0xffffff800910527c task_blocks_on_rt_mutex+0x54`
  `stp x20,x19,[x21,#0x30]` (`[x21,#0x30]=task=x20, [x21,#0x38]=lock=x19`).
  Before: `bl __rt_mutex_adjust_prio @0x5278`. After: `ldr w0,[x20,#0x68]
  @0x5280` (task->prio) + `str w0,[x21,#0x40]` + deadline `ldr/str
  @0x5288/0x528c`. Creator rtmutex.c:997-998 (`waiter->task = task;
  waiter->lock = lock`). Source grep `waiter->lock =`: exactly 1 hit.
  EVIDENCE: OFFLINE_ONLY (source + binary 30/30 verify).
* In-window readers: `H16.4 0x52fc ldr x25,[x0,#0x38]` (first stale deref,
  next_lock as x3) and `H16.7 0x4df0 ldr x0,[x28,#0x38]` + `cmp x20,x0
  @0x4df4 / b.ne out` (first value branch). Both read the SAME stack slot
  twice; stability required across both. EVIDENCE: OFFLINE_ONLY.
* W waiter = FWRQ stack slot SP0-0x2b0 (x29+0x80, `add x21,x29,#0x80
  @0xb454`, frame 0x1a0 @0xb398, DWARF futex.c:2858 fbreg-288).
  Frame alive while W sleeps (W never returns, hrtimer only exit,
  `fwake_errno=22` = futex_wake refuses PI). EVIDENCE: OFFLINE_ONLY for
  layout; HARDWARE_OBSERVED for alive (P3/P4 lines + double TIMEOUT).

## 3. pi_state->pi_mutex Dataflow

Full chain `futex target -> futex key -> pi_state -> pi_mutex -> waiter->lock`
(`--pi-source` output, each hop VA+insn+reg+offset+source+transform+life+control):

* S0 STRUCT (futex.c:197-213): `futex_pi_state { list 0x00(16); pi_mutex
  0x10(32); owner 0x30(8); refcount 0x38(4); key 0x40(16); }`. `pi_mutex`
  is INLINE: `&pi_state->pi_mutex == pi_state + 0x10` (LEA, never a stored
  pointer). No memory word holds the pointer. EVIDENCE: OFFLINE_ONLY.
* S1 TARGET -> KEY (`get_futex_key` futex.c:498-531, PRIVATE fast):
  `key->private.mm = current->mm; key->private.address = page-aligned uaddr;
  key->both.offset = uaddr % PAGE_SIZE`. uaddr = x0 syscall arg
  (&f_target / &f_alt / &f_chain). Keys live on requeue/lookup stack
  (futex_requeue x29+0xc0/0xd8; wait_requeue_pi key2 stack; lock_pi x29+0xd0).
  Userspace picks WHICH futex, not key bytes. f_target vs f_alt: different
  uaddrs, same mm -> keys differ in address word; buckets may collide but
  `match_futex` compares full keys. EVIDENCE: OFFLINE_ONLY.
* S2 KEY -> PI_STATE (futex_requeue + proxy_trylock path):
  `futex_requeue @0xa8d8 bl futex_top_waiter` ->
  `futex_lock_pi_atomic @0x97b4 bl futex_top_waiter` ->
  `attach_to_pi_state @0x97c8` (reuse: TID match + refcount!=0 check
  `ldr w0,[x19,#0x38] @0x922c`, inc `add x2,x19,#0x38 @0x9254` ldxr/stxr,
  `*ps = pi_state`) OR `attach_to_pi_owner @0x9874`
  (fresh: `alloc_pi_state` = `ldr x20,[x0,#0x8e0] @0x9600`
  current->pi_state_cache, then `add x0,x20,#0x10 @0x9614`,
  `bl rt_mutex_init_proxy_locked`, `pi_state->key = *key`
  `stp/ldp @0x961c-0x9630`, `pi_state->owner = p str @0x9650`).
  `futex_q.pi_state` at q+0x50 (`str x0,[x26,#0x50] @0xabe0`).
  Lifetime refcount>0 from attach to last `put_pi_state`; GhostLock window
  holds refs (no teardown). Userspace selects key + uval TID, cannot pick
  heap address. EVIDENCE: OFFLINE_ONLY.
* S3 PI_STATE -> PI_MUTEX (LEA, the H16 value source):
  `0x9614 add x0,x20,#0x10` (attach, x20=pi_state) +
  `0xabe4 add x0,x0,#0x10` (futex_requeue, x0=pi_state from [x29,#0xa8] ->
  x0=&pi_mutex, then `bl start_proxy_lock @0xabe8`) +
  `0xb1b8/0xb238/0xb2a0 add x0,x0,#0x10` (futex_lock_pi, x0=q.pi_state
  from [x29,#0x120]). `+0x10 == offsetof(pi_mutex)` (list_head 16B).
  Constant +0x10 only; no key/owner/TID mixed in. Valid while refcount>0.
  Control NONE beyond S2. EVIDENCE: OFFLINE_ONLY.
* S4 PI_MUTEX -> WAITER->LOCK (H16.0 above): x19=lock (from S3 x0 via
  `start_proxy_lock(lock,waiter,task)` -> `task_blocks(lock,waiter,task)`,
  `mov x19,x0 / mov x21,x1 / mov x20,x2 @0x5240-0x5248`) ->
  `[x21,#0x38]`. No transform. EVIDENCE: OFFLINE_ONLY.

GhostLock W instance: key2 = f_target key -> pi_state(f_target, owner O) ->
`add +0x10` -> `start_proxy_lock` on behalf of W (`this->task = W`) ->
`waiter->lock = &f_target.pi_mutex`. Consumer C instance: same chain with
f_chain key -> `waiter->lock = &f_chain.pi_mutex` (own stack, valid).
EVIDENCE: OFFLINE_ONLY for dataflow; HARDWARE_REPRODUCED for end values
(N1/N2 EDEADLK consumes f_target; alt_only TIMEOUT ignores f_alt).

## 4. pi_mutex Writers

Writers of `pi_state->pi_mutex`-as-pointer: ZERO (LEA, not a stored word).
Inventory by class:

* NATURAL_WRITER (address): exactly 1: H16.0 `stp @0x527c` (birth).
  EVIDENCE: OFFLINE_ONLY (grep 1 hit + verify).
* CONTENT writers (lock fields, address unchanged, listed so they are not
  mistaken for source control): `rt_mutex_init_proxy_locked @0x5828`
  (wait_lock/waiters/owner init); enqueue/dequeue (waiters rb + leftmost);
  trylock RMW (wait_lock); `fixup_pi_state_owner` (owner handoff
  futex.c:2219, owner only); `put_pi_state` proxy_unlock on free. None
  writes `waiter->lock`. EVIDENCE: OFFLINE_ONLY.
* REUSE_WRITER: NONE (requeue `start_proxy` reuses the SAME pi_state for the
  requeued waiter = same birth path, not a rewrite of live H16).
  EVIDENCE: OFFLINE_ONLY.
* LIFETIME_WRITER: NONE (`put/free/cache` never touches `waiter->lock`;
  frame alive so no recycle inside window). EVIDENCE: OFFLINE_ONLY.
* CORRUPTION_ONLY: any post-birth store to `[W_waiter,#0x38]`; none found
  (3384 `#0x38` stores / 202 subsys / 7 PI-adjacent all KERNEL_ONLY or
  small-int; `--h16-write` live scan + 87 spill + 22 ioctl review).
  EVIDENCE: OFFLINE_ONLY (scan) + INCONCLUSIVE on stock (no candidate to probe).

## 5. Futex Target Derivation

`pi_mutex` address = f(target key) = (pi_state object for that key)+0x10.
f_target key != f_alt key (different uaddr, same mm) -> different pi_state
objects -> different pi_mutex addrs. No alias: hash collision still
key-compared (`match_futex`); bucket reuse never merges states.
`pi_state->key` written once at creation (`stp x0,x1,[x20,#0x40]` +
`str x0,[x20,#0x50] @0x961c-0x9630` from key stack); NO updater exists
(`fixup_pi_state_owner` updates owner only; `requeue_futex` updates
`q->key`, never `pi_state->key`). Same pi_state cannot represent another
target. Pointing CMP_REQUEUE at f_alt births H16=f_alt but moves the WHOLE
graph (owner A, key f_alt), not H16 alone — changes the experiment, not the
pointer. EVIDENCE: OFFLINE_ONLY for structure; HARDWARE_REFUTED for natural
retarget (sec. 10).

## 6. Requeue/Rebind Analysis

`futex_requeue` obtains pi_state for key2 BEFORE the loop
(`futex_proxy_trylock_atomic`/`lookup_pi_state`), then per-waiter:
`this->pi_state = pi_state (str @0xabe0)` +
`rt_mutex_start_proxy_lock(&pi_state->pi_mutex, this->rt_waiter, this->task)`
which births `waiter->lock` (H16.0). No second store updates `waiter->lock`
after birth (binary 0x5400-0x554c `remove_waiter` has no `str` to `+0x38`;
enqueue/dequeue never touch `+0x38`). Rollback (`start_proxy` EDEADLK ->
`remove_waiter`) dequeues but leaves `waiter->lock` intact. PI->PI requeue
rejected: loop bails `-EINVAL` if `this->pi_state || !this->rt_waiter`
mismatch (futex.c:1920-1925); `f_wait(non-PI)->f_target(PI)` ok once,
`f_target(PI)->f_alt(PI)` refused. So no `f_target -> f_alt -> stale waiter`
without a fresh birth on a fresh waiter (different slot/graph). The requeue
mechanism offers no way to choose which `rt_mutex` the EXISTING waiter
records in H16. EVIDENCE: OFFLINE_ONLY (dataflow); discarded.

## 7. PI State Lifetime

`alloc_pi_state` (futex.c:804): `pi_state = current->pi_state_cache`
(task+0x8e0) or slab `futex_pi_state` via `refill_pi_state_cache`;
`put_pi_state` (futex.c:820): `atomic_dec_and_test(refcount @+0x38)` then
list-del + proxy_unlock + kfree-or-cache. GhostLock preserves the graph
(no FUPI, no unlock, no join; `fwake_errno=22` keeps W FWRQ frame +
pi_state refs alive). No free/reuse inside the window; `h16_static` double
probe lands on the same live objects (identical verdicts 3000ms apart).
`pi_state->owner` may hand off (`fixup_pi_state_owner`) but the address
`pi_state+0x10` never moves. EVIDENCE: OFFLINE_ONLY for code;
HARDWARE_REPRODUCED for alive-across-window (double TIMEOUT).

## 8. Candidate Source Control

Zero plausible legitimate paths survived S1-S4 + writers + rebind:

* Requeue to f_alt: moves whole graph, not H16 alone. Rejected (sec. 5-6).
* Rollback updating `waiter->lock`: `remove_waiter` never touches `+0x38`.
  Rejected offline.
* Lifetime reuse/alias: W frame alive, no second mapper; occ/altocc waiters
  live on other stacks, never referenced by `W->pi_blocked_on` (bug preserves
  exactly W_waiter). Rejected offline + hardware (alt_only).
* Sched/deboost rewriting it: `adjust_pi` only READS (H16.12), deboost only
  `+0x40/+0x48`. Rejected offline (+ schedA silent history).
* Second waiter substituting the reference: `pi_blocked_on` still W_waiter.
  Rejected by alt_only hardware (sec. 10).
* CMP_REQUEUE_PI / WAIT_REQUEUE_PI / LOCK_PI / UNLOCK_PI / owner handoff /
  key replacement / bucket reuse / object transitions: each either births a
  NEW waiter (different slot) or updates owner/key-of-queue, never the live
  `[W_waiter,#0x38]`. EVIDENCE: OFFLINE_ONLY + HARDWARE_REPRODUCED (fidelity).

No CASE B variant constructed: there is no legitimate mechanism to test, and
fabricating one would be a fake-address experiment, out of scope. The existing
`alt_tgt` / `alt_only` / `alt_base` matrix already covers CASE A
(`pi_state->pi_mutex = f_target`) vs CASE B (`= f_alt`) semantically:
A decides, B ignored. EVIDENCE: HARDWARE_REPRODUCED.

## 9. Hardware Experiment

FASE 0 mandatory `h16_static` executed FIRST on stock before widening analysis
(sec. 1, 2x + controls). No new corruption probe: FASE 3-8 found zero
candidates, so FASE 10 candidate-write test is NOT APPLICABLE (no candidate).
Protocol when one appears (pre-registered): (1) write to a SAFE legitimate
kernel target with observable effect first, then (2) `[W_waiter+0x38] ->
&f_alt`. No crash-target probing. Stock-first rule honored: offline minimal ->
physical test as soon as baseline meaningful -> offline interpret -> repeat
(2x identical). No contradiction between binary and stock on the baseline.
EVIDENCE: HARDWARE_REPRODUCED (baseline); INCONCLUSIVE (candidate write,
by design — nothing to run).

## 10. Retarget Result

Decisive semantic test (no stack write, legitimate objects only):

* Natural `waiter->lock = &f_target.pi_mutex` (occ_tgt history + alt_tgt this
  round): EDEADLK_CYCLE errno=35 0ms. EVIDENCE: HARDWARE_REPRODUCED.
* Alternative `waiter->lock = &f_alt.pi_mutex` naturally: alt_only
  (f_target empty, f_alt occupied, alt_parked=1): TIMEOUT_BLOCK errno=110
  3000ms — walk IGNORES occupied f_alt, follows empty f_target.
  EVIDENCE: HARDWARE_REPRODUCED (this round + 2x history).
* `h16_static` double probe: TIMEOUT+TIMEOUT, same frame. EVIDENCE:
  HARDWARE_REPRODUCED (2x).
* Downstream coherence requirement (owner/leftmost/has_waiters/return/
  chainwalk of each object): f_target path coherent per heap-consumption
  report (trylock heap, leftmost gate, owner O, EDEADLK vs TIMEOUT tied to
  f_target occupancy); f_alt path under the walk never observed (walk never
  consumed f_alt) — signature defined, never observed. Timing alone not
  accepted; the discriminator here is occupancy-gated verdict (EDEADLK vs
  TIMEOUT), which IS a semantic field of the consumed object (leftmost
  existence + owner cycle). EVIDENCE: HARDWARE_REPRODUCED for f_target path;
  INCONCLUSIVE for f_alt path (no retarget).

Retarget reproducibly: NO (naturally impossible; as corruption unattempted).
EVIDENCE: HARDWARE_REFUTED (natural) + INCONCLUSIVE (corruption).

## 11. H16 Source Control Verdict

`H16 SOURCE CONTROL = NATURALLY IMPOSSIBLE`. Exactly one writer at birth
(H16.0), origin fixed LEA `pi_state+0x10`, target determines the pointer via
key->pi_state, requeue does not rebind, lifecycle does not rebind, no alias
exists. This verdict is OFFLINE_ONLY for the purely structural property
(single LEA derivation + zero pointer writers + immutable key binding);
no stock test is needed for that property, and none can refute arithmetic.
The companion dynamic claim (no natural retarget on stock) is
HARDWARE_REFUTED via alt_only/alt_tgt fidelity. EVIDENCE: OFFLINE_ONLY
(structure) + HARDWARE_REFUTED (natural retarget).

The problem is therefore exactly: `8-byte corruption of [W_waiter+0x38]`.
EVIDENCE: OFFLINE_ONLY (derivation above).

## 12. Minimum Required Corruption

DESTINO: `[W_waiter+0x38]` (W FWRQ frame, lab-relative SP0-0x2b0+0x38; stock
absolute STOCK UNKNOWN, frame alive while W sleeps). TAMANHO: 8 bytes, single
word (wider risks frame). VALOR: `&f_alt.pi_mutex` (heap, learned not guessed;
f_alt valid+contended per alt_base). LIFETIME: frame alive between trigger
return and consumer walk; stable across BOTH H16.4 (`0x52fc` x25) AND H16.7
(`0x4df0` + `cmp @0x4df4`) — mismatch bails at `+0x4df8`. VALOR ANTERIOR:
`&f_target.pi_mutex`. VALOR NOVO: `&f_alt.pi_mutex`. PRIMEIRO LEITOR APOS A
CORRUPCAO: H16.4 (consumer entry `ldr x25,[x0,#0x38]`), then H16.7 gate.
Constraints (all OFFLINE_ONLY): f_alt top->lock BUG_ON must hold (true iff
f_alt occupied by a consistent waiter — arm altocc); f_alt+0x00 trylock must
succeed or the walk spins; owner A must stay consistent or H11 bails.
EVIDENCE: OFFLINE_ONLY (offsets/insns) + HARDWARE_REPRODUCED (window alive
via double TIMEOUT).

## 13. Existing Primitive Composition

No new generic-write hunt; only a primitive satisfying `write 8 bytes +
dest can reach live kernel stack + value can equal kernel pointer`:

* BL33/fastboot control primitive (rounds 7-16,37-38): bootloader USB path,
  not reachable from shell futex context, no kernel-stack store.
  NOT APPLICABLE. EVIDENCE: OFFLINE_ONLY.
* Futex tooling (chain/reachability/race/uaf/reclaim): trigger + consumer +
  occupancy only; FWRQ self-overlap (EAGAIN restamp) hand-verified: prologue
  never spills x0-x5, lock slot never written. EVIDENCE: OFFLINE_ONLY +
  HARDWARE_REPRODUCED (HANGs, zero fake writes).
* ashmem/configfs: surfaces exist but f_op-swap/blob never demonstrated on
  PI.2055 stock in this repo (ARM32 blob LP64-incompatible). NOT DEMONSTRATED.
  EVIDENCE: OFFLINE_ONLY.
* Pipes/sockets/mmap/ioctl/write/fcntl/debug: spill 87 + 22 vendor ioctls
  reviewed; all int/32b/masked/kernel-fixed or hw side effects; nearest clean
  pointer misses by 0x20 with no alignment knob. No survivor.
  EVIDENCE: OFFLINE_ONLY.
* PI-path composition (trylock, pi_lock, usage INC, enqueue, waiter+0x40/+0x48,
  hash/pi_state/task stores): all dests fixed natural addrs; owner+0x28 INC
  base is O task_struct (heap) with fixed off 0x28, value +1 — provably not
  steerable to `[W_waiter,#0x38]` (type + binary base trace `ldr x19,[x20,#0x18]`).
  Discarded in dataflow. EVIDENCE: OFFLINE_ONLY.
* Async/alias: signal/timers/workqueue/completion targets are own structs;
  futex wake refuses PI; sched path only READS. No waiter-pointer writer.
  EVIDENCE: OFFLINE_ONLY + HARDWARE_OBSERVED (schedA silent history).

Answer: NO existing primitive satisfies exactly this need (0 survivors).
EVIDENCE: OFFLINE_ONLY (scan+review); hardware probe NOT RUN (no candidate).

## 14. What Is Proven

* `h16_static` baseline on stock (double TIMEOUT 3000ms/110, same live frame,
  2x + alt_only/alt_tgt controls). EVIDENCE: HARDWARE_REPRODUCED.
* H16 birth exact (H16.0 `stp @0x527c`, single store, rtmutex.c:998).
  EVIDENCE: OFFLINE_ONLY.
* `pi_state->pi_mutex` dataflow S0-S4 with VA+insn+reg+offset+source+transform+
  lifetime+control per hop. EVIDENCE: OFFLINE_ONLY (`--pi-source` live).
* `pi_mutex` writer inventory (1 NATURAL address writer, 0 REUSE/LIFETIME,
  CORRUPTION_ONLY empty). EVIDENCE: OFFLINE_ONLY.
* Target derives the pointer (key->pi_state->+0x10); same pi_state cannot
  represent another target (key immutable, no updater). EVIDENCE: OFFLINE_ONLY.
* Requeue cannot rebind live H16 (PI->PI rejected, no post-birth store,
  rollback preserves value). EVIDENCE: OFFLINE_ONLY.
* PI state lifetime covers the window (no free/reuse inside).
  EVIDENCE: OFFLINE_ONLY + HARDWARE_REPRODUCED (alive).
* Natural H16 retarget refuted (alt_only ignores f_alt, alt_tgt follows
  f_target). EVIDENCE: HARDWARE_REPRODUCED.
* Prior proofs untouched (GhostLock EDEADLK, stale pi_blocked_on, stale deref,
  FULL_CHAINWALK, f_target has_waiters gate, leftmost predicate, heap
  consumption, pos_cycle). Not reopened.

## 15. Next Bottleneck

Exactly one: a durable 8-byte write primitive to the live W FWRQ slot
`[waiter,#0x38]` carrying `&f_alt.pi_mutex` (heap address, must be learned),
stable across H16.4 AND H16.7 while the frame is alive. Minimum spec: size 8B;
dest = live W stack slot (stock addr unknown, SP0-relative; learn via safe
probe, not lab constant); value = `&f_alt.pi_mutex` (heap disclosure, not
guess); window = between trigger return and consumer walk; consumer =
`FUTEX_LOCK_PI(f_chain)` FULL; mechanism = any existing path with dest+value
control (none found; new vuln or new alias/async chain required). Do NOT build
fake objects, do NOT chase generic R/W, do NOT touch cred: solve only this
word, then rerun alt_tgt-vs-alt_only as L0-vs-L1. If the analysis holds:

* `H16 CONTROL: HARDWARE_REFUTED NATURALLY`,
* `H16 SOURCE CONTROL: NATURALLY IMPOSSIBLE (OFFLINE_ONLY structure)`,
* `SECOND WRITE PRIMITIVE: NOT FOUND`,
* next step is a fresh primitive search OUTSIDE the surfaces closed here
  (new syscall family, new driver, or heap+stack disclosure first — do not
  repeat the spill window as-is).

---
BOTTOM LINE:

* h16_static reproduced on stock? YES 2x TIMEOUT+TIMEOUT 3000ms/110, plus alt_only TIMEOUT and alt_tgt EDEADLK controls.
* exact origin of pi_state->pi_mutex? LEA pi_state+0x10 (inline struct, three add sites 0x9614/0xabe4/0xb1b8); S1-S4 chain above.
* how many writers? ZERO pointer writers (LEA); ONE address writer H16.0 birth; zero reuse/lifetime; corruption-only empty.
* can requeue rebind pi_mutex? NO (PI->PI rejected, no post-birth store, key immutable, rollback preserves).
* natural path to f_alt? NONE (requeue-to-f_alt moves whole graph; alt_only proves walk ignores f_alt).
* reproducible retarget? NO (HARDWARE_REFUTED natural; INCONCLUSIVE as corruption, unattempted).
* H16 still needs corruption? YES, exactly 8B [W_waiter+0x38] = &f_alt.pi_mutex across H16.4+H16.7.
* minimum corruption size? 8 bytes, single word, live-frame window, learned heap value.
* any existing primitive fits? NO (0 survivors across 3384/202/7 + 87+22 + PI/async/alias).
* single next bottleneck? durable 8B live-stack write with kernel-pointer value; search outside closed surfaces.
