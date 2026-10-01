#!/usr/bin/env bash
# e3.sh - cold_boot vs normal, with and without the flag. four runs, one watcher.
#
# round 36 §5 predicts that once FORCE_USB_BOOT is armed, `reboot normal`
# (PSCI x1=1) wedges exactly like `reboot cold_boot` (x1=0), because the mode
# lands in RTI_STATUS_REG3[3:0] and SD_CFG15[15:12], and neither of bl2's two
# gates reads either field. they read [15:12] and GP_CFG0[3:0].
#
# that is a falsifiable prediction and it has never been run, because round 34
# only ever used cold_boot. this runs the full 2x2 so the answer is
# interpretable:
#
#   N0  reboot normal,   no flag   the missing baseline. round 34 proved
#                                cold_boot works unflagged (C0, 17.5 s) but
#                                never ran normal, so a wedge below would be
#                                ambiguous between "flag" and "normal is
#                                broken". this is the leg that rules that out.
#   N1  reboot normal,   flag      E3 proper
#   C0  reboot cold_boot, no flag  round 34 repeat, same session, same watcher
#   C1  reboot cold_boot, flag     round 34 F2 repeat
#
# the watcher is usb_watch.py at 4 ms, which logs every device on the bus and
# not just the three targets, so "no USB at all" is a real measurement and not
# an absence of matching VID:PID. read-only apart from the two oem commands:
# set_usb_boot and reboot. no MMIO writes, no poke, no RUN_IN_ADDR.
#
#   tools/e3.sh 900
set -u
cd "$(dirname "$0")/.."

DURATION="${1:-900}"
PREFIX="${E3_PREFIX:-reports/round36-e3}"
WATCH="tools/usb_watch.py"

run() {  # run <name> <flag:0|1> <mode>
  local name="$1" flag="$2" mode="$3"
  echo
  echo "################ $name : flag=$flag mode=$mode ################"
  # watcher first, so the reset itself is inside the window
  python3 "$WATCH" "$PREFIX-$name-usbwatch.log" "$DURATION" 0.004 \
    > /dev/null 2>&1 &
  local wpid=$!
  sleep 2

  if [ "$flag" = "1" ]; then
    echo "--- fastboot oem set_usb_boot 2 ---"
    timeout 20 fastboot oem set_usb_boot 2 2>&1 | sed 's/^/    /'
  fi
  echo "--- fastboot oem reboot $mode ---"
  timeout 20 fastboot oem reboot "$mode" 2>&1 | sed 's/^/    /'

  # let the watcher run its course; it logs the OFF and any return
  wait $wpid
  echo "--- $name watcher tail ---"
  tail -12 "$PREFIX-$name-usbwatch.log" | sed 's/^/    /'
  echo "--- bus now ---"
  lsusb 2>/dev/null | grep -E "1b8e|18d1|2717" | sed 's/^/    /' || echo "    no target on the bus"
}

for spec in "N0 0 normal" "N1 1 normal" "C0 0 cold_boot" "C1 1 cold_boot"; do
  # shellcheck disable=SC2086
  set -- $spec
  # only start the next run if the stick is actually back on android
  if ! timeout 10 adb devices 2>/dev/null | grep -q "device$"; then
    echo
    echo "### $1 skipped: stick is not on adb. it needs a power-cycle."
    echo "### (a wedge is the expected result for the flagged legs)"
    continue
  fi
  run "$@"
done
