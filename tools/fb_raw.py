#!/usr/bin/env python3
"""fb_raw.py - minimal raw fastboot client (pyusb only, no host-side filtering).

The stock `fastboot` CLI validates `download`/`set_active` args locally and
never puts our bytes on the wire. This tool sends exactly what we say:
  fb_raw.py getvar <name>              -> prints reply value
  fb_raw.py download <file>            -> download:<hex> + raw bytes
  fb_raw.py cmd '<raw command>'        -> sends verbatim, prints reply
It finds the fastboot USB interface by class/subclass/protocol (ff/42/03).
Read-only except download (RAM buffer) and whatever raw cmd you pass.
"""
import sys
import time
import usb.core
import usb.util

CLS, SUB, PROTO = 0xFF, 0x42, 0x03


def find():
    for dev in usb.core.find(find_all=True):
        try:
            for cfg in dev:
                for intf in cfg:
                    if (intf.bInterfaceClass, intf.bInterfaceSubClass,
                            intf.bInterfaceProtocol) == (CLS, SUB, PROTO):
                        return dev, intf.bInterfaceNumber
        except usb.core.USBError:
            continue
    return None, None


def open_ep():
    dev, ifnum = find()
    if dev is None:
        print("no fastboot USB interface found", file=sys.stderr)
        return None, None, None
    try:
        if dev.is_kernel_driver_active(ifnum):
            dev.detach_kernel_driver(ifnum)
    except (usb.core.USBError, NotImplementedError):
        pass
    try:
        cfg = dev.get_active_configuration()
    except usb.core.USBError:
        # only configure when nothing is active; a redundant
        # SET_CONFIGURATION wedges this 2015.01 gadget (needs USB
        # port reset to recover)
        dev.set_configuration()
        cfg = dev.get_active_configuration()
    intf = usb.util.find_descriptor(cfg, bInterfaceNumber=ifnum)
    ep_out = usb.util.find_descriptor(intf, custom_match=lambda e:
        usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
    ep_in = usb.util.find_descriptor(intf, custom_match=lambda e:
        usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)
    return dev, ep_out, ep_in


def read_reply(ep_in, timeout=10000):
    data = bytes(ep_in.read(64, timeout))
    return data.split(b"\0")[0].decode("ascii", "replace")


def raw_cmd(cmd, timeout=10000):
    dev, ep_out, ep_in = open_ep()
    if dev is None:
        return 2, "NO-DEVICE"
    t0 = time.time()
    try:
        ep_out.write(cmd.encode("ascii"), timeout)
        reply = read_reply(ep_in, timeout)
    except usb.core.USBError as e:
        return 0, "USB-GONE after %.1fs (%s)" % (time.time() - t0, e)
    dt = time.time() - t0
    return 0, "%s (%.1fs)" % (reply, dt)


def do_getvar(name):
    rc, r = raw_cmd("getvar:" + name)
    print(r)
    return rc


def do_download(path):
    dev, ep_out, ep_in = open_ep()
    if dev is None:
        print("NO-DEVICE")
        return 2
    blob = open(path, "rb").read()
    t0 = time.time()
    try:
        ep_out.write(("download:%08x" % len(blob)).encode("ascii"), 5000)
        r = read_reply(ep_in, 5000)
        if not r.startswith("DATA"):
            print("unexpected: " + r)
            return 1
        mps = ep_out.wMaxPacketSize
        for off in range(0, len(blob), mps):
            ep_out.write(blob[off:off + mps], 10000)
        r2 = read_reply(ep_in, 15000)
    except usb.core.USBError as e:
        print("USB-GONE after %.1fs (%s)" % (time.time() - t0, e))
        return 0
    print("%s (%.1fs)" % (r2, time.time() - t0))
    return 0 if r2.startswith("OKAY") else 1


def main():
    if len(sys.argv) < 3 and not (len(sys.argv) == 2 and sys.argv[1] == "devices"):
        print(__doc__)
        return 2
    if sys.argv[1] == "devices":
        dev, ifnum = find()
        print("fastboot USB: %s" % (dev is not None))
        return 0 if dev else 1
    if sys.argv[1] == "getvar":
        return do_getvar(sys.argv[2])
    if sys.argv[1] == "download":
        return do_download(sys.argv[2])
    if sys.argv[1] == "cmd":
        rc, r = raw_cmd(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 10000)
        print(r)
        return rc
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
