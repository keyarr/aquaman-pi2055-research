# BL33 map round 41: live cmd_tbl + pointers + gd/env + E2-like targets

date: 2026-10-01. offline over `reports/round14-bl33-persist/bl33-37e18000.bin`
(sha256 `664fb34a...`, `[0x37e18000,0x37ff0000)`), crossed with live E0 from
round40 (`reports/round40-optimus-consumption/01_cmdtbl_mread.txt`: 0 diffs).
no write in this step. no `0x05`, cmd_tbl, pointer, pagetable,
code, eMMC, BL31 touched here.

inherited live context: stage `00 07 00 10` (TPL/BL33), WRITE_MEM 0x01 HARDWARE_REPRODUCED
round39, double consumption HARDWARE_REPRODUCED round40 (arena via upload + .rodata string via
bulk reply, both with restore).

## 0. answer

```text
cmd_tbl live  0x37f60eb0..0x37f62470, 116 entries, stride 0x30, E0 0 diffs
consumer      0x37e5f6e8 ldr x4,[x19,#0x10] + 0x37e5f6fc blr x4, 64-bit
handlers      116/116 inside BL33, 4 duplicated groups (legitimate alias)
func slots    2597 qwords -> BL33, 39 clusters >=4 slots
gd/env live   default .rodata at ~0x37eb65a0; live env in BSS 0x37f8xxxx, no fixed offline offset
E2-like       string content usage/help of echo/version/false + maxargs/repeatable, never pointer
8B flow       only at [entry+#0x10] cmd and sub-table +0x10; rest is data or lookup DoS
next          E2-bis in help/version string; maxargs in 2nd; flow stays vetoed
```

## 1. cmd_tbl: read-only reconstruction

live method (E0, round40, read-only):

```text
tools/optimus.py mread 0x37f60eb0 0x15c0 > /tmp/opencode/cmd_tbl_live.bin
# 0x15c0 = 5568 = 116 * 0x30; compare with offline bin slice
tools/optimus.py mread 0x37e5f664 0x100  # call_cmd, consumer
```

struct: `.src/u-boot-khadas/include/command.h:30`
`+0x00 name ptr64, +0x08 maxargs u32, +0x0c repeatable u32, +0x10 cmd ptr64,`
`+0x18 usage ptr64, +0x20 help ptr64, +0x28 complete ptr64`.
`0x37f60fd0` is not base, it is entry 6 bootm. `0x37f60eb0` is entry 0
aml_sysrecovery. the old "80 slots" were a short-name filter that breaks
on `ddr_dqs_window_step`.

table (idx | addr | name | handler | max | rep):

