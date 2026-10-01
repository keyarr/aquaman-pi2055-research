# ghostlock h16 write — targeted 8B store [W_waiter+0x38]=&f_alt.pi_mutex

Date: 2026-10-01. Stock authority: Xiaomi Mi TV Stick 1080p (aquaman,
S805Y/GXL, Android 9, PI.2055, 4.9.113 arm64). Lab: build-aq/vmlinux +
.src/linux-amlogic (rtmutex.c, futex.c, sched.h). No fake, no stamper,
no spill, no stack spray, no poll/pselect stamp in the verdict path.
Second legitimate rt_mutex only (f_alt).

Tools: `tools/ghostlock_deref_chain.py --h16` (H16.0-H16.12, unchanged)
+ `--h16-write` (new this round: FASE1 table + narrowed #0x38 store scan
+ PI-path composition + FASE4/7/8 verdicts, live from the binary).
`tools/ghostlock_chain.c` minimal delta: header documents the H16 write
objective + new safe mode `h16_static` (mode 22, two sequential timed
LOCK_PI(f_chain) probes on the same live frame, no corruption).
P0-P8 protocol unchanged.

Objective (FASE 11-12 gate): one controlled 64-bit store
`[W_waiter+0x38] = &f_alt.pi_mutex`, then the natural chain must consume
f_alt instead of f_target with a legitimate-PI signature. Nothing else
(cred/root/RW/fops) is in scope until this word moves on stock.

## 1. Objective

Prove or kill the first corruption point: the 8-byte slot
`[W_waiter,#0x38]` (`waiter->lock`) between `H16.4 = 0x52fc` and
`H16.7 = 0x4df0/0x4df4`. Desired value `&f_alt.pi_mutex` (heap, valid,
owner A + 1 waiter, wait_lock free). Success A = slot changes
reproducibly on stock. Success B = a primitive that can write 8 bytes to
a chosen dest, first target H16. Success C = no legitimate way exists;
close the chain that demands a second primitive (size/dest/value/window/
consumer/mechanism). EVIDENCE labels per claim below.

## 2. H16 Exact Lifetime

Lab VAs (OFFLINE_ONLY, stock slides every VA by KASLR; offsets
build-invariant). Base `task_blocks_on_rt_mutex` = 0xffffff8009105228,
`rt_mutex_adjust_prio_chain` = 0xffffff8009104d68.

* Relative addr: `[W_waiter+0x38]`, W FWRQ frame `SP0-0x2b0+0x38`
  (lab-relative; STOCK UNKNOWN absolute, frame alive while W sleeps).
* Birth: `H16.0 0xffffff800910527c task_blocks_on_rt_mutex+0x54`
  `stp x20,x19,[x21,#0x30]` (`[x21,#0x30]=task [x21,#0x38]=lock`).
  Before: `bl __rt_mutex_adjust_prio @0x5278`. After: `ldr w0,[x20,#0x68]
  @0x5280` + `str w0,[x21,#0x40]` (prio) + `ldr/str @0x5288/0x528c`
  (deadline). Creator: `task_blocks_on_rt_mutex` (rtmutex.c:997-998).
  First writer: H16.0 itself. EVIDENCE: OFFLINE_ONLY.
* In-window readers: `H16.4 0x52fc ldr x25,[x0,#0x38]` (first stale
  deref, next_lock, carried as x3) and `H16.7 0x4df0 ldr x0,[x28,#0x38]`
  + `cmp x20,x0 @0x4df4 / b.ne out` (first value branch on H16).
  Both read the SAME stack slot twice; stability required across both.
  EVIDENCE: OFFLINE_ONLY.
* Last read before consumer: H16.4. Last read after consumer entry:
  H16.7. Consumer still reads the field after the critical window at
  H16.10 (`0x4ff8 ldr x20,[x0,#0x38]`, iter2 next) and H16.11/H16.12
  top/sched readers. EVIDENCE: OFFLINE_ONLY.
