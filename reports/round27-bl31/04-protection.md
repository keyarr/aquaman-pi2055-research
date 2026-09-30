# 04 — protection: why 0x05000000 reads and 0x05100000 faults

## step 1: rule out the reader's own MMU (EXACT evidence)

the page table that BL33 executes against is at `0x37ff0000` (round15 §G) and
is inside the persisted round-13 dump (`0x37800000..0x38000000`, dump offset
`0x7f0000`, 64 KiB). decode (`tools/round27_layout.py pt_census/pt_covers`):

```text
8192/8192 descriptors valid, desc[1:0]=1 (level-2 section), single table
covering 4 GiB, SECTION_SHIFT=29 (arch/arm/include/asm/armv8/mmu.h,
cache_v8.c mmu_setup: PGTABLE_SIZE 0x10000, 512 MiB per entry):
  idx 0  VA 0x00000000-0x1fffffff  attr 0x411 (MT_DEVICE_NGNRNE)
  idx 1  VA 0x20000000-0x3fffffff  attr 0x401 (MT_NORMAL, cached)
  idx 2..7                        attr 0x401 (normal)
```

therefore:

```text
0x05000000..0x053fffff  mapped, cached, normal — including BOTH the
                        readable MiB and the faulting 0x05100000..0x05300000
unmapped-hole hypothesis: REFUTED. a translation fault at 0x05100000 is
                        impossible in this table.
page-boundary hypothesis: REFUTED. with 512 MiB sections the only mapping
                        boundaries are at 0x00000000/0x20000000/0x40000000;
                        0x05100000 cannot be one.
```

this also closes brief s7's optional probes as unnecessary: a page-vs-security
distinction is fully determined offline.

## step 2: rule out BL33-side runtime protection

BL33 contains no SCR_EL3/VBAR_EL3/TTBR rewrites, no TZ controller access, no
self-modifying of the page table after mmu_setup (round14 censuses; the table
decoded above is a static single-level identity map). the `clear_range` BL33
writes into the DTB (05-boundary.md) is a *kernel-side* pte-clear instruction,
executed only by Linux later — it cannot affect BL33's own reads, and the
faults were observed in TPL before any kernel existed.

## step 3: what the evidence supports

```text
class        : secure-memory protection (platform memory firewall / TZ
               address-space controller) configured by the pre-BL33 chain,
               covering the BL31 image window [0x05100000, 0x05300000)
               (+ the bl32 slot from 0x05300000)
evidence for : window == BL2's declared image base (02); marking must precede
               BL33 because BL33 boots with the boundary already effective;
               the fault behavior is an external abort (data abort taken to
               EL3, gadget dies) — round26 Errno 5 then Errno 19 + bus drop;
               BL33 is Normal-world (EL1/EL2) and the readable/protected
               split follows Secure/NS exactly
evidence out : concrete register UNKNOWN. no TZASC/TZPC node or driver
               exists anywhere in the amlogic u-boot/linux trees here; the
               gxl bl31.bin AO window touches watchdog/JTAG/GPIO/clock only;
               the aquaman secure side (which would hold the programming)
               is the unreadable window itself.
```

round26's own stop condition said the same: "TrustZone protection vs
TPL-MMU-unmapped vs device hole are indistinguishable with 0x02/mread alone".
round27 closes two of the three from persisted evidence: it is NOT the MMU
(step 1) and NOT a device hole (the image actually lives there — 02); it is
the security attribute.

## why Optimus can read 0x05000000 but not 0x05100000 (brief s6)

the gadget's `0x02`/`mread` are NS memcpy loops in BL33. the first MiB is NS
share memory by design (03); the image window is Secure. same instruction,
same MMU mapping, different attribute -> abort. there is nothing to find in
the gadget: the mechanism is not in the gadget.

## note on the G12B parallel (GENERIC REFERENCE)

`mesong12b.dtsi` secmon node carries `clear_range = <0x05100000 0x200000>`
with `cma_mmu_op(page, cnt, 0)` (pte_clear over the range, `mm/cma.c`) — the
family re-uses the same window/length pair (0x05100000 + 2 MiB) for
"kernel must drop its ptes here". on aquaman the property is absent from the
runtime DTB (the rsvmem clear_range write is skipped — see 05), but the
family DTS corroborates that this exact range is treated as untouchable by
the kernel as well.
