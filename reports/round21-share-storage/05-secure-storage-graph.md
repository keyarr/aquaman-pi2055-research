# round21 05: secure_storage_* call graph (names vs functions)

literal-name audit (whole 0x1d8000 image, case-sensitive): zero hits for
`secure_storage`, `secure_storage_init`, `secure_storage_getbuffer`,
`bl31_storage_read/write/query/status/tell/verify`, `secure_storage_set_info`,
`secure_storage_set_enctype` as strings, and zero `bl` targets by those names
(the image is stripped; names below come from DTB props, fstrings, and
round14 IDS mapping). the functional graph exists under different names.
this is a naming fact, not a missing edge.

## actual BL33 names (fstring-proven)

| brief name | VA | fstrings | role |
|---|---|---|---|
| init | 0x37e8bbb8 | none (called lazily everywhere) | 0x23/24/25/27 -> globals + flag |
| getbuffer | 0x37e8bc84 | none | BLOCK base + fresh 0x27 size |
| write | 0x37e8bd10 | none | stage -> SMC 0x62 |
| read | 0x37e8bdc8 | none | stage -> SMC 0x61 -> copy-out |
| query | 0x37e8be98 | none | stage -> SMC 0x60 -> word |
| status | 0x37e8bf3c | none | stage -> SMC 0x65 -> word |
| tell | 0x37e8bfe0 | none | stage -> SMC 0x63 -> word |
| verify | 0x37e8c084 | none (via 0x37e8c508 trampoline) | stage -> SMC 0x64 -> 0x20 B |
| set_info | 0x37e8c138 | none | SMC 0x28 scalar |
| set_enctype | 0x37e8c14c | none | SMC 0x6a scalar |
| notify_ex | 0x37e8bcfc | none | SMC 0x69 scalar (w2,w1,w0 passthrough) |
| amlkey_write | 0x37e8c450 | `amlkey_write` | -> write + store_key_write |
| amlkey_read | 0x37e8c3e4 | `amlkey_read` | -> read |
| amlkey_isexsit | 0x37e8c2ec | `amlkey_isexsit` | -> query |
| amlkey_get_attr | 0x37e8c16c | `amlkey_get_attr` | -> status |
| amlkey_size | 0x37e8c374 | `amlkey_size` | -> tell |
| amlkey_init-ish | 0x37e8c1dc | `amlkey_init` | getbuffer + 0x6a + 0x69 + backend checks |
| key_manage_* | 0x37e7430c etc | `key_manage_write/read/query_size/query_exist/query_secure` | shell/DTB layer above amlkey_* |
| store_key_read/write | 0x37e350e8/0x37e35170 | `store_key_read/write` | backend dispatcher (state table) |

callers (bl-exact): amlkey_write <- `0x37e8c484` only from 0x37e8c450 is
backwards; correctly: `0x37e8bd10 <- 0x37e8c484 (in 0x37e8c450)`;
`0x37e8bdc8 <- 0x37e8c414 (in 0x37e8c3e4)`;
`0x37e8be98 <- 0x37e8c324 (in 0x37e8c2ec)`;
`0x37e8bf3c <- 0x37e8c1a4 (in 0x37e8c16c)`;
`0x37e8bfe0 <- 0x37e8c3ac (in 0x37e8c374)`;
`0x37e8c084 <- trampoline 0x37e8c508 <- 0x37e75f78 (in 0x37e75e7c)`;
getbuffer <- `0x37e8c238 + 0x37e8c2a8` (both in 0x37e8c1dc).
upper: 0x37e8c450 <- `0x37e748a0/0x37e748f8/0x37e7494c (in key_manage_write
0x37e7430c)` + `0x37e75f20 (in 0x37e75e7c)`; key_manage_read path <-
`0x37e750c4` (table) + `0x37e8240c` (store shell) + fastboot/usb `0x37e94838`
(read-side only: query/size/read wrappers).

## brief questions answered

- `secure_storage_init`: functional equivalent = `0x37e8bbb8` (lazy, flag-gated).
  direct use of 0x05000000/0x05040000/0x05080000? NO (stores SMC returns, never
  literals; code-exact).
- `secure_storage_getbuffer`: equivalent = `0x37e8bc84`. returns runtime
  `[[0x37fbde68]]` (= 0x05080000) + `*size` (= 0x40000). direct literal? NO;
  global->SMC-returned-pointer->load, which the brief accepts as valid
  evidence: YES, this is the accepted-indirect edge for BLOCK.
- `bl31_storage_read/write/query/status/tell/verify`: equivalents =
  `0x37e8bdc8/0x37e8bd10/0x37e8be98/0x37e8bf3c/0x37e8bfe0/0x37e8c084`.
  each loads `[[0x37fbde60]]` (= 0x05000000) as staging dest and 5/6 load
  `[[0x37fbde58]]` (= 0x05040000) as copy-out src. accepted-indirect edge: YES
  for IN (all six) and OUT (five).
- `secure_storage_set_info` (0x28): = `0x37e8c138`, caller `0x37e90614`.
  uses buffers? NO (scalar X1=1, code-exact). REFUTED for buffer use.
- `secure_storage_set_enctype` (0x6a): = `0x37e8c14c`, caller `0x37e8c264`.
  uses buffers? NO (scalar, code-exact). REFUTED for buffer use.

## graph (only demonstrated edges)

```
keyman/keyunify shell, unifykey DTB, store shell, fastboot/usb (read-side)
  -> key_manage_* (0x37e7430c/0x37e74d18/...)
    -> amlkey_* (0x37e8c450/0x37e8c3e4/0x37e8c2ec/0x37e8c16c/0x37e8c374)
      -> low writers (0x37e8bd10/0x37e8bdc8/0x37e8be98/0x37e8bf3c/0x37e8bfe0/0x37e8c084)
        -> [[0x37fbde60]] = 0x05000000 (IN staging, memcpy)
        -> SMC 0x60/61/62/63/64/65 (no register args)
        -> [[0x37fbde58]] = 0x05040000 (OUT parse: len+blob / word / 0x20 B)
      -> amlkey_init-ish 0x37e8c1dc
        -> getbuffer -> [[0x37fbde68]] = 0x05080000 + size 0x40000
        -> store_key_read/write backend (state-gated)
        -> scalar 0x69 / 0x6a
  -> boot path 0x37e904ac -> 0x28 scalar (store selector = 2)
```

no function in this graph takes 0x05000000/0x05040000/0x05080000 as an
immediate; all reach them via the SMC-return globals. that indirection is the
whole design (BL33 never hardcodes the secmon window; DTB only describes it).
