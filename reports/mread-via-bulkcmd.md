# mread mem via 0x34 + 0x33: CONFIRMADO

date: 2026-09-29, round 6. the goal was the official Amlogic mread path,
`AM_REQ_BULKCMD` (0x34) + `upload mem` + BULK IN through the Optimus upload
routine. **it works.** 1 MiB came out and matched `AM_REQ_READ_MEM` (0x02) byte
for byte, 16384 control reads, zero mismatches. 64 MiB came out at 15 MiB/s.

no write verb, no eMMC, no env, no flash, no 0x05, no 0x12. see §7 for the
state of the stick.

## 0. TL;DR

- **`mread mem` via 0x34 + 0x33: CONFIRMED.** 0x200, 0x1000, 0x10000 and
  0x100000 all byte-for-byte identical to 0x02.
- **0x12 is gone from the tree.** `read_large_mem` and the `rdlarge` verb are
  deleted, along with `tools/rdlarge_test.py` and `tools/rdlarge_probe.py`.
  the old report stays as the record of the negative result.
- **the framing was read out of the Amlogic host, not guessed.** the exact
  setup packets are in §2, they come from `AmlLibusb.cpp`.
- **byproduct: 0x02 caps at 64 bytes on this build, not 512.** round 4 claimed
  512 and never tested it. measured 1..64 answer, 65+ time out. this makes the
  cross-check path 8x more expensive than everyone thought, see §5.
- **13 MiB/s.** the 512 MB window that was "off the table" in round 5 is now
  about 40 seconds of transfer. the blocker is gone.
- the stick dropped off the bus when I pointed the scanner at 0x0, see §6. do
  not do that. unmapped is worse than a wedge.

## 1. why 0x12 was the wrong door

0x12 (`AM_REQ_RD_LARGE_MEM`) asks the device to DMA an arbitrary address out on
the bulk IN endpoint, armed from `do_vendor_out_complete`, `usb_pcd.c:634`.
It never produced a byte on this build, six sizes, two addresses, one session
with a working 0x34 right before it. full write-up in
`reports/rdlarge-bulk-read.md`.

0x34 + 0x33 is a different door into the same hardware. The payload still comes
straight out of RAM, but it is armed by `optimus_buf_manager_get_buf_for_bulk_transfer`
after a successful `optimus_working()`, not by a raw setup packet. The buf
manager also runs `optimus_dump_storage_data` first, which for
`OPTIMUS_MEDIA_TYPE_MEM` is a validated `memcpy` from the source address into
the transfer buffer. Same bytes, a lot more code around them, and that code
path is exercised by the shipping burning tool every day. **that is the whole
difference: 0x12 is an untested corner, 0x33 is the path the vendor depends
on.**

## 2. the framing, from the host tool

read from `zspace/amlogic-p230-update`, files `AmlLibusb.cpp` and
`UsbRomDrv.cpp`. nothing here is inferred from function names.

### 2.1 the command, 0x34

`update_sub_cmd_mread`, `update.cpp`:

```c
snprintf(buffer, sizeof(buffer), "upload %s %s %s 0x%llx",
         storeOrMem, partition, filetype, readSize);
buffer[66] = 1;
rom.bufferLen = 68;
AmlUsbBulkCmd(&rom);
```

`AmlUsbBulkCmd` sends control code 0x80002050, which lands in
`IOCTL_BULK_CMD_Handler`, `AmlLibusb.cpp:234`:

```c
if (!ctrl.in_buf || ctrl.in_len != 68) return 0;
int ret = usb_control_msg(handle, 64, request, 0, 2, ctrl.in_buf, 64, 50000);
```

so the wire format is, for `upload mem 0x20000000 normal 0x1000`:

```
40 34 00 00 02 00 40 00
75 70 6c 6f 61 64 20 6d 65 6d 20 30 78 32 30 30 30 30 30 30 30 20 6e
6f 72 6d 61 6c 20 30 78 31 30 30 30 00 ...pad to 64
```

bmRequestType 0x40, bRequest 0x34, **wValue 0, wIndex 2, wLength 64**, then 64
bytes of NUL-padded ASCII. `buffer[66] = 1` is not sent: bytes 64..67 of the
host struct are where wValue/wIndex live, and the handler only puts bytes
0..63 on the wire.

