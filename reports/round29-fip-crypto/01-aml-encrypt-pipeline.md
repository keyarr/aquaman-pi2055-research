# round29 / 01 — the `aml_encrypt_gxl` pipeline, reconstructed

Source: `.src/u-boot-khadas/fip/gxl/aml_encrypt_gxl`, ELF64 x86-64, static,
not stripped, `debug_info`, build stamp `aml_encrypt_gxl.c Apr 25 2017
13:51:05`, banner string `AMLOGIC-GXL-GXM-TXL-SIG-module : Ver-1.3`.
All addresses below are static VAs in that binary. No file was executed.

## entrypoint and CLI

`main` @0x41e74b builds a 30-entry `option` array on the stack (name
pointers 0x4e892e..0x4e89d7), copies 30 handler pointers from
`.data:0x4e8a00`, seeds `srandom(time(NULL))` (0x452580 — **rand() is the
key generator throughout**), then `getopt_long(argc, argv, optstring@
0x4e6ca1, longopts, &idx)` and dispatches `handlers[idx](argc, argv)`.

```text
idx  long option   handler              idx  long option   handler
 0   sigchk        aml_sig_check         15  mkcusid       aml_mk_customer_id
 1   rsacheck      aml_rsa_check         16  bl2sig        aml_bl2_sig
 2   rsagen        aml_rsa_gen           17  bl2enc        aml_bl2_enc
 3   keysig        aml_key_sig           18  bl2sig3       aml_bl2_sig_v3
 4   keybnd        aml_key_bnd           19  bl2enc3       aml_bl2_enc
 5   keysig3       aml_key_sig_v3        20  bl3enc        aml_bl3_enc
 6   keybnd3       aml_key_bnd_v3        21  bl3sig        aml_bl3_sig
 7   binsig        aml_bin_sig           22  bl3sig3       aml_bl3_sig_v3
 8   bootsig       aml_boot_sig          23  bootmk        aml_boot_make
 9   bootsig3      aml_boot_sig_v3       24  bootmk3       aml_boot_make_v3
10   imgsig        aml_img_sig           25  efsgen        aml_efuse_gen
11   mksd          aml_mk_sd             26  efsgen3       aml_efuse_gen_v3
12   sha           aml_sha               27  bin2hex       aml_bin2hex
13   upgsig        aml_upgrade_sig       28  efsproc       aml_efuse_process
14   mkpsd         aml_mk_password       29  help          aml_show_help
```

## the crypto kernel

`aml_file_aes(fp, len, key30, mode, rw)` @0x40159e:
stat → size, `len` must be 16-aligned, `mbedtls_aes_setkey_enc(ctx,
key_info[0:0x20], 0x100)`; in-place: `fseek(fp,0)`, loop
`fread(0x10000) → aes_crypt_cbc(MBEDTLS_AES_ENCRYPT, iv=key_info[0x20:0x30],
... ) → fseek → fwrite → fflush`; returns to caller.

