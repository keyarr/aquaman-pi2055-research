# round29 / 06 — the 128-byte record, five sites

## observations (round 28, re-verified here)

```text
sites       0xC080  0x10080  0x20080  0x4C080  0x8C080     all ≡ 0x80 mod 0x10000
content     128 identical bytes at all five sites; 8 distinct 16B slices
first16     7903307770ddfd6550dad979a1f39256
occupancy   101 distinct byte values — NOT a plaintext pattern, NOT the
            firmware KeyID (round 28), NOT any in-tree plaintext object's
            bytes (tested this round)
```

## parser references: none

No in-tree parser reads offsets 0x80-mod-0x10000 of a file. The things
that DO live at +0x80 of the family containers:

```text
aml_bl3_enc_file ctrl  +0x40 key+IV, +0x70/+0x78 sizes, +0x88/+0xb0
                       timestamps (aml_set_blk_time_stamp)
bootmk v1 ctrl         same ctrl block, written at 0xC000 and 0xFE00
FIP ToC entries        0x28-byte entries starting at ToC+0x10 — +0x80
                       would be entry 4 inside the header block
```

## the mechanism this round established

CBC is all-or-nothing per block and chains: an identical 128-byte
ciphertext run at the same offset in five streams requires, for each
stream, (a) identical plaintext there and (b) an identical key+IV stream
up to that point — i.e. **all five streams were encrypted under the same
key with the same IV, with deterministic (non-rand) content in the
128-byte window**. The v1.3 in-tree code gives every `--bl3enc` stream an
independent `rand()` key and a time()-based timestamp, which would make
these five windows differ. Therefore the production build:

```text
1. used ONE key for all five streams (the userkey tail32 — the
   bootmk3/bootsig composition does exactly this for the header; the
   five streams followed suit), and
2. the 128-byte window is deterministic metadata — most plausibly the
   ctrl/timestamp block area whose content was fixed at build time.
```

## what it is not

```text
metadata useful for decryption   NO — its content is ciphertext under the
                                 same key as the streams; it leaks nothing
                                 without the key
external transport header        NO — no in-tree plaintext format matches
                                 (bl31.img header, AMLSECU descriptors,
                                 KeyID, LZ4C wrapper: all excluded)
inside an encrypted region       YES — every site is mid-stream, and the
                                 streams' ciphertext is uniform otherwise
```

Alignment cross-check:

```text
0xC080 mod 0x10   = 0   (AES block aligned)
0xC080 mod 0x200  = 0x80 (second half of a ctrl block sector)
0xC080 mod 0x1000 = 0x80
0xC080 - 0xC000   = 0x80 = header entry region / ctrl timestamps area
```

Conclusion: the record is a **build-time-deterministic 128-byte metadata
window at stream+0x80, encrypted under the common build key**. It is a
side effect of the pipeline, not a handle on it. The possibility of
useful plaintext-adjacent metadata in bootloader.img is eliminated: no
plaintext region of any size exists outside the (unknown-key) envelope.
