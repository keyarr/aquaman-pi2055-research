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
 - reports/bl33-offline-round10.md : the U-Boot anchor. matched
   securestorage.c + 13 BL31 ids at 0x01040000..0x0107ffff, pulled from a 16 MiB
   RAM dump. first real code for BL33 instead of string hunting.
 - reports/bl33-offline-round11.md : the base. that 256 KiB is the middle of a
   ~1.8 MiB image based at 0x01000000 — a stale load copy the kernel DTB was
   later staged over. do_bootm / aml_sec_boot_check / the boot-path SMC are
   not in the dump; the live copy is derived to ~0x37d90000..0x37e10000.
   fresh 16 MiB read, byte identical to round 8.
 - reports/bl33-offline-round12.md : **BL33 located.** read 0x37800000..0x38000000,
   found the executing copy at 0x37e18000 (`_start` + banner + cmd_tbl). full
   boot path mapped: do_bootm=0x37e24c00 -> aml_sec_boot_check=0x37e19ea8 ->
   smc #0 @0x37e19ed8 (x0=0x820000ff). this supersedes the "not in the dump"
   lines in rounds 10/11 — they were true of the stale load copy only.
 - reports/bl33-offline-round13.md : the relocation re-read on a fresh boot is
   byte-identical to round 12 (sha256 3d2eca1d…, cmp 0 diffs). base 0x37e18000,
   do_bootm, aml_sec_boot_check and the SMC site all reproduce — deterministic,
   not a one-session artifact.
 - reports/bl33-bl31-interface-round14.md : the BL33 image is a file now
   (0x37e18000..0x37ff0000, 0x1d8000, sha256 664fb34a…), carved offline out of
   the round-13 band. the whole SMC surface is enumerated (15 `smc #0` sites,
   22 ids) and the answer to "is there a privileged path besides
   aml_sec_boot_check" is yes: the fastboot `oem` command is a host-driven
   run_command (0x37e95630) and, unlike flash/erase/flashall/set_active, it
   never checks the lock state; `update` enters the v2 usbburning protocol; the
   secure-storage key interface is present but has no callers in this build.
   findings are classified informational/suspicious/strong candidate, no
   exploit, secure boot untouched.
 - reports/aquaman-dtb-extraction.md : the device tree, read out of DRAM at
   0x01000000. valid FDT, 376 nodes, 1798 props. artifacts/aquaman.dtb + .dts.
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
 fastboot-boot-verdict.md. from the RAM dump rounds: the "second copy of the
 DTB" in bl33-offline-round8.md §3.1, the "11 SMC sites" in §5 (wrong opcode
 constant), the "unidentified ARM64, not U-Boot" verdict for 0x01040000 in §3.2,
 and every "the board DTB is sealed in dt.img" line — that DTB is out of RAM now.

 short version: the kernel builds (Image + dtb + modules, reproducible with
 tools/build_aquaman_kernel.sh), the stock modules are extracted and mapped, the
 device tree is out of the stick, and execution is BLOCKED at BL31, which is
 secure-fused and refuses unsigned images. not an address problem. the U-Boot
 fragment found in RAM does not change that: it is the secure-storage interface,
 not the key, and AML_DATA_PROCESS is not in the dump.

 what's actually true right now:

   kernel exploit path : trigger/reachability known, primitive not demonstrated,
                         oracle unstable, no root
   BL31 path           : strong U-Boot/Amlogic anchor, secure-storage functions
                         identified, call graph incomplete, secure-boot bypass
                         NOT demonstrated
   DTS/DTB             : runtime DTB recovered from RAM, first DTS sketch done,
                         many nodes now checkable against real data, exact
                         vendor source still unavailable
   KernelSU/APatch     : plausible for a rebuilt kernel, still needs a path to
                         run modified kernel code

 bootloader crypto status (rounds 28-30): the whole aml_encrypt_gxl pipeline
 is reconstructed and test-pinned (reports/round29-bootloader-crypto.md); the
 single missing input is the 32-byte aeskey tail of the OEM aml-user-key.sig.
 round 30 exhausted public provenance for it: no public copy of the PI.2055
 build, no aquaman key package anywhere, the one public production key
 (superbird) tested oracle-negative, and the pipeline was reproduced
 end-to-end offline with that public key. verdict:
 reports/round30-firmware-provenance.md — CRYPTOGRAPHICALLY CLOSED.

 full writeup: reports/provenance.md

how i unlocked the bootloader:
[bootloader_unlock](https://github.com/keyarr/aquaman-pi2055-research/blob/main/reports/bootloader_unlock.md)
