# USB recovery without a power cycle

Applicable to the `1b8e:c003` gadget (Amlogic burning/optimus, stage 16
TPL/BL33) of the Xiaomi Mi TV Stick 1080p. Detailed document:
`USB_RECOVERY_WITHOUT_POWER_CYCLE.md`.

## Method

```python
import time, usb.core
d = usb.core.find(idVendor=0x1B8E, idProduct=0xC003)
assert d is not None, "device off the bus"
try:
    d.reset()                      # libusb_reset_device / USBDEVFS_RESET
except usb.core.USBError:
    pass
time.sleep(0.6)
d = usb.core.find(idVendor=0x1B8E, idProduct=0xC003)
assert d is not None, "did not come back after reset"
print(bytes(d.ctrl_transfer(0xC0, 0x20, 0, 0, 4, 2000)).hex())
# expected: 00070010
```

Full implementation: `tools/recover_usb.py`.

```sh
sudo python3 tools/recover_usb.py --dry-run   # diagnostic, no action
sudo python3 tools/recover_usb.py -y          # execute
sudo python3 tools/optimus.py identify        # verify 00 07 00 10
```

## Prerequisites

- `lsusb -d 1b8e:c003` still returns a handle (errno 19 with disconnect means
  the device left the bus; the method does not apply).
- `identify` fails with errno 19, 75, or 110 while the gadget remains
  enumerated.
- Root on the host; no other USB tool with the interface claimed.
- Verify identity and stage before calling `d.reset()`.

## Mechanism

`dev.reset()` -> `libusb_reset_device` -> `ioctl(USBDEVFS_RESET)` -> `PORT_RESET`
at the hub (SE0 ~10 ms in USB 2.0). It does not issue
`ClearPortFeature(PORT_POWER)`, does not cut VBUS, and does not restart the SoC.
The 0.6 s sleep and the re-find are necessary because usbfs may emit UNBIND
without BIND after the reset.

`clear_halt` does not work: it fails with errno 75 and only clears one
endpoint's toggle; it does not restart SET_ADDRESS or the gadget state machine.

## Limitations

- Does not recover a device off the bus (read of an unmapped region,
  `RUN_IN_ADDR 0x05`, MREAD of Secure memory `0x05100000`).
- Does not recover BL33 stuck in the `do_reset` loop: the firmware stopped
  serving SET_ADDRESS and there is no target for the reset.
- Volatile state (configuration, altsettings, toggles) is discarded. If the
  stage changes from 16 after the reset, stop and investigate.
- Not ADB recovery: if the device is `2717:4e40`, use `adb reconnect` on the
  host.

## Observed results

On 2026-11-19 the wedge was induced with explicit authorization via
`AM_REQ_RD_LARGE_MEM 0x12` (`addr=0x20000000, size=0x1000`):

```
before:            OK 00070010
liveness:          FAIL errno=75
lsusb -d 1b8e:c003 -> still enumerated
recover_usb.py -y  -> dev.reset() -> recovered: version 0.7, stage 16
identify pos:      00 07 00 10
mread 0x20000000:  NFANDROID2-PRV-AQUAMAN-... (readable RAM)
dmesg:             reset high-speed USB device (no disconnect on 3-3)
```

Method validated live. In the round 62-64 experiments the gadget dropped off
the bus (not a wedge), so this procedure was not applied; the device rebooted
by itself into Android in ~17-19 s and was re-entered into optimus via
`adb reboot fastboot` + `fastboot oem update 5000`.

Rule: in case of a lockup, prioritize this reset. Never replace it with a power
cycle automatically, and do not enter an infinite loop of resets.
