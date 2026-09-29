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

 current state, start here:
 - reports/fastboot-memory-flow.md : where the payload goes. refutes the
   old "download != boot source" root cause.
 - reports/vendor-modules.md : the 28 stock .ko, extracted from the OTA dumps
   in this repo. no root, no device needed.
 - reports/rebuilt-kernel.md : the rebuild, and why it is not a reproduction.
 - reports/custom-kernel-execution.md : execution paths and the blocker.
 - reports/aquaman-dts-port.md : mainline 2025 -> 4.9, node by node.
 - reports/repo-state.md : audit. what is proven, what is hypothesis, and
   the list of contradictions found in the older reports.

 stale claims in older reports carry a banner at the top saying which newer
 file supersedes them. the wrong ones worth knowing about: the plaintext-boot
 "CONFIRMED" in amlsecu-open-questions.md, `X = 0x10200000` in
 bootm-test-image.md / set-active-sink.md, "root is required" in
 vendor-module-compat.md, and the max-download-size root cause in
 fastboot-boot-verdict.md.

 short version: the kernel builds (Image + dtb + modules, reproducible with
 tools/build_aquaman_kernel.sh), the stock modules are extracted and mapped,
 and execution is BLOCKED at BL31, which is secure-fused and refuses unsigned
 images. not an address problem.

 full writeup: reports/provenance.md

how i unlocked the bootloader:
[bootloader_unlock](https://github.com/keyarr/aquaman-pi2055-research/blob/main/reports/bootloader_unlock.md)
