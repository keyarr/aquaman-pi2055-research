#!/usr/bin/env python3
"""rti_probe.py - E1 from round36: where does `set_usb_boot 2` actually write?

Round 36 reconstructed the armed state as `AO_RTI_STATUS_REG3` (0xc810001c):
[11:8] is what BL31's own string literal calls the "usb flag", and [15:12] is
what BL2 compares against 2 to enter its USB branch. Both halves of that are
static inference, because the bl31 handler body sits in the 0x05100000 blob
that no fip/*/bl31.* file contains. The prediction is falsifiable from inside
BL33 with the read primitive that already works, so this measures it.

Same shape as flagtest.py, and for the same reason it has to be one process in
one burning window: the only read path is AM_REQ_READ_MEM 0x02 inside the optimus
gadget, and re-entering optimus means `fastboot oem update 5000`, which runs
`aml_burn_check_is_ready_for_burn` -> `is_tpl_loaded_from_usb()` and would clear
a set flag before we ever got to look at it.

Three things learned on the device, all kept here because they change the shape
of the tool:

  - a 64-byte read of 0xc8100000 returns I/O error. flagtest.py and round 26
    only ever read 4 bytes. this walks word by word.
  - **one faulting 0x02 read kills the stick's USB endpoint, not just the host
    handle.** 0xc8100200 and 0xc8100000 both return errno 5 after ~160 ms, and a
    fresh libusb_open right after gets ENODEV, so the gadget is gone rather than
    stalled. GP_CFG7/GP_CFG0/SD_CFG15 at 0xc810025c/40/3c read fine, so the
    RTI_STATUS block at 0xc8100000 and SD_CFG0..7 at 0xc8100200 are both out of
    bounds for this primitive. a fresh handle does not help, only
    tools/optimus_reboot.py does. sweeps are opt-in and every address in one
    must already be known-readable or the run is a one-shot.
  - the burning window is 5 s (`fastboot oem update 5000`), and optimus.read_mem
    hardcodes a 5000 ms control timeout, which is the whole window. one bad
    address would burn all of it. the transfer is issued here with a 250 ms
    timeout instead; a good 0x02 read takes ~6 ms (round 26: 21 ms for a whole
    read/SMC/read pair).

Read-only in the RAM sense: 0x02 reads plus `set_usb_boot` commands. no 0x01, no
0x03, no fill, no poke, no RUN_IN_ADDR, and deliberately no reset, because the
armed state is the thing under test and a reset would consume it.

    OPTIMUS_PY=tools/rti_probe.py tools/optimus_enter.sh
    OPTIMUS_PY=tools/rti_probe.py tools/optimus_enter.sh 0xc8100200:0x100
    OPTIMUS_PY=tools/rti_probe.py tools/optimus_enter.sh --rti
"""
import struct
import sys
import time

import usb.core

import optimus

# known readable, flagtest.py read all three in F1
KEYS = (
    ("GP_CFG7", 0xC810025C),   # round36: [8:31] is a gpio pad array
    ("GP_CFG0", 0xC8100240),   # [3:0] is the real rom boot-device id
    ("SD_CFG15", 0xC810023C),  # [15:12] boot mode, [31:28] reboot reason
    # the rest of the block that is proven readable. 0xc810023c..0xc8100264 is
    # SD_CFG12..15 plus GP_CFG0..9. 0xc8100200 (SD_CFG0) is NOT readable and
    # kills the endpoint, so the run dies if the window starts below 0xc810023c.
    ("SD_CFG12", 0xC8100230),
    ("SD_CFG13", 0xC8100234),
    ("SD_CFG14", 0xC8100238),
    ("GP_CFG1", 0xC8100244),
    ("GP_CFG2", 0xC8100248),
    ("GP_CFG3", 0xC810024C),
    ("GP_CFG4", 0xC8100250),
    ("GP_CFG5", 0xC8100254),
    ("GP_CFG6", 0xC8100258),
    ("GP_CFG8", 0xC8100260),
    ("GP_CFG9", 0xC8100264),
)

# read last, one at a time, because the first of these drops the endpoint
RTI_BLOCK = (
    ("RTI_STATUS_REG3", 0xC810001C),
    ("RTI_STATUS_REG1", 0xC8100004),
    ("AO_REG_0x120", 0xC8100120),
)


def read4(dev, addr, timeout=250):
    """one word, or None if the block refuses it. never raises."""
    try:
        b = bytes(dev.ctrl_transfer(optimus.RT_IN, optimus.REQ_READ_MEM,
                                    (addr >> 16) & 0xFFFF, addr & 0xFFFF,
                                    4, timeout))
        return struct.unpack("<I", b)[0] if len(b) == 4 else None
    except (usb.core.USBError, OSError):
        return None


