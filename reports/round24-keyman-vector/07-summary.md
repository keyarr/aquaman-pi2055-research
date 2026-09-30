# round24 07: summary (static, code-exact)

## 7.1 the primitive, exactly

```text
host-controlled destination (argv addr, 64-bit, !=0 only)
+ secure-world-controlled bytes (C2 blob / efuse bytes)
+ secure-world-controlled length (query/tell/C2 len, never argv)
= secure-data-to-host-selected-RAM sink
```

verdict: CONFIRMED as a MECHANISM (every link code-exact: 01/03/06).
"arbitrary write" for host PAYLOAD: REFUTED (host controls no content
byte on the read path, and no length either). the only host-shaped
bytes on any keyman path are WRITE-path data, which face DTS +
per-type validators before storage (05).

## 7.2 fixed hdcp2 paths

```text
hdcp2lc128 / hdcp2key = fixed-name direct path = CONFIRMED
generic host-selected name reaching the same direct edge = NO
  (the direct bl sites take FIXED rodata names; the caller-name slot in
  the hdcp flow carries 4 transformed bytes, not raw argv, and fires
  only inside the magic+0x386-shaped flow)
same validator/device backend: YES for storage (amlkey 0x61/0x62, same
  C1/C2 shapes, exact want-ret sizes 0x24/0x35e/4), with the EXTRA hdcp
  shape gate (magic + size) that generic names never face.
```

no key content examined, no secret names tested, nothing executed.

## 7.3 answers (objective, no hedging words beyond the labels)

```text
generic read implementation      = secure: 0x37e7609c (via device_read
                                   [+0x30], direct bl amlkey_read 0x61);
                                   efuse: 0x37e762f4 (via same slot,
                                   efuse backend); hdcp2: DIRECT
                                   3x amlkey_read (fixed names)
generic write implementation     = secure: 0x37e75e7c (via device_write
                                   [+0x10], direct bl amlkey_write 0x62
                                   + verify 0x64); efuse: 0x37e761f0
                                   (via same slot, efuse backend);
                                   hdcp2: DIRECT 3x amlkey_write
device selected by DTS           = key-device prop -> class 1/2/3 ->
                                   0x37f5e4b8 (efuse) / 0x37f5e478
                                   (secure+normal); per-key array DDR
                                   @[0x37f89fe0], stride 0x68, 19 entries
validator chain                  = DTS cfg (0x198/0x269) -> type_resolve
                                   0..3 -> mac ==0x11+':' / sha1 >0x14+
                                   suffix / hdcp2 >0x385+magic+0x386
                                   transform / raw DTS-only ->
                                   device exist/query/tell gates ->
                                   exact want-ret on fixed slots
read length source               = key_info_query 0x37e74c0c (dev_exist
                                   + type + len_lookup/tell/fixed
                                   0x11/0x386); NO argv len exists
output destination controlled    = YES (argv[2] base-16 -> memcpy dst)
output length controlled         = NO (secure-reported; host has no input)
secure-data-to-host-RAM sink     = YES (mechanism CONFIRMED; exploitability
                                   depends on RAM-primitive windows = UNKNOWN)
arbitrary payload write          = REFUTED (read path carries no host bytes)
```

## 7.4 residual UNKNOWNs (do not promote without new ground truth)

* entry+0x58 (read by `0x37e75524`, writer not found).
* key-permit enforcement point (parsed, no BL33 consumer).
* efuse SMC ids at single-site certainty (FAMILY REFERENCE: DTS
  `read_cmd`/`write_cmd` + census, wrapper-level only).
* C1/C2 capacities (no IN/OUT size in image; `0x10000` = staging,
  `0x40000` = BLOCK, neither is the C1/C2 limit).
* blob semantics (opaque: shape CONFIRMED, plaintext-vs-cipher UNPROVEN).
* host-readability of the chosen RAM through mread/Optimus windows
  (no live probe per brief).

no device touched, no commands run, no secrets requested. `git diff --check` clean.
