#!/usr/bin/env python3
"""mread_test.py - the official mread mem, 0x34 + 0x33, and the proof.

Read-only. `upload mem <addr> normal <size>` is the read half of the burning
protocol: isUpload keeps nextWriteBackSlot at 0, so nothing is written back
(optimus_buffer_manager.c:149). No eMMC, no env, no flash, no 0x05, no 0x12.

The ladder stops at the first failure. Leaving a bulk IN transfer armed but
unread wedges the gadget until a libusb reset, so a broken run ends the
session instead of producing a second round of timeout noise.
"""
import hashlib
import sys
import time

import usb.core

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from optimus import MAX_RD, do_desc, find, identify, mread_mem, read_mem

# 0x200 first: 0x02 already knows this range, so the comparison is against
# something proven. Then 64K, the slot size, then 1 MiB.
LADDER = [
    (0x20000000, 0x200),
    (0x20000000, 0x1000),
    (0x20000000, 0x10000),
    (0x20000000, 0x100000),
]


def verify_with_02(dev, addr, size, got, budget=600.0):
    """Re-read the same range with AM_REQ_READ_MEM in control reads and compare
    byte for byte. This is the slow path, it is the point. 64B per transfer, so
    1 MiB is 16384 of them."""
    t0 = time.time()
    pos = 0
    reads = 0
    while pos < size:
        if time.time() - t0 > budget:
            return False, "verify budget blown at +0x%x" % pos, reads
        n = min(MAX_RD, size - pos)
        ref = bytes(read_mem(dev, addr + pos, n))
        if ref != got[pos:pos + n]:
            off = next(i for i in range(n) if ref[i] != got[pos + i])
            return False, "mismatch at 0x%08x (got %02x want %02x)" % (
                addr + pos + off, got[pos + off], ref[off]), reads
        pos += n
        reads += 1
    return True, "%.1fs, %d control reads of 64B" % (time.time() - t0, reads), reads


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


def step(dev, addr, size, outdir):
    print("\n=== mread mem 0x%08x size=0x%x ===" % (addr, size), flush=True)
    # 0x02 answers at most 64 bytes on this build, so the cross-check of 1 MiB
    # is 16384 control transfers. It runs, it just takes a while.
    t0 = time.time()
    try:
        got, transfers = mread_mem(dev, addr, size)
    except (usb.core.USBError, IOError) as e:
        print("  FAIL %s: %s" % (type(e).__name__, e), flush=True)
        return False, "transfer failed"
    dt = time.time() - t0

    print("  got %d bytes in %d transfers, %.3fs (%.1f KiB/s)"
          % (len(got), transfers, dt, len(got) / dt / 1024.0), flush=True)
    print("  sha256 %s" % hashlib.sha256(got).hexdigest(), flush=True)
    if len(got) != size:
        print("  LENGTH MISMATCH, want %d" % size, flush=True)
        return False, "wrong length"

    path = "%s/mread_%08x_%06x.bin" % (outdir, addr, size)
    with open(path, "wb") as f:
        f.write(got)
    print("  wrote %s" % path, flush=True)

    ok, why, reads = verify_with_02(dev, addr, size, got)
    print("  0x02 cross-check: %s (%s)" % ("MATCH" if ok else "FAIL", why), flush=True)
    if not ok:
        return False, why
    print("  gadget: %s" % alive(dev), flush=True)
    return True, "%d transfers, %d reads, %.1f KiB/s" % (transfers, reads,
                                                         len(got) / dt / 1024.0)


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "reports/round6-mread"
    dev = recover()
    if dev is None:
        print("no 1b8e:c003")
        return 2
    do_desc(dev)
    identify(dev)

    results = []
    for addr, size in LADDER:
        ok, why = step(dev, addr, size, outdir)
        results.append((addr, size, "OK" if ok else "FAIL", why))
        if not ok:
            print("\nLADDER STOPPED after the first failure.", flush=True)
            break

    print("\n=== summary ===", flush=True)
    print("addr      size     status  detail", flush=True)
    for r in results:
        print("0x%08x 0x%-7x %-6s %s" % r, flush=True)
    return 0 if all(r[2] == "OK" for r in results) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except usb.core.USBError as e:
        print("USBError: errno=%s %s" % (e.errno, e), file=sys.stderr)
        sys.exit(3)
