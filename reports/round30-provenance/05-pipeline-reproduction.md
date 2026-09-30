# round30 / 05 — pipeline reproduction with public material only

Brief rule 8: "known key → encrypt known FIP → compare expected structure",
no device. The one public production package (superbird, sha256-pinned by
its own downstream project) was run through the ENTIRE vendor pipeline,
offline, on family artifacts. This is the first end-to-end execution of the
round-29 model with a demonstrated key.

## answer block

```text
pipeline reproducible with public data   YES
package -> tail32 -> AES key contract    PROVEN LIVE (block 0 + window)
stage-1 [0,0xC000) tail32 IV=0           CONFIRMED exactly as round 29 stated
"no plaintext anywhere at rest" variant  REPRODUCED (v1.3 --bootsig --aeskey enable
                                          itself emits zero plaintext AMLC/magic)
record128 constraint                     CONFIRMED IMPOSSIBLE for per-stream keys
                                          (reproduced output has 0 repeated 16B blocks)
plaintext BL31 recovery                  not needed, not attempted (per brief)
artifact                                 /tmp/round30-repro/u-boot.bin.encrypt
                                          sha256 54f630f184300dfe90e13c7bb45f50988df53e65fb7b3a0d08558716995a2e06
```

## the run (Makefile 962..980 path, v1.3 tool)

```text
inputs   .src/u-boot-khadas/fip/gxl/{bl2.bin,bl30.bin,bl31.img} + random
         bl32/bl33 filler (only layout matters); package =
         artifacts/public-keys/superbird_aml-user-key.sig (PUBLIC)
stage A  --bl3enc bl30/bl31.img/bl32/bl33   (per-object rand key)
stage B  --bl2sig bl2.bin -> bl2.n.bin.sig  (0xC000)
stage C  --bootmk -> u-boot.bin             (0x60000; ctrl@0xC000+0xFE00
                                             plaintext, AMLC@0xC00C/0xFE0C…)
stage D  --bootsig --amluserkey <superbird> --aeskey enable
         -> u-boot.bin.encrypt              (0x60200, delta +0x200)
```

Stage D succeeded with a REAL production 0x1B40 package — the consumer
contract (package accepted, tail32 consumed as AES key) is thereby
demonstrated end-to-end, exactly the rule-8 requirement.

## measured results

```text
1  oracle(enc[0:16], key=tail32, expected=pre[0:16])  = TRUE
    (IV=0 → block 0 = ECB block; the tail32 IS the stage-1 key)
2  tail32-CBC decrypt of enc[0,0xC000) == bl2.n.bin.sig content
    everywhere EXCEPT 148 blocks in 8 spans (0x10..0xF70) = the
    re-signature data bootsig inserts BEFORE encrypting.
    → the FULL [0,0xC000) window is re-encrypted under tail32/IV=0.
3  enc has NO plaintext ctrl copy: no AMLC anywhere (pre had 8);
    both ctrl copies (0xC000/0xFE00) are encrypted.
4  enc has ZERO repeated 16-byte blocks (pre/at-rest census method);
    the at-rest record128 (5 identical 128B records) cannot be produced
    by this per-stream-random-key composition — re-proving the round-29
    deduction that the production build encrypted ALL streams under ONE
    key (the tail32).
5  reference fixture tail32 does NOT decrypt the new artifact (negative
    control for the oracle run itself).
6  decrypted-header word0/word1 did not equal the bootmk constants under
    any tried rand-blob layout — the exact v1.3 bootsig header-wrapper
    (rand blob position/format) stays OPEN; it does not touch the key
    question because stage 1 is proven directly on block 0 + window.
```

## relation to the at-rest aquaman bootloader.img

```text
matches (now mechanism-PROVEN, was MEDIUM-HIGH):
    stage-1 window/key/IV contract
    "no plaintext anywhere at rest" production behaviour
    one-key-across-streams requirement (record128)
still differs (the production variant question, unchanged):
    at-rest stream encryption appears single-key (record128) vs this
    composition's per-stream rand keys; exact tool version/flag open.
    Irrelevant to the key question: in BOTH variants the key identity is
    the OEM package tail32.
```

## conclusion

Every element of the round-29 pipeline that can be tested without the
aquaman secret has now been executed with public material and behaved as
documented. The reproduction validates the tooling, the package format,
the key-consumption contract and the at-rest structure constraints — and
simultaneously demonstrates that with a KNOWN package the pipeline turns
into a straightforward decryptor (the new artifact's BL2 window was
decrypted transparently). The single missing input for the aquaman file
remains its own 0x1B40 package.
