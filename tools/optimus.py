#!/usr/bin/env python3
"""optimus.py - minimal Amlogic optimus v2 USB burning client (read-only).

The U-Boot console on this stick is invisible (reports/usb-entry-aquaman.md
2.2), so `md` / `mread` / `sha1sum` are useless over the tpl_cmd channel: they
print to a console nobody sees and the host only ever gets "success". The bytes
have to come out through the vendor control requests instead.

  optimus.py identify              -> 0x20, 4 bytes {ver_maj,ver_min,stage_maj,stage_min}
  optimus.py desc                  -> real endpoint descriptors of the device
  optimus.py read <addr> <len>     -> 0x02, raw RAM dump to stdout
  optimus.py bulkcmd '<command>'   -> 0x34 out + 512B bulk IN reply (denylisted)
  optimus.py mread <addr> <len>    -> 0x34 "upload mem" + 0x33, the official mread
  optimus.py scan <a> <b> <pat>    -> 0x02 in 512B windows, hunt for a byte string
  optimus.py tpl '<command>'      -> 0x30 out + 0x31 in, tpl_cmd string (denylisted)
  optimus.py fill <addr> <val> ... -> 0x03, 32-bit write, needs --enable-write
  optimus.py poke <addr> <val>     -> 0x01, block write, needs --enable-write

Write verbs are refused unless --enable-write is passed, and even then the
target must be inside --write-ok ranges. There is no code path here that
touches flash, the env, the OTP or any partition.

0x12 (AM_REQ_RD_LARGE_MEM) is gone, it is dead on this build, see
reports/rdlarge-bulk-read.md. 0x33 + 0x34 replaced it, see
reports/mread-via-bulkcmd.md.
"""
import hashlib
import struct
import sys
import time
import usb.core
import usb.util

VID, PID = 0x1B8E, 0xC003

RT_OUT = 0x40
RT_IN = 0xC0

REQ_READ_MEM = 0x02
REQ_FILL_MEM = 0x03
REQ_IDENTIFY = 0x20
REQ_TPL_CMD = 0x30
REQ_TPL_STAT = 0x31
REQ_UPLOAD = 0x33
REQ_BULKCMD = 0x34

# dwc_pcd.h:17,18,23  USE_FULL_SPEED is commented out, so this is a high speed
# gadget: bulk IN is EP1 IN (0x81), bulk OUT is EP2 (0x02), MPS 512.
BULK_IN_EP = 0x81

BULK_CHUNK = 1 << 20
BULK_TIMEOUT = 15000

# CMD_BUFF_SIZE 512, AM_BULK_REPLY_LEN = CMD_BUFF_SIZE. The bulkcmd command
# payload is the first 64 bytes of a 68 byte host struct; bytes 64..67 are
# wValue/wIndex and are not sent as data (AmlLibusb.cpp:238, 161).
BULKCMD_DATA = 64
BULK_REPLY = 512

# optimus_buf_manager_get_command_data_for_upload_transfer, 16 bytes back:
# [0-3] 0xefe8, [4-7] bytes about to be streamed, [8-15] stale.
UPLOAD_CMDLEN = 16
UPLOAD_MAGIC = 0xEFE8

# The real cap on this build is 64, not the 512 the reference tree's
# _pcd_buff[512] suggests. Measured: 1..64 answer, 65+ time out, and the
# timeout is not caused by anything we did beforehand, 0x02 alone after a bus
# reset does it too. The official host agrees, AmlLibusb.cpp:61 sends
# min(out_len, 64u) for READ_MEM. Round 4 never went above 64 so it never saw
# it. A bigger w_length makes the device memcpy() past the EP0 staging buffer,
# so this is a read-or-crash line, not a politeness limit.
MAX_RD = 64

# optimus_working() dispatches these by name. Anything not listed falls through
# to run_command(), so a denylist is the only thing between us and a flash.
DENY = ("flash", "erase", "format", "saveenv", "setenv", "write_raw_img",
        "erase_bootloader", "key", "burn_complete", "save_setting", "update",
        "reset", "poweroff", "simg2part", "download", "upload", "low_power",
        "disk_initial", "run", "bootm", "go", "booti")


