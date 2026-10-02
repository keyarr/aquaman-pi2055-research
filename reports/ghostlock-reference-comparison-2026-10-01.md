# ghostlock reference comparison 2026-10-01 — archaeology, no device run

> DIRECTION (2026-10-02, see `reports/CURRENT_STATE.md`): principal is
> post-free stack reuse + disclosure; H16 live retarget is secondary;
> reclaim without verifier, audited live H16 writer search, fake object,
> arbitrary R/W, cred/root are closed. Post-free reuse is not demonstrated
> on Aquaman. Live-retarget was audited and not demonstrated.

Date: 2026-10-01. Scope: comparative architecture only. No third-party
exploit executed, no payload copied, no offsets ported, no root/cred/RW
attempted, no fuzzing. All device claims below cite prior Aquaman reports
on BOOT_ID 3ec336a5; all reference claims cite public READMEs/writeups
plus raw-file confirmation where noted.

## 1. Scope

Question: is Aquaman hunting the wrong primitive, or missing a known stage
from other GhostLock ports?

Closed and not reopened: reclaim FAIL (mm-reclaim-probe-2026-10-01,
reclaim_hits=0), H16 direct live write NO_EXACT_WRITER_FOUND
(411 8B stores in window, 33 exact, 0 TARGET_RT_MUTEX producer),
stock disclosure NO_DISCLOSURE_FOUND (POINTER_BYTES_FOUND 0, 22 tests).

This round: locate Hazel + Fire TV + relevant family ports, reconstruct
each chain as trigger -> consumer -> stale object -> memory control ->
primitive -> final effect, compare dangling-object handling, map gaps,
list max 3 concrete hypotheses, single verdict.

## 2. References analyzed

| project | target device/kernel | arch | trigger | consumer | primitive | final stage | source |
|---|---|---|---|---|---|---|---|
| NebuSec IonStack canonical (CVE-2026-43499) | kernelCTF LTS 6.12.80 generic | x86_64 | FWRQ/FCRQ 3-futex PI cycle -> EDEADLK rollback via remove_waiter on wrong task | sched_setattr on waiter -> rt_mutex_adjust_prio_chain FULL walk | rb_erase single constrained pointer write into target slot, then CEA-resident fake table + short ROP DirtyMode (core_pattern mode flip) | world-writable core_pattern -> usermode root | nebusec.ai/research/ionstack-part-2 (full writeup) + CyberMeowfia poc/poc.c raw confirmed (waiter/owner/consumer trio, PR_SET_MM_MAP + setsockopt/pselect/keyctl stamp options, sched_setattr consumer) |
| dorlow hazel-cve-2026-43499 (Hazel) | Toshiba Fire TV hazel AFTHA004, PS7716.5665N hw-tested, Linux 4.9.113 | ARM32 | same FWRQ/FCRQ trio -> EDEADLK | PI chainwalk via sched path (same rtmutex walk family) | mm_struct cross-cache reclaim via AF_UNIX skb payload; fake rt_mutex/waiter/task/fops in reclaimed page; configfs read/write via ashmem fd | cred patch to uid 0, SELinux stays Enforcing, root daemon in shell context | github dorlow/hazel-cve-2026-43499 README + hazel_reclaim.h raw confirmed (ks_hash/ks_solve_mm futex-hash timing, alloc_held_mm via /proc/pid/mem, socketpair+send reclaim, MSG_PEEK finder) |
| R0rt1z2 GhostLock-5.10 (Fire TV karat/sunstone) | Fire Max 11 sunstone + Fire TV Stick 4K Max karat, Fire OS 8, 5.10 | ARM64 | same trio -> EDEADLK (inherited from CyberMeowfia via IonStackQuest3) | same PI walk family | dedicated slide.c KASLR leak + pipe_buffer reclaim path (MM_ORDER 3 class), per-target header | cred patch to root, OTA disable | github R0rt1z2/GhostLock-5.10 README (supported builds table, credits IonStackQuest3 first 5.10 port + CyberMeowfia upstream); code-level .c not audited this round, README-level confidence |
| yijiacloud GhostLock-OPPO-PCKM00 (family 4.14 reference) | OPPO PCKM00 OP4A57 SM6150, Android 11, 4.14.180-perf+ | ARM64 | same futex requeue-PI UAF -> EDEADLK | pselect fd_set stack reuse + sched_setattr walk | KASLR slide via boot_id path + ashmem fops overwrite -> legacy configfs read/write -> pipe_buffer physrw | task walk + cred patch + selinux permissive | github yijiacloud README + report.md (chain diagram, kallsyms method, 4.14 API deltas: legacy configfs read/write, selinux_state field) |
| cyberbalsa Shield mdarcy 9.2.4 (closest 4.9 kin) | NVIDIA Shield TV Pro 2019 mdarcy, 4.9.141-tegra, SE 9.2.4 | ARM64 | same vulnerable remove_waiter path confirmed on live machine code | same PI walk family | deterministic MCAST_BLOCK_SOURCE stack stamp + order-2 mm_struct reclaim with shaped skb + fake rt-mutex/task layout -> ashmem_misc.fops redirect to legacy 4.9 configfs handlers | bounded adbd cred write + selinux permissive, fops restored | github cyberbalsa README + PORT_STATUS.md (proven chain 1-7, exact task_struct layout noted as target-specific, pipe stage explicitly NOT used) |

