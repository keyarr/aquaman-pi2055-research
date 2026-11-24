cmd_arch/arm64/kernel/vdso/vdso.lds := /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu-gcc -E -Wp,-MD,arch/arm64/kernel/vdso/.vdso.lds.d -nostdinc -isystem /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/MiTV_OpenSource/cross_compile_tool/bin/../lib/gcc/aarch64-linux-gnu/6.3.1/include -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include -I./arch/arm64/include/generated/uapi -I./arch/arm64/include/generated  -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include -I./include -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi -I./include/generated/uapi -include /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kconfig.h -D__KERNEL__ -mlittle-endian -P -C -Uarm64 -P -C -Uarm64 -D__ASSEMBLY__ -DLINKER_SCRIPT -o arch/arm64/kernel/vdso/vdso.lds /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/kernel/vdso/vdso.lds.S

source_arch/arm64/kernel/vdso/vdso.lds := /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/kernel/vdso/vdso.lds.S

deps_arch/arm64/kernel/vdso/vdso.lds := \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/const.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/page.h \
    $(wildcard include/config/arm64/page/shift.h) \
    $(wildcard include/config/arm64/cont/shift.h) \
    $(wildcard include/config/have/arch/pfn/valid.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/getorder.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/vdso.h \

arch/arm64/kernel/vdso/vdso.lds: $(deps_arch/arm64/kernel/vdso/vdso.lds)

$(deps_arch/arm64/kernel/vdso/vdso.lds):
