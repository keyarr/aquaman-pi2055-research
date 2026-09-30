# round 16.03 - control analysis (dst / size / source)

static only. answers the brief's sections 3-6 with per-instruction
evidence. ratings use the brief's scale.

## 1. destination control (brief section 3)

Question: does argv[2] reach the store address without relevant change?

Path in image:

```text
argv[2] (x0=[x19,#0x10])
 -> bl 0x37e3cbb0 -> w0 (32-bit wrap, 0x-prefix aware)
 -> mov w25, w0
 -> mov w23, w25
 -> mov x0, x23            ; zero-extend to 64
 -> bl 0x37e3aea0, store via stur w3,[x0,-...] / str w6,[x3]
```

Searched the whole handler and the loop for each operation class:

```text
AND on dst:       none (only and is timer-flag masking elsewhere, not on w25/x23/x0)
LSR/LSL on dst:   none (the only lsr is lsr w2,w2,#2 on SIZE at 0x37e3aea0)
mask on dst:      none
alignment on dst: none
range compare:    none (no cmp/ccmp/csel/tbz against RAM top 0x38000000,
                  image 0x37e18000, DTB, or buffers before the stores)
base addition:    none (dst is used as-is; the only adds are x0+=0x10 cursor
                  and x4+=x0 stride in the fill outer loop)
truncation:       YES, 64->32 at parse (mov w25,w0), then 32->64 zero-extend.
                  On a <4 GiB machine this is a width limit, not a clamp:
                  any RAM address the board has is representable.
signed conversion: none (all w, unsigned; cmn/cmp use unsigned hs/ls where checked)
```

The fill loop and the tail use the same x23/x24 (derived from argv[2]
with no further transform): mov x4,x23; add x24,x23,x27; str [x23,x27].

Rating:

```text
HIGH: argv[2] -> effective store address with no clamp.
```

Scope note: HIGH here means "address reach is unclamped", not "arbitrary
write is proven". Section 3 of this file keeps the two separate on
purpose; the composition verdict is in 05 and the summary.

OEM budget check (tools/bl33_round16.py oem_fits): full 8-hex-digit
addresses do not always fit 31 chars with the command name
(e.g. "ddr_test_copy 7700000 37e18000 1000" is 35 chars), but short hex
without 0x does ("ddr_test_copy 7700000 37e18000 1000" minus prefixes,
or smaller sizes). The parser accepts no-0x hex (base forced 16), so
the budget constrains spelling, not reachability. Not counted as a clamp.

## 2. size control (brief section 4)

Question: does argv[3] become the loop length directly?

Path:

```text
argv[3] -> bl 0x37e3cbb0 -> w20 (32-bit wrap)
 -> validity: *argv[3]==0 or *endp!=0 -> keep parsed? (source says -> default;
    image checks both bytes before the clamp; exact invalid-input value is
    parse-dependent, default path forces 0x2000000)
 -> cmp w20,#0xfff / csel w20,w20,0x2000000,hi  (floor only)
 -> mov w2,w20 at call; loop uses N=w2>>2, N iters x 16 B x loop
```

Present: minimum floor (0..0xfff -> 0x2000000). Defaults for argc<=3.
Absent, each checked:

```text
max length:       none (0xffffffff parses, wraps only at 32 bits)
minimum length:   0x1000 effective floor (see above); len=0 unreachable
                  (0 -> 0x2000000 -> 128 MiB effective)
rounding:         size>>2 truncation (size&3 dropped, then x4)
overflow check:   none (madd/mul wrap silently)
wraparound check: none
block count:      n/a (byte size, not blocks; contrast mmc below)
src+len check:    none
dst+len check:    none
```

Reachable lengths (loop=1): min 0x4000 bytes effective (req 0x1000),
default 0x8000000 bytes effective (req 0x2000000), max ~0x3ffffffc*4
wrapping at 32 bits. Any len crosses boundaries without a check:
no compare of dst+len or src+len against anything. len very large is
statically possible (no max); it will fault/hang on unmapped-MMIO
touch, but nothing in BL33 stops the attempt.

## 3. source control (brief section 5)

Question: can argv[1] point at a host-controlled buffer?

```text
argv[1] -> bl 0x37e3cbb0 -> w24 -> w26 -> x1 (same no-clamp shape as dst)
fastboot buffer [0x10200000,0x18200000): representable in 32 bits, YES
burning buffer  [0x07700000,0x0b700000): representable in 32 bits, YES
```

Full path:

```text
fastboot download -> [0x10200000 + download_bytes] (01)
  -> oem ddr_test_copy <src=0x10200000..> <dst> <len> (02)
  -> x1 = src, copy+fill+tail run
burning update -> [0x07700000 + slot offset] (01)
  -> same ddr_test_copy source step
```

Composition of ADDRESSES is proven statically (widths match, no clamp
in between). Composition of DATA is not: the copy is overwritten by the
fill (02 section 4), leaving only 4 src-derived words at dst+len. So
"source reaches the read side: YES; host bytes survive to dst: NO
(except 16 bytes at a fixed offset)".

## 4. matrix (brief section 6)

"Arbitrary RAM write" here means strictly: host data + controllable
source + controllable destination + sufficient length, all proven, with
the data surviving to the destination.

```text
property                  result     evidence
host controls data        YES        rx_handler memcpy (fastboot) / bulk slots (burning), 01
host controls source      YES        argv[1]->x1 no clamp; both buffers in 32-bit range, 02+01
host controls destination YES        argv[2]->x0 no clamp, HIGH above
host controls length      PARTIAL    argv[3]->w2 with 0x1000 floor, no max; effective len is 4x req
destination range clamp   NO         no compare/mask/base-add on dst path
length clamp (max)        NO         floor only; no max, no wrap check
length clamp (min)        YES        <0x1000 -> 0x2000000 (forces >=16 KiB effective)
data survives to dst      NO         fill overwrites copy; only 16 B tail at dst+len, 02 sect 4
arbitrary RAM write       NO         fails the survival leg; see 05 for the exact shape
```

The last row is a deliberate downgrade from round 15's HIGH: round 15
proved "host arg reaches a store" (true, kept as HIGH above for the
address leg). Round 16 proves the handler then destroys the payload.
A primitive that writes 128 MiB of 0x12345678 + 16 controlled bytes to
an arbitrary address is a destructive constant-fill with a word-tail,
not an arbitrary write. Calling it "arbitrary RAM write" would require
all four legs plus survival; survival is refuted by the fill loop.
