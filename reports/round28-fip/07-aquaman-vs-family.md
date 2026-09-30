# round28 s7: aquaman vs family reference

offline. the point of this file is to stop the family artifacts from being
promoted to aquaman facts. every row states which artifact produced it.

## 1. separation

```text
EXACT AQUAMAN      byte-derived from this repo's own captures
FAMILY REFERENCE   .src/u-boot-khadas/fip/{gxl,gxb,txl,...} + the two vendor
                   tools. Structure only. Never evidence about the aquaman.
INFERRED           an aquaman claim argued from family structure plus an
                   independent aquaman measurement. Labelled as such.
```

## 2. table

| property | value | source | exact-aquaman |
|---|---|---|---|
| bootloader.img size | 0x148200 | measured | YES |
| bootloader.img sha256 | c7b8eea6…3424 | measured | YES |
| uniform ciphertext | chi2 226.6, 0/329 blocks deviant | measured | YES |
| known magics present | none of 11 searched | measured | YES |
| 128-byte record, 5 sites | 0xc080 0x10080 0x20080 0x4c080 0x8c080 | measured | YES |
| BL33 payload not ECB | 0 block matches vs live BL33 | measured | YES |
| BL31 load address | 0x05100000 | live AO CFG5 + BL33 `clear_range` derivation | YES (derived) |
| BL31 reservation | 0x05000000 + 0x300000 | live AO CFG5/CFG3 + DTB | YES |
| BL31 secure window | 0x05100000 + 0x200000 | live fault boundary + DTB | YES |
| BL32 base / size | 0x05300000 / 0x2000000 | live AO CFG4/CFG3-lo + DTB | YES |
| BL33 base | 0x01000000 | exact BL33 dump | YES |
| BL33 size at rest | UNKNOWN | — | — |
| FIP ToC layout | 0x10 hdr, 0x28 entries | fip_create run offline | no |
| UUID table | 6 uuids incl. BL31 `05d0e189…` | fip_create .data | no |
| bl31.img header fields | 6 values, magic 0x12348765 | gxl/bl31.img | no |
| AML control block | 0x200, AMLC at +0x0c/+0xfc | aml_ctrl_blk_check | no |
| AES-256-CBC, IV=0, [0,0xC000) | exact | aml_bl2_enc_file disasm | no |
| per-image random key + IV | exact | aml_bl3_enc_file disasm | no |
| three root-key SHA-2 digests | exact | aml_check_root_key_sha2_with_efuse | no |
| object boundaries | 0xC000 0x10000 0x20000 0x4C000 0x8C000 | hypothesis | no |
| BL31 object offset/size | 0x20000 / 0x2C000 | hypothesis | no |
| BL31 entrypoint | UNKNOWN | no field carries one | — |

## 3. where the family is *not* evidence

* `gxl/bl31.bin` (0x2C368) and `gxb/bl31.bin` are different binaries. Using
  their size to call the 0x2C000 region "BL31" is a size coincidence, not an
  identification, and it is recorded as such.
* The aquaman BL33 is `2015.01-g7ac5df7677-dirty` and is 0x1d8000 bytes in
  RAM. No gxl/gxb `bl33` artifact exists in the tree, so there is no family
  reference for BL33 at all.
* `+0x04 = 0x4e20` is constant across gxl and gxb, which proves only that it
  is not board-specific. Its meaning is UNKNOWN.
* The three root-key digests are Amlogic master-key fingerprints. They say
  nothing about whether the aquaman uses one of them.

## 4. the one place family and aquaman meet on measured ground

The bl31.img header's six values (`0x05100000`, `0x05000000`, `0x300000`,
`0x05100000`, `0x200000`) reproduce the aquaman's live AO registers and its
runtime DTB exactly. That is what makes the header the right hypothesis for
how BL2 learns the layout, and it is why the hypothesis is kept. It is still
a hypothesis: no aquaman header byte has been read.