# GhostLock aquaman plan (Phase 2 + Phase 13-17 + verdict)

## Phase 2 — real config (aquaman-config, 5381 lines, arm64 4.9.113)

| Symbol | aquaman | Hazel 4.9 ARM32 | Aresin 4.14 ARM64 | Practical effect |
|---|---|---|---|---|
| CONFIG_FUTEX / RT_MUTEXES | y / y | y / y | y / y | PI compiled in all 3; 4.9 lacks separate CONFIG_FUTEX_PI |
| CONFIG_PREEMPT (not RT) | y | y | y | Preemptible, race viable |
| CONFIG_DEBUG_RT_MUTEXES | unset | unset | unset | Waiter without debug fields: 0x50 layout |
| CONFIG_SLUB | y | y | y | Same allocator family |
| CONFIG_SLUB_DEBUG | unset | unset | ? | No redzone/poison by default |
| CONFIG_SLAB_FREELIST_RANDOM | unset | unset | n/a 4.14 | Deterministic freelist: aids reclaim |
| CONFIG_SLAB_FREELIST_HARDENED | check* | n/a 4.9 | ? | *grep found neither unset nor set: verify exact line before exploit |
| CONFIG_KASAN | unset | unset | unset | No sanitizer on target |
| CONFIG_HARDENED_USERCOPY | y | y (hazel note) | y | Kernel text reads via configfs rejected; use lowmem addrs (hazel does this) |
| CONFIG_ARM64_VA_BITS | 39 | n/a (ARM32) | 39? (MTK) | PAGE_OFFSET 0xffffff8000000000 |
| CONFIG_KALLSYMS(_ALL,_BASE_REL) | y | y | y | Present but blocked for shell; irrelevant until uid 0 |
| CONFIG_MODULES | y | ? | y | Irrelevant for exploit |
| CONFIG_ASHMEM | y | y | y/n? | Hazel uses; aresin used pipe |
| CONFIG_CONFIGFS_FS | y | y | ? | Hazel uses; Plan B pipe exists |
| CONFIG_UNIX / IPV6 / NET | y / y / y | y / y / y | y | AF_UNIX spray + IPV6 stamper available by config |
| CONFIG_AMLOGIC_SLUB_DEBUG | unset | n/a | n/a | Vendor did not harden SLUB |

Runtime (/dev/ashmem, configfs mount, pstore): pending, checklist in
`ghostlock-ashmem-configfs.md`. Config says "possible", not "present".

## Phase 13 — escalation plan specific to aquaman 4.9.113 ARM64

Order, each step only after previous is green:
1. Offsets: pahole on dangal-built vmlinux + runtime validation
   (Phase 3). Forbidden to blindly copy hazel (ARM32) or aresin (4.14 MTK).
2. Symbols: no kallsyms; anchor swapper + task list after kernel read
   (Phase 8). First profile constructed from local build + mm leak.
3. Heap: measure real slab/mm on device (leak), choose AF_UNIX vs
   pipe; recalibrate ks_* (0x1c0 grid dead on ARM64).
4. Kernel R/W: regenerate configfs blob for LP64 (+0x20 mutex) OR aresin
   pipe route if ashmem/configfs fail at runtime.
5. Current: walk task list with VA39 ranges.
6. Cred: zero 0x20 at cred+4 after confirming DEBUG_CREDENTIALS unset.
7. SELinux: no bypass planned; ceiling = uid 0 in u:r:shell:s0
   (matching hazel). Sufficient for introspection.

## Phase 14 — SELinux

ro.debuggable=0 + Enforcing: uid 0 does not automatically become permissive and
does not alter domain. Hazel proves that uid 0 in shell domain suffices for
diagnostics and data collection, which is our target (Phase 16). Disabling enforcement
or transitioning to init domain = out of scope for this stage.

## Phase 15/16 — temporary root and extraction

Only after Phase 12 progression is fully green. Read-only extraction listed in brief
(kallsyms, config.gz, cmdline, devicetree, modules, iomem, pstore...).
No flashing, nothing persistent.

## Phase 17 — no KernelSU/APatch yet

Temporary uid 0 feeds into the reconstruction of the 2022 kernel; persistence
is evaluated afterwards, once the genuine kernel is available.

## Final answers (13 questions) — updated 2026-09-29 with device data

1. CONFIG_FUTEX_PI enabled? YES by construction (FUTEX=y +
   RT_MUTEXES=y; no separate symbol in 4.9). CONFIRMED ON AQUAMAN KERNEL (config).
2. Exact CVE condition in code? YES in analyzed 4.9.113 tree;
   exact binary INFERRED (without PI.2055 source/vmlinux), but rollback
   via EDEADLK confirmed 5/5 on device.
3. CMP_REQUEUE_PI reachable? CONFIRMED ON AQUAMAN KERNEL (probe 7/7 +
   race 5/5 EDEADLK, 2026-09-29).
4. Hazel usable as structural base? YES for trigger, chain model,
   runtime validation, and daemon; NO for concrete numbers. CONFIRMED ONLY ON ANOTHER DEVICE.
5. What to rewrite for ARM64? Configfs blob (LP64), mm/slab grid, kzhash
   leak, validation ranges, task/cred offsets, stack stamper.
6. Where does Aresin help? Pipe/physmap route (Plan B), 4.9x4.14 difference
   map (rb_node identical, task_struct different), KASLR slide method.
7. Required structs/offsets? Listed in Phase 3; final values only via
   pahole + runtime. NOT PROVEN.
8. Base/symbols without kallsyms? Via timing leak + swapper anchor after
   kernel read (Phase 8). Does not require kallsyms or AMLSECU key.
9. Ashmem/configfs available? Compiled in: YES; runtime: CONFIRMED
   (/dev/ashmem rw for shell, configfs mounted rw). Dentry tolerance:
   NOT PROVEN.
10. Reclaim plausible? AF_UNIX cross-cache (via hazel) or pipe (via
    aresin); geometry to be measured. INFERRED/NOT PROVEN.
11. Reachability without risk? YES, probe ready, 7/7 on device.
    CONFIRMED ON AQUAMAN KERNEL.
12. Plausible path to temporary uid 0? YES, with listed adaptations;
    true probability known only after Phase 11 (lab) + trigger with reclaim.
13. What does root unlock? kallsyms, config, dt, modules, iomem —
    pstore NO (denied to shell; recheck as root). Baseline to
    reconstruct the 2022 kernel and evaluate KernelSU afterwards.

## General classification — updated 2026-09-29

CVE present + path reachable: CONFIRMED ON AQUAMAN KERNEL
(probe 7/7, race EDEADLK 5/5, ashmem+configfs runtime OK).
Compatible layouts: NOT PROVEN (offsets pending).
Primitive available: NOT PROVEN (reclaim not attempted).
Adaptation feasible: YES (plan above).
Verdict: 4.9.113 DOES NOT imply exploitable on its own, but here we have
CVE in source + rollback reachable 5/5 + runtime surfaces OK.
What remains before any risky testing: offsets (pahole/lab) and
slab geometry. Next physical step: offline lab, then trigger
with read-only reclaim.
