# round59 03: test matrix and predictions (offline)

Prediction convention: `OK with data` = X0=0 and readable bytes at the destination;
`error` = X0 != 0, no observable write; `reset` = gadget leaves the bus
(external abort / watchdog). All rows are predictions derived from 01 and
02, not results. None were executed in this phase.

## 3.1 targets

| target | address | nature (round27) | readable by MREAD? |
| ------ | ------- | ---------------- | ------------------ |
| C0 control | `0x01080000` | normal NS RAM | yes |
| C1 low share | `0x05000000` | NS share IN (0x23) | yes |
| C2 high share | `0x05040000` | NS share OUT (0x24) | yes |
| S1 bl31 window | `0x05100000` | BL31 image, Secure | no (fault at 0x05100000) |
| S2 bl31 window | `0x05200000` | BL31 image, Secure | no |
| S3 bl32 slot | `0x05300000` | BL32 no-map, status=disable | no |
| SRAM | `0xD9013F00` | SRAM mailbox, FAMILY REFERENCE (`round27-bl31/06`), not Aquaman ground truth | unknown |

`0x05400000` is only the end of the DTB pool, with no HW meaning
(`round27-bl31/05`). The `03-memory-layout.md` map does not provide an address for
secure SRAM; the SRAM row exists only because 06 provides the mailbox. If the
objective requires Aquaman's SRAM, that address must be confirmed before
using it as a target.

## 3.2 0x820000ff family: only path where the host address enters EL3

Rule: X1=cmd, X2=buf, X3=len, X4=opt (01.1). Predictions for `cmd=0x40`
(decrypt in-place, site1), the case already seen working on C0:

| target | prediction | rationale |
| ------ | ---------- | --------- |
| C0 `0x01080000` | OK with data | plan item 1: `ANDROID!`, `0x959000` B |
| C1 `0x05000000` | OK with data, staging desired | NS share is writable; may corrupt C1/C2/BLOCK and break subsequent storage commands |
| C2 `0x05040000` | OK with data, staging desired | same |
| S1 `0x05100000` | OK with data **or** reset | 02: MMU off + raw pointer; if the firewall allows secure access from EL3, BL31 writes; if it blocks, abort. X0 in RESULT discriminates |
| S2 `0x05200000` | OK with data **or** reset | same |
| S3 `0x05300000` | OK with data **or** reset | disabled BL32 slot; may not be backed |
| SRAM `0xD9013F00` | error or reset | outside the declared map; may not exist on Aquaman |

For the other cmds in the family the prediction is less informative because the
reference does not match the device (cmd 0x100 is accepted on the live device, not in the
reference). Even so:

| cmd | function in reference | C0 | S1/S2/S3 |
| --- | --------------------- | -- | -------- |
| 0x10/0x11/0x12 | 0x511b6b8 | OK / status | OK or reset |
| 0x14 | 0x511bd24 | OK / status | OK or reset |
| 0x20 | 0x511cfc8 | OK / status (reads 0x200 B from buf) | OK or reset |
| 0x80 | 0x511c530 | OK / status | OK or reset |
| 0x100 | absent in reference | OK, x0=0 (live) | unknown |

If any cmd writes to the buffer, it is a candidate for an arbitrary write equivalent
to 0x40. Confirm the write semantics of each before using it as a
primitive.

## 3.3 0x60..0x65 family: host address does not reach EL3

Here the address supplied by the host (`keyman read <n> <addr>`) is a
`memcpy` destination **in BL33**. BL31 always writes to the fixed OUT `0x05040000` and reads
always from the fixed IN `0x05000000` (02.2). Changing the globals
`[0x37fbde60]/[0x37fbde58]` only misaligns local staging: the BL31 handler
ignores those globals and uses the internal constants.

| case | action | prediction | is it a write in EL3? |
| ---- | ------ | ---------- | --------------------- |
| C0 control | `keyman read sn1 0x1080000` | OK with data | no |
| C1/C2 share | destination `0x05000000`/`0x05040000` | OK with data (overwrites staging) | no |
| S1..S3 | destination `0x05100000+` | reset in BL33 `memcpy`, after the SMC already returned OK | **no**: the abort is from NS |
| IN global -> S1 | poke `[0x37fbde60]=0x05100000` before the SMC | reset in BL33 staging, before the SMC | no |
| OUT global -> S1 | poke `[0x37fbde58]=0x05100000` before the SMC | SMC OK, reset in BL33 `memcpy` | no |

Matrix conclusion: no 0x60..0x65 row is a candidate for an arbitrary write
in EL3. They serve only as control and discriminator: if S1
fails on 0xff and fails differently here, the difference locates the
barrier (NS vs EL3).

## 3.4 getters 0x23/0x24/0x25/0x27

No address argument. Single prediction: X0 = 0x05000000 / 0x05040000 /
0x05080000 / 0x40000, independent of X1..X3. There is no destination matrix.
Useful for confirming that the live binary uses the same bases as the reference.

## 3.5 order, oracle and safety

- One row per session. The plan records that a direct call by the stub
  worked once and hung the gadget in all subsequent attempts
  (`plan-smc-gate-neutralize-magisk.md`, item 1); do not repeat site2 over the
  plaintext without `imgread` in the same session.
- Each row: Phase 0 read-only (handler `false`, call sites, scratch), save
  baseline; write stub; `dcache flush`; trigger `false`; `dcache flush`;
  read RESULT 0x20; restore handler/scratch/RESULT; oracle
  `false -> failed:` / `true -> success`.
- If the gadget drops, recovery is power cycle + re-hunt of dynamic
  addresses (cmd_tbl is stable; htab is not).
- Do not use flash/erase/saveenv/efuse/BootROM/`RUN_IN_ADDR`/`MODIFY`.
- Remember that writing to C1/C2/BLOCK can destroy the session's storage state;
  do that last, never before a test boot.
