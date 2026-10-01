# root path: reclaim + consumer + mali-stateful (offline round)

Date: 2026-10-01. Authority: stock Aquaman PI.2055 unless tagged otherwise.
Method: OFFLINE ONLY. Zero boots spent, zero device runs, no flash, no
persist, no cred/function-pointer/return/code touch. Lab binary
`build-aq/vmlinux` used for structure/offsets only; lab VAs are not stock
VAs. Prior refutations cited, not reopened (H16 retarget by poll/select,
futex hash timing oracle, fastboot boot unsigned, BL31 crypto bypass,
keyman arbitrary write, blind ioctl fuzz, fake rt_mutex/task before
reclaim, cred overwrite).

New artifacts this round: `tools/mm_reclaim_probe.c` (syntax-checked,
not run). No existing file modified.

## 0. Summary (factual)

- current confirmed chain: FUTEX_WAIT_REQUEUE_PI + FUTEX_CMP_REQUEUE_PI
  dispatch reachable unpriv (7/7) + rollback EDEADLK (5/5) on stock. Post
  state (victim task->pi_blocked_on dangling at stack rt_waiter) is
  DERIVED_STATICALLY from `.src/linux-amlogic` (rtmutex.c:1099-1111 clears
  `current` not `waiter->task`); never observed on device (no post-mortem:
  pstore denied, dmesg blocked).
- current blocker: no controlled reclaim demonstrated; no consumer walk
  proven to consume attacker bytes; no disclosure. Everything downstream
  of the dangling pointer is UNK on stock.
- reclaim status: mechanism DERIVED_STATICALLY (see sec 2), reliability
  NOT_PROVEN. Sentinel-in-MSG_PEEK is plumbing only, explicitly NOT
  slab-reuse proof (sec 2.5). Harness ready, 1 boot for full + same-boot
  control (sec 5).
- consumer status: FUTEX_LOCK_PI(f_chain) is the correct consumer
  (reaches stale via owner chain walk). pthread_setschedparam is the
  WRONG consumer for this bug (gated twice, usually walks nothing).
  Table sec 1. schedA silence (rc=0 HANG, ghostlock_chain.c:67-70)
  is explained, not anomalous.
- Mali stateful status: 34-command dispatch censused OFFLINE_ONLY from
  `out/vendor/modules/mali.ko` (corrects prior 31). All stateful
  handlers BOUNDED_COPY+VALIDATED or SCALAR/NO_EMIT with balanced
  alloc/free + get/put + open/close evidence. Zero OOB/UAF/KPTR/
  ARBITRARY_RW candidates proven. Every exploitability claim stays
  INCONCLUSIVE/LAB_ONLY by rule.
- strongest new primitive candidate: none proven. Strongest load-bearing
  UNK with a concrete closing experiment: order-2 paged-skb reclaim
  attempt rate (sec 5). No cred path mapped (correctly, per order A-G).
- exact next hardware experiment: run `mm_reclaim_probe control` then
  `full` on one boot, record P0-P8 + buddy deltas (sec 5). Expected
  0 reboots.

## 1. CONSUMER CORRECTNESS (task A)

All `pi_blocked_on` sites in `.src/linux-amlogic` (grep, kernel/ + include/):

- fork.c:1465 init NULL (fork, not a consumer).
- rtmutex-debug.c:61 WARN_ON (debug, no deref).
- rtmutex.c:423 `task_blocked_on_lock`, 468 comment, 548 chain walk [2],
  904/924 comments, 933/939 clear, 1007 set, 1020 check, 1110 buggy clear,
  1165 adjust_pi load.
- core.c:3765 WARN_ON (exit path), 4368 get_effective_prio (pi_waiters,
  NOT blocked_on), 4401 adjust_pi call.
- sched.h:1891 field decl, sched/rt.h:26 `task_has_pi_waiters` (pi_waiters).

Consumers that actually dereference the stale pointer (victim V, owner O):

