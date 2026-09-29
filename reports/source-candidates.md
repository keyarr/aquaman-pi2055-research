# source-candidates — honest ranking

NO EXACT SOURCE. Nothing with aquaman branch + 4.9.113 + 2022.

1. MiCode/MiTV_OpenSource dangal-p-oss — closest among "official Xiaomi + 4.9.113"
   https://github.com/MiCode/MiTV_OpenSource branch dangal-p-oss commit 2ecab23dd 2019-07-11 (1 real commit + initial). Makefile 4.9.113. Configs identical to McMCCRU + meson64_a32. 126 DTS without dangal/aquaman. Score 14.07%. Wrong device (dangal TV), but demonstrates the format of the Xiaomi P drop.
2. McMCCRU/linux-amlogic master 3d4ab79e 2019-06-27 — Amlogic 4.9.113 base, 8 commits, 805Y ID present, without Xiaomi. Cloned in `.src/linux-amlogic`. Score 14.05%. Best local base for diffing.
3. khadas/linux ubuntu-4.9 + LineageOS android_kernel_amlogic_linux-4.9 lineage-22.2 — correct GXL family (VIM1 S905X), fresh, wrong board, no aquaman. Driver reference, not device source.
4. hardkernel/linux odroidg12/n2-4.9.y (4.9.216, G12) — wrong subfamily. LibreELEC/linux-amlogic (3.14 archived) — unusable.
5. torvalds/linux meson-gxl-s805y-xiaomi-aquaman.dts — only aquaman DTS, mainline 2025, based on p241. Hardware map, not build source.
6. MiBox once-o-oss 4.9.54 — proves that Xiaomi publishes Amlogic boxes, but wrong version and wrong device.

web fingerprints:
- "c5-mitv-cm-build06.bj": 0 hits (internal user@host, not indexed; droid*-bj hosts appear in XDA UART logs of the same device).
- "aquaman-user-9-PI-2055-release-keys": only dumps.tadiphone (now 404) + XDA unbrick thread (Yandex OTA, post-build string). No source.
- MiTV-AESP0/MDZ-24-AA: only hardware datasheets (S805Y, 1GB/8GB). No kernel.
- GPL: issue MiBox_Kernel_OpenSource#11 (Jan 2025) requesting aquaman+u-boot source, open.

where the real source lives: internal Xiaomi Beijing tree (c5-mitv-cm-build06) with aquaman DTS + defconfig + TV deltas + AMLSECU key. Never published as of 2026-09.
