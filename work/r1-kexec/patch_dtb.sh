#!/bin/sh
# PREPARATION ONLY - DO NOT EXECUTE ON DEVICE
# Offline DTB patcher: add /chosen/bootargs (and optional initrd pointers).

set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
SRC_DTB="${SRC_DTB:-$REPO/artifacts/aquaman.dtb}"
OUT_DTB="${OUT_DTB:-$HERE/aquaman-r1.dtb}"
DTC="${DTC:-dtc}"

# Stock cmdline from artifacts/aquaman-linux.dts, minus skip_initramfs.
CMDLINE="${CMDLINE:-init=/init loglevel=8 console=ttyS0,115200 no_console_suspend earlycon=aml_uart,0xc81004c0 ramoops.pstore_en=1 ramoops.record_size=0x8000 ramoops.console_size=0x4000 ro rootwait reboot_mode_android=normal androidboot.selinux=permissive logo=osd1,loaded,0x3d800000,1080p60hz maxcpus=4 vout=1080p60hz,enable hdmimode=1080p60hz androidboot.hardware=amlogic otg_device=1 buildvariant=user r1probe=DEADBEEF}"

# Set both to add linux,initrd-start / linux,initrd-end (physical addresses).
INITRD_START="${INITRD_START:-}"
INITRD_END="${INITRD_END:-}"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fail() { echo "FATAL: $*" >&2; exit 1; }

command -v "$DTC" >/dev/null 2>&1 || fail "dtc not found"
[ -f "$SRC_DTB" ] || fail "source DTB missing: $SRC_DTB"

if [ -n "$INITRD_START" ] || [ -n "$INITRD_END" ]; then
	[ -n "$INITRD_START" ] && [ -n "$INITRD_END" ] ||
		fail "set both INITRD_START and INITRD_END"
	CMDLINE=$(printf '%s\n' "$CMDLINE" | sed 's/skip_initramfs//g')
	START_HEX=$(printf '0x%x' "$INITRD_START")
	END_HEX=$(printf '0x%x' "$INITRD_END")
fi

"$DTC" -f -I dtb -O dts -o "$TMP/in.dts" "$SRC_DTB"
grep -q '/chosen' "$TMP/in.dts" && fail "source DTB already has /chosen"

# The live bootloader FDT reserves the whole 0x5000000..0x7400000 secure
# window for secmon (36 MiB pool, 35 MiB taken). artifacts/aquaman.dtb ships
# only 4 MiB / 3 MiB, which releases the 0x5300000..0x5400000 part back to the
# buddy allocator; PFN 0x5307 then get used as pagecache and faults on access.
sed -i \
	-e 's/reserve_mem_size = <0x300000>;/reserve_mem_size = <0x2300000>;/' \
	-e 's/size = <0x00 0x400000>;/size = <0x00 0x2400000>;/' \
	-e 's/alloc-ranges = <0x00 0x5000000 0x00 0x400000>;/alloc-ranges = <0x00 0x5000000 0x00 0x2400000>;/' \
	"$TMP/in.dts"
CHOSEN_FILE="$TMP/chosen.txt"
export CHOSEN_FILE
CMDLINE_DTS=$(printf '%s' "$CMDLINE" | sed 's/\\/\\\\/g; s/"/\\"/g')

{
	printf '\tchosen {\n'
	printf '\t\tbootargs = "%s";\n' "$CMDLINE_DTS"
	if [ -n "$INITRD_START" ]; then
		printf '\t\tlinux,initrd-start = /bits/ 64 <%s>;\n' "$START_HEX"
		printf '\t\tlinux,initrd-end = /bits/ 64 <%s>;\n' "$END_HEX"
	fi
	printf '\t};\n'
	printf '\n'
} >"$TMP/chosen.txt"

awk 'BEGIN { while ((getline line < ENVIRON["CHOSEN_FILE"]) > 0) block = block line "\n" }
     !done && /^\t.*\{/ { printf "%s", block; done = 1 }
     { print }
     END { if (!done) exit 2 }' "$TMP/in.dts" >"$TMP/final.dts"

# -f: the stock DTB contains one empty-name node (/@c1108d80); dtc 1.8.1
# reports it as an error but emits a byte-identical tree when forced.
"$DTC" -f -I dts -O dtb -o "$OUT_DTB" "$TMP/final.dts"
"$DTC" -f -I dtb -O dtb -o /dev/null "$OUT_DTB"

echo "== DTB written: $OUT_DTB ($(stat -c %s "$OUT_DTB") bytes)"
grep -E 'bootargs|initrd-(start|end)' "$TMP/final.dts"
