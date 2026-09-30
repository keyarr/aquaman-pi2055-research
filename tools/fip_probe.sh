#!/bin/sh
# Rebuilds the reference FIP whose ToC is stored as
# reports/round28-fip/ref5-toc.bin. Offline, vendor tools only, nothing from
# the device is touched. The bl32/bl33 payloads are random filler: only the
# ToC layout and the payload sizes matter for round 28.
set -e
FIP=.src/u-boot-khadas/fip
OUT=${TMPDIR:-/tmp}/round28-fip
mkdir -p "$OUT"

dd if=$FIP/gxl/bl2.bin  of="$OUT/bl2.bin"  bs=1 count=1 status=none
cp $FIP/gxl/bl2.bin $FIP/gxl/bl30.bin $FIP/gxl/bl31.img "$OUT/"
head -c 50000 /dev/urandom > "$OUT/f_bl32.bin"
head -c 70000 /dev/urandom > "$OUT/f_bl33.bin"

"$FIP/fip_create" --bl2 "$OUT/bl2.bin" --bl30 "$OUT/bl30.bin" \
                  --bl31 "$OUT/bl31.img" --bl32 "$OUT/f_bl32.bin" \
                  --bl33 "$OUT/f_bl33.bin" "$OUT/ref5.fip"

"$FIP/fip_create" --dump "$OUT/ref5.fip"
dd if="$OUT/ref5.fip" of=reports/round28-fip/ref5-toc.bin bs=1 count=256 status=none
sha256sum reports/round28-fip/ref5-toc.bin