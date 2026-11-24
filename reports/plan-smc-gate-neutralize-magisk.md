# Operational plan: neutralize the SMC gate and boot the Magisk image

Date: 2026-11-19. Parts executed live on 2026-11-19; see "Execution status"
below. Parts not executed remain marked as such. The primitives used
(WRITE 0x01, FILL 0x03, cmd_tbl handler redirect, bulkcmd 0x34, MREAD 0x02) are
HARDWARE_REPRODUCED in earlier rounds.

## Execution status (2026-11-19, live session)

- Phase 0: PASS. Oracle `false -> failed:` / `true -> success`; `false` handler at
  `0x37f616d0` = `64 67 e3 37 00 00 00 00`; site1 `0x37e24cf0` = `6e d4 ff 97`;
  site2 `0x37e24f90` = `c6 d3 ff 97`; scratch `0x37800000` zeroed. Baselines in
  `/tmp/smc_gate_baseline/`. No writes in this phase.
- In-band output to `18d1:0d02`: REFUTED. `fastboot` handler `0x37e3a840`
  confirmed live, `bulkcmd "fastboot"` returned `success`, but the gadget
  remained `1b8e:c003` for 20 s. No return to fastboot without reset; Phase 3 as
  a write is not reachable in this session.
- Phase 1: GO. Stub `00 00 80 52 c0 03 5f d6` (`mov w0,#0 ; ret`) at
  `0x37800000`, `false` handler pointed to `0x37800000`, `dcache flush`,
  `false -> success` (previously `failed:`). Clean restore: original handler,
  `false -> failed:`, zero scratch, final oracle sound. E3 answered: host bytes
  execute via `ldr x4,[x19,#0x10] ; blr x4`.
- Item 1 (SMC diagnostics via stub, without eret): site 1
  (`x0=0x40, x1=0x1080000, x2=0x1800000, x3=7`) returned `x0=0` and left the
  kernel in plaintext at `0x1080000` (`ANDROID!`, size `0x959000` = 9801728 B,
  identical to the kernel of the Magisk image). Site 2
  (`x0=0x100, x1=0x1080000, x2=0x500, x3=7`) over the encrypted container
  returned `x0=0`. Clean restore in both. Attempt to repeat site 2 over the
  plaintext (without `imgread`) froze the gadget on the second call to site 1:
  USB dropped, device left the bus, and the session was lost. Consequence:
  `x0=0` makes `low16 != 0x100`, so the `csel` at `0x37e24fa0` selects `xzr` and
  `x2=0`. Attempt A (`mov w0,#0x100`) also produces `x2=0` because
  `high16(0x100)=0`; only B changes the result.
- Phase 2 (Attempt B of site 2): PATCH APPLIED in this session, without boot.
  `imm16 = 5` (ramdisk 376988 >> 16, only material change to the image).
  `0x37e24f90..a0`: `00 20 80 52 a0 00 a0 72 3f 00 01 eb` =
  `movz w0,#0x100 ; movk w0,#5,lsl#16 ; cmp x1,x1`. The `cmp x1,x1` replaces
  the `and x1,x0,#0xffff` and forces `eq`, so that the original `ubfx`/`csel`
  (`0x37e24f9c/a0`, intact) produce `x2=5`. Without it, the original
  `cmp x1,#0x100` would use `x1=0x1080000` and the `csel` would select `xzr`.
  Baseline `c6 d3 ff 97 01 3c 40 92 3f 00 04 f1` saved in
  `/tmp/smc_gate_baseline/smc_site2_37e24f80.bin`. Readback and oracle
  OK. Site 1 remains original. Without boot: the download tool (item 2) is
  missing to load the image at `0x1080000`. Reset/restore in the next session.

### Item 2 and boot attempts (continuation of the session)

