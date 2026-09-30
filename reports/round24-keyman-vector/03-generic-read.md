# round24 03: generic read (static, code-exact)

chain (shell path):

```
keyman read <name> <addr> [fmt]  (0x37e750c4)
 -> key_info_query 0x37e74c0c(name, &len)      ; length born here, no argv len
 -> key_manage_read 0x37e74d18(name, buf=addr, len)
 -> type_resolve 0x37e7414c                     ; 0 mac / 1 sha1 / 2 hdcp2 / 3 raw
 -> mac  -> device_read 0x37e7394c -> efuse read (mac keys are DTS efuse)
 -> hdcp2-> 3x DIRECT bl amlkey_read 0x37e8c3e4 (caller 4 B + hdcp2key + hdcp2lc128)
 -> else -> device_read 0x37e7394c -> vector ops (blr, runtime)
 -> fmt: silent | hexdump | setenv
```

## 3.1 per-implementation table (aquaman-effective entries)

```text
operation: generic secure read (raw + sha1-typed secure keys, e.g.
  widevinekeybox, hdcp22_fw_private, PlayReadykeybox25, prpubkeybox,
  prprivkeybox, attestationkeybox; plus DTS-normal keys sn1/sn2/mn1/mn2/
  hdcp2_rx/bt_rc_mac/netflix_mgkid/region which share the same vector)
device implementation: 0x37e7609c keymanage_secukey_read
caller: device_read 0x37e7394c @0x37e73a78 ([+0x30] blr), itself called
  from key_manage_read 0x37e74d18 @0x37e74eb0/0x37e75078
validator: device_read gates ([+0x20] query, [+0x28] exist, [+0x18] tell
  size check vs expected, 0x13a on overflow) + key_manage clamp
  (queried>=arg, 0x1ca) + type_resolve DTS gate
C1: namelen + hint + name (0x37e8be34..50), hint = DTS-queried len
C2: [OUT+0]=len (secure-reported, str *len_ptr), memcpy(caller, OUT+4, len)
SMC: 0x82000061 SECURITY_KEY_READ (census site 0x37e8be5c in 0x37e8bdc8)
return: secure len on ok (0x37e8c3e4 returns [x29,#0x20]), 0 on fail
confidence: HIGH (direct bl to amlkey_read inside the vector leg)

operation: generic efuse read (mac/mac_bt/mac_wifi; usid is NOT in
  unifykey so unreachable via keyman: no DTS entry -> 0x198 reject)
device implementation: 0x37e762f4 keymanage_efuse_read
caller: same device_read [+0x30] slot
validator: queried-size vs expected (b.hi -> 0x97 fail), DTS mac typing
  upstream in key_manage (==0x11 ascii path uses this leg too)
C1: n/a (efuse path, no secure-storage C1; goes via 0x37e72d98 ->
  0x37e727a4 DTS efuse node + 0x37e725b8 backend)
C2: n/a (returns efuse bytes to caller buf, no C2 parse)
SMC: efuse family (0x82000030/0x31 class; exact id FAMILY REFERENCE)
return: 0 ok / line-code error
confidence: HIGH for dispatch, MEDIUM for SMC id (wrapper-level)

operation: mac-ascii read (type 0 leg in key_manage_read 0x37e74e20)
device implementation: device_read -> efuse vector (same as above),
  then ascii-format loop into caller buf ('%s%02x' @0x37ed769e)
caller: key_manage_read
validator: len cap 0x10 (b.hi fail -0xa3) + len_lookup must be 0x11 or 6
C1/C2/SMC/return: as efuse read above
confidence: HIGH

operation: hdcp2 read (type 2 leg 0x37e74f3c)
device implementation: DIRECT, no vector:
  1. bl amlkey_read(caller_name, staging, 4) want-ret 4, else 0x15f
  2. bl amlkey_read("hdcp2key", staging+0x28, 0x35e) want-ret, else 0x167
  3. bl amlkey_read("hdcp2lc128", staging+4, 0x24) want-ret, else 0x16f
  4. transform loop 0x386 via 0x37e740d8 -> caller buf
caller: key_manage_read
validator: w23>0x385 else 0x156 (same shape as write side)
C1: name-only per fixed/caller name; C2: len+blob per slot
SMC: 0x82000061 x3
return: 0 ok / line-code
confidence: HIGH (direct bl edges, fixed strings in rodata)

operation: query (length source for ALL shell reads)
device implementation: key_info_query 0x37e74c0c:
  dev_exist 0x37e74ba4 (device lookup + exist op, fail 0x1f8) ->
  *len==0 check (0x1fc) -> type_resolve (0x202) ->
  type==2: *len=0x386; type-magic-0 path: *len=0x11 default;
  else len_lookup 0x37e73aa0 (device [+0x28] gate + [+0x18] tell)
caller: do_keyman_read @0x37e75140; key_manage_read @0x37e74d44 (re-check)
validator: unknown name -> reject before any SMC (0x198/0x269 family)
C1/C2/SMC: query leg uses QUERY/TELL ids (0x60/0x63), never bulk read
return: 0 ok + *len; nonzero aborts read
confidence: HIGH
```

## 3.2 classification tags

```text
EXACT AQUAMAN: dispatch addresses, offsets, flags, DTS key table (19),
  secure SMC ids 0x60/0x61/0x62/0x63/0x64, C1/C2 layouts, fixed hdcp
  strings+sizes, query length derivation.
FAMILY REFERENCE: efuse SMC pair 0x30/0x31 (cited via DTS read_cmd/
  write_cmd + EFUSE_USER_MAX census, not single-site proven here);
  secukey hash/encrypt helpers (0x37ea94a4/9510/951c) semantics.
UNKNOWN: +0x58 field, permit enforcement, secure-side byte semantics,
  IN/OUT capacities.
```
