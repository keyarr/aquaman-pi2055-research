# Recovery of the Mi TV Stick without a power cycle

Scope: Xiaomi Mi TV Stick 1080p (MiTV-AESP0, `aquaman`, Amlogic S805Y/GXL),
Android 9 PI.2055. The method below applies to the USB gadget `1b8e:c003` in
optimus mode (TPL/BL33-U-Boot), not to Android itself.

## 1. Symptoms and conditions of the lockup

The recoverable "lockup" is a **USB gadget wedge**, not a SoC hang. It occurs
after a bulk transfer that the firmware arms but never drains (e.g.
`AM_REQ_RD_LARGE_MEM 0x12`, or a read from an unmapped address):

```
bulk IN on 0x81: errno 110 ETIMEDOUT
next request: errno 75 EOVERFLOW
clear_halt on 0x81 and 0x02: errno 75, does not help
```

Signatures 19 (ENODEV), 75 (EOVERFLOW), and 110 (ETIMEDOUT) mean the same thing
**as long as the device remains enumerated** (`rdlarge-bulk-read.md:352-353`).
The gadget goes deaf to new transfers, but the BL33 firmware is alive.

Mandatory condition: `usb.core.find(idVendor=0x1B8E, idProduct=0xC003)` still
returns a handle. If it returns `None`, the device has left the bus and this
method does not apply (see section 9).

## 2. Device state before recovery

Current state at the start of this investigation (2026-11-19):

```
lsusb:            Bus 003 Device 002: ID 1b8e:c003 Amlogic, Inc.
bcdDevice:        0.07
identify:         raw 00 07 00 10 -> version 0.7, stage 16 (TPL/BL33-u-boot)
adb devices:      empty
fastboot devices: empty
```

**At the start the device was NOT locked up.** `optimus.py desc` and `identify`
responded normally. I induced the wedge deliberately; the execution is in
section 5.1.

Documented historical wedge episode (`reports/round5-rdlarge/02_probe_stages.txt:1-4`):

```
=== step 1: identify ===
  FAIL (USBError errno=75)
  after reset: OK (00 07 00 10)
=== step 4: 0x12 size=0x1000, interface claimed ===
  FAIL USBTimeoutError errno=110
  liveness: FAIL (USBError errno=75)
```

## 3. Interfaces that remained accessible

In the `1b8e:c003` stage 16 state:

| Interface | Status | How |
| --- | --- | --- |
| USB control EP0 | accessible | `REQ_IDENTIFY 0x20`, `REQ_READ_MEM 0x02`, descriptors |
| Bulkcmd | accessible | `0x34` -> `run_command()` inside `optimus_working` |
| mread | accessible | `0x34` + `0x33` |
| USB bus reset | accessible | `dev.reset()` via libusb |
| ADB | inaccessible | is another VID:PID (`2717:4e40`), only exists in Android |
| fastboot | inaccessible | `18d1:0d02`, only exists in the bootloader |
| UART / U-Boot console | inaccessible | there is no visible console on this board |

Empty ADB here does **not** indicate a lockup: the burning gadget replaces the
ADB interface. `adb kill-server`, `adb reconnect`, and udev are useless in this
state and were not needed.

## 4. Hypotheses investigated

1. **ADB server hung on the host** - ruled out. The VID:PID changed; there is no
   ADB interface to reconnect to (`reports/_archive/usb-entry-aquaman.md:557-561`).
2. **Android hung with ADB dead** - ruled out. There is no `2717:4e40` on the
   bus.
3. **USB gadget locked up with BL33 alive** - confirmed as the class that the
   method resolves (`rdlarge-bulk-read.md:198-205`).
4. **BL33 stuck in `do_reset`** - investigated, not the current case, and USB
   reset **does not** fix it. `do_reset` (0x37e21684) falls into `0x37e1a058`, a
   loop with no exit that writes `0x07a00003` to `0xc11098d0` and kicks
   `0xc11098dc` on every pass (`round33-doreset-watchdog-loop.md:43-116`). The
   watchdog never expires because it is rearmed; BL33 stops serving USB and the
   gadget leaves the bus.
5. **Triggering the watchdog via SMC/PSCI to recover without cutting power** -
   unfeasible from the locked state. SMC is an instruction executed by the CPU
 in BL33; if BL33 is in the loop, no one executes it. PSCI `0x84000009`
   requires a live BL33 to receive the command (`round59/01`, `round36:261-294`).
6. **clear_halt as a cure** - refuted. It fails with errno 75; only the bus
   reset works (`rdlarge-bulk-read.md:349-350`).

## 5. Commands executed and results

Diagnostics in this session (read-only):

```
adb devices -l                          -> empty
fastboot devices                        -> empty
lsusb                                   -> 1b8e:c003 Amlogic, Inc.
lsusb -d 1b8e:c003 -v                   -> bcdDevice 0.07, vendor class 0xff
sudo python3 tools/optimus.py desc      -> ep 0x81 IN mps 512, ep 0x02 OUT mps 512
sudo python3 tools/optimus.py identify  -> version 0.7, stage 16 (TPL/BL33-u-boot)
```

