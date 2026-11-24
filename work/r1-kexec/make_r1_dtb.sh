#!/bin/sh
# Build the R1 DTB with the FULL live cmdline (including dm= and root=/dev/dm-0).
# Only differences vs live cmdline: selinux permissive, loglevel=8, r1probe marker.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
SRC_DTB="${SRC_DTB:-$REPO/artifacts/aquaman.dtb}"
CMDLINE_FILE="${CMDLINE_FILE:-$HERE/cmdline-r1.txt}"
OUT_DTB="${OUT_DTB:-$HERE/aquaman-r1-full.dtb}"
DTC="${DTC:-dtc}"

fail() { echo "FATAL: $*" >&2; exit 1; }

command -v "$DTC" >/dev/null 2>&1 || fail "dtc not found"
[ -f "$SRC_DTB" ] || fail "source DTB missing: $SRC_DTB"
[ -f "$CMDLINE_FILE" ] || fail "cmdline file missing: $CMDLINE_FILE"

CMDLINE=$(cat "$CMDLINE_FILE")
# Escape for a dts C-style string: backslash first, then double quote.
ESC=$(printf '%s' "$CMDLINE" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

"$DTC" -f -I dtb -O dts -o "$TMP/in.dts" "$SRC_DTB"
grep -q '/chosen' "$TMP/in.dts" && fail "source DTB already has /chosen"

{
	printf '\tchosen {\n'
	printf '\t\tbootargs = "%s";\n' "$ESC"
	printf '\t};\n'
	printf '\n'
} >"$TMP/chosen.txt"

CHOSEN_FILE="$TMP/chosen.txt"
export CHOSEN_FILE
awk 'BEGIN { while ((getline line < ENVIRON["CHOSEN_FILE"]) > 0) block = block line "\n" }
     !done && /^\t.*\{/ { printf "%s", block; done = 1 }
     { print }
     END { if (!done) exit 2 }' "$TMP/in.dts" >"$TMP/final.dts"

# Stock DTB has one empty-name node (/@c1108d80); dtc 1.8.1 errors but emits a
# byte-identical tree when forced.
"$DTC" -f -I dts -O dtb -o "$OUT_DTB" "$TMP/final.dts"
"$DTC" -f -I dtb -O dtb -o /dev/null "$OUT_DTB"

echo "== DTB written: $OUT_DTB ($(stat -c %s "$OUT_DTB") bytes)"
echo "== round-trip OK"
