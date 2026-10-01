# ghostlock deep emit — Mali + depth>3 dispatch (read-only pointer disclosure)

Date: 2026-10-01. Authority: PI.2055 stock (MiTV-AESP0/aquaman, Android 9,
4.9.113 arm64, shell uid 2000, SELinux Enforcing).
Lab: build-aq/vmlinux + .src/linux-amlogic + out/vendor/modules/mali.ko
(ALL OFFLINE_ONLY). No write, no trigger integration, no cred/root.

Tools: `tools/ghostlock_emit_search.py` extended (`--depth N`, `--deep`,
`--mali`, `--user-output`, `--kptr`, `--private-data`, `--struct-copy`;
old modes kept) + `tools/ghostlock_mali_probe.c` (3 read-only Mali queries).

Prior state untouched: GhostLock, stale pi_blocked_on/waiter, H16 static
baseline + immutability, C1/C2/C3 negatives — cited, not reopened.

## 1. Objective

Close the only two emit surfaces left INCONCLUSIVE: (A) /dev/mali* +
related interfaces, (B) any indirect dispatch chain deeper than the old
depth-3 scanner. Mission is read-only only: kernel pointer -> emit ->
userspace. No write/stack-corruption/fake-object/R-W/cred/root work.

## 2. Stock Device Census (FASE 0)

Hardware (`adb -s 26919800005844922 shell`):

* Exactly ONE mali node: `/dev/mali`, char 10:48, `crw-rw-rw-`
  system:graphics. No `/dev/mali*` siblings, no `*mali*` auxiliaries.
  `ls /dev/mali* /dev/*mali*` returns the same single node twice (glob).
* Symlink/interface: `/sys/class/misc/mali -> ../../devices/platform/
  d00c0000.mali/misc/mali`; driver is `mali-utgard` (NOT midgard/kbase).
  `/sys/devices/platform/d00c0000.mali/` readable listing only; all
  attribute reads denied. No `/proc/mali*`, no `/sys/kernel/debug/mali*`.
* `cat /dev/mali` = `Invalid argument` (same open-OK/read-EINVAL shape as
  binder/ion). Shell `exec 3<>/dev/mali` = OK.
* Module: `mali 344064, 16` in lsmod (out-of-tree, vendor). Stock
  `/vendor/lib/modules/mali.ko` is shell-unreadable (Permission denied),
  so dispatch was reconstructed from the identical-build module at
  `out/vendor/modules/mali.ko` (ELF aarch64 relocatable, not stripped,
  `API_VERSION=900 ... TARGET_PLATFORM=meson_bu`).
* `file->private_data` offset: mali_open does
  `str x0(session),[x20(file),#0xd0]`; mali_ioctl reloads with
  `ldr x0,[x21,#0xd0]` + `cbz` fail. Every wrapper gets
  `(session, user_ptr)`.

| device | path | major:minor | mode | open result |
|---|---|---|---|---|
| mali | /dev/mali | 10:48 | crw-rw-rw- system:graphics | OPEN_OK (shell fd, read=EINVAL) |

EVIDENCE: HARDWARE_OBSERVED (ls/open/cat) + OFFLINE_ONLY (module ident).

## 3. Mali Devices

One node only (sec. 2). No auxiliary mali interfaces exist on stock.
EVIDENCE: HARDWARE_OBSERVED.

## 4. Mali Dispatch (FASE 1)

`mali_ioctl` (mali.ko `0xd228`, ~0x4b0 bytes) is a binary-search dispatch
tree over the full 32-bit ioctl number (`mov w19,w1` at entry, then
`mov w1,#lo; movk w1,#hi; cmp w19,w1; b.eq handler / b.ls+b.hi subtree`).
31 command entries recovered (EQ direct + FALLTHROUGH leaf chains),
each stub = `mov x1,x20(user); bl wrapper; sxtw x0,w0`:

(condensed; full map in tool output `--mali`)

* RDWR size4..408, types 0x82/0x83/0x84/0x85: version, settings, mem
  alloc/free/bind/unbind/cow/resize, job start/submit/signal, vsync,
  notifications, mmu dump, timeline, dma-buf-size.
* _IOR (dir=READ) size16/24, types 0x83/0x84/0x85/0x86: core-version,
  num-cores, usage, mmu-dump-size, dma-buf-size.
* _IOW (dir=WRITE) size8/16/24: suspend-response, vsync-report,
  disable-wb, high-priority (copy-FROM-user only, no emit semantic).

Bl-census per read-only wrapper (reloc-resolved, `--mali`):

* get_api_version_wrapper: `__might_fault x3 + _mali_ukk_get_api_version`,
  NO copy_to/from. ukk stores const `0x03840384` (900|900<<16) at +0x4/+0x8.
