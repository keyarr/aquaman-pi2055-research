# key surface round24 (consolidated, static only)

image `reports/round14-bl33-persist/bl33-37e18000.bin` base `0x37e18000`.
DTS `artifacts/aquaman.dts` (`gxl_aquaman_1g`). no device, no reads, no SMC,
no commands run. detail: `reports/round24-key-surface/01..07`.

round23 closed the CONTRACT (argv roles, C1/C2, gates, destinations).
round24-vector closed the MECHANISM (static vectors, DTS-populated key array,
per-leg validators, direct bl inside vector legs). this round closes the
SURFACE: which of the 19 DTS keys each generic operation reaches.

## main table (read; write has no host-visible output)

```text
key | generic keyman read | backend | secure-world data returned | host-controlled dest | host-visible output
sn1,sn2,mn1,mn2,hdcp2_rx,bt_rc_mac,netflix_mgkid,region | YES x8 | 0x37f5e478 -> 0x37e7609c normal generic | opaque blob | YES | RAM ONLY (+UART/ENV w/ fmt)
hdcp,widevinekeybox,hdcp22_fw_private,PlayReadykeybox25,prpubkeybox,prprivkeybox,attestationkeybox | YES x7 | 0x37f5e478 -> 0x37e7609c secure generic | opaque blob | YES | RAM ONLY (+UART/ENV w/ fmt)
mac,mac_bt,mac_wifi | YES x3 | 0x37f5e4b8 -> 0x37e762f4 efuse via mac-ascii leg | opaque blob (ascii-shaped) | YES | RAM ONLY (+UART/ENV w/ fmt)
secure_boot_set | NO | efuse vector, name-gate refused on read / setenv-diverted on write | none | n/a | NO
hdcp2lc128,hdcp2key (fixed, non-DTS) | NO | direct 3x amlkey, type-2 leg dead on this DTS | n/a | n/a | NO
```

## backend

```text
key -> device/class (0x37e75590: 1 efuse / 2 secure / 3 normal)
 -> 0x37e73380 (1->0x37f5e4b8, 2/3->0x37f5e478)
 -> device_read[+0x30]/device_write[+0x10] blr
 -> 0x37e7609c/0x37e75e7c (secure, bl amlkey 0x61/0x62) or
    0x37e762f4/0x37e761f0 (efuse backend) or DIRECT hdcp2 (fixed names)
secure generic 7 / normal generic 8 / efuse 3+1 diverted / HDCP2 special 0 DTS keys / unknown 0.
```

## reachability

```text
selection = NAME string (argv[1]); no index/slot; unknown name -> 0x198/0x269 reject before SMC.
read: 18 YES (all except secure_boot_set, refused by strcmp gates in 0x37e762cc/0x37e7637c, not by permit bits).
write: 19 names accepted; 18 reach storage; secure_boot_set diverted to setenv path in 0x37e761f0.
hdcp2lc128/hdcp2key/hdcp2 as argv: NO (no DTS entry; fixed slots fire only as secondaries inside the dead type-2 leg).
only host-driven entry is do_keyman_read; second caller 0x37e8240c uses a fixed caller-side name.
```

## permit

parsed (`entry+0x5c` bits 1/2/4, disasm `0x37e75d50..0x37e75dd8`) but zero
consumers on the `keyman -> key_manage_* -> entry` path (scoped `#0x5c`
scan: only the three parser stores). BL33 enforcement ABSENT (HIGH);
overall UNKNOWN (secure-world side unexamined). `secure_boot_set`
write-only alignment is by code name-checks, not bit tests.

## output

```text
secure legs: C1[namelen,hint,name] -> SMC 0x61 -> C2[len,blob] -> staging malloc(0x10000) -> caller RAM @argv addr.
  len = secure-reported (query/tell/C2, never argv); max UNKNOWN; no alignment; status out-of-band (X0).
  class per backend: status (write) / opaque blob (read) / never plaintext-ciphertext without secure ground truth.
host dest: base==0 rejected only; 64-bit; no alignment/range/overflow checks. host-dest HIGH, secure-len HIGH.
fmt absent: RAM ONLY. fmt=hex: +UART ONLY (hexdump, not oem USB). fmt=str: +INDIRECT ENV ONLY
  (ascii-checked setenv, RAM env, no saveenv/USB/fastboot). no run_command stitching. DIRECT FASTBOOT never.
```

## answers

```text
19 keys mapped = YES
generic keyman read reaches N keys = 18
generic keyman write reaches N keys = 19 (18 storage + 1 env-diverted)
secure backend reachable = YES
efuse backend reachable = YES
HDCP2 generic reachability = NO
key-permit enforcement = UNKNOWN (ABSENT in BL33)
secure-data-to-host-RAM sink = CONFIRMED
arbitrary write = REFUTED
```

question answered: generically reachable host operations are `keyman read
<18 DTS names> <addr> [hex|str]` (secure/efuse bytes -> host-chosen RAM,
+console/env copies with fmt) and `keyman write <19 DTS names> ...`
(gated, type-checked, into secure/efuse storage except the
`secure_boot_set` env divert). everything else needs a fixed internal
caller or a DTS that is not this one. static only; nothing executed, nothing extracted.
