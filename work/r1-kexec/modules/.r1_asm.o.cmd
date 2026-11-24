cmd_/home/erick/Documentos/projetos/aquaman_9_PI_2055/work/r1-kexec/modules/r1_asm.o := /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu-gcc -Wp,-MD,/home/erick/Documentos/projetos/aquaman_9_PI_2055/work/r1-kexec/modules/.r1_asm.o.d -nostdinc -isystem /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/MiTV_OpenSource/cross_compile_tool/bin/../lib/gcc/aarch64-linux-gnu/6.3.1/include -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include -I./arch/arm64/include/generated/uapi -I./arch/arm64/include/generated  -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include -I./include -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi -I./include/generated/uapi -include /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kconfig.h -D__KERNEL__ -mlittle-endian -D__ASSEMBLY__ -fno-PIE -DCONFIG_AS_LSE=1 -DCC_HAVE_ASM_GOTO -Wa,-gdwarf-2 -DMODULE  -c -o /home/erick/Documentos/projetos/aquaman_9_PI_2055/work/r1-kexec/modules/r1_asm.o /home/erick/Documentos/projetos/aquaman_9_PI_2055/work/r1-kexec/modules/r1_asm.S

source_/home/erick/Documentos/projetos/aquaman_9_PI_2055/work/r1-kexec/modules/r1_asm.o := /home/erick/Documentos/projetos/aquaman_9_PI_2055/work/r1-kexec/modules/r1_asm.S

deps_/home/erick/Documentos/projetos/aquaman_9_PI_2055/work/r1-kexec/modules/r1_asm.o := \
    $(wildcard include/config/kexec.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/linkage.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/compiler.h \
    $(wildcard include/config/sparse/rcu/pointer.h) \
    $(wildcard include/config/trace/branch/profiling.h) \
    $(wildcard include/config/profile/all/branches.h) \
    $(wildcard include/config/kasan.h) \
    $(wildcard include/config/enable/must/check.h) \
    $(wildcard include/config/enable/warn/deprecated.h) \
    $(wildcard include/config/kprobes.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/stringify.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/export.h \
    $(wildcard include/config/have/underscore/symbol/prefix.h) \
    $(wildcard include/config/modules.h) \
    $(wildcard include/config/modversions.h) \
    $(wildcard include/config/trim/unused/ksyms.h) \
    $(wildcard include/config/unused/symbols.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/linkage.h \

/home/erick/Documentos/projetos/aquaman_9_PI_2055/work/r1-kexec/modules/r1_asm.o: $(deps_/home/erick/Documentos/projetos/aquaman_9_PI_2055/work/r1-kexec/modules/r1_asm.o)

$(deps_/home/erick/Documentos/projetos/aquaman_9_PI_2055/work/r1-kexec/modules/r1_asm.o):
