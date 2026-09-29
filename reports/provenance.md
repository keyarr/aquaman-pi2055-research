# provenance — which tree built the aquaman PI.2055 4.9.113 kernel

device: Xiaomi Mi TV Stick 1080p, MiTV-AESP0, aquaman, S805Y/GXL, Android 9 PI.2055
kernel on device: 4.9.113, jenkins@c5-mitv-cm-build06.bj, Tue Sep 6 12:53:43 CST 2022, gcc 6.3.1 Linaro 6.3-2017.02

## McMCCRU/linux-amlogic: ANCESTOR, not EXACT SOURCE

repo: https://github.com/McMCCRU/linux-amlogic
HEAD: 3d4ab79ea3638850a736bf2f7f65e55cb47368c4, tag 00001, single branch master
rev-list --count: 8. root 17cef223 2019-06-04 "Amlogic official release kernel linux-4.9.113", HEAD 2019-06-27.
Makefile: VERSION=4 PATCHLEVEL=9 SUBLEVEL=113, NAME=Roaring Lionus.
configs: arch/arm64/configs/{defconfig,meson64_defconfig,meson64_smarthome_defconfig,ranchu64_defconfig} only.

evidence that it is an ancestor from the same family:
- same SUBLEVEL 113 and same Amlogic base (meson64_defconfig is a 100% subset of aquaman-config minus 6 options, see config-diff.md)
- has is_meson_gxl_package_805Y (package_id 0xb0) in include/linux/amlogic/cpu_version.h + 2 driver branches (hdmitx, vdec)
- drivers/amlogic/*, binder, sdcardfs, Android P era — all compatible with a 2019-2022 TV stick

evidence that it is NOT the exact source:
- 8 commits in 23 days, squashed vendor drop, no upstream history. Device build is from 2022-09-06, 3 years later.
- zero aquaman/aesp0/mdz-24/xiaomi/mitv/c5-mitv/PI.2055/dtbo_idx/jenkins strings across the entire tree (grep confirms; only "jenkins" hits are Robert Jenkins lookup hashes in net/)
- no aquaman DTS; only references to gxl_p212/p230/p231/p241 (p241 carries an s805x comment, not 805Y)
- no AMLSECU tooling, no BoardConfig/device/vendor, empty LOCALVERSION
- dangal-p-oss (official Xiaomi, same version, different device) yields the same similarity score — meaning McMCCRU contains nothing aquaman-specific

classification: ANCESTOR (direct family baseline, without Xiaomi/aquaman deltas).

## closest source found

NO EXACT SOURCE. ranking by actual proximity:

1. MiCode/MiTV_OpenSource@dangal-p-oss — official Xiaomi, 4.9.113, Amlogic, 2019-07-11. Wrong device (dangal TV), no aquaman DTS, no 805Y DTS. Config score 14.07% vs 14.05% for McMCCRU (technical tie). Useful as a reference for how Xiaomi packages a 4.9.113 Amlogic P kernel.
   URL: https://github.com/MiCode/MiTV_OpenSource, branch dangal-p-oss, commit 2ecab23dd 2019-07-11.
2. McMCCRU/linux-amlogic@master (3d4ab79e 2019-06-27) — same base, without Xiaomi. Best local inventory (cloned in `.src/linux-amlogic`).
3. khadas/linux ubuntu-4.9 / LineageOS android_kernel_amlogic_linux-4.9 lineage-22.2 — same GXL family (VIM1 S905X ~ S805Y), fresh (2025-2026), wrong board, no aquaman.
4. torvalds/linux meson-gxl-s805y-xiaomi-aquaman.dts (merged May 2025) — only aquaman DTS existing anywhere, but modern mainline, not 4.9 downstream. Serves as hardware map (1GB, eMMC HS200, RTL8821CS via sd_emmc_b, uart_A BT, hdmi_tx + cec_AO, sound XIAOMI-AQUAMAN), based on p241. Not suitable for a 4.9 rebuild.

## does a Xiaomi 2022 tree exist publicly? NO

- MiCode has 3 repos: Xiaomi_Kernel_OpenSource (phones only), MiBox_Kernel_OpenSource (once-o-oss, 4.9.54, MiBox3, 2019-02), MiTV_OpenSource (dangal/machuca/venom, no aquaman). Issue #11 on the MiBox repo (Jan 2025) requests aquaman GPL source and remains open.
- fingerprint c5-mitv-cm-build06.bj: zero indexed hits. PI-2055: only dumps (tadiphone, now 404) + XDA thread with Yandex OTA. No repo/branch/commit.
- conclusion: the 2022 build came from an internal Xiaomi/Amlogic tree that was never published. What is missing is exactly: downstream aquaman DTS, aquaman defconfig, Android TV deltas, and AMLSECU packaging with the user-key.

## is it possible to reproduce 4.9.113? NOT YET

We have the version + partial config + mainline hardware map, but the 3 items above + the AMLSECU key are missing. Without them, any rebuild is an approximation, not a reproduction.
No reports/EXACT_SOURCE_FOUND file was created, by design.
