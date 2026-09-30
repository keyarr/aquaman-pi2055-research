# round27: BL31 layout, load origin, protection (OFFLINE round, no device)

date: 2026-09-30. **zero device I/O this round**: every number is derived from
bytes already in the repo (round-13/14 BL33 dumps, family FIP files in
`.src/u-boot-khadas/fip/`, reference sources in `.src/`, runtime DTB, and the
round-26 live results). tools: `tools/round27_layout.py`; tests `TestRound27Layout`
in `tools/run_tests.py` (5 tests, pass; full suite passes except the
pre-existing vendor-modinfo sandbox hang, unrelated).

round26 state (input, not re-litigated): AO-decoded bl31 range
`[0x05000000, 0x05300000)`, bl32 `[0x05300000, 0x07300000)`, live readability
`0x05000000..0x050fffff` READABLE (storage/share buffers, volatile),
`0x05100000..` deterministic FAULT. bytes of BL31 still NOT recovered.

## 0. answer block

```text
0x05000000  = bl31 reserved-memory START   (AO CFG5, written by BL2 at load time)
0x05300000  = bl32 reserved START          (AO CFG4)
0x00300000  = bl31 reserved SIZE           (AO CFG3 hi16 x 2^10)
0x02000000  = bl32 reserved SIZE           (AO CFG3 lo16 0x8000 x 2^10)
0x05100000  = BL31 IMAGE LOAD ADDRESS      (BL2 FIP table + bl31.img header)
              = BL33 clear_range derivation (bl31_start + 0x100000)
              = family bl31.img "secure window" start (+0x200000 size)
0x0c008000  = CFG3 = packed KiB counters: hi16 0x0c00 -> 0x300000 (bl31),
              lo16 0x8000 -> 0x2000000 (bl32). not an address, not a flag.
protection  = secure-memory class (image is marked Secure before BL33 runs);
              MMU-unmapped REFUTED (page table decode, s5); register UNKNOWN.
BL31 image location  = 0x05100000..0x05300000 (2 MiB secure window)
BL31 bytes readable  = NO
reason               = window is Secure-only; TPL/BL33 runs in NS and every NS
                       read aborts (external abort class -> USB drop)
family gxl bl31.bin  = PARTIAL IMAGE, round 31 §4.2. valid text to 0x2c398,
                       but it references data at 0xc5000 / 0xc5ec0 and a
                       128-byte FID class map at 0xcb040, all past the end of
                       the file. the SMC dispatch table and the 0x82000043
                       handler are therefore NOT in any artifact. do not cite
                       this binary as a behavioural reference for BL31.
```

## 1. origin of the AO values: register -> decoder -> semantics -> DTB

Registers (GXL `secure_apb.h:1602-1625`, FAMILY REFERENCE, byte-verified):

```text
AO_SEC_GP_CFG3 = 0xC8100000 + (0x93<<2) = 0xC810024C   sizes (hi=bl31, lo=bl32)
AO_SEC_GP_CFG4 = 0xC8100000 + (0x94<<2) = 0xC8100250   bl32 start
AO_SEC_GP_CFG5 = 0xC8100000 + (0x95<<2) = 0xC8100254   bl31 start
(SEC_ alias 0xda100xxx = the same registers from the secure side)
```

Decoder, disassembled from the EXACT AQUAMAN BL33 dump
(`reports/round14-bl33-persist/bl33-37e18000.bin`, both listed by round 26):

```text
dump  0x37e62eec (do_rsvmem_dump):
  0x37e62f04  mov  x0,#0x24c ; movk x0,#0xc810,lsl#16 ; ldr w19,[x0]   CFG3
  0x37e62f10  mov  x0,#0x254 ; movk x0,#0xc810,lsl#16 ; ldr w1,[x0]    CFG5 = bl31 start
  0x37e62f1c  mov  x0,#0x250 ; movk x0,#0xc810,lsl#16 ; ldr w20,[x0]   CFG4 = bl32 start
  0x37e62f34  lsr  w1,w19,#0x10 ; lsl w1,w1,#0xa     -> bl31 size = hi16<<10
  0x37e62f5c  ubfiz w1,w19,#0xa,#0x10                 -> bl32 size = lo16<<10
check 0x37e62f78 (do_rsvmem_check): same three reads, then
  w20=bl31_size w19=bl31_start w22=bl32_start w24=CFG3
```

Source match: `.src/u-boot-khadas/common/cmd_rsvmem.c:53-57`
(`((data & 0xffff0000)>>16)<<10`, `(data & 0xffff)<<10`, CFG5, CFG4) —
FAMILY STRUCTURAL REFERENCE whose binary the aquaman image carries.