`aml_file_duplicate(src, dst, ...)` @0x40d07f makes the working copy that
is encrypted in place (the tool never encrypts the user's input file).
`aml_file_boom(fp, filler, len)` @0x1d40 pads to alignment with a repeated
byte; `aml_file_copy(src, dst, n)` @0x4018dc; `aml_file_sha2(fp, buf,
fseek_to, len)` @0x40ce07.

## --bl2enc → aml_bl2_enc_file (the round-28 finding, re-verified)

`aml_bl2_enc` @0x418cdb (handler 17): 11-option getopt, then
`aml_bl2_enc_file(opts)` @0x40d2a6:

```text
require input[0] and keypackage[1] stat-able, output[2] optional
key_info[0x30] = bzero(0x30)
fopen(keypackage,"rb"), fseek END, size = ftell
fseek(size-0x20); fread(key_info, 0x20)          <- LAST 32 BYTES
fclose; require size in {0x20, 0x1B40}
dst = (output? output : sprintf("%s.encrypt", input))   [0x4e77a0]
aml_file_duplicate(input, dst, 0)                 <- never mutates input
fopen(dst,"r+b"); aml_file_aes(fp, 0xC000, ...)   <- window [0, 0xC000)
```

key = package tail 32B; `key_info[0x20:0x30]` stays zero → **IV = 0**.

## --bl3enc → aml_bl3_enc_file (per-object random key)

`aml_bl3_enc` @0x41b1a0 → `aml_bl3_enc_file(opts)` @0x40d57c:

```text
input stat; fopen; read 0x200 ctrl; aml_ctrl_blk_check(ctrl)   [0x4022ee]
keep a copy of ctrl[0:0x80]
key30 = bzero(0x30); fill key30[0:0x30] with rand()             [48 bytes]
if keypackage[1] given:
    fopen(keypackage), fseek END, require size in {0x20, 0x1B40}
    if size == 0x12348765-marked ctrl input: treat 0x200 header
    out = sprintf("%s.encrypt", input)                     [0x4e6a44/0x4e6a4d]
    aml_file_duplicate; copy size; then:
    out2 = sprintf("%s.enc", out)                          [0x4e6a57]
    copy 0x400 + size into out2
    fill 0x80 header: word0 = "LZ4C" (0x43345A4C), u16@+6 = 0x80,
        10 rand() bytes, timestamp sprintf("%04d%02d%02d%02d:%02d:%02d")
        [0x4e77b2], aml_file_sha2_gxl(input) into +0x10
    LZ4_compress_HC(file, size, dst, size+0x400, 12)
    sha2(header[0:0x60]); fwrite(header 0x80); fwrite(lz4)
    <- this is the "%s.lz4" path used with BL33_COMPRESS_FLAG
encrypt path (non-compress):
    size rounded up to 0x200 (aml_file_boom fills 0xFF)
    ctrl[+0x00..] rewritten: +0x40 = key30 (48B PLAINTEXT),
        +0x70 = size, +0x78 = size
    fseek 0; aml_file_aes(fp, size, key30)        <- IV = key30[0x20:0x30]
    aml_set_blk_time_stamp(0, ctrl)               <- +0x88 / +0xb0 fields
    aml_file_sha2(fp, ctrl+0x20, 0, size)
    fseek 0;  fwrite(ctrl 0x200)                  <- at +0x000
    fseek END; fwrite(ctrl 0x200)                 <- second copy at tail
result file = [ctrl 0x200 PLAINTEXT][ciphertext size][copy ctrl 0x200]
```

The 0x200 ctrl block (`aml_ctrl_blk_check`, 0x4022ee) is the container of
every per-object key in this toolchain: **key+IV live in plaintext at
ctrl+0x40 whenever the key is rand()-generated**.

## --bl2sig / --bl3sig

`aml_bl2_sig_file` @0x419d42 appends the RSA signature block; `--bl3sig`
(`aml_bl3_sig_file` @0x41b27b, file worker @0x41460a) wraps a payload as:

```text
[header 0x200 PLAINTEXT][payload intact][signature 0x200]
header: +0x00 0x12348765, +0x04 u32, +0x08 u64 load, +0x10 u64 rsv_start,
        +0x18 u64 rsv_size, +0x20 u64 secure_start, +0x28 u64 secure_size
```

Verified against the in-tree fixture: `.src/u-boot-khadas/fip/gxl/bl31.img`
(0x2C5A8) = header 0x200 (magic 0x12348765, +0x04=0x4E20, load 0x05100000,
rsv 0x05000000+0x300000, secure 0x05100000+0x200000) + `bl31.bin`
byte-identical + 0x200 tail. **The bl31.img "header" is plaintext and was
never inside the encrypted window of anything.**

## --bootmk → aml_boot_make (assembles the whole file)

`aml_boot_make` @0x41c9dd, options `bl2 bl30 bl31 bl32 bl33 bl3x output
userkey input level` (table 0x4e8640, 11 entries):

```text
out = fopen(remove(output) then fopen(output,"w+b"))
header buffer (0x4000, bzero): [0]=0xAA640001, [4]=0x12345678,
    [0xC00..0xC80] = 0xFF fill
entries[5] at header+0x10, stride 0x28: uuid word0..1 copied from
    .data table 0x716700 (bl2 0becf95f, bl30 3dfd6697, bl32 6d08d447,
    bl31 05d0e189); flags qword at entry+0x18
i==0 (bl2):  aml_file_copy(bl2file, out, 0xC000); fwrite(header 0x4000)
             <- BL2 occupies [0, 0xC000), header stored at 0xC000
i>0: fread 0x50 (0x12348765-marked input keeps the plaintext header);
     entry offset = running total (starts 0x4000);
     if RSA loaded: append signature blocks (sha2 + rsa_private over the
     ctrl block 0x200)
     aml_file_copy(file, out, size); total += size;
     pad to 0x4000 alignment with rand() bytes
after loop: fseek 0xC000; fwrite(header 0x4000)      <- header @0xC000
encrypt: if level/userkey set:
    key30 = rand()[0:0x30]; fill ctrl (0x200 bzero, AMLC @+0x0c/+0xfc,
    +0x02=+0x14=+0xfa=0x200) with sizes; ctrl+0x40 = key30
    fseek 0xC000; aml_file_aes(fp, 0x3E00, key30)   <- [0xC000, 0xFE00)
    aml_set_blk_time_stamp(0, ctrl); aml_file_sha2(fp, ctrl+0x20, 0xC000, 0x3E00)
    RSA: 0x0180 rand bytes -> rsa_private in 0x40-byte steps
    fseek 0xC000; fwrite(ctrl); fseek 0xFE00; fwrite(ctrl)  <- SECOND COPY
finally aml_uboot_process(out path...)                [0x40fcab]
```

So the v1.3 layout is: **BL2 [0,0xC000) encrypted under the userkey tail32
(only if a userkey was given), FIP header at 0xC000 encrypted
[0xC000,0xFE00) under a random key whose key+IV sit PLAINTEXT at ctrl+0x40,
payload streams from 0x10000, each with a plaintext ctrl header, second
ctrl copy at 0xFE00.**

## --bootmk3 → aml_boot_make_v3 @0x41d860

```text
header 0x4000: [0xC000]=0xAA640001, [0xC004]=0x00030001 (version 3)
entries[5] stride 0x28 at header+0x10; uuid table 0x716760 (two 16B
    uuids per slot = full GUID halves); entry.offset = i*0x468+0x188,
    entry.size = 0x468 constant
per-stream records: stride 0x468: +0x10 = 32B (sha2 of key),
    +0x14 = rand() key+IV 32B (when signing enabled),
    +0x1D0+0x14 = 0x40C bytes read from input, +0x490 = next read;
    aml_file_copy(file, out, size)
header fields baked at 0xC0C0..: 0x1100000, 0x10100000, 0x10000000,
    0x10100000/0x200000, 0x100000/0x5300000, 0x32000000, 0x32320000,
    0x3200/0x100, 0x1000000  (the AO/secure layout constants)
sha2 over header[0x10, 0x3FF0) -> stored at header+0x3FE0
if signing: rsa_pkcs1_sign (SHA256) over [0x3E00, 0x3E00+0x200-keylen)
if userkey: mbedtls_aes_setkey_enc(userkey[0:0x20], 0x100);
    aes_crypt_cbc(ENCRYPT, iv = userkey[0:0x10], header[0:0x4000])
fseek 0xC000; fwrite(header 0x4000)
```

The v3 header carries the same UUIDs but stores per-stream SHA2 records
(0x468-stride table) and the header itself is encrypted with the userkey
package bytes **[0:16] as IV and [0:0x20] as key** — a different contract
from v1 (v1 header key = package TAIL, IV = 0).

## --bootsig → aml_boot_sig_file @0x410fa2 (the Makefile's final step)

```text
paths: input+".sig", ".pkg", ".enc", ".dec", tmp
copy(input, sig, 0xC000)                      <- first 0xC000 to .sig
aml_bl2_sig_file(input, sig)                  <- re-sign BL2 block
aml_bl2_enc_file(input, keypackage, pkg)      <- encrypt [0,0xC000)
copy(pkg, enc, 0x4000)                        <- header block to .enc
for i in 0..9 (streams):
    aml_dec_bl3_file(enc, dec, 0x80)          <- decrypt stream ctrl
    aml_file_boom(dec, 0x4000)                <- align
    aml_bl3_enc_file(dec, keypackage, enc)    <- re-encrypt w/ userkey path
    aml_bl3_sig_file(dec, keypackage, enc)    <- re-sign
aml_boot_make_file(0x10 streams)              <- reassemble
cleanup: remove() every intermediate that exists
```

`--bootsig --aeskey enable` therefore re-wraps every stream with the
userkey package and re-assembles — the earlier `--bootmk` output is an
intermediate, not the final artifact. The final artifact's stream ctrl
blocks are userkey-wrapped, not plaintext-keyed.

## uboot tail

`aml_uboot_process` @0x40fcab (last call of bootmk/bootsig): works on the
first 0xC000 bytes only — reads them, `.tmp` copies, one `rand()`-driven
0x200 block, three further 0xC000 read/write passes with names built from
0x4e799d/0x4e79a8/0x4e79b3. BL2-local processing; it never touches the
payload region.

## answers pinned by this round

```text
entrypoint              main 0x41e74b, 30 subcommands, table 0x4e8a00
aes                     mbedtls aes_setkey_enc(key, 0x100) + aes_crypt_cbc
in-place                yes, always via aml_file_duplicate working copy
--bl2enc window         [0x0000, 0xC000) of the copy; IV = 0; key = pkg tail32
--bootmk assembly       BL2 [0,0xC000) + header@0xC000 + streams@0x10000..
--bootmk header enc     [0xC000,0xFE00), random key, key+IV plaintext @ctrl+0x40
--bootmk3 header enc    [0xC000,0x10000), key = pkg[0:0x20], IV = pkg[0:0x10]
--bl3enc object         [0x200, 0x200+size), key+IV plaintext @ctrl+0x40
per-object keys         rand(), seeded from time(NULL) — host-side random
bl31.img header         PLAINTEXT 0x200, never encrypted (fixture-proven)
```
