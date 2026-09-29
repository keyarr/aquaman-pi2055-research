# USB entry from U-Boot on aquaman, audit plus read-only probe (round 3)

date: 2026-09-29. goal: find out whether the aquaman U-Boot can be pushed into
USB burning / USB download / BootROM without HDMI boot dongle, UART or opening
the box. no `flash`, no `erase`, no `format`, no `setenv`, no `saveenv`.
nothing was written to eMMC, the env, the OTP or any partition. `update` and
`reboot` WERE run, deliberately, after the offline analysis, with the user
present and physical access available for recovery. both are listed with
exactly what they did.

## 0. TL;DR

- **CONFIRMED on aquaman: a U-Boot -> USB path exists, no extra hardware.**
  `fastboot oem update 5000` takes the stick out of fastboot and makes it
  enumerate `1b8e:c003` (Amlogic USB burning, optimus v2 protocol) in ~370 ms,
  where it waits for the host. nothing was written to eMMC.
- that `1b8e:c003` is **BL33 (U-Boot)**, not the BootROM. the descriptor
  matches `v2_usb_tool/usb_pcd.c` from the reference tree byte for byte,
  including bcdDevice `0x0007`, zero string descriptors and MaxPower 2 mA. the
  round-2 claim that `1b8e:c003 = BootROM` is wrong.
- **BootROM via `set_usb_boot 2`: tried 3 times, failed 3 times.** three
  different resets (`reboot cold_boot`, `reset`, `fastboot reboot`), same
  outcome: dead box, zero USB devices for ~85 s, manual power cycle required.
  the "wrong reset mode" hypothesis is refuted. the path is CONFIRMED in the GXL
  code but **does not reproduce** on aquaman. see §2.6.
- `fastboot oem sleep 3` wedged the fastboot session. the stick needed a power
  cycle. any U-Boot command that blocks kills the session.

## 1. offline audit (phase 1)

### 1.1 what we actually have as reference

| tree | what it is | usable as U-Boot reference? |
|---|---|---|
| `.src/u-boot-khadas` | u-boot 2015.01, `khadas-vims-nougat`, GXL boards | yes, the only one |
| `.src/MiTV_OpenSource` | Linux **kernel** tree (MiCode dangal-p-oss) | no. zero U-Boot sources in it |
| `.src/linux-amlogic` | Linux kernel tree | no |

`bootloader.img` (1344000 B, sha256 `c7b8eea6…3424`, entropy 7.99988, 0
meaningful strings) gives us **nothing** statically. every statement below that
comes from the tree is family evidence, not device ground truth.

### 1.2 the aquaman fastboot is NOT the khadas fastboot

this matters for every conclusion that follows. the device answers
`getvar:all` with a modern AOSP-style table:

```
version-bootloader:U-Boot 2015.01-g7ac5df7677-dirty
hw-revision:EVT   max-download-size:0x08000000   off-mode-charge:0
variant:US   battery-soc-ok:yes   battery-voltage:4.2V
partition-type:boot:raw   partition-size:boot:0000000001000000
partition-type:system:ext4 … erase-block-size:2000  logical-block-size:2000
secure:no   unlocked:yes
```

`cb_getvar` in `.src/u-boot-khadas/drivers/usb/gadget/f_fastboot.c:396-475`
implements **none** of those. the reference snapshot is an older Amlogic
fastboot; the device runs a Xiaomi fork of a later one. the reference tree is
therefore *family* evidence only, and the presence/absence of any U-Boot
command on the device cannot be derived from it.

what is still shared, and is a real fingerprint: the round-2 test recorded
`getvar current-slot` → `FAILED (Status read failed)`, gadget dropped instantly,
device came back to Android 19 s later
(`reports/round2-update-test/12_fastboot_getvars.txt:31-34`). the khadas code
does exactly that when the env var is missing:

```c
/* f_fastboot.c:445 */
} else if (!strcmp_l1("current-slot", cmd)) {
        s3 = getenv("active_slot");
        strncat(response, s3, chars_left);   /* s3 == NULL -> fault */
```

