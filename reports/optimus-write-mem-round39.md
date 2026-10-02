# Optimus WRITE_MEM round 39: real RAM write via 0x01

date: 2026-10-01. live, on device. BL33 em RAM, `1b8e:c003`, stage 16.
build: aquaman_9_PI_2055, U-Boot 2015.01. entrada: `fastboot oem update 5000`.
verbo: `AM_REQ_WRITE_MEM` 0x01 (`ctrl OUT 0x01, wValue=addr>>16, wIndex=addr&0xffff, 4B`).
leitura: `AM_REQ_READ_MEM` 0x02. detalhe: `reports/round39-optimus-write/00_session1.txt`, `01_session2.txt`.
equivale a `tools/optimus.py poke` + `read`; the test used a one-process script only, to avoid burning the window.

## 0. answer

```text
WRITE_MEM exists in the running binary: YES, 0x01 answers and alters RAM
host alters BL33 RAM: YES in arena 0x378xxxxx (below base); inside BL33 NOT TESTED
confirming readback: YES, 2 addresses, before/after/reread/restore
RUN_IN_ADDR / bootm / flash / eMMC: NOT TOUCHED
```

## 1. session 1: 0x37800000

empty arena, below BL33 (`0x37e18000`), far from cmd_tbl and page tables.

```text
BEFORE 0x37800000: 00 *16
WRITE  0x01 0x37800000 <- 41 42 43 44 (4B, `ABCD` on the wire)
AFTER  0x37800000: 41 42 43 44 00 *12
RESTORE <- 00 00 00 00 ; verify 00 *16 OK
timing: immediate write ok, readback +200ms, identify stage 16
state: 1b8e:c003 stays enumerated and responsive, no hang
```

## 2. session 2: 0x37801000

```text
BEFORE2 0x37801000: 00 *16
WRITE2  0x37801000 <- 44 33 22 11
AFTER2  0x37801000: 44 33 22 11 00 *12
REREAD  +1s: igual, session-persistent
RESTORE2 verify 00 *16 OK
CHECK1  0x37800000: 00 *16 clean (isolation between writes)
```

## 3. what this proves

HARDWARE_REPRODUCED:

* 0x01 WRITE_MEM exists in the running firmware, not only in the tree. refutes the hypothesis "command only in source" (cf. caso RD_LARGE que divergiu).
* aligned 4B payload writes and readbacks via 0x02 at 2 distinct addresses.
* no hang, no wedge, no power-cycle needed. distinct from the unmapped-address wedge in round 4.
* arena restored to zero after the test. nothing persistent left.

NAO HARDWARE_REPRODUCED:

* write inside `0x37e18000..0x37ff0000` (code, cmd_tbl, got). not attempted.
* max size, non-4 alignment, cache flush, accepts-any-address. only aligned 4B tested.
* RUN_IN_ADDR 0x05. never sent.
* persistence across reboot. session only.
* relation to rounds 16/37/38: those were `ddr_test_copy` via `oem` (D: no compatible consumer). this is direct host write via USB. different primitives, independent verdicts.

## 4. honest next step

1. mapear limites ainda na arena: 8B/16B/64B, 1B unaligned em `0x37800001`, endereco no teto `0x37e17ffc` (ultimo antes de BL33).
2. so depois: 4B em dado de controle inofensivo do BL33 com readback, sem executar.
3. RUN_IN_ADDR continua gated: nao enviar ate escrita em BL33 estar caracterizada.

## 5. risco

stick ficou em `1b8e:c003` ao fim das duas sessoes. ou espera o auto-burn timeout (volta sozinho a Android) ou power-cycle manual. nao deixar host grudado em optimus.
