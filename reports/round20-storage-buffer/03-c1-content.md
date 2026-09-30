# round20 03: C1 content analysis (static, no decrypt, no keys)

file: `reports/round19-candidates/c1-5000000-64k.bin`
size 0x10000 (65536 B), sha256 `4cd2c04f5bf5d712e342312d67c406c5f0d85fd9d391c2cc831715910c91bfa8`
source: Optimus READ_MEM 0x02 + mread at 0x05000000, round19 live session
(stage 16 TPL/BL33). first-64B cross-check MATCH. analyzed here read-only.

## 1. bulk stats

- nonzero 65256/65536 (0.9957). zero-runs >= 8 bytes: none.
- overall byte entropy 7.9967 bits/B; per-16KiB pages 7.9879-7.9898.
  dense, uniform, no sparse regions, no padding, no alignment structure.
- distinct LE u32 words 16384/16384 (every word unique). top-byte-0x82
  words: 56 of 16384 (expected ~64 for uniform random; no SMC-id table).
- eret words (0xd69f03e0): 0. smc#0 words (0xd4000001): 0.
  0x820000xx distinct: 0 (round19 classifier). no vectors, no prologues.
- printable strings >= 6 chars: 99, longest 12 (`l3znkf-+O0(1`).
  all look like random-byte runs through printable range, no words, no
  paths, no `AMLSECU/aml/secure/secmon/bl31/opteed/PSCI/tee/SMC`.
- head: `04 00 00 00 75 73 69 64 6f 6e 32 ...` = u32 4, then `usidon2`,
  then uniform random from offset 11 on.

## 2. header parse vs the storage request format

storage request layout per 01 (0x37e8bd10 family):

```text
[in+0] u32 namelen (strlen of key name)
[in+4] u32 datalen
[in+8] u32 flags/type
[in+12] name bytes (namelen)
[in+12+namelen] data bytes (datalen)
```

C1 head as that struct: namelen=4, datalen=`usid` (=0x64697375),
flags=`on2\xa2` (=0xa2326e6f). name at +12 would be `91 0e ab 6c ...`
(non-ASCII). datalen 0x64697375 (1.6 GiB) is absurd against a 0x40000
block. so C1 is NOT a plaintext storage request at read time.

`usidon2` itself: no match anywhere in BL33 strings (case-insensitive
search for usidon/sidon: zero hits over 279 key/storage strings). it is
not a BL33-known key name. it could be a secure-side key blob label, a
ciphertext fragment that happens to be printable, or heap garbage. the
leading u32 4 does not equal the visible name length 7, so even as
`len + name` it does not parse.

## 3. layout verdicts (exclusion only)

- NOT code: zero eret/SMC/EL3/branch-structure (round19: 993 branch
  mnemonics at density 1.000 is a skipdata artifact on random bytes).
- NOT zero/heap-shaped: 0.996 nonzero, no zero runs, no pointers, no
  freelist shapes.
- NOT plaintext block/filesystem: no headers, no repetition, no ASCII
  structure past offset 11.
- compatible with (indistinguishable): ciphertext, crypto scratch,
  compressed/encrypted key blob, or stale secure-side working buffer.
  entropy alone cannot pick between these, and no decrypt was attempted.

## 4. what C1 does and does not tell us

- does: rules OUT resident BL31/BL32 code at 0x05000000 (at least for the
  first 64 KiB at round19 read time). fills the only previous gap: no dump
  had ever covered C1 (prior bands 0x01000000+16M, 0x37800000+8M,
  0x20000000+1M).
- does not: confirm or deny storage-in staging. a staging buffer that just
  held ciphertext (or that BL31 rewrote after consuming a request) would
  look exactly like this. the stale equality `[0x37fbde60] == C1 base`
  predicts C1 *could* be the request buffer, but the bytes at read time
  are not a live request. both "request buffer between uses" and
  "unrelated secure heap" fit.
- needed to decide: current content of [0x37fbde60] (8 B read). if it still
  equals 0x05000000, C1 is at least the *address* BL33 would stage into;
  if not, the coincidence is dead. content alone cannot close this.