`strncat(dst, NULL, n)` faults, the U-Boot loop dies, the gadget disappears and
the watchdog reboots. so the aquaman fastboot still carries this Amlogic bug,
i.e. `active_slot` is not set in the aquaman env. classification: **DERIVED
from observed behaviour, strongly consistent, not proven byte-for-byte**.

### 1.3 the two USB entry paths in the GXL family

**path A, BL33 USB burning (U-Boot level, "optimus v2")**

```
common/update_tftp()                     <- unrelated, TFTP auto-update, no U_BOOT_CMD
drivers/usb/gadget/v2_burning/v2_usb_tool/optimus_core.c:57
    U_BOOT_CMD(update, 3, 0, do_v2_usbtool, "Enter v2 usbburning mode", "usbburning timeout")
    do_v2_usbtool:  optimus_work_mode_set(OPTIMUS_WORK_MODE_USB_UPDATE);
                     setenv("identifyWaitTime", pcToolWaitTime);
                     v2_usbburning(timeout);
    v2_usbburning:  set_usb_phy_config(EXT_CLOCK); usb_parameter_init(timeout);
                     loop { if (usb_pcd_irq()) break; }
    usb_pcd_irq:    no SOF for timeout/2  -> power off PHY, return 2
                    elapsed > timeout     -> power off PHY, return 2
```

gadget: `v2_usb_tool/usb_pcd.c:24-25` → VID `0x1B8E`, PID `0xC003`.
built only when `CONFIG_AML_V2_FACTORY_BURN` is set
(`v2_burning/Makefile:12`).

env side (`board/amlogic/configs/gxl_skt_v1.h:96-100`):

```
usb_burning=update 1000
try_auto_burn=update 700 750
sdc_burning=sdc_burn ${sdcburncfg}
update = run usb_burning; run sdc_burning; … run recovery_from_flash;
switch_bootmode = get_rebootmode; … else if reboot_mode = update then run update
```

so `adb reboot update` (reboot_mode 3) walks straight into
`update 1000` → **a 1000 ms window where the device is 1b8e:c003**.
round 2 (`reports/round2-update-test/report.txt:10-22`) polled `lsusb` once per
second and saw nothing for 12 s, then recovery MTP. a 1 s window sampled at 1 s
is very easy to miss, so that test is **NOT** a refutation of path A.

**path B, BootROM USB download (BL1 level)**

```
common/cmd_reboot.c:207   U_BOOT_CMD(set_usb_boot, 2, 0, do_set_usb_boot, …)
common/cmd_reboot.c:165   do_set_usb_boot -> set_usb_boot_function(usb_mode)
arch/arm/cpu/armv8/gxl/bl31_apis.c:310
    x0 = SET_USB_BOOT_FUNC (0x82000043), x1 = mode, smc #0
bl31_apis.h:63-66   1 = CLEAR_USB_BOOT  2 = FORCE_USB_BOOT
                    3 = RUN_COMD_USB_BOOT  4 = PANIC_DUMP_USB_BOOT
```

the bit that the ROM reads on the next start is pinned by the same tree:

```c
/* v2_burning/aml_v2_burning.c:72 */
int is_tpl_loaded_from_usb(void)
{
    int boot_id = readl(P_AO_SEC_GP_CFG0) & 0xf;
    unsigned forceUsbBoot = readl(P_AO_SEC_GP_CFG7);
    return (BOOT_DEVICE_USB == boot_id) || (forceUsbBoot & (1U << 31));
}
```

`P_AO_SEC_GP_CFG7[31]` *is* the "boot the ROM from USB" flag. BL31 sets it when
U-Boot asks for FORCE_USB_BOOT, and the ROM consumes it at the next reset.
that is the software equivalent of the HDMI `boot@USB` dongle, and it does not
touch eMMC. it is a hardware register though: it survives a warm reset and is
only cleared by a full power cycle. `set_usb_boot 1` also clears it from
U-Boot (`aml_burn_usb_producing()` calls `CLEAR_USB_BOOT` before burning).

### 1.4 command table

origin: `.src/u-boot-khadas` unless stated. "aquaman" column is the honest
answer, which for most rows is *unknown*, see §1.2, we cannot read the
device's command table.