def alive(dev):
    try:
        return dev.get_descriptor(1) is not None
    except (usb.core.USBError, OSError):
        return False


def decode(snap):
    g7, g0, s15 = snap.get(0xC810025C), snap.get(0xC8100240), snap.get(0xC810023C)
    if g0 is not None and g7 is not None:
        print("    GP_CFG0[3:0]=%d  GP_CFG7[31]=%d  -> is_tpl_loaded_from_usb()=%d"
              % (g0 & 0xF, (g7 >> 31) & 1, (g0 & 0xF == 5) or (g7 >> 31) & 1),
              flush=True)
    if s15 is not None:
        print("    SD_CFG15[15:12]=0x%x  SD_CFG15[31:28]=0x%x  SD_CFG15[11:8]=0x%x"
              % ((s15 >> 12) & 0xF, (s15 >> 28) & 0xF, (s15 >> 8) & 0xF),
              flush=True)


def keys(dev, tag):
    out = {}
    print("\n== %s ==" % tag, flush=True)
    for name, addr in KEYS:
        v = read4(dev, addr)
        out[addr] = v
        print("  %-10s 0x%08x  %s" % (name, addr,
                                      "X unreadable" if v is None else "0x%08x" % v),
              flush=True)
    decode(out)
    return out


def sweep(dev, base, size, label):
    out = {}
    print("\n-- sweep %s 0x%08x..0x%08x --" % (label, base, base + size),
          flush=True)
    for off in range(0, size, 4):
        v = read4(dev, base + off)
        out[base + off] = v
        print("  0x%08x  %s" % (base + off, "X" if v is None else "0x%08x" % v),
              flush=True)
    return out


def diff(old, new, title):
    print("\n---- %s ----" % title)
    hits = 0
    for addr in sorted(old):
        o, n = old[addr], new[addr]
        if o == n or n is None:
            continue
        hits += 1
        print("  0x%08x  %s -> 0x%08x   (xor 0x%08x)"
              % (addr, "X" if o is None else "0x%08x" % o, n, (o or 0) ^ n))
    if not hits:
        print("  no change")
    return hits


def cmd(dev, c):
    print("\n== bulkcmd: %s ==" % c, flush=True)
    print("  " + optimus.bulkcmd(dev, c).split(b"\0")[0]
          .decode("ascii", "replace"), flush=True)


def main():
    argv = sys.argv[1:]
    ranges = [tuple(a.split(":")) for a in argv if ":" in a]
    want_rti = "--rti" in argv

    dev = optimus.find()
    if optimus.identify(dev) != 0:
        sys.exit("not stage 16, refusing: that is not the BL33 we mapped")

    t0 = time.time()
    a = keys(dev, "before")

    cmd(dev, "set_usb_boot 2")
    b = keys(dev, "after set_usb_boot 2")
    n_arm = diff(a, b, "keys: set_usb_boot 2")

    cmd(dev, "set_usb_boot 1")
    c = keys(dev, "after set_usb_boot 1 (clear)")
    n_clr = diff(b, c, "keys: set_usb_boot 1")

    for r in ranges:
        sa = sweep(dev, int(r[0], 0), int(r[1], 0), r[0])
        cmd(dev, "set_usb_boot 2")
        sb = sweep(dev, int(r[0], 0), int(r[1], 0), r[0])
        n_arm += diff(sa, sb, "sweep %s: set_usb_boot 2" % r[0])
        cmd(dev, "set_usb_boot 1")

    print("\n== verdict, %.3f s ==" % (time.time() - t0))
    print("  words changed by the arm: %d, by the clear: %d" % (n_arm, n_clr))
    for name, addr in KEYS:
        o, n = a.get(addr), b.get(addr)
        if o != n:
            print("  %s MOVED 0x%08x -> 0x%08x (xor 0x%08x)"
                  % (name, o, n, o ^ n))
        elif o is None:
            print("  %s unreadable at 0x%08x" % (name, addr))
        else:
            print("  %s unchanged at 0x%08x" % (name, addr))
    print("  left disarmed with set_usb_boot 1, no reset issued.")

    if want_rti:
        print("\n== rti block, read last: this is expected to drop the endpoint ==",
              flush=True)
        for name, addr in RTI_BLOCK:
            v = read4(dev, addr)
            print("  %-16s 0x%08x  %s"
                  % (name, addr, "X unreadable" if v is None else "0x%08x" % v),
                  flush=True)
            if v is None or not alive(dev):
                print("  endpoint gone after 0x%08x, stopping" % addr, flush=True)
                break


if __name__ == "__main__":
    main()
