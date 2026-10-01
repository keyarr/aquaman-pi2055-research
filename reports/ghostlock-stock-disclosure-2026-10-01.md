RESULT: NO_DISCLOSURE_FOUND
BOOT_ID: 3ec336a5-439f-497f-b9f7-08fd7441b174
TARGET_POINTER: [W_waiter+0x38] (waiter->lock) / &f_alt.pi_mutex
DISCLOSED_BYTES: none (0 bytes kernel pointer disclosed)
SURFACE: none
REPRODUCED: n/a
REBOOTS: 0
TESTS: 22

# ghostlock stock disclosure 2026-10-01 — information only, no write

Date: 2026-10-01. Device: MiTV-AESP0 aquaman S805Y, Android 9 PI.2055,
kernel 4.9.113 #1 SMP PREEMPT 2022-09-06 armv8l, shell uid=2000
u:r:shell:s0 Enforcing. Lab: build-aq/vmlinux + .src/linux-amlogic
(OFFLINE_ONLY for VAs/offsets). Stock: everything below re-probed on
device this boot unless marked OFFLINE_ONLY.

Rule compliance: no exploit, no write, no fake object, no spray, no cred,
no SELinux bypass, no module, no patch, no flash, no blind fuzz. Timeout
delta not counted as leak. Crash log not counted as leak. errno alone not
counted as leak. Leak requires recovered pointer bytes.

## 1. Current state

LEVEL_2 preserved on same BOOT_ID 3ec336a5 (zero reboot, up ~30k s).

Chain (STATIC_CONFIRMED, not reopened):

```text
FWRQ/FCRQ -> EDEADLK -> FUTEX_LOCK_PI(f_chain) -> futex_lock_pi
-> rt_mutex_timed_futex_lock(FULL) -> slowlock -> task_blocks
-> waiter->lock -> adjust chain -> EDEADLK
```