Without sudo, `optimus.py` fails with `USBError: [Errno 13] Access denied`.

Historical evidence for the method:

```
reports/round5-rdlarge/02_probe_stages.txt:1-3   identify FAIL errno=75 -> after reset OK
reports/round5-rdlarge/03_probe_bulkcmd.txt:1-3   identify FAIL errno=110 -> after reset OK
reports/round5-rdlarge/05_interleave.txt          errno 75 after each wedge
```

### 5.1 Live execution (2026-11-19, I induced the wedge)

I induced the lockup and reproduced the
`AM_REQ_RD_LARGE_MEM 0x12` from round 5 with parameter
`{addr=0x20000000, size=0x1000}`, with no writes to flash/env/efuse:

```
before:            OK 00070010
param:             00000020001000000000000000000000
control OUT:       completed
liveness:          FAIL errno=75 [Errno 75] Overflow
lsusb -d 1b8e:c003 -> device still enumerated
```

`identify` failed with the documented signature and the device did not leave
the bus, the necessary condition for the method. The trigger script's
`claim_interface` failed due to the pyusb API, but the control OUT alone already
armed the bulk and locked up the gadget, as in round 5.

Confirmation and recovery:

```
sudo python3 tools/recover_usb.py --dry-run
  WARNING gadget unresponsive: ETIMEDOUT: Operation timed out
  INFO dry run: would reset, sleep 0.6s, re-find, identify; no action

sudo python3 tools/recover_usb.py -y
  WARNING gadget unresponsive: ETIMEDOUT: Operation timed out
  INFO dev.reset() -> libusb_reset_device / USBDEVFS_RESET (VBUS untouched)
  INFO recovered: version 0.7, stage 16 (TPL/BL33-u-boot)
  exit=0
```

Post-recovery verification:

```
sudo python3 tools/optimus.py identify  -> raw 00 07 00 10, stage 16
sudo python3 tools/optimus.py read 0x20000000 64
  -> NFANDROID2-PRV-AQUAMAN-MGK00000008037639,...   (RAM readable)
dmesg:
  [18338.125177] usb 3-3: reset high-speed USB device number 2 using xhci_hcd
```

dmesg records only `reset high-speed USB device`, with no `USB disconnect` for
3-3 at that moment. This confirms a bus reset with VBUS preserved. The
`USB disconnect` that appears earlier at 17634 is from a previous session and
affects all devices on the hub.

## 6. Method that worked

```python
dev.reset()                    # libusb_reset_device
time.sleep(0.6)
usb.core.find(idVendor=0x1B8E, idProduct=0xC003)
```

After that `identify` responds with stage 16 again and `0x02` reads RAM
normally. It was found by accident in the first session of round 5 and reused
in all subsequent sessions of that round (`rdlarge-bulk-read.md:336-353`).
Surviving code: `tools/mread_test.py:60-69`, `tools/bl33_read.py:60-69`,
`tools/mread_scan.py:103-108`.

Round 4 (2026-09-29) prescribed manual unplug (`optimus-ram-read.md:286-288`);
round 5 explicitly corrected it: "that is no longer true". The discovery was
buried: no index (`MAP.md`, `CURRENT_STATE.md`) cites `rdlarge-bulk-read.md`, no
commit mentions the libusb reset, and 2026-11-19 reports went back to
prescribing a power cycle. I found the method in `reports/rdlarge-bulk-read.md`
section 7.

## 7. Technical mechanism

Exact chain on Linux:

```
libusb_reset_device()
  -> ioctl(fd, IOCTL_USBFS_RESET)        # == USBDEVFS_RESET == _IO('U', 20)
  -> drivers/usb/core/devio.c: proc_resetdevice()
  -> usb_reset_device() -> usb_reset_and_verify_device() -> hub_port_reset()
  -> SetPortFeature(PORT_RESET) no hub
```

`PORT_RESET` in USB 2.0 is SE0 (D+/D- to ground) for ~10-20 ms. The device
returns to the Default state (address 0), losing configuration and endpoint
toggles. The kernel reads the descriptors and restores the configuration; if
the descriptors do not change, it keeps the same `devnum` and there is no full
"new device detected". This is a **bus reset**, not a VBUS cut: it does not
issue `ClearPortFeature(PORT_POWER)`, does not disable the hub, and does not
restart the SoC.

Amlogic's forced boot order does not change either: it depends on the boot flow
and a reboot-mode register, not on the bus state. Even a warm reboot preserves
optimus mode; the bus reset is far less invasive.

Why it works: the lockup was in the **USB/endpoint state machine**, not the CPU.
The UDC receives the reset event, completes pending requests, negotiates speed,
clears the address, and signals `usb_gadget_udc_reset()`. The BL33 firmware
stays in the optimus command loop and starts responding again.

