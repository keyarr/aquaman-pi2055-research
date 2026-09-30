# round24 05: validator map (static, code-exact)

gate order on both paths: DTS cfg -> type_resolve -> per-type shape ->
device op gates. a failure anywhere aborts before bulk SMC.

## 5.1 type_resolve 0x37e7414c (name -> 0..3)

* reads DTS key-type for the name (entry+0x30, default "raw").
* strcmp against 4-entry list @`0x37eb5058`: `{mac, sha1, hdcp2, raw}`
  -> type 0..3.
* DTS-raw + name override: `mac|mac_bt|mac_wifi` -> 0, `hdcp2` -> 2.
* unknown name / no DTS cfg -> nonzero return -> write `0x198`,
  read-query `0x202`/`0x269`. CONFIRMED.

so `keyman write` is generic in SYNTAX (any string parses) but NOT in
REACHABILITY: the DTS limits the usable set, and the type selects the
shape check. "really generic" = NO; "DTS-limited generic front" = YES.

## 5.2 per-type validators

```text
MAC (type 0, 0x37e743d8):
  minimum  = maximum = 0x11 (17 ascii chars), -0x16 else
  alignment: none
  format:   every 3rd char ':' (0x3a), others hexdigit (table @0x37eb5098
            mask 0x44); violations 0x63/0x68
  fixed prefix/name: none (any DTS-mac name; aquaman: mac/mac_bt/mac_wifi)
  destination: device_write -> efuse backend (aquaman) or secure C1
  extra: precheck 0x37e75590==4 else 0x6f; len_lookup in {0x11, 6} else 0x7c
  confidence: HIGH

SHA1 (type 1, 0x37e74668):
  minimum: >0x14 (20), 0xd2 else; maximum: 0x10000 (numeric parser cap)
  alignment: none
  format: trailing-0x14 suffix discipline (memcmp-style, 0xe6 + hexdump)
  fixed prefix/name: none (aquaman: hdcp)
  destination: device_write -> secure vector (DTS secure)
  confidence: HIGH

HDCP2 (type 2, 0x37e74790 write / 0x37e74f3c read):
  minimum: >0x385 (901); maximum: 0x10000
  alignment: none
  format: LE magic data[0..3]==0x02000000 else 0x12a; 0x386 transform loop
  fixed names: hdcp2lc128 (0x24) + hdcp2key (0x35e) + caller 4 B
  destination: DIRECT amlkey_write/read, exact want-ret match else
    0x138/0x140/0x147 (write) / 0x15f/0x167/0x16f (read)
  confidence: HIGH

RAW (type 3, 0x37e74840):
  minimum: none beyond parser (len!=0 numeric, hex/ascii strlen);
  maximum: 0x10000 (numeric cap; hex/ascii bounded by oem truncation)
  alignment/format/fixed-name: none
  destination: device_write -> secure or efuse vector per DTS key-device
  confidence: HIGH
```

## 5.3 parser-level caps (before type dispatch)

```text
write hex: len=strlen/2, malloc(len), hex decode else 1; no code cap
write str: len=strlen, every byte <0x80 else 1; no code cap
write num: len=strtoul(base 0), 0 -> 0x2bb; >0x10000 -> 0x2bf;
           addr=strtoul(base 16), no range check (used as pointer)
read:      addr=strtoul(base 16), ==0 -> 0x263; NO len argv at all
```

## 5.4 permit bits (NOT a BL33 gate)

parsed into entry+0x5c (1 read / 2 write / 4 del) from DTS `key-permit`,
but no BL33 read/write/query path loads +0x5c. enforcement UNKNOWN
(secure-world side). do NOT cite key-permit as a RE-checked gate.
note the DTS still matters: `secure_boot_set` is write-only AND gets a
code special-case in efuse read/exist/write (`secure_boot_set` strcmp
in `0x37e761f0/0x37e76268/0x37e7637c`), so a read is refused with
"can't read, is configured secured?"-family prints. that is a NAME
check, not a permit-bit check. CONFIRMED (strings `0x37ecfa08`,
`0x37ed7cbd`).
