#!/usr/bin/env python3
"""usb_watch.py - log every USB bus change, with the timing the reset tests need.

The round-3 watcher was an ad-hoc shell loop that never got committed, which
is why "three resets, one outcome" survived as a claim with no instrument
behind it. This is that instrument.

Polls /sys/bus/usb/devices (no root, no lsusb fork, no udev latency) and logs:

  - the full VID:PID set every time it changes, relative to t0
  - bcdDevice / speed / class when a device appears, so 1b8e:c003 from BL33
    optimus can be told apart from a BootROM 1b8e:c003
  - the intervals where no Aquaman device (2717:4e40, 18d1:0d02, 1b8e:c003) is
    on the bus at all, which is the "USB completely absent" measurement

String descriptors (iProduct/iManufacturer) are not in sysfs. Run
`journalctl -kf | grep -i usb` alongside this for those; it does not stall the
poll loop the way an in-loop `lsusb -v` would.

    usb_watch.py out/logs/c0.log 600
"""
import os
import sys
import time

DEV = "/sys/bus/usb/devices"

# the three IDs this project cares about, plus anything else gets logged too
TARGET = {("2717", "4e40"): "android",
          ("18d1", "0d02"): "fastboot BL33",
          ("1b8e", "c003"): "optimus/TPL/BL33"}


def snapshot():
    """(vid, pid) -> sysfs dir name, for every enumerated device."""
    out = {}
    try:
        names = os.listdir(DEV)
    except OSError:
        return out
    for name in names:
        base = os.path.join(DEV, name)
        try:
            with open(os.path.join(base, "idVendor")) as f:
                vid = f.read().strip().lower()
            with open(os.path.join(base, "idProduct")) as f:
                pid = f.read().strip().lower()
        except OSError:
            continue  # interface node, or the device left between listdir and open
        out[(vid, pid)] = name
    return out


def detail(name):
    bits = []
    for attr in ("bcdDevice", "speed", "bDeviceClass", "bNumConfigurations"):
        try:
            with open(os.path.join(DEV, name, attr)) as f:
                bits.append("%s=%s" % (attr, f.read().strip()))
        except OSError:
            pass
    return " ".join(bits) or "no sysfs attrs"


def main():
    log = sys.argv[1] if len(sys.argv) > 1 else "out/logs/usbwatch.log"
    duration = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
    interval = float(sys.argv[3]) if len(sys.argv) > 3 else 0.004

    os.makedirs(os.path.dirname(log) or ".", exist_ok=True)
    fh = open(log, "w")

    def say(t, line):
        fh.write("t=%8.3f  %s\n" % (t, line))
        fh.flush()
        print("t=%8.3f  %s" % (t, line))

    t0 = time.monotonic()
    prev = snapshot()
    prev_target = bool(set(prev) & set(TARGET))
    # log the attrs of the targets already up, not just of the ones that
    # appear later. bcdDevice on the pre-existing 18d1:0d02 is the reference
    # to compare a post-reset 1b8e:c003 against.
    for k in sorted(prev):
        if k in TARGET:
            say(0.0, "start   %s:%s  %-18s %s"
                % (k[0], k[1], TARGET[k], detail(prev[k])))
    say(0.0, "start   other: %s"
        % (sorted("%s:%s" % k for k in prev if k not in TARGET) or "none"))
    say(0.0, "target present: %s" % prev_target)

    while True:
        now = time.monotonic()
        t = now - t0
        if t >= duration:
            say(t, "watcher done, %.0f s" % duration)
            break

        cur = snapshot()
        if cur != prev:
            gone = set(prev) - set(cur)
            new = set(cur) - set(prev)
            for k in sorted(gone):
                say(t, "OFF      %s:%s %s" % (k[0], k[1], TARGET.get(k, "")))
            for k in sorted(new):
                say(t, "ON       %s:%s  %-18s %s"
                    % (k[0], k[1], TARGET.get(k, "other"), detail(cur[k])))
            if not (set(cur) & set(TARGET)):
                say(t, "*** no Aquaman device on the bus ***")
            prev = cur

        cur_target = bool(set(cur) & set(TARGET))
        if cur_target != prev_target:
            say(t, "target %s -> %s" % ("up" if prev_target else "down",
                                        "up" if cur_target else "down"))
            prev_target = cur_target

        left = interval - (time.monotonic() - now)
        if left > 0:
            time.sleep(left)

    fh.close()


if __name__ == "__main__":
    main()
