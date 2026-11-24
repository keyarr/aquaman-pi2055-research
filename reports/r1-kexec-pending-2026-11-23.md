# R1 - custom kernel boot via kexec in an LKM (2026-11-23)

Status: **PENDING**. No custom kernel boot. Nothing was reflashed,
formatted, or written to any partition. The device ends up intact: stock 4.9.113,
root via ODM, SELinux Permissive via module.

> Device state at the time of this round: the 2026-11-23 ODM root plus
> `seflip`. Current state: `reports/kernelsu-persist-2026-11-24.md`.

Goal: load a custom Image without going through the BL31 signature gate.
With root and `CONFIG_MODULE_SIG` disabled, a module gives arbitrary execution in
kernel mode; the route tries to use this to jump directly to another kernel,
skipping U-Boot/`bootm`/SMC.

## Current state

- LKM trampoline: complete and functional. Breadcrumb reaches step 14 (branch).
- The new kernel's `stext` executes (marker 0x5251).
- `head.S` advances until TTBR0/TTBR1 are loaded (marker 0x5260 = 21088).
- Exact hang: `msr sctlr_el1, x0` in `__enable_mmu`, when enabling the MMU.
  It never reaches marker 0x5261, `start_kernel`, or the
  `r1probe=DEADBEEF` marker in `/proc/cmdline`.
- Watchdog reset after ~50 s, no panic and no new pstore record.
- `console-ramoops` shows a CPU hardlockup, even with `skip_offline=1`;
  it is a side effect of the trampoline state, not the confirmed cause.

## Ruled out

| Hypothesis | Result |
| ---------- | ------ |
| Lack of free CMA | Valid for the default pool and for `0x38c00000` (fragmented). `0x3d800000` (32 MiB) works. |
| Entry at `image_phys + text_offset` | Wrong. `text_offset` is a load offset in RAM; `_text` is at the image base. |
| KASLR alignment | Fixed: the image base needs the same 2 MiB sub-allocation as `text_offset` (`+0x80000`). The offset read in `head.S` is 0. |
| Injected DTB | Ruled out. The original DTB without `/chosen` also hangs when re-entering the same kernel. |
| Incompatible local Image | Ruled out. `artifacts/kernel_image.bin` (decrypted stock) hangs at the same point. |
| Secondaries via `cpu_down` | `skip_offline=1` does not change the stopping point. |
| `text_offset`/addresses | Checked live: physical `_text` `0x3d880000`, virtual target `0x09080000` (low bits), KASLR offset 0. |

## Fixes already applied to the module

- Copy via `page_address(pages)` instead of a physical address used as a virtual pointer.
- Entry at the image base.
- Base alignment with `text_offset & (2M-1)`.
- Breadcrumb at `0x07501000`, 4 KiB inside a ramoops record (the start of the
  record is rewritten with `PERSISTENT_RAM_SIG` on every boot).
- `dc civac` after each breadcrumb via VA; physical write after MMU off.
- Breadcrumb VA passed from C (`phys_to_virt`), no PAGE_OFFSET constant
 in assembly.

## Next technical step

Install minimal exception vectors in the trampoline's idmap to capture
`ESR_EL2`/`FAR_EL2` at the instant of `msr sctlr_el1`. This classifies the fault
(translation, permission, fetch) and may close the route in a few iterations.
With no serial/UART on the device, this is the only observable output besides the breadcrumb.

Alternatives if it does not converge:

1. R2: keep the stock kernel and apply custom behavior via a persistent module
   (already works; covers root, hooks and dm-verity).
2. Custom ROM by flashing `system`/`vendor` via fastboot + module, without
   replacing the Image.
3. Repeat the BL33 chain with the entry and alignment fixes discovered
   here; the SMC gate still stands.

## Artifacts

- `work/r1-kexec/`: `README.md`, `checks.md`, `OPEN_QUESTIONS.md`, `build.sh`,
  `patch_dtb.sh`, `stage.sh`, `modules/r1_main.c`, `modules/r1_asm.S`,
  `modules/Kbuild`, `modules/r1_kexec.ko`, `aquaman-r1.dtb`,
  `aquaman-r1-full.dtb`.
- The module has diagnostic parameters (`fire`, `read_crumb` as a physical
  address, `panic_at`, `reenter_self`, `skip_offline`) that must be removed
  before normal use.
- `artifacts/kernel_image.bin`: decrypted stock Image, used in the
  comparisons.

## Cleanup pending

The local tree is instrumented with diagnostic markers. `.src/` is
gitignored, but the builds reflect the edits:

- `.src/linux-amlogic/arch/arm64/kernel/head.S`: macros `R1_MARKP`/`R1_MARKV`,
  markers in `stext`, `__create_page_tables`, `__enable_mmu` and writes of
  `x23`/`x3`/`x5` to `0x07502000`/`0x07503000`/`0x07504000`.
- `.src/linux-amlogic/init/main.c`: `r1_mark`, markers in `start_kernel` and
  `do_basic_setup`, `panic` in `late_initcall`.

Revert these edits before any final build.
