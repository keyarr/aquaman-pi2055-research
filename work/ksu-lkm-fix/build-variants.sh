#!/bin/bash
set -eu

ROOT=/home/erick/Documentos/projetos/aquaman_9_PI_2055
WORK=$ROOT/work/ksu-lkm-fix
KDIR=$ROOT/.src/linux-amlogic
OBJ=$WORK/kernel-obj
M=$WORK/ksu-skeleton
CROSS=$ROOT/.src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu-

build() {
	local out=$1
	shift
	find "$M" -name '*.o' -delete
	rm -f "$M/kernelsu.ko"
	make -C "$KDIR" O="$OBJ" M="$M" ARCH=arm64 CROSS_COMPILE="$CROSS" \
		HOSTCFLAGS=-fcommon "$@" modules > "$WORK/build-$out.log" 2>&1
	cp "$M/kernelsu.ko" "$WORK/$out.ko"
	sha256sum "$WORK/$out.ko" | tee -a "$WORK/HASHES.txt"
}

: > "$WORK/HASHES.txt"
echo "# kernel module candidates ($(date -u +%Y-%m-%dT%H:%M:%SZ))" >> "$WORK/HASHES.txt"
sha256sum "$WORK/ref/kernelsu_stock_img.ko" >> "$WORK/HASHES.txt"

build kernelsu-control
build kernelsu-persist KSU_ALLOWLIST_IO_VIA_KSUD=1 KSU_NO_EXT4_SYSFS_NUKE=1