Notes: Fire TV 5.10 entry is README-level (no raw .c audit this round).
All others confirmed at least to raw-file or full-writeup level. No code
copied into this workspace. No offsets reused; every port states layouts
are build-specific.

## 3. Exploit architecture comparison

Canonical shape shared by every reference:

```text
trigger (FWRQ/FCRQ 3-futex cycle -> EDEADLK)
 -> consumer (PI chainwalk: sched_setattr/sched_setscheduler or FUTEX_LOCK_PI,
    same rt_mutex_adjust_prio_chain walk)
 -> stale object (rt_mutex_waiter on waiter kernel stack, pi_blocked_on dangling)
 -> memory control (same-thread stack reuse AFTER frame return + kernel VA disclosure)
 -> primitive (one constrained write -> fake fops/table -> read/write or physrw)
 -> final effect (cred patch and/or selinux/mode flip)
```

Per-reference table (stage / implementation / required primitive /
Aquaman equivalent / status):

Canonical x86:

```text
trigger / FWRQ+FCRQ trio / 3 futexes + 3 roles / Aquaman identical / confirmed (LEVEL_2 history)
consumer / sched_setattr walk FULL / live waiter task / Aquaman FUTEX_LOCK_PI variant, same walk family / confirmed (differential EDEADLK vs TIMEOUT)
stale object / stack rt_mutex_waiter / dangling pi_blocked_on / Aquaman same type inferred statically / plausible (not observed as bytes)
memory control / PR_SET_MM_MAP auxv over freed frame (pselect/setsockopt/keyctl alternates in PoC) / post-free reuse + KASLR slide via prefetch / Aquaman none (H16 live-write hunt, NO_EXACT_WRITER_FOUND) / missing
disclosure / prefetch text+physmap leak -> CEA direct-map alias / timing side channel / Aquaman none (POINTER_BYTES_FOUND 0) / missing
reclaim / CEA + direct-map alias as known-address controlled page (no mm slab reclaim on this target) / known VA spray / Aquaman mm order-2 FAIL / missing-or-different (x86 does not use mm path)
primitive / rb_erase single pointer write into inet6 table slot, then handler hijack on loopback packet / constrained write + valid neighbours / Aquaman none / missing
final / DirtyMode core_pattern mode flip -> usermode root / short ROP / Aquaman none / missing
```

Hazel ARM32:

```text
trigger / same trio / same / confirmed
consumer / sched-family walk / same / confirmed family
stale object / stack rt_mutex_waiter / same / plausible
memory control / setsockopt MCAST stack stamp over freed frame / post-free reuse / Aquaman pselect attempts 6/6 reboots, MCAST overlap uncalculated / missing
disclosure / futex-hash timing (pile + measure + solve mm) / side channel + slab grid / Aquaman hash incompatible (3-word vs 4-word LP64) + timing refuted on A53 class / missing
reclaim / AF_UNIX SOCK_STREAM socketpair + full-page send reclaiming mm slab page / cross-cache + MSG_PEEK finder / Aquaman FAIL hits=0 / missing
primitive / fake lock/waiter/task/fops -> configfs read/write via ashmem fd / controlled page + valid kernel VAs / Aquaman ashmem/configfs present but dentry tolerance unverified, blob incompatible LP64 / missing
final / cred patch, Enforcing stays, shell-context root / bounded write / Aquaman none / missing
```

Fire TV 5.10 (karat/sunstone via Quest3 lineage):

```text
trigger / same trio / same / confirmed
consumer / same walk family / same / confirmed family
stale object / stack rt_mutex_waiter / same / plausible
memory control / stack reuse stamp family (Quest3 lineage) / post-free reuse / Aquaman none / missing
disclosure / dedicated slide/KASLR leak path / per-build leak / Aquaman none / missing
reclaim / pipe_buffer + physmap-oriented reclaim, order-3 class / spray to known page / Aquaman FAIL / missing
primitive / fake objects -> read/write route (per-target header) / controlled page / Aquaman none / missing
final / cred root + OTA disable / same class / Aquaman none / missing
```

OPPO 4.14:

```text
trigger / same UAF / same / confirmed
consumer / pselect fd_set reuse + sched_setattr walk / same / Aquaman consumer variant confirmed, stamper missing / partial
stale object / stack rt_mutex_waiter, compact task+0x30/lock+0x38 class / same type / plausible
memory control / pselect fd_set copy over freed frame / post-free reuse / Aquaman none / missing
disclosure / slide/boot_id + fops verification pass / leak before forge / Aquaman none / missing
reclaim / pipe_buffer physrw after fops stage / heap page control / Aquaman FAIL / missing
primitive / ashmem fops -> legacy configfs -> pipe physrw / staged escalation / Aquaman none / missing
final / cred + selinux + seccomp handling / same class / Aquaman none / missing
```

Shield 4.9 (nearest kin):

```text
trigger / live remove_waiter machine code still vulnerable / same / confirmed
consumer / same walk family / same / confirmed family
stale object / stack stale waiter at deterministic stamp displacement / same type / plausible
memory control / MCAST_BLOCK_SOURCE deterministic stamp / post-free reuse / Aquaman none / missing
disclosure / fixed-base/slide route with full-lock variant / leak before forge / Aquaman none / missing
reclaim / order-2 mm slab reclaim with shaped skb + mixed payload / cross-cache / Aquaman FAIL (same order class, zero hits) / missing
primitive / full disjoint fake layout -> ashmem fops -> legacy 4.9 configfs handlers, pipe stage NOT used / controlled page / Aquaman none / missing
final / bounded adbd cred write + permissive, restore fops / same class / Aquaman none / missing
```

## 4. Dangling object handling

Answer from code-confirmed sources (NebuSec writeup + poc.c waiter path,
hazel_reclaim.h waiter/slab handling, OPPO report chain, Shield proven
chain list):

In every port the dangling object is:

```text
rt_mutex_waiter on the waiter thread kernel stack (freed stack frame),
reachable via waiter task pi_blocked_on
```

Not task_struct, not heap waiter, not pi_state. pi_state/mm_struct appear
only as neighbouring/leveraged objects, never as the dangling pointer
itself.

How each port controls the bytes the consumer reads:

- Canonical: waiter returns to userspace, then same thread issues
  PR_SET_MM_MAP with attacker auxv; large aligned stack buffer lands over
  the freed frame. Alternates listed in PoC: setsockopt, pselect, keyctl,
  TCP getter, process_vm, timerfd, futex. Classification: OBJECT_REUSE
  (stack reuse after free). No cross-thread write to a live frame.
