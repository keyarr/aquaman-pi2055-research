# round24-key-surface 05: output path, host destination, fmt handling

## 5.1 key_manage_read -> backend -> C2 -> len -> caller -> argv dest

shell path (disasm this round):

```text
do_keyman_read 0x37e750c4:
  x20 = strtoul(argv[2], NULL, 16)          ; @0x37e750f4..0x37e75100, 64-bit x0 return
  rc  = key_info_query 0x37e74c0c(name, &[sp+0x30])   ; LENGTH BORN HERE, no argv len
  rc  = key_manage_read 0x37e74d18(name, x20, [sp+0x30])
key_manage_read:
  re-query @0x37e74d44; clamp queried>=arg else 0x1ca (dead-equal on shell path)
  type_resolve @0x37e74dbc; fail -> 0x1d0
  malloc(0x10000) staging @0x37e74dfc
  type 0 mac-ascii leg @0x37e74e20 (cap 0x10, want 0x11/6, device_read, ascii-format loop)
  type 2 hdcp leg @0x37e74f3c (w23>0x385 else 0x156; 3x DIRECT amlkey_read + 0x386 transform)
  else generic @0x37e7506c: device_read 0x37e7394c(name, caller_buf, len)
  free(staging) on every leg
low reader 0x37e8bdc8 (secure legs):
  C1 [IN+0x00]=namelen, [IN+0x04]=hint(=expected len), [IN+0x08..]=name; SMC 0x61
  status=X0; cbnz -> fail, no touch
  w2=[OUT+0] (secure-reported u32); x1=OUT+4
  str w2,[len_ptr]; memcpy(caller_buf, OUT+4, w2)   ; NO clamp vs caller len
  amlkey_read returns secure len on ok, 0 on fail
efuse legs: no C1/C2; 0x37e72d98/0x37e727a4 backend bytes -> caller buf;
  size pre-check b.hi -> 0x97 fail.
```

per-backend output classification (shape only, no plaintext claims):

```text
secure generic (0x37e7609c, 15 keys): C2 [u32 len + blob] -> staging -> caller RAM.
  returned length = secure-reported u32 ([OUT+0], mirrored to *len_ptr).
  maximum = UNKNOWN (no IN/OUT capacity in image; 0x10000 is staging, 0x40000 is BLOCK, neither is the C2 limit).
  aligned = NO requirement (memcpy w2 bytes, no alignment check).
  status accompanies blob = YES but out-of-band (SMC X0; nonzero => no copy, error print only).
  metadata precedes blob = NO on caller buffer (len is returned via *len_ptr + w return, not prepended;
    only the transient C2 slot has [len][blob]).
  class = opaque blob. CONFIRMED shape, HIGH.
mac/efuse (0x37e762f4, 3 keys): efuse bytes -> staging -> ascii-format loop -> caller RAM.
  returned length = DTS cfg size path (0x37e72c40/0x37e73aa0), capped 0x10 in the ascii leg.
  class = opaque blob (ascii-shaped on the caller copy). HIGH.
hdcp2 direct (dead on this DTS, see 06): per-slot len+blob (4 / 0x24 / 0x35e) + 0x386 transform.
  class = opaque blob. HIGH (edge exists, reachability NO).
write paths: status only, no OUT parse. class = status. CONFIRMED.
```

no crypto/format evidence in BL33 around OUT (the `0x6a enctype` switch
never branches on the read copy). plaintext-vs-ciphertext UNPROVEN.

## 5.2 host destination restrictions (argv base -> RAM)

```text
base==0 rejected: YES (cbnz @0x37e75108 else print + 0x263). CONFIRMED.
width = 64-bit: YES (strtoul full x0 -> mov x20 -> x-registers through key_manage/device/low reader;
  no w-narrowing of the address). CONFIRMED.
alignment requirement: NONE (no and/cmp on low bits). CONFIRMED negative.
destination range checks: NONE (no NULL-page / DRAM-window / TOP check in BL33). CONFIRMED negative.
size interaction: NONE on the copy (low reader memcpy(dst, OUT+4, secure_len) has no dst+len check;
  device_read has a queried-vs-expected check 0x13a but expected==queried on shell path, and the
  low copy itself is unclamped). CONFIRMED.
overflow checks: NONE (dst+len unchecked). CONFIRMED negative.
```

therefore:

```text
host-controlled destination = HIGH (CONFIRMED code-exact)
secure-controlled length = HIGH (CONFIRMED: query/tell/C2, never argv)
secure-controlled content = HIGH (CONFIRMED: no host byte on read path)
```

this is a secure-data-to-host-RAM sink, NOT an arbitrary write (host
controls no content byte and no length bit). the only host-shaped bytes
in keyman are WRITE-path data, which face DTS + per-type validators
before storage.

## 5.3 fmt=str / fmt=hex (tail of do_keyman_read, 0x37e75194..0x37e75234)

```text
no fmt word (x21==NULL): silent, blob stays at argv addr only. return 0. CONFIRMED.
fmt=hex (strcmp @0x37ed7572 == 0): hexdump 0x37e735c8(addr, len, 0) + "[KM]Msg:key len is %d" print.
  destination = CONSOLE (UART). cb_oem never forwards handler stdout, no fastboot-send call on path.
  class = UART ONLY. needs UART tap, not host USB. CONFIRMED edge.
fmt=str (strcmp @0x37ebf6d4 == 0): ascii loop (ldrsb + tbz bit31; non-ascii -> print + return 1),
  then setenv_helper 0x37e5848c(name=x22, value=addr-buf) -> {"setenv",name,value} + do_setenv 0x37e58294.
  binary NUL truncates (C string). size bound = env store bound (CONFIG_ENV_SIZE, not parsed here).
  persistence = RAM env only; saveenv is a SEPARATE command, never bl-called on this path.
  USB/fastboot response = none (return code only). class = INDIRECT ENV ONLY. CONFIRMED edge,
  chain to later exfil via other commands UNPROVEN (mechanism-only, not executed).
other word: "Err key dataFmt" print, blob stays at argv addr. CONFIRMED.
```

answers:

```text
keyman read -> fmt=str -> environment -> run_command: NO (no run_command/saveenv/USB/fastboot call
  between 0x37e750c4 and return; consumer table round22 03.4 / round23 03.4 stands).
keyman read -> setenv (RAM only): YES.
saveenv / USB response / fastboot response on this path: NONE. CONFIRMED negatives.
host-readable automatically: NO (RAM ONLY by default; UART ONLY with hex; INDIRECT ENV ONLY with str;
  DIRECT FASTBOOT never).
```
