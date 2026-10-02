# ghostlock h16 targeted write — stock-relative stack rewrite search

> DIRECTION (2026-10-02, see `reports/CURRENT_STATE.md`): principal is
> post-free stack reuse + disclosure; H16 live retarget is secondary;
> reclaim without verifier, audited live H16 writer search, fake object,
> arbitrary R/W, cred/root are closed. Post-free reuse is not demonstrated
> on Aquaman. Live-retarget was audited and not demonstrated.

Date: 2026-10-01. Authority: Xiaomi Mi TV Stick 1080p (aquaman, S805Y/GXL,
Android 9, PI.2055, 4.9.113 arm64). Lab instruments: build-aq/vmlinux +
.src/linux-amlogic + full disassembly cache. No fake, no arbitrary R/W,
no cred/root in scope. Single target: 8 bytes `[W_waiter+0x38]`.

Tools: `tools/ghostlock_h16_search.py` (new this round, stock-relative,
H16-centered, kernel-pointer-first) + `tools/ghostlock_deref_chain.py
--h16/--h16-write/--pi-source` (unchanged semantics, header notes
LAB != STOCK) + `tools/ghostlock_chain.c` (header-only delta, binary
rebuilt, P0-P8 unchanged, modes unchanged).

Prior spill result (`0 DIRECT/USER_DERIVED` at SP0-0x278) is RETIRED as a
closing claim: it used lab geometry. It is kept as a lab data point only.
This round re-searches stock-relative.

## 1. Objective

Demonstrate `[W_waiter+0x38] = address of another legitimate rt_mutex`
(first prize `&f_alt.pi_mutex`, any second legitimate rt_mutex accepted
as first address-control proof), with the rest of the GhostLock path
intact. Targeted stack rewrite first, general primitive only after.
EVIDENCE labels per claim below.

## 2. Stock Stack Model

Lab geometry (OFFLINE_ONLY, build-aq/vmlinux, verified): SyS_futex 0x70 +
do_futex 0x120 + futex_wait_requeue_pi.constprop.8 0x1a0; rt_waiter at
x29+0x80 = SP0-0x2b0; waiter->lock = SP0-0x278; size 0x50.
Stock conjecture for this round: rt_waiter = SP0-0x2c8,
waiter->lock = SP0-0x290 (H16_REL=0x290, 0x18 deeper than lab).
STOCK GEOMETRY = INCONCLUSIVE (no stock frame dump exists; KASLR slides
VAs, config shifts frames).

What IS stock-proven about the frame path (HARDWARE_REPRODUCED this
round, see sec. 9): same task, same kernel stack page, same SP base
across FWRQ and the next syscall. `pollA` stock log (pad 0x0, fwrq 2s):

```
P4 STAMP_POLL mode=pollA pad=0 sp_futex=0x7d91da6b80 sp_poll=0x7d91da6b80
dist=0 waiter_est=0x7d91da68d0 page_off=0x28d0 ev=0x4141 key=0x4159
```

dist=0 means the SP the kernel sees at FWRQ entry equals the SP at poll
entry on the same thread. Page reuse holds. Absolute waiter offset still
unknown, so only the relative relation `W_waiter+0x38` inside one page is
claimed. EVIDENCE: HARDWARE_OBSERVED (SP equality) + OFFLINE_ONLY (lab
frames) + INCONCLUSIVE (stock absolute offsets).

FWRQ frame lifetime: W never returns in-window (hrtimer is the only
exit; `fwake_errno=22` = futex_wake refuses PI). In `h16_static` the
frame stays alive across two 3 s probes. In stamp modes W returns after
`g_fwrq_sec` and the bytes persist on the page until the same thread's
next syscall overwrites them. Safe reuse region is therefore defined
relatively (H16+-0x40), never absolutely. EVIDENCE: HARDWARE_REPRODUCED
(alive) + OFFLINE_ONLY (layout).

## 3. H16 Lifetime

Birth `H16.0 0xffffff800910527c stp x20,x19,[x21,#0x30]` in
task_blocks_on_rt_mutex (rtmutex.c:997-998); `[x21,#0x38]=lock=x19`.
One store in kernel/locking+futex.c (`waiter->lock =` grep = 1 hit).
In-window readers `H16.4 0x52fc ldr x25,[x0,#0x38]` (next_lock as x3)
and `H16.7 0x4df0 ldr x0,[x28,#0x38]` + `cmp x20,x0 @0x4df4 / b.ne out`
(first value branch). Both read the same stack slot; stability across
both is required. Consumer still reads the field after the window
(H16.10/H16.11/H16.12). Size 8 bytes, dest `[W_waiter+0x38]`, live during
H16.4->H16.7, consumed by the FULL chainwalk. EVIDENCE: OFFLINE_ONLY.
Natural immutability after birth stands (not reopened).

