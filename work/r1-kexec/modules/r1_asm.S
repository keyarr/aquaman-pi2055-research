/*
 * PREPARATION ONLY - DO NOT EXECUTE ON DEVICE
 *
 * Cache/idmap/jump helpers for r1_kexec. Derived from the amlogic 4.9 tree:
 *   arch/arm64/kernel/relocate_kernel.S   (cache maintenance + final branch)
 *   arch/arm64/kernel/cpu-reset.S         (SCTLR teardown)
 *   arch/arm64/mm/mmu.c / mmu_context.h   (idmap installation)
 * Those objects are absent from the running kernel (CONFIG_KEXEC is not set),
 * so the relevant sequences live here instead.
 */

#include <linux/linkage.h>

/* void r1_dcache_clean_poc(void *start, unsigned long len) */
ENTRY(r1_dcache_clean_poc)
	mrs	x2, ctr_el0
	ubfx	x2, x2, #16, #4		/* DminLine: log2(min line / 4 bytes) */
	mov	x3, #4
	lsl	x2, x3, x2		/* x2 = 4 << DminLine = line size in bytes */
	sub	x3, x2, #1
	bic	x4, x0, x3
	add	x5, x0, x1
1:	dc	civac, x4
	add	x4, x4, x2
	cmp	x4, x5
	b.lo	1b
	dsb	sy
	ret
ENDPROC(r1_dcache_clean_poc)

/* void r1_icache_inval_all(void) */
ENTRY(r1_icache_inval_all)
	ic	iallu
	dsb	nsh
	isb
	ret
ENDPROC(r1_icache_inval_all)

/*
 * void r1_install_idmap(unsigned long pgd_phys, unsigned long t0sz)
 * Page tables are already populated and cleaned to PoC by the caller.
 * EL1 register names alias to EL2 under VHE, which is the running mode.
 */
ENTRY(r1_install_idmap)
	mrs	x2, tcr_el1
	bic	x2, x2, #0x3f
	orr	x2, x2, x1
	msr	tcr_el1, x2
	msr	ttbr0_el1, x0
	isb
	tlbi	vmalle1
	dsb	sy
	isb
	ret
ENDPROC(r1_install_idmap)

/*
 * void r1_relocate_new_kernel(unsigned long entry_phys,
 *                            unsigned long dtb_phys,
 *                            unsigned long stack_top_phys)
 *
 * Entered at its PHYSICAL address via the temporary identity map. No literal
 * pool on purpose: once the MMU is off every fetch must hit the identity map.
 */
ENTRY(r1_relocate_new_kernel)
	mov	x19, x0			/* entry */
	mov	x20, x1			/* dtb */
	mov	x21, x2			/* stack top */

	msr	daifset, #0xf		/* mask all exceptions */
	dsb	sy
	isb

	/* Crumbs 11/15-18 use the linear-map VA from the C caller (MMU on). */
	mov	w9, #11
	str	w9, [x3]
	dc	civac, x3
	dsb	sy
	mov	w9, #15
	str	w9, [x3]
	dc	civac, x3
	dsb	sy

	/* SCTLR_ELx_FLAGS = M|A|C|SA|I (0x100f), same teardown as cpu-reset.S. */
	mov	x22, #0x100f
	mrs	x23, CurrentEL
	mov	w9, #16
	str	w9, [x3]
	dc	civac, x3
	dsb	sy
	cmp	x23, #0x8		/* EL2? */
	b.eq	1f
	mrs	x24, sctlr_el1
	mov	w9, #17
	str	w9, [x3]
	dc	civac, x3
	dsb	sy
	bic	x24, x24, x22
	mov	w9, #18
	str	w9, [x3]
	dc	civac, x3
	dsb	sy
	msr	sctlr_el1, x24
	isb
	b	2f
1:	mrs	x24, sctlr_el2
	mov	w9, #17
	str	w9, [x3]
	dc	civac, x3
	dsb	sy
	bic	x24, x24, x22
	mov	w9, #18
	str	w9, [x3]
	dc	civac, x3
	dsb	sy
	msr	sctlr_el2, x24
	isb
2:
	/* MMU off: crumbs now use the raw physical address. */
	movz	x8, #0x1000
	movk	x8, #0x750, lsl #16	/* x8 = 0x07501000 */
	mov	w9, #12
	str	w9, [x8]
	dsb	sy

	/* MMU and D-cache off; refresh I-cache for the new image. */
	ic	iallu
	dsb	sy
	isb

	mov	sp, x21
	mov	w9, #13
	str	w9, [x8]
	dsb	sy

	mov	x0, x20			/* x0 = DTB phys, as arm64 stext expects */
	mov	x1, xzr
	mov	x2, xzr
	mov	x3, xzr
	mov	w9, #14
	str	w9, [x8]
	dsb	sy
	br	x19
ENDPROC(r1_relocate_new_kernel)

/* Copied to the staging buffer together with the function body. */
	.globl	r1_relocate_new_kernel_end
r1_relocate_new_kernel_end:
