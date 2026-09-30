# round 16.02 - ddr_test_copy parser and copy loop

static only, no device. image + .src/u-boot-khadas/common/cmd_ddr_test.c.
tool verbs: ddrcopy, copyloop. handler 0x37e3d1b0, loop 0x37e3aea0,
strtoul32 0x37e3cbb0. full disasm already in
reports/round15-bl33-interface/06_handlers.txt; only the load-bearing
lines are repeated here.

## 1. handler shape (argc dispatch)

```text
0x37e3d210  cmp   w23, #3        ; w23 = argc
0x37e3d214  b.le  default        ; argc<=3 -> defaults, no host args
defaults: src=0x1080000-ish test area, dst=+0x8000000, size=0x2000000
0x37e3d218  ldr   x0, [x19, #8]  ; argv[1]
0x37e3d224  bl    0x37e3cbb0     ; w24 = strtoul32(argv[1],16)
0x37e3d22c  ldr   x0, [x19, #0x10]; argv[2]
0x37e3d238  bl    0x37e3cbb0     ; w25 = strtoul32(argv[2],16)
0x37e3d240  ldr   x0, [x19, #0x18]; argv[3]
0x37e3d24c  bl    0x37e3cbb0     ; w20 = strtoul32(argv[3],16)
0x37e3d254  ldr   x0, [x19, #0x18]; argv[3] ptr again
0x37e3d258  ldrb  w0, [x0]       ; *argv[3]
0x37e3d25c  cbz   w0, force_default
0x37e3d260  ldr   x0, [x29, #0x60]; endp
0x37e3d264  ldrb  w0, [x0]       ; *endp
0x37e3d268  cbnz  w0, force_default
0x37e3d26c  cmp   w20, #0xfff
0x37e3d270  mov   w0, #0x2000000
0x37e3d274  csel  w20, w20, w0, hi ; if (size>0xfff) keep else 0x2000000
0x37e3d278  cmp   w23, #4
0x37e3d27c  b.le  loop=1,print=1
0x37e3d280  ldr   x0, [x19, #0x20]; argv[4]
0x37e3d28c  bl    0x37e3cbb0     ; w21 = loop (+ validity dance, default 1)
0x37e3d2b4  cmp   w23, #5
0x37e3d2c0  ldr   x0, [x19, #0x28]; argv[5]
0x37e3d2cc  bl    0x37e3cbb0     ; w22 = print_flag (default 1)
```

Mapping (source cmd_ddr_test.c:1667 do_ddr_test_copy confirms names):

```text
argv[1] -> w24 -> w26 -> x1 = src
argv[2] -> w25 -> w23 -> x0 = dst
argv[3] -> w20 -> w2  = size (floored to 0x2000000 if <0x1000)
argv[4] -> w21       = loop (default 1)
argv[5] -> w22       = print_flag (default 1)
```

Call site:

```text
0x37e3d304  mov   x0, #0x9988 / movk x0, #0xc110,lsl#16 ; timer reg (not a clamp)
0x37e3d318  mov   w23, w25     ; dst
0x37e3d31c  mov   w26, w24     ; src
0x37e3d33c  mov   x0, x23
0x37e3d340  mov   x1, x26
0x37e3d344  mov   w2, w20
0x37e3d348  bl    0x37e3aea0   ; ddr_test_copy(dst, src, size)
0x37e3d364  subs  x19, x19, #1
0x37e3d368  b.ne  0x37e3d33c   ; repeat loop times
```

## 2. integer types and width

- strtoul32 0x37e3cbb0 returns w0=w21 (32-bit). Core: madd w21,w21,w20,w0,
  i.e. acc = acc*base + digit with 32-bit wrap. 0x-prefix skipped for
  base 16, base-10 leading-0 skip present. No errno, no saturation.
- Handler keeps everything in w regs (w24/w25/w20/w21/w22), then
  zero-extends into x0/x1 for the call. Addresses above 4 GiB are
  unrepresentable (truncation, not a check). Sizes above 0xffffffff wrap
  at parse time.
- simple_strtoul 0x37eac21c (used by mmc, update, bootm) is the 64-bit
  sibling (madd x5,x5,x2,x3). ddr_test_copy deliberately uses the 32-bit
  one; the truncation is visible in mov w24,w0 / mov w25,w0 / mov w20,w0.

## 3. the copy loop 0x37e3aea0 (the 4x factor)

```text
0x37e3aea0  lsr   w2, w2, #2    ; N = size>>2
0x37e3aea4  sub   w2, w2, #1    ; N-1
0x37e3aea8  cmn   w2, #1        ; N-1+1 = N, sets Z iff N==0
0x37e3aeac  b.eq  ret           ; size<4 -> 0 iters
0x37e3aeb0  prfm  pldl1keep, [x1, #0x178]
0x37e3aeb4  ldr   w3, [x1]
0x37e3aeb8  add   x0, x0, #0x10
0x37e3aebc  stur  w3, [x0, #-0x10]
0x37e3aec0  ldr   w3, [x1, #4]
0x37e3aec4  add   x1, x1, #0x10
0x37e3aec8  stur  w3, [x0, #-0xc]
0x37e3aecc  ldur  w3, [x1, #-8]
0x37e3aed0  stur  w3, [x0, #-8]
0x37e3aed4  ldur  w3, [x1, #-4]
0x37e3aed8  stur  w3, [x0, #-4]
0x37e3aedc  b     0x37e3aea4    ; w2--, exit when w2==0xffffffff
```

Iterations = N, bytes/iter = 16, total = N*16 = (size>>2)*16.
For size>=4: effective = (size & ~3)*4. That is 4x the requested size.
Source cmd_ddr_test.c:1623 has the identical bug (m_len=size/4;
while(m_len--) { 4x *p_dest++=*p_src++ }), so the image matches source
line for line; this is not a disassembly mistake.

Examples (loop=1): size 0x1000 -> 0x4000 bytes; size 0x2000000 -> 0x8000000
(128 MiB). Minimum reachable through the parser is 0x1000 (anything
smaller is forced to 0x2000000, i.e. 128 MiB effective).

Alignment: none required. ldr/str w (4-byte) with post-index #0x10;
unaligned src/dst do not trap on ARMv8, they just run slower. No
alignment mask or check anywhere on the path.

## 4. what runs AFTER the copy (why it is not a clean copy)

The handler does not return after the bl. In order:

1. copy loop (above) x loop times, timing prints.
2. fill loop at 0x37e3d3bc..0x37e3d434: lsr w22,w20,#2 (N), x0=N*16,
   inner writes 4x 0x12345678 per iter (movw 0x5678/movk 0x1234), N iters,
   outer repeats w25=loop times at dst+k*N*16. Net: the just-copied
   region is overwritten with constant 0x12345678 over exactly the same
   footprint (loop*N*16 bytes).
3. read loop at 0x37e3d49c..0x37e3d4b4 strides src (w19=N, step 4 B,
   keeps last word in w1).
4. tail stores at 0x37e3d4b8..0x37e3d4dc:
   x27 = N*16*loop (total fill length), x24 = dst+x27,
   str w1,[x23,x27] (one src-derived word at dst+len),
   str w0,[x24,#4], str w0,[x24,#8], str w0,[x24,#0xc]
   (three more src words at dst+len+4/8/12).

So the observable end state is: loop*N*16 bytes of 0x12345678 at dst,
plus 16 bytes of src-derived words at dst+len. The transient copy is
destroyed before return. Pseudocode sustained by the assembly above:

```text
N = clamped_size >> 2; L = N*16*loop
memcpy_4x(dst, src, clamped_size)  // transient, loop times
memset_pattern(dst, 0x12345678, L) // destroys it
dst[L+0..L+15] = last_words_read_from(src) // 4 words survive
```

## 5. checks present / absent

Present: argc>3 gate for host args; *argv[3]/*endp validity -> default;
size floor (<0x1000 -> 0x2000000); loop/print defaults.
Absent: no AND/LSR/mask on src/dst; no range compare against RAM top,
image, DTB, or buffers; no base addition; no signed conversion; no
overflow check (madd/mul wrap); no maximum length; no src+len / dst+len
wrap check; no alignment check. Termination is w2==0xffffffff (N==0
only when size<4, unreachable via parser except by 32-bit wrap to <4,
which is then floored anyway unless it wraps to >=0x1000).