* All xrefs to `+0x38` on PI path: `0x52a0 H16.1` (NOT stale, top check),
  `0x52d8 H16.2` (NOT stale, owner path), `0x52fc H16.4` (STALE first),
  `0x4df0 H16.7` (STALE re-read), `0x4f34/0x4fd4/0x4ff8/0x5090/0x5094/
  0x50d8/0x5108/0x5168/0x5190/0x51c0` (iter2/tail, owner-or-top),
  `0x5428/0x54ac/0x54d0 H16.11` (MIN-tail), `0x5784 H16.12` (sched).
  EVIDENCE: OFFLINE_ONLY (`--h16-write` prints the narrowed set live).

Full table (`reader/writer | VA | instruction | function | timing |
source | destination`), NATURAL vs POTENTIAL split:

* NATURAL WRITERS (1): `STORE | 0xffffff800910527c |
  stp x20,x19,[x21,#0x30] | task_blocks_on_rt_mutex | waiter birth
  (wait_lock+pi_lock held) | x19=lock(&f_target.pi_mutex heap) |
  [W_waiter,#0x38]`. EVIDENCE: OFFLINE_ONLY (source grep
  `waiter->lock =` = 1 hit, rtmutex.c:998; binary 30/30 verify).
* NATURAL READERS (stale, in-window): `LOAD | 0x52fc | ldr x25,[x0,#0x38]
  | task_blocks | consumer entry | W_waiter | x25` and `LOAD | 0x4df0 |
  ldr x0,[x28,#0x38] | adjust_prio_chain | walk head gate | W_waiter |
  x0`. EVIDENCE: OFFLINE_ONLY.
* POTENTIAL CORRUPT WRITERS: NONE FOUND (FASE3-8 below).
  EVIDENCE: OFFLINE_ONLY (scan) + INCONCLUSIVE on stock (not probed;
  no candidate to probe).

## 3. Natural Writers

Exactly one store in `kernel/locking + futex.c`: rtmutex.c:998
(`waiter->lock = lock`, binary H16.0). Callers bind the value at birth:
requeue path `lock = pi_state->pi_mutex` of the TARGET futex, slowlock
path `lock = target`. After birth: requeue/dequeue/enqueue,
remove_waiter (stores `current->pi_blocked_on` only, never
`waiter->lock`; binary 0x5400-0x554c has no `str` to `+0x38`),
adjust_prio_chain requeue path (re-enqueues SAME waiter on SAME lock),
adjust_pi/deboost/fixup/try_to_take never store `waiter->lock`.
Stack death recycles bytes but is not a store and the harness keeps the
FWRQ frame alive (fwake_errno=22). So `waiter->lock` is immutable after
creation by any legitimate syscall; overwrite-only by external
corruption. EVIDENCE: OFFLINE_ONLY. `waiter->lock = &f_alt.pi_mutex` as
a NATURAL change is HARDWARE_REFUTED (alt_only: f_alt occupied ignored,
walk follows f_target; 2x, see h16-control report sec.8).

## 4. Write Primitive Search

Full-binary census (OFFLINE_ONLY, `llvm-objdump -d`, live count this
round): `str` 165487, `stp` 156646, `stxr` 2830, `stlxr` 2654,
`stlr` 604; 64-bit `str Xt` 92779; atomic RMW class 5484. Isolated
counts prove nothing; the auditable surface is the narrowed scan:

* Stores with `#0x38`: 3384 total. In futex/RT/signal/poll/select/pipe/
  socket/mmap/ioctl/configfs/ashmem/workqueue/timer/task_work/
  completion subsys: 202. In PI-adjacent symbols
  (`task_blocks,adjust_prio_chain,remove_waiter,adjust_pi,enqueue,
  dequeue,futex_requeue,__pollwait,do_sys_poll,complete_signal,
  process_one_work,configfs_setattr`): 7, all printed live by
  `--h16-write`: `complete_signal+0x?? str x19,[x24,#0x38]` (siginfo),
  `process_one_work x2 (2x) [x0,#0x38]` (worker struct), `futex_requeue
  stp x2,x3,[x21,#0x38]` (futex keys, sec.6), `__pollwait str x22,
  [x0,#0x38]` (poll entry key/wait), `configfs_setattr stp x0,x1,
  [x23,#0x38]` + `stp x0,x1,[x25,#0x38]` (inode timespec/current_time).
  None has dest = W FWRQ stack AND value = `&f_alt.pi_mutex`.
  EVIDENCE: OFFLINE_ONLY.
