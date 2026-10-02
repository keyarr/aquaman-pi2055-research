# ghostlock h16 durable write — [W_waiter+0x38] = &f_alt.pi_mutex

> DIRECTION (2026-10-02, see `reports/CURRENT_STATE.md`): principal is
> post-free stack reuse + disclosure; H16 live retarget is secondary;
> reclaim without verifier, audited live H16 writer search, fake object,
> arbitrary R/W, cred/root are closed. Post-free reuse is not demonstrated
> on Aquaman. Live-retarget was audited and not demonstrated.

Date: 2026-10-01. Device: Xiaomi Mi TV Stick 1080p (aquaman, S805Y/GXL, Android 9, PI.2055, 4.9.113 arm64). Lab: build-aq/vmlinux + .src/linux-amlogic. One boot, no power-cycle, no flash, no SELinux bypass, no root.

Tools: `tools/ghostlock_deref_chain.py --h16/--h16-write/--pi-source/--target` + `tools/ghostlock_h16_target_search.py --all/--carrier/--atomic/--rtmutex/--current/--frame-reuse/--ioctl/--syscall/--store8/--verify` (live from binary) + `tools/ghostlock_chain.c` (unchanged P0-P8, modes alt_only/alt_tgt/h16_static/occ_tgt/trg_inwin/occ_base/base_t). Full disassembly cache `/tmp/opencode/aq_full.asm` (3768288 lines). Static verify 30/30. `pthread_setschedparam` not used.

Hardware log: `out/logs/ghostlock_h16_durable_boot3ec336a5-439f-497f-b9f7-08fd7441b174.log` (this round, same BOOT_ID as prior `ghostlock_consumer_boot3ec336a5.log`).

## 1. Hypothesis

A durable 8-byte store lands on the live waiter slot while the GhostLock graph is armed and survives both in-window readers, swapping the birth value:

```text
legitimate operation -> exact store -> [W_waiter+0x38] -> exact &f_alt.pi_mutex
waiter nasce (waiter->lock = &f_target.pi_mutex) -> [corruption window] -> H16.4 read -> H16.7 read
```

Success requires dest AND value AND timing AND durability AND differential together. Anything less is not LEVEL_3.

## 2. Exact target

```text
[W_waiter + 0x38] = &f_alt.pi_mutex, 8 bytes, single word
```

* Birth `H16.0 0xffffff800910527c task_blocks_on_rt_mutex+0x54`: `stp x20,x19,[x21,#0x30]` (`[x21,#0x30]=task=x20, [x21,#0x38]=lock=x19`). Source `rtmutex.c:997-998` (`waiter->task = task; waiter->lock = lock`). Source grep `waiter->lock =`: exactly 1 hit. EVIDENCE: OFFLINE_ONLY (source + binary 30/30 verify).
* Layout `waiter+0x30 = task, waiter+0x38 = lock, waiter+0x40 = prio, waiter+0x48 = deadline`, size 0x50 (two rb_node 0x18 each + 8 + 8 + 4 + 8, CONFIG_DEBUG_RT_MUTEXES=n). Binary confirms: after birth `ldr w0,[x20,#0x68] @0x5280` + `str w0,[x21,#0x40]` (prio) + `ldr/str @0x5288/0x528c` (deadline). EVIDENCE: OFFLINE_ONLY.
* In-window readers read the SAME slot twice: `H16.4 0x52fc ldr x25,[x0,#0x38]` (first stale deref, next_lock as x3) and `H16.7 0x4df0 ldr x0,[x28,#0x38]` + `cmp x20,x0 @0x4df4 / b.ne out @0x4df8` (first value branch). Stability across both required; mismatch bails. EVIDENCE: OFFLINE_ONLY.
* W waiter = FWRQ stack slot SP0-0x2b0 lab (`add x21,x29,#0x80 @0xb454`, frame 0x1a0 @0xb398). Stock absolute STOCK UNKNOWN; only relative `W_waiter+0x38` claimed. Frame alive while W sleeps (hrtimer only exit, `fwake_errno=22` = futex_wake refuses PI). EVIDENCE: OFFLINE_ONLY layout + HARDWARE_REPRODUCED alive (P3/P4 + double TIMEOUT this round).
* No legitimate writer after birth. `remove_waiter 0x5400-0x554c` has zero `str` to `+0x38` (hand-checked in cached disassembly: only `ldr x0,[x22,#0x38] @0x5428`, `ldr x0,[x1,#0x38] @0x54ac`, `ldr x21,[x0,#0x38] @0x54d0`, all loads; one store `str xzr,[x24,#0x7f0] @0x5454` is current->pi_blocked_on). Enqueue/dequeue never touch `+0x38`. Requeue `start_proxy` reuses same pi_state for a fresh birth, never rewrites live H16. PI->PI requeue rejected (`futex.c:1920-1925`). EVIDENCE: OFFLINE_ONLY.
* Hypothesis really requires external corruption: exactly one natural writer exists, zero post-creation writers, zero rebind. EVIDENCE: OFFLINE_ONLY + HARDWARE_REFUTED natural (alt_only ignores f_alt).

## 3. Existing writer census

Only candidates that reach the window are listed. Full-binary counts are context, not proof. Classification per task: EXACT_TARGET / EXACT_OFFSET_WRONG_VALUE / EXACT_VALUE_WRONG_SLOT / POSSIBLE_ALIAS / GEOMETRY_ONLY / UNRELATED.

Narrowed `#0x38` scan (live): 3384 total `str` with `#0x38`, 202 in futex/RT/signal/poll/select/pipe/socket/mmap/ioctl/configfs/ashmem/workqueue/timer/completion, 7 PI-adjacent. All 7 KERNEL_ONLY or small-int, none with dest=W stack AND value=&f_alt (see `--h16-write`). EVIDENCE: OFFLINE_ONLY.

Stock-relative 8B census (`--all`, H16_REL=0x290 conjecture, depth<=3, 303 SyS roots): 411 8B in H16+-0x40 (KPTR 154, UPTR 29, rest INTEGER/DERIVED/UNKNOWN). EXACT_H16 (delta==0,w==8): 33 total = 9 KPTR, 0 UPTR, 2 INTEGER, 1 DERIVED, 21 UNKNOWN. Lab-relative comparison (`--lab` 0x278): 513 in window, 10 EXACT (5 KPTR, 0 UPTR, 0 TARGET). TARGET_RT_MUTEX at EXACT: 0 in both geometries. EVIDENCE: OFFLINE_ONLY.

The 9 EXACT KPTR (all EXACT_OFFSET_WRONG_VALUE, none EXACT_TARGET):

* `kobject_add 0x468834/0x468844` (finit/init_module, heap/code): privileged module load, CAP_SYS_MODULE shell lacks, heavy. REJECT.
* `get_page_from_freelist 0x1be94c/0x1bf1f8/0x1bf550` (io_setup/mincore, heap): MM allocator, sleeps, zone locks, heavy. REJECT.
* `congestion_wait 0x1db8b8` (io_setup, current): MM sleep, schedules, heavy. REJECT.
* `__slab_free 0x20a6ac` (reboot>do_exit>kfree, heap): process-exit, destructive. REJECT.
* `printk 0x1b416c` (renameat2>audit, heap): error formatting, transient, value is audit struct word. REJECT.
* `__vmalloc_node_range 0x1fa39c str x2,[sp]` (select>core_sys_select>vmalloc, `ldr x2,[x20,#0x38] @0x1fa394` heap): hand-verified recursive call-arg, transient, wrong value type (vmap internal), sleeps+allocs. Nearest exact KPTR, still REJECT.
* 2 INTEGER (`get_page_from_freelist stp x5` mov #a, `warn_alloc stp x4` immediates) + 1 DERIVED (`__alloc_pages_nodemask str x0` masked find_vma chain): EXACT_OFFSET_WRONG_VALUE, scalars by construction. REJECT.
* 21 UNKNOWN (`str xN,[sp,#..]` callee-saved spills incl. SyS_futex `get_futex_value_locked 0x39114`, `put_pi_state 0xa680`, `rt_mutex_start_proxy_lock 0x58b4`, `___might_sleep 0xd58e8`, `attach_to_pi_owner 0x9590`, SyS_pselect6 `preempt_count_sub 0xd5810`, SyS_process_vm_readv/writev `process_vm_rw_core 0x1fb574`, SyS_remap_file_pages `__lock_page`, SyS_select `printk`): untainted regs, deep/heavy or PI-internal spills, none is a kptr carrier (tool class UNKNOWN ptr=False). Hand rule: untainted spill restores caller reg, not a steerable pointer; none derives from pi_state+0x10. Class: GEOMETRY_ONLY (fast ones) or UNRELATED (heavy ones). REJECT as writers (not pointers).

Atomics (`--atomic`): 0 atomic stack stores total, 0 in window. PI RMWs are heap-fixed (trylock `[x20,#0x00]`, pi_lock `[x19+0x7d4]`, usage INC `[x19+0x28]` with base `ldr x19,[x20,#0x18]` owner, value +1). Class: UNRELATED. EVIDENCE: OFFLINE_ONLY.

Ioctl (`--ioctl`, depth 4): 1 near 8B (`locks_mandatory_area 0x27583c str x25,[sp,#0x40]` delta -48), 0 exact. Vendor f_op past depth 4 INCONCLUSIVE (not claimed covered). Class: GEOMETRY_ONLY at best. EVIDENCE: OFFLINE_ONLY.

`copy_*_user`/memcpy (`--memcpy`, 337 callsites): all dests heap (kmalloc/alloc_fdtable) in sampled output, none with stack dest carrying KPTR near H16. do_sys_poll stack_pps copy (`x29+0xa0`, 240B entries SP0-0x3a4..SP0-0x2b4 lab) misses waiter by 4B structural; table stores are the only stack stores and carry small-int/current (sec. 4). Class: UNRELATED for H16 dest. EVIDENCE: OFFLINE_ONLY.

Poll/select fast reuse (`--same-task`/`--frame-reuse`): fast-syscall 8B in window 62. do_sys_poll `0xbb8 stp table` + `0xbd0 str x0 current` are H16_RELATIVE delta +32/+8 stock (+0x20/+8 lab), KPTR but value = current/task_struct and table/code, never rt_mutex. Under lab geometry table base == waiter base exactly, lock slot gets `events|0x18` small-int (fault if reached = reach proof, not pointer). Class: GEOMETRY_ONLY, never promoted. Prior pollA/B HANG with zero panic confirms no reach as pointer. EVIDENCE: OFFLINE_ONLY dataflow + HARDWARE_OBSERVED safety.

No EXACT_TARGET in audited surface (depth<=3, all SyS roots). Deeper-than-3 or indirect f_op dispatch explicitly not claimed covered.

## 4. Value derivation

Desired value `&f_alt.pi_mutex` is heap, learned not guessed; f_alt valid+contended (alt_base TIMEOUT history + ALT_ARMED this round). Carrier classes: EXACT_KPTR / DERIVED_KPTR only if derivation demonstrable; else USER_POINTER / INTEGER / UNKNOWN.

* PI LEAs verified (`--rtmutex`): `attach_to_pi_owner 0x9614 add x0,x20,#0x10`, `futex_requeue 0xabe4 add x0,x0,#0x10`, `futex_lock_pi 0xb1b8/0xb238/0xb2a0`, `wait_requeue_pi 0xb574/0xb58c/0xb628/0xb6d0/0xb7cc`, `task_blocks 0x5298/0x52d4 ldr +0x10`. Forward-spill check in same bodies: attach/task_blocks/start_proxy/init_proxy ZERO KPTR stack spills; futex_requeue/futex_lock_pi spill only code/current, never the `+0x10` lock reg. Lock reg dies in regs/epilogue. So `f_alt -> PI helper -> live reg -> stamper spill -> H16` has no binary support. Class: no EXACT_KPTR, no DERIVED_KPTR at EXACT. EVIDENCE: OFFLINE_ONLY.
* USER_POINTER at EXACT: 0 hits. Userspace literal `&f_alt` cannot be placed without a heap leak; no leak demonstrated (disclosure/emit phases: mali GET/QUERY read-only refuted, ashmem/configfs not demonstrated, robust/sched/getsockname scalars). Class: USER_POINTER absent. EVIDENCE: OFFLINE_ONLY.
* INTEGER at EXACT: 2 + 1 DERIVED, all scalars/masked (mov #a, warn_alloc immediates, find_vma masked chain ending in ubfx/csel). Cannot equal a heap pointer. Class: INTEGER. EVIDENCE: OFFLINE_ONLY.
* Poll/current carriers: value is task_struct (`mrs SP_EL0`) or `events|0x18` small-int or code `adr`. Pointer to f_alt but not to `pi_mutex`, or not a pointer at all. Offset wrong by definition (`f_alt.pi_mutex` = pi_state+0x10, not task, not table). Class: EXACT_VALUE_WRONG_SLOT or INTEGER. EVIDENCE: OFFLINE_ONLY + HARDWARE_OBSERVED (pollA/B silent).
* Result: stored_value == &f_alt.pi_mutex has zero demonstrable producers at EXACT dest. EXACT_VALUE: NOT_FOUND.

## 5. Timing/durability

Window: birth (trigger requeue `start_proxy_lock`) -> H16.4 `0x52fc` (consumer entry `ldr x25`) -> H16.7 `0x4df0` + `cmp @0x4df4` (walk head gate). Both must see the same 8 bytes; mismatch bails at `+0x4df8`. Consumer re-reads at H16.10/H16.11/H16.12 after the window. EVIDENCE: OFFLINE_ONLY.

* Same-thread reuse requires W to return from FWRQ then issue a second syscall whose frame overlaps H16. But GhostLock window keeps W blocked (inwin: `w_back` infinite loop in kernel frame, hrtimer only exit; main runs consumer without waiting for W). While blocked the thread cannot execute a stamper. After return the frame is dead; bytes persist until same-thread reuse, but then H16.4/H16.7 would read recycled stack, not a live frame. The task demands store while W_waiter is alive; post-return reuse violates the live-frame constraint and was deliberately not thrown at H16 (wrong value + garbage trylock risk). EVIDENCE: OFFLINE_ONLY (control flow) + HARDWARE_REPRODUCED (inwin alive via double TIMEOUT).
* Cross-thread write to another thread kernel stack has no path: all audited stores use `x29/sp` of the running thread (dest_rel = SP0 - sumF + off by construction); no `copy_to_user` with kernel-stack dest; no `process_vm_writev` to kernel; `futex_wake` refuses PI (`fwake_errno=22`); sched path only READS (H16.12, schedA silent history). Async (signal/workqueue/timer/completion) targets own structs (siginfo/work/timer), none takes a waiter pointer; only waiter-pointer receivers are readers. EVIDENCE: OFFLINE_ONLY + HARDWARE_OBSERVED (schedA/pollA/B silent).
* do_sys_poll examined by hand: `0xbb8 stp x0,x1,[x29,#0x1b8]` is table init (code addrs), `0xbd0 str x0,[x29,#0x1b8]` is current (`mrs x0,SP_EL0 @0xbcfc`), `0xca8 str x3,[x29,#0x1a8]` is `events|0x18` small-int (`orr w4,w4,#0x18`), `0xc30 add x23,x29,#0xa0` is stack_pps head. No store carries rt_mutex; nearest exact KPTR (`__vmalloc [sp]`) is a transient recursion arg overwritten before return. No durable carrier. EVIDENCE: OFFLINE_ONLY (hand disassembly above).
* Therefore even if geometry aligned under one conjecture, durability across H16.4+H16.7 with value `&f_alt` has no mechanism. DURABLE_ACROSS_H16: UNPROVEN (no candidate to test).

## 6. Hardware experiment

No new harness, no new mode, no memory touched beyond existing legitimate syscalls. One boot `3ec336a5-439f-497f-b9f7-08fd7441b174`, zero reboot, adb stable. `adb push` already present; binary `out/ghostlock_chain` (static aarch64, NDK r28c) reused as-is.

Matrix (task mapping; W1/W2 have no candidate so they are NOT RUN by design, not skipped):

```text
C0 alt_only: sem writer, f_target vazio, f_alt ocupado (a_armed=1 alt_parked=1). Esperado TIMEOUT. Observado TIMEOUT 3000ms/110. PASS.
C1 h16_static: writer path armada (mesma arming que C0) mas condicao que nao deve atingir slot (duplo LOCK_PI(f_chain) no mesmo frame vivo, sem corrupcao). Esperado TIMEOUT+TIMEOUT. Observado 3000ms/110 + 3000ms/110. PASS.
W1 writer path f_target->f_alt: SEM CANDIDATO EXATO, nao executado (executar poll/current com valor errado seria GEOMETRY_ONLY e arriscaria garbage trylock; proibido pela Fase 5).
W2 mesma preparacao sem store final: NAO APLICAVEL pelo mesmo motivo.
Discriminadores (diferencial ja validado, re-rodados neste boot):
  base_t (sem trigger, f_chain) TIMEOUT 3000ms/110. PASS.
  occ_base (sem trigger, f_target ocupado) TIMEOUT 3000ms/110. PASS.
  trg_inwin (trigger, f_target vazio) TIMEOUT 3000ms/110. PASS.
  occ_tgt (trigger, f_target ocupado) EDEADLK 0ms/35. PASS.
  alt_tgt (trigger, f_target ocupado + f_alt ocupado) EDEADLK 0ms/35. PASS.
```

Instrumentation per run (P0-P8): BOOT_ID implicit (same `adb shell cat /proc/.../boot_id`), PID/TID (P0 main_pid/main_tid/W_tid), variant (P0 var/mode/pad/fake/win/pipe), W_waiter identity (P4 sp_futex + waiter_est_lab, NOT stock offset; page_off), W_waiter+0x30/+0x38 not directly readable (no leak; birth value inferred from differential), f_target/f_alt (P4 ALT_ARMED f_alt u32, P7 occ/alt_parked), writer candidate (none; P4 NO_STAMP), store insn (none), stored value class (none), H16.4/H16.7 results (inferred via consumer verdict: TIMEOUT = gate shut or empty leftmost, EDEADLK = FULL cycle W->O->W), consumer rc/errno/elapsed (P5/P5b/P6), hang/reboot (none; all EXIT 0/1 clean, uptime monotonic).

Full lines in `out/logs/ghostlock_h16_durable_boot3ec336a5-439f-497f-b9f7-08fd7441b174.log`. Absolute VAs are aux; offsets/relations (`W_waiter+0x38`, `f_alt+pi_mutex`) are the claim.

## 7. Differential evidence

Same boot, same pad 0x0, VAR B:

```text
base_t    TIMEOUT 3000ms/110 (no trigger, baseline)
occ_base  TIMEOUT 3000ms/110 (occupied f_target alone, no requeue -> no cycle)
trg_inwin TIMEOUT 3000ms/110 (trigger, f_target empty -> gate shut)
occ_tgt   EDEADLK 0ms/35 (trigger, f_target occupied -> gate open)
alt_only  TIMEOUT 3000ms/110 (trigger, f_target empty + f_alt occupied -> walk IGNORES f_alt)
alt_tgt   EDEADLK 0ms/35 (trigger, f_target occupied + f_alt occupied -> walk FOLLOWS f_target)
h16_static TIMEOUT+TIMEOUT 3000ms/110 each (same live frame, slot static)
```

Interpretation closed: occupancy alone does not make EDEADLK without requeue (occ_base); stale alone without occupancy does not make EDEADLK (trg_inwin); stale + correct target does (occ_tgt/alt_tgt); stale + wrong-target occupancy does not (alt_only); double probe proves slot static across H16.4/H16.7 window. This sustains LEVEL_2 and refutes natural retarget. No written variant exists to compare, so `alt_only vs alt_tgt` remains the fidelity discriminator, not a write proof.

## 8. Verdict

```text
NO_EXACT_WRITER_FOUND
```

LEVEL_2_UNCHANGED as consequence (differential preserved, zero new capability). LEVEL_3 criteria: (1) writer dest == W+0x38 NOT FOUND, (2) carrier == &f_alt NOT FOUND, (3) timing live-frame NOT DEMONSTRABLE without a writer thread, (4) durability across H16.4/H16.7 UNPROVEN, (5) differential change to f_alt NOT OBSERVED. Missing all but (5) baseline. No upgrade on futex behavior alone. No crash/reboot/hang used as proof (all runs clean EXIT, REBOOTS 0).

## 9. Next bottleneck

Only one: stock stack+heap disclosure (learn live `[W_waiter+0x38]` address and `&f_alt.pi_mutex` value) before any new stamp attempt, then a fresh dest+value path outside the closed surface (new syscall family, new driver, or stack-derived dest; do not repeat the same depth<=3 window as-is).

---
BOTTOM LINE:

* writer beyond birth: none (1 birth stp, 0 post-creation, requeue/rollback/dequeue/enqueue/sched all read-only for +0x38).
* second primitive present: none (33 EXACT all rejected: 9 heavy KPTR + 3 int/derived + 21 spills; atomics 0; ioctl 0 exact; poll GEOMETRY_ONLY).
* H16 dest controllable: no (poll near-miss +8/+20 stock, exact only under lab with wrong value).
* value &f_alt controllable: no carrier (PI LEA register-only zero spills; 0 UPTR at exact).
* strongest candidate: none (nearest `__vmalloc [sp]` transient + wrong type, rejected).
* tested on stock: yes, fidelity matrix re-ran (6 modes, zero panic, zero reboot).
* H16 changed: no (never attempted, no carrier).
* retarget observed: no (walk follows f_target, ignores f_alt).
* single next bottleneck: stock disclosure, then fresh path.
