# kernelsu-next — VIABILIDADE: VIAVEL COM SOURCE (via manual, sem kprobe)

docs: https://kernelsu-next.github.io/webpage/pages/how-to-integrate-for-non-gki.html, https://github.com/KernelSU-Next/KernelSU-Next

suporte: kernels 4.4–6.12, arm64 ok. 4.9.113 entra. <4.14 so driver built-in (sem LKM/prebuilt), com backports possiveis.

metodo kprobe: BLOQUEADO aqui. precisa CONFIG_KPROBES=y + KPROBE_EVENTS=y + KSU_KPROBE_HOOKS=y. aparelho tem CONFIG_KPROBES=n. docs mandam tentar habilitar, mas em BSP Amlogic kprobe costuma dar bootloop (debug: comentar ksu_sucompat_init/ksu_ksud_init; bootou = kprobe quebrado).

metodo manual: O CAMINHO. setup.sh legacy + CONFIG_KSU=y + patch em 5 pontos (fs/exec.c do_execve, fs/open.c SYSCALL_DEFINE3, fs/read_write.c vfs_read, fs/stat.c SYSCALL_DEFINE4, kernel/reboot.c SYSCALL_DEFINE4). doc original ainda exige CONFIG_KPROBES desligado no manual (senao volume-down entra em safe mode). nosso KPROBES=n ajuda, nao atrapalha.

riscos reais 4.9 Amlogic: kprobe quebrado (irrelevante no manual), LSM/SELinux hooks, sdcardfs/binder antigos, toolchain (build 2022 usou gcc 6.3.1 Linaro; rebuild moderno com gcc 8+ precisa dos fixes que o McMCCRU ja tem). nada disso e bloqueador, e trabalho de port.

classificacao: VIAVEL COM SOURCE (integracao manual). sem source confirmado + sem packaging AMLSECU, nao compilar ainda.
proximo passo quando houver arvore: copiar tree para kernel-test/, rodar setup.sh legacy, aplicar os 5 patches, revisar diff hostil antes de qualquer build.
