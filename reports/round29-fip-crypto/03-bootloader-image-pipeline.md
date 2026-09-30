# round29 / 03 — what `bootloader.img` is, and what it is not

## the contradiction, resolved

Round 28 carried two facts that did not fit together:

```text
aml_encrypt_gxl encrypts [0x0000, 0xC000)      (aml_bl2_enc_file)
bootloader.img = 0x148200 of uniform ciphertext everywhere
```

Both survive this round, but they describe **two different operations of
the same tool**, and neither of them alone produces this file:

```text
--bl2enc/--bl2enc3   encrypts ONLY [0, 0xC000) of a copy. Output would be
                     0xC000+ bytes with the rest plaintext. Not our file.
--bootmk (v1)        assembles the WHOLE file: BL2 [0,0xC000) + header at
                     0xC000 + payload streams from 0x10000. Encrypts
                     [0xC000, 0xFE00) with a RANDOM key, key+IV stored
                     PLAINTEXT at ctrl+0x40, ctrl written at 0xC000 AND
                     0xFE00.
--bootmk3            same assembly; header [0xC000,0x10000) encrypted with
                     the USERKEY (key = pkg[0:0x20], IV = pkg[0:0x10]);
                     version word 0x00030001.
--bootsig (final)    re-encrypts BL2 [0,0xC000) under the userkey tail32
                     and re-wraps every stream ctrl through
                     aml_bl3_enc_file, then re-assembles.
```

The Makefile pipeline (`.src/u-boot-khadas/Makefile:940-980`) is:

```text
bl2_new.bin = bl2 + acs + bl21 (blx_fix.sh)
--bl3enc --input bl30_new.bin            (or --bl3sig in V3)
--bl3enc --input bl31.$(BL3X_SUFFIX)
--bl3enc --input bl32 (optional)
--bl3enc --input bl33.bin (with optional LZ4)
--bl2sig --input bl2_new.bin --output bl2.n.bin.sig
--bootmk --output u-boot.bin --bl2 ... --bl30 ... --bl31 ... --bl33 ...
[CONFIG_AML_CRYPTO_UBOOT]
--efsgen --amluserkey board/aml-user-key.sig --output u-boot.bin.encrypt.efuse
--bootsig --input u-boot.bin --amluserkey board/aml-user-key.sig \
          --aeskey enable --output u-boot.bin.encrypt
```

So the answer to *is `bootloader.img` the direct output of
`aml_encrypt_gxl`?* is: **YES — of `--bootsig --aeskey enable`, the
composition, not of `--bl2enc` or of bare `--bootmk`** — with the caveat
that three structural details of the at-rest file do not match the
in-tree v1.3 binary exactly (below). The tool that made this file is this
family, but a build configuration (and likely tool version) whose exact
plaintext-header placement differs.

## three observable contradictions with the in-tree v1.3 outputs

```text
1. ctrl copy mismatch     v1 --bootmk writes the 0x200 ctrl at 0xC000 and
                          a copy at 0xFE00; the key+IV would sit PLAINTEXT
                          at ctrl+0x40. bootloader.img[0xC000:0xC200] !=
                          [0xFE00:0x10000] and no AMLC magic exists
                          anywhere in the file.  -> either the signing
                          (level=1 / --aeskey enable) path encrypted the
                          ctrl blocks too, or the production tool version
                          differs.
2. no plaintext header    every in-tree --bl3enc/--bl3sig object carries a
                          plaintext 0x200 ctrl / 0x12348765 header. The
                          five bootloader.img streams start at 0xC000 /
                          0x10000 / 0x20000 / 0x4C000 / 0x8C000 with no
                          plaintext anything.  -> the production pipeline
                          encrypts the object headers as well (an
                          aml_boot_sig_file with the headers inside the
                          encrypted envelope would look exactly like
                          this).
3. record128 survives     the identical 128-byte record at stream+0x80 in
                          all five streams REQUIRES identical first-128
                          plaintext AND identical key+IV per stream. v1.3
                          gives each --bl3enc stream an INDEPENDENT rand()
                          key.  -> the production pipeline either uses a
                          fixed per-build key for all five streams (the
                          userkey tail32), or the timestamp fields the
                          record covers were made deterministic.
```

The five streams at 0xC000 / 0x10000 / 0x20000 / 0x4C000 / 0x8C000 with
sizes 0x4000 / 0x10000 / 0x2C000 / 0x40000 / 0xBC200 now have a *mechanism*:
they are the **five --bootmk streams** (header + BL30 + BL31 + BL32 +
BL33) from the round-28 reading B, and the shared record is the ctrl/timestamp
field area at stream+0x80 (`aml_set_blk_time_stamp` writes ctrl+0x88 /
+0xb0 — inside the observed 128-byte window) under one common key.

## same family as boot/dt?

```text
boot/recovery/dt   AMLSECU! 0x0905 container; per-object RANDOM key+IV
                   exported to "<name>.key.pxp" at packaging time; objects
                   carry a PLAINTEXT 32B szSHA2KeyID prefix (dt.img) or
                   descriptor table (boot.img).
bootloader.img     gxl FIP family: NO KeyID anywhere, NO plaintext
                   headers, five streams, userkey-scheme.
verdict            same toolchain, DIFFERENT branch: the AMLSECU!
                   per-object random-key scheme (aml_bl3_enc_file, host
                   rand()) vs the bootmk/bootsig userkey scheme. The
                   bootloader does not carry per-object key identity
                   metadata because its key identity is the OEM package
                   itself.
```

## remaining explanations for the exact byte layout (open, LOW)

```text
X1  production aml_encrypt_gxl is a later version than the in-tree v1.3
    (2017) with ctrl/header encryption folded into bootmk.  MOST LIKELY.
X2  bootmk was run with signing (RSA key present, "level" set) which
    encrypts the ctrl copies.  CONSISTENT WITH X1.
X3  the file was produced by --bootsig --aeskey enable whose re-wrap
    covers everything; plaintext headers never survive that path.
    CONSISTENT WITH X1.
X4  a different vendor entirely (not excluded by anything measured, but
    the sizes, alignment and UUID scheme are all this family).
```

What is closed by measurement:

```text
aml_encrypt_gxl produces bootloader.img directly = YES (the --bootsig
    composition; not --bl2enc alone, not bare --bootmk v1.3)
encryption scope of the FIRST stage = [0, 0xC000) BL2 under userkey tail32
outer encryption stage = bootmk/bootsig header+streams; v3 header window
    [0xC000,0x10000) under pkg[0:0x20]/IV pkg[0:0x10]
plaintext ToC present = NO (would be at 0xC000, ciphertext there)
```
