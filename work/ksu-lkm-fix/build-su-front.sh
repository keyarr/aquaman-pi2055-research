#!/bin/bash
set -eu

ROOT=/home/erick/Documentos/projetos/aquaman_9_PI_2055
WORK=$ROOT/work/ksu-lkm-fix
CROSS=$ROOT/.src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu-

"$CROSS"gcc -fno-builtin -nostdlib -static -Os -s -o "$WORK/su-helper" "$WORK/su_front.c"
sha256sum "$WORK/su-helper"
