RESULT: NO_LEAK_SOURCE

> DIRECTION (2026-10-02, see `reports/CURRENT_STATE.md`): principal is
> post-free stack reuse + disclosure; H16 live retarget is secondary;
> reclaim without verifier, audited live H16 writer search, fake object,
> arbitrary R/W, cred/root are closed. Post-free reuse is not demonstrated
> on Aquaman. Live-retarget was audited and not demonstrated.
REFERENCES_ANALYZED: 5
COMMON_LEAK: kernel-VA disclosure before forge in every port (side-channel or perf/boot_id/fixed-base, never proc copy_to_user)
COMMON_REUSE: same-thread post-return STACK_REUSE over freed rt_mutex_waiter frame + separate SLAB_REUSE for fake page (except canonical x86 which uses CEA alias instead of slab)
AQUAMAN_HAS: trigger YES + consumer YES + stale-object-type YES (static), second-syscall carriers present in source but overlap unproven
AQUAMAN_MISSING: any kernel-VA disclosure as bytes on audited surface (POINTER_BYTES_FOUND 0, 22 tests)
NEXT_SINGLE_BOTTLENECK: stock kernel-stack-address or heap-address disclosure source readable by shell uid 2000

# ghostlock disclosure stack-reuse gap 2026-10-01

Date: 2026-10-01. Scope: architectural comparison only. No fuzzing, no spray
without hypothesis, no exploit run, no third-party exploit executed, no root,
no cred overwrite, no arbitrary R/W, no kernel patch, no flash, no SELinux
bypass. No device scan this round. All Aquaman device claims cite prior
reports on BOOT_ID 3ec336a5-439f-497f-b9f7-08fd7441b174. All reference claims
cite writeup plus raw-file audit (file/function level, no code copied, no
offsets ported).

Prior closed state cited, not reopened: LEVEL_2 consumer matrix
(base_t/occ_base/trg_inwin TIMEOUT, occ_tgt/alt_tgt EDEADLK), H16 live-write
NO_EXACT_WRITER_FOUND, stock disclosure NO_DISCLOSURE_FOUND (22 tests,
POINTER_BYTES_FOUND 0), mm reclaim FAIL (hits=0), SAME_ARCHITECTURE_GAP
(`reports/ghostlock-reference-comparison-2026-10-01.md`).

Question for this round only: how do known ports turn a freed waiter into
reusable observable storage, and what is the Aquaman ARM64 4.9.113 equivalent.
No write hunt. No final primitive.

## 1. References

| project | kernel | arch | confidence this round |
|---|---|---|---|
| NebuSec canonical x86_64 (IonStack CVE-2026-43499) | kernelCTF LTS 6.12.80 generic | x86_64 | code-confirmed: `nebusec.ai/research/ionstack-part-2` full writeup + `CyberMeowfia/IonStack/CVE-2026-43499/poc/poc.c` raw (trigger trio, stamps[], consumer) |
| Hazel ARM32 (dorlow hazel-cve-2026-43499) | Toshiba hazel 4.9.113 ARM32, PS7716.5665N hw-tested | ARM32 | code-confirmed: `hazel_reclaim.h` raw (ks_* leak + reclaim) + `hazel_root.c` raw (waiter/owner/consumer + stamp_stack) |
| Fire TV 5.10 (R0rt1z2 GhostLock-5.10, Quest3 lineage) | Fire OS 8 5.10 sunstone/karat | ARM64 | partial: `src/slide.c` + `src/q3slide.c` + `src/main.c` + `src/util.c` + `src/rootchain.c` raw for leak/chain; reclaim internals README-level |
| OPPO (yijiacloud GhostLock-OPPO-PCKM00) | OPPO PCKM00 4.14.180-perf+ SM6150 | ARM64 | code-confirmed: `exploit/src/slide.c` + `main.c` + `util.c` + `fops.c` raw |
| Shield (cyberbalsa GhostLock-NVIDIA-Shield-9.2.4) | Shield mdarcy 4.9.141-tegra SE 9.2.4 | ARM64 | README/PORT_STATUS-level only, no .c audit this round; closest 4.9 kin, treated as low confidence for code locations |

No README-only verdict accepted where raw was available. Fire TV reclaim and
all Shield code locations stay README-level and are marked as such below.