def find():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        print("no 1b8e:c003 on the bus", file=sys.stderr)
        sys.exit(2)
    try:
        dev.is_kernel_driver_active(0)
        dev.detach_kernel_driver(0)
    except (usb.core.USBError, NotImplementedError, AttributeError):
        pass
    if dev.get_active_configuration() is None:
        dev.set_configuration()
    return dev


def identify(dev):
    d = dev.ctrl_transfer(RT_IN, REQ_IDENTIFY, 0, 0, 4, 2000)
    stage = d[2] * 256 + d[3] if len(d) == 4 else -1
    name = {0: "IPL/BL1", 8: "SPL/BL2", 16: "TPL/BL33-u-boot"}.get(stage, "?")
    print("raw     %s" % " ".join("%02x" % b for b in d))
    print("version %d.%d" % (d[0], d[1]))
    print("stage   %d (%s)" % (stage, name))
    # TPL is the only answer that means we are talking to U-Boot and not the ROM
    return 0 if stage == 16 else 1


def read_mem(dev, addr, length):
    if length > MAX_RD:
        sys.exit("length %d over the %d cap" % (length, MAX_RD))
    return dev.ctrl_transfer(RT_IN, REQ_READ_MEM,
                             (addr >> 16) & 0xFFFF, addr & 0xFFFF,
                             length, 5000)


def bulkcmd(dev, cmd, timeout=5000):
    """AM_REQ_BULKCMD. Runs one U-Boot command and returns the 512B reply.

    Framing is copied from the Amlogic host, not guessed:
    AmlLibusb.cpp:234 IOCTL_BULK_CMD_Handler sends bmRequestType 0x40,
    bRequest 0x34, wValue 0, wIndex 2, wLength 64, then AmlUsbBulkCmd reads
    512 bytes off the bulk IN endpoint. The device side is do_bulk_cmd(),
    usb_pcd.c:944: it calls optimus_working() and then bulk_cmd_reply(),
    which always ships exactly AM_BULK_REPLY_LEN on EP1 IN.

    wIndex 2 is not decoration, usb_pcd.c:547 uses it to set the reply cmd id
    so the host can be told "Continue:34" while a long command runs.
    """
    if len(cmd) >= BULKCMD_DATA:
        sys.exit("command does not fit the %d byte buffer" % BULKCMD_DATA)
    dev.ctrl_transfer(RT_OUT, REQ_BULKCMD, 0, 2,
                      cmd.encode() + b"\0" * (BULKCMD_DATA - len(cmd)), timeout)
    return bytes(dev.read(BULK_IN_EP, BULK_REPLY, BULK_TIMEOUT))


def upload_next(dev, timeout=5000):
    """AM_REQ_UPLOAD, one chunk. Returns the byte count the device is about to
    stream on bulk IN, 0 when the upload is done.

    AmlLibusb.cpp:210 IOCTL_READ_MEDIA_Handler is a control IN: wValue is the
    block size, wIndex the block count, wLength 16. The 16 bytes coming back
    are filled by optimus_buf_manager_get_command_data_for_upload_transfer
    (optimus_buffer_manager.c:307): [0-3] 0xefe8, [4-7] thisTransDataLen.
    wIndex is the "block count" the host computes but the device never reads
    it, usb_pcd.c:512 only stores w_length.

    That 16 byte answer is the trigger. do_vendor_in_complete(), usb_pcd.c:739,
    runs on the status stage of this very transfer and calls start_bulk_transfer.
    Nothing else arms the payload.
    """
    hdr = bytes(dev.ctrl_transfer(RT_IN, REQ_UPLOAD, 0x1000, 1,
                                  UPLOAD_CMDLEN, timeout))
    if len(hdr) < UPLOAD_CMDLEN or struct.unpack_from("<I", hdr, 0)[0] != UPLOAD_MAGIC:
        raise IOError("upload header %r is not 0xefe8" % hdr.hex(" "))
    return struct.unpack_from("<I", hdr, 4)[0]


