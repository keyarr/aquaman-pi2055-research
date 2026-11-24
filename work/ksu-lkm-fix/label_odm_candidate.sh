#!/bin/bash
set -eu

ROOT=/home/erick/Documentos/projetos/aquaman_9_PI_2055
IMG=$ROOT/work/ksu-lkm-fix/odm20_ksu_persist.img
MNT=/tmp/opencode/ksu-odm-label

mkdir -p "$MNT"
sudo umount "$MNT" 2>/dev/null || true
sudo mount -o loop,rw "$IMG" "$MNT"
trap 'sudo umount "$MNT"' EXIT

sudo setfattr -n security.selinux -v 'u:object_r:vendor_file:s0' "$MNT/kernelsu.ko"
sudo setfattr -n security.selinux -v 'u:object_r:vendor_file:s0' "$MNT/ksud32"
sudo setfattr -n security.selinux -v 'u:object_r:init_exec:s0' "$MNT/etc/init/root.rc"
sudo setfattr -n security.selinux -v 'u:object_r:vendor_file:s0' "$MNT/bin"
sudo setfattr -n security.selinux -v 'u:object_r:shell_exec:s0' "$MNT/bin/su"

echo "labelled files in $IMG"
