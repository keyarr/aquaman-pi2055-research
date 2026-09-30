# round21 03: who reads C2 (OUT 0x05040000)

slot: `[0x37fbde58]`, runtime 0x05040000. BL33 never stores into
`[[0x37fbde58]]` (zero stores in image). BL31 is the sole writer
(secure side fills response after SMC 0x60/61/63/64/65). 6 adrp/add sites:
init store + 5 loaders below. closed set.

## reader 1: 0x37e8bdc8 (read -> SMC 0x61), the only bulk copy-out

```
x24 = [0x37fbde58]            ; 0x37e8be24 ldr (before SMC)
... SMC 0x61 ...
cbnz x0 -> fail (no parse)
x1 = x24
ldr w2,[x1],#4                ; [out+0] = len, post-inc x1 past it
str w2,[x22]                  ; *caller_len_ptr = len (x22 = arg x3)
memcpy(x21/caller_buf, x1, w2); x21 = arg x1
return SMC status (0 on this path)
```

so OUT layout for 0x61: `[+0] u32 len; [+4] len bytes payload`.
dest: caller buffer. length: BL31-returned len (untrusted from BL33 view, but
no overflow analysis attempted: caller allocated it).
above: amlkey_read -> key_manage_read -> unifykey/store/fastboot paths.
content class: key blob / value bytes. encryption state UNKNOWN (see below).

## readers 2-4: query/status/tell (single word)

```
... SMC 0x60/0x65/0x63 ...
cbnz x0 -> fail
ldr w1,[x21]                  ; [out+0] word, x21 = [slot]
str w1,[x20]                  ; *caller = word, x20 = arg x1
```

- 0x37e8be98 query: exists/status word.
- 0x37e8bf3c status: attr word.
- 0x37e8bfe0 tell: size word.
content class: status/metadata (u32). not key material, not plaintext payload.
no parsing beyond the copy to caller stack slot (`add x1,x29,#0x20` at upper
wrappers, then error-print on nonzero).

## reader 5: 0x37e8c084 (verify -> SMC 0x64), fixed 0x20

```
... SMC 0x64 ...
cbnz x0 -> fail
memcpy(x21/caller, x22/OUT, 0x20)   ; x21 = arg x1, x22 = [slot]
```

OUT layout for 0x64: first 0x20 bytes = digest/comparison blob, copied
unconditionally (no len prefix). content class: 32-byte verify material
(likely hash/digest by size, but name not proven: call it 0x20-B blob).
encryption: UNKNOWN. no decrypt in BL33 around it (no crypto call between
SMC return and memcpy).

## what OUT does NOT do

- never parsed as struct beyond word/len/0x20 (no field splits, no offsets).
- never branched on content except `cbnz SMC_status` (register, not buffer).
- never forwarded to another SMC or to IN (no OUT->IN edge in any function).
- never stored to eMMC/env directly: upper wrappers copy OUT word to stack,
  then either return it or print `[KM]Error` / `[store]Err`. the bulk payload
  (0x61) goes to the caller's buffer (key_manage_read), which returns up to
  shell/unifykey/fastboot.

## plaintext/status/etc verdict

| reader | OUT bytes used | delivered as | class | confidence |
|---|---|---|---|---|
| 0x37e8bdc8 | [+0] len + [+4..] payload | memcpy to caller buf | key blob, plaintext-vs-cipher UNKNOWN | CONFIRMED shape, UNKNOWN content |
| 0x37e8be98/0x37e8bf3c/0x37e8bfe0 | [+0] u32 | `*caller = word` | status/metadata | CONFIRMED |
| 0x37e8c084 | [+0..0x20) | 0x20-B memcpy | verify blob (digest-sized, unnamed) | CONFIRMED shape, UNKNOWN meaning |

no evidence OUT holds plaintext keys vs encrypted blobs: the enctype switch
(`0x8200006a`, see 01/04) exists but BL33 never branches on it around OUT, and
no crypto helper touches the copy-out path. do not claim either.