* RMW/atomic (`stxr/stlrx/cas/casp/swp/ldadd`): 5484 total; on the PI
  path all dests are fixed natural addrs (sec.8: trylock, pi_lock,
  usage INC, enqueue). No user-controlled dest. EVIDENCE: OFFLINE_ONLY.
* Prior spill search (87 window candidates, 8 exact-slot hits, 22 vendor
  ioctls via indirect chain): 0 carry a controlled 64-bit user pointer
  (ints/32b/masked/kernel-heap after review; nearest clean pointer
  `amstream_do_ioctl_old stp +0x48 -> SP0-0x258` misses by 0x20 + programs
  hardware). See ghostlock-spill-search.md sec.6. EVIDENCE: OFFLINE_ONLY.

Per-candidate dest/value/lifetime/userspace-influence: no candidate
passes both dest and value (sec.9). Full per-insn taint of 328k stores
is explicitly NOT claimed; the claim is the narrowed auditable surface
above plus the prior 87-candidate review. EVIDENCE: OFFLINE_ONLY.

## 5. Destination Taint

Backward taint per candidate (user input -> pointer/object -> kernel
transform -> dest pointer -> store):

* H16.0 birth: KERNEL_ONLY (base = new waiter stack, value =
  pi_state->pi_mutex heap). Not user-derived.
* Poll table `+0x38`: base is own stack (fixed SP0-0x2b0), value is
  `events|0x18` small int. Class: KERNEL_POINTER_WITH_USER_CONTROLLED_
  BASE rejected (base fixed, value not a pointer). No pointer control.
* `futex_requeue stp x2,x3,[x21,#0x38]`: dest `x21` is a futex-hash-bucket
  waiter object, values `x2,x3` are futex keys (`ldp x2,x3,[x29,#0xd8]`
  from `attach_to_pi_owner` path), not a user address; lifetime is the
  requeue frame, not W FWRQ. Class: KERNEL_ONLY. EVIDENCE: OFFLINE_ONLY.
* `configfs_setattr` pair: dests are inode (`x23/x25`), values are
  timespec (`current_time`/`timespec_trunc`). Class: KERNEL_ONLY.
* `complete_signal / process_one_work / __pollwait`: dests are
  siginfo/work/poll structs, values kernel pointers/ints. Class:
  KERNEL_ONLY. EVIDENCE: OFFLINE_ONLY.
* Spill-search 87: all KERNEL_ONLY or int/32b/masked after review; 0
  DIRECT_USER_POINTER and 0 USER_DERIVED_POINTER at SP0-0x278 with a 64b
  pointer value. UNKNOWN: none left unclassified (each of the 8 exact
  hits hand-disassembled). EVIDENCE: OFFLINE_ONLY.

 survivors for FASE4: none. Only KERNEL_ONLY remains.

## 6. Value Taint

Value must be `&f_alt.pi_mutex` (heap address, learned not guessed).

* `&f_alt.pi_mutex` exists and is valid on stock (f_alt held by A + 1
  parked waiter; alt_base TIMEOUT proves contended-valid).
  EVIDENCE: HARDWARE_REPRODUCED (prior round).
* No store above takes a user-controlled 64-bit value that could carry a
  heap address: poll key is `events|0x18` (low 16b user, high bits zero);
  `str wN` stores are 32b; printk/warn_alloc values are sizes after
  sxtw/add/lsr; BPF immediates are decoded ints (privileged anyway);
  cmsg stores are kernel sock/stack pointers; compat stores are 32b ints;
  configfs stores are timespecs; futex_requeue stores are keys.
  EVIDENCE: OFFLINE_ONLY.
* DESTINATION CONTROL: none (no dest reaches W FWRQ slot).
  VALUE CONTROL: none (no value carries `&f_alt.pi_mutex`).
  Accepted cases A/B/C: zero candidates. Case C (partial dest + value
  control) also zero: nearest (`amstream +0x48`) misses by 0x20 with no
  arg-controlled alignment knob. EVIDENCE: OFFLINE_ONLY.

