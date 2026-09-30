# round24 06: output sink (static, code-exact)

## 6.1 query -> malloc -> read -> copy (where length is born)

```
do_keyman_read 0x37e750c4:
  x20 = strtoul(argv[2], NULL, 16)          ; @0x37e75104, w==64-bit, ==0 reject
  rc  = key_info_query 0x37e74c0c(name, &[x29+0x30])  ; LENGTH BORN HERE
  rc  = key_manage_read 0x37e74d18(name, x20, [x29+0x30])
key_info_query:
  dev_exist 0x37e74ba4 -> 0x1f8 on unknown
  *len==0 -> 0x1fc
  type_resolve -> 0x202 on unknown
  type==2 -> *len = 0x386
  typemagic==0 path -> *len = 0x11
  else len_lookup 0x37e73aa0 -> device [+0x28] gate + [+0x18] tell
key_manage_read:
  re-query, clamp queried>=arg else 0x1ca (dead on shell path: equal)
  malloc(0x10000) staging @0x37e74dfc         ; secure reads land here first
  per-type leg -> device_read or DIRECT amlkey_read
  free(staging) before return, every leg
low reader 0x37e8bdc8:
  status = SMC 0x61; cbnz -> fail, no touch
  w2 = [OUT+0] (secure-reported u32); x1 = OUT+4
  str w2,[x22] (*caller_len_ptr = len)
  memcpy(caller_buf, OUT+4, w2)               ; NO clamp vs caller len
```

limits: query path has none beyond device-reported sizes; the low copy
trusts secure-reported len against a 0x10000 staging buffer, so a lying
secure world could overflow staging -- but len comes from secure world,
not host. overflow `dst+len`: no check against the caller allocation
(the caller IS an argv address, see 6.2). caller verifies rc, not len:
nonzero rc -> `0x26e` print, no fmt handling. CONFIRMED.

## 6.2 host-controlled destination (argv addr -> memcpy dst)

```
argv[2] string -> strtoul(base 16) -> x20 (full x-register, 64-bit)
 -> key_manage_read x1=caller_buf -> device leg x1 / amlkey_read x1
 -> low reader x0=caller_buf -> memcpy dst
 -> (hdcp/mac legs: transform/format loop dst, same register)
```

* width: 64-bit (`mov x23,x1`, `str x1,[x29..]`, `blr` with x-registers).
* truncation: none found (no `w`-narrowing of the address on this path).
* alignment: none checked.
* range checks: `==0` rejected only (`0x263`). no NULL-page, no DRAM-window,
  no TOP check in BL33.
* overflow: `dst+len` unchecked in the low reader.

classification:

```text
host-selected destination = CONFIRMED (argv[2] -> memcpy dst, code-exact)
arbitrary address range   = UNKNOWN (no BL33 check either way; whether an
  address is writable/readable is a property of the MMU + RAM-primitive
  windows, not of keyman; no live probe this round per brief)
```

do NOT call this "arbitrary write": content + length are both
secure-world-controlled (see 07).

## 6.3 fmt=str (setenv path)

tail of `do_keyman_read` (`strcmp=="str"@0x37ebf6d4`):

```
ascii loop over blob (ldrsb + tbz; non-ascii -> "[KM]Msg:key value has
  non ascii, can't pr", return 1)
setenv_helper 0x37e5848c(name=x22, value=addr-buf)
  builds {"setenv", name, value, NULL} + do_setenv 0x37e58294 (argc 3,
  or 2/delete if value empty)
return continues as w19
```

* size limit: env store bound (CONFIG_ENV_SIZE, not parsed in this round;
  blob len itself is secure-reported). UNKNOWN exact bytes here.
* binary NUL: NOT preserved -- value is a C string, first NUL truncates.
* truncation: at first NUL by construction; further env-size truncation
  possible but UNPROVEN here.
* caller return: w19 chain (0 ok), same as silent path.
* persistence: RAM env only (`do_setenv` in-memory store). `saveenv` is a
  SEPARATE command, never called on this path. so: alters RAM env state,
  not persistent storage. CONFIRMED (no bl to saveenv between 0x37e750c4
  and return; consumer table round22 03.4 / round23 03.4 stands).
* USB: blob never enters the `oem` response (return code only). CONFIRMED.

## 6.4 fmt=hex (console path, for completeness)

`hexdump 0x37e735c8(addr, len, 0)` + `[KM]Msg:key len is %d...` prints to
CONSOLE (UART), not to the USB `oem` response (`cb_oem` never forwards
handler stdout). needs a UART tap, not host USB. CONFIRMED edge.
