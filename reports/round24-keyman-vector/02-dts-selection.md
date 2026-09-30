# round24 02: DTS selection (static, code-exact)

DTS source: `artifacts/aquaman.dts` (RAM-extracted blob, `gxl_aquaman_1g`).
code: `0x37e757ec` parser + `0x37e75590` class getter + `0x37e73380` selector.

## 2.1 DTS nodes that matter (only these)

```text
/unifykey {
  compatible = "amlogic, unifykey"; status = "ok";
  unifykey-num = <0x13>;                       ; 19 keys
  key_0..key_18 { key-name; key-device; [key-type]; key-permit; }
/securitykey {
  compatible = "aml, securitykey";
  storage_query = <0x82000060>; storage_read = <0x82000061>;
  storage_write = <0x82000062>; storage_tell = <0x82000063>;
  storage_verify = <0x82000064>; storage_status = <0x82000065>;
  ... in/out/block/size/enctype/version funcs ...
}
/efuse { compatible = "amlogic, efuse"; read_cmd = <0x82000030>;
         write_cmd = <0x82000031>; get_max_cmd = <0x82000033>; }
/secmon { in_base_func = <0x82000020>; out_base_func = <0x82000021>; }
```

`/securitykey` gives the SMC NUMBERS the secure legs use (matches the
census: 0x60/0x61/0x62/0x63/0x64/0x65). `/efuse` gives the efuse family.
`/secmon` gives the sharemem base funcs. `/unifykey` gives the per-key
routing. nothing else in the DTS influences keyman dispatch. CONFIRMED
by the parser only reading `/unifykey*` props (plus `dtb_mem_addr` env
for the fdt base).

## 2.2 aquaman key table (DTS data, not code)

| # | key-name | key-device | key-type | key-permit |
|---|---|---|---|---|
| 0 | sn1 | normal | (raw) | read,write,del |
| 1 | sn2 | normal | (raw) | read,write,del |
| 2 | hdcp | secure | sha1 | read,write,del |
| 3 | secure_boot_set | efuse | (raw) | write |
| 4 | mn1 | normal | (raw) | read,write,del |
| 5 | mn2 | normal | (raw) | read,write,del |
| 6 | hdcp2_rx | normal | (raw) | read,write,del |
| 7 | mac_bt | efuse | mac | read,write |
| 8 | mac | efuse | mac | read,write |
| 9 | mac_wifi | efuse | mac | read,write |
| 10 | widevinekeybox | secure | (raw) | read,write,del |
| 11 | hdcp22_fw_private | secure | (raw) | read,write,del |
| 12 | PlayReadykeybox25 | secure | (raw) | read,write,del |
| 13 | bt_rc_mac | normal | (raw) | read,write,del |
| 14 | prpubkeybox | secure | (raw) | read,write,del |
| 15 | prprivkeybox | secure | (raw) | read,write,del |
| 16 | attestationkeybox | secure | (raw) | read,write,del |
| 17 | netflix_mgkid | normal | (raw) | read,write,del |
| 18 | region | normal | (raw) | read,write,del |

(raw) = no `key-type` prop in DTS, parser defaults entry+0x30 to `"raw"`.
note `hdcp2_rx` is DTS-typed raw/normal here; the `hdcp2` TYPE id in code
comes from `type_resolve` name-override (`name=="hdcp2"`), a different
key name than `hdcp2_rx`. do not conflate them.

## 2.3 the edge, property by property

```text
DTS unifykey-num
 -> fdt_getprop @0x37e758f8, rev, str [0x37f5e5e8] (count)
 -> cap 32 (0x37e75990, error 0x143), malloc(num*0x68)
 -> bounds every later loop. CONFIRMED.

DTS key-name (per /unifykey/key_%d)
 -> fdt_getprop @0x37e75b24, len<=0x2f else error
 -> memcpy(entry+0x00) + NUL
 -> strcmp target in 0x37e754b4 (device lookup by NAME). CONFIRMED.

DTS key-device ("normal"/"secure"/"efuse")
 -> fdt_getprop @0x37e75bb8, strcmp triple @0x37e75c00/18/34
 -> str 3/2/1 @entry+0x54  (normal=3, secure=2, efuse=1)
 -> 0x37e75590 returns entry+0x54
 -> 0x37e73380: 1->0x37f5e4b8, 2/3->0x37f5e478, else NULL
 -> selects secure vs efuse IMPLEMENTATION. CONFIRMED.

DTS key-type ("mac"/"sha1"/"hdcp2"/absent)
 -> fdt_getprop @0x37e75c4c, default strcpy "raw" @entry+0x30
 -> read by 0x37e75650 (entry+0x40 path) and type_resolve 0x37e7414c
 -> selects mac/sha1/hdcp2/raw VALIDATOR (jump table @0x37ebea34).
 CONFIRMED (mechanism; the exact fdt->type_resolve call reads the same
 entry field, verified by string xrefs to "key-type" @0x37ed7b5c).

DTS key-permit ("read"/"write"/"del" substrings)
 -> entry+0x5c bits 1/2/4 @0x37e75d70..d8
 -> NO BL33 consumer found (full-image scan for +0x5c loads: none
    outside the parser). enforcement UNKNOWN, presumably secure-world.
 recorded, not claimed.

DTS key-encrypt
 -> entry+0x40 (<=0xf). consumed by secukey paths as isEncrypt print
    + hash/select logic. CONFIRMED parsed; semantic effect MEDIUM
    (needs secure-world ground truth).
```

## 2.4 what selection does NOT depend on

* driver strings: `compatible` is never compared on this path (no strcmp
  against `"amlogic, unifykey"` etc found in key functions). the parser
  finds `/unifykey` by PATH (`/unifykey/key_%d` sprintf), not by driver.
* `status`: never read by the parser (no "status" getprop in `0x37e757ec`).
* `__symbols__`/phandles: the parser uses formatted paths, not phandles.
* efuse `key_0..key_3` (`mac/mac_bt/mac_wifi/usid` offsets): the BL33
  keyman path does not read `/efusekey` at all; efuse offsets come from
  `0x37e727a4` DTS lookups at runtime, not from unifykey entries.

verdict: device selection = `key-device` prop -> class int -> static ops
struct. type validation = `key-type` prop (+ name overrides) -> validator.
both edges code-exact. a driver string alone selects nothing. CONFIRMED.
