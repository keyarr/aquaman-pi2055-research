# round28 s6: key origin — where the chain stops being observable

offline. the key chain is reconstructed as far as static evidence goes, and
the exact point where it becomes unobservable is named.

## 1. host-side flow

```text
aml_encrypt_gxl --rsagen
      RSA-2048 root keypair  +  32-byte AES key
        -> "keymax"  (signed root-key package, 0x1b40 bytes accepted)

aml_encrypt_gxl --keybnd   (aml_key_bnd_v3)
      options: --input  --aeskey  --output  --N  --compress
      input  = signed keymax
      aeskey = the 32-byte AES key
      output = "aml user key" package

aml_encrypt_gxl --bootsig --input <FIP> --amluserkey <pkg> --output <out>
      aml_bl2_enc_file takes the LAST 0x20 bytes of <pkg> as the AES-256 key
```

So the AES-256 key that protects `[0, 0xC000)` is **the last 32 bytes of the
per-OEM user key package**. The RSA signature chain secures the package's
integrity; the AES key inside it is what actually encrypts the image.

Accepted package sizes are `0x20` (raw 32-byte key) and `0x1B40`
(keymax/key-bound form). `aml_create_key_info_from_file_x` additionally
accepts `0x1248` and `0x6A0` when parsing key files.

## 2. the accepted root keys are hardcoded in the tool

`aml_check_root_key_sha2_with_efuse @0x4064ce` builds three 32-byte
constants on the stack, byte by byte, and returns 0 on the first memcmp hit:

```text
02bc96a283e26fb38be4c0872a6e913dcbf7976192d3daabf7ba3b2ee7cae6ee
557eecbd90829f8ed64faf63eb3c3b558d72f0a5505863b8b6c2398c583945eb
33fbf3b3bc07c3c9b67d0fab0c52dfdea7b2c13005257087d10d33de6cf8debb
```

These are SHA-2 digests of the root keys the tool will accept. They are the
vendor's master-key fingerprints; an OEM key that does not chain to one of
them is rejected. They are **not** the AES key, but they are tried as
candidate keys in the test suite anyway (they are the only 32-byte constants
the binary actually contains), and they do not decrypt the ToC.

## 3. device-side flow

The function name `..._with_efuse` is the whole story for the tail of the
chain. On the device the verification and unwrap live in the secure world,
behind the boundary round 27 established:

```text
efuse / secure key ladder
   -> BL31 (or BL32) key-slot service
      -> SMC 0x82000060 SECURITY_KEY_QUERY   (round 14, in the exact BL33)
      -> SMC 0x82000061 SECURITY_KEY_READ    (round 14, in the exact BL33)
         -> returns to the NS world only handles/bases, never key bytes
            (round 14/15/17: no pointer or value crosses)
```

BL33 has exactly two key-related SMC sites and both are queries/reads of
handles. Round 18 established that the key material is not in the BL31
window in readable form and not in the DTB.

## 4. the exact stop line

```text
KNOWN (byte-verified)     AES-256-CBC, IV = 16 zero bytes
                          key = last 32 bytes of the aml user key package
                          window = [0, 0xC000)
                          three accepted root-key SHA-2 fingerprints
                          per-image keys are random and shipped out of band

UNOBSERVABLE FROM HERE   the aquaman's user key package
                          its derivation from an Amlogic root key
                          whether the root key matches one of the three
                          the efuse/ladder slot layout on this SKU
                          the unwrap code, which runs in BL31/BL32

WHY IT STOPS              the unwrap is in the secure world (0x05100000,
                          round 27: secure firewall, pre-BL33) and BL33 can
                          only ask for handles, not values.
```

## 5. what was tried and failed, so nobody retries it

With IV = 0 the first block is a perfect single-block oracle, so every
"maybe the key is public" hypothesis is cheap to test. Tried against the
known ToC plaintext prefix:

```text
the three hardcoded digests above
all-zero key, all-0xff key
sha256 of: aml, amlogic, Amlogic, aml_encrypt, gxlimg, amlogicboot,
           aml_encrypt_gxl, aml_rsa_key, fip, 0x12345678, 12345678,
           amlogic_gxl, secure_boot
result: no key yields 0xaa640001 at offset 0. Test-pinned as
       test_no_public_key_reveals_the_toc.
```

The AES key is not in any artifact in this repo and is not derivable from any
public constant in the vendor binary. Brute force is 2^256 with a 1-block
oracle per guess and is not attempted.

## 6. case classification

```text
CASE C.
  ciphertext available           YES, bootloader.img, 0x148200 bytes
  algorithm known                YES, AES-256-CBC, IV = 0, window [0, 0xC000)
  key derivation known           PARTIALLY: package layout and the accepted
                                 root-key fingerprints are known
  key material / derivation      EXCLUSIVELY SECURE: efuse -> key ladder ->
  exclusively secure             BL31/BL32 unwrap, none of it observable

No decryption path is invented. Nothing outside the secure world plus the
per-OEM key package can produce the plaintext FIP.
```