- Download tool v2 (`/tmp/download_mem.py`): `AM_REQ_DOWNLOAD 0x32`
  (control OUT 0x40 with 0x20 B `CmdData_WriteMedia`, `chkAlg=0x00EE`,
  `wIndex=65535`), armed by `bulkcmd "download mem 0x1080000 normal 0x1000000"`,
  64 KiB chunks via bulk OUT `0x02`, reply `"OK!!"` on `0x81`. Loaded the 16 MiB
  of the image in 0.8 s; sha256 read back via MREAD matched the file. Structure
  read from `.src/u-boot-khadas/drivers/usb/gadget/v2_burning/`.
- **Attempt A of site 1 REFUTED**: replacing the `bl` with `mov w0,#0` makes
  `bootm` return `failed:` in 2.1 s. Reason: the wrapper is the same code that
  decrypts; without it the container remains `AMLSECU!` at `0x1080800`.
- **Site 2 must NOT be patched**. Only Attempt B (`0x37e24f90`) already makes
  `bootm` return `failed:` in 2.4 s; `mov w0,#0x100` (A) produces `x2=0` because
  `high16(0x100)=0`. Original site2 + `imgread` + `bootm` is the working E4
  control (USB drops at 4.75 s).
- Approach adopted: keep the `bl` (decrypts) and intercept the `cbz` at
  `0x37e24cf8` (`c0 00 00 34`) with `b 0x37800000` (`c2 6c e7 17`). Stub at
  `0x37800000` copies, before returning to `0x37e24d10`: Magisk header
  (`0x800`: `0x38000000 -> 0x1080000`), DTB (`0xF000`: `0x19d9800 ->
  0x1a358a0`) and ramdisk (`0x5c0a0`: `0x38959800 -> 0x19d9800`). Positions
  checked against `common/image-android.c` (`rd_start = hdr+page+ALIGN(kernel)`,
  `ft_addr = rd_start+ALIGN(ramdisk)`). Magisk is placed at `0x38000000` via
  download. The DTB needs to be relocated: the ramdisk overwrites `0x19d9800`.
- Error already fixed: the first version of the stub added the offsets by hex
  concatenation (`0x108959800`/`0x380959800` instead of `0x19d9800`/
  `0x38959800`) and caused a reset. Stub later validated with a variant ending
 in `ret`: MREAD confirmed header and ramdisk byte-identical to the Magisk file
  and DTB copied.
- **Boot result with the stub**: USB drops at 4.76 s (same as the E4 control) and
  Android comes back in ~19 s with `sys.boot.reason=reboot,fastboot`, but without
  `su`, without `init.svc.magiskd`, without `/sbin/su`. Kernel boots; Magisk
  ramdisk is not consumed. Live `bootargs` at `0x33e1d73f` has `init=/init` and
  `rootfstype=ramfs`, without `skip_initramfs` and without `root=`.
- Other refuted variants: `bootm 0x1080000 0x1000000` and an extra copy of the
  ramdisk at `0x1000000` -> `failed:` in 2.7 s.
- Reliability: direct SMC call via the stub worked once (item 1) and froze the
  gadget on all subsequent attempts, requiring a power cycle. The workaround
  was to let `bootm` itself call the SMC on the stock image.
- **Current blocker**: the `bootm` of this build is the custom Amlogic path, not
  the standard `image-android.c`. It does not register `rd_start`/
  `linux,initrd-start` in the FDT for the modified image, so the kernel ignores
  the ramdisk. Root not reached. Next step would require instrumenting
  `rd_start`/FDT inside bootm or abandoning the Magisk route.

## Goal

Make `bootm` accept `magisk_patched-30700_X0fyo.img` without going through
`aml_sec_boot_check`, nullifying the SMC call sites inside `bootm`, and reach
`uid=0` via the Magisk ramdisk. RAM-only, one session, power cycle restores.

## Why this path is short

The Magisk image already exists and was rejected only by the gate: byte-identical
kernel, real ramdisk, only material change is `ramdisk_size 0 -> 376988` in the
external Android header (`magisk-boot-test-2026-10-01.md`). The gate is the
`bl 0x37e19ea8` inside `bootm`, not the image format.

