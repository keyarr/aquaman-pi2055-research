# 05 — the 0x05100000 boundary

## every place 0x05100000 appears in reachable artifacts

```text
EXACT BL33 dump (0x37e18000..0x37ff0000) : literal 0x05100000 words = 0.
        but DERIVED twice (below).
family gxl/gxb bl31.bin                  : literal = 0.
family bl2.bin                           : +0x94b8 as the bl31 load address
        inside BL2's own FIP table (02-load-origin.md (a)). plaintext.
family bl31.img x2                       : +0x08 load and +0x20 secure-start
        fields (02-load-origin.md (b)). plaintext.
runtime DTB                              : absent as value (no node uses
        0x05100000 on aquaman).
family mesong12b.dtsi                    : secmon clear_range <0x05100000
        0x200000> (GENERIC REFERENCE).
live behavior (round26)                  : last readable byte 0x050fffff;
        first fault 0x05100000, deterministic across sessions/primitives.
```

## derivation #1 — BL33 encodes clear_range = bl31_start + 0x100000 (EXACT)

`do_rsvmem_check` disassembly (0x37e63310..0x37e63348), after successfully
reading `/secmon clear_range`:

```text
37e63330  add w2, w19, #0x100, lsl #12      ; w19 = bl31_start (CFG5)
                                            ; -> w2 = 0x05000000+0x100000
                                            ;    = 0x05100000
37e63334  sub w3, w20, #0x500, lsl #12      ; w20 = bl31_size (CFG3 hi<<10)
                                            ; -> w3 = bl31_size - 0x500000
37e63338  bl  sprintf("fdt set /secmon clear_range <0x%x 0x%x>;", ...)
```

on aquaman: `bl31_size (0x300000) - 0x500000` = negative -> w3 wraps; the
`fdt get value secmon_clear_range /secmon clear_range;` lookup then returns
nonzero (property absent, matching the runtime DTB) so the whole block is
skipped before the fdt-set runs (cbnz -> 0x37e63134). the arithmetic still
proves where BL33's authors *expected* the secure window to start:
`bl31_start + 1 MiB` — independent corroboration of the 1 MiB NS share split.

## derivation #2 — BL2/BL31 headers pin the same address (FAMILY)

see 02-load-origin.md: bl31 load = 0x05100000 (BL2 table), secure window
start = 0x05100000 size 0x200000 (bl31.img header). the boundary between
readable and unreadable is not "somewhere in the reservation" — it is the
image base, declared by the producer chain.

## verdict

```text
0x05100000 = HARD BOUNDARY (start of the Secure image window)
coincidence option  = REFUTED (three independent derivations + live behavior
                      agree; a mapping boundary is impossible per 04)
0x05400000          = DTB container end only, no HW meaning
0x05000000          = reservation start (NS share area begins)
0x05300000          = bl31 window end == bl32 slot start (second boundary,
                      also faulting, consistent)
```
