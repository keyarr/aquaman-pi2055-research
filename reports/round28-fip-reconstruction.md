# round28: offline FIP / firmware-pipeline reconstruction

date 2026-09-30. **zero device I/O this round.** no `0x05`, no SMC host, no
secure reads, no RAM or eMMC writes, no firmware modification, no execution
of device code. inputs were bytes already in the repo plus two not-stripped
vendor binaries that ship inside the reference tree.

tools `tools/round28_fip.py`, `tools/fip_probe.sh`; tests `TestRound28Fip`
(12 tests, pass). detail in `reports/round28-fip/`.

## 0b. follow-up delta pass (same round, same constraints)

A second static pass over the two vendor binaries plus the AMLSECU! family
images added four results that do not change the case verdict but close
gaps in the container map:

```text
1  AMLSECU! provenance      the magic (rodata 0x4e7c0b) is referenced only
                            inside aml_img_sig (--imgsig); that path encrypts
                            via aml_bl3_enc_file. boot/recovery/dt objects
                            are therefore AES-256-CBC under a RANDOM
                            per-object key+IV exported to "<name>.key.pxp"
                            at packaging time. s5b.
2  boot.img payload map     kernel object [0x1000,0x95a000), dtb object
                            [0x95a000,0x969000), AVB hash block, unsigned
                            vbmeta ("AVB0", algorithm 0) @0x96a000,
                            "AVBf" footer in the last 0x40 bytes with
                            vendor-deviant BE u32 fields. s1 s7.
3  dt.img structure         32-byte PLAINTEXT szSHA2KeyID prefix
                            (ef8996bd…1492 == all four AMLSECU! descriptors
                            of boot+recovery) + 0xE800 uniform ciphertext;
                            same plaintext as boot.img's dtb object but a
                            different ciphertext (203/59424 bytes coincide,
                            chance level) — direct corroboration of the
                            per-object random key scheme. s1 s7.
4  no KeyID in bootloader   the five 128-byte records do not embed the
                            firmware KeyID in any 16-byte slice; the two
                            containers share no observable metadata. s1 s7.
```

All four are pinned in `TestRound28Fip` (9 -> 12 tests).

## 0. answer block

```text
bootloader container format   = UNKNOWN. Uniform ciphertext end to end; not a
                                plaintext fip_create package, not a --bootsig
                                output, not ECB.
FIP location                   = UNKNOWN. ToC magic 0xaa640001 absent.
BL31 object offset             = UNKNOWN, candidate 0x20000      (LOW-MED)
BL31 object size               = UNKNOWN, candidate 0x2C000      (LOW-MED)
BL31 load address              = 0x05100000                      (CONFIRMED)
BL31 entrypoint                = UNKNOWN. no field carries one.
BL32 object                    = UNKNOWN, candidate 0x4C000+0x40000
BL33 object                    = UNKNOWN, candidate 0x8C000+0xBC200
encryption algorithm          = AES-256-CBC, block 16
IV                             = 16 zero bytes
encryption window             = [0x0000, 0xC000), in place
decryption entrypoint          = aml_bl2_enc_file/aml_file_aes (host); on the
                                device the unwrap is BL31/BL32, secure-only
key source                     = last 32 bytes of the per-OEM aml user key
                                package, rooted in an efuse-bound root key
offline decryption possible   = NO. CASE C.
```

## 1. the round's actual finding

The encryption is not inferred from behaviour any more. It was read out of
`.src/u-boot-khadas/fip/gxl/aml_encrypt_gxl`, a static, not-stripped ELF64
with `debug_info` and stack-obfuscated strings:

```text
aml_file_aes()      @0x40159e  AES-256-CBC in place, 16B blocks, length must
                              be 16-aligned, key at key_info[0:0x20],
                              IV at key_info[0x20:0x30]
aml_bl2_enc_file()  @0x40d2a6  key_info bzero'd, then the LAST 0x20 bytes of
                              the key package read into key_info[0:0x20]
                              -> IV stays zero; aml_file_aes(fp, 0xC000, ..)
                              with fp freshly fopen'd -> encrypts [0, 0xC000)
```

The zero IV is the useful consequence: the first plaintext block is
`AES_decrypt(C[0])` alone, so any candidate key is checkable against the
single known block `01 00 64 aa 78 56 34 12 00 00 00 00 00 00 00 00`.
Test-pinned.

Also recovered this round:

```text
FIP ToC layout     0x10-byte header (0xaa640001, 0x12345678), 0x28-byte
                   entries {uuid[16], u64 off, u64 size, u64 flags}, null-uuid
                   terminator carrying the image end. Proven by RUNNING
                   fip_create on the family artifacts.
UUID table         6 uuids. BL31 = 05d0e189-53dc-1347-8d2b-500a4b7a3e38.
lookup rule        entry.uuid is the PREDECESSOR's uuid; search(UUID_BL30)
                   to reach the BL31 payload.
ctrl block         aml_ctrl_blk_check: 0x200 bytes, 'AMLC' at +0x0c and
                   +0xfc, 0x200 at +0x02/+0x14/+0xfa, version <= 1 at +0x06.
per-image crypto   aml_bl3_enc_file fills key_info with rand() (32B key +
                   16B IV) and exports it to "%s.key.pxp". Per-object keys
                   exist in this toolchain.
root keys          aml_check_root_key_sha2_with_efuse hardcodes three 32-byte
                   SHA-2 fingerprints of accepted Amlogic master keys.
```

## 2. bootloader.img at rest

```text
0x148200 bytes, sha256 c7b8eea6…3424
whole-file chi2 = 226.6 (df=255)
per-4KiB chi2    min 200.0  median 253.9  max 314.9, 0/329 blocks deviant
11 magics searched (ToC, AMLC, @AML, 6 uuid words, bl31 magic, ANDROID!)
                  0 hits
ECB vs the live BL33 plaintext (round-14 dump, 79601 blocks, every
                  ciphertext offset)  = 0 hits, ECB refuted
```

Correction to an intermediate result: the final 4 KiB block initially scored
chi2 = 3170. That was a bug in the analysis script (expected count hardcoded
to 4096/256 for a 512-byte tail). Recomputed correctly it scores 277. There
is no tail anomaly.

The file's only non-random structure is a **128-byte record repeated exactly
five times**, at

```text
0xc080   0x10080   0x20080   0x4c080   0x8c080      all 0x80 mod 0x10000
```

Eight repeated 16-byte blocks are the eight slices of that one record; an
unaligned sweep of every 16-byte window in the file finds nothing else
repeated. Because a block cipher block is all-or-nothing and CBC chains, this
constrains object bases to two readings:

```text
reading A (CBC-consistent)  bases AT the sites; first 128 plaintext bytes
                            of every object identical, byte 0x80 differs
reading B (ECB-consistent)  bases 0xC000 0x10000 0x20000 0x4C000 0x8C000,
                            record 0x80 into each; sizes
                            0x4000 / 0x10000 / 0x2C000 / 0x40000 / 0xBC200
```

B is preferred on structure (4 of 5 bases 0x10000-aligned, and 0xC000 is
exactly the end of the encryption window) and its 0x2C000 region is 0.4%
off the family BL31 size. But ECB is refuted for the payloads, so B is a
**hypothesis, not a measurement**, and is labelled LOW-MEDIUM throughout.

## 3. case

**CASE C.** Ciphertext in hand; algorithm fully known; key derivation
partially known (package layout and the accepted root-key fingerprints);
key material exclusively secure (efuse -> hardware key ladder -> BL31/BL32
unwrap, none of it observable, and BL33 only holds handles for SMC
0x82000060/61, never values).

No decryption path is invented.

## 4. public-key hypotheses, tested and closed

Because the IV is zero, testing a candidate key costs one AES block. Tried
against the known ToC prefix and all negative: the three hardcoded digests,
all-zero, all-0xff, and sha256 of `aml`, `amlogic`, `Amlogic`, `aml_encrypt`,
`gxlimg`, `amlogicboot`, `aml_encrypt_gxl`, `aml_rsa_key`, `fip`,
`0x12345678`, `12345678`, `amlogic_gxl`, `secure_boot`. Pinned in
`test_no_public_key_reveals_the_toc` so nobody repeats it.

## 5. what would actually move this

One thing, and it is not more offline analysis: a legitimate copy of the
per-OEM `aml user key` package for MiTV-AESP0/aquaman PI.2055. With it the
procedure is already complete — one AES-256-CBC pass, zero IV, over
`[0, 0xC000)`, then the ToC, then the BL2 table, then the bl31.img header,
then the BL31 object. Everything downstream of the key is specified.

## 6. final table

| field | value | source | exact-aquaman | confidence |
|---|---|---|---|---|
| container format | unknown, uniform ciphertext | s1 | YES | HIGH |
| FIP location | unknown | s1 s2 | — | — |
| BL31 object offset | 0x20000 | s2 s6 | no | LOW-MED |
| BL31 object size | 0x2C000 | s2 s6 | no | LOW-MED |
| BL31 load address | 0x05100000 | AO CFG5 + BL33 derivation | YES | HIGH |
| BL31 entrypoint | unknown | s4 | — | — |
| BL31 reservation | 0x05000000 + 0x300000 | AO CFG5/CFG3 + DTB | YES | HIGH |
| BL31 secure window | 0x05100000 + 0x200000 | live fault boundary | YES | HIGH |
| BL32 base / size | 0x05300000 / 0x2000000 | AO CFG4/CFG3-lo + DTB | YES | HIGH |
| BL33 base | 0x01000000 | exact BL33 dump | YES | HIGH |
| encryption algorithm | AES-256-CBC | aml_bl2_enc_file | no | HIGH |
| IV | 16 x 0x00 | aml_bl2_enc_file | no | HIGH |
| encryption window | [0x0000, 0xC000) | aml_file_aes call site | no | HIGH |
| BL31 uuid | 05d0e189-53dc-1347-8d2b-500a4b7a3e38 | fip_create .data | no | HIGH |
| ToC layout | 0x10 header, 0x28 entries | fip_create run | no | HIGH |
| ctrl block | 0x200, AMLC at +0x0c/+0xfc | aml_ctrl_blk_check | no | HIGH |
| key source | aml user key pkg, last 32 B | aml_bl2_enc_file | no | HIGH |
| key material | secure-only | s6 | — | HIGH |
| per-image key | random, exported `.key.pxp` | aml_bl3_enc_file | no | HIGH |
| ECB | refuted for BL33 | s1 s5 | YES | HIGH |
| 128B record | 5 sites, 0x80 mod 0x10000 | s1 | YES | HIGH |
| offline decryption | NO, case C | s6 | YES | HIGH |
| AMLSECU! producer | --imgsig -> aml_bl3_enc_file, random per-object key | s5b | no | HIGH |
| boot.img payload map | kernel 0x1000-0x95a000, dtb 0x95a000-0x969000 | s1 s7 | YES | HIGH |
| dt.img structure | keyid32 plaintext + 0xE800 ciphertext | s1 s7 | YES | HIGH |
| firmware KeyID | ef8996bd…1492, constant across boot+recovery | s1 s7 | YES | HIGH |
| bootloader record vs KeyID | no KeyID bytes in any slice | s1 s7 | YES | HIGH |

## 7. continuity: the chain, traversed to its end

```text
AES                      -> AES-256-CBC                        [known]
mode                     -> CBC, not ECB                       [known]
IV                       -> 16 zero bytes                      [known]
window                   -> [0, 0xC000)                        [known]
key source               -> aml user key pkg, last 32 bytes    [known]
derivation               -> efuse -> key ladder -> BL31 unwrap   [STOPS HERE]
caller                   -> aml_bl2_enc_file / aml_file_aes    [known]
hardware/secure dep.     -> BL31/BL32 in 0x05100000+           [STOPS HERE]
```

and on the object side

```text
offset     -> candidate 0x20000                              [hypothesis]
header     -> format known, aquaman bytes unreadable         [partial]
uuid       -> 05d0e189-53dc-1347-8d2b-500a4b7a3e38          [known]
payload    -> unreadable                                    [stops here]
loader     -> BL2, lookup algorithm reconstructed           [partial]
decrypt    -> AES-256-CBC/IV=0                              [known]
destination-> 0x05100000                                    [known]
```

The only inaccessible link on both chains is the same one: a 32-byte secret
inside the secure world.

## 8. artifacts

```text
tools/round28_fip.py               parsers, crypto contract, census, probes
tools/round28_vendor_summ.py       per-function call/constant summary of
                                   aml_encrypt_gxl, reproduces the s5/s6 evidence
tools/fip_probe.sh                 rebuilds the reference FIP + ToC fixture
reports/round28-fip/ref5-toc.bin   256B ToC fixture, sha256 7c114a2e…
tools/run_tests.py                 TestRound28Fip, 9 tests
reports/round28-fip/01..08.md      per-section detail
```