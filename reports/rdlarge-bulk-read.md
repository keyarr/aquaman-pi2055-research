# AM_REQ_RD_LARGE_MEM (0x12) on aquaman: the bulk IN never streams

date: 2026-09-29, round 5. the goal was narrow: get `AM_REQ_RD_LARGE_MEM`
working so RAM could be pulled out in big blocks instead of 512B at a time.
**it does not work on this build. the result is negative**, and it is negative
in a way that rules out the obvious explanations. no write verb was issued, no
eMMC, no env, no `flash`, no `RUN_IN_ADDR`. the stick was left enumerated in
optimus mode, see §9.

## 0. TL;DR

- **`RD_LARGE_MEM: NOT CONFIRMED.** the control stage is correct and completes
  in 0.000 s, the endpoint is healthy, the address is mapped, and the device
  still never puts a single byte on the wire. this is not a client bug.
- the bulk IN endpoint **works**: `AM_REQ_BULKCMD` (0x34) returned its full
  512-byte reply on EP 0x81 in the same sessions where 0x12 returned nothing at
  all. same endpoint, same session, seconds apart. that is the whole finding.
- the 0x12 control OUT never stalls. it completes. then EP 0x81 goes silent
  and the gadget dies. the failure is entirely in the bulk half.
- sizes 0x200 through 0x4000 all fail. it is not a block size limit.
- both proven addresses fail identically. it is not the address.
- **new operational fact, better than round 4's:** `libusb_reset_device`
  recovers the wedged gadget. no power cycle needed. round 4 §4 said the
  device needed a manual unplug, that is no longer true.
- the blocker is upstream of this task: without a bulk read, a 512 MB sweep is
  1,048,576 control transfers, which does not fit in a 77 second window. see §8.

## 1. transport audit, answered from the code

reference: `.src/u-boot-khadas/drivers/usb/gadget/v2_burning/v2_usb_tool/`,
the same family the device runs. the task said not to trust a project README,
and the README was not used. everything below is from `usb_pcd.c`,
`dwc_pcd.c`, `dwc_pcd_irq.c`, `dwc_pcd.h`.

### 1.1 the two request stages

`do_vendor_request`, `usb_pcd.c:484-498`:

```c
case AM_REQ_WR_LARGE_MEM:
        value = 1;
case AM_REQ_RD_LARGE_MEM:
        _pcd->bulk_len = w_value;      /* block length  */
        _pcd->bulk_num = w_index;      /* block count   */
        _pcd->buf = buff;              /* EP0 staging   */
        _pcd->length = w_length;       /* must be 16    */
        break;
```

note there is **no `bRequestType` check** on this path, unlike
`AM_REQ_READ_MEM` at `usb_pcd.c:436` which insists on 0xC0. both 0x40 and 0xC0
reach the handler.

`do_vendor_out_complete`, `usb_pcd.c:632-650`, the part that actually arms
everything:

```c
case AM_REQ_WR_LARGE_MEM:
        value = 1;
case AM_REQ_RD_LARGE_MEM:
{
        const unsigned* intBuf = (unsigned*)buff;
        _pcd->bulk_out      = (char)value;   /* 0 => read => IN */
        _pcd->bulk_buf      = (char*)(u64)intBuf[0];
        _pcd->bulk_data_len = intBuf[1];
        _pcd->bulk_xfer_len = 0;
        _pcd->xferNeedReply = 0;
        _pcd->bulk_len = DWC_BLK_LEN(_pcd->bulk_data_len);
        _pcd->bulk_num = DWC_BLK_NUM(_pcd->bulk_data_len);
        memcpy(&this_pcd[BULK_IN_EP_NUM], _pcd, sizeof(pcd_struct_t));
        start_bulk_transfer(_pcd);
}
```

`start_bulk_transfer` (`usb_pcd.c:270-274`) sets `bulk_lock` and calls
`dwc_otg_ep_req_start(_pcd, BULK_IN_EP_NUM)`.

### 1.2 the questions the task asked

**endianness.** both words are read as native `unsigned`, so on this ARM32 LE
target they are little endian 32-bit:

| offset | meaning |
|---|---|
| `buf[0:4]`  | address, LE32 |
| `buf[4:8]`  | total length, LE32 |
| `buf[8:16]` | never read by any code path |

**does wValue/wIndex need to match the total size?** no, and this is worth
writing down because it kills a whole family of guesses. `do_vendor_request`
stores them into `bulk_len`/`bulk_num`, and then `do_vendor_out_complete`
**overwrites both** at `usb_pcd.c:645-646` with `DWC_BLK_LEN`/`DWC_BLK_NUM`
computed from the real length, before any transfer is armed. on the wire they
are dead values. the host still sends them, because the public spec says to.

**max size per transfer.** `bulk_data_len` is `int`, signed 32-bit
(`dwc_pcd.h:184`), so the ceiling is 0x7fffffff in principle. in practice there
is no device-side buffer: `bulk_buf` is a raw pointer into RAM and the payload
is streamed straight out of it, so the only real limits are the burning window
and the host. **not the blocker**, see §3.

**max safe blocks.** `bulk_num` is not a host-controlled quantity at all, it is
recomputed from the length and merely decremented in `do_bulk_complete`
(`usb_pcd.c:856`). it never gates anything. a host-supplied block count is
irrelevant, consistent with 1.2.

**the IN endpoint, this build.** **0x81, bulk, MPS 512.** read off the running
device, not assumed:

```
$ python3 tools/optimus.py desc
if 0 alt 0 class 0xff/00/00
  ep 0x81 IN  2 mps 512
  ep 0x02 OUT 2 mps 512
```

and independently, `lsusb -v` plus sysfs: `Negotiated speed: High Speed
(480Mbps)`, `speed 480`, `bcdUSB 2.00`. so `USE_FULL_SPEED` is genuinely not
defined on this build and `BULK_EP_MPS` is 512 (`dwc_pcd.h:20-24`), which is
what `dwc_otg_bulk_ep_activate` programs into the 11-bit `depctl.mps` field
(`dwc_pcd.h:1380`). that checks out, `mps` really is wide enough for 512.

### 1.3 two things that will bite whoever picks this up again

**the block size the host asks for is ignored.** `DWC_BLK_MAX_LEN` is a
hardcoded `0x1000` (`usb_pcd.c:20`) and `DWC_BLK_LEN()` is
`min`-ish on that constant, never on `w_value`. so the device always ships
4096-byte blocks regardless of the "block length" in `wValue`. **phase 5's
`block_len` sweep of 0x100/0x400/0x1000/0x2000/0x4000 is a no-op on this
build by construction.** it would have measured noise. it is not needed.

`DWC_BLK_LEN` also has a tail quirk: for a remainder between 512 and 0xfff it
returns **512**, not the remainder, so the last chunk goes out in 512-byte
pieces. harmless, `do_bulk_complete` re-arms until `leftDataLen == 0`, but it
means the wire is not 4096-aligned at the end.

**the bulk IN is not hardware DMA.** `dwc_otg_ep_start_transfer` programs the
transfer and then unmasks the non-periodic-TX-FIFO-empty interrupt
(`dwc_pcd.c:478-497`); the FIFO is filled a dword at a time by
`dwc_otg_ep_write_packet` reading `ep->xfer_buff` (`dwc_pcd_irq.c:406-461`),
driven from `dwc_otg_pcd_handle_np_tx_fifo_empty_intr`. the whole thing is
polled, not interrupt driven: `optimus_core.c:31-36` is
`while (1) { if (usb_pcd_irq()) break; }`. good news is the data path is a
plain CPU read of `bulk_buf` and is therefore address agnostic. bad news is
that if that poll loop is not spinning, nothing moves.

## 2. what was built

`read_large_mem(addr, size, block_len=0x1000)` in `tools/optimus.py`, next to
the existing 0x02 reader, reusing the existing `find()`. it does exactly the
four steps and nothing else: control OUT for 0x12 with the 16-byte parameter
block, then read EP 0x81 until `size` bytes, then give up. **no retry**, no
fallback to 0x02, no write verb, no reset. a stall or a short read raises and
stops, because round 4 established that one bad address costs the session and
retrying on top of a wedged gadget only produces more timeout noise.

also added:

- `optimus.py desc` - dump the real endpoint descriptors
- `optimus.py rdlarge <addr> <len> [blk]` - raw dump, hash on stderr
- `tools/rdlarge_test.py` - the phase 3/4 ladder (0x1000, 0x10000, 0x100000
  against both proven addresses, each cross-checked byte for byte against 0x02)
- `tools/rdlarge_probe.py` - the diagnostic that isolated the failure

the ladder is correct and ready to run. it stops on the first failure by
design, which is why it stopped at step one.

## 3. the transaction that was actually sent

this is the deliverable the task asked for when the sequencing fails. eight
setup bytes then sixteen data bytes, on EP0 OUT, then a bulk read on 0x81.

**setup packet** (`bmRequestType` `bRequest` `wValue` `wIndex` `wLength`):

```
40 12 00 10 01 00 10 00
```

for `addr=0x20000000 size=0x1000 block_len=0x1000`. `wIndex=1` is
`ceil(0x1000/0x1000)`, i.e. the "block count" from the public spec, which
§1.2 shows is ignored anyway.

**16 byte OUT payload** (`usb_pcd.c:636`, `intBuf[0]` then `intBuf[1]`):

```
00 00 00 20 00 10 00 00  00 00 00 00 00 00 00 00
|------- addr -------| |------ len -------| |- ignored -|
```

`00 00 00 20` = 0x20000000 LE32. `00 10 00 00` = 0x1000 LE32.

**endpoint**: EP 0x81, bulk IN, MPS 512, high speed.

**response**: the control transfer **completes, in 0.000 s, no STALL**. that is
the important part and it took a while to appreciate. the setup and the OUT
stage are accepted and finished. then:

```
bulk IN on 0x81: nothing, ever, until the 8 s host timeout
  errno 110 ETIMEDOUT
then the gadget is dead:
  next request: errno 75 EOVERFLOW
```

and a libusb reset brings it back, stage 16 intact, `0x02` reading normally.

**the exact source used to build it**: `do_vendor_request` `usb_pcd.c:486-498`
for the setup fields, `do_vendor_out_complete` `usb_pcd.c:634-650` for the
parameter decode and the bulk arming, `start_bulk_transfer` `usb_pcd.c:270-274`
and `dwc_otg_ep_req_start` `dwc_pcd.c:547-563` for the EP1 IN setup, and
`dwc_otg_pcd_handle_np_tx_fifo_empty_intr` `dwc_pcd_irq.c:672` for the payload
loop.

## 4. the evidence

entry is unchanged from round 3/4: `adb reboot fastboot`, `fastboot oem
update 5000`, `1b8e:c003` in ~380 ms. baseline `unlocked: yes`, `secure: no`.
identify answers `00 07 00 10` = version 0.7, **stage 16 = TPL = U-Boot BL33**,
every session, before and after every failure.

### 4.1 the client is fine

`tools/rdlarge_probe.py`, one session, ordered by cost:

```
=== step 1: identify ===                        OK 00 07 00 10
=== step 2: 0x02 read 64B @ 0x20000000 ===       OK e3 95 62 04 ff ff ff ff ...
=== step 3: 0x34 BULKCMD, same endpoint ===      bulk IN 512 bytes: b'success\x00...'
=== step 4: 0x12 size=0 (arm ZLP, no DMA) ===    control OK 0.000s, bulk IN timeout
=== step 5: 0x12 size=0x1000 ===                 bulk IN timeout, gadget dead
```

step 3 is the load-bearing line. **`0x34` delivered 512 bytes on EP 0x81.** it
is the same `dwc_otg_ep_req_start` bulk branch, the same FIFO, the same poll
loop, the same endpoint. the only reason it works is that the payload comes
out of `_bulk_replyBuf`, a U-Boot static, instead of an arbitrary RAM address.

`md` was used for the 0x34 payload on purpose. `optimus_mem_md`
(`optimus_transform.c:275-297`) only reads and prints to the invisible console
and answers `"success"`, and the address was `0x20000000`, not `0x0`, because
`0x0` is unmapped on this SoC and a CPU read of it aborts. no side effect was
reachable from that request.

### 4.2 it is not the size

each attempt starts from a libusb reset, because a wedged session cannot
answer for the next size:

```
size 0x200  FAIL  usb errno=110
size 0x400  FAIL  usb errno=110
size 0x800  FAIL  usb errno=110
size 0x1000 FAIL  usb errno=110
size 0x2000 FAIL  usb errno=110
size 0x4000 FAIL  usb errno=110
```

six sizes, 512B to 16KB, all dead. so the FIFO does not run out of room and
this is not a "large" block problem. it is not large **at all**.

### 4.3 it is not the address

```
0x20000000  0x02 says: e3 95 62 04 ff ff ff ff ff ff ff ff ff ff ff ff
            0x12 control OK, 0x12 bulk IN FAIL errno=110
