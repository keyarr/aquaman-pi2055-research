# 02 — load origin: who produced the bytes at [0x05100000, 0x05300000)

answer: **BL2 loads BL31 from the eMMC FIP at 0x05100000**; the layout is
declared twice in the family FIP files that ship inside this repo.

## (a) BL2's own load-address table (FAMILY STRUCTURAL REFERENCE)

`.src/u-boot-khadas/fip/gxl/bl2.bin` @0x9458 (gxb identical in meaning):

```text
09458  00 00 00 00 97 66 fd 3d ...   <- FIP img-table magic 0xAABBCCDD
09460  ... 00000010 01 000000 ...    <- record: u64 addr 0x01100000, "bl30"
09470  "bl30"  aabbccdd              <- link = next uuid word0 (bl301)
09490  ... 00000020 01 ... "bl301"   <- 0x01200000, link 6d08d447 (bl31)
094b0  ... 00000010 05 ... "bl31"    <- 0x05100000, link 89e1d005 (bl32)
094e0  ... 00000030 05 ... "bl32"    <- 0x05300000, link a7eed0d6 (bl33)
09510  "bl33"                        <- 0x01000000, link 0
```

record = `u64 load_addr; char name[8]; u32 0; u32 next_uuid_w0; u64 0; u64 0`,
stride 0x28; the uuid word0 chain matches `gxlimg/fip.c uuid_list` exactly
(bl30 97 66 fd 3d / bl301 dd cc bb aa / bl31 47 d4 08 6d / bl32 05 d0 e1 89 /
bl33 d6 d0 ee a7). this is BL2's resident load table — **bl31 -> 0x05100000,
bl32 -> 0x05300000**.

## (b) bl31.img wrapper header (FAMILY STRUCTURAL REFERENCE)

`.src/u-boot-khadas/fip/gxl/bl31.img` and `gxb/bl31.img`, header @0x00
(0x50 bytes; gxlimg `fip.c gi_fip_add`: read at file offset 0x100? no —
`bl31.img` head, `BL31_MAGIC 0x12348765`, copied into the FIP at
`FTE_BL31HDR_OFF(n) = 0x430 + 0x50*n`; comment: *"BL31 binary store
information about load address and entry point in the FIP data"*):

```text
+0x00 12348765        BL31_MAGIC
+0x04 00004e20        (constant, both SoCs; meaning not established)
+0x08 0000000005100000  load address      -> 0x05100000
+0x10 0000000005000000  rsvmem start     -> 0x05000000  (= AO CFG5)
+0x18 0000000000300000  rsvmem size      -> 0x00300000  (= AO CFG3 hi)
+0x20 0000000005100000  secure window start -> 0x05100000
+0x28 0000000000200000  secure window size  -> 0x00200000
+0x30.. 0x00
```

both gxl and gxb carry identical values — a fixed platform layout, not a
per-board choice.

## writers of CFG3/4/5 — exhaustive negative results

```text
EXACT BL33 dump:      every ldr/str/ldp/stp/stur/adrp+add with disp
                      0x24c/0x250/0x254 -> 4 read sites only (01-ao-regs.md).
                      zero writes.
gxl bl31.bin:         17 AO movz/movk constants (0xc8100228 x2, 0xda10023c,
                      0xda10001c x4, 0xda10025c x5, 0xda100248, 0xda100140,
                      0xc81004c0 x2): watchdog, JTAG, GPIO, clock. none at
                      0x24c/0x250/0x254.
gxb bl31.bin:         no AO movz/movk pair at all.
u-boot tree (full):   no writel(P_AO_SEC_GP_CFG[3-5]) — grep over all of
                      .src/u-boot-khadas (164 matches for the symbol, all
                      secure_apb.h defines + readers in cmd_rsvmem.c,
                      aml_v2_burning.c CFG0/CFG7 reads, board files CFG0).
linux tree (full):    no AO_SEC_GP_CFG access at all.
```

therefore the writer is the pre-BL33 chain (BootROM/BL2/BL30), and BL2 is
demonstrated to carry the exact numbers (a). The at-rest aquaman equivalent
is encrypted: `bootloader.img` has no plaintext FIP table (round18: no
`01 00 64 AA` magic, only a ciphertext `TOC` fragment at 0x4bebe; no
`bl30/bl301/bl31/bl32/bl33` name strings; magic 0x12348765 = 0 hits) — the
aquaman values themselves are UNRECOVERABLE without decrypting the FIP, but
the platform is the same GXL family and the live AO values match the family
constants exactly.

## timeline

```text
BootROM -> BL2 (from eMMC boot0/boot1) -> loads BL30, BL31@0x05100000,
BL32@0x05300000, BL33@0x01000000 (table a); marks BL31 window Secure;
publishes layout via AO GP regs; BL33 reads regs (01) and publishes to DTB.
```
