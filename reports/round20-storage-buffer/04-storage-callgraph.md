# round20 04: storage callgraph - writers, readers, SMC consumers

image/base as in 01. helpers: 0x37eaad30 = strlen, 0x37eaaeec = memcpy
(212 bl sites), 0x37eaae84 = memset (251 bl sites). no device touched.

## 1. writers to the 0x23-buffer (stale content == C1 base)

slot [0x37fbde60] is loaded (never stored, except in init) by:

- 0x37e8bd10+0x60 (write path): `str w0,[x19]; str w22,[x19,#8];
  str w20,[x19,#4]` then 2x memcpy (name, data). x19 = [slot].
- 0x37e8bdc8+0x18 (read path): `str w0,[x19]; str w23,[x19,#4]`
  then 1x memcpy (name). shorter header (query-by-name).
- 0x37e8be98+0x3dc (query): `str w2,[x0],#4` where x0 = [slot]
  (post-increment store of a strlen result), then memcpy.
- 0x37e8bf3c+0x80 / 0x37e8bfe0+0x24 / 0x37e8c084+0xc8 (status/tell/verify):
  same single-`str w2,[x0],#4` + memcpy shape.
- upper wrappers pass the key material down: 0x37e8c484->0x37e8bd10
  (write), 0x37e8c414->0x37e8bdc8 (read), 0x37e8c324->0x37e8be98 (query),
  0x37e8c3ac->0x37e8bfe0 (tell); verify 0x37e8c084 has no bl caller
  (reachable via the 0x37e8c508 trampoline / function-pointer table, not
  via direct bl - same as most 0x37e8cxxx wrappers per 10_ss_callers.txt).

lengths: source = strlen(name) via 0x37eaad30 (bounded by NUL), plus
caller-supplied datalen (w2). destination = [slot] (+0/+4/+8/+12).
no bounds check against [0x37fbde48] (block size) on the write path.
callers: key-manage/unifykey layer (0x37e8c1dc, 0x37e8c450), themselves
called from store/key shells. full chain: shell -> unifykey -> 0x37e8bd10
family -> sharemem -> SMC 0x62/61/60/65/63/64.

## 2. readers of the 0x24-buffer (stale 0x05040000)

slot [0x37fbde58] is loaded by the five read-side functions:

- 0x37e8bdc8: `ldr w2,[x1],#4` + memcpy to caller (len-prefixed blob).
- 0x37e8be98 / 0x37e8bf3c / 0x37e8bfe0: `ldr w1,[x21]; str w1,[x20]`
  (single-word status/tell/query result).
- 0x37e8c084: 0x20-byte memcpy from [slot] to caller (verify digest).

no other code in the image loads [0x37fbde58]. the out-buffer is
read-only from BL33's side; BL31 is the writer.

## 3. block region (stale 0x05080000/0x40000)

- produced: [0x37fbde68] (base) + [0x37fbde48] (size) from 0x25/0x27.
- consumed: only 0x37e8bc84 (returns base, refreshes size via a fresh
  0x27 SMC). callers 0x37e8c238 + 0x37e8c2a8 inside 0x37e8c1dc, which
  stores the returned base into its own context struct ([x19]) and later
  uses it for `memset 0x100` (0x37eaae84) and `bl 0x37e350e8` checks.
- the duplicate 0x05080000 at 0x37f5fd68 belongs to a different struct
  (func-ptr + base + size + byte table) consumed once at 0x37e8c4ac via
  `bl 0x37e35170`. unrelated to storage; ignore for staging.

## 4. SMC consumers (is there a read-C1 -> SMC path?)

yes in pattern, unproven in address:

```text
BL33 stages request into [[0x37fbde60]] -> smc #0 (0x60/61/62/63/64/65)
BL31 writes response into [[0x37fbde58]] -> BL33 copies out
```

this is the only BL33->BL31 interface that moves bulk data (the 0xff
AML_DATA_PROCESS path moves its own buf/len/opt triple instead, and the
0x20/0x21 secmon path moves 0x500 B the same way - see below). if
[0x37fbde60] is currently 0x05000000, then every secure-key read/write
stages through C1's first bytes, and C1's live content is whatever the
last operation left (request remnant or BL31 scratch). the static side of
this path is fully proven; only the current base equality is missing.

## 5. parallel channel: secmon 0x20/0x21 (for contrast)

0x37e19d70: lazy-cache [0x37f71480] via 0x82000020 and [0x37f71488] via
0x82000021, then: if req-type==1, `memcpy([in-cache], [req+0x10], len)`;
`smc #0` with w0=0x82000030/31/32; on success + type==0,
`memcpy([req+0x10], [out-cache], ret)`. efuse path 0x37e562e8 repeats
`bl 0x37e19d68 (0x20) + memcpy 0x500 + bl 0x37e19ea8 (0x10/0x20/0x11/0x12)`
x4. same staging discipline as storage, smaller (0x500 B) and at the far
end of the window (stale 0x050fe000/0x050ff000). proves the firmware treats
these windows as BL31-owned sharemem, not as BL33 heap.

## 6. hygiene notes

- no cache flush surrounds the storage staging (the 0xff wrapper
  0x37e19ea8 has the `add x1,x6,x5; bl 0x37e19310` post-SMC flush; the six
  storage functions issue SMC bare). coherency, if any, is by mapping
  attribute, not by maintenance in BL33.
- no SET_STORAGE_INFO (0x28) or SET_ENCTYPE (0x6a) traffic touches either
  buffer (scalar args only).
- nothing else in the image stores into [[0x37fbde60]] or loads from
  [[0x37fbde58]]: writer/reader sets are closed (modulo indirect calls,
  which for this file are the 0x37e8cxxx wrappers already enumerated).