`wIndex 2` is not decoration. `usb_pcd.c:547`:

```c
if (2 == w_index) usb_set_reply_cmd_id(AM_REQ_BULKCMD);
```

which is what arms the "Continue:34" keepalive the host polls for in
`AmlUsbBulkCmd`. My first probe used `wValue 0x200 wIndex 2 wLength 18` and it
also worked, but the official framing is the one in the tool.

the reply is **always 512 bytes** on EP 0x81. `do_bulk_cmd`, `usb_pcd.c:944`,
calls `bulk_cmd_reply` unconditionally, and `AM_BULK_REPLY_LEN` is
`CMD_BUFF_SIZE` = 512. measured: 512 bytes, `success` then NUL padding.

### 2.2 the transfer, 0x33

`ReadMediaFile` loops on `AmlReadMedia`, which sends control code 0x8000204C,
`IOCTL_READ_MEDIA_Handler`, `AmlLibusb.cpp:210`:

```c
if (!ctrl.in_buf || ctrl.in_len <= 0xF) return 0;
int value = *((short *)ctrl.in_buf + 32);
if (!value || value > 0x1000) value = 4096;
uint64_t len = LONG_AT(ctrl.in_buf, 4);
unsigned int index = (unsigned int)(value + len - 1) / value;
int ret = usb_control_msg(handle, USB_ENDPOINT_IN | USB_TYPE_VENDOR,
    AML_LIBUSB_REQ_READ_MEDIA, value, index, ctrl.in_buf, 16, timeout);
```

`AML_LIBUSB_REQ_READ_MEDIA` is 0x33. The transfer is:

```
C0 33 00 10 01 00 10 00
```

bmRequestType 0xC0, bRequest 0x33, wValue 0x1000, wIndex 1, **wLength 16**,
and it returns 16 bytes. Measured on the device:

```
e8 ef 00 00  00 10 00 00  00 00 00 00  00 00 00 00
|--- 0xefe8 ---| |--- 0x1000 ----| |---- zero ----|
```

those are `optimus_buf_manager_get_command_data_for_upload_transfer`,
`optimus_buffer_manager.c:307`, writing `[0-3] = 0xefe8` and
`[4-7] = thisTransDataLen`. nothing writes [8-15].

**this 16-byte answer is the trigger.** `do_vendor_in_complete`,
`usb_pcd.c:739`, runs on the status stage of that very control IN and calls
`start_bulk_transfer`. the payload then arrives on EP 0x81 with no further
request. the host loop is: send 0x33, read `[4:8]` bytes off bulk IN, repeat.
`[4:8] == 0` means done.

## 3. the questions phase 2 asked

| question | answer | source |
|---|---|---|
| which request triggers the upload | 0x33, control IN, wLength 16 | measured |
| does 0x34 alone leave state pending | yes, it arms the buf manager, nothing streams until 0x33 | `optimus_parse_download_cmd` |
| must the host send 0x33 after | yes, once per chunk | `ReadMediaFile` loop |
| bytes per transfer | min(64K, remaining). 0x100000 = 16 transfers, 0x10000 = 1 | `OPTIMUS_DOWNLOAD_SLOT_SZ` |
| how does the host know it is done | `[4:8] == 0` in the 0x33 answer | `thisTransDataLen` |
| how is the address interpreted | `simple_strtoull(argv[2], 0)`, so `0x20000000` parses as hex | `optimus_download.c:1103` |
| decimal or hex size | `0x%llx`, and parsed with base 0, so hex | `update.cpp` / `:1098` |
| per-block transport header | none. raw bytes, no length prefix, no checksum | the payload is the `memcpy` result |

## 4. what was built

three files, all read-only:

- `tools/optimus.py` - `bulkcmd()`, `upload_next()`, `mread_mem()`,
  `scan`/`read`/`tpl` unchanged. the `rdlarge` verb and `read_large_mem()`
  are deleted.
- `tools/mread_test.py` - the ladder with the 0x02 cross-check.
- `tools/mread_scan.py` - region scanner, `0x20000000..0x21000000` style.

`mread_mem()` is the whole thing:

```python
reply = bulkcmd(dev, "upload mem 0x%x normal 0x%x" % (addr, size))
while len(out) < size:
    want = upload_next(dev)     # the 16 bytes, 0xefe8 + length
    if not want:
        break
    ... read `want` bytes off EP 0x81 ...
```

