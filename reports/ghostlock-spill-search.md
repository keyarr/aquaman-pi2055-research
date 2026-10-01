# ghostlock spill search — controlled pointer to waiter->lock

Date: 2026-10-01. Device: Xiaomi Mi TV Stick 1080p (aquaman, S805Y/GXL,
Android 9, PI.2055, 4.9.113 arm64, PREEMPT=y, shell uid=2000, no root,
no ftrace, no kmsg). Lab authority: build-aq/vmlinux + full disassembly
dump + source. Hardware runs in this phase: 4 (pollNone, pollA, pollB,
schedA). No panic, no reboot, no fake writes in any run.

## 1. Objective

Find ONE kernel path where a userspace-controlled pointer is spilled to the
stack slot the dangling `rt_waiter.lock` occupies, i.e. `SP0-0x278`
(`SP0` = SP at syscall entry, same thread => same absolute address).
Success = `userspace pointer -> kernel register -> stack spill ->
waiter->lock -> rt_mutex_adjust_prio_chain`. No R/W primitive, no cred
work, no root in this phase.

## 2. Target Stack Geometry

From build-aq/vmlinux (verified, unchanged from ghostlock-deep-poll.md):

- FWRQ frame 0x1a0 via SyS_futex 0x70 + do_futex 0x120: waiter at
  `SP0-0x330+0x80 = SP0-0x2b0`, size 0x50.
- `waiter+0x30` task = `SP0-0x280`, `waiter+0x38` lock = `SP0-0x278`,
  `waiter+0x40` prio = `SP0-0x270`, `waiter+0x48` deadline = `SP0-0x268`.
- do_sys_poll table base = `SP0-0x2b0` (exact overlap, sys_poll path),
  but `table+0x38` = `entry0.key = events|0x18` (small int, fault
  generator, not a pointer). `table+0x40` = `wait.flags` (0).
- Window accepted: `[SP0-0x288, SP0-0x268]` (lock slot +-0x10, each
  candidate mapped byte-exact, "near" never accepted as success).

## 3. Spill Search Method

New tool `tools/ghostlock_spill_search.py` (offline, vmlinux only):

- Full-binary single disassembly (`llvm-objdump -d`, 3.7M lines, cached)
  instead of per-symbol calls; `SyS_`/`sys_` alias normalization.
- Frame size from first `sub sp,sp,#imm` / `stp [sp,#-imm]!`.
- Intra-function forward taint: `x0-x5` = DIRECT_USER_ARG at entry;
  `mov`/`add`-family/`csel`-family/`sxtw` propagate with transform notes;
  `ldr` from tainted base = USER_BUFFER_DERIVED; `str`/`stp` to
  `[x29/sp,#off]` recorded with origin + detail chain; `bl` snapshots
  `x0-x7` and kills `x0` (return value). Loads never kill taint
  (path-insensitivity: an epilogue restore on a not-taken path must not
  erase a live pointer; false positives are hand-filtered, false
  negatives are not recoverable).
- Call graph via direct `bl` targets, BFS depth 3 from every `SyS_` root
  (303 roots). SP0-relative destination:
  `dest = SP0 - sum(frames on path) + local_off`.
  `stp` counts as two consecutive 8B words. Indirect `blr` (driver
  dispatch) handled separately by `--ioctl` mode with fixed chain
  `SyS_ioctl(0x40) > do_vfs_ioctl(0x80) > vfs_ioctl(0x30) > vendor`
  (vendor entry `x2` = ioctl arg = fully controlled pointer).
- Modes: `--frames`, `--deep`, `--func`, `--chain`, `--all`,
  `--ioctl <vendor>`, `--verify`.

## 4. Dataflow Rules

- KEEP: DIRECT_USER_ARG with no transform beyond register moves;
  USER_BUFFER_DERIVED only if the loaded field is a full 64-bit pointer
  stored by `copy_from_user` with no masking/shift/page arithmetic.
- DROP with explicit reason: 32-bit truncation (`str wN`, `ldrh`,
  `w`-loads), `and`/`lsr` masking, `+offset` arithmetic on the pointer,
  kernel-heap result (`kmalloc`, `filp`, `sock`, `current`), slab/page
  struct pointers after page arithmetic, error-path-only execution
  (`printk` after `__check_object_size` failure), privileged-only
  syscalls (`bpf` needs CAP_SYS_ADMIN), graph-destroying or blocking
  paths, stores overwritten by the next call's prologue before return.

## 5. Candidate Table

`--all` (depth 3, window +-0x10): 87 candidates. Grouped by class;
exact `SP0-0x278` hits: 8. NO candidate survived review (section 6).

| # | root | function (path) | store | dest | origin (tool) | verdict |
|---|---|---|---|---|---|---|
| 1 | SyS_madvise | `__alloc_pages_nodemask` (via readahead x3) | `str x0,[x29,#0x98]` sumF=0x310 | SP0-0x278 | USER_BUFFER_DERIVED | REJECT 6a |
| 2 | SyS_mincore x4 | `get_page_from_freelist` (via alloc x3) | `str xN,[x29,#0xa8]` sumF=0x320 | SP0-0x278 | USER_BUFFER_DERIVED | REJECT 6a |
| 3 | SyS_process_vm_readv/writev | `process_vm_rw_core.isra.0` | `str x1,[x29,#0xa8]` sumF=0x320 | SP0-0x278 | USER_BUFFER_DERIVED | REJECT 6b |
| 4 | SyS_select | `printk` (via `__check_object_size`) | `stp x2,x3,[x29,#0x70]` sumF=0x2f0 | SP0-0x280/0x278 | DIRECT_USER_ARG | REJECT 6c |
| 5 | SyS_renameat2, SyS_select, SyS_io_setup, SyS_finit_module | `printk`/`warn_alloc` (error paths) | various `stp` | SP0-0x258..0x298 | DIRECT_USER_ARG | REJECT 6c |
| 6 | SyS_process_vm_readv/writev, SyS_madvise/mincore | `__slab_free`, `__alloc_pages_nodemask`, `sort`, `get_page_from_freelist` | various | SP0-0x258..0x298 | USER_BUFFER_DERIVED | REJECT 6a |
| 7 | SyS_bpf | `do_check`, `fixup_bpf_calls` | `str x0,[x29,#0x60]` sumF=0x2d0 etc | SP0-0x270/0x268/0x260 | USER_BUFFER_DERIVED | REJECT 6d |
| 8 | SyS_sendmsg | `cmsghdr_from_user_compat_to_kern` | `stp x1,x2,[x29,#0x60]` sumF=0x2d0; `str x0,[x29,#0x78]` | SP0-0x270/0x268/0x258 | USER_BUFFER_DERIVED | REJECT 6e |
| 9 | SyS_vmsplice | `iov_iter_advance` | `str x1,[x29,#0x68]` sumF=0x2c0 | SP0-0x258 | USER_BUFFER_DERIVED | REJECT 6f |
| 10 | SyS_recvmsg/recvmmsg | `get_compat_msghdr` | `str x1,[x29,#0x60/0x68]` sumF=0x2a0/0x320 | SP0-0x240/0x2c0 | DIRECT/USER_BUFFER | REJECT 6g |
| 11 | SyS_remap_file_pages | `__lock_page` | `str x19,[x29,#0x20]` sumF=0x2a0 | SP0-0x280 | DIRECT_USER_ARG | REJECT 6a |
| 12 | 22 vendor ioctls (`--ioctl` batch) | `ge2d`, `dvb_*`, `osd`, `amstream_*`, `amvenc`, `mmc`, `mtd`, `gdc`, ... | none in window; nearest `amstream_do_ioctl_old` `stp x1,x2,[x29,#0x48]` sumF=0x2a0 -> SP0-0x258 | - | DIRECT_USER_ARG | REJECT 6h |

## 6. Rejected Candidates (explicit reasons)

- 6a MM/slub/sort (`__alloc_pages_nodemask`, `get_page_from_freelist`,
  `__slab_free`, `__lock_page`, `sort`): values are `struct page *` /
  slab internals after page arithmetic (`and`/`lsr`/`add`), i.e. kernel
  heap pointers, never the user address; paths allocate, sleep, and take
  allocator locks. Not controllable, heavy side effects.
- 6b `process_vm_rw_core.isra.0 +0xa8` (exact slot): `x1 =
  min(pinned<<12 - off, iov_len)` = a small byte COUNT, not a pointer
  (verified in disassembly around 0x...b634-0x...b640). The nearby
  `+0xb8` (prio slot, SP0-0x268) holds `iov_base & ~0xFFF`, but the
  syscall pins foreign-mm pages (`mm_access`, `get_user_pages`, sleeps)
  and the lock slot itself gets the int. Wrong slot + int + heavy path.
