#!/bin/sh
# PREPARATION ONLY - DO NOT EXECUTE ON DEVICE
# Build a static AArch64 /init and a newc initrd for the userspace probe.

set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../../.." && pwd)
TC="$REPO/.src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu-"
OUT="$HERE/initrd.cpio.gz"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

"$TC"as -o "$TMP/init.o" "$HERE/init.S"
"$TC"ld -nostdlib -static --build-id=none -Ttext=0x400000 \
	-o "$HERE/init" "$TMP/init.o"

"$TC"readelf -h "$HERE/init" | grep -E 'Entry point|Type:|Machine:'
"$TC"readelf -l "$HERE/init" | grep -E 'LOAD| VirtAddr|Align' 

python3 - "$HERE/init" "$HERE/initrd.cpio" <<'PY'
import os, sys

src, out = sys.argv[1], sys.argv[2]
data = open(src, 'rb').read()

def entry(name, mode, body):
    nameb = name.encode()
    hdr = (b'070701' + b'%08x' % 0 + b'%08x' % mode +
           b'%08x' % 0 + b'%08x' % 0 + b'%08x' % 1 + b'%08x' % 0 +
           b'%08x' % len(body) + b'%08x' % 0 + b'%08x' % 0 +
           b'%08x' % 0 + b'%08x' % 0 +
           b'%08x' % (len(nameb) + 1) + b'%08x' % 0)
    assert len(hdr) == 110, len(hdr)
    raw = hdr + nameb + b'\0'
    raw += b'\0' * ((-len(raw)) % 4)  # newc: pad name to 4 bytes
    raw += body
    return raw + b'\0' * ((-len(raw)) % 4)

blob = entry('init', 0o100755, data)
blob += entry('TRAILER!!!', 0, b'')
with open(out, 'wb') as f:
    f.write(blob)
print('init bytes:', len(data), 'cpio bytes:', len(blob))
PY

gzip -9 -n -c "$HERE/initrd.cpio" > "$OUT"
echo "== initrd: $OUT ($(stat -c %s "$OUT") bytes)"
sha256sum "$OUT"
