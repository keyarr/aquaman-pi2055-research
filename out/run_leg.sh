#!/bin/bash
# run_leg.sh <leg> <tool>
LEG=$1; TOOL=${2:-ghostlock_uaf_isolate}
U0=$(adb shell 'cut -d" " -f1 /proc/uptime' | tr -d '\r')
echo "=== $TOOL leg=$LEG  uptime_before=$U0"
adb shell "/data/local/tmp/$TOOL $LEG" 2>&1 | tee "out/logs/${TOOL}_leg${LEG}.log" | sed 's/^/  | /'
U1=$(adb shell 'cut -d" " -f1 /proc/uptime' | tr -d '\r')
echo "=== uptime_after=$U1"
python3 -c "print('REBOOT DETECTADO' if float('$U1') < float('$U0') else 'sem reboot (uptime subiu %.1fs)' % (float('$U1')-float('$U0')))"
