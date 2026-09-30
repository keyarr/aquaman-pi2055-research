# round28 s2: FIP container format, recovered from the vendor toolchain

offline. the reference tree ships two not-stripped x86-64 binaries:

```text
.src/u-boot-khadas/fip/fip_create          ELF64 dynamic, not stripped
.src/u-boot-khadas/fip/gxl/aml_encrypt_gxl ELF64 static, debug_info, not stripped
```

`fip_create` was **run** on the family gxl artifacts to produce a reference
package and read its own `--dump` output. That is the ground truth for the
container; nothing about the aquaman is inferred from it. Reproduce with
`tools/fip_probe.sh`, fixture `reports/round28-fip/ref5-toc.bin`.

## 1. FIP ToC layout

```text
+0x00  u32  0xaa640001   ToC magic
+0x04  u32  0x12345678   version word, constant
+0x08  u64  0
entry[i] @ 0x10 + 0x28*i:
        u8  uuid[16]
        u64 offset_address
        u64 size
        u64 flags
terminator: uuid all zero, offset_address == end of image data
```

Entry stride is 0x28. Measured from `fip_create --dump` on a package built
from the family gxl artifacts (bl32/bl33 were random filler of fixed size so
the offsets are deterministic):

```text
entry[0] @0x0010 uuid=TOC  off=0x4000  size=0x95C0    -> BL2   payload
entry[1] @0x0038 uuid=BL2  off=0x10000 size=0x9784    -> BL30  payload
entry[2] @0x0060 uuid=BL30 off=0x1C000 size=0x2C3A8   -> BL31  payload
entry[3] @0x0088 uuid=BL31 off=0x4C000 size=0xC350    -> BL32  payload
entry[4] @0x00B0 uuid=BL32 off=0x5C000 size=0x11170   -> BL33  payload
entry[5] @0x00D8 uuid=NULL off=0x70000 size=0         -> end
```

`0x95C0` = gxl/bl2.bin, `0x9784` = gxl/bl30.bin, `0x2C3A8` = gxl/bl31.bin.
Payloads after BL2 are placed on 0x10000 boundaries; BL2 itself starts at
0x4000. Only `fip_create` stores `bl31.bin`, not `bl31.img`: the 0x50-byte
`bl31.img` header is folded into the ToC, which is what round 27 reported
from gxlimg.

## 2. the entry/payload uuid offset-by-one

Each entry carries the uuid of the **predecessor** component, and the
offset/size of its **successor** payload. Searching `UUID_X` therefore yields
the component that runs after X. Verified on the 5-component package above,
where every uuid and every size is independently accounted for.

## 3. UUID table

Lifted from `fip_create` `.data @0x6030a0` (`toc_entry_lookup_list`, 8 x
`{ptr, name, flags, pad}`):

```text
TOC    5ff9ec0b-4d22-3e4d-a544-c39d81c73f0a
BL2    9766fd3d-89be-e849-ae5d-78a140608213
BL301  ddccbbaa-cdabefef-abcd-12345678abcd
BL30   47d4086d-4cfe-9846-9b95-2950cbbd5a00
BL31   05d0e189-53dc-1347-8d2b-500a4b7a3e38
BL32   d6d0eea7-fcea-d54b-9782-9934f234b6e4
```

BL2/BL30/BL31/BL32 are the canonical TF-A `plat_amlogic` fip uuids. **BL31 =
`05d0e189-53dc-1347-8d2b-500a4b7a3e38`** is the identifier to look for once
the container is readable. It is absent from `bootloader.img` (s1 s3), which
is consistent with the ToC being inside the encrypted region.

## 4. Amlogic control block

`aml_ctrl_blk_check @0x4022ee`, reimplemented in
`round28_fip.check_ctrl_blk`:

```text
0x200 bytes
+0x02 u16 == 0x200     block size
+0x06 u16 <=  1        version
+0x0c u32 == 'AMLC'
+0x14 u32 == 0x200
+0xfa u16 == 0x200
+0xfc u32 == 'AMLC'
```

Both `aml_bl2_sig_file` and `aml_bl3_enc_file` read the first 0x200 bytes and
call this before doing anything else. The key is elsewhere in the file: the
128-byte record from s1 cannot be this block, because the block is 0x200
bytes and is per-image.

## 5. is `bootloader.img` a FIP in this format?

```text
expected: plaintext ToC at 0x0, plaintext BL2 at 0x4000, and per s5 an
          AES-CBC pass over [0, 0xC000) leaving everything above it readable
observed: chi2 = uniform over all 329 4 KiB blocks, no magic, no zero fill
verdict : bootloader.img is NOT a `fip_create` package that went through
          aml_bl2_enc_file alone. Either the whole image was encrypted in one
          pass, or the factory artifact is a different container entirely.
```

## 6. what the 128-byte record implies about boundaries

Under any 16-byte-block cipher a block is all-or-nothing, and CBC chains, so
the observation "bytes `[s-1]` differ, `[s, s+0x80)` agree, `[s+0x80]` differ"
at five sites constrains the object bases to two readings:

```text
reading A (CBC-consistent):  objects start AT the sites
    0xc080 0x10080 0x20080 0x4c080 0x8c080
    -> first 128 plaintext bytes of every object are identical, byte 0x80
       onwards differs. All five bases are 0x80 mod 0x10000.

reading B (ECB-consistent):  the record sits 0x80 into each object
    0xc000 0x10000 0x20000 0x4c000 0x8c000
    -> four of five bases are 0x10000-aligned and the first is exactly the
       end of the aml_bl2_enc_file window [0, 0xC000). Region sizes
       0x4000 / 0x10000 / 0x2C000 / 0x40000 / 0xBC200.
```

Reading B is preferred on structure (alignment, and `0xC000` matching the
encryption window end exactly), but s1 s5 shows the payloads are not ECB, so
B cannot be taken as established. Reading B also produces a plausible
partition, with the 0x2C000 region as the only one matching the family BL31
size (`gxl/bl31.bin` = 0x2C368, 176 KiB, 0.4% off). That is circumstantial:
the aquaman's own BL31 is a different binary.

```text
hypothesised boundaries   0xC000 0x10000 0x20000 0x4C000 0x8C000
hypothesised BL31 region  0x20000 .. 0x4C000   (0x2C000 = 180224 bytes)
confidence                LOW-MEDIUM. hypothesis, not measurement.
```