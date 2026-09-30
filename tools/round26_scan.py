#!/usr/bin/env python3
"""round26 secmon scan: read-only mread sweep with per-chunk files + resume.

Only uses the sanctioned primitives (bulkcmd 0x34 + upload 0x33 via
optimus.mread_mem). No writes, no SMC, no 0x05, no bootm.

  python3 tools/round26_scan.py 0x05000000 0x05300000 dumps/

Each chunk is one mread of 0x10000 (64K). Files:
  dumps/chunk_05000000.bin ... one per chunk base.
On a gadget fault the device drops off USB; the script stops at the exact
failing base and exits nonzero. Re-run with a new lo to resume past the hole
after re-entering Optimus (fastboot oem update 5000, sanctioned entry only).
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from optimus import find, identify, mread_mem

CHUNK = 0x10000


def main():
    lo, hi, outdir = int(sys.argv[1], 0), int(sys.argv[2], 0), sys.argv[3]
    os.makedirs(outdir, exist_ok=True)
    dev = find()
    identify(dev)
    base = lo
    while base < hi:
        n = min(CHUNK, hi - base)
        path = os.path.join(outdir, "chunk_%08x.bin" % base)
        if os.path.exists(path) and os.path.getsize(path) == n:
            print("0x%08x SKIP exists" % base, flush=True)
            base += n
            continue
        try:
            got, transfers = mread_mem(dev, base, n)
        except Exception as e:
            print("0x%08x FAIL after %d done (%r)" % (base, base - lo, e), flush=True)
            return 3
        if len(got) != n:
            print("0x%08x SHORT %d/%d" % (base, len(got), n), flush=True)
            return 4
        open(path, "wb").write(got)
        print("0x%08x OK %dB %d transfers sha256=%s" % (
            base, len(got), transfers, hashlib.sha256(got).hexdigest()), flush=True)
        base += n
    print("done 0x%08x..0x%08x" % (lo, hi))
    return 0


if __name__ == "__main__":
    sys.exit(main())
