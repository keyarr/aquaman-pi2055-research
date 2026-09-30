# keyman vector round24 (consolidated, static only)

image `reports/round14-bl33-persist/bl33-37e18000.bin` base `0x37e18000`.
DTS `artifacts/aquaman.dts` (`gxl_aquaman_1g`, RAM-extracted).
no device, no reads, no SMC, no commands run. detail: `reports/round24-keyman-vector/01..07`.

round23 closed the CONTRACT (argv roles, C1/C2 layouts, gates, output
destinations). this round closes the MECHANISM behind the generic hop:
the vectors are static, the key array is DTS-populated, each device leg
is reconstructed, and the secure legs are shown to call amlkey directly
(one blr dispatch hop + one direct bl, validators in between).

## main table

```text
operation
  -> DTS/device
  -> implementation
  -> validator
  -> C1
  -> SMC
  -> C2
  -> host-controlled destination
  -> length source
  -> classification
```

```text
secure read (raw/sha1 secure+normal keys)
  -> key-device secure/normal -> ops 0x37f5e478
  -> 0x37e7609c via device_read [+0x30] (query+exist+tell gates first)
  -> DTS cfg + type_resolve + queried>=arg clamp
  -> C1 [namelen,hint,name], hint=queried len
  -> 0x82000061 READ (direct bl 0x37e8c3e4 inside the leg)
  -> C2 [len,blob], *len_ptr=len, memcpy(caller,OUT+4,len), staging freed
  -> YES (argv[2] base-16 -> memcpy dst, 64-bit, !=0 only)
  -> secure (query/tell/C2, never argv)
  -> secure-data-to-host-RAM sink CONFIRMED; arbitrary write REFUTED

efuse read (mac/mac_bt/mac_wifi)
  -> key-device efuse -> ops 0x37f5e4b8
  -> 0x37e762f4 via same [+0x30] slot (size check b.hi 0x97)
  -> DTS mac typing (==0x11 ascii leg) + cfg-size match
  -> n/a (efuse backend 0x37e72d98/0x37e727a4, no C1)
  -> efuse family (FAMILY REFERENCE)
  -> n/a, bytes to caller buf
  -> YES (same argv addr mechanism)
  -> DTS cfg size
  -> same classification

secure write (raw/sha1 secure+normal keys)
  -> same secure vector
  -> 0x37e75e7c via device_write [+0x10] (flag skips exist gate)
  -> class==2 + isEncrypt/keyAttr + ret==len + sha256 verify (0x64)
  -> C1 [namelen,datalen,flags=0,name,data]
  -> 0x82000062 WRITE (+0x64 VERIFY), direct bl 0x37e8c450 inside leg
  -> none (status only, returns datalen)
  -> n/a (write stores, no host RAM output)
  -> host-influenced, type-checked, <=0x10000
  -> gated generic write CONFIRMED

efuse write (mac keys, secure_boot_set, ...)
  -> efuse vector (-> [+0x10] after [+0x20] exist gate, flag==0)
  -> 0x37e761f0 (secure_boot_set strcmp -> setenv path, else 0x37e72ca4)
  -> DTS gate (+ mac shape upstream for mac keys)
  -> n/a (efuse backend)
  -> efuse family (FAMILY REFERENCE)
  -> none
  -> n/a
  -> host-influenced, type-checked
  -> gated generic write CONFIRMED

hdcp2 read/write (fixed)
  -> name-shaped flow, DTS hdcp2 typing + magic
  -> DIRECT 3x bl amlkey_read/write (hdcp2lc128 0x24, hdcp2key 0x35e,
     caller 4 B), no vector
  -> len>0x385 + LE magic 0x02000000 + 0x386 transform + exact want-ret
  -> same C1/C2 shapes per slot
  -> 0x61 / 0x62
  -> per-slot len+blob
  -> read: YES (same argv addr); write: n/a
  -> read: fixed 0x386/0x24/0x35e/4; write: shaped host data
  -> fixed-name direct path CONFIRMED, generic-name NO
```

## objective answers

```text
generic read implementation      = 0x37e7609c secure / 0x37e762f4 efuse
generic write implementation     = 0x37e75e7c secure / 0x37e761f0 efuse
device selected by DTS           = key-device -> 1:0x37f5e4b8 / 2,3:0x37f5e478
validator chain                  = DTS cfg -> type 0..3 -> mac/sha1/hdcp2/raw
                                   shapes -> device gates -> exact want-ret
read length source               = 0x37e74c0c query (no argv len)
output destination controlled    = YES
output length controlled         = NO
secure-data-to-host-RAM sink     = YES (mechanism; window reach UNKNOWN)
arbitrary payload write          = REFUTED
```

central question -- `host -> keyman read/write -> exact DTS-selected
device -> secure world`: secure/normal DTS keys run `0x37e75e7c` /
`0x37e7609c` (direct bl to amlkey 0x62/0x61 + verify/query/tell gates);
efuse DTS keys run `0x37e761f0` / `0x37e762f4` (efuse backend via
`0x37e727a4`); hdcp2-typed flows bypass the vector with fixed-name
direct bl sites. limits: validators in 05, `0x10000` staging/numeric
cap, no argv length on read, argv address only (`!=0`) on both paths.
no other primitive sought, nothing executed.
