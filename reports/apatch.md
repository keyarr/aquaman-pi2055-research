# apatch — FEASIBILITY: VIABLE WITH SOURCE (custom recompiled kernel)

docs: https://apatch.dev/install.html, https://github.com/bmax121/APatch

requirements: arm64 ONLY. Android kernel 3.18–6.12. KALLSYMS=y + (ALL=y or ALL=n with initial support). No kprobes requirement — KernelPatch resolves symbols via kallsyms at patch time.

device: arm64 ok. 4.9.113 within 3.18–6.12 ok. KALLSYMS=y + ALL=y + BASE_RELATIVE=y ok. KPROBES=n is irrelevant for APatch.

however: APatch does not solve AMLSECU. The stock kernel is ciphertext (magic AMLSECU! ver 0x905, 3 blocks, timestamp 2022090612544443, entropy 8.0) — direct patching of the stock boot.img is impossible. The flow would have to be: source + custom rebuild (maintaining KALLSYMS_ALL=y) + AMLSECU packaging + fastboot boot. To the question "Does APatch work on this kernel?", the answer is yes for a rebuild with matching config; for the current encrypted blob, injecting anything without the key is impossible.

classification: VIABLE WITH SOURCE (custom rebuild + repackaging; never direct patch on current ciphertext blob).

# amlsecu — what is missing (without attempting to break anything)

header (LE offsets, from cmd_imgread.c + local parser):
magic 8s @0x00 = AMLSECU!, version u32 @0x08 = 0x905, nBlkCnt @0x0c = 3, timestamp ascii @0x10 (boot 2022090612544443, recovery 2022090613082318),
blk0 kernel @0x20 (off 0x800 raw 0x9589d1=9800145 tot 0x959000=9801728),
blk1 ramdisk @0x80 (boot all zeroes; recovery off 0x959800 raw 0x651235 tot 0x651800=6625280),
blk2 dtb @0xe0 (off 0x959800 raw 0xe820=59424 tot 0xf000=61440).
second (61440) = encrypted blk2 without header. dt.img (59424) = raw payload of blk2. dtbo.img = empty plaintext with AVB.
boot kernel sha256 3ebb0b28...e9e != recovery f9ff8d05...7 (almost all payload bytes differ, not just timestamp). magisk_patched modifies only ramdisk (kernel byte-for-byte identical).

to produce a bootable component, the following are missing:
1. Image + DTB recompiled from the matching source,
2. Closed tool aml_encrypt_gxb/gxl/g12a (--imgsig --amluserkey <key.sig>) + vendor user-key (derived from eFuse, never published),
3. Or bootloader that accepts unencrypted images (not the case here: U-Boot 2015.01-g7ac5df7677-dirty expects AMLSECU).
Public tools (gxlimg, meson-tools, BMU, FIP-hack, AIK) only cover bootloader FIP (--bootsig/--bl2sig), never kernel --imgsig. topjohnwu/Magisk#2555 and XDA confirm the dead end.
Public source code for the format: parser side only (U-Boot cmd_imgread.c, local tools/analyze_android_boot.py). Re-encryption: nothing public.