## 4. Targeted Stack Search

New tool `tools/ghostlock_h16_search.py` (this round). Method: full-binary
single disassembly; frame from first sub/stp; intra-function forward
taint with kernel sources (x0-x5 USER at entry; `mrs` current/task,
`adrp/adr` code, heap loads, allocator/helper returns, stack-address
`add x29/sp` as KERNEL_POINTER; masking/shift kills pointer nature;
`bl` snapshots x0-x7 and re-taints x0 by return class); call graph via
direct `bl`, BFS depth 3 from every SyS_ root (303); dest normalized to
SP0-relative `dest_rel = SP0 - sumF + local_off`, `delta = dest_rel -
H16_REL`; stp counts as two 8 B words; copy/memcpy sites recorded
separately. Window H16+-0x40 listed; HIT only if 8 B and delta==0.
Default H16_REL=0x290 (stock conjecture); `--lab` selects 0x278 for
comparison. Counts (OFFLINE_ONLY):

* stock window (0x290): 411 8 B stores in H16+-0x40; 154 KERNEL_POINTER,
  29 USER_POINTER, rest INTEGER/KERNEL_DERIVED/UNKNOWN.
* lab window (0x278, comparison): 513 8 B stores; 197 KERNEL_POINTER,
  35 USER_POINTER.
* exact delta 0, 8 B, stock window: 9 KERNEL_POINTER, 0 USER_POINTER,
  2 INTEGER, 1 KERNEL_DERIVED_INTEGER, 21 UNKNOWN (mostly `str x19,[sp,#0x10]`
  callee-saved spills in tiny leaves, value unknown, deep/heavy paths).

Old `0 DIRECT/USER_DERIVED` is therefore restated stock-relative as:
0 USER_POINTER at exact delta 0 (this tool, this window). The old claim
is not reused as proof; the numbers above replace it. EVIDENCE:
OFFLINE_ONLY.

## 5. Destination Dataflow

Every candidate reports function, syscall root, frame size, store VA,
instruction, dest offset, dest relative to FWRQ frame (delta + waiter_off
= 0x38+delta), bytes, source reg, source origin/detail, lifetime note,
side-effect tags. Example (lab-relative, stock INCONCLUSIVE):

```
[KERNEL_POINTER delta+8 w=8] do_sys_poll 0xffffff8009230bd0:
str x0,[x29,#0x1b8] -> SP0-0x298 (sumF=0x450) origin=KERNEL_CURRENT
(mrs SP_EL0) path SyS_poll>do_sys_poll se=USER_COPY/IO
```

Dest coverage: table base (poll_wqueues at x29+0x1a0 = SP0-0x2b0 lab)
overlaps the lab waiter exactly; under the stock conjecture it sits
+0x20 into the table. Copy_from_user entries (stack_pps x29+0xa0, max
240 B) miss H16 by design (lab 4 B structural; stock-conjecture gap
~0x24 above entries top). No candidate is accepted on destination alone;
value must also fit (sec. 6). EVIDENCE: OFFLINE_ONLY.

## 6. Kernel Pointer Carrier Search

Value classes per store (FASE 4): KERNEL_POINTER > USER_POINTER >
UNKNOWN > KERNEL_DERIVED_INTEGER > INTEGER. Priority is KERNEL_POINTER
so no heap leak is needed. Sources treated as KERNEL_POINTER:
pi_state->pi_mutex (LEA +0x10 sites), rt_mutex *, task_struct *,
sock/file/filp, futex_pi_state *, waiter *, current (mrs SP_EL0), helper
returns (alloc/get/find/lookup/attach), heap loads, stack addresses,
code addresses. Truncated/masked derivations fall to
KERNEL_DERIVED_INTEGER/INTEGER even with a pointer base; `str Wn` is
never a pointer.

Result: 154 KPTR 8 B spills in the stock window lab-relative, but every
exact-delta-0 KPTR sits in a heavy/privileged/error path (sec. 8). No
exact KPTR in a fast graph-safe syscall. The question "does a syscall
copy an already-existing kernel pointer onto H16" is therefore answered
NO for the audited surface (BFS depth 3, all SyS_ roots, 8 B, delta 0).
Deeper-than-3 or indirect-dispatch (f_op) paths outside the scan are not
claimed covered. EVIDENCE: OFFLINE_ONLY.

