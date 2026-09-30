# round29 / 07 — summary and decision

Question of the round: *how much of `bootloader.img` can be reconstructed
offline without the secure-only secret?* — asked after round 28 closed
the crypto as CASE C but before the pipeline itself was fully
reconstructed.

## answer block

```text
aml_encrypt_gxl produces bootloader.img directly = YES
    -- the --bootmk/--bootsig composition (Makefile:962..980), NOT
    --bl2enc alone and not bare v1.3 --bootmk (three structural
    contradictions with the 2017 in-tree binary, pinned below)

encryption scope =
    stage 1 (--bl2enc):       [0x0000, 0xC000),  AES-256-CBC,
                              key = pkg tail32, IV = 0
    stage 2 (--bootmk):       header [0xC000, 0xFE00) v1 / [0xC000,
                              0x10000) v3; streams = whole objects
    stage 3 (--bootsig):      re-encrypts BL2 [0,0xC000) under pkg tail32
                              and re-wraps every stream ctrl

outer encryption stage = the bootmk/bootsig envelope; production variant
    encrypts object headers too (no plaintext survives anywhere)

FIP plaintext recoverable offline = NO
user-key package format = SOLVED
    0x1B40 = rootkeymax(0x1248) + ukey(0x8D8) + aeskey tail32(0x20)
    0x20   = bare AES key
    producer = aml_key_bnd --keybnd (build-time); consumers read the
    tail32 verbatim as the AES-256 key
final AES key source = build-time aeskey file, copied verbatim into the
    package by aml_key_bnd; bound to the board later by --efsgen
    enrollment (efuse fingerprint of the package)
final AES key present in repo = NO
    32 vendor aml-user-key.sig fixtures exist; all share ONE tail32
    (the Amlogic reference key) and ALL are oracle-negative. The
    no-userkey all-zero variant is also oracle-negative.
BL31 object boundary = 0x20000 + 0x2C000   (MEDIUM-HIGH, mechanism-backed:
    bootmk stream order + exact tail closure 0x8C000+0xBC200=0x148200)
BL31 payload ciphertext = inside stream 2, uniform
BL31 header recoverable = NO offline (the 0x12348765 header is plaintext
    in v1.3 objects, but the production envelope encrypts it; the header
    CONTENT is known from the family fixture: load 0x05100000,
    secure 0x05100000+0x200000, rsv 0x05000000+0x300000)
offline decrypt path = NO
blocking dependency = the 32-byte aeskey tail of the MiTV-AESP0/aquaman
    PI.2055 aml-user-key.sig package (or an equivalent 0x1B40 package)
```

## what changed since round 28

```text
1  pipeline fully reconstructed  main -> 30 subcommands; bootmk/bootsig/
   bootmk3/bl2enc/bl3enc/keybnd all read out of the vendor ELF. The
   "[0,0xC000) vs 0x148200" contradiction is resolved: they are two
   different stages of one composition.
2  package format SOLVED         not "last 32 bytes of a mysterious
   package" any more: rootkeymax + ukey + aeskey-tail, sizes pinned by
   the 0x20/0x1B40 consumer check and the 0x1248 rootkeymax pad in
   aml_key_bnd. The tail32 is build-input key material, verbatim.
3  producers found               aml_key_bnd (package), --rsagen --aes
   (aeskey file), Makefile inputs (board/aml-user-key.sig). No device
   step constructs it.
4  fixtures found and used       32 real packages; one unique tail32;
   first-block oracle applied; all negative (documented, pinned, not
   to be repeated).
5  record128 explained           deterministic metadata at stream+0x80
   encrypted under one common key across all five streams — eliminates
   any useful plaintext metadata alongside the ciphertext.
6  three contradictions pinned   v1.3 plaintext ctrl copy @0xFE00 absent;
   no plaintext 0x12348765 header; record128 incompatible with per-
   stream rand() keys. Production tool = same family, later version or
   signing path. These are the reasons the file cannot be decrypted
   with the v1.3 layout alone even WITH the reference key.
7  round-28 candidate boundary upgraded: the five streams are the bootmk
   streams; BL31 = stream 2 = [0x20000, 0x4C000).
```

## the chain, traversed to its end (continuity rule applied)

```text
AES-256-CBC            known
IV                     0 (stage 1) / pkg[0:16] (v3 header)
window(s)              [0,0xC000) + [0xC000,0xFE00|0x10000) + streams
key source             pkg tail32 — KNOWN FORMAT
key package producer   aml_key_bnd — KNOWN
aeskey file producer   --rsagen / OEM build input — KNOWN SHAPE
the aeskey itself      MiTV-AESP0 OEM secret — ABSENT FROM REPO   [STOP]
efuse binding          --efsgen fingerprint + secure-world ladder   [STOP]
```

The opaque link moved: it is no longer "unknown derivation inside the
secure world" — it is a **32-byte file the OEM build consumed and did
not ship**. Everything else between ciphertext and plaintext is now
specified to the byte.

## offline reconstruction ceiling

```text
can be reconstructed offline today
    the container layout (five streams, bases, sizes)      MEDIUM-HIGH
    the ToC format, UUIDs, entry layout                    HIGH
    the BL31 header content (from family fixture)          HIGH (not the
                                                           aquaman bytes)
    the BL2 object layout                                  HIGH
cannot be reconstructed offline
    any plaintext byte of bootloader.img                   —
```

## closure

```text
OFFLINE PATH CLOSED — round 29

blocking dependency (unchanged in kind, narrowed in form):
    32-byte secret = tail32 of the aquaman aml-user-key.sig build input
    (a file), plus the production build's header-encryption variant.
    Not brute-forceable, not in the repo, not derivable from anything
    shipped. The secure-world ladder remains the enforcement side.
```

The one legitimate acquisition that would reopen everything is a copy of
the OEM key package (from the OEM/build side — not from the device, which
remains out of scope). With it, the documented procedure (round 28 §5,
now with the corrected stage list) applies directly.
