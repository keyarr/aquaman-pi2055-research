RAM candidates, read-only plan. No live read was performed this round
(offline only: no USB, no 0x05, no bootm, no SMC, no RAM patch, no eMMC write).
Each candidate gets a 64 KiB probe first, only on a live device in a later round.

| # | address | reason | expected size | first probe | exact-aquaman | confidence |
|---|---|---|---|---|---|---|
| C1 | 0x05000000 | DTB linux,secmon alloc-ranges base (0x5000000, 0x400000); /secmon memory-region target; rsvmem CMA path writes exactly this property | 0x400000 (DTB) / 0x300000 (reserve_mem_size) | 0x05000000+64K: AArch64 vectors, eret, smc-dispatch, AMLSECU/secureboot strings | derived-exact (range from runtime DTB) | MEDIUM as location, LOW as content |
| C2 | 0x05300000 | DTB linux,secos reg base (disabled, no-map); BL32 slot adjacent to secmon; rsvmem BL32 path | 0x2000000 | 0x05300000+64K: TEE/optee strings vs BL31 vectors (distinguishes BL32 from BL31) | derived-exact (range from runtime DTB) | LOW (status=disable, may be empty) |
| C3 | sharemem in/out (runtime) | BL33 efuse path uses SMC 0x82000020/0x82000021 bases (get_sharemem_info); only addresses BL31 itself reports | 0x500 each per caller | bases first, then +64K each: readable ASCII vs secure-block fault | exact only if read live | LOW (addresses unknown until queried) |
| C4 | 0x01000000 | DTB link/load address (fdtaddr, dtb_mem_addr default); not BL31, but the one known-good secure-adjacent pointer for calibrating a read primitive | DTB 0xe3a8 | already have blob (sha b00adab...) | YES (DTB itself) | HIGH as calibration, NIL as BL31 |
| C5 | below 0x00800000 | round-14 instruction: do not go below 0x00800000; listed only to forbid it (BootROM/FIP live area risk) | n/a | NO PROBE | n/a | FORBIDDEN |

Content signatures for a strong candidate (code, not strings alone):
AArch64 density, exception vectors + eret (reference BL31 has 2 eret, zero smc #0:
it receives SMC), PSCI/opteed_std/opteed_fast, AMLSECU!/secureboot strings,
SMC id table containing 0x820000ff, msr/mrs SCR_EL3/SPSR_EL3/ELR_EL3/VBAR_EL3.
A reserved-memory marking alone proves nothing.

Result this round: no runtime copy saved (no strong candidate without a live read).
