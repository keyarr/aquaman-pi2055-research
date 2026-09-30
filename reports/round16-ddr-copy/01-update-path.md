# round 16.01 - update path: where host bytes land

date: 2026-09-30. static only, no device, no USB, no execution.
image: reports/round14-bl33-persist/bl33-37e18000.bin (0x37e18000..0x37ff0000,
sha256 664fb34a...). reference: .src/u-boot-khadas (khadas-vims-nougat).
tool: tools/bl33_round16.py (buffers, update verbs).

## 1. two different "update" data paths, both fixed-address

There are two host-to-RAM ingress paths in this build. Neither takes a
host address. Both take host data + host size with a gate.

### 1a. fastboot download -> 0x10200000 (PROVEN in image)

rx_handler_dl_image at 0x37e95274 (drivers/usb/gadget/f_fastboot.c):

```text
0x37e952dc  mov   x1, #0x10200000
0x37e952e0  add   x0, x1, w0, uxtw     ; dst = 0x10200000 + download_bytes
0x37e952e4  mov   w2, w22              ; len = min(remain, req buf)
0x37e952e8  mov   x1, x5               ; src = USB req buf
0x37e952ec  bl    0x37eaaeec           ; memcpy
0x37e952f4  add   w22, w22, w0
0x37e952f8  str   w22, [x21]           ; download_bytes += len
```

cb_download at 0x37e95408 parses the size and gates it:

```text
0x37e95450  mov   x1, #0
0x37e95458  bl    0x37eac21c           ; download_size = simple_strtoul(cmd,16)
0x37e95464  str   w0, [x19]            ; [0x37fbdf90] = download_size
0x37e95478  str   wzr, [x21]           ; [0x37fbdf8c] = download_bytes = 0
0x37e95498  mov   w0, #0x10200000
0x37e954a0  bl    0x37e953e4           ; w0 = ddr_size_usable(0x10200000)
0x37e954a8  cmp   w2, w0
0x37e954ac  b.ls  ok
0x37e954b4  str   wzr, [x19]           ; too large -> download_size = 0 + FAIL
```

ddr_size_usable at 0x37e953e4:

```text
0x37e953e4  ldr   x1, [x18]            ; gd
0x37e953e8  mov   w2, #-0xd000000      ; -208 MiB reserve bundle
0x37e953ec  ldr   x1, [x1, #0x90]      ; bi_dram size (1 GiB on aquaman)
0x37e953f0  add   w1, w1, w2           ; dram - 0x0d000000
0x37e953f4  sub   w0, w1, w0           ; minus addr_start
0x37e953f8  mov   w1, #0x8000000       ; 128 MiB cap
0x37e953fc  cmp   w0, w1
0x37e95400  csel  w0, w0, w1, ls       ; usable = min(computed, 128 MiB)
```

Result:

```text
update buffer base (fastboot) = 0x10200000
update size source = host "download:<hex>", simple_strtoul, 32-bit w
size limit = min(dram-0x0d000000-0x10200000, 0x8000000); 0 rejected, over-limit rejected
address control by host = NO (base is mov-imm, offset is download_bytes counter)
range = [0x10200000, 0x18200000) at most 128 MiB
```

Correction to reports/fastboot-memory-flow.md: that file said BUF was
unknown / not proven and used khadas constants (BUF 0x10200000 ->
usable 0x22e00000). The image proves BUF = 0x10200000 AND a different
usable function (208 MiB reserve bundle + 128 MiB cap), which is exactly
why the device reports max-download-size 0x08000000. The old arithmetic
table is superseded for this build; the conclusion (BUF != proof via
that arithmetic) still stands, but the premise "BUF unknown" is now
false.

### 1b. v2 burning (cmd update) -> 0x07700000 (PROVEN in image + source)

optimus_buf_manager_init at 0x37e7bbe0:

```text
0x37e7bbe8  adrp  x1, #0x37f5e000
0x37e7bbec  add   x1, x1, #0x600       ; x1 = 0x37f5e600 (&transferBuf)
0x37e7bbf0  ldr   x2, [x1]
0x37e7bbf4  mov   x3, #0x7700000
0x37e7bbf8  cmp   x2, x3
0x37e7bbfc  b.eq  ok                   ; transferBuf must equal 0x7700000
```

Header .src/u-boot-khadas/drivers/usb/gadget/v2_burning/v2_common/optimus_download.h:63-78:

```text
DDR_MEM_ADDR_START 0x073<<20 (=0x07300000)
SPARSE_IMG_LEFT_DATA_ADDR_LOW = +2M (=0x07500000)
OPTIMUS_DOWNLOAD_TRANSFER_BUF_ADDR = +2M (=0x07700000)
OPTIMUS_DOWNLOAD_TRANSFER_BUF_TOTALSZ = 64M
```

Result:

```text
update buffer base (burning) = 0x07700000
update size source = host USB bulk slots (64 KiB slots, 1024 slots, manager-checked)
size limit = 64 MiB window [0x07700000, 0x0b700000); oversize is a protocol error, not a store
address control by host = NO (base is a header constant + runtime equality check)
```

### 1c. cmd update handler itself takes no address

cmd_tbl slot 0x37f62230: update -> 0x37e78ff8, maxargs 3. Handler:

```text
0x37e79008  cmp   w2, #1
0x37e7901c  ldr   x0, [x3, #8]         ; argv[1]
0x37e79024  bl    simple_strtoul       ; w20 = timeout/ms
0x37e79038  ldr   x0, [x21, #0x10]     ; argv[2]
0x37e79044  bl    simple_strtoul       ; w19 = second numeric arg
0x37e79058  mov   w0, #0xefe5
0x37e7905c  bl    0x37e7b8e4           ; [0x37f8aa38] = 0xefe5 (mode tag, not addr)
0x37e79060  cbz   w19, default
0x37e79064  ldr   x1, [x21, #0x10]     ; argv[2] string
0x37e7906c  adrp  x1, default ...      ; else "identifyWaitTime" default env path
0x37e79074  adrp  x0, ...              ; "identifyWaitTime"
0x37e7907c  bl    setenv_backend
0x37e79080  mov   w0, w20
0x37e79090  b     0x37e78f94           ; v2 burning entry, w0 = timeout
```

0x37e78f94 -> 0x37e76df8 (phy regs) -> 0x37e767c4 (w0=timeout: 0 means
default 0x4c4b40 at [0x37f8a384]) -> buffer init -> burning loop. Neither
argv becomes a store address. maxargs 3 means at most argv[1..2] anyway.

## 2. required output

```text
update buffer base (fastboot) = 0x10200000
update buffer base (burning)  = 0x07700000
update size source = host download_size (fastboot) / host bulk slots (burning)
size limit (fastboot) = min(dram-0x0d000000-base, 0x8000000); 0 and over-limit rejected
size limit (burning)  = 64 MiB window; manager-checked slots
address control by host = NO (both paths)
```

Distinction the brief demands:

```text
host controls the DATA: YES (both paths memcpy host USB bytes to the fixed buffer)
host controls the SIZE: YES within the gate (fastboot) / slot protocol (burning)
host controls the ADDRESS: NO (mov-imm bases; offset is a device counter, not a host arg)
```

No address control is inferred from data control. The two are separated
above by instruction, not by assumption.
