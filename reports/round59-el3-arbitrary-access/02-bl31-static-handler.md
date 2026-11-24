# round59 02: static dump of BL31 and the address-translation question

Offline. No USB session open in this phase, so there is no current MREAD to
compare with the round19 `DATA_ONLY` (`c1-5000000-64k.bin`: entropy 7.9967,
zero eret/smc#0, header `04 00 00 00 75 73 69 64 6f 6e 32`). That dump
remains classified as DATA_ONLY / working set of the NS share area; it does
not contain EL3 code. The structural reference is
`.src/u-boot-khadas/fip/gxl/bl31.bin` (FAMILY STRUCTURAL REFERENCE,
`round27-bl31/02-load-origin.md`).

## 2.1 the reference is real EL3 code

`python3 tools/bl31_live_probe.py .src/u-boot-khadas/fip/gxl/bl31.bin 0x5100000`:

```text
size 0x2c3a8  sha256 93259d548dbb32d17e320bb62c1ac1f31c794ea2e520086d4a2c23ddfaa0ac38
nonzero 0.890  eret_words 2  smc#0_words 0  el3reg 74
disasm insn=45290 branch=3586 eret=2 smc=0 density=1.000
strings AMLSECU(2) aml(6) secure(2) bl31(2) opteed(2) PSCI(2) tee(5)
```

Classification: SECURE_MONITOR_LIKE / BL31_STRONG_CANDIDATE. `msr vbar_el3`
at `0x5100024`, `0x51000ec`, `0x5124e50`. Load base `0x05100000`
(matches `round27-bl31/02`, the BL2 table and the bl31.img header).

## 2.2 the dispatcher

Entry: `0x5119d78`. Preserved SMC registers:

```text
w20 = X0 low32 (id)      x22 = X1       x23 = X2       x2 = X3
x28 = X4                 x21 = X6       x7  = X7 (bit0 = seletor NS/secure)
```

A context pointer is read from `[0x51c5000 + 0xec0] = [0x51c5ec0]`;
`0x5119d18..0x5119d34` initializes that slot with `0x51254c8` (function
`0x5119388`). The struct at `0x51254c8` contains 60 function pointers
(offsets `0x00..0x1d8`), all link-time constants. The dispatcher compares
`w20` against `0x820000xx` assembled with `mov w0,#lo ; movk w0,#0x8200,lsl#16`
and calls the struct pointer; there is no address translation in the dispatcher.

Useful mapping (dispatcher handler -> struct pointer -> function):

| id | trampoline | slot | function |
| --- | --- | --- | --- |
| 0x82000020 | 0x511a338 | +0x00 / +0x08 | 0x5119278 / 0x5119290 |
| 0x82000024 | 0x511a380 | +0x30 / +0x38 | 0x511da20 / 0x511da28 |
| 0x82000028 | 0x511a6cc | +0x180 | 0x5119348 |
| 0x82000060 | 0x511a554 | +0xd8 | 0x511d8ac |
| 0x82000061 | 0x511a524 | +0xc8 | 0x511d854 |
| 0x82000062 | 0x511a278 | +0xc0 | 0x511d828 |
| 0x82000063 | 0x511a548 | +0xd0 | 0x511d888 |
| 0x82000065 | 0x511a560 | +0xe8 | 0x511d8f4 |
| 0x820000ff | 0x511a4bc | +0xa0 | 0x511d1e4 |

Ids `0x23`, `0x25`, `0x27`, `0x64` do NOT appear as individual comparisons
in this reference. The generic blocks `0x511a350` / `0x511a368`
(reached via `b.ls`/fallthrough after `cmp 0x22`, not via `b.eq`) return
the same base constants via slots `+0x10/+0x18/+0x20/+0x28`. The
live device emits 0x23/0x24/0x25/0x27 and 0x64, so the live table
is not identical to this one; further evidence of the version caveat in 2.4.

The base functions translate nothing; they are constants:

```text
0x5119278: mov x0,#0xe000 / movk x0,#0x50f,lsl#16 -> 0x050fe000  (secmon IN)
0x5119284: -> 0x050ff000  (secmon OUT)
0x511da10: mov x0,#0x5000000 ; ret                  -> 0x05000000  (storage IN)
0x511da20: mov x0,#0x5040000 ; ret                  -> 0x05040000  (storage OUT)
0x511da30: mov x0,#0x5080000 ; ret                  -> 0x05080000  (BLOCK)
0x511d918: mov w0,#0x40000 ; ret                    -> 0x40000      (BLOCK size)
```

This independently confirms the "stale" values from the round20/21 reports
and closes the question: the bases of SMCs 0x23/24/25/27 are constants inside
BL31, not the result of NS translation. The host cannot redirect them via
the SMC registers; messing with the BL33 globals only misaligns local staging.

The storage handlers (e.g. `0x511d854` for 0x61 and `0x511d828` for 0x62)
receive `x0 = IN base` and `x1 = OUT base` from these constants, and read the
request header from `[IN]`. No host register address is used as a destination.

## 2.3 the answer that matters: 0xff uses the raw value, with MMU off

`0x511a4bc` prepares the call:

```text
ldr x4,[ctx,#0xa0]   ; 0x511d1e4
mov x3,x28           ; opt  (SMC X4)
mov x1,x23           ; buf  (SMC X2)
mov x0,x22           ; cmd  (SMC X1)
blr x4
```

`0x511d1e4`:

```text
mov x5,x1            ; buf
mov x6,x2            ; len
dsb sy ; isb
mrs x7,sctlr_el3
and x7,x7,#0xfffffffe
msr sctlr_el3,x7     ; M = 0  -> translation OFF
isb
cmp x0,#0x14 ...
cmp x0,#0x40 -> 0x511c9fc (x0=buf, x1=len, x2=opt)   ; decrypt (site1)
cmp x0,#0x80 -> 0x511c530 (x0=buf, x1=len, x2=opt)
cmp x0,#0x20 -> 0x511cfc8 (x0=buf, x1=len)
cmp x0,#0x10/0x11/0x12 -> 0x511b6b8
default -> x0 = 0x958
... restores SCTLR_EL3.M = 1 before returning
```

In the inspected destinations (`0x511c9fc`, `0x511c530`, `0x511cfc8`,
`0x511cb04`) the value of `buf` is used directly as a physical pointer:

```text
0x511ca54: add x23,x19,#0x400      ; x19 = buf
0x511ca74: mov x0,x19 ; bl 0x511c964
0x511cac4: add x0,x1,x19           ; buf + offset -> descriptor
0x511c548: ands x19,x2,#7          ; checks LEN ALIGNMENT, not the address
0x511cfe4: mov x19,x0              ; raw buf
```

There is no NS translation call, no range `at`/`dc cvac`, no
comparison of the address against the window `0x05000000..0x05100000` in the
branches traversed. What exists is size-alignment checking and header validation
inside the buffer. As a rule, the address supplied by the host is used as a raw
physical address, in EL3, with MMU off. That is the hypothesis to
be tested in the 03 matrix.

## 2.4 version caveat (do not skip)

The reference is of a family, not the exact BL31 of Aquaman. Proof: the device
accepted `cmd=0x100` at site 2 (x0 returned 0, `diag_packed.py`), while
in this binary `0x100` falls into the default `0x958`. The 0xff command set
differs between builds. What carries over is the STRUCTURE (turn off M, use raw
X2, constant base in the getters), not the table of ids. Do not cite 0x511c9fc
as a live address; cite it as a family implementation pattern.

## 2.5 what remains open

- Current MREAD of `0x05000000` (to confirm it remains DATA_ONLY in this
  session) was not done: offline phase.
- Aquaman's exact BL31 remains unreadable by NS from `0x05100000`
  (`round27-bl31/04`); the raw/restore translation cannot be confirmed in the
  device binary without decrypting the FIP.
- Secure SRAM: `03-memory-layout.md` does NOT give an SRAM address. The only
  available value is the mailbox `0xd9013f00` in `round27-bl31/06-entry-handoff.md`,
  as a FAMILY REFERENCE (`bl31.bin`), not as Aquaman ground truth.
