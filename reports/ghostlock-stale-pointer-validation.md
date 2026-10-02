# ghostlock stale-pointer validation — no-stamp trigger vs stock geometry

Date: 2026-10-01. Device: Xiaomi Mi TV Stick 1080p (aquaman, S805Y/GXL,
Android 9, PI.2055, 4.9.113 arm64, PREEMPT=y, shell uid=2000, no root,
no ftrace, no kmsg). Lab authority: build-aq/vmlinux + same-compiler
rebuild objects with the stock codegen flag. Hardware runs in this phase:
3 (base_t, trig_t, ctrl_t), one boot, zero panics, zero reboots.

Stage 3 (controlled data injection) stayed frozen. No new stamper was
built or tested. Previous reports are not modified.

## 1. Objective

Answer H1 and H2 independently:

- H1: does the stale `task->pi_blocked_on` survive the rollback and get
  consumed WITHOUT any stamp?
- H2: does the lab stack geometry (build-aq/vmlinux) match stock PI.2055,
  or are the predicted `rt_waiter` / `waiter->lock` positions wrong?

## 2. Stock vs Lab Binary Comparison

Stock plaintext is NOT available. `boot_unpack/kernel` (9.3M) starts with
`AMLSECU!` magic ver 0x0905, 3 blocks, entropy ~8.0 bits/byte after the
0x800 header: ciphertext. No vmlinux/Image, no kallsyms, no DWARF, no
relocations extractable on host (see ghostlock-kaslr-symbols.md; the
finding stands and is repeated here so no lab number below is mistaken
for a stock fact). Direct stock disassembly was therefore impossible;
the comparison is done with a same-compiler proxy.

Proxy construction (all verified, not assumed):

- Stock build string: `gcc 6.3.1 20170109 (Linaro GCC 6.3-2017.02)`.
  Lab build-aq uses the vendored identical toolchain
  (`.src/MiTV_OpenSource/cross_compile_tool`, same version string in
  `build-aq/include/generated/compile.h`). Compiler delta: NONE.
- Lab `build-aq/.config` vs `aquaman-config`: the single global codegen
  delta touching these files is the stack protector:
  stock `CONFIG_CC_STACKPROTECTOR_STRONG=y`,
  lab `CONFIG_CC_STACKPROTECTOR_NONE=y`
  (lab cmd lines confirm `-fno-stack-protector` in
  `build-aq/kernel/.futex.o.cmd`, `build-aq/fs/.select.o.cmd`).
  `OPTIMIZE_FOR_PERFORMANCE`, `FRAME_POINTER`, `PREEMPT`,
  `THREAD_INFO_IN_TASK` are identical. The 48 remaining differs are
  drivers/USB/HID/TV (different translation units, no effect on
  futex/select/rtmutex codegen).
- `kernel/futex.c`, `kernel/locking/rtmutex.c`, `fs/select.c` in the lab
  tree textually match upstream 4.9.113 in the PI path (no Amlogic/Xiaomi
  hunks; see ghostlock-source-check.md). Vendor patches to these exact
  functions remain the one unclosed assumption (confidence: medium-high,
  stated per function below).
- Method: recompile the three objects with the stock flag
  (`-fstack-protector-strong` swapped into the exact kbuild command,
  same `-O2 -fno-omit-frame-pointer -g -pg`), disassemble, diff frames
  and x29-relative offsets against `build-aq/vmlinux`.

Result: EVERY function with a stack array or an address-taken local
grows or shifts under STRONG; functions without either are bit-identical
in frame size. Relocation check confirms canaries:
`select_strong.o` carries `__stack_chk_guard` / `__stack_chk_fail`
relocs; `do_sys_poll` epilogue checks `[x29,#0x408]` against the guard.

LAB vs STOCK-PROXY frames (first-insn `sub`/`stp!`):

| function | LAB (NONE, vmlinux) | STOCK-proxy (STRONG, .o) | delta | canary? | confidence |
|---|---|---|---|---|---|
| sys_futex (entry) | 0x70 | 0x70 | 0 | no | high |
| do_futex | 0x120 | 0x130 | +0x10 | yes | high |
| futex_wait_requeue_pi.constprop.8 | 0x1a0 | 0x1b0 | +0x10 | yes | high |
| rt_waiter off x29 | +0x80 | +0x88 | +8 | - | high |
| futex_lock_pi | 0x140 | 0x150 | +0x10 | yes | high |
| sys_poll | 0x40 | 0x50 | +0x10 | yes | high |
| do_sys_poll | 0x410 | 0x410 | 0 size, internals -8 | yes, at [x29,#0x408] | high |
| stack_pps off x29 | +0xa0 | +0x98 | -8 | - | high |
| poll table off x29 | +0x1a0 | +0x198 | -8 | - | high |
| sys_pselect6 | 0x90 | 0xb0 | +0x20 | yes | high |
| core_sys_select | 0x190 | 0x1a0 | +0x10 | yes | high |
| stack_fds off x29 | +0x90 | +0x98 | +8 | - | high |
| do_select | 0x3a0 | 0x3a0 | 0 | no | high |
| sys_ppoll | 0x80 (lab) | not rebuilt | ? | (rejected path anyway) | medium |
| rt_mutex_adjust_prio_chain | 0x90 | 0x90 | 0 | no | high |
| task_blocks_on_rt_mutex | 0x50 | 0x50 | 0 | no | high |
| remove_waiter | 0x40 | 0x40 | 0 | no | high |
| rt_mutex_timed_futex_lock | 0x20 | not rebuilt (no array) | 0 assumed | no | medium-high |

H2 verdict: CONFIRMADA. Lab != stock. Every prior stamp experiment that
used lab-exact slots (`SP0-0x278` lock, `SP0-0x270` prio, pad 0x120 as an
exact number) is marked GEOMETRICALLY INVALID for stock: the true slots
sit 0x18 deeper and every entry-frame number that produced them is wrong
on stock. History is preserved, not rewritten: the pselect-miss and
spill-search conclusions survive qualitatively (section 4), the exact
slot numbers do not.

## 3. Trigger Stack Geometry

LAB trigger chain: `sys_futex 0x70 + do_futex 0x120 + FWRQ 0x1a0 = 0x330`;
`rt_waiter = SP0-0x330+0x80 = SP0-0x2b0` (x29+0x80, `add x21,x29,#0x80`
at FWRQ+0xbc, DWARF fbreg-288, CFA x29+0x1a0).

STOCK-proxy trigger chain: `0x70 + 0x130 + 0x1b0 = 0x350`;
`rt_waiter = SP0-0x350+0x88 = SP0-0x2c8`.
Waiter fields: `task` SP0-0x298, `lock` SP0-0x290, `prio` SP0-0x288,
`deadline` SP0-0x280 (each lab value minus 0x18).

What moves the waiter: the canary (8B at frame top) plus gcc's local
re-layout under STRONG (+8 x29 shift for the waiter, +0x10 frame growth
in do_futex and FWRQ). `sys_futex` (entry, no array) does not move, so
the full 0x18 slide comes from the two inner frames plus the waiter
shift. The rtmutex logic frames (consumer side) do NOT move (section 4).

## 4. Consumer Stack Geometry

Consumer-side logic is frame-identical lab vs stock-proxy:
`rt_mutex_adjust_prio_chain 0x90`, `task_blocks_on_rt_mutex 0x50`,
`remove_waiter 0x40` in both builds (no arrays, no address-taken locals,
no canary). The `--verify` curated chain still passes 30/30, 0
mismatches on the lab image; the VAs are lab-absolute but the
mnemonic+offset pattern for these three functions is build-invariant
under the measured delta (no frame change, no local reordering observed
in the strong objects).

Consumer entry frames DO move (`futex_lock_pi 0x140 -> 0x150`), but that
only shifts the consumer thread's own stack, which never overlaps the
waiter page (different thread, different stack). Irrelevant to reach;
relevant only as further proof the lab numbers are not stock numbers.

Struct offsets (`task+0x7f0 pi_blocked_on`, `waiter+0x38 lock`,
`+0x40 prio`, `rt_mutex+0x18 owner`, `task+0x28 usage`,
`task+0x7d4 pi_lock`) are DWARF-derived from the lab build; none of the
48 config differs touches these structs' layouts (driver options only;
`THREAD_INFO_IN_TASK`, `RT_MUTEXES`, `FUTEX`, credential debug flags
identical). Confidence high, assumption stated: no vendor patch to
`rtmutex_common.h` / `sched.h` field order.