Why `clear_halt` does not work: `libusb_clear_halt()` only sends
`CLEAR_FEATURE(ENDPOINT_HALT)` and clears the toggle of **one** endpoint. It
does not restart SET_ADDRESS, does not reconfigure endpoints, and does not
rerun the state machine. Pipe scope, not device scope.

`errno 75` is the reliable signature of the wedge. `errno 19` and `110`
appeared in earlier rounds with the same meaning. The `sleep(0.6)` + re-find is
necessary because, after a reset without full re-enumeration, usbfs emits
UNBIND without a completing BIND; the old handle may become invalid.

Sources:
- https://libusb.sourceforge.io/api-1.0/group__libusb__dev.html
- https://github.com/libusb/libusb/blob/master/libusb/os/linux_usbfs.c
- https://www.kernel.org/doc/html/latest/driver-api/usb/power-management.html
- https://www.kernel.org/doc/html/latest/driver-api/usb/gadget.html
- https://www.01signal.com/other/usb-device-stuck-reset/
- https://lore.kernel.org/linux-usb/a0934cb4-82f2-42bf-abd8-95a0016fb0e4@rowland.harvard.edu/
- https://docs.u-boot-project.org/en/latest/board/amlogic/boot-flow.html

## 8. Recovery procedure

```sh
# 1. confirm the gadget is still on the bus
lsusb -d 1b8e:c003

# 2. check whether it is stuck (error 19/75/110 = wedge)
sudo python3 tools/recover_usb.py --dry-run

# 3. recover
sudo python3 tools/recover_usb.py           # asks for confirmation
sudo python3 tools/recover_usb.py -y        # no prompt

# 4. verify
sudo python3 tools/optimus.py identify      # expected: 00 07 00 10
```

The script `tools/recover_usb.py` only runs if `1b8e:c003` is enumerated. If
`identify` responds, it does nothing. It uses only `REQ_IDENTIFY` (read) and
`dev.reset()`. It does not touch flash, env, efuse, USB configuration, or sysfs.

Minimal equivalent code, if the script is not available:

```python
import time, usb.core
d = usb.core.find(idVendor=0x1B8E, idProduct=0xC003)
assert d is not None, "device off the bus"
try:
    d.reset()
except usb.core.USBError:
    pass
time.sleep(0.6)
d = usb.core.find(idVendor=0x1B8E, idProduct=0xC003)
assert d is not None, "did not come back after reset"
print(bytes(d.ctrl_transfer(0xC0, 0x20, 0, 0, 4, 2000)).hex())
# expected: 00070010
```

## 9. Limitations and failure conditions

- **Device off the bus** (`find()` returns `None`, errno 19 with disconnect):
  there is no target for `dev.reset()`. Occurs on reads of unmapped regions,
  `RUN_IN_ADDR 0x05`, and MREAD of Secure memory (`0x05100000`). In these cases
  the 2026-11-19 reports are right: a power cycle was required or the device
  rebooted by itself into Android in ~17 s. Direct counter-evidence in
  `bl33-campaign-round43.md:93`: "usb reset => gone from bus. needs physical
  power-cycle".
- **BL33 in a loop (`do_reset`)**: the gadget drops off the bus and no firmware
  is serving SET_ADDRESS. USB reset does not recover it. Neither do watchdog,
  SMC, or PSCI: all require a live BL33 to receive the command.
- **Volatile state lost**: the bus reset discards configuration, altsettings,
  and toggles. If the stage changes from 16 after the reset, stop and
  investigate.
- **Permissions**: run as root. Another process with the interface claimed can
  make the kernel refuse the ioctl. Do not run in parallel with other USB
  tools.
- **Not Android recovery**: if the device is at `2717:4e40` with ADB dead, use
  `adb reconnect` / `kill-server` / `start-server` on the host. The method here
  is specific to the `1b8e:c003` gadget.
- **Alternative reset without cutting power**: `oem reboot cold_boot` (PSCI
  `0x84000009`) is a real SoC reset verified on C0 (`c0/c0.txt`), returning to
  Android in ~17.5 s without generating `1b8e:c003`. Do not use if a usb-boot
  armed in the session (`set_usb_boot 2 + cold_boot` produced an 885 s wedge).

## 10. Status of the success criteria

| Criterion | Status |
| --- | --- |
| Device leaves the lockup | Yes. I induced the wedge, `identify` failed with errno 75/110 and returned to stage 16 after the reset (section 5.1). |
| No power interruption | Yes. `USBDEVFS_RESET` does not touch VBUS; dmesg shows `reset high-speed USB device`, with no disconnect of 3-3. |
| Mechanism identified | Yes. libusb -> kernel -> PORT_RESET chain, with source code and docs cited. |
| Repeatable procedure | Yes. Reproduced live and encoded in `tools/recover_usb.py`. |
| Commands documented | Yes. Sections 5.1 and 8. |

Pending: none. I validated the method live on 2026-11-19 by inducing the wedge.
The limit remains that of section 9: if the
device leaves the bus or BL33 enters the `do_reset` loop, this method does not
recover it.
