#!/usr/bin/env python3
"""round61: read-only keyman blob collection over Optimus stage 16.

For every DTS key name, issue `keyman read <name> <addr>` (BL33 writes the
secure-reported blob into host-chosen RAM), then MREAD the same window before
and after. The changed prefix is the blob: its length is secure-controlled and
never returned over USB, so it is recovered by differential read instead of
guessed.

No write verbs: no keyman write, flash, saveenv, efuse, BootROM, RUN_IN_ADDR,
MODIFY. Only identify, bulkcmd and mread. Usage inside one burning window:

    OPTIMUS_PY=tools/round61_keyman_collect.py \
      OPTIMUS_OUT=/tmp/round61-session.log \
      tools/optimus_enter.sh <start> <end>

Example: tools/optimus_enter.sh 0 6
"""
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import optimus

NAMES = [
    "sn1", "sn2", "hdcp", "secure_boot_set", "mn1", "mn2", "hdcp2_rx",
    "mac_bt", "mac", "mac_wifi", "widevinekeybox", "hdcp22_fw_private",
    "PlayReadykeybox25", "bt_rc_mac", "prpubkeybox", "prprivkeybox",
    "attestationkeybox", "netflix_mgkid", "region",
]

SCRATCH = 0x20000000
STRIDE = 0x1000
WINDOW = 0x400
BLOBS = "/tmp/blobs"


def bulk(dev, cmd):
    return optimus.bulkcmd(dev, cmd, timeout=15000).split(b"\0")[0].decode("ascii", "replace").strip()


def oracle(dev):
    r = {}
    for c in ("false", "true", "test 1 = 2", "test 1 = 1"):
        r[c] = bulk(dev, c)
    ok = r["false"].startswith("failed:") and r["test 1 = 2"].startswith("failed:") \
        and r["true"].startswith("success") and r["test 1 = 1"].startswith("success")
    print("oracle %s %s" % ("PASS" if ok else "FAIL", r), flush=True)
    return ok


def changed_prefix(pre, post):
    n = min(len(pre), len(post))
    i = n - 1
    while i >= 0 and pre[i] == post[i]:
        i -= 1
    return i + 1


def main():
    a = sys.argv[1:]
    lo = int(a[0], 0) if len(a) > 0 else 0
    hi = int(a[1], 0) if len(a) > 1 else len(NAMES)
    hi = min(hi, len(NAMES))

    os.makedirs(BLOBS, exist_ok=True)
    dev = optimus.find()
    if optimus.identify(dev) != 0:
        sys.exit("ABORT: not stage 16")

    t0 = time.time()
    if not oracle(dev):
        sys.exit("ABORT: baseline oracle failed")

    for idx in range(lo, hi):
        name = NAMES[idx]
        dest = SCRATCH + idx * STRIDE
        pre, _ = optimus.mread_mem(dev, dest, WINDOW)
        pre = bytes(pre)
        rc = bulk(dev, "keyman read %s 0x%x" % (name, dest))
        post, _ = optimus.mread_mem(dev, dest, WINDOW)
        post = bytes(post)
        n = changed_prefix(pre, post)
        blob = post[:n]
        path = os.path.join(BLOBS, name + ".bin")
        with open(path, "wb") as f:
            f.write(blob)
        print("[%02d] %-20s rc=%-12r dest=0x%x len=%d rc_ok=%s sha256=%s t=%.2fs"
              % (idx, name, rc, dest, n, rc == "success",
                 hashlib.sha256(blob).hexdigest(), time.time() - t0), flush=True)
        print("     head=%s" % blob[:32].hex(" "), flush=True)

    ok = oracle(dev)
    manifest = {
        "names": NAMES[lo:hi],
        "scratch_base": SCRATCH,
        "stride": STRIDE,
        "window": WINDOW,
        "oracle_after": ok,
        "elapsed_s": time.time() - t0,
    }
    with open(os.path.join(BLOBS, "manifest-%02d-%02d.json" % (lo, hi)), "w") as f:
        json.dump(manifest, f, indent=2)
    print("done oracle=%s elapsed=%.2fs" % (ok, time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
