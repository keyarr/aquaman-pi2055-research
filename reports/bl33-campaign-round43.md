# BL33 campaign round 43: sinks, handlers, redirects x3, FILL, RUN wedge

date: 2026-10-01. live, on device, stage `00 07 00 10` (TPL/BL33).
base: round39 (WRITE 0x01), round40 (double consumption), round41 (116 map),
round42 (false->true). no flash/eMMC/efuse touched. no persistent write
left (all with restore, remainder wiped by reboot).
sessions: S1 recon + T1/T2 + MODIFY-crash, S2 re-entry + P1/P2/P3 + RUN-wedge.

## 0. verdict

```text
L0 read-only            HARDWARE_REPRODUCED (0x02 + mread, cmd_tbl 0 diffs)
L1 arbitrary write      HARDWARE_REPRODUCED (0x01 8/16/64B; FILL 0x03 scattered)
L2 control-data         HARDWARE_REPRODUCED (round40 string; slots read)
L3 control-flow to code HARDWARE_REPRODUCED x3 (false->true, test->true, envprint->true)
L4 arbitrary BL33 exec  NOT (RUN jumps but wedges USB, no exec observed)
L5 secure boundary      NOT (SMC 0x820000ff intact)
L6/L7 root/persist      NOT
FILL_MEM 0x03           EXISTS, hardware-reproduced in arena (2nd write primitive)
MODIFY 0x04             handler alive but DESTRUCTIVE (kills session, no readback)
RUN_IN_ADDR 0x05        handler alive but WEDGES USB even for no-op + KEEP_POWER
sub-table redirect      HARDWARE_REPRODUCED (env print -> true, cross-table)
WRITE 64B               HARDWARE_REPRODUCED in 1 transfer
```

## 1. read-only recon (S1, one session)

```text
cmd_tbl 0x37f60eb0 0x15c0 mread: 0 diffs vs offline, sha 8c2f2b92...
call_cmd 0x37e5f664: ldr x4,[x19,#0x10] @0x37e5f6e8 + blr x4 @0x37e5f6fc, live==offline
handlers false/true/echo/version/help/run/bootm: live==offline (16-32B each)
mmc disp 0x37e2ca3c / store 0x37e33900 / env 0x37e57d6c: live==offline
mmc tab 0x37ee5bc0 14 entries (info..test), store 0x37ee62f0 14 (init..mbr),
  env 0x37ee70f8 8 valid (default..set, entry 8 garbage = end)
cipher ops 0x37f5e478 / block ops 0x37fbc940 / bss 0x37f60cc0 / usb 0x37f62550: live==offline
defenv 0x37eb65a0 bootcmd=run storeboot / banner / failed: string: live==offline
pagetable idx0 desc 0x411 idx1 0x20000411, AttrIdx 4 Normal-WB, AP 0 EL1-RW, XN 0
  => reconstructed descriptors for RAM 0x10200000 and BL33 0x37e18000 are compatible with RWX; active MMU state not demonstrated.
BSS 0x37f80000 16K: zero (and unstable: repeated mread timed out 1x)
0x37f84000: 34B sparse nonzero. 0x37f88000: 180B, contains
  0x37f8a388 'success' + 0x37f8a638 'upload mem ...' (residue of own commands)
0x37f60000: partition strings (pattern/Umagic/bootloader/AML_TABLE/fastboot_context)
  + blob 0x37f626e0+ (android log-spam, burning buffer, not env)
live env NOT located at 0x37f80000..0x37f83fff. hunt continues at 0x37f84000+.
```

bulk baselines (oracle failed:/success, sha 614bbb7c vs 1ca51e20):

```text
failed: false, test 1 = 2, test, env print foo, run foo1234, foo1234
success true, test 1 = 1, echo, version, help, ?, printenv, env print,
  mmc info/list/dev/rescan, store init/exit, env default -a
mmc info FLAKY: failed: in one session, success in another. do not use as discriminator.
false 1st bulk after reads times out 1x and passes on retry. harness needs retry+drain.
mread size 8 flaky (timeout 2x, retry passes). use >=0x40 for cross-check.
```

## 2. S1 battery: WRITE sizes + FILL + MODIFY-crash

