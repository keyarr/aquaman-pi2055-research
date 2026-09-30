# round21 06: protocol (only demonstrated steps)

## flow (code-exact, runtime addresses in parens)

```
boot / first use
  [0x37fbde50] == 0 ? -> bl 0x37e8bbb8 : skip
    0x82000023 -> [0x37fbde60] (= 0x05000000 IN base)
    0x82000024 -> [0x37fbde58] (= 0x05040000 OUT base)
    0x82000025 -> [0x37fbde68] (= 0x05080000 BLOCK base)
    0x82000027 -> [0x37fbde48] (= 0x40000 size)
    [0x37fbde50] = 1 iff none == 0xffffffff
  else assert [0x37fbde50] == 1 or return -1 (no SMC)

op (example: read 0x61; write/query/status/tell/verify differ only in header)
  x = [IN slot]
  [x+0] = namelen (strlen); [x+4 or +8] = len/flags variant
  memcpy(x+header, name, namelen) [+ memcpy(x+header+namelen, data, datalen) for write]
  smc 0x82000061 (X1/X2/X3 unset)
  if SMC_status != 0: return status, touch no buffer
  else:
    0x61: len = [OUT+0]; *caller_len = len; memcpy(caller, OUT+4, len)
    0x60/65/63: *caller = [OUT+0] (word)
    0x64: memcpy(caller, OUT, 0x20)

control (outside the bulk path)
  boot path 0x37e904ac: [0x37f60878] = 2; SMC 0x82000028(X1=1) -> continue boot
  amlkey_init-ish 0x37e8c1dc: getbuffer -> BLOCK base+size -> store backend check
    -> SMC 0x82000069 (notify_ex, scalar) / SMC 0x8200006a (set_enctype, scalar)
```

request header variants (all start at `[[0x37fbde60]]`):

| op | SMC | header | body |
|---|---|---|---|
| write | 0x62 | u32 namelen @+0, u32 datalen @+4, u32 flags @+8 | name + data |
| read | 0x61 | u32 namelen @+0, u32 hint @+4 | name |
| query/status/tell/verify | 0x60/65/63/64 | u32 namelen @+0 (post-inc store) | name |

response variants (all start at `[[0x37fbde58]]`): `len + bytes` (0x61),
`u32 word` (0x60/65/63), `0x20 bytes` (0x64).

## struct reconstruction

no named struct is recoverable beyond the header/response layouts above.
offsets, sizes, writers, readers, confidence:

| offset | size | meaning | writer | reader | conf |
|---|---|---|---|---|---|
| IN+0 | 4 | namelen (strlen result) | 6 BL33 writers | BL31 (consumes) | CONFIRMED (insns) |
| IN+4 | 4 | datalen (write) / hint (read) / name-start (others*) | BL33 writers | BL31 | CONFIRMED shape, mixed meaning |
| IN+8 | 4 | flags (write only) / name-start (read/others) | BL33 writers | BL31 | CONFIRMED |
| IN+12/8/4 | N | name + [data] bytes | memcpy | BL31 | CONFIRMED |
| OUT+0 | 4 | len (0x61) / status word (others) | BL31 | 5 BL33 readers | CONFIRMED |
| OUT+4 | len | payload (0x61 only) | BL31 | 0x37e8bdc8 | CONFIRMED shape |
| OUT+0..32 | 0x20 | verify blob (0x64) | BL31 | 0x37e8c084 | CONFIRMED shape |

*the 4-writer family uses post-inc `str w2,[x0],#4` so name starts at +4,
not +12. do not merge the two header shapes into one struct.

no field names invented; `namelen/datalen/flags/len/word/blob` are the only
words the instructions justify.

## AML_DATA_PROCESS relation

wrapper `0x37e19ea8`: `X0=0x820000ff, X1=buf, X2=len, X3=opt; smc;
post-flush (bl 0x37e19310)`. callers: bootm, image-load, decrypt, efuse paths
(12 sites). the storage path uses sharemem + bare SMC (no flush, no register
triple). no bl edge in either direction between the storage six and 0x19ea8;
no shared buffer (IN/OUT/BLOCK slots never loaded in 0x19ea8, its buf comes
from its own callers). verdict: NO relation (REFUTED as shared-buffer claim;
coexistence only).

## what is NOT in the protocol

- 0x82000026: never issued. not part of the protocol.
- OUT->IN feedback: none. cache flush around storage staging: none (contrast
  0xff wrapper which flushes; storage relies on mapping attributes).
- BLOCK in the op path: none. BLOCK only appears in the init/backend path.
- bounds check of staging against 0x40000: none.
