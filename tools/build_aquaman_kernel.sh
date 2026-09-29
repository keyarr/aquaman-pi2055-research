#!/bin/sh
# build_aquaman_kernel.sh - reproducible 4.9.113 Image/DTB/modules for aquaman
#
# source: McMCCRU/linux-amlogic @ 3d4ab79e (ANCESTRAL, not the exact source
# that built the stock kernel -- see reports/provenance.md)
# toolchain: Linaro 6.3.1-2017.02, the exact gcc in the stock build string
#
# no sudo, no network, no || true. any failure is fatal on purpose: a build
# that hides errors is worse than no build for research.
#
# usage: tools/build_aquaman_kernel.sh [--clean]

set -eu

REPO=$(cd "$(dirname "$0")/.." && pwd)
SRC="$REPO/.src/linux-amlogic"
TOOLCHAIN="$REPO/.src/MiTV_OpenSource/cross_compile_tool"
OBJ="$REPO/build-aq"
LOGDIR="$REPO/out/build-logs"
EXPECTED_COMMIT=3d4ab79ea3638850a736bf2f7f65e55cb47368c4
JOBS=$(nproc 2>/dev/null || echo 4)

if [ "${1:-}" = "--clean" ]; then
	echo "== clean: removing $OBJ"
	rm -rf "$OBJ"
fi

mkdir -p "$LOGDIR"

fail() {
	echo "FATAL: $*" >&2
	exit 1
}

# ---- 1. validate dependencies -------------------------------------------
for t in make git gcc python3 dtc; do
	command -v "$t" >/dev/null 2>&1 || fail "missing tool: $t"
done
[ -d "$SRC" ] || fail "source not found at $SRC (git clone McMCCRU/linux-amlogic)"
[ -x "$TOOLCHAIN/bin/aarch64-linux-gnu-gcc" ] || fail "toolchain missing at $TOOLCHAIN"

# ---- 2. validate source/commit ------------------------------------------
COMMIT=$(git -C "$SRC" rev-parse HEAD)
echo "== source commit: $COMMIT"
[ "$COMMIT" = "$EXPECTED_COMMIT" ] || fail "commit drift: $COMMIT != $EXPECTED_COMMIT"

SUBLEVEL=$(sed -n 's/^SUBLEVEL *= *//p' "$SRC/Makefile" | head -1)
echo "== kernel sublevel: $SUBLEVEL"
[ "$SUBLEVEL" = "113" ] || fail "not 4.9.113 (SUBLEVEL=$SUBLEVEL)"

# the vendored Linaro toolchain ships liblto_plugin.so.0.0.0 without the
# .so symlink the gcc driver looks for during linking. research copy, so
# patching it is fine -- it is not upstream and not shared.
LTO="$TOOLCHAIN/libexec/gcc/aarch64-linux-gnu/6.3.1"
[ -e "$LTO/liblto_plugin.so" ] || ln -s liblto_plugin.so.0.0.0 "$LTO/liblto_plugin.so"

CROSS_COMPILE="$TOOLCHAIN/bin/aarch64-linux-gnu-"
# 4.9's bundled dtc does not link against host gcc >= 10
HOSTCFLAGS="-fcommon"

# ---- 3. config ------------------------------------------------------------
if [ ! -f "$OBJ/.config" ]; then
	echo "== generating meson64_defconfig"
	make -C "$SRC" ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE" \
		HOSTCFLAGS="$HOSTCFLAGS" O="$OBJ" meson64_defconfig \
		>"$LOGDIR/01-defconfig.log" 2>&1 || fail "defconfig failed, see $LOGDIR/01-defconfig.log"
fi

# three deltas, all documented in reports/kernel-build-env.md
#   VDEC_VP9  - broken at this tip (gvs undeclared in vvp9.c), device has no VP9
#   VIDEOSYNC - video_sink calls videosync_pcrscr_update unguarded, link fails.
#               device has neither: Xiaomi reorganised the media Kconfig
#   AMLOGIC_DVB - the only one that moves AWAY from the device, and the only
#               honest option: HEAD commit 3d4ab79e backported the DVB/CAM
#               driver but not the UAPI it needs (CA_CW_DES_*, CA_CW_SM4_*,
#               ca_descr_ex.mode, CA_DSC_IDSA do not exist in this tree's
#               include/uapi/linux/dvb/ca.h). -D on the command line does not
#               help, the values simply are not in the header. the alternative
#               is inventing values in a public UAPI struct, so the module is
#               dropped instead. device has CONFIG_AMLOGIC_DVB=y.
sed -i 's/^CONFIG_AMLOGIC_MEDIA_VDEC_VP9=y/# CONFIG_AMLOGIC_MEDIA_VDEC_VP9 is not set/' "$OBJ/.config"
sed -i 's/^# CONFIG_AMLOGIC_VIDEOSYNC is not set/CONFIG_AMLOGIC_VIDEOSYNC=y/' "$OBJ/.config"
sed -i 's/^CONFIG_AMLOGIC_DVB=y/# CONFIG_AMLOGIC_DVB is not set/' "$OBJ/.config"

echo "== olddefconfig"
make -C "$SRC" ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE" \
	HOSTCFLAGS="$HOSTCFLAGS" O="$OBJ" olddefconfig \
	>"$LOGDIR/02-olddefconfig.log" 2>&1 || fail "olddefconfig failed"

# ---- 4. build ------------------------------------------------------------
echo "== building Image + dtb + modules (-j$JOBS), this takes a while"
make -C "$SRC" ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE" \
	HOSTCFLAGS="$HOSTCFLAGS" O="$OBJ" Image dtbs modules -j"$JOBS" \
	>"$LOGDIR/03-build.log" 2>&1 || fail "build failed, see $LOGDIR/03-build.log"

# ---- 5. validate artifacts ----------------------------------------------
python3 "$REPO/tools/validate_artifacts.py" "$OBJ" | tee "$LOGDIR/04-validate.log"