## 5. Natural rt_waiter Values

Source-derived (upstream 4.9.113 == lab tree for these files), no stamp,
preserved graph (no FUPI, owner still blocked, waiter woken to park):

1. `futex_requeue` (FCRQ): `this->pi_state = pi_state(f_target)`;
   `rt_mutex_start_proxy_lock(&pi_state->pi_mutex, W_waiter, W_task)`.
2. `task_blocks_on_rt_mutex(lock=f_target, waiter=W_waiter, task=W)`:
   `waiter->task = W; waiter->lock = &f_target pi_mutex (heap, VALID,
   owner O); waiter->prio = W prio (~120); enqueue; W->pi_blocked_on =
   W_waiter`. Cycle W->O->W detected -> `-EDEADLK`.
3. `remove_waiter(lock, waiter)`: `raw_spin_lock(&current->pi_lock)`
   where current = requeuer (main M), NOT `waiter->task` (W);
   `current->pi_blocked_on = NULL` clears M (already NULL), dequeues
   W_waiter from f_target waiters, leaves W_waiter fields AND
   `W->pi_blocked_on = W_waiter` intact. That is the leak.
4. Expected natural waiter at consumer time: `task=W`,
   `lock=&f_target pi_mutex` (heap, owner O still blocked),
   `prio~=120`. `lock` is NOT NULL and NOT a small int: a natural walk
   faults nowhere and writes only to heap + peer stacks (section 7).

Caveat: step 3 describes the state at EDEADLK time. The harness then
FWAKES f_wait to park W; W's FWRQ return path runs before the consumer.
Whether that path preserves `W->pi_blocked_on` is exactly what the
timed experiment tests (section 8/10), not something asserted here.

## 6. Timeout Consumer

`FUTEX_LOCK_PI` timeout semantics confirmed in source before choosing
flags (`kernel/futex.c`): `futex_lock_pi()` hardcodes
`CLOCK_REALTIME/HRTIMER_MODE_ABS`; the `SYSCALL_DEFINE6(futex)` wrapper
does NOT add `now` for `LOCK_PI` (unlike `WAIT`, which does
`ktime_add_safe(ktime_get(), t)`). So the consumer passes ABSOLUTE
realtime (`clock_gettime(CLOCK_REALTIME)+3s`). Unit: timespec seconds +
nanoseconds, absolute. Returns: 0 acquired, `-EDEADLK` on cycle detect
(fast, no sleep), `-ETIMEDOUT` (110) after ~3s on plain block. The 3s
value only bounds a naturally blocked consumer; it is not exploited.

## 7. Control Runs

Three modes added to `tools/ghostlock_chain.c` (8/9/10, old modes
untouched):

- CONTROL A `base_t`: same arming (W holds f_chain, O blocked on
  f_chain, W in FWRQ), NO CMP_REQUEUE trigger, park W the same way,
  timed consumer `LOCK_PI(f_chain)`. No stale pointer can exist.
  Expect `TIMEOUT_BLOCK` ~3000ms.
- CONTROL B `trig_t`: full GhostLock trigger (FCRQ -> EDEADLK 35),
  graph preserved, NO stamp, timed consumer `LOCK_PI(f_chain)`.
  `EDEADLK_CYCLE` fast proves the walk consumed the stale waiter and
  completed the W->O->W cycle; `TIMEOUT_BLOCK` means the walk bailed
  (NULL stale, lock mismatch at +0x4df4, top_waiter checks) or slept a
  normal block. Indistinguishable-from-baseline is a result, recorded.
