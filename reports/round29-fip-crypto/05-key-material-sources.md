# round29 / 05 — key material sources and the fixture oracle

## the search, as run

Structured search over the whole repo (respecting ignore rules), for:
`.key.pxp`, `aml-user-key.sig`, `userkey`, `key package`, `pxp`,
test vectors, sample FIPs, CI inputs. Results:

```text
32 fixtures   .src/u-boot-khadas/board/amlogic/<board>/aml-user-key.sig
              every board directory of the reference tree, 0x1B40 bytes
              each — REAL producer outputs of --keybnd, the exact file the
              Makefile passes to --bootsig/--imgsig/--efsgen.
0             *.key.pxp files (per-object random key exports) anywhere
0             sample FIPs, CI key inputs, test vectors beyond the above
1 vendor tool with keys inside: the three root RSA SHA-2 fingerprints at
              0x4064ce (read out in round 28, imported by round 29 code)
```

The 32 fixtures reduce to **one unique tail32**:

```text
02bc96a283e26fb38be4c0872a6e913dcbf7976192d3daabf7ba3b2ee7cae6ee
```

— the Amlogic reference AES key, shared by every reference board (gxb,
gxl, gxm, gxtvbb, axg, txl, txlx). Their rootkeymax/ukey blobs differ per
SoC family (three distinct whole-file SHA-256s), which independently
confirms the package layout: the per-family RSA blobs differ, the AES
tail does not.

## semantic role of every candidate

| candidate | source | reference | semantic role | used by aml_encrypt_gxl | exact length | final AES key? |
|---|---|---|---|---|---|---|
| reference tail32 | 32 aml-user-key.sig | keybnd output, Makefile input | build-time AES key of the REFERENCE boards | yes (tail32 contract) | 32 | YES for reference builds — oracle-negative for aquaman |
| fixture head32 | same | — | rootkeymax blob prefix, NOT a key | no | 32 | no |
| root RSA SHA-2 fingerprints x3 | 0x4064ce | efuse check | digests, not keys | compare-only | 32 | no (hashes) |
| all-zero 32B | no-userkey build path | bootmk/bootsig when userkey absent | degenerate key variant | yes | 32 | oracle-negative |
| all-ff 32B | n/a | historical negative | — | no | 32 | no |
| sha256("aml"/"amlogic"/etc) | round 28 | — | string guesses | no | 32 | no |

Every negative was tested against **both** candidate first-block sites —
`ct[0x0000:0x0010]` (BL2 window, the round-28 assumption) and
`ct[0xC000:0xC010]` (the bootmk header, where the ToC actually lives per
the reconstructed assembly) — with IV = 0, expected plaintext
`01 00 64 aa 78 56 34 12 00 00 00 00 00 00 00 00`. All negative. Pinned in
`TestRound29Crypto.test_fixtures_are_single_tailed_and_not_the_key` and
`test_no_public_key_reveals_the_toc` (round 28).

## the oracle

`tools/round29_crypto.py::check_key` — one AES-256 ECB block decryption
per call, `IV=0` composes it into the CBC first-block test. It is a
verifier for demonstrated candidates only, and its unit test proves it
returns True for a key with demonstrated provenance (round-trip) and
False otherwise. No brute force was run and none is possible: 2^256.

## what the OEM key would be, if present

The aquaman/`aml-user-key.sig` of the MiTV build is the one missing build
input. Its tail32 would be the AES-256 key of `[0, 0xC000)` (`--bl2enc`
stage) and, per the v3 contract, of the header at 0xC000 (key =
pkg[0:0x20] = tail32 for a 0x1B40 package... note the 0x1B40 package's
[0:0x20] is the rootkeymax blob's first 32 bytes — the v3 IV = pkg[0:16]
therefore also comes from the package, verbatim, no derivation).

Nothing in the repo or the vendor tree approximates it: the reference
tail32 is the only AES key material the family ever shipped publicly, and
it is demonstrably not this device's key.
