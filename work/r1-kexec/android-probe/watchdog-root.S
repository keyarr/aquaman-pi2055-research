/* Static AArch64 /init wrapper: mount the real system root, run Android init.
 * No libc, direct syscalls only.
 *
 * The wrapper forks a watchdog child, mounts the system partition at /root,
 * chroots into it and execs /init while keeping PID 1. After 30 s the child
 * sends SIGSEGV to PID 1 so a hanging boot panics and leaves a pstore log.
 * Failures exit with distinct codes (100+errno at clone, 120+errno at mount,
 * 130+errno at chroot, 140+errno at chdir, 150+errno at execve).
 */

	.global _start
	.text

_start:
	/* pid = clone(SIGCHLD, stack_top) */
	mov	x0, #17
	adr	x1, stack_top
	mov	x8, #220		/* __NR_clone */
	svc	#0
	cmp	x0, #0
	b.eq	watchdog
	b.lt	clone_failed

	/* mkdir("/root", 0755): failures are harmless, mount reports them. */
	mov	x0, #-100		/* AT_FDCWD */
	adr	x1, root_path
	mov	x2, #493
	mov	x8, #34		/* __NR_mkdirat */
	svc	#0
	cmp	x0, #0
	b.ge	mount_first
	add	x1, x0, #17		/* tolerate EEXIST */
	cmp	x1, #0
	b.eq	mount_first
	neg	x0, x0
	and	x0, x0, #0x1f
	add	x0, x0, #110
	b	exit_now

mount_first:
	/* give devtmpfs time to create the eMMC partition nodes */
	adr	x0, mount_delay
	mov	x1, #0
	mov	x8, #101		/* __NR_nanosleep */
	svc	#0

	/* mkdirat("/dev/block", 0755) so the node can be created below */
	mov	x0, #-100		/* AT_FDCWD */
	adr	x1, block_dir
	mov	x2, #493
	mov	x8, #34		/* __NR_mkdirat */
	svc	#0

	/* mknodat("/dev/block/system", S_IFBLK|0644, 179:18); EEXIST is fine */
	mov	x0, #-100		/* AT_FDCWD */
	adr	x1, node_path
	mov	x2, #0x61a4		/* S_IFBLK | 0644 */
	mov	x3, #45842		/* makedev(179, 18) */
	mov	x8, #33		/* __NR_mknodat */
	svc	#0
	cmp	x0, #0
	b.ge	do_mount
	add	x1, x0, #17		/* tolerate EEXIST */
	cmp	x1, #0
	b.eq	do_mount
	neg	x0, x0
	and	x0, x0, #0x1f
	add	x0, x0, #112
	b	exit_now

do_mount:
	/* mount("/dev/block/dm-0", "/root", "ext4", MS_RDONLY, NULL) */
	adr	x0, dm_path
	adr	x1, root_path
	adr	x2, ext4
	mov	x3, #1
	mov	x4, #0
	mov	x8, #40		/* __NR_mount */
	svc	#0
	cmp	x0, #0
	b.ge	do_chroot

	/* fallback: mount the underlying system partition directly */
	adr	x0, mmc_path
	adr	x1, root_path
	adr	x2, ext4
	mov	x3, #1
	mov	x4, #0
	mov	x8, #40
	svc	#0
	cmp	x0, #0
	b.ge	do_chroot
	neg	x0, x0
	and	x0, x0, #0x1f
	add	x0, x0, #122
	b	exit_now

do_chroot:
	adr	x0, root_path
	mov	x8, #51		/* __NR_chroot */
	svc	#0
	cmp	x0, #0
	b.ge	do_chdir
	neg	x0, x0
	and	x0, x0, #0x1f
	add	x0, x0, #130
	b	exit_now

do_chdir:
	adr	x0, slash
	mov	x8, #49		/* __NR_chdir */
	svc	#0
	cmp	x0, #0
	b.ge	do_exec
	neg	x0, x0
	and	x0, x0, #0x1f
	add	x0, x0, #140
	b	exit_now

do_exec:
	adr	x0, init_path
	adr	x1, argv
	adr	x2, envp
	mov	x8, #221		/* __NR_execve */
	svc	#0
	neg	x0, x0
	and	x0, x0, #0x1f
	add	x0, x0, #150
	b	exit_now

clone_failed:
	neg	x0, x0
	and	x0, x0, #0x1f
	add	x0, x0, #100
	b	exit_now

watchdog:
	adr	x0, timespec
	mov	x1, #0
	mov	x8, #101		/* __NR_nanosleep */
	svc	#0
	mov	x0, #1
	mov	x1, #11		/* SIGSEGV */
	mov	x8, #129		/* __NR_kill */
	svc	#0
	mov	x0, #0
exit_now:
	mov	x8, #93		/* __NR_exit */
	svc	#0
1:	b	1b

	.section .rodata
	.align 3
root_path:
	.asciz "/root"
dm_path:
	.asciz "/dev/block/dm-0"
mmc_path:
	.asciz "/dev/block/system"
node_path:
	.asciz "/dev/block/system"
block_dir:
	.asciz "/dev/block"
ext4:
	.asciz "ext4"
slash:
	.asciz "/"
init_path:
	.asciz "/init"
init_argv0:
	.asciz "/init"
argv:
	.quad init_argv0
	.quad 0
envp:
	.quad 0
timespec:
	.quad 30
	.quad 0
mount_delay:
	.quad 4
	.quad 0

	.section .bss
	.align 12
	.space 16384
stack_top:
