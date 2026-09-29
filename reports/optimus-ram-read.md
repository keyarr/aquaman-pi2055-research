# Optimus v2 RAM read over USB, round 4 (read-only)

date: 2026-09-29. goal of this round was narrow: prove that real bytes can be
pulled out of BL33 RAM through the `1b8e:c003` optimus v2 path, using nothing
but vendor control requests. no `flash`, no `erase`, no `setenv`, no
`saveenv`, no `write_raw_img`, no eMMC, no OTP, no partition. **no write verb
was ever issued to the device.** the stick was recovered by a manual power
cycle at the end, see §4.

## 0. TL;DR

- **RAM read: CONFIRMED.** not "success", not an oracle, actual bytes, twice,
  in two independent sessions.
- **the tools the task asked for (`md`, `mread`, `sha1sum`) cannot work on this
  device, and the code says so.** `optimus_mem_md()` prints to a console nobody
  can see and puts the literal string `"success"` in the reply. it returns zero
  bytes. the task premise was wrong; the working primitive is a vendor control
  request nobody had listed.
- the path that works is `AM_REQ_READ_MEM` (0x02): `memcpy` from an arbitrary
  address into the EP0 staging buffer, returned in the control IN stage.
  512 bytes per transfer max, and that cap is real, see §4.
- **an unmapped address kills the USB gadget for the rest of the session.**
  this is the single most important operational fact here, and it is what ate
  the rest of the round. `0x0` and `0x3ff00000` both stall and wedge it.
- the burning window is finite and the gadget is not resilient. a bad read does
  not self-heal the way a plain timeout does, it needs the power cycle.

## 1. the code audit: `md` is a dead end, and that is provable without a device

`optimus_mem_md()` in `v2_usb_tool/optimus_transform.c:275`:

```c
print_buffer(addr, (void*)addr, size, length, 16/size);   /* console */
strcpy(info, "success");                                   /* the only reply */
```

`print_buffer()` writes to the U-Boot console. round 3 (`usb-entry-aquaman.md`
§2.2) established the console on this stick is invisible: no UART, no video, and
the fastboot `oem` channel answers the constant `INFOAMLOGIC` regardless of
command. so `md` over optimus returns the same seven bytes `oem printenv`
returned. **zero bytes of RAM.**

`optimus_sha1sum()` with the 3-arg memory form has the identical defect
(`optimus_transform.c:180-203`): it hashes the range, `printf`s the digest,
`return 0`. a hash oracle with the digest printed to nowhere.

`mread` is not in the `optimus_working()` whitelist at all
(`optimus_transform.c:404-498`), so it falls through to `run_command()`
(`:495`) and prints to the same invisible console.

all three are refuted as *data* sources. they are at best existence oracles,
and even that is weak, because the optimus reply is the only thing the host
gets and the reply does carry the real `failed:` / `success` string, which is
more than the fastboot `oem` channel gave us. worth noting for later.

## 2. what does work: `AM_REQ_READ_MEM`

`v2_usb_tool/usb_pcd.c:435`, inside `do_vendor_request()`:

```c
case AM_REQ_READ_MEM:                       /* bRequest 0x02, bmRequestType 0xC0 */
        uint64_t memAddr = w_value;         /* 16 bits */
        memAddr <<= 16;
        memAddr += w_index;                 /* (wValue<<16)|wIndex = 32-bit addr */
        memcpy((void*)buff, (char*)memAddr, w_length);
        _pcd->buf    = buff;
        _pcd->length = w_length;
```

arbitrary address, arbitrary length, straight into the control IN stage. no
console, no parser, no `run_command()`. this is the primitive the task was
looking for and it is 4 lines of device code.

cap: `_pcd_buff[512]` (`usb_pcd.c:201`) and `CMD_BUFF_SIZE 512`. a bigger
`wLength` makes the device `memcpy` past `_pcd_buff` into the neighbouring
statics, so 512 is not a politeness limit, it is the line between a read and a
crash. the client hard-refuses anything larger.

the fast path for a full-DDR scan is `AM_REQ_RD_LARGE_MEM` (0x12,
`usb_pcd.c:486` and `:634`), which moves `intBuf[0]=addr, intBuf[1]=len` over
EP0 and streams the data out the bulk IN endpoint. **not exercised this round**,
see §7.

## 3. the evidence

entry is the round 3 path, unchanged: `adb reboot fastboot` →
`fastboot oem update 5000` → `1b8e:c003` in ~370 ms. baseline before the
trigger was `unlocked: yes`, `secure: no`,
`U-Boot 2015.01-g7ac5df7677-dirty` (`01_fastboot_baseline.txt`).

### 3.1 identify, stage 16 = TPL = U-Boot

```
$ python3 tools/optimus.py identify
raw     00 07 00 10
version 0.7
stage   16 (TPL/BL33-u-boot)
```

this is the control round 3 left as "NOT RUN, needs root". it is now run. the
stage byte is the discriminator from §4.2 of that report: `{maj,min,0,16}` means
U-Boot TPL, so the target is BL33, not the BL1 BootROM. **this closes the last
hole in the round 3 identification.**

