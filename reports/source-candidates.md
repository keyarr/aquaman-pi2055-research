# source-candidates — ranking honesto

nenhum SOURCE EXATO. nada com branch aquaman + 4.9.113 + 2022.

1. MiCode/MiTV_OpenSource dangal-p-oss — o mais proximo em "oficial Xiaomi + 4.9.113"
   https://github.com/MiCode/MiTV_OpenSource branch dangal-p-oss commit 2ecab23dd 2019-07-11 (1 commit real + initial). Makefile 4.9.113. configs iguais ao McMCCRU + meson64_a32. 126 dts sem dangal/aquaman. score 14.07%. aparelho errado (dangal TV), mas mostra o formato do drop Xiaomi P.
2. McMCCRU/linux-amlogic master 3d4ab79e 2019-06-27 — base Amlogic 4.9.113, 8 commits, 805Y id presente, sem Xiaomi. clonado em /tmp/kernel-src/linux-amlogic. score 14.05%. melhor base local para diff.
3. khadas/linux ubuntu-4.9 + LineageOS android_kernel_amlogic_linux-4.9 lineage-22.2 — familia GXL certa (VIM1 S905X), frescos, board errado, sem aquaman. referencia de driver, nao de aparelho.
4. hardkernel/linux odroidg12/n2-4.9.y (4.9.216, G12) — subfamilia errada. LibreELEC/linux-amlogic (3.14 arquivado) — inutil.
5. torvalds/linux meson-gxl-s805y-xiaomi-aquaman.dts — unico dts aquaman, mainline 2025, baseado em p241. mapa de HW, nao source do build.
6. MiBox once-o-oss 4.9.54 — prova que a Xiaomi publica box Amlogic, mas versao errada e aparelho errado.

fingerprints web:
- "c5-mitv-cm-build06.bj": 0 hits (user@host interno, nao indexado; hosts droid*-bj aparecem em logs UART XDA do mesmo aparelho).
- "aquaman-user-9-PI-2055-release-keys": so dumps.tadiphone (hoje 404) + XDA brick thread (OTA yandex, post-build string). sem source.
- MiTV-AESP0/MDZ-24-AA: so fichas de hardware (S805Y, 1GB/8GB). sem kernel.
- GPL: issue MiBox_Kernel_OpenSource#11 (jan 2025) pedindo source aquaman+u-boot, aberto.

onde estaria o source real: arvore interna Xiaomi Beijing (c5-mitv-cm-build06) com DTS aquaman + defconfig + deltas TV + chave AMLSECU. nunca publicada ate 2026-09.
