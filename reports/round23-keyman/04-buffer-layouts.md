# round23 04: C1 / C2 buffer layouts (static, code-exact)

slot globals (populated once by `sharemem_setup 0x37e8bbb8` via
SMC `0x23/0x24/0x25/0x27`; integrity flag @`0x37fbde50` must read 1):

```text
[0x37fbde60] = IN base  (runtime 0x05000000, SMC 0x23)
[0x37fbde58] = OUT base (runtime 0x05040000, SMC 0x24)
BLOCK [0x37fbde68]/size [0x37fbde48]: never touched on op paths (round22 04.4)
```

X1/X2/X3 unset at all 60..65 sites; stub `0x37e8bba0` (`smc #0; ret`).

## 4.1 C1 write layout (`low writer 0x37e8bd10`, x0=name, x1=data, w2=len, w3=flags)

```
0x37e8bd70: bl strlen(name) -> w0
0x37e8bd74: str w0, [IN]        ; +0x00 namelen  u32
0x37e8bd78: str w22, [IN,#8]    ; +0x08 flags    u32 (= w3, always 0 upstream)
0x37e8bd7c: str w20, [IN,#4]    ; +0x04 datalen  u32
0x37e8bd80: x22 = namelen (zero-extended)
0x37e8bd84: IN+0x0c
0x37e8bd94: memcpy(IN+0x0c, name, namelen)
0x37e8bd98: x0 = IN+0x0c+namelen
0x37e8bda4: memcpy(IN+0x0c+namelen, data, datalen)
0x37e8bda8: x0=0x62, movk 0x8200 -> SMC
```

```text
C1 (write, SMC 0x62):
+0x00 u32 namelen  = strlen(host-or-fixed name)   CONFIRMED
+0x04 u32 datalen  = w2 (validated upstream)      CONFIRMED
+0x08 u32 flags    = w3 = 0 constant              CONFIRMED
+0x0c ..  name bytes (namelen, NO trailing NUL)   CONFIRMED
+0x0c+namelen .. data bytes (datalen)             CONFIRMED
total staged = 12 + namelen + datalen. NO capacity check in the
writer (straight memcpy pair). IN capacity itself UNKNOWN statically
(BL31 reports no IN size; only BLOCK size 0x40000 is known).
effective bound comes from upstream validators (02), not from C1.
```

per-field source/confidence:

```text
+0x00 | u32 | namelen      | derived (strlen of name ptr) | CONFIRMED
+0x04 | u32 | datalen      | host-influenced, type-checked| CONFIRMED
+0x08 | u32 | flags        | constant 0                   | CONFIRMED
+0x0c | ... | name bytes   | fixed-or-gated host name     | CONFIRMED
+0x0c+n|... | data bytes   | format-checked host data     | CONFIRMED
```

no C struct invented: offsets are the `str` immediates above.

## 4.2 C1 read layout (`low reader 0x37e8bdc8`, x0=name, x1=caller_buf, w2=hint, x3=len_ptr)

```
0x37e8be34: bl strlen(name)
0x37e8be3c: str w0, [IN]        ; +0x00 namelen u32
0x37e8be40: str w23, [IN,#4]    ; +0x04 hint    u32 (= w2)
0x37e8be44: x0 = IN+8
0x37e8be50: memcpy(IN+8, name, namelen)
0x37e8be54: x0=0x61, movk -> SMC
```

```text
C1 (read, SMC 0x61):
+0x00 u32 namelen = strlen(name)                  CONFIRMED
+0x04 u32 hint    = w2 (caller len / expected)    CONFIRMED
+0x08 ..  name bytes (namelen, no NUL)            CONFIRMED
```

on the shell path hint = DTS-queried len (03.3), not raw argv.

## 4.3 C2 / output layout (read only; write has no OUT parse)

