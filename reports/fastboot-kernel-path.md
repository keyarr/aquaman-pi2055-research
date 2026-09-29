# fastboot-kernel-path — how `fastboot boot` really works on aquaman

sources: Amlogic U-Boot 2015.01 tree (same vintage as the device's
`2015.01-g7ac5df7677-dirty`), concrete reference `khadas/u-boot` master
branch (living Amlogic fork). no command was executed on the device for
this report; everything below is public-source reading + local dumps.
the firmware's bootloader.img is encrypted (entropy 7.9999, zero strings),
so there is no ground truth from the binary — family ground truth only.

## full chain

```text
host: fastboot boot <file>
  ↓ USB, "download:<hex>" command
drivers/usb/gadget/f_fastboot.c :: cb_download
  → writes to CONFIG_USB_FASTBOOT_BUF_ADDR, size limit =
    ddr_size_usable() (reported by `getvar max-download-size`)
  ↓ host sends "boot" command
drivers/usb/gadget/f_fastboot.c :: cb_boot
  → answers OKAY and schedules do_bootm_on_complete
do_bootm_on_complete:
  sprintf(addr, "0x%lx", load_addr);          // NOTE: uses `load_addr`, see §2
  do_bootm("bootm", addr)
  if do_bootm returns (any failure): do_reset()   // back to Android
  ↓
common/cmd_bootm.c :: do_bootm (Amlogic variant)
  1. aml_sec_boot_check(AML_D_P_IMG_DECRYPT, nLoadAddr, GXB_IMG_SIZE, GXB_IMG_DEC_ALL)
     if != 0: printf "aml log : Sig Check %d" and RETURN (→ do_reset in caller)
  2. ee_gate_off()
  3. do_bootm_states(START|FINDOS|FINDOTHER|LOADOS|PREP|FAKE_GO|GO)
```

## 1. AMLSECU is not required here — by construction

`aml_sec_boot_check` with `secure=no` accepts a payload without `AMLSECU!`
(the parser returns 0 = plaintext when the device is not secure; error only
when `isSecure` and the magic is missing — see `reports/amlsecu-reverse.md`
§1-2). that matches the stub test: U-Boot did not veto the download.
previous conclusion stands: AMLSECU does not block `fastboot boot` on this device.

## 2. WHERE the payload goes — real caveat

`cb_download` writes to `CONFIG_USB_FASTBOOT_BUF_ADDR` (build-time constant),
but `do_bootm_on_complete` boots from the global `load_addr`
(`loadaddr` variable, default `CONFIG_SYS_LOAD_ADDR`):

```c
sprintf(boot_addr_start, "0x%lx", load_addr);
```

upstream this was a known bug (Peter Chubb's patch, Sept 2016, swapping
`load_addr` for `CONFIG_FASTBOOT_BUF_ADDR`); the Amlogic fork still has the
old code. if on this build `loadaddr != USB_FASTBOOT_BUF_ADDR`, `bootm` reads
stale memory, not the download. UNKNOWN on aquaman.
clean check (read-only, no reboot): `fastboot oem printenv loadaddr`
(oem is a passthrough to run_command in this U-Boot) or the empirical M1 test.
until that's resolved, every kernel test carries this uncertainty.

## 3. what `bootm` accepts — and what it does with raw input

`boot_get_kernel` (common/bootm.c) → `genimg_get_format` (common/image.c):

| magic in buffer | format | destination |
|---|---|---|
| `0x27051956` | LEGACY uImage | legacy boot |
| `0xd00dfeed` | FIT/FDT | FIT boot |
| `ANDROID!` | ANDROID | `android_image_get_kernel` |
| anything else | INVALID | `Wrong Image Format` → NULL → `ERROR: can't get kernel image!` → return 1 |

a 20-byte raw payload with no magic falls into the last case. `do_bootm`
returns 1, `do_bootm_on_complete` calls `do_reset`. device goes back to
Android. **reboot after a raw stub is the expected REJECTION behavior,
not proof of execution.**

same for a stub wrapped in `ANDROID!` (the local `plain_boot.img` case):
the ANDROID path extracts the kernel (20 bytes) to `kload`, but `bootm_load_os`
(`CONFIG_ANDROID_BOOT_IMAGE` branch) requires a valid ARM64 Image:

```c
if (*(uint32_t *)(images->ep + 0x38) != 0x644d5241) {
    printf("Bad Linux ARM64 Image magic!(Maybe unsupported zip mode.)\n");
    return 1;
}
```

stub with no magic → fails → reset. again: back to Android having executed nothing.

## 4. what gets through the funnel (requirements for M1/M2)

1. `ANDROID!` image (v0 is enough; stock-like v1 works too),
   `kernel_addr = 0x1080000` (same as stock; this fork's quirk remaps
   `0x10008000 → 0x1080000`, so both values work),
   `page_size = 2048`, `ramdisk_size = 0`, `second_size = 0`;
2. kernel payload = **valid Linux ARM64 `Image`**: magic `0x644d5241`
   at offset `0x38`, `text_offset` and `image_size` filled in;
3. `bootm_load_os` copies the payload to `kload` with `IH_COMP_NONE`
   (memmove; if download==kload it's effectively a no-op);
4. ramdisk: absent → `rd_start = rd_end = 0`, continues with no initrd;
5. DTB: `boot_get_fdt` with no 3rd argument uses `dtb_mem_addr`/the
   U-Boot's own control DTB (`gd->fdt_blob`, with `get_multi_dt_entry`
   under `CONFIG_MULTI_DTB`); i.e. the kernel is gifted the DTB U-Boot
   already has — **no need to pack a DTB for M1/M2**;
6. `bootargs`: from U-Boot's `bootargs` env;
7. GO: `do_bootm_linux` ARM64 → entrypoint with `x0` = physical address
   of the FDT, `x1..x3` = 0, at EL2 (that's where U-Boot runs; HVC reaches
   BL31/EL3), MMU/caches off at handoff, 1 CPU at the entry point
   (4.9's Documentation/arm64/booting.txt).

formats that do NOT work via `fastboot boot` (bootm, not booti):
raw `Image` without `ANDROID!`, `Image`+DTB concatenated, DTB on a separate
partition, 32-bit uImage, zImage (`bootz` is not reachable from this path).

## 5. maximum size

`download_size > ddr_size_usable(...)` → `FAILdata too large`.
with 1 GB of DRAM the ceiling is in the hundreds of MB
(`getvar max-download-size` gives the exact number; read-only).
our 26 MB `Image` fits with room to spare.

## 6. how to PROVE execution (no UART)

since rejection and execute-with-reset converge on the same reboot, M1 needs
a timing signature or an absence signature:

- M1a (recommended): stub = valid Image + **~8 s delay** + PSCI SYSTEM_RESET.
  host times `fastboot boot` → USB re-enumeration. reject resets in ~1-2 s;
  the delay shifts the reboot by +8 s. the difference = proof of execution.
- M1b (alternative, needs a physical power cycle): stub with no reset
  (eternal wfi). reject goes back to Android; execution hangs until unplug.
  unambiguous, but physically annoying.
- M3 (later): use `ramoops`/pstore or bootreason for a persistent signature;
  only after M1/M2.

## phase 1 answers (best working fastboot boot format)

`ANDROID!` + valid ARM64 `Image` kernel with magic, `kernel_addr 0x1080000`,
no ramdisk/second. simplest and least ambiguous: minimal v0 header + delay stub.
single open item: confirm `loadaddr` vs download addr (§2).
