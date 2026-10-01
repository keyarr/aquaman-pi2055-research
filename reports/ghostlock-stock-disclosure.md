# ghostlock stock disclosure — READ/DISCLOSE phase (no writes)

Date: 2026-10-01. Authority: Xiaomi Mi TV Stick 1080p (aquaman, S805Y/GXL,
Android 9, PI.2055, 4.9.113 arm64, shell uid 2000, SELinux Enforcing).
Lab instruments: build-aq/vmlinux + .src/linux-amlogic (OFFLINE_ONLY).
No kernel-memory write in this phase. No stack corruption, no fake object,
no root, no arbitrary R/W. Read-only disclosure only.

Tools: `tools/ghostlock_disclosure.py` (new: --proc/--copy/--stack-flow/
--heap/--verify/--all) + `tools/ghostlock_deref_chain.py --disclosure`
(new: disclosed-target -> known-consumer ruler, FASE 12) +
`tools/ghostlock_chain.c` disclose modes 23/24/25 (read-only probes +
FASE 11 harness, binary rebuilt and pushed as
`/data/local/tmp/ghostlock_disclose`).

Prior state preserved: GhostLock, stale task->pi_blocked_on, stale waiter
traversal, FUTEX_LOCK_PI(f_chain), FULL_CHAINWALK, f_target has_waiters
gate, leftmost predicate, heap consumption, pos_cycle, H16 immutability,
h16_static baseline, f_alt.pi_mutex legitimacy, f_target vs f_alt
separation — none reopened (cited, not re-proven).

## 1. Objective

Decide whether the two absolute addresses needed for a future
`WRITE8(H16_addr, F_alt_addr)` can be obtained read-only on stock:

* STACK: absolute address of `[W_waiter + 0x38]` (live kernel stack slot).
* HEAP: absolute address of `&f_alt.pi_mutex` (heap rt_mutex).
* RELATION: each disclosed value must be shown to be the same object the
  chainwalk consumes (not two plausible-but-unlinked pointers).

Verdict up front: neither disclosure exists on the audited surface.
STACK_DISCLOSURE and HEAP_DISCLOSURE stay INCONCLUSIVE-as-absent
(no candidate survived to probe). The read-only phase therefore closes
with a documented negative, one SINGLE_SOURCE-adjacent identity rule
(f_alt occupancy verdict), and a ready FASE 11 harness. EVIDENCE: mix
below per claim.

## 2. Stock Authority

Device: `Linux version 4.9.113 (jenkins@c5-mitv-cm-build06.bj) gcc 6.3.1`
`PI/2055 user/release-keys`, `Enforcing`, shell `u:r:shell:s0`.
Config facts (`aquaman-config`): `KALLSYMS=y`, `KALLSYMS_ALL=y`,
`KALLSYMS_BASE_RELATIVE=y`, `IKCONFIG_PROC=y`, `DEBUG_FS=y`,
`PROC_PAGE_MONITOR=y`, `PERF_EVENTS=y` (paranoid 3 on stock),
`TASKSTATS=y`, `SCHED_DEBUG=y`, `SCHEDSTATS=y`, `FRAME_POINTER=y`.

FASE 0 baseline re-ran FIRST on stock this round (`h16_static`, 4th
overall counting history, pad 0x0, VAR B):

```
P0 READY var=B mode=h16_static pad=0x0 fake=0x7faf710000 win=0x2740c0
P1 TRIGGER_ENTER cmp_requeue_pi f_wait->f_target
P2 EDEADLK errno=35
P3 GRAPH_PRESERVED no_teardown waiter_keeps_f_chain owner_blocked
   fwrq_alive=1 fwake_errno=22
P4 NO_STAMP in_window sp_futex=0x7d9e462b80 waiter_est_lab=0x7d9e4628d0
   (NOT a stock offset)
P4 OCCUPANCY_ARMED occ_n=0 occ2_parked=0
P4 ALT_ARMED a_armed=1 alt_go=1 alt_parked=1 f_alt=2147496858
P5 LOCK_PI_DONE rc=-1 errno=110 elapsed_ms=3000
P5b LOCK_PI_TARGET_DONE rc=-1 errno=110 elapsed_ms=3000
P6 RESULT=TIMEOUT_BLOCK mode=h16_static target=f_chain
```

