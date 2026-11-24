cmd_security/selinux/ss/policydb.o := /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu-gcc -Wp,-MD,security/selinux/ss/.policydb.o.d -nostdinc -isystem /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/MiTV_OpenSource/cross_compile_tool/bin/../lib/gcc/aarch64-linux-gnu/6.3.1/include -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include -I./arch/arm64/include/generated/uapi -I./arch/arm64/include/generated  -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include -I./include -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi -I./include/generated/uapi -include /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kconfig.h -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux -Isecurity/selinux -D__KERNEL__ -mlittle-endian -Wall -Wundef -Wstrict-prototypes -Wno-trigraphs -fno-strict-aliasing -fno-common -fshort-wchar -Werror-implicit-function-declaration -Wno-format-security -std=gnu89 -fno-PIE -fno-PIE -mgeneral-regs-only -DCONFIG_AS_LSE=1 -fno-asynchronous-unwind-tables -mpc-relative-literal-loads -fno-pic -fno-delete-null-pointer-checks -Wno-frame-address -O2 --param=allow-store-data-races=0 -DCC_HAVE_ASM_GOTO -Wframe-larger-than=2048 -fstack-protector-strong -Wno-unused-but-set-variable -Wno-unused-const-variable -fno-omit-frame-pointer -fno-optimize-sibling-calls -fno-var-tracking-assignments -g -pg -Wdeclaration-after-statement -Wno-pointer-sign -fno-strict-overflow -fno-merge-all-constants -fmerge-constants -fno-stack-check -fconserve-stack -Werror=implicit-int -Werror=strict-prototypes -Werror=date-time -Werror=incompatible-pointer-types  -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux  -I/home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/include    -DKBUILD_BASENAME='"policydb"'  -DKBUILD_MODNAME='"selinux"' -c -o security/selinux/ss/.tmp_policydb.o /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/ss/policydb.c

source_security/selinux/ss/policydb.o := /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/ss/policydb.c

