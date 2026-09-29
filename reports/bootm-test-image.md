# bootm-test-image — offline proof that m1_boot.img / m1b_boot.img reach the entrypoint

reference source: /tmp/kernel-src/uboot-khadas (khadas/u-boot, branch
khadas-vims-nougat), same 2015.01 Amlogic vintage as the device
(`2015.01-g7ac5df7677-dirty`). board config closest to aquaman:
board/amlogic/configs/gxl_p241_v1.h (gxl, p241_1g DTB matches local build).

tool: `tools/inspect_test_image.py` replicates every gate below.
both payloads print VERDICT: would reach entrypoint; a raw 4 KiB file
prints INVALID (the trap the old test fell into).

## 0. addresses (why bootm needs an explicit X)

X = 0x10200000 download buffer, CONFIG_USB_FASTBOOT_BUF_ADDR
(include/g_dnl.h:18). cb_download memcpys there
(drivers/usb/gadget/f_fastboot.c:504), size gate vs ddr_size_usable
(f_fastboot.c:556).
Y = 0x1080000 stale addr, loadaddr env default
(board/amlogic/configs/gxl_p241_v1.h:90: "loadaddr=1080000").
do_bootm_on_complete sprintfs load_addr (f_fastboot.c:576) and calls
do_bootm (f_fastboot.c:577), so plain `fastboot boot` reads Y, not X.
our test never uses `fastboot boot`; it calls `bootm X` explicitly.

## 1. exact bootm sequence for `bootm 0x10200000`

1. do_bootm (common/cmd_bootm.c:96). argv[0] is a valid number, so no
   subcommand detour (:117-131). nLoadAddr defaults to GXB_IMG_LOAD_ADDR
   (:133) then is overridden by argv[0] → 0x10200000 (:135-140).
2. aml_sec_boot_check(AML_D_P_IMG_DECRYPT, 0x10200000, GXB_IMG_SIZE,
   GXB_IMG_DEC_ALL) (cmd_bootm.c:142). pure SMC wrapper
   (arch/arm/cpu/armv8/gxl/bl31_apis.c:255-308, x0=AML_DATA_PROCESS).
   GXB_IMG_SIZE = 24<<20, GXB_IMG_LOAD_ADDR = 0x1080000
   (arch/arm/include/asm/arch-gxl/bl31_apis.h:118-119).
   nonzero → "aml log : Sig Check" + return (:143-147). our 4 KiB file
   sits fully inside the 24 MiB window. plaintext passes iff the device
   is not secure-fused (expected: getvar unlocked=yes, secure=no;
   confirm on device before sending).
3. do_bootm_states(START|FINDOS|FINDOTHER|LOADOS|PREP|FAKE_GO|GO)
   (cmd_bootm.c:150-158).
   - START: bootm_start zeroes images, verify=getenv("verify")
     (common/bootm.c:68-80).
   - FINDOS: bootm_find_os → boot_get_kernel (bootm.c:82,795).
     img_addr = argv[0] = X (image.c:genimg_get_kernel_addr_fit).
     genimg_get_format (image.c:730-749) checks LEGACY (:736),
     FIT (:740), ANDROID (:744), else INVALID (:748).
     ANDROID branch (bootm.c:884-893): android_image_need_move
     (returns 0 for COMP_NONE, image-android.c:174) then
     android_image_get_kernel (image-android.c:37): os_data = hdr +
     page_size (:80-83), os_len = kernel_size (:85), bootargs extended
     (:60-78, RAM-only setenv, no save).
   - bootm_find_os ANDROID case (bootm.c:152-165): type=KERNEL,
     comp=android_image_get_comp, os=LINUX, end=android_image_get_end,
     load=kload=kernel_addr (quirk 0x10008000→0x1080000 at :160-161),
     ep=load (:162). NO arch check exists on this path (arch is only
     checked for LEGACY :774-778 and FIT image-fit.c:1598).
   - FINDOTHER (bootm.c:293-304 → 280-291): ramdisk absent
     (ramdisk_size=0 → rd_start=rd_end=0), fdt from control DTB:
     bootm_find_fdt wrapper preset dtb_mem_addr (bootm.c:231-244) +
     get_multi_dt_entry for MULTI_DTB (bootm.c:246-250).
     env dtb_mem_addr=0x1000000 (gxl_p241_v1.h env block),
     CONFIG_MULTI_DTB=1 (gxl_p241_v1.h:470). no DTB must be packed.
   - LOADOS: bootm_load_os (bootm.c:415-471). decomp_image COMP_NONE =
     memmove load<-image_start (bootm.c:326-335), flush_cache (:437).
     then the overlap gate (:442-468): no_overlap = (comp==NONE &&
     load==image_start). ours: load=0x1080000, image_start=0x10200800,
     blob=[0x10200000,0x10201000), load_end=0x1080070 → disjoint →
     check SKIPPED, return 0. (if the same bytes are booted from
     Y=0x1080000, overlap=True and ep+0x38 IS checked: magic present,
     passes.)
   - PREP/GO: do_bootm_linux → boot_prep_linux (fdt setup) →
     boot_jump_linux (arch/arm/lib/bootm.c:262-283):
     announce_and_cleanup (MMU/caches off), do_nonsec_virt_switch,
     kernel_entry(ft_addr, 0, 0, 0) at ep=0x1080000. no return.