```text
TEST T1-WRITE-8/16/64 TARGET 0x37800000 BEFORE zero MID == pattern AFTER zero RESTORE ok STATUS PASS x3
  => 0x01 accepts >=64B per transfer. 1 WRITE covers 1 cmd_tbl entry (0x30).
TEST T2-FILL TARGET arena BEFORE 0 MID 5a5aa5a5 (=0xA5A55A5A le, only low 4B) mread match True
  RESTORE ok STATUS PASS-FILL-EXISTS
  => 0x03 exists in live build. 2nd primitive: (addr,val) pairs 8B each, *(u32*)addr=val.
TEST T3-MODIFY op0 (mem=arena data=0x12345678) => Errno 19 disconnect on next rd.
  session dead. after ~40s stick at 2717:4e40 adb android. REBOOTED ALONE.
  => 0x04 serviced but DESTRUCTIVE (either crash or stall). opcode semantics NOT proven.
  do not repeat mid-session: leave for last.
```

detail: T1-8 MID wrote 0x37e3676c to the arena and the following mread-8
timed out (retry with 0x40 passed in T2). arena cross-check stays on 0x02 only.

## 3. S2 battery (fresh boot post-crash): P1/P2/P3 + RUN-wedge

arena clean post-reboot. slots at originals.

```text
TEST P1 TARGET 0x37f616d0 (false idx43) BEFORE 6467e337 (=0x37e36764)
  MODIFICATION <- 6c67e337 trigger false: BEFORE failed: AFTER success
  RESTORE orig, retrigger failed: STATUS PASS (re-confirms round42)
TEST P2 TARGET 0x37f62180 (test idx100 +0x10) BEFORE 7467e337 (=0x37e36774)
  trigger 'test 1 = 2': BEFORE failed: AFTER success (slot now true)
  RESTORE, retrigger failed: STATUS PASS (2nd main-table pair, generalizes)
TEST P3 TARGET 0x37ee71c8 (env print sub-slot +0x10) BEFORE a87ee537 (=0x37e57ea8)
  trigger 'env print foo': BEFORE failed: AFTER success (handler true cross-table)
  RESTORE, retrigger failed: STATUS PASS (1st sub-dispatcher redirect proof)
TEST T7 RUN_IN_ADDR 0x05 addr=0x37e3676c(true) flags=0x10 KEEP_POWER
  => Errno 5 I/O error in everything after. STATUS WEDGE.
TEST T8 RUN addr=0x0 flags=0x10 => already dead, SEND-EXC. ident dead.
post: 1b8e:c003 enumerated but deaf for 110s+ (descriptors via lsusb ok,
  zero vendor req responds). usb reset => gone from bus. needs physical power-cycle.
```

P3 is the main S2 finding: env sub-table has the same pattern
`ldr x4,[x0,#0x10]+blr x4` and the slot accepts a handler from another table.
compatible calling convention (cmdtp,flag,argc,argv).

## 4. sinks (static, capstone, 352 sites)

total `ldr xN,[xM,#off]` + `blr/br xN` delta<=32B same func: 352 (blr 351,
br 1) in 199 funcs. full list in subagent ses_f063e628 (archived).
main ones:

```text
cmd_tbl 0x37e5f664: [x19+#0x10] -> blr (main consumer)
mmc 0x37e2ca3c: [x19+#0x10] tab 0x37ee5bc0 stride 0x30 14 entries
store 0x37e33900: [x0+#0x10] tab 0x37ee62f0 14 entries
env 0x37e57d6c: [x0+#0x10] tab 0x37ee70f8 8 entries
imgread/avb/keyman/fdt/usb: same pattern via find_cmd + blr x4
cipher ops 0x37f5e478 (34 slots) consumed at 0x37e73730/50/ec
block ops 0x37fbc940 (24 ptrs 0x37e84xxx-0x37e85xxx)
bss 0x37f60cc0 (24 ptrs), usb state 0x37f62550/0x37f62638
hook 0x37ee2710 (blr x0 at 0x37e19848)
```

clusters >=4 slots (gap<=0x40): 39. dense regions 0x37ee59a8..67d0 (mmc+store),
0x37ee70f8..7b10 (env+heap), 0x37f60df8..24e0 (embedded cmd_tbl, 475 ptrs).

## 5. handlers by capability (static, detail ses_f0638c36)

