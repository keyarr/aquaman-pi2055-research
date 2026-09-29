#!/bin/bash
# um PAD por execucao, 1 shot por boot, log incremental no host
cd /home/erick/Downloads/aquaman_9_PI_2055
LOG=out/logs/scan_pads.log
: > $LOG
for pad in 0x120 0x128 0x130 0x138 0x140 0x148 0x150 0x158 0x160 \
           0x168 0x170 0x178 0x180 0x188 0x190 0x198 0x1a0 0x1a8 \
           0x1b0 0x1b8 0x1c0; do
  U0=$(adb shell 'cut -d" " -f1 /proc/uptime' 2>/dev/null | tr -d '\r')
  [ -z "$U0" ] && U0=0
  echo "#### PAD $pad  uptime_before=$U0" | tee -a $LOG
  adb shell "/data/local/tmp/ghostlock_stack_cal $pad $pad 1" 2>&1 | tee -a $LOG | sed 's/^/  | /'
  sleep 2
  U1=$(adb shell 'cut -d" " -f1 /proc/uptime' 2>/dev/null | tr -d '\r')
  [ -z "$U1" ] && U1=0
  if python3 -c "import sys; sys.exit(0 if float('$U1')>=float('$U0') else 1)"; then
    echo "#### PAD $pad RESULT=SOBREVIVEU" | tee -a $LOG
  else
    echo "#### PAD $pad RESULT=REBOOT (uptime $U0 -> $U1), aguardando device" | tee -a $LOG
    for i in $(seq 1 60); do
      adb wait-for-device >/dev/null 2>&1
      S=$(adb shell 'getprop sys.boot_completed' 2>/dev/null | tr -d '\r')
      [ "$S" = "1" ] && break
      sleep 2
    done
    echo "#### device de volta apos reboot, uptime=$(adb shell 'cut -d" " -f1 /proc/uptime' | tr -d '\r')" | tee -a $LOG
  fi
done
echo "#### SCAN FIM" | tee -a $LOG
