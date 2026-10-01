# ghostlock deep poll stamper

Date: 2026-10-01. Device target: Xiaomi Mi TV Stick 1080p (aquaman, S805Y/GXL,
Android 9, PI.2055, 4.9.113, arm64, PREEMPT=y). Lab authority:
build-aq/vmlinux + DWARF + source (build-aq/source). No device run in this
phase; every address below is verified in the lab binary, device section is
an explicit prediction with pass/fail criteria.

## 1. Objective

Answer one question: can a controlled difference between VAR A and VAR B be
placed in the kernel-stack interval where the dangling `rt_waiter` resides,
using `do_sys_poll` as stamper, inside the preserved protocol
trigger -> EDEADLK -> graph preserved -> stamp -> single FUTEX_LOCK_PI?
No root, no cred overwrite, no arbitrary R/W in this phase. Success is reach
proof (A/B divergence correlated with waiter position), not exploitation.

## 2. Poll Stack Layout

SP0 = SP at SyS_ entry. Same thread, same kernel stack page, same pt_regs
save => SP0 is the same absolute address for every syscall. All offsets below
are SP0-relative, sys_poll path (ppoll shifts everything -0x40, worse).

| function | SP delta | local object | size | userspace-controlled? | write primitive | notes |
|---|---|---|---|---|---|---|
| SyS_futex | SP0-0x70..SP0 | saved regs + arg spill | 0x70 | no | spill | entry, calls do_futex |
| do_futex | SP0-0x190..SP0-0x70 | saved regs, no array | 0x120 | no | none | calls FWRQ clone |
| FWRQ constprop.8 | SP0-0x330..SP0-0x190 | rt_waiter at x29+0x80 | 0x50 | no (victim) | none | TARGET [SP0-0x2b0,SP0-0x260): task+0x30 lock+0x38 prio+0x40 |
| sys_pselect6 | SP0-0x90..SP0 | saved regs + timeout | 0x90 | no | spill | calls core_sys_select |
| core_sys_select | SP0-0x220..SP0-0x90 | stack_fds at x29+0x90 | 0xf0 | yes (3 slots) | copy_from_user x3 + memset x3 | [SP0-0x190,SP0-0xa0), MISSES waiter, gap 0x120 |
| do_select | SP0-0x5c0..SP0-0x220 | locals x29+0x68..0x158 only; waiter equiv x29+0x310 = NO STORE | 0x3a0 | no | none at waiter | deep but EMPTY at waiter: VARs cannot diverge, explains 6/6 HANG |
| sys_poll | SP0-0x40..SP0 | saved regs + timespec | 0x40 | no | spill | calls do_sys_poll |
| sys_ppoll | SP0-0x80..SP0 | saved regs + ksigmask | 0x80 | no | spill | table=SP0-0x2f0, entries gap 0x44, NOT recommended |
| do_sys_poll head | SP0-0x3b0..SP0-0x2b0 | stack_pps at x29+0xa0 (256B), entries at +0xc, max 30x8 | 0x100 | yes | copy_from_user entries + kernel revents | [SP0-0x3a4,SP0-0x2b4) max, MISSES waiter by 4B structural (256-252) |
| do_sys_poll table | SP0-0x2b0..SP0-0x40 | poll_wqueues at x29+0x1a0 (624B) | 0x270 | partial | init + per-fd _key/entry0 | TABLE==WAITER exactly; +0x38=entry0.key(small); +0x40=flags(0); NO pointer |
| poll_initwait | below table | header init (inlined at x29+0x1a0..0x1c8) | 0x20 | no | __pollwait/~0/NULL/current/0s | always runs, even nfds=0 |
| __pollwait | below table | entry0 at table+0x30..0x70 | 0x40 | indirect | filp=heap, key=events\|0x18, wait.private=pwq | once per valid fd with poll op |

Emit locally: `python3 tools/ghostlock_deref_chain.py build-aq/vmlinux --poll`
(9/9 frames OK against first-insn disassembly).

## 3. Binary Evidence

All VAs are VA39 unslid lab values; frames verified by first-insn:

- do_sys_poll 0xffffff8009230a50: `sub sp,sp,#0x410`. Head
  `add x20,x29,#0xa0` (0x...aac), entries dest `add x28,x20,#0xc` (0x...ac4),
  `str w19,[x20,#0x8]` (len), `bl __arch_copy_from_user` (0x...b64, dest x28).
  Max-len guard `cmp w22,#0x1e` (0x...a98, 0x1e=30=N_STACK_PPS from
  (256-16)/8) then `csel w19` (min(nfds,30)). rlimit gate at 0x...a8c
  (`ldr x0,[x0,#0x318]`, `b.hi`).
- table stores: `stp x0,x1,[x29,#0x1a0]` (0x...bb8, pt=__pollwait/~0),
  `str xzr,[x29,#0x1b0]` (table=NULL), `str x0,[x29,#0x1b8]`
  (polling_task=current), wzr at 0x1c0/0x1c4/0x1c8
  (triggered/error/inline_index=0). Per-fd `_key`:
  `ldrh w4,[x28,#0x4]` (events), `orr w4,#0x18`, `str x3,[x29,#0x1a8]`
  (0x...ca8, table+0x08=_key).
- DWARF: table at `DW_OP_fbreg -624` (624=0x270, x29+0x1a0),
  stack_pps at `DW_OP_fbreg -880` (880=0x370, x29+0xa0). poll_wqueues 0x270:
  pt+0x00, table+0x10, polling_task+0x18, triggered+0x20, error+0x24,
  inline_index+0x28, inline_entries+0x30 (9x0x40). poll_table_entry 0x40:
  filp+0x00, key+0x08, wait+0x10 (flags+0x00/private+0x08/func+0x10/list+0x18),
  wait_address+0x38.
- poll_initwait 0xffffff800922f5e0 disasm confirms init values
  (`stp x0,x2,[x19]` with x2=-1; `stp xzr,x1,[x19,#0x10]` with x1=current).
- pipe has `.poll = pipe_poll` (build-aq/source/fs/pipe.c:1018),
  pipe_poll calls poll_wait -> __pollwait. Valid pipe fd queues entry0.
- do_select 0xffffff800922fc78: `sub sp,sp,#0x3a0`; all `str [x29,#off]`
  with off in 0x68..0x158 only; waiter equiv x29+0x310 has NO store.
  pselect VAR bytes (stack_fds) never touch waiter; do_select leaves it
  stale. Root cause of 6/6 identical HANG.
- --verify still 30/30, 0 mismatches. --poll frame check 9/9 OK.

## 4. Device SP Measurements

No new device run this phase. Known same-boot probes (prior boot):
sp_futex vs sp_psel dist=0x120, implied_pad=0x120, waiter_est=sp_futex-0x2b0.
That calibration is tautological (raw_psel does `sub sp,pad`, so dist==pad by
construction; it proves user SP moves, not that kernel frames match).
Kernel frames are fixed, so pad NEVER moves stack_fds (fixed x29+0x90) nor
table (fixed x29+0x1a0). The poll harness therefore does NO fixed-point
loop: single poll publish (P4 STAMP_POLL prints sp_futex, sp_poll, dist,
waiter_est, ev, predicted key). dist==pad is still expected (tautology
check) but carries no kernel information. Pad independence is the test:
same VAR at pad 0x0/0x120/0x200 must behave identically if the model holds.
Independent waiter estimate stays sp_futex-0x2b0 (binary, not pad-derived).

## 5. Stamp Design

Waiter does ONE `poll(pfds,30,timeout=0)` then parks (no loop, no FUPI, no
aux futex, no sleep). win[240B] reused as pollfd[30]: fd[0]=pipe read end
(valid, queues entry0), fd[1..29]=-1 (no queue, but entries still copy user
bytes to stack_pps). timeout=0 => do_poll single pass, no schedule sleep.
nfds=30 fills stack_pps maximally (closest to waiter, still 4B short) and
queues exactly one table entry (minimal lateral: one fdget/fput pair, one
poll_wait/add_wait_queue + freewait remove/fput). f_chain graph untouched
(pipe fds are unrelated to futex keys). Consumer is unchanged single
FUTEX_LOCK_PI. pollNone (no syscall, park immediately) is the explicit
control for the poll series.

## 6. VAR A / VAR B

