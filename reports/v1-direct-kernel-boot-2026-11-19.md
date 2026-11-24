# V1 direct kernel boot - 2026-11-19

Final status: **NO-GO**. uid=0 was NOT proven. No success criterion
passed. Nothing in this report supersedes `CURRENT_STATE.md` or any line of
`INVALIDATED_HYPOTHESES.md`; it is a new record, with an index to update later.

Evidence convention: PROVEN, HARDWARE_REPRODUCED, OFFLINE_ONLY, INCONCLUSIVE,
REFUTED. BOOT_ID is the value of `/proc/sys/kernel/random/boot_id` read in Android
during that session; when the gadget froze and there was no Android, there is no BOOT_ID.

---

## Phase A - offline (OFFLINE_ONLY, device not involved)

### A.1 What bootm does in the last minute

Chain disassembled from the real binary `reports/round14-bl33-persist/bl33-37e18000.bin`
(virtual base 0x37e18000, offset = VA - 0x37e18000):

```
bootm @0x37e24c00
  -> cbz @0x37e24cf8 (right after the decrypt wrapper at 0x37e19ea8)
  -> do_bootm_states @0x37e255c8 (w4=0x70f = START|FINDOS|FINDOTHER|LOADOS|PREP|FAKE_GO|GO)
     -> bootm_load_os @0x37e5b880 (decompresses gzip, populates [images+0x100]/[0x108])
     -> state OS_GO bit10 @0x37e25f50 -> @0x37e265c0 -> blr x4 (do_bootm_linux)
        -> boot_jump_linux ARM64 @0x37e21284
           -> announce_and_cleanup @0x37e192b4
           -> eret @0x37e19264
```

The `eret` at 0x37e192b0 is the real transfer, not a `br`:

```
0x37e19264  mov x20,x0        ; x0 = entry (images->ep)
0x37e19268  mov x21,x1        ; x1 = 0xf81 (magic Amlogic)
0x37e1926c  mov x22,x2        ; x2 = physical FDT
0x37e19270  mrs x0,sctlr_el2 ; clears bit 33
0x37e19280  mov x0,#0x878
0x37e19284  movk x0,#0xc5,lsl#16
0x37e19288  msr sctlr_el1,x0 ; SCTLR_EL1 = 0x00c50878 (M=0, C=0, I=0)
0x37e19290  msr hcr_el2,x0   ; HCR_EL2 = 0
0x37e19294  isb
0x37e19298  mov x0,#0x1d3
0x37e1929c  msr spsr_el2,x0 ; SPSR_EL2 = 0x1d3
0x37e192a0  msr elr_el2,x20 ; ELR_EL2 = entry
0x37e192a4  mov x0,#0
0x37e192a8  mov x1,x21      ; 0xf81
0x37e192ac  mov x2,x22      ; FDT
0x37e192b0  eret            ; EL2 -> EL1
```

At 0x37e21284 bootm loads `x0 = [images+0xe8]` (entry),
`x2 = [images+0x100]` (ft_addr), `x1 = 0xf81`, and only enters the `eret` when
`[images+0xe3] == 2` (ARM64). `arch_fixup_fdt`, board setup and `fdt_chosen`
operate on the same blob before the swap (per round57, not reopened).

### A.2 Kernel entry

(a) Entry: **0x1080000**. The Android header has `kernel_addr = 0x1080000`; the
plaintext kernel starts at 0x1080800 and is gzip. bootm_load_os decompresses to
0x1080000. There is no relocation of the kernel to another address. The decompressed
kernel has `text_offset = 0x1080000`, `image_size = 0x1ac9000`, magic `ARMd` at +0x38.

(b) State required at the jump: EL2 -> EL1 via `eret`, SCTLR_EL1 = 0x00c50878,
HCR_EL2 = 0, SPSR_EL2 = 0x1d3, ELR_EL2 = 0x1080000, x0 = 0, x1 = 0xf81,
x2 = FDT, x3 = 0. The ancestral kernel in
`.src/linux-amlogic/arch/arm64/kernel/head.S:242` reads the FDT from x0, but the
device build delivers it in x2 with x1 = 0xf81 (Amlogic convention). Both
registers were filled in the live tests to cover both.

(c) Layout used in Phase C: see table below (the initial Phase B layout was
corrected after discovering that the decompressed kernel has 0x1950a00 bytes).

