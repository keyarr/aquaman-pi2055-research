/* Static AArch64 /init wrapper: mount the real system root, pivot_root into
 * it, and exec the real Android /init as PID 1. No libc, direct syscalls.
 *
 * Unlike watchdog-root.S / timeout-root.S this does NOT chroot(). chroot leaves
 * /proc/self/fd/N resolving to "/root/sys/..." while libandroid_runtime's
 * FileDescriptorWhitelist expects "/sys/kernel/debug/tracing/trace_marker", so
 * nativeForkSystemServer aborts. pivot_root makes the system partition the
 * global root, so the same fds resolve to "/sys/...".
 *
 * Uses the util-linux switch_root idiom: chdir(newroot), pivot_root(".", "."),
 * umount2(".", MNT_DETACH), chdir("/"), execve("/init"). No clone/wait4/reboot.
 *
 * Each failure exits with a distinct code so the kernel prints it in
 * "Attempted to kill init! exitcode=0xNN00" (NN = exit code):
 *   10+errno mkdir /root, 20+errno mknod, 30+errno mount,
 *   70+errno chdir("/root"), 80+errno pivot_root, 90+errno chdir("/"),
 *   100+errno execve, 110+errno umount2.
 */

	.global _start
	.text

_start:
	/* mkdir("/root", 0755): EEXIST is fine, mount reports real failures. */
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
	b	exit_10

mount_first:
	/* give devtmpfs time to create the eMMC partition nodes */
	adr	x0, mount_delay
	mov	x1, #0
	mov	x8, #101		/* __NR_nanosleep */
	svc	#0

	/* mkdirat("/dev/block", 0755) so the node can be created below */
	mov	x0, #-100
	adr	x1, block_dir
	mov	x2, #493
	mov	x8, #34
	svc	#0

	/* mknodat("/dev/block/mmcblk0p18", S_IFBLK|0644, 179:18) */
	mov	x0, #-100
	adr	x1, mmc_path
	mov	x2, #0x61a4
	mov	x3, #45842		/* makedev(179, 18) */
	mov	x8, #33		/* __NR_mknodat */
	svc	#0
	cmp	x0, #0
	b.ge	do_mount
	add	x1, x0, #17		/* tolerate EEXIST */
	cmp	x1, #0
	b.eq	do_mount
	b	exit_20

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
	b.ge	do_pivot

	/* fallback: mount the underlying system partition directly */
	adr	x0, mmc_path
	adr	x1, root_path
	adr	x2, ext4
	mov	x3, #1
	mov	x4, #0
	mov	x8, #40
	svc	#0
	cmp	x0, #0
	b.ge	do_pivot
	b	exit_30

do_pivot:
	/* switch_root idiom: enter the new root before pivoting. */
	adr	x0, root_path
	mov	x8, #49		/* __NR_chdir */
	svc	#0
	cmp	x0, #0
	b.lt	exit_70

	/* pivot_root(".", "."): new and put_old are both the new root's root. */
	adr	x0, dot
	adr	x1, dot
	mov	x8, #41		/* __NR_pivot_root */
	svc	#0
	cmp	x0, #0
	b.lt	exit_80

	/* detach the old root, still mounted over "/" as put_old */
	adr	x0, dot
	mov	x2, #2		/* MNT_DETACH */
	mov	x8, #166	/* __NR_umount2 */
	svc	#0
	cmp	x0, #0
	b.lt	exit_110

	adr	x0, slash
	mov	x8, #49		/* __NR_chdir */
	svc	#0
	cmp	x0, #0
	b.lt	exit_90

do_exec:
	adr	x0, init_path
	adr	x1, argv
	adr	x2, envp
	mov	x8, #221		/* __NR_execve */
	svc	#0
	b	exit_100

exit_10:
	mov	x9, #10
	b	fail
exit_20:
	mov	x9, #20
	b	fail
exit_30:
	mov	x9, #30
	b	fail
exit_70:
	mov	x9, #70
	b	fail
exit_80:
	mov	x9, #80
	b	fail
exit_90:
	mov	x9, #90
	b	fail
exit_100:
	mov	x9, #100
	b	fail
exit_110:
	mov	x9, #110
	b	fail

fail:
	neg	x0, x0
	and	x0, x0, #0x1f
	add	x0, x0, x9
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
	.asciz "/dev/block/mmcblk0p18"
block_dir:
	.asciz "/dev/block"
ext4:
	.asciz "ext4"
dot:
	.asciz "."
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
mount_delay:
	.quad 4
	.quad 0