- 6c `printk`/`warn_alloc` family (all 10 DIRECT_USER_ARG hits): reached
  only when `__check_object_size` FAILS (error return path); spilled
  values are sizes/counts after `sxtw/add/lsr/lsl` chains (e.g. pselect
  `nfds` mangling), never pointers. Error-path ints.
- 6d `bpf do_check`/`fixup_bpf_calls`: values are BPF insn
  immediates/offsets after decode (`and`/`add`); `bpf()` requires
  CAP_SYS_ADMIN (shell has none). Privileged + ints.
- 6e `cmsghdr_from_user_compat_to_kern` (hand-verified callsite at
  `___sys_sendmsg+0x1f0`): entry `x1` = `sock->...` (kernel heap),
  `x2` = `x29+0x58` (own stack) — the tool's linear taint merged an
  earlier `x1` definition with the callsite (path-insensitivity false
  positive, documented). Kernel pointers, plus a later `sock_sendmsg`
  (frame 0x30) prologue reuses `[SP0-0x270,SP0-0x240)`, clobbering the
  pair before return. Rejected on value AND survival.
- 6f `iov_iter_advance`: values transformed through pipe-buffer structs
  (`ldr` chains + `sub`); kernel pipe internals. Not a user pointer.
- 6g `get_compat_msghdr` (hand-verified): stores are `str w1` (32-bit)
  of compat-struct int fields (`msg_namelen`-class); gated on
  `MSG_CMSG_COMPAT`. 4B ints, and bracketed geometrically (recvmsg cum
  0x2a0 -> SP0-0x240, recvmmsg cum 0x320 -> SP0-0x2c0, no middle caller).
- 6h vendor ioctls: 22 functions with frame >= 0x120 scanned, zero
  tainted spills in window. Nearest is `amstream_do_ioctl_old +0x48`
  (SP0-0x258, 0x20 short of lock; `+0x28` would be exact but is a
  prologue callee-saved slot). An extra wrapper (`amstream_ioctl 0x30 >
  amstream_do_ioctl 0x60`) moves it to SP0-0x2E8 (overshoot). All vendor
  paths program video/display/storage hardware (side effects
  unacceptable for a stamper) and need device nodes with unknown shell
  permissions. Class rejected, not one function misread.
- 6i FWRQ self-overlap (same-function idea, hand-verified): prologue
  never spills `x0-x5`; `str xzr,[x29,#0xb0]` zeroes waiter+0x30, slot
  `+0xb8` (lock) is never written on the EAGAIN path, `+0x80`/`+0x188`
  get kernel stack addresses. No user pointer, so same-layout restamping
  via instant-EAGAIN `FUTEX_WAIT_REQUEUE_PI` cannot work. (EAGAIN path
  itself is side-effect-free, but there is nothing to deliver.)

## 7. Best Candidate

None exact. Nearest with a clean pointer: `amstream_do_ioctl_old +0x48`
(SP0-0x258, DIRECT_USER_ARG pair, 0x20 off). Not pursued: wrong slot with
no arg-controlled alignment knob, hardware side effects, wrapper-depth
overshoot. The honest result of this round is RESULT C (section 12).

## 8. Offline Verification

- `ghostlock_spill_search.py --verify`: 3/3 poll-table stores OK.
- `--frames`: 303 `SyS_` roots ranked (top: recvfrom 0x140, sendto 0x130).
- `--deep`: 418 functions with frame >= 0x100 (vendor ioctls 0x1a0-0x550,
  `do_sys_poll` 0x410, `do_select` 0x3a0, `___sys_sendmsg` 0x180).
- `--all` run twice (before/after `csel`-family taint fix): 84 -> 87
  candidates; the 3 new ones are MM-class (6a). Fix did not promote any
  DIRECT pointer into the window.
- Every exact-slot store (8) hand-disassembled at its VA; values traced
  to ints/kernel pointers (section 6). No byte-layout ambiguity remains
  for the listed stores.

## 9. Device Probe

Same boot, VAR B fake, pad 0x0, rebuilt `ghostlock_chain` (adds `schedA`
mode + waiter TID publish; `pipe()` gate fixed to `g_mode >= 4` after a
first schedA run queued no fd — that run is discarded for the reach
question and noted here so the log is not misread):

1. `pollNone`: P2 EDEADLK(35), P4 STAMP_SKIPPED, P5 entered, P6
   `HANG_IN_WALK`, fake `+0x08/+0x10` zero. Control as predicted.
