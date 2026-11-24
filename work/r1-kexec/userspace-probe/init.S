/* Minimal AArch64 /init: no libc, direct syscalls only. */
/* write(1, marker, len); reboot(magic1, magic2, RESTART, 0); exit(42). */

	.global _start
	.text

_start:
	mov	x0, #1
	adr	x1, marker
	mov	x2, #marker_len
	mov	x8, #64		/* __NR_write */
	svc	#0

	movz	x0, #0xdead
	movk	x0, #0xfee1, lsl #16
	movz	x1, #0x1969
	movk	x1, #0x2812, lsl #16
	movz	x2, #0x4567
	movk	x2, #0x0123, lsl #16	/* LINUX_REBOOT_CMD_RESTART */
	mov	x3, #0
	mov	x8, #104	/* __NR_reboot */
	svc	#0

	/* Reboot did not return: report it and let init panic. */
	mov	x0, #2
	adr	x1, failed
	mov	x2, #failed_len
	mov	x8, #64
	svc	#0

	mov	x0, #42
	mov	x8, #93		/* __NR_exit */
	svc	#0
1:	b	1b

	.section .rodata
marker:
	.ascii "R1_USERSPACE_EL0_A7C3F19D\n"
	.equ marker_len, . - marker
failed:
	.ascii "R1_REBOOT_FAILED_A7C3F19D\n"
	.equ failed_len, . - failed
