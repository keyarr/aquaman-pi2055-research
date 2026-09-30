# round29: bootloader crypto closed out — pipeline reconstructed, package format solved

date 2026-09-30. **zero device I/O this round.** inputs: the bytes already
in the repo, the not-stripped vendor `aml_encrypt_gxl` ELF, and the 32
`aml-user-key.sig` fixtures that ship inside the vendor tree. tools
`tools/round29_crypto.py`; tests `TestRound29Crypto` (12 tests; suite total
106, pass). detail in `reports/round29-fip-crypto/01..07`.

## 0. answer block

```text
aml_encrypt_gxl produces bootloader.img directly = YES
    -- the --bootmk/--bootsig composition (Makefile:962-980). Not --bl2enc
       alone; not bare v1.3 --bootmk (3 pinned contradictions).
encryption scope =
    stage 1 --bl2enc:  [0x0000, 0xC000), AES-256-CBC, key=pkg tail32, IV=0
    stage 2 --bootmk:  header [0xC000,0xFE00) v1 / [0xC000,0x10000) v3 +
                       whole-object streams from 0x10000
    stage 3 --bootsig: BL2 re-encrypted under pkg tail32, stream ctrls
                       re-wrapped, reassembled
outer encryption stage = bootmk/bootsig envelope; the production variant
    encrypts object headers too (no plaintext anywhere at rest)
FIP plaintext recoverable offline = NO
user-key package format = SOLVED:
    0x1B40 = rootkeymax(0x1248) + ukey(0x8D8) + aeskey tail32(0x20)
    0x20   = bare AES key
    producer = aml_key_bnd --keybnd (build-time, host-side)
final AES key source = build-time aeskey file, copied VERBATIM into the
    package tail by aml_key_bnd; bound to the board afterwards via
    --efsgen (efuse fingerprint), not derived from it
final AES key present in repo = NO
    (32 fixtures all share the Amlogic reference tail32; all negative;
    all-zero no-userkey variant negative)
BL31 object boundary = 0x20000 + 0x2C000  (MEDIUM-HIGH: mechanism-backed)
BL31 payload ciphertext = inside stream 2 [0x20000, 0x4C000), uniform
BL31 header recoverable = NO offline; header CONTENT known from the
    family fixture (load 0x05100000, secure 0x05100000+0x200000,
    rsv 0x05000000+0x300000)
offline decrypt path = NO
blocking dependency = the 32-byte aeskey tail32 of the MiTV-AESP0 /
    aquaman PI.2055 aml-user-key.sig build package (a file the OEM build
    consumed and did not ship) + the production header-encryption variant
```

## 1. the pipeline (01)

`main` @0x41e74b: 30 `getopt_long` subcommands (table @0x4e8a00),
`srandom(time(NULL))`, dispatch. The crypto kernel is `aml_file_aes`
@0x40159e — mbedtls `aes_setkey_enc(key,0x100)` + `aes_crypt_cbc`,
in-place over a `aml_file_duplicate` working copy.

```text
--bl2enc   aml_bl2_enc_file 0x40d2a6   pkg size ∈ {0x20,0x1B40};
                                       key_info[0:0x20]=pkg TAIL 32B;
                                       IV stays zero; window [0,0xC000)
--bl3enc   aml_bl3_enc_file 0x40d57c   per-object rand() key+IV 48B
                                       stored PLAINTEXT at ctrl+0x40;
                                       encrypt [0x200, 0x200+size)
--bootmk   aml_boot_make    0x41c9dd   assembles the file: BL2 [0,0xC000)
                                       + header@0xC000 + streams@0x10000,
                                       rand padding to 0x4000;
                                       header [0xC000,0xFE00) rand-key
                                       encrypted; ctrl copies at 0xC000
                                       AND 0xFE00
--bootmk3  aml_boot_make_v3 0x41d860  header [0xC000,0x10000) encrypted
                                       key=pkg[0:0x20], IV=pkg[0:0x10];
                                       version word 0x00030001
--bootsig  aml_boot_sig_file 0x410fa2 re-signs BL2, re-encrypts [0,0xC000),
                                       re-wraps every stream ctrl, calls
                                       aml_boot_make_file, cleans temps
--keybnd   aml_key_bnd      0x40af24  PRODUCER of the user-key package
```

