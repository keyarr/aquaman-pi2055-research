cmd_arch/arm64/kernel/vdso/note.o := /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu-gcc -Wp,-MD,arch/arm64/kernel/vdso/.note.o.d -nostdinc -isystem /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/MiTV_OpenSource/cross_compile_tool/bin/../lib/gcc/aarch64-linux-gnu/6.3.1/include -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include -I./arch/arm64/include/generated/uapi -I./arch/arm64/include/generated  -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include -I./include -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi -I./include/generated/uapi -include /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kconfig.h -D__KERNEL__ -mlittle-endian -D__ASSEMBLY__ -fno-PIE -DCONFIG_AS_LSE=1 -DCC_HAVE_ASM_GOTO -Wa,-gdwarf-2   -c -o arch/arm64/kernel/vdso/note.o /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/kernel/vdso/note.S

source_arch/arm64/kernel/vdso/note.o := /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/kernel/vdso/note.S

deps_arch/arm64/kernel/vdso/note.o := \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/uts.h \
    $(wildcard include/config/default/hostname.h) \
  include/generated/uapi/linux/version.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/elfnote.h \

arch/arm64/kernel/vdso/note.o: $(deps_arch/arm64/kernel/vdso/note.o)

$(deps_arch/arm64/kernel/vdso/note.o):