## 2. Leak primitive comparison

Tabela exigida: project / source / object leaked / required condition.

| project | source (code location) | object leaked | required condition |
|---|---|---|---|
| NebuSec | prefetch timing side-channel (`ionstack-part-2` sections Prefetch ASLR Leak + CEA spray; `poc.c` has no leak, only trigger/stamp demo) | kernel text base (~9-bit slide) + physmap base, then `cea_direct = physmap_base + CPU1_CEA_BASE` | x86 prefetch timing oracle + KPTI off on target (kernelCTF); EntryBleed pairing if KPTI on. Not a copy_to_user leak. |
| Hazel | futex-hash timing Kernelsnitch (`hazel_reclaim.h`: `ks_measure` FUTEX_WAKE_PRIVATE timing, `ks_find_collisions_child` pile 2048 + arena 16384 pages x 20 repeats, `ks_hash` backported 16-byte key [mm,pad,address,offset], `ks_solve_mm` 4-thread brute over 0xc0000000 range, `alloc_held_mm` via /proc/pid/mem held fds) | mm_struct heap address (32-bit ARM32), then `page_base = leaked_mm & ~(8K-1)` + slot index check on 0x1c0 grid | controllable futex hash collisions + ability to hold/free mm descriptors via fork/memfd; timing stable on target. Leak runs before trigger threads. |
| Fire TV 5.10 | perf callchain sampler (`src/q3slide.c:getkerneltextstart`, `src/slide.c:slide_leak_kernel_base`): perf_event_open tracepoint sys_enter_getpid/gettid/getuid else HW_CPU_CYCLES / SW_PAGE_FAULTS / SW_CPU_CLOCK, IP+callchain 24 entries, ktext filter 0xffff.., bucket histogram shift 21, densest bucket = text_start | kernel text start (KASLR slide) | perf_event_open reachable by unpriv + tracefs/syscall ids or HW counters; per-build P0/phys calibration in `src/targets`. Generic kernel feature, not Android/vendor specific. |
| OPPO | two-stage: (a) boot_id pre-leak (`exploit/src/slide.c:slide_read_stext` reads /proc/sys/kernel/random/boot_id, parses 16B as LE pointer, checks >>48==0xffff, subtracts `p0_alias_image_offset(SLIDE_NFULNL_LOGGER)` = stext); (b) fops verify (`exploit/src/fops.c:leak_kernel_base` reads ashmem_fops open/ioctl/mmap/release slots via configfs primitive, checks against `text_addr()` expectations, derives base) + Kernelsnitch mm leak (`exploit/src/util.c:prepare_kernel_page`, same family as Hazel, order-3 32K window, retries over mm sizes 0x370-0x400) | (a) kernel data pointer (nfulnl logger alias) -> KASLR base; (b) kernel text pointers via fops slots; mm page base via Kernelsnitch | world-readable boot_id path + pre-shaped kernel page (`prepare_good_kernel_page(PAGE_PAYLOAD_SLIDE)`) before route; fops stage needs reclaimed page already working. Same primitive family as Hazel, variation = boot_id shortcut + verify pass. |
| Shield | fixed-base or slide-mcast full-lock (`PORT_STATUS.md`: link `_text 0xffffff8008080000`, runtime offset disabled; env `GHOSTLOCK_FIXED_BASE=1`, `GHOSTLOCK_MAIN_ROUTE=slide-mcast`, `GHOSTLOCK_SLIDE_FULL_LOCK=1`) | kernel text base (trivial if fixed) or slide-derived base; order-2 mm page base via shaped reclaim (README-level) | no-KASLR build collapses disclosure; otherwise same slide family. Code-level source not audited this round. |

Answers Fase 1:

- NebuSec: leaked info = text slide + physmap base, not waiter bytes. Syscall/path = prefetch timing loop in userspace, no syscall produces bytes. Class: neither stack/heap/task copy; timing oracle yielding KERNEL text + direct-map alias (used as known storage address).
- Hazel: leak before reclaim = mm_struct heap address via futex-hash timing. Correlation to waiter = none directly; leak gives reclaim page base for fake objects, waiter forged separately by stack stamp. Files above.
- Fire TV: kernel pointer source = perf ring buffer sampled IPs, generic kernel perf, not Android/vendor specific. Per-build calibration only.
- OPPO: same Kernelsnitch family as Hazel, variation = boot_id data-pointer shortcut for initial slide + fops slot read-back as verification. Both code-confirmed.
- Shield: equivalent on 4.9 = fixed base (no leak needed on that build) or slide-mcast variant. README-level only.

