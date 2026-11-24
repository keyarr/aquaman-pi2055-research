#!/bin/bash
set -eu

ROOT=/home/erick/Documentos/projetos/aquaman_9_PI_2055
WORK=$ROOT/work/ksu-lkm-fix
KDIR=$ROOT/.src/linux-amlogic
OBJ=$WORK/kernel-obj
M=$WORK/ksu-skeleton
CROSS=$ROOT/.src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu-

# 1. stock vmlinux + stock CRC map
[ -f "$WORK/stock_vmlinux.elf" ] || \
	"$HOME/.local/bin/vmlinux-to-elf" "$ROOT/artifacts/kernel_image.bin" "$WORK/stock_vmlinux.elf"
python3 "$WORK/make_symvers.py" "$WORK/stock_vmlinux.elf" "$OBJ/Module.symvers"

# 2. prepare objdir from the device config
[ -f "$OBJ/.config" ] || cp "$ROOT/aquaman-config" "$OBJ/.config"
make -C "$KDIR" O="$OBJ" ARCH=arm64 CROSS_COMPILE="$CROSS" HOSTCFLAGS=-fcommon olddefconfig modules_prepare
make -C "$KDIR" O="$OBJ" ARCH=arm64 CROSS_COMPILE="$CROSS" HOSTCFLAGS=-fcommon security/selinux/

# 3. this source tree selects CONFIG_CC_STACKPROTECTOR via STRONG; the stock
#    kernel does not, and the extra task_struct.stack_canary shifts every field
#    by 8 bytes. Drop the define; module CFLAGS use -fno-stack-protector.
sed -i '/^#define CONFIG_CC_STACKPROTECTOR 1$/d' "$OBJ/include/generated/autoconf.h"

# 4. build
find "$M" -name '*.o' -delete
rm -f "$M/kernelsu.ko"
make -C "$KDIR" O="$OBJ" M="$M" ARCH=arm64 CROSS_COMPILE="$CROSS" HOSTCFLAGS=-fcommon modules

cp "$M/kernelsu.ko" "$WORK/kernelsu-fixed.ko"
sha256sum "$WORK/kernelsu-fixed.ko"