| command | origin | aquaman | likely effect | persistent | risk |
|---|---|---|---|---|---|
| `update [t] [pct]` | optimus_core.c:57, `CONFIG_AML_V2_FACTORY_BURN` | **confirmed**, run, see §2.4 | BL33 v2 USB burning, 1b8e:c003, waits `t` ms | no (RAM/USB) | med, kills the fastboot gadget; a host tool that sends a package writes eMMC |
| `usb_burning` (env) = `update 1000` | gxl_skt_v1.h:96 | env unreadable | same, 1000 ms window | no | med |
| `try_auto_burn` (env) | gxl_skt_v1.h:98 | env unreadable | `update 700` + identifyWaitTime 750 | no | med |
| `sdc_burning` (env) / `sdc_burn` | gxl_skt_v1.h:100, v2_sdc_burn/ | unknown | burn from SD `aml_sdc_burn.ini` | **yes, eMMC** | high |
| `set_usb_boot 1..4` | cmd_reboot.c:207 | **tested 3x**, see §2.6 | SMC 0x82000043 to BL31; `2` = force next boot into ROM USB | **yes, AO register** (warm-reboot proof, power-cycle clear) | high, all three trials killed the box and needed a manual power cycle |
| `get_rebootmode` | cmd_reboot.c:181 | unknown | reads `AO_SEC_SD_CFG15[15:12]`, setenv `reboot_mode` (RAM only) | no | low |
| `reboot [mode]` | cmd_reboot.c:189 | unknown | `aml_reboot(PSCI_SYS_REBOOT, mode)`; `update`=3, `fastboot`=4, `bootloader`=7 | no | med, reboots |
| `fastboot` | cmd_fastboot.c:36 | **confirmed** (we are in it) | serve fastboot | no | low |
| `reboot-bootloader` (fastboot cmd) | f_fastboot.c:368 | confirmed present in family | `run_command("reboot fastboot")` | no | low |
| `tiny_usbtool` | aml_tiny_usbtool/aml_tiny_usbtool.c:71 | unknown | 1b8e:c003 tiny USB tool (efuse, reg read) | some ops write efuse | high |
| `usbboot` | cmd_usb.c:707 | unknown | **USB mass-storage diskboot**, *not* burning | no | low |
| `usb start/stop` | cmd_usb.c:682 | unknown | USB host mode | no | low |
| `autoscr` / `aml_autoscript` | cmd_autoscript.c:224, gxl_skt_v1.h:173-180 | unknown | run a U-Boot command script from RAM | depends on script | high |
| `printenv` | standard | certain | prints to console only | no | low |
| `sleep` | cmd_misc.c:34, `CONFIG_CMD_MISC` | unknown | delay in seconds | no | low, but see §2.3 |
| `setenv` / `saveenv` | standard | **confirmed** (`oem setenv lock 10100000` + `saveenv` flipped `unlocked`/`secure`, reports/bootloader_unlock.md) | env write | **yes** | high |
| `bootm` | standard | confirmed | boot, goes through `aml_sec_boot_check` SMC | no | low |
| `booti` / `go` | cmd_booti.c / cmd_bootd.c | **refuted** (reports/custom-kernel-execution.md §2) | n/a | n/a | n/a |
| `amlmmc` | cmd_aml_mmc.c:876 | unknown | raw eMMC read/write | write path yes | high |

## 2. device probe (phase 2, read-only only)

device was already in fastboot (`18d1:0d02`, BL33) at the start of the session.

### 2.1 getvar, all clean

```
getvar unlocked            -> unlocked: yes
getvar secure              -> secure: no
getvar version-bootloader  -> U-Boot 2015.01-g7ac5df7677-dirty
getvar product             -> aquaman
getvar serialno            -> 1234567890
getvar all                 -> (full table, see §1.2)
```

### 2.2 the `oem` channel carries no output, this kills the printenv plan

```
fastboot oem version            -> (bootloader) AMLOGIC x3  + OKAY  0.002s
fastboot oem help               -> (bootloader) AMLOGIC x3  + OKAY
fastboot oem printenv           -> (bootloader) AMLOGIC x3  + OKAY
fastboot oem printenv bootcmd   -> (bootloader) AMLOGIC x3  + OKAY
fastboot oem printenv usb_burning / reboot_mode / sdc_burning / upgrade_step / lock
                                -> identical reply, byte for byte
python3 tools/fb_raw.py cmd 'oem printenv'  -> INFOAMLOGIC (0.0s)
```

the wire reply is the constant `INFOAMLOGIC` (fastboot status `INFO` + text
`AMLOGIC`) followed by `OKAY`. it is the same for `version`, `help`,
`printenv` and for env names that certainly do not exist.

consequences, and they are the core result of phase 2:

1. U-Boot console output (printenv, help, any command) **never reaches the
   host**. there is no UART and no video console. `printenv` is useless here,
   which also means the variable list asked for in the task (reboot_mode,
   upgrade_step, usb, burn, update, bootcmd, …) is **unreadable** on this
   device. not "hard to read", unreadable by any means.
2. the reply does not encode the command result, so there is **no
   command-existence oracle** in the fastboot interface. `run_command("bogus")`
   and `run_command("printenv")` are indistinguishable from the host.
3. the only evidence that `oem` really reaches `run_command()` is indirect and
   comes from the unlock: `oem setenv lock 10100000` + `oem saveenv` changed
   `getvar unlocked` to `yes` and `getvar secure` to `no`
   (reports/bootloader_unlock.md:21-31), and both still read that way now.
   → **CONFIRMED (indirect)**: `fastboot oem <cmd>` is a U-Boot command
   passthrough on this device.

### 2.3 `fastboot oem sleep 3` wedged the fastboot session

```
fastboot oem sleep 3            -> no reply, client hung > 120 s
after that: getvar unlocked     -> timeout
            getvar version-bootloader -> timeout
            oem version          -> timeout
            fastboot devices     -> 1234567890 Android Fastboot
            lsusb                -> Bus 003 Device 030: ID 18d1:0d02
```

the gadget stays enumerated, U-Boot answers nothing. the device is not bricked
, it is USB powered, so unplug/replug recovers it, but the fastboot session is
dead until then.

what this proves and what it does not:

- **CONFIRMED**: the `oem` path can block the fastboot reply path with no
  timeout. any long or blocking U-Boot command kills the session.
- **POSSIBLE**: the command really executed `sleep 3` and the reply never went
  out. the previous `oem version` / `oem nosuchcmd` had already started timing
  out at 25 s in the same batch, so the session was already degrading.
- **UNKNOWN**: whether `sleep` exists in this build.
- risk note for the real test: `fastboot oem update 1000` will also take the
  fastboot gadget down and, by design, will not send a reply until the burning
  window closes. plan for a power cycle, not for a clean return.

## 2.4 the decisive test, run after a power cycle

device was power cycled by the user and put back in fastboot
(`18d1:0d02`, `getvar version-bootloader` answering normally again). a USB bus
watcher was started **before** the trigger, polling
`/sys/bus/usb/devices/*/idVendor:idProduct` every 4 ms.

```
$ fastboot oem update 5000
FAILED (Status read failed (No such device))

usbwatch, seconds from start:
  0.000  [0408:403a, 04ca:3802, 18d1:0d02, 1d6b:0002, 1d6b:0003, 3151:3020]
  1.585  [0408:403a, 04ca:3802, 1d6b:0002, 1d6b:0003, 3151:3020]        <- fastboot gone
  1.952  [0408:403a, 04ca:3802, 1b8e:c003, 1d6b:0002, 1d6b:0003, 3151:3020]
  1b8e:c003 window: (1.952, 40.002) and still present 100 s later
```

raw log: `reports/round3-usb-entry/usbwatch_t0.log`.

reading:

- the `update` command **exists in this build**. CONFIRMED no aquaman.
- it is `do_v2_usbtool` exactly as in the reference tree: the fastboot gadget
  is torn down, the USB PHY is re-initialised in device mode with the v2
  burning descriptors, and the device waits for the host.
- the fastboot client answer `FAILED (Status read failed)` is the predicted
  consequence of the gadget disappearing, not an error in the command.
- the device holds the burning mode for as long as a host keeps the USB port
  active. it did **not** drop at the 5000 ms mark, so the `usb_pcd_irq`
  timeout does not fire while SOFs keep arriving. recovery is a power cycle,
  not a timeout.
