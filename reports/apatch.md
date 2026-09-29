# apatch — VIABILIDADE: VIAVEL COM SOURCE (kernel recompilado proprio)

docs: https://apatch.dev/install.html, https://github.com/bmax121/APatch

requisitos: SOMENTE arm64. kernel Android 3.18–6.12. KALLSYMS=y + (ALL=y ou ALL=n com suporte inicial). sem exigencia de kprobes — KernelPatch resolve simbolos via kallsyms em tempo de patch.

aparelho: arm64 ok. 4.9.113 dentro de 3.18–6.12 ok. KALLSYMS=y + ALL=y + BASE_RELATIVE=y ok. KPROBES=n irrelevante para APatch.

porem: APatch nao resolve o AMLSECU. o kernel stock e ciphertext (magic AMLSECU! ver 0x905, 3 blocos, timestamp 2022090612544443, entropia 8.0) — nao da para patchar o boot.img atual direto. o fluxo teria que ser: source + rebuild proprio (com KALLSYMS_ALL=y mantido) + packaging AMLSECU + fastboot boot. a pergunta "APatch trabalha nesse kernel?" responde sim para um rebuild com a mesma config; para o blob atual, nao ha como injetar nada sem a chave.

classificacao: VIAVEL COM SOURCE (rebuild proprio + re-empacotamento; nunca patch no blob cifrado atual).

# amlsecu — o que falta (sem tentar quebrar nada)

header (offsets LE, de cmd_imgread.c + parse local):
magic 8s @0x00 = AMLSECU!, version u32 @0x08 = 0x905, nBlkCnt @0x0c = 3, timestamp ascii @0x10 (boot 2022090612544443, recovery 2022090613082318),
blk0 kernel @0x20 (off 0x800 raw 0x9589d1=9800145 tot 0x959000=9801728),
blk1 ramdisk @0x80 (boot zerado; recovery off 0x959800 raw 0x651235 tot 0x651800=6625280),
blk2 dtb @0xe0 (off 0x959800 raw 0xe820=59424 tot 0xf000=61440).
second (61440) = blk2 cifrado sem header. dt.img (59424) = payload raw do blk2. dtbo.img = plaintext vazio com AVB.
boot kernel sha256 3ebb0b28...e9e != recovery f9ff8d05...7 (quase todo payload difere, nao so timestamp). magisk_patched so mexe ramdisk (kernel identico byte a byte).

para produzir componente bootavel falta:
1. Image + dtb recompilados do source certo,
2. ferramenta fechada aml_encrypt_gxb/gxl/g12a (--imgsig --amluserkey <key.sig>) + a user-key do vendor (derivada de efuse, nunca publicada),
3. ou bootloader que aceite imagem sem cifra (nao e o caso: U-Boot 2015.01-g7ac5df7677-dirty espera AMLSECU).
ferramentas publicas (gxlimg, meson-tools, BMU, FIP-hack, AIK) cobrem so FIP de bootloader (--bootsig/--bl2sig), nunca --imgsig de kernel. topjohnwu/Magisk#2555 e XDA confirmam o beco.
codigo-fonte publico do formato: so o lado parse (U-Boot cmd_imgread.c, tools/analyze_android_boot.py local). re-encryption: nada publico.
