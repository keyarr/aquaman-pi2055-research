# round30 / 03 — public search for aml-user-key.sig / build key material

Question: does an `aml-user-key.sig` (or equivalent build key material)
exist publicly that could be the MiTV-AESP0 / aquaman PI.2055 package?

## answer block

```text
aquaman aml-user-key.sig public            NO
production (non-reference) packages public YES — ONE: superbird/Car Thing
superbird package sha256                   f48c731e064193c6584fe3785c193e6ec0ed51c892b5c20457641945cf906afc
superbird tail32 (last 0x20)               ab6541be131018f71fbc266f4643ff0d7626f9ab4ee2077ab7fd63dc620c090d
superbird head32                           05bc26eac626c4f6d0686ebdf045b92ca905ef0d625999a301a22a5fb60dfc5c
package size                               0x1B40 (full format: rootkeymax+ukey+aeskey tail)
ORACLE vs aquaman bootloader.img           NEGATIVE (both sites ct[0x0000] and ct[0xC000])
local copy persisted at                    artifacts/public-keys/superbird_aml-user-key.sig
```

## sources for `aml-user-key.sig` on public trees

| tree | board/SOC | what it is |
|---|---|---|
| spsgsb/uboot (branch buildroot-openlinux-201904-g12a and master) `board/amlogic/superbird_production/aml-user-key.sig` | S905D2 (g12a) | **real PRODUCTION key of the Spotify Car Thing**, leaked then published; the ThingLabsOSS/superbird-fip-tools setup.sh pins its sha256 (`f48c731e…`) as the expected value — byte-for-byte confirmed by this round's download |
| 32 vendor fixtures `.src/u-boot-khadas/board/amlogic/*/aml-user-key.sig` | gxl/axg reference boards | Amlogic REFERENCE key, one unique tail32 `02bc96a2…e7cae6ee`, all oracle-negative (round 29) |
| Amlogic-Lineage franklin.mk | g12a? reference path | points at `amlogic/g12a_u212_v1/aml-user-key.sig` — a reference-tree fixture, not a production package |
| hardkernel buildroot `aml_upgrade_pkg_gen.sh` | odroid boards | invokes the toolchain; odroidn2 uses its own package (g12b, not gxl-family, not public) |
| khadas forum thread (2022) | vim3 | instructions to GENERATE a package with rsagen — tooling, not a leaked key |

**Conclusion of the sweep:** across all public trees, exactly one
non-reference production package exists (superbird). No
`MiTV-AESP0`/aquaman/Xiaomi-TV package, no `keybnd` output, no aeskey file,
no `--rsagen --aes` artifact ever surfaced. The round-29 statement
("the aeskey exists only inside the OEM build environment") survives this
round's stronger search.

## structural comparison: superbird package vs the 32 reference fixtures

Both are 0x1B40 and produced by the same `aml_key_bnd` template:

```text
zero-run map (runs >= 16B) IDENTICAL between superbird and fixtures:
    (0x1250,0x1258) (0x1398,0x1498) (0x15F0,0x16F0) (0x17F4,0x18F4) (0x18F9,0x1980)
interpretation: same producer, same RSA blob sizes (ukey length equal);
only the key material differs. This pins the FORMAT exactly as round 29
derived it (rootkeymax 0x1248 + ukey 0x8D8 + aeskey tail 0x20) on a
second, independent production sample.
```

## what was NOT assumed (rule 4 of the brief)

The brief said: do not conclude "GXL key == aquaman key" without evidence.
Nothing was concluded — it was TESTED:

- oracle (one AES-256 ECB block per call, IV=0, round-29 `check_key`)
  applied to the superbird tail32 against the aquaman ciphertext first
  block at BOTH candidate sites (`ct[0x0000]` and `ct[0xC000]`), expecting
  the known ToC first block `010064aa 78563412 00000000 00000000`;
- result: **NEGATIVE on both sites**. The superbird production key does
  not decrypt the aquaman bootloader.img.

Per rule 4, this is recorded as an observed fact about these two boards
only. The also-tested superbird head32 is negative too (formality — head32
is not key material).

## classification

```text
same key reused by related board (superbird g12a == aquaman gxl-family):
    NO  — measured, oracle-negative
tail32 availability for aquaman: UNCHANGED — ABSENT from public material
```
