# ghostlock: frame reconciled + value oracle (host, 0 reboots)

(a) lab geometry re-measured on vmlinux: NO number changed. everything stays
INFERRED for stock (stock = AMLSECU! in boot_unpack, sealed; see
out/logs/frame_reconcile*.log).
item | old -> corrected | source
SyS_futex 0x70 -> = | stp [sp,#-0x70]! @0xffffff800913ca30
do_futex 0x120 -> = | stp [sp,#-0x120]! @0xffffff800913bec0
fwrq 0x1a0 -> = | constprop.8 @0xffffff800913b398; System.map only has the clone (t),
direct dispatch at do_futex+0x4b4 @0xffffff800913c374 (no plain symbol)
rt_waiter x29+0x80 -> = | DIE 0xa9e1d8 fbreg -288 (futex.c:2858), CFA x29+0x1a0;
asm: x21=x29+0x80 @0x913b454 becomes q.rt_waiter @0x913b4a8 and waiter arg @0x913b6d4
WAITER_OFF_SP 0x2b0 -> = | 0x70+0x120+0x1a0-0x80
pselect6 0x90, css 0x190 -> = | @0xffffff8009230770 / @0xffffff8009230260;
stack_fds x29+0x90 @0xffffff80092302d4; DIE select.c:561 long[32] fbreg -256
STACK_FDS_OFF 0x190, PAD 0x120 -> = | 0x90+0x190-0x90; 0x2b0-0x190; window [0x120,0x1c0]
dwarf_offsets.py: mismatches 0, all structs match (task 0xdc0/prio 0x68/pi 0x7e0-8, rtmw 0x50/task 0x30).
(b) 0x138 = FLAKE, not a hit. stamp() allocates a fixed-size VLA (MAX_PAD
4096) and only varies the memset len: user SP is identical for every PAD and
the kernel stack_fds is a pure function of fixed base + fixed frames. the
[0x120,0x1c0] scan was a no-op; 19 stalls = the only real behavior (stale
intact waiter -> slow path). 1 reboot in ~30 trials, neighbors 0x130/0x140
in stall, irreproducible 0x180 = stack page reuse lottery (fresh pthreads
per trial) + EDEADLK/timeout race, i.e. the already-known leg3 crash.
lab geometry absolved; what broke was the stamper model, not the numbers.
(c) VALUE oracle, proven in asm, proof in out/logs/value_oracle.log. read:
rt_mutex_get_effective_prio @0xffffff8009105678 touches ONLY task+0x7e0,
+0x7e8, leftmost+0x18, +0x68 and returns min (@0x56a4-56ac; cbz fast @0x5698).
write: __sched_setscheduler str w0,[x27,+0x68] @0xffffff80090d77d0 (bl @0x77cc;
pre-check @0x7898). exposure: task_prio ldr +0x68 @0xffffff80090daf40, sub
#100 @0xaf48; do_task_stat bl @0xffffff800929aaf8 -> /proc/<waiter>/stat
field 18; field 19 (nice, +0x6c-120 @0x929ab08) = negative control. pattern:
fake task_struct in mlocked user-mem, u32 P=0 at +0x68, fake addr at
waiter+0x30 (byte 0x30 of the fd_set at nominal PAD 0x120 lab). intact E=120
-> f18=20; hit E=0 -> f18=-100. P=0 takes the fair path @0x7d00 (bit5 clear,
no RT promotion); the walk touches 1 fake word; no PAN in config
(SW_TTBR0_PAN unset) -> user deref ok. leftover risk: adjust_pi @0x7a78
(w3=1 @0x90d809c) walks the stamped tree; survived in the 0x180 hit; budget
= 1 reboot. 1-boot validation, no new consumer: (1) no stamp: consumer ->
stall + f18==20 (proves the store via the dangling node). (2) with fake:
rc=0 fast + f18==-100 and f19==0. (3) PAD sweep reading f18 (20 = miss,
-100 = hit), 3 reps on the same boot.
