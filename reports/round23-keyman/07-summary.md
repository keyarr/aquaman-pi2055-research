# round23 07: summary + error map (static, code-exact)

## 7.1 error map (real codes/strings; w19 line-codes mirror key_manage.c lines)

write (`do_keyman_write` parser level):

```text
argc'<=3               | -1  | silent (usage)                              | CONFIRMED
hex decode fail        | 1   | "Fail in change hex argv[3] to bin, err=%d" | CONFIRMED
non-ascii in str fmt   | 1   | "inputFmt is %s, but argv[3] contain non ascii" | CONFIRMED
len==0 (numeric)       | 0x2bb | "dataLen err"                             | CONFIRMED
len>0x10000 (numeric)  | 0x2bf | "keylen 0x%x too large!"                  | CONFIRMED
key_manage rc !=0      | 1   | (key_manage already printed)                | CONFIRMED
```

write (`key_manage_write` level, selected):

```text
device/init fail       | 0x192 | "[KM]Error:f[%s]L%d:" + "key_manage_write" | CONFIRMED
unknown name/no DTS    | 0x198 | same header + "key %s not know device %d"-family | CONFIRMED
mac len !=0x11         | -0x16 | mac-format family                          | CONFIRMED
mac char violations    | 0x63/0x68 | hexdigit/':' checks                   | CONFIRMED
not-4-code prechecks   | 0x6f  | hdcp-precheck family                       | CONFIRMED
len not 0x11/6         | 0x7c  | len_lookup family                          | CONFIRMED
hex/ascii backend fail | 0x91  | decrypt family                             | CONFIRMED
sha1 short (<=0x14)    | 0xd2  | sha1 family                                | CONFIRMED
sha1 memcmp mismatch   | 0xe6  | hexdump + fail                             | CONFIRMED
hdcp2 short (<=0x385)  | 0x126 | hdcp2 family                               | CONFIRMED
hdcp2 magic mismatch   | 0x12a | "Version value 0x%x is error, should be..."-family | CONFIRMED
hdcp2 fixed-write lens | 0x138/0x140/0x147 | "Fail in write hdcp2 ..."     | CONFIRMED
```

read:

```text
argc'<=2               | -1  | silent                                      | CONFIRMED
addr==0                | 0x263 | "Fail in parse argv[2] to dataBuf"        | CONFIRMED
info query fail        | 0x269 | (query already printed)                   | CONFIRMED
manage read fail       | 0x26e | "Fail in read key[%s] at sz %zd"          | CONFIRMED
non-ascii (str fmt)    | 1   | "[KM]Msg:key value has non ascii, can't pr" | CONFIRMED
bad fmt word           | (print) | "[KM]Msg:Err key dataFmt(%s)"           | CONFIRMED
keysize > bufLen       | 0x1ca | size family (dead on shell path)          | CONFIRMED
unknown name           | 0x1c6/0x269 | query family                        | CONFIRMED
```

read vs write vs query split (kind, from code not names):

```text
write path | bulk store, C1 carries data, SMC 0x62, status-only back | CONFIRMED
read path  | addressed fetch, C1 name-only, C2 len+blob to RAM       | CONFIRMED
query path | console status words (exist/size/secure), NO amlkey_*,
           | NO SMC 60..65 edge from any command                     | CONFIRMED
```

so `keyman` is a generic-but-gated storage front (DTS allowlist +
per-type validators), not an admin-limited wrapper and not an open
bulk pipe: names are allowlisted by DTS, shapes by type, sizes by
exact-match on the fixed slots.

## 7.2 final verdicts (CONFIRMED / UNPROVEN / REFUTED only)

```text
keyman write:
  host controls name/data? YES, GATED (DTS cfg + type validators) — CONFIRMED
  reaches SMC 0x62? YES (hdcp fixed names direct; others via runtime
    device vector) — CONFIRMED (mechanism), generic-name direct edge UNPROVEN
  size bounded? YES (per-type exact/inequality clamps + 0x10000 numeric cap) — CONFIRMED
  names restricted? YES (DTS cfg required; unknown => reject) — CONFIRMED

keyman read:
  host controls name? YES, GATED (same DTS gate; hint/len NOT argv) — CONFIRMED
  reaches SMC 0x61? YES (hdcp leg direct incl. caller-name 4-B read;
    generic leg via runtime device vector) — CONFIRMED (mechanism)
  output type? opaque blob (len+bytes shape CONFIRMED; plaintext vs
    cipher UNPROVEN) — CONFIRMED as opaque blob
  output destination? caller RAM @argv addr (host-chosen) + freed heap
    staging; optional console hexdump / env setenv with fmt word — CONFIRMED
  host-readable through existing RAM-read path? UNKNOWN — UNPROVEN
    (no live probe; depends on RAM-primitive windows, not on keyman)
```

## 7.3 corrections to round22 (load-bearing)

1. generic write hop is `0x37e73880 -> blr` device vector (runtime
   DTS-bound), NOT a direct `bl amlkey_write` with raw argv. the direct
   sites are hdcp fixed-name (+4-B caller-name inside hdcp flow) only.
   graph YES stands; "untransformed argv->SMC" does NOT (REFUTED,
   validators + dispatch in between).
2. read has NO argv length input: hint/len is DTS-queried (`0x37e74c0c`).
   round22's "dest addr+C2" stands; "length control" does not exist.
3. `0x37e5848c` on the read `str` path is `setenv(name, blob)` (argv
   `{"setenv",name,value}` + `do_setenv`), and `0x37e735c8` on the
   `hex` path is a console hexdump. both CONFIRMED new output edges
   (console/env, still not USB).
4. C1/C2 capacities: UNPROVEN (no IN/OUT size in image). `0x10000` is
   the heap staging size, `0x40000` the BLOCK size; neither is the
   C1/C2 limit. do not cite them as such.

## 7.4 non-claims

- no key extraction, no credential disclosure, no exploit. the blob
  class stays "opaque blob".
- no live probe, no device touched, no `keyman read/write` executed,
  no secret slots touched. static only; `git diff --check` clean.
- the contract now closed:
  `host -> keyman read/write (validated) -> C1/C2 -> secure world`,
  with exact argv roles, exact C1/C2 layouts, exact gates, and exact
  output destinations above. what enters and leaves is known; what the
  bytes MEAN is not (secure-world side UNPROVEN).
