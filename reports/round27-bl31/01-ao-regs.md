# 01 — AO regs: register -> decoder -> semantics -> DTB

registers (`arch/arm/include/asm/arch-gxl/secure_apb.h:1602-1625`, FAMILY
STRUCTURAL REFERENCE; byte-verified offsets):

```text
0xC810024C  AO_SEC_GP_CFG3  (SEC alias 0xDA10024C)  sizes
0xC8100250  AO_SEC_GP_CFG4  (SEC alias 0xDA100250)  bl32 start
0xC8100254  AO_SEC_GP_CFG5  (SEC alias 0xDA100254)  bl31 start
```

live values (round 26, primitive 0x02):

```text
CFG3 = 0x0c008000   CFG4 = 0x05300000   CFG5 = 0x05000000
```

## decoder (EXACT AQUAMAN, disassembly of the persisted BL33)

`do_rsvmem_dump` @0x37e62eec:

```text
37e62f04  mov x0,#0x24c ; movk x0,#0xc810,lsl#16 ; ldr w19,[x0]   ; CFG3
37e62f10  mov x0,#0x254 ; movk x0,#0xc810,lsl#16 ; ldr w1,[x0]    ; CFG5 bl31 start
37e62f1c  mov x0,#0x250 ; movk x0,#0xc810,lsl#16 ; ldr w20,[x0]   ; CFG4 bl32 start
37e62f34  lsr w1,w19,#0x10 ; lsl w1,w1,#0xa                        ; bl31_size = hi16<<10
37e62f3c  bl printf("bl31 reserved memory start: 0x%08x\n", CFG5)
37e62f5c  ubfiz w1,w19,#0xa,#0x10                                  ; bl32_size = lo16<<10
```

`do_rsvmem_check` @0x37e62f78: same three reads first (0x37e62f80-0x37e62fbc),
then uses `w20=bl31_size w19=bl31_start w22=bl32_start w24=CFG3` to gate and
emit the fdt-set commands below.

source match: `.src/u-boot-khadas/common/cmd_rsvmem.c:53-57` (identical
masks/shifts, same print order) — FAMILY STRUCTURAL REFERENCE.

## field extraction

```text
CFG3 = 0x0c008000
  hi16 0x0c00 << 10 = 0x00300000   bl31 reserved size
  lo16 0x8000 << 10 = 0x02000000   bl32 reserved size
CFG5 = 0x05000000   bl31 reserved start
CFG4 = 0x05300000   bl32 reserved start
check: CFG5 + bl31_size == CFG4  (0x05000000+0x00300000 = 0x05300000) ✓
```

## semantic meaning -> DTB property (run_command templates in the same dump)

```text
strings @0x37ed4254.. : "fdt get value env_compatible /reserved-memory/linux,secmon compatible;"
  0x37ed42c7 "shared-dma-pool"  0x37ed42d7 "amlogic, aml_secmon_memory"
  0x37ed4329 "fdt set /reserved-memory/linux,secmon reg <0x0 0x%x 0x0 0x%x>;"
  0x37ed43ca "fdt set /reserved-memory/linux,secmon size <0x0 0x%x>;"
  0x37ed4470 "fdt set /reserved-memory/linux,secmon alloc-ranges <0x0 0x%x 0x0 0x%x>;"
  0x37ed44ef "fdt set /secmon reserve_mem_size <0x%x>;"
  0x37ed45ec "fdt set /reserved-memory/linux,secos reg <0x0 0x%x 0x0 0x%x>;"
  0x37ed46fa "fdt get value secmon_clear_range /secmon clear_range;"
  0x37ed4730 "fdt set /secmon clear_range <0x%x 0x%x>;"
```

live DTB result (`artifacts/aquaman.dtb`): alloc-ranges `0x05000000+0x400000`,
size `0x400000` (round-up of 0x300000), `/secmon reserve_mem_size 0x300000`,
secos reg `0x05300000+0x2000000` status=disable.

chain proven end-to-end: **AO register -> BL33 decoder -> fdt-set -> runtime
DTB property**. nothing stops at "looks like a base".
