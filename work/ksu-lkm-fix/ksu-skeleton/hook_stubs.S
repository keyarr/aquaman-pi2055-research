/*
 * One 0x100-byte stub per hooked kernel function. The first 0x28 bytes save
 * all argument registers plus LR; the dispatch slot calls the C dispatcher
 * with x1 == sp (the saved register frame). The restore block puts the
 * registers back, then the original 24 bytes are replayed in place before
 * branching to target+24.
 */
#include <linux/linkage.h>

.macro KSU_STUB name, id
	.globl ksu_stub_\name
	.type ksu_stub_\name, %function
ksu_stub_\name:
	sub	sp, sp, #0xa0
	stp	x0, x1, [sp]
	stp	x2, x3, [sp, #0x10]
	stp	x4, x5, [sp, #0x20]
	stp	x6, x7, [sp, #0x30]
	stp	x8, x9, [sp, #0x40]
	stp	x10, x11, [sp, #0x50]
	stp	x12, x13, [sp, #0x60]
	stp	x14, x15, [sp, #0x70]
	stp	x16, x17, [sp, #0x80]
	str	x30, [sp, #0x90]
	mov	w0, #\id
	mov	x1, sp
	nop
	ldr	x16, ksu_stub_\name\()_dispatch_slot
	blr	x16
	b	ksu_stub_\name\()_restore

ksu_stub_\name\()_dispatch_slot:
	.quad	0

ksu_stub_\name\()_restore:
	ldp	x0, x1, [sp]
	ldp	x2, x3, [sp, #0x10]
	ldp	x4, x5, [sp, #0x20]
	ldp	x6, x7, [sp, #0x30]
	ldp	x8, x9, [sp, #0x40]
	ldp	x10, x11, [sp, #0x50]
	ldp	x12, x13, [sp, #0x60]
	ldp	x14, x15, [sp, #0x70]
	ldp	x16, x17, [sp, #0x80]
	ldr	x30, [sp, #0x90]
	add	sp, sp, #0xa0

ksu_stub_\name\()_orig_slot:
	.rept	6
	.word	0
	.endr
	ldr	x16, ksu_stub_\name\()_cont_slot
	br	x16

ksu_stub_\name\()_cont_slot:
	.quad	0
	.size ksu_stub_\name, . - ksu_stub_\name
.endm

KSU_STUB execve, 0
KSU_STUB faccessat, 1
KSU_STUB read, 2
KSU_STUB newfstatat, 3
KSU_STUB reboot, 4
KSU_STUB prctl, 5
KSU_STUB sysexecve, 6