0x3f000000  0x02 says: 0c 00 00 00 01 00 00 00 a8 aa ae d2 10 10 00 00
            0x12 control OK, 0x12 bulk IN FAIL errno=110
control: 0x34 bulk IN 512 bytes b'success\x00...'
```

both proven addresses, both readable by 0x02 in the same session, both dead
over 0x12, and 0x34 alive again immediately afterwards.

side note, 0x3f000000 did not return the round 4 §3.3 pattern this time, it is
`0c 00 00 00 01 00 00 00 a8 aa ae d2 10 10 00 00`. different boot, different
point in U-Boot's life, so that region is **not** stable across sessions.
anything built on reading it needs to re-read it each time.

### 4.4 it is not ordering, and the endpoint is not cold

```
A1 0x34 bulk IN 512 bytes b'success...'
A2 0x12 bulk IN FAIL errno=110 (control 0.000s, got 0)
B1 0x12 again, warm: control FAIL
C1 0x34 again: control FAIL      <- gadget dead by now, so B and C are void
```

A is the one that counts: a successful 0x34 immediately before a failed 0x12,
same endpoint, same session. B and C only show the usual death spiral after the
wedge and are not evidence on their own.

## 5. what is left unexplained, honestly

`start_bulk_transfer` is called with `this_pcd[0]`, the **EP0** struct, while
the working 0x34 path calls `dwc_otg_ep_req_start(&this_pcd[BULK_IN_EP_NUM])`,
the **bulk IN** struct (`bulk_cmd_reply`, `usb_pcd.c:930-939`). at arm time
`dwc_otg_ep_req_start` only reads `bulk_buf`, `bulk_len` and `bulk_xfer_len`
out of the pcd it was handed, and all three are set on `this_pcd[0]` too, so
the two calls are equivalent as far as the arming goes. the struct it is
handed is not the difference.

what is left, in the order I would bet on it:

1. the arming happens inside the EP0 OUT-data-phase completion, before the
   status stage has unwound (`handle_ep0` case `EP0_OUT_DATA_PHASE`,
   `dwc_pcd_irq.c:244-248`), and then the ISR writes back the whole captured
   `GINTSTS` at `dwc_pcd_irq.c:1286`. the 0x34 path has an
   `optimus_working()` call in between, so it arms from a quieter state. this
   is a guess about an interrupt-ack ordering race, and I could not confirm it
   without a console.
2. the device's copy of this driver is a Xiaomi fork, not this tree. round 4
   already found a version divergence, the device says 0.07 and this tree
   says 0.08. the 0x12 path may simply be different or dead in the real build.
3. something about `bulk_buf` pointing at 0x20000000 rather than a U-Boot
   static, even though the read itself is a plain CPU read.

**none of these are testable from the host**, and chasing them needs either a
console or a modified bootloader. I stopped here rather than grinding through
parameter combinations, which the task explicitly told me not to do.

## 6. phases 2 to 6, status

| phase | status |
|---|---|
| 1. transport audit | **done**, all six questions answered, §1 |
| 2. minimal 0x12 client | **done**, `read_large_mem`, no writes, no retry, §2 |
| 3. ladder 0x1000 / 0x10000 / 0x100000 | **stopped at step 1**, 0x12 returns 0 bytes |
| 4. byte-for-byte vs 0x02 | **impossible**, nothing to compare |
| 5. max useful block_len | **moot**, the host block length is ignored (§1.3) |
| 6. BL33 search prep | **blocked**, no bulk read means no scan |

the deliverable asked for, "a file of at least 0x10000 bytes that matches 0x02
byte for byte", **does not exist**. I am not going to dress up a 0x12 that
returns nothing as progress.

## 7. one thing that did get better

round 4 §4 concluded that a wedged gadget needs a manual power cycle, and it
cost the user an unplug. that is no longer necessary:

```python
dev.reset()          # libusb_reset_device
time.sleep(0.6)
usb.core.find(idVendor=0x1B8E, idProduct=0xC003)
```

after that, identify answers stage 16 again and 0x02 reads normally. it was
found by accident, on the first session, and every later test in this round
used it to recover instead of asking for a power cycle. `clear_halt` on 0x81
and 0x02 does **not** help, it fails with errno 75; only the bus reset does.

`errno 75 EOVERFLOW` is the reliable signature of a wedged gadget here. round 4
saw errno 19 and 110. all three mean the same thing.

## 8. what this costs the project

the original reason for wanting 0x12 was throughput. without it:

- 512 bytes per control transfer is the hard cap, `_pcd_buff[512]` at
  `usb_pcd.c:201` and `CMD_BUFF_SIZE 512`. a bigger `wLength` makes the device
  `memcpy` past the buffer into neighbouring statics, so it is a crash, not a
  politeness limit.
- 512 MB / 512 B = 1,048,576 transfers.
- the observed burning window is 77 s, and the clean part of it is much
  shorter.

so a full sweep is off the table and a targeted one is not affordable either.
the remaining ways to get U-Boot out of RAM are all worse than what we had:

1. find a code path that reuses the buffer manager, i.e. `AM_REQ_UPLOAD` (0x33)
   or `AM_REQ_DOWNLOAD` (0x32). **0x33 does not help**, `optimus_buf_manager`
   only holds data that was previously downloaded, it cannot be pointed at
   arbitrary RAM. worth knowing before anyone spends a round on it.
2. give up on reading RAM and go after the on-disk bootloader instead.
   `bootloader.img` is 1.3 MB and already in this repo. the round 5 question
   was "find U-Boot in RAM", and the honest answer is that RAM reading is
   capped at 512 B per request, so the on-disk artifact is the cheaper path to
   the same code.
3. `AM_REQ_RUN_IN_ADDR` (0x05) can call back into U-Boot and have *it* copy the
   data out. forbidden this round, and still forbidden, and it is the most
   dangerous request in the protocol. noting it only so the next round does not
   rediscover it as if it were new.

## 9. state of the stick, and residual risk

- **left enumerated as `1b8e:c003` in optimus mode**, alive at the end of the
  last test (0x34 succeeded, so the gadget was healthy). it may self-reboot
  back to Android, round 4 saw that after 77 s, or it may need a power cycle.
  no writes were issued at any point in this round, so nothing persistent
  changed.
- a wedged gadget is recoverable in software now, see §7, so the blast radius
  of a failed 0x12 is one reset.
- `0x3f000000` is **not** stable across boots (§4.3). anything that caches it
  is wrong.
- the phase 6 goal, "identify a first BL33 code region", is not reached and is
  not currently reachable without either the bootloader image or a bulk read
  path that this round could not make work.
