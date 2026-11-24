# Offline checks - R1

**PREPARATION ONLY - DO NOT EXECUTE ON DEVICE**

All items below were run locally, without touching the device.

## 1. Module

- [x] `sh work/r1-kexec/build.sh` exits with status 0.
- [x] `modinfo work/r1-kexec/modules/r1_kexec.ko` shows `vermagic: 4.9.y SMP preempt mod_unload modversions aarch64` (same as the `seflip` test module).
- [x] `modinfo ... | grep depends` -> empty.
- [x] `aarch64-linux-gnu-nm -u r1_kexec.ko`: every undefined symbol is in `build-aq/Module.symvers`. In particular `memstart_addr`, `__cpu_online_mask`, `nr_cpu_ids`, `_mcount`, `find_next_bit`, `strcmp` are present.
- [x] `nm` shows `T r1_dcache_clean_poc`, `T r1_icache_inval_all`, `T r1_install_idmap`, `T r1_relocate_new_kernel`.
- [x] The build reports no circular dependencies or duplicate symbols.

To repeat only the symbol check:

```
NM=.src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu-nm
$NM -u work/r1-kexec/modules/r1_kexec.ko
```

## 2. Image

- [x] `build-aq/arch/arm64/boot/Image` exists, 27308544 bytes.
- [ ] Confirm in the future, via root on the device, that the banner is `4.9.113-g963f962d046a-dirty` and matches dmesg. (Not done here: would require device interaction.)
- [ ] The module requires 2 MiB alignment for the Image; check in the `r1_kexec: image=0x...` log that the address ends in `00000`.

## 3. DTB

- [x] `dtc -f -I dtb -O dts -o /tmp/in.dts artifacts/aquaman.dtb` works.
- [x] `dtc -f -I dtb -O dtb -o /dev/null work/r1-kexec/aquaman-r1.dtb` works (round-trip).
- [x] `aquaman-r1.dtb` has magic `d00dfeed` and 58705 bytes.
- [x] `dtc -f -I dtb -O dts aquaman-r1.dtb | grep -A4 'chosen {'` shows `bootargs`.
- [x] The generated default cmdline does **not** contain `skip_initramfs`.
- [x] initrd variant: `CMDLINE='rootwait skip_initramfs quiet' INITRD_START=0x38d00000 INITRD_END=0x38f00000 OUT_DTB=/tmp/r1-initrd.dtb sh work/r1-kexec/patch_dtb.sh` removes `skip_initramfs` and emits `/bits/ 64 <0x0 0x...>` for start/end.
- [ ] When loading with initrd, the module rewrites start/end to the real physical values; check in the new kernel's dmesg (not executed).

Note: `dtc 1.8.1` reports `node_name_not_empty` for the node `/@c1108d80` already present in the stock DTB; `-f` is used explicitly. This is pre-existing, not introduced by the patch.

## 4. Addresses / CMA

- [x] CMA pools listed (from the earlier survey): `0x05000000` (36M), `0x2ac00000` (208M codec_mm), `0x38c00000` (76M), `0x37c00000` (16M), `0x3d800000` (32M), `0x3f800000` (8M), 8M at `0x2a400000`.
- [x] `cma_phys=0x38c00000` is 2M-aligned and the pool has 76 MiB, enough for Image (27.3 MB) + DTB + initrd + 2M of trampoline.
- [ ] Confirm on the device that the chosen pool is free (depends on codec_mm state). Not verified offline.
- [x] Stock `loadaddr` `0x1080000` is not used as the destination; the new kernel is placed in CMA and head.S computes the physical offset via `adrp x23, __PHYS_OFFSET`.

## 5. Secure boot gate

- [x] The R1 path does not call `bootm`/verification SMC; direct jump to the copied Image. No signature validation is involved.

## 6. Rollback

- [x] Stock copy at `/tmp/opencode/odm_probe/odm20_stock.img` referenced in README and stage.sh. It was neither modified nor used.
