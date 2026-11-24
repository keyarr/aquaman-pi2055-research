cmd_kernel/bounds.s := /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu-gcc -Wp,-MD,kernel/.bounds.s.d -nostdinc -isystem /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/MiTV_OpenSource/cross_compile_tool/bin/../lib/gcc/aarch64-linux-gnu/6.3.1/include -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include -I./arch/arm64/include/generated/uapi -I./arch/arm64/include/generated  -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include -I./include -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi -I./include/generated/uapi -include /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kconfig.h -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/. -I. -D__KERNEL__ -mlittle-endian -Wall -Wundef -Wstrict-prototypes -Wno-trigraphs -fno-strict-aliasing -fno-common -fshort-wchar -Werror-implicit-function-declaration -Wno-format-security -std=gnu89 -fno-PIE -fno-PIE -mgeneral-regs-only -DCONFIG_AS_LSE=1 -fno-asynchronous-unwind-tables -mpc-relative-literal-loads -fno-pic -fno-delete-null-pointer-checks -Wno-frame-address -O2 --param=allow-store-data-races=0 -DCC_HAVE_ASM_GOTO -Wframe-larger-than=2048 -fstack-protector-strong -Wno-unused-but-set-variable -Wno-unused-const-variable -fno-omit-frame-pointer -fno-optimize-sibling-calls -fno-var-tracking-assignments -g -pg -Wdeclaration-after-statement -Wno-pointer-sign -fno-strict-overflow -fno-merge-all-constants -fmerge-constants -fno-stack-check -fconserve-stack -Werror=implicit-int -Werror=strict-prototypes -Werror=date-time -Werror=incompatible-pointer-types    -DKBUILD_BASENAME='"bounds"'  -DKBUILD_MODNAME='"bounds"'  -fverbose-asm -S -o kernel/bounds.s /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/kernel/bounds.c

source_kernel/bounds.s := /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/kernel/bounds.c

deps_kernel/bounds.s := \
    $(wildcard include/config/smp.h) \
    $(wildcard include/config/nr/cpus.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/page-flags.h \
    $(wildcard include/config/mmu.h) \
    $(wildcard include/config/arch/uses/pg/uncached.h) \
    $(wildcard include/config/memory/failure.h) \
    $(wildcard include/config/idle/page/tracking.h) \
    $(wildcard include/config/64bit.h) \
    $(wildcard include/config/highmem.h) \
    $(wildcard include/config/swap.h) \
    $(wildcard include/config/ksm.h) \
    $(wildcard include/config/transparent/hugepage.h) \
    $(wildcard include/config/hugetlb/page.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/types.h \
    $(wildcard include/config/have/uid16.h) \
    $(wildcard include/config/uid16.h) \
    $(wildcard include/config/lbdaf.h) \
    $(wildcard include/config/arch/dma/addr/t/64bit.h) \
    $(wildcard include/config/phys/addr/t/64bit.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/types.h \
  arch/arm64/include/generated/asm/types.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/types.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/int-ll64.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/int-ll64.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi/asm/bitsperlong.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/bitsperlong.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/bitsperlong.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/posix_types.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/stddef.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/stddef.h \
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
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi/asm/posix_types.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/posix_types.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/bug.h \
    $(wildcard include/config/generic/bug.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/bug.h \
    $(wildcard include/config/debug/bugverbose.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/brk-imm.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/bug.h \
    $(wildcard include/config/bug.h) \
    $(wildcard include/config/generic/bug/relative/pointers.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kernel.h \
    $(wildcard include/config/preempt/voluntary.h) \
    $(wildcard include/config/debug/atomic/sleep.h) \
    $(wildcard include/config/prove/locking.h) \
    $(wildcard include/config/panic/timeout.h) \
    $(wildcard include/config/tracing.h) \
    $(wildcard include/config/ftrace/mcount/record.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/MiTV_OpenSource/cross_compile_tool/lib/gcc/aarch64-linux-gnu/6.3.1/include/stdarg.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/linkage.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/stringify.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/export.h \
    $(wildcard include/config/have/underscore/symbol/prefix.h) \
    $(wildcard include/config/modules.h) \
    $(wildcard include/config/modversions.h) \
    $(wildcard include/config/trim/unused/ksyms.h) \
    $(wildcard include/config/unused/symbols.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/linkage.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/bitops.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/bitops.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/barrier.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/barrier.h \
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
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/mmdebug.h \
    $(wildcard include/config/debug/vm.h) \
    $(wildcard include/config/debug/virtual.h) \
    $(wildcard include/config/debug/vm/pgflags.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/mmzone.h \
    $(wildcard include/config/force/max/zoneorder.h) \
    $(wildcard include/config/cma.h) \
    $(wildcard include/config/memory/isolation.h) \
    $(wildcard include/config/zsmalloc.h) \
    $(wildcard include/config/numa.h) \
    $(wildcard include/config/amlogic/cma.h) \
    $(wildcard include/config/memcg.h) \
    $(wildcard include/config/zone/dma.h) \
    $(wildcard include/config/zone/dma32.h) \
    $(wildcard include/config/zone/device.h) \
    $(wildcard include/config/sparsemem.h) \
    $(wildcard include/config/memory/hotplug.h) \
    $(wildcard include/config/compaction.h) \
    $(wildcard include/config/discontigmem.h) \
    $(wildcard include/config/flat/node/mem/map.h) \
    $(wildcard include/config/page/extension.h) \
    $(wildcard include/config/no/bootmem.h) \
    $(wildcard include/config/numa/balancing.h) \
    $(wildcard include/config/deferred/struct/page/init.h) \
    $(wildcard include/config/have/memory/present.h) \
    $(wildcard include/config/have/memoryless/nodes.h) \
    $(wildcard include/config/need/node/memmap/size.h) \
    $(wildcard include/config/have/memblock/node/map.h) \
    $(wildcard include/config/need/multiple/nodes.h) \
    $(wildcard include/config/have/arch/early/pfn/to/nid.h) \
    $(wildcard include/config/flatmem.h) \
    $(wildcard include/config/sparsemem/extreme.h) \
    $(wildcard include/config/have/arch/pfn/valid.h) \
    $(wildcard include/config/holes/in/zone.h) \
    $(wildcard include/config/arch/has/holes/memorymodel.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kbuild.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/spinlock_types.h \
    $(wildcard include/config/generic/lockbreak.h) \
    $(wildcard include/config/debug/spinlock.h) \
    $(wildcard include/config/debug/lock/alloc.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/spinlock_types.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/lockdep.h \
    $(wildcard include/config/lockdep.h) \
    $(wildcard include/config/lock/stat.h) \
    $(wildcard include/config/trace/irqflags.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/rwlock_types.h \

kernel/bounds.s: $(deps_kernel/bounds.s)

$(deps_kernel/bounds.s):
