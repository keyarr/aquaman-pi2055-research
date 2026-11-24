# Open questions - R1

**PREPARATION ONLY - DO NOT EXECUTE ON DEVICE**

Decisions that depend on hardware or operational choice. I followed the simplest option compatible with a first marker test.

## 1. Target CMA pool

- Options: (a) default CMA (`cma_phys=0`, via `dma_alloc_from_contiguous(NULL, ...)`); (b) explicit pool `0x38c00000` (76 MiB); (c) `0x05000000` (36 MiB).
- **Decision:** default is (a), `cma_phys=0`. The module aligns the Image to 2 MiB within the allocation. (b) is the alternative documented in `stage.sh` if the default CMA does not have 28 MiB free.
- **Recommendation:** try (a) first; if `dma_alloc_from_contiguous` fails, use (b).

## 2. DTB address in RAM

- Options: right after the Image in the same CMA allocation; or a separate fixed address.
- **Decision:** right after the Image, inside the same CMA allocation. The new kernel accesses the FDT via fixmap, so it does not need to be in the first 2 MiB of the Image.
- **Recommendation:** keep. Avoids a second allocation and ensures the DTB survives until the new kernel maps memory.

## 3. initrd vs no initrd

- Options: (a) no initrd, boot stock system via dm-verity; (b) with the Magisk ramdisk (`patched_unpack/ramdisk`, 376988 B, cpio).
- **Decision:** first test without initrd. The default-generated DTB has no `linux,initrd-*` and the cmdline has no `skip_initramfs`. The initrd variant is implemented: `patch_dtb.sh` accepts `INITRD_START`/`INITRD_END` and the module rewrites the properties with the real physical addresses.
- **Recommendation:** validate (a) before trying (b); for (b), remove `skip_initramfs` and check whether the Magisk init needs extra `overlay.d/sbin/magisk.xz`.

## 4. Shutting down secondary CPUs

- Options: (a) `cpu_down()` (exported; internally uses PSCI `CPU_OFF` via `cpu_ops`); (b) IPI + SMC PSCI CPU_OFF directly in the module.
- **Decision:** (a). It is synchronous, handled by the kernel and uses PSCI underneath. (b) would require discovering the SMC/HVC conduit from the DT and managing a count of shut-down CPUs.
- **Recommendation:** keep (a). If `cpu_down` fails on any CPU, the module aborts before the jump and releases the CMA.

## 5. Trampoline identity map

- Options: (a) reuse the kernel's `idmap_pg_dir`; (b) build own PGD/PMD in allocated pages.
- **Decision:** (b). The kernel's `idmap_pg_dir` covers only `__idmap_text_start..end`, which does not include the trampoline in CMA.
- **Recommendation:** keep (b). T0SZ = 25 (VA_BITS=39), 2 MiB PMD block with `MT_NORMAL` attributes.

## 6. Jump trigger

- Options: (a) `fire=1` on `insmod`; (b) trigger via sysfs/procfs.
- **Decision:** (a). `proc_create` is not exported in this kernel and a `module_param` with callback would add complexity with no gain for the first test.
- **Recommendation:** keep (a) for the marker. If it becomes a repeatedly used tool, implement (b) via `misc_register`.

## 7. Items requiring the device (outside this preparation)

- Confirm the chosen CMA has free space at load time.
- Confirm the new kernel boots with the injected DTB (`/proc/cmdline`, `uname -a`).
- Validate the path with initrd and the Magisk init, if applicable.
- Confirm that rollback via stock ODM restores the root service.