Semantics -> DTB (EXACT AQUAMAN chain, disasm + runtime DTB agree):

```text
CFG5 0x05000000 -> "fdt set /reserved-memory/linux,secmon reg/alloc-ranges <0x05000000 ...>"
CFG3 hi 0x300000-> "fdt set /secmon reserve_mem_size <0x300000>"
CFG3 hi rounded -> "fdt set .../linux,secmon size <0x400000>" (4 MiB round-up)
CFG4 0x05300000 -> /reserved-memory/linux,secos reg (only if status gate opens;
                   on aquaman CFG5+CFG3==CFG4 exactly, and compatible is CMA,
                   so the secos branch takes the "enlarge secmon" path instead)
live result = artifacts/aquaman.dtb: alloc-ranges 0x05000000+0x400000,
reserve_mem_size 0x300000, secos reg 0x05300000+0x2000000 status=disable
```

## 2. who writes CFG3/4/5 and who loads BL31

Scans executed (all negative unless stated):

```text
BL33 (EXACT):     every ldr/str/adrp+add at disp 0x24c/0x250/0x254 ->
                  readers only (the 4 sites in s1). ZERO writers.
gxl bl31.bin:     movz/movk AO census (round 31, tools/bl31_ao_census.py,
                  names resolved from secure_apb.h): 0xda10025c x6 =
                  SEC_AO_SEC_GP_CFG7, 0xda10001c x5 = AO_RTI_STATUS_REG3,
                  0xda10023c x1 = AO_SEC_SD_CFG15 (read only),
                  0xda100248 x1, 0xda100140 x1, 0xc8100228 x2,
                  0xc81004c0 x3. ZERO at 0x24c/0x250/0x254.
                  *** the 6 GP_CFG7 refs are all read-modify-write: two clear
                  [7:0] (and #0xffff00ff), two are bit-indexed pin helpers
                  (1 << (idx+8), idx = (x&0xff)+((x&0xff00)>>6), a pad-index
                  decoder at 0x24a50). NONE sets bit 31. round 31 §4.2. ***
                  CORRECTION: this census line previously read "17 constants,
                  0xda10025c x5, all watchdog/JTAG/GPIO/clock", which is wrong
                  twice — the count is 6, and AO_SEC_GP_CFG7 is not a
                  watchdog/JTAG/GPIO/clock register. that mislabel is what let
                  the clear path stay invisible. the 0x18ddc function also holds
                  a literal "bl31 clear usb flag" printf.
gxb bl31.bin:     no AO movz/movk pair at all.
u-boot source:    no writel(P_AO_SEC_GP_CFG[3-5]) anywhere.
linux source:     no AO_SEC_GP_CFG writer (kernel only consumes DTB).
```

Loader found — BL2 carries the addresses twice (FAMILY STRUCTURAL REFERENCE,
gxl AND gxb identical; the aquaman equivalents are encrypted inside
`bootloader.img`, whose only ToC fragment is ciphertext, so no EXACT header is
available — classification in the final table reflects this):

```text
(a) bl2.bin tail, plaintext FIP image table (stride 0x28:
    u64 load_addr; char name[8]; u32 0; u32 next_uuid_w0; u64 0; u64 0;
    uuid word0 links match gxlimg uuid_list: bl30->bl301->bl31->bl32->bl33):
      bl30  -> 0x01100000    bl301 -> 0x01200000
      bl31  -> 0x05100000    bl32  -> 0x05300000
      bl33  -> 0x01000000
(b) bl31.img wrapper header @0x00 (magic 0x12348765, gxlimg BL31_MAGIC;
    fip.c copies this 0x50-byte header into the FIP ToC area @0x430+n*0x50
    and states: "BL31 binary store information about load address and entry
    point in the FIP data"):
      +0x00 magic    0x12348765          +0x08 load    0x05100000
      +0x10 rsv start 0x05000000          +0x18 rsv size 0x00300000
      +0x20 secure start 0x05100000       +0x28 secure size 0x00200000
      (+0x04 = 0x4e20, constant in both SoCs, meaning not established)
```

Derivation, end to end:

```text
BL2 (encrypt-time constants, from the vendor FIP packaging)
  --load--> BL31 image lands at 0x05100000
  --rsvmem-> CFG5=0x05000000, CFG3=(0x0c00<<16)|0x8000, CFG4=0x05300000
BL33 boots, reads the AO regs (s1), patches the runtime DTB (s1)
Linux reads the DTB (secmon driver consumes reserve_mem_size + sharemem funcs)
```

The 1 MiB split inside the reservation is therefore **by design, twice**:
BL2 declares rsvmem `0x05000000+0x300000` but the secure *image* window is
`0x05100000+0x200000`; the first MiB is the NS-reachable share area.

