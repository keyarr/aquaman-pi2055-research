aquaman PI.2055 kernel provenance research

 spent way too long on this. 
 
 Mi TV Stick 1080p (MiTV-AESP0, aquaman, S805Y/GXL),
 Android 9 PI.2055, kernel 4.9.113 built 2022-09-06 by jenkins@c5-mitv-cm-build06.bj.
 question was simple: which source tree built this kernel?

 verdict: no exact source exists in public.
 - McMCCRU/linux-amlogic (4.9.113, 2019-06-27) is ancestor, not exact. same
   sublevel, same amlogic base, has the 805Y package id. but zero aquaman
   strings, zero aquaman dts, 3 years older than the build.
 - no Xiaomi 2022 tree published anywhere. MiCode has dangal/machuca/venom,
   nothing for aquaman. GPL request (MiBox repo issue #11) open since jan 2025.
 - AMLSECU packaging sealed, no board config, no aquaman defconfig upstream.

 layout:
 - reports/ : provenance.md is the full story, start there. plus config diffs,
   dts analysis, ksu/apatch notes.
 - reports/config-diff/ : aquaman-config vs defconfig/meson64/smarthome + ranking.
 - tools/ : small scripts (boot parsing, config fingerprint, fastboot probe).
 - firmware/ : boot, dt, dtbo, vbmeta, bootloader imgs + SHA256SUMS.txt.
 - aquaman-config : kernel config extracted from the device.

 full writeup: reports/provenance.md

how i unlocked the bootloader:
[bootloader_unlock](https://github.com/keyarr/aquaman-pi2055-research/blob/main/reports/bootloader_unlock.md)