Common pattern: every port leaks before forging because fake
task/lock/table pointers must be valid kernel VAs. Zero ports leak
`W_waiter+0x38` or waiter->lock value directly; all leak an anchor (text,
physmap/CEA, mm page, fops slot, boot_id data pointer) that lets them compute
forge addresses.

## 3. Reuse primitive comparison

Tabela: project / freed object / reuse target / mechanism. Classification per
task spec.

| project | freed object | reuse target | mechanism |
|---|---|---|---|
| NebuSec | stack `rt_mutex_waiter` (waiter thread `FUTEX_WAIT_REQUEUE_PI` frame; `struct rt_mutex_waiter` tree+pi_tree+task+lock+wake_state) | same thread kernel stack, overlapping frame via `prctl(PR_SET_MM,PR_SET_MM_MAP)` auxv copy into `user_auxv[AT_VECTOR_SIZE]` stack buffer; alternates in `poc.c:stamps[]` = setsockopt/pselect/keyctl/TCP-getter/process_vm/timerfd/futex | STACK_REUSE. Waiter really stack YES. Same thread YES (waiter returns, then prctl). Second syscall YES. Same CPU NO (thread-bound, CEA per-CPU handled via physmap). Prior leak YES (prefetch text+physmap). |
| Hazel | same stack waiter (ARM32 4.9, same futex.c path) | same-thread stack stamp via `setsockopt(MCAST_JOIN_SOURCE_GROUP)` 260B buf (`hazel_root.c:stamp_stack`, `prepare_stack_stamp`, payload 0xc0 via `make_reclaimed_write_payload` target ASHMEM_MISC_FOPS); separate fake page via AF_UNIX full-page reclaim (`hazel_reclaim.h:setup_socket_reclaim`, `launch_socket_reclaim`, `find_fake_fops_word` MSG_PEEK verifier) | STACK_REUSE (waiter) + SLAB_REUSE (mm 8K cross-cache). Same thread YES. Second syscall YES (setsockopt after WAIT return + UNLOCK_PI). Same CPU pinned (WAITER_CORE/CONSUMER_CORE profile). Prior leak YES (Kernelsnitch before threads). |
| Fire TV 5.10 | same stack waiter (Quest3 lineage) | same-thread stack stamp family (`src/rootchain.c:stamp_once` -> `exp_stack_once`; exact stamper .c not pinned this round) + pipe-oriented reclaim order-3 class (README-level) | STACK_REUSE + SLAB_REUSE (README-level for reclaim). Same thread YES. Second syscall YES. Same CPU assumed pinned. Prior leak YES (perf slide). Reclaim code confidence README only. |
| OPPO | same stack waiter (4.14 layout comment in `slide.c:prepare_slide_pselect_fdsets`: tree 0x00, pi_tree 0x18, task 0x30, lock 0x38, prio 0x40, deadline 0x48, size 0x50; `PSELECT_WAITER_WORD_SHIFT=2`, waiter offset=(fd_set word-2)*8) | same-thread pselect fd_set copy (`exploit/src/fops.c:prepare_pselect_fdsets` in[2]=fake_w0, out[3]=INIT_TASK, out[4]=fake_lock, ex[0]=prio; `do_pselect_fake_lock_route` + `main.c:waiter_thread` calls it after WAIT return) + Kernelsnitch order-3 page (`util.c:prepare_kernel_page`) | STACK_REUSE + SLAB_REUSE. Same thread YES. Second syscall YES (pselect timeout). Same CPU pinned (`pin_to_core`). Prior leak YES (boot_id slide + page_base before route). |
| Shield | same stack waiter at deterministic displacement +0xb0 (`PORT_STATUS.md` chain step 2) | MCAST_BLOCK_SOURCE deterministic stamp + order-2 mm slab reclaim with shaped skb + mixed payload -> fake rt-mutex/task -> ashmem_misc.fops (pipe stage NOT used) | STACK_REUSE + SLAB_REUSE (both README-level). Same thread YES (implied). Second syscall YES. Same CPU implied pinned. Prior leak trivial (fixed base) or slide variant. |

