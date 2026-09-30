# round24-key-surface 07: exposure matrix + summary

static only. no device, no reads, no SMC, no commands run. base `0x37e18000`.

## 7.1 exposure matrix (read path; write has no host-visible output)

```text
key | generic keyman read | backend | secure-world data returned | host-controlled dest | host-visible output | confidence
sn1 | YES | secure vector 0x37e7609c (normal generic) | opaque blob (C2 len+bytes) | YES (argv addr) | RAM ONLY (UART ONLY with fmt=hex; INDIRECT ENV ONLY with fmt=str) | HIGH
sn2 | YES | secure vector (normal generic) | opaque blob | YES | RAM ONLY (+hex/env w/ fmt) | HIGH
hdcp | YES | secure vector (secure generic, sha1-typed) | opaque blob | YES | RAM ONLY (+hex/env) | HIGH
secure_boot_set | NO (device name-gate refusal) | efuse vector, diverted on write | none on read (reject before SMC) | n/a | NO | HIGH
mn1 | YES | secure vector (normal generic) | opaque blob | YES | RAM ONLY (+hex/env) | HIGH
mn2 | YES | secure vector (normal generic) | opaque blob | YES | RAM ONLY (+hex/env) | HIGH
hdcp2_rx | YES | secure vector (normal generic, raw; NOT hdcp2 leg) | opaque blob | YES | RAM ONLY (+hex/env) | HIGH
mac_bt | YES | efuse 0x37e762f4 via mac-ascii leg | opaque blob (ascii-shaped) | YES | RAM ONLY (+hex/env) | HIGH
mac | YES | efuse via mac-ascii leg | opaque blob (ascii-shaped) | YES | RAM ONLY (+hex/env) | HIGH
mac_wifi | YES | efuse via mac-ascii leg | opaque blob (ascii-shaped) | YES | RAM ONLY (+hex/env) | HIGH
widevinekeybox | YES | secure vector (secure generic) | opaque blob | YES | RAM ONLY (+hex/env) | HIGH
hdcp22_fw_private | YES | secure vector (secure generic) | opaque blob | YES | RAM ONLY (+hex/env) | HIGH
PlayReadykeybox25 | YES | secure vector (secure generic) | opaque blob | YES | RAM ONLY (+hex/env) | HIGH
bt_rc_mac | YES | secure vector (normal generic) | opaque blob | YES | RAM ONLY (+hex/env) | HIGH
prpubkeybox | YES | secure vector (secure generic) | opaque blob | YES | RAM ONLY (+hex/env) | HIGH
prprivkeybox | YES | secure vector (secure generic) | opaque blob | YES | RAM ONLY (+hex/env) | HIGH
attestationkeybox | YES | secure vector (secure generic) | opaque blob | YES | RAM ONLY (+hex/env) | HIGH
netflix_mgkid | YES | secure vector (normal generic) | opaque blob | YES | RAM ONLY (+hex/env) | HIGH
region | YES | secure vector (normal generic) | opaque blob | YES | RAM ONLY (+hex/env) | HIGH
hdcp2lc128 (fixed, non-DTS) | NO | direct 3x amlkey (dead on this DTS) | n/a (unreachable) | n/a | NO | HIGH
hdcp2key (fixed, non-DTS) | NO | direct 3x amlkey (dead on this DTS) | n/a (unreachable) | n/a | NO | HIGH
```

host-visible categories used: NO / RAM ONLY / UART ONLY / INDIRECT ENV ONLY.
DIRECT FASTBOOT appears nowhere on the keyman read path (return code only
reaches `oem` USB). UNKNOWN not needed: every cell above is code-decided.
"host-visible" is NOT inferred from RAM presence alone.

## 7.2 objective answers

```text
19 keys mapped = YES (verbatim DTS names, 01)
generic keyman read reaches 18 keys = 18 (all except secure_boot_set; 02)
generic keyman write reaches 19 keys = 19 names accepted, 18 reach storage, 1 diverted (02.3)
secure backend reachable = YES (15 keys via 0x37e75e7c/0x37e7609c; 03)
efuse backend reachable = YES (3 mac keys via 0x37e761f0/0x37e762f4; secure_boot_set diverted/refused; 02+03)
HDCP2 generic reachability = NO (fixed slots only, type-2 leg dead on this DTS; 06)
key-permit enforcement = UNKNOWN overall (ABSENT in BL33, secure-world side unexamined; 04)
secure-data-to-host-RAM sink = CONFIRMED (argv addr + secure len/content; 05)
arbitrary write = REFUTED (no host content/length bit on read; 05)
```

## 7.3 what was NOT done (per brief)

no `keyman read` executed on any real key. no HDCP/DRM/key material
extracted. no brute force. no permit bypass attempted. blob semantics stay
`opaque blob`; never upgraded to plaintext/ciphertext. host-readability of
the chosen RAM through mread/Optimus windows stays a RAM-primitive question,
answered elsewhere, not here.
