# round30 / 06 — summary and decision

Question of the round: does the missing 32-byte aeskey (tail32 of the
MiTV-AESP0/aquaman PI.2055 `aml-user-key.sig`) exist in PUBLIC material —
via the exact firmware, its build tree, or any sibling key package?

## answer block (brief rule 9 fields)

```text
exact PI.2055 bootloader found          NO    (local copy is the only known one;
                                               no public mirror/dump/archive)
exact ciphertext match                  NO    (no public candidate exists to compare)
matching build tree                     NO    (tadiphone aquaman tree DEAD — "No
                                               repository" live AND in the 2026-08
                                               Wayback snapshot; nearest "tree" is
                                               the RAM-recovered DTB/DTS in this repo)
aquaman aml-user-key found              NO
same key reused by related board        NO    (superbird production package tested,
                                               oracle-negative — measured, not assumed)
pipeline reproducible with public data  YES   (full bootmk/bootsig chain run offline
                                               with the public superbird package;
                                               stage-1 contract proven live)
remaining secret                        the 32-byte aeskey tail32 of the
                                        aquaman build package — absent from
                                        every public source searched
```

## what this round added

```text
1  provenance closed  the exact OTA exists only as the local device-side
   dumps; the dump-tree that once held aquaman (tadiphone, PI.2055
   fingerprint posts on @android_dumps point at it) is dead live and in
   the archive; no mirror of bootloader.img exists anywhere public.
2  first REAL production package tested  superbird/Car Thing
   aml-user-key.sig (0x1B40, sha256 f48c731e…, pinned upstream by its own
   recovery toolkit): format-identical to the vendor fixtures (identical
   zero-run map → same aml_key_bnd template, same RSA blob sizes), and
   ORACLE-NEGATIVE against the aquaman ciphertext at both candidate sites.
   The last plausible public key candidate is eliminated by measurement.
3  pipeline executed end-to-end with a public key  stage A..D with the
   vendor v1.3 tool; the produced artifact's BL2 window decrypts
   cleanly under the package tail32 (IV=0) — the round-29 consumer
   contract is now demonstrated, not just read out of the binary. The
   reproduction also re-proves the three at-rest constraints (no
   plaintext AMLC, zero repeated blocks, per-stream keys incompatible
   with record128) on a REAL bootsig output.
4  build-reuse table  unfillable (no sibling artifacts public);
   recorded as UNKNOWN per the no-assumption rule.
```

## the chain, unchanged in substance, now double-checked

```text
AES-256-CBC / IV / windows / package format / producer  KNOWN+REPRODUCED
key package                                             PUBLIC samples exist (2 families)
the aquaman package (tail32)                            ABSENT — never shipped,
                                                        never leaked, tree dead
efuse binding                                           enforcement side only
```

## decision (brief rule 10 — stopping rule)

```text
exact firmware = unavailable (locally held only)
aml-user-key   = absent from public
tail32         = unavailable
```

```text
CRYPTOGRAPHICALLY CLOSED — round 30

The trilha is closed. No further round may attempt to guess/derive/
bruteforce the 32 bytes. Reopening requires a NEW CONCRETE PUBLIC
ARTIFACT — e.g. an aquaman bootloader.img from a second build (which
would also answer the reuse question), a published Xiaomi/MiTV key
package, or the OEM build tree — not another hypothesis.
```