- CONTROL D `ctrl_t`: full trigger, NO stamp, timed consumer
  `LOCK_PI(f_ctrl)` (fresh futex, no pi_state, untouched by the
  trigger). Expect `ACQUIRED` rc=0 in ~0ms. Proves the consumer
  thread/syscall path and the timeout mechanism are healthy; a hang
  here would invalidate the trial.

## 8. Stale Pointer Evidence

`tools/ghostlock_deref_chain.py --natural` (new) prints the full
unstamped path, per hop: VA, instruction, field, source/destination
registers, offset, expected natural value, consequence (section 7 of the
tool output; VAs are lab-absolute, offsets are build-invariant for the
rtmutex functions per section 4). Shortest statement: the first
operation that necessarily touches memory outside the waiter stack is
`bl _raw_spin_trylock` at `rt_mutex_adjust_prio_chain+0xdc`
(0xffffff8009104e44), RMW at `lock+0x00` where lock is naturally the
heap f_target mutex: valid address, user-invisible either way. The
first user-visible write in the stamped-fake design
(`str w0,[x28,#0x40]` at +0xec) lands in W's kernel stack naturally:
also invisible. Hence no stamp-free page observation is possible; the
timed return CODE is the only discriminator.

## 9. HANG Reclassification

The old `HANG_IN_WALK` label (consumer entered=1, done=0 after a fixed
sleep) conflated three states: spinning in the trylock retry loop
(+0x4e4c `cpu_relax`), sleeping in `__rt_mutex_slowlock` after the walk
returned 0, and never entering the walk at all (plain futex block). The
code could not distinguish them, and "processo travou" was never
accepted as proof. New classification (timed modes only; old modes keep
their strings for history):

- `EDEADLK_CYCLE` (done, errno=35, fast): walk consumed stale waiter,
  completed W->O->W cycle. H1 evidence.
- `TIMEOUT_BLOCK` (done, errno=110, ~3000ms): consumer slept the full
  timeout with no cycle detected. Walk location UNKNOWN (bailed or
  normal block). Not evidence for either hypothesis.
- `ACQUIRED` (done, rc=0): lock taken. Only sane for `ctrl_t`.
- `STILL_PENDING` (not done past timeout+margin): abnormal, investigate.

## 10. Hardware Results

One boot, three runs, device stable throughout (uptime 1:52 -> 1:55
monotonic, no panic, no reboot, adb attached):

RUN 1 `ghostlock_chain 0x0 B base_t` (CONTROL A):
P0 READY, P1 TRIGGER_SKIPPED, P2 BASELINE, P3 GRAPH_BASELINE,
P4 STAMP_SKIPPED base_t sp_futex=0x7d73df2b80,
P5 LOCK_PI_ENTER mode=base_t timeout_abs3s,
P5 LOCK_PI_DONE rc=-1 errno=110 (Connection timed out) elapsed_ms=3000,
P6 RESULT=TIMEOUT_BLOCK entered=1 done=1. As predicted (normal block).

RUN 2 `ghostlock_chain 0x0 B trig_t` (CONTROL B):
P1 TRIGGER_ENTER, P2 EDEADLK errno=35 (Resource deadlock would occur),
P3 GRAPH_PRESERVED,
P4 STAMP_SKIPPED trig_t sp_futex=0x7da509cb80,
P5 LOCK_PI_ENTER mode=trig_t timeout_abs3s,
P5 LOCK_PI_DONE rc=-1 errno=110 elapsed_ms=3000,
P6 RESULT=TIMEOUT_BLOCK entered=1 done=1. EDEADLK reproduces (trigger
works); consumer is identical to baseline: no EDEADLK_CYCLE, zero fake
writes (none expected without stamp), no panic.

RUN 3 `ghostlock_chain 0x0 B ctrl_t` (CONTROL D):
P1 TRIGGER_ENTER, P2 EDEADLK errno=35, P3 GRAPH_PRESERVED,
P4 STAMP_SKIPPED ctrl_t,
P5 LOCK_PI_ENTER mode=ctrl_t timeout_abs3s,
P5 LOCK_PI_DONE rc=0 errno=0 (Success) elapsed_ms=0,
P6 RESULT=ACQUIRED. Consumer path + timeout mechanism healthy; trial
valid; device not wedged by the trigger.

