/* Diagnostic only: run on the stock kernel, no fire. */
/* execve("/system/bin/echo", {"echo","OK",NULL}, NULL); exit(errno). */

	.global _start
	.text
_start:
	adr	x0, path
	adr	x1, argv
	adr	x2, envp
	mov	x8, #221		/* __NR_execve */
	svc	#0
	neg	x0, x0
	and	x0, x0, #0xff
	mov	x8, #93
	svc	#0
1:	b	1b

	.section .rodata
path:
	.asciz "/system/bin/echo"
a0:
	.asciz "echo"
a1:
	.asciz "TESTEXEC_OK"
argv:
	.quad a0
	.quad a1
	.quad 0
envp:
	.quad 0