def mread_mem(dev, addr, size):
    """The official mread mem, byte for byte. This is what "update mread mem"
    does: one bulkcmd to arm the read, then upload transfers until done.

        upload mem 0x20000000 normal 0x200

    optimus_parse_download_cmd (optimus_download.c:1072) parses the address
    into partBaseOffset, optimus_buf_manager_tplcmd_init records the total
    size in tplcmdTotalSz, and every chunk is copied out of RAM by
    optimus_dump_storage_data -> optimus_storage_read, OPTIMUS_MEDIA_TYPE_MEM,
    which is a plain memcpy from partBaseOffset + offset. No eMMC, no write
    back: nextWriteBackSlot stays 0 for an upload.

    Each bulk IN is at most OPTIMUS_DOWNLOAD_SLOT_SZ (64K), the last one
    whatever is left. Zero length means the device is finished.
    """
    reply = bulkcmd(dev, "upload mem 0x%x normal 0x%x" % (addr, size))
    text = reply.split(b"\0")[0].decode("ascii", "replace")
    if not text.startswith("success"):
        raise IOError("bulkcmd said %r, nothing was armed" % text)

    out = bytearray()
    transfers = 0
    while len(out) < size:
        want = upload_next(dev)
        if not want:
            break
        while want:
            chunk = dev.read(BULK_IN_EP, min(want, BULK_CHUNK), BULK_TIMEOUT)
            if not chunk:
                raise IOError("bulk IN gave up at %d of %d bytes" % (len(out), size))
            out += chunk
            want -= len(chunk)
        transfers += 1
    return bytes(out), transfers


def do_desc(dev):
    """Dump the real endpoints. The reference tree is a Xiaomi fork of GXL, it
    is evidence, not the build in front of us."""
    cfg = dev.get_active_configuration()
    for intf in cfg:
        print("if %d alt %d class 0x%02x/%02x/%02x"
              % (intf.bInterfaceNumber, intf.bAlternateSetting,
                 intf.bInterfaceClass, intf.bInterfaceSubClass,
                 intf.bInterfaceProtocol))
        for ep in intf:
            # endpoint_type() wants bmAttributes, not the endpoint address
            print("  ep 0x%02x %s %s mps %d"
                  % (ep.bEndpointAddress,
                     "IN " if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN else "OUT",
                     usb.util.endpoint_type(ep.bmAttributes),
                     ep.wMaxPacketSize))
    return 0


def hexdump(b, base):
    for i in range(0, len(b), 16):
        row = b[i:i + 16]
        txt = "".join(chr(c) if 32 <= c < 127 else "." for c in row)
        print("%08x  %-*s |%s|" % (base + i, 16 * 3, " ".join("%02x" % c for c in row), txt))


def do_scan(dev, start, end, pattern, step=MAX_RD):
    t0 = time.time()
    done = 0
    for base in range(start, end, step):
        chunk = read_mem(dev, base, min(step, end - base))
        off = chunk.find(pattern)
        if off >= 0:
            at = base + off
            print("HIT %r at 0x%08x" % (pattern, at))
            ctx = read_mem(dev, max(start, at - 32), MAX_RD)
            hexdump(ctx, max(start, at - 32))
            return 0
        done += len(chunk)
        if done % (1 << 20) < step:
            rate = done / max(time.time() - t0, 1e-6) / 1024.0
            print("  ...%u MiB, %.0f KiB/s" % (done >> 20, rate), file=sys.stderr)
    print("no %r in 0x%08x..0x%08x" % (pattern, start, end))
    return 1


def do_tpl(dev, cmd):
    head = cmd.split()[0]
    if head in DENY:
        sys.exit("refused, %r is denylisted" % head)
    dev.ctrl_transfer(RT_OUT, REQ_TPL_CMD, 0, 1, cmd.encode() + b"\0", 5000)
    reply = bytes(dev.ctrl_transfer(RT_IN, REQ_TPL_STAT, 0, 0, 512, 5000))
    print(reply.split(b"\0")[0].decode("ascii", "replace"))


def require_write(flag):
    if not flag:
        sys.exit("refused, write verbs need --enable-write")


