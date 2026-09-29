# kernelsu-next — FEASIBILITY: VIABLE WITH SOURCE (manual integration, without kprobes)

docs: https://kernelsu-next.github.io/webpage/pages/how-to-integrate-for-non-gki.html, https://github.com/KernelSU-Next/KernelSU-Next

support: kernels 4.4–6.12, arm64 ok. 4.9.113 is supported. <4.14 only built-in driver (no LKM/prebuilt), with backports possible.

kprobe method: BLOCKED here. Requires CONFIG_KPROBES=y + KPROBE_EVENTS=y + KSU_KPROBE_HOOKS=y. Device has CONFIG_KPROBES=n. Docs suggest enabling it, but on Amlogic BSPs kprobes frequently causes bootloops (debug: comment out ksu_sucompat_init/ksu_ksud_init; boots = broken kprobes).

manual method: THE VIABLE PATH. setup.sh legacy + CONFIG_KSU=y + 5 hook patches (fs/exec.c do_execve, fs/open.c SYSCALL_DEFINE3, fs/read_write.c vfs_read, fs/stat.c SYSCALL_DEFINE4, kernel/reboot.c SYSCALL_DEFINE4). Original docs require CONFIG_KPROBES disabled for the manual method (otherwise volume-down triggers safe mode). Our KPROBES=n is helpful, not an obstacle.

real risks on 4.9 Amlogic: broken kprobes (irrelevant for manual), LSM/SELinux hooks, legacy sdcardfs/binder, toolchain (2022 build used gcc 6.3.1 Linaro; modern rebuild with gcc 8+ requires fixes already present in McMCCRU). None of these are blockers; they are porting tasks.

classification: VIABLE WITH SOURCE (manual integration). Without confirmed source + AMLSECU packaging, do not compile yet.
next step when source tree is confirmed: copy tree to kernel-test/, run setup.sh legacy, apply the 5 patches, review hostile diff before any build.
