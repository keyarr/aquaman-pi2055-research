# dts-analysis — no public aquaman DTS, but the runtime DTB is out of RAM

read this first, it changed the answer and only the last section still holds.

```text
DTB runtime:
    encontrado em 0x01000000
    FDT válido
    gxl_aquaman_1g
    amlogic, Gxl
    mali@d00c0000

DTS:
    primeiro esboço já reconstruído a partir do dump de RAM
    parcialmente correlacionado com os nós/props observados no FDT
    ainda não provado como source exato do vendor

dt.img:
    continua criptografado no artifact de firmware
    não confundir o primeiro esboço extraído da RAM com o DTS original
```

the FDT was pulled out of live DRAM at `0x01000000` on 2026-09-29, 58280
bytes, valid, 376 nodes with properties and 1798 properties.
`artifacts/aquaman.dtb` and `artifacts/aquaman.dts` are it, and
`reports/aquaman-dtb-extraction.md` is the full node-by-node writeup.

that is worth more than it looks like. every question below that used to be a
hypothesis about the hardware is now a question about a blob we hold, and
several of them are answered outright there: 1 GiB of usable RAM with a 1 MiB
hole at the bottom, 1 ns vs 3.5 ns DDR (no CKE pin on this board, which matches
`linux,usable-memory` and the mainline DTS), three `meson-mmc-gxl` controllers
all enabled, three `meson-gxl-usb2` ports, no ethernet node at all.

what the RAM blob does **not** give: the vendor's DTS source, its file layout,
its `dtb-1`/`dtb-2` naming, or the `dt.img` packaging. those stay unavailable.

the sections below are unchanged and still true about **public source trees**.

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

## DTB in firmware: dt.img still encrypted, RAM copy is not

**the "sealed" verdict below is obsolete for the DTB itself and still correct
for `dt.img`.** do not read "the board DTB is inaccessible" any more: it is
`artifacts/aquaman.dtb`, extracted from `0x01000000` in DRAM, hash
`b00adaba...4468`, validated by `fdtdump`, round-trips through `dtc` with zero
errors and 1798 value-identical properties. `aquaman-dtb-extraction.md` §3 also
kills the old "second copy of the tree" claim: `d00dfeed` appears once in the
16 MiB dump.

what is still sealed, and stays sealed:

dt.img 59424 B sha256 ea2f4c65...5593 entropy 7.9965, no D00DFEED, 672 ASCII runs without keywords — encrypted.
second 61440 B sha256 3ba00608...e9e entropy 7.9710, no keywords — encrypted (encrypted DTB, without AMLSECU header).
dt.img[0:32] == kernel[0x60:0x80] (ef8996bd...) = DTB payload within AMLSECU blk2 (raw 59424 = 0xe820, tot 61440 = 0xf000).
dtbo.img 8MB: valid d7b7ab1e magic but only 320 nonzero bytes in 8MB (dummy-battery/dummy-charger + AVB avbtool 1.1.0). Overlay is effectively empty.
boot cmdline: androidboot.dtbo_idx=0 otg_device=1 buildvariant=user.

so: no vendor DTS source, and the shipped `dt.img` payload is still ciphertext.
**the DTS that was reconstructed is a reconstruction, not the original.** do not
present `artifacts/aquaman.dts` as Xiaomi's file, and do not use it to claim
the vendor tree is recovered.