## 7. Existing Primitive Inventory

Explicit repo-wide review (no new vuln invented):

* BL33/fastboot reports (rounds 7-16,37-38): control primitive is a
  bootloader USB/download-path artifact, not reachable from the Android
  shell uid-2000 futex context and not composed with the live W frame.
  No kernel-stack store to the waiter. Status: NOT APPLICABLE to H16.
  EVIDENCE: OFFLINE_ONLY.
* Futex tooling (`ghostlock_chain`, `reachability`, `race_stats`,
  `uaf_check/isolate`, `reclaim_try`): trigger + consumer + occupancy
  only; no write primitive. The FWRQ self-overlap idea (EAGAIN restamp)
  hand-verified: prologue never spills x0-x5, lock slot never written.
  EVIDENCE: OFFLINE_ONLY + HARDWARE_REPRODUCED (HANGs, zero fake writes).
* ashmem/configfs (`ghostlock-ashmem-configfs.md`): surfaces exist
  (`/dev/ashmem` crw, configfs mounted) but the f_op-swap/blob route was
  never demonstrated on PI.2055 stock in this repo; hazel blob is ARM32
  LP64-incompatible and the dentry fragility is unclosed. No H16 write
  shown. Status: NOT DEMONSTRATED. EVIDENCE: OFFLINE_ONLY.
* Pipes/sockets (`pipe()`, AF_UNIX, sendmsg/recvmsg/vmsplice/splice):
  spill search covered `cmsghdr_from_user_compat_to_kern`,
  `iov_iter_advance`, `get_compat_msghdr`, `___sys_sendmsg`; all rejected
  (kernel pointers, transformed pipe internals, 32b ints, clobbered
  before return). No survivor. EVIDENCE: OFFLINE_ONLY.
* mmap/ioctl/write/fcntl/debug: 22 vendor ioctls scanned (ge2d, dvb_*,
  osd, amstream_*, amvenc, mmc, mtd, gdc...), zero tainted spills in
  window; all program hardware (side effects unacceptable for a
  stamper). No survivor. EVIDENCE: OFFLINE_ONLY.
* Shared thread objects: occ/altocc waiters live on OTHER stacks, never
  referenced by W->pi_blocked_on; second waiter cannot substitute the
  reference (alt_only hardware negative control). EVIDENCE:
  HARDWARE_REPRODUCED (fidelity) + OFFLINE_ONLY (code paths).

Answer to "exists a second primitive already present": NO, none found
that writes 8 bytes with H16 dest (and value) control.
EVIDENCE: OFFLINE_ONLY (scan+review); HARDWARE probe NOT RUN (no
candidate to probe).

## 8. PI-path Composition

All GhostLock-induced writes examined (waiter/lock/owner/pi_state/task/
hash bucket), especially `owner+0x28` and RMWs:

* `0x4e44 trylock [x20,#0x00]`: dest = H16 VALUE (lock heap). Cannot
  write H16 itself (it consumes it). Fixed heap addr.
* `0x4f54/0x4f60 waiter+0x40/+0x48`: dests ARE W stack but offsets are
  +0x40/+0x48, never +0x38; values are task->prio/deadline, never
  `&f_alt`. No off-by-8 path exists in binary. Cannot be redirected:
  immediates are encoded in the instruction.
* `0x4f64 enqueue -> lock+0x08/+0x10`: dests are heap f_target waiters,
  value `&W_waiter`. Wrong memory (heap vs W stack).
* `0x4fac owner+0x28 INC`: base `x19+0x28` where `x19` = O task_struct
  (heap), value +1 fixed (`ldxr/add/stxr`). To hit `[W_waiter,#0x38]`
  would need O == W_waiter-stack AND 0x28 == 0x38: both false by type
  (task_struct vs rt_mutex_waiter) and by binary (base traces to
  `ldr x19,[x20,#0x18]` owner load, not to W stack). Dataflow PROVES no.