## 3. 0x0c008000 exactly

CFG3 packs two independent 16-bit values in KiB:

```text
0x0c008000 = (0x0c00 << 16) | 0x8000
  0x0c00 << 10 = 0x00300000  bl31 reserved size (3 MiB)
  0x8000 << 10 = 0x02000000  bl32 reserved size (32 MiB)
```

Not a flag, not an address: two size counters. The decoder reads both halves
with distinct masks/shifts (`lsr #16; lsl #10` and `ubfiz #0xa,#0x10`), and
`do_rsvmem_check` uses them independently (sizes >0 gate each fdt-set branch).
No other use of CFG3 exists in BL33.

## 4. reservation vs image: what occupies 0x05000000..0x05100000

Resolved from the round-26 subregion map + the layout above:

```text
0x05000000  storage IN  (SMC 0x23)   \  NS-reachable share windows,
0x05040000  storage OUT (SMC 0x24)    > placed by BL31 inside the first MiB
0x05080000  storage BLOCK (0x25)     /   of its own reservation
0x050fe000/ff0000  secmon IN/OUT (0x20/21) share-mem ABI
0x05100000  BL31 image base (Secure) —— protected
```

Answer to the three-way question: **option 3** — the reservation is a
container whose first 1 MiB is, by design, the NS share area; the remaining
2 MiB are the monitor image itself. Evidence: sharemem bases are *requested
from* BL31 at runtime (SMC 0x82000020/21/23/24/25, rounds 14/26) and every
returned base lands inside `[0x05000000, 0x05100000)`; the AO/BL2 layout
declares exactly that split (s2b); the readable MiB is volatile storage
content (round26 §6) while everything from the image base onward faults.
`/secmon reserve_mem_size 0x300000 == AO bl31 size` is the same fact seen
from Linux: the kernel is told the monitor's total reservation, and its
driver (`drivers/amlogic/secmon/secmon.c`, GENERIC REFERENCE for the family)
hands the CMA slice back to the secure world's use.

## 5. the 0x05100000 boundary: hard, not coincidence

```text
constant search         : 0x05100000 as a literal appears in NONE of:
                          BL33 dump, gxl/gxb bl31.bin, bl2.bin (except the
                          FIP table itself), DTB, or the reference trees.
derived in BL33 (EXACT) : do_rsvmem_check encodes
                          "fdt set /secmon clear_range <0x%x 0x%x>" with
                          w2 = bl31_start + 0x100000   (0x37e63330:
                          add w2,w19,#0x100,lsl#12  -> 0x05100000)
                          w3 = bl31_size - 0x500000   (negative here -> wrap;
                          on aquaman the pair encodes "no kernel clear
                          window", test-pinned in TestRound27Layout)
declared by BL2 (FAMILY): bl31 load address in the FIP table = 0x05100000
declared by BL31 (FAMILY): bl31.img secure-window start = 0x05100000
family DTB parallel     : mesong12b.dtsi secmon clear_range = <0x05100000
                          0x200000> — same boundary, 2 MiB long, i.e. the
                          same "image window" (GENERIC REFERENCE)
live fault map (round26): 0x050fffc0 OK / 0x05100000+ FAULT, sharp at exactly
                          this address
```

Verdict: **hard boundary** — it is the start of the secure image window,
derived from `bl31_start+0x100000` by BL33 policy and pinned by the BL2/BL31
headers of the family. The alternative ("page boundary coincidence") is
refuted by the page-table decode below: BL33 maps the whole range, so a
*mapping* boundary cannot exist there.

## 6. protection mechanism