- nothing was written to eMMC. no burning package was sent, and none can be
  sent without an actual host tool driving the protocol.

### 2.5 the descriptor proves it is BL33, not BootROM

captured from the device (kernel descriptor cache, no privileged access
needed): `reports/round3-usb-entry/usb_burning_1b8e_c003.txt`.

| field | reference `v2_usb_tool/usb_pcd.c` | observed on aquaman |
|---|---|---|
| bcdUSB | `0x0200` (:41) | 2.00 |
| bDeviceClass/Sub/Protocol | `0x00/0/0` (:43-45) | 0 / 0 / 0 |
| bMaxPacketSize0 | 64 (:46) | 64 |
| idVendor / idProduct | `0x1B8E` / `0xC003` (:24-25) | 0x1b8e / 0xc003 |
| **bcdDevice** | `0x0007` (:49) | **0.07** |
| **iManufacturer / iProduct / iSerial** | `0 / 0 / 0` (:50-52) | **0 / 0 / 0** |
| iConfiguration | 0 (:75) | 0 |
| bmAttributes | `ATT_ONE\|ATT_SELFPOWER` = 0xc0 (:76-77) | 0xc0 |
| **MaxPower** | `1` = 2 mA (:78) | **2mA** |
| interface class/sub/proto | `0xFF/0x00/0x00` (:88-90) | 255 / 0 / 0 |
| endpoint IN / OUT | `0x81` / `0x02` (:95,:108) | 0x81 / 0x02 |
| wMaxPacketSize | 512 (:99) | 512 |
| wTotalLength | `0x0020` (:60) | 0x0020 |

every field is a literal constant from the U-Boot C source, down to the 2 mA
power budget and the `0x0007` bcdDevice. a BootROM BL1 image is a different
firmware and cannot produce those numbers. this also retroactively invalidates
the identifier the round-2 report used.

the optional confirmation is the stage byte: the vendor control request
`AM_REQ_IDENTIFY_HOST` (0x20) returns 4 bytes
`{USB_ROM_VER_MAJOR, USB_ROM_VER_MINOR, USB_ROM_STAGE_MAJOR, USB_ROM_STAGE_MINOR}`
= `{0, 8, 0, 16}` on GXL, with `16 // IPL = 0, SPL = 8, TPL = 16`
(`usb_pcd.c:522-537`, `platform.h:105-112`). TPL means U-Boot. NOT RUN, it
needs root on the host to claim the device (`sudo` asks for a password here)
and the descriptor match above already settles the question.

### 2.6 `set_usb_boot 2`, three resets, three identical failures

run with the user present, bus watcher up, one command at a time. three
trials, each ending in a manual power cycle:

| # | reset used | what it is | result |
|---|---|---|---|
| 1 | `oem reboot cold_boot` | `aml_reboot(PSCI_SYS_REBOOT, 0)` → mode 0, PSCI path (cmd_reboot.c:155) | logo Xiaomi ~100 ms, then off. 83 s of bus silence. |
| 2 | `oem reset` | `reset_cpu(0)` directly, no mode tag, no PSCI (arch/arm/lib/reset.c:30-41) | black screen from the start. 89 s of bus silence. |
| 3 | `fastboot reboot` | maps to `run_command("reboot fastboot")` (f_fastboot.c:366-369) → mode 4 | same, dead box, needed a power cycle |

trial 2 was run fully stepwise, the only one with a clean before/after:

```
17:10:48  adb reboot fastboot
17:10:55  fastboot 18d1:0d02 up
17:11:03  baseline: U-Boot 2015.01-g7ac5df7677-dirty / unlocked yes / secure no
17:11:05  oem set_usb_boot 2   -> AMLOGIC x3, 97 ms, no visible effect
17:11:10  oem reset            -> FAILED (Status read failed), gadget dropped
17:11:10 .. 17:12:39  bus completely empty
```

journal: `reports/round3-usb-entry/setusbboot_timeline.txt`.

user observations, the part no log can give:
- trial 1: rebooted, **Xiaomi logo for ~100 ms**, then powered off.
- trials 2 and 3: **black screen**, nothing on the Linux bus.