Note: P4 `waiter_est` prints use the LAB 0x2b0 constant and are therefore
0x18 shallow vs the stock-proxy 0x2c8. They are retained as raw SP
probes (sp_futex values are real); the derived estimate is lab-based and
must be re-derived with 0x2c8 for stock. No stamper uses them in *_t
modes.

## 11. H1 Verdict

INCONCLUSIVA (leaning negative for the observable-cycle form).
The stale pointer was NOT demonstrated without a stamper: trigger and
baseline are indistinguishable under the minimal discriminator
(both `TIMEOUT_BLOCK`, same 3000ms elapsed). The binary path for the
consumer to consult `pi_blocked_on` exists (`task_blocks_on_rt_mutex`
loads at +0x52f0/+0x53e8, FULL entry at +0x5378), so H1 is NOT refuted
either. Ranked explanations for the missing EDEADLK: (a) `W->pi_blocked_on`
NULL at consumer time (cleared or never visible through W's FWAKE/return
path: the `cbz x0` at +0x52f8 then takes the no-walk return); (b) walk
entered but bailed before completing the cycle (lock mismatch at +0x4df4
cannot fire on stable natural bytes, so this means a top_waiter/owner
gate); (c) consumer never reached `task_blocks` (unlikely: owner W holds
f_chain, atomic path must fail into slowlock). Separating (a) from (b)
is the next discriminator (section 14); forcing an interpretation now
would violate the rules.

## 12. H2 Verdict

CONFIRMADA. Stock and lab do NOT share frame layout: STRONG adds canaries
and shifts every array/address-taken function in the trigger and stamper
paths (table section 2), moving `rt_waiter` from SP0-0x2b0 (lab) to
SP0-0x2c8 (stock-proxy) and `waiter->lock` from SP0-0x278 to SP0-0x290.
All prior stamp experiments are therefore marked GEOMETRICALLY INVALID
for exact slots (their conclusion about pselect-miss and spill-search-emptiness
survive: pselect gap grows under STRONG, and the 87->0 spill result was
computed on lab frames but the window shift (-0x18, uniform for
table==waiter) does not promote any rejected candidate: all exact-slot
hits were ints/kernel pointers regardless of slot, and the nearest clean
pointer still misses). Qualitative poll result SURVIVES with shifted
absolute: table==waiter overlap is preserved under STRONG (both slide
-0x18; entries still miss by structural 4B; lock slot still table+0x38).
The prior pollA/B HANGs are now re-read as `TIMEOUT_BLOCK`-equivalent
plain sleeps, consistent with EITHER table-miss OR no-walk (stale NULL):
given RUN 2 == RUN 1, no-walk ranks first, which is why H1 (not another
stamper) was and remains the priority.

quantity | lab | stock-proxy | confidence (section 2 assumptions)

- rt_waiter base | SP0-0x2b0 | SP0-0x2c8 | high (proxy, AMLSECU blocks direct)
- waiter->task | SP0-0x280 | SP0-0x298 | high
- waiter->lock | SP0-0x278 | SP0-0x290 | high
- waiter->prio | SP0-0x270 | SP0-0x288 | high
- task->pi_blocked_on | +0x7f0 | +0x7f0 | high (struct, no config effect)
- poll table base (sys_poll) | SP0-0x2b0 | SP0-0x2c8 | high
- poll entries (max) | [SP0-0x3a4,SP0-0x2b4) | [SP0-0x3bc,SP0-0x2cc) | high
- entries-vs-waiter gap | 4B miss | 4B miss (structural, preserved) | high
- FWRQ frame | 0x1a0 | 0x1b0 | high
- do_futex frame | 0x120 | 0x130 | high
- sys_futex frame | 0x70 | 0x70 | high
- sys_poll frame | 0x40 | 0x50 | high
- do_sys_poll frame | 0x410 | 0x410 (canary inside, locals -8) | high
- sys_pselect6 frame | 0x90 | 0xb0 | high
- core_sys_select frame | 0x190 | 0x1a0 | high
- rtmutex logic frames | 0x90/0x50/0x40 | identical | high