* `0x4fc8 owner+0x7d4 pi_lock`: same base, fixed off, cmpxchg.
* Hash-bucket / pi_state / task stores: `task->pi_blocked_on` (0x52b8,
  C task only), `current->pi_blocked_on = NULL` (0x5454, current only),
  dequeue `str x19,[x19]` / `str x0,[x20,#0x10]` (tree self/leftmost,
  fixed). None takes H16 as dest.

Verdict: no natural PI write can be redirected to the H16 slot.
Proved in dataflow (bases/values fixed above), discarded.
EVIDENCE: OFFLINE_ONLY.

## 9. Async/Alias Analysis

* Overlap (FASE7): reuse/alias/`container_of`/union/wrapper examined.
  W FWRQ frame alive (W never returns; hrtimer is the only exit; main
  does not need W back). No second writer maps that stack. occ/altocc
  waiters are separate stacks, separate `waiter->lock` values
  (`&f_target` / `&f_alt`), never aliased into W->pi_blocked_on (the bug
  preserves exactly W_waiter). `rt_mutex_enqueue_pi/dequeue_pi` operate
  on pi_waiters trees, never store `waiter->lock`. No legitimate alias
  turns an existing write into an H16 write. EVIDENCE: OFFLINE_ONLY +
  HARDWARE_REPRODUCED (alt_only fidelity: f_alt ignored).
* Async (FASE8): signal (`complete_signal` target is siginfo),
  timers/hrtimer/task_work/completion/workqueue (targets are pool/work/
  timer structs), interrupt context, futex wake/requeue helpers
  (`futex_wake` refuses PI, `futex_requeue` copies keys, never stores
  `waiter->lock`), `sched_setscheduler` path only READS (H16.12, schedA
  rc=0 silent). Question "does any callback receive/derive a waiter
  pointer": NO writer found; the only waiter-pointer receivers are
  readers. No artificial race introduced (no pointer chain shown).
  EVIDENCE: OFFLINE_ONLY (binary+source) + HARDWARE_OBSERVED (schedA
  silent, prior round).

## 10. Hardware Probe

FASE2 safe observability design (no corruption yet). New harness mode
`h16_static` (mode 22): same arming as alt_only (occ_n=0, f_alt held +
1 parked waiter, W/O/C trio + trigger + in-window), but the consumer
does TWO sequential timed LOCK_PI(f_chain) probes on the SAME live
frame (first via g_lock1, second repeats g_lock1; `g_second == 2`).
Both TIMEOUT_BLOCK ~3000ms proves: (1) W_waiter alive, (2) slot did not
change naturally, (3) consumer still reads the field after the window.
Commands (one boot, same pad):

```
adb push ghostlock_chain /data/local/tmp/
adb shell /data/local/tmp/ghostlock_chain 0x0 B h16_static
# expect: P4 ALT_ARMED a_armed=1 alt_parked=1, P5 DONE errno=110 ~3000ms,
#   P5b second DONE errno=110 ~3000ms, P6 TIMEOUT_BLOCK
adb shell /data/local/tmp/ghostlock_chain 0x0 B alt_only   # control
adb shell /data/local/tmp/ghostlock_chain 0x0 B alt_tgt    # control
```

Status: NOT RUN this round (offline phase only; no adb in this
session). Desired result `H16 STATIC DURING WINDOW =
HARDWARE_REPRODUCED` is therefore INCONCLUSIVE (pending). Prior
adjacent evidence: alt_only 2x TIMEOUT + alt_tgt 1x EDEADLK already show
the slot is stable enough to decide deterministically, but the explicit
double-probe has not executed. No dangerous target used; both probes
are legitimate timed LOCK_PI on f_chain. EVIDENCE: INCONCLUSIVE
(harness ready, hardware pending).

Candidate-write minimal test (FASE10, gated on finding a candidate):
none to run, because FASE3-8 found zero plausible candidates. The
protocol when one appears: (1) write to a SAFE legitimate kernel target
with observable effect first, then (2) `[W_waiter+0x38] -> &f_alt`.
No crash-target probing. Status: NOT APPLICABLE (no candidate).
EVIDENCE: INCONCLUSIVE by design.

## 11. Exact H16 Write

Decisive test design (not executed, no candidate):