what this settles:

- "wrong reset mode" → **REFUTADO**. `reset` is `reset_cpu(0)` with no mode
  tag at all, and it failed the same way as PSCI mode 0. three different reset
  paths, one outcome.
- "the ROM honoured FORCE_USB_BOOT and enumerated 1b8e:c003" → **REFUTADO**,
  three times.
- "the box stayed on the normal boot path" → **REFUTADO**, it never booted.
- "the boot behaviour changed" → **CONFIRMADO**. a plain reset on this device
  returns to Android in 15-20 s; the round-2 log records exactly that for
  `adb reboot`, and `do_reset` is the standard fallback when `fastboot boot`
  is rejected (`f_fastboot.c:580`). 83-89 s of nothing is not that.
- "the mechanism is the documented FORCE_USB_BOOT one" → **DESCONHECIDO**.
  two survivors:
  1. Xiaomi's BL31 ignores SMC `0x82000043`, the flag was never set, and
     `set_usb_boot`/`reset` is independently broken in this build. Consistent
     with everything observed, including the fact that the flag *is* cleared
     by a power cycle (which would be a no-op if it were never set).
  2. the flag is set, the ROM enters USB, the handshake never completes, and
     the box falls through to power-off.
- the 100 ms Xiaomi splash in trial 1 is a real data point and it is awkward:
  the BootROM is BL1 and has no splash. a Xiaomi logo means BL33 or the kernel
  ran, so the box got past the ROM. that argues against "died in the ROM" and
  slightly for survivor 1. trial 2 showed a black screen instead, so even the
  splash is not consistent across resets.
- recovery was a power cycle every single time, as the "warm reboot keeps the
  order, cold reset clears it" note predicted. **no damage**: Android came
  back normal after all three, and `unlocked: yes` / `secure: no` were never
  touched.
- **do not run this again.** three trials, three power cycles, zero USB
  devices, no new information. anything further needs either a different
  trigger (physical strap, HDMI dongle) or a different order of operations that
  nobody has a reason to guess at on a box that currently boots fine.

## 3. the transition questions (phase 3)

**A. is there a read-only command that reveals how U-Boot treats
`reboot_mode`?**
`get_rebootmode` (cmd_reboot.c:181) exists in the family and does exactly that
, it decodes `AO_SEC_SD_CFG15[15:12]` into `reboot_mode` (cmd_reboot.c:34-119,
values in `arch/arm/include/asm/reboot.h:41-51`). but it only writes an env var
and prints to the console, and we proved in §2.2 that console output is
invisible. → command **CONFIRMED in GXL, not confirmed on aquaman**, and even
if present it is **unusable** for this task. no workaround exists.

**B. is there a mechanism to select USB as the next boot without writing
eMMC?**
Yes, two, both register/RAM only:
- `set_usb_boot 2` (FORCE_USB_BOOT) → SMC `0x82000043` → BL31 sets
  `P_AO_SEC_GP_CFG7[31]` → next reset the ROM comes up in USB download.
  CONFIRMED in GXL (cmd_reboot.c + bl31_apis.c + aml_v2_burning.c reading the
  very same bit), **not confirmed on aquaman**, not tested.
- `update <t>` → BL33 enumerates 1b8e:c003 right now, no reboot needed.
  **CONFIRMED no aquaman** (§2.4), descriptor match in §2.5.
Neither writes eMMC.

**C. is there a variable already persisted on the device that forces USB on the
next reboot?**
Cannot be answered. the env is on eMMC, `printenv` output is invisible (§2.2),
and the only env-reading getvar in the family is `current-slot`, which on this
device faults instead of answering (§1.2). the reference env *does* carry
`usb_burning=update 1000` and `try_auto_burn=update 700 750`
(gxl_skt_v1.h:96-98) and they are triggered by `reboot_mode=update`, but
whether Xiaomi shipped them is **DESCONHECIDO**.

