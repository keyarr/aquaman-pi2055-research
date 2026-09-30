# round28 s5: the decrypt pipeline, reconstructed from aml_encrypt_gxl

offline. this is the first round where the encryption is not inferred from
behaviour but read out of the vendor binary. `.src/u-boot-khadas/fip/gxl/aml_encrypt_gxl`
is a static ELF64, **not stripped**, with `debug_info`, and its strings are
stack-deobfuscated so they have to be read off the disassembly.

## 1. the primitive

```c
/* aml_file_aes @0x40159e, decompiled */
int aml_file_aes(FILE *fp, int len, key_info *ki, u8 enc)
{
    u8 buf[0x400];
    u8 key[0x28];                    /* 0x30-byte struct, 0x28 used */
    u8 *iv = ki + 0x20;
    ...
    memcpy(key, ki, 0x28);
    if (enc) aes_setkey_enc(&ctx, key, 0x100);   /* 0x100 = 256 */
    else     aes_setkey_dec(&ctx, key, 0x100);
    size = min(len, filesize - ftell(fp));
    if (size & 0xf) return 0;                  /* 16-byte alignment required */
    while (size) {
        n = fread(buf, 1, min(0x400, size), fp);
        if (!n) break;
        size -= n;
        aes_crypt_cbc(&ctx, iv, buf, buf, n, enc);   /* in place */
        fseek(fp, -n, SEEK_CUR);
        fwrite(buf, 1, n, fp);
    }
}
```

Hard facts, no interpretation:

```text
algorithm    AES-256-CBC   (mbedtls aes_crypt_cbc + aes_setkey_{enc,dec}, bits=0x100)
key          key_info[0x00:0x20]   32 bytes
iv           key_info[0x20:0x30]   16 bytes
block size   16, and the length must be a multiple of 16 or the call no-ops
direction    same call encrypts and decrypts, `enc` selects the key schedule
```

The key material is the *first* 32 bytes of the struct and the IV is the
next 16, which is why `aml_bl2_enc_file` gets the IV for free (see 2).

## 2. the bootloader pass: IV = zero

`aml_bl2_enc_file @0x40d2a6`:

```c
u8 ki[0x30] = {0};                            /* bzero */
ksz = size(keyfile);
if (ksz != 0x20 && ksz != 0x1B40) return;    /* accepted key-package sizes */
fseek(kf, ksz - 0x20, SEEK_SET);
fread(&ki, 1, 0x20, kf);                      /* key -> ki[0:0x20] */
fclose(kf);
sprintf(out, "%s.enc", input);
duplicate(input, out);
FILE *f = fopen(out, "rb+");                  /* position 0 */
aml_file_aes(f, 0xC000, &ki, 1);               /* encrypt [0, 0xC000) in place */
```

`ki[0x20:0x30]` is never written after the `bzero`, so:

```text
key = last 0x20 bytes of the key package
IV  = 16 * 0x00
window = [0x0000, 0xC000) of the image, encrypted in place
```

This is the single most useful fact of the round. **Because the IV is zero,
the first plaintext block is `AES_decrypt(C[0])` and nothing else**, so a
candidate key is checkable against one known 16-byte block: the FIP ToC
prefix `01 00 64 aa 78 56 34 12 00 00 00 00 00 00 00 00`. Implemented as
`round28_fip.cbc_decrypt_block0` and exercised in the test suite.

## 3. the per-image pass: random key per object

`aml_bl3_enc_file @0x40d57c` is a different path, used for standalone
binaries rather than the bootloader:

```c
u8 ki[0x30] = {0};
for (i = 0; i < 0x30; i++) ki[i] = rand();    /* 32B key + 16B IV, random */
write("%s.key.pxp", ki);                      /* exported in the clear */
```

The tool literally prints `AES key for PXP :` (immediate strings
`"AES key "` / `"for PXP "` / `": \n"` at `0x4086d2`). So per-image keys are
random per invocation and have to be shipped out of band. Whether the
aquaman's FIP uses this scheme or a shared key cannot be told without the
key material.

## 4. the `--bootsig` sequence

`aml_boot_sig_file @0x410fa2`, in order:

```text
1  aml_bl2_sig_file      sign BL2 (RSA, key package)
2  aml_bl2_enc_file      AES-256-CBC/IV=0 over [0, 0xC000)  -> "%s.enc"
3  aml_file_copy         0x4000 bytes                      (16 KiB granularity)
4  aml_dec_bl3_file      X -> "X.dec", swaps the first 0x200 header
5  aml_file_boom(dst, 0x4000, 0)   pad to a 16 KiB boundary
```

Step 5 explains s1's size observation: `bootloader.img` is 0x148200, not a
multiple of 0x4000, so it is **not** a `--bootsig` output.

## 5. what is NOT in the pipeline

```text
no key ladder, no keyslot table, no per-slot IV, no GCM/CTR anywhere
ctr_drbg_* and mbedtls are linked into the binary but aes_crypt_ctr /
aes_crypt_cfb128 / block_cipher_df are unreferenced by any of the enc paths
no SMC, no AMLSECU call, no hardware crypto engine: this is the host-side
  packaging tool, it never talks to the device
LZ4 (lz4.c, lz4hc.c, compiled into the tool) is available for payload
  compression but is not called from the enc paths examined
```

## 5b. who produces AMLSECU! and how it encrypts (delta, same round)

`"AMLSECU!"` exists in the tool at `.rodata 0x4e7c0b`, next to `"ANDROID!"`,
and both xrefs land **inside `aml_img_sig`** (`--imgsig`), not in any of the
FIP/BL paths:

```text
413b21  mov $0x4e7c0b,%esi    (inside aml_img_sig 0x41378c..0x41460a)
4141e9  mov $0x4e7c0b,%esi    (inside aml_img_sig)
```

`aml_img_sig` calls `aml_bl3_enc_file` (section 3: random key+IV exported to
`<name>.key.pxp`) and `aml_bl3_sig_file`, i.e.:

```text
--imgsig   = AMLSECU! container producer, AES-256-CBC with a RANDOM
             per-object key + random IV, shipped out of band in .key.pxp
--bootsig  = FIP producer path (section 2: fixed key, zero IV)
```

This closes the format provenance of `boot.img`/`recovery.img`/`dt.img`:
AMLSECU! 0x0905 images are the `--imgsig` product, and their encryption is
the same primitive (`aml_file_aes`, CBC) with a per-object random key.

Corroboration from the artifacts themselves (s1 s7 delta): `dt.img` and
`boot.img`'s dtb object wrap the same 59424-byte plaintext under two
independent encryptions (203/59424 ciphertext bytes coincide, chance level),
and `dt.img` carries a 32-byte plaintext `szSHA2KeyID` prefix. Both facts are
what a random-key CBC scheme predicts and hard to explain any other way.

No key file ships in the repo, so the kernel/ramdisk/dtb plaintexts stay
unreachable for the same reason as the FIP: the keys were exported at
packaging time into files (`*.key.pxp` / the OEM key package) that only the
firmware vendor holds.

## 6. summary

```text
algorithm         AES-256-CBC
key               32 bytes, from the key package
IV                16 zero bytes
block size        16, length must be 16-aligned
window (bootload) [0x0000, 0xC000) in place
window (per-image) from 0x200 when the bl31.img magic is present
mode              CBC, not ECB (and s1 s5 independently confirms it)
```