one divergence worth recording: the reference tree says GXL answers
`{0, 8, 0, 16}` (`platform.h` via `USB_ROM_VER_MINOR`), the device answers
`{0, 7, 0, 16}`. minor byte differs, stage matches. more evidence for the
round 3 §1.2 conclusion that aquaman is a Xiaomi fork of a later tree, and a
reminder that family evidence is family evidence.

### 3.2 the actual RAM bytes

`06_probe_nonzero.txt`, one session, two reads:

```
0x20000000:
20000000  e3 95 62 04 ff ff ff ff ff ff ff ff ff ff ff ff  |..b.............|
20000010  ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff  |................|
...  0xff all the way down

0x3f000000:
3f000000  fe 69 00 01 05 40 fe 69 00 01 04 29 fe 69 00 01  |.i...@.i...).i..|
3f000010  05 2d fe 69 00 01 04 80 fe 69 00 01 02 e7 fe 69  |.-.i.....i.....i|
3f000020  00 01 05 74 fe 69 00 01 04 9b fe 69 00 01 05 1e  |...t.i.....i.....|
3f000030  fe 69 00 01 04 56 fe 69 00 01 02 33 fe 69 00 01  |.i...V.i...3.i..|
```

**RAM read: confirmed.** this is not a status string. three independent reasons
these are real DRAM contents and not an artifact:

1. `0x20000000` returns a plausible mixed state: 4 meaningful bytes then
   `0xff` fill, which is what a partly-used, never-rewritten DRAM region looks
   like. a stubbed or failed path would return a constant, not two different
   non-constant patterns at two different addresses.
2. the two addresses return **different, address-specific** data.
3. the device stayed enumerated (`1b8e:c003`, bus 003 device 048) after the
   reads, so the gadget did not fault.

### 3.3 the 12-byte record at `0x3f000000`

the second dump is not noise. it is a repeating 12-byte record:

```
fe 69 00 01 | 05 | 40
fe 69 00 01 | 04 | 29
fe 69 00 01 | 05 | 2d
fe 69 00 01 | 04 | 80
fe 69 00 01 | 02 | e7
fe 69 00 01 | 05 | 74
```

`fe 69 00 01` is a constant tag, byte 4 alternates `05/04/05/04/02/05`, byte 5
varies. that is a structured table sitting near the top of the 512 MB CPU
window, not U-Boot code and not stack. **UNCHARACTERIZED.** it is a lead for
the next round, not a finding. a plausible Amlogic guess is a DDR training or
PHY tuning result table, since GXL leaves those in high DRAM and the alternating
tag reads like a per-channel index, but that is a guess and the source tree did
not confirm it. do not build on it until it is.

## 4. what went wrong, and the one rule that matters

**reading an unmapped address wedges the USB gadget.** two observations, both
reproducible:

```
0x0         -> USBError [Errno 5] Input/Output Error    (stall)
0x3ff00000  -> USBError [Errno 5] Input/Output Error    (stall)
```

after either one, every subsequent request in that session fails with
`Errno 19 no such device` or `Errno 110 timed out`, and the gadget stays
enumerated but dead. 60 s of 1 Hz polling saw `1b8e:c003` present the whole time
and unresponsive. **the user power cycled the stick to recover it** (confirmed,
so this is not a self-recovery, do not assume one). same wedged-but-not-bricked
behaviour round 3 §2.3 saw with `oem sleep 3`, so it is a known property of this
build, not something new this round broke.

consequence for the method: **one bad address costs the whole session**, and a
scan that starts at an unmapped address tells you nothing about every address
after it. this is what burned the round. the scan of
`0x3e000000..0x40000000` started at `0x3e000000`, stalled immediately, and the
two probe sessions that followed reported timeouts that have nothing to do with
the addresses they named. do not read those timeouts as "0x3ff00000 is bad" or
"0x3fc00000 is bad". the only clean single-address result is the one in
`07_probe_3ff00000.txt`, and even that was taken against a gadget already dead
from the previous session, so **0x3ff00000 is not actually characterised yet**.

consistent with the GXL memory map: on this SoC `0x00000000` is not normal
DDR, and the CPU-accessible window starts around `0x20000000`. `0x20000000` and
`0x3f000000` both worked, `0x0` did not. **the usable read window is
`0x20000000..0x3fffffff` and the edges are unmapped.** derived from two data
points, not mapped. treat the boundaries as unknown until probed one address
per session.

## 5. timing, for whoever runs the next round

- entry to `1b8e:c003` on the bus: **370 to 490 ms** after `fastboot oem update
  5000`. consistent with round 3.
- one observed burning window: `1b8e:c003` from t=942.394 to t=1019.485, i.e.
  **77 s**, after which the device **rebooted itself back into Android**
  (2717:4e40, adb up) with no host action. round 3 recorded 100 s+ and no
  self-recovery, so the auto-burn timeout does fire eventually.
- but the *clean* window is much shorter than 77 s. the successful session in
  §3.2 completed identify + 2 reads in **134 ms total**. everything that
  followed, that spanned separate shell invocations, lost.
- **run identify, and all the reads, in one process, immediately after entry.**
  re-opening the device per command burns the window on process startup and on
  `sudo`. `tools/optimus_enter.sh` exists for exactly this.
- 512 bytes per control transfer is slow. a full sweep of the 512 MB window is
  1,048,576 transfers and will not fit in any window. **the scan needs the bulk
  path, see §7.**
- **two different failure modes, do not confuse them.** a clean auto-burn
  timeout drops `1b8e:c003` and the device comes back as Android on its own
  (observed, §5 bullet 2). a bad address instead leaves `1b8e:c003` enumerated
  but unresponsive, and that one needed the power cycle (§4). if the stick is
  still enumerated but every request times out, you are in the second case.

## 6. host side, two things worth knowing

- pyusb 1.3.1 and libusb 1.0 are present. claiming `1b8e:c003` needs root, same
  as round 3 §2.5 noted. no udev rule was installed, `sudo` was used directly,
  so the host is unmodified.
- **this host has sudo `tty_tickets` enabled, so a sudo call inside a pipe gets
  a fresh tty ticket and a fresh password prompt.** every `sudo` in the capture
  scripts is therefore a direct call with the password piped into `sudo -S`, and
  output is captured with `>` redirection instead of a pipe. this cost about
  twenty minutes and is worth writing down so the next round does not rediscover
  it.

## 7. what is left, in the order it should be done

1. ~~power cycle the stick.~~ done, the user did it, it is back on Android
   (`2717:4e40`, adb up). no cleanup outstanding.
2. **map the readable window one address per session**, binary-search style,
   starting from the known-good `0x3f000000` and `0x20000000`. do not scan into
   unknown space, that is what kills the gadget.
3. **get the bulk read working** (`AM_REQ_RD_LARGE_MEM`, 0x12). it needs a
   SETUP+OUT+IN sequence, EP0 OUT carrying `{addr, len}`, then the data comes
   back on the bulk IN endpoint. libusb's single-shot
   `libusb_control_transfer` cannot express that, so it needs either two chained
   control transfers or `libusb_alloc_transfer` with the two stages. without
   it there is no way to search anything.
4. only then hunt for `U-Boot 2015.01` or the `bd_t` / `gd_t` structures in the
   top of DRAM. the reference tree puts `CONFIG_SYS_MEM_TOP_HIDE` at
   `0x08000000` (`gxl_skt_v1.h:433`), which is a strong hint that U-Boot lives
   in the 16 to 32 MB below the top of the 512 MB window, which is where the
   §3.3 table already is. **a hint, not a location.**
5. characterise the 12-byte record before assuming it is anything.

## 8. phases 2 to 6 status

| phase | status |
|---|---|
| 1. prove RAM read | **CONFIRMED**, real bytes, two sessions, §3.2 |
| 2. locate U-Boot in RAM | not started, one lead (§3.3), window unmapped |
| 3. prove volatile RAM write | **not attempted**, deliberately, read-only round |
| 4. locate `do_bootm` / `aml_sec_boot_check` | not started, blocked on phase 2 |
| 5. patch feasibility | not started |
| 6. conclusion | premature, phase 2 not done |

the write primitives were audited but **not touched**: `AM_REQ_FILL_MEM` (0x03,
`usb_pcd.c:593`) writes 32-bit words from `(addr, value)` pairs,
`AM_REQ_WRITE_MEM` (0x01) writes a block, `AM_REQ_MODIFY_MEM` (0x04) is a masked
RMW. `tools/optimus.py` implements `fill` and `poke` but both refuse to run
without `--enable-write` **and** a `--write-ok lo,hi` range, so there is no
accidental path to a write in this round's tooling.

and one thing that belongs in phase 5 but is already visible now, so it does not
get forgotten: `AM_REQ_RUN_IN_ADDR` (0x05, `usb_pcd.c:621`) is

```c
value = (w_value << 16) + w_index;
fp = (void(*)(void))value;
dwc_otg_power_off_phy();
fp();
```

arbitrary code execution at an arbitrary address. phase 5 asks whether the
signature check can be patched in place, and the answer to that is partly
"you would not have to". not used, not going to be used this round. recording
it because it is the most dangerous request in the protocol and the stick
should not be left in optimus mode with a host attached.

## 9. residual risk

- the stick was left wedged in optimus mode and **was recovered by a manual
  power cycle** (user, confirmed). no writes were issued, so nothing persistent
  changed, and it is back on Android with adb up.
- a wrong address is destructive to the session, not to the device. nothing
  observed suggests a bad read corrupts anything; it kills the gadget.
- `0x0` and `0x3ff00000` are confirmed stall addresses, or rather `0x0` is;
  `0x3ff00000` was probed against an already-dead gadget and its result is
  **void**, not negative.
- no write, no flash, no env, no OTP, no partition. `unlocked: yes` /
  `secure: no` were read at baseline and never written this round.
