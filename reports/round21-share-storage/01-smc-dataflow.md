# round21 01: SMC dataflow 0x23/24/25/27/28 (+ consumers)

image: `reports/round14-bl33-persist/bl33-37e18000.bin`, base 0x37e18000,
sha256 `664fb34a...`. method: capstone disasm of bytes on disk + `tools/bl33_audit.py smc`.
no device touched. no reads, no writes, no SMC.

runtime values (round20 live probe, 2026-09-30): `[0x37fbde60]=0x05000000`,
`[0x37fbde58]=0x05040000`, `[0x37fbde68]=0x05080000`, `[0x37fbde48]=0x40000`,
`[0x37fbde50]=1`. the dataflow below is code-exact; the addresses are runtime.

stubs: `0x37e8bba0: smc #0; ret`, `0x37e8bba8: smc #0; ret`,
`0x37e8bbb0: smc #0; ret`. every storage SMC goes through one of these with
only X0 preset. X1/X2/X3 at every storage SMC site = whatever the caller left
(never set up: the payload travels in sharemem, not registers).

## 0x82000023 GET_SHARE_STORAGE_IN_BASE

setup site: `0x37e8bbc0` inside init `0x37e8bbb8`:
`mov x0,#0x23; movk x0,#0x8200,lsl#16; bl 0x37e8bba0`.
caller of init: 7 lazy sites (see below) + no direct external caller.
X1/X2/X3: untouched (garbage/whatever).
return: `mov x21,x0; adrp x0,#0x37fbd000; add x0,#0xe60; str x21,[x0]`.
global write: `[0x37fbde60] = X0`. no other store to this slot in the image.
subsequent loads: 6 request builders load it
(`0x37e8bd60 0x37e8be18 0x37e8bedc 0x37e8bf80 0x37e8c024 0x37e8c0c8`).
no code ever stores into `[[0x37fbde60]]` except those builders.

## 0x82000024 GET_SHARE_STORAGE_OUT_BASE

setup: `0x37e8bbe4` in same init: `mov x0,#0x24; movk; bl`.
return: `mov x20,x0; str x20,[0x37fbde58]`.
global write: `[0x37fbde58] = X0`.
subsequent loads: 5 response readers
(`0x37e8be24 0x37e8bee8 0x37e8bf8c 0x37e8c030 0x37e8c0d4`).
BL33 never stores into `[[0x37fbde58]]`: out-buffer is read-only from BL33 side.

## 0x82000025 GET_SHARE_STORAGE_BLOCK_BASE

setup: `0x37e8bc00` in same init: `mov x0,#0x25; movk; bl`.
return: `mov x19,x0; str x19,[0x37fbde68]`.
global write: `[0x37fbde68] = X0`.
subsequent loads: exactly 1: getbuffer `0x37e8bc84` at `0x37e8bcd8`
(`ldr x0,[0x37fbde68]`, returned to caller). no other user.
note: duplicate stale word at `0x37f5fd68` is struct-copy content, consumed once
at `0x37e8c4ac` via `bl 0x37e35170` (store_key_write dispatcher). not a source.

## 0x82000027 GET_SHARE_STORAGE_BLOCK_SIZE

setup: `0x37e8bc1c` in init + refresh in getbuffer `0x37e8bcbc`:
`mov x0,#0x27; movk; bl 0x37e8bba0`.
return init: `str x0,[0x37fbde48]`. return getbuffer: same store + `str w0,[x19]`
(`*caller_size = X0`, caller out-ptr passed in x0).
global writes: `[0x37fbde48]` at both sites. only 2 sites in image.
subsequent loads: callers of getbuffer compare `*size` (`0x37e8c2b8 cmp w1,w0`).
fail path: getbuffer returns 0 and stores 0 to `*size`.

## 0x82000028 SET_STORAGE_INFO (scalar control, not a buffer)

setup: `0x37e8c138: mov w1,w0; mov x0,#0x28; movk; smc #0; ret`.
caller: exactly 1 bl site `0x37e90614` inside `0x37e904ac` (boot/state machine).
at that site: `ldr w0,[x19,#0xec]` (=1 on the taken path), `cmp w0,#1`,
`mov w2,#2; str w2,[0x37f60878]` (store backend selector = 2), then `bl`.
so X0=0x82000028, X1=w0=1. X2/X3 untouched.
return: X0 status, compared/returned by caller path (`0x37e90618` continues boot
regardless; no global write, no sharemem touch).
verdict: control SMC, proven not a staging consumer.

## init gate (all six consumers)

init tail `0x37e8bc34..0x37e8bc70`: each of x21/x20/x19/x0 compared against
`0xffffffff`; `[0x37fbde50] = 1` iff none failed else `-1` (w0 returned too).
every consumer prologue: `ldr w1,[0x37fbde50]; cbnz -> skip bl init;
ldr; cmp #1; b.ne return -1`. so no storage SMC issues unless init succeeded.
`0x82000026` (message base): zero setup sites in the whole image
(movz/movk census + smc census). DTB has no `storage_message` prop either
beyond block/size. UNUSED.

## consumers 0x60..0x65 (bulk path, sharemem args)

| func | SMC site | X0 | X1/X2/X3 | return | globals touched |
|---|---|---|---|---|---|
| 0x37e8bd10 write | 0x37e8bda8/0x37e8bdb0 via stub | 0x82000062 | none set | stub X0 ignored, returns via epilogue | loads [0x37fbde60] as staging base |
| 0x37e8bdc8 read | 0x37e8be54/0x37e8be5c | 0x82000061 | none | `mov x19,x0; cbnz -> fail`; on 0 parses OUT | loads IN + OUT slots |
| 0x37e8be98 query | 0x37e8bf14/0x37e8bf1c | 0x82000060 | none | `cbnz x0 -> fail` else `ldr w1,[x21]; str w1,[x20]` | loads IN + OUT |
| 0x37e8bf3c status | 0x37e8bfb8/0x37e8bfc0 | 0x82000065 | none | same single-word pattern | loads IN + OUT |
| 0x37e8bfe0 tell | 0x37e8c05c/0x37e8c064 | 0x82000063 | none | same | loads IN + OUT |
| 0x37e8c084 verify | 0x37e8c100/0x37e8c108 | 0x82000064 | none | `mov x19,x0; cbnz -> fail` else 0x20-B copy | loads IN + OUT |

no X1/X2/X3 setup before any of the six `bl 0x37e8bba0`. request travels
entirely through `[[0x37fbde60]]`, response through `[[0x37fbde58]]`.

## non-staging SMCs for contrast

- `0x37e8bcfc`: `mov w2,w1; mov w1,w0; x0=0x82000069; b 0x37e8bbb0`.
  caller `0x37e8c2a0` in `0x37e8c1dc`. scalar notify_ex, no sharemem.
- `0x37e8c14c`: `mov w1,w0; x0=0x8200006a; bl 0x37e8bba8`.
  caller `0x37e8c264` in `0x37e8c1dc`. scalar set_enctype, no sharemem.
- `0x820000ff` wrapper `0x37e19ea8`: `mov x1,x7(buf); mov x2,x6(len);
  mov x3,x5(opt); smc` — register-passed triple + post-SMC flush
  (`add x1,x6,x5; bl 0x37e19310`). separate channel, see 06.
