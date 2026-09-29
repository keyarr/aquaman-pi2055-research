#!/usr/bin/env python3
"""bl33_read.py - one burning window: probe 0x01000000, then dump 16 MiB.

Read-only, same ground as mread_test.py. `upload mem <addr> normal <size>` is
the read half of the burning protocol, nothing is written back.

Everything runs in ONE process on purpose. The window is ~77s
(reports/optimus-ram-read.md 5) and re-opening the device per command burns it
on process startup and on sudo. If any step fails, the session stops and logs
it: an armed-but-unread bulk IN wedges the gadget until a libusb reset, so a
broken run ends the session instead of producing a second round of timeout
noise.

The ladder stops at the first failure and never adapts: 0x01000000 mapped or it
is not, and guessing another low address is how round 6 read the wrong 512 MiB.

  tools/bl33_read.py reports/round8-bl33-read
"""
import hashlib
import os
import sys
import time

import usb.core

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from optimus import MAX_RD, find, hexdump, identify, mread_mem, read_mem

# CONFIG_SYS_TEXT_BASE for gxl, derived from the khadas tree, not measured on
# the aquaman. See reports/bl33-offline-round7.md 3.2.
BASE = 0x01000000
LADDER = [0x200, 0x1000, 0x10000]
DUMP = 0x01000000


def verify_02(dev, addr, size, got):
    """Same range again through AM_REQ_READ_MEM, 64 bytes per control
    transfer, compared byte for byte. This is the slow path, it is the point."""
    t0 = time.time()
    pos = 0
    reads = 0
    while pos < size:
        n = min(MAX_RD, size - pos)
        ref = bytes(read_mem(dev, addr + pos, n))
        if ref != got[pos:pos + n]:
            off = next(i for i in range(n) if ref[i] != got[pos + i])
            return False, "mismatch at 0x%08x (mread %02x, 0x02 %02x)" % (
                addr + pos + off, got[pos + off], ref[off]), reads
        pos += n
        reads += 1
    return True, "%.3fs, %d control reads of %dB" % (time.time() - t0, reads, MAX_RD), reads


def alive(dev):
    try:
        d = dev.ctrl_transfer(0xC0, 0x20, 0, 0, 4, 2000)
        return "alive, identify=%s" % " ".join("%02x" % b for b in d)
    except usb.core.USBError as e:
        return "GADGET DEAD: %s" % e


def recover():
    d = usb.core.find(idVendor=0x1B8E, idProduct=0xC003)
    if d is None:
        return None
    try:
        d.reset()
    except usb.core.USBError:
        pass
    time.sleep(0.8)
    return find()


def ladder(dev, size, outdir, results):
    t0 = time.time()
    try:
        got, transfers = mread_mem(dev, BASE, size)
    except (usb.core.USBError, IOError) as e:
        print("  FAIL %s: %s" % (type(e).__name__, e), flush=True)
        results.append((size, "FAIL", "transfer failed"))
        return False
    dt = time.time() - t0
    print("  got %d bytes in %d transfers, %.3fs (%.1f KiB/s)"
          % (len(got), transfers, dt, len(got) / dt / 1024.0), flush=True)
    print("  sha256 %s" % hashlib.sha256(got).hexdigest(), flush=True)
    if len(got) != size:
        print("  LENGTH MISMATCH, want %d" % size, flush=True)
        results.append((size, "FAIL", "wrong length"))
        return False

    path = "%s/mread_%08x_%06x.bin" % (outdir, BASE, size)
    with open(path, "wb") as f:
        f.write(got)
    print("  wrote %s" % path, flush=True)

    ok, why, reads = verify_02(dev, BASE, size, got)
    print("  0x02 cross-check: %s (%s)" % ("MATCH" if ok else "FAIL", why), flush=True)
    if not ok:
        results.append((size, "FAIL", why))
        return False
    print("  gadget: %s" % alive(dev), flush=True)
    results.append((size, "OK", "%d transfers, %d reads, %.1f KiB/s"
                    % (transfers, reads, len(got) / dt / 1024.0)))
    return True