```text
display-only, no storage/reset/smc (safe targets for redirect):
  true 0x37e3676c (mov w0,#0;ret), false 0x37e36764 (mov w0,#1;ret),
  echo 0x37e28000, version 0x37e26688, help/? 0x37e26644
execution/control: run 0x37e5ea04 (loop getenv+run_command), fastboot 0x37e3a840
  (enters USB loop), bootm 0x37e24c00 (SMC 0x820000ff via 0x37e19ea8 + run_command x2),
  usbboot/usb (strtoul+memset, boot path), fdt (RAM DTB edit), imgread (dispatcher)
memory: ddr_test_copy 0x37e3d1b0 (destructive benchmark, no flush), mmc/store
  (eMMC dispatchers), ext4load/fatload (file->RAM arbitrary, L2 memcpy)
state: env dispatcher, setenv (RAM, only persists with saveenv), saveenv (flash!),
  set_active_slot (slot flip), set_usb_boot (strtoul->SMC 0x82000043), get_rebootmode
crypto: avb, keyman, keyunify, efuse 0x37e56804 (SMC, OTP!), efuse_user (SMC L3, OTP!)
reset: reboot (SMC reset), reset 0x37e21684 (MMIO watchdog loop, never returns)
reuse as primitive: loadb/loadx/loady 0x37e2c1a0 (addr via argv + UART-store loop,
  best arbitrary-write as command); ddr_test_copy inner 0x37e3aea0 (clean copier
  if registers controllable); update/usb_burn/sdc_update (flash, do not use).
no handler calls smc directly in body; SMC only via callees
  (bootm, set_usb_boot, efuse*, reboot).
```

## 6. RUN_IN_ADDR (source + static + live)

tiny source (`usb_pcd.c`, NOT the BL33 stack, which is v2):
setup 0x05 only arms buf; complete: addr=(wValue<<16)+wIndex,
flags=*(u32*)OUT[0], if !(flags&0x10) power_off_phy(), unconditional fp().
WRITE 0x01: buf=(char*)addr direct. FILL 0x03: 8B pairs. MODIFY 0x04:
opcodes 0-7, 7 = `while(data--)*mem++=*mem2++` (memcpy!).
password: need_password=1/password_ok=0 at init, but live answers
`need_password=0` in identify => no gate at this stage. verify always-true for <=64B.
in BL33 binary: tiny path absent; only v2 (`v2_usb_tool/usb_pcd.c`,
strings BULKcmd/tplcmd/Enter v2 usbburning). pattern `(wValue<<16)+wIndex`
not found; KEEP_POWER 0x10 only as generic immediate.
live: 0x03 CONFIRMED, 0x04 disruptive, 0x05 wedge even with 0x10 on a no-op.
=> handler 0x05 exists but does NOT have the tame tiny semantics, or the jump
corrupts the USB return. next round needs UART + flag variants.
candidates for 1st RUN (when controlled): true/false (zero access, only prove
no-crash), version (print, needs UART to observe). help/echo as raw RUN
= PROBABLE data abort (garbage argv). do not use.

## 7. pagetable / code / env (static + live)

builder 0x37e19314: OA=i<<29, identity, TCR 0x300004516, MAIR ...ff440c0400.
only idx0,1 are Normal-WB RAM; rest Device. AP 0 (EL1 RW), XN 0 in all.
=> reconstructed descriptors for BL33 and scratch 0x10200000 are compatible with RWX in EL; active MMU state not demonstrated. SCTLR C/I not determinable offline.
WRITE to code NOT tested (no reversible hypothesis yet; I-cache off in
source but D-cache on => would need flush via `dcache` idx11).
env default rodata ~0x37eb65a0 (bootcmd=run storeboot, bootdelay=1...);
live env in BSS with no fixed offset (zero in binary). read-only hunt:
`mread 0x37f84000+ + grep`, never poke until consumer found.

## 8. chains

```text
HARDWARE_REPRODUCED:  WRITE(0x01) -> cmd_tbl[i].cmd -> legitimate handler -> reply failed:/success
HARDWARE_REPRODUCED:  WRITE -> env sub-table -> cross-table handler (P3)
HARDWARE_REPRODUCED:  FILL(0x03) -> RAM (missing FILL->slot demo; same slot, should work)
PROBABLE: FILL 6 pairs -> full 0x30 entry (name+max+cmd) in one logical WRITE
PROBABLE: WRITE/FILL -> maxargs/usage/help (data, display-only)
BLOCKED: WRITE/FILL -> RUN(0x05) -> exec (RUN wedges USB before observing)
BLOCKED: handler -> SMC 0x820000ff -> unsigned boot (secure boot holds)
OPEN:   WRITE -> live env (address unknown)
OPEN:   WRITE -> .text code (descriptors compatible with RWX, no test; needs flush+I-cache story)
DEAD (do not repeat): ddr_test_copy as write (r38: 32b x4 vs ldr x64),
  RD_LARGE, setenv lock / set_usb_boot as bypass, magisk boot unsigned.
```