The real blocker to getting there is the E3 question: do bytes written by the
host ever get fetched as an instruction? The dump of `SCTLR_EL1 = 0x300004516`
gives M=0, I=0, C=1. If that is the state of the burning session, there is no
execute-permission check and no stale I-cache: a dcache clean is enough. The
`dcache flush` command (idx 11, handler 0x37e27ba4, maxargs=2) exists and has
never been run.

## Addresses (all derived from `04-cmdtbl-slots.txt` and the trace `bootm_37e24c00.txt`)

```text
cmd_tbl base                 0x37f60eb0, stride 0x30
false (idx 43) entry         0x37f616c0
false handler field (+0x10)  0x37f616d0   original value 0x37e36764
test  (idx 100) handler      0x37f62180   original value 0x37e36774 (already used in round46)
dcache (idx 11) handler      0x37e27ba4

SMC call site 1              0x37e24cf0   bl 0x37e19ea8
    args: x0=0x40, x1=0x1080000, x2=0x1800000, x3=7
    pos:  mov x20,x0 ; cbz w0 -> 0x37e24d10 ; else error + ret -1
SMC call site 2              0x37e24f90   bl 0x37e19ea8
    args: x0=0x100, x1=0x1080000, x2=0x500, x3=7
    pos:  and x1,x0,#0xffff ; cmp x1,#0x100 ; ubfx x2,x0,#0x10,#0x10 ;
          csel x2,x2,xzr,eq  (0x37e24f94..0x37e24fa4)

scratch for stub             0x37800000   (already written with readback in previous rounds)
```

Required AArch64 encodings:

```text
mov w0,#0        0x52800000   bytes 00 00 80 52
ret              0xd65f03c0   bytes c0 03 5f d6
stub 8B          00 00 80 52 c0 03 5f d6
mov w0,#0x100    0x52802000   bytes 00 20 80 52
```

## Session preconditions

Same entry as round46: `adb reboot fastboot`, `fastboot oem update 5000` (the
`FAILED (Status read failed)` is expected), `1b8e:c003`, identify stage 16.
Re-hunt dynamic addresses at the start of every boot. cmd_tbl is stable across
boots, htab is not. Use bulkcmd 0x34 as oracle: `false -> failed:`,
`true -> success`. `fastboot oem <cmd>` only returns AMLOGIC+OKAY for everything,
it is not useful as an oracle. `mmc info` is flaky, do not use.

Do not use: flash, erase, saveenv, persistent setenv, efuse, BootROM,
`RUN_IN_ADDR 0x05`, `MODIFY 0x04`, blind ioctls.

## Phase 0 - read-only validation (zero writes)

1. `MREAD 0x37f616c0 0x10` and check handler `64 67 e3 37 00 00 00 00`.
2. `MREAD 0x37e24ce0 0x30` and check `mov x0,#0x40 ... bl 0x37e19ea8` at
   `0x37e24cf0`.
3. `MREAD 0x37e24f80 0x20` and check `bl 0x37e19ea8` at `0x37e24f90`.
4. `MREAD 0x37800000 0x40` and check that the region is free/reset.
5. Save the four dumps as the session baseline.

If any address does not match the trace, stop. Do not improvise offsets.

## Phase 1 - GO/NO-GO: execute host bytes inside BL33

This is the only question that needs an answer before touching the SMC.

```text
SAVE    FILL 8B @ 0x37f616d0  -> 64 67 e3 37 00 00 00 00 (false handler)
SAVE    MREAD 0x37800000 0x10

STAGE   FILL 8B @ 0x37800000  -> 00 00 80 52 c0 03 5f d6   (mov w0,#0 ; ret)
VERIFY  MREAD 0x37800000 0x10
PATCH   FILL 8B @ 0x37f616d0  -> 00 00 80 37 00 00 00 00   (points to the stub)
VERIFY  MREAD 0x37f616d0 0x10
FLUSH   bulkcmd "dcache flush"   (check reply)
TRIGGER bulkcmd "false"
```

