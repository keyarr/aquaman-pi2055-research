# round20 05: round13 snapshot reconciliation

the "stale snapshot" is the live .bss inside the 0x37800000+8M band:

- band: `reports/round13-reloc-verify/mread_37800000_00800000.bin`,
  base 0x37800000, size 0x800000,
  sha256 `3d2eca1d7c4030250fef733272878c0ca0f3b798b9ae4ba54a110b7e1012b04e`
- the values below are read from that band at (VA - 0x37800000), i.e. from
  the persisted image at (VA - 0x37e18000). they are DRAM bytes captured
  over Optimus mread while stage 16 (TPL/BL33) was up. they are NOT
  constants in the image; they are whatever the SMC init had returned on
  those boots.
- determinism note: round12 and round13 bands are byte-identical over the
  full 8 MiB (see round13 00_session.txt). so the snapshot repeated once.
  still stale for round19: different session, no global re-read was taken
  there, and .bss is rewritten by every init.

## audit table

| value (stale) | slot | file off | how obtained | current evidence | verdict |
|---|---|---|---|---|---|
| 0x050fe000 secmon-in | 0x37f71480 | 0x159480 (u64) | band bytes at 0x37f71480; slot written only by 0x37e19d70 path via 0x82000020 return | none (no live read in r19; DTB only gives the 0x05000000/0x400000 window, not this sub-address) | STALE BUT PLAUSIBLE |
| 0x050ff000 secmon-out | 0x37f71488 | 0x159488 (u64) | same, via 0x82000021 return | none | STALE BUT PLAUSIBLE |
| 0x05000000 storage-in | 0x37fbde60 | 0x1a5e60 (u64) | band bytes; slot written only by init 0x37e8bbb8 via 0x82000023 return | none current; equals C1 base (DTB-exact range base) which is why it is a lead and not a finding | STALE BUT PLAUSIBLE |
| 0x05040000 storage-out | 0x37fbde58 | 0x1a5e58 (u64) | via 0x82000024 return | none | STALE BUT PLAUSIBLE |
| 0x05080000 storage-block | 0x37fbde68 | 0x1a5e68 (u64) | via 0x82000025 return | none (duplicate copy at 0x37f5fd68 is same stale bytes, not independence) | STALE BUT PLAUSIBLE |
| 0x40000 block size | 0x37fbde48 | 0x1a5e48 (u32) | via 0x82000027 return; flag [0x37fbde50]=1 | none current; note DTB secmon window is also 0x400000, so size==window is suggestive but not evidence | STALE BUT PLAUSIBLE |
| flag 1 | 0x37fbde50 | 0x1a5e50 (u32) | init success path | none current | STALE BUT PLAUSIBLE |

nothing is REFUTED (no contradicting read exists) and nothing is
CURRENTLY VERIFIED (no round19+ read of any of these six slots).

## geometry sanity (static, DTB-exact)

- DTB `linux,secmon alloc-ranges <0x5000000 0x400000>` ->
  window 0x05000000..0x05400000. all six stale values fall inside it:
  in 0x05000000, out 0x05040000 (+0x40000), block 0x05080000 (+0x80000,
  size 0x40000 -> ends 0x050c0000), secmon-in/out 0x050fe000/0x050ff000
  (top 8 KiB). layout is non-overlapping and 0x40000-aligned. tidy, which
  is why the snapshot *looks* right - but tidiness is not verification.
- DTB `/secmon reserve_mem_size 0x300000` vs secmon size 0x400000 mismatch
  (round18) is untouched by this: the stale sub-layout fits either way.
- C2 0x05300000 (secos, status=disable) overlaps the same window per DTB
  reg <0x5300000 0x2000000>. the round19 C2 fault (errno 5/19 +
  disconnect x2) says nothing about these addresses.

## what would promote each row to CURRENTLY VERIFIED

one minimal live step, explicitly justified (no fishing): with Optimus
stage 16 up, `0x02 READ_MEM` 8 B each of 0x37f71480, 0x37f71488,
0x37fbde60, 0x37fbde58, 0x37fbde68, 0x37fbde48 (+ flag 0x37fbde50).
seven tiny reads, no writes, no SMC, no 0x05. if [0x37fbde60] still reads
0x05000000, the storage-in == C1 link becomes CURRENTLY VERIFIED and the
rest of the table follows by the same session. until then every row stays
exactly where it is: plausible, reused at our peril, never ground truth.
