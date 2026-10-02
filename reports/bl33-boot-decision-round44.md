# BL33 round 44: which boot decisions change with already-demonstrated primitives

date: 2026-10-02. offline + synthesis of prior live work. no new writes,
no RUN/MODIFY/reset/update/flash in this session. no secure-boot bypass attempt.

base:
- image `reports/round14-bl33-persist/bl33-37e18000.bin` (base 0x37e18000,
  `[0x37e18000,0x37ff0000)`, sha256 `664fb34a…`), capstone disasm this session.
- inherited live: round39 (WRITE 0x01), round40 (double consumption), round41 (116-cmd
  map), round42 (false->true), round43 (test->true, env print->true,
  FILL 0x03, RUN wedge, live env in `reports/round43-campaign/hunt_33e18000_32k.bin`).
- reference: round35 (mode 7 = `setenv bootdelay -1`, gate `cmn w19,#1`).

session question: what is the smallest reversible RAM change that alters BL33
boot behaviour before secure boot?

answer: FILL 1 pair (or WRITE 8B) in slot `test` (`0x37f62180` low
`0x74->0x6c`, high already zero) redirecting `test 0x37e36774` to
`true 0x37e3676c`. 1 effective byte, oracle `test 1 = 2` failed:->success,
restore done (P2 round43). every `if test` in storeboot/switch/init
changes together, before the first `bl aml_sec_boot_check`.

## 1. Exp1: bootdelay as first gate

`main_loop 0x37e22328`: `preboot` (0x37e22354) runs before
`bootdelay_process 0x37e24480` (0x37e22358), which runs before
`autoboot_command 0x37e244dc` (0x37e2235c).

`bootdelay_process 0x37e24480` (disasm this session):
`0x37e2448c add x0,#0xfbb` ("bootdelay") -> `bl env_get 0x37e58920` ->
`cbz` -> `simple_strtoul 0x37eac374` base 10 -> `str w19,[0x37f723d8]`.
without env, `0x37e244b0 mov w19,#1`.

`autoboot 0x37e244dc`:
`0x37e244f8 ldr w19,[0x37f72000+0x3d8]` -> `0x37e24500 cmn w19,#1` ->
`0x37e24504 b.eq 0x37e245f4` (skip bootcmd, falls into cli_loop).

| field | address | original value | consumer | deciding instruction |
|---|---|---|---|---|
| `bootdelay` live env | `0x33e1daa0` (`hunt_33e18000_32k.bin`) | `"1"` | `bootdelay_process` | `0x37e24498 cbz` / strtoul / default `mov w19,#1` |
| `bootdelay` default rodata | `0x37eb65b6`, name `0x37ebffbb` | `"1"` | same | same |
| `stored_bootdelay` u32 | `0x37f723d8` | `1` (`-1` = `0xffffffff` after mode 7) | `autoboot_command` | `0x37e24500 cmn` + `0x37e24504 b.eq` |
| `bootcmd` live | `0x33e1da88` | `"run storeboot"` | autoboot tail (`b run_command_list`) | `0x37e24508 cbz x21` |

copied (string -> u32), not direct. writer of `-1`: `0x37e60618`
(`setenv bootdelay,"-1"`, mode 7 only). format: ASCII decimal.
status: code OFFLINE_ONLY; live value `1` HARDWARE_OBSERVED in hunt dump.
poke NOT PROVEN (not executed).

## 2. Exp2: flow-change oracle

bulkcmd 512B already discriminates by return code, no printenv/RUN/MODIFY/reset.
baselines round43, same session:

```
failed: : false, `test 1 = 2`, `test`, `env print foo`, `run foo1234`, unknown
success : true, `test 1 = 1`, echo, version, help, ?, printenv, `env print`
```

recommended pair: `test 1 = 2` vs `test 1 = 1`. binary, no output, no
storage. `false`/`true` is the backup (round42). `echo`/`version`/`help`
discarded as discriminator: all `success`. `mmc info` FLAKY, do not use.
`get_rebootmode` as oracle: PROBABLE, no recorded baseline.

## 3. Exp3: reboot_mode

reader `0x37e60478`: `ldr SD_CFG15 0xc810023c` (`0x37e604a4/a8/ac`),
`ubfx [15:12]` (`0x37e604b0`), jump via table `0x37ebe910`
(`ldrb` + `add sxtb #2` + `br`). 15 entries (round35): 0 cold_boot,
1 normal, 2 factory_reset, 3 update, 4 fastboot, 5 suspend_off, 6 hibernate,
7 bootloader, 8 shutdown_reboot, 9 rpmbp, 10/14 recovery_quiescent,
11 crash_dump, 12 kernel_panic, 13 watchdog_reboot, >14 charging.

`switch_bootmode` (`0x37eb6eab`) has 6 branches; `bootloader` is not one:

```
7 bootloader -> no branch -> only setenv bootdelay -1 -> skip bootcmd -> cli_loop
4 fastboot   -> storeargs; fastboot (gadget 18d1:0d02)
0 cold_boot  -> storeargs, follows bootcmd
2/3          -> recovery_from_flash / update
```

RAM equivalent: live env `reboot_mode` (e.g. value `0x33e1e1df` in that
session). heap `0x33e1xxxx`, varies per boot; re-hunt with
`mread 0x33e18000 32k` + grep. never write `0xc810023c`.

## 4. Exp4: storeboot

rodata script `0x37eb71f2` (live in arena). live offsets this session:

| var | live value | writer | consumer/comparison | effect |
|---|---|---|---|---|
| `active_slot` | `0x33e1d6da`=`normal` | `get_valid_slot 0x37e2bb7c` | `test != normal`, `= _a`, `= _b` (`test 0x37e36774`) | `slot_suffix`, `root=mmcblk0p23/24` |
| `avb2` | `0x33e1d6e6`=`1` | `get_avb_mode 0x37e2b820` | `test = 0` | picks `root=` when 0 |
| `system_mode` | no scalar in dump | `get_system_as_root_mode 0x37e2b7ac` (`setenv 0/1`, strs `0x37ec2dcd`,`0x37eccb38`,`0x37ecdd94`) | `test = 1` at head | `fs_type ro…` + `run storeargs` |
| `boot_part` | `0x33e1d731`=`boot` | default | `imgread kernel ${boot_part} ${loadaddr}` (`0x37e356d0`) | which partition loads |
| `loadaddr` | `0x33e1e0ef`=`1080000` | default | `imgread` dst + `bootm` src (`0x37e24c00`) | where it lands / where it boots from |
| `bootargs` | `0x33e1d73f` 832B | `storeargs` + `bootm` | concatenation | kernel cmdline |
| `upgrade_step` | `0x33e1f1d8`=`2` | state | `itest == 3` (`0x37e2b348`) in `upgrade_check`/`recovery_from_flash` | `==3` -> `run update` |

`test`/`itest` is the common point. nothing modified here.

## 5. Exp5: boot-goal redirects

consumer `0x37e5f6e8 ldr x4,[x19,#0x10]` + `0x37e5f6fc blr x4` (64-bit).

| candidate | original -> alt | slot | effect | risk | oracle | status |
|---|---|---|---|---|---|---|
| `test` idx100 | `0x37e36774`->`true 0x37e3676c` | `0x37f62180` | every `if test` becomes true | low | `test 1 = 2` -> success | HARDWARE_REPRODUCED P2 |
| `run` idx84 | `0x37e5ea04`->`true` | `0x37f61e80` | `run` becomes no-op | medium (breaks boot without restore) | `run foo1234` -> success | PROBABLE, not executed |
| `get_rebootmode` idx51 | `0x37e60478`->`true` | `0x37f61850` | `reboot_mode`/`bootdelay` freeze | medium | no baseline | NOT PROVEN |
| `fdt` idx49 | `0x37e2852c`->`true` | `0x37f617f0` | DTB edit becomes no-op | low alone | weak | NOT PROVEN |

## 6. Exp6: final barrier

`aml_sec_boot_check 0x37e19ea8` = `mov x0,#0x820000ff` + `smc #0 0x37e19ed8`.
`bl` census to it (disasm this session): bootm 2 (`0x37e24cf0`,`0x37e24f90`),
unpackimg/imgread 3 (`0x37e35ec4`,`0x37e3623c`,`0x37e36340`), fdt 2,
store 4, query/efuse 4. `usbboot 0x37e371f0` 0 calls (descriptor/print only,
does not boot kernel). `ext4load`/`fatload` 0 calls on load, but they do not jump to
kernel; boot requires `bootm`.

```
path               loads image?  passes SMC?  evidence
bootm              yes            yes           2 bl + smc 0x820000ff
unpackimg/imgread  yes (0x37e351f8) yes         3 bl
fdt                no (edits DTB) yes (subpath) 2 bl
store              yes            yes           4 bl
ext4load/fatload   yes (file->RAM) no on load, yes on boot via bootm  stubs 8B
usbboot            no             no            print only
update/usb_burn    flash, no boot n/a           out of scope
```

no path loads-and-executes without `aml_sec_boot_check`. static check;
`bootm` never executed live.

## 7. ranking

### Path 1 — HARDWARE_REPRODUCED

```
FILL 1 pair (or WRITE 8B) -> test 0x37f62180 -> true
  -> ifs in storeboot/switch/init decide differently -> before SMC
  -> oracle failed:->success -> restore -> failed:
```

### Path 2 — PROBABLE

```
WRITE/FILL -> live env 0x33e1xxxx or run/get_rebootmode slot
  -> script/boot decision changes before bootm
```

read-only location OFFLINE_ONLY; poke NOT PROVEN.

### Path 3 — limit, BLOCKED

```
WRITE/FILL -> RUN 0x05 -> USB wedge (T7/T8 round43)
           -> MODIFY 0x04 -> dead session
handler -> SMC 0x820000ff -> secure boot holds
```

no arbitrary exec, no persistence (reboot clears).

## 8. ledger

HARDWARE_REPRODUCED: WRITE 8/16/64B, scattered FILL, redirects
false/test/env-print->true + double restore, oracle failed:/success,
page-table descriptors compatible with RWX for idx0/1 (active state not
demonstrated), cmd_tbl live==offline, live env located (`bootdelay 1`,
`bootcmd run storeboot`, `upgrade_step 2`, `active_slot normal`, `avb2 1`).
OFFLINE_ONLY: gate `cmn/b.eq`, table `0x37ebe910`, scripts
storeboot/switch/init/upgrade_check, barrier `bootm->sec_check->SMC`.
PROBABLE: `test->true` changes boot decision (mechanism proven, `run
storeboot` never executed live for risk reasons); live env storage is
writable, semantic consumption of the mutation by the script is not demonstrated.
NOT PROVEN: SMC bypass, exec via RUN, any persistence.

repro offline:
`python3 -c` + capstone over the bin (bootdelay_process, autoboot, do_bootm,
sec_check, get_rebootmode); `grep` the hunt `reports/round43-campaign/hunt_33e18000_32k.bin`.
rules: full command only + drain `0x33`; `mread` 8 flaky (use `0x02` or
`>=0x40`); 0x04/0x05 last or never without UART; never saveenv/flash.