* CASE A `waiter->lock = &f_target.pi_mutex`: EDEADLK_CYCLE 0ms
  (natural, already HARDWARE_REPRODUCED as occ_tgt/alt_tgt).
* CASE B `waiter->lock = &f_alt.pi_mutex`: expect behavior of f_alt
  natural state (sec.12 signature; with occ_n=0 + f_alt occupied the
  natural analog is alt_only TIMEOUT, but under retarget the walk
  consumes f_alt's leftmost/owner instead — the exact verdict depends
  on f_alt occupancy armed for the run; pre-register occupancy before
  claiming).
* CASE CONTROL no corruption: `&f_target` (same as A).

Only the H16 word differs between A and B. Status: NOT EXECUTED.
EVIDENCE: INCONCLUSIVE. Prior: CASE A HARDWARE_REPRODUCED;
CASE B HARDWARE_REFUTED naturally (impossible without corruption).

## 12. Retarget Signature

Pre-register (both legitimate, opposite states where possible):

* f_target: owner O (blocked on f_chain), occupancy variable occ_n
  (0 = empty/leftmost NULL, >=1 = occ waiter prio 120).
* f_alt: owner A (spinning holder, never blocks), exactly 1 parked
  waiter altocc (prio 120, `waiter->lock=&f_alt`), owner/leftmost/uaddr
  all differ from f_target. `alt_base` (consumer f_alt timed) TIMEOUT
  proves valid+contended. EVIDENCE: HARDWARE_REPRODUCED (prior round).

If H16 -> f_alt, downstream must be coherent with f_alt (different owner
consumed at 0x4f9c, different top waiter at 0x508c/0x5094, different
branch at 0x5098/0x4f10, EDEADLK-vs-TIMEOUT tied to f_alt occupancy, not
timing alone). Timing alone is NOT accepted. Status: signature defined,
never observed (no retarget). EVIDENCE: INCONCLUSIVE.

## 13. Reproducibility

Zero H16 writes demonstrated. Counts: natural-writer scan 1/1, narrowed
#0x38 scan 7/7 classified, spill 87+22 reviewed, PI RMWs 6/6 fixed,
hardware H16 probes 0 new this round (prior: occ_tgt 7x total, occ2 3x,
trg_inwin 2x, alt_tgt 1x, alt_only 2x, alt_base 1x — all stable, zero
panic). Dest/size/prev/new/value-origin/insn/thread/reproductions for
an 8-byte write: NOTHING TO RECORD (no write). Target claim `8-byte
write = HARDWARE_REPRODUCED`: NOT MET. EVIDENCE: INCONCLUSIVE (offline
negative, hardware pending only for the safe static probe).

## 14. Security Impact

Unchanged from prior reports: GhostLock gives a deterministic stale
`task->pi_blocked_on` + FULL_CHAINWALK consumer + first heap RMW
(trylock) + owner INC/pi_lock + leftmost gate, all on NATURAL addresses
with balanced effects. Without H16 control there is no attacker-chosen
address, no arbitrary R/W, no cred/fops path, no privilege escalation.
The stale pointer is a real bug (wrong-task clear in remove_waiter) but
today it only walks between two legitimate heap mutexes. Do not cite
this round as a write primitive. EVIDENCE: HARDWARE_REPRODUCED (walk
fidelity) + OFFLINE_ONLY (impact scope).

## 15. What Is Proven

* `[W_waiter+0x38]` birth/store/read/window/gate exact (H16.0/H16.4/H16.7
  + full xref set). EVIDENCE: OFFLINE_ONLY (verify 30/30; `--h16-write`
  live scan).
* Exactly one natural writer (birth `stp @0x527c`, rtmutex.c:998); zero
  post-creation natural writers. EVIDENCE: OFFLINE_ONLY.
* `waiter->lock = &f_alt.pi_mutex` is HARDWARE_REFUTED as a natural
  change (alt_only ignores f_alt). EVIDENCE: HARDWARE_REPRODUCED
  (prior round fidelity).
* Full 8B-store census + narrowed #0x38 scan (3384 / 202 / 7) with every
  PI-adjacent hit classified KERNEL_ONLY/small-int. EVIDENCE:
  OFFLINE_ONLY.
