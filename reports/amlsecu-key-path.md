# amlsecu-key-path — de onde vem a user-key

## o que e a user-key (FORTE EVIDENCIA)

arquivo `aml-user-key.sig`, chave RSA do vendor, usada em duas pontas:

```bash
aml_encrypt_<soc> --efsgen --amluserkey aml-user-key.sig \
  --output SECURE_BOOT_SET            # padrao queimado no efuse
aml_encrypt_<soc> --imgsig --amluserkey aml-user-key.sig \
  --input boot.img --output boot.img.encrypt   # container AMLSECU!
```

fontes: hardkernel/buildroot `aml_upgrade_pkg_gen.sh`,
onethingcloud-oes-linux, LibreELEC `amlogic-boot-fip/gxl.inc`.
o hash SHA256 das chaves RSA vai para o efuse (`0x140-0x160 rsa hash
of all rsa keys`, Raxone/Amlogic-efuse). o `szSHA2KeyID` do nosso dump
(`ef8996bd...`, igual nos 5 blocos nao vazios) tem o formato exato de
um desses identificadores: 32 bytes, constante por firmware, zero no
bloco vazio. leitura: e o KeyID da user-key, nao hash do payload.

## onde a key mora no boot (FORTE EVIDENCIA)

* eFuse/OTP e a raiz: `is_secure_boot_enabled()` le `AO_SEC_SD_CFG10`
  bit 4 (khadas) ou bits de licenca OTP `FEAT_ENABLE_DEVICE_SCS_SIG_*`
  (S4 `aml_efuse.c`). layout de efuse documentado (Raxone):
  `0x20-0x40 aeskey`, `0x40-0x50 aeskey iv`, `0xa0-0xc0` nivel secure,
  `0x140-0x160` hash das chaves RSA.
* o uso e sempre via SMC (`aml_sec_boot_check` -> `smc #0`,
  `x0=AML_DATA_PROCESS`). o normal world passa buffer+tipo; o
  BL31/BL32 usa DMA + engine de crypto com a key derivada do efuse.
  a key plaintext nunca aparece no U-Boot (nao ha leitura de key no
  `cmd_imgread.c`; so magic/version/tamanho).
* no kernel, `CONFIG_AMLOGIC_SEC/TEE/EFUSE` + `unifykey` mostram o
  segundo acesso: chaves `KEY_EFUSE` / `KEY_SECURE` (so hash SHA256 sai
  para o normal world, nunca o segredo). coerente com o mesmo desenho.

## algoritmo (EVIDENCIA FRACA -> NAO PROVADO)

* o flag `--aeskey enable` no `--bootsig` e os campos `aeskey`/`aeskey
  iv` no efuse provam AES no secure boot do bootloader (BL2 usa
  AES-256-CBC segundo reversing-gxbb-bl2; ferramenta Raxone extrai
  `bl2aeskey`, `bl2aesiv`, `bl3xaeskey`, `kernelaeskey`).
* para o payload `--imgsig` (kernel/ramdisk/dtb) nenhum fonte publica
  nomeia o modo. AES e a inferencia obvia (engine existe, keys existem,
  entropia 8.0, alinhamento preservado), mas modo (CBC/CTR/XTS?),
  IV/nonce por bloco e derivacao exata (key ladder? TEE? salt por chip?)
  sao desconhecidos. o `szSHA2IMG` zerado elimina "hash plaintext no
  header" como fonte de verificacao offline.
* assinatura de 512 bytes em +0x600: tamanho compativel com RSA-4096.
  nao confirmado; pode ser outro esquema. tratar como opaco.

## as 9 perguntas da FASE 4

1. fixa por modelo — EVIDENCIA FRACA (KeyID igual em boot+recovery do
   mesmo build; Xiaomi gera uma user-key por produto/linha, mas sem a
   `aml-user-key.sig` vazada nao ha como afirmar).
2. fixa por firmware — EVIDENCIA FRACA (mesmo KeyID nas duas imagens do
   PI.2055; esperado se a key e por produto).
3. por dispositivo — NAO PROVADO (nada no container varia por serial;
   chipid existe no efuse `0x04-0x20` mas nenhum campo do header o
   referencia).
4. derivada de eFuse — FORTE EVIDENCIA (raiz de verificacao e OTP bits;
   aeskey mora no efuse).
5. efuse + salt — NAO PROVADO.
6. obtida do TEE — FORTE EVIDENCIA como executor (SMC/BL32), mas "obter"
   e a palavra errada: o TEE nao entrega, ele usa.
7. secure storage — EVIDENCIA FRACA (unifykey `KEY_SECURE` existe no
   kernel; papel no boot nao documentado).
8. key ladder — NAO PROVADO (termo aparece no BSP, sem binding com
   `--imgsig` em fonte publica).
9. combinacao — inferencia honesta: efuse (AES key + RSA hash + secure
   level) + user-key RSA do vendor + crypto no secure world. o elo
   exato entre eles e fechado.

## consequencia pratica

mesmo que a key fosse por modelo (melhor caso para nos), ela nao esta
em nenhum artefato publico: `bootloader.img` local e ciphertext sem
strings, `aml-user-key.sig` do aquaman nunca vazou, e o BL31 que usa a
key e binario fechado. sem ela, `--imgsig` nao e reproduzivel e forca
bruta e inviavel (espaco de 128/256 bits, sem oraculo rapido).