| 0 | 0x37f60eb0 | aml_sysrecovery | 0x37e8387c | 3 | 0 |
| 1 | 0x37f60ee0 | amlmmc | 0x37e2f064 | 6 | 1 |
| 2 | 0x37f60f10 | avb | 0x37e63a64 | 2 | 0 |
| 3 | 0x37f60f40 | bcb | 0x37e2b3e8 | 2 | 0 |
| 4 | 0x37f60f70 | bmp | 0x37e277f0 | 5 | 1 |
| 5 | 0x37f60fa0 | boot_cooling | 0x37e56860 | 5 | 0 |
| 6 | 0x37f60fd0 | bootm | 0x37e24c00 | 64 | 1 |
| 7 | 0x37f61000 | chipid | 0x37e634bc | 1 | 1 |
| 8 | 0x37f61030 | clkmsr | 0x37e57ac8 | 2 | 1 |
| 9 | 0x37f61060 | cvbs | 0x37e62b44 | 64 | 1 |
| 10 | 0x37f61090 | d2pll | 0x37e3a9e8 | 5 | 1 |
| 11 | 0x37f610c0 | dcache | 0x37e27ba4 | 2 | 1 |
| 12 | 0x37f610f0 | ddr_dqs_window_step | 0x37e40c08 | 6 | 1 |
| 13 | 0x37f61120 | ddr_spec_test | 0x37e3e098 | 8 | 1 |
| 14 | 0x37f61150 | ddr_sram_tune | 0x37e3aaf4 | 5 | 1 |
| 15 | 0x37f61180 | ddr_test_ac_bit_setup_hold_windo | 0x37e41468 | 6 | 1 |
| 16 | 0x37f611b0 | ddr_test_cmd | 0x37e56170 | 30 | 1 |
| 17 | 0x37f611e0 | ddr_test_copy | 0x37e3d1b0 | 7 | 1 |
| 18 | 0x37f61210 | ddr_test_data_bit_setup_hold_win | 0x37e41f58 | 6 | 1 |
| 19 | 0x37f61240 | ddr_test_tune_dqs_env | 0x37e3cc8c | 30 | 1 |
| 20 | 0x37f61270 | ddr_tune_aclcdlr_step | 0x37e46964 | 7 | 1 |
| 21 | 0x37f612a0 | ddr_tune_ddr_ac_acbdlr_ck | 0x37e47b20 | 6 | 1 |
| 22 | 0x37f612d0 | ddr_tune_ddr_ac_aclcdlr | 0x37e471dc | 6 | 1 |
| 23 | 0x37f61300 | ddr_tune_ddr_ac_bdlr | 0x37e482c8 | 7 | 1 |
| 24 | 0x37f61330 | ddr_tune_ddr_vref | 0x37e48f4c | 7 | 1 |
| 25 | 0x37f61360 | ddr_tune_dqs | 0x37e40148 | 6 | 1 |
| 26 | 0x37f61390 | ddr_tune_dqs_step | 0x37e40c08 | 7 | 1 |
| 27 | 0x37f613c0 | ddrft | 0x37e3abf4 | 5 | 1 |
| 28 | 0x37f613f0 | ddrtest | 0x37e3d540 | 5 | 1 |
| 29 | 0x37f61420 | ddrtest_gate | 0x37e42a30 | 7 | 1 |
| 30 | 0x37f61450 | ddrtest_gx_crosstalk | 0x37e3e640 | 5 | 1 |
| 31 | 0x37f61480 | ddrtest_gxtvbb_crosstalk | 0x37e3f31c | 5 | 1 |
| 32 | 0x37f614b0 | defenv_reserv | 0x37e58f10 | 64 | 0 |
| 33 | 0x37f614e0 | dtimg | 0x37e36508 | 64 | 0 |
| 34 | 0x37f61510 | echo | 0x37e28000 | 64 | 1 |
| 35 | 0x37f61540 | efuse | 0x37e56804 | 5 | 1 |
| 36 | 0x37f61570 | efuse_user | 0x37e72ef0 | 5 | 1 |
| 37 | 0x37f615a0 | emmc | 0x37e2f0ec | 4 | 1 |
| 38 | 0x37f615d0 | env | 0x37e57d6c | 64 | 1 |
| 39 | 0x37f61600 | exit | 0x37e280e4 | 2 | 1 |
| 40 | 0x37f61630 | ext4load | 0x37e28124 | 7 | 0 |
| 41 | 0x37f61660 | ext4ls | 0x37e2812c | 4 | 1 |
| 42 | 0x37f61690 | ext4size | 0x37e2811c | 4 | 0 |
| 43 | 0x37f616c0 | false | 0x37e36764 | 64 | 1 |
| 44 | 0x37f616f0 | fastboot | 0x37e3a840 | 1 | 0 |
| 45 | 0x37f61720 | fatinfo | 0x37e2814c | 3 | 1 |
| 46 | 0x37f61750 | fatload | 0x37e2813c | 7 | 0 |
| 47 | 0x37f61780 | fatls | 0x37e28144 | 4 | 1 |
| 48 | 0x37f617b0 | fatsize | 0x37e28134 | 4 | 0 |
| 49 | 0x37f617e0 | fdt | 0x37e2852c | 255 | 0 |
| 50 | 0x37f61810 | get_avb_mode | 0x37e2b820 | 1 | 0 |
| 51 | 0x37f61840 | get_rebootmode | 0x37e60478 | 1 | 0 |
| 52 | 0x37f61870 | get_system_as_root_mode | 0x37e2b7ac | 1 | 0 |
| 53 | 0x37f618a0 | get_valid_slot | 0x37e2bb7c | 2 | 0 |
| 54 | 0x37f618d0 | gpio | 0x37e2a204 | 4 | 0 |
| 55 | 0x37f61900 | gpt | 0x37e2e9b8 | 64 | 1 |
| 56 | 0x37f61930 | guid | 0x37eab688 | 64 | 1 |
| 57 | 0x37f61960 | hdmitx | 0x37e6141c | 64 | 0 |
| 58 | 0x37f61990 | help | 0x37e26644 | 64 | 1 |
| 59 | 0x37f619c0 | i2c | 0x37e2a4e4 | 6 | 1 |
| 60 | 0x37f619f0 | icache | 0x37e27b18 | 2 | 1 |
| 61 | 0x37f61a20 | img_osd | 0x37e6225c | 5 | 1 |
| 62 | 0x37f61a50 | imgread | 0x37e356d0 | 5 | 0 |
| 63 | 0x37f61a80 | irblaster | 0x37e27c30 | 5 | 1 |
| 64 | 0x37f61ab0 | itest | 0x37e2b348 | 4 | 0 |
| 65 | 0x37f61ae0 | keyman | 0x37e74290 | 5 | 0 |
| 66 | 0x37f61b10 | keyunify | 0x37e73c84 | 64 | 1 |
| 67 | 0x37f61b40 | loadb | 0x37e2c1a0 | 3 | 0 |
| 68 | 0x37f61b70 | loadx | 0x37e2c1a0 | 3 | 0 |
| 69 | 0x37f61ba0 | loady | 0x37e2c1a0 | 3 | 0 |
| 70 | 0x37f61bd0 | mmc | 0x37e2ca3c | 7 | 1 |
| 71 | 0x37f61c00 | mmcinfo | 0x37e2cbf0 | 1 | 0 |
| 72 | 0x37f61c30 | monitor_bt_cmdline | 0x37e63e44 | 1 | 1 |
| 73 | 0x37f61c60 | open_scp_log | 0x37e60864 | 2 | 1 |
| 74 | 0x37f61c90 | osd | 0x37e61da0 | 7 | 1 |
| 75 | 0x37f61cc0 | printenv | 0x37e57ea8 | 64 | 1 |
| 76 | 0x37f61cf0 | query | 0x37e56224 | 5 | 2 |
| 77 | 0x37f61d20 | ? | 0x37e26644 | 64 | 1 |
| 78 | 0x37f61d50 | read_temp | 0x37e571f8 | 5 | 0 |
| 79 | 0x37f61d80 | reboot | 0x37e60654 | 2 | 0 |
| 80 | 0x37f61db0 | reset | 0x37e21684 | 1 | 0 |
| 81 | 0x37f61de0 | ringmsr | 0x37e57afc | 2 | 1 |
| 82 | 0x37f61e10 | rpmb_state | 0x37e57b4c | 64 | 0 |
| 83 | 0x37f61e40 | rsvmem | 0x37e62e84 | 2 | 0 |
| 84 | 0x37f61e70 | run | 0x37e5ea04 | 64 | 1 |
| 85 | 0x37f61ea0 | saveenv | 0x37e57d3c | 1 | 0 |
| 86 | 0x37f61ed0 | sdc_burn | 0x37e80b74 | 5 | 0 |
| 87 | 0x37f61f00 | sdc_update | 0x37e7f90c | 5 | 0 |
| 88 | 0x37f61f30 | set_active_slot | 0x37e2bd60 | 2 | 1 |
| 89 | 0x37f61f60 | set_trim_base | 0x37e56d40 | 5 | 1 |
| 90 | 0x37f61f90 | set_usb_boot | 0x37e607e8 | 2 | 0 |
| 91 | 0x37f61fc0 | setenv | 0x37e58470 | 64 | 0 |
| 92 | 0x37f61ff0 | setkeys | 0x37e219f0 | 1 | 1 |
| 93 | 0x37f62020 | showvar | 0x37e22aa8 | 64 | 1 |
| 94 | 0x37f62050 | silent | 0x37e59300 | 2 | 0 |
| 95 | 0x37f62080 | sleep | 0x37e2c9b8 | 2 | 1 |
| 96 | 0x37f620b0 | store | 0x37e33900 | 64 | 1 |
| 97 | 0x37f620e0 | systemoff | 0x37e6084c | 2 | 1 |
| 98 | 0x37f62110 | tee_log_level | 0x37e63534 | 64 | 0 |
| 99 | 0x37f62140 | temp_triming | 0x37e56d80 | 5 | 1 |
| 100 | 0x37f62170 | test | 0x37e36774 | 64 | 1 |
| 101 | 0x37f621a0 | true | 0x37e3676c | 64 | 1 |
| 102 | 0x37f621d0 | ui | 0x37e62580 | 9 | 1 |
| 103 | 0x37f62200 | unpackimg | 0x37e358e0 | 2 | 0 |
| 104 | 0x37f62230 | update | 0x37e78ff8 | 3 | 0 |
| 105 | 0x37f62260 | usb | 0x37e37310 | 5 | 1 |
| 106 | 0x37f62290 | usb_burn | 0x37e81efc | 5 | 0 |
| 107 | 0x37f622c0 | usb_update | 0x37e81f68 | 5 | 0 |
| 108 | 0x37f622f0 | usbboot | 0x37e371f0 | 3 | 1 |
| 109 | 0x37f62320 | uuid | 0x37eab688 | 64 | 1 |
| 110 | 0x37f62350 | version | 0x37e26688 | 1 | 1 |
| 111 | 0x37f62380 | vout | 0x37e62d0c | 64 | 1 |
| 112 | 0x37f623b0 | vpp | 0x37e602cc | 64 | 0 |
| 113 | 0x37f623e0 | vpu | 0x37e3a88c | 5 | 0 |
| 114 | 0x37f62410 | write_trim | 0x37e57518 | 5 | 0 |
| 115 | 0x37f62440 | write_version | 0x37e56d18 | 5 | 0 |

