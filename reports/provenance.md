# provenance — qual arvore gerou o 4.9.113 do aquaman PI.2055

dispositivo: Xiaomi Mi TV Stick 1080p, MiTV-AESP0, aquaman, S805Y/GXL, Android 9 PI.2055
kernel no aparelho: 4.9.113, jenkins@c5-mitv-cm-build06.bj, Tue Sep 6 12:53:43 CST 2022, gcc 6.3.1 Linaro 6.3-2017.02

## McMCCRU/linux-amlogic: ANCESTRAL, nao SOURCE EXATO

repo: https://github.com/McMCCRU/linux-amlogic
HEAD: 3d4ab79ea3638850a736bf2f7f65e55cb47368c4, tag 00001, branch unico master
rev-list --count: 8. root 17cef223 2019-06-04 "Amlogic official release kernel linux-4.9.113", HEAD 2019-06-27.
Makefile: VERSION=4 PATCHLEVEL=9 SUBLEVEL=113, NAME=Roaring Lionus.
configs: arch/arm64/configs/{defconfig,meson64_defconfig,meson64_smarthome_defconfig,ranchu64_defconfig} apenas.

evidencia que e ancestral da mesma familia:
- mesmo SUBLEVEL 113 e mesma base Amlogic (meson64_defconfig e 100% subset do aquaman-config menos 6 opcoes, ver config-diff.md)
- tem is_meson_gxl_package_805Y (package_id 0xb0) em include/linux/amlogic/cpu_version.h + 2 branches de driver (hdmitx, vdec)
- drivers/amlogic/*, binder, sdcardfs, era Android P — tudo compativel com um TV stick 2019-2022

evidencia que NAO e o source exato:
- 8 commits em 23 dias, drop squashado de vendor, sem historico upstream. build do aparelho e de 2022-09-06, 3 anos depois.
- zero strings aquaman/aesp0/mdz-24/xiaomi/mitv/c5-mitv/PI.2055/dtbo_idx/jenkins na arvore inteira (grep confirma; unicos "jenkins" sao hash Robert Jenkins em net/)
- nenhum DTS aquaman; so referencia gxl_p212/p230/p231/p241 (p241 carrega comentario s805x, nao 805Y)
- nenhum tooling AMLSECU, nenhum BoardConfig/device/vendor, LOCALVERSION vazio
- dangal-p-oss (Xiaomi oficial, mesma versao, outro aparelho) da o mesmo score de similaridade — ou seja, McMCCRU nao tem nada de especifico do aquaman

classificacao: ANCESTRAL (base direta da familia, sem deltas Xiaomi/aquaman).

## source mais proximo encontrado

nenhum SOURCE EXATO. ranking por proximidade real:

1. MiCode/MiTV_OpenSource@dangal-p-oss — Xiaomi oficial, 4.9.113, Amlogic, 2019-07-11. aparelho errado (dangal TV), sem DTS aquaman, sem 805Y DTS. score config 14.07% vs 14.05% do McMCCRU (empate tecnico). util como referencia de como a Xiaomi empacota um 4.9.113 Amlogic P.
   URL: https://github.com/MiCode/MiTV_OpenSource, branch dangal-p-oss, commit 2ecab23dd 2019-07-11.
2. McMCCRU/linux-amlogic@master (3d4ab79e 2019-06-27) — mesma base, sem Xiaomi. melhor inventario local (ja clonado em /tmp/kernel-src/linux-amlogic).
3. khadas/linux ubuntu-4.9 / LineageOS android_kernel_amlogic_linux-4.9 lineage-22.2 — mesma familia GXL (VIM1 S905X ~ S805Y), frescos (2025-2026), board errado, sem aquaman.
4. torvalds/linux meson-gxl-s805y-xiaomi-aquaman.dts (merge maio 2025) — unico DTS aquaman existente em qualquer lugar, mas mainline moderno, nao 4.9 downstream. serve como mapa de hardware (1GB, eMMC HS200, RTL8821CS via sd_emmc_b, uart_A BT, hdmi_tx + cec_AO, som XIAOMI-AQUAMAN), baseado em p241. nao serve para rebuild 4.9.

## existe arvore Xiaomi 2022? NAO

- MiCode tem 3 repos: Xiaomi_Kernel_OpenSource (só celular), MiBox_Kernel_OpenSource (once-o-oss, 4.9.54, MiBox3, 2019-02), MiTV_OpenSource (dangal/machuca/venom, nenhum aquaman). issue #11 no MiBox repo (jan 2025) pede GPL do aquaman e segue aberto.
- fingerprint c5-mitv-cm-build06.bj: zero hits indexados. PI-2055: so dumps (tadiphone, hoje 404) + thread XDA com OTA yandex. nenhum repo/branch/commit.
- conclusao: build 2022 foi de arvore interna Xiaomi/Amlogic nunca publicada. o que falta e exatamente: DTS aquaman downstream, defconfig aquaman, deltas Android TV, e o packaging AMLSECU com a user-key.

## e possivel reproduzir 4.9.113? AINDA NAO

temos versao + config parcial + mapa de hardware mainline, mas faltam os 3 itens acima + chave AMLSECU. sem eles, qualquer rebuild e aproximacao, nao reproducao.
nenhum arquivo reports/EXACT_SOURCE_FOUND foi criado, de proposito.
