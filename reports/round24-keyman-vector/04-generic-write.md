# round24 04: generic write (static, code-exact)

chain (shell path):

```
keyman write <name> <fmt|len> <data|addr>  (0x37e749ac)
 -> key_manage_write 0x37e7430c(name, data, len)
 -> 0x37e73864 (device present?) + type_resolve 0x37e7414c (DTS gate)
 -> jump table @0x37ebea34 (type 0..3)
 -> type 0/1/3: device_write 0x37e73880 -> blr vector (RUNTIME)
 -> type 2:     3x DIRECT bl amlkey_write 0x37e8c450 (FIXED names)
 -> low writer 0x37e8bd10 -> C1 -> SMC 0x62
```

## 4.1 per-implementation table

```text
operation: generic secure write (raw-typed secure/normal keys)
device implementation: 0x37e75e7c keymanage_secukey_write
caller: device_write 0x37e73880 @0x37e73934 ([+0x10] blr, flag-skipped
  exist gate); called from key_manage_write @0x37e74780 (sha1 leg) and
  @0x37e7484c (raw leg)
validator: class==2 check (cset eq @0x37e75ea8) + isEncrypt/keyAttr
  prints + amlkey_write ret==len else 0x34 + sha256 gen/verify
  (0x37e8c508 -> VERIFY 0x64, memcmp loop, 0x50 on mismatch)
C1: namelen + datalen + flags=0 + name + data (0x37e8bd70..a4)
C2: none (status only; amlkey_write returns datalen on ok)
SMC: 0x82000062 SECURITY_KEY_WRITE (+ 0x64 verify after)
return: 0 ok / 0x33/0x34/0x3e/0x50 line-codes
confidence: HIGH (direct bl 0x37e8c450 inside the vector leg, so the
  "generic path never touches amlkey" reading of round22 is REFUTED at
  the device-implementation level; the blr is only the DISPATCH hop)

operation: generic efuse write (mac keys, secure_boot_set, others)
device implementation: 0x37e761f0
caller: same device_write [+0x10] slot (after [+0x20] exist gate,
  because efuse flag +0x38==0)
validator: strcmp(name,"secure_boot_set"): match -> sprintf+setenv
  path (0x37e5e968), else bl 0x37e72ca4 (size==cfg check 0xbb +
  backend write, 0xb7/0xc1 on fail)
C1/C2: n/a (efuse backend, no C1)
SMC: efuse family (FAMILY REFERENCE)
return: 0 ok / line-code
confidence: HIGH dispatch, MEDIUM SMC id

operation: mac write (type 0 leg 0x37e743d8)
device implementation: device_write -> vector (efuse for aquaman mac keys)
caller: key_manage_write
validator: len==0x11 else -0x16; every 3rd char ':' + hexdigit table
  @0x37eb5098 else 0x63/0x68; precheck 0x37e75590==4 else 0x6f;
  len_lookup must be 0x11 or 6 else 0x7c
C1/SMC/return: per device above (secure C1 or efuse backend)
confidence: HIGH

operation: sha1 write (type 1 leg 0x37e74668)
device implementation: device_write -> secure vector (DTS hdcp key is
  secure/sha1 on aquaman)
caller: key_manage_write
validator: len>0x14 else 0xd2; trailing-0x14 memcmp-style check else
  0xe6 + hexdump
confidence: HIGH

operation: hdcp2 write (type 2 leg 0x37e74790)
device implementation: DIRECT, no vector:
  1. bl amlkey_write("hdcp2lc128", buf+4, 0x24)
  2. bl amlkey_write("hdcp2key", buf+0x28, 0x35e)
  3. bl amlkey_write(caller_name, buf, 4)
caller: key_manage_write
validator: len>0x385 else 0x126; LE magic ==0x02000000 else 0x12a;
  0x386 transform loop via 0x37e740d8
confidence: HIGH

operation: raw write (type 3 leg 0x37e74840)
device implementation: straight device_write(name, data, len), no extra
  checks in key_manage
caller: key_manage_write
validator: DTS gate only (type_resolve must yield 3)
confidence: HIGH
```

## 4.2 correction to round23 wording (load-bearing, kept)

round23 02.4 said "whether the secure device's op wraps amlkey_write is
UNPROVEN (no image edge)". that was wrong at one remove: the edge is
`0x37e75e7c -> bl 0x37e8c450` (secure write impl calls amlkey_write
directly) and `0x37e7609c -> bl 0x37e8c3e4` (secure read impl calls
amlkey_read directly). what is runtime-resolved is only WHICH device
impl runs (blr at `0x37e73880/0x37e7394c`), selected by the DTS class.
the generic NAME path therefore reaches SMC 0x61/0x62 through one blr
hop + one direct bl, with validators in between. graph YES stands;
"untransformed argv->SMC" stays REFUTED.
