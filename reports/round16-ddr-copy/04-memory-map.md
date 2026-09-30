# round 16.04 - memory map for the primitive

static only. only regions already proven or strongly established are
listed. permissions are NOT invented: readable/writable mean "demonstrated
by a prior read/write or by code that provably touches it", otherwise
UNPROVEN. MMU permission bits are not decoded here to avoid inventing
rights from descriptor-shaped words.

Base image for everything BL33: [0x37e18000,0x37ff0000), sha256 664fb34a,
page table at 0x37ff0000 (8192 words ending at 0x3800000).
Source: reports/round14-bl33-persist/00_persist.txt.

## 1. regions

```text
region                  range                        mapped  read   write  evidence
BL33 live copy          [0x37e18000,0x37ff0000)       YES     YES    UNPROVEN  page map 00_persist.txt; mread rounds 12-13;
                                                                          nonzero tail to 0x37feffff; live .bss write at
                                                                          0x37f8a638 ('upload mem 0x37800000 ...' left by
                                                                          the burning tool, round 14 A.3)
BL33 code pages         scattered, e.g.              YES     YES    UNPROVEN  same page map (code/data/rodata runs);
                        0x37e19000..0x37e1ffff etc.                             no write demonstrated; perms not decoded
BL33 cmd_tbl            ~0x37f60fd0.. (80 slots,      YES     YES    UNPROVEN  04_cmds.txt round 14; 01_cmdsurface round 15;
                        48 B stride)                                            write would be dst=table addr, len>=16 KiB
                                                                          pattern -> destructive, not surgical
BL33 page table         [0x37ff0000,0x38000000)       YES     YES    UNPROVEN  8192 descriptor words, 00_persist.txt;
                        64 KiB                                                     corrupting it hangs the board; no clamp
                                                                          stops dst from pointing here
fastboot download buf   [0x10200000,0x18200000)       YES     YES    YES      rx_handler 0x37e95274 mov x1,#0x10200000;
                        (max 128 MiB)                                             download_bytes counter; prior mread-style
                                                                          reads of nearby DRAM in rounds 7-13
burning transfer buf    [0x07700000,0x0b700000)       YES     YES    YES      0x37e7bbf4 mov x3,#0x7700000 + header math;
                        (64 MiB)                                                  optimus slots; upload/download used it
                                                                          in every round since 7
runtime DTB             [0x01000000,0x0100e3a8)       YES     YES    UNPROVEN  artifacts/aquaman.dtb 58280 B, FDT totalsize
                        (58280 B)                                                 0xe3a8, from mread_01000000_01000000.bin
                                                                          sha256 f5e20c9e...; dtb_mem_addr=0x1000000
kernel load area        board-dependent (bootm       UNPROVEN UNPROVEN UNPROVEN  no kernel dump in repo; bootm default
                        default 0x1080000, SMC                                    0x1080000 / 0x1800000 window known from
                        window 24 MiB)                                            E3, but residency not demonstrated
AML_RES / misc eMMC     eMMC, not RAM              n/a     n/a    n/a      out of scope for a RAM primitive; listed only
                                                                          so it is not confused with the buffers above
page tables (BL33's)    [0x37ff0000,0x38000000)       YES     YES    UNPROVEN  same as BL33 page table row; reachable as
                                                                          dst (no clamp) but write = likely hang
MMIO (e.g. 0xc1109988   unmapped-cached? touch =        n/a     n/a    n/a      timer/PHY regs touched by the handler itself;
timer, 0xc8836c00 PHY)  hang/fault risk                                           large dst/len can hit these: no check
                                                                          stops it, consequence is a crash not a write
```

Notes:

- "currently mapped" means the descriptor window covers it AND prior
  reads touched nearby DRAM without fault. The two host buffers and the
  BL33 window satisfy both. Kernel/AML_RES do not.
- No region above is marked writable on MMU-permission grounds. The only
  YES writes are the two host buffers (their own ingress protocol
  writes them). Everything else writable-by-primitive is address-reach,
  not permission proof.
- DTB base 0x01000000 is 16 MiB below the fastboot buffer and 96 MiB
  below the burning buffer; all three fit the ddr_test_copy 32-bit src.

## 2. what the primitive could reach IF it were arbitrary (offline only)

Address reach (no clamp) includes, in principle:

```text
class                 example in image              surgical?  note
code section          0x37e21000.. text              NO         min 16 KiB pattern fill destroys surrounding code;
                                                                  board hangs before any branch lands
function pointer      cmd_tbl slots / find_cmd       NO         same overwrite footprint; table entry is 8 B but
                      blr x4 targets (mmc/store/env)               handler writes >=16 KiB around it
command table entry   0x37f60fd0..                   NO         same reason
string pointer        rodata c-strings               NO         pointer is 8 B; fill kills neighbours
branch target         b/bl immediates in text        NO         same footprint problem
control data          download_size [0x37fbdf90],    MAYBE*     *the 16-byte tail at dst+len is the onlyPrecise
                      download_bytes [0x37fbdf8c],                write; hitting a 4/8-byte control word exactly
                      transferBuf [0x37f5e600]                    at dst+len while the 16 KiB+ pattern lands
                                                                  elsewhere is theoretically placeable but
                                                                  the pattern still lands somewhere: never clean
```

Nothing was written. No payload is proposed. The table exists to stop
the "patch before execution" hypothesis from being hand-waved: even
ignoring the fill, the minimum footprint (16 KiB pattern) makes every
class above destructive, and with the fill the only precise write is
the 16-byte tail whose address is dst+len (attacker picks both, but the
pattern still fires). A surgical function-pointer or branch-target
overwrite without crashing the board is not shown and, given the floor,
is not credibly reachable through this handler.
