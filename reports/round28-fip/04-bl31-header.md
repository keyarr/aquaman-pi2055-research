# round28 s4: the bl31.img header

offline. round 27 established the field set from the family artifacts; this
round pins the **container position** of the header and the condition the
vendor tool uses to detect it.

## 1. header, family reference

`gxl/bl31.img`, 0x2C428 bytes, header at offset 0:

```text
+0x00 u32  0x12348765   magic
+0x04 u32  0x00004e20   constant in gxl and gxb; meaning not established
+0x08 u64  0x05100000   load address
+0x10 u64  0x05000000   reserved-memory start
+0x18 u64  0x00300000   reserved-memory size
+0x20 u64  0x05100000   secure-window start
+0x28 u64  0x00200000   secure-window size
+0x30..    zero
```

`+0x08` and `+0x10`/`+0x18` reproduce the live AO register values exactly
(`CFG5 = 0x05000000`, `CFG3 hi = 0x300000`), and `+0x20`/`+0x28` reproduce
the runtime fault boundary (`0x05100000`, 2 MiB). Round 27 closed that chain.

## 2. where the header lives

`fip_create` consumes `bl31.img` and stores **only** `bl31.bin` in the
package; `size=0x2C3A8` is `gxl/bl31.bin` (181160), not `bl31.img`
(181672). The 0x50 header is not kept as a separate payload. Where it goes
is the open question: gxlimg's `fip.c` copies it into the ToC data area,
which is the sentence round 27 quoted. This round did not locate the gxlimg
source, so that remains a single-source claim.

## 3. the detection rule, from the vendor tool

`aml_bl3_enc_file @0x40d57c`, first 0x200 bytes read and
`aml_ctrl_blk_check`ed, then:

```asm
cmp  eax, 0x12348765      ; the image's magic
jne  skip
mov  [off], 0x200         ; presence of the bl31.img header shifts the
                         ; encryption start to 0x200
```

So: **magic 0x12348765 present means the 0x200-byte control block is skipped
and encryption begins at 0x200.** That pins the header relative to the
control block, and it is consistent with `+0x04 = 0x4e20` being a header
sub-field rather than a container field.

## 4. aquaman exact

```text
bl31.img magic present in bootloader.img      NO (0x12348765 absent, s1 s3)
aquaman bl31 header bytes                     NOT RECOVERED
```

Nothing in the aquaman's at-rest image exposes this header. The field
*semantics* carry over as a strong hypothesis because the AO registers
(`CFG3/CFG4/CFG5`, read live in round 26 and decoded from the exact BL33 in
s1 of round 27) must be written by BL2 from *something*, and the bl31.img
header is the only structure in the family toolchain that carries exactly
those six numbers. But that is an inference, and it is recorded as one.

## 5. the exact-aquaman / family-reference boundary

```text
FAMILY REFERENCE   header layout, magic, the six field values, the 0x200 skip
                  rule. All byte-verified in .src/u-boot-khadas/fip/gxl.
AQUAMAN EXACT     nothing. The header is inside the encrypted region.
UNKNOWN           +0x04 meaning; entry point (no field carries one); whether
                  the aquaman's +0x04 equals 0x4e20.
```