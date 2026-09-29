# GhostLock KASLR + symbols + stock kernel (Phase 8 + Phase 9)

## Stock kernel as an artifact — result

- boot.img -> boot_unpack/kernel 9.3M starts with AMLSECU! magic
  (version 0x905, 3 blocks, build timestamp 2022090612544443).
- Entropy ~8.0 bits/byte after header: ciphertext, no plaintext.
- m1b_kernel.bin in workspace is 112B (stub, not full kernel).
- Conclusion: NO offline-analyzable vmlinux/Image available today. The
  "extract and run pahole/Ghidra" approach is BLOCKED without the AMLSECU key,
  which is outside our scope (secure world).

## What this closes and what remains

Closes: (B) static artifacts — no text base, no kallsyms, no
relocations, no DWARF, no IKCONFIG from the actual binary.
Remains:
  A) Direct: /proc/version, /proc/cmdline, getprop, uname (basic).
  C) Side-channel: leak via futex hash timing (hazel ks_*) or KASLR
     slide via relative reads — functions WITHOUT kallsyms, but requires
     the reclaim primitive working first (chicken-and-egg resolved
     by hazel: mm leak comes before kernel R/W and uses only futex
     timing + child's /proc/pid/mem, all userspace).
  D) Post-R/W: with kernel read, anchor init_task via "swapper" comm +
     task list, then derive remaining offsets. Similar to hazel
     (validate_runtime_profile + find_current_task).

## Blocked kallsyms: not an insurmountable obstacle

All three ports assume kallsyms is closed to unprivileged shell:
- hazel: profiles with absolute addresses + runtime read validation
  ("swapper" comm + next/prev from task list). KASLR? On ARM32 4.9 FireOS
  no effective lowmem KASLR — addresses remain stable per firmware.
- aresin: slide_leak_kernel_base + resolve_missing_offsets via kallsyms
  WHEN available (root/Magisk), otherwise static fallback. On aquaman
  without prior root, static fallback does not yet exist: must construct
  the first profile via a compatible compiled kernel (dangal + approximate
  config) or via leak (C) prior to any write.
- dnlid: uses offline evidence VAs for documentation purposes only,
  not for exploitation.

For aquaman ARM64 VA39 (CONFIG_ARM64_VA_BITS=39, PAGE_OFFSET
0xffffff8000000000): if KASLR is active, kernel text floats within a known window;
the leak must resolve the slide before fake fops point to
real functions. Practical order: (1) UAF + reclaim with payload that DOES NOT
require symbols (fake lock/waiter pointing to a controlled page known
via mm leak, as hazel does with slab page_base);
(2) Kernel read of the page -> anchor swapper -> resolve init_task;
(3) From there derive fops/configfs/ashmem by reading pointers
    (e.g., file->f_op from a real ashmem fd via task read? requires
    file table walk — high effort but feasible) OR via a locally compiled
    compatible kernel image.

## Recommended path for initial aquaman profile

1. Compile dangal-p-oss (local MiTV_OpenSource) with approximate aquaman-config,
   extract vmlinux, run pahole across all Phase 3 structs, record function
   addresses as REFERENCE (not as absolute target).
2. On device: reachability (Phase 10) -> EDEADLK race stats (dnlid
   --race) -> mm leak (hazel ks_*) calibrated for real ARM64 slab.
3. With kernel read: anchor swapper, construct runtime-validated profile.
4. Only then craft fake fops + cred patch.

None of this requires open kallsyms or breaking AMLSECU.