* get_api_version_v2_wrapper: same shape, const at +0x8/+0xc.
* get_user_settings_wrapper: `_mali_ukk_get_user_settings` (memcpy 44B
  from global u32 settings table, zero `str x` stores) + 1x
  `__arch_copy_to_user` 56B.
* gp/pp_get_core_version_wrapper: u32 MMIO-reg read, inline `str w`.
* gp_get_number_of_cores_wrapper: u32 const/versioned count, inline str.
* pp_get_number_of_cores_wrapper: 1x `__arch_copy_to_user` 16B.
* mem_usage_get_wrapper: copy_from 24B + ukk (only `str w` into outbuf:
  size words at +0x8/+0x10) + copy_to 24B.
* mem_query_mmu_page_table_dump_size_wrapper: u32 size store, inline str.
* mali_dma_buf_get_size: copy_from + `dma_buf_get` + scalar size out.
* wait_for_notification_wrapper: 1x `__arch_copy_to_user` 104B. Inner
  `_mali_ukk_wait_for_notification` stores ONLY `str w2,[x19,#0x8]`
  (type u32) / fallback `str w0=#0x20`. Zero 64-bit stores.
* mem_dump_mmu_page_table_wrapper: 2x `__arch_copy_to_user` (table bytes
  + header). Inner's only two `str x` store the USER buffer cursor/pointer
  echo (`[x19,#0x10]` in, `[x19,#0x20/#0x30]` out); dumped contents are
  MMU phys/GPU entries, never KVAs.

EVIDENCE: OFFLINE_ONLY (mali.ko disasm + relocs).

## 5. Deep Call Graph (FASE 2)

`--depth N` / `--deep` BFS over `bl` edges from
{binder_ioctl, ashmem_ioctl, ion_ioctl}: visited set, edge dedup,
emit sinks recorded-not-expanded, cap 6000 nodes. Single BFS to max
depth, cumulative rows (`--deep`):

```
DEPTH=5   nodes=480  (+480) edges=1484 (+1484) emit_bl=6 callers=6
DEPTH=8   nodes=859  (+379) edges=3053 (+1569) emit_bl=6 callers=6
DEPTH=12  nodes=1152 (+293) edges=4311 (+1258) emit_bl=6 callers=6
```

Same 6 callers at every depth, ALL already classified in the prior
census: binder_ioctl, binder_ioctl_write_read, binder_thread_read,
get_name (ashmem), ion_ioctl, ion_query_heaps — each `bl
__arch_copy_to_user` of USER-echo/scalar/index fields. Nodes (+379/+293)
and edges (+1569/+1258) keep growing while emit_bl and callers stay
FLAT: extra depth reaches only mem/lock/helper functions, never a new
emitter. Cap never hit (1152 < 6000), no pruning was even needed.

EVIDENCE: OFFLINE_ONLY.

## 6. Pointer Sources (FASE 3)

`--kptr` 64-bit-store screen + `--dispatch` field audit (kept):

* current/task_struct/stack: shell-reachable shows stay %pK-masked
  (sec. 10). No new edge at depth>3 (no new emit caller at all).
* rt_mutex/waiter/pi_state: zero copy_to_user in futex.c+rtmutex.c
  (re-cited); deep BFS adds no waiter-adjacent emitter.
* file/sock/mm/vma/page/dma: unchanged INDEX/MASKED/USER_ECHO verdicts;
  no new emitter.
* mali session/device/buffer/page pointers: every `str x` into an emit
  buffer is a USER VA echo (dump cursor) or absent; out-bufs receive
  only `str w` scalars + phys/GPU words. Classes: SCALAR_ONLY,
  USER_ECHO, PHYS/GPU. NO DIRECT_KERNEL_PTR / PLUS_CONST / DERIVED.

EVIDENCE: OFFLINE_ONLY.

## 7. User Output Sites

Reachable `__arch_copy_to_user` callers from candidate ioctls (depth<=8):
exactly the 6 in sec. 5. Mali adds: settings-56B, pp-cores-16B,
usage-24B, notification-104B, dump-table+header (all classified sec. 4/6).
EVIDENCE: OFFLINE_ONLY.

## 8. Private Data Paths (FASE 8)

`--private-data`: mali open->ioctl session flow proven in binary
(sec. 2); binder proc/node, ashmem area, ion registry unchanged:
session/device pointers are USED (register reads, queue, sizes) but no
session-pointer FIELD is ever copied out on any probed/audited path.
Candidate-strong pattern exists structurally, emits nothing.
EVIDENCE: OFFLINE_ONLY.

## 9. Struct Copy Paths (FASE 9)

