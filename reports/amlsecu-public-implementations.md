# amlsecu-public-implementations — who uses the same format

## 0x0905 and common Amlogic family (CONFIRMED)

The trio: magic `AMLSECU!` + `0x0905` + `t_aml_enc_blk` is byte-identical in:

* khadas/u-boot `common/cmd_imgread.c` (VIM, GXL/GXM).
* nest-open-source manifest_repos/u-boot `cmd/amlogic/imgread.c`.
* AOSP `platform/external/u-boot` branches android-tv-9 / tv-s-beta3
  (`common/cmd_imgread.c` + `AmlSecureBootImg9Header` with reserve 2048).
* CoreELEC bl301 (commits PD#132936, PD#137972: DTB encrypted along with kernel,
  `imgread dtb` with decrypt).

Conclusion: `0x0905` is not a Xiaomi custom format. It is standard Amlogic versioning
from the Android 9 era, shared across GXB/GXL/GXM and derivatives (S805Y is
GXL). Its presence on aquaman does not indicate a unique vendor fork.

## products facing the same issue

* Mi Box 3 / 3S (MDZ-19-AA, S905X-H): Magisk issue #2555 (2020).
  Encrypted ramdisk, `bad cpio header`, AIK fails to recognize. topjohnwu
  closed as unsupported: without the key, there is no decryption. Same conclusion
  as this report, 6 years prior, on another SoC in the same family.
* AIK (osm0sis) documents: "Xiaomi Mi Box 3S, ZTE B860H STB — special
  image signing adds AMLSECU! ... ramdisk cannot be unpacked or
  modified".
* Antminer S19 XP (Bitmain, Amlogic control board): open source parser
  HashSource/BMU (fork of AnatolyGeorgievski/BMU) reads the same header
  (`version 905`, blocks with data offset / raw length / total length)
  and extracts kernel/ramdisk/second. Useful as an independent parser implementation,
  but does not decrypt (the `key1/key2` keys there belong to Bitmain's scheme, not Amlogic).
* Yandex Station / Quasar (Amlogic): reports of `boot.img.encrypt` /
  `dtb.img.encrypt` with `AMLSECU!` visible in dump. Same scheme.

## tooling: existing vs missing

| tool | coverage | useful for aquaman? |
|---|---|---|
| `aml_encrypt_gx* --bootsig/--efsgen` (Amlogic binary, requires `aml-user-key.sig`) | FIP + eFuse pattern | only with Xiaomi's key |
| `aml_encrypt_gx* --imgsig` (same) | AMLSECU! container | same — the missing piece |
| `gxlimg` (repk, open) | bl2/bl3x/fip without key (GXL) | does not do imgsig |
| `meson-tools amlbootsig/amlinfo` (afaerber) | unsigned/sha256 FIP | does not do imgsig |
| `meson64-tools` (angerman) | G12B/G12A/SM1 | does not do imgsig |
| BMU `bmu_parser` (HashSource) | parses 905 header | parse ok, no decryption |
| `tools/parse_amlsecu.py` (this repo) | parses 905 header | parse ok, no decryption |

`amlogic-boot-fip` (LibreELEC) distributes `aml_encrypt_gxl` binaries,
etc., but without any `aml-user-key.sig` (each vendor protects their own).
Having the binary does not help without the key.

## TEE (summary of PHASE 5)

`aml_sec_boot_check` = SMC `AML_DATA_PROCESS` to closed BL31/BL32.
Classification: C (secure world executes the entire decryption; U-Boot only
measures size and executes flush_cache). The key never leaves the TEE/secure monitor
in any documented flow. Offline re-implementation would require the key
(`kernelaeskey` vector, cf. Raxone usbdl) or BL31 itself — both
unreachable without USB reboot exploit (out of scope: requires power cycling
and physical boot mode).
