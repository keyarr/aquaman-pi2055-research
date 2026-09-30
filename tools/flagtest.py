#!/usr/bin/env python3
"""flagtest.py - does `set_usb_boot 2` change GP_CFG7[31]? one burning window.

Runbook reasoning, because this is the one thing that has never been done:

The `oem` fastboot channel reaches BL33 (round 3, `oem set_usb_boot 2` returned
AMLOGIC in 97 ms), but there is no read primitive there. The only read path is
AM_REQ_READ_MEM 0x02 inside the optimus gadget, and getting back into optimus
means `fastboot oem update 5000`, which runs
`aml_burn_check_is_ready_for_burn` (0x37e765d8) -> `is_tpl_loaded_from_usb()`
-> and if GP_CFG7[31] is set it CLEARS it over SMC before enumerating.

So a before/after pair taken in two separate sessions always reads 0 after,
whether or not the SMC did anything. The whole measurement has to happen in
one process, inside one window, with the read straddling the command.

    OPTIMUS_PY=tools/flagtest.py optimus_enter.sh

That is `adb reboot fastboot` -> `fastboot oem update 5000` -> identify ->
read -> `set_usb_boot 2` over bulkcmd -> read, all in that order, in one
process, with the sudo already warm. Read-only in the RAM sense: 0x02 reads
plus one command, no 0x01/0x03, no reset, no fill/poke/RUN_IN_ADDR.

GP_CFG0 is read too, not because it is interesting on its own but because
`is_tpl_loaded_from_usb()` is `GP_CFG0[3:0]==5 || GP_CFG7[31]`; if GP_CFG0
already says BOOT_DEVICE_USB the flag is redundant and the test means nothing.
"""
import struct
import sys
import time

import optimus

# P_AO_SEC_GP_CFG7, the register is_tpl_loaded_from_usb() reads bit 31 of
# P_AO_SEC_GP_CFG0, the other half of that same expression
# P_AO_SEC_SD_CFG15, the ROM-visible reboot mode BL33 reads at 0x37e604a4
GP_CFG7 = 0xC810025C
GP_CFG0 = 0xC8100240
SD_CFG15 = 0xC810023C

REGS = (("GP_CFG7", GP_CFG7), ("GP_CFG0", GP_CFG0), ("SD_CFG15", SD_CFG15))


def snap(dev, tag):
    vals = {}
    print("\n== %s ==" % tag)
    for name, addr in REGS:
        b = bytes(optimus.read_mem(dev, addr, 4))
        v = struct.unpack("<I", b)[0]
        vals[name] = v
        print("  %-8s 0x%08x  0x%08x  %s" % (name, addr, v, b.hex(" ")))
    print("  GP_CFG7[31] = %d   GP_CFG0[3:0] = %d   SD_CFG15[15:12] = %d"
          % (vals["GP_CFG7"] >> 31, vals["GP_CFG0"] & 0xF,
             (vals["SD_CFG15"] >> 12) & 0xF))
    return vals


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "2"

    dev = optimus.find()
    if optimus.identify(dev) != 0:
        sys.exit("not stage 16, refusing: that is not the BL33 we mapped")

    t0 = time.time()
    before = snap(dev, "before set_usb_boot %s" % mode)

    # 0x34 bulkcmd, not 0x30 tpl_cmd. both land in optimus_working(), which
    # falls through to run_command() for set_usb_boot, but 0x34/0x33 is the
    # path round 6 proved live on this stick. 0x30/0x31 is in the source and
    # untested here. reply is useless either way: the console is invisible and
    # optimus_working always answers "success", so the register is the evidence.
    print("\n== set_usb_boot %s (bulkcmd 0x34 -> run_command) ==" % mode)
    print("  " + optimus.bulkcmd(dev, "set_usb_boot %s" % mode)
          .split(b"\0")[0].decode("ascii", "replace"))

    after = snap(dev, "after set_usb_boot %s" % mode)

    b31 = (before["GP_CFG7"] >> 31) & 1
    a31 = (after["GP_CFG7"] >> 31) & 1
    print("\n== verdict, %.3f s ==" % (time.time() - t0))
    print("  GP_CFG7[31]  %d -> %d" % (b31, a31))
    for name, _ in REGS:
        if before[name] != after[name]:
            print("  %s also changed: 0x%08x -> 0x%08x" % (name, before[name], after[name]))
    if b31 == 1 and a31 == 1:
        print("  already set before the command: this run proves nothing, "
              "power-cycle and repeat")
    elif b31 == 0 and a31 == 1:
        print("  FLAG SET. evidence the SMC produced the expected state.")
    elif b31 == 0 and a31 == 0:
        print("  NO OBSERVABLE CHANGE. the register is readable, so this is a "
              "real null, not a failed read. whether BL31 ignored the SMC or "
              "something cleared it after is still open.")
    else:
        print("  1 -> 0, something cleared it. worth a look, log the run.")


if __name__ == "__main__":
    main()
