/* Diagnostic only: run on stock kernel, no fire. */
/* mkdir("/data/local/tmp/r1/testdir", 0755); exit(errno or 0). */

	.global _start
	.text
_start:
	adr	x0, path
	mov	x1, #493
	mov	x8, #1030		/* __NR_mkdir */
	svc	#0
	cmp	x0, #0
	b.ge	ok
	neg	x0, x0
	and	x0, x0, #0xff
	mov	x8, #93
	svc	#0
1:	b	1b
ok:
	mov	x0, #0
	mov	x8, #93
	svc	#0
1:	b	1b

	.section .rodata
path:
	.asciz "/data/local/tmp/r1/testdir"