2. `pollA` (ev=0x4141 key=0x4159, fd=3 valid): identical HANG, no P6
   absence, no panic, no reboot. FAIL vs pre-registered prediction.
3. `pollB` (ev=0x4242 key=0x425A): identical HANG. No A/B divergence.
4. `schedA` (pollA stamp + `sched_setscheduler(waiter,SCHED_OTHER)` rc=0
   after hang): still HANG, no panic, uptime continuous. The MIN walk
   (`rt_mutex_adjust_pi`, `pi=true` on the syscall path, verified in
   source) also shows nothing.

`schedB` not run: with schedA silent it carries no information
(silence vs silence); recorded as a deliberate skip, not an omission.

## 10. GhostLock Integration

Not performed. No spill was demonstrated in isolation (PASSO 10 gate),
so no `spill0` mode was added to `ghostlock_chain.c` (a stub driving no
candidate would be dead code). The only harness additions are the
`schedA/schedB` tiebreaker modes + TID publish, kept because they test
the consumer side, not a spill.

## 11. Fault Interpretation

No fault occurred in 4 runs, so there is nothing to correlate — and per
PASSO 13 this is stated plainly: no `0x4141/0x425A` fault, no
FULL_CHAINWALK proof, no fake consumption, no R/W primitive. The HANGs
are ambiguous between (i) table missed the slot (stock frames differ
from lab build-aq), (ii) no stale waiter exists (consumer never walks),
(iii) walk runs on the natural stale lock (writes land in kernel
memory, invisible; consumer blocks on it). The `schedA` silence rules
out "MIN walk reaches trylock on stamped bytes" but does not separate
(i)-(iii). No claim beyond this is made.

## 12. Conclusion

RESULT C (spill incapable) for the offline search + reach unproven on
device. Concretely:

- 87 window candidates exist; 8 hit `SP0-0x278` exactly; 0 carry a
  controlled 64-bit user pointer (all are small ints, 32-bit fields,
  kernel heap/stack pointers, or page/slab pointers).
- 22 vendor ioctls scanned via the indirect chain; 0 hits.
- poll table reaches per LAB binary but the device shows no effect
  (HANG x4, no panic), so either the lab frame model does not match
  stock PI.2055 or the consumer never walks.
- The problem therefore moves from "find the spill" to "prove the walk":
  without an observable consumer, no stamper can be validated, and
  without a validated stamp geometry, the spill search has no ground
  truth. That transition is made explicitly here.

## 13. Next Bottleneck

Prove or kill the stale pointer WITHOUT any stamper: the single cheapest
discriminator left is a consumer that returns instead of blocking — e.g.
consumer `FUTEX_LOCK_PI` with a timeout (`ETIMEDOUT` + return value
distinguishes EDEADLK-bail from plain block), or walking the owner side
(`FUTEX_UNLOCK_PI`/`WAKE` patterns that make `task_blocks` return
`EDEADLK` to the consumer, which proves the walk RAN and read the stale
slot). Only after the walk is observable does another spill round make
sense; the next spill round should then target `SP0-0x280`/`SP0-0x270`
pairs too (a `stp` covering lock+prio with one controlled word is
enough for FULL, which ignores prio), and should re-derive stock frames
from the device (frame sizes are config-dependent; lab == stock is now
suspect #1 for the poll miss).

---
BOTTOM LINE (per-round summary)

- Spill candidates in window: 87 (depth<=3, all SyS_ roots) + 22 vendor
  ioctls via indirect chain; exact-slot hits: 8.
- With truly controllable 64-bit user-pointer origin: 0. Nearest clean
  pointer (`amstream_do_ioctl_old +0x48`) misses by 0x20 and programs
  hardware.
- Best "exact" stores are an iov length int (process_vm), slab/page
  pointers (mm), error-path ints (printk), BPF immediates (privileged),
  kernel sock/stack pointers (cmsg), 32-bit compat ints (get_compat).
- Device: pollNone/pollA/pollB/schedA all HANG_IN_WALK, zero fake
  writes, zero panics, zero reboots. VAR A/B divergence: none (no
  candidate to drive it).
- Pointer did NOT reach waiter->lock by any path tested.
- Real next bottleneck: the consumer walk itself is unobserved on
  device (stale pointer unproven); prove it with a returning consumer
  (timeout/EDEADLK) before any further stamp work, and re-derive stock
  frames (lab==stock now suspect).
