# amlsecu-public-implementations — quem usa o mesmo formato

## 0x0905 e familia comum Amlogic (CONFIRMADO)

o trio magic `AMLSECU!` + `0x0905` + `t_aml_enc_blk` e byte-identico em:

* khadas/u-boot `common/cmd_imgread.c` (VIM, GXL/GXM).
* nest-open-source manifest_repos/u-boot `cmd/amlogic/imgread.c`.
* AOSP `platform/external/u-boot` branches android-tv-9 / tv-s-beta3
  (`common/cmd_imgread.c` + `AmlSecureBootImg9Header` com reserve 2048).
* CoreELEC bl301 (commits PD#132936, PD#137972: dtb passa a ser cifrado
  junto, `imgread dtb` com decrypt).

ou seja: `0x0905` nao e custom Xiaomi. e o versionamento padrao Amlogic
da era Android 9, compartilhado por GXB/GXL/GXM e derivados (S805Y e
GXL). a presenca no aquaman nao indica fork.

## produtos com o mesmo problema

* Mi Box 3 / 3S (MDZ-19-AA, S905X-H): Magisk issue #2555 (2020).
  ramdisk cifrado, `bad cpio header`, AIK nao reconhece. topjohnwu
  fechou como sem suporte: sem a key nao ha decrypt. mesma conclusao
  deste relatorio, 6 anos antes, outro SoC da mesma familia.
* AIK (osm0sis) documenta: "Xiaomi Mi Box 3S, ZTE B860H STB — special
  image signing adds AMLSECU! ... ramdisk cannot be unpacked or
  modified".
* Antminer S19 XP (Bitmain, controle Amlogic): parser open source
  HashSource/BMU (fork de AnatolyGeorgievski/BMU) le o mesmo header
  (`version 905`, blocos com data offset / raw length / total length)
  e salva kernel/ramdisk/second. util como segunda implementacao do
  parser, mas nao faz decrypt (as keys `key1/key2` ali sao do esquema
  Bitmain, nao Amlogic).
* Yandex Station / Quasar (Amlogic): relatos de `boot.img.encrypt` /
  `dtb.img.encrypt` com `AMLSECU!` visivel no dump. mesmo esquema.

## tooling: o que existe e o que falta

| ferramenta | cobre | serve p/ aquaman? |
|---|---|---|
| `aml_encrypt_gx* --bootsig/--efsgen` (binario Amlogic, precisa `aml-user-key.sig`) | FIP + efuse pattern | so com a key da Xiaomi |
| `aml_encrypt_gx* --imgsig` (idem) | container AMLSECU! | idem — peca que falta |
| `gxlimg` (repk, open) | bl2/bl3x/fip sem key (GXL) | nao faz imgsig |
| `meson-tools amlbootsig/amlinfo` (afaerber) | FIP unsigned/sha256 | nao faz imgsig |
| `meson64-tools` (angerman) | G12B/G12A/SM1 | nao faz imgsig |
| BMU `bmu_parser` (HashSource) | parse do header 905 | parse ok, decrypt nao |
| `tools/parse_amlsecu.py` (este repo) | parse do header 905 | parse ok, decrypt nao |

`amlogic-boot-fip` (LibreELEC) distribui os binarios `aml_encrypt_gxl`
etc., mas sem nenhuma `aml-user-key.sig` (cada vendor guarda a sua).
ter o binario nao adianta sem a key.

## TEE (resumo da FASE 5)

`aml_sec_boot_check` = SMC `AML_DATA_PROCESS` para BL31/BL32 fechado.
classificacao: C (secure world executa o decrypt inteiro; U-Boot so
mede tamanho e da flush_cache). a key nao sai do TEE/secure monitor
em nenhum fluxo documentado. reimplementacao offline exigiria a key
(vector `kernelaeskey`, cf. Raxone usbdl) ou o proprio BL31 — ambos
fora de alcance sem exploit com reboot via USB (fora de escopo:
exige reiniciar e modo fisico).