No port does live `waiter->lock` overwrite from another thread while the
FWRQ frame is alive. All replace whole object after return. All need second
syscall on same thread. All need prior leak (except fixed-base Shield where
base is known).

## 4. Aquaman mapping

Aquaman base: 4.9.113 vendor ARM64, THREAD_SIZE 16384
(`arch/arm64/include/asm/thread_info.h:32`), THREAD_INFO_IN_TASK=y, SLUB,
RANDOMIZE_BASE=y, CHECKPOINT_RESTORE=n, SLABINFO=n, Enforcing shell uid 2000.
Struct: `kernel/locking/rtmutex_common.h:25` rt_mutex_waiter without
DEBUG_RT_MUTEXES = 0x50 bytes. Vulnerable path present in source:
`kernel/locking/rtmutex.c:remove_waiter` clears `current->pi_blocked_on`
(should be waiter->task), called from `rt_mutex_start_proxy_lock` EDEADLK
rollback; birth site `kernel/futex.c:futex_wait_requeue_pi` stack local
`rt_waiter`.

| stage | status | evidence |
|---|---|---|
| trigger (FWRQ/FCRQ trio -> EDEADLK) | YES | LEVEL_2 history preserved same BOOT_ID; prior matrix base_t/occ_base/trg_inwin TIMEOUT, occ_tgt/alt_tgt EDEADLK; cited from reference-comparison, not re-run. |
| consumer (PI walk reaches stale waiter) | YES | FUTEX_LOCK_PI differential (occupied+stale=EDEADLK else TIMEOUT); binary task_blocks ldr x25,[x0,#0x38] + adjust head ldr x0,[x28,#0x38]/cmp gate; prior consumer report. |
| stale object type (stack rt_mutex_waiter via pi_blocked_on) | YES (static only) | source birth + remove_waiter misuse above; no bytes observed; plausible, not byte-proven. |
| disclosure (any kernel VA as bytes: stack base / frame pos / heap / object) | NO | NO_DISCLOSURE_FOUND on audited surface; POINTER_BYTES_FOUND 0 over 22 tests (proc stack/wchan/syscall/stat/sched/net-unix/tcp/kallsyms/dmesg/debug/tracing/slab/buddyinfo + binder/ashmem/ion/ge2d/vfm + disclose 23/24 + PI copy audit 0 hits); stock-disclosure + next-bottleneck reports. |
| reuse (post-free controlled bytes under consumer) | NO | zero controlled bytes ever landed; poll dist=0 proves page/SP reuse only; pselect history 6/6 reboots cited in reference-comparison; MCAST overlap uncalculated; H16 live-write census empty and in any case wrong mechanism (zero precedent). |
| controlled object consumed by walk | NO | fidelity shows walk follows birth f_target, ignores f_alt; no fake consumed. |
| read/write or physrw primitive | NO | out of scope until above moves; none. |

Only YES with evidence. Reuse/stack-overlap and any address stay NO.

## 5. Missing primitive

Single choice (one only):

```text
NO_LEAK_SOURCE
```

Why this one and not the others:

- NO_STACK_REUSE_PATH rejected as single: second-syscall carriers exist in
  Aquaman source (`fs/select.c:core_sys_select` pselect fd_set copy;
  `net/ipv6/ipv6_sockglue.c:do_ipv6_setsockopt` MCAST group_source_req 260B
  copy_from_user). Overlap geometry vs freed 0x50 waiter frame is unproven and
  pselect history is adverse, but path is not Kconfig-absent.
- NO_OBJECT_REUSE_PATH rejected: same reason, slab side (SLUB, mm order-2
  plausible) was tried and FAILed (hits=0) but not Kconfig-impossible.
- ARCHITECTURE_DIFFERENCE rejected: Aquaman shares trigger/consumer/stale-type
  with all refs including 4.9 kin Shield; canonical x86 specifics (CEA,
  DirtyMode, PR_SET_MM_MAP) differ, but ARM ports prove same arch family works
  via pselect/MCAST + mm reclaim. Difference is missing stage, not different
  architecture.
- NO_LEAK_SOURCE selected: earliest hard blocker in every reference chain.
  Without a valid kernel VA, forge is impossible (task/lock/table pointers
  must be valid). Aquaman audited surface yields zero bytes; Kconfig/policy
  closes obvious sources (kptr_restrict/dmesg_restrict/SELinux deny,
  SLABINFO=n, slab attrs 0400, trace disabled/denied, PI path 0 copy_to_user).
  Canonical stamper PR_SET_MM_MAP is additionally compiled out
  (`CONFIG_CHECKPOINT_RESTORE is not set`, `kernel/sys.c:prctl_set_mm_map`
  behind ifdef), so even the x86 reuse carrier is absent at Kconfig level.

Fase 4 lifetime (source-only, no device):

- Birth: `futex_wait_requeue_pi` stack local `rt_waiter` (`kernel/futex.c`
  ~2858, comment waiter allocated on our stack, manipulated by requeue while
  we sleep).
- Free: function return pops frame (`out_put_keys/out_key2/out` + hrtimer
  cancel path); stale `pi_blocked_on` dangles into popped frame after EDEADLK
  rollback in `rt_mutex_start_proxy_lock`.
- On kernel stack YES (local, THREAD_SIZE 16K).
- Syscall returning after free: the same `FUTEX_WAIT_REQUEUE_PI` (syscall A).
  Model holds: syscall A creates+free waiter, returns to userspace; syscall B
  on same thread must reuse stack. Candidates in source: syscall B = pselect6
  (`fs/select.c:do_pselect/core_sys_select` stack_fds + get_fd_set copy) or
  setsockopt MCAST (`ipv6_sockglue.c` greqs copy). Overlap vs waiter frame
  uncalculated; no claim made.
- Address source before reuse: none found on audited surface. Mark:

```text
NO_ADDRESS_SOURCE_FOUND
```

Fase 5 re-target (not W_waiter+0x38): sought kernel stack base or any VA
locating freed storage. Result on audited surface:

```text
NO_POINTER
```

(not KERNEL_STACK_ADDRESS, not HEAP_ADDRESS, not OBJECT_ADDRESS).

## 6. Next bottleneck

One only:

- Finish read-only disclosure census for a shell-reachable kernel-VA emit:
  perf_event_open callchain reachability + remaining /dev ioctl struct-field
  audit with source-visible copy_to_user, EMIT-only, no blind ioctls, no
  UAF walk, no stamper, no fake, no reclaim retry. Stop at first address
  byte; then re-run disclosure ruler before any reuse geometry thinking.
  No device run executed this round; matrix below is hypothesis-only.

Fase 6 matrix (no test executed, comparison only):

```text
candidate | why exists | test | result
(none proposed) | no reference primitive has a proven Aquaman equivalent yet | no device test | NOT_RUN
```

Device work stays closed until a stock address discloses. No new scans.

---

Conclusions (only these four):

1. Leak ports use: prefetch timing (NebuSec text+physmap/CEA), futex-hash
   timing mm leak (Hazel/OPPO Kernelsnitch + OPPO boot_id shortcut + fops
   verify), perf callchain text sampler (Fire TV 5.10), fixed-base (Shield
   4.9 build). Every one leaks an anchor VA before forging; none leaks
   waiter->lock value directly.
2. Reuse they do: same-thread post-return STACK_REUSE over the freed waiter
   frame (PR_SET_MM_MAP auxv on x86; MCAST setsockopt on Hazel/Shield;
   pselect fd_set on OPPO/Fire-TV lineage) plus separate SLAB_REUSE for the
   fake page (AF_UNIX skb / pipe_buffer, MSG_PEEK-style verifier), except
   canonical x86 which uses CEA direct-map alias instead of slab.
3. Equivalent in Aquaman: trigger + consumer + stale-type match; pselect and
   MCAST carriers exist in source but overlap unproven; PR_SET_MM_MAP absent
   by Kconfig; slab reclaim tried and FAILed; zero addresses disclosed.
4. Exact missing stage: disclosure. No kernel stack address, no heap address,
   no object address as bytes on audited surface. Reuse geometry cannot be
   validated without it. Single verdict NO_LEAK_SOURCE.