* No PI-path write redirectable to H16 (owner+0x28 INC, enqueue,
  waiter+0x40/+0x48, trylock all fixed). EVIDENCE: OFFLINE_ONLY.
* No alias/async writer to the live W frame. EVIDENCE: OFFLINE_ONLY +
  HARDWARE_OBSERVED (schedA silent).
* No second primitive with H16 dest+value control in the repo surface.
  EVIDENCE: OFFLINE_ONLY (review); hardware probe pending only for the
  safe static test.
* Harness ready: `h16_static` double-probe + `--h16-write` surface tool.
  EVIDENCE: OFFLINE_ONLY (compiled: `gcc -fsyntax-only` clean,
  `py_compile` clean, `--h16-write` runs).

## 16. What Is Not Proven

* Slot alive/static on stock THIS round (`h16_static` not run):
  INCONCLUSIVE (pending; adjacent fidelity HARDWARE_REPRODUCED).
* Any targeted 8-byte write, H16 or otherwise: INCONCLUSIVE (none
  found, none attempted). Not a silent negative: the searched surface
  is listed in sec.4-5.
* Arbitrary R/W, cred, root, fops, code exec: not attempted,
  INCONCLUSIVE by design (explicitly out of scope until H16 moves).
* Absolute stock VAs/KASLR slide, vendor hunks for these structs:
  OFFLINE_ONLY / INCONCLUSIVE as before. Old lab stack geometry stays
  closed (not reopened).
* f_alt downstream signature under the walk (walk never consumed f_alt):
  INCONCLUSIVE.

## 17. Next Bottleneck

Exactly one: a durable 8-byte write primitive to the live W FWRQ slot
`[waiter,#0x38]` stable across H16.4 AND H16.7 while the frame is alive,
carrying `&f_alt.pi_mutex` (heap address, must be learned). Minimum spec
for the missing primitive: size 8B (single word; wider risks frame),
dest = live W stack slot (stock addr unknown, same-thread SP0-relative;
learn via safe probe, not lab constant), value = `&f_alt.pi_mutex`
(learn via heap disclosure, not guess), window = between trigger return
and consumer walk, stable across BOTH stale reads (0x52fc x25 AND 0x4df0
cmp @0x4df4), consumer = `FUTEX_LOCK_PI(f_chain)` FULL, mechanism = any
existing path with dest+value control (none found; new vuln or new
alias/async chain required). Do NOT build fake objects, do NOT chase
generic R/W, do NOT touch cred: solve only this word, then rerun
alt_tgt-vs-alt_only as L0-vs-L1. If the analysis holds:

* `H16 CONTROL: HARDWARE_REFUTED NATURALLY` (this round re-confirms),
* `SECOND WRITE PRIMITIVE: NOT FOUND` (this round),
* next step is the safe `h16_static` double-probe on stock (FASE2),
  then a fresh primitive search OUTSIDE the surfaces closed here
  (new syscall family, new driver, or heap-disclosure + stack-disclosure
  first — do not repeat the spill window as-is).

---
BOTTOM LINE (5-10 lines, per spec):

* Natural writer beyond birth: none (1 birth store, 0 post-creation).
* Second primitive already present: none found (3384/202/7 scanned, 87+22 spill reviewed, PI/async/alias closed).
* H16 dest controllable: no (0 DIRECT/USER_DERIVED candidates at SP0-0x278 with 64b ptr).
* Value &f_alt controllable: no carrier (all values ints/32b/kernel-fixed; heap addr never in a store).
* Strongest candidate: none (nearest amstream misses 0x20 + hw side effects, rejected).
* Tested on stock: no new H16 probe this round (harness ready, pending); prior fidelity alt_only/alt_tgt stands.
* H16 changed on hardware: no (never attempted, no candidate).
* Retarget to f_alt reproduced: no (HARDWARE_REFUTED naturally, INCONCLUSIVE as corruption).
* Targeted-only vs general: neither demonstrated (only natural walk fidelity).
* Single next bottleneck: durable 8B `[W_waiter+0x38]=&f_alt` stable across H16.4+H16.7; first run `h16_static` double-probe.
