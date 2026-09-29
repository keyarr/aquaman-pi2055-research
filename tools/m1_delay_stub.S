// M1 delay stub — proof of execution via fastboot boot (without UART).
//
// Layout: Linux ARM64 Image header (only what bootm checks: magic @0x38)
// + delay in loop + PSCI SYSTEM_RESET via HVC. Position-independent,
// no memory access beyond its own code. Runs in EL2 (U-Boot).
//
// Linaro 6.3.1: aarch64-linux-gnu-gcc -c m1_delay_stub.S
// Entry: x0 = DTB (ignored), rest zeroed. Does not return.

	.text
	.arch armv8-a
	.global _start
_start:
	// --- Linux ARM64 Image header (64 bytes) ---
	b	entry			// code0: branch to real code
	.long	0			// code1 (reserved)
#ifndef M1_TEXTOFFSET
#define M1_TEXTOFFSET 0
#endif
	.quad	M1_TEXTOFFSET	// text_offset (booti uses: dst = dram_start + text_offset)
	.quad	_image_size		// image_size
	.quad	0			// flags/res1 (LE, zeros)
	.quad	0			// res2
	.quad	0			// res3
	.quad	0			// res4
	.long	0x644d5241		// magic "ARM\x64" — ONLY field checked by bootm
	.long	0			// res5 (header footer)
#ifndef M1_OUTER
#define M1_OUTER 0x0FA0		// 4000 → ~5-15 s (M1a)
#endif
entry:
	// --- delay: nested loop, M1_OUTER × 1M iters ---
	mov	x1, #M1_OUTER		// outer
1:	mov	x2, #0x4240		// inner lo = 0x4240
	movk	x2, #0xF, lsl #16	// inner = 0xF4240 = 1,000,000
2:	subs	x2, x2, #1
	b.ne	2b
	subs	x1, x1, #1
	b.ne	1b
	// --- PSCI SYSTEM_RESET (fid 0x84000009) ---
	movz	x0, #0x8400, lsl #16	// x0 = 0x84000000
	movk	x0, #0x9		// x0 = 0x84000009 = PSCI SYSTEM_RESET
	hvc	#0
	// fid identical to plaintext test stub (plain_kernel.bin:
	// d2b08000 f2800120 d4000002) for complete comparability.
3:	wfi
	b	3b			// never reaches here if HVC reset succeeded
_image_size = . - _start
