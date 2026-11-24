# R1 - custom kernel boot via kexec in an LKM (aquaman)

**PREPARATION ONLY - DO NOT EXECUTE ON DEVICE**

R1 route: loadable module (`r1_kexec.ko`) that copies `Image` + DTB (+ optional initrd) from the filesystem into contiguous physical memory via CMA, shuts down secondary CPUs via PSCI (`cpu_down`), installs a private identity map, disables MMU/D-cache and jumps to the new kernel with `x0` = physical address of the DTB, at the current EL. Skips U-Boot and the BL31 signature check.

**Status: PREPARED / NOT EXECUTED.** No `adb`, `nc`, `insmod`, `reboot`, `fastboot` command or write to the device was run. Build and validation were done offline only.

## Prerequisites

- Repo at `/home/erick/Documentos/projetos/aquaman_9_PI_2055`, with `.src/linux-amlogic/` and `build-aq/` already built.
- Linaro cross compiler in `.src/MiTV_OpenSource/cross_compile_tool/bin/`.
- `dtc`, `modinfo`, `make`, `awk`.
- Running kernel: vermagic `4.9.y SMP preempt mod_unload modversions aarch64`, `CONFIG_MODULES=y`, without `CONFIG_KEXEC`/`CONFIG_KPROBES`/`CONFIG_DEVMEM`. Root via listener 4444 already established (future use, not done here).
- Symbols used by the module confirmed in `build-aq/Module.symvers`: `dma_alloc_from_contiguous`, `dma_release_from_contiguous`, `aml_cma_alloc_range`, `aml_cma_free`, `cpu_down`, `kernel_read`, `filp_open`, `filp_close`, `memstart_addr` (used by `page_to_phys`), `_mcount`, `strcmp`.

## Offline build and validation

```
cd /home/erick/Documentos/projetos/aquaman_9_PI_2055
sh work/r1-kexec/build.sh
sh work/r1-kexec/patch_dtb.sh
sh work/r1-kexec/stage.sh          # only prints the commands; runs nothing
```

Detailed verification: `work/r1-kexec/checks.md`. Open decisions: `work/r1-kexec/OPEN_QUESTIONS.md`.

Current build output:
- `work/r1-kexec/modules/r1_kexec.ko` - vermagic matches, `depends` empty, no unresolved symbols.
- `work/r1-kexec/aquaman-r1.dtb` - 58705 bytes, dtc round-trip, `/chosen/bootargs` present, no `skip_initramfs`.

## Future load procedure (NOT EXECUTED)

See `stage.sh`. Summary:

1. Build and patch the DTB offline. For initrd, `patch_dtb.sh` must include `linux,initrd-start`/`initrd-end` with placeholder values; the module rewrites both properties with the real physical addresses computed at load time.
2. Copy `.ko`, `Image`, DTB and initrd to `/data/local/tmp/r1/` on the device.
3. `insmod ... image_path=... dtb_path=... [initrd_path=...] [cma_phys=...] fire=1`.
4. `fire=1` triggers the jump inside the module's `init`. There is no return; the `adb` session dies. Reconnect and check `/proc/cmdline`, `uname -a` and `dmesg`.
5. `fire=0` (default) only validates parameters and does nothing - there is no sysfs trigger because `proc_create` is not exported in this kernel.

Module parameters: `image_path`, `dtb_path`, `initrd_path` (optional), `cma_phys` (0 = default CMA; else 2M-aligned physical address), `fire`.

## Rollback (NOT EXECUTED)

If the new kernel does not boot, reflash the stock ODM from `/tmp/opencode/odm_probe/odm20_stock.img` (host copy) via the normal fastboot path, in a recovery/fastboot session, and boot stock Android. No flash/fastboot/dd commands are included in this directory.

## Known limitations

- The new Image must be 2 MiB aligned; the module aligns it inside the CMA allocation.
- A failure in `cpu_down` aborts before the jump and releases the CMA; a successful `fire=1` has no way back.
- The trampoline uses x19-x24 registers without saving: intentional, there is no return.
- The default CMA pool may not have 28 MiB free. See `OPEN_QUESTIONS.md`.