| region | final address | size | reason |
| --- | --- | --- | --- |
| kernel Image | 0x1080000 | 0x1950a00 | entry, text_offset of the Image itself |
| ramdisk Magisk | 0x31000000 | 0x5c09c | above the kernel, outside the env arena |
| DTB with /chosen | 0x30000000 | 0xe705 | above the kernel, outside 0x33e18000 |
| scratch stub | 0x37800000 | 0x100 | hardware-proven |
| fake images | 0x37900000 | 0x200 | extra area |
| decrypt temp | 0x1080000 | 0x1000000 | wrapper site1 |

(d) Offsets of the plaintext boot.img (header read via MREAD, not deduced):

```
magic        ANDROID!            @0x00
kernel_size  0x00959000 (9801728) @0x08
kernel_addr  0x01080000           @0x0c
ramdisk_size 0                    @0x10  (stock; Magisk = 376988)
ramdisk_addr 0x01000000           @0x14
second_size  0xf000               @0x18
page_size    0x800                @0x24
kernel       @0x800   (AMLSECU! encrypted; decompress -> ARMd, 0x1950a00)
ramdisk      @0x959800 (Magisk CPIO 070701, 376988 B)
second/DTB   @0x9b6000 (0xf000 B, encrypted in stock)
```

kallsyms: not extracted. The image is plaintext only during the burning session;
the dump `kernel_plain.bin` (the gzip) and `kernel_image.bin` (the decompressed Image)
were saved, but the kallsyms table was not parsed. Outside the scope of the V1
success criterion and does not change the conclusion.

---

## Phase B - offline (OFFLINE_ONLY)

Artifacts in `/tmp/v1/artifacts/` (outside the repo, as requested):

| file | sha256 | size |
| --- | --- | --- |
| boot_final.img | db4e3ac560559371cb65c4a850c7ca67a5bb832176a7f26c45b4b0b2012861cd | 16777216 |
| final.dtb | 18d1e613360ab1ee474a6ff2a3b71dc56292306fdc2b70acae73c1fdedcd45ad | 59141 |
| kernel_plain.bin | 035aa74de5c48f72189597ed823bea574a06696ef71608ab6d7a695d8768a02f | 9801728 |
| kernel_image.bin | 3c3522d804cf586f4a873a23b5481588574c565f9cac896d3a880325d0e3dca8 | 26544640 |
| stub_decrypt.bin | fcfd6399817019f155bfac89a2563881a264952f15383b1d57cf8c7248da98cb | 32 |
| stub_jump_eret.bin | ff9505783136f38fce530318d70b126347c6ad1aedd6bafbe4dbb74124d753bf | 84 |
| stub_jump_br.bin | 8ee2b3817a95e930968ae26fe8910822a08c2f4570e7e6babbfb5908e43f91f8 | 20 |
| stub_oneshot.bin | 36cd44c01539feff92a235321966de679e6c27b1660e9797022bb7116dc10776 | 120 |
| stub_entrycall.bin | f611d44141d12d8bcc5a770063eb3b136858be5c3a07368761dac911bc69b605 | 92 |
| stub_br_final.bin | e8f99c1043178c27258e34e33e17d0c6fd2d5f3b32c184a1bab3585314941a84 | 24 |
| stub_dtbswap.bin | fb69240aef86dd04733fdb75df7e6b0e7497e3c7a386ba8fd8edf06e44f52f6e | 44 |

`kernel_plain.bin` is the gzip stream obtained by MREAD after the wrapper.
`kernel_image.bin` is the decompressed gzip (26,544,640 B, valid ARMd magic).
`boot_final.img` is the Magisk image with `second` replaced by the patched DTB;
the decrypt attempt on it failed (wrapper refused the modified container),
so the live path used `imgread` of the stock image from eMMC.

DTB patched with `fdtput` on `artifacts/aquaman.dtb`:
`/chosen/bootargs` (full string, with `init=/init`, `console=ttyS0,115200
no_console_suspend`, `earlycon=aml_uart,0xc81004c0`, `rootfstype=ramfs`,
`androidboot.selinux=permissive`), `/chosen/linux,initrd-start` and
`linux,initrd-end`. Verified with `fdtdump`: on both final values used
(0x2000000 and 0x31000000 for start). Did not touch mem/alias/ethaddr.

AArch64 encodings validated offline with capstone 5.0.7:

```
stub_decrypt (calls wrapper 0x37e19ea8, ret):
  000880d2  mov x0,#0x40
  0121a0d2  mov x1,#0x1080000
  0230a0d2  mov x2,#0x1800000
  e30080d2  mov x3,#7
  04d593d2  mov x4,#0x9ea8
  24fca6f2  movk x4,#0x37e1,lsl#16
  80003fd6  blr x4
  c0035fd6  ret

stub_br_final (direct jump, used in the two attempts that booted):
  0000a6d2  mov x0,#0x30000000   (DTB; in the 1st attempt 0x2a000000)
  21f081d2  mov x1,#0xf81        (magic; in the 1st attempt x1=0)
  e20300aa  mov x2,x0
  e3031faa  mov x3,xzr
  1421a0d2  mov x20,#0x1080000
  80021fd6  br x20

stub_dtbswap (copies DTB to 0x19d9800 and returns to bootm):
  000080d2 / 0000a6f2  x0 = 0x30000000
  00009bd2 / 2103a0f2  x1 = 0x19d9800
  0000f0d2            x2 = 0xf000
  038440f8  ldr x3,[x0],#8
  238400f8  str x3,[x1],#8
  422000f1  subs x2,x2,#8
  acffff54  b.gt
  <b relative to 0x37e24d10>
```

Fresh Phase 0 baselines in `/tmp/v1/baseline/` (4 dumps,
confirmed in all sessions: false handler `64 67 e3 37 00 00 00 00`,
site1 `6e d4 ff 97`, site2 `c6 d3 ff 97`, scratch zero).

---

## Phase C - live (HARDWARE_REPRODUCED / HARDWARE_OBSERVED)

Entry: `adb reboot fastboot` -> `fastboot oem update 5000` (expected FAILED) ->
`1b8e:c003`, stage 16. Phase 0 + GO passed in all sessions used
(`false -> failed:`, `true -> success`; `false -> success` with test stub).

### Attempt 1 - direct call to the wrapper by the stub (v1_decrypt.py)

`GO: True`. Download of boot_final.img (16 MiB) at 0x1080000, stub A
(0x37e19ea8 with site1 args), trigger `false`. Result: USBTimeout in 20 s;
device 1b8e:c003 still enumerated but with no response to control transfers.
Gadget froze. Cause: known trap of a direct SMC call by the stub.
Requires power cycle. BOOT_ID: none (no Android).

### Attempt 2 - one-shot with eret (v1_oneshot.py)

Download of ramdisk/DTB/boot.img, cbz 0x37e24cf8 -> `b 0x37800000`, stub copies
kernel + eret. `bootm 0x1080000` with no reply in 15 s, USB never dropped, gadget froze.
Later cause: the copied kernel was still gzip. BOOT_ID: none.

### Attempt 3 - obtain plaintext while keeping the gadget (v1_getplaintext.py)

First version of the return stub used `ret`, which went back to 0x37e24cf4 (x30
was clobbered by the `bl` to the wrapper) and looped. Fixed to
`mov w0,#0 ; b 0x37e25000` (the real epilogue of do_bootm). With boot_final.img the
wrapper did NOT decrypt (kernel stayed `AMLSECU!` at +0x800) and bootm
returned `success` in 0.02 s. With `imgread kernel boot 0x1080000` (v1_getplaintext2.py)
the wrapper worked: the kernel at +0x800 became `1f 8b 08 00` (gzip), sha of
the stream `035aa74d...`. MREAD of 9,801,728 B in 0.9 s. Gadget survived, final
oracle `failed:/success`. BOOT_ID: none (returned to U-Boot, not Android).

### Attempt 4 - bootm entry with fake images (v1_jump.py)

Decompressed kernel (26.5 MB) at 0x1080000, ramdisk at 0x2a100000, DTB at
0x2a000000, fake images at 0x37900000 (arch=2, ep=0x1080000, ft=0x2a000000),
stub F calls 0x37e21284 via `blr x6`. Trigger `false` with no reply in 15 s, USB
never dropped, gadget froze. BOOT_ID: none.

### Attempt 5 - direct br (v1_jump_br.py) - KERNEL STARTED

Same layout, stub `br x20`. Trigger `false`: USBError "No such device" in 1.6 s.
Timeline `/tmp/v1/usb_jump_br.log`:

```
t=  2.079  OFF  1b8e:c003
t= 53.581  ON   2717:4e40 android
```

Kernel started (USB dropped). Android came back. Criteria failed: `su: not found`,
no magiskd, `ro.boot.selinux=enforcing`, root on `/dev/root ext4`. BOOT_ID:
7bcb68bc-b84d-426c-adcd-4fa567b53791 (read after this sequence).

### Attempt 6 - br with x1=0xf81 and DTB moved away (revised v1_jump_br.py)

DTB at 0x30000000, ramdisk at 0x31000000, `x1=0xf81`. Timeline
`/tmp/v1/usb_jump_br2.log`:

```
t=  2.060  OFF  1b8e:c003
t= 51.645  ON   2717:4e40 android
```

Kernel started again, but bootargs stayed stock (`ro.boot.selinux=enforcing`,
`ro.boot.reboot_mode=watchdog_reboot`, `/dev/root ext4`). The DTB passed in x0/x2
was not consumed. BOOT_ID: 7bcb68bc-b84d-426c-adcd-4fa567b53791.

### Attempt 7 - full bootm + DTB swap (v1_final.py)

Ramdisk at 0x31000000, patched DTB at 0x30000000, stock `imgread`, cbz ->
stub_dtbswap (copies 0xf000 B from 0x30000000 to 0x19d9800 and returns to
0x37e24d10), `bootm 0x1080000`. USB dropped in 4.74 s (matches E4 control),
Android came back in 24.734 s. Timeline `/tmp/v1/usb_final.log`:

```
t=  5.223  OFF  1b8e:c003
t= 24.734  ON   2717:4e40 android
```

BOOT_ID: 622d8aa9-2542-46af-a39b-4e264e4d3057.

Exact output of the success-criterion commands (after attempt 7):

```
$ adb shell su -c id
/system/bin/sh: su: not found

$ adb shell getprop init.svc.magiskd
(none)

$ adb shell getprop ro.boot.selinux
enforcing

$ adb shell getprop ro.boot.reboot_mode
normal

$ adb shell ls -l /sbin/su
ls: /sbin/su: No such file or directory

$ adb shell ls -l /data/local/tmp/v1_ok
ls: /data/local/tmp/v1_ok: No such file or directory
```

`adb shell id` returns `uid=2000(shell)` (normal, not a criterion).

---

## Restoration

Everything written was RAM-only. Attempts 5, 6 and 7 ended in a kernel boot,
which reboots the SOC and discards all RAM: the `false` handler, site1, site2,
scratch, fake images and the three planted artifacts return to factory state
on reboot. There was no flash, erase, saveenv, persistent setenv, efuse, BootROM,
RUN_IN_ADDR, MODIFY or blind ioctl. No versioned file was altered other than
this report. The frozen gadget in attempts 1, 2 and 4 was recovered by
a power cycle of the device (6 cycles total), with no persistent consequence.

---

## Verdict

**NO-GO.** Exact point where it stopped: the stock decompressed kernel did in fact start
(USB OFF in ~2 s with `br`, ~5 s with `bootm`), but **no DTB passed by the stub
was consumed** - `ro.boot.selinux=enforcing` in all attempts, even with
`androidboot.selinux=permissive` in the `/chosen/bootargs` of the planted DTB, and root
on `/dev/root ext4`, without initramfs. Consequently the Magisk ramdisk was never
used and no uid=0 criterion passed.

Levels: Phase A and B OFFLINE_ONLY (disasm + header + hashes, PROVEN within
the static scope); Phase 0 and GO HARDWARE_REPRODUCED; decrypt via `imgread`+bootm and
the fact that the kernel starts HARDWARE_OBSERVED; uid=0 REFUTED in this strategy.

Next question to answer: **why does the kernel ignore the DTB at 0x30000000 /
0x2a000000 even with x0 and x2 pointing at it and x1=0xf81?** Hypotheses still
untested, in order of cost: (1) the kernel uses a fixed DTB address instead
of the registers in this Amlogic build; (2) bootm's `arch_fixup_fdt` /
`boot_relocate_fdt` rewrites `ft_addr` after the intercept, making the
swap at 0x19d9800 ineffective; (3) `[images+0x100]` must be updated after
`bootm_load_os`, not before. None was executed; do not reopen without static
evidence predicting the bootargs=permissive + initrd consumed pair.
