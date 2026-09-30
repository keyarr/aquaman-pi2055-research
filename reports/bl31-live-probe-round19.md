# BL31 live probe round 19: EXECUTED live, C1 DATA_ONLY, C2 faults

date: 2026-09-30 ~11:50-11:58 UTC. entry `fastboot oem update 5000` only.
identify raw `00 07 00 10`, version 0.7, stage 16 (TPL/BL33-u-boot), two
sessions. zero writes, zero SMC, zero 0x05, zero ADB reads.

## probe table

candidate | address | size | sha256 | classification | evidence
C1 secmon | 0x05000000 | 0x10000 | 4cd2c04f5bf5d712e342312d67c406c5f0d85fd9d391c2cc831715910c91bfa8 | DATA_ONLY | first-ever read; 0x02-vs-mread first64 MATCH; 0 eret/SMC/EL3/0x820000xx/strings; nonzero 0.996 high-entropy
C1 ext | 0x05000000 | 0x40000 | n/a | NOT RUN | gated on code-like 64K per brief s5; C1 is DATA_ONLY so not taken
C2 secos | 0x05300000 | 0x10000 | n/a (not acquired) | UNREADABLE | 0x02 -> Errno 5 + disconnect; mread -> Errno 19 + disconnect; deterministic x2; status=disabled so proves nothing historical
C3 secmon in | stale 0x050fe000 (global 0x37f71480) | n/a | n/a | UNKNOWN | caller graph exact, address runtime-only, stale snapshot
C3 secmon out | stale 0x050ff000 (global 0x37f71488) | n/a | n/a | UNKNOWN | same
C3 storage in | stale 0x05000000 (global 0x37fbde60) | n/a | n/a | UNKNOWN | init 0x37e8bbb8 graph exact, value stale; equals C1 base (lead: C1 may be storage/crypto buffer)
C3 storage out | stale 0x05040000 (global 0x37fbde58) | n/a | n/a | UNKNOWN | same
C3 storage block | stale 0x05080000 size 0x40000 (globals 0x37fbde68/48) | n/a | n/a | UNKNOWN | same

detail: reports/round19-candidates/01-c1.md 02-c2.md 03-c3.md 04-summary.md.
bin: reports/round19-candidates/c1-5000000-64k.bin (65536 B).
classifier: tools/bl31_live_probe.py (brief s6 classes + s2 signal list).

## answers to brief s7/s8 prompts

no candidate base/entry/vector/dispatcher/SMC-ID/memory-check anchor
recovered; C1's 64K hold no anchor of any kind. C2/C3 content type
unanswered (C2 unreadable from TPL, C3 not probed per gate). C1 is dense
nonzero high-entropy (not zero/buffer/heap-shaped). E3 remains UNKNOWN.
no full-RAM scan started.

## close

```text
BL31 exact image found      = NO
BL31 runtime copy found     = NO
SMC dispatcher found        = NO
0x820000ff handler found    = NO
AML_DATA_PROCESS checks     = UNKNOWN
E3                         = UNKNOWN
BL33 validation            = ABSENT
C1 0x05000000 64K           = READ, DATA_ONLY, sha256 4cd2c04f...
C2 0x05300000              = UNREADABLE from TPL (fault x2)
```
