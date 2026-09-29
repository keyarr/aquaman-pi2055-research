#!/usr/bin/env bash
# Re-enter optimus v2 burning and run one optimus.py verb against it.
# The burning window is short and the auto-burn timeout closes it, so entry,
# trigger and the probe have to be one tight sequence.
#
#   optimus_enter.sh probe 0x20000000 0x30000000
#   optimus_enter.sh scan 0x3f000000 0x40000000 "U-Boot"
set -u
cd "$(dirname "$0")/.."
PW="${OPTIMUS_PW:-}"
OUT="${OPTIMUS_OUT:-/dev/stdout}"

{
  echo "=== session $(date +%s.%N) : $* ==="
  timeout 20 adb reboot fastboot 2>&1
  for _ in $(seq 1 40); do
    timeout 5 fastboot devices 2>/dev/null | grep -q . && break
    sleep 1
  done
  timeout 5 fastboot devices 2>&1
  echo "=== trigger $(date +%s.%N) ==="
  timeout 20 fastboot oem update 5000 2>&1
  for _ in $(seq 1 400); do
    lsusb 2>/dev/null | grep -q "ID 1b8e:c003" && break
    sleep 0.05
  done
  echo "=== optimus up $(date +%s.%N) ==="
  printf '%s\n' "$PW" | sudo -S python3 "${OPTIMUS_PY:-tools/optimus.py}" "$@" 2>&1
  echo "=== done $(date +%s.%N) ==="
  lsusb 2>/dev/null | grep -E "1b8e|18d1|2717" || echo "target gone from bus"
} > "$OUT" 2>&1
cat "$OUT"
