#!/usr/bin/env python3
"""Fastboot address arithmetic for the GXL 2015.01 fork.

Two things this exists to settle, both pure arithmetic:
  1. what CONFIG_USB_FASTBOOT_BUF_ADDR must be, given the max-download-size
     the device reported (inverts ddr_size_usable from f_fastboot.c)
  2. whether the reported max-download-size is even consistent with the
     download buffer sitting at loadaddr

usage: fastboot_addr.py [--dram 0x40000000] [--max-download-size 0x08000000]
                        [--loadaddr 0x01080000]
prints the whole address model, no device access.
"""
import sys

# f_fastboot.c:132-142 (khadas/u-boot @ khadas-vims-nougat, 2015.01)
DRAM_UBOOT_RESERVE = 0x01000000
# arch/arm/include/asm/arch-gxl/cpu.h:33
MALLOC_LEN = 64 * 1024 * 1024
# board/amlogic/configs/gxl_p241_v1.h:469
MEM_TOP_HIDE = 0x08000000
# board/amlogic/configs/gxl_p241_v1.h:90
LOADADDR_DEFAULT = 0x01080000
# include/g_dnl.h:18
KCADAS_BUF_ADDR = 0x10200000


def ddr_size_usable(addr_start, dram):
    """Verbatim from drivers/usb/gadget/f_fastboot.c:133-142."""
    return (dram - DRAM_UBOOT_RESERVE - addr_start - MALLOC_LEN - MEM_TOP_HIDE)


def buf_addr_for_usable(usable, dram):
    """Invert the same expression."""
    return dram - DRAM_UBOOT_RESERVE - MALLOC_LEN - MEM_TOP_HIDE - usable


def opt(name, default):
    if name in sys.argv:
        return int(sys.argv[sys.argv.index(name) + 1], 0)
    return default


def main():
    dram = opt("--dram", 0x40000000)
    reported = opt("--max-download-size", 0x08000000)
    loadaddr = opt("--loadaddr", LOADADDR_DEFAULT)

    print("constants (khadas/u-boot, gxl 2015.01, reference only):")
    print("  DRAM_UBOOT_RESERVE     0x%08x  (16 MiB)" % DRAM_UBOOT_RESERVE)
    print("  CONFIG_SYS_MALLOC_LEN  0x%08x  (64 MiB)" % MALLOC_LEN)
    print("  CONFIG_SYS_MEM_TOP_HIDE 0x%08x (128 MiB)" % MEM_TOP_HIDE)
    print("  DRAM (aquaman)         0x%08x  (1 GiB, MemTotal 1004412 kB)" % dram)
    print()
    print("model: usable = DRAM - 16M - BUF - 64M - 128M")
    print()

    for name, addr in (("khadas g_dnl.h", KCADAS_BUF_ADDR), ("loadaddr", loadaddr)):
        print("  if BUF = %-16s 0x%08x -> max-download-size 0x%08x (%d MiB)"
              % (name, addr, ddr_size_usable(addr, dram),
                 ddr_size_usable(addr, dram) >> 20))

    implied = buf_addr_for_usable(reported, dram)
    print()
    print("  device reported max-download-size 0x%08x (%d MiB)"
          % (reported, reported >> 20))
    print("  -> if the device uses the khadas formula+constants, BUF = 0x%08x"
          % implied)
    match = [n for n, a in (("khadas g_dnl.h", KCADAS_BUF_ADDR), ("loadaddr", loadaddr))
             if ddr_size_usable(a, dram) == reported]
    print("  -> consistent with BUF == %s" % (", ".join(match) if match else
                                               "NEITHER known address"))

    print()
    if match == ["loadaddr"]:
        print("CONSISTENT with reports/buffer-equals-loadaddr-proof.md (BUF==loadaddr)")
    elif not match:
        print("INCONSISTENT with both BUF==loadaddr and BUF==khadas.")
        print("Either the device hardcodes/recomputes max-download-size, or its")
        print("ddr_size_usable constants differ from the reference tree.")
        print("bootloader.img is encrypted, so this cannot be settled from the dump.")


if __name__ == "__main__":
    main()
