#!/usr/bin/env python3
"""optimus_reboot.py - get the stick out of optimus without touching the plug.

`fastboot oem update 5000` puts BL33 into optimus v2 burning and arms a 5 s
auto-burn timeout, but the timeout is not always what brings it back. twice on
2026-09-30 the stick sat on 1b8e:c003 for 90 s+ with adb gone and no fastboot
device, because the host process died inside the window instead of letting the
timeout fire. there is no fastboot device to talk to in that state, so the only
way out short of a physical power-cycle is the optimus channel itself: 0x34
bulkcmd is `run_command()` inside optimus_working(), and `reboot` with no argument
is AMLOGIC_NORMAL_BOOT, i.e. PSCI 0x84000009 with x1=1. round 6 proved bulkcmd is
live on this stick, and round 31 decoded the mode table.

    sudo python3 tools/optimus_reboot.py            # reboot (normal)
    sudo python3 tools/optimus_reboot.py "reboot cold_boot"

This issues one real reset. it does not arm anything, and it is the only tool here
that resets on purpose, so it is kept separate from the read-only probes.
"""
import sys
import time

import optimus


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "reboot"
    dev = optimus.find()
    if dev is None:
        sys.exit("no 1b8e:c003 on the bus, nothing to do")
    if optimus.identify(dev) != 0:
        sys.exit("not stage 16, refusing: that is not the BL33 we mapped")

    print("identified stage 16, running %r" % cmd)
    print("  " + optimus.bulkcmd(dev, cmd).split(b"\0")[0]
          .decode("ascii", "replace"))
    for i in range(20):
        time.sleep(1)
        if not dev:
            print("device left the bus after %d s, that is the reset" % (i + 1))
            return
    print("still on the bus after 20 s, the reset may not have taken")


if __name__ == "__main__":
    main()
