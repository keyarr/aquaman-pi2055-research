#!/bin/sh
# PREPARATION ONLY - build the userspace watchdog wrapper and its initrd.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../../.." && pwd)
TC="$REPO/.src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu-"
SRC_RAMDISK="$REPO/patched_unpack/ramdisk"
OUT="$HERE/initrd-watchdog.cpio.gz"

"${TC}as" -o "$HERE/watchdog.o" "$HERE/watchdog.S"
"${TC}ld" -e _start -Ttext=0x400000 -o "$HERE/watchdog" "$HERE/watchdog.o"
chmod 755 "$HERE/watchdog"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
(cd "$TMP" && cpio -idm --quiet < "$SRC_RAMDISK") || true
[ -f "$TMP/init" ] || { echo "FATAL: ramdisk /init missing" >&2; exit 1; }
mv "$TMP/init" "$TMP/realinit"
chmod 755 "$TMP/realinit"
cp "$HERE/watchdog" "$TMP/init"
chmod 755 "$TMP/init"
(cd "$TMP" && find . -mindepth 1 -print0 | cpio -o --null --quiet -H newc) >"$HERE/initrd-watchdog.cpio"
gzip -9 -c "$HERE/initrd-watchdog.cpio" >"$OUT"

echo "== built $OUT ($(stat -c %s "$OUT") bytes)"
sha256sum "$OUT"