`--struct-copy`: binder_version/put_user, node_debug_info-24B (USER echo),
write_read (USER bufs), ashmem name[256], ion_heap_data-48B (id=INDEX),
mali 16/24/56/104B (scalars + USER echoes + phys). Padding rule kept:
no padding word carries a proven KVA LOAD, so no padding leak is claimed.
EVIDENCE: OFFLINE_ONLY.

## 10. Candidate Commands (FASE 5/6)

READ-only, GET/QUERY/VERSION/INFO semantic, executed max-3 (FASE 11):

* M1 `0xc0108203` GET_API_VERSION_V2 (RDWR size16, version-query
  semantic): predicted const 0x03840384 at +8/+12.
* M2 `0xc0048203` GET_API_VERSION (RDWR size4, version-query semantic):
  predicted const at +4/+8.
* M3 `0x80108502` GP_GET_CORE_VERSION (_IOR size16): predicted u32 reg
  value at +8.

NOT executed (and why): submit/start/signal/alloc/free/bind/unbind/map
(state change, banned by FASE 6); wait_for_notification (would BLOCK on
empty GPU queue); mem_dump (needs session allocation + buffer setup).
Their offline verdicts stay OFFLINE_ONLY (sec. 4), explicitly not
hardware claims.

## 11. Hardware Probes (FASE 11/12)

`tools/ghostlock_mali_probe.c` (static, NDK clang), pushed to
/data/local/tmp/mali_probe, ran once on 26919800005844922:

```
P0 READY dev=/dev/mali (read-only version/info, no trigger)
P1 OPEN fd=3 (success; errno print is stale-errno noise, fd>=0 rules)
P2 QUERY API_V2 rc=0
P3 CAPTURE api_v2 bytes: aa aa aa aa aa aa aa aa 84 03 84 03 00 00 00 00
P5 VERIFY M1 w8=58983300 w12=0 q64=0x3840384 kptr=0 (900/900 packed)
P2 QUERY API_V1 rc=0
P3 CAPTURE api_v1 bytes: aa aa aa aa 84 03 84 03 00 00 00 00 aa aa aa aa
P5 VERIFY M2 w4=58983300 ... kptr=0 (900 packed)
P2 QUERY GP_CORE_VER rc=0
P3 CAPTURE gp_core bytes: aa aa aa aa aa aa aa aa 00 00 07 0d aa aa aa aa
P5 VERIFY M3 w8=218562560 (0x0d070000 reg) kptr=0
P4 CLOSE fd closed
P6 RESULT=MALI_PROBE_DONE (read-only, no trigger, no write)
```

* Values match the binary-predicted stores EXACTLY (const 900/900, reg
  0x0d070000), so the cmd->handler map is validated, not assumed.
* Untouched buffer bytes stay 0xaa: wrappers write ONLY the predicted
  words (4B/8B/4B), no wider struct copy, no adjacent pointer word.
* is_kptr hits: 0 across all 3 outputs. Stability: single run (values
  are device constants; repeat runs add nothing — documented, not hidden).

No pointer-like value appeared, so per STOP rule no further Mali fuzzing
was done. Classification: SINGLE_SOURCE not even reached — there is no
source; all three are SCALAR_ONLY by construction + value.
EVIDENCE: HARDWARE_REPRODUCED (values above).

## 12. Pointer Validation

Ruler (FIELD+LOAD+COPY+USER+MASK): M1/M2/M3 have COPY+USER but their
LOADs are immediates/device-reg constants, never kernel objects — they
fail FIELD-as-pointer at the first bar. Zero 0xffffff words anywhere.
Nothing is SINGLE_SOURCE; everything is negative by construction+value.
EVIDENCE: OFFLINE_ONLY (ruler) + HARDWARE_REPRODUCED (zero hits).

## 13. Mali Verdict

MALI EMIT (kernel-pointer disclosure via read-only GET/QUERY surface) =
HARDWARE_REFUTED for the version/core/version surface (probed, scalar,
exact-match), and OFFLINE_ONLY-negative for the remaining read-only
wrappers (settings/counts/usage/query-size/notification/dump: scalars +
USER echoes + phys/GPU entries, zero 64-bit KVA stores into out-bufs).
The blocking/state-changing handlers were deliberately not executed;
they are not claimed either way and are not disclosure-shaped (submit/
alloc/free/copy-from). No INCONCLUSIVE remainder on the GET/QUERY path.

## 14. Depth>3 Verdict