| consumer | first stale dereference | fields read | fields written | required object shape | user-controlled inputs | expected observable effect | stock/lab status |
|---|---|---|---|---|---|---|---|
| chainwalk `rt_mutex_adjust_prio_chain` (rtmutex.c:548) via FUTEX_LOCK_PI on f_chain | [2] `waiter = task->pi_blocked_on` (V=owner W of f_chain); [4] `lock = waiter->lock` (+0x38); trylock `lock->wait_lock` (+0x00 RMW) | waiter ptr; +0x38 lock; +0x40 prio (exit gates 578/610); lock->{wait_lock,waiters,leftmost,owner} (+0x00/+0x08/+0x10/+0x18); owner->pi_lock/pi_waiters/pi_blocked_on | waiter->prio/deadline (+0x40/+0x48) at 723-724 under [L]; rb requeue on lock + owner pi tree; owner prio adjust | stale must be readable waiter (0x50) + lock must be mapped rt_mutex (0x20) with valid wait_lock; owner must be valid task or NULL terminator | f_chain/f_target occupancy (occ_n), consumer timeout (3s abs), stale bytes IF reclaim controls the frame | EDEADLK immediate = cycle W->O->W consumed stale; ETIMEDOUT ~3000ms = walk bailed/slept normal; panic = stale lock wild | DERIVED_STATICALLY (source + ghostlock_chain trig_t/base_t design). Stock walk outcome UNK (hang variants observed, cycle EDEADLK observed only with live occupancy, not with stale) |
| `rt_mutex_adjust_pi` (rtmutex.c:1157, via __sched_setscheduler pi=1, core.c:4401) | `waiter = task->pi_blocked_on` (1165); `waiter->prio` (+0x40) compare; `next_lock = waiter->lock` (+0x38) | waiter ptr; +0x40 prio; +0x38 lock; then full chainwalk surface above | none directly; passes task+next_lock to MIN_CHAINWALK | same as chainwalk but gated by prio inequality (1166) AND by __sched_setscheduler reaching 4401 at all | sched policy/prio/nice args; target tid; stale bytes IF reclaim controls frame | rc=0 fast + no walk = gate shut (most setschedparam calls); walk = only when prio actually changes AND waiter prio differs | DERIVED_STATICALLY. Stock: schedA rc=0 HANG = gate shut, NOT reach proof (sec 1.1). LAB_ONLY for walk reach |
| `task_blocked_on_lock` (rtmutex.c:421-423) inline helper | `p->pi_blocked_on->lock` (+0x38) | waiter ptr; +0x38 lock | none | readable waiter | none (called internally from 681/800/1027/1130) | no direct observable; gates chainwalk continuation (NULL ends walk) | DERIVED_STATICALLY |
| `rt_mutex_get_effective_prio` (rtmutex.c:349, via core.c:4368 + __setscheduler keep_boost) | NONE (does not touch pi_blocked_on; reads pi_waiters/leftmost->task->prio) | pi_waiters root (+0x7e0), leftmost (+0x7e8), waiter->task (+0x30 via +0x18), task->prio (+0x68) | none | N/A for stale blocked_on | sched args | fast return newprio when no pi_waiters; can NOT observe stale blocked_on by construction | DERIVED_STATICALLY. Old harness driving this path measured the wrong tree (hazel report sec 2.3 #3 stands) |
| exit/WARN paths (core.c:3765, rtmutex-debug.c:61) | WARN_ON(p->pi_blocked_on) boolean only | waiter ptr non-NULL test | none | N/A | process exit | warning/reboot only if reached with stale set; hold round already refuted exit as the observed actor | REFUTED as observed actor (hold.md:20-27, cited) |

### 1.1 Why pthread_setschedparam is the wrong consumer here

Two gates, both closed for the harness's actual args:

1. `__sched_setscheduler` early return (core.c:4295-4305): policy ==
   p->policy with same nice/prio returns 0 BEFORE `rt_mutex_adjust_pi`.
2. `rt_mutex_adjust_pi` early return (rtmutex.c:1166): `waiter->prio ==
   task->prio && !dl_prio` returns WITHOUT walk. Victim blocked at prio
   120 (OTHER/BATCH nice 0 share normal_prio 120); OTHER->BATCH nice 0
   does not change prio, so waiter (120) == task (120) -> no walk.

Hence `schedA: SETSCHED rc=0, still HANG, no panic` is the PREDICTED
outcome of a shut gate, not evidence for/against reach. The harness's
FUTEX_LOCK_PI timed consumer (base_t/trig_t/tgt_t/trg_tgt/trg_inwin/
occ_*/alt_*/h16_static) is the correct consumer: consumer blocks on
f_chain, owner W has the stale pi_blocked_on, chain walk step [2]
loads it. No new harness needed; do not rebuild the consumer.

Required object shape for the winning consumer: readable 0x50 waiter at
stale VA with +0x38 lock pointing at a mapped 0x20 rt_mutex; lock+0x00
must survive trylock RMW; lock+0x18 owner NULL ends walk cleanly
(VAR B terminator) or valid task continues. All other shapes risk panic
by construction; VAR B only until reclaim is proven.

## 2. HAZEL RECLAIM CHAIN, FUNCTION BY FUNCTION (task B)

Geometry premises (not re-derived; hazel report sec 3 stands):
sizeof 0x338, stride 0x340, order 2, 19/slab, 0x4000/slab, align 64,
offset 0, max_order 3, min_objects 16, dedicated `mm_struct` cache,
SLUB_DEBUG=n, FREELIST_RANDOM=n, HARDENED nonexistent in 4.9. All
LAB+CONF-config INFERRED for stock binary (sealed).

### 2.1 alloc_held_mm (/proc/pid/mem hold)

CODE PATH: fork -> child mm from `allocate_mm` = kmem_cache_alloc
(fork.c:752,875) -> parent `open(/proc/pid/mem)` -> `mem_open`
(base.c:821) -> `__mem_open(PTRACE_MODE_ATTACH)` (:810) ->
`proc_mem_open` (:790) -> `mm_access(ATTACH|FSCREDS)` (:796,
fork.c:1047: get_task_mm + ptrace_may_access) -> `atomic_inc(mm_count)`
(:801) + `mmput` (drops users ref, :803). Net: fd holds one mm_count,
memory unpinned. SIGKILL -> exit_mm -> mmput -> users 0 -> `__mmput`
(fork.c:900-919) -> `mmdrop`, but mm_count>=1 so slab object survives.
`close` -> `mem_release` (:917-922) -> `mmdrop` (sched.h:3059) ->
`__mmdrop` (fork.c:888-897) -> `free_mm` = kmem_cache_free (:753) ->
`__slab_free` (slub.c:2785).

Permission gate uid2000 same-uid: `__ptrace_may_access` (ptrace.c:268-
329): same-thread-group bypass (:290); else fsuid/fsgid vs target
uid/gid/euid/suid/egid/sgid all-equal -> ok (:309-315); dumpable
(:322-326); then `security_ptrace_access_check` (SELinux policy).
YAMA absent (no CONFIG_SECURITY_YAMA, DEFAULT_SECURITY=selinux), DAC
passes by construction for same-uid fork. Only SELinux self-access
rule is policy-dependent. Status: DERIVED_STATICALLY, 1 live open to
close (EACCES vs fd).

### 2.2 Shaping counts (18 -> 19 rescale)

Hazel: prep 576 (32*18), spray 162 (9*18), pre 17, post 18 + 1 leak.
Aquaman: prep 608 (32*19), spray 171 (9*19), pre 18, post 19 + 1 leak =
817 held mms (~43 slabs). LIFO freelist (no RANDOM), deterministic-ish.
Caveats DERIVED_STATICALLY: `CONFIG_SLUB_CPU_PARTIAL=y` parks freed
slabs on per-cpu partials (`put_cpu_partial`, slub.c:2211+; drain on
alloc/sched), so close storm needs settle/sched before pages hit buddy;
close ORDER affects LIFO position only, Hazel order transfers unchanged
(pre, leak, post, spray, prep). `min_partial = ilog2(832)/2 = 4`
(slub.c:3566); slab returns to buddy only when inuse==0 AND
nr_partial>=min_partial -> `discard_slab` (:1705) -> `__free_slab`
(:1639) -> `__free_pages(order 2)` (:1667).

### 2.3 Reclaim send (load-bearing, verified in source)

CODE PATH: `unix_stream_sendmsg` (af_unix.c:1846-1947) builds PAGED skb,
not one linear buffer: `size=min(len-sent,(sndbuf>>1)-64,
SKB_MAX_HEAD+32768)` (:1885-1888); `sock_alloc_send_pskb(...,
get_order(32768)=3)` (:1894-1896); `alloc_skb_with_frags`
(skbuff.c:4659-4723) tries largest fitting compound page first with
`__GFP_COMP|__GFP_NOWARN|__GFP_NORETRY`, NO direct reclaim (:4693-
4699), fallback order-0 + `alloc_page` (:4708). For 16384B payload:
header ~= SKB_MAX_HEAD, data_len = PAGE_ALIGN(size-header) -> npages 4
-> first attempt `alloc_pages(order 2)` = one contiguous 16K compound
page (the freed slab page IF buddy hands it back). On failure scatters
(2x order-1 / 4x order-0), no single slab reclaimed. Each socket = one
independent order-2 attempt. SO_SNDBUF 1MB: no cap check needs priv
(sock.c:706-718; only SNDBUFFORCE needs CAP_NET_ADMIN); clamps to
sysctl_wmem_max (~212992), still >>16384 so each send is one skb.
No priv check in sendmsg (only MSG_OOB/peer/state, af_unix.c:1864-
1879). MSG_PEEK=2 honored (af_unix.c:2173,2305,2420). All
DERIVED_STATICALLY.

### 2.4 ARM64 packing (arithmetic over LAB sizes)

task 0xdc0, waiter 0x50 (task 0x30, lock 0x38, prio 0x40), rt_mutex
0x20, fops 0xf0, configfs_buffer 0x60 mutex +0x20 (Hazel ARM32 +0x18
must be regenerated; hazel 5.3 stands). Pack: lock +0x0 (0x20),
waiter +0x100 (0x50), fops +0x200 (ends 0x2F0), task +0x300 (ends
0x10C0=4288). Raw 0xF20=3872, sentinel 0x3FFC disjoint. Fits 16384
with 12096 spare. DERIVED_STATICALLY.

### 2.5 Sentinel correction (was H6, now closed)

HYPOTHESIS: sentinel PASS proves reclaim.
CODE PATH: send bytes -> skb frags -> MSG_PEEK copies same bytes back.
EXACT EVIDENCE: skbuff.c:4693-4723 fallback (scattered pages still
deliver identical bytes); af_unix.c:2173 peek duplicates instead of
detaching.
REQUIRED USER ACTION: run probe, read P5 line.
EXPECTED: hits>0.
ACTUAL: not yet run (this round offline).
STATUS: REFUTED as stated (proves plumbing only). Reclaim proof needs
UAF read of reclaimed bytes or post-foothold
/sys/kernel/slab/mm_struct counters. Both probe modes (full/control)
are therefore EXPECTED to PASS on PEEK even with zero slab reuse;
the control exists to demonstrate exactly that.

### 2.6 Verdict table (task: CONFIRMADAS STOCK / LAB / DERIVADAS / NAO PROVADAS)

| item | verdict |
|---|---|
| trigger dispatch + EDEADLK rollback | CONFIRMADA NO STOCK (7/7 + 5/5, cited logs) |
| waiter on FWRQ stack, q.rt_waiter points at it | CONFIRMADA APENAS NO LAB (DWARF+asm) |
| victim pi_blocked_on dangles post-EDEADLK | DERIVADA STATICAMENTE (rtmutex.c:1099-1111); NAO PROVADA no stock |
| mm 0x338/stride 0x340/order2/19/0x4000 | DERIVADA STATICAMENTE (closed derivation; stock binary sealed) |
| hash 4-word LP64, Hazel ks_hash not portable | DERIVADA STATICAMENTE + LAB (0xdeadbeff imm) |
| /proc/pid/mem hold same-uid | DERIVADA STATICAMENTE (SELinux self-rule needs 1 live open) |
| counts 608/171/18/19, free->buddy, 16K send attempt-first | DERIVADA STATICAMENTE (mechanism); per-attempt success NAO PROVADA |
| SO_SNDBUF/16K/PEEK unpriv | DERIVADA STATICAMENTE |
| sentinel PASS = reclaim | REFUTADA como prova (plumbing only) |
| fake pack 4288 fits 16384 | DERIVADA STATICAMENTE |
| any UAF read / reclaim / disclosure on stock | NAO PROVADA |

## 3. VENDOR STATEFUL: MALI + AMLOGIC (second line)

Method: OFFLINE_ONLY disasm of `out/vendor/modules/mali.ko` (utgard,
single /dev/mali 10:48 OPEN_OK). Prior read-only GET/QUERY verdict
stands (SCALAR_ONLY, 3 probed HARDWARE_REPRODUCED, rest OFFLINE_ONLY-
negative). This round audited STATEFUL only. Full 34-handler census
(corrects prior 31; extra entries are per-core GET variants +
vsync/suspend/disable split).

Stateful handlers (opcode dir/size | wrapper copy | inner | class):

- mem_alloc 0xc0288300 RW40: cf40 + ukk_allocate (align 0xfff tst, size
  checks, struct_create+backend). BOUNDED_COPY_IN/SCALAR_OUT.
- mem_free 0xc0108301 RW16: cf16 + ukk_free (session+0x1b0 lookup, type
  1/3 check). free CONFIRMED; double-free REFUTED at check level.
- mem_bind 0xc0288302 RW40: cf40 + ukk_bind (flags 0x3f00, dma_buf vs
  block) -> dma_buf_get + IS_ERR + size cmp + attach/map. BOUNDED.
- mem_unbind 0xc0108303 RW16: lookup+type -> unmap/detach/put + backend
  destroy; get/put paired. BOUNDED, lifetime balanced.
- mem_cow 0xc0288304 RW40 / cow_range 0xc0188305 RW24 / resize
  0xc0188306 RW24: cf + ukk, access_ok + ukk checks. BOUNDED.
- write_safe 0xc020830a RW32: cf32 + 4x overflow guards (adds/csel/sbcs
  + b.hs fails) + _osk_mem_write_safe. BOUNDED_VALIDATED, OOB REFUTED
  at guard level.
- dump_mmu 0xc0388308 RW56: cf56 + overflow guard + size cap (sub/cmp
  0x7fffff b.hi) + valloc + ukk_dump + copy_to table + copy_to hdr56 +
  vfree. Contents PHYS/GPU, cursor USER_ECHO. BOUNDED/PHYS, KVA
  REFUTED; size-mismatch OOB INCONCLUSIVE (needs ukk_dump fill audit).
- wait_notif 0xc0688202 RW104: no cf, ukk (queue_receive+memcpy+delete,
  only u32 type stored) + copy_to104. SCALAR_ONLY+ZERO_PAD. Blocks.
- post_notif 0xc0108204 RW16: ukk_post only. NO_EMIT.
- gp_start 0xc0688500 RW104 / pp_start 0xc1988400 RW408 / pp_and_gp
  0xc0188404 RW24: no wrapper copy (ukk does get_user), job_create +
  tracker_add. JOB_ALLOC, NO_EMIT, LAB_ONLY.
- soft_start 0xc030820b RW48: cf48 + fence_copy + job_create/start/
  destroy (error paths destroy). JOB_ALLOC, NO_EMIT.
- soft_signal 0xc010820c RW16 / timeline_* (create_fence 0xc020820a
  RW32 cf16+sync_create+put fd; wait 0xc0208209 RW32 cf16+fence_wait;
  latest 0xc0108208 RW16 user-load+cmp+get_latest+put u32):
  BOUNDED/SCALAR, FD=INDEX.
- dma_buf_size 0x80108309 R16: cf16 + dma_buf_get + IS_ERR + scalar
  size ldr->str + put on both paths. SCALAR_ONLY, get/put BALANCED.
- W_ONLY (no emit semantic): gp_suspend 0x40188503 W24, pp_disable_wb
  0x40188403 W24, req_high_prio 0x40088207 W8, vsync 0x40108700 W16.
- mmap mali_mmap: pgoff 32-bit shift truncation NOTE (lsl w21,#12) but
  gated by session+0x1b0 lookup + id/type dispatch + per-type cpu_map
  + vma flags + alloc_ref. Mapping GATED_BY_LOOKUP; bypass
  INCONCLUSIVE/LAB_ONLY.
- session: open malloc(512)+list_init, stores sess->[file+0xd0];
  release -> close (abort_session, sched/exec/soft abort, wq_flush,
  timeline abort/destroy, memory_session_end, pagedir unmap/free,
  osk_free). Open/close BALANCED; no sess ptr copied out. UAF
  across close/race INCONCLUSIVE/LAB_ONLY.
- compat_ioctl: no sym in mali.ko (mali_ioctl only); 32/64 mismatch
  INCONCLUSIVE.

Other Amlogic KOs (nm ioctl/mmap): stream_input 8, vpu 3, encoder 3,
dmx 3, rtl8821cs 2, w1 1. Prior stock census: shell-openable =
binder/hwbinder/ashmem/ion/mali/xt_qtaguid only; ge2d/ionvideo/
amvideo/vfm DENIED. amstream/vpu/encoder nodes not in openable set.
Status: UNREACHABLE for uid2000 per existing census; promoting any
needs a fresh open probe. INCONCLUSIVE/LAB_ONLY, not audited deeper
(no user pointer stored/lifetime chain without openability).

Classification summary: every stateful Mali handler examined =
SCALAR, USER_ECHO, BOUNDED_COPY (+VALIDATED where guards found), or
PHYS/GPU. Zero KERNEL_POINTER / OOB_READ / OOB_WRITE / UAF /
ARBITRARY_RW_CANDIDATE proven. No HYPOTHESIS block promoted above
INCONCLUSIVE/LAB_ONLY; none claimed as primitive (rule: memcpy alone
is not exploitability).

## 4. NAO CONFUNDIR "PODE TER" COM "TEM" (hypothesis log this round)

HYPOTHESIS: FUTEX_LOCK_PI(f_chain) consumes the stale waiter.
CODE PATH: futex_lock_pi (futex.c:2545) -> rt_mutex_timed_futex_lock ->
task_blocks_on (consumer) -> chain walk from owner W ->
adjust_prio_chain[2] waiter=W->pi_blocked_on (rtmutex.c:548).
EXACT EVIDENCE: source chain above; ghostlock_chain trig_t/base_t
design; occ/alt matrices (TIMEOUT vs EDEADLK on live occupancy).
REQUIRED USER ACTION: run timed consumer in-window (g_inwin=1).
EXPECTED SIGNAL: EDEADLK immediate (cycle) vs ETIMEDOUT ~3000ms.
ACTUAL RESULT: not run this round (offline); prior live hangs are
for nostamp/poll/sched variants, trig_t EDEADLK-vs-TIMEOUT split not
yet isolated for stale-vs-live.
STATUS: INCONCLUSIVE.

HYPOTHESIS: pthread_setschedparam proves/controls stale reach.
CODE PATH: setscheduler -> get_effective_prio (pi_waiters, 4368) ->
__setscheduler -> adjust_pi (4401) -> chainwalk (548).
EXACT EVIDENCE: gates core.c:4295-4305 + rtmutex.c:1166 (sec 1.1).
REQUIRED USER ACTION: setschedparam OTHER->BATCH nice 0 on waiter.
EXPECTED: rc=0 fast, no walk (gate shut).
ACTUAL: schedA rc=0 HANG matches prediction (prior log).
STATUS: REFUTED as consumer (measures wrong tree / shut gate).

HYPOTHESIS: 16K unix send reclaims freed order-2 slab page.
CODE PATH: af_unix.c:1846-1947 + skbuff.c:4659-4723 (sec 2.3).
EXACT EVIDENCE: attempt-first order-2 with NOWARN/NORETRY fallback.
REQUIRED USER ACTION: run mm_reclaim_probe full + control (sec 5).
EXPECTED: PEEK hits>0 both modes (plumbing); buddy order-2 delta
recorded raw.
ACTUAL: not run (offline).
STATUS: INCONCLUSIVE.

HYPOTHESIS: Mali stateful handler yields UAF/OOB/ptr primitive.
CODE PATH: per-handler list sec 3 (wrappers + ukk + mmap + session).
EXACT EVIDENCE: bounded copies, guards, balanced get/put + open/close;
no 64-bit KVA store into out-buf; no stored user pointer deref chain.
REQUIRED USER ACTION: none (no fuzz; needs full data chain first).
EXPECTED: none claimed.
ACTUAL: none observed offline.
STATUS: INCONCLUSIVE (LAB_ONLY negative, not a hardware claim for
unprobed blocking paths).

## 5. NEXT HARDWARE EXPERIMENT (exact, minimal)

Binary: `tools/mm_reclaim_probe.c` (new, syntax-checked, static NDK
build). No futex, no UAF, no cred/fptr/code, no persist/flash/eMMC.

Steps (ONE boot, two execs, no power-cycle expected):
1. `adb push mm_reclaim_probe /data/local/tmp/`
2. `adb shell /data/local/tmp/mm_reclaim_probe control` (sockets only).
3. `adb shell /data/local/tmp/mm_reclaim_probe full` (817 holds + 512 pairs).
4. Optionally `... smoke` first if fd pressure is a concern.

Boots: 1. Power-cycle: no. Control: control exec is the control
(same binary, same boot). Record: full P0-P8 stdout + exit code +
errno lines + buddy before/after deltas.

PASS: hits>0 in P5 (plumbing works; both modes expected PASS).
FAIL: hits==0 (send path or harness broken; reclaim question
untouched). BUDDY: raw lines only, no gate.

Crash classification: none expected (no kernel pointer exists here).
Any reboot = FAIL + record phase line (P0/P1/P2/P3), not success.

What this unlocks: plumbing green -> next round adds the UAF read
(trig_t timed consumer against shaped+sprayed slabs, VAR B
terminator only, still no cred/fptr). Plumbing red -> fix send/harness
before any UAF work. No step skips to R/W or cred (order A-G kept).

Cost of NOT doing offline first (already paid): 0 boots this round.

## 6. Deliverable checklist

- [x] hazel chain re-derived func-by-func (sec 2) with
  CONFIRMADA-STOCK / LAB / DERIVADA / NAO-PROVADA + REFUTADA marks.
- [x] consumer table with first deref/reads/writes/shape/inputs/signal
  (sec 1), no subjective ranking; winner = FUTEX_LOCK_PI by mechanism,
  setschedparam refuted with gate evidence.
- [x] mali stateful census 34 handlers + mmap/session + amlogic reach
  (sec 3), all BOUNDED/SCALAR/NO_EMIT, zero primitives claimed.
- [x] minimal harness `tools/mm_reclaim_probe.c` (1 exec/boot,
  no cred/fptr/code/persist/flash/eMMC).
- [x] next experiment exact with boots/PASS/FAIL/control (sec 5).
- [x] no hardware log this round (offline by design); next round must
  attach raw P0-P8 logs or references.

## 7. Success criterion for this round

At least one of (a) mm reclaim HARDWARE_REPRODUCED, (b) vendor bug
HARDWARE_REPRODUCED with defined primitive, (c) UAF consumer
HARDWARE_REPRODUCED + first controllable field: NOT MET (offline
round by instruction: analysis before destructive exec). Delivered
instead: (i) consumer correctness closed statically (setschedparam
refuted, FUTEX_LOCK_PI selected with gate evidence), (ii) reclaim
mechanism closed statically with the attempt-first correction +
sentinel-as-plumbing refutation, (iii) mali stateful closed as
OFFLINE_ONLY-negative over 34 handlers, (iv) exact 1-boot experiment
that advances (a) without touching cred. Chain breaks exactly here:
per-attempt order-2 success rate + SELinux self-access rule + stale
reach on stock are the three UNKs, each with a named closing run.
