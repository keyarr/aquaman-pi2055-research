# amlsecu-structure — layout formal do container 0x0905

ferramenta: `tools/parse_amlsecu.py` (so leitura). saidas verificadas
contra `boot_unpack/kernel` e `recovery_unpack/kernel`.

## header global (offset relativo ao inicio do slice kernel, LE)

| offset | tam | campo | endian | boot | recovery |
|---|---|---|---|---|---|
| +0x00 | 8 | magic `AMLSECU!` | ascii | `414d4c5345435521` | igual |
| +0x08 | 4 | version | u32 LE | `0x0905` | igual |
| +0x0C | 4 | nBlkCnt | u32 LE | 3 | 3 |
| +0x10 | 16 | szTimeStamp | ascii | `2022090612544443` | `2022090613082318` |
| +0x20 | 96 | amlKernel (t_aml_enc_blk) | — | ver abaixo | ver abaixo |
| +0x80 | 96 | amlRamdisk (t_aml_enc_blk) | — | zerado | ver abaixo |
| +0xE0 | 96 | amlDTB (t_aml_enc_blk) | — | ver abaixo | ver abaixo |
| +0x140 | 1088 | reservado | — | zeros | zeros |
| +0x600 | 512 | assinatura da imagem | opaco | `6f3a5499...` | `60735030...` (diferente) |
| +0x800 | — | inicio do payload blk0 | — | ciphertext | ciphertext (diferente do boot desde o byte 0) |

header total `0x800`. para Android 9 o U-Boot usa base 4096 e poe o
info em +2048 (`(secureKernelImgSz>>1)`), com `reserve4ImgHdr[2048]`.
`COMPILE_TYPE_ASSERT(2048 >= sizeof(...))` no fonte pre-9 virou 4096
na variante 9. o magic em offset de arquivo `0x800` (depois da pagina
do Android header) e consequencia direta disso, nao coincidencia.

## descritor por bloco (96 = 0x60 bytes, u32 LE)

| +off | tam | campo (fonte) | boot blk0 | boot blk2 | rec blk1 | rec blk2 |
|---|---|---|---|---|---|---|
| +0x00 | 4 | nOffset | `0x800` | `0x959800` | `0x959800` | `0xfab000` |
| +0x04 | 4 | nRawLength | 9800145 | 59424 | 6623797 | 59424 |
| +0x08 | 4 | nSigLength | 9801728 | 61440 | 6625280 | 61440 |
| +0x0C | 4 | nAlignment | 2048 | 2048 | 2048 | 2048 |
| +0x10 | 4 | nTotalLength | 9801728 | 61440 | 6625280 | 61440 |
| +0x14 | 12 | szPad | zeros | zeros | zeros | zeros |
| +0x20 | 32 | szSHA2IMG | zeros | zeros | zeros | zeros |
| +0x40 | 32 | szSHA2KeyID | `ef8996bd...1492` | mesmo | mesmo | mesmo |

blk1 do boot e 96 bytes zerados (sem ramdisk).

## regras derivadas (todas verificadas)

* `nTotalLength = ALIGN_UP(nRawLength, 2048)`:
  9800145->9801728, 59424->61440, 6623797->6625280. alinhamento e de
  pagina/flash, nao de bloco AES (16).
* neste firmware `nSigLength == nTotalLength` sempre. o nome sugere
  "tamanho assinado", mas nao da para distinguir de "tamanho cifrado";
  tratar como opaco.
* `nOffset` e offset de arquivo/flash do slice: blk0 `0x800` (= inicio
  do slice kernel), blk1 `0x959800` (`0x800+9801728`, inicio do slice
  ramdisk), blk2 boot `0x959800` (ramdisk vazio, second colado no kernel),
  blk2 recovery `0xfab000` (`0x800+9801728+6625280`, inicio do second).
  confere com `kernel_size`/`ramdisk_size`/`second_size` do Android header.
* tamanho total seguro (Android 9):
  `4096 + sum(nTotalLength)`. boot: 4096+9801728+0+61440 = 9867264
  (`0x969000`); AVB em 9871360 (+4096). recovery:
  4096+9801728+6625280+61440 = 16492544 (`0xfba800`); AVB em 16494592
  (+2048). bate com o loop do `_aml_get_secure_boot_kernel_size`.
* `szSHA2IMG` zerado em todos os blocos das duas imagens: o campo de
  hash de imagem nao e usado neste fluxo (ou e preenchido so no verify
  em memoria). nao e hash por bloco.
* `szSHA2KeyID` identico (`ef8996bd...`) nos 5 blocos nao vazios das
  duas imagens, zerado no bloco vazio. e identificador da key, nao hash
  do conteudo. ver amlsecu-key-path.md.
* assinatura de 512 bytes em +0x600 difere entre boot e recovery
  (timestamps a 14 min de distancia). cobre header+payloads; sem a
  user-key nao e reproduzivel.

## classificacao dos campos

* constantes: magic, version, nAlignment (2048), szPad, szSHA2IMG (zero).
* por firmware (iguais em boot+recovery): nRaw/nSig/nTotal do kernel e
  do DTB, szSHA2KeyID.
* por imagem: timestamp, payloads, assinatura 512 B, blocos presentes
  (ramdisk so no recovery).
* por bloco: nOffset, nRawLength, nTotalLength.