**D. is there a command that only prepares the next stage for USB and waits
for the host?**
That is literally what `do_v2_usbtool` does: it sets the work mode, arms the
`identifyWaitTime` env, powers the USB PHY in device mode and blocks in
`usb_pcd_irq()` until the host enumerates it or the timeout expires
(optimus_core.c:40-61, usb_pcd.c:218-268). **CONFIRMED no aquaman** in §2.4,
including the "waits for the host" part: the device sat in `1b8e:c003` for
100 s+ with a host present. same for `set_usb_boot 2`, which arms the ROM for
the *next* boot, still untested.

**E. what does `update` mean in this build?**
**1. USB burning.** not recovery, not a script, not the TFTP helper.
- the `update` *command* is `do_v2_usbtool`, "Enter v2 usbburning mode"
  (optimus_core.c:57-61);
- `common/update.c` is a different thing entirely: it is the TFTP/FIT
  auto-update helper (`update_tftp`, called from `common/main.c:78`) and it
  registers **no** `U_BOOT_CMD`, so there is no name clash;
- there is an env *variable* also called `update`
  (gxl_skt_v1.h:161-172) which is a shell script that starts with
  `run usb_burning`, i.e. `update 1000`. that is why `run update` and
  `update 1000` both lead to USB burning.
- the fastboot command `update:` (with the colon) is a *third* thing: it is
  `cb_download` (f_fastboot.c:727-730), a plain download alias.

Determined by code first, then confirmed by observation in §2.4/§2.5: the
device enumerated `1b8e:c003` with the v2 burning descriptors, which only
`do_v2_usbtool` can produce.

## 4. BL33 vs BL1 (phase 4)

### 4.1 the round-2 VID:PID assumption is wrong

`reports/round2-update-test/report.txt:28` states "1b8e:c003 = WorldCup/BootROM
GX". false as a discriminator:

| | BL33 U-Boot v2 burning | BL1 BootROM |
|---|---|---|
| VID:PID | `1b8e:c003` (`v2_usb_tool/usb_pcd.c:24-25`) | `1b8e:c003` |
| bcdDevice | `0x0007` (usb_pcd.c:49) | different |
| iManufacturer / iProduct / iSerial | **0 / 0 / 0**, no string descriptors at all (usb_pcd.c:50-52, config iConfiguration=0 at :75) | has strings |
| interface | 1 iface, class FF/00/00, 2 bulk EP, 512 B MPS, MaxPower 1 (2 mA) | n/a |
| protocol | vendor control requests + bulk: `0x20` identify, `0x36` nop, `0x01` write, `0x11` write-large, `0x05` run | same wire protocol family, that is the point of the compatibility |

the tiny_usbtool uses the same pair too
(`aml_tiny_usbtool/usb_pcd.c:35-36`). so `1b8e:c003` on the bus means "an
Amlogic USB device-mode target", nothing more.

### 4.2 how to actually tell them apart, from the code

- **stage byte in the identify answer.** U-Boot answers the control request
  `AM_REQ_IDENTIFY_HOST` (0x20) with exactly 4 bytes
  `{USB_ROM_VER_MAJOR, USB_ROM_VER_MINOR, USB_ROM_STAGE_MAJOR, USB_ROM_STAGE_MINOR}`
  = `{0, 8, 0, 16}` for GXL (usb_pcd.c:522-537, platform.h:105-112, with
  `16 // IPL = 0, SPL = 8, TPL = 16`). BootROM BL1 does not answer a control
  request; it answers a bulk read of 8 bytes with the ROM version string
  (`GXL:BL1:<ver>:<ver>`). a host that reads 4 bytes of `{0,8,0,16}` is talking
  to U-Boot.
- **timing.** BootROM USB exists ~instantly after reset, before BL2/BL30/BL31
  run. on this device BL33 fastboot shows up at +4 s after
  `adb reboot bootloader` (round-2 report:50). anything appearing in the first
  second or two is BL1.
- **no fastboot interface.** if `fastboot devices` shows the device, it is
  BL33. neither BL1 nor the optimus gadget exposes ff/42/03.

### 4.3 can BootROM be selected without a dongle

in software, via the same register the ROM itself checks:
`set_usb_boot 2` → SMC → BL31 sets `P_AO_SEC_GP_CFG7[31]` → reset → ROM boots
from USB. no eMMC write, no physical access, no HDMI dongle. the cost is that
the flag survives warm reboot, so recovery needs a power cycle (or
`set_usb_boot 1` from inside U-Boot before the reset, which does not help if
you already lost fastboot).