## 2. field → validator → source line → expected result (m1/m1b)

| field | validator | source line | m1/m1b value → result |
|---|---|---|---|
| bytes 0..7 = ANDROID! | genimg_get_format ANDROID branch | image.c:744, image-android.c:100-103 memcmp | ANDROID! → IMAGE_FORMAT_ANDROID, pass |
| page_size | android_image_get_kernel offsets | image-android.c:80-92 | 2048 (stock value) → os_data=X+2048, pass |
| kernel_size | os_len != 0 | bootm.c:92-95 | 112 → pass |
| kernel payload 9 first bytes | android_image_get_comp | image-android.c:143-164 | branch opcode, not lzo/gzip → COMP_NONE, pass |
| kernel_addr | kload + quirk | bootm.c:159-162 | 0x1080000 → load=ep=0x1080000, pass |
| ramdisk_size=0 | boot_get_ramdisk skip | bootm.c:210-223 | rd 0/0, pass |
| fdt | bootm_find_fdt control DTB | bootm.c:231-277, gxl_p241_v1.h:470 | dtb_mem_addr path, pass |
| kernel+0x38 magic | bootm_load_os overlap branch | bootm.c:442-466 | 0x644d5241; X-path skips check (disjoint), Y-path checks and passes |
| text_offset/image_size | — (unused on ANDROID path) | — | 0/112, informational only |
| total footprint 4096 | GXB window | bl31_apis.h:118 | 4096 < 24 MiB, pass |
| file size 4096 | download gate | f_fastboot.c:556 | << ddr_size_usable, pass |

minimum viable size on this path: 2048 (one page header) + 60 (magic at
+0x38 needs 60 bytes) = 2108 bytes. ours is 4096 (page-padded 112 B
kernel). kernel_addr may also be 0x10008000 (quirk remaps it).

## 3. why legacy/FIT were not chosen

LEGACY uImage (64 B header + payload): needs IH_MAGIC 0x27051956,
correct hcrc ALWAYS (image.c:754), arch==22 ARM64
(IH_ARCH_DEFAULT, arch/arm/include/asm/u-boot.h:49), os==5, type
KERNEL-family, comp NONE; dcrc only if verify=yes. in-place
(load==X+64) would also skip the ARM64 check, and the file would be
~176 B. rejected anyway: checksums add failure modes, arch string must
match exactly, and no existing tooling/images prove the path on this
family — stock boots ANDROID, not legacy. smaller but riskier.
FIT: needs valid FDT container + config node + kernel subimage with
arch/os/type/load/entry (image-fit.c:1508-1698), then the SAME ep+0x38
check (bootm.c:462, overlap branch). strictly more gates, ~57 KiB for
m1b_fit.itb, zero benefit. rejected.
raw Image / raw stub: genimg_get_format → INVALID (image.c:748) →
boot_get_kernel NULL → "Wrong Image Format"/"ERROR: can't get kernel
image!" (bootm.c:896,92-94) → return 1 → reset. this is exactly why the
old 4 KiB raw test proved nothing.

verdict: ANDROID! v0 + ARM64 stub, COMP_NONE, kload 0x1080000. smallest
gate count (no CRC, no arch check, no packed DTB), deterministic copy to
a fixed ep, tooling already reproducible (tools/mk_m1_boot.py).

## 4. payload (tools/m1_delay_stub.S, 112 B)

position-independent, EL2-safe, zero memory access beyond its own code:
Linux ARM64 header (b entry + zeros + magic 0x644d5241 at +0x38, the
only field bootm ever reads) → nested delay loop
(outer × 1M inner: m1 outer 0x0FA0=4000 ≈ seconds-scale, m1b outer
0xEA60=60000 = 15×) → PSCI SYSTEM_RESET fid 0x84000009 via hvc #0
(same fid as prior stub) → wfi park. no eMMC, no userdata, no env
writes, no partitions, no UART, no Linux dependency.
rebuild: python3 tools/mk_m1_boot.py 0x0FA0 m1_boot.img (A),
python3 tools/mk_m1_boot.py 0xEA60 m1b_boot.img (B). both verified
byte-reproducible and inspector-clean (see §2 table, both rows pass).
