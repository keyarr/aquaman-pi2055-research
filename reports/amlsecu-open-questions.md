# amlsecu-open-questions — open questions and next steps

> **partially revoked, 2026-09-29.** Items 9 and 10 were incorrect and
> were corrected in place (see their text). The remainder of this file remains
> valid, including items 1-8, which cover the solid findings: container layout,
> SMC, absence of public tooling — none of that changed.
> Item 9 is the most expensive mistake in this repo because item 10 was built on
> top of it. Full context in `reports/fastboot-memory-flow.md` §6 and
> `reports/custom-kernel-execution.md`.

## direct answers (11 questions)

1. `0x0905` format: CONFIRMED (public structs + local parser matches both dumps; table in amlsecu-structure.md).
2. Algorithm: NOT PROVEN. AES is a strong inference (engine + eFuse aeskey + `--aeskey enable`), mode/IV/derivation unknown.
3. Where the key lives: root in eFuse/OTP, exclusive use in secure world via SMC (STRONG EVIDENCE). `szSHA2KeyID` (`ef8996bd...`) identifies the vendor user-key.
4. Key scope: per product/firmware is the honest assessment (WEAK EVIDENCE); per device, NOT PROVEN.
5. Does the key leave the TEE? Not in any documented flow. TEE/BL31 performs the decryption (Option C).
6. Public implementation to reproduce encrypt? NO. Parsers exist (BMU, parse_amlsecu.py); the `--imgsig` packer is closed.
7. Public tool equivalent to `aml_encrypt --imgsig`? NO (`gxlimg`/`meson-tools` do not cover imgsig).
8. Offline path to produce a valid image? NO, without aquaman's `aml-user-key.sig` (or the kernel-AES key extracted via exploit).
9. ~~Custom kernel accepted by `fastboot boot` without user-key?~~ **REVOKED. INCORRECT.** The original reading of this item was wrong and represents the most costly error in the repo, as it became the premise for item 10. The 4096-byte plaintext DID NOT execute: the device returned to Android in 16-21 s, identical to the INVALID control, with an empty `bootreason`. That timing is the **rejection** duration (`do_bootm` fails -> `do_reset`), not execution duration. The decisive test is M1b: identical stub with a 15x delay loop, and reboot timing did not shift at all. An executing payload does not return in rejection time. See `reports/fastboot-boot-verdict.md` (M1/M1b/M2/E1, all revoked) and `reports/fastboot-memory-flow.md` §6 for the explanation.
   What item 9 conflated: "U-Boot accepted download" and "bytes executed" are different. The download is accepted; execution is gated at BL31.
10. Real blocker for KernelSU/APatch: **also incorrect, due to item 9.** The blocker is NOT AMLSECU packaging alone, but neither is it "lack of functional kernel/DTB". It is BL31: `do_bootm` calls `aml_sec_boot_check` (SMC) prior to any format validation, and BL31 is secure-fused on this device. An AMLSECU signature is what it requires. See `reports/custom-kernel-execution.md` for the full matrix. Magisk/APatch patching stock `boot.img` remains infeasible (ramdisk ciphertext, #2555) — that part of the original item remains correct.
11. What lifts the blocker: (a) leaked `aml-user-key.sig` for aquaman/PI.2055; (b) kernel-AES key extracted via BootROM USBDL exploit (Raxone, fredericb) — requires physical reboot, currently out of scope; (c) proof that `secure=no` + unlocked accepts plaintext under `fastboot boot` — requires an authorized test boot, also out of scope currently.

## inference vs unknown (summary)

* Proven: layout, size semantics, offsets, constant KeyID, 512 B signature, imgread->SMC flow, absence of public tooling.
* Inference: AES in payload, RSA-4096 in signature, key per product.
* Unknown: AES mode, IV, exact key ladder, BL31 contents, exact behavior of `fastboot boot` with plaintext on this unit.

## highest-value offline next step (without touching device)

1. Extract `build.prop` / userspace TA/TEE (`tee-supplicant`, keybox, widevine) from `system/vendor/odm` (local `*.new.dat.br` dumps) to check if any UUID/TA references the user-key — zero cost, decompression only.
2. Search for `aml-user-key*.sig` / `SECURE_BOOT_SET` / `aml_encrypt_gxl` in public aquaman dumps/OTAs (XDA/Yandex) — unlikely, but cheap.
3. Construct a plaintext test `boot.img` (mainline kernel + minimal ramdisk) ready for future authorized `fastboot boot` — without executing now.

## what NOT to do

* No `fastboot boot/flash/erase/reboot`, `saveenv`, `setenv`, `oem` fuzzing, or `current-slot`: all reset or modify device state.
* No brute force of key (no oracle, infeasible keyspace).
* Do not compile kernel or build flash images in this phase.