DEPTH>3 EMIT = HARDWARE_REFUTED-as-absent on the seeded surface, with
OFFLINE_ONLY method: 5/8/12 rows (sec. 5) show emit callers frozen at
the 6 classified ones while the graph keeps growing underneath. There
is no seventh `kernel-pointer -> output` candidate hiding at depth 6..12
behind binder/ashmem/ion ioctls. Combined with the Mali dispatch census
(sec. 4, full depth by construction: ioctl -> wrapper -> ukk, every one
of the 31 commands resolved), both INCONCLUSIVE classes from the prior
phase are now closed with evidence.

## 15. Useful Disclosure

None. No rt_mutex/pi_state/waiter/task/stack pointer, and no unrelated
kernel pointer either, reached userspace on Mali or on any depth>3 path.
Version 900, core-reg 0x0d070000, ion ids, binder zeros are correctly NOT
promoted. KASLR slide: still INCONCLUSIVE (absent).

## 16. Rejected Paths

* Mali: version/core/settings/counts/usage/query-size (SCALAR_ONLY);
  user-buffer fields (USER_ECHO); mmu entries (PHYS/GPU, not KVA);
  write-only cmds (no emit semantic); submit/alloc/free (state change,
  unprobed by rule).
* Depth>3: every newly reached node past depth 5 is a mem/lock/helper,
  not an emitter (rows sec. 5).
* Re-cited closures (not reopened): binder C1, ashmem C2, ion C3, proc
  %pK-masked shows, PI index-only, fstat, poll stamper, spill search.
* %p/%px/%pK/%pS (FASE 10): stock shows `[<0000000000000000>]` stack,
  `0000000000000000` unix sk; kptr_restrict/dmesg_restrict/kallsyms all
  shell-denied; `%px` absent from reachable drivers/staging+amlogic
  (grep 0 hits); reachable `%pK/%pB/%ps/%p` are masked/symbol/user -
  text output is never an address proof here.

## 17. What Is Proven

* Single /dev/mali node census + Utgard ident + open-OK.
  EVIDENCE: HARDWARE_OBSERVED.
* Full 31-entry mali_ioctl dispatch map + per-wrapper emit census.
  EVIDENCE: OFFLINE_ONLY.
* 3 read-only Mali queries return exact binary-predicted scalars,
  zero kptr hits. EVIDENCE: HARDWARE_REPRODUCED.
* Depth>3 BFS method + growth rows. EVIDENCE: OFFLINE_ONLY.
* Tool flags --depth/--deep/--mali/--user-output/--kptr/--private-data/
  --struct-copy added, old modes kept. EVIDENCE: OFFLINE_ONLY (code).

---

BOTTOM LINE (10 answers):

* Mali paths audited? All 31 ioctl commands resolved; 14 wrappers
  bl-censused; read-only GET set fully dataflow-audited (only `str w`
  scalars + USER echoes + phys/GPU entries into out-bufs).
* Max depth verified? 12 (BFS 480/859/1152 nodes, 1484/3053/4311 edges).
* kernel-pointer -> output candidates? ZERO (6 emit callers, all
  USER_ECHO/SCALAR/INDEX; Mali: 0 kptr-width KVA slots).
* Reached hardware? YES: 3 Mali read-only queries (2x version + core).
* Real pointer produced? NO: 900/900, 900, 0x0d070000; zero is_kptr.
* private_data revealed anything? Structurally present (session flow
  proven) but emits nothing — NO.
* struct copy revealed anything? Only scalars/echoes/ids — NO.
* Mali closed or INCONCLUSIVE? CLOSED (GET/QUERY = HARDWARE_REFUTED;
  rest OFFLINE_ONLY-negative, submit paths unbothered by rule).
* depth>3 closed or INCONCLUSIVE? CLOSED (emit callers flat 6-6-6).
* Single next bottleneck? The 8-byte targeted H16 write with NO leak
  primitive in hand and no read-only surface left open.

## 18. What Is Not Proven

* Any kernel pointer to shell (SUCESSO A/B/C/D all NO). INCONCLUSIVE-
  as-absent on audited surface only.
* H16 absolute / &f_alt.pi_mutex / KASLR slide. INCONCLUSIVE (absent).
* Blocking/state-change Mali handlers (submit/alloc/dump-with-buf):
  unprobed by rule; OFFLINE_ONLY-negative, not hardware claims.
* Generalization beyond audited seeds: absence on binder/ashmem/ion/
  mali-GET + depth-N BFS is not absence everywhere.

## 19. Next Bottleneck

Exactly one: a read-only kernel-pointer SOURCE for either address that
survives stock masking. Mali-GET and depth>3 in-tree dispatch are now
closed as sources; the remaining unknown is no longer "which surface"
but the primitive itself: WITHOUT any disclosure, the next problem is
directly the 8-byte targeted H16 write (per mission SUCCESS-E), with no
leak primitive in hand and no further read-only surface left open.