CONFIRMED: 116/116 handlers inside `[0x37e18000,0x37ff0000)`, 0 outside.
duplicates: `0x37e40c08` x2, `0x37eab688` guid+uuid, `0x37e26644` help+`?`,
`0x37e2c1a0` loadb/loadx/loady x3. alias, not corruption.
`complete` nonzero only in printenv/run/setenv = `0x37e5f0d0`.
classes: fastboot 44, boot 6 bootm, update 104, env 38/75/84/85/91,
memory 17/70/40/46/11/60, debug 34/58/110/64/100/54/59.

NOT HARDWARE_REPRODUCED live: today's `usage/help/complete`. `name/max/rep/cmd`
stable per E0; rest decided with same `mread`.

## 2. function pointers in 0x37e18000-0x37ff0000

offline method: all 8-aligned qwords falling in BL33, cluster
with gap <=0x40. 2597 slots, 39 clusters >=4. nothing written.

main ones, with role:

```text
0x37ee5bc0 mmc sub-table (info/read/write/erase..., stride 0x30, dispatcher 0x37e2ca3c)
0x37ee62f0 store sub-table (init/exit/read/write..., dispatcher 0x37e33900)
0x37ee70f8 env sub-table (default/delete/export/import/print/run/save/set, dispatcher 0x37e57d6c)
0x37f60cc0 bss state, 24 ptrs 0x37e9xxxx (storage/fastboot glue)
0x37f62550 usb/fastboot state (~34 slots, includes 0x37f62638)
0x37fbc940 mmc/block ops (24 ptrs 0x37e84xxx-0x37e85xxx)
0x37f5e478 cipher ops x4 (consumed at 0x37e73730/50/ec)
0x37ee2710 hook (blr x0 at 0x37e19848)
```

