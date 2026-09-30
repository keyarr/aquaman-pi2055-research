bootloader.img                                             EXACT AQUAMAN image    0x148200  xiaomi aquaman bootloader (1.3 MiB); encrypted at rest, TOC frag at 0x4bebe, no FIP magic, no plaintext BL31
boot.img                                                   EXACT AQUAMAN image    0x1000000  aquaman boot.img; AMLSECU! 0x0905 container at 0x800 (kernel+dtb, xiaomi ts 2022090612544443); payloads encrypted
recovery.img                                               EXACT AQUAMAN image    0x1800000  aquaman recovery.img; same AMLSECU! shape (kernel+ramdisk+dtb, ts 2022090613082318); payloads encrypted
dt.img                                                     EXACT AQUAMAN image    0xe820  aquaman dt partition (59424 B); encrypted at rest, no FDT magic, no AMLSECU magic
artifacts/aquaman.dtb                                      EXACT AQUAMAN runtime  0xe3a8  decrypted runtime DTB recovered at 0x01000000 (secmon/secos/psci/partitions nodes, see dtb verb)
artifacts/aquaman.dts                                      EXACT AQUAMAN runtime  0xfe1c  text reconstruction of the runtime DTB
reports/round14-bl33-persist/bl33-37e18000.bin             EXACT AQUAMAN BL33     0x1d8000  relocated BL33 DRAM copy 0x37e18000..0x37ff0000; caller side of 0x820000ff, not a BL31 source
.src/u-boot-khadas/fip/gxl/bl31.bin                        FAMILY GXL/GXB         0x2c3a8  khadas GXL reference BL31 (0x2c3a8); AMLSECU/secureboot strings, no 0x820000ff word, no smc #0
.src/u-boot-khadas/fip/gxl/bl31.img                        FAMILY GXL/GXB         0x2c5a8  FIP wrapper around the GXL reference
.src/u-boot-khadas/fip/gxb/bl31.bin                        FAMILY GXL/GXB         0x16120  khadas GXB reference BL31 (0x16120); same shape + DMA SHA2/AES neighbor strings
.src/u-boot-khadas/fip/gxb/bl31.img                        FAMILY GXL/GXB         0x16320  FIP wrapper around the GXB reference
.src/u-boot-khadas/fip/gxl/bl2.bin                         FAMILY GXL/GXB         0x95c0  reference BL2 (loads FIP, not aquaman behavior)
.src/u-boot-khadas/fip/gxl/bl30.bin                        FAMILY GXL/GXB         0x9784  reference SCPI/bl30 (not BL31)
.src/u-boot-khadas/fip/gxb/bl2.bin                         FAMILY GXL/GXB         0x9580  reference BL2
.src/u-boot-khadas/fip/gxb/bl30.bin                        FAMILY GXL/GXB         0x9820  reference SCPI/bl30
.src/u-boot-khadas/arch/arm/include/asm/arch-gxl/bl31_apis.h GENERIC/FAMILY header  0x1033  caller-side SMC id + type constants (AML_DATA_PROCESS 0x820000ff); not BL31 behavior
.src/u-boot-khadas/common/cmd_rsvmem.c                     GENERIC/FAMILY source  0x1e90  BL33 rsvmem source matching the image strings; reads HW regs, patches DTB

EXACT AQUAMAN BL31 binary/dump/map/objdump: ABSENT (no file above is one).

