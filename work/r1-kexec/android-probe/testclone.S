/* Diagnostic only: run on the stock kernel, no fire. */
/* clone(SIGCHLD, stack): parent exits 0, child exits 77, errors exit errno. */

	.global _start
	.text
_start:
	mov	x0, #17
	adr	x1, stack_top
	mov	x8, #220		/* __NR_clone */
	svc	#0
	cmp	x0, #0
	b.eq	child
	b.lt	failed
	mov	x0, #0
	mov	x8, #93
	svc	#0
1:	b	1b
child:
	mov	x0, #77
	mov	x8, #93
	svc	#0
1:	b	1b
failed:
	neg	x0, x0
	and	x0, x0, #0xff
	mov	x8, #93
	svc	#0
1:	b	1b

	.section .bss
	.align 12
	.space 16384
stack_top:
