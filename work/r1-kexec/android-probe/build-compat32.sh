#!/bin/sh
# PREPARATION ONLY - build a static ARM EABI /init and a newc initrd.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
NDK=/home/erick/Android/Sdk/ndk/28.2.13676358/toolchains/llvm/prebuilt/linux-x86_64/bin
OUT="$HERE/initrd-compat32.cpio.gz"
"$NDK/clang" --target=armv7a-linux-androideabi21 -nostdlib -fno-builtin \
	-c "$HERE/compat32.S" -o "$HERE/compat32.o"
"$NDK/ld.lld" -m armelf_linux_eabi -nostdlib -static \
	-T "$HERE/compat32.ld" "$HERE/compat32.o" -o "$HERE/compat32"
"$NDK/llvm-readelf" -hW "$HERE/compat32" | grep -E 'Class:|Machine:|Type:|Entry point'
"$NDK/llvm-readelf" -lW "$HERE/compat32" | grep -E 'LOAD'
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cp "$HERE/compat32" "$TMP/init"
chmod 755 "$TMP/init"
(cd "$TMP" && printf 'init\0' | cpio -o --null --quiet -H newc) >"$HERE/initrd-compat32.cpio"
gzip -9 -n -c "$HERE/initrd-compat32.cpio" >"$OUT"
echo "== built $OUT ($(stat -c %s "$OUT") bytes)"
sha256sum "$OUT"