Stamp VAR decoupled from fake VAR (argv[2] fake A/B/C/D, argv[3] stamp):

- pollNone: no poll. Header untouched, entries untouched. Expect HANG
  (same as nostamp). Control.
- pollA: events=0x4141 all 30 fds. entries get user bytes (miss waiter by
  4B); table+0x08=_key=0x4159 (0x4141|0x18); entry0.key=0x4159 at
  waiter+0x38 (lock slot); entry0.wait.flags=0 at waiter+0x40 (prio slot).
  If reach holds, consumer trylock at 0x4159 faults => PANIC, no P6.
- pollB: events=0x4242. Same but key=0x425A. Fault address differs by 0x100.
  Two different panics prove low-16-bit control of the lock slot.
- Distinguisher ladder: pollNone HANG (P6 HANG_IN_WALK) vs pollA/B no-P6
  (panic) proves TABLE reached waiter. pollA vs pollB fault-addr delta
  proves EVENTS reached waiter+0x38. entries user bytes are NOT the proof
  (4B miss); the proof is key-on-lock-slot.
- Untouched vs partial vs full: pollNone=untouched (stale); invalid-fd
  poll=partial (header smashed +0x00..0x28, lock stale); valid-fd
  poll=full (header + entry0, lock=small). Harness uses full only.

## 7. Hardware Results

NOT RUN yet. Predictions with pass/fail (one boot, VAR B fake, pad 0x0):

1. `ghostlock_chain 0x0 B pollNone` => P5 entered, P6 HANG_IN_WALK,
   fake+0x08/+0x10 zero. PASS = HANG (control).
2. `ghostlock_chain 0x0 B pollA` => P5 entered, NO P6 (panic in walk),
   console/serial fault at 0x4159 (or 0x...4159 unmapped). PASS = panic.
3. `ghostlock_chain 0x0 B pollB` => P5 entered, NO P6, fault at 0x425A.
   PASS = panic at different addr than pollA.
4. Repeat pollA at pad 0x120/0x200 => same 0x4159 fault. PASS = pad
   independence (kills pad theory for good).
FAIL modes: pollA HANGs like pollNone => table did NOT reach (model wrong:
SP0 not shared, or stock frames differ, or entry0 not queued). pollA/B same
fault addr => events did not arrive (mask path differs on stock).

## 8. HANG Classification

Existing P0-P6 already distinguishes the 7 cases, no new phases needed:

1. consumer entered: P5 LOCK_PI_ENTER + entered=1 (flag before svc).
2. consumer returned: P5 LOCK_PI_DONE (only if walk returned, no panic).
3. entered expected path: FULL assumed from binary (w1=1 at
   rt_mutex_timed_futex_lock); device proof pending VAR divergence.
4. fake consumed: P6 HIT_ENQUEUE (leftmost==&win) / HIT_OTHER_WRITE.
5. normal LOCK_PI block: P6 HANG_IN_WALK with stale lock (pollNone/nostamp).
6. corruption HANG: same P6 string but after stamp that should have faulted;
   disambiguated by VAR ladder (pollNone HANG + pollA HANG = no reach).
7. panic: P5 present, P6 ABSENT, adb disconnect, uptime resets. pollA/B
   predict this. Capture fault addr from serial/last_kmsg; 0x4159 vs 0x425A
   is the signature. No P6 is data, not missing data.

## 9. PREEMPT Analysis

CONFIG_PREEMPT=y unchanged, still NOT the bottleneck. Argument stands:
until stamp reach is proven, preemption/clobber/CPU-migration reasoning is
speculation. Poll design minimizes the window anyway (single timeout=0
poll, immediate park, consumer at once; no busy variant for poll series).
After reach is proven (panic ladder), the next question is clobber between
stamp return and consumer svc (interrupts, migration, softirq touching the
same stack page). Only then pin/window experiments earn their keep. Do not
invoke PREEMPT to explain a stamp that never arrived.

## 10. Poll Reachability Verdict