def dump(dev, outdir):
    """16 MiB at 0x01000000, written to disk before anything else touches it.

    Round 6 streamed 64 MiB into a hash and dropped the bytes. Every number
    this prints comes from the file that is already on disk, not from the
    buffer that is about to be freed."""
    t0 = time.time()
    try:
        got, transfers = mread_mem(dev, BASE, DUMP)
    except (usb.core.USBError, IOError) as e:
        print("  FAIL %s: %s" % (type(e).__name__, e), flush=True)
        return False
    dt = time.time() - t0

    path = "%s/mread_%08x_%08x.bin" % (outdir, BASE, DUMP)
    with open(path, "wb") as f:
        f.write(got)
    print("  wrote %s" % path, flush=True)

    # re-read from disk, so the sha below is the file, not the buffer
    onfile = open(path, "rb").read()
    print("  address      0x%08x" % BASE, flush=True)
    print("  size asked   0x%08x (%d)" % (DUMP, DUMP), flush=True)
    print("  size on file %d" % len(onfile), flush=True)
    print("  chunks       %d upload transfers of 64 KiB" % transfers, flush=True)
    print("  time         %.3fs" % dt, flush=True)
    print("  throughput   %.2f MiB/s" % (len(onfile) / dt / (1 << 20)), flush=True)
    print("  sha256       %s" % hashlib.sha256(onfile).hexdigest(), flush=True)
    if len(onfile) != DUMP:
        print("  SHORT DUMP, not a candidate for anything", flush=True)
        return False

    ok, why, _ = verify_02(dev, BASE, MAX_RD, onfile)
    print("  0x02 cross-check of the first %d bytes: %s (%s)"
          % (MAX_RD, "MATCH" if ok else "FAIL", why), flush=True)
    if not ok:
        return False
    print("  gadget: %s" % alive(dev), flush=True)
    return True


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "reports/round8-bl33-read"
    os.makedirs(outdir, exist_ok=True)

    dev = recover()
    if dev is None:
        print("no 1b8e:c003 on the bus")
        return 2
    identify(dev)
    print("gadget: %s" % alive(dev), flush=True)

    print("\n=== 0x02 read of 0x%08x, %d bytes ===" % (BASE, MAX_RD), flush=True)
    try:
        head = bytes(read_mem(dev, BASE, MAX_RD))
    except (usb.core.USBError, IOError) as e:
        print("  FAIL %s: %s" % (type(e).__name__, e), flush=True)
        print("\n0x%08x is not readable through 0x02. Logged, no adaptive scan,"
              " no other low address tried this session." % BASE)
        return 3
    with open("%s/read02_%08x_%d.bin" % (outdir, BASE, MAX_RD), "wb") as f:
        f.write(head)
    print("  sha256 %s" % hashlib.sha256(head).hexdigest(), flush=True)
    hexdump(head, BASE)

    results = []
    for size in LADDER:
        print("\n=== mread mem 0x%08x size=0x%x ===" % (BASE, size), flush=True)
        if not ladder(dev, size, outdir, results):
            print("\nLADDER STOPPED after the first failure. 0x%08x readable but"
                  " not the shape we wanted, or not mapped at this size." % BASE)
            break
    else:
        print("\n=== dump 0x%08x size=0x%08x ===" % (BASE, DUMP), flush=True)
        dump(dev, outdir)

    print("\n=== summary ===", flush=True)
    print("size     status  detail", flush=True)
    for r in results:
        print("0x%-7x %-6s %s" % r, flush=True)
    return 0 if results and all(r[1] == "OK" for r in results) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except usb.core.USBError as e:
        print("USBError: errno=%s %s" % (e.errno, e), file=sys.stderr)
        sys.exit(3)
