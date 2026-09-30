# round21 02: who writes C1 (IN 0x05000000)

slot: `[0x37fbde60]`, runtime 0x05000000 (round20 probe). code never holds
0x05000000 as a literal (word scan: 1 hit = the slot content itself; movz/movk
and adrp/add scans: zero builders). every writer below uses
`ldr xN,[0x37fbde60]` then stores/copies into `xN`. static only.

helpers: `0x37eaad30` = strlen, `0x37eaaeec` = memcpy. no DMA, no memset, no
strcpy-like beyond memcpy, no loop-stores into IN besides the header `str`s.

## writer 1: 0x37e8bd10 (write path -> SMC 0x62)

```
x19 = [0x37fbde60]                    ; 0x37e8bd60 ldr
w0 = strlen(x21=name)                 ; 0x37e8bd70 bl
[x19+0] = w0 (namelen)                ; str w0,[x19]
[x19+8] = w22 (flags/type, arg w3)    ; str w22,[x19,#8]
[x19+4] = w20 (datalen, arg w2)       ; str w20,[x19,#4]
x19 += 0xc
memcpy(x19, x21/name, namelen)
memcpy(x19+namelen, x23/data, datalen)
SMC 0x82000062
```

source: caller x0=name ptr, x1=data ptr, w2=datalen, w3=flags.
dest: `[[0x37fbde60]]` (+0/+4/+8/+12). length: 12 + namelen + datalen.
caller: `0x37e8c484` in `0x37e8c450` (amlkey_write). origin above that:
`key_manage_write 0x37e7430c` (3 call sites: keyman shell path + unifykey
DTB init) and `keymanage_secukey_write 0x37e75e7c` (function-table, no bl
caller). classification: eMMC/env/DTB-controlled key material + caller data;
constrained by key-format checks in 0x37e7430c (mac/hdcp2 special cases).
not raw host bytes: no fastboot/usb download buffer flows here (proven by
caller census: only the two amlkey paths above).

## writer 2: 0x37e8bdc8 (read path -> SMC 0x61)

```
x19 = [slot]; x24 = [0x37fbde58]      ; 0x37e8be18/0x37e8be24 ldrs
w2 = strlen(x20=name)
[x19+0] = namelen; [x19+4] = w23 (arg w2, size/len hint)
memcpy(x19+8, x20/name, namelen)
SMC 0x82000061
```

shorter header (query-by-name, 8 + namelen). source: caller name + len hint.
caller: `0x37e8c414` in `0x37e8c3e4` (amlkey_read). above: `key_manage_read
0x37e74d18` <- `0x37e750c4` (unifykey userspace shim, no bl caller = table) +
`0x37e8240c` (store shell path) and `0x37e7609c` (secukey_read, table).
also reachable from fastboot/usb via `0x37e94838` -> amlkey_read wrapper
(see 05). classification: filesystem/eMMC-controlled name; host can *trigger*
reads via fastboot/usb but the bytes staged into C1 are the key name, not
host payload.

## writers 3-6: query/status/tell/verify (single-word header + name)

identical shape, only SMC id and response differ:

```
x0 = [slot]                            ; ldr x22/x19
w2 = strlen(x19=name arg)
str w2,[x0],#4                         ; [in+0] = namelen, post-inc
memcpy(x0, name, w2)
SMC 0x60 / 0x65 / 0x63 / 0x64
```

- 0x37e8be98 query -> 0x60, caller `0x37e8c324` (amlkey_isexsit).
- 0x37e8bf3c status -> 0x65, caller `0x37e8c1a4` (amlkey_get_attr).
- 0x37e8bfe0 tell -> 0x63, caller `0x37e8c3ac` (amlkey_size).
- 0x37e8c084 verify -> 0x64, no bl caller (via `0x37e8c508` trampoline /
  function-pointer table, same as most 0x37e8cxxx wrappers).

lengths: 4 + namelen. no datalen, no flags. no bounds check against
`[0x37fbde48]` (0x40000) on any of the six paths (code-exact: no load of the
size slot in these functions).

## closed set

7 adrp/add sites reference `0x37fbde60`: init store + the 6 loaders above.
nothing else in the 0x1d8000 image loads the slot (code-exact scan, round20
02). modulo indirect calls (already enumerated: the 0x37e8cxxx wrappers are
the indirect targets), the writer set is closed.

## classification

| writer | source | dest | len | caller | input origin | class |
|---|---|---|---|---|---|---|
| 0x37e8bd10 | name ptr + data ptr + w2/w3 | [[slot]] | 12+strlen+datalen | amlkey_write | shell/DTB/env key + data | filesystem/env-controlled, NOT raw host |
| 0x37e8bdc8 | name ptr + w2 hint | [[slot]] | 8+strlen | amlkey_read | shell/DTB/fastboot-triggered name | filesystem-controlled |
| 0x37e8be98 | name ptr | [[slot]] | 4+strlen | amlkey_isexsit | shell name | internal/generated |
| 0x37e8bf3c | name ptr | [[slot]] | 4+strlen | amlkey_get_attr | shell name | internal/generated |
| 0x37e8bfe0 | name ptr | [[slot]] | 4+strlen | amlkey_size | shell/fastboot-triggered name | internal/generated |
| 0x37e8c084 | name ptr | [[slot]] | 4+strlen | table/trampoline | unknown caller via table | unknown |

`host controlled` (arbitrary host bytes -> C1): NO evidence. the only
host-reachable edges stage a *key name* chosen from BL33 shell/DTB vocab, and
the write path (the only one that stages bulk data) has no fastboot/usb
caller. secure-world-returned content in C1 between ops is BL31 scratch, not
a writer in BL33 scope.

flow proven: `caller args -> strlen/memcpy -> [[0x37fbde60]] -> SMC 0x60-65`.
`[[0x37fbde60]] == 0x05000000` is runtime CONFIRMED, so every op above stages
through C1's first bytes.