PROBABLE: same shape as main cmd_tbl (`find + ldr x4 + blr x4`).
NOT HARDWARE_REPRODUCED live: BSS/state values change per session (burning buf at
`~0x37f8a620` already proved this in E0). `.text/.rodata` stable.

## 3. gd/env/state

CONFIRMED: compiled default at `~0x37eb65a0`
(`bootcmd=run storeboot`, `bootdelay=1`, `baudrate=115200`, `preboot=...`).
this is `.rodata`, not the live env. side proof of live BSS: `0x37f8a638`
in persisted bin contains leftover of `upload mem 0x37800000...` from the
read session itself.

PROBABLE: `gd` just below `0x37e18000`, stack descending. live env at
`0x37f8xxxx`.

NOT HARDWARE_REPRODUCED: exact address of live `env_t`, live `bootargs`, fastboot
flags, `gd` pointer. read-only hunt, no write:

```text
tools/optimus.py mread 0x37f80000 0x10000 > /tmp/opencode/bss_live.bin
# grep bootdelay/bootargs in dump; never poke here in this step
```

## 4. E2-like targets (data, observable, restorable)

E2 round40: `0x37ed8794 failed:` via bulk reply, 4B write + trigger
`foo1234` + restore. shape: data read by BL33 + visible effect + restore.