Criterion:
- `success` in place of `failed:` -> GO. Host bytes executed via
  `ldr x4,[x19,#0x10] ; blr x4`. Proceed to Phase 2.
- still `failed:` -> NO-GO. Stop. There is no code execution in this form; the
  SMC patch chain is not reachable. Do not try `RUN/MODIFY`.

Always restore, even on GO:

```text
RESTORE FILL 8B @ 0x37f616d0  -> 64 67 e3 37 00 00 00 00
RE-TRIG bulkcmd "false"       -> failed:
RESTORE FILL 8B @ 0x37800000  -> baseline from Phase 0
```

The stub only proves capability. It does not need to stay in memory for Phase 2:
the SMC patches are data, not code.

## Phase 2 - patch SMC call sites

### Site 1 (0x37e24cf0) - the signature gate

Replace the 4 bytes of the `bl` with `mov w0,#0`:

```text
SAVE    MREAD 0x37e24cf0 0x08
WRITE   4B @ 0x37e24cf0 <- 00 00 80 52
VERIFY  MREAD 0x37e24cf0 0x08   (next instruction intact)
```

Expected effect: x0=0, `mov x20,x0`, `cbz w0` takes the success path at
`0x37e24d10`. The `bl` to the wrapper does not happen, so there is no SMC and no
decrypt. The content at Y remains what fastboot downloaded.

Do not patch the entire `0x37e19ea8` wrapper: it serves 15 sites, including
`store dtb decrypt`. Killing all sites would prevent DTB decryption and the boot
would die later.

### Site 2 (0x37e24f90) - header query, NOT a gate

This SMC is a query. The return value is packed: low 16 bits compared with 0x100,
high 16 bits become `x2` via `ubfx`/`csel`. Zeroing x0 here produces `x2=0` and
can break bootm in `do_bootm_states`. Proceed by trial:

```text
SAVE    MREAD 0x37e24f90 0x08
ATTEMPT A: WRITE 4B @ 0x37e24f90 <- 00 20 80 52   (mov w0,#0x100)
VERIFY  MREAD 0x37e24f90 0x08
Test boot (Phase 3). If it fails, restore and try B.
ATTEMPT B: synthesize the packed value with the real image size:
    movz w0,#0x0100       -> 00 20 80 52
    movk w0,#<size_hi>,lsl#16 -> 00 00 a0 72 with imm16 = size>>16
    (covers 8 bytes: 0x37e24f90 and 0x37e24f94; realign the later logic)
RESTORE original MREAD at the end
```

Before attempt B, a useful diagnostic: with Phase 1 proven, the stub can be
swapped for one that calls `0x37e19ea8` with the site 2 args and returns x0 in a
scratch readable by `MREAD`. This resolves the packed format without a boot.

## Phase 3 - boot and success criterion

1. Restore the `false` handler and the scratch (Phase 1). Keep only the Phase 2
   patches.
2. `fastboot boot magisk_patched-30700_X0fyo.img` (E5/E4 form, RAM-only).
3. Measure the USB timeline with `tools/usb_watch.py`: the known rejection band
   is USB off at ~4.2 s, Android on at ~21.9 s, `reboot,fareboot`. Any strong
   deviation from that band is a sign the gate fell.
4. Real root criterion, not timing: `adb shell su -c id` -> uid=0;
   `getprop init.svc.magiskd`; `ls /sbin/su`. Absence of all three = failure.

If it fails, restore the 4 bytes of each call site and stop. Do not repeat the
boot with address variations: the gate is logical, not positional.

## Rollback and limits

Every byte written has its original saved in Phase 0/2. A single power cycle
restores the factory state in RAM. Nothing here is persistent.

What this plan does NOT cover:
- If Phase 1 fails, there is no code execution in BL33 in this form and the SMC
  patch is unreachable. Fall back to observations 2 and 3.
- If site 2 cannot be synthesized, boot stops after the gate. In that case the
  next step is to instrument the SMC return with the diagnostic stub, not another
  blind boot.
- Nothing here depends on env, cmdline, DTB or GhostLock.