MMU-unmapped REFUTED (EXACT evidence, from the persisted round-13 dump —
BL33's page table at `0x37ff0000`, 64 KiB at dump offset `0x7f0000`):

```text
8192/8192 level-2 descriptors valid (desc[1:0]=1), single 4 GiB identity
map, SECTION_SHIFT=29 (512 MiB per entry, cache_v8.c):
  idx 0 (0x00000000-0x1fffffff) attr 0x104 (device)
  idx 1 (0x20000000-0x3fffffff) attr 0x100 (normal/cached)  <- includes
      0x05000000..0x053fffff AND the faulting 0x05100000..0x05300000
  idx 2..7 fill 0x40000000..0xffffffff
=> 0x05100000 is mapped, cached, normal memory in the reader's own MMU.
   a read there CANNOT fault on translation.
```

(The 512 MiB sections also mean BL33 could not have a sub-2 MiB unmapped
hole even if it wanted one, without switching to finer tables — it does not.)

Mechanism class: **secure-memory protection set up before BL33 runs** (BL2
marks the image window Secure in the platform's memory firewall / TZ
address-space controller; NS reads then abort at the interconnect). Evidence
for the class: the image is loaded and marked secure *before* BL33 (s2), the
boundary is the image base (s5), the abort is deterministic and kills the USB
gadget (external abort behavior, round26), and BL33 itself contains no
SCR_EL3/VBAR/TZ-controller traffic (rounds 14/18 censuses). The concrete
register on this SoC is **not identifiable from any available artifact**: no
TZASC/TZPC driver exists in the u-boot tree for amlogic, and the gxl BL31
reference never touches one (its AO window is watchdog/JTAG/GPIO only). So:

```text
protection register R + bit/range  = UNKNOWN (would need a secure-side dump,
                                     which is the same unreadable window)
mechanism class                    = secure-memory firewall, pre-BL33
MMU/unmapped/page-boundary         = REFUTED
```

## 7. entrypoint and handoff

```text
gxlimg fip.c: the FIP stores BL31 "load address and entry point". In the
0x50-byte family header the only nonzero fields are +0x08..+0x2f (s2b); no
separate entry word exists, so the family convention reads entry == load ==
0x05100000 (BL2 jumps to the image base; RESET_TO_BL31=0 path in the
embedded firmware tree passes plat params in x4/x5 — the reference bl31.bin
first instructions consume exactly x4/x5, then clear SCTLR_EL3.M).
handoff to BL33: ranges only (AO regs), plus the sharemem ABI
(SMC 0x82000020/21) — no pointer/entry/vector ever crosses to NS. the
SMC dispatcher that serves BL33's 15 smc sites (round 14) has only one
place left to live: the protected window 0x05100000..0x05300000.
```

## 8. BL32

`[0x05300000, 0x07300000)`: CONFIRMED reserved (AO CFG4+CFG3-lo, DTB secos
reg, BL2 table bl32→0x05300000), `no-map`+`status=disable` on this build, and
unreadable at its base (round19/26). Not further pursued per brief.

## 9. final table

| property | status | evidence |
|---|---|---|
| BL31 runtime range | CONFIRMED `[0x05000000,0x05300000)` | AO CFG3/CFG5 live (r26) + decoder disasm + DTB `reserve_mem_size` |
| BL31 image base | CONFIRMED-STRUCTURAL `0x05100000` | BL2 FIP table + bl31.img header (family); BL33 `clear_range = start+0x100000` (exact); live fault boundary |
| BL31 entrypoint | UNKNOWN (presumed = base `0x05100000`) | header carries no separate entry field; gxlimg says entry is in FIP data; reference `_start` consumes x4/x5 |
| BL31 size | CONFIRMED `0x300000` reserved / `0x200000` secure window | AO CFG3 + bl31.img header +0x18/+0x28 |
| first readable byte | `0x05000000` | round26 byte-proven 1 MiB |
| first protected byte | `0x05100000` | round26 faults (x2 sessions) + header `secure_start` + BL33 derivation |
| protection mechanism | class CONFIRMED (secure firewall, pre-BL33); register UNKNOWN | PT decode refutes MMU; boundary == image base; no TZ reg in any artifact |
| BL32 base | CONFIRMED `0x05300000` | AO CFG4 + DTB + BL2 table |
| BL32 size | CONFIRMED `0x2000000` | AO CFG3 lo + DTB |
| image source | boot0/boot1 hw partitions ← `bootloader.img` FIP (encrypted at rest) | rounds 18/26; plaintext table absent (TOC frag is ciphertext) |
| loader | BL2/BL30 chain (family design); exact aquaman str site UNKNOWN | BL2-only writer candidate; BL33/BL31/kernel all read-only, proven |
| handoff | AO GP regs + sharemem SMC `0x82000020/21`; no pointers to NS | decoder disasm + DTB + round14 SMC census |

```text
BL31 runtime range   = CONFIRMED
BL31 image location  = 0x05100000..0x05300000 (secure window, 2 MiB)
BL31 entrypoint      = UNKNOWN (presumed 0x05100000 = image base)
BL31 protection      = secure-memory firewall configured before BL33;
                       register UNIDENTIFIED; MMU-unmapped REFUTED
BL31 bytes readable  = NO
reason               = window is Secure-only; TPL/BL33 is Normal-world and
                       every NS read aborts (Errno 5/19, USB drop)
next static path     = decrypt bootloader.img (needs the vendor FIP key /
                       aml_encrypt_gxl inverse) to read the EXACT aquaman
                       BL2 table + bl31.img header + the loader str sites;
                       everything else is now derived
```

no device was touched this round; no new probes were needed (brief s7
optional probes not taken — the boundary question was answered offline).
aux evidence: `reports/round27-bl31/01..06`.
