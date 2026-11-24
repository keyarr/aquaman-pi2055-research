/* Static AArch64 /init for the one-shot compat-EL0 evidence boot.
 * No libc, direct syscalls only.
 *
 * clone() a child that execve()s /probe32 (a static ARM EABI ELF). The
 * parent polls wait4(WNOHANG) once per second for at most 20 seconds and
 * exits 42 when the child completed normally, 107 on timeout, 99 on any
 * syscall failure, signal death or unexpected child exit status.
 */

	.global _start
	.text

_start:
	/* pid = clone(SIGCHLD, stack_top, NULL, NULL, 0) */
	mov	x0, #17
	adr	x1, stack_top
	mov	x2, #0
	mov	x3, #0
	mov	x4, #0
	mov	x8, #220			/* __NR_clone */
	svc	#0
	cmp	x0, #0
	b.eq	probe_child
	b.lt	probe_fail			/* clone error */
	mov	x19, x0			/* parent: child pid */
	mov	x20, #20			/* 1 s x 20 */

wait_loop:
	/* wait4(pid, &status, WNOHANG, NULL) */
	mov	x0, x19
	adr	x1, wstatus
	mov	x2, #1
	mov	x3, #0
	mov	x8, #260			/* __NR_wait4 */
	svc	#0
	cmp	x0, #0
	b.lt	probe_fail			/* wait4 error */
	b.eq	no_status
	ldr	w1, wstatus
	and	w2, w1, #0x7f
	cbnz	w2, probe_fail			/* signal / stop / continue */
	lsr	w2, w1, #8
	and	w2, w2, #0xff
	cmp	w2, #0
	b.eq	probe_ok			/* validated probe exits 0 */
	cmp	w2, #42
	b.eq	probe_ok
	b	probe_fail

no_status:
	/* nanosleep(&ts, NULL): 1 second */
	adr	x0, timespec
	mov	x1, #0
	mov	x8, #101			/* __NR_nanosleep */
	svc	#0
	subs	x20, x20, #1
	b.ne	wait_loop
	mov	x0, #107			/* timeout */
	b	probe_exit

probe_ok:
	mov	x0, #42
	b	probe_exit

probe_fail:
	mov	x0, #99

probe_exit:
	mov	x8, #93			/* __NR_exit */
	svc	#0
1:	b	1b

probe_child:
	/* execve("/probe32", argv, envp) */
	adr	x0, probe_path
	adr	x1, argv
	adr	x2, envp
	mov	x8, #221			/* __NR_execve */
	svc	#0
	/* execve failed */
	mov	x0, #99
	mov	x8, #93
	svc	#0
1:	b	1b

	.section .rodata
	.align	3
probe_path:
	.asciz	"/probe32"
argv0:
	.asciz	"/probe32"
argv:
	.quad	argv0
	.quad	0
envp:
	.quad	0
timespec:
	.quad	1
	.quad	0

	.section .bss
	.align	12
wstatus:
	.word	0
	.align	12
	.space	16384
stack_top:
