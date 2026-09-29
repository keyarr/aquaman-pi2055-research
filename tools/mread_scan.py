#!/usr/bin/env python3
"""mread_scan.py - hunt for BL33 in RAM with the 0x34 + 0x33 mread path.

Read-only, same as mread_test.py. 0x12 is gone, 0x33 + 0x34 replaced it, so a
scan is now 13 MiB/s instead of 64 bytes per control transfer.

  python3 tools/mread_scan.py 0x20000000 0x21000000
  python3 tools/mread_scan.py 0x20000000 0x40000000 --save 0x20000000:0x1000000

Markers are split in two on purpose. MARKERS only exist inside a U-Boot or
Optimus image, a single hit there is a real lead. NOISE hits the Android heap
constantly ("ddr" is a substring of haveOnlyLoopbackAddresses, "log" of a
thousand java symbols) and round 6 read 210 of them and called it a scan. Noise
is counted and capped, never dumped as a list of addresses.
"""
import argparse
import hashlib
import os
import sys
import time

import usb.core

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from optimus import find, identify, mread_mem

MARKERS = [
    b"U-Boot",
    b"u-boot",
    b"2015.01",
    b"g7ac5df7677",
    b"aml log : Sig Check",
    b"aml_sec_boot_check",
    b"Optimus",
    b"usb_pcd",
    b"usb_burning",
    b"set_usb_boot",
    b"do_bootm",
    b"gd->",
    b"optimus_working",
    b"optimus_buf_manager",
    b"loadaddr=",
    b"dtb_mem_addr=",
    b"boot_delay",
    # cmd_tbl names are NUL terminated, and that \0 is what kills the round 6
    # false positives: ro.bootmode and a base64 "BL2E3Tw" both matched.
    b"bootm\0",
    b"setenv\0",
    b"fastboot\0",
    b"bl33\0",
    b"BL33\0",
    b"BL2\0",
    b"Amlogic",
]

# substring traps, these say nothing on their own
NOISE = [b"ddr", b"aml_", b"boot", b"log"]


def scan(dev, lo, hi, block=0x1000000, quiet=False):
    hits = {}
    t0 = time.time()
    done = 0
    for base in range(lo, hi, block):
        n = min(block, hi - base)
        try:
            got, _ = mread_mem(dev, base, n)
        except Exception as e:
            # An unmapped address drops the stick off the bus entirely, it does
            # not just wedge the gadget, so there is nothing to recover here.
            # 0x0 and the BootROM/ATF window below the DDR are not mapped in
            # TPL, never point this at anything under 0x20000000.
            print("  0x%08x FAILED %s, giving up (unmapped range?)" % (base, e),
                  flush=True)
            return hits, done, time.time() - t0
        for p in MARKERS + NOISE:
            off = 0
            while True:
                i = got.find(p, off)
                if i < 0:
                    break
                hits.setdefault(p, []).append(base + i)
                off = i + 1
        done += len(got)
        if not quiet and done % (16 << 20) < block:
            print("  ...%u MiB, %.1f MiB/s"
                  % (done >> 20, done / max(time.time() - t0, 1e-9) / (1 << 20)),
                  flush=True)
    return hits, done, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lo")
    ap.add_argument("hi")
    ap.add_argument("--block", default="0x1000000")
    ap.add_argument("--save", help="ADDR:SIZE, dump that range to a file")
    args = ap.parse_args()
    lo, hi = int(args.lo, 0), int(args.hi, 0)

    dev = usb.core.find(idVendor=0x1B8E, idProduct=0xC003)
    if dev is None:
        print("no 1b8e:c003")
        return 2
    try:
        dev.reset()
    except usb.core.USBError:
        pass
    time.sleep(0.8)
    dev = find()
    identify(dev)

    if args.save:
        at, sz = args.save.split(":")
        got, n = mread_mem(dev, int(at, 0), int(sz, 0))
        path = "reports/scan_%08x_%06x.bin" % (int(at, 0), int(sz, 0))
        os.makedirs("reports", exist_ok=True)
        open(path, "wb").write(got)
        print("saved %d bytes in %d transfers to %s sha256=%s"
              % (len(got), n, path, hashlib.sha256(got).hexdigest()))
        return 0

    print("scanning 0x%08x..0x%08x, %d MiB" % (lo, hi, (hi - lo) >> 20), flush=True)
    hits, done, dt = scan(dev, lo, hi, int(args.block, 0))
    print("\n%u MiB in %.1fs (%.1f MiB/s)" % (done >> 20, dt, (done >> 20) / dt))
    for p in MARKERS:
        if p in hits:
            addrs = hits[p]
            print("%-20s %5d hits  %s"
                  % (p.decode(), len(addrs),
                     " ".join("0x%08x" % a for a in addrs[:12])))
    for p in NOISE:
        if p in hits:
            print("%-20s %5d hits  (noise, first: %s)"
                  % (p.decode(), len(hits[p]),
                     " ".join("0x%08x" % a for a in hits[p][:4])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
