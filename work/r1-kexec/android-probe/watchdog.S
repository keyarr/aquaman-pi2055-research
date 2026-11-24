/* Static AArch64 /init wrapper for a diagnosable Android boot attempt.
 * No libc, direct syscalls only.
 *
 * The wrapper forks a watchdog child, then execs /realinit (the real
 * ramdisk /init) while keeping PID 1. After 30 s the child sends SIGSEGV
 * to PID 1 so a hanging boot panics and leaves a readable pstore record.
 * If the exec fails, PID 1 exits with the errno and panics immediately.
 */

	.global _start
	.text

_start:
	/* pid = clone(SIGCHLD, stack_top) */
	mov	x0, #17		/* SIGCHLD */
	adr	x1, stack_top
	mov	x8, #220		/* __NR_clone */
	svc	#0
	cmp	x0, #0
	b.eq	watchdog
	/* clone error: distinct exit code */
	b.lt	clone_failed

	adr	x0, realinit_path
	adr	x1, argv
	adr	x2, envp
	mov	x8, #221		/* __NR_execve */
	svc	#0

exec_failed:
	/* execve returned -errno in x0; report the errno as the exit code. */
	neg	x0, x0
	and	x0, x0, #0xff
	mov	x8, #93		/* __NR_exit */
	svc	#0
1:	b	1b

clone_failed:
	/* clone returned -errno; use 100 plus the low 5 bits of the errno. */
	neg	x0, x0
	and	x0, x0, #0x1f
	add	x0, x0, #100
	mov	x8, #93
	svc	#0
1:	b	1b

watchdog:
	/* nanosleep(&ts, NULL) */
	adr	x0, timespec
	mov	x1, #0
	mov	x8, #101		/* __NR_nanosleep */
	svc	#0
	/* kill(1, SIGSEGV) */
	mov	x0, #1
	mov	x1, #11
	mov	x8, #129		/* __NR_kill */
	svc	#0
	/* exit(0) */
	mov	x0, #0
	mov	x8, #93
	svc	#0
1:	b	1b

	.section .rodata
	.align 3
realinit_path:
	.asciz "/realinit"
init_argv0:
	.asciz "/init"
argv:
	.quad init_argv0
	.quad 0
envp:
	.quad 0
timespec:
	.quad 30
	.quad 0

	.section .bss
	.align 12
	.space 16384
stack_top:
