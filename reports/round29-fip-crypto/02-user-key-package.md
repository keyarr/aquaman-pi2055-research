# round29 / 02 — the `aml user key` package

## producers

One producer inside the vendor tool: **`aml_key_bnd` @0x40af24** (option
`--keybnd`), which writes *"keys package for secure boot"*:

```text
options: ukey file, rootkeymax file, aeskey file, level
validations:
  rootkeymax stat'able, aml_sig_key_check(rootkeymax)  [0x404a95]
  output name = "--output" or sprintf("%s-%s-%s.key", ukey, rootkeymax,
      hex(rnd[0]))                      [0x4e74b4 "%s-%s-%s.key"]
  output file opened "wb"
assembly:
  buf = bzero(0x2000)
  if rootkeymax given:
      n = fread(rootkeymax, 0x2000); if n <= 0x1247: n = 0x1248  <- PAD UP
  fwrite(buf, n)                        <- rootkeymax blob, 0x1248
  if ukey given:
      n = fread(ukey, 0x2000)
  fwrite(ukey, n)                       <- ukey blob, up to 0x8D8
  if rootkeymax given:
      /* re-open rootkeymax, fseek END, size-0x20, fread 0x20 */
      require rootkeymax size in {0x20, 0x1B40}
      <- the rootkeymax input can itself be a package; its TAIL 32B is
         carried forward
  fwrite(key30, 0x20)                   <- last write = 32 bytes
```

The final 32 bytes come from two sources depending on branch:

```text
branch A (no --ukey):  the last 0x20 of the rootkeymax file (which, if it
                       is a 0x1B40 package, is its aeskey tail32)
branch B (with ukey):  the last 0x20 of the AES key file
                       ("--rsagen ... aes : AES key file without IV,
                        GX series used only" — help text 0xe6ec1)
```

Total size check: 0x1248 + ukey + 0x20 = 0x1B40 ⇒ ukey blob = **0x8D8**.
Both consumers and `aml_key_bnd` itself accept exactly `0x20` (bare AES
key) or `0x1B40` (full package).

## format (full package, 0x1B40)

```text
[0x0000..0x1248)  rootkeymax blob  = "sig-rsa-key" from --keysig
                  (RSA keymax image, signatured by the root RSA key)
[0x1248..0x1B20)  ukey blob        = user RSA key (secure-boot ukey)
[0x1B20..0x1B40)  aeskey tail32    = LAST 32 BYTES OF THE BUILD-TIME
                                     AES KEY FILE, VERBATIM
```

No magic, no version field, no checksum over the whole package — the only
internal structure is the rootkeymax blob itself (which carries its own
AMLSECU-era RSA signature format). The 32-byte tail is **key material
direct** — a build-time input copied into place by `aml_key_bnd`, not a
wrapped key, not a derived key, not device- or efuse-derived at package
construction time. It is however *enrolled* later: `--efsgen`
(`aml_efuse_process`/`aml_efuse_gen` 0x418515/0x417d8a) computes the
package hash fingerprint burned into eFuse, which is what binds the
package to a board (`.pxp.efuse` string @0xe6cd9, `%s.key.pxp` @0xe6cb2).

## consumers of the tail32

```text
aml_bl2_enc_file  0x40d2a6  key_info[0:0x20] = tail32, IV = 0
aml_boot_make_v3  0x41d860  key = tail32 (wait: package[0:0x20]), IV = pkg[0:0x10]
aml_bl3_enc_file  0x40d57c  only when --amluserkey given: re-encrypt path
aml_boot_sig_file 0x410fa2  same, via bl3_enc on each stream
```

Correction to the round-28 statement *"rooted in an efuse-bound root
key"*: at **package construction** the AES tail32 is an ordinary build
input. The eFuse binding enters through the rootkeymax blob (RSA root
key, whose SHA-2 fingerprints are hardcoded at 0x4064ce) and through the
`--efsgen` enrollment step — the host-side AES tail itself is only ever
compared/used as raw bytes. The secure world independently holds its own
key ladder; the host AES key and the efuse ladder are two legs of the
same secure-boot design that must be equal for boot to succeed, but the
package file itself is plain build material.

## the OEM key for this device

```text
provenance of bootloader.img's AES key = last 32B of the MiTV-AESP0 /
aquaman PI.2055 build's aml-user-key.sig / aeskey input
present in repo = NO (see 05)
fixture set = 32 board aml-user-key.sig files in the vendor tree, all
              0x1B40, sharing ONE tail32 (02bc96a2…e7cae6ee) — the
              Amlogic reference key. This is the demonstration that the
              tail32 is the operative AES secret.
```
