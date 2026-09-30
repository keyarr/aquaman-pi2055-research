# round20 02: xrefs to 0x05000000 and neighbors

image: `reports/round14-bl33-persist/bl33-37e18000.bin`, base 0x37e18000.
method: word scan + movz/movk scan + adrp/add target resolution over raw
words (capstone used only for disasm quotes; the scan is opcode-exact).
no device touched.

## 1. literal words (exact 32-bit matches)

| value | hits | VA(s) | file off(s) |
|---|---|---|---|
| 0x05000000 | 1 | 0x37fbde60 | 0x1a5e60 |
| 0x05040000 | 1 | 0x37fbde58 | 0x1a5e58 |
| 0x05080000 | 2 | 0x37f5fd68, 0x37fbde68 | 0x147d68, 0x1a5e68 |
| 0x050fe000 | 1 | 0x37f71480 | 0x159480 |
| 0x050ff000 | 1 | 0x37f71488 | 0x159488 |
| 0x050c0000 | 0 | - | - |
| 0x00040000 | 6 | 0x37eb6350, 0x37f4ae94, 0x37f5fd70, 0x37f60998, 0x37f609d8, 0x37fbde48 | - |

every 0x05xxxxxx literal sits in data (.bss-ish), not in code. each is the
*content* of a global slot, never an instruction operand. there is exactly
one 0x05000000 word in the whole 0x1d8000 image and it is the stale content
of the 0x23 global.

## 2. code-built addresses (movz/movk/adrp/add/ldr-literal)

- movz/movk scan over all 483328 instructions: zero sequences build
  0x05000000, 0x05040000, 0x05080000, 0x050fe000 or 0x050ff000 into a
  register. the only movk hits with a 0x5xxx high half are unrelated
  (efuse ids 0x51-0x5a, CBUS/VPU/MMIO constants, sha/crypto immediates).
- adrp/add scan (ADD-imm decode: tgt = page + imm12, or imm12<<12 if sh):
  zero adrp/add pairs compute 0x05000000 anywhere in code. same for the
  other four 0x05 values. BL33 never hardcodes the secmon CMA window.
- ldr-literal pools: no pool entry holds 0x05000000 either (follows from
  the word scan: the single occurrence is at 0x37fbde60, which is only ever
  accessed via adrp/add, never via ldr-literal).

consequence: code yields call graphs + global slots, never the addresses.
any 0x05000000 the firmware uses arrives at runtime via SMC return.

## 3. who references the global slots (adrp/add, exact)

0x37fbde60 (in, 0x23): 7 sites
`0x37e8bbd8 0x37e8bd60 0x37e8be18 0x37e8bedc 0x37e8bf80 0x37e8c024 0x37e8c0c8`
= init store + the five request builders that load it (+ verify).

0x37fbde58 (out, 0x24): 6 sites
`0x37e8bbf4 0x37e8be24 0x37e8bee8 0x37e8bf8c 0x37e8c030 0x37e8c0d4`
= init store + the five response readers.

0x37fbde68 (block, 0x25): 2 sites `0x37e8bc10 0x37e8bcd8`
= init store + getbuffer return-load. no other user.

0x37fbde48 (size, 0x27): 2 sites `0x37e8bc28 0x37e8bcc8`
= init store + getbuffer refresh-store.

0x37fbde50 (valid flag): 1 direct adrp site `0x37e8bc94` plus
offset-reaching loads/stores from the same page register in init and the
six gated functions (add #0xe50 from the 0x37fbd000 page).

secmon caches: 0x37f71480: 1 site `0x37e19d88` (in-cache load/store in
0x37e19d70); 0x37f71488: 2 sites `0x37e19db4 0x37e19f74` (out-cache in
0x37e19d70 and chip-id 0x37e19f4c). separate channel from storage, same
lazy-cache-then-SMC shape.

0x37f5fd68 (second 0x05080000): 1 site `0x37e8c4ac` (inside 0x37e8c450).
struct at 0x37f5fd60: `[ptr 0x37e8ade0][u64 0x05080000][u32 0x40000][byte
table 01 02 ...]`. the user loads [0x37f5fd68] as x0 and [+8] as w1, then
`bl 0x37e35170`. that callee is a bootloader-state-gated dispatcher, not a
storage helper; the 0x05080000 here is a *copy* of the block value inside an
unrelated context struct, not a second source of truth. do not cite it as
an independent confirmation of the block base.

## 4. classification

| addr | literal in code | runtime-returned | global slot | code ref |
|---|---|---|---|---|
| 0x05000000 | NO (0 code sites) | claimed via 0x23 return (stale evidence only) | 0x37fbde60 content (stale) | none |
| 0x05040000 | NO | claimed via 0x24 return (stale) | 0x37fbde58 content (stale) | none |
| 0x05080000 | NO | claimed via 0x25 return (stale) | 0x37fbde68 + 0x37f5fd68 contents (stale) | none |
| 0x050fe000 | NO | claimed via 0x20 return (stale) | 0x37f71480 content (stale) | none |
| 0x050ff000 | NO | claimed via 0x21 return (stale) | 0x37f71488 content (stale) | none |

bottom line: there is no static xref from BL33 code to C1. the only link is
`0x23-return -> [0x37fbde60]`, whose content happened to be 0x05000000 in a
stale snapshot. coincidence is neither confirmed nor refuted by xrefs.