Slot static across the H16.4/H16.7 window on the same live frame.
EVIDENCE: HARDWARE_REPRODUCED.

## 3. Stack Disclosure Candidates

FASE 1 inventory (taint backward OUTPUT USERSPACE <- kernel field <-
pointer source). Full table from `--proc`; summary:

| # | interface | format / dataflow | class | stock result |
|---|-----------|-------------------|-------|--------------|
| S1 | /proc/pid/stack | `[<%pK>] %pB` (base.c:472) | masked pointer + symbol | all `0000000000000000` |
| S2 | /proc/pid/wchan | symbol or `0` (base.c:411) | symbol, never address | `0` |
| S3 | /proc/pid/syscall | nr + 6 user args + user sp/pc `%lx` (base.c:642) | user regs (non-pointer wrt kernel) | user SP only |
| S4 | /proc/pid/stat kstkesp/kstkeip | zeroed unless PF_DUMPCORE (array.c:436) | non-pointer metadata | fields 29/30 = `0 0` |
| S5 | /proc/pid/stat start_stack | `mm->start_stack` (user) | user pointer | user stack |
| S6 | /proc/net/unix,tcp,packet | `sk` column | masked pointer | `0000000000000000` |
| S7 | /proc/pid/sched,schedstat | counters + policy/prio | non-pointer metadata | readable, no pointers |
| S8 | maps/smaps/pagemap | user VMAs; PFN needs priv | user + index only | PFN reads `0` |
| S9 | /proc/kallsyms | %pK-gated, kptr_restrict | masked/unreachable | Permission denied |
| S10 | dmesg/kmsg/pstore | dmesg_restrict + SELinux | unreachable | all Permission denied |
| S11 | /sys/kernel/slab/* | attrs | unreachable metadata | every attr Permission denied |
| S12 | /sys/kernel/debug,tracing | — | unreachable | Permission denied |
| S13 | /proc/sys/kernel/* | tunables incl. kptr_restrict | unreachable | listing Permission denied |
| S14 | binder debug | — | unreachable | Permission denied |
| S15 | unix/netlink diag | ino/dev/qlen/path (diag.c) | index only | no pointer field by source |

No candidate above yields a kernel-stack pointer to shell.
EVIDENCE: OFFLINE_ONLY (formats) + HARDWARE_OBSERVED (each stock denial/
masking above was read on the device this round).

## 4. Heap Disclosure Candidates

FASE 6 inventory (ideal `f_alt -> pi_state -> pi_mutex -> userspace`).
Full table from `--heap`; summary: PI state never copied out (zero
`copy_to_user` in futex.c/rtmutex.c); robust list is a USER echo;
sched/signal/socket copies are scalars, sender-controlled si_ptr, or
address bytes; SIOCGIFCONF echoes the caller buffer; unix diag emits
inodes; ge2d ioctls return dma-buf fds (and `/dev/ge2d` is not
shell-openable: `system:graphics`); vfm GET is compiled out
(`return -EIO`, copy commented); binder returns handles.
No `f_alt.pi_mutex -> userspace` edge exists on the audited surface.
EVIDENCE: OFFLINE_ONLY (source structs + binary `--verify` counts).

## 5. Pointer Dataflow

FASE 2 (struct -> copy_to_user -> userspace) per candidate: struct,
field, offset, copy site, syscall, reachability, masking, width,
KASLR transform, userspace control — see `--copy` output (10 rows).
Heads: `get_robust_list` echoes a `__user` head (source futex.c:3055);
`sched_attr`/`sched_param` are scalar-only by UAPI; `siginfo.si_ptr`
is sender/user-PC sourced, never waiter/stack/rt_mutex; `sockaddr`
and `ifconf` carry addresses/USER echo; diag carries inodes.
FASE 3 (current/stack/waiter auto-reference): `current->mm` + user
uaddr flow into the futex key (ints, never `task->stack`);
`task_stack_page()` consumers are fork/oops/kdb (privileged-only);
`futex_q.rt_waiter` never leaves the kernel; `KSTK_EIP/ESP` in
seccomp/audit are USER pc/sp; no `current->stack -> copy_to_user`
edge exists. FASE 4 (indirect inference): no interface on the
audited surface branches on the kernel stack address in a
shell-observable way; the old futex timing oracle is NOT rebuilt
(per phase rule, timing is not an address proof).
EVIDENCE: OFFLINE_ONLY.

## 6. Rejected Disclosure Paths

Per path: masked (S1 stack, S6 net sk, S9 kallsyms %pK); symbol-only
(S2 wchan); user-regs-only (S3 syscall user sp/pc, S4 kstk zeroed,
S5/S8 user VMAs, pagemap PFN 0); index-only (S7 sched counters, S15
diag ino, binder handles); USER echo (robust head, si_ptr,
ifc_buf); scalar-only (sched_attr/param, sockaddr); disabled
(vfm GET); privileged-only (task_stack_page consumers, debugfs,
tracing, slab attrs, sys tunables, dmesg/kmsg/pstore).
Vendor ioctl sweep (ge2d/vfm/media): fds + sizes or disabled; no
`rt_mutex *` field in any shell-reachable struct. Each rejection
names the masking/permission check that kills it; none is rejected
by assertion. EVIDENCE: OFFLINE_ONLY + HARDWARE_OBSERVED (denials).

## 7. Stack Disclosure Probe

FASE 5. New read-only harness mode `disclose_stack` (23): no trigger,
no stamp, no fake, no write. Stock output (this round, twice stable):

```
P0 READY var=B mode=disclose_stack (read-only, no trigger, no write)
P4 DISCLOSE STACK /proc/self/stack: "[<0000000000000000>] walk_stackframe+0x58/0x58"
P4 DISCLOSE WCHAN /proc/self/wchan: "0"
P4 DISCLOSE SYSCALL /proc/self/syscall: "63 0x3 0x7dd5536150 0x400 ... (user regs)"
P4 DISCLOSE STAT /proc/self/stat: "... 29:0 30:0 (kstkesp/kstkeip zero)"
P4 DISCLOSE ROBUST rc=0 errno=0 head=0x0 len=24 kptr=0 (USER echo)
P4 DISCLOSE SCHED_GETPARAM rc=0 errno=0 prio=0 (scalar)
P4 DISCLOSE GETSOCKNAME rc=0 alen=2 bytes0=01000000 (addr bytes)
P6 RESULT=DISCLOSURE_PROBE_DONE mode=disclose_stack
```

Repeat run: identical masking (STACK zeros, WCHAN 0, only user addresses
vary by ASLR). No 64-bit kernel pointer in any output; `is_kptr()`
fires on nothing. FASE 13 note: the first real reference to the stack
address is `mrs SP_EL0` (current) and `add x29/sp` frame bases, but no
edge carries either to userspace — so even a `waiter *` shortcut (which
would suffice: H16 = waiter+0x38) is not disclosed either.
EVIDENCE: HARDWARE_OBSERVED (probe) + OFFLINE_ONLY (dataflow).

## 8. Heap Disclosure Probe

New mode `disclose_heap` (24): same read-only set plus the heap rule.
Stock output matches disclose_stack (all masked/scalar/USER echo) plus:

```
P4 DISCLOSE HEAP_RULE f_alt identity = occupancy verdict
   (alt_base TIMEOUT_BLOCK 3000ms), not a pointer;
   SINGLE_SOURCE until a second path confirms
```

f_alt signature (kept, not reopened): owner A holds f_alt + 1 parked
altocc waiter; `alt_base` (consumer f_alt timed, no trigger)
TIMEOUT_BLOCK 3000ms proves a valid contended rt_mutex;
`alt_only` (f_target empty + f_alt occupied) TIMEOUT ignores f_alt;
`alt_tgt` (f_target occupied + f_alt occupied) EDEADLK follows f_target.
These verdicts identify the OBJECT semantically but disclose no ADDRESS:
they are the reason a future heap address, once disclosed, can be
checked — not a disclosure themselves. FASE 14 note: the kernel already
carries `pi_state->pi_mutex` as the `+0x10` LEA in registers
(attach 0x9614, requeue 0xabe4, lock_pi 0xb1b8/0xb238/0xb2a0), but the
`--rtmutex` spill check shows the LEA reg dies in registers/epilogue
and never lands on a reusable stack slot — documented as a
register-only carrier, not a leak, and NOT written in this phase.
EVIDENCE: HARDWARE_OBSERVED (probe) + HARDWARE_REPRODUCED (occupancy
history) + OFFLINE_ONLY (LEA/carrier dataflow).

## 9. Cross-Validation

Two independent paths per address were required; neither address was
disclosed, so there is nothing to cross-check. What exists:
PATH A (stack): every /proc channel masked/denied/user-only — no PATH B
to pair. PATH B (heap): occupancy verdict identifies the object, but it
is not an address source, so it cannot pair with a (nonexistent) pointer
disclosure either. Any future single-path disclosure stays
SINGLE_SOURCE until a second confirmation appears. No claim is treated
as truth on one path. EVIDENCE: INCONCLUSIVE (nothing to correlate).

## 10. H16 Address

Not obtained. No absolute address, no stock-relative offset beyond the
existing conjecture (`SP0-0x290`, waiter `SP0-0x2c8`, STOCK
INCONCLUSIVE), no equivalent representation sufficient to address the
slot. `STACK_DISCLOSURE = NOT FOUND (audited surface)`.
EVIDENCE: HARDWARE_OBSERVED (probes) + OFFLINE_ONLY (inventory).

## 11. f_alt Address

Not obtained. `&f_alt.pi_mutex` has no read-only path to userspace on
the audited surface. The object is legitimate and live (occupancy
proof), but its ADDRESS stays undisclosed.
`HEAP_DISCLOSURE = NOT FOUND (audited surface)`.
EVIDENCE: HARDWARE_OBSERVED (probes) + HARDWARE_REPRODUCED (validity)
+ OFFLINE_ONLY (inventory).

## 12. Read-Only Consumer Validation

`--disclosure` ruler (new in deref_chain.py, FASE 12): any future
H16_addr must equal walk base x28 at H16.7 (`0x4df0 ldr x0,[x28,#0x38]`)
with value equality against x20 at `0x4df4 cmp` (and against the H16.4
`0x52fc` x25 read — same 8 bytes twice); any future F_alt_addr must
equal `pi_state_alt+0x10` with trylock-free `+0x00`, occupied `+0x10`
whose top `+0x38` reads back the same address, and non-NULL owner
`+0x18`. Verified as a RULER only (offline mapping, no addresses to
feed it). `DISCLOSED TARGET -> KNOWN CONSUMER = NOT CLOSED`
(nothing disclosed yet). EVIDENCE: OFFLINE_ONLY.

## 13. Future Targeted Write

FASE 10 classification (chosen after the negative result): A
(userspace must know F_alt_addr as an immediate) vs B (a future
primitive reads it from a kernel structure directly). Answer: UNDECIDED
— A needs both disclosures (absent); B needs a kernel-pointer carrier
with dest+value control (the only known carrier, `pi_state+0x10` LEA,
is register-only with zero stack spills, so B has no binary support
today either). FASE 11 harness (mode `disclose_write8`, 25) accepts
both values as hex parameters and checks size (fixed 8B), alignment
(8B both), kptr heuristic notes, lifetime rule (frame alive across
H16.4+H16.7), and consumer mapping — WITHOUT touching memory:

```
P4 WRITE8_SPEC h16=0xffffffc012345678 falt=0xffffffc087654320
P4 WRITE8_SIZE 8 (single word [W_waiter+0x38])
P4 WRITE8_LIFETIME frame-alive required ... NOT verified here (no write)
P4 WRITE8_CONSUMER H16.7 ... h16 == x28 base, falt == x0/x20 value
P4 WRITE8_ACCEPT spec well-formed (telemetry only, NO memory touched)
```

Malformed input is rejected (`null`, `unaligned` cases probed on
stock). No `WRITE8` was performed. EVIDENCE: HARDWARE_OBSERVED
(harness runs) + OFFLINE_ONLY (spec).

## 14. What Is Proven

* h16_static baseline again on stock (TIMEOUT+TIMEOUT, live frame).
  EVIDENCE: HARDWARE_REPRODUCED (4th overall).
* Every shell-reachable /proc/sysfs/debugfs/net disclosure channel is
  masked, denied, user-only, scalar, index-only, USER echo, disabled,
  or privileged-only (S1-S15 table + stock denials).
  EVIDENCE: HARDWARE_OBSERVED + OFFLINE_ONLY.
* Every reachable `copy_to_user` struct is scalar/USER-echo/index, and
  the PI path has zero struct copies (futex.c/rtmutex.c grep).
  EVIDENCE: OFFLINE_ONLY + HARDWARE_OBSERVED (probe outputs).
* No `current->stack` / waiter * / kernel-SP edge to userspace exists;
  even the weaker `waiter *` shortcut is undisclosed.
  EVIDENCE: OFFLINE_ONLY.
* f_alt is valid+contended (occupancy) but address-undisclosed; the
  `pi_state+0x10` carrier is register-only (zero spills).
  EVIDENCE: HARDWARE_REPRODUCED + OFFLINE_ONLY.
* Read-only probes (23/24) and write harness (25) run cleanly with no
  panic, no write, no trigger. EVIDENCE: HARDWARE_OBSERVED.
* Consumer ruler for both addresses is defined read-only.
  EVIDENCE: OFFLINE_ONLY.

## 15. What Is Not Proven

* H16 absolute address on stock. EVIDENCE: INCONCLUSIVE (absent).
* `&f_alt.pi_mutex` value on stock. EVIDENCE: INCONCLUSIVE (absent).
* Any cross-check between the two (nothing to correlate).
  EVIDENCE: INCONCLUSIVE.
* Paths deeper than the audited surface (indirect f_op dispatch beyond
  BFS, unreviewed vendor ioctls beyond the 22+ge2d/vfm sample, novel
  async/alias channels that EMIT pointers — the closed set was
  write-oriented; the emit-oriented set reviewed here is
  proc/sys/net/futex/sched/signal/socket/binder/ge2d/vfm).
  EVIDENCE: INCONCLUSIVE (explicitly not claimed covered).
* Stock VAs/KASLR slide. EVIDENCE: OFFLINE_ONLY / INCONCLUSIVE.

## 16. Remaining Ambiguity

Exactly one per address, both the same shape: absence on the audited
surface is not absence everywhere. The inventory covered the
shell-reachable read-only surface systematically (proc, sysfs, debugfs,
net, futex, sched, signal, socket, binder, sampled vendor ioctls), but
a full ioctl census across every world-accessible `/dev` node was not
run, and indirect/dispatch-heavy paths (f_op chains past depth 3) were
not exhaustively walked for EMIT (only for STAMP in the prior round).
Either address could in principle surface from an unaudited corner;
neither did from any probed one. The occupancy verdict is the sole
heap-identity signal and it is deliberately NOT called a disclosure.

## 17. Next Bottleneck

Exactly one: a read-only kernel-pointer source for EITHER address that
survives stock masking. Candidates in order: (1) finish the `/dev`
ioctl emit census for shell-openable nodes (open test + struct-field
audit per ioctl, same copy_to_user discipline as FASE 2); (2) re-walk
f_op/indirect dispatch past BFS depth 3 looking only for EMIT
(copy_to_user/put_user of kernel-pointer fields), never for STAMP;
(3) if either address discloses, immediately re-run the FASE 12 ruler
before any write thinking. Do NOT build a stack stamper, fake object,
cred/root path, or arbitrary R/W while the addresses are unknown —
there is no target to write and no value to write yet. The mandatory
STOP after both addresses confirm still stands; this round did not
reach it.

---
BOTTOM LINE:

* direct stack disclosure? NO (all /proc channels masked/denied/user-only; probes show zeros).
* indirect waiter/stack disclosure? NO (no waiter * edge; even the weaker shortcut is absent).
* H16 absolute obtained on stock? NO (conjecture SP0-0x290 unchanged, INCONCLUSIVE).
* direct f_alt.pi_mutex disclosure? NO (PI state never copied out; all struct copies scalar/echo/index).
* heap address obtained on stock? NO (object valid by occupancy verdict, address undisclosed).
* both cross-checked? NOTHING to cross-check (no addresses; future single-source stays SINGLE_SOURCE).
* best origin of each pointer? stack: none found (mrs/frame refs die in kernel); heap: pi_state+0x10 LEA, register-only carrier, zero spills.
* kernel-pointer carrier without leak? ONLY the register-only LEA (no stack landing, not usable as-is).
* what stays OFFLINE_ONLY? inventory dataflow, rejection formats, carrier spill check, consumer ruler, write spec.
* single next bottleneck? one read-only kernel-pointer source for either address (/dev emit census, then deeper EMIT walk).