- Hazel: same-thread stack stamper (MCAST family per credits) over the
  freed frame, then separate mm-slab reclaim for the fake page.
  Classification: OBJECT_REUSE for the waiter + RECLAIM for the fake page.
- Fire TV 5.10 lineage: same stack-reuse family + dedicated leak +
  pipe-oriented reclaim. Classification: OBJECT_REUSE + RECLAIM.
- OPPO: pselect fd_set copy over the freed frame. Classification:
  OBJECT_REUSE.
- Shield: MCAST_BLOCK_SOURCE deterministic stamp over the freed frame.
  Classification: OBJECT_REUSE + RECLAIM (order-2 skb).

No port performs a direct 8-byte write to the live
[W_waiter+0x38] slot from another thread while the FWRQ frame is alive.
No port alters waiter->lock in place. All replace the whole object after
return. All require a kernel-VA disclosure before forging because
waiter->task, waiter->lock, and fake table pointers must be valid kernel
addresses.

Aquaman contrast: H16 hunt searches for an in-place live-slot writer
carrying a legitimate rt_mutex pointer. Binary census finds zero usable
carriers (heavy/privileged/transient only, PI +0x10 LEA register-only).
That mechanism has zero precedent in the references above.

## 5. Primitive gap analysis

YES only on evidence (device log or code-confirmed reference stage).

```text
primitive / Hazel / Fire TV 5.10 / Canonical x86 / OPPO 4.14 / Shield 4.9 / Aquaman
trigger (FWRQ/FCRQ -> EDEADLK) / YES / YES / YES / YES / YES / YES (5/5 EDEADLK history, LEVEL_2 matrix)
consumer (PI chainwalk reaches stale waiter) / YES / YES / YES / YES / YES / YES (FUTEX_LOCK_PI differential: occupied+stale=EDEADLK, else TIMEOUT)
stale object type identified (stack rt_mutex_waiter) / YES / YES / YES / YES / YES / YES (static inference only, no bytes)
post-free stack reuse stamp / YES / YES / YES / YES / YES / NO (pselect reboots, MCAST overlap open, H16 live-write NOT the same mechanism)
address disclosure (slide / mm / table VA as bytes) / YES / YES / YES / YES / YES / NO (POINTER_BYTES_FOUND 0, 22-test audit)
mm/heap reclaim with verifier / YES / YES / N/A (CEA alias instead) / YES / YES / NO (FAIL hits=0, plumbing-only)
controlled fake object consumed by walk / YES / YES / YES / YES / YES / NO
read/write or physrw primitive / YES / YES / YES / YES / YES / NO
cred/final effect / YES / YES / YES / YES / YES / NO
```

Reading: Aquaman matches the first three rows and misses every row after
the stale-object type. The break is sharp and identical across all
references.

## 6. Aquaman missing stage

Aquaman current (same BOOT_ID 3ec336a5 throughout):

```text
trigger / FWRQ/FCRQ trio / confirmed (EDEADLK 5/5, matrix base_t/occ_base/trg_inwin/occ_tgt/alt_only/alt_tgt)
consumer / FUTEX_LOCK_PI timed walk, FULL chainwalk / confirmed (U1 vs L0/L1/U0 + alt negatives, pos_cycle live control)
stale object / waiter_task pi_blocked_on -> stack rt_waiter slot / statically inferred, differential EDEADLK consistent / plausible, not byte-proven
memory control (post-free reuse stamp) / none / NO_EXACT_WRITER_FOUND, poll dist=0 proves page reuse only, no controlled bytes ever landed / missing
disclosure (W_waiter / waiter->lock value / slide as bytes) / none / NO_DISCLOSURE_FOUND on audited proc/sys/net/futex/vendor sample / missing
reclaim (order-2 slab capture with verifier) / none / FAIL reclaim_hits=0 in A/B/control, MSG_PEEK is plumbing-only / missing
controlled object / none / fidelity shows walk follows birth f_target, ignores f_alt / missing
primitive + final / none / out of scope until slot moves / missing
```

