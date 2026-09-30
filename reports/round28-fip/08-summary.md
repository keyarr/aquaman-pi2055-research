# round28 s8: summary

offline round. no `0x05`, no SMC host, no secure reads, no RAM or eMMC
writes, no firmware modification. every number comes from bytes already in
the repo or from static analysis of vendor binaries already in the repo.

## what changed in our knowledge this round

Before: "bootloader.img is encrypted, we do not know what encrypts it or
with what." After: the encryption is fully specified and the key chain is
traced to a single named wall.

```text
NEW  AES-256-CBC, IV = 16 zero bytes, window [0x0000, 0xC000), in place.
     Read out of aml_bl2_enc_file, not guessed. The zero IV means the first
     plaintext block is a pure single-block oracle.

NEW  FIP ToC layout and the complete UUID table, obtained by RUNNING the
     vendor fip_create on the family artifacts. BL31 = 05d0e189-53dc-1347-
     8d2b-500a4b7a3e38.

NEW  the ToC entry carries its predecessor's uuid, so the lookup chain is
     search(UUID_BL30) to reach the BL31 payload.

NEW  aml_ctrl_blk_check contract (0x200, AMLC at +0x0c and +0xfc).

NEW  per-image encryption uses a random 32-byte key and random IV exported to
     "<name>.key.pxp". Per-object keys exist.

NEW  the three root-key SHA-2 fingerprints the vendor tool accepts, and the
     fact that the AES key is the last 32 bytes of the per-OEM key package.

NEW  bootloader.img is uniformly random with exactly one piece of structure:
     a 128-byte record at five offsets, all 0x80 mod 0x10000. ECB refuted
     against the live BL33 plaintext.

NEW  bootloader.img is NOT a --bootsig output (size not 0x4000-aligned, and
     --bootsig ends in a 0x4000 pad).

NEW  (delta, follow-up pass of the same round) AMLSECU! provenance closed:
     the magic is referenced only inside aml_img_sig (--imgsig), which
     delegates to aml_bl3_enc_file — so boot/recovery/dt AMLSECU! objects
     are AES-256-CBC under a RANDOM per-object key+IV exported to
     "<name>.key.pxp" at packaging time.

NEW  boot.img fully mapped from its plaintext AMLSECU! header: kernel object
     [0x1000, 0x95a000), dtb object [0x95a000, 0x969000), AVB hash block,
     unsigned vbmeta ("AVB0", algorithm 0) at 0x96a000, "AVBf" footer in the
     last 0x40 bytes with vendor-deviant BE u32 fields.

NEW  dt.img structure: 32-byte PLAINTEXT szSHA2KeyID prefix (ef8996bd…1492,
     identical to all four AMLSECU! descriptors of boot+recovery) + 0xE800
     uniform ciphertext. Same plaintext as boot.img's dtb object, different
     ciphertext — direct corroboration of the per-object random key scheme.

NEW  the bootloader.img 128-byte record does not embed the firmware KeyID
     in any slice; the two containers share no metadata we can see.
```

## case

```text
CASE C. algorithm fully known, key derivation partially known, key material
exclusively in the secure world. No offline decryption path exists.
```

## answer block

```text
bootloader container format   = UNKNOWN. Uniform ciphertext; not a plaintext
                                fip_create package, not a --bootsig output.
                                Not ECB (proven vs live BL33).
FIP location                   = UNKNOWN. The ToC is inside the encrypted
                                region; magic 0xaa640001 absent.
BL31 object offset             = UNKNOWN. Candidate 0x20000 (LOW-MEDIUM).
BL31 object size               = UNKNOWN. Candidate 0x2C000 (LOW-MEDIUM).
BL31 load address              = 0x05100000  (CONFIRMED, derived from live AO
                                registers and the exact BL33)
BL31 entrypoint                = UNKNOWN. The family header has no entry field.
BL32 object                    = UNKNOWN. Candidate region 0x4C000 + 0x40000.
BL33 object                    = UNKNOWN. Candidate region 0x8C000 + 0xBC200.
encryption algorithm          = AES-256-CBC, block 16, IV = 16 zero bytes.
decryption entrypoint          = aml_bl2_enc_file/aml_file_aes on the host
                                side; on the device the unwrap is BL31/BL32,
                                behind the secure boundary.
key source                     = last 32 bytes of the per-OEM aml user key
                                package, itself rooted in an efuse-bound
                                Amlogic root key.
offline decryption possible    = NO. Case C.
```

