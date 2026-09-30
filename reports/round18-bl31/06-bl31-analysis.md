.src/u-boot-khadas/fip/gxl/bl31.bin len=0x2c3a8 AMLSECU=True 0x820000ff-words=0 smc#0=0 eret=2
.src/u-boot-khadas/fip/gxb/bl31.bin len=0x16120 AMLSECU=True 0x820000ff-words=0 smc#0=0 eret=2
gxl strings: bl31 reboot reason / [BL31]: GXL CPU setup / teedata /
  AMLSECU! / Amlogic-secure-boot-module-v0.4 / flash-too-large / storage-larger-than-flash /
  opteed_std+opteed_fast / PSCI no-System-Off/Reset-hook errors.
gxb adds: exceed max DMA SHA2/AES length (crypto helpers, unlinked).
dispatcher: table-driven SiP/runtime-service; no literal 0x820000ff compare isolated,
no call edge from a 0x820000ff dispatch to AMLSECU/secureboot code established.
comparative only: must not be cited as aquaman BL31 behavior.

