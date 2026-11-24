#!/bin/sh
# PREPARATION ONLY - build the pivot_root init wrapper and its initrd.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../../.." && pwd)
TC="$REPO/.src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu-"
OUT="$HERE/initrd-pivot2.cpio.gz"

"${TC}as" -o "$HERE/pivot-root.o" "$HERE/pivot-root.S"
"${TC}ld" -e _start -Ttext=0x400000 -o "$HERE/pivot-root" "$HERE/pivot-root.o"
chmod 755 "$HERE/pivot-root"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cp "$HERE/pivot-root" "$TMP/init"
chmod 755 "$TMP/init"
(cd "$TMP" && printf 'init\0' | cpio -o --null --quiet -H newc) >"$HERE/initrd-pivot2.cpio"
gzip -9 -n -c "$HERE/initrd-pivot2.cpio" >"$OUT"

echo "== built $OUT ($(stat -c %s "$OUT") bytes)"
sha256sum "$OUT"
