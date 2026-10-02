# BL33 write primitive round 16: update + ddr_test_copy is not an arbitrary write

date: 2026-09-30. static only, no device, no USB, no execution.
image: reports/round14-bl33-persist/bl33-37e18000.bin (0x37e18000..0x37ff0000,
sha256 664fb34a9c6d92cdcd576659fb5359bd5218841612dbf38c01426c5d3c1b7818).
reference: .src/u-boot-khadas (cmd_ddr_test.c, f_fastboot.c, optimus_download.h).
tool: tools/bl33_round16.py. detail: reports/round16-ddr-copy/01..05.
tests: TestBl33Round16 in tools/run_tests.py (pass).

Round 15 confirmed two HIGH store-reaching paths via oem->run_command:
mmc read 0x37e2d890 (eMMC->RAM) and ddr_test_copy 0x37e3d1b0 (RAM->RAM,
loop 0x37e3aea0). Round 16 was asked whether host->update->RAM plus
ddr_test_copy composes into a truly arbitrary RAM write. Answer: no.
The address legs are unclamped (kept HIGH); the data leg is destroyed
by the handler itself.

## 1. what was audited

```text
cmd update 0x37e78ff8 (maxargs 3) -> 0x37e78f94 burning entry
fastboot rx_handler 0x37e95274 / cb_download 0x37e95408 / usable 0x37e953e4
burning buf init 0x37e7bbe0 (transferBuf == 0x7700000)
do_ddr_test_copy 0x37e3d1b0 (argv->w24/w25/w20/w21/w22, floor, loop)
copy loop 0x37e3aea0 (lsr #2, 16 B/iter, 4x factor)
strtoul32 0x37e3cbb0 (32-bit wrap) vs simple_strtoul 0x37eac21c (64-bit)
do_mmc_read 0x37e2d890 (blk_dread + ubfiz mask)
```

## 2. matrix (brief section 6, strict definition)

Arbitrary RAM write = host data + controllable source + controllable
destination + sufficient length, with the data surviving to dst.

```text
property                  result     evidence
host controls data        YES        fixed-buffer memcpy of USB bytes (01)
host controls source      YES        argv[1]->x1 no clamp; 0x10200000/0x07700000 in range (03)
host controls destination YES        argv[2]->x0 no clamp, HIGH (03)
host controls length      PARTIAL    floor <0x1000->0x2000000, no max, 4x effective (03)
destination range clamp   NO         no and/lsr/mask/cmp/base-add on dst
length clamp (max)        NO         none; no wrap check
length clamp (min)        YES        floor forces >=16 KiB effective
data survives to dst      NO         fill overwrites copy; 16 B tail only (02 sect 4)
arbitrary RAM write       NO         survival leg fails; shape is pattern-fill + tail
```

mmc read for comparison:

```text
source = eMMC blocks (host picks blk/cnt, not bytes)
destination = RAM controllable, no clamp
length = (cnt&0x7ffffF)*512
verdict: same address power, weaker data leg (needs eMMC round-trip).
```

## 3. memory reached (no invented permissions)

Proven/mapped: BL33 [0x37e18000,0x37ff0000) + page table [0x37ff0000,
0x3800000); fastboot buf [0x10200000,0x18200000); burning buf
[0x07700000,0x0b700000); runtime DTB [0x01000000,0x0100e3a8).
Readable: all of the above (prior mreads / dumps). Writable by protocol:
the two host buffers only. Writable by primitive address-reach: anything
32-bit (no clamp), including BL33/cmd_tbl/page table, but min 16 KiB
pattern footprint makes code-pointer/string-pointer/branch-target
overwrite destructive, never surgical; the only precise write is the
16-byte tail at dst+len. Kernel/AML_RES residency: UNPROVEN. Detail: 04.

## 4. conclusion (only CONFIRMED / UNPROVEN / REFUTED)

```text
1. Do host bytes reach a known RAM region?
   CONFIRMED. Fastboot: [0x10200000,0x18200000) via 0x37e95274.
   Burning/update: [0x07700000,0x0b700000) via 0x37e7bbe0 + header math.
   Both fixed-address, gated size, no host address (01).
2. Can this region be used as ddr_test_copy source?
   CONFIRMED for address reach. argv[1] takes any 32-bit addr incl.
   both buffers, no clamp (02, 03). Data survival is a separate
   question (see 6).
3. Is the destination controllable?
   CONFIRMED as address reach (HIGH, 03): argv[2]->x0 with no
   and/lsr/mask/range-compare/base-add/truncation-beyond-32-bit.
4. Is the size controllable?
   CONFIRMED with a floor (PARTIAL): argv[3]->w2, <0x1000 forced to
   0x2000000, no max, effective bytes 4x requested (02, 03).
5. Is there enough clamp to prevent arbitrary write?
   REFUTED as the reason: there is deliberately NO dst/max clamp, yet
   arbitrary write still fails. What blocks it is not a clamp but the
   handler's own fill phase destroying the payload (02 sect 4).
   Minimum clamp (<0x1000 floor) exists but is not what defeats the chain.
6. Does the update + ddr_test_copy composition constitute, statically,
   an arbitrary RAM write?
   REFUTED. End state is L bytes of 0x12345678 at dst plus 16
   src-derived bytes at dst+L (L=(clamp(len)>>2)*16*loop, min 16 KiB),
   not N free host bytes at dst (05 sect 1). Round 15 HIGH is kept for
   the address leg and corrected for the primitive: destructive
   constant-fill with word-tail, not arbitrary write.
```

Also unchanged: signature, key and BL31 bypass remain undemonstrated
(UNPROVEN). E2 stays refuted. Nothing was executed on the
device. No patch to SMC / aml_sec_boot_check / do_bootm was attempted.

## 5. files and tests

```text
reports/round16-ddr-copy/01-update-path.md       buffers, handler args, NO addr control
reports/round16-ddr-copy/02-ddr-copy.md          parser, widths, 4x loop, fill-then-tail
reports/round16-ddr-copy/03-control-analysis.md  HIGH dst, PARTIAL len, matrix
reports/round16-ddr-copy/04-memory-map.md        proven regions, patch classes (offline)
reports/round16-ddr-copy/05-composition.md       chain walk, salvages that fail, mmc read
tools/bl33_round16.py                            offline verbs + pure clamp/bytes helpers
tools/run_tests.py                               TestBl33Round16 (new, image-gated + pure)
```

Run: python3 tools/run_tests.py (or -v). No device, no network.