UUID table @0x716700 (v1) / 0x716760 (v3): TF-A UUIDs — BL2 `0becf95f…`,
BL30 `3dfd6697…`, BL32 `6d08d447…`, BL31 `05d0e189…` (as round 28),
plus BL33 `a7eed0d6…` (boot_sig_file comparators 0x4114f0..0x411524).

## 2. resolving the round-28 contradiction (03)

`[0,0xC000)` and `0x148200` were two stages of one composition, not one
operation. The Makefile shows the real sequence:

```text
blx_fix.sh bl2+acs+bl21 -> bl2_new.bin
--bl3enc/--bl3sig on bl30/bl31/bl32/bl33
--bl2sig bl2_new.bin -> bl2.n.bin.sig
--bootmk ... -> u-boot.bin
--efsgen --amluserkey board/aml-user-key.sig   (enrollment)
--bootsig --input u-boot.bin --amluserkey ... --aeskey enable
           -> u-boot.bin.encrypt     <- this is bootloader.img
```

Three measurable contradictions with the in-tree v1.3 (2017) outputs pin
the production build as the same family with header encryption folded in
(later version or the signing/`--aeskey enable` path):

```text
1. no plaintext ctrl copy at 0xFE00 (v1 bootmk would leave one)
2. no plaintext 0x12348765 object header anywhere (v1 objects carry one)
3. record128 identical in five streams requires ONE key across streams
   and deterministic content (v1 uses per-stream rand() keys)
```

`aml_uboot_process` @0x40fcab (final call of bootmk/bootsig) touches only
the first 0xC000 bytes — no additional payload stage exists.

## 3. the user-key package (02, 04)

```text
0x0000..0x1248   rootkeymax blob   "sig-rsa-key" from --keysig,
                                   padded UP to 0x1248 if smaller
0x1248..0x1B20   ukey blob         user RSA key (≤ 0x8D8)
0x1B20..0x1B40   aeskey tail32     LAST 32 BYTES OF THE BUILD-TIME AES
                                   KEY FILE, VERBATIM ("AES key file
                                   without IV, GX series used only")
```

The tail32 is **key material direct** — a build input copied into place
by `aml_key_bnd`. Not wrapped, not derived, not device/efuse-derived at
construction. Correction to round 28: the package is not "rooted in an
efuse-bound root key" at construction; the efuse enters via the
rootkeymax RSA fingerprints and the separate `--efsgen` enrollment.
Producers: `aml_key_bnd` only; the aeskey file comes from `--rsagen
--aes` or the OEM's own key generation.

## 4. fixtures and the oracle (05)

32 `aml-user-key.sig` fixtures (one per reference board), each 0x1B40,
**one unique tail32** `02bc96a2…e7cae6ee` (the Amlogic reference AES
key). The first-block oracle (one AES ECB block per call, IV=0) was
applied to every structurally-derived candidate against both candidate
sites — `ct[0x0000]` (BL2/ToC per round 28) and `ct[0xC000]` (the bootmk
header, where the ToC actually sits):

```text
NEGATIVE (pinned, do not repeat):
  reference tail32 (all 32 boards)
  reference head32 (not a key; formality)
  all-zero 32B (the no-userkey build variant)
  all-ff 32B
  root RSA SHA-2 fingerprints x3 (round 28)
  sha256 of aml/amlogic/fip/12345678/aml_encrypt_gxl (round 28)
```

`check_key` is a verifier, not a search; its own test proves the True
case (round-trip under a demonstrated key). No brute force run or
possible.

## 5. record128 (06)

Five identical 128-byte records at 0xC080/0x10080/0x20080/0x4C080/
0x8C080 — all ≡ 0x80 mod 0x10000 (stream+0x80). CBC requires identical
plaintext AND one common key+IV across all five streams. The window is
deterministic build metadata — the ctrl/timestamp area
(`aml_set_blk_time_stamp` writes ctrl+0x88/+0xb0, inside the observed
window). It is not parseable, not the KeyID, not a plaintext transport
header, and it leaks nothing without the key. The possibility of useful
plaintext metadata beside the ciphertext is **eliminated**.

## 6. FIP layout (04)

The round-28 reading B is now mechanism-backed:

```text
stream  base      size      content                   ends
  0     0x0C000   0x04000   FIP header (0xAA640001)   0x10000
  1     0x10000   0x10000   BL30                      0x20000
  2     0x20000   0x2C000   BL31                      0x4C000
  3     0x4C000   0x40000   BL32                      0x8C000
  4     0x8C000   0xBC200   BL33                      0x148200 = EOF
```

`0x8C000 + 0xBC200 = 0x148200` exactly. Stream order = bootmk getopt
order. BL31 boundary upgraded LOW-MEDIUM → MEDIUM-HIGH.

## 7. relation to boot/dt (10 of the brief)

Same toolchain, different branch: boot/recovery/dt use the AMLSECU!
per-object random-key scheme (`aml_bl3_enc_file`, host `rand()`, keys
exported to `.key.pxp` at packaging; plaintext KeyID in dt.img);
bootloader.img uses the bootmk/bootsig userkey scheme (no KeyID, no
per-object key identity — the key identity IS the OEM package). The KeyID
of dt/boot is irrelevant to bootloader.img, as round 28 already showed.

## 8. continuity: the chain to its end

```text
AES-256-CBC            known
IV                     0 (stage1) / pkg[0:16] (v3 header)
windows                [0,0xC000) + [0xC000,0xFE00|0x10000) + streams
key source             pkg tail32 — format KNOWN
package producer       aml_key_bnd — KNOWN
aeskey file producer   --rsagen --aes / OEM input — KNOWN SHAPE
the aeskey itself      OEM secret, absent from repo         [STOPS HERE]
efuse binding          --efsgen fingerprint + secure ladder [STOPS HERE]
```

The opaque link narrowed from "unknown secure-world derivation" to a
**32-byte file the OEM build consumed and did not ship**. Everything
between ciphertext and plaintext is specified to the byte; the only
missing element is the file itself, and the production build's header
variant (X1–X3 in 03) which does not change the key question.

## 9. final table

| field | value | confidence |
|---|---|---|
| producer of bootloader.img | aml_encrypt_gxl --bootmk + --bootsig composition | HIGH |
| stage-1 window/key/IV | [0,0xC000), pkg tail32, IV=0 | HIGH |
| header window | [0xC000,0xFE00) v1 / [0xC000,0x10000) v3 | HIGH (tool), variant at rest |
| package layout | 0x1248 + 0x8D8 + 0x20 | HIGH |
| tail32 semantics | direct build-time AES key material | HIGH |
| fixtures | 32 packages, 1 unique tail32, all negative | HIGH |
| stream map | 5 streams, table above, tail closes exactly | MEDIUM-HIGH |
| BL31 stream | [0x20000, 0x4C000) | MEDIUM-HIGH |
| plaintext anywhere in bootloader.img | none | HIGH |
| offline FIP reconstruction | NO | HIGH |
| blocking dependency | aquaman aml-user-key.sig (32B tail32) | HIGH |

## 10. closure

```text
OFFLINE PATH CLOSED — round 29
```

Not with "the key comes from the secure world" but with the sharper
statement the continuity rule asked for: the entire pipeline — parsing,
assembly, per-stage windows, IV contracts, package format, producer,
even the reference key material — is reconstructed and test-pinned; the
single missing element is a 32-byte build input that exists only inside
the OEM's build environment. The secure-world ladder (round 28) remains
the enforcement side; it is no longer the unknown.