```
0x37e8be60: x19 = SMC X0 status; cbnz => fail (no touch), return status
0x37e8be68: x1 = OUT base (loaded pre-SMC @0x37e8be2c, reused)
0x37e8be6c: ldr w2,[x1],#4   ; w2 = [OUT+0] = len (secure-reported), x1=OUT+4
0x37e8be70: x0 = caller_buf (arg x1)
0x37e8be74: str w2,[x22]     ; *caller_len_ptr (arg x3) = len
0x37e8be7c: memcpy(caller_buf, OUT+4, w2)
0x37e8be80: return 0 (status path value)
```

```text
C2 (SMC 0x61 response):
+0x00 u32 len  (secure-reported)                  CONFIRMED
+0x04 ..  blob (len bytes)                        CONFIRMED (shape only)
```

copy chain: `C2 -> staging(malloc 0x10000) -> caller RAM @argv-addr`
(hdcp leg inserts the `0x386` transform loop before the caller copy;
mac leg inserts the ascii-format loop; generic leg copies via device op).
upper wrappers never `printf` the blob on the silent path (errors only).

content classification: **opaque blob** (len + bytes shape CONFIRMED,
plaintext-vs-ciphertext UNPROVEN; no crypto/format evidence in BL33).
the `0x6a enctype` switch exists but BL33 never branches on it around
OUT (round22 04.3). no upgrade of this verdict without secure-world
ground truth.

## 4.4 C1 vs C2 protocol (read vs write)

```text
write: populate C1[namelen,datalen,flags=0,name,data] -> SMC 0x62
       -> status only (stub ret ignored; epilogue uses backend rc).
       amlkey_write returns datalen on ok (0 on SMC-fail) + mirrors to
       store_key_write backend (0x37e8c4ac path, eMMC side).
read:  populate C1[namelen,hint,name] -> SMC 0x61
       -> status gate -> parse C2[len,blob] -> caller buf + *len.
       amlkey_read returns secure len on ok (0 on fail).
```

differences: write C1 carries bulk data + flags, expects no C2;
read C1 carries name only, expects C2 len+blob. both share the
`[flag]==1` sharemem-ready check and the no-register-arg convention.

## 4.5 size-limit table (independent per field)

```text
field            | input width | internal width | max effective | clamp | evidence
name ptr (w)     | argv string | strlen u32     | oem 33 B cmd  | DTS gate + strlen | 01, 02.1
hex data         | strlen/2    | malloc(len)    | oem-truncated | none in code      | 0x37e749f4
ascii data       | strlen      | memcpy len     | oem-truncated | byte<0x80 each    | 0x37e74a84 loop
numeric len      | strtoul b0  | w2 u32         | 0x10000       | cmp+0x2bf fail    | 0x37e74b10
numeric addr     | strtoul b16 | x1 pointer     | 64-bit RAM    | !=0 only          | 0x37e74b48
mac data         | 0x11 ascii  | device op      | ==0x11        | eq + ':' checks   | 02.3
sha1 data        | >0x14       | device op      | >0x14         | cmp+0xd2 fail     | 02.3
hdcp2 data       | >0x385      | 0x386 transform| >0x385+magic  | cmp+magic fail    | 02.3
C1 total         | 12+n+d      | memcpy pair    | UNKNOWN       | none in writer    | 04.1
read hint        | DTS query   | u32            | device-len    | queried>=arg      | 03.2
C2 len           | secure u32  | memcpy w2      | UNKNOWN       | none in reader    | 04.3
staging bufs     | malloc      | 0x10000        | 0x10000       | fixed arg         | 0x37e743a8/0x37e74dfc
fixed slots      | 0x24/0x35e/4| amlkey pass    | exact-match   | ret==want else err| 02.3/03.2
```

C1/C2 capacities: UNPROVEN (no BL33-side size query for IN/OUT;
only BLOCK size `0x40000` is reported). do NOT present `0x40000` or
`0x10000` as the C1/C2 limit: staging is `0x10000`, BLOCK is `0x40000`,
IN/OUT limits are simply not in the image.
