cmd_arch/arm64/kernel/vdso/gettimeofday.o := /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu-gcc -Wp,-MD,arch/arm64/kernel/vdso/.gettimeofday.o.d -nostdinc -isystem /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/MiTV_OpenSource/cross_compile_tool/bin/../lib/gcc/aarch64-linux-gnu/6.3.1/include -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include -I./arch/arm64/include/generated/uapi -I./arch/arm64/include/generated  -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include -I./include -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi -I./include/generated/uapi -include /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kconfig.h -D__KERNEL__ -mlittle-endian -D__ASSEMBLY__ -fno-PIE -DCONFIG_AS_LSE=1 -DCC_HAVE_ASM_GOTO -Wa,-gdwarf-2   -c -o arch/arm64/kernel/vdso/gettimeofday.o /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/kernel/vdso/gettimeofday.S

source_arch/arm64/kernel/vdso/gettimeofday.o := /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/kernel/vdso/gettimeofday.S

deps_arch/arm64/kernel/vdso/gettimeofday.o := \
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
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/asm-offsets.h \
  include/generated/asm-offsets.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/unistd.h \
    $(wildcard include/config/compat.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi/asm/unistd.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/unistd.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/unistd.h \
    $(wildcard include/config/mmu.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi/asm/bitsperlong.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/bitsperlong.h \
    $(wildcard include/config/64bit.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/bitsperlong.h \

arch/arm64/kernel/vdso/gettimeofday.o: $(deps_arch/arm64/kernel/vdso/gettimeofday.o)

$(deps_arch/arm64/kernel/vdso/gettimeofday.o):
