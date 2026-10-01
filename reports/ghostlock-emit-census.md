# ghostlock emit census — read-only kernel-pointer disclosure (no writes)

Date: 2026-10-01. Authority: Xiaomi Mi TV Stick 1080p (aquaman, S805Y/GXL,
Android 9, PI.2055, 4.9.113 arm64, shell uid 2000, SELinux Enforcing).
Lab instruments: build-aq/vmlinux + .src/linux-amlogic (OFFLINE_ONLY).
No kernel-memory write in this phase. No stack overwrite, no fake object,
no arbitrary R/W, no cred, no root. Read-only disclosure only.

Tools: `tools/ghostlock_emit_search.py` (new: --emit/--dev/--dispatch/
--taint/--pi/--task/--pistate/--verify/--all) +
`tools/ghostlock_emit_probe.c` (new: C1/C2/C3 safe-ioctl probes, pushed as
`/data/local/tmp/ghostlock_emit_probe`) +
`tools/ghostlock_chain.c` emit_dev (26) / emit_pi (27) (read-only open
census + PI rule, P0-P8 intact) +
`tools/ghostlock_deref_chain.py --emit` (new: FASE 13 validation ruler;
--disclosure preserved).

Prior state preserved: GhostLock, stale task->pi_blocked_on, stale waiter
traversal, FUTEX_LOCK_PI(f_chain), FULL_CHAINWALK, f_target has_waiters
gate, leftmost predicate, heap consumption, pos_cycle, H16 immutability,
h16_static baseline, f_alt.pi_mutex legitimacy, f_target vs f_alt
separation, register-only pi_state+0x10 carrier — none reopened
(cited, not re-proven).

## 1. Objective

Find ONE read-only path on stock that emits any useful kernel pointer
to shell. It does not need to be H16 or &f_alt.pi_mutex: any kernel
pointer that establishes (1) disclosure exists, (2) how the emit surface
works, (3) whether 64 bits survive, (4) whether masking applies,
(5) whether a second address can be derived from it.

Verdict up front: no such path was found on the audited surface.
SUCESSO A/B/C/D all NO (this phase). The three strongest /dev candidates
were probed on hardware and all emit only scalars, USER echoes, or
indices, with zero is_kptr hits across all outputs.
EVIDENCE: mix below per claim.

## 2. Stock /dev Census

Hardware enumeration (`ls -l /dev`, 262 nodes) plus OPEN census
(`ghostlock_chain emit_dev`: open O_RDONLY|O_NONBLOCK + close, no ioctl,
no read; and `cat` open-vs-read discriminator):

| node | major | DAC | stock OPEN |
|---|---|---|---|
| binder | 10,60 | o+rw | OPEN_OK |
| hwbinder | 10,59 | o+rw | OPEN_OK |
| ashmem | 10,61 | o+rw | OPEN_OK |
| ion | 10,57 | o+rw (system:graphics) | OPEN_OK |
| mali | 10,48 | o+rw (system:graphics) | OPEN_OK |
| xt_qtaguid | 10,54 | o+r | OPEN_OK |
| ge2d | 236,0 | system:system | DENIED errno=13 |
| vndbinder | 10,58 | o+rw | DENIED errno=13 (SELinux, DAC-open) |
| ionvideo | 270,0 | media:system o+rw | DENIED errno=13 (SELinux) |
| amvideo | 264,0 | media:system o+rw | DENIED errno=13 (SELinux) |
| cec | 501,0 | o+rw | DENIED errno=13 (SELinux) |
| vfm | 269,0 | root:root --- | DENIED errno=13 |
| null/zero | 1,* | o+rw | OPEN_OK |
| full | 1,7 | o+rw | DENIED errno=13 (SELinux; dd count=0 does NOT test open) |

Note on method: `dd count=0` does not open the input (ge2d falsely
"passed" under dd but `cat` and the C open census both report
Permission denied). Only real open() results are cited above.
EVIDENCE: HARDWARE_OBSERVED (emit_dev full output in sec. 10).

## 3. Emit Primitives

FASE 1 (`--emit`): source-wide grep counts, then field-level audit
(dataflow, not just `%p`):

* copy_to_user 3487 hits tree-wide; put_user 3977; __copy_to_user 248;
  raw_copy_to_user 0; seq_printf (fs) 745; proc_show (fs/proc) 14;
  debugfs (fs/debugfs) 386; compat_ioctl (drivers) 470;
  unlocked_ioctl (drivers/amlogic) 100; getsockopt/recvmsg present in net.
