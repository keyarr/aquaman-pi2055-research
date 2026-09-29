# GhostLock port comparison (Phase 4 + Phase 5)

Matrix: Hazel 4.9 ARM32 (dorlow, hw-tested PS7716) x Aresin 4.14 ARM64
(NothingFumo, in progress, offsets TODO) x Aquaman 4.9 ARM64 (target).

Legend: identical / changed / non-existent / requires-adaptation.

## Trigger futex

- Hazel: waiter LOCK_PI(chain) + WAIT_REQUEUE_PI(wait->target chain),
  owner LOCK_PI(target)+LOCK_PI(chain), main CMP_REQUEUE_PI(wake=1).
  EDEADLK expected (errno 35 returned).
- Aresin: identical trio waiter/owner/consumer, identical syscalls.
- Aquaman: identical. The trio is version-independent; reusable.
  Status: identical.

## PI rollback / stack UAF

- Mechanism (remove_waiter with current during proxy rollback) is identical across
  all three versions: 4.9 and 4.14 share structurally identical vulnerable code.
- Difference: dangling object is rt_waiter on the waiter's stack across all three.
  What varies is the mechanism stamping the stack afterwards:
  Hazel uses setsockopt IPV6 MCAST_JOIN_SOURCE_GROUP; Aresin uses
  pselect/sched_setattr route + pipe; dnlid only validates EDEADLK.
- Aquaman: requires-adaptation. Consumer (sched_setattr nice) should
  behave identically (sched_setattr exists in 4.9), but the stack stamper
  requires local testing; waiter offset on the stack shifts depending on
  compiler/vendor.

## Address leak (mm kzhash / futex timing)

- Hazel: kernel address leak via futex hash timing (ks_measure +
  ks_solve_mm), assuming 16-byte futex key [mm,pad,addr,off] and
  mm_struct 0x1c0 in 8K slab. Code in hazel_reclaim.h.
- Aresin: slide.c with dedicated KASLR leak (physmap/data-only approach).
- Aquaman: requires-adaptation, high risk point. Futex hash and key format
  must be checked in 4.9 Amlogic (hazel's comment regarding "backported 16-byte
  futex key" is specific to FireOS kernel; upstream 4.9 already uses union futex_key
  with ptr+word+offset, but jmp_hash and shifts require confirmation). The 0x1c0
  grid DOES NOT apply on ARM64 (larger mm_struct). All ks_* requires recalibration
  with aquaman's actual slab/mm geometry.

## Allocator primitive / reclaim

- Hazel: AF_UNIX SOCK_STREAM socketpair + SO_SNDBUF 1MB + send 8K
  (full-page skb) reclaiming the mm slab page. Cross-cache
  mm_struct -> skb page.
- Aresin: pipe_buffer (pipe.c) + physmap write, alternative route.
- Aquaman: requires-adaptation. AF_UNIX exists (CONFIG_UNIX=y) and pipe
  exists, but geometry (slab size, objects per slab, freelist randomization —
  absent, good) must be measured on aquaman allocator. SLUB without
  FREELIST_RANDOM and without HARDENED favors deterministic reclaim.
  Do not assume socket reclaim behaves identically; pipe alternative is
  already precedented in aresin.

## Fake object (lock + fops in reclaimed page)

- Hazel: fake rt_mutex at page+0x100, fake waiter at +0x140, fake
  file_operations at +0x200 with read/write/ioctl/mmap/open/release
  pointing to real configfs_* and ashmem_*.
- Aquaman: requires complete offset adaptation. rt_mutex_waiter 4.9 ARM64
  has task at 0x30 (matching 4.14), but fake task fields (prio,
  pi_lock, pi_blocked_on) and fake fops layout depend on unmeasured offsets.
  Conceptual structure is reusable; numbers are not.

## Kernel read/write

- Hazel: configfs read/write via ashmem fd with crafted name
  (configfs_buffer page/pos/mutex), boundary-crossing fault trick on
  write (page = target-1, controlled EFAULT).
- Aresin: pipe physmap read/write (data-only route, without fake fops).
- Aquaman: configfs=y and ashmem=y compiled in (CONFIRMED in config), but
  runtime (mounted configfs, /dev/ashmem accessible to shell) = NOT PROVEN.
  ARM32 blob is DIRECTLY INCOMPATIBLE (mutex +0x18 -> +0x20 in LP64).
  If configfs/ashmem fail at runtime, aresin's pipe route is documented Plan B.

## Current task discovery

- Hazel: walks task list backward from INIT_TASK_TASKS comparing comm
  (prctl PR_GET_NAME), range check 0xc13/0xf00 ARM32.
- Aquaman: same technique applies, with ARM64 VA39 range
  (0xffffff8000000000+, KIMAGE base via KASLR) and 4.9 Amlinux tasks/comm offsets.
  Mechanical adaptation required.

## Cred patch

- Hazel: zeroes 0x20 at cred+4 (8 ids + securebits), verifies read.
- Aquaman: identical if DEBUG_CREDENTIALS is unset (confirm). Identical mechanics.

## SELinux handling

- Hazel: no bypass — Enforcing remains, daemon runs as
  u:r:shell:s0 with uid 0. uid 0 without new domain.
- Aresin: attempts setenforce/sid — in progress.
- Aquaman (ro.debuggable=0, Enforcing): expect the same ceiling as hazel:
  uid 0 in shell context. Sufficient for inspection (Phase 16). Do not presume
  SELinux bypass.

## Primary concrete difference preventing direct port (priority answer)

Hazel's forged blob cannot be transplanted directly: configfs_buffer.mutex at
+0x18 (ARM32) vs +0x20 (ARM64 LP64), mm_struct 0x1c0 vs unknown ARM64 size,
and all ARM32 pointers/anchors. Furthermore, the kzhash leak depends on
unmeasured slab geometry. Summary: trigger is reusable, but all downstream
elements require re-derivation with real offsets.
