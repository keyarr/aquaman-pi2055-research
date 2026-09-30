# round24-key-surface 06: HDCP2 separation

three code paths carry HDCP2 names; all DIRECT (no vector), all fixed strings:

```text
rodata: hdcp2lc128 @0x37ed74f4 (0x24 B), hdcp2key @0x37ed7535 (0x35e B),
        hdcp2 @0x37ed72f7 (type-override probe), mac trio @0x37ebf6e2/0x37ebf674/0x37ebf67b
write leg 0x37e74790 (type 2): len>0x385 else 0x126; LE magic data[0..3]==0x02000000 else 0x12a;
  0x386 transform via 0x37e740d8; 3x bl 0x37e8c450 amlkey_write:
    ("hdcp2lc128",buf+4,0x24), ("hdcp2key",buf+0x28,0x35e), (caller_name,buf,4);
  want-ret exact else 0x138/0x140/0x147.
read leg 0x37e74f3c (type 2): w23>0x385 else 0x156; 3x bl 0x37e8c3e4 amlkey_read:
    (caller_name,staging,4) want 4 else 0x15f; ("hdcp2key",+0x28,0x35e) else 0x167;
    ("hdcp2lc128",+4,0x24) else 0x16f; then 0x386 transform -> caller buf.
type probe 0x37e7414c: DTS-raw + name=="hdcp2" -> type 2 (csel @0x37e74260).
```

## 6.1 verdict per question

```text
hdcp2lc128 / hdcp2key as host argv[1] (generic keyman reachable) = NO.
  reason: neither string is a DTS key-name (19 rows contain neither); type_resolve
  needs a DTS cfg (0x37e756e4 miss -> 0x2a/0x198/0x202/0x269 reject) before any SMC.
  verified: strrefs show the two strings referenced only from 0x37e7430c (write leg)
  and 0x37e74d18 (read leg) as FIXED operands, never as argv-parsed values.
fixed caller only = YES (as secondary slots inside the type-2 flow; the caller-name
  slot carries 4 TRANSFORMED bytes, not raw argv, and fires only inside the
  magic+0x386-shaped flow).
generic vector path = NO (both legs use DIRECT bl, zero blr; the vector is bypassed).
```

on THIS DTS the type-2 flow itself is unreachable from host input: no DTS key
is typed `hdcp2` and no DTS key is named `hdcp2`, so `type_resolve` never
yields 2 for any of the 19 names. the legs exist in code (HIGH) but are dead
for `keyman read/write <19-names>` (HIGH). do not count them as exposed.

## 6.2 confusions to avoid

* `hdcp` (DTS key_2, secure/sha1) is NOT `hdcp2`, NOT `hdcp2key`, NOT
  `hdcp2lc128`. different string, different type, generic path.
* `hdcp2_rx` (DTS key_6, normal/raw) is NOT `hdcp2`. the override probe is
  exact strcmp against `"hdcp2"`; `"hdcp2_rx"` misses it and stays raw/generic.
  CONFIRMED by the csel chain in 0x37e74210..0x37e74264.
* the two fixed reads/writes share the SMC ids (0x61/0x62) and C1/C2 shapes
  with the generic path (same low reader/writer), plus the EXTRA hdcp shape
  gate (magic + size + exact want-ret) that generic names never face.
  same storage family, different front door.
