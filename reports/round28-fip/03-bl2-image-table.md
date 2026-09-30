# round28 s3: BL2 image table and loader reconstruction

offline. the aquaman's own BL2 is inside the encrypted region of
`bootloader.img` (s1), so nothing below is aquaman-exact. What is new this
round is the *algorithm*, taken from the family `bl2.bin` table that round 27
found, plus the mechanism the loader uses to consume it, recovered from the
u-boot reference tree.

## 1. the table, re-measured

`round27_layout.parse_bl2_fip_table` walks the tail of `gxl/bl2.bin`. Records
are 0x28 bytes and each carries the first word of the **next** image's uuid,
which is how the chain links:

```text
uuid_w0    load        name
9766fd3d   0x01100000  bl30
ddccbbaa   0x01200000  bl301
47d4086d   0x05100000  bl31
05d0e189   0x05300000  bl32
d6d0eea7   0x01000000  bl33
```

Cross-check against the s2 UUID table: `9766fd3d` is UUID_BL2, `ddccbbaa` is
UUID_BL301, `47d4086d` is UUID_BL30, `05d0e189` is **UUID_BL31**, `d6d0eea7`
is UUID_BL32. So the record named `bl31` carries UUID_BL30, consistent with
the same predecessor-shift the FIP ToC uses. `BL33`'s uuid is the last entry
and is not present in the gxl artifacts.

## 2. the chain, end to end

```text
ROM  -> fip_toc_search(UUID_TOC)  -> BL2 @ FIP offset, load 0x01000000-class
BL2  -> fip_toc_search(UUID_BL2)  -> BL30 payload (offset,size from ToC)
BL2  -> fip_toc_search(UUID_BL30) -> BL31 payload
BL30 -> fip_toc_search(UUID_BL301)-> BL301 payload
...
```

Concretely, locating BL31 requires two independent structures agreeing:

```text
1. FIP ToC   : search UUID_BL30 -> (offset, size) of the BL31 payload
2. BL2 table : find the record whose uuid_w0 == 47d4086d -> load address 0x05100000
```

Both live inside the encrypted region of `bootloader.img`, so neither is
readable at rest. This is the same conclusion round 27 reached, now with the
lookup rule and the target uuid written down.

## 3. what BL2 does with the pair

The loader must, per image: read `(offset,size)`, decrypt, relocate to the
table's load address, then hand control over. The pieces that are pinned:

```text
decrypt primitive            AES-256-CBC, IV = 16 zero bytes (s5)
destination                  from the BL2 table load address
per-object key               see s6: random per object, exported to a side file
```

The relocation/entry step is NOT pinned for the aquaman. Family `bl31.img`
carries no entry-point field (s4), so the convention is entry == load base;
gxlimg's `fip.c` states the entry point is kept in FIP data, which is either
the ToC flags word or the BL31 header. UNKNOWN which, until the header is
readable.

## 4. BL33 has no FIP table

Confirmed by round 14 (15 SMC sites, no ToC parse) and by s1: the BL33 dump
contains no `0xaa640001`. The FIP is consumed entirely by BL2/BL30. BL33 is
handed ranges over the AO registers plus the sharemem SMC ABI, never a
pointer (round 27 s7). So there is no later loader to consult; BL2 is the
only consumer, and BL2 is the thing that is encrypted.

## 5. status

```text
BL2 image table present in aquaman      almost certainly YES (same family,
                                         same load addresses pinned by AO regs)
BL2 table bytes readable at rest         NO
lookup algorithm                         reconstructed above
per-image key availability               see s6
```