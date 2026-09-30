#!/usr/bin/env python3
"""why_die.py - is a failed 0x02 read poisoning the usb handle or the gadget?

Three runs on 2026-09-30 all died the same way and none of them agreed with the
obvious explanation. GP_CFG7/GP_CFG0/SD_CFG15 at 0xc810025c/40/3c read fine,
then something fails, then **every** later read in the same session returns an
error, including addresses that had just read fine. so either

  (a) one faulting address poisons the pyusb/libusb handle and the fix is to
      re-find the device per read, or
  (b) the fault kills the optimus gadget on the stick and no amount of re-opening
      helps, which would mean every 0x02 read has to be planned so it never
      touches a bad address.

This distinguishes them, and it is the difference between a wide sweep being
possible at all and it having to stay a three-register probe. Fresh handle per
read, alternating a known-good address with a candidate, so the ordering shows
which of the two it is.

    OPTIMUS_PY=tools/why_die.py tools/optimus_enter.sh 0xc8100200 0xc810025c ...
"""
import struct
import sys
import time

import usb.core

import optimus


def read4(dev, addr, timeout=250):
    try:
        b = bytes(dev.ctrl_transfer(optimus.RT_IN, optimus.REQ_READ_MEM,
                                    (addr >> 16) & 0xFFFF, addr & 0xFFFF,
                                    4, timeout))
        return struct.unpack("<I", b)[0] if len(b) == 4 else None
    except (usb.core.USBError, OSError) as e:
        return ("ERR", getattr(e, "errno", None))


def one(addr, timeout):
    """fresh handle, one read. returns (value, error)."""
    dev = optimus.find()
    if dev is None:
        return ("GONE", None)
    try:
        if optimus.identify(dev) != 0:
            return ("NOTSTAGE16", None)
        v = read4(dev, addr, timeout)
        usb.util.dispose_resources(dev)
        return v
    except (usb.core.USBError, OSError) as e:
        return ("ERR", getattr(e, "errno", None))


def main():
    addrs = [int(a, 0) for a in sys.argv[1:]] or [0xC8100200, 0xC810025C]
    if optimus.identify(optimus.find() or object()) != 0:
        pass  # first handle is consumed by find() inside one()
    print("\n== alternating fresh-handle reads ==", flush=True)
    for rnd in range(3):
        for a in addrs:
            t = time.time()
            v, e = one(a, 250)
            dt = (time.time() - t) * 1000
            if isinstance(v, int):
                print("  round %d  0x%08x  0x%08x   %5.1f ms"
                      % (rnd, a, v, dt), flush=True)
            else:
                print("  round %d  0x%08x  %-9s %s  %5.1f ms"
                      % (rnd, a, v, e, dt), flush=True)
    print("\n  if the good address keeps reading after a bad one, it is the")
    print("  handle (a) and a sweep is possible with a re-find per read.")
    print("  if everything goes ERR after the first bad one, it is the")
    print("  gadget (b) and reads must be planned to never touch a bad address.")


if __name__ == "__main__":
    main()
