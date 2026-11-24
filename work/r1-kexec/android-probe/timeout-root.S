/* Static AArch64 /init wrapper with a guaranteed panic on init hang.
 * No libc, direct syscalls only.
 *
 * PID 1 mounts the Android system root, chroots into it, then clones a
 * child that execs the real /init. The parent waits with wait4(WNOHANG)
 * for up to 45 s. A normal child exit is forwarded with the child's code
 * (0 and 42 both become 42); a timeout exits 107 so "Attempted to kill
 * init!" panics and leaves a pstore record. No reboot calls.
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
	b	mount_failed

mount_first:
	/* give devtmpfs time to create the eMMC partition node */
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
	mov	x3, #45842
	mov	x8, #33		/* __NR_mknodat */
	svc	#0
	cmp	x0, #0
	b.ge	do_mount
	add	x1, x0, #17		/* tolerate EEXIST */
	cmp	x1, #0
	b.eq	do_mount
	b	mount_failed

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

	/* fallback: the underlying system partition mmcblk0p18 */
	adr	x0, mmc_path
	adr	x1, root_path
	adr	x2, ext4
	mov	x3, #1
	mov	x4, #0
	mov	x8, #40
	svc	#0
	cmp	x0, #0
	b.ge	do_chroot

mount_failed:
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
	b.ge	do_clone
	neg	x0, x0
	and	x0, x0, #0x1f
	add	x0, x0, #140
	b	exit_now

do_clone:
	/* child_pid = clone(SIGCHLD, stack_top) */
	mov	x0, #17
	adr	x1, stack_top
	mov	x8, #220		/* __NR_clone */
	svc	#0
	cmp	x0, #0
	b.eq	child_exec
	b.lt	exit_99
	mov	x19, x0		/* child pid */
	adr	x20, wait_status
	mov	w21, #9		/* 9 x 5 s = 45 s */

wait_loop:
	/* wait4(child_pid, &status, WNOHANG, NULL) */
	mov	x0, x19
	mov	x1, x20
	mov	x2, #1
	mov	x3, #0
	mov	x8, #260		/* __NR_wait4 */
	svc	#0
	cmp	x0, #0
	b.gt	child_exited
	b.lt	exit_99

	/* still running: nanosleep({5, 0}) */
	adr	x0, sleep_spec
	mov	x1, #0
	mov	x8, #101
	svc	#0
	subs	w21, w21, #1
	b.ne	wait_loop
	mov	x0, #107		/* timeout: panic via init death */
	b	exit_now

child_exited:
	ldr	w0, [x20]
	and	w1, w0, #0x7f		/* signaled? */
	cbnz	w1, exit_42
	ubfx	w0, w0, #8, #8		/* WEXITSTATUS */
	cbz	w0, exit_42
	cmp	w0, #42
	b.eq	exit_42
	b	exit_now

exit_42:
	mov	x0, #42
	b	exit_now

exit_99:
	mov	x0, #99

exit_now:
	mov	x8, #93		/* __NR_exit */
	svc	#0
1:	b	1b

child_exec:
	adr	x0, init_path
	adr	x1, argv
	adr	x2, envp
	mov	x8, #221		/* __NR_execve */
	svc	#0
	mov	x0, #99		/* execve failed */
	b	exit_now

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
sleep_spec:
	.quad 5
	.quad 0

	.section .bss
	.align 12
wait_status:
	.space 8
	.space 16376
stack_top:
