/* Minimal static ARM EABI ELF: no libc, direct syscalls only, no reboot. */
/* write(1, marker, 21); exit(42). No open, no close, no file I/O. */
	.syntax unified
	.arm
	.global _start
	.text
_start:
	/* write(1, marker, 21) */
	mov	r0, #1			/* stdout */
	ldr	r1, =marker
	mov	r2, #21		/* marker_len */
	mov	r7, #4			/* __NR_write (ARM EABI) */
	svc	#0

	/* exit(42) */
	mov	r0, #42
	mov	r7, #1			/* __NR_exit */
	svc	#0
1:	b	1b

	.ltorg
	.align	2
	.section .rodata
marker:
	.ascii "R1_EVIDENCE_5A31C0DE\n"
	.equ marker_len, . - marker
