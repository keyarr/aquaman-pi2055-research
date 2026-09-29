# amlsecu-open-questions — o que falta e o proximo passo

## respostas diretas (11 perguntas)

1. formato `0x0905`: CONFIRMADO (structs publicas + parser local bate
   nos dois dumps; tabela em amlsecu-structure.md).
2. algoritmo: NAO PROVADO. AES e inferencia forte (engine + efuse
   aeskey + `--aeskey enable`), modo/IV/derivacao desconhecidos.
3. onde esta a chave: raiz em eFuse/OTP, uso exclusivo no secure world
   via SMC (FORTE EVIDENCIA). `szSHA2KeyID` (`ef8996bd...`) identifica
   a user-key do vendor.
4. escopo da key: por produto/firmware e o palpite honesto (EVIDENCIA
   FRACA); por dispositivo, NAO PROVADO.
5. a chave sai do TEE? Nao em nenhum fluxo documentado. o TEE/BL31
   executa o decrypt (opcao C).
6. implementacao publica p/ reproduzir o encrypt? NAO. parser existe
   (BMU, parse_amlsecu.py); packer `--imgsig` e fechado.
7. ferramenta publica equivalente a `aml_encrypt --imgsig`? NAO
   (`gxlimg`/`meson-tools` nao cobrem imgsig).
8. caminho offline p/ imagem valida? NAO, sem a `aml-user-key.sig` do
   aquaman (ou a kernel-AES key extraida via exploit).
9. kernel custom que `fastboot boot` aceite sem a user-key? CONFIRMADO
   (teste 2026-09-29, reboot autorizado): `boot.img` plaintext de 4096
   bytes (header v1, kernel = stub ARM64 de 20 bytes sem magic AMLSECU,
   sem ramdisk/second) foi aceito via `fastboot boot` — aparelho saiu
   do fastboot, executou o stub (PSCI SYSTEM_RESET) e voltou ao Android
   sozinho em ~30s, sem intervencao fisica. secure=no + unlocked =
   path `secureKernelImgSz == 0` ativo; U-Boot nao exige AMLSECU em
   imagem sem magic. stub: movz/movk x0 = 0x84000009, hvc #0, wfi loop.
10. bloqueio real p/ KernelSU/APatch: nao e o packaging AMLSECU nem
    o kernel em si — `fastboot boot` aceita plaintext (item 9), entao
    um kernel rebuildado + DTB (ex. mainline
    `meson-gxl-s805y-xiaomi-aquaman.dts`) pode bootar sem nenhuma key.
    o que falta e o kernel/DTB funcional em si (DTS downstream, defconfig
    exata, drivers TV), nao a criptografia. Magisk/APatch sobre o
    `boot.img` stock continuam inviaveis (ramdisk ciphertext, #2555),
    mas patch via rebuild proprio + `fastboot boot` nao precisa da
    user-key. flash permanente (`fastboot flash`) continua nao testado
    e arriscado: U-Boot pode exigir AMLSECU no boot da eMMC mesmo com
    secure=no.
11. o que elimina o bloqueio: (a) `aml-user-key.sig` do aquaman/PI.2055
    vazada; (b) kernel-AES key extraida via exploit BootROM USBDL
    (Raxone, fredericb) — exige reboot fisico, fora de escopo agora;
    (c) prova de que `secure=no` + unlocked aceita plaintext no
    `fastboot boot` — exige um boot de teste, tambem fora de escopo
    agora.

## inferencia x desconhecido (resumo)

* provado: layout, semantica dos tamanhos, offsets, KeyID constante,
  assinatura 512 B, fluxo imgread->SMC, ausencia de tooling publico.
* inferencia: AES no payload, RSA-4096 na assinatura, key por produto.
* desconhecido: modo AES, IV, key ladder exato, conteudo do BL31,
  comportamento do `fastboot boot` com plaintext neste aparelho.

## proximo passo offline de maior valor (sem tocar no aparelho)

1. extrair do `system/vendor/odm` (dumps `*.new.dat.br` ja locais) o
   `build.prop` / TA/TEE userspace (`tee-supplicant`, keybox, widevine)
   para ver se algum UUID/TA referencia a user-key — custo zero, so
   descompactar.
2. caçar `aml-user-key*.sig` / `SECURE_BOOT_SET` / `aml_encrypt_gxl`
   em dumps/OTAs publicos do aquaman (XDA/yandex) — improvavel, mas
   barato.
3. montar um `boot.img` plaintext de teste (kernel mainline + ramdisk
   minimo) e deixar pronto para um futuro `fastboot boot` autorizado —
   sem executar agora.

## o que NAO fazer

* nenhum `fastboot boot/flash/erase/reboot`, `saveenv`, `setenv`,
  fuzzing `oem`, `current-slot`: tudo reinicia ou altera estado.
* nenhum brute force de key (sem oraculo, espaco inviavel).
* nao compilar kernel nem gerar imagem de flash nesta etapa.