## 7. rt_mutex Pointer Sources

`&f_alt.pi_mutex` exists and is valid on stock (holder A + 1 parked
waiter; alt_base TIMEOUT proves contended-valid). EVIDENCE:
HARDWARE_REPRODUCED (history + this round ALT_ARMED lines).

Carrier scan (`--rtmutex`, OFFLINE_ONLY): pi_state+0x10 LEAs verified at
`attach_to_pi_owner 0x9614`, `futex_requeue 0xabe4`,
`futex_lock_pi 0xb1b8/0xb238/0xb2a0`, `wait_requeue_pi
0xb574/0xb58c/0xb628/0xb6d0/0xb7cc` (add xN,xM,#0x10). Forward-spill
check in the same bodies: attach/task_blocks/start_proxy/init_proxy
have ZERO KERNEL_POINTER stack spills of the LEA reg;
futex_requeue/futex_lock_pi spill only code addresses (adr) and current
(mrs), never the `+0x10` lock reg to their own stack. So no
`rt_mutex * -> reg -> str/stp -> stack` chain exists inside the PI path
itself that a second syscall could borrow. Composition
`f_alt -> PI helper -> live reg -> stamper spill -> H16` has no binary
support: the lock reg dies in registers/epilogue, never lands on a
reusable stack slot. EVIDENCE: OFFLINE_ONLY.

## 8. Frame-Reuse Candidates

Ranked by FASE 10 (same task, same page, near H16, KPTR source, low side
effects, fast, graph-safe). Exact-delta-0 KPTR hits (lab-relative,
H16_REL=0x290), each rejected for stamper use:

* kobject_add x2 (`SyS_finit_module/init_module>load_module>...`, adr/heap):
  privileged module load, CAP_SYS_MODULE shell lacks, heavy. REJECT.
* get_page_from_freelist x3 (`SyS_io_setup/mincore>...alloc_pages...`,
  heap): MM allocator, sleeps, takes zone locks, heavy. REJECT (x3: same).
* congestion_wait x4 (`...>congestion_wait`, current): MM sleep path,
  schedules, heavy. REJECT.
* __slab_free x2 (`SyS_reboot>do_exit>kfree>...`, heap): process-exit path,
  destructive. REJECT.
* printk x4 (`SyS_renameat2>...>__audit_inode>printk`, heap): audit/error
  formatting path, prints, value is audit struct field, not steerable.
  REJECT.
* __vmalloc_node_range `[sp]` (`SyS_select>core_sys_select>vmalloc>...`,
  `ldr x2,[x20,#0x38]` heap): verified by hand at 0x1fa39c (`str x2,[sp]`
  sets up a RECURSIVE call arg; `ldr x2,[x20,#0x38] @0x1fa394` before it).
  Rare large-allocation recursion only, allocates+sleeps, value is a vmap
  internal word, slot is a transient call-arg overwritten before return.
  Nearest exact-delta KPTR with hand-verified dataflow, still REJECT as
  stamper (wrong value type + heavy + transient lifetime).
  EVIDENCE: OFFLINE_ONLY (hand disassembly above).

No USER_POINTER at exact delta 0 (0 hits): userspace-literal
`&f_alt.pi_mutex` cannot be placed without a leak, and no leak is
invented. VALUE ACQUISITION via userspace literal = NEXT PROBLEM (not
pursued; kernel-carrier path preferred and also empty). EVIDENCE:
OFFLINE_ONLY.

Principal candidate selected (geometry probe ONLY, not a retarget
stamper): do_sys_poll table/current spills (`0xbb8 stp table init`,
`0xbd0 str x0,[x29,#0x1b8] current`, delta +0x20/+8 lab, KERNEL_POINTER,
path SyS_poll>do_sys_poll, se=USER_COPY/IO, timeout 0, nfds<=30
stack-only, no alloc/sleep, graph untouched). Reason: only exact-overlap
family in a fast unprivileged graph-safe syscall; value is NOT rt_mutex
(current/task_struct *), so it must never be thrown at H16 for retarget;
its use is to measure stock geometry (sec. 9-10). EVIDENCE: OFFLINE_ONLY
for dataflow; HARDWARE_OBSERVED for safety (prior pollA/B/schedA silent,
zero panic).

## 9. Candidate Selection

ONE principal: STAMP_POLL geometry probe (above). Not a retarget
primitive. Everything else is explicitly not selected (heavy MM/slub,
module, exit/panic, audit-printk, vmalloc recursion, compat-msg 32 b,
cmsg kernel-fixed, BPF privileged, vendor ioctl hardware side effects).
No matrix of dozens is run. EVIDENCE: OFFLINE_ONLY (selection rationale).

## 10. Isolated Stock Probe

Before any GhostLock+stamp: page-reuse probe on stock (no corruption).
`pollA` with fwrq 2 s on stock this round: sp_futex == sp_poll (dist 0,
sec. 2) proves the waiter thread's next syscall reuses the same stack
page/SP base. P4 also carries the lab waiter estimate for reference
only (NOT a stock offset). No H16 write was provoked by this probe
beyond the poll table's natural stores, which already ran in prior
pollA/B (HANG, zero panic). No safe observable beyond SP equality +
HANG-vs-fault exists without the chainwalk, so geometry beyond page
reuse stays INCONCLUSIVE. EVIDENCE: HARDWARE_OBSERVED (dist 0 + HANG,
zero panic, zero reboot).

## 11. GhostLock Integration

Not executed with a stamper (no value-carrier exists). Baseline
`h16_static` re-ran first on stock this round (FASE 0, sec. 13). The
P0-P7 ghost+stamp protocol (P0 READY, P1 FWRQ, P2 EDEADLK, P3
GRAPH_PRESERVED, P4 CANDIDATE_STAMP, P5 LOCK_PI(f_chain), P6 RESULT, P7
CLASSIFICATION) is defined but gated on finding a carrier; running it
with `current` or a small-int as the stamp value would not test
`f_alt` retarget and risks a garbage trylock, so it was deliberately not
run. No FUPI, no owner join, no thread teardown introduced.
EVIDENCE: INCONCLUSIVE (by design, no candidate to integrate).

## 12. H16 Write Evidence

No 8-byte H16 write demonstrated on stock. Dest/size/prev/new/value-
origin/insn/thread/reproductions: nothing to record. The only exact-
delta KPTR HIT (`__vmalloc_node_range [sp]`) was hand-verified as a
transient recursion arg with the wrong value type and a heavy path, not
a durable H16 write. Poll table/current spills are near (delta +8/+20
lab) and already exercised naturally with no effect. EVIDENCE:
INCONCLUSIVE (no write) + OFFLINE_ONLY (rejection dataflow).

## 13. Retarget Signature

Pre-registered (unchanged): f_target owner O + occupancy occ_n; f_alt
owner A + 1 parked waiter; alt_base TIMEOUT proves f_alt valid. Under
H16->f_alt the walk must consume f_alt's owner/leftmost/has_waiters and
return EDEADLK-vs-TIMEOUT tied to f_alt occupancy, never timing alone.
Never observed (no retarget). Natural fidelity stands: alt_tgt follows
f_target (EDEADLK), alt_only ignores f_alt (TIMEOUT). EVIDENCE:
HARDWARE_REPRODUCED (fidelity) + INCONCLUSIVE (f_alt downstream under
walk).

## 14. Reproducibility

* `h16_static` (occ_n=0 + f_alt held+occupied, 2x timed LOCK_PI(f_chain)
  on the same live frame): P5 3000 ms/110 + P5b 3000 ms/110,
  P6 TIMEOUT_BLOCK, this round again (3rd overall counting history 2x).
  Commands: `adb push ghostlock_chain /data/local/tmp/`,
  `adb shell /data/local/tmp/ghostlock_chain 0x0 B h16_static`.
  EVIDENCE: HARDWARE_REPRODUCED.
* `pollA` geometry (pad 0x0, fwrq 2 s): P4 dist 0, P6 HANG_IN_WALK, zero
  fake writes, zero panic. Command:
  `adb shell /data/local/tmp/ghostlock_chain 0x0 B pollA 200000 x 2`.
  EVIDENCE: HARDWARE_OBSERVED.
* Offline: `--verify` 4/4 OK; `--all` stock 411/154/29 and lab 513/197/35;
  exact-delta-0 9/0/2/1/21 per class; `--rtmutex` LEAs + zero spills;
  `__vmalloc_node_range` hand check at 0x1fa394/0x1fa39c. EVIDENCE:
  OFFLINE_ONLY.

## 15. What Is Proven

* H16 birth/readers/window/gate exact (H16.0/H16.4/H16.7 + xrefs).
  EVIDENCE: OFFLINE_ONLY.
* Exactly one natural writer (birth); natural retarget HARDWARE_REFUTED;
  source control NATURALLY IMPOSSIBLE (structure). Not reopened.
  EVIDENCE: OFFLINE_ONLY + HARDWARE_REPRODUCED (fidelity).
* Stock page/SP reuse across FWRQ->poll on the same task (dist 0).
  EVIDENCE: HARDWARE_OBSERVED.
* H16 slot static across the window on stock (`h16_static` 3rd run).
  EVIDENCE: HARDWARE_REPRODUCED.
* Stock-relative 8 B census + per-class exact-delta counts with every
  exact KPTR hand-rejected; zero rt_mutex carriers; zero USER_POINTER at
  delta 0. EVIDENCE: OFFLINE_ONLY.
* Prior lab-window closing claim retired (LAB != STOCK). EVIDENCE:
  OFFLINE_ONLY (method note).
* No second primitive with H16 dest+rt_mutex-value control in the
  audited surface. EVIDENCE: OFFLINE_ONLY (scan+review, depth<=3).

## 16. What Is Not Proven

* Stock absolute waiter/lock offsets (0x2c8/0x290 is a conjecture).
  EVIDENCE: INCONCLUSIVE.
* Any durable 8-byte H16 write, targeted or general. EVIDENCE:
  INCONCLUSIVE (none found, none attempted).
* f_alt downstream signature under the walk. EVIDENCE: INCONCLUSIVE.
* Arbitrary R/W, cred, root, fops, code exec: out of scope until H16
  moves. EVIDENCE: INCONCLUSIVE by design.
* Paths deeper than BFS 3 or indirect f_op dispatch outside the scan.
  EVIDENCE: INCONCLUSIVE (explicitly not claimed covered).
* Stock VAs/KASLR slide, vendor hunks for these structs. EVIDENCE:
  OFFLINE_ONLY / INCONCLUSIVE as before.

## 17. Next Bottleneck

Exactly one: a durable 8-byte write to the live W FWRQ slot
`[waiter,#0x38]` (stock address unknown, H16_REL=0x290 conjecture only)
stable across H16.4 AND H16.7 while the frame/page is alive, carrying a
learned `&f_alt.pi_mutex`. Minimum spec: size 8 B single word; dest =
live W stack slot (learn via safe SP/dist probe, not lab constant);
value = `&f_alt.pi_mutex` (heap disclosure first, not guess); window =
trigger return to consumer walk; consumer = FUTEX_LOCK_PI(f_chain) FULL;
mechanism = any existing path with dest+value control (none found in
audited surface; new syscall family, new driver, heap+stack disclosure,
or stack-address-derived destination needed — do not repeat the same
window as-is). If the analysis holds:

* `H16 CONTROL: HARDWARE_REFUTED NATURALLY`,
* `H16 SOURCE CONTROL: NATURALLY IMPOSSIBLE (OFFLINE_ONLY structure)`,
* `TARGETED STACK REWRITE = NOT FOUND (audited surface)`,
* next step is stock disclosure (stack+heap addresses) before any new
  stamp attempt, then rerun alt_tgt-vs-alt_only as L0-vs-L1.

---
BOTTOM LINE:

* stock-relative H16? conjecture SP0-0x290 (waiter SP0-0x2c8), STOCK INCONCLUSIVE; page/SP reuse proven (dist 0).
* syscall/frame touching H16? 411 8 B in H16+-0x40 lab; 9 exact KPTR, all heavy/rejected; poll table/current (delta +8/+20) is the only clean geometry probe.
* kernel-pointer carrier? none usable (0 rt_mutex spills; exact KPTR are MM/module/exit/audit/vmalloc-recursion).
* legitimate rt_mutex * loadable as value? f_alt exists+valid, but no store carries it (VALUE ACQUISITION = NEXT PROBLEM).
* lowest-risk candidate? poll table/current for GEOMETRY ONLY, never for retarget.
* probe run on stock? yes: h16_static (TIMEOUT+TIMEOUT) + pollA (dist 0, HANG, no panic).
* H16 changed? no (never attempted, no carrier).
* f_alt downstream observed? no (fidelity only: walk follows f_target, ignores f_alt).
* targeted vs general? neither demonstrated (only natural walk fidelity).
* single next bottleneck? stock stack+heap disclosure, then a fresh dest+value path outside the closed surface.