* Emit != disclosure: every reachable struct copy on the audited surface
  is scalars, USER-echo pointers, inodes/handles/ids, or masked %pK.
  Field audit lives in --dispatch/--taint, binary presence in --verify.
EVIDENCE: OFFLINE_ONLY.

## 4. Pointer Sources

FASE 4 (`--taint`): forward taint from each source to copy_to_user:

* current / task_struct *: consumers are copy_thread, scheduler, futex
  key (mm+uaddr ints), seccomp user-PC; task->stack consumers are
  fork/oops/kdb (privileged/dmesg only). NO edge to shell. NO_POINTER.
* stack (SP/x29): shell-reachable shows are %pK-masked zeros, symbols,
  or user regs. PTR_MASKED.
* rt_mutex * / waiter *: in-kernel walk only; zero copy_to_user in
  futex.c + rtmutex.c (grep: 0 hits both). NO_POINTER.
* futex_pi_state *: attach/lookup/requeue internal; syscalls return
  int/long/TID. NO_POINTER (see sec. 6/9).
* sock * / file *: sk column masked to 0; fdinfo ino/flags/pos;
  sock_diag ino/dev/qlen/path. PTR_MASKED / INDEX.
* mm / vma *: USER vmas only; pagemap PFN 0 without priv; start_stack
  is USER. USER_ECHO / INDEX.
* vendor ptrs (heaps, codec_mm, ge2d dmabuf): fds/handles/ids only;
  ge2d unreachable anyway. INDEX.
* harness heap ptrs (f_alt, occ waiters): no token-to-pi_state copy-out;
  only echo channels echo USER input. USER_ECHO.
* Priority DIRECT/PLUS/DERIVED/MASKED: none present on any
  shell-reachable emit path audited.
EVIDENCE: OFFLINE_ONLY.

## 5. /dev Candidates

FASE 2 (`--dev`): source fops per node (binder.c binder_fops,
ashmem.c ashmem_fops, ion-ioctl.c ion_fops all have
unlocked_ioctl+compat_ioctl; mali is out-of-tree, unauditable;
xt_qtaguid emits counters only; ge2d/vfm/vendored media unreachable
or disabled). FASE 10 shortlist (max 3, all shell-openable +
source-auditable + safe side-effect-free):

* C1 binder: BINDER_VERSION (scalar) + BINDER_GET_NODE_DEBUG_INFO
  (ptr/cookie USER echo rule) + BINDER_WRITE_READ (USER buffers/handles).
* C2 ashmem: ASHMEM_GET_SIZE (scalar return) + ASHMEM_GET_NAME
  (USER string, copy_to_user in get_name ashmem.c:575).
* C3 ion: ION_IOC_HEAP_QUERY cnt=0 (count scalar) + with buffer
  (name/type/id constants, copy_to_user ion.c:1221).
* Rejected: mali (openable but unauditable, needs blind ioctls);
  xt_qtaguid (counters only); ge2d/vndbinder/ionvideo/amvideo/cec/vfm
  (unreachable); mem nodes (no pointer field by construction).
EVIDENCE: OFFLINE_ONLY (fops) + HARDWARE_OBSERVED (OPEN results).

## 6. PI Emit Paths

FASE 6 (`--pi`): futex.c copy_to_user hits = 0; rtmutex.c hits = 0
(verified by grep on source). Per struct:

* futex_pi_state { pi_mutex, list }: no emitter; FUTEX_* return
  int/long/TID. NO_POINTER.
* rt_mutex { wait_lock, waiters, leftmost, owner }: walkers only;
  sched shows prio ints. NO_POINTER.
* rt_mutex_waiter { task, lock, prio, deadline, tree_entry }: birth stp
  in task_blocks_on_rt_mutex, walk reads, stores land on peer
  stacks/heap, zero copy-out. NO_POINTER (even waiter* shortcut absent).
* futex_q { rt_waiter, pi_state }: stack+heap, freed on wake. NO_POINTER.
* robust_list_head: USER echo (futex.c:3055). USER_ECHO.
* sched_attr/param: UAPI scalars. SCALAR_ONLY.
* si_ptr/si_addr: sender/user-PC sourced. USER_ECHO.
* sockaddr/ifconf/diag: bytes/caller-echo/ino. SCALAR/USER_ECHO/INDEX.
* ge2d/vfm: fds+sizes or DISABLED (-EIO). INDEX/DISABLED.
* binder_transaction_data ptr.buffer/offsets: sender USER pointers.
  USER_ECHO.
EVIDENCE: OFFLINE_ONLY.

## 7. task/current Emit Paths

