# round20 01: SMC storage dataflow in persisted BL33

image: `reports/round14-bl33-persist/bl33-37e18000.bin`
base 0x37e18000, size 0x1d8000, sha256 `664fb34a9c6d92cdcd576659fb5359bd5218841612dbf38c01426c5d3c1b7818`
method: capstone disasm of the bytes on disk. no device touched.

## 1. init 0x37e8bbb8: the only place 0x23/24/25/27 are issued for storage

verbatim (abbreviated, full in tool output):

```text
0x37e8bbb8  stp x29,x30,[sp,#-0x30]!
0x37e8bbc0  mov x0,#0x23 / movk x0,#0x8200,lsl#16   ; 0x82000023
0x37e8bbd0  bl 0x37e8bba0                           ; stub: smc #0; ret
0x37e8bbd4  mov x21,x0                              ; X0 -> x21
0x37e8bbd8  adrp x0,#0x37fbd000 / add x0,x0,#0xe60  ; = 0x37fbde60
0x37e8bbe0  str x21,[x0]                            ; [0x37fbde60] = 0x23 return
0x37e8bbe4  mov x0,#0x24 / movk #0x8200            ; 0x82000024
0x37e8bbec  bl 0x37e8bba0
0x37e8bbf0  mov x20,x0
0x37e8bbf4  adrp/add -> 0x37fbde58 / str x20,[x0]   ; [0x37fbde58] = 0x24 return
0x37e8bc00  mov x0,#0x25 / movk #0x8200            ; 0x82000025
0x37e8bc08  bl 0x37e8bba0
0x37e8bc0c  mov x19,x0
0x37e8bc10  adrp/add -> 0x37fbde68 / str x19,[x0]   ; [0x37fbde68] = 0x25 return
0x37e8bc1c  mov x0,#0x27 / movk #0x8200            ; 0x82000027
0x37e8bc24  bl 0x37e8bba0
0x37e8bc28  adrp x1,#0x37fbd000 / add x1,#0xe48    ; = 0x37fbde48
0x37e8bc30  str x0,[x1]                             ; [0x37fbde48] = 0x27 return
0x37e8bc34  mov x1,#0xffffffff
0x37e8bc38  cmp x21,x1 / b.eq fail
0x37e8bc44  cmp x20,x1 / b.eq fail
0x37e8bc4c  cmp x19,x1 / b.eq fail
0x37e8bc54  cmp x0,x1  / b.ne ok
fail: x2 = 0x37fbde50 (flag), w0 = -1, str w0,[x2]
ok:   x2 = 0x37fbde50, w0 = 1, str w0,[x2]
```

dataflow, proven by instructions:

```text
0x82000023 -> X0 -> x21 -> STR [0x37fbde60]   (in base)
0x82000024 -> X0 -> x20 -> STR [0x37fbde58]   (out base)
0x82000025 -> X0 -> x19 -> STR [0x37fbde68]   (block base)
0x82000027 -> X0 -> STR [0x37fbde48]          (block size)
flag [0x37fbde50] = 1 if none of the four == 0xffffffff, else -1
```

file offsets (VA - 0x37e18000): 0x37fbde60 -> 0x1a5e60, 0x37fbde58 -> 0x1a5e58,
0x37fbde68 -> 0x1a5e68, 0x37fbde48 -> 0x1a5e48, 0x37fbde50 -> 0x1a5e50.

no adrp/add in this function resolves to 0x05000000 itself. the function only
writes SMC *returns* into globals. the addresses, if any, arrive at runtime
from BL31.

## 2. getbuffer 0x37e8bc84: returns the BLOCK base, not in/out

```text
0x37e8bc84  x19 = x0 (caller out-ptr for size)
0x37e8bc94  adrp/add -> 0x37fbde50 flag; ldr w1,[x1]
0x37e8bca4  cbnz w1 -> skip init; else bl 0x37e8bbb8 (lazy init)
0x37e8bcb0  ldr w0,[0x37fbde50]; cmp w0,#1; b.ne fail
0x37e8bcbc  x0 = 0x82000027; bl 0x37e8bba0        ; fresh size query
0x37e8bcc8  adrp/add -> 0x37fbde48; str x0,[x1]    ; refresh [size]
0x37e8bcd4  str w0,[x19]                           ; *caller = size
0x37e8bcd8  adrp/add -> 0x37fbde68; ldr x0,[x0]    ; return [block base]
fail: str wzr,[x19]; return 0
```

callers (bl): 0x37e8c238 and 0x37e8c2a8, both inside 0x37e8c1dc.
meaning: the "getbuffer" helper hands out the block region + size.
it never touches [0x37fbde60] (in) or [0x37fbde58] (out).

## 3. request/response functions: all six share one shape