## final table

| field | value | source | exact-aquaman | confidence |
|---|---|---|---|---|
| container format | unknown, uniform ciphertext | s1 | YES | HIGH |
| FIP location | unknown | s1 s2 | — | — |
| BL31 object offset | 0x20000 | s2 s6 | no | LOW-MED |
| BL31 object size | 0x2C000 | s2 s6 | no | LOW-MED |
| BL31 load address | 0x05100000 | AO CFG5, BL33 clear_range | YES | HIGH |
| BL31 entrypoint | unknown | s4 | — | — |
| BL31 reservation | 0x05000000 + 0x300000 | AO CFG5/CFG3, DTB | YES | HIGH |
| BL31 secure window | 0x05100000 + 0x200000 | live fault boundary, DTB | YES | HIGH |
| BL32 base / size | 0x05300000 / 0x2000000 | AO CFG4/CFG3-lo, DTB | YES | HIGH |
| BL33 base | 0x01000000 | exact BL33 dump | YES | HIGH |
| encryption algorithm | AES-256-CBC | aml_bl2_enc_file | no | HIGH |
| IV | 16 x 0x00 | aml_bl2_enc_file | no | HIGH |
| encryption window | [0x0000, 0xC000) | aml_file_aes call site | no | HIGH |
| BL31 uuid | 05d0e189-53dc-1347-8d2b-500a4b7a3e38 | fip_create .data | no | HIGH |
| ToC layout | 0x10 header, 0x28 entries | fip_create run | no | HIGH |
| key source | aml user key package, last 32 bytes | aml_bl2_enc_file | no | HIGH |
| key material | secure-only (efuse -> ladder -> BL31) | s6 | — | HIGH |
| ECB | refuted for BL33 | s1 s5 | YES | HIGH |
| 128B record | 5 sites, 0x80 mod 0x10000 | s1 | YES | HIGH |
| offline decryption | NO, case C | s6 | YES | HIGH |

## where the chain stops

```text
efuse / hardware key ladder
  -> BL31 or BL32 key-slot unwrap      [in the secure world, unreadable]
    -> AES-256-CBC with IV = 0         [known]
      -> plaintext FIP                 [requires the key]
```

The wall is not a missing algorithm and not a missing format description.
It is one 32-byte secret held by the secure world.

## what would actually move this

Only one thing, and it is not more offline analysis: a legitimate copy of the
per-OEM `aml user key` package for MiTV-AESP0/aquaman PI.2055. Given that,
`s6` gives a complete procedure — one AES-256-CBC pass with a zero IV over
`[0, 0xC000)`, then read the ToC, then the BL2 table, then the bl31.img
header, then the BL31 object. Everything downstream of the key is already
specified. Nothing else in this repository can substitute for it.

## artefacts

```text
tools/round28_fip.py        FIP/ToC/ctrl-blk parsers, crypto contract,
                            AMLSECU! descriptor reader, entropy census,
                            repeat probe, block search, single-block IV=0
                            oracle
tools/round28_vendor_summ.py  per-function call/constant summary of
                            aml_encrypt_gxl; reproduces the s5/s6 evidence
tools/fip_probe.sh          rebuilds the reference FIP and the ToC fixture
reports/round28-fip/ref5-toc.bin   256-byte ToC fixture (sha256 7c114a2e…)
tools/run_tests.py          TestRound28Fip, 12 tests
```