Direct answers to Phase 4:

- Do other ports alter waiter->lock in place while live? No. Zero cases.
- Do they substitute the pointed object? No; they keep the dangling slot
  address and replace the bytes after free.
- Do they control content after free? Yes. All of them. That is the stage.
- Do they use stack reclaim? Yes. Same-thread second syscall overlapping
  the freed frame in every port.
- Do they avoid direct write? Yes. The live-write path Aquaman hunts has
  no precedent; references bypass it by design.

So yes: Aquaman hunts the wrong instantiation of the memory-control
stage. The stage itself (controlled bytes under the consumer) is correct;
the mechanism (live 8-byte retarget to another legitimate lock) is not
used anywhere.

## 7. Candidate next bottlenecks

Max 3, each concrete, no spray/fuzz/offset-guess proposals.

1. hypothesis: post-free same-thread stack reuse is the only
   precedent-backed memory-control mechanism; H16 live retarget should be
   retired as the active hunt.
   evidence from reference: canonical PoC lists PR_SET_MM_MAP/pselect/
   setsockopt/keyctl as interchangeable reclaim syscalls fired AFTER the
   waiter returns; Hazel/OPPO/Shield all stamp after return, never live.
   Aquaman evidence: page/SP reuse proven (pollA dist=0), zero controlled
   bytes ever landed, H16 census empty of usable carriers.
   experiment needed: read-only geometry check of which second-syscall
   frame overlaps the freed waiter region on stock (no fake, no write,
   no consumer walk): compare candidate syscall frames for overlap only,
   then stop.
   risk: low (no corruption, no walk, no reboot expected beyond prior
   pselect history; do not combine with consumer until overlap proven).

2. hypothesis: read-only kernel-pointer disclosure is the earliest hard
   blocker; forging is impossible without it.
   evidence from reference: every port leaks before forging (prefetch/
   futex-hash/slide/boot_id/tracefs); fake task/lock/table pointers must
   be valid kernel VAs.
   Aquaman evidence: NO_DISCLOSURE_FOUND, POINTER_BYTES_FOUND 0; H16 value
   acquisition explicitly open (&f_alt.pi_mutex is itself a kernel heap
   address, not userspace-known).
   experiment needed: finish the shell-openable /dev emit census with
   source-audited copy_to_user field audit only (no blind ioctls), plus
   f_op/indirect dispatch beyond BFS depth 3 for EMIT only; stop at first
   address, then re-run disclosure ruler before any stamp thinking.
   risk: low (read-only opens + struct audit; no UAF/cred/SELinux).

3. hypothesis: order-2 slab capture needs a verifier-backed single
   experiment, not repeated blind spray.
   evidence from reference: Hazel/Shield shape mm cache via held-mm
   descriptors then verify capture per-socket (peek-style finder);
   plumbing success without verifier is explicitly not reclaim.
   Aquaman evidence: mm_reclaim_probe FAIL with 512/512 plumbing in all
   modes; sends_ok does not distinguish order-2 capture from scatter.
   experiment needed: one shaped hold/free/spray run whose ONLY pass
   criterion is a sentinel at the tail word of a 16 KiB unit; on
   hits=0 close as FAIL without redesign.
   risk: low-medium (allocator pressure only, no UAF walk, no cred).

## 8. Verdict

```text
SAME_ARCHITECTURE_GAP
```

Aquaman trigger, consumer family, and stale-object type match every
reference. The miss is a known shared stage, not a novel architecture:
post-free stack reuse + kernel-VA disclosure + verified reclaim +
controlled fake object. The H16 live-write hunt is the wrong
instantiation of the memory-control stage and should stop consuming
cycles. Disclosure is the earliest concrete gap; reuse geometry is the
second; verified reclaim is the third. No new front beyond these three.
