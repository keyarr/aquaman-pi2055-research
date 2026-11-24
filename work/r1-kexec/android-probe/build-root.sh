#!/bin/sh
# PREPARATION ONLY - build the root-mounting watchdog wrapper and its initrd.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../../.." && pwd)
TC="$REPO/.src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu-"
OUT="$HERE/initrd-watchdog-root.cpio.gz"

"${TC}as" -o "$HERE/watchdog-root.o" "$HERE/watchdog-root.S"
"${TC}ld" -e _start -Ttext=0x400000 -o "$HERE/watchdog-root" "$HERE/watchdog-root.o"
chmod 755 "$HERE/watchdog-root"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cp "$HERE/watchdog-root" "$TMP/init"
chmod 755 "$TMP/init"
(cd "$TMP" && printf 'init\0' | cpio -o --null --quiet -H newc) >"$HERE/initrd-watchdog-root.cpio"
gzip -9 -c "$HERE/initrd-watchdog-root.cpio" >"$OUT"

echo "== built $OUT ($(stat -c %s "$OUT") bytes)"
sha256sum "$OUT"