## 13. What Is Now Proven

- Stock PI.2055 frames differ from lab build-aq by the STRONG delta
  (measured with the identical compiler, not guessed). Exact lab slots
  are void for stock.
- The GhostLock trigger (EDEADLK 6/6 historically, 2/2 today) and graph
  preservation remain safe and stable (no panic/reboot across 3 timed
  runs + all prior runs).
- A timed `FUTEX_LOCK_PI` consumer (absolute CLOCK_REALTIME +3s) cleanly
  separates immediate-cycle from plain-block without hanging trials:
  baseline TIMEOUT_BLOCK, control-lock ACQUIRED.
- Without a stamper, trigger and baseline are indistinguishable
  (both TIMEOUT_BLOCK): no stale-pointer consumption demonstrated, no
  fake read/write claimed, no panic misread as proof.
- The natural waiter, if consumed, would walk heap + peer stacks only
  (first off-stack op: trylock RMW at heap f_target+0x00), explaining
  silent stability with zero user-visible writes.
- Old `HANG_IN_WALK` verdicts are reclassified as `TIMEOUT_BLOCK`-
  equivalent plain sleeps with unproven walk location.

## 14. Next Bottleneck

One objective discriminator between stale-NULL (cbz bail at +0x52f8, no
walk) and stale-nonNULL-but-bailed (walk entered, gated before EDEADLK).
Cheapest candidates, in order: (1) read `dmesg` for the WARN_ONs on W's
FWRQ return path (`mark_wake_futex` refusing-PI-wake at futex.c:1277,
`WARN_ON(!q.pi_state)` at :2978): which wake path ran determines whether
the stale could have survived FWAKE; shell may lack kmsg, then the
check is closed without privilege escalation attempts; (2) consumer
`LOCK_PI(f_target)` instead of f_chain (owner O, whose pi_blocked_on is
a VALID non-stale waiter): EDEADLK there proves the consumer/walk path
is functional on this device, isolating the suspect to W's stale word
specifically; (3) only then consider a minimal natural signature (e.g.,
sched-prio observation of O/W boost through the preserved graph, still
no stamper). No new stamper, no spill search, no fake object until the
NULL-vs-bail question has an answer.

---
BOTTOM LINE (per-round summary)

- Stock and lab frames were PROVEN different (STRONG vs NONE, same
  compiler): every array/address-taken function shifts; rtmutex logic
  frames identical.
- rt_waiter on stock-proxy sits at SP0-0x2c8 (lab said SP0-0x2b0);
  waiter->lock natural slot SP0-0x290 (lab said SP0-0x278).
- Natural waiter->lock, if the stale survived, would be &f_target
  pi_mutex (heap, VALID, owner O): a silent walk, never a fault.
- Stale pi_blocked_on consumed without stamper: NOT demonstrated
  (trig_t TIMEOUT_BLOCK 3000ms == base_t TIMEOUT_BLOCK 3000ms).
- FUTEX_LOCK_PI enters slowlock in all runs; the old HANG_IN_WALK is
  reclassified as unlocated plain sleep (TIMEOUT_BLOCK), not chainwalk
  proof; only an EDEADLK_CYCLE code would prove the walk.
- ctrl_t ACQUIRED rc=0 separates mechanism-health from behavior:
  the timeout consumer works, the device is not wedged.
- H1: INCONCLUSIVA (path exists in binary, cycle unobserved).
- H2: CONFIRMADA (lab slots void for stock; poll overlap preserved
  relatively, absolute -0x18; pselect-miss and spill-emptiness stand
  qualitatively).
- Single next bottleneck: NULL-stale vs bailed-walk discriminator
  (dmesg WARN check, then LOCK_PI(f_target) consumer); no stamper until
  answered.