status on aquaman: **tested three times, never worked** (§2.6). the change in
boot behaviour is real and reproducible, the BootROM USB device is not. so the
honest answer to phase 4 is:

- the *mechanism* is CONFIRMED in the GXL reference code. whether it is
  functional in this particular build is UNKNOWN, and three attempts to find
  out produced a dead box rather than a USB device.
- the reset mode was ruled out as the variable, so there is no cheap retry
  left. the two remaining explanations (BL31 ignoring the SMC, or a failed ROM
  USB handshake) are not separable from the host side with the tools here.
- for BootROM USB on this stick, the route that works is the physical one
  (HDMI `boot@USB` dongle or strap). that is not a claim about Amlogic in
  general, it is what the evidence on this device supports.

## 5. verdict

**Conclusion 1, confirmed: there is a U-Boot -> USB path on the aquaman that can
be triggered from the host with no extra hardware.**

### the working path

1. stage: BL33, U-Boot fastboot at `18d1:0d02`, gadget serving ff/42/03.
2. command: `fastboot oem update 5000`.
3. what it does: `run_command("update 5000")` → `do_v2_usbtool` → sets
   `OPTIMUS_WORK_MODE_USB_UPDATE`, arms `identifyWaitTime`, tears down the
   fastboot gadget, re-inits the USB PHY in device mode with the v2 burning
   descriptors and blocks in `usb_pcd_irq()`.
4. next stage: **U-Boot BL33 USB burning (optimus v2)**. same VID:PID as the
   BootROM but demonstrably not the BootROM (§2.5).
5. success detection on the PC: `18d1:0d02` disappears and `1b8e:c003` appears
   within ~400 ms, with `bcdDevice 0.07`, no string descriptors, MaxPower 2 mA,
   endpoints 0x81/0x02. run a bus watcher **before** the command.
6. return to normal without writing anything: unplug the stick from USB and
   plug it back. there is no clean in-band exit, the fastboot session is gone
   the moment the command runs.

### what this is not

this is **not** BootROM. it is the U-Boot-level Amlogic factory burning mode
(the one the `aml_update_pkg` / "Amlogic USB Burning Tool" drives). reaching the
actual BL1 BootROM needs `set_usb_boot 2` plus a reset, and that was tried three
ways and produced no USB device at all (§2.6), or the physical strap.

### everything that stayed unknown

- why the `set_usb_boot` path fails: a BL31 that ignores SMC `0x82000043`
  versus a ROM that enters USB and never completes the handshake.
  **DESCONHECIDO**, and not separable from the host side with what is here.
- the U-Boot env contents: permanently unreadable from the host (§2.2).
- whether `usb_burning=update 1000` exists in the aquaman env (it would give a
  1 s automatic window on `reboot_mode=update`): **DESCONHECIDO**.

## 6. residual risk

- `update` is the only Amlogic command in this family that can start a write
  flow. we entered the mode twice and sent no protocol commands, so no write was
  possible. the safe rule going forward: never leave a real Amlogic burning tool
  attached while this command is in flight.
- `set_usb_boot 2` is the one that needs a warning label. three trials, three
  dead boxes, three manual power cycles, zero new information. **do not run it
  again.** the whole point of running the three reset variants was to rule out
  the reset mode as the variable, and it did: that closes the cheap retries.
- the fastboot session on this build is fragile: one blocking `oem` command
  (`sleep 3`) killed it (§2.3). every future test needs a power-cycle plan and a
  USB bus monitor running *before* the trigger.
- the round-2 "adb reboot update was negative for 1b8e:c003" evidence is weak
  and should be treated as a missed 1 s window, not a refutation. §2.4 shows the
  window really is about 370 ms wide when triggered from fastboot.
- nothing in this round wrote to eMMC, the env, the OTP or any partition. the
  only lasting state change is the one-shot `P_AO_SEC_GP_CFG7[31]` flag, which
  the power cycle already cleared. device is back on Android, unlocked, no
  writes.