no retry, no fallback to 0x02, no reset. if the gadget is already wedged the
run ends, because round 5 established that retrying on top of a dead gadget
only produces more timeout noise.

**denylist.** `upload` is in `DENY` because `optimus_working` dispatches it.
the `bulkcmd` verb allows exactly `upload mem ...`, which is the read half:
`isUpload` keeps `nextWriteBackSlot` at 0 so nothing is ever written back
(`optimus_buffer_manager.c:149`). `download` stays denied.

## 5. the evidence

`reports/round6-mread/`, entry is `fastboot oem update 5000`, identify answers
`00 07 00 10` = version 0.7, **stage 16 = TPL = U-Boot BL33**.

### 5.1 the remote command, phase 1

```
bulkcmd 'echo hello'                       -> 512 bytes, b'success\0...'
bulkcmd 'upload mem 0x20000000 normal 0x1000' -> 512 bytes, b'success\0...'
```

`echo hello` answering `success` with no text is expected: it goes through
`run_command()` and prints to the console nobody has, exactly like `md` in round
4. what matters is that the command is accepted and the buf manager is armed.

### 5.2 the 0x33 answer, measured

```
0x33 #0 -> 16 bytes e8 ef 00 00 00 10 00 00 00 00 00 00 00 00 00 00
            magic=0xefe8 len=0x1000
```

for `upload mem 0x20000000 normal 0x1000`. the length is the whole request, in
one transfer.

### 5.3 the ladder, phase 3 and 4

`12_ladder.txt`, one session, `0x20000000`:

| size | bytes | transfers | time | throughput | 0x02 cross-check |
|---|---|---|---|---|---|
| 0x200 | 512 | 1 | 0.020s | 24 KiB/s | MATCH, 8 reads |
| 0x1000 | 4096 | 1 | 0.021s | 194 KiB/s | MATCH, 64 reads |
| 0x10000 | 65536 | 1 | 0.024s | 2.6 MiB/s | MATCH, 1024 reads |
| 0x100000 | 1048576 | 16 | 0.088s | 11.4 MiB/s | MATCH, 16384 reads |

```
0x20000000 0x100000 sha256 0b1b76d138721ca9e640f899a3f85c713f08a9eb44730b6097e2edd326b18f75
```

every one is byte-for-byte identical to 0x02. that is the deliverable.

larger, `13_scale.txt`, no cross-check, hash only:

```
0x20000000 67108864 bytes  1024 transfers  4.34s  15.1 MiB/s
0x3f000000     65536 bytes     1 transfers  0.02s   2.6 MiB/s
```

64 MiB is 1024 transfers of 64K, so the chunk size is confirmed at scale, and
the second proven address works through the same path.

throughput note: the per-call overhead dominates, 0x10000 in one 64K transfer
beats 16 x 64K by 4x. the cost is the 0x33 round trip per chunk, not USB.

### 5.4 the 0x02 cap is 64, not 512

this is the one thing round 4 got wrong and I only found it because the
cross-check kept timing out. `11_02_boundary.txt`, one session, 0x02 alone
after a bus reset, no mread anywhere:

```
len=  1 OK      len= 64 OK
len= 32 OK      len= 65 FAIL errno 110
len= 63 OK      len= 66 FAIL errno 110
                 len=128 FAIL errno 110
```

`_pcd_buff` is 64 bytes on this build. the official host agrees:
`AmlLibusb.cpp:61` sends `min(ctrl.out_len, 64u)` for `READ_MEM`. **round 4
never went above 64**, `do_probe` only ever read 64, so the 512 cap in
`reports/optimus-ram-read.md` §1 is an assumption from the reference tree that
was never tested. `MAX_RD` is now 64 and the comment says why.

this is the real reason the 0x02 cross-check is slow: 1 MiB is 16384 control
transfers, not 2048. it still took 1.1s, so it is not a problem, but every
number in the old report that assumed 512 B/transfer is 8x optimistic.

### 5.5 the race I chased and did not find

`05_state_after.txt` through `09_matrix64.txt`. my first ladder run timed out
on the 0x02 right after a successful mread, which looked like the upload
leaving the gadget in a bad state. it is not: 0x02 above 64 always fails,
mread or no mread. at 64 the same read succeeds four times in a row after an
mread. **no race, just the 64-byte cap.** recorded because the symptom looked
like one and someone will hit it again.