deps_security/selinux/ss/policydb.o := \
    $(wildcard include/config/mls.h) \
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
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/sched.h \
    $(wildcard include/config/cpu/quiet.h) \
    $(wildcard include/config/no/hz/common.h) \
    $(wildcard include/config/sched/debug.h) \
    $(wildcard include/config/prove/rcu.h) \
    $(wildcard include/config/hotplug/cpu.h) \
    $(wildcard include/config/lockup/detector.h) \
    $(wildcard include/config/detect/hung/task.h) \
    $(wildcard include/config/core/dump/default/elf/headers.h) \
    $(wildcard include/config/virt/cpu/accounting/native.h) \
    $(wildcard include/config/no/hz/full.h) \
    $(wildcard include/config/sched/autogroup.h) \
    $(wildcard include/config/bsd/process/acct.h) \
    $(wildcard include/config/taskstats.h) \
    $(wildcard include/config/audit.h) \
    $(wildcard include/config/inotify/user.h) \
    $(wildcard include/config/fanotify.h) \
    $(wildcard include/config/epoll.h) \
    $(wildcard include/config/posix/mqueue.h) \
    $(wildcard include/config/keys.h) \
    $(wildcard include/config/perf/events.h) \
    $(wildcard include/config/bpf/syscall.h) \
    $(wildcard include/config/sched/info.h) \
    $(wildcard include/config/task/delay/acct.h) \
    $(wildcard include/config/schedstats.h) \
    $(wildcard include/config/sched/smt.h) \
    $(wildcard include/config/sched/mc.h) \
    $(wildcard include/config/numa.h) \
    $(wildcard include/config/sched/walt.h) \
    $(wildcard include/config/fair/group/sched.h) \
    $(wildcard include/config/rt/group/sched.h) \
    $(wildcard include/config/thread/info/in/task.h) \
    $(wildcard include/config/cgroup/sched.h) \
    $(wildcard include/config/preempt/notifiers.h) \
    $(wildcard include/config/blk/dev/io/trace.h) \
    $(wildcard include/config/preempt/rcu.h) \
    $(wildcard include/config/tasks/rcu.h) \
    $(wildcard include/config/memcg.h) \
    $(wildcard include/config/slob.h) \
    $(wildcard include/config/compat/brk.h) \
    $(wildcard include/config/cgroups.h) \
    $(wildcard include/config/cc/stackprotector.h) \
    $(wildcard include/config/cpu/freq/times.h) \
    $(wildcard include/config/virt/cpu/accounting/gen.h) \
    $(wildcard include/config/sysvipc.h) \
    $(wildcard include/config/auditsyscall.h) \
    $(wildcard include/config/rt/mutexes.h) \
    $(wildcard include/config/debug/mutexes.h) \
    $(wildcard include/config/trace/irqflags.h) \
    $(wildcard include/config/lockdep.h) \
    $(wildcard include/config/ubsan.h) \
    $(wildcard include/config/block.h) \
    $(wildcard include/config/task/xacct.h) \
    $(wildcard include/config/cpusets.h) \
    $(wildcard include/config/futex.h) \
    $(wildcard include/config/compat.h) \
    $(wildcard include/config/debug/preempt.h) \
    $(wildcard include/config/numa/balancing.h) \
    $(wildcard include/config/arch/want/batched/unmap/tlb/flush.h) \
    $(wildcard include/config/fault/injection.h) \
    $(wildcard include/config/latencytop.h) \
    $(wildcard include/config/function/graph/tracer.h) \
    $(wildcard include/config/kcov.h) \
    $(wildcard include/config/uprobes.h) \
    $(wildcard include/config/bcache.h) \
    $(wildcard include/config/vmap/stack.h) \
    $(wildcard include/config/arch/wants/dynamic/task/struct.h) \
    $(wildcard include/config/have/unstable/sched/clock.h) \
    $(wildcard include/config/irq/time/accounting.h) \
    $(wildcard include/config/proc/fs.h) \
    $(wildcard include/config/stack/growsup.h) \
    $(wildcard include/config/have/copy/thread/tls.h) \
    $(wildcard include/config/have/exit/thread.h) \
    $(wildcard include/config/amlogic/vmap.h) \
    $(wildcard include/config/debug/stack/usage.h) \
    $(wildcard include/config/preempt.h) \
    $(wildcard include/config/cpu/freq.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/sched.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/sched/prio.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi/asm/param.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/param.h \
    $(wildcard include/config/hz.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/param.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/capability.h \
    $(wildcard include/config/multiuser.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/capability.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/threads.h \
    $(wildcard include/config/nr/cpus.h) \
    $(wildcard include/config/base/small.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/timex.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/timex.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/time.h \
    $(wildcard include/config/arch/uses/gettimeoffset.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/seqlock.h \
    $(wildcard include/config/debug/lock/alloc.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/spinlock.h \
    $(wildcard include/config/debug/spinlock.h) \
    $(wildcard include/config/generic/lockbreak.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/preempt.h \
    $(wildcard include/config/preempt/count.h) \
    $(wildcard include/config/preempt/tracer.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/list.h \
    $(wildcard include/config/debug/list.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/poison.h \
    $(wildcard include/config/illegal/pointer/value.h) \
    $(wildcard include/config/page/poisoning/zero.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/const.h \
  arch/arm64/include/generated/asm/preempt.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/preempt.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/thread_info.h \
    $(wildcard include/config/have/arch/within/stack/frames.h) \
    $(wildcard include/config/hardened/usercopy.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/bug.h \
    $(wildcard include/config/generic/bug.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/bug.h \
    $(wildcard include/config/debug/bugverbose.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/brk-imm.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/bug.h \
    $(wildcard include/config/bug.h) \
    $(wildcard include/config/generic/bug/relative/pointers.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/restart_block.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/current.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/thread_info.h \
    $(wildcard include/config/arm64/sw/ttbr0/pan.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/stack_pointer.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/irqflags.h \
    $(wildcard include/config/irqsoff/tracer.h) \
    $(wildcard include/config/trace/irqflags/support.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/irqflags.h \
    $(wildcard include/config/amlogic/debug/lockup.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/ptrace.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi/asm/ptrace.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/hwcap.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi/asm/hwcap.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/ptrace.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/../drivers/amlogic/debug/irqflags_debug_arm64.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/amlogic/debug_lockup.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/bottom_half.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/spinlock_types.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/spinlock_types.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/lockdep.h \
    $(wildcard include/config/lock/stat.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/rwlock_types.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/spinlock.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/lse.h \
    $(wildcard include/config/as/lse.h) \
    $(wildcard include/config/arm64/lse/atomics.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/processor.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/string.h \
    $(wildcard include/config/binary/printf.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/string.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/string.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/alternative.h \
    $(wildcard include/config/arm64/uao.h) \
    $(wildcard include/config/foo.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/cpucaps.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/insn.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/fpsimd.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/hw_breakpoint.h \
    $(wildcard include/config/have/hw/breakpoint.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/cpufeature.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/jump_label.h \
    $(wildcard include/config/jump/label.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/jump_label.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/virt.h \
    $(wildcard include/config/arm64/vhe.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/sections.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/sections.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/pgtable-hwdef.h \
    $(wildcard include/config/pgtable/levels.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/rwlock.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/spinlock_api_smp.h \
    $(wildcard include/config/inline/spin/lock.h) \
    $(wildcard include/config/inline/spin/lock/bh.h) \
    $(wildcard include/config/inline/spin/lock/irq.h) \
    $(wildcard include/config/inline/spin/lock/irqsave.h) \
    $(wildcard include/config/inline/spin/trylock.h) \
    $(wildcard include/config/inline/spin/trylock/bh.h) \
    $(wildcard include/config/uninline/spin/unlock.h) \
    $(wildcard include/config/inline/spin/unlock/bh.h) \
    $(wildcard include/config/inline/spin/unlock/irq.h) \
    $(wildcard include/config/inline/spin/unlock/irqrestore.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/rwlock_api_smp.h \
    $(wildcard include/config/inline/read/lock.h) \
    $(wildcard include/config/inline/write/lock.h) \
    $(wildcard include/config/inline/read/lock/bh.h) \
    $(wildcard include/config/inline/write/lock/bh.h) \
    $(wildcard include/config/inline/read/lock/irq.h) \
    $(wildcard include/config/inline/write/lock/irq.h) \
    $(wildcard include/config/inline/read/lock/irqsave.h) \
    $(wildcard include/config/inline/write/lock/irqsave.h) \
    $(wildcard include/config/inline/read/trylock.h) \
    $(wildcard include/config/inline/write/trylock.h) \
    $(wildcard include/config/inline/read/unlock.h) \
    $(wildcard include/config/inline/write/unlock.h) \
    $(wildcard include/config/inline/read/unlock/bh.h) \
    $(wildcard include/config/inline/write/unlock/bh.h) \
    $(wildcard include/config/inline/read/unlock/irq.h) \
    $(wildcard include/config/inline/write/unlock/irq.h) \
    $(wildcard include/config/inline/read/unlock/irqrestore.h) \
    $(wildcard include/config/inline/write/unlock/irqrestore.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/atomic.h \
    $(wildcard include/config/generic/atomic64.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/atomic.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/atomic_ll_sc.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/cmpxchg.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/atomic-long.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/math64.h \
    $(wildcard include/config/arch/supports/int128.h) \
  arch/arm64/include/generated/asm/div64.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/div64.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/time64.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/time.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/param.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/timex.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/arch_timer.h \
    $(wildcard include/config/fsl/erratum/a008585.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/clocksource/arm_arch_timer.h \
    $(wildcard include/config/arm/arch/timer.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/timecounter.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/timex.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/jiffies.h \
  include/generated/timeconst.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/plist.h \
    $(wildcard include/config/debug/pi/list.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/rbtree.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/rcupdate.h \
    $(wildcard include/config/tiny/rcu.h) \
    $(wildcard include/config/tree/rcu.h) \
    $(wildcard include/config/rcu/trace.h) \
    $(wildcard include/config/rcu/stall/common.h) \
    $(wildcard include/config/rcu/nocb/cpu.h) \
    $(wildcard include/config/debug/objects/rcu/head.h) \
    $(wildcard include/config/rcu/boost.h) \
    $(wildcard include/config/rcu/nocb/cpu/all.h) \
    $(wildcard include/config/no/hz/full/sysidle.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/cpumask.h \
    $(wildcard include/config/cpumask/offstack.h) \
    $(wildcard include/config/debug/per/cpu/maps.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/bitmap.h \
    $(wildcard include/config/s390.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/completion.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/wait.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/wait.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/debugobjects.h \
    $(wildcard include/config/debug/objects.h) \
    $(wildcard include/config/debug/objects/free.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/ktime.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/timekeeping.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/errno.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/errno.h \
  arch/arm64/include/generated/asm/errno.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/errno.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/errno-base.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/rcutree.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/nodemask.h \
    $(wildcard include/config/highmem.h) \
    $(wildcard include/config/movable/node.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/numa.h \
    $(wildcard include/config/nodes/shift.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/mm_types.h \
    $(wildcard include/config/split/ptlock/cpus.h) \
    $(wildcard include/config/arch/enable/split/pmd/ptlock.h) \
    $(wildcard include/config/amlogic/page/trace.h) \
    $(wildcard include/config/have/cmpxchg/double.h) \
    $(wildcard include/config/have/aligned/struct/page.h) \
    $(wildcard include/config/transparent/hugepage.h) \
    $(wildcard include/config/kmemcheck.h) \
    $(wildcard include/config/userfaultfd.h) \
    $(wildcard include/config/aio.h) \
    $(wildcard include/config/mmu/notifier.h) \
    $(wildcard include/config/compaction.h) \
    $(wildcard include/config/x86/intel/mpx.h) \
    $(wildcard include/config/hugetlb/page.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/auxvec.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/auxvec.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi/asm/auxvec.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/rwsem.h \
    $(wildcard include/config/rwsem/spin/on/owner.h) \
    $(wildcard include/config/rwsem/generic/spinlock.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/err.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/osq_lock.h \
  arch/arm64/include/generated/asm/rwsem.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/rwsem.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/uprobes.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/page-flags-layout.h \
    $(wildcard include/config/sparsemem.h) \
    $(wildcard include/config/sparsemem/vmemmap.h) \
  include/generated/bounds.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/sparsemem.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/workqueue.h \
    $(wildcard include/config/debug/objects/work.h) \
    $(wildcard include/config/freezer.h) \
    $(wildcard include/config/sysfs.h) \
    $(wildcard include/config/wq/watchdog.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/timer.h \
    $(wildcard include/config/timer/stats.h) \
    $(wildcard include/config/debug/objects/timers.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/sysctl.h \
    $(wildcard include/config/sysctl.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/uidgid.h \
    $(wildcard include/config/user/ns.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/highuid.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/sysctl.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/page.h \
    $(wildcard include/config/arm64/page/shift.h) \
    $(wildcard include/config/arm64/cont/shift.h) \
    $(wildcard include/config/have/arch/pfn/valid.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/personality.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/personality.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/pgtable-types.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/pgtable-nopud.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/memory.h \
    $(wildcard include/config/arm64/va/bits.h) \
    $(wildcard include/config/blk/dev/initrd.h) \
  arch/arm64/include/generated/asm/sizes.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/sizes.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/sizes.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/mmdebug.h \
    $(wildcard include/config/debug/vm.h) \
    $(wildcard include/config/debug/virtual.h) \
    $(wildcard include/config/debug/vm/pgflags.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/memory_model.h \
    $(wildcard include/config/flatmem.h) \
    $(wildcard include/config/discontigmem.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/pfn.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/getorder.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/mmu.h \
    $(wildcard include/config/unmap/kernel/at/el0.h) \
    $(wildcard include/config/harden/branch/predictor.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/percpu.h \
    $(wildcard include/config/need/per/cpu/embed/first/chunk.h) \
    $(wildcard include/config/need/per/cpu/page/first/chunk.h) \
    $(wildcard include/config/have/setup/per/cpu/area.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/smp.h \
    $(wildcard include/config/amlogic/modify.h) \
    $(wildcard include/config/up/late/init.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/llist.h \
    $(wildcard include/config/arch/have/nmi/safe/cmpxchg.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/smp.h \
    $(wildcard include/config/arm64/acpi/parking/protocol.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/percpu.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/percpu.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/percpu-defs.h \
    $(wildcard include/config/page/table/isolation.h) \
    $(wildcard include/config/debug/force/weak/per/cpu.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/cputime.h \
  arch/arm64/include/generated/asm/cputime.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/cputime.h \
    $(wildcard include/config/virt/cpu/accounting.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/cputime_jiffies.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/sem.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/sem.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/ipc.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/ipc.h \
  arch/arm64/include/generated/asm/ipcbuf.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/ipcbuf.h \
  arch/arm64/include/generated/asm/sembuf.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/sembuf.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/shm.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/shm.h \
  arch/arm64/include/generated/asm/shmbuf.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/shmbuf.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/shmparam.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/shmparam.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/signal.h \
    $(wildcard include/config/old/sigaction.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/signal.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi/asm/signal.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/signal.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/signal.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/signal-defs.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi/asm/sigcontext.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi/asm/siginfo.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/siginfo.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/siginfo.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/pid.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/topology.h \
    $(wildcard include/config/use/percpu/numa/node/id.h) \
    $(wildcard include/config/have/memoryless/nodes.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/mmzone.h \
    $(wildcard include/config/force/max/zoneorder.h) \
    $(wildcard include/config/cma.h) \
    $(wildcard include/config/memory/isolation.h) \
    $(wildcard include/config/zsmalloc.h) \
    $(wildcard include/config/amlogic/cma.h) \
    $(wildcard include/config/zone/dma.h) \
    $(wildcard include/config/zone/dma32.h) \
    $(wildcard include/config/zone/device.h) \
    $(wildcard include/config/memory/hotplug.h) \
    $(wildcard include/config/flat/node/mem/map.h) \
    $(wildcard include/config/page/extension.h) \
    $(wildcard include/config/no/bootmem.h) \
    $(wildcard include/config/deferred/struct/page/init.h) \
    $(wildcard include/config/have/memory/present.h) \
    $(wildcard include/config/need/node/memmap/size.h) \
    $(wildcard include/config/have/memblock/node/map.h) \
    $(wildcard include/config/need/multiple/nodes.h) \
    $(wildcard include/config/have/arch/early/pfn/to/nid.h) \
    $(wildcard include/config/sparsemem/extreme.h) \
    $(wildcard include/config/holes/in/zone.h) \
    $(wildcard include/config/arch/has/holes/memorymodel.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/pageblock-flags.h \
    $(wildcard include/config/hugetlb/page/size/variable.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/memory_hotplug.h \
    $(wildcard include/config/memory/hotremove.h) \
    $(wildcard include/config/have/arch/nodedata/extension.h) \
    $(wildcard include/config/have/bootmem/info/node.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/notifier.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/mutex.h \
    $(wildcard include/config/mutex/spin/on/owner.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/srcu.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/topology.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/topology.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/seccomp.h \
    $(wildcard include/config/seccomp.h) \
    $(wildcard include/config/have/arch/seccomp/filter.h) \
    $(wildcard include/config/seccomp/filter.h) \
    $(wildcard include/config/checkpoint/restore.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/seccomp.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/seccomp.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/unistd.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi/asm/unistd.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/unistd.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/unistd.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/seccomp.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/unistd.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/rculist.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/rtmutex.h \
    $(wildcard include/config/debug/rt/mutexes.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/resource.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/resource.h \
  arch/arm64/include/generated/asm/resource.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/resource.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/resource.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/hrtimer.h \
    $(wildcard include/config/high/res/timers.h) \
    $(wildcard include/config/time/low/res.h) \
    $(wildcard include/config/timerfd.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/timerqueue.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kcov.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/kcov.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/task_io_accounting.h \
    $(wildcard include/config/task/io/accounting.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/latencytop.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/cred.h \
    $(wildcard include/config/debug/credentials.h) \
    $(wildcard include/config/security.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/key.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/assoc_array.h \
    $(wildcard include/config/associative/array.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/selinux.h \
    $(wildcard include/config/security/selinux.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/gfp.h \
    $(wildcard include/config/pm/sleep.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/magic.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/cgroup-defs.h \
    $(wildcard include/config/sock/cgroup/data.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/limits.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/idr.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/percpu-refcount.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/percpu-rwsem.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/rcu_sync.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/bpf-cgroup.h \
    $(wildcard include/config/cgroup/bpf.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/bpf.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/bpf_common.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/cgroup_subsys.h \
    $(wildcard include/config/cgroup/cpuacct.h) \
    $(wildcard include/config/cgroup/schedtune.h) \
    $(wildcard include/config/blk/cgroup.h) \
    $(wildcard include/config/cgroup/device.h) \
    $(wildcard include/config/cgroup/freezer.h) \
    $(wildcard include/config/cgroup/net/classid.h) \
    $(wildcard include/config/cgroup/perf.h) \
    $(wildcard include/config/cgroup/net/prio.h) \
    $(wildcard include/config/cgroup/hugetlb.h) \
    $(wildcard include/config/cgroup/pids.h) \
    $(wildcard include/config/cgroup/debug.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/slab.h \
    $(wildcard include/config/debug/slab.h) \
    $(wildcard include/config/failslab.h) \
    $(wildcard include/config/have/hardened/usercopy/allocator.h) \
    $(wildcard include/config/slab.h) \
    $(wildcard include/config/slub.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kmemleak.h \
    $(wildcard include/config/debug/kmemleak.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kasan.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/audit.h \
    $(wildcard include/config/audit/compat/generic.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/ptrace.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/pid_namespace.h \
    $(wildcard include/config/pid/ns.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/mm.h \
    $(wildcard include/config/have/arch/mmap/rnd/bits.h) \
    $(wildcard include/config/have/arch/mmap/rnd/compat/bits.h) \
    $(wildcard include/config/mem/soft/dirty.h) \
    $(wildcard include/config/arch/uses/high/vma/flags.h) \
    $(wildcard include/config/x86.h) \
    $(wildcard include/config/x86/intel/memory/protection/keys.h) \
    $(wildcard include/config/ppc.h) \
    $(wildcard include/config/parisc.h) \
    $(wildcard include/config/metag.h) \
    $(wildcard include/config/ia64.h) \
    $(wildcard include/config/shmem.h) \
    $(wildcard include/config/fs/dax.h) \
    $(wildcard include/config/debug/vm/rb.h) \
    $(wildcard include/config/page/poisoning.h) \
    $(wildcard include/config/debug/pagealloc.h) \
    $(wildcard include/config/hibernation.h) \
    $(wildcard include/config/hugetlbfs.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/debug_locks.h \
    $(wildcard include/config/debug/locking/api/selftests.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/range.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/bit_spinlock.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/shrinker.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/page_ext.h \
    $(wildcard include/config/idle/page/tracking.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/stacktrace.h \
    $(wildcard include/config/stacktrace.h) \
    $(wildcard include/config/user/stacktrace/support.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/stackdepot.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/page_ref.h \
    $(wildcard include/config/debug/page/ref.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/page-flags.h \
    $(wildcard include/config/arch/uses/pg/uncached.h) \
    $(wildcard include/config/memory/failure.h) \
    $(wildcard include/config/swap.h) \
    $(wildcard include/config/ksm.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/tracepoint-defs.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/static_key.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/pgtable.h \
    $(wildcard include/config/arm64/hw/afdbm.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/proc-fns.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/pgtable-prot.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/fixmap.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/boot.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/fixmap.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/pgtable.h \
    $(wildcard include/config/have/arch/soft/dirty.h) \
    $(wildcard include/config/have/arch/huge/vmap.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/huge_mm.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/vmstat.h \
    $(wildcard include/config/vm/event/counters.h) \
    $(wildcard include/config/debug/tlbflush.h) \
    $(wildcard include/config/debug/vm/vmacache.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/vm_event_item.h \
    $(wildcard include/config/migration.h) \
    $(wildcard include/config/memory/balloon.h) \
    $(wildcard include/config/balloon/compaction.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/nsproxy.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kref.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/ns_common.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/ptrace.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/audit.h \
    $(wildcard include/config/change.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/elf-em.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/syscall.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/compat.h \
    $(wildcard include/config/compat/old/sigaction.h) \
    $(wildcard include/config/odd/rt/sigaction.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/stat.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/stat.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi/asm/stat.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/stat.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/compat.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/stat.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/socket.h \
  arch/arm64/include/generated/asm/socket.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/socket.h \
  arch/arm64/include/generated/asm/sockios.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/sockios.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/sockios.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/uio.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/uio.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/socket.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/if.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/libc-compat.h \
    $(wildcard include/config/data.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/hdlc/ioctl.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/fs.h \
    $(wildcard include/config/fs/posix/acl.h) \
    $(wildcard include/config/cgroup/writeback.h) \
    $(wildcard include/config/ima.h) \
    $(wildcard include/config/fsnotify.h) \
    $(wildcard include/config/fs/encryption.h) \
    $(wildcard include/config/file/locking.h) \
    $(wildcard include/config/quota.h) \
    $(wildcard include/config/mandatory/file/locking.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kdev_t.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/kdev_t.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/dcache.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/rculist_bl.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/list_bl.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/lockref.h \
    $(wildcard include/config/arch/use/cmpxchg/lockref.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/stringhash.h \
    $(wildcard include/config/dcache/word/access.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/hash.h \
    $(wildcard include/config/have/arch/hash.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/path.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/list_lru.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/radix-tree.h \
    $(wildcard include/config/radix/tree/multiorder.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/semaphore.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/fcntl.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/fcntl.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/uapi/asm/fcntl.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/fcntl.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/fiemap.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/migrate_mode.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/blk_types.h \
    $(wildcard include/config/blk/dev/integrity.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/bvec.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/delayed_call.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/fs.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/ioctl.h \
  arch/arm64/include/generated/asm/ioctl.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/ioctl.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/ioctl.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/quota.h \
    $(wildcard include/config/quota/netlink/interface.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/percpu_counter.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/dqblk_xfs.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/dqblk_v1.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/dqblk_v2.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/dqblk_qtree.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/projid.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/quota.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/nfs_fs_i.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/aio_abi.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/flex_array.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/reciprocal_div.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/include/security.h \
    $(wildcard include/config/netlabel.h) \
  security/selinux/flask.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/ss/policydb.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/ss/symtab.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/ss/hashtab.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/ss/avtab.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/ss/sidtab.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/ss/context.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/ss/ebitmap.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/netlabel.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/net.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/random.h \
    $(wildcard include/config/gcc/plugin/latent/entropy.h) \
    $(wildcard include/config/arch/random.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/once.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/random.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/irqnr.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/irqnr.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kmemcheck.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/net.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/skbuff.h \
    $(wildcard include/config/nf/conntrack.h) \
    $(wildcard include/config/bridge/netfilter.h) \
    $(wildcard include/config/xfrm.h) \
    $(wildcard include/config/ipv6/ndisc/nodetype.h) \
    $(wildcard include/config/net/switchdev.h) \
    $(wildcard include/config/net/sched.h) \
    $(wildcard include/config/net/cls/act.h) \
    $(wildcard include/config/net/rx/busy/poll.h) \
    $(wildcard include/config/xps.h) \
    $(wildcard include/config/network/secmark.h) \
    $(wildcard include/config/network/phy/timestamping.h) \
    $(wildcard include/config/netfilter/xt/target/trace.h) \
    $(wildcard include/config/nf/tables.h) \
    $(wildcard include/config/ip/vs.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/textsearch.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/checksum.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/uaccess.h \
    $(wildcard include/config/arm64/pan.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/kernel-pgtable.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kasan-checks.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/compiler.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/checksum.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/checksum.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/dma-mapping.h \
    $(wildcard include/config/have/generic/dma/coherent.h) \
    $(wildcard include/config/has/dma.h) \
    $(wildcard include/config/arch/has/dma/set/coherent/mask.h) \
    $(wildcard include/config/need/dma/map/state.h) \
    $(wildcard include/config/dma/api/debug.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/device.h \
    $(wildcard include/config/debug/devres.h) \
    $(wildcard include/config/generic/msi/irq/domain.h) \
    $(wildcard include/config/pinctrl.h) \
    $(wildcard include/config/generic/msi/irq.h) \
    $(wildcard include/config/dma/cma.h) \
    $(wildcard include/config/of.h) \
    $(wildcard include/config/devtmpfs.h) \
    $(wildcard include/config/sysfs/deprecated.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/ioport.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kobject.h \
    $(wildcard include/config/uevent/helper.h) \
    $(wildcard include/config/debug/kobject/release.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/sysfs.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kernfs.h \
    $(wildcard include/config/kernfs.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kobject_ns.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/klist.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/pinctrl/devinfo.h \
    $(wildcard include/config/pm.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/pinctrl/consumer.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/seq_file.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/pinctrl/pinctrl-state.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/pm.h \
    $(wildcard include/config/vt/console/sleep.h) \
    $(wildcard include/config/amlogic/usb.h) \
    $(wildcard include/config/pm/clk.h) \
    $(wildcard include/config/pm/generic/domains.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/ratelimit.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/device.h \
    $(wildcard include/config/iommu/api.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/pm_wakeup.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/dma-debug.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/dma-direction.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/scatterlist.h \
    $(wildcard include/config/debug/sg.h) \
    $(wildcard include/config/need/sg/dma/length.h) \
    $(wildcard include/config/arch/has/sg/chain.h) \
    $(wildcard include/config/sg/pool.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/io.h \
  arch/arm64/include/generated/asm/early_ioremap.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/early_ioremap.h \
    $(wildcard include/config/generic/early/ioremap.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/xen/xen.h \
    $(wildcard include/config/xen.h) \
    $(wildcard include/config/xen/dom0.h) \
    $(wildcard include/config/xen/pvh.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/io.h \
    $(wildcard include/config/generic/iomap.h) \
    $(wildcard include/config/has/ioport/map.h) \
    $(wildcard include/config/virt/to/bus.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/pci_iomap.h \
    $(wildcard include/config/pci.h) \
    $(wildcard include/config/no/generic/pci/ioport/map.h) \
    $(wildcard include/config/generic/pci/iomap.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/vmalloc.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/dma-mapping.h \
    $(wildcard include/config/iommu/dma.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/xen/hypervisor.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/../../arm/include/asm/xen/hypervisor.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/netdev_features.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/flow_dissector.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/in6.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/in6.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/if_ether.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/splice.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/pipe_fs_i.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/if_packet.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/flow.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/in.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/in.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/netlink.h \
    $(wildcard include/config/have/efficient/unaligned/access.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/netlink.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/scm.h \
    $(wildcard include/config/security/network.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/security.h \
    $(wildcard include/config/security/network/xfrm.h) \
    $(wildcard include/config/security/path.h) \
    $(wildcard include/config/securityfs.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/netlink.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/request_sock.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/sock.h \
    $(wildcard include/config/ipv6.h) \
    $(wildcard include/config/net.h) \
    $(wildcard include/config/rps.h) \
    $(wildcard include/config/inet.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/hardirq.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/ftrace_irq.h \
    $(wildcard include/config/ftrace/nmi/enter.h) \
    $(wildcard include/config/hwlat/tracer.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/vtime.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/context_tracking_state.h \
    $(wildcard include/config/context/tracking.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/hardirq.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/irq.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/irq.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/irq_cpustat.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/list_nulls.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/netdevice.h \
    $(wildcard include/config/dcb.h) \
    $(wildcard include/config/hyperv/net.h) \
    $(wildcard include/config/wlan.h) \
    $(wildcard include/config/ax25.h) \
    $(wildcard include/config/mac80211/mesh.h) \
    $(wildcard include/config/net/ipip.h) \
    $(wildcard include/config/net/ipgre.h) \
    $(wildcard include/config/ipv6/sit.h) \
    $(wildcard include/config/ipv6/tunnel.h) \
    $(wildcard include/config/netpoll.h) \
    $(wildcard include/config/bql.h) \
    $(wildcard include/config/rfs/accel.h) \
    $(wildcard include/config/fcoe.h) \
    $(wildcard include/config/net/poll/controller.h) \
    $(wildcard include/config/libfcoe.h) \
    $(wildcard include/config/wireless/ext.h) \
    $(wildcard include/config/net/l3/master/dev.h) \
    $(wildcard include/config/vlan/8021q.h) \
    $(wildcard include/config/net/dsa.h) \
    $(wildcard include/config/tipc.h) \
    $(wildcard include/config/mpls/routing.h) \
    $(wildcard include/config/netfilter/ingress.h) \
    $(wildcard include/config/net/flow/limit.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/delay.h \
  arch/arm64/include/generated/asm/delay.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/delay.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/prefetch.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/dmaengine.h \
    $(wildcard include/config/async/tx/enable/channel/switch.h) \
    $(wildcard include/config/dma/engine.h) \
    $(wildcard include/config/rapidio/dma/engine.h) \
    $(wildcard include/config/async/tx/dma.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/dynamic_queue_limits.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/ethtool.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/ethtool.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/if_ether.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/net_namespace.h \
    $(wildcard include/config/ieee802154/6lowpan.h) \
    $(wildcard include/config/ip/sctp.h) \
    $(wildcard include/config/ip/dccp.h) \
    $(wildcard include/config/netfilter.h) \
    $(wildcard include/config/nf/defrag/ipv6.h) \
    $(wildcard include/config/netfilter/netlink/acct.h) \
    $(wildcard include/config/nf/ct/netlink/timeout.h) \
    $(wildcard include/config/wext/core.h) \
    $(wildcard include/config/mpls.h) \
    $(wildcard include/config/net/ns.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/netns/core.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/netns/mib.h \
    $(wildcard include/config/xfrm/statistics.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/snmp.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/snmp.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/u64_stats_sync.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/netns/unix.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/netns/packet.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/netns/ipv4.h \
    $(wildcard include/config/ip/multiple/tables.h) \
    $(wildcard include/config/ip/route/classid.h) \
    $(wildcard include/config/ip/mroute.h) \
    $(wildcard include/config/ip/mroute/multiple/tables.h) \
    $(wildcard include/config/ip/route/multipath.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/inet_frag.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/netns/ipv6.h \
    $(wildcard include/config/ipv6/multiple/tables.h) \
    $(wildcard include/config/ipv6/mroute.h) \
    $(wildcard include/config/ipv6/mroute/multiple/tables.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/dst_ops.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/netns/ieee802154_6lowpan.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/netns/sctp.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/netns/dccp.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/netns/netfilter.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/netfilter_defs.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/netfilter.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/netns/x_tables.h \
    $(wildcard include/config/bridge/nf/ebtables.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/netns/conntrack.h \
    $(wildcard include/config/nf/conntrack/events.h) \
    $(wildcard include/config/nf/conntrack/labels.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/netfilter/nf_conntrack_tcp.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/netfilter/nf_conntrack_tcp.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/netns/nftables.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/netns/xfrm.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/xfrm.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/flowcache.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/interrupt.h \
    $(wildcard include/config/irq/forced/threading.h) \
    $(wildcard include/config/generic/irq/probe.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/irqreturn.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/netns/mpls.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/seq_file_net.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/dsa.h \
    $(wildcard include/config/net/dsa/hwmon.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/of.h \
    $(wildcard include/config/sparc.h) \
    $(wildcard include/config/of/dynamic.h) \
    $(wildcard include/config/attach/node.h) \
    $(wildcard include/config/detach/node.h) \
    $(wildcard include/config/add/property.h) \
    $(wildcard include/config/remove/property.h) \
    $(wildcard include/config/update/property.h) \
    $(wildcard include/config/of/numa.h) \
    $(wildcard include/config/no/change.h) \
    $(wildcard include/config/change/add.h) \
    $(wildcard include/config/change/remove.h) \
    $(wildcard include/config/of/resolve.h) \
    $(wildcard include/config/of/overlay.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/mod_devicetable.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/uuid.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/uuid.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/property.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/fwnode.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/phy.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/mdio.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/mdio.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/mii.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/mii.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/module.h \
    $(wildcard include/config/modules/tree/lookup.h) \
    $(wildcard include/config/livepatch.h) \
    $(wildcard include/config/cfi/clang.h) \
    $(wildcard include/config/module/sig.h) \
    $(wildcard include/config/kallsyms.h) \
    $(wildcard include/config/tracepoints.h) \
    $(wildcard include/config/event/tracing.h) \
    $(wildcard include/config/module/unload.h) \
    $(wildcard include/config/constructors.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/kmod.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/elf.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/elf.h \
  arch/arm64/include/generated/asm/user.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/user.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/elf.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/moduleparam.h \
    $(wildcard include/config/alpha.h) \
    $(wildcard include/config/ppc64.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/extable.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/rbtree_latch.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/cfi.h \
    $(wildcard include/config/cfi/clang/shadow.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/module.h \
    $(wildcard include/config/arm64/module/plts.h) \
    $(wildcard include/config/randomize/base.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/asm-generic/module.h \
    $(wildcard include/config/have/mod/arch/specific.h) \
    $(wildcard include/config/modules/use/elf/rel.h) \
    $(wildcard include/config/modules/use/elf/rela.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/phy_fixed.h \
    $(wildcard include/config/fixed/phy.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/netprio_cgroup.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/cgroup.h \
    $(wildcard include/config/cgroup/data.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/cgroupstats.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/taskstats.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/user_namespace.h \
    $(wildcard include/config/persistent/keyrings.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/neighbour.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/netdevice.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/if_link.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/if_link.h \
    $(wildcard include/config/pending.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/if_bonding.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/pkt_cls.h \
    $(wildcard include/config/net/cls/ind.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/pkt_sched.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/hashtable.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/uaccess.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/page_counter.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/memcontrol.h \
    $(wildcard include/config/memcg/swap.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/vmpressure.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/eventfd.h \
    $(wildcard include/config/eventfd.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/writeback.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/flex_proportions.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/backing-dev-defs.h \
    $(wildcard include/config/debug/fs.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/filter.h \
    $(wildcard include/config/bpf/jit.h) \
    $(wildcard include/config/have/ebpf/jit.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/sch_generic.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/pkt_cls.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/gen_stats.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/gen_stats.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/rtnetlink.h \
    $(wildcard include/config/net/ingress.h) \
    $(wildcard include/config/net/egress.h) \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/rtnetlink.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/if_addr.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/rtnetlink.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/arch/arm64/include/asm/cacheflush.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/filter.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/rculist_nulls.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/linux/poll.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/poll.h \
  arch/arm64/include/generated/asm/poll.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/asm-generic/poll.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/dst.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/neighbour.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/net/tcp_states.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/include/uapi/linux/net_tstamp.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/ss/mls_types.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/ss/constraint.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/ss/conditional.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/ss/../include/conditional.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/ss/mls.h \
  /home/erick/Documentos/projetos/aquaman_9_PI_2055/.src/linux-amlogic/security/selinux/ss/services.h \

security/selinux/ss/policydb.o: $(deps_security/selinux/ss/policydb.o)

$(deps_security/selinux/ss/policydb.o):
