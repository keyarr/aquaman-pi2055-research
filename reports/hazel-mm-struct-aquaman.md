# hazel / mm_struct / aquaman: static feasibility gate

Date: 2026-09-29. Static analysis only. No device run, no reboot spent, no
repo file modified other than this report.

Scope: whether the Hazel chain
(`CVE-2026-43499 -> futex PI UAF -> reclaim mm_struct -> controlled kernel object
-> read/write`) is portable to `aquaman` (Xiaomi Mi TV Stick 1080p, S805Y/GXL,
4.9.113, arm64, PI.2055), and specifically what the `mm_struct` reclaim step
requires once the real allocator geometry is derived instead of assumed.

Primary evidence: `.src/linux-amlogic` (McMCCRU 3d4ab79e, ancestral), DWARF from
`build-aq/vmlinux`, `aquaman-config` (the device's own config), disassembly of
`build-aq/vmlinux`, and the public Hazel sources
(`dorlow/hazel-cve-2026-43499`: `hazel_root.c`, `hazel_reclaim.h`,
`profiles/hazel-PS7716.5665N-5665.conf`).

Every constant is classified:

| tag | meaning |
|---|---|
| `CONF` | confirmed on the Aquaman kernel (config or lab binary) |
| `LAB` | confirmed only in the lab build `build-aq` (ancestral tree, not stock) |
| `HAZEL` | specific to the Hazel target, not transferable |
| `UNK` | unknown, needs measurement |

---

## 0. Correction to a prior framing

An earlier framing in this investigation treated "2 pages" as a design target
inherited from Hazel (`MM_SLAB_SIZE = KS_PAGE * 2`). That was wrong in framing.
The page count is an **output** of the SLUB geometry, not a requirement. This
report derives the geometry from the code and reports whatever order results.

The `MM_OBJS 18` / `MM_OBJ_SIZE 0x1c0` numbers in `hazel_reclaim.h` are the
Hazel kernel's measured geometry, not a template. Section B derives the
Aquaman equivalents and shows they are different.

---

## 1. State of the Aquaman (what the repo already proves)

Reconstructed from the code and the logs, not from the prose summaries.

**Proven on device** (`reports/ghostlock-reachability.md:27-41`,
`out/logs/`, `reports/ghostlock-oracle-v2-*.md`):

1. `FUTEX_WAIT_REQUEUE_PI` and `FUTEX_CMP_REQUEUE_PI` dispatch is reachable from
   an unprivileged shell: 7/7 probe checks pass (`tools/ghostlock_reachability.c`).
2. The rollback path is reached: `CMP_REQUEUE_PI -> EDEADLK` (errno 35) in 5/5
   rounds (`tools/ghostlock_race_stats.c`), device healthy, no reboot.
3. `EDEADLK` is reproduced repeatedly in the oracle harness
   (`out/logs/oracle_v2_holdA_nostamp.log:2`, `oracle_v2_holdB_stamp0120.log:2`).
4. Runtime surfaces exist: `/dev/ashmem` is `crw-rw-rw-` and openable by shell;
   `configfs` is in `/proc/filesystems` and mounted rw
   (`reports/ghostlock-ashmem-configfs.md:11-17`).
5. `CONFIG_ARM64_SW_TTBR0_PAN` is **not set** (`aquaman-config:479`), with
   `CONFIG_ARM64_PAN=y` (485) and an A53 with no `pan`/`uas` features
   (`reports/ghostlock-oracle-v2-device.md:41`). Software PAN is off, so a
   user-space address is dereferenceable from kernel context. This is `CONF`.

**Not proven, and actively negative:**

6. The stack-stamp route is a dead end on hardware. 6 of 6 boots rebooted
   (`reports/ghostlock-oracle-v2-gate3.md:5-8`,
   `reports/ghostlock-oracle-v2-hold.md:9-12`). `f18_post` was never read once,
   in any trial, on any boot. The value oracle is `UNTESTED` since inception.
7. The old "PAD 0x180 hit" is **not** evidence of a working stamp.
   `out/logs/scan_pads.log:119-127` records the hit, but
   `reports/ghostlock-value-oracle.md:18-24` shows why it is a false positive:
   `stamp()` in that build allocated a fixed 4096-byte VLA and varied only the
   `memset` length, so the user SP was identical for every PAD and the
   `stack_fds` address never moved. The scan was a no-op by construction.
   `out/logs/rep_0x180.log` then shows 9/9 rep runs with "frame intocado".
   Reconciled: the 0x180 result is a stack-reuse lottery plus the known
   EDEADLK/timeout race, not a stamp hit. **No stamp byte was ever written
   on the device in any boot** (`ghostlock-oracle-v2-gate3.md:127-129`).
8. Reclaim has never been attempted against a controlled object.
   `tools/ghostlock_reclaim_try.c` exists but its log is absent from `out/logs/`
   (only `cal_probe_0x120.log`, `frame_reconcile*.log`, the oracle logs and
   `scan_*.log` are present). `reports/ghostlock-risk.md:26-27` still lists
   "reclaim + read-only validation" as PENDING.

**Structural finding, new here**: the ancestral source is *not* vanilla
4.9.113, but the delta does not touch the vulnerable path:

- `kernel/locking/rtmutex.c` vs `torvalds/v4.9`: 6 hunks, all DL-deadline or
  lockdep related. `remove_waiter()` at `rtmutex.c:1099-1111` still uses
  `current->pi_lock` / `current->pi_blocked_on`, the pre-patch pattern.
- `kernel/futex.c` vs `torvalds/v4.9`: 73 changed lines, all in
  `fixup_pi_state_owner`, `atomic_inc_not_zero` hardening, `futex_atomic_op_inuser`
  (4.9.110+ CVE-2016-5195 follow-up), and a `nr_wake < 0` check. The
  requeue-PI path is untouched.

So `CVE-2026-43499` is structurally present (`CONF` on the ancestral tree,
`UNK` for the stock 2022 binary, which is AMLSECU-encrypted and cannot be
disassembled, see `reports/ghostlock-kaslr-symbols.md:3-12`.

---

## 2. Part A: UAF state after `FWRQ -> CMP_REQUEUE_PI -> EDEADLK`

### 2.1 Where the dangling object is

`futex_wait_requeue_pi()` declares the waiter on the **kernel stack**:

- `.src/linux-amlogic/kernel/futex.c:2858`, `struct rt_mutex_waiter rt_waiter;`
  a plain local in the function frame.
- DWARF `DIE 0x00a9e1d8`, `DW_OP_fbreg -288`, CFA `x29+0x1a0`
  (`out/logs/frame_reconcile.log`), so the object sits at `x29+0x80` inside the
  `futex_wait_requeue_pi` frame. `LAB`.
- The `futex_q` local is in the same frame; `q.rt_waiter` is set from the same
  address: `stp x21, x22, [x29,#0x188]` at `0xffffff800913b4a8`
  (`out/logs/frame_reconcile.log`). `q` is at `x29+0x130`, and
  `q.rt_waiter` is at `+0x58` (`futex_q` layout, `dwarf_offsets.py` output:
  `rt_waiter 0x58`). So `x29+0x130+0x58 = x29+0x188`. Self-consistent.

`futex_q` offsets (`LAB`, from `python3 tools/dwarf_offsets.py build-aq/vmlinux`):
`list 0x00`, `task 0x28`, `lock_ptr 0x30`, `key 0x38`, `pi_state 0x50`,
`rt_waiter 0x58`, `requeue_pi_key 0x60`, `bitset 0x68`, size `0x70`.

`rt_mutex_waiter` (`LAB`, DWARF, no `CONFIG_DEBUG_RT_MUTEXES`):
size `0x50`, `tree_entry 0x00`, `pi_tree_entry 0x18`, `task 0x30`,
`lock 0x38`, `prio 0x40`, `deadline 0x48`.

### 2.2 The exact post-EDEADLK state

Chain, in the order the kernel executes it:

1. Waiter is blocked in `rt_mutex_start_proxy_lock(&pi_state->pi_mutex,
   &rt_waiter, current)` called from `futex_wait_requeue_pi`
   (`futex.c:1956-1958` in the requeue path, and the initial call site in
   `futex_wait_requeue_pi`). `task_blocks_on_rt_mutex` sets
   `waiter->task = task` (`rtmutex.c:997`), `waiter->lock = lock`
   (`rtmutex.c:998`), and `task->pi_blocked_on = waiter`
   (`rtmutex.c:1007`). The waiter is now enqueued in the target's
   `waiters` tree and in the owner's `pi_waiters` tree.
2. `main` calls `CMP_REQUEUE_PI` -> `futex_requeue(requeue_pi=1)`
   (`futex.c:3283-3284`) -> `rt_mutex_start_proxy_lock(&pi_state->pi_mutex,
   this->rt_waiter, this->task)` at `futex.c:1956-1958`.
   Note the arguments: `task` is `this->task` (**the victim**), while
   `current` is the requeuer.
3. `task_blocks_on_rt_mutex` enqueues the victim waiter again and calls
   `rt_mutex_adjust_prio_chain(owner, RT_MUTEX_FULL_CHAINWALK, lock,
   next_lock, waiter, task)`, which walks the chain and returns `-EDEADLK`.
4. `rt_mutex_start_proxy_lock` sees `ret != 0`, the lock still has an owner, so
   `ret` stays `-EDEADLK`, and it calls
   `remove_waiter(lock, waiter)` (`rtmutex.c:1718`).
5. `remove_waiter` (`rtmutex.c:1099-1111`) does the bug:

```c
raw_spin_lock(&current->pi_lock);        /* current == requeuer, NOT waiter->task */
rt_mutex_dequeue(lock, waiter);
current->pi_blocked_on = NULL;           /* clears the WRONG task */
raw_spin_unlock(&current->pi_lock);
```

6. Because `is_top_waiter` is true and an owner exists, it also runs
   `rt_mutex_dequeue_pi(owner, waiter)` (`rtmutex.c:1122`) and the tail
   `rt_mutex_adjust_prio_chain(owner, RT_MUTEX_MIN_CHAINWALK, lock, next_lock,
   NULL, current)` at `rtmutex.c:1147-1148`, again
   with `current` rather than `waiter->task`.

**Resulting state, precisely:**

- The victim's `rt_waiter` has been removed from `lock->waiters` and from
  `owner->pi_waiters`. The rbtree is *not* corrupt; both trees are clean.
- The victim's `task_struct->pi_blocked_on` is **still pointing at
  `&rt_waiter`**, the stack object. `remove_waiter` cleared the requeuer's
  field instead.
- The victim is still blocked in `rt_mutex_finish_proxy_lock` ->
  `__rt_mutex_slowlock` (`futex.c:2961`, `rtmutex.c:1774`), about to sleep on
  a node that no longer belongs to any tree.

This matches the fixed upstream form: the patch series
(`3bfdc63936dd` and siblings) changes `current` to `waiter_task` at exactly
these three sites.

### 2.3 What the victim holds, and the UAF window

The victim's `pi_blocked_on` is a pointer into its own kernel stack frame. Once
`futex_wait_requeue_pi` returns, that frame is dead stack. Any path that
dereferences `victim->pi_blocked_on` after the frame is gone is the UAF read.
Candidates in this tree:

- `task_blocked_on_lock()` -> `rtmutex.c:423`: `p->pi_blocked_on->lock`.
  Used by `remove_waiter` (`:1129`) and `task_blocks_on_rt_mutex` (`:1023`).
- `rt_mutex_adjust_prio_chain()` -> `rtmutex.c:548`: `waiter = task->pi_blocked_on;`
  then `waiter->lock`, `waiter->prio`, `waiter->task`.
- `rt_mutex_adjust_pi()` -> `rtmutex.c:1165`: `waiter = task->pi_blocked_on;`
  Reached from `__sched_setscheduler` at `core.c:4401` **when `pi` is true**.
- `rt_mutex_get_effective_prio()` -> `rtmutex.c:349-357`, inlined at
  `core.c:4368` and `core.c:4078`. This is the consumer path the repo's oracle
  targets. Assembly (`build-aq/vmlinux`, `rt_mutex_get_effective_prio` at
  `0xffffff8009105678`) reads exactly four things:

```asm
ffffff8009105694:  ldr  x0, [x19, #0x7e0]   /* task->pi_waiters     */
ffffff8009105698:  cbz  x0, +0x48           /* NULL -> fast return, frame untouched */
ffffff800910569c:  ldr  x0, [x19, #0x7e8]   /* task->pi_waiters_leftmost */
ffffff80091056a0:  ldr  x0, [x0, #0x18]     /* -> waiter->task  (pi_tree_entry+0x18) */
ffffff80091056a4:  ldr  w0, [x0, #0x68]     /* -> task->prio */
ffffff80091056a8:  cmp  w0, w20
ffffff80091056ac:  csel w0, w0, w20, le     /* min(prio, newprio) */
```

`LAB`. This confirms the repo's `out/logs/value_oracle.log` claim about the
read path, and it also confirms the **fast path**: if `task->pi_waiters` is
NULL the frame is never touched at all. That is the `cbz` at `+0x48`.

Important consequence for the oracle design: this walk goes through
`task->pi_waiters`, i.e. the **owner's** tree, not the victim's
`pi_blocked_on`. The dangling `pi_blocked_on` is reached by a *different*
consumer (`rt_mutex_adjust_pi` at `core.c:4401`, and the chain walk at
`rtmutex.c:548`). The repo's oracle conflates the two. That is a real
hypothesis-level error in the current tooling, independent of the stamp
question.

### 2.4 What was demonstrated vs inferred

| claim | status |
|---|---|
| dispatch reachable, 7/7 | `CONF` on device |
| rollback reached, `EDEADLK` 5/5 | `CONF` on device |
| the waiter is on the stack, `q.rt_waiter` points at it | `LAB` (DWARF+asm) |
| post-rollback the victim's `pi_blocked_on` dangles | `LAB` (code read), **not observed on device** |
| any later code dereferences the dead frame and crashes | `CONF` that reboots happen; **the specific actor is `UNK`** |
| a stamp can control the frame contents | `UNK` (never executed on device) |

The 6 reboots are real and reproducible, but no log identifies *which* path
faulted. `reports/ghostlock-oracle-v2-hold.md:20-27` correctly killed the
`exit_pi_state` hypothesis and showed the death happens before process
teardown. The remaining candidates (`rt_mutex_rebalance_locked` in the
background, the still-armed FWRQ `hrtimer_sleeper`, the owner thread's
unwind through the `f_chain` tree) were never separated. Nothing in the repo
distinguishes them.

---

## 3. Part B: `mm_struct` allocator geometry, derived

Following the requested chain, every step from code.

### 3.1 `sizeof(struct mm_struct)`

`0x338` = 824 bytes. From `python3 tools/dwarf_offsets.py build-aq/vmlinux`
(`LAB`). Present in the output alongside `total_vm 0xb0`, `task_size 0x30`,
`start_brk 0x108`, `env_end 0x138`.

Config dependencies of the struct, checked one by one against both configs:

| field guard | device | lab | affects size? |
|---|---|---|---|
| `CONFIG_AIO` (`ioctx_lock`, `ioctx_table`) | `y` | `y` | yes, both same |
| `CONFIG_MEMCG` (`owner`) | `n` | `n` | both same |
| `CONFIG_MMU_NOTIFIER` (`mmu_notifier_mm`) | absent | absent | both same |
| `CONFIG_TRANSPARENT_HUGEPAGE` (`pmd_huge_pte`) | `n` | `n` | both same |
| `CONFIG_CPUMASK_OFFSTACK` (`cpumask_allocation`) | absent | absent | both same |
| `CONFIG_NUMA_BALANCING` | absent | absent | both same |
| `CONFIG_ARCH_WANT_BATCHED_UNMAP_TLB_FLUSH` | absent | absent | both same |
| `CONFIG_HUGETLB_PAGE` (`hugetlb_usage`) | `n` | `n` | both same |
| `CONFIG_X86_INTEL_MPX` | absent | absent | both same |
| `CONFIG_PGTABLE_LEVELS > 2` (`nr_pmds`) | `3` | `3` | both same |

`CONFIG_MMU_NOTIFIER` is `bool` with no prompt (`mm/Kconfig:326-328`), selected
only by KVM and DRM; all are off, so it is absent from both `.config` files and
the field is excluded from both builds. Every guard that touches
`mm_struct`'s size agrees between the device config and the lab config.
**The lab-derived `0x338` is therefore consistent with the device config.**

`CONFIG_KSM` differs (`y` device, `n` lab) but KSM does not add a field to
`mm_struct`; it uses `mm->flags`. No size impact.

Status: `0x338` is `LAB`, and consistent with the device's own config. Whether
the stock 2022 Xiaomi tree kept the same `mm_types.h` is `UNK`: it is not
public and the boot image is sealed.

### 3.2 The real slot size is `0x340`, not `0x338`

`kernel/fork.c:2140`:

```c
mm_cachep = kmem_cache_create("mm_struct",
        sizeof(struct mm_struct), ARCH_MIN_MMSTRUCT_ALIGN,
        SLAB_HWCACHE_ALIGN|SLAB_PANIC|SLAB_NOTRACK|SLAB_ACCOUNT,
        NULL);
```

`ARCH_MIN_MMSTRUCT_ALIGN` is `0` on arm64 (`fork.c:2103-2105`:
`#ifndef ARCH_MIN_MMSTRUCT_ALIGN #define ARCH_MIN_MMSTRUCT_ALIGN 0`).

`calculate_alignment()` (`mm/slab_common.c:304-325`) with `SLAB_HWCACHE_ALIGN`:

```c
if (flags & SLAB_HWCACHE_ALIGN) {
        unsigned long ralign = cache_line_size();
        while (size <= ralign / 2)
                ralign /= 2;
        align = max(align, ralign);
}
```

`cache_line_size()` on arm64 (`arch/arm64/include/asm/cache.h:41-45`) returns
`4 << CTR_EL0.CWG` when the coprocessor reports it, else `L1_CACHE_BYTES`.
For an A53 the D-cache line is 64 B, so `CWG = 4` and `cache_line_size() = 64`.
`while (824 <= 32)` never runs, so `ralign` stays 64, `align = 64`.
`ARCH_SLAB_MINALIGN` on arm64 is 8, so no bump. Result: `align = 64`.

Then `mm/slub.c:3501-3502`:
`size = ALIGN(size, s->align); s->size = size;`
`ALIGN(0x338, 64) = 0x340` = 832.

**So the object stride is `0x340` (832 B), while `sizeof` is `0x338` (824 B).**
The 8-byte difference is the alignment tail. `s->object_size` keeps the
user-requested size, assigned in `create_cache` at `slab_common.c:341`, so it
stays `0x338`; `calculate_sizes` then overwrites only `s->size` (`slub.c:3502`)
to `0x340`. `s->inuse = 0x338` (`slub.c:3453`). `s->offset` and `s->reserved`
stay `0`: `create_cache` uses `kmem_cache_zalloc` (`slab_common.c:336`), and the
only writer of `s->offset` is the `SLAB_DESTROY_BY_RCU | SLAB_POISON | ctor`
block at `slub.c:3455-3467`, none of which applies to this cache.

`tools/ghostlock_target.h:227` records `GL_MM_SIZE 0x338`. The stride the
kernel actually walks is `0x340`, and the slab is order 2 with 19 objects
(derived in §3.3; a prior revision of this report said order 1 / 9 objects,
which was wrong — see §3.3 correction).

On the merge question, because a merged cache would break the whole grid:
`find_mergeable` (`mm/slab_common.c:253-297`) rejects every `kmalloc-*`
candidate for this cache. `size` is first `ALIGN(824, 64) = 832`, then
`if (size > s->size) continue;` (`slab_common.c:276`) rejects the smaller
caches (`kmalloc-512` and below), and
`if (s->size - size >= sizeof(void *)) continue;` (`slab_common.c:288`)
rejects the larger ones outright (`1024 - 832 = 192 >= 8` for
`kmalloc-1024`, more for the rest). Note the merge gate before those:
`SLAB_MERGE_SAME` (`slab_common.c:279`) passes for both sides here because
`SLAB_NOTRACK`/`SLAB_ACCOUNT` evaluate to `0` (`CONFIG_KMEMCHECK`/
`CONFIG_MEMCG` unset in `aquaman-config`), and the align check
(`slab_common.c:285`) also passes (`kmalloc-*` align is 64 on this tree via
`ARCH_KMALLOC_MINALIGN=ARCH_DMA_MINALIGN=64`, not 8 — a prior revision of
this report said 8, which was wrong). The size window is what rejects:
a merge needs an existing cache with `s->size` in `[832, 839]`, and none
exists. Non-kmalloc neighbours existing at `proc_caches_init()` time miss
it by hundreds of bytes (lab DWARF: `fs_cache` stride `0x40`, `files_cache`
`0x2c0`, `signal_cache` `0x440`, `task_struct` `0xdc0`; `sighand_cache` is
unmergeable via `SLAB_DESTROY_BY_RCU`+ctor; boot caches carry
`refcount=-1`). Had a merge happened, `__kmem_cache_alias`
(`slub.c:4208-4236`) would have adopted the older cache's geometry and name.
So `mm_struct` ends up in a dedicated cache named `mm_struct`. Residual
caveat: merging is only *attempted* because `slab_nomerge` is `0` by default
(`slab_common.c:47`), and it can be forced to 1 by a `slab_nomerge` kernel
command-line parameter (`slab_common.c:49-59`); the stock cmdline
(`boot.img` header) has none. A `slab_nomerge` on the device cmdline would
only make the cache *more* dedicated, not less, so this does not affect the
geometry.

### 3.3 Order and objects per slab

`calculate_order()` (`slub.c:3227-3276`):

```c
min_objects = slub_min_objects;                  /* 0: CONFIG_SLUB_MIN_OBJECTS unset */
if (!min_objects)
        min_objects = 4 * (fls(nr_cpu_ids) + 1);
max_objects = order_objects(slub_max_order, size, reserved);
min_objects = min(min_objects, max_objects);
```

- `slub_max_order = PAGE_ALLOC_COSTLY_ORDER` = 3 (`slub.c:3175`,
  `mmzone.h:36`, `Documentation/vm/slub.txt:120`), no
  `CONFIG_SLUB_MAX_ORDER` in 4.9. A prior revision of this report said 1;
  that was wrong (1 is neither the default nor present anywhere on this
  path) and everything derived from it (min_objects=9, order 1) was wrong
  with it. Overrides checked and absent: no `slub_max_order=` /
  `slub_min_objects=` / `slub_min_order=` / `slab_nomerge` / `maxcpus` on
  the stock cmdline (`boot.img` header:
  `androidboot.dtbo_idx=0 otg_device=1 buildvariant=user`);
  `debug_guardpage_minorder()` is 0 (`CONFIG_DEBUG_PAGEALLOC=n`,
  `aquaman-config:5250`); no vendor assignment to `slub_max_order` anywhere
  in the tree (only `mm/slub.c`; the Amlogic `MEMORY_EXTEND` hooks touch
  the `kmalloc_order` large path and `L1_CACHE_SHIFT`, not the order path).
- `slub_min_objects` is a boot/module param, `0` by default
  (`CONFIG_SLUB_MIN_OBJECTS` does not exist in 4.9; confirmed absent from both
  configs and from the Kconfig). Same for `slub_min_order` (= 0).
- `reserved = 0` (needs `SLAB_DESTROY_BY_RCU`; not set here).
- `nr_cpu_ids = 4` at `proc_caches_init()` time: `setup_nr_cpu_ids()` runs
  in `start_kernel` (`init/main.c:517`), long before `proc_caches_init()`
  (`init/main.c:642`); the runtime DTB (`artifacts/aquaman.dtb`) has 4 CPU
  nodes, so `nr_cpu_ids = find_last_bit(possible,8)+1 = 4`
  (`kernel/smp.c:541-544`). No `maxcpus=` to clamp it further.

Objects per slab at each order, with `size = 0x340`, and the waste gate
(`rem <= slab_size / fraction`, fraction tried as 16, then 8, then 4 —
note: the divisor is the fraction itself, not `100/(100-fraction)`; a prior
revision used the percentage form from newer kernels, which was wrong):

```
order 0:  4096 B ->  4 objects, 768 B leftover (18.8%; > 1/16 and > 1/8)
order 1:  8192 B ->  9 objects, 704 B leftover ( 8.6%; > 1/16, <= 1/8)
order 2: 16384 B -> 19 objects, 576 B leftover ( 3.5%; <= 1/16)
order 3: 32768 B -> 39 objects, 320 B leftover ( 1.0%; <= 1/16)
```

`min_objects = 4 * (fls(nr_cpu_ids) + 1)`, capped at
`max_objects = order_objects(slub_max_order, size, 0)`:

```
nr_cpu_ids=1 -> fls=1 -> min_objects=8   vs max(order 3)=39 -> 8
nr_cpu_ids=2..3 -> fls=2 -> min_objects=12 vs 39 -> 12
nr_cpu_ids=4..7 -> fls=3 -> min_objects=16 vs 39 -> 16
nr_cpu_ids=8 -> fls=4 -> min_objects=20 vs 39 -> 20
```

(`min_objects` is a floor that sets the start order, not the final object
count — see §3.6. A prior revision plugged `min(16, 9) = 9`, which only
holds under the refuted `max_order=1` premise.)

Then the loop tries `fraction = 16, 8, 4` and `slab_order()`
(`slub.c:3203-3225`):

```c
if (order_objects(min_order, size, reserved) > MAX_OBJS_PER_PAGE) ...
for (order = max(min_order, get_order(min_objects * size + reserved));
     order <= max_order; order++) {
        unsigned long slab_size = PAGE_SIZE << order;
        rem = (slab_size - reserved) % size;
        if (rem <= slab_size / fract_leftover) break;
}
```

Aquaman case (`nr_cpu_ids=4`, `min_objects=16`, `max_order=3`):
start at `get_order(16*832) = get_order(13312) = 2`.
`order 2`: `slab_size=16384`, `rem = 576`, fraction 16 gives
`576 <= 16384/16 = 1024` -> **break at the first fraction tried**.
=> **order 2, 19 objects per 16384-byte slab.** No fraction fallback, no
`min_objects` decrement loop (`while (min_objects > 1)` at `slub.c:3248`
is never reached).

Sensitivity (same code, other inputs):
- `nr_cpu_ids=1`, `min_objects=8`: start `get_order(6656)=1`; order 1:
  `704 > 8192/16=512`, no break; order 2: `576 <= 1024`, break -> order 2.
- `nr_cpu_ids=8`, `min_objects=20`: start `get_order(16640)=3`; order 3:
  `320 <= 2048`, break -> order 3, 39 objects. Ruled out by the 4-CPU DTB.
- `max_order=1` (refuted, needs a cmdline param that is absent):
  `min(16,9)=9`, start 1, order 1 fails at fraction 16, passes at
  fraction 8 (`704 <= 1024`) -> order 1, 9 objects. This is the only branch
  that yields order 1, and its premise contradicts the stock cmdline.
- `max_order=0`: order 0, 4 objects. Same refutation.

So the derivation lands on **order 2, 19 objects, 16384 B per slab** for
`nr_cpu_ids` 1..7 (4 on device), and the CPU count only matters at 8.
The old `order=1` result is refuted, not merely unconfirmed.

**Derived geometry (`LAB` sizes + `CONF` config/cmdline/DTB + `UNK` stock
binary):**

```
cache name      : "mm_struct"          (fork.c:2140)   CONF (source)
sizeof          : 0x338 (824)          (DWARF)          LAB
object_size     : 0x338               (slab_common.c:341)  LAB
inuse           : 0x338               (slub.c:3453)         LAB
s->size (stride): 0x340 (832)          (slub.c:3502)    LAB
s->offset       : 0x0                                    LAB
s->align        : 0x40 (64)            (slab_common.c:304)  LAB
slab order      : 2 (16384 B)          (slub.c:3227)    INFERRED (closed
objects/slab    : 19                   (oo_make)         derivation; stock
max_order       : 3 (PAGE_ALLOC_COSTLY_ORDER)            binary sealed)
min_objects     : 16 (nr_cpu_ids=4)
```

### 3.4 `min_objects` is a floor, not the object count (correction)

A prior revision treated `min_objects=9` as implying 9 objects per slab.
The code uses it only as the loop floor:
`for (order = max(min_order, get_order(min_objects * size + reserved)); ...)`.
The final count is `order_objects(chosen order, size, reserved)`.
Here `min_objects=16` forces the search to *start* at order 2 (room for 16),
and order 2 fits 19. Floor 16, result 19 — no contradiction.

### 3.5 The outcomes, and which one the code selects

| outcome | condition | status |
|---|---|---|
| order-0, 4 x `0x340` | `slub_max_order=0` via cmdline/guardpage | **ruled out**: stock cmdline has no `slub_max_order=`, `CONFIG_DEBUG_PAGEALLOC=n` |
| order-1, 9 x `0x340` | `slub_max_order=1` via cmdline | **ruled out**: same; the only branch yielding order 1 and its premise is absent |
| order-2, 19 x `0x340` | defaults (`max_order=3`, `min_objects=16`) | **selected by the derivation** |
| order-3, 39 x `0x340` | `nr_cpu_ids=8` | **ruled out**: DTB has 4 CPUs, `nr_cpu_ids=4` before `proc_caches_init()` |
| other | vendor override of the order path in the stock tree | residual `UNK`; the ancestral tree has none and the stock binary is sealed |

This selects **order-2, 19 x `0x340`**. It is not copied from Hazel (whose
`MM_OBJS 18` comes from a `0x1c0` stride on ARM32) and it is not assumed:
it falls out of `slub_max_order=3` + `nr_cpu_ids=4` with no open branch.
The prior revision's order-1 result traced to a single wrong premise
(`PAGE_ALLOC_COSTLY_ORDER = 1`); with the correct default (3) order 1 is
unreachable without a cmdline override.

Caveat that keeps this `LAB` and not `CONF`: this is the *lab* build. Its
`build-aq/.config` has `CONFIG_SLUB_DEBUG=y` while the device has it `n`
(`aquaman-config:203`). `CONFIG_SLUB_DEBUG` adds red zones, `STORE_USER` and
tracking, which would change the geometry. The device has it **off**, which is
the *simpler* case: no `SLAB_RED_ZONE` (so no `size += sizeof(void*)` +
`red_left_pad` at `slub.c:3479-3491`), no `SLAB_STORE_USER`
(`slub.c:3469-3476`), no `disable_higher_order_debug` bump
(`slub.c:3541-3549`). The derivation above used the device's
`SLUB_DEBUG=n` condition. The lab's own `0x338` DWARF size is unaffected
(`CONFIG_SLUB_DEBUG` does not change `mm_types.h`), only the slab geometry
would be, which is why the lab build's real cache is *not* the device's real
cache and why nothing here is `CONF` until measured.

### 3.6 What is directly observable on the device, and how

This is the part that can be closed with **zero reboots and no UAF**:

- `CONFIG_SLABINFO` is **not set** on the device (`aquaman-config` has no
  `SLABINFO` line; it is `bool` depending on `PROC_FS` and `SLAB || SLUB_DEBUG`
  at `init/Kconfig:2029-2033`, and the device has `SLUB=y` with `SLUB_DEBUG=n`,
  so it evaluates to `n`). **Therefore `/proc/slabinfo` does not exist on the
  Aquaman.** The lab build has it (`build-aq/.config:276`) only because the lab
  has `SLUB_DEBUG=y`. Any plan that reads `/proc/slabinfo` on the device is
  dead.
- `/sys/kernel/slab/` **does** exist: `slab_sysfs_init()` is under
  `#ifdef CONFIG_SYSFS` (`slub.c:5719-5759`), and the device has
  `CONFIG_SYSFS=y`. It is registered at `__initcall`, so it runs for every
  cache, including `mm_struct`.

The exact values live in per-cache sysfs attributes. The read-only ones are
`SLAB_ATTR_RO` = mode `0400` (`slub.c:4831-4833`): `slab_size` (`s->size`),
`object_size` (`s->object_size`), `objs_per_slab` (`oo_objects(s->oo)`), `align`
(`slub.c:4843-4861`). Note the name is **`slab_size`, not `size`**, and there is
**no `offset` attribute** in this 4.9 tree; the full attribute list is
`slub.c:4843-5190` and `offset` is absent from it. `order` exists but is
`SLAB_ATTR` = mode `0600`, read-write (`slub.c:4880-4884`), and writable `order`
is rejected above `slub_max_order` (`slub.c:4873`). So all of `0400`, i.e.
**root only** for the geometry, plus `order` which is rw for root.

So on an unprivileged shell the geometry is *not* readable. It becomes
readable after any uid-0 foothold, at which point it is a `cat`, not an
experiment. This reframes the measurement: the geometry is not something to
measure before the exploit; it is something to confirm after the first
primitive, and it is cheap to confirm.

---

## 4. Part C: the futex hash

### 4.1 Hazel's hash function, decoded

`hazel_reclaim.h`:

```c
/* Hazel has the backported 16-byte futex key: [mm, pad, address, offset]. */
static inline uint32_t ks_hash(uintptr_t addr, uint32_t mm) {
        uint32_t a, b, c;
        uint32_t page = (uint32_t)addr & ~(KS_PAGE - 1);
        uint32_t off   = (uint32_t)addr &  (KS_PAGE - 1);
        a = b = c = 0xdeadbeefu + 12u + off;
        a += mm;
        c += page;
        c ^= b; c -= ks_rol(b, 14);
        a ^= c; a -= ks_rol(c, 11);
        b ^= a; b -= ks_rol(a, 25);
        c ^= b; c -= ks_rol(b, 16);
        a ^= c; a -= ks_rol(c,  4);
        b ^= a; b -= ks_rol(a, 14);
        c ^= b; c -= ks_rol(b, 24);
        return c & (KS_HASH - 1);
}
```

This is `jhash2` over **three** 32-bit words with `length = 3`:
`a = b = c = JHASH_INITVAL + (3 << 2) + initval` = `0xdeadbeef + 12 + off`
(`include/linux/jhash.h:117-145`), then the `switch (length)` tail
`case 3: c += k[2]; case 2: b += k[1]; case 1: a += k[0];` and
`__jhash_final`. So `k = {mm, pad, address_page}` with `initval = off`.
The comment is accurate about the *word layout* but the function is a
**32-bit-only** model.

### 4.2 The Aquaman hash is the upstream v4.9.113 one, byte for byte

`.src/linux-amlogic/kernel/futex.c:391-397`:

```c
static struct futex_hash_bucket *hash_futex(union futex_key *key)
{
        u32 hash = jhash2((u32*)&key->both.word,
                          (sizeof(key->both.word)+sizeof(key->both.ptr))/4,
                          key->both.offset);
        return &futex_queues[hash & (futex_hashsize - 1)];
}
```

`diff` against `torvalds/v4.9` `kernel/futex.c`: no hunk in this function, and
`union futex_key` (`include/linux/futex.h:35-52`) is identical to upstream
`v4.9.113`. `CONF` for the source, and `jhash.h` matches upstream too
(`__jhash_final` rotations: 14, 11, 25, 16, 4, 14, 24, identical in both).

Confirmed in the lab binary, not just the source. `hash_futex` at
`0xffffff8009138e70` in `build-aq/vmlinux`:

```asm
ffffff8009138e88:  mov  w3, #0xbeff            // JHASH_INITVAL low half
ffffff8009138e90:  movk w3, #0xdead, lsl #16  // 0xdeadbeff  (0xdeadbeef + 0x10)
ffffff8009138e8c:  ldp  w0, w5, [x19]         // both.word  lo / hi
ffffff8009138e94:  ldr  w2, [x19, #0x10]      // both.offset
ffffff8009138e98:  ldr  w1, [x19, #0x8]      // both.ptr lo
ffffff8009138ea0:  ldr  w3, [x19, #0xc]      // both.ptr hi
ffffff8009138e9c:  add  w2, w2, w3           // a = b = c = 0xdeadbeff + offset
...                 (mix, ror #28/26/24/16/13/...)
ffffff8009138f64:  and  x1, x1, x4           // hash & (futex_hashsize - 1)
ffffff8009138f68:  add  x0, x0, x1, lsl #6   // sizeof(bucket) = 64
```

`LAB`, and decisive. Two things fall out:

1. **`0xdeadbeff` = `0xdeadbeef + 16` = `JHASH_INITVAL + (4 << 2)`.** The length
   is **4**, not 3. The key is consumed as four 32-bit words.
2. The two loads at `#0x8`/`#0xc` are the **low and high halves of one 64-bit
   pointer** (`key->both.ptr`, i.e. `mm` on a private futex), and
   `#0x10` is `both.offset`. `both.word` is loaded as a 64-bit pair
   (`ldp w0, w5`).

That is exactly the LP64 layout of `union futex_key`:

```c
struct { unsigned long word; void *ptr; int offset; } both;   /* 8 + 8 + 4 */
```

`sizeof(word) + sizeof(ptr) = 16`, `/4 = 4` words. `both.offset` is at
`+0x10`. All consistent.

### 4.3 The consequence: Hazel's `ks_hash` is not portable

Hazel's model hashes `{mm, pad, address}` as three 32-bit words. The Aquaman
hashes `{word_lo, word_hi, mm_lo, mm_hi}` as four 32-bit words, with
`initval = offset` and the first word being the **address**, not the `mm`.

Concretely, for a private futex on Aquaman:
- `k[0],k[1]` = low/high 32 bits of `key->both.word` = the **user address**
- `k[2],k[3]` = low/high 32 bits of `key->both.ptr` = the **64-bit `mm` pointer**
- `initval` = `key->both.offset` = the page offset of the address

Hazel's brute force (`ks_solve_mm`, `ks_brute_thread`) iterates `mm` over
`0xc0000000 .. 0xf0000000` in steps of 4 and checks that four collision
observations are consistent. On the Aquaman:

- The `mm` is a 64-bit kernel VA. With `CONFIG_ARM64_VA_BITS=39` and
  `PAGE_OFFSET 0xffffff8000000000` (`aquaman-config:405-407`,
  `ghostlock_target.h:29`), a slab `mm` sits in the linear map. Its high 32
  bits are not free to be ignored, but they are *not* an independent unknown
  either: they are a function of the physical page mapped into the direct map.
- The search must therefore be a **64-bit** search over the linear map, or a
  two-stage search that first recovers the high word.

Feasibility of the timing side channel itself is **unresolved**. Hazel's
approach creates `KS_PILE = 2048` threads on one futex address, then times
`FUTEX_WAKE_PRIVATE` on `KS_TEST_PAGES = 16384` candidate addresses and takes
the slowest ones as same-bucket collisions. On the Aquaman, `futex_hashsize`
is `roundup_pow_of_two(256 * num_possible_cpus())` (`futex.c:3353`),
i.e. **1024 for 4 CPUs** (2 CPUs -> 512, 1 CPU -> 256). So the mask is `0x3ff`,
not Hazel's `KS_HASH 1024`-and-`KS_HASH-1` coincidence, and the number of
expected collisions per bucket scales accordingly. Whether a 4-core A53 at
1.2 GHz with 2048 runnable threads produces a measurable timing gap is an
empirical question, not a static one. `UNK`.

Secondary risk: `futex_hashsize` is not a compile-time constant on the target
either; it is set in `futex_init()` via `alloc_large_system_hash` with
`low_limit = high_limit = futex_hashsize` (`futex.c:3356-3361`), then
`futex_hashsize = 1UL << futex_shift` (`futex.c:3362`). The `alloc_large_system_hash`
body (`mm/page_alloc.c:7249+`) clamps against `low_limit`/`high_limit` and
rounds to a power of two, so it should stay 1024, but this is a boot-time
value and would be readable from `__futex_data` with a kernel read.

Status table:

| item | status |
|---|---|
| `hash_futex` == upstream 4.9.113, 4 words, LP64 | `CONF` (source) + `LAB` (asm) |
| `ks_hash` from Hazel is directly reusable | **NO**, `CONF` mismatch |
| `mm` must be recovered as a 64-bit value | `CONF` |
| timing side channel works on this SoC | `UNK` |
| `futex_hashsize == 1024` | `LAB`, plausible, boot-time |

---

## 5. Part D: cross-cache reclaim

### 5.1 What Hazel actually does

`hazel_reclaim.h`, `prepare_reclaimed_page()`:

- `MM_OBJS 18`, `MM_OBJ_SIZE 0x1c0`, `MM_SLAB_SIZE = KS_PAGE * 2 = 8192`.
  Hazel's `mm_struct` is `0x1c0` = 448 B, 18 per 8 KiB slab.
  `448 * 18 = 8064`, leftover 128 B. Consistent with order 1.
- `alloc_held_mm()`: fork a child, `open("/proc/<pid>/mem")`, `SIGKILL`,
  `waitpid`. The `/proc/pid/mem` fd holds a reference to the `mm_struct`
  through the open file, so the `mm` survives the process death but is pinned.
  This is the standard "hold an mm via procfs" trick and it is version
  independent.
- Shaping: `prep_n = 32 * MM_OBJS = 576` held mms, then `spray_n = (1 +
  MM_PARTIALS) * MM_OBJS = 9 * 18 = 162`. Then `MM_OBJS-1 = 17` "pre" and
  `MM_OBJS = 18` "post" around the leak child, which is the one whose address
  is recovered.
- Free ordering: close the 17 pre, close the leak fd, close the 18 post, close
  the 162 spray, close the 576 prep. All mms land in the `mm_struct` cache's
  free lists and the slab pages return to the page allocator.
- Reclaim: `1024` `AF_UNIX` `SOCK_STREAM` socketpairs with
  `SO_SNDBUF = 1 MB`, then `send()` of `RECLAIM_DATA = MM_SLAB_SIZE = 8192`
  bytes into each. An 8 KiB `send` to a unix stream socket allocates a
  contiguous 8 KiB data buffer (order-1 pages), which is exactly the order-1
  slab page the `mm_struct` cache just released. The payload becomes the
  content of those pages.
- Verification: `find_reclaim_value()` uses `recv(MSG_PEEK)` on each socket
  and searches for a known word at a known offset. If a specific offset
  contains the expected value, that socket is the one that got the reclaimed
  page, and its buffer address is the controlled kernel address.

The payload (`fill_reclaim_payload`) places, relative to `page_base`:
`fake rt_mutex` at `+0x100`, `fake waiter` at `+0x140`, `fake task` at `+0x400`,
`fake fops` at `+0x200`. Everything inside one 8 KiB unit. `MAX` byte written
is `+0x400 + 0x6c8 = 0xACC = 2764 B`, comfortably inside 8192.

### 5.2 Which numbers depend on what

| number | depends on | Aquaman value |
|---|---|---|
| `MM_OBJS 18` | `mm_struct` size / slab order | **19** (derived, 3.1-3.5) |
| `MM_OBJ_SIZE 0x1c0` | `sizeof` + `SLAB_HWCACHE_ALIGN` | **`0x340`**, not `0x1c0` |
| `MM_SLAB_SIZE 8192` | slab order | **16384** (order 2) |
| payload offsets `+0x100/+0x140/+0x200/+0x400` | Hazel's ARM32 struct sizes | **must be recomputed** for LP64 |
| `RECLAIM_PAGES 1024` | statistical, empirical | `UNK` |
| `MM_PARTIALS 8`, `prep_n 32*MM_OBJS` | SLUB partial-list behaviour | `UNK`, rescale by the object-count change (18 -> 19) |
| `SO_SNDBUF 1 MB` | nothing target specific | reusable |
| 8 KiB `send` | must equal the slab order | order 2 -> 16 KiB `send` needed, not 8 KiB |

`SLAB_FREELIST_RANDOM` is unset on the device (`aquaman-config:208`), and
`CONFIG_AMLOGIC_SLUB_DEBUG` is unset (`:1557`), and `SLAB_FREELIST_HARDENED`
does not exist in 4.9. So there is no freelist randomization and no hardening
to defeat. That is favourable and is a genuine `CONF`.

### 5.3 The payload does not fit in the ARM32 layout, and that is the real problem

Not a page-count problem. A **width** problem, and it is fatal to a direct
translation:

Hazel's fake objects are all 4-byte-pointer structures. Their largest
internal span is the fake `task_struct`, which needs fields up to `+0x6c8`
(`pi_blocked_on`-ish region, per `fill_reclaim_payload`). The Aquaman
`task_struct` is `0xdc0` = 3520 B with `pi_lock` at `0x7d4`, `pi_waiters` at
`0x7e0`, `pi_waiters_leftmost` at `0x7e8`, `pi_blocked_on` at `0x7f0`
(`dwarf_offsets.py`, `LAB`, and the `rt_mutex_get_effective_prio` disassembly
confirms `0x7e0`/`0x7e8`/`0x68`).

Budget inside one 16384 B unit:

```
fake rt_mutex   0x20  (lock 0x00, waiters 0x08, leftmost 0x10, owner 0x18)
fake waiter     0x50  (tree 0x00, pi_tree 0x18, task 0x30, lock 0x38, prio 0x40, deadline 0x48)
fake fops       0xf0  (read 0x10, write 0x18, ioctl 0x48, mmap 0x58, open 0x60, release 0x70)
fake task     0xdc0  (prio 0x68, pi_lock 0x7d4, pi_waiters 0x7e0, leftmost 0x7e8, blocked_on 0x7f0)
------------------------------------------------------------------
raw sum               0x0f20 = 3872 B
```

Even with zero padding and zero alignment waste, the four objects need
3872 B of *contiguous, non-overlapping* space. That fits in 16384. But:

- `fake task` alone is `0xdc0` = 3520 B, so the reclaim unit is dominated by it.
- The reclaim primitive here is a **single 16 KiB unix-socket send**: the payload
  is copied into one contiguous buffer. Fine, 3872 < 16384.
- However the objects must land at *fixed relative offsets* the kernel will
  follow (`+0x100`, `+0x140`, `+0x200`, `+0x400` in Hazel). Recomputing for
  LP64: with 64-byte alignment, a natural packing is `lock` at `+0x000`,
  `waiter` at `+0x100`, `fops` at `+0x200`, `task` at `+0x300`. Task then ends
  at `0x300 + 0xdc0 = 0x10c0` = 4288 B. Fits in 16384 with 12096 B spare.

So the width problem is **solvable within one 16 KiB unit**, and the geometry
question is not what blocks the payload. What is not yet answered is whether
the 16 KiB send reliably lands on the released slab page: that is empirical.

Important: the LP64 fops is `0xf0` (15 pointers, `include/linux/fs.h:1728-1756`),
and this 4.9 tree has `read_iter`/`write_iter`, which Hazel's ARM32 blob also
has. But Hazel's ARM32 offsets (`hazel_root.c:283-287`, `mutex at +0x18`)
must be regenerated: `configfs_buffer` here is size `0x60` with `mutex` at
`+0x20` (`ghostlock_target.h:242-248`, `LAB`), not `+0x18`. Already noted in
`reports/ghostlock-structs-4.9-arm64.md:70-74`, and it is correct there.

### 5.4 The hypothesis, stated as a hypothesis

Engineering hypothesis for the Aquaman cross-cache step, not a design
decision:

1. Shape the `mm_struct` cache with `alloc_held_mm()` (`/proc/pid/mem` hold
   trick), sized to the **19 objects per slab** geometry, not 18.
2. Free all held mms in one window so the order-2 slab pages return to the
   page allocator.
3. Reclaim with `AF_UNIX` `SOCK_STREAM` socketpairs, `SO_SNDBUF 1 MB`, and
   16 KiB `send`s, matching the order-2 slab.
4. Pack `rt_mutex` / `rt_mutex_waiter` / `file_operations` / `task_struct`
   at 64-byte-aligned offsets, total 4288 B, verified to fit in 16384.
5. Confirm with `MSG_PEEK` per socket, exactly as Hazel does.

Steps 1-4 are derived. Step 5's reliability, the number of sockets, and the
partial-list shaping constants are `UNK`.

---

## 6. Part E: why the current path is stuck

Reclassifying the failures per the requested taxonomy. This is the part with
the least evidence in the repo, so most entries are marked as such.

| # | classification | verdict | evidence |
|---|---|---|---|
| 1 | bug in the experiment | **partly** | `tools/ghostlock_oracle_v2.c` was rewritten 3x mid-flight and each rewrite changed the geometry. The gate/rate/stop-rule churn is visible in `reports/ghostlock-oracle-v2-*.md`. Not a single-variable experiment. |
| 2 | wrong offset | **plausible, unproven** | `GL_MM_SIZE 0x338` should be `0x340` (§3.2). Does not affect the current oracle (which never reached the consumer), so this is a latent bug, not a proven cause. |
| 3 | wrong frame | **likely, and the strongest static finding** | §2.3: the oracle drives `rt_mutex_get_effective_prio`, which reads `task->pi_waiters` (the *owner's* tree). The dangling object is the *victim's* `pi_blocked_on`, read by `rt_mutex_adjust_pi` (`core.c:4401`) or the chain walk (`rtmutex.c:548`). These are different code paths. The oracle was pointed at a path that may never touch the freed frame. |
| 4 | wrong timing | **ruled out for the observed deaths** | `ghostlock-oracle-v2-hold.md:29-35`: holdB died before the first heartbeat at `+0 ms` with a 250 ms settle, so the actor is faster than the settle. "Shorten the settle" was already tried. |
| 5 | correct UAF, wrong primitive | **not excluded** | The reboot is consistent with a UAF read, but no log names the faulting path. A wrong-but-live consumer is as plausible as a stamp failure. |
| 6 | right hypothesis, wrong oracle | **confirmed for the `0x180` "hit"** | `ghostlock-value-oracle.md:18-24`: fixed 4096 B VLA meant the user SP never moved, so the sweep was a no-op. The "hit" was stack-reuse luck. `rep_0x180.log` shows 9/9 "frame intocado". |
| 7 | false hypothesis | **one confirmed** | The claim that the actor is process exit was refuted by the hold round (`hold.md:20-27`). |

Reconciling the old "PAD 0x180 hit" with the later reboots, as requested:
`scan_pads.log:119-127` recorded `[pad 0x180] ACERTO consumer rapido prio=0
us=706` and survived. That run predates the `stamp_at()` rewrite. Under the
old fixed-VLA stamper the user SP was constant for every PAD, so 0x180 was not
measuring a stack offset at all; it was a fresh-pthread stack-reuse lottery
combined with the known EDEADLK/timeout race. The later `rep_0x180.log` is
the same geometry re-run 9 times with zero hits. **0x180 is not evidence.**
No stamp byte was ever written on the device.

The single most actionable item in this section is #3: before spending another
reboot, confirm which consumer path the freed frame is actually reachable
from. That is a static/source question, not a device question.

---

## 7. Part F: compatibility matrix

Legend: `CONF` confirmed, `PLAUS` plausible, `UNK` unknown, `INCOM` incompatible.

Rows: GhostLock/Karat (`R0rt1z2/GhostLock-5.10`, 5.10 arm64, Fire OS 8),
Hazel (4.9 ARM32, Fire OS 7), Aquaman current work (this repo).

| stage | Karat | Hazel | Aquaman | note |
|---|---|---|---|---|
| `trigger` | CONF | CONF | **CONF** | 7/7 dispatch + 5/5 EDEADLK on device |
| `stack reuse` | CONF | CONF | **UNK** | reclaim code exists (`ghostlock_reclaim_try.c`) but never ran |
| `stack stamp` | CONF (setsockopt) | CONF (setsockopt) | **INCOM/unknown** | `pselect` 6/6 reboots; the MCAST 40 B overlap is uncalculated (§8) |
| `mm_struct leak` | CONF (dedicated slide.c) | CONF (futex hash timing) | **UNK** | Hazel route needs a 4-word LP64 hash reimplementation; SoC timing untested |
| `cross-cache` | CONF (pipe, `MM_ORDER 3`) | CONF (AF_UNIX 8 KiB) | **PLAUS** | geometry derived: order 2, 19 x `0x340`; step-5 reliability untested |
| `controlled object` | CONF | CONF | **PLAUS** | 3872 B raw sum fits in 16384; offsets must be regenerated |
| `kernel read` | CONF | CONF | **UNK** | `configfs_buffer.mutex` at `+0x20` here vs `+0x18` in Hazel; dentry tolerance unverified |
| `kernel write` | CONF | CONF | **UNK** | the EFAULT boundary trick depends on the vendor `copy_from_user` direction, untested on arm64 |
| `task/cred` | CONF | CONF | **PLAUS** | `cred` size `0xa8`, `uid` at `+0x04`, `DEBUG_CREDENTIALS` unset: mechanics identical. Needs an address. |
| `SELinux` | CONF (bypass) | CONF (uid 0 in shell) | **PLAUS (ceiling)** | Enforcing stays; `uid 0` in `u:r:shell:s0` is the expected ceiling, same as Hazel |

Karat is not a useful donor for the `mm_struct` step: it uses a dedicated
`slide.c` KASLR leak and `pipe_buffer` reclaim with `MM_STRUCT_SZ 0x3c0` /
`MM_ORDER 3` (`src/targets/karat/target.h:51-53`), i.e. a different geometry
again. Its `FAKE_TASK_*` offsets (`target.h:79-86`) are 5.10 values.

---

## 8. The MCAST overlap, left explicitly open

Per instruction, "MCAST is too short" is **not** claimed. The 40-byte figure
(`sizeof(struct group_source_req)`) is established: the copy is
`copy_from_user(&greqs, optval, sizeof(greqs))` at
`net/ipv6/ipv6_sockglue.c:680-684`, and the lab disassembly shows
`mov x2, #0x14` (= 20, for the `group_req` case) with the source-group case
sharing the `x29+0xd8` destination. What has **not** been computed:

```
stack frame
  -> position of the waiter inside it
  -> which bytes the 40-byte MCAST write actually covers
  -> which waiter fields must be controlled (task 0x30, lock 0x38, prio 0x40, deadline 0x48)
  -> which can come from the still-intact waiter
```

`struct group_source_req` is 4 + 16 + 4 + 16 = 40 B, of which the first 4 B are
`gsr_group.gr_group.sin6_family` and the rest is address material. If the
window happens to cover `pi_tree_entry` and `task`, 40 B is ample. If it covers
only `tree_entry` and `pi_tree_entry`, the `task` pointer cannot be forged and
the stamp cannot redirect the walk. **Not decided.** The setsockopt path frame
is `0x1e0` (`do_ipv6_setsockopt.isra.4`) and the write lands at `x29+0xd8`, so
the destination offset is known; the missing piece is the futex-side waiter
offset in the *same* thread's stack, which requires fixing the two call
depths. This is a computation, not an experiment.

---

## 9. Current bottlenecks

1. **No stamp has ever succeeded.** The value oracle is `UNTESTED` after 6
   boots. Everything downstream of it is unproven.
2. **The oracle may be pointed at the wrong consumer** (§6 #3). If correct,
   this invalidates the current design rather than a constant, and it is
   detectable statically. Cheapest possible win in the project.
3. **The `mm_struct` grid in the tooling was wrong** (order 1 / 9 / 8192 B
   from a wrong `PAGE_ALLOC_COSTLY_ORDER=1` premise; fixed to order 2 /
   19 / 16384 B in `ghostlock_target.h`, `ghostlock_mm_enum.h`,
   `ghostlock_leak_cal.c:77`, plus the latent `0x338`-as-stride in older
   comments). The stride `0x340` was already right.
4. **No reclaim has been attempted.** `tools/ghostlock_reclaim_try.c` has no
   log in `out/logs/`.
5. **Stock binary is unavailable.** `boot.img` is AMLSECU-encrypted
   (`ghostlock-kaslr-symbols.md:3-12`), so every `LAB` number stays
   inferential for the 2022 build.
6. **No post-mortem.** pstore is denied to shell, `dmesg` is blocked
   (`ghostlock-ashmem-configfs.md:18-20`), and `pstore_io_save` is missing from
   the rebuilt kernel (`repo-state.md:233-236`). Every reboot is a black box.

---

## 10. Remaining hypotheses (explicitly marked)

| # | hypothesis | status |
|---|---|---|
| H1 | `mm_struct` stock size is `0x338` like the lab | PLAUS (all size-affecting config guards agree; stock source unknown) |
| H2 | slab order 2, 19 objects, 16384 B | INFERRED: closed derivation from ancestral tree + device config/DTB/cmdline; stock binary sealed |
| H3 | `futex_hashsize == 1024` | LAB, plausible, boot-time value |
| H4 | hash timing is measurable on a quad A53 | UNK |
| H5 | 16 KiB unix send reclaims the released order-2 slab | UNK |
| H6 | the orphan `pi_blocked_on` is what the reboot faults on | UNK |
| H7 | the 40 B MCAST window covers the fields that matter | UNK (§8) |
| H8 | configfs dentry tolerance survives an ashmem `f_op` swap | UNK |

---

## 11. Next experiment

Per the requested priorities: maximize information, minimize reboots, one
variable at a time, allocator/reclaim before primitive, nothing touching
cred/SELinux before reclaim is confirmed.

**Step 0 is static and costs nothing. Do it before any reboot.**

Resolve, from source + `build-aq/vmlinux` only:

- **0a.** Which consumer path dereferences the orphaned `pi_blocked_on` in a
  form the attacker can influence: `rt_mutex_adjust_pi` (`core.c:4401`,
  reached from `__sched_setscheduler` with `pi=1`) or the chain walk
  (`rtmutex.c:548`). Compute the stack-address relationship between the
  FWRQ frame (waiter at `x29+0x80` of a `0x1a0` frame, `LAB`) and the
  setsockopt frame (`0x1e0`, write at `x29+0xd8`, `LAB`) for the same thread.
  This yields the 40-byte MCAST overlap (H7) and tells us which stamper, if
  any, can control `waiter->task` and `waiter->lock`.
- **0b.** With 0a, decide whether a control register is possible at all. If
  not, the `pselect` route is closed for a *structural* reason, not a timing
  one, and that is worth knowing before spending a boot.

**Single question for experiment 1, with a binary criterion:**

> *Question:* can a 16384-byte `AF_UNIX` `send` recover the order-2 slab page
> released by a batch of held `mm_struct`s?

Binary criterion:

- **PASS**: at least one socket's `MSG_PEEK` buffer contains the 32-bit
  sentinel `0x5A5A5A5A` at offset `0x3FFC` (last word of a 16384 B payload).
  Then the reclaim primitive is demonstrated.
- **FAIL**: zero sockets show the sentinel after the full spray, on all
  repetitions in the batch.

Cost and risk: no UAF, no kernel write, no cred, no SELinux. A
`/proc/<pid>/mem`-holding fork loop and unix socketpairs only. Failure mode is
a clean exit, not a panic: there is no corrupted pointer in this experiment.
This deliberately validates allocator/reclaim first, per the stated priority,
and it is a strict prerequisite for any primitive work.

Only after a green reclaim does the value-oracle question come back, and it
should be re-posed against the consumer path identified in 0a, not the one the
current `oracle_v2` drives.

Note on measurement: `/proc/slabinfo` does not exist on the device
(`CONFIG_SLABINFO` evaluates to `n`), so the geometry confirmation
(H1/H2) is not a pre-exploit step. It becomes a `cat` of
`/sys/kernel/slab/mm_struct/{slab_size,object_size,objs_per_slab,order,align}`
after any uid-0 foothold, at mode `0400` (`order` is `0600`). Note the
attribute is `slab_size`, not `size`, and this 4.9 tree exposes no `offset`
attribute, so `s->offset` is not directly observable.

---

## 12. GO / NO-GO / UNKNOWN

**GO**: the trigger, the UAF mechanism, and the allocator geometry:

- `CVE-2026-43499` is present in the ancestral `rtmutex.c` by code inspection
  (`remove_waiter` uses `current` at `rtmutex.c:1108-1111`), and the
  `CMP_REQUEUE_PI -> EDEADLK` rollback is reached on the device 5/5.
- The `mm_struct` cache geometry is derivable: `sizeof 0x338`, stride `0x340`,
  order 2, 19 objects, 16384 B, `max_order=3`, `min_objects=16`.
  Derived from `fork.c:2140` + `slab_common.c:304-325` + `slub.c:3203-3276`,
  with the device's own `SLUB_DEBUG=n`, stock cmdline (no `slub_*`), and the
  4-CPU DTB (`nr_cpu_ids=4` before `proc_caches_init()`).
- The four forged objects need 3872 B raw and pack into 4288 B at
  64-byte-aligned offsets, inside the 16384 B unit.
- No allocator hardening to defeat: `# CONFIG_SLUB_DEBUG is not set`
  (`aquaman-config:203`, no red zones and no `STORE_USER`),
  `# CONFIG_SLAB_FREELIST_RANDOM is not set` (`aquaman-config:208`),
  `# CONFIG_AMLOGIC_SLUB_DEBUG is not set` (`aquaman-config:1557`),
  `# CONFIG_KASAN is not set` (`aquaman-config:5262`), and
  `SLAB_FREELIST_HARDENED` does not exist in this 4.9 tree.

**NO-GO**: these specific things, as written:

- Hazel's `ks_hash` is **not** portable. It models a 3-word key
  `[mm, pad, addr]`; the Aquaman hashes 4 words
  `[word_lo, word_hi, mm_lo, mm_hi]` (`LAB`, from the `0xdeadbeff` immediate
  in `hash_futex`). The `mm` must be recovered as a 64-bit value.
- The old order-1 grid (`tools/ghostlock_target.h`, `ghostlock_mm_enum.h`,
  `tools/ghostlock_leak_cal.c:77`) was wrong; the stride is `0x340` and the
  slab is order 2 with 19 objects, not order 1 with 9 (and not order 0
  with 4). Fixed in this revision.
- The "PAD 0x180 hit" is not evidence. Fixed-VLA stamper, SP never moved,
  0 hits on re-run.
- The `pselect` stack stamp, as built, is a dead end: 6/6 reboots, oracle
  never once read.
- `/proc/slabinfo` is unavailable on the device (`CONFIG_SLABINFO` = `n`).

**UNKNOWN**: cannot be settled without more work, listed as hypotheses:

- Whether the stock 2022 kernel's `mm_struct` is still `0x338` (H1). The
  source is not public and the boot image is sealed.
- Whether a hash-collision timing side channel is measurable on a quad A53 at
  this clock, and at what pile size (H4).
- Whether the 40-byte MCAST window covers `waiter->task`/`waiter->lock` (H7).
  Deliberately not answered; §8 has the open computation.
- Which code path actually faults in the 6 observed reboots (H6).
- Whether a 16 KiB unix send reliably captures the released slab page (H5).
- Whether configfs tolerates an ashmem `f_op` swap on this build (H8), and
  whether the `copy_from_user` boundary trick behaves the same on arm64.
- The stock kernel's `futex_hashsize` (H3) and its KASLR window behaviour.
