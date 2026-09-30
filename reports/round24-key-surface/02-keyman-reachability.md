# round24-key-surface 02: keyman reachability (which of the 19)

chain (re-verified):

```text
keyman 0x37e74290 (sub-table 0x37f5e4f8: read->0x37e750c4, write->0x37e749ac)
 -> do_keyman_read 0x37e750c4 / do_keyman_write 0x37e749ac
 -> key_info_query 0x37e74c0c (read gate) / type_resolve 0x37e7414c (both)
 -> key_manage_read 0x37e74d18 / key_manage_write 0x37e7430c
 -> type leg (mac/sha1/hdcp2/raw) -> device_read 0x37e7394c / device_write 0x37e73880
 -> vector blr -> impl
```

## 2.1 selection mechanism (no index, no slot)

* selectable unit is the key NAME string (`argv[1]`, `x22` in
  `do_keyman_read`). disasm `0x37e750d8: ldr x22,[x3,#8]`.
* no numeric index parsing on keyman read/write (no strtoul of a slot,
  no `[slot]` table; `0x37e754b4` walks by strcmp, step `0x68`).
  CONFIRMED negative.
* no wildcard/prefix compare (all name compares are exact strcmp).
  CONFIRMED negative.
* unknown name (no DTS entry): `type_resolve 0x37e7414c` returns nonzero
  (`0x2a` path), `key_info_query` returns `0x1f8/0x1fc/0x202`,
  `do_keyman_read` aborts `0x269` before any SMC; write aborts `0x198`.
  CONFIRMED gate. so reachability = DTS-membership + per-type/device gates.

callers of `key_manage_read 0x37e74d18`: only `0x37e75158`
(`do_keyman_read`) and `0x37e8248c` (fixed internal caller, download-key
path using template `keyman read %s 1080000 str`). callers of
`device_read`: `0x37e73f48` (`do_keyunify`), `0x37e74eb0/0x37e75078`
(both inside `key_manage_read`). no other generic caller. so the only
host-driven entry is `do_keyman_read`; the `0x37e8240c` caller uses a
fixed caller-side name, not host argv.

## 2.2 per-key verdict (read)

```text
0  sn1                YES (explicit name; raw -> generic secure read)
1  sn2                YES (explicit name; raw -> generic secure read)
2  hdcp               YES (explicit name; sha1 -> read takes generic leg; sha1 shape only gates WRITE)
4  mn1                YES (explicit name; raw -> generic secure read)
5  mn2                YES (explicit name; raw -> generic secure read)
6  hdcp2_rx           YES (explicit name; DTS raw/normal -> generic secure read; NOT the hdcp2 type leg)
7  mac_bt             YES (explicit name; mac -> mac-ascii leg -> efuse read 0x37e762f4; len cap 0x10, want 0x11/6)
8  mac                YES (same as mac_bt)
9  mac_wifi           YES (same as mac_bt)
10 widevinekeybox     YES (explicit name; raw secure -> generic secure read)
11 hdcp22_fw_private  YES (explicit name; raw secure -> generic secure read)
12 PlayReadykeybox25  YES (explicit name; raw secure -> generic secure read)
13 bt_rc_mac          YES (explicit name; raw normal -> generic secure read)
14 prpubkeybox        YES (explicit name; raw secure -> generic secure read)
15 prprivkeybox       YES (explicit name; raw secure -> generic secure read)
16 attestationkeybox  YES (explicit name; raw secure -> generic secure read)
17 netflix_mgkid      YES (explicit name; raw normal -> generic secure read)
18 region             YES (explicit name; raw normal -> generic secure read)
3  secure_boot_set    NO  (explicit name accepted by parser/type_resolve, then REFUSED by device gates:
                          efuse [+0x28] 0x37e762cc returns 0 for this name (cset ne) -> device_read 0x134;
                          len_lookup [+0x28] same fail 0x150; dev_exist [+0x20] 0x37e7637c takes the
                          equal-branch. name check, not permit-bit check. CONFIRMED by disasm this round.)
```

read total: **18 YES / 1 NO** out of 19 DTS keys.

fixed names (not DTS, not counted above):

```text
hdcp2lc128 / hdcp2key as argv[1]  NO (no DTS entry -> 0x198/0x269 reject before any SMC)
hdcp2 as argv[1]                  NO on this DTS (no DTS entry named "hdcp2" -> same reject;
                                    the type-2 leg is dead for host input here; fixed slots fire only
                                    as secondary reads inside that leg, see 06)
numeric index (e.g. "3")          NO (no slot parsing; "3" is just a name miss -> reject)
```

## 2.3 per-key verdict (write, for contrast)

all 19 names pass `type_resolve` (DTS membership). dispatch:

```text
0,1,2,4,5,6,10..18  YES -> device_write[+0x10] -> 0x37e75e7c (secure) or efuse per device
7,8,9 (mac)         YES -> device_write -> 0x37e761f0 (efuse), mac validator ==0x11 + ':' + hexdigit
3 secure_boot_set    YES (parser-accepted) but DIVERTED: 0x37e761f0 strcmp-match -> sprintf+setenv
                     path (0x37e5e968), never reaches efuse storage backend. counts as write-reachable,
                     not as storage-write.
```

write total: **19 names accepted / 18 reach storage backends / 1 diverted to env**.

## 2.4 confidence

HIGH for mechanism (every edge disassembled this round: argv load,
strtoul base-16, query gate, strcmp walk, vector blr slots, impl bl).
MEDIUM for SMC ids on efuse legs (family reference, DTS read_cmd/write_cmd
+ census, not single-site). reachability labels above are BL33-code
reachability, not secure-world authorization.
