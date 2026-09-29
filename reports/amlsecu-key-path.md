# amlsecu-key-path — where the user-key comes from

## what the user-key is (STRONG EVIDENCE)

The `aml-user-key.sig` file, vendor RSA key, used at both ends:

```bash
aml_encrypt_<soc> --efsgen --amluserkey aml-user-key.sig \
  --output SECURE_BOOT_SET            # pattern burned into efuse
aml_encrypt_<soc> --imgsig --amluserkey aml-user-key.sig \
  --input boot.img --output boot.img.encrypt   # AMLSECU! container
```

Sources: hardkernel/buildroot `aml_upgrade_pkg_gen.sh`, onethingcloud-oes-linux, LibreELEC `amlogic-boot-fip/gxl.inc`.
The SHA256 hash of the RSA keys goes into the eFuse (`0x140-0x160 rsa hash of all rsa keys`, Raxone/Amlogic-efuse). The `szSHA2KeyID` in our dump (`ef8996bd...`, identical across all 5 non-empty blocks) has the exact format of one of these identifiers: 32 bytes, constant per firmware, zeroed in the empty block. Interpretation: it is the KeyID of the user-key, not a payload hash.

## where the key lives at boot (STRONG EVIDENCE)

* eFuse/OTP is the root: `is_secure_boot_enabled()` reads `AO_SEC_SD_CFG10` bit 4 (khadas) or OTP license bits `FEAT_ENABLE_DEVICE_SCS_SIG_*` (S4 `aml_efuse.c`). Documented eFuse layout (Raxone): `0x20-0x40 aeskey`, `0x40-0x50 aeskey iv`, `0xa0-0xc0` secure level, `0x140-0x160` RSA keys hash.
* Access is always via SMC (`aml_sec_boot_check` -> `smc #0`, `x0=AML_DATA_PROCESS`). Normal world passes buffer+type; BL31/BL32 uses DMA + crypto engine with the key derived from eFuse. The plaintext key never appears in U-Boot (there is no key reading in `cmd_imgread.c`; only magic/version/size).
* In kernel, `CONFIG_AMLOGIC_SEC/TEE/EFUSE` + `unifykey` show the secondary access: `KEY_EFUSE` / `KEY_SECURE` keys (only SHA256 hash leaves to normal world, never the secret). Consistent with the same design.

## algorithm (WEAK EVIDENCE -> NOT PROVEN)

* The `--aeskey enable` flag in `--bootsig` and the `aeskey`/`aeskey iv` fields in eFuse prove AES in the bootloader secure boot (BL2 uses AES-256-CBC according to reversing-gxbb-bl2; Raxone tool extracts `bl2aeskey`, `bl2aesiv`, `bl3xaeskey`, `kernelaeskey`).
* For the `--imgsig` payload (kernel/ramdisk/dtb), no public source names the cipher mode. AES is the obvious inference (hardware engine exists, keys exist, 8.0 entropy, alignment preserved), but mode (CBC/CTR/XTS?), per-block IV/nonce, and exact derivation (key ladder? TEE? per-chip salt?) are unknown. The zeroed `szSHA2IMG` eliminates "plaintext hash in header" as an offline verification oracle.
* 512-byte signature at +0x600: size is compatible with RSA-4096. Unconfirmed; could be another scheme. Treat as opaque.

## the 9 questions of PHASE 4

1. Fixed per model — WEAK EVIDENCE (identical KeyID in boot+recovery of the same build; Xiaomi generates a user-key per product/line, but without a leaked `aml-user-key.sig` there is no definitive proof).
2. Fixed per firmware — WEAK EVIDENCE (same KeyID in both PI.2055 images; expected if the key is per product).
3. Per device — NOT PROVEN (nothing in the container varies by serial; chipid exists in eFuse `0x04-0x20` but no header field references it).
4. Derived from eFuse — STRONG EVIDENCE (verification root is OTP bits; aeskey lives in eFuse).
5. eFuse + salt — NOT PROVEN.
6. Obtained from TEE — STRONG EVIDENCE as the executor (SMC/BL32), but "obtain" is the wrong verb: TEE does not hand it out, it uses it internally.
7. Secure storage — WEAK EVIDENCE (unifykey `KEY_SECURE` exists in the kernel; role during early boot is undocumented).
8. Key ladder — NOT PROVEN (term appears in BSP, without binding to `--imgsig` in public source).
9. Combination — Honest inference: eFuse (AES key + RSA hash + secure level) + vendor RSA user-key + crypto inside secure world. The exact link between them is proprietary and closed.

## practical consequence

Even if the key were per-model (the best case for us), it is not in any public artifact: local `bootloader.img` is ciphertext without strings, aquaman's `aml-user-key.sig` was never leaked, and the BL31 executing the key check is a closed binary. Without it, `--imgsig` is not reproducible and brute force is infeasible (128/256-bit keyspace, no fast oracle).