## 6. phase 5, the scanner

`tools/mread_scan.py` is ready and ran. `14_scan.txt`:

```
0x20000000..0x21000000  16 MiB in 1.2s   ddr 121 hits
0x3f000000..0x40000000  16 MiB in 1.2s   ddr 68 hits, aml_ 1 hit at 0x3f2420a8
```

and `16_scan_20000000_22000000.txt`, 32 MiB in 2.4s, 13.2 MiB/s.

**what the hits are: not BL33.** `15_context.txt` and
`17_bl33_context.txt` show `ro.bootmode` (the "bootm" hit is a substring) and
a base64 blob (the "BL2" hit). both of the phase 5 target regions are the
**running Android system image**, framework strings and vendor HALs. the BL33
we are burning from is not resident there, or is not in the first 32 MiB of
DDR.

no U-Boot version string, no `gd->`, no `aml_sec_boot_check` anywhere in
0x20000000..0x22000000 or 0x3f000000..0x40000000. the phase 5 goal of finding
BL33 is **not** met, and I am not going to call a substring match progress.

**do not scan below 0x20000000.** `18_scan_low.txt`: pointing the scanner at
0x0 killed the session outright, `errno 19 no such device`, the stick left the
bus entirely. that is not the "wedge the gadget, reset recovers" failure from
round 5, that is the whole USB device going away. 0x0 is BootROM/ATF territory
and it is not mapped in TPL. the scanner now stops instead of trying to
recover, because there is nothing to recover.

next step for whoever continues: the search has to go somewhere else. the
reference tree puts the transfer buffer at
`OPTIMUS_DOWNLOAD_TRANSFER_BUF_ADDR` = `DDR_MEM_ADDR_START + 4M`, 64 MiB of it
(`optimus_download.h:72-78`), so DDR starts around 0x20000000 and the buffer
runs to about 0x20400000. the interesting range is probably **above** the
Android image, 0x3f000000 and up is system, so try the 0x21000000..0x24000000
band and the region between the Android bits.

> **CORRECTED in round 7, this paragraph is wrong.** `DDR_MEM_ADDR_START
> ( 0x073<<20 )` is hardcoded for the KHADAS 128 MiB VIM board, it says nothing
> about the aquaman. the aquaman has **1 GiB with base 0x0**
> (`memory@0 reg = <0 0 0 40000000>`, `MemTotal 1004412 kB`), so 0x20000000 is
> DDR offset 512 MiB and 0x3f000000 is offset 1023 MiB. both scans above
> looked at the top half of RAM, which is where the running Android heap is.
> u-boot is at `CONFIG_SYS_TEXT_BASE` = 0x01000000, 512 MiB below the first
> byte that was ever dumped. see `reports/bl33-offline-round7.md`.

## 7. state of the stick, and residual risk

- **the stick is off the bus**, back in normal Android mode, after the 0x0
  scan. no writes were ever issued in this round, so nothing persistent
  changed. `adb devices` is empty and `lsusb` shows no 1b8e, which is the
  expected state after it self-rebooted. re-enter with `fastboot oem update
  5000`.
- 0x33 arms a bulk IN from an address the host chooses. a bad address does not
  wedge the gadget, it **removes the device from the bus**, see §6. treat any
  address under 0x20000000 as hostile.
- the 64 MiB read at 15 MiB/s means a 512 MB sweep is ~35s of transfer plus
  whatever the protocol overhead costs. that fits in the burning window now.
  it did not in round 5. **the throughput blocker from round 5 §8 is
  resolved.**

## 8. phases, status

| phase | status |
|---|---|
| 1. bulkcmd only | **done**, `echo hello` and `upload mem` both reply `success` |
| 2. exact upload framing | **done**, from `AmlLibusb.cpp`, §2 |
| 3. smallest mread, 0x200 vs 0x02 | **done**, byte for byte |
| 4. 0x1000 / 0x10000 / 0x100000 | **done**, all byte for byte, plus 64 MiB |
| 5. region scanner | **tool ready and run**, BL33 **not** found, §6 |
| 6. 0x12 retired | **done**, code and tools deleted |