FASE 7/8 (`--task`): S1 /proc/pid/stack %pK zeros; S2 wchan 0/symbol;
S3 syscall user regs; S4 kstkesp/kstkeip 0; S5 start_stack USER;
S6 net sk zeros; S7 sched scalars; S8 maps USER + pagemap PFN 0;
S9 kallsyms denied; S10 dmesg/kmsg/pstore denied; S11-S13 slab/debugfs/
tracing/sys denied; binder node ptr/cookie USER echo (tested C1 zeros);
owner TID int (INDEX, identity only, not a pointer).
No task_struct* or current-derived kernel pointer reaches shell, so no
task->stack bridge exists either.
EVIDENCE: OFFLINE_ONLY (formats) + HARDWARE_OBSERVED (prior masked
probes, re-cited not re-run).

## 8. Stack Emit Paths

Same S1-S5 channels as sec. 7 plus carrier analysis: the first real
stack references are `mrs SP_EL0` (current) and `add x29/sp` frame
bases, but no edge carries either to userspace. /proc/self/stack shows
`[<0000000000000000>]` (masked); wchan `0`; syscall user SP/PC only;
stat kstk 0 0. No raw stack word reaches shell on the audited surface.
STACK_DISCLOSURE = NOT FOUND (audited surface).
EVIDENCE: OFFLINE_ONLY + HARDWARE_OBSERVED (prior disclose_stack probe).

## 9. Candidate Ranking

1. C1 binder — best pointer-width field (ptr/cookie u64) but source
   proves USER echo (node->ptr set by creator userspace at
   BC_TRANSACTION BINDER_TYPE_BINDER; fresh fd has no nodes -> zeros).
   Safe, deterministic, repeatable. Rank 1.
2. C3 ion — heap query returns name/type/id (id is INDEX, the honest
   address-derived scalar); buffer quirk (rc=-EINVAL with filled buffer)
   is source-verified behavior, not a leak. Rank 2.
3. C2 ashmem — scalar size + USER name string; caught and fixed a wrong
   ioctl magic ('a' vs 0x77) via source, proving offline->stock loop
   works. Rank 3.
4. Everything else — unreachable or unauditable or counter-only.
EVIDENCE: OFFLINE_ONLY (ranking) + HARDWARE_REPRODUCED (values below).

## 10. Hardware Probes

P0-P5 isolated from GhostLock (no trigger), read-only. Binary
`ghostlock_emit_probe all` run 3x total (1 + 2x repeat), stable:

```
P0 READY candidate=C1 dev=/dev/binder (read-only, no trigger)
P1 OPEN fd=3 errno=0 (Success)
P2 QUERY BINDER_VERSION rc=0 errno=0 (Success) protocol=8 kptr=0
P3 CAPTURE NODE_DEBUG rc=0 errno=0 (Success)
P3 CAPTURE ptr=0 cookie=0 strong=0 weak=0
P5 VERIFY C1 ptr_kptr=0 cookie_kptr=0 ptr_like=0 (expect 0/0/0 on fresh fd: USER_ECHO zeros)
P3 CAPTURE repeat rc=0 ptr=0 cookie=0 (stability check)
P4 CLOSE fd closed
P0 READY candidate=C2 dev=/dev/ashmem (read-only, no trigger)
P1 OPEN fd=3 errno=0 (Success)
P2 QUERY ASHMEM_GET_SIZE rc=0 errno=0 (Success) kptr=0 (expect 0, scalar)
P3 CAPTURE ASHMEM_GET_NAME rc=0 errno=0 (Success) name="dev/ashmem" kptr=0 (expect USER_ECHO dev/ashmem)
P4 CLOSE fd closed
P5 VERIFY C2 scalar+user-string only (no kernel pointer by construction)
P0 READY candidate=C3 dev=/dev/ion (read-only, no trigger)
P1 OPEN fd=3 errno=0 (Success)
P2 QUERY HEAP_QUERY_CNT0 rc=0 errno=0 (Success) cnt=3 kptr=0 (expect count scalar)
P3 CAPTURE HEAP_QUERY_BUF rc=-1 errno=22 (Invalid argument) cnt=3
P3 CAPTURE heap[0] name="codec_mm_ion" type=5 id=5 kptr=0
P3 CAPTURE heap[1] name="cma_ion" type=4 id=4 kptr=0
P3 CAPTURE heap[2] name="vmalloc_ion" type=0 id=0 kptr=0
P5 VERIFY C3 name/type/id only (INDEX+SCALAR, no kernel VA by construction)
P4 CLOSE fd closed
P6 RESULT=EMIT_PROBE_DONE which=all (read-only, no trigger, no write)
```