def in_ok(addr, size, ok_ranges):
    if not ok_ranges:
        sys.exit("refused, --enable-write also needs --write-ok lo,hi")
    for lo, hi in ok_ranges:
        if lo <= addr and addr + size <= hi:
            return
    sys.exit("refused, 0x%x..0x%x outside --write-ok" % (addr, addr + size))


def do_fill(dev, pairs, flag, ok_ranges):
    require_write(flag)
    for a, _ in pairs:
        in_ok(a, 4, ok_ranges)
    buf = b"".join((a.to_bytes(4, "little") + v.to_bytes(4, "little")) for a, v in pairs)
    dev.ctrl_transfer(RT_OUT, 0x03, 0, 0, buf, 5000)
    print("wrote %d word(s)" % len(pairs))


def do_poke(dev, addr, data, flag, ok_ranges):
    require_write(flag)
    in_ok(addr, len(data), ok_ranges)
    dev.ctrl_transfer(RT_OUT, 0x01, (addr >> 16) & 0xFFFF, addr & 0xFFFF, data, 5000)
    print("wrote %d byte(s) at 0x%08x" % (len(data), addr))


def do_probe(dev, addrs):
    """identify + a batch of reads in one process, so the burning window is not
    spent re-opening the device between shell calls."""
    identify(dev)
    for a in addrs:
        addr = int(a, 0)
        print("\n0x%08x:" % addr)
        try:
            b = bytes(read_mem(dev, addr, 64))
        except usb.core.USBError as e:
            print("  USBError %s" % e)
            continue
        hexdump(b, addr)


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    verb = a[0]
    write = "--enable-write" in a
    a = [x for x in a if x != "--enable-write"]

    if "--write-ok" in a:
        i = a.index("--write-ok")
        lo, hi = (int(x, 0) for x in a[i + 1].split(","))
        ok = [(lo, hi)]
        del a[i:i + 3]
    else:
        ok = []

    if verb == "identify":
        return identify(find())
    dev = find()
    if verb == "desc":
        return do_desc(dev)
    if verb == "bulkcmd":
        cmd = " ".join(a[1:])
        argv = cmd.split()
        # "upload mem <addr> normal <size>" is the read half of the burning
        # protocol: isUpload keeps nextWriteBackSlot at 0, so nothing is ever
        # written back (optimus_buffer_manager.c:149). "download" stays denied.
        if argv[0] in DENY and not (argv[0] == "upload" and len(argv) > 1
                                   and argv[1] == "mem"):
            sys.exit("refused, %r is denylisted" % argv[0])
        print(bulkcmd(dev, cmd).split(b"\0")[0].decode("ascii", "replace"))
    elif verb == "mread":
        addr = int(a[1], 0)
        length = int(a[2], 0)
        t0 = time.time()
        b, n = mread_mem(dev, addr, length)
        sys.stderr.write("0x%08x %d bytes in %d transfers, %.3fs sha256=%s\n"
                         % (addr, len(b), n, time.time() - t0,
                            hashlib.sha256(b).hexdigest()))
        sys.stdout.buffer.write(b)
    elif verb == "probe":
        do_probe(dev, a[1:])
    elif verb == "read":
        addr = int(a[1], 0)
        length = int(a[2], 0) if len(a) > 2 else MAX_RD
        b = bytes(read_mem(dev, addr, length))
        if len(a) > 3:
            hexdump(b, addr)
        else:
            sys.stdout.buffer.write(b)
    elif verb == "scan":
        return do_scan(dev, int(a[1], 0), int(a[2], 0), a[3].encode())
    elif verb == "tpl":
        do_tpl(dev, " ".join(a[1:]))
    elif verb == "fill":
        pairs = [(int(a[i], 0), int(a[i + 1], 0)) for i in range(1, len(a), 2)]
        do_fill(dev, pairs, write, ok)
    elif verb == "poke":
        do_poke(dev, int(a[1], 0), bytes.fromhex(a[2]), write, ok)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except usb.core.USBError as e:
        print("USBError: %s" % e, file=sys.stderr)
        sys.exit(3)