| func | SMC via stub | request buffer | response buffer |
|---|---|---|---|
| 0x37e8bd10 write (0x62) | 0x37e8bdb0: x0=0x82000062 | x19 = [0x37fbde60] (in) | none read (fire) |
| 0x37e8bdc8 read (0x61) | 0x37e8be5c: x0=0x82000061 | x19 = [0x37fbde60] (in) | x24 = [0x37fbde58] (out) |
| 0x37e8be98 query (0x60) | 0x37e8bf1c: x0=0x82000060 | x22 = [0x37fbde60] (in) | x21 = [0x37fbde58] (out) |
| 0x37e8bf3c status (0x65) | 0x37e8bfc0: x0=0x82000065 | x22 = [0x37fbde60] (in) | x21 = [0x37fbde58] (out) |
| 0x37e8bfe0 tell (0x63) | 0x37e8c064: x0=0x82000063 | x22 = [0x37fbde60] (in) | x21 = [0x37fbde58] (out) |
| 0x37e8c084 verify (0x64) | 0x37e8c108: x0=0x82000064 | x19 = [0x37fbde60] (in) | x22 = [0x37fbde58] (out) |

common prologue (all six): load flag [0x37fbde50]; if 0, bl 0x37e8bbb8;
re-check flag == 1 else return -1 without touching SMC. so every storage SMC
is gated on a successful 0x23/24/25/27 init.

request build (example 0x37e8bd10):

```text
0x37e8bd60  ldr x19,[0x37fbde60]      ; in base
0x37e8bd6c  x0 = name; bl strlen (0x37eaad30)
0x37e8bd74  str w0,[x19]              ; [in+0] = namelen
0x37e8bd78  str w22,[x19,#8]          ; [in+8] = flags/type
0x37e8bd7c  str w20,[x19,#4]          ; [in+4] = datalen
0x37e8bd84  x19 += 0xc
0x37e8bd90  memcpy(x19, name, namelen)        ; bl 0x37eaaeec
0x37e8bda4  memcpy(x19+namelen, data, datalen)
0x37e8bda8  x0 = 0x82000062; bl stub         ; args already in sharemem
```

no X1/X2/X3 setup before the SMC. the request travels entirely through the
in-buffer. same for the other five, with small header variants (single w2
store, post-increment `str w2,[x0],#4`).

response consume (example 0x37e8bdc8):

```text
0x37e8be68  x1 = [0x37fbde58] (out base)
0x37e8be6c  ldr w2,[x1],#4            ; [out+0] = status/len, post-inc
0x37e8be74  str w2,[x22]              ; caller out
0x37e8be7c  memcpy(caller, x1, w2)
```

query/status/tell do `ldr w1,[x21]; str w1,[x20]` (single word response).
verify (0x37e8c084) does a 0x20-byte memcpy from out-buffer to caller.

## 4. the rest of the storage SMC surface

- 0x37e8bcfc: `mov w2,w1; mov w1,w0; x0=0x82000069; b 0x37e8bbb0` (stub).
  caller 0x37e8c2a0 (inside 0x37e8c1dc). id 0x69 is outside the DTB
  securitykey list; purpose unknown, no sharemem traffic in the trampoline.
- 0x37e8c138 (`secure_storage_set_info` caller): `mov w1,w0; x0=0x82000028;
  smc #0; ret`. single bl caller 0x37e90614 (inside 0x37e904ac). at the call
  site w2=2 was just stored to [0x37f60878]; w0 carries whatever the path
  computed (register value, not a buffer pointer). no sharemem staging here.
- 0x37e8c14c (`secure_storage_set_enctype` caller): `mov w1,w0;
  x0=0x8200006a; bl 0x37e8bba8`. callers 0x37e8c264 (inside 0x37e8c1dc) plus
  the 0x37e8c134 fallthrough. scalar arg, no buffer.
- 0x82000028/0x6a never read [0x37fbde60]/[0x37fbde58]. they are control
  SMCs, not staging consumers.

## 5. what this proves about 0x82000023 and C1

proven: 0x82000023 -> X0 -> x21 -> [0x37fbde60]. the global slot is exact
(adrp/add dataflow, 7 code sites reference the slot, see 02-c1-xrefs.md).

NOT proven: [0x37fbde60] == 0x05000000 at any current boot. the value
0x05000000 at file offset 0x1a5e60 is a stale .bss snapshot (rounds 12/13
band, sha 3d2eca1d..., see 05-round13-reconciliation.md). code never
materialises 0x05000000 (see 02). so `0x82000023 -> C1` is UNKNOWN: the edge
to the global is proven, the global-to-C1 equality is stale-only.

naming note: DTB calls 0x23 storage_in_func, 0x24 storage_out_func,
0x25 storage_block_func, 0x27 storage_size_func
(artifacts/aquaman.dtb /securitykey node). the BL33 code behavior matches
those names (in=request staging, out=response staging, block=getbuffer
region). the names are corroborated by use, not just labels.