## 9. levels L0-L7 (factual)

L0 read-only: YES (0x02 up to 64B + mread + bulk oracle).
L1 arbitrary write: YES (0x01 8/16/64B any tested address; 0x03 scattered).
L2 control-data: YES (round40 string + slots).
L3 control-flow to existing code: YES (P1/P2/P3 + double restore).
L4 arbitrary BL33 exec: NOT (RUN jumps but no controlled exec observed).
L5 outside BL33 / secure: NOT. L6 temp root: NOT. L7 persistence: NOT
(all RAM; reboot wiped S1->S2).

## 10. next 3 (highest value)

1. DONE (S3): FILL->redirect demo PASS (F1 below). Remains: full entry
   via 6 FILL pairs (swap name+max+cmd in one logical WRITE).
2. RUN with UART + flag matrix (0x10 vs 0x00 vs len 0) for no-op target and for
   function writing magic to arena; decides between PHY-off (recoverable) and
   CPU fault. requires physical access + serial. without it, RUN stays wedge.
   Do NOT repeat RUN/MODIFY without UART: each costs 1 power-cycle.
3. DONE partial (S3): live env LOCATED (see S12). Missing: hash format
   + test with designed observable (printenv does not show in bulk reply;
   candidate: var consumed by `run`/`bootm`, dangerous; or redirect making
   env observable via return-code).

## 12. S3 post-power-cycle (new session, stage 16, alive at end)

health: arena zero, false/test/envprint slots at originals (reboot wipes everything).

```text
TEST F1 FILL->false->true (1 32b pair, high already 0)
  BEFORE failed: MID slot 6c67e33700000000 TRIGGER success RESTORE orig retrigger failed:
  STATUS PASS. 2nd independent path for flow (0x01 unnecessary for slot <4GB).
TEST F2 scattered FILL (3 pairs 1 transfer, gaps untouched)
  MID 11111111/00000000/22222222/00000000/33333333 RESTORE zero STATUS PASS
HUNT env: 0x37f50000/8c/90/94/98/9c + 0x37e10000 zero; 0x37f84000/88000
  deterministic (same sha across boots: firmware structs, not residue)
```

## 13. live env LOCATED (read-only, no writes)

malloc arena 0x33e18000+ (`hunt_33e18000_32k.bin`, 32K from 0x33e18000):

```text
hash table   ~0x33e1d6e8: active_slot=normal avb2=1 baudrate=115200 bcb_cmd=...
             boardid=3 boot_part=... (28+ vars)
bootcmd      0x33e1da8c: run storeboot
bootdelay    0x33e1da8c+ : 1
bootargs     0x33e1d811+ (35 androidboot.*, 28 bootargs refs)
scripts      storeboot @0x33e1eb21, recovery/switch_bootmode/upgrade_check...
upgrade_step 0x33e1f1cb: 2
lock         outputmode ctx: 10100000
consumers printenv/env-print (invisible in bulk) + run/bootm/get_rebootmode
```

dense regions without strings (blobs, not env): 0x37f00000..0x37f40000
(~15K nonzero each, short junk); 0x37f70000 = ICU unicode tables (309 strs);
0x37f88000 = burning buffers (residue of own uploads + descriptors
0x37f89fxx-0x37f8abxx); 0x37f84000 = heap ptrs 0x33xxxxxx + BL33 0x37e1xxxx.
NOT WRITTEN: no USB observable for env change (bulk only returns success),
live env storage is writable; semantic consumption not demonstrated. any poke here waits for the item 10.3 test.

## 11. risks and harness rules (learned this round)

```text
0x04 and 0x05 kill the session. always test LAST, never in the middle.
incomplete bulk crashes gadget even without write (round40). only full command + 0x33 drain.
post-timeout: drain 0x33 until n==0 before next bulkcmd.
mread size 8 flaky; cross-check with >=0x40 or only 0x02.
first false bulk post-burst can timeout 1x; retry 3x + drain.
arena restored to zero in both sessions; P1/P2/P3 slots restored and re-verified.
S2 ended wedged (RUN); S1 ended in android-reboot (MODIFY). nothing persistent.
```

logs: `reports/round43-campaign/` (battery.log, battery3.log, ro_cmdtbl_full.bin).
repro: `sudo python3 tools/optimus.py identify/mread/bulkcmd`,
scripts in `/tmp/opencode/{campaign_ro,bsshunt,dump_sub2,baseline,battery2,battery3}.py`.