REACHES the region, DOES NOT deliver a pointer. Binary proof: table base =
x29+0x1a0 = SP0-0x40-0x410+0x1a0 = SP0-0x2b0 = waiter base (sys_poll path),
sizes lock the fit (0xa0+0x100=0x1a0, 0x1a0+0x270=0x410). Entries
[SP0-0x3a4,SP0-0x2b4) miss by 4B structural (256-12-240=4, never written).
Table [SP0-0x2b0,SP0-0x40) overlaps waiter [SP0-0x2b0,SP0-0x260) exactly over
its first 0x50B. But table+0x38 is entry0.key (events|0x18, small int) and
table+0x40 is wait.flags (0): a fault generator, not a fake lock pointer.
So poll satisfies criterion C (deep poll demonstrates reach, precise stamp
formulated: ev->key->lock-slot) and enables criterion A (pollNone HANG vs
pollA/B panic, pollA vs pollB addr delta). It does NOT satisfy B (controlled
signature INSIDE waiter observed as data -- panics are signatures, but the
device run is still pending) and does NOT give pointer control for the
exploit step. pselect is CLOSED (gap + do_select no-store, VARs cannot
diverge). ppoll is rejected (0x40 deeper, worse).

## 11. Alternative Stamper

Surveyed all SyS_ first-insn frames in build-aq/vmlinux: deepest with a
direct user->stack copy is do_sys_poll (0x410+0x40=0x450 from SP0). Next
are recvfrom 0x140 (sockaddr at SP0-0x80), sendto 0x130 (same), reboot
0x130 (no copy), ___sys_sendmsg 0x180 (msghdr at SP0-0x130). None reach
SP0-0x278 (lock slot) with user bytes. do_select (0x3a0, total 0x5c0)
reaches but stores nothing at waiter equiv. Therefore the pointer stamper
is NOT another big-array syscall; it is a SPILL-based one: any syscall
that spills a user-pointer argument register (x0/x1, 8B, fully attacker
chosen as an address) at SP0-0x278 and returns (even with error, leftovers
persist for the consumer). Concrete next work: script the spill search
(user-arg `str xN,[x29,#off]` per syscall path, SP0-relative math, filter
off==0x278/0x270) and pick the shallowest caller with no allocation, no
wakeup, no graph contact. Candidates to check first: syscalls taking a
user pointer + int (ioctl-like spills), compat paths excluded. One
candidate at a time; poll stays as the reach baseline until a spill
candidate is binary-proven.

## 12. Next Experiment

One boot, VAR B fake, fixed pad 0x0 (then repeat 0x120 for independence):

1. pollNone => expect HANG (control, P6 present).
2. pollA => expect panic, fault ~0x4159, no P6.
3. pollB => expect panic, fault ~0x425A, no P6.
4. If 1-3 hold: FULL_CHAINWALK device proof is ONE step away -- replace
   small-key entry0 with a spill pointer at +0x38 (section 11) and rerun
   VAR A (lock=NULL, silent block) vs VAR B (lock=fake, HIT_ENQUEUE).
5. If pollA HANGs: table did not reach -- stop, dump SPs + last_kmsg,
   re-derive stock frames (KASLR slide does not move relative offsets, so
   suspect stock config difference or entry0 not queued: check pipe fd,
   check dmesg for poll errors).
6. Only after VAR divergence: VAR C (+0x28 refcount) and recursion
   (owner+0x7f0) per the existing chain; never before.

BOTTOM LINE

- poll reaches the waiter region (table base == waiter base, binary 9/9
  frames + DWARF sizes); entries miss by 4B structural, pselect misses by
  0x120 + do_select no-store.
- real depth: table [SP0-0x2b0,SP0-0x40), lock slot = table+0x38 =
  entry0.key = events|0x18 (small int), prio slot = flags (0).
- VAR A/B (pollA 0x4141 vs pollB 0x4242) have NOT run on hardware yet;
  prediction is pollNone HANG vs pollA/B panic at 0x4159/0x425A.
- consumer protocol unchanged (single FLPI, entered flag before svc).
- HANG vs panic disambiguated by P6 presence + fault addr, not timing.
- FULL_CHAINWALK on device still NOT proven; poll gives the reach ladder,
  pointer control needs a spill-based stamper next.
- next objective bottleneck: find one syscall spilling a user pointer at
  SP0-0x278 with no side effects (script the spill search, prove one).
