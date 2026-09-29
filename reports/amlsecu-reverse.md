# amlsecu-reverse — AMLSECU pipeline in U-Boot (public sources)

firmware: aquaman PI.2055. container: `AMLSECU!` ver `0x0905`, nblk=3.
no command was executed on the device. everything below is offline
analysis of local dumps + cited public sources.

## 1. exact source of the parser

the AMLSECU parser is standard Amlogic code, identical across several trees:

* `common/cmd_imgread.c` (khadas/u-boot, master branch):
  https://github.com/khadas/u-boot/blob/69eb192a445cd1d485954175a18b46b152bd7abd/common/cmd_imgread.c
* `cmd/amlogic/imgread.c` (nest-open-source manifest_repos/u-boot):
  https://nest-open-source.googlesource.com/manifest_repos/u-boot/+/06419a4bae2adcdd0ed4e73f93f3f40a82172e45/cmd/amlogic/imgread.c
* `platform/external/u-boot`, branch `android-tv-s-beta3`, same file.
* history: around since at least 2013 (`cmd_imgread.c` version 1.0.0,
  author Sam.Wu) and the Android 9 variant (`is_andr_9_image`,
  `AmlSecureBootImg9Header`) shows up in the tv-9/tv-s trees.

structs (copied verbatim from khadas/u-boot):

```c
typedef struct __aml_enc_blk{
        unsigned int  nOffset;
        unsigned int  nRawLength;
        unsigned int  nSigLength;
        unsigned int  nAlignment;
        unsigned int  nTotalLength;
        unsigned char szPad[12];
        unsigned char szSHA2IMG[32];
        unsigned char szSHA2KeyID[32];
}t_aml_enc_blk;

#define AML_SECU_BOOT_IMG_HDR_MAGIC        "AMLSECU!"
#define AML_SECU_BOOT_IMG_HDR_VESRION      (0x0905)

typedef struct {
        unsigned char magic[8];
        unsigned int  version;
        unsigned int  nBlkCnt;
        unsigned char szTimeStamp[16];
        t_aml_enc_blk   amlKernel;
        t_aml_enc_blk   amlRamdisk;
        t_aml_enc_blk   amlDTB;
}AmlEncryptBootImgInfo;

// pre-Android 9
typedef struct _boot_img_hdr_secure_boot {
    unsigned char           reserve4ImgHdr[1024];
    AmlEncryptBootImgInfo   encrypteImgInfo;
}AmlSecureBootImgHeader;
// Android 9: reserve4ImgHdr[2048], header at +0x800
```

## 2. call chain (normal boot, eMMC)

`imgread kernel <part> <loadaddr>` (`do_image_read_kernel`):

1. `store_read_ops(part, loadaddr, 0, IMG_PRELOAD_SZ)` (1 MiB).
2. `genimg_get_format` must be `IMAGE_FORMAT_ANDROID`.
3. `_aml_get_secure_boot_kernel_size(loadaddr, &secureKernelImgSz)`:
   * Android 9: `secureKernelImgSz = 4096`,
     `info = pAndHead + 2048` (half). that's exactly where the magic
     shows up in boot.img (file offset `0x800`).
   * pre-9: header at +1024, base 2048.
   * `memcmp` of the magic. no magic: returns 0 (plaintext image) if
     `!isSecure`, error if `isSecure`.
   * with magic: requires `isSecure`, requires version `0x0905`,
     adds `secureKernelImgSz += nTotalLength` per block (nBlkCnt times).
4. reads the rest (`actualBootImgSz - IMG_PRELOAD_SZ`), `flush_cache`.
5. the decrypt/verify itself is NOT here. it happens later, in `bootm` /
   `do_image_read_dtb`, via SMC (section 3).

`imgread dtb` reads second (`lflashReadOff = page + ALIGN(kernel) +
ALIGN(ramdisk)`, `nFlashLoadLen = ALIGN(second)`), then calls:

```c
flush_cache(dtImgAddr, nFlashLoadLen);
nReturn = aml_sec_boot_check(AML_D_P_IMG_DECRYPT,
    (unsigned long)loadaddr, GXB_IMG_SIZE, GXB_IMG_DEC_DTB);
```

and only then does `fdt_check_header` + `memmove`. i.e.: the DTB is only
readable after decrypt in the secure world.

## 3. the decrypt is an SMC into the secure world

`aml_sec_boot_check(nType, pBuffer, nLength, nOption)`
(`arch/arm/cpu/armv8/*/bl31_apis.c`, e.g. gxtvbb/axg/g12a) is just an
SMC wrapper:

```c
x0 = AML_DATA_PROCESS; x1 = nType; x2 = pBuffer; x3 = nLength; x4 = nOption;
asm volatile("smc #0");
flush_dcache_range(pBuffer, pBuffer + nLength);
```

types seen in code: `AML_D_P_IMG_DECRYPT`,
`AML_D_P_IMG_DECRYPT_V3`, `AML_D_P_EXT_IMG_DECRYPT_V3`,
`AML_D_Q_IMG_SIG_HDR_SIZE`, options `GXB_IMG_DEC_ALL`, `GXB_IMG_DEC_DTB`,
`GXB_IMG_SIZE`, `GXB_IMG_LOAD_ADDR`, `GXB_EFUSE_PATTERN_SIZE`.

consequence: the normal-world U-Boot never handles the key. it passes
pointer+size+type and the BL31/BL32 (closed) does verify+decrypt
in-place with DMA (hence the `flush_cache` before). PHASE 5 classification:
option C (TEE runs the whole decrypt), with D as the mechanism
(DMA/hw crypto unlocked by the secure world). A and B (key in plaintext in
normal world) have no support in the code.
`is_secure_boot_enabled()` (khadas): `readl(AO_SEC_SD_CFG10) & (1<<4)`.
on newer trees: `IS_FEAT_BOOT_VERIFY()` = OTP license bits
(`FEAT_ENABLE_DEVICE_SCS_SIG_0/1`). either way the root is eFuse/OTP,
not an environment variable.

## 4. packing (PC side, closed)

public scripts that invoke the packer (hardkernel/buildroot
`aml_upgrade_pkg_gen.sh`, onethingcloud-oes-linux, LibreELEC
`amlogic-boot-fip/gxl.inc`):

```bash
aml_encrypt_<soc> --imgsig --amluserkey aml-user-key.sig \
  --input boot.img --output boot.img.encrypt
aml_encrypt_<soc> --bootsig --amluserkey aml-user-key.sig \
  --aeskey enable --input u-boot.bin --output u-boot.bin.encrypt
aml_encrypt_<soc> --efsgen --amluserkey aml-user-key.sig \
  --output u-boot.bin.encrypt.efuse   # SECURE_BOOT_SET, efuse default
```

`--imgsig` is the operation that produces the `AMLSECU!` container
(kernel/ramdisk/dtb). no open-source equivalent exists: `gxlimg` (repk),
`meson-tools` (afaerber) and `meson64-tools` (angerman) cover FIP/BL2/BL3x
(`bl2sig`, `bl3enc`, `bootmk`), never `--imgsig`. confirmed gap.

## 5. status per hypothesis

* size/parser path in U-Boot: CONFIRMED (source + dumps agree).
* decrypt via SMC in secure world, key outside normal world: STRONG
  EVIDENCE (SMC wrapper is public; BL31 is closed).
* exact payload algorithm: NOT PROVEN (AES is inference, see
  amlsecu-key-path.md).
* offline repacking: REFUTED with what's public
  (missing `aml_encrypt --imgsig` + `aml-user-key.sig`).