candidates same family, all content (never pointer):

```text
0x37ec1479 echo args to console (usage echo, visible in help echo)
0x37ec0a40 alias for 'help' (? / help)
0x37ebfe66 Unknown command (invalid-command response)
0x37ec00de Sig Check (bootm path, read-only here)
0x37ebdcc0 U-Boot 2015.01... (banner version)
0x37ec738f do nothing, unsuccessfully (false)
maxargs/repeatable of echo/false/version (u32, relaxing check does not crash)
```

rule: touch string byte, never the qword pointing to it.
`[entry+#0x18/+0x20]` is pointer, out of this step even though 8B.

## 5. 8-byte flow, theory only

CONFIRMED mechanism at `call_cmd 0x37e5f664`: `x19=find_cmd`,
`0x37e5f6e8 ldr x4,[x19,#0x10]`, `0x37e5f6fc blr x4`, no mask in between.
8B at `[entry+#0x10]` swap the handler. same shape in mmc/store/env
sub-tables +0x10. round38 already closed that 32b `W` repeated x4 does not form
useful canonical pointer (`0x1020000010200000`, top16=0x1020).

PROBABLE: `[entry+#0x00]` swapped name ptr = lookup DoS
(`strncasecmp` fails first), not flow. `[+#0x18/+0x20]` = wrong string.
`[+#0x28]` complete = only autocomplete, 3 entries.

NOT HARDWARE_REPRODUCED (and vetoed in this step): any real swap of `cmd`,
sub-command, cipher/mmc ops, usb state, pagetable. map closes, write does not.

## 6. next experiment

1. safest for first 8B: string content `usage/help` of
   echo/version/false (e.g. `0x37ec1479`). printf consumes, restore = original
   bytes, no pointer/pagetable/code/eMMC.
2. best chance to change behavior without crash: `maxargs/repeatable`
   of harmless entry (false/echo). 8B cover both u32 together;
   raising `maxargs` only relaxes the `cmp` at `0x37e5f6b4`.
3. flow: `cmd_tbl[i].cmd +0x10` or sub-table `+0x10`. vetoed now.
4. best risk/return: E2-bis in `help`/`version`. minimal risk
   (rodata display-only), high return (2nd WRITE->consumption->restore proof
   in documented structure, without the 16 KiB collateral of ddr_test_copy).

real risk: do not touch BSS/env and pagetable; incomplete bulk (`upload` without
args) already dropped the gadget once with no write (round40 §4). only
complete command with drain via 0x33.

## 7. repro

```text
python3 tools/bl33_ctrl.py dump 0x37f60eb0  # offline neighborhood
python3 -c "import struct; d=open('reports/round14-bl33-persist/bl33-37e18000.bin','rb').read(); ..."
# table §1 generated from bin, handlers-inside + dups check by script, not by eye
```
