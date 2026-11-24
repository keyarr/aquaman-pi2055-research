#!/bin/sh
# PREPARATION ONLY - DO NOT EXECUTE ON DEVICE
# Offline build + validation of the r1_kexec loadable module.

set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
SRC="$REPO/.src/linux-amlogic"
OBJ="$REPO/build-aq"
TC="$REPO/.src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu-"
MODDIR="$HERE/modules"
KO="$MODDIR/r1_kexec.ko"
EXPECTED_VERMAGIC="4.9.y SMP preempt mod_unload modversions aarch64"

fail() { echo "FATAL: $*" >&2; exit 1; }

[ -d "$SRC" ] || fail "kernel source missing: $SRC"
[ -d "$OBJ" ] || fail "build tree missing: $OBJ"
[ -x "${TC}gcc" ] || fail "cross compiler missing: ${TC}gcc"
[ -f "$OBJ/Module.symvers" ] || fail "Module.symvers missing (build the kernel first)"

echo "== building r1_kexec.ko"
make -C "$SRC" ARCH=arm64 CROSS_COMPILE="$TC" HOSTCFLAGS=-fcommon \
	O="$OBJ" M="$MODDIR" modules

[ -f "$KO" ] || fail "module was not produced: $KO"

echo "== modinfo"
modinfo "$KO" | grep -E '^(filename|name|license|depends|vermagic):'

VERMAGIC=$(modinfo "$KO" | awk -F: '/^vermagic:/{gsub(/^ +/,"",$2); print $2}')
[ "$VERMAGIC" = "$EXPECTED_VERMAGIC" ] ||
	fail "vermagic mismatch: got '$VERMAGIC', expected '$EXPECTED_VERMAGIC'"
echo "== vermagic OK: $VERMAGIC"

echo "== undefined symbols"
UNDEF=$(${TC}nm -u "$KO" | awk '{print $2}' | sed '/^$/d' | sort -u)
printf '%s\n' "$UNDEF"
BAD=""
for sym in $UNDEF; do
	case "$sym" in
		__this_module|__module_*|*strcmp*|*memcpy*|*memset*|*memmove*) continue ;;
	esac
	if ! grep -qw "$sym" "$OBJ/Module.symvers"; then
		BAD="$BAD $sym"
	fi
done
[ -z "$BAD" ] || fail "unresolved symbols:$BAD"

for sym in r1_dcache_clean_poc r1_icache_inval_all r1_install_idmap \
           r1_relocate_new_kernel; do
	${TC}nm "$KO" | grep -q " [Tt] $sym$" || fail "missing helper symbol: $sym"
done
echo "== helper symbols present, no unresolved kernel symbols"

echo "== OK: $KO"
