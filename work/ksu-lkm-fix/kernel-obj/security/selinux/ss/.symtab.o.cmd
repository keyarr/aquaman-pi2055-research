cmd_security/selinux/ss/symtab.o := /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu-gcc -Wp,-MD,security/selinux/ss/.symtab.o.d -nostdinc -isystem /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/MiTV_OpenSource/cross_compile_tool/bin/../lib/gcc/aarch64-linux-gnu/6.3.1/include -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include -I./arch/arm64/include/generated/uapi -I./arch/arm64/include/generated  -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include -I./include -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi -I./include/generated/uapi -include /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kconfig.h -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux -Isecurity/selinux -D__KERNEL__ -mlittle-endian -Wall -Wundef -Wstrict-prototypes -Wno-trigraphs -fno-strict-aliasing -fno-common -fshort-wchar -Werror-implicit-function-declaration -Wno-format-security -std=gnu89 -fno-PIE -fno-PIE -mgeneral-regs-only -DCONFIG_AS_LSE=1 -fno-asynchronous-unwind-tables -mpc-relative-literal-loads -fno-pic -fno-delete-null-pointer-checks -Wno-frame-address -O2 --param=allow-store-data-races=0 -DCC_HAVE_ASM_GOTO -Wframe-larger-than=2048 -fstack-protector-strong -Wno-unused-but-set-variable -Wno-unused-const-variable -fno-omit-frame-pointer -fno-optimize-sibling-calls -fno-var-tracking-assignments -g -pg -Wdeclaration-after-statement -Wno-pointer-sign -fno-strict-overflow -fno-merge-all-constants -fmerge-constants -fno-stack-check -fconserve-stack -Werror=implicit-int -Werror=strict-prototypes -Werror=date-time -Werror=incompatible-pointer-types  -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux  -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/include    -DKBUILD_BASENAME='"symtab"'  -DKBUILD_MODNAME='"selinux"' -c -o security/selinux/ss/.tmp_symtab.o /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/ss/symtab.c

source_security/selinux/ss/symtab.o := /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/ss/symtab.c

deps_security/selinux/ss/symtab.o := \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kernel.h \
    $(wildcard include/config/lbdaf.h) \
    $(wildcard include/config/preempt/voluntary.h) \
    $(wildcard include/config/debug/atomic/sleep.h) \
    $(wildcard include/config/mmu.h) \
    $(wildcard include/config/prove/locking.h) \
    $(wildcard include/config/panic/timeout.h) \
    $(wildcard include/config/tracing.h) \
    $(wildcard include/config/ftrace/mcount/record.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/MiTV_OpenSource/cross_compile_tool/lib/gcc/aarch64-linux-gnu/6.3.1/include/stdarg.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/linkage.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/compiler.h \
    $(wildcard include/config/sparse/rcu/pointer.h) \
    $(wildcard include/config/trace/branch/profiling.h) \
    $(wildcard include/config/profile/all/branches.h) \
    $(wildcard include/config/kasan.h) \
    $(wildcard include/config/enable/must/check.h) \
    $(wildcard include/config/enable/warn/deprecated.h) \
    $(wildcard include/config/kprobes.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/compiler-gcc.h \
    $(wildcard include/config/arch/supports/optimized/inlining.h) \
    $(wildcard include/config/optimize/inlining.h) \
    $(wildcard include/config/gcov/kernel.h) \
    $(wildcard include/config/stack/validation.h) \
    $(wildcard include/config/arch/use/builtin/bswap.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/types.h \
  arch/arm64/include/generated/asm/types.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/types.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/int-ll64.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/int-ll64.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi/asm/bitsperlong.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/bitsperlong.h \
    $(wildcard include/config/64bit.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/bitsperlong.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/posix_types.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/stddef.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/stddef.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi/asm/posix_types.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/posix_types.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/stringify.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/export.h \
    $(wildcard include/config/have/underscore/symbol/prefix.h) \
    $(wildcard include/config/modules.h) \
    $(wildcard include/config/modversions.h) \
    $(wildcard include/config/trim/unused/ksyms.h) \
    $(wildcard include/config/unused/symbols.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/linkage.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/types.h \
    $(wildcard include/config/have/uid16.h) \
    $(wildcard include/config/uid16.h) \
    $(wildcard include/config/arch/dma/addr/t/64bit.h) \
    $(wildcard include/config/phys/addr/t/64bit.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/bitops.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/bitops.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/barrier.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/barrier.h \
    $(wildcard include/config/smp.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/bitops/builtin-__ffs.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/bitops/builtin-ffs.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/bitops/builtin-__fls.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/bitops/builtin-fls.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/bitops/ffz.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/bitops/fls64.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/bitops/find.h \
    $(wildcard include/config/generic/find/first/bit.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/bitops/sched.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/bitops/hweight.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/bitops/arch_hweight.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/bitops/const_hweight.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/bitops/lock.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/bitops/non-atomic.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/bitops/le.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi/asm/byteorder.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/byteorder/little_endian.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/byteorder/little_endian.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/swab.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/swab.h \
  arch/arm64/include/generated/asm/swab.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/swab.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/byteorder/generic.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/log2.h \
    $(wildcard include/config/arch/has/ilog2/u32.h) \
    $(wildcard include/config/arch/has/ilog2/u64.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/typecheck.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/printk.h \
    $(wildcard include/config/message/loglevel/default.h) \
    $(wildcard include/config/early/printk.h) \
    $(wildcard include/config/printk/nmi.h) \
    $(wildcard include/config/printk.h) \
    $(wildcard include/config/dynamic/debug.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/init.h \
    $(wildcard include/config/debug/rodata.h) \
    $(wildcard include/config/debug/set/module/ronx.h) \
    $(wildcard include/config/lto/clang.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kern_levels.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/cache.h \
    $(wildcard include/config/arch/has/cache/line/size.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/kernel.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/sysinfo.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/cache.h \
    $(wildcard include/config/amlogic/memory/extend.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/cachetype.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/cputype.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/sysreg.h \
    $(wildcard include/config/arm64/4k/pages.h) \
    $(wildcard include/config/arm64/16k/pages.h) \
    $(wildcard include/config/arm64/64k/pages.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/opcodes.h \
    $(wildcard include/config/cpu/big/endian.h) \
    $(wildcard include/config/cpu/endian/be8.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/../../arm/include/asm/opcodes.h \
    $(wildcard include/config/cpu/endian/be32.h) \
    $(wildcard include/config/thumb2/kernel.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/string.h \
    $(wildcard include/config/binary/printf.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/string.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/string.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/errno.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/errno.h \
  arch/arm64/include/generated/asm/errno.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/errno.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/errno-base.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/ss/symtab.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/ss/hashtab.h \

security/selinux/ss/symtab.o: $(deps_security/selinux/ss/symtab.o)

$(deps_security/selinux/ss/symtab.o):
