#!/bin/sh
# PREPARATION ONLY - DO NOT EXECUTE ON DEVICE
# Running this file only PRINTS the future staging commands. Nothing below is
# executed by this script, and nothing here has been run during preparation.

cat <<'STAGE_COMMANDS'

# --- future procedure (NOT EXECUTED) ------------------------------------
# Host side: build and patch offline first.
#   sh work/r1-kexec/build.sh
#   sh work/r1-kexec/patch_dtb.sh          # no initrd (default)
#   # or, for the initrd variant (values are placeholders; the module
#   # rewrites them to the real physical addresses at load time):
#   CMDLINE="init=/init rootwait quiet" \
#     INITRD_START=0x0 INITRD_END=0x0 \
#     OUT_DTB=work/r1-kexec/aquaman-r1-initrd.dtb \
#     sh work/r1-kexec/patch_dtb.sh

# Device side: stage files, then load the module with fire=1.
adb shell "mkdir -p /data/local/tmp/r1"
adb push work/r1-kexec/modules/r1_kexec.ko   /data/local/tmp/r1/r1_kexec.ko
adb push build-aq/arch/arm64/boot/Image      /data/local/tmp/r1/Image
adb push work/r1-kexec/aquaman-r1.dtb        /data/local/tmp/r1/aquaman-r1.dtb
# Optional initrd variant:
# adb push patched_unpack/ramdisk /data/local/tmp/r1/initrd.cpio

# Sanity check on device before firing (read-only):
adb shell "ls -l /data/local/tmp/r1/; dmesg | tail -20"

# Variant A - no initrd, explicit 0x3d800000 (32 MiB, confirmed free on
# 2026-11-23). The default CMA and 0x38c00000 were fragmented then.
adb shell "insmod /data/local/tmp/r1/r1_kexec.ko \
  image_path=/data/local/tmp/r1/Image \
  dtb_path=/data/local/tmp/r1/aquaman-r1.dtb \
  cma_phys=0x3d800000 fire=1"

# Variant B - initrd, explicit CMA pool at 0x38c00000 (76 MiB):
# adb shell "insmod /data/local/tmp/r1/r1_kexec.ko \
#   image_path=/data/local/tmp/r1/Image \
#   dtb_path=/data/local/tmp/r1/aquaman-r1-initrd.dtb \
#   initrd_path=/data/local/tmp/r1/initrd.cpio \
#   cma_phys=0x38c00000 fire=1"

# After fire=1 the old kernel never returns. Reconnect (power-cycle if adb
# does not come back) and check the breadcrumb and the new kernel:
adb shell "insmod /data/local/tmp/r1/r1_kexec.ko read_crumb=0x07501000"
adb shell "insmod /data/local/tmp/r1/r1_kexec.ko read_crumb=0x07502000"
adb shell "cat /proc/cmdline; uname -a; dmesg | head -60"

# --- rollback (NOT EXECUTED) ---------------------------------------------
# If the new kernel does not come up, restore the stock ODM image that carries
# the original root service. The stock copy lives on the host at
# /tmp/opencode/odm_probe/odm20_stock.img. Reflash it through the normal
# fastboot path from a recovery/fastboot session, then boot stock Android.
# No fastboot/flash/dd command is included here on purpose.

STAGE_COMMANDS
