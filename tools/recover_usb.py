#!/usr/bin/env python3
"""Unstick a wedged Amlogic 1b8e:c003 optimus gadget via USB bus reset.

Mechanism: libusb_reset_device() -> USBDEVFS_RESET -> PORT_RESET (SE0 ~10 ms
on USB2). VBUS is never removed; this is not a power cycle and not a SoC reset.

Only two operations are used: a read-only REQ_IDENTIFY control transfer and
the bus reset itself. No flash, env, efuse, config or sysfs changes.

Exit codes: 0 healthy/recovered/dry-run, 1 user abort, 2 not enumerated,
3 reset failed, 4 vanished after reset, 5 still unresponsive.
"""
import argparse
import errno
import logging
import sys
import time

import usb.core

VID, PID = 0x1B8E, 0xC003
RT_IN = 0xC0
REQ_IDENTIFY = 0x20
IDENT_LEN = 4
IDENT_TIMEOUT = 2000
DEFAULT_SETTLE = 0.6  # reports/rdlarge-bulk-read.md section 7

STAGE_NAME = {0: "IPL/BL1", 8: "SPL/BL2", 16: "TPL/BL33-u-boot"}
ERR_NAME = {
    errno.EIO: "EIO/STALL",
    errno.ENODEV: "ENODEV",
    errno.EOVERFLOW: "EOVERFLOW",
    errno.ETIMEDOUT: "ETIMEDOUT",
}

log = logging.getLogger("recover_usb")


def find_dev():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        return None
    try:
        if dev.is_kernel_driver_active(0):
            dev.detach_kernel_driver(0)
    except (usb.core.USBError, NotImplementedError, AttributeError):
        pass
    return dev


def probe(dev):
    """(healthy, stage, text). One control IN, no writes."""
    try:
        data = dev.ctrl_transfer(RT_IN, REQ_IDENTIFY, 0, 0, IDENT_LEN, IDENT_TIMEOUT)
    except usb.core.USBError as e:
        name = ERR_NAME.get(e.errno, "errno=%s" % e.errno)
        return False, None, "%s: %s" % (name, e.strerror or str(e))
    if len(data) != IDENT_LEN:
        return False, None, "short reply (%d bytes)" % len(data)
    stage = data[2] * 256 + data[3]
    return True, stage, "version %d.%d, stage %d (%s)" % (
        data[0], data[1], stage, STAGE_NAME.get(stage, "?"))


def main():
    p = argparse.ArgumentParser(
        description="Recover a wedged 1b8e:c003 gadget via USB bus reset only")
    p.add_argument("--dry-run", action="store_true", help="probe and report only")
    p.add_argument("-y", "--yes", action="store_true", help="skip confirmation prompt")
    p.add_argument("--settle", type=float, default=DEFAULT_SETTLE,
                   help="seconds after reset before re-find (default: %(default)s)")
    p.add_argument("-v", "--verbose", action="store_true", help="debug log")
    a = p.parse_args()

    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")

    dev = find_dev()
    if dev is None:
        log.error("no 1b8e:c003 on the bus; no physical re-enumeration attempted")
        return 2

    ok, _stage, text = probe(dev)
    if ok:
        log.info("gadget already healthy: %s; no reset", text)
        return 0
    log.warning("gadget unresponsive: %s", text)

    if a.dry_run:
        log.info("dry run: would reset, sleep %.1fs, re-find, identify; no action",
                 a.settle)
        return 0

    if not a.yes:
        try:
            answer = input("USB bus reset (no power cut)? [y/N] ")
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            log.info("aborted by user")
            return 1

    log.info("dev.reset() -> libusb_reset_device / USBDEVFS_RESET (VBUS untouched)")
    try:
        dev.reset()
    except usb.core.USBError as e:
        # A stale handle after reset is normal; the re-find below is authoritative.
        log.warning("dev.reset() reported %s; continuing to re-find", e.strerror or str(e))
    except Exception as e:
        log.error("dev.reset() failed: %s", e)
        return 3

    time.sleep(a.settle)

    dev = find_dev()
    if dev is None:
        log.error("device gone after reset; bus reset cannot recover a device off the bus")
        return 4

    ok, _stage, text = probe(dev)
    if not ok:
        log.error("still unresponsive after reset: %s", text)
        return 5
    log.info("recovered: %s", text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
