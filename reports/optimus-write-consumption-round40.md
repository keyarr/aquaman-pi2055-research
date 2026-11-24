# Optimus WRITE consumption round 40: BL33 consumed host-written bytes, twice

date: 2026-10-01. live, on device. BL33 in RAM, `1b8e:c003`, stage 16.
build: aquaman_9_PI_2055, U-Boot 2015.01. entry: `fastboot oem update 5000`.
base: round39 (`reports/optimus-write-mem-round39.md`) proved WRITE_MEM 0x01
in arena. this round proves consumption: BL33 read back via its own path,
not only 0x02 readback. detail: `reports/round40-optimus-consumption/`.

## 0. answer

```text
WRITE_MEM in arena: HARDWARE_REPRODUCED (round39, re-done E1 BEFORE)
consumption via memcpy upload (0x34+0x33): HARDWARE_REPRODUCED, E1, restore ok
consumption via .rodata reply (bulk): HARDWARE_REPRODUCED, E2, restore ok
cmd_tbl live == offline 116 entries: HARDWARE_REPRODUCED, E0, read-only
RUN_IN_ADDR / bootm / flash / eMMC: NOT TOUCHED
cmd_tbl / page table / BL31: NOT WRITTEN
```

## 1. E0 live map, read-only

probe 13 addresses in one session + mread 0x37f60eb0 0x15c0.
`00_e0_probe.txt`, `01_cmdtbl_mread.txt`.

```text
_start 0x37e18000, aml_sec_boot_check 0x37e19ea8, SMC 0x37e19ed8,
do_bootm 0x37e24c00, banner 0x37ebdcc0: same as offline
serialno 0x37edf398, product 0x37edf3b8: same
cmd_tbl 0x37f60eb0..0x37f62470, 5568B: 0 diffs vs offline
arena 0x37800000: zero, clean
burning buf ~0x37f8a620: live, changes every command by design
page table 0x37ff0000: descriptors, DO NOT TOUCH
```

correction: cmd_tbl base is 0x37f60eb0 (entry 0 aml_sysrecovery).
0x37f60fd0 is entry 6 bootm. 116 entries, stride 0x30, consumer
ldr x4,[x19,#0x10] at 0x37e5f6e8 + blr x4 at 0x37e5f6fc, 64b.
the old "80 slots" were a short-name filter that breaks on
ddr_dqs_window_step. round38 already closed this.

## 2. E1 arena loopback, restore ok

`02_e1_loopback.txt`. one session, one process, only 0x37800000 4B.

```text
BEFORE 0x02: 00 *16, PRE mread: 00 *16, match02=True
WRITE 0x01 <- a5 a5 5a 5a
AFTER 0x02: a5 a5 5a 5a ..., POST mread: a5 a5 5a 5a ...
RESULT: CONSUMPTION CONFIRMED via BL33 memcpy
RESTORE verify 0x02 OK, RESTORE mread verify OK
```

this rules out CPU-less USB alias: 0x02 and 0x33 agree.

## 3. E2 .rodata string display-only, restore ok

`04_e2_string.txt`. target 0x37ed8794 `failed:\0`, .rodata, aligned,
display-only, outside forbidden areas. safe trigger `foo1234`
(unknown, immediate error, no upload armed).

```text
BEFORE: 66 61 69 6c 65 64 3a 00, PRE trigger -> b'failed:'
WRITE 0x01 <- 46 58 41 58 ('FXAX')
MID readback ok, POST trigger -> b'FXAXed:'
RESTORE verify OK, trigger -> b'failed:' OK
```

the log says INCONCLUSIVE because of a wrong expected constant in the script
(`FAXXed:` vs `FXAXed:`). evidence is HARDWARE_REPRODUCED: reply followed
the written 4B and returned on restore.

## 4. wedge without write, warning

`03_bulk_probe.txt`. bulkcmd `upload` without args dropped 1b8e:c003
off the bus (Errno 19, disconnect in dmesg). `foo` alone is safe.
rule: only complete commands; `upload mem <addr> normal <size>` always
with drain via 0x33.

## 5. what this proves

HARDWARE_REPRODUCED:

* 0x01 writes and BL33 consumes via two independent paths
  (upload memcpy, bulk reply), with restore verified in both.
* live cmd_tbl equals offline, 116 entries, no write.
* incomplete bulk session drops the gadget even without write.

NOT HARDWARE_REPRODUCED:

* write inside code, cmd_tbl, page table. not attempted.
* flow alteration, RUN_IN_ADDR, secure boot bypass.
* persistence across reboot. session only.

## 6. honest next step

read-only survey of 64b pointers + live gd/env via 0x02/mread.
no write until the consumer map is closed.

## 7. risk

device at `1b8e:c003` stage 16 at the end of E2, verified with identify.
nothing persistent left: arena restored to zero, `failed:` restored.
do not leave host stuck on optimus; wait for timeout or power-cycle.
