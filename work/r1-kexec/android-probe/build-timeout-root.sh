#!/bin/sh
# PREPARATION ONLY - build the timeout init wrapper and its initrd.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../../.." && pwd)
TC="$REPO/.src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu-"
OUT="$HERE/initrd-realinit-timeout.cpio.gz"

"${TC}as" -o "$HERE/timeout-root.o" "$HERE/timeout-root.S"
"${TC}ld" -e _start -Ttext=0x400000 -o "$HERE/timeout-root" "$HERE/timeout-root.o"
chmod 755 "$HERE/timeout-root"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cp "$HERE/timeout-root" "$TMP/init"
chmod 755 "$TMP/init"
(cd "$TMP" && printf 'init\0' | cpio -o --null --quiet -H newc) >"$HERE/initrd-realinit-timeout.cpio"
gzip -9 -n -c "$HERE/initrd-realinit-timeout.cpio" >"$OUT"

echo "== built $OUT ($(stat -c %s "$OUT") bytes)"
sha256sum "$OUT"
