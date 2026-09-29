# dts-analysis — does an aquaman DTS exist? NO (partial via mainline)

## McMCCRU/linux-amlogic: zero aquaman

arch/arm64/boot/dts/amlogic/: 125 files. grep aquaman|aesp0|mdz-24 = 0 hits. grep xiaomi|mibox|mitv = 0 (only false positive LIMITVALUE macros).
805Y appears in 2 places: cpu_version.h (package_id 0xb0) + hdmitx/vdec branches. No DTS selects by 805Y.
All gxl_*: generic model="Amlogic", compatible="amlogic, meson-gxl"; discriminator is amlogic-dt-id + usable-memory.

| file | dt-id | ram | verdict |
|---|---|---|---|
| gxl_p241_1g(+buildroot), v2-1g(+buildroot) | gxl_p241_1g / v2-1g | 1G (0x3ff00000) | same family, likely different (s805x comment on venc, no aquaman evidence) |
| gxl_p212_1g(+hd,+buildroot), _2g(+buildroot) | p212 | 1G/2G | same family, likely different (S905X reference) |
| gxl_p230_2g(+buildroot) | p230 | 2G | same family, likely different |
| gxl_p231/p400/p401/sei210/skt, gxm_* | — | — | same family / different SoC (GXM), likely different |
| g12a/g12b/axg/txl/txlx/tl1, partition_*, firmware_* | — | — | likely different / irrelevant |

rule: gxl_p241 is NOT aquaman without evidence. No candidate is eligible for promotion.

## dangal-p-oss (MiCode): also zero

126 dts, identical names, find *dangal*/*aquaman* = empty. Confirms: the published official Xiaomi tree does not contain the stick's board.

## only existing aquaman DTS: mainline 2025 (PARTIAL)

torvalds/linux arch/arm64/boot/dts/amlogic/meson-gxl-s805y-xiaomi-aquaman.dts (Ferass El Hafidi, merged May 2025):
model="Xiaomi Mi TV Stick (aquaman)", compatible="xiaomi,aquaman","amlogic,s805y","amlogic,meson-gxl".
declared base: p241. Memory 0x40000000 = 1GB. No amlogic-dt-id.
nodes: sd_emmc_b SDIO wifi RTL8821CS + pwm 32k, uart_A BT (rtscts), sd_emmc_c eMMC 8-bit HS200, hdmi_tx + cec_AO + hdmi-connector A, sound "XIAOMI-AQUAMAN", led GPIODV_24, saradc, usb otg vbus.
https://github.com/torvalds/linux/blob/master/arch/arm64/boot/dts/amlogic/meson-gxl-s805y-xiaomi-aquaman.dts
Serves as a hardware map for a future 4.9 port, not as the 2022 build source.

## DTB in firmware: sealed

dt.img 59424 B sha256 ea2f4c65...5593 entropy 7.9965, no D00DFEED, 672 ASCII runs without keywords — encrypted.
second 61440 B sha256 3ba00608...e9e entropy 7.9710, no keywords — encrypted (encrypted DTB, without AMLSECU header).
dt.img[0:32] == kernel[0x60:0x80] (ef8996bd...) = DTB payload within AMLSECU blk2 (raw 59424 = 0xe820, tot 61440 = 0xf000).
dtbo.img 8MB: valid d7b7ab1e magic but only 320 nonzero bytes in 8MB (dummy-battery/dummy-charger + AVB avbtool 1.1.0). Overlay is effectively empty.
boot cmdline: androidboot.dtbo_idx=0 otg_device=1 buildvariant=user.
No DTB generated from source comes close without the real DTS; do not generate DTB yet.