Device identity (checked after a second unrelated device briefly
appeared on adb): serial 26919800005844922 = MiTV-AESP0 / aquaman /
PI 2055 / 4.9.113 (`getprop` + `uname`); the other serial
(GT52JM045123071J) is gone and every probe command was pinned with
`adb -s 26919800005844922`. The single unpinned command issued while
both were attached errored (`more than one device/emulator`) and
executed nothing, so no probe ever ran on the wrong device.
EVIDENCE: HARDWARE_OBSERVED.
RUN2 identical (stability). emit_dev open census (15 nodes) and emit_pi
(fstat dev=11 ino=359 index-only + PI NO_POINTER rules) also ran clean.
Side effects: open+close of own fds only; no trigger; no write.
EVIDENCE: HARDWARE_REPRODUCED (values stable 3x/2x; exact bytes above).

Two corrections found by the offline->stock loop (kept, not hidden):
(a) ashmem magic is 0x77 not 'a' (first run gave ENOTTY, source fixed
it, re-run returned 0/dev/ashmem as predicted);
(b) ion buffer query returns -EINVAL with a FILLED buffer (source
ion.c: ret stays -EINVAL on the buffer path) — the names/ids above are
real emits, the rc is a quirk, neither is a kernel pointer.

## 11. Pointer Validation

FASE 13 (`--emit` ruler): DIRECT_KERNEL_PTR needs FIELD + LOAD + COPY +
USER + MASK/identity; less stays SINGLE_SOURCE. Applied:

* C1 ptr/cookie: FIELD binder_node_debug_info.ptr/cookie; LOAD from
  node->ptr (binder.c binder_ioctl_get_node_debug_info); COPY at
  binder.c:4829; USER ioctl buffer 8B; MASK none — but identity is USER
  echo (creator-provided), and stock value is 0. Fails identity as
  kernel pointer. USER_ECHO. EVIDENCE: OFFLINE_ONLY (chain) +
  HARDWARE_REPRODUCED (zeros).
* C2 name: USER string, never a pointer. C2 size: scalar.
* C3 heap id: INDEX by construction (registry id, not VA).
* is_kptr hits across ALL C1/C2/C3 outputs: 0.
* No 0xffffff... value appeared, so no leak-vs-truth adjudication was
  needed. Nothing is SINGLE_SOURCE; everything is classified negative
  by construction + value.
EVIDENCE: OFFLINE_ONLY (ruler) + HARDWARE_REPRODUCED (zero hits).

## 12. Cross-Checks

Two independent paths per address were required; no address was
disclosed, so there is nothing to cross-check. What exists:
PATH A (stack): every /proc channel masked/denied/user-only (prior) and
every /dev candidate scalar/echo/index (this phase) — no PATH B to pair.
PATH B (heap): occupancy verdict (alt_base TIMEOUT) identifies the f_alt
object semantically but is not an address source. Any future single-path
disclosure stays SINGLE_SOURCE until a second confirmation appears.
EVIDENCE: INCONCLUSIVE (nothing to correlate).

## 13. Useful Disclosure

None. No task/stack/waiter/pi_state/rt_mutex pointer, and no unrelated
kernel pointer either, reached userspace on any probed path. USEFULNESS
classification is moot: there is no leak whose usefulness to assess.
The ion heap ids (5/4/0) and binder zeros are correctly NOT promoted to
pointers. EVIDENCE: HARDWARE_REPRODUCED (negative outputs).

## 14. Rejected Disclosure

* Masked: /proc stack, net sk, kallsyms %pK (prior, re-cited).
* Symbol/user-only: wchan, syscall user regs, kstk zeroed, start_stack
  USER, maps USER, pagemap PFN 0.
* Index-only: sched counters, diag ino, binder handles/cmds, ion heap
  id, fstat dev/ino, owner TID.
* USER echo: robust head, si_ptr, ifc buffer, binder ptr/cookie +
  transaction buffers, ashmem name.
* Scalar-only: sched_attr/param, BINDER_VERSION=8, ASHMEM_GET_SIZE=0,
  ion cnt=3, sockaddr bytes.
* Disabled: vfm GET (-EIO). Unreachable: ge2d/vndbinder/ionvideo/
  amvideo/cec/vfm/debugfs/tracing/slab/sys/dmesg (denied).
* Unauditable: mali (out-of-tree; openable but needs blind ioctls;
  explicitly NOT probed beyond open this phase).
Each rejection names the masking/permission/construction reason.
EVIDENCE: OFFLINE_ONLY + HARDWARE_OBSERVED/REPRODUCED (as marked).

