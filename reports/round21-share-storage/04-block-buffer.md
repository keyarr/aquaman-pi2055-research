# round21 04: block buffer (0x05080000, size 0x40000)

slots: `[0x37fbde68]` base (runtime 0x05080000), `[0x37fbde48]` size (runtime
0x40000). producers: init `0x37e8bbb8` (0x25/0x27 returns) + getbuffer
`0x37e8bc84` (fresh 0x27 refresh + return base). static only.

## who writes

nobody in BL33 stores into `[[0x37fbde68]]`. code-exact: the only load of the
slot is `0x37e8bcd8` (getbuffer return). BL31 owns the bytes. the duplicate
stale word at `0x37f5fd68` is not a write: it is snapshot content of struct
`0x37f5fd60 = [ptr][u64 base][u32 size][byte table]`, consumed once at
`0x37e8c4ac` (see below), never stored by code in this image.

## who reads

exactly one BL33 consumer chain, both call sites inside `0x37e8c1dc`
(amlkey_init-ish, fstring `amlkey_init`):

```
0x37e8c234: x0 = sp+0x34 (size out-ptr); bl 0x37e8bc84   ; base returned in x0
0x37e8c23c: str x0,[x19]                                 ; [ctx+0] = block base
0x37e8c25c..: w22 transformation; bl 0x37e8c14c (0x6a set_enctype, scalar)
0x37e8c268: x0 = [ctx]; w1 = [ctx+8]; x2 = sp+0x30; bl 0x37e350e8
            (store_key_read backend check)
0x37e8c27c: cbz w0 -> ok path
0x37e8c280: x0 = [ctx]; w1 = w21; x2 = 0x100; bl memset (0x37eaae84)
            ; memset(block_base, ?, 0x100) — only bounded use, 256 B
0x37e8c294..: [ctx+8] update; 0x37e8c2a0: bl 0x37e8bcfc (0x69 notify_ex, scalar)
0x37e8c2a4: x0 = sp+0x34; bl 0x37e8bc84 again           ; re-get base+size
0x37e8c2ac: str x0,[x19]
0x37e8c2b4: compare [sp+0x34] vs [sp+0x30]; b.ne fail
0x37e8c2c0: clear bit in [0x37f72b5c] on match
```

second reader: `0x37e8c450` (amlkey_write) tail:

```
0x37e8c4ac: x1 = 0x37f5fd68-struct; x0 = [x1] (stale block copy)
0x37e8c4c0: w1 = [x1+8]; x2 = sp+0x20; bl 0x37e35170 (store_key_write)
```

`0x37e350e8`/`0x37e35170` are bootloader-state dispatchers (`[0x37f60878]`
selector written as 2 by the 0x28 path; `sub w3,#1; cmp #4; b.hi` + `br x5`
jump table). fstrings: `store_key_read` / `store_key_write`.

## size questions

- `0x40000` is capacity reported by BL31 (0x27 return), stored to
  `[0x37fbde48]` and refreshed on every getbuffer call. not a BL33 constant
  (no literal 0x40000 feeds it; the 6 stale `0x40000` words include the slot
  content, not code immediates for this).
- physical vs reported: from BL33 side, only *reported*. BL33 never probes
  the region (no read/write loop over it, no fault test). whether BL31 backs
  all 0x40000 is invisible here.
- max used (demonstrated): 0x100 (memset at `0x37e8c28c`). everything else is
  backend-internal (`store_key_read/write` take base+len args but their bodies
  dispatch out of this image region via the state table at `0x37e90bf8/0x37e90cb4`).
- block index / offset / sector / alignment ops: none in BL33. zero
  `lsl #9`, `and #0x1ff`, sector arithmetic, or index*size around the block
  base. the `lsl`/`udiv` at `0x37e8c588+` belong to an unrelated clock helper,
  not storage.

## role

input, output, or scratch? none of the three in the IN/OUT sense:

- not an input: BL33 never stages a request into it (no memcpy/str into
  `[[0x37fbde68]]`).
- not an output: BL33 never parses it (no ldr/memcpy from it except handing
  the *base* to the store backend).
- scratch/region handle: YES (CONFIRMED shape). BL33 treats it as an opaque
  base+size pair: getbuffer hands it to `store_key_read/write` and memsets
  0x100 on one error path. internal division (if any) lives behind the
  backend dispatcher / in BL31, not in this code.

geometry note (static, DTB-exact): IN 0x05000000 + OUT 0x05040000 (+0x40000)
+ BLOCK 0x05080000 (+0x80000, size 0x40000 -> ends 0x050c0000) are
non-overlapping, 0x40000-aligned, all inside `linux,secmon
alloc-ranges <0x5000000 0x400000>`. tidy but tidiness is not the evidence;
the SMC->global edges + getbuffer discipline are.
