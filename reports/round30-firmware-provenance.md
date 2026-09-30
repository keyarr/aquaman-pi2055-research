# round30: firmware provenance — public material exhausted, trilha closed

date 2026-09-30. **zero device I/O this round** (no adb, no fastboot, no
mread; the round was pure public-provenance work plus one local AES oracle
run). inputs: the repo's own pinned artifacts, the vendor `aml_encrypt_gxl`
v1.3 ELF, the 32 vendor fixtures, and ONE newly-acquired public production
key package. detail in `reports/round30-provenance/01..06`.

## 0. answer block

```text
OFFLINE PROVENANCE CLOSED — round 30

exact PI.2055 bootloader found       NO   (the repo's local copy is the only
                                           one known to exist)
exact ciphertext match               NO   (no public candidate to compare)
matching build tree                  NO   (tadiphone aquaman tree dead live +
                                           Wayback 2026-08-13)
aquaman aml-user-key found           NO
same key reused by related board     NO   (superbird tested: oracle-NEGATIVE)
pipeline reproducible w/ public data YES  (full bootmk/bootsig chain executed
                                           offline with the public superbird
                                           package; stage-1 contract proven live)
remaining secret                     the 32-byte aeskey tail32 of the
                                     aquaman aml-user-key.sig build package

CRYPTOGRAPHICALLY CLOSED
```

## 1. the exact firmware (01)

The only public echo of the build tree (`dumps.tadiphone.dev/dumps/xiaomi/
aquaman`, referenced by @android_dumps for fingerprint
`Xiaomi/aquaman/aquaman:9/PI/2055:user/release-keys`) is **"No repository"**
— live today and in the 2026-08-13 Wayback snapshot. No OTA mirror, no
eMMC dump, no archive of `aquaman_9_PI_2055.zip` is reachable; the XDA
"seeking u-boot for aquaman" thread (2024) shows the community never got
it either. The nearest thing to a public tree remains the RAM-recovered
DTB/DTS in `artifacts/`. The local artifact set (boot/bootloader/dt/dtbo/
vbmeta, sha256-pinned in `firmware/SHA256SUMS.txt`, bootloader
`c7b8eea6…`, 0x148200) is the reference; nothing public exists to match
against it.

## 2. the public key sweep (03)

Across all public trees, exactly ONE non-reference production
`aml-user-key.sig` exists: the **superbird / Spotify Car Thing** package
(S905D2/g12a), published in `spsgsb/uboot` and sha256-pinned upstream by
the ThingLabsOSS recovery toolkit (`f48c731e…` — byte-confirmed this
round; local copy `artifacts/public-keys/superbird_aml-user-key.sig`).

Facts established, no assumptions carried:

```text
format   0x1B40, zero-run map IDENTICAL to the 32 vendor fixtures
         → same aml_key_bnd template, same RSA blob sizes; second
           independent production sample confirming the round-29 layout
key test superbird tail32 ab6541be…620c090d → ORACLE NEGATIVE on
         bootloader.img at both sites (ct[0x0000], ct[0xC000], IV=0,
         expected ToC block 010064aa78563412…)
scope    a g12a production key does NOT open an S905Y2 Xiaomi TV file;
         recorded per board pair, no extrapolation either way
```

No MiTV/Xiaomi/aquaman package, no aeskey file, no keybnd output ever
surfaced publicly. Rule-4/5 questions (sibling-board reuse, PI.998 →
PI.2055 rotation) are UNDETERMINABLE: not one sibling artifact exists
publicly (04).

## 3. the reproduction (05) — the round's technical core

Rule 8 executed literally: **known public key → encrypt known FIP →
compare expected structure.** The full Makefile chain (bl3enc ×4 → bl2sig
→ bootmk → bootsig `--amluserkey <superbird> --aeskey enable`) ran offline
with the vendor v1.3 tool. Results:

```text
package accepted end-to-end; tail32 consumed as the AES-256 key
oracle(enc[0:16], tail32) == pre-encrypt plaintext block 0  → TRUE
whole [0,0xC000) BL2 window decrypts under tail32/IV=0, except
    8 spans of re-signature data inserted pre-encryption
reproduced output: ZERO plaintext AMLC, ZERO repeated 16B blocks
    → re-proves on a real artifact why the at-rest record128 forces
      ONE common key across streams (and why per-stream rand() keys
      are excluded)
negative control: reference fixture tail32 does NOT decrypt it
```

With a known package, the pipeline is a transparent decryptor — the exact
procedure round 28 §5 documented is confirmed operational. The only open
tool question (v1.3 bootsig's header-wrapper rand-blob layout) does not
touch the key contract, which is proven directly on the ciphertext.

## 4. stopping rule applied (brief rule 10)

```text
exact firmware = unavailable (only the local device-side dumps)
aml-user-key   = absent from public
tail32         = unavailable
```

⇒ `CRYPTOGRAPHICALLY CLOSED`. No further round may attempt the 32 bytes.
Reopening condition: a **new concrete public artifact** — a second-build
aquaman bootloader.img (which would also answer key rotation), a published
Xiaomi/MiTV key package, or the OEM build tree. Hypotheses no longer count.

## 5. continuity table

| question | answer | evidence |
|---|---|---|
| producer of bootloader.img | aml_encrypt_gxl bootmk+bootsig composition | round 29, re-proven live (05) |
| stage-1 window/key/IV | [0,0xC000), pkg tail32, IV=0 | PROVEN live with public key (05) |
| package format | 0x1B40 = rootkeymax+ukey+tail32 | second production sample confirms (03) |
| public production keys | 1 (superbird), oracle-negative | measured (03) |
| aquaman package | absent from public | exhaustive sweep (01, 03) |
| build reuse across PI.998..2055 | UNKNOWN, undeterminable | no sibling artifacts (04) |
| reproduction with public data | YES | full chain executed (05) |
| closure | CRYPTOGRAPHICALLY CLOSED | stopping rule (06) |
