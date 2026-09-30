# 03 — memory layout: reservation, share area, image window

## composed map (round26 live + round27 structure)

```text
0x05000000 ┐
0x05040000 │ NS share area (first MiB of the bl31 reservation, BY DESIGN)
0x05080000 │   storage IN  (SMC 0x23)   @0x05000000
0x050fe000 │   storage OUT (SMC 0x24)   @0x05040000
0x050ff000 │   storage BLOCK(0x25) 0x05080000+0x40000
0x05100000 │   secmon IN  (SMC 0x20)    @0x050fe000
     │     │   secmon OUT (SMC 0x21)    @0x050ff000
     ▼     │
0x05100000 ┤ ================= FAULT BOUNDARY =================
0x05300000 │ BL31 IMAGE WINDOW (Secure) — 2 MiB, unreadable from NS
0x05300000 ┤ BL32 RESERVATION — 32 MiB, no-map, status=disable (dead on this build)
0x05400000 │   (DTB pool end — no HW meaning; 0x05400000+ round19 fault covered
0x07300000 │    by the secos slot from 0x05300000)
```

## the three-way question (brief s4): how do the buffers relate to the reservation?

```text
option 1 (buffers inside the bl31 reservation by accident)  : NO
option 2 (separate share memory that only coincides)        : NO
option 3 (container whose first MiB is the NS share area)   : YES
```

evidence for option 3:

```text
- the share bases are not static in BL33: they are *returned by BL31* at
  runtime via SMC 0x82000020/21 (get_sharemem_info) and 0x82000023/24/25
  (storage init), consumed by the efuse path (bl31_apis.c) and the
  secure-storage module (round14 0x37e8bbb8 init). every returned base lands
  inside [0x05000000, 0x05100000).
- the family layout declares the split exactly: rsvmem = 0x05000000+0x300000
  but secure window = 0x05100000+0x200000 (02-load-origin.md (b)).
- /secmon reserve_mem_size (0x300000) == AO bl31 size: the kernel is told the
  total reservation; the family secmon driver then ioremaps the share bases
  returned by SMC (drivers/amlogic/secmon/secmon.c, GENERIC REFERENCE).
- round26: the readable MiB is volatile storage working-set; the bytes from
  0x05100000 are the only remaining bl31 candidates and are protected.
```

## why the DTB pool looks like 4 MiB

`do_rsvmem_check` rounds the secmon CMA size to 4 MiB multiples:
`(bl31_size + 0x400000 - 1)/0x400000*0x400000` (source line 108; aquaman
disasm 0x37e633c8-0x37e633ec `add +0x3ff,000; and #0xfc00000`). so
`linux,secmon size = 0x400000` while the HW reservation is 0x300000. the
extra MiB (0x05300000..0x05400000) overlaps the secos `reg` — DTB-declared
only; on HW it is the first MiB of the bl32 no-map slot. already flagged in
round26; now fully explained by the two-in-one CMA branch (secos start ==
secmon end -> single enlarged pool instead of separate reservations).

## DTB inventory (final, for the layout)

```text
/reserved-memory/linux,secmon : shared-dma-pool, reusable, size 0x400000,
                                align 0x400000, alloc-ranges 0x05000000+0x400000
/secmon                       : amlogic,secmon, memory-region phandle 0xf,
                                in/out_base_func 0x82000020/21,
                                reserve_mem_size 0x300000
                                (clear_range: absent on aquaman — see 05)
/reserved-memory/linux,secos  : aml_secos_memory, reg 0x05300000+0x2000000,
                                no-map, status=disable
```
