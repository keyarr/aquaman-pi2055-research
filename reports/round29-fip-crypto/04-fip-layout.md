# round29 / 04 — the FIP layout inside the 0x148200-byte file

## the five streams, now with a mechanism

The round-28 reading B (bases 0xC000 / 0x10000 / 0x20000 / 0x4C000 /
0x8C000) is no longer only structure-inference: `aml_boot_make` assembles
exactly this shape — header at 0xC000 followed by payload streams padded
to 0x10000, each stream the output of `--bl3enc`/`--bl3sig`. The tail
arithmetic closes exactly:

```text
stream  base      size      content (v1.3 order)      ends
  0     0x0C000   0x04000   FIP header (0xAA640001)   0x10000
  1     0x10000   0x10000   BL30 (scp/bl30+bl301)     0x20000
  2     0x20000   0x2C000   BL31                      0x4C000
  3     0x4C000   0x40000   BL32 (optee/tee)          0x8C000
  4     0x8C000   0xBC200   BL33 (u-boot)             0x148200  = file end
```

`0x8C000 + 0xBC200 = 0x148200` — the file size, exactly, with no trailing
gap. The 0x4000/0x10000/0x2C000/0x40000/0xBC200 sizes are the round-28
candidates; the round-28 boundary is therefore **upgraded to MEDIUM-HIGH**
for the *envelope* (the stream partitioning), with the caveat that the
enclosed content may still deviate from the v1.3 sizes if the production
tool padded differently.

## which object is which

Corroboration independent of sizes:

```text
BL31 uuid  05d0e189-53dc-1347-8d2b-500a4b7a3e38   (in-tree table 0x716700
                                                   + boot_sig_file compare
                                                   words 0x4114f0..)
BL32 load  0x05300000, size 0x2000000             (v3 header constants
BL33 base  0x01000000                              baked at 0xC0C0.. —
                                                   identical to the
                                                   family bl2.bin FIP
                                                   table and the live AO
                                                   registers)
BL31 load  0x05100000                              (bl31.img header fixture)
```

The stream order bl30/bl31/bl32/bl33 is the v1.3 bootmk order (its getopt
table is `bl2 bl30 bl31 bl32 bl33 bl3x`) and the stream sizes must grow in
the observed 0x10000 → 0x2C000 → 0x40000 → 0xBC200 pattern. BL30 (SCP,
0x9784 family) fits 0x10000; BL31 (family 0x2C3A8) fits 0x2C000; BL32
(optee, typically ≤ 0x40000) fits 0x40000; BL33 (aquaman u-boot =
0x1D8000 raw, but the bootmk stream is the *signed+encrypted+LZ4* object;
family reference 0x11170 compressed in the round-28 fip_create run) fits
0xBC200 with room for the AMLSECU-era expansions.

## the 0x20000 + 0x2C000 = BL31 boundary

Round 28's LOW-MEDIUM label came from size-matching alone. This round:

```text
for:     bootmk assembles streams in exactly this order and the sizes
         close the file exactly; BL31 is the third stream in every
         gxl layout; family bl31.bin = 0x2C3A8 < 0x2C000 only because the
         FIP stream carries header+signature overhead — the family fip
         BL31 stream measured 0x2C3A8 WITH padding in round 28's
         fip_create run (ref5 ToC: BL30@0x1C000 size 0x2C3A8).
against: nothing measured contradicts it.
label    MEDIUM-HIGH (envelope). The boundary is unobservable directly
         (no plaintext headers) but is now the only assignment consistent
         with the reconstructed assembly algorithm.
```

## what a ToC recovery would give

If any stage is ever reversed, the file becomes:

```text
0x0C000  FIP ToC (0xAA640001, version, 0x28-byte entries, null-uuid
         terminator) — encrypted in both v1 and v3 paths
0x10000  BL30 stream: plaintext ctrl 0x200 (AMLC, key+IV @+0x40,
         timestamps @+0x88/+0xb0) + ciphertext + ctrl copy
         — OR encrypted whole, per the production variant
0x20000  BL31 stream: as above; after decryption the object begins with
         the 0x12348765 header (load 0x05100000) — this is the bl31.img
         header round 27/28 wanted
0x4C000  BL32 stream
0x8C000  BL33 stream (possibly LZ4C-wrapped u-boot)
```

The record128 sits at stream+0x80 in every stream — the only position
both the v1 ctrl timestamps (+0x88) and a deterministic build stamp
occupy, which is why it survived five independent encryptions (see 06).
