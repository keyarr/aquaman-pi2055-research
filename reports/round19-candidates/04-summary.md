# round19 summary — EXECUTED live. C1 DATA_ONLY, C2 UNREADABLE, C3 not probed

date: 2026-09-30 ~11:50-11:58 UTC. two Optimus stage-16 sessions, then
device off-bus.

## session log (brief s1/s2)

- start: fastboot 18d1:0d02 present. getvar: product aquaman,
  bootloader U-Boot 2015.01-g7ac5df7677-dirty, serial 1234567890.
- `fastboot oem update 5000` -> FAILED / Status read failed (expected,
  stick leaves fastboot). 1b8e:c003 appears.
- identify: raw `00 07 00 10`, version 0.7, stage 16 (TPL/BL33-u-boot).
  EP 0x81 IN / 0x02 OUT bulk, MPS 512.
- session 1: C1 0x02 64B OK + C1 mread 64K OK; C2 0x02 @ 0x05300000 ->
  Errno 5, disconnect, stick reboots to ADB 2717:4e40.
- recovery: `adb reboot fastboot` (operator-corrected) -> 18d1:0d02;
  `fastboot oem update 5000` -> 1b8e:c003, identify stage 16 again.
- session 2: C2 mread @ 0x05300000 -> Errno 19 mid bulk-IN, disconnect.
  device off-bus (later re-enumerates on its own; left alone).
- writes: zero. no 0x05, no flash/erase/env, no payload, no ADB reads.
  only sanctioned mode-switch + one recovery reboot + read primitives.

## results

C1 = DATA_ONLY, read and classified (01-c1.md):
  reports/round19-candidates/c1-5000000-64k.bin, 65536 B,
  sha256=4cd2c04f5bf5d712e342312d67c406c5f0d85fd9d391c2cc831715910c91bfa8.
  0x02-vs-mread first-64B cross-check MATCH.
  zero eret/SMC/EL3/0x820000xx/strings. 0x40000 ext NOT taken (not code-like).
C2 = UNREADABLE, concrete gadget fault x2 via two paths (02-c2.md).
  proves nothing historical (status=disabled). no bin, no fake bytes.
C3 = UNKNOWN / not probed, gate correctly fails (03-c3.md).

content classes found: DATA_ONLY (C1). zeroed/buffers/heap (brief s8): C1 is
dense nonzero (0.996) high-entropy, not zero, not heap-shaped. E3 stays
UNKNOWN: no BL31 image, no dispatcher, no 0x820000ff handler found anywhere.

## state carried forward (round18 close, updated)

BL31 exact image NO. BL31 runtime copy NO. SMC dispatcher NO.
0x820000ff handler NO. AML_DATA_PROCESS checks UNKNOWN. E3 UNKNOWN.
BL33 validation ABSENT (round17 site 0x37e24cf0).
C1 was MEDIUM/LOW as BL31 location, now DATA_ONLY by bytes (first-ever read
of 0x05000000). C2 LOW, now UNREADABLE from TPL. C3 LOW.
new lead (hypothesis): stale storage-in pointer == C1 base suggests C1 is a
secure-storage/crypto buffer. unproven.

## artifacts

- reports/round19-candidates/01-c1.md, 02-c2.md, 03-c3.md, 04-summary.md
- reports/round19-candidates/c1-5000000-64k.bin (65536 B, sha256 above)
- reports/bl31-live-probe-round19.md (probe table)
- tools/bl31_live_probe.py (unchanged, used as-is per brief s9)
- prior artifacts untouched.

## success criterion (brief s10)

minimum met: 1b8e:c003 found, C1 64K read, C1 sha256, 0x02==mread on first
64 B, C1 classified. ideal partially met: C2 attempted twice, classified as
UNREADABLE (concrete USB failure, not absence of trying). C1 not code-like,
so no 0x40000 dump per the stop rule.
