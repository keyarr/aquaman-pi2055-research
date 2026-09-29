// M1 delay stub — prova de execução via fastboot boot (sem UART).
//
// Layout: header Linux ARM64 Image (só o que o bootm confere: magic @0x38)
// + delay em loop + PSCI SYSTEM_RESET via HVC. Position-independent,
// sem acesso a memória além do próprio código. Roda em EL2 (U-Boot).
//
// Linaro 6.3.1: aarch64-linux-gnu-gcc -c m1_delay_stub.S
// Entrada: x0 = DTB (ignorado), resto zerado. Não retorna.

	.text
	.arch armv8-a
	.global _start
_start:
	// --- Linux ARM64 Image header (64 bytes) ---
	b	entry			// code0: branch p/ código real
	.long	0			// code1 (reservado)
#ifndef M1_TEXTOFFSET
#define M1_TEXTOFFSET 0
#endif
	.quad	M1_TEXTOFFSET	// text_offset (booti usa: dst = dram_start + text_offset)
	.quad	_image_size		// image_size
	.quad	0			// flags/res1 (LE, zeros)
	.quad	0			// res2
	.quad	0			// res3
	.quad	0			// res4
	.long	0x644d5241		// magic "ARM\x64" — ÚNICO campo conferido pelo bootm
	.long	0			// res5 (pezinho do header)
#ifndef M1_OUTER
#define M1_OUTER 0x0FA0		// 4000 → ~5-15 s (M1a)
#endif
entry:
	// --- delay: nested loop, M1_OUTER × 1M iters ---
	mov	x1, #M1_OUTER		// outer
1:	mov	x2, #0x4240		// inner lo = 0x4240
	movk	x2, #0xF, lsl #16	// inner = 0xF4240 = 1.000.000
2:	subs	x2, x2, #1
	b.ne	2b
	subs	x1, x1, #1
	b.ne	1b
	// --- PSCI SYSTEM_RESET (fid 0x84000009) ---
	movz	x0, #0x8400, lsl #16	// x0 = 0x84000000
	movk	x0, #0x9		// x0 = 0x84000009 = PSCI SYSTEM_RESET
	hvc	#0
	// fid idêntico ao stub do teste plaintext (plain_kernel.bin:
	// d2b08000 f2800120 d4000002) para comparabilidade total.
3:	wfi
	b	3b			// nunca cai aqui se o HVC resetou
_image_size = . - _start
