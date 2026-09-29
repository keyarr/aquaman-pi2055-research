# GhostLock structs 4.9.113 ARM64 (Phase 3)

Source: `.src/linux-amlogic` (headers + .c). Numerical offsets
marked INFERRED: calculated from field ordering in source for
LP64, without aquaman vmlinux/DWARF to confirm. Do not use in exploit
without runtime read validation or pahole on a compatible vmlinux.
Layouts marked CONFIRMED apply to the analyzed tree.

## struct rt_mutex_waiter — CONFIRMED (rtmutex_common.h:25-37)

Without CONFIG_DEBUG_RT_MUTEXES (unset in aquaman-config), the layout is:

    0x00  struct rb_node tree_entry      (24B in LP64)
    0x18  struct rb_node pi_tree_entry   (24B)
    0x30  struct task_struct *task       (8B)
    0x38  struct rt_mutex *lock          (8B)
    0x40  int prio                       (4B + 4 pad)
    0x48  u64 deadline                   (8B)
    size  0x50

Identical to what the aresin port documents for 4.14 ARM64. 4.9 and 4.14 use
rb_node here (plist_node only appears in futex_q). Hazel ARM32 differs
only in pointer widths (task at 0x18 on ARM32).

## struct futex_q — CONFIRMED (futex.c:237-247)

    struct plist_node list; struct task_struct *task; spinlock_t *lock_ptr;
    union futex_key key; struct futex_pi_state *pi_state;
    struct rt_mutex_waiter *rt_waiter; union futex_key *requeue_pi_key;
    u32 bitset;

Relevant: q.rt_waiter points to the rt_waiter on the waiter's stack
(futex_wait_requeue_pi). This is the object that becomes dangling.

## struct task_struct — fields used, ordering CONFIRMED (sched.h)

Relative positions in source, not numerical offsets:

- tasks (list_head) ............ sched.h:1703
- real_cred / cred (__rcu ptr) .. :1828/:1830, adjacent
- comm[TASK_COMM_LEN=16] ........ :1832, right after cred
- pi_lock (raw_spinlock_t) ...... :1882
- pi_waiters (rb_root) .......... :1888
- pi_waiters_leftmost ........... :1889
- pi_blocked_on ................. :1891, right after pi_waiters_leftmost

Useful pattern for runtime validation (as hazel does): read comm from
init_task ("swapper"), then next/prev from task list. ARM64 reference:
aresin measured on 4.14 MTK real_cred=0x788 cred=0x790, pi_lock=0x85c,
pi_waiters=0x868, pi_blocked_on=0x880. For 4.9 Amlogic the numbers WILL
DIFFER — 4.9 task_struct lacks uclamp/cgroup v2/rseq and the vendor
config modifies structure size. Do not copy 0x788/0x790.

## struct cred — CONFIRMED (cred.h)

Without CONFIG_DEBUG_CREDENTIALS (check config before using):

    usage(4) | uid(4) gid(4) suid(4) sgid(4) euid(4) egid(4) fsuid(4)
    fsgid(4) | securebits(4) | cap_inheritable(8) cap_permitted(8)
    cap_effective(8) cap_bset(8) cap_ambient(8) | ...

Hazel zeroes cred+0x04 for 0x20 (8 ids + securebits) — the same arithmetic
applies on ARM64 if DEBUG_CREDENTIALS is unset (uid at +4). Confirm unset
status in aquaman-config before any usage.

## struct configfs_buffer — CONFIRMED (fs/configfs/file.c:45-56)

    count(8) pos(8) page(8) ops(8) mutex(0x18) needs_read_fill(4) ...

Hazel crafts a forged mutex at +0x18 (count=1 = unlocked) and page at +0x10.
In LP64 is mutex still at +0x20? NO: count 8 + pos 8 + page 8 +
ops 8 = mutex at +0x20 on ARM64, not +0x18. Concrete ARM32->ARM64 difference
preventing transplanting hazel's blob directly. DIRECTLY INCOMPATIBLE, must
recalculate (details in `ghostlock-port-comparison.md`).

## struct ashmem_area — CONFIRMED (ashmem.c:54-60)

    name[ASHMEM_FULL_NAME_LEN] + list_head(16) + file(8) + size(8) + prot(8)

ASHMEM_FULL_NAME_LEN differs across versions; read ashmem.h from tree before
assuming "/dev/ashmem/" prefix. Hazel's trick (first word of
area as huge count) relies on this literal prefix — verify.

## struct file / file_operations — standard 4.9, expected

f_op in file+? , read/write in fops+? : extract via pahole when
vmlinux is available. Do not guess.

## struct mm_struct — vendor-dependent size

Hazel uses MM_OBJ_SIZE=0x1c0 (ARM32, FireOS config). In ARM64 4.9 with
MMU the mm_struct is larger (rb_root + vmacache + additional 64-bit fields).
The 0x1c0 grid DOES NOT apply. Actual size is obtained via pahole or runtime
leak (leaked_mm & mask). Mark as primary heap divergence.

## How to resolve offsets (order)

1. pahole on a compatible 4.9.113 ARM64 vmlinux (local dangal build with
   approximate aquaman-config);
2. Validation via runtime read after kernel R/W (comm + task list anchors);
3. Never by copying directly from another device.
