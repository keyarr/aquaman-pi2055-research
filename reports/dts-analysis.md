# dts-analysis — tem DTS aquaman? NAO (parcial via mainline)

## McMCCRU/linux-amlogic: zero aquaman

arch/arm64/boot/dts/amlogic/: 125 arquivos. grep aquaman|aesp0|mdz-24 = 0 hits. grep xiaomi|mibox|mitv = 0 (so falsos positivos LIMITVALUE).
805Y aparece em 2 lugares: cpu_version.h (package_id 0xb0) + branch hdmitx/vdec. nenhum DTS seleciona por 805Y.
todos gxl_*: model="Amlogic", compatible="amlogic, meson-gxl" generico; discriminador e amlogic-dt-id + usable-memory.

| arquivo | dt-id | ram | veredito |
|---|---|---|---|
| gxl_p241_1g(+buildroot), v2-1g(+buildroot) | gxl_p241_1g / v2-1g | 1G (0x3ff00000) | mesma familia, provavelmente diferente (comentario s805x no venc, sem evidencia aquaman) |
| gxl_p212_1g(+hd,+buildroot), _2g(+buildroot) | p212 | 1G/2G | mesma familia, provavelmente diferente (ref S905X) |
| gxl_p230_2g(+buildroot) | p230 | 2G | mesma familia, provavelmente diferente |
| gxl_p231/p400/p401/sei210/skt, gxm_* | — | — | mesma familia / SoC diferente (GXM), provavelmente diferente |
| g12a/g12b/axg/txl/txlx/tl1, partition_*, firmware_* | — | — | provavelmente diferente / irrelevante |

regra: gxl_p241 NAO e aquaman sem evidencia. nenhum candidato promovivel.

## dangal-p-oss (MiCode): tambem zero

126 dts, mesmos nomes, find *dangal*/*aquaman* = vazio. confirma: arvore Xiaomi oficial publicada nao tem o board do stick.

## unico DTS aquaman existente: mainline 2025 (PARCIAL)

torvalds/linux arch/arm64/boot/dts/amlogic/meson-gxl-s805y-xiaomi-aquaman.dts (Ferass El Hafidi, merge maio 2025):
model="Xiaomi Mi TV Stick (aquaman)", compatible="xiaomi,aquaman","amlogic,s805y","amlogic,meson-gxl".
base declarada: p241. memoria 0x40000000 = 1GB. sem amlogic-dt-id.
nodes: sd_emmc_b SDIO wifi RTL8821CS + pwm 32k, uart_A BT (rtscts), sd_emmc_c eMMC 8-bit HS200, hdmi_tx + cec_AO + hdmi-connector A, som "XIAOMI-AQUAMAN", led GPIODV_24, saradc, usb otg vbus.
https://github.com/torvalds/linux/blob/master/arch/arm64/boot/dts/amlogic/meson-gxl-s805y-xiaomi-aquaman.dts
serve como mapa de hardware para um futuro port 4.9, nao como source do build 2022.

## DTB no firmware: selado

dt.img 59424 B sha256 ea2f4c65...5593 entropia 7.9965, sem D00DFEED, 672 runs ascii sem keywords — cifrado.
second 61440 B sha256 3ba00608...e9e entropia 7.9710, sem keywords — cifrado (dtb cifrado, sem header AMLSECU).
dt.img[0:32] == kernel[0x60:0x80] (ef8996bd...) = payload dtb dentro do bloco AMLSECU blk2 (raw 59424 = 0xe820, tot 61440 = 0xf000).
dtbo.img 8MB: magica d7b7ab1e valida mas 320 bytes nonzero em 8MB (dummy-battery/dummy-charger + AVB avbtool 1.1.0). overlay efetivamente vazio.
boot cmdline: androidboot.dtbo_idx=0 otg_device=1 buildvariant=user.
nenhum DTB geravel do source chega perto sem o dts real; nao gerar DTB ainda.
