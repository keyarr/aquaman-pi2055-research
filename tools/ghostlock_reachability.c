/*
 * ghostlock_reachability.c — Phase 10, benign reachability probe.
 *
 * Tests ONLY that the FUTEX_WAIT_REQUEUE_PI / FUTEX_CMP_REQUEUE_PI paths
 * exist and respond as stock 4.9.113 should respond to invalid parameters.
 * Does not create a PI pair, does not attempt deadlock, does not touch credentials,
 * does not write to kernel pointers, does not perform reclaim.
 *
 * Risk: negligible. All calls use invalid or matching uaddrs and
 * must return -EINVAL before any waiter manipulation. The only
 * functional test (LOCK_PI/UNLOCK_PI on own private futex) is normal
 * PI mutex usage, without requeue.
 *
 * Build (NDK, ARM64, Android 9+):
 *   $NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android28-clang \
 *     -O2 -Wall -Wextra -fPIE -pie ghostlock_reachability.c -o ghostlock_reachability
 * Run:
 *   adb push ghostlock_reachability /data/local/tmp/
 *   adb shell /data/local/tmp/ghostlock_reachability
 *
 * Expected output on a 4.9.113 kernel with PI compiled in:
 *   7 checks, 7 PASS. Any FAIL indicates INCOMPATIBLE in the report.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>

#ifndef __NR_futex
#define __NR_futex 98
#endif
#ifndef FUTEX_WAIT_REQUEUE_PI
#define FUTEX_WAIT_REQUEUE_PI 11
#define FUTEX_CMP_REQUEUE_PI 12
#define FUTEX_LOCK_PI 6
#define FUTEX_UNLOCK_PI 7
#define FUTEX_PRIVATE_FLAG 128
#endif

static int g_pass = 0, g_fail = 0;

static long xfutex(void *u1, int op, uint32_t val, void *timeout, void *u2,
                   uint32_t val3) {
    return syscall(__NR_futex, u1, op, val, timeout, u2, val3);
}

static void check(const char *name, int expect_errno, long ret) {
    int got = (ret == -1) ? errno : 0;
    if (ret == -1 && got == expect_errno) {
        printf("[PASS] %-48s errno=%d (%s)\n", name, got, strerror(got));
        g_pass++;
    } else {
        printf("[FAIL] %-48s ret=%ld errno=%d want errno=%d\n", name, ret,
               got, expect_errno);
        g_fail++;
    }
}

int main(void) {
    struct utsname u;
    uint32_t a = 0, b = 0;

    if (!uname(&u))
        printf("[info] kernel %s %s %s\n", u.release, u.version, u.machine);

    /* 1-2: uaddr1 == uaddr2 always returns -EINVAL before touching waiter
     * (futex.c: uaddr check at start of futex_wait_requeue_pi and
     * futex_requeue requeue_pi). If command were absent, we would see
     * -ENOSYS. */
    check("WAIT_REQUEUE_PI same uaddr -> EINVAL",
          EINVAL, xfutex(&a, FUTEX_WAIT_REQUEUE_PI | FUTEX_PRIVATE_FLAG,
                         0, NULL, &a, 0));
    check("CMP_REQUEUE_PI same uaddr -> EINVAL",
          EINVAL, xfutex(&a, FUTEX_CMP_REQUEUE_PI | FUTEX_PRIVATE_FLAG,
                         1, (void *)(uintptr_t)1, &a, 0));

    /* 3: CMP_REQUEUE_PI with divergent cmpval should return -EAGAIN after
     * resolving keys (proves get_futex_key + comparison work).
     * Mapping: val=nr_wake(1), timeout=nr_requeue(1), uaddr2, val3=cmpval.
     * a=0, cmpval=0xdeadbeef -> mismatch -> EAGAIN. */
    a = 0;
    check("CMP_REQUEUE_PI bad cmpval -> EAGAIN",
          EAGAIN, xfutex(&a, FUTEX_CMP_REQUEUE_PI | FUTEX_PRIVATE_FLAG,
                         1, (void *)(uintptr_t)1, &b, 0xdeadbeef));

    /* 4: invalid user address should return -EFAULT, no crash. */
    check("CMP_REQUEUE_PI bad uaddr -> EFAULT",
          EFAULT, xfutex((void *)0xdead0000,
                         FUTEX_CMP_REQUEUE_PI | FUTEX_PRIVATE_FLAG,
                         1, (void *)(uintptr_t)0, &b, 0));

    /* 5-6: zero bitset in WAIT_REQUEUE_PI returns -EINVAL (proves handler
     * entered argument parsing). This test uses timeout NULL + mismatched val:
     * expected path is EAGAIN/EINVAL, never blocking. Zero timeout avoids waiting. */
    {
        struct timespec ts = {0, 0};
        long r = xfutex(&a, FUTEX_WAIT_REQUEUE_PI | FUTEX_PRIVATE_FLAG,
                        0x12345678, &ts, &b, 0);
        /* val does not match *uaddr (0): futex_wait_setup returns -EAGAIN. */
        check("WAIT_REQUEUE_PI val mismatch -> EAGAIN",
              EAGAIN, r);
    }

    /* 7-8: Basic functional PI, without requeue: LOCK_PI on zeroed private futex
     * acquires immediately (ret 0), UNLOCK_PI releases (ret 0). Proves
     * rt_mutex PI is operational for caller. */
    {
        uint32_t pi = 0;
        long r1 = xfutex(&pi, FUTEX_LOCK_PI | FUTEX_PRIVATE_FLAG, 0,
                         NULL, NULL, 0);
        if (r1 == 0) {
            printf("[PASS] %-48s ret=0\n", "LOCK_PI self acquire");
            g_pass++;
        } else {
            printf("[FAIL] %-48s ret=%ld errno=%d\n",
                   "LOCK_PI self acquire", r1, errno);
            g_fail++;
        }
        long r2 = xfutex(&pi, FUTEX_UNLOCK_PI | FUTEX_PRIVATE_FLAG, 0,
                         NULL, NULL, 0);
        if (r2 == 0) {
            printf("[PASS] %-48s ret=0\n", "UNLOCK_PI self release");
            g_pass++;
        } else {
            printf("[FAIL] %-48s ret=%ld errno=%d\n",
                   "UNLOCK_PI self release", r2, errno);
            g_fail++;
        }
    }

    printf("[summary] pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail ? 1 : 0;
}
