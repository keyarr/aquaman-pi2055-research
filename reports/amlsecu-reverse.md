# amlsecu-reverse — pipeline AMLSECU no U-Boot (fontes publicas)

firmware: aquaman PI.2055. container: `AMLSECU!` ver `0x0905`, nblk=3.
nenhum comando foi executado no aparelho. tudo abaixo e analise offline
de dumps locais + fontes publicas citadas por URL.

## 1. fonte exata do parser

o parser AMLSECU e codigo Amlogic padrao, identico em varias arvores:

* `common/cmd_imgread.c` (khadas/u-boot,branch master):
  https://github.com/khadas/u-boot/blob/69eb192a445cd1d485954175a18b46b152bd7abd/common/cmd_imgread.c
* `cmd/amlogic/imgread.c` (nest-open-source manifest_repos/u-boot):
  https://nest-open-source.googlesource.com/manifest_repos/u-boot/+/06419a4bae2adcdd0ed4e73f93f3f40a82172e45/cmd/amlogic/imgread.c
* `platform/external/u-boot`, branch `android-tv-s-beta3`, mesmo arquivo.
* historico: existe desde pelo menos 2013 (`cmd_imgread.c` versao 1.0.0,
  autor Sam.Wu) e a variante Android 9 (`is_andr_9_image`,
  `AmlSecureBootImg9Header`) aparece nas arvores tv-9/tv-s.

structs (copiadas verbatim do khadas/u-boot):

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
// Android 9: reserve4ImgHdr[2048], header em +0x800
```

## 2. cadeia de chamadas (boot normal, eMMC)

`imgread kernel <part> <loadaddr>` (`do_image_read_kernel`):

1. `store_read_ops(part, loadaddr, 0, IMG_PRELOAD_SZ)` (1 MiB).
2. `genimg_get_format` tem que ser `IMAGE_FORMAT_ANDROID`.
3. `_aml_get_secure_boot_kernel_size(loadaddr, &secureKernelImgSz)`:
   * Android 9: `secureKernelImgSz = 4096`,
     `info = pAndHead + 2048` (metade). e exatamente onde o magic
     aparece no boot.img (offset de arquivo `0x800`).
   * pre-9: header em +1024, base 2048.
   * `memcmp` do magic. sem magic: retorna 0 (imagem plaintext) se
     `!isSecure`, erro se `isSecure`.
   * com magic: exige `isSecure`, exige version `0x0905`,
     soma `secureKernelImgSz += nTotalLength` por bloco (nBlkCnt vezes).
4. le o resto (`actualBootImgSz - IMG_PRELOAD_SZ`), `flush_cache`.
5. o decrypt/verify em si NAO esta aqui. acontece depois, no `bootm` /
   `do_image_read_dtb`, via SMC (secao 3).

`imgread dtb` le o second (`lflashReadOff = page + ALIGN(kernel) +
ALIGN(ramdisk)`, `nFlashLoadLen = ALIGN(second)`), depois chama:

```c
flush_cache(dtImgAddr, nFlashLoadLen);
nReturn = aml_sec_boot_check(AML_D_P_IMG_DECRYPT,
    (unsigned long)loadaddr, GXB_IMG_SIZE, GXB_IMG_DEC_DTB);
```

e so depois faz `fdt_check_header` + `memmove`. ou seja: o DTB so e
legivel depois do decrypt no secure world.

## 3. o decrypt e SMC para o secure world

`aml_sec_boot_check(nType, pBuffer, nLength, nOption)`
(`arch/arm/cpu/armv8/*/bl31_apis.c`, ex. gxtvbb/axg/g12a) e so um
wrapper de SMC:

```c
x0 = AML_DATA_PROCESS; x1 = nType; x2 = pBuffer; x3 = nLength; x4 = nOption;
asm volatile("smc #0");
flush_dcache_range(pBuffer, pBuffer + nLength);
```

tipos observados no codigo: `AML_D_P_IMG_DECRYPT`,
`AML_D_P_IMG_DECRYPT_V3`, `AML_D_P_EXT_IMG_DECRYPT_V3`,
`AML_D_Q_IMG_SIG_HDR_SIZE`, opcoes `GXB_IMG_DEC_ALL`, `GXB_IMG_DEC_DTB`,
`GXB_IMG_SIZE`, `GXB_IMG_LOAD_ADDR`, `GXB_EFUSE_PATTERN_SIZE`.

consequencia: o U-Boot normal world nunca manipula a key. ele passa
ponteiro+tamanho+tipo e o BL31/BL32 (fechado) faz verify+decrypt
in-place com DMA (por isso o `flush_cache` antes). classificacao FASE 5:
opcao C (TEE executa o decrypt inteiro), com D como mecanismo
(DMA/hw crypto liberado pelo secure world). A e B (key em plaintext no
normal world) nao tem suporte no codigo.

`is_secure_boot_enabled()` (khadas): `readl(AO_SEC_SD_CFG10) & (1<<4)`.
nas arvores novas: `IS_FEAT_BOOT_VERIFY()` = bits de licenca OTP
(`FEAT_ENABLE_DEVICE_SCS_SIG_0/1`). em ambos os casos a raiz e eFuse/OTP,
nao variavel de ambiente.

## 4. empacotamento (lado PC, fechado)

scripts publicos que invocam o packer (hardkernel/buildroot
`aml_upgrade_pkg_gen.sh`, onethingcloud-oes-linux, LibreELEC
`amlogic-boot-fip/gxl.inc`):

```bash
aml_encrypt_<soc> --imgsig --amluserkey aml-user-key.sig \
  --input boot.img --output boot.img.encrypt
aml_encrypt_<soc> --bootsig --amluserkey aml-user-key.sig \
  --aeskey enable --input u-boot.bin --output u-boot.bin.encrypt
aml_encrypt_<soc> --efsgen --amluserkey aml-user-key.sig \
  --output u-boot.bin.encrypt.efuse   # SECURE_BOOT_SET, padrao de efuse
```

`--imgsig` e a operacao que gera o container `AMLSECU!` (kernel/ramdisk/
dtb). nao existe equivalente open source: `gxlimg` (repk), `meson-tools`
(afaerber) e `meson64-tools` (angerman) cobrem FIP/BL2/BL3x (`bl2sig`,
`bl3enc`, `bootmk`), nunca `--imgsig`. lacuna confirmada.

## 5. status por hipotese

* parser/size path no U-Boot: CONFIRMADO (fonte + dumps batem).
* decrypt via SMC no secure world, key fora do normal world: FORTE
  EVIDENCIA (wrapper SMC e publico; BL31 e fechado).
* algoritmo exato do payload: NAO PROVADO (AES e inferencia, ver
  amlsecu-key-path.md).
* reempacotamento offline: REFUTADO com o que e publico
  (falta `aml_encrypt --imgsig` + `aml-user-key.sig`).