Consumer: task_blocks 0x52fc ldr x25,[x0,#0x38] + adjust head 0x4df0
ldr x0,[x28,#0x38] / 0x4df4 cmp+b.ne gate. Birth value
waiter->lock == &f_target.pi_mutex.

Re-validated this round (same boot, tools/ghostlock_chain rebuilt binary
already on device, no new tool):

```text
base_t  TIMEOUT_BLOCK 110 3000ms (L0, no trigger)
occ_tgt EDEADLK_CYCLE 35 0ms     (U1, trigger + f_target occupied)
```

Full logs prior: out/logs/ghostlock_consumer_boot3ec336a5.log.
Spot logs this round in §7. alt_only/alt_tgt fidelity (f_alt ignored,
walk follows f_target) cited, not re-run.

Reclaim: FAIL closed, not reopened. H16 write hunt: NO_EXACT_WRITER_FOUND
(411 stores 8B in window, 33 exact offsets, 0 TARGET_RT_MUTEX, 0 producer
of &f_alt.pi_mutex, atomics 0, ioctl 0, poll GEOMETRY_ONLY), not retried.

## 2. Target

Need runtime bytes, not offline layout:

```text
static:  waiter->lock == &f_target.pi_mutex (birth)
runtime: W_waiter = 0xffff... (live stack addr of waiter object)
         waiter->lock = 0xffff... (current 8B value in slot +0x38)
minimum: any live kernel pointer belonging to the PI object
         (rt_mutex_waiter / rt_mutex / futex_pi_state / task_struct
          of W/O/C chain)
```

Offline (lab VA, DWARF, SP0-0x2b0/0x290 conjectures, waiter_est_lab)
explicitly NOT accepted. Must be stock bytes via shell-reachable surface.

## 3. Surfaces audited

| surface | reachable | result | classification |
|---|---|---|---|
| /proc/self/stack | yes, readable | all `[<0000000000000000>] walk_stackframe` masked | FALSE_POSITIVE if mistaken for leak / BLOCKED as disclosure |
| /proc/self/task/*/stack | yes | same zeros | BLOCKED |
| /proc/self/wchan | yes | `0` | BLOCKED (symbol-only, never addr) |
| /proc/self/syscall | yes | `63 0x3 0x...user...` user regs only | AUXILIARY (user SP ref only) / BLOCKED as kptr |
| /proc/self/stat kstkesp/kstkeip | yes | fields 29/30 `0 0` (zeroed, no PF_DUMPCORE) | BLOCKED |
| /proc/self/sched,schedstat,status,maps | yes | counters/policy/prio/user VMAs, no kptr | AUXILIARY (metadata) / BLOCKED as leak |
| /proc/net/unix,tcp | yes | Num/sk `0000000000000000`, inodes only | BLOCKED (masked/index-only) |
| /proc/interrupts | yes | counters only, no pointers | AUXILIARY |
| /proc/slabinfo | NO (absent, SLABINFO=n) | `No such file` | BLOCKED |
| /proc/buddyinfo | NO (denied) | `Permission denied` | BLOCKED |
| /proc/kallsyms | NO | `Permission denied` | BLOCKED |
| /proc/sys/kernel/kptr_restrict,dmesg_restrict,ftrace_enabled | NO | `Permission denied` | BLOCKED |
| dmesg/kmsg/pstore | NO | `klogctl: Operation not permitted` / denied | BLOCKED |
| /sys/kernel/slab/* | listing partial, every attr denied | `Permission denied` on slab_size etc | BLOCKED |
| /sys/kernel/debug,/sys/kernel/debug/tracing,/d/tracing | NO | `Permission denied` | BLOCKED |
| /sys/kernel/tracing | listing empty, trace/events absent | `No such file` | BLOCKED (DISABLED on stock) |
| atrace/ftrace shell path | NO | no trace access, events dir absent | BLOCKED |
| futex PI return/errno | yes (syscall reachable) | int errno only (35/110/0), no struct | FALSE_POSITIVE if errno called leak |
| robust/sched_param/getsockname copy_to_user | yes | USER echo / scalars / addr bytes (see §4) | FALSE_POSITIVE |
| binder/hwbinder/ashmem open | yes (world rw) | handles/fds only, debug denied | BLOCKED as kptr (index-only) |
| /dev/ion,/dev/mali open | yes (0666 system:graphics) | heap names/fds/counts, no kptr (see §6) | FALSE_POSITIVE |
| /dev/ge2d open | NO (0660 system:system, shell denied) | shell not in graphics/system | BLOCKED (unreachable) |
| /dev/media.vfm,media.*,ppmgr,amstream_* | mixed perms, cat EPERM | VFM_GET disabled -EIO, ge2d fds only | BLOCKED / FALSE_POSITIVE |
| disclose_stack probe (mode 23) | yes | zeros/user/scalar only, kptr=0 | PROOF of absence on probed surface |
| disclose_heap probe (mode 24) | yes | same + HEAP_RULE occupancy verdict only | PROOF of absence / AUXILIARY identity |
| GhostLock armed vs normal output | yes | only errno 35 vs 110 + 0ms vs 3000ms, no bytes | FALSE_POSITIVE as leak |

Legend: PROOF = bytes/pointer recovered (only for leak; none here, used
for negative proof of masking). AUXILIARY = metadata supporting reasoning.
FALSE_POSITIVE = must not be called leak. BLOCKED = denied/masked/absent/
disabled/unreachable.

## 4. Futex PI analysis

Paths checked in .src/linux-amlogic/kernel/futex.c + locking/rtmutex.c +
build-aq/vmlinux --verify:

* FUTEX_LOCK_PI -> futex_lock_pi (uaddr,flags,timeout,0): returns int.
  Atomic fastpath (case 1 -> 0), -EFAULT/-EAGAIN retry, else
  rt_mutex_timed_futex_lock + fixup_owner. No copy_to_user in body
  (binary n_insn=272 copy_bl=0). pi_state stays in kernel (q.pi_state
  heap, freed on wake). No waiter/task/mutex bytes to user.
* FUTEX_TRYLOCK_PI -> same with trylock=1 -> rt_mutex_trylock, ret
  fixup to 0/-EWOULDBLOCK. Same: int only.
* FUTEX_UNLOCK_PI -> futex_unlock_pi: get_user uval, TID check
  (uval&TID_MASK vs vpid -> -EPERM), hash lookup, wake. Owner TID visible
  via uaddr word is user TID int, not task_struct pointer. Int only.
* FUTEX_CMP_REQUEUE_PI -> futex_requeue(...,pi=1): int (woken count)
  only. Requeue stores keys (x2,x3 from attach path) to bucket waiter,
  never waiter->lock to user.
* FUTEX_WAIT_REQUEUE_PI -> futex_wait_requeue_pi.constprop.8: birth site
  of W_waiter (stp [sp,#-0x1a0], waiter x29+0x80). Zero copy_to_user
  (verified). Hrtimer stack only.
* get_robust_list: put_user(head) where head = p->robust_list __user set
  by userspace (futex.c:3084-3086, inlined stxr not bl). USER echo.
  Probe: head=0x0 len=24 kptr=0.
* sched_getattr/getparam: copy_to_user scalar structs (sched_attr all
  scalars, sched_param int prio). Probe: prio=0 scalar.
* signal copy_siginfo_to_user: si_ptr sender-controlled/user-PC, never
  waiter/stack/rt_mutex. Not a PI leak.
* socket getsockname/SIOCGIFCONF/unix diag: sockaddr addr bytes, ifconf
  USER buf echo, diag ino/dev/qlen. No sk/task pointer. Probe:
  alen=2 bytes0=01000000.
* printk in futex.c:2322 fixup_owner `pi-mutex: %p` + rtmutex.c:524
  `Maximum lock depth` are dmesg-only. dmesg/kmsg/pstore all denied to
  shell (klogctl EPERM), SELinux denied. Reachable=no. Even if read,
  4.9 %p without %pK hashes on stock with kptr_restrict. Class BLOCKED,
  not a shell disclosure.
* trace_printk/pr_debug in PI path: none emitting waiter/mutex addr to
  shell; ftrace/tracefs disabled/denied (see §5). Class BLOCKED/DISABLED.
* Return value / errno as oracle: EDEADLK 35 vs TIMEOUT 110 vs ACQUIRED 0
  is 2-bit state (LEVEL_2 differential). Contains zero pointer bytes.
  Per task rules: not a leak. Class FALSE_POSITIVE if claimed.

Net: zero PI struct -> copy_to_user/put_user/seq_printf path exists.
Grep `copy_to_user` in futex.c+rtmutex.c = 0 hits (only put_user robust
echo). Binary --verify confirms: task_blocks 0 copy, adjust_chain 0 copy.

## 5. Proc/debug analysis

Real device results this boot (uid=2000, same BOOT_ID):

```text
/proc/self/stack          -> 9x [<0000000000000000>] (%pK masked, base.c:472)
/proc/self/task/*/stack   -> same zeros
/proc/self/wchan          -> 0 (symbol-or-0, base.c:411)
/proc/self/syscall         -> 63 ... user sp/pc only (base.c:642)
/proc/self/stat            -> ... 29:0 30:0 kstk zeroed (array.c:436)
/proc/self/sched           -> counters/prio/policy, no pointers
/proc/self/status          -> Uid/Gid/Vm*, no pointers
/proc/interrupts           -> AVAILABLE counters, no pointers (AUXILIARY)
/proc/slabinfo             -> NOT_PRESENT (SLABINFO=n)
/proc/buddyinfo            -> PERMISSION_DENIED
/proc/kallsyms             -> PERMISSION_DENIED (%pK/kptr_restrict)
/proc/sys/kernel/*         -> PERMISSION_DENIED listing
dmesg/kmsg/pstore          -> PERMISSION_DENIED / Operation not permitted
/sys/kernel/slab/*         -> listing ok, every attr PERMISSION_DENIED
/sys/kernel/debug*         -> PERMISSION_DENIED
/sys/kernel/tracing        -> empty, events/ absent, trace absent (DISABLED)
/proc/net/unix             -> Num 0000000000000000 (masked), inodes only
/proc/self/net/tcp         -> addresses as ints, sk 0000000000000000
/proc/self/maps            -> AVAILABLE user VMAs only
pagemap                    -> hexdump missing, PFN 0 historically (SANITIZED)
```

Classification per task spec: AVAILABLE (stack/wchan/syscall/stat/sched/
status/interrupts/net-unix/maps), PERMISSION_DENIED (kallsyms/kmsg/slab
attrs/debug/tracing/buddyinfo), NOT_PRESENT (slabinfo,trace/events),
SANITIZED (stack zeros, sk zeros, kstk 0 0, pagemap PFN 0).

Debug/trace verdict:

```text
tracefs/debugfs/atrace/ftrace/vendor hooks exposing task/waiter/mutex/futex:
USER_ACCESSIBLE: none found
ROOT_ONLY: debug/tracing nodes exist but all denied to shell
DISABLED: /sys/kernel/tracing empty, VFM_GET -EIO, slabinfo absent
```

Config notes (aquaman-config, OFFLINE_ONLY): KALLSYMS=y ALL=y
BASE_RELATIVE=y, IKCONFIG_PROC=y, DEBUG_FS=y, PROC_PAGE_MONITOR=y,
PERF_EVENTS=y (paranoid 3), TASKSTATS=y, SCHED_DEBUG=y, SCHEDSTATS=y,
FRAME_POINTER=y, FTRACE=y SYSCALLS=y, but stock SELinux + dmesg_restrict +
kptr_restrict mask/deny all above to shell.

Probes (HARDWARE_OBSERVED, /data/local/tmp/ghostlock_chain modes 23/24):

```text
disclose_stack: STACK zeros, WCHAN 0, SYSCALL user regs,
  STAT 29:0 30:0, ROBUST kptr=0, SCHED prio=0, SOCK addr bytes.
  is_kptr fires on nothing. Repeat stable (ASLR moves user addrs only).
disclose_heap: same + HEAP_RULE occupancy verdict (not a pointer,
  SINGLE_SOURCE until second path confirms).
```

## 6. Vendor read surfaces

Not full re-audit. Only read/copy_to_user paths, shell reachability,
kernel-pointer content. No new candidates found.

| handler/opcode | buffer/size | source object | contains kptr? | reachable by shell? |
|---|---|---|---|---|
| ge2d GE2D_REQUEST_BUFF/EXP_BUFF (ge2d_main.c:990/996) | struct ge2d_dmabuf_req_s {int index; u32 len; u32 dir} / exp_s {int index; u32 flags; int fd} | dma-buf fd + sizes | no (fd ints) | no (/dev/ge2d 0660 system:system, shell denied) -> BLOCKED |
| vfm VFM_IOCTL_CMD_GET (vfm.c:758) | commented out, returns -EIO | none | n/a | no (disabled + /dev/media.vfm 0600 root) -> BLOCKED/DISABLED |
| ion ION_IOC_HEAP_QUERY (ion-ioctl.c:183, ion.c:1221) | struct ion_heap_data {char name[32]; u32 type/heap_id/...} / query {u32 cnt; u64 heaps} | heap names/counts | no | yes (/dev/ion 0666) but FALSE_POSITIVE (no pointer) |
| mali/ionvideo/hwbinder/binder/ashmem | fds/handles/buffers | dma-buf fd / u32 handle | no | yes but index-only -> BLOCKED as leak |
| amstream_*/ppmgr/media.* | status/dump structs | sizes/handles | no rt_mutex field in any reachable struct | no kptr -> FALSE_POSITIVE |

Source check: `copy_to_user` in ge2d/vfm = fds only or disabled;
in ion = names/ints only; `&f_alt.pi_mutex` / waiter / pi_state appear in
none. Prior 22-ioctl sample (ge2d,dvb,osd,amstream,amvenc,mmc,mtd,gdc)
stands: fds+sizes or disabled. No shell-openable node returns
`rt_mutex *` / `waiter *` / `task *` / `pi_state *`.

## 7. Hardware tests

Same BOOT_ID 3ec336a5, 0 reboots. Each test one question.

```text
T01 /proc/self/stack read            -> zeros, no bytes. BLOCKED.
T02 /proc/self/wchan read            -> 0. BLOCKED.
T03 /proc/self/syscall read          -> user regs. AUXILIARY only.
T04 /proc/self/stat read             -> 29:0 30:0. BLOCKED.
T05 /proc/self/sched read            -> counters. AUXILIARY.
T06 /proc/self/status read           -> no ptr. AUXILIARY.
T07 /proc/interrupts read            -> counters. AUXILIARY.
T08 /proc/slabinfo read              -> absent. BLOCKED.
T09 /proc/kallsyms read              -> denied. BLOCKED.
T10 kptr/dmesg_restrict read         -> denied. BLOCKED.
T11 dmesg/kmsg read                  -> denied/EPERM. BLOCKED.
T12 /sys/kernel/debug/tracing ls     -> denied/empty. BLOCKED/DISABLED.
T13 /proc/self/task stack read       -> zeros. BLOCKED.
T14 /dev perms + open (ion/mali/ge2d/amstream/vfm/ppmgr/binder) -> §6. BLOCKED/FALSE_POSITIVE.
T15 /proc/net/unix,tcp read          -> masked/index. BLOCKED.
T16 buddyinfo/schedstat/fdinfo/slab attrs -> denied/ints. BLOCKED/AUXILIARY.
T17 disclose_stack probe             -> P4 zeros/user/scalar kptr=0, RESULT DONE. PROOF of absence.
T18 disclose_heap probe              -> same + HEAP_RULE occupancy only. PROOF/AUXILIARY.
T19 base_t spot (L0)                 -> TIMEOUT 110 3000ms. PROOF differential member.
T20 occ_tgt spot (U1)                -> EDEADLK 35 0ms. PROOF differential member.
T21 maps/pagemap                     -> user VMAs / PFN 0. AUXILIARY/BLOCKED.
T22 futex --verify binary + grep     -> 0 copy in PI path. OFFLINE_ONLY.
```

Spot logs (this boot):

```text
base_t:  P5 DONE rc=-1 errno=110 3000ms, P6 TIMEOUT_BLOCK
occ_tgt: P1 TRIGGER_ENTER, P2 EDEADLK 35, P5 DONE errno=35 0ms, P6 EDEADLK_CYCLE
disclose_stack: P4 STACK zeros, WCHAN 0, SYSCALL user, STAT 29:0 30:0,
  ROBUST kptr=0, SCHED prio=0, SOCK bytes0=01000000, RESULT DONE
disclose_heap:  same + HEAP_RULE occupancy verdict, not a pointer
```

No panic/reboot/hang beyond expected 3 s sleeps. No loops. LEVEL_2 intact.

Phase 4 GhostLock-vs-normal content check: armed state changes only errno
(35 vs 110) and elapsed (0ms vs 3000ms). Zero pointer bytes in any output
(P0-P8 fields are uaddrs user, sp_futex user, waiter_est_lab offline,
f_alt u32 TID-ish value, not kptr). Verdict: FALSE_POSITIVE as leak per
rules. Content requirement not met.

## 8. Verdict

```text
DISCLOSURE_FOUND: no
NO_DISCLOSURE_FOUND: yes
INCOMPLETE: no
```

Formally:

```text
RESULT: NO_DISCLOSURE_FOUND
```

No stock surface probed reveals live W_waiter, waiter->lock value, or any
related PI kernel pointer as bytes. All /proc channels masked/denied/
user-only, all reachable copy_to_user structs scalar/echo/index, PI path
zero copies, debug/trace denied/disabled, vendor reads fds-or-disabled.
Probes show zeros. GhostLock delta remains errno-only.

Useful negative: closes audited surface (proc/sys/net/futex/sched/signal/
socket/binder/ion/ge2d/vfm + disclose 23/24 + --verify) on this boot.
Does not claim unaudited corners (full /dev ioctl census beyond sample,
f_op dispatch past BFS 3, novel async/alias emit) — those stay INCONCLUSIVE
explicitly, not proof of absence everywhere.

## 9. Next bottleneck

One only: a read-only kernel-pointer source for EITHER address that
survives stock masking — finish the /dev ioctl emit census for
shell-openable nodes (open test + per-ioctl struct-field audit, same
copy_to_user discipline as §4/§6), then if found immediately re-run the
disclosed-target -> known-consumer ruler (H16.7 x28 base vs x20 value,
pi_state+0x10 + trylock/leftmost/owner checks) before any write thinking.
Do not build stamper/fake/RW/cred until an address discloses; there is no
target and no value yet. STOP after both addresses confirm still stands.

---
BOTTOM LINE: stock reveals zero bytes of W_waiter / waiter->lock /
&f_alt.pi_mutex to shell on audited surface; LEVEL_2 stays differential-only,
not yet a measurable primitive.
