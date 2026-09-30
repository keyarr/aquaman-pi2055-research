#!/usr/bin/env python3
"""reloc_read.py - read one arbitrary DRAM band through optimus v2, read-only.

Round 12 generalization of bl33_read.py. same discipline (one process, ladder
that never adapts, save to disk before anything else, 0x02 cross-check on every
step), but the base and size come from argv so the round 11 derived band -- the
relocated BL33 near the top of usable RAM -- can be read without touching the
round 8 client.

  tools/reloc_read.py OUTDIR BASE SIZE [PROBE,PROBE,...]

  tools/reloc_read.py reports/round12-reloc 0x37800000 0x800000
  tools/reloc_read.py /tmp/x 0x37c00000 0x200 0x37d90000,0x37e00000

`upload mem` is the read half of the burning protocol: isUpload keeps
nextWriteBackSlot at 0, nothing is written back. 0x02 is capped at 64 bytes and
an armed-but-unread bulk IN wedges the gadget until a libusb reset, so a broken
step ends the session instead of producing a second round of timeout noise.
"""
import hashlib
import os
import sys
import time

import usb.core

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from optimus import MAX_RD, find, hexdump, identify, mread_mem, read_mem  # noqa


def alive(dev):
    try:
        d = dev.ctrl_transfer(0xC0, 0x20, 0, 0, 4, 2000)
        return "alive, identify=%s" % " ".join("%02x" % b for b in d)
    except usb.core.USBError as e:
        return "GADGET DEAD: %s" % e


def verify_02(dev, addr, size, got, budget=0x1000):
    """Same range again through AM_REQ_READ_MEM, 64 bytes per control transfer.

    budget caps the slow path: 64 bytes per transfer means a full 8 MiB
    cross-check is 131072 control transfers, which is minutes. the first
    `budget` bytes are enough to prove the mread path agrees with 0x02.
    """
    size = min(size, budget)
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


def ladder(dev, base, size, outdir, results):
    t0 = time.time()
    try:
        got, transfers = mread_mem(dev, base, size)
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

    path = "%s/mread_%08x_%06x.bin" % (outdir, base, size)
    with open(path, "wb") as f:
        f.write(got)
    print("  wrote %s" % path, flush=True)

    ok, why, reads = verify_02(dev, base, size, got)
    print("  0x02 cross-check: %s (%s)" % ("MATCH" if ok else "FAIL", why), flush=True)
    if not ok:
        results.append((size, "FAIL", why))
        return False
    print("  gadget: %s" % alive(dev), flush=True)
    results.append((size, "OK", "%d transfers, %d reads, %.1f KiB/s"
                    % (transfers, reads, len(got) / dt / 1024.0)))
    return True


def dump(dev, base, size, outdir):
    t0 = time.time()
    try:
        got, transfers = mread_mem(dev, base, size)
    except (usb.core.USBError, IOError) as e:
        print("  FAIL %s: %s" % (type(e).__name__, e), flush=True)
        return False
    dt = time.time() - t0

    path = "%s/mread_%08x_%08x.bin" % (outdir, base, size)
    with open(path, "wb") as f:
        f.write(got)

    onfile = open(path, "rb").read()          # hash the file, not the buffer
    print("  address      0x%08x" % base, flush=True)
    print("  size asked   0x%08x (%d)" % (size, size), flush=True)
    print("  size on file %d" % len(onfile), flush=True)
    print("  chunks       %d upload transfers of 64 KiB" % transfers, flush=True)
    print("  time         %.3fs" % dt, flush=True)
    print("  throughput   %.2f MiB/s" % (len(onfile) / dt / (1 << 20)), flush=True)
    print("  sha256       %s" % hashlib.sha256(onfile).hexdigest(), flush=True)
    if len(onfile) != size:
        print("  SHORT DUMP", flush=True)
        return False
    ok, why, _ = verify_02(dev, base, MAX_RD, onfile)
    print("  0x02 cross-check of the first %d bytes: %s (%s)"
          % (MAX_RD, "MATCH" if ok else "FAIL", why), flush=True)
    print("  gadget: %s" % alive(dev), flush=True)
    return True


def probe(dev, addrs):
    for a in addrs:
        print("\n0x%08x:" % a, flush=True)
        try:
            b = bytes(read_mem(dev, a, MAX_RD))
        except usb.core.USBError as e:
            print("  USBError %s" % e, flush=True)
            continue
        hexdump(b, a)


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    outdir, base, size = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0)
    probes = [int(x, 0) for x in sys.argv[4].split(",")] if len(sys.argv) > 4 else []
    os.makedirs(outdir, exist_ok=True)

    dev = find()
    identify(dev)
    print("gadget: %s" % alive(dev), flush=True)

    print("\n=== 0x02 read of 0x%08x, %d bytes ===" % (base, MAX_RD), flush=True)
    try:
        head = bytes(read_mem(dev, base, MAX_RD))
    except usb.core.USBError as e:
        print("  FAIL %s: 0x%08x is not readable through 0x02. logged, no adaptive"
              " scan, no other address tried." % (e, base), flush=True)
        return 3
    with open("%s/read02_%08x_%d.bin" % (outdir, base, MAX_RD), "wb") as f:
        f.write(head)
    print("  sha256 %s" % hashlib.sha256(head).hexdigest(), flush=True)
    hexdump(head, base)

    if probes:
        print("\n=== extra 64B probes ===", flush=True)
        probe(dev, probes)

    results = []
    for s in [0x200, 0x1000, 0x10000]:
        if s > size:
            continue
        print("\n=== mread 0x%08x size=0x%x ===" % (base, s), flush=True)
        if not ladder(dev, base, s, outdir, results):
            print("\nLADDER STOPPED after the first failure.", flush=True)
            return 1

    if size > 0x10000:
        print("\n=== dump 0x%08x size=0x%08x ===" % (base, size), flush=True)
        if not dump(dev, base, size, outdir):
            return 1

    print("\n=== summary ===", flush=True)
    for r in results:
        print("0x%-7x %-6s %s" % r, flush=True)
    return 0 if results and all(r[1] == "OK" for r in results) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except usb.core.USBError as e:
        print("USBError: errno=%s %s" % (e.errno, e), file=sys.stderr)
        sys.exit(3)