## 15. What Is Proven

* Stock /dev census: 262 nodes; 6 shell-openable (binder, hwbinder,
  ashmem, ion, mali, xt_qtaguid) + null/zero; 6 denied (ge2d,
  vndbinder, ionvideo, amvideo, cec, vfm). EVIDENCE: HARDWARE_OBSERVED
  (emit_dev).
* C1/C2/C3 emit values stable: binder 8 + zeros; ashmem 0 +
  "dev/ashmem"; ion cnt 3 + (codec_mm_ion/5/5, cma_ion/4/4,
  vmalloc_ion/0/0). EVIDENCE: HARDWARE_REPRODUCED.
* Every emitted pointer-width field on C1/C2/C3 is USER echo or absent;
  every other field is scalar/index. EVIDENCE: OFFLINE_ONLY (dispatch) +
  HARDWARE_REPRODUCED (values match the predicted class).
* Zero copy_to_user of PI state (futex.c 0, rtmutex.c 0); H16 birth has
  no copy-out; pi_state+0x10 carrier stays REGISTER_ONLY.
  EVIDENCE: OFFLINE_ONLY.
* Binary presence check (--verify): SyS_sched_getattr 1, binder_ioctl 1,
  ion_ioctl 1, ion_query_heaps 1, get_name 1, PI walk funcs 0 copy/put.
  EVIDENCE: OFFLINE_ONLY.
* Probes are side-effect-free (own-fd open/close + version/query only;
  no trigger; no write; device stable). EVIDENCE: HARDWARE_OBSERVED.
* Validation ruler for any future leak defined (FIELD+LOAD+COPY+USER+
  MASK). EVIDENCE: OFFLINE_ONLY.

## 16. What Is Not Proven

* H16 absolute address on stock. EVIDENCE: INCONCLUSIVE (absent).
* &f_alt.pi_mutex value on stock. EVIDENCE: INCONCLUSIVE (absent).
* Any kernel pointer to shell on stock (SUCESSO A). EVIDENCE:
  INCONCLUSIVE-as-absent on the audited surface (not claimed everywhere).
* Paths deeper than audited: mali ioctls (unaudited, unprobed beyond
  open), unaudited amlogic ioctls on unreachable nodes, indirect
  f_op dispatch past BFS depth 3 for EMIT, novel async/alias channels.
  EVIDENCE: INCONCLUSIVE (explicitly not covered).
* Stock VAs/KASLR slide. EVIDENCE: INCONCLUSIVE.
* That the audited negatives generalize: absence on C1/C2/C3 + proc/sys/
  net/futex/sched/signal/socket/binder-sample is not absence everywhere.
  The report claims exactly the audited set, nothing more.

## 17. Next Bottleneck

Exactly one: a read-only kernel-pointer source for EITHER address that
survives stock masking. Candidates in order: (1) /dev ioctl emit census
past C1/C2/C3 for shell-openable nodes with source-auditable structs
(mali needs source first — no blind ioctl campaign); (2) re-walk
f_op/indirect dispatch past BFS depth 3 looking only for EMIT
(copy_to_user/put_user of kernel-pointer fields), never for STAMP;
(3) if either address discloses, immediately re-run the FASE 12 ruler
(--disclosure) + FASE 13 ruler (--emit) before any write thinking.
Do NOT build a stack stamper, fake object, cred/root path, or arbitrary
R/W while the addresses are unknown. The mandatory STOP after both
addresses confirm still stands; this round did not reach it.

---
BOTTOM LINE:

* direct stack disclosure? NO (proc masked; /dev C1/C2/C3 scalar/echo/index, zero kptr).
* indirect waiter/stack disclosure? NO (no waiter* edge; PI copies zero).
* H16 absolute obtained on stock? NO (INCONCLUSIVE, absent).
* direct f_alt.pi_mutex disclosure? NO (PI state never copied out).
* heap address obtained on stock? NO (object valid by occupancy, address undisclosed).
* both cross-checked? NOTHING to cross-check (no addresses; future single-source stays SINGLE_SOURCE).
* best origin of each pointer? stack: none (mrs/frame refs die in kernel); heap: pi_state+0x10 LEA register-only, zero spills.
* kernel-pointer carrier without leak? ONLY the register-only LEA (not usable as-is).
* what stays OFFLINE_ONLY? inventory dataflow, dispatch classes, carrier spill check, rulers, write spec.
* single next bottleneck? one read-only kernel-pointer source for either address (post-C1/C2/C3 /dev corners, then deeper EMIT walk).
