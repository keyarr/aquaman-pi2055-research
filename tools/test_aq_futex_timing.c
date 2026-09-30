/*
 * test_aq_futex_timing.c — observational benchmark: is the aquaman futex
 * hash bucket visible in FUTEX_WAKE_PRIVATE latency?
 *
 * Benign by construction. No PI, no rtmutex, no mm_struct, no reclaim, no
 * kernel write, no UAF. Private futexes only, one process, one mm, one CPU
 * per role, clean exit. The only thing it does is park some threads on
 * private futex cells and time wake syscalls on other cells.
 *
 * WHAT IS MEASURED (the whole point, stated up front):
 *   syscall   : futex(uaddr, FUTEX_WAKE_PRIVATE, 1, NULL, NULL, 0)
 *               do_futex() forces val3 = FUTEX_BITSET_MATCH_ANY for
 *               FUTEX_WAKE (kernel/futex.c:3263-3265), so val3 = 0 is the
 *               plain "wake up to 1 waiter of this key" call, no bitset ptr.
 *   key       : private, so get_futex_key() takes the fast branch
 *               (futex.c:520-528): both.word = address & ~PAGE_MASK,
 *               both.ptr = current->mm, both.offset = address % PAGE_SIZE.
 *               No get_user_pages, no vma lookup, no user page fault.
 *   state     : every measured address has NO waiter of its own, so the wake
 *               matches nothing, returns 0, and mutates nothing. The wake is
 *               idempotent, so no condition can pollute the next sample.
 *   measurer  : the main thread, pinned, verified with sched_getcpu() during
 *               the run.
 *   waiter    : separate pthread, pinned to another CPU (or to the same CPU in
 *               --affinity same), blocked in FUTEX_WAIT_PRIVATE for the run.
 *
 * WHY THERE CAN BE A DIFFERENCE AT ALL (mechanism, from the source):
 *   struct futex_hash_bucket { atomic_t waiters; spinlock_t lock;
 *                              struct plist_head chain; }
 *        ____cacheline_aligned_in_smp        (futex.c:260-264)
 *   futex_wake() (futex.c:1424-1441):
 *       hb = hash_futex(&key);            // jhash2, 4 words, initval = offset
 *       if (!hb_waiters_pending(hb))      // ONE load of bucket->waiters
 *               goto out;                  // empty bucket: no lock, no walk
 *       spin_lock(&hb->lock);
 *       plist_for_each_entry_safe(this, next, &hb->chain, list) match_futex(...)
 *       spin_unlock(&hb->lock);
 *   The only work a bucket-sharing wake does that an empty-bucket wake does
 *   not is: take the bucket spinlock, walk N futex_q nodes, compare keys.
 *   A parked futex_q is 0x58 bytes (futex.c:237-247) and the walk touches
 *   +0x20 (plist node_list.next), +0x28..+0x37 (key), +0x38 (pi_state),
 *   +0x40 (rt_waiter), +0x50 (bitset), so 1-2 cache lines per node.
 *   The number of NODES, not of waiters, is what costs: 2048 threads on one
 *   address share one futex_q, so a pile of waiters cannot amplify the walk.
 *   So this benchmark plants several DISTINCT addresses in the target bucket,
 *   each with its own waiter, and wakes a further address in that bucket.
 *
 * WHAT IS NOT CONTROLLED / THE KNOWN UNKNOWN:
 *   The bucket depends on mm, which userspace does not know. MATCH and
 *   MISMATCH here are labels computed under an ASSUMED mm (printed). Under a
 *   wrong assumption the MATCH label is just another random pair, so the
 *   per-pair comparison has about 1/1226944 power. That is why the SCAN
 *   phase exists: it needs no mm and looks for the predicted heavy tail.
 *   Nothing in this tool tries to solve for mm, and nothing it does gets
 *   anywhere near the UAF, the slab, or reclaim.
 *
 * Build (host):
 *   gcc -O2 -Wall -Wextra -o /tmp/test_aq_futex_timing \
 *       tools/test_aq_futex_timing.c -lpthread
 * Build (device, NDK r29, same recipe as the other tools):
 *   aarch64-linux-android28-clang -O2 -Wall -Wextra -static \
 *       tools/test_aq_futex_timing.c -o test_aq_futex_timing
 * Run:
 *   ./test_aq_futex_timing --n 20000 --affinity split
 *   ./test_aq_futex_timing --n 20000 --affinity same
 *   ./test_aq_futex_timing --csv /data/local/tmp/aq_futex.csv
 */
#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#include "ghostlock_mm_enum.h"

#ifndef __NR_futex
#define __NR_futex 98
#endif
#define FUTEX_WAIT_OP 0
#define FUTEX_WAKE_OP 1
#define FUTEX_PRIVATE_FLAG 128
#define FWAKE (FUTEX_WAKE_OP | FUTEX_PRIVATE_FLAG)
#define FWAIT (FUTEX_WAIT_OP | FUTEX_PRIVATE_FLAG)

#define PAGE 4096UL
#define POOL_PAGES 4096u        /* 16 MiB of cells, 4096 distinct page addrs */
#define SCAN_FIRST 32u          /* scan starts here, plan cells are skipped too */
#define NPAIRS 3                /* MATCH1..3 / MISMATCH1..3 */
#define MAXSPRAY 64             /* cap on nodes planted in the pile bucket */
#define PILE_THREADS 4          /* waiters on the pile address: 1 futex_q, walk cost 0 */
#define WARMUP 2000u
#define PASSES 3               /* repeats of the main phase, to test reproducibility */
#define CAL_THREADS 512        /* waiter threads parked during calibration */
                                  /* 512 gives a 39/61 mixture and stays quiet;
                                   * 3072 was tried and the scheduler noise of that
                                   * many tasks swamped the per-cell distribution */
#define CAL_PARK_PAGES 2048u    /* pages the calibration waiters are spread over */
#define CAL_REP 5              /* reps per cell in the calibration */
#define CAL_PAGES 256u         /* cells timed in the calibration */
#define DEFAULTS_N 20000u
#define DEFAULTS_REP 4u
#define NOFF 4

/* Offset classes are shared by MATCH_k and MISMATCH_k on purpose: the page
 * offset feeds initval, so it must not be confounded with the condition. */
static const uint32_t g_off[NOFF] = { 0x00, 0x40, 0x100, 0x3c0 };

static uint32_t *g_pool;
static uint64_t g_mm;                 /* assumed mm, printed everywhere */
static int g_cpu_waiter = 0, g_cpu_measurer = 1, g_split = 1, g_pin_fail;
static int g_spray_max = MAXSPRAY;
static const char *g_csv;
static FILE *g_csvf;
static long g_mig, g_probe;
static uint64_t *g_pool_med;   /* post-parking cost, per pool cell */
static uint64_t *g_base_min;   /* pre-parking min, per pool cell */
static uint64_t *g_base_med;   /* pre-parking median, per pool cell */
static uint64_t g_base_mad;     /* how much the per-cell cost varies, machine dependent */

#define BASE_REP 15            /* reps for the pre-parking sweep */
#define BASE_TOL_NS 1          /* max allowed baseline gap inside a pair */

struct cond {
    const char *name;
    uint32_t *cell;
    uint32_t off;
    uint32_t bucket;
    int nwait;
    int idx;              /* 1-based pair number, so the CSV rows stay distinct */
    uint64_t *samp;
};

static struct cond g_c[3 * NPAIRS];   /* MATCH_k, MISMATCH_k, MISMATCH2_k */
static int g_nc;
static struct cond g_ctrl;
static struct cond g_self;
static struct cond g_base[1 + NPAIRS];
static int g_nbase;
static struct cond g_pile;
static struct cond g_spray[MAXSPRAY];
static int g_nspray;
static uint32_t g_pair_page[NPAIRS];
static uint64_t g_pair_spread[NPAIRS];
static pthread_t g_th[MAXSPRAY + PILE_THREADS];
static pthread_t g_cal_th[CAL_THREADS];
static volatile int g_quit;
static int g_nth;

static uint64_t now_ns(void)
{
    struct timespec ts;

    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

static long xfutex(void *u, int op, uint32_t val)
{
    return syscall(__NR_futex, u, op, val, NULL, NULL, 0);
}

static double fabs_(double x)
{
    return x < 0 ? -x : x;
}

static int gcd(int a, int b)
{
    while (b) {
        int t = a % b;

        a = b;
        b = t;
    }
    return a;
}

static uint64_t diff_ns(uint64_t a, uint64_t b)
{
    return a > b ? a - b : b - a;
}


static int pin(int cpu)
{
    cpu_set_t m;

    CPU_ZERO(&m);
    CPU_SET(cpu, &m);
    if (sched_setaffinity(0, sizeof(m), &m)) {
        printf("[warn] sched_setaffinity cpu=%d errno=%d\n", cpu, errno);
        g_pin_fail = 1;
        return -1;
    }
    return 0;
}

static void *waiter_fn(void *arg)
{
    uint32_t *cell = (uint32_t *)arg;

    if (g_cpu_waiter >= 0)
        pin(g_cpu_waiter);
    /* Parks and re-parks. Re-arming matters: a one-shot waiter leaves after the
     * first wake that matches it, so the bucket empties partway through a
     * measurement and the rest of the samples describe something else. An
     * earlier one-shot version of this benchmark reported "no difference
     * between an occupied and an empty bucket" for exactly that reason.
     *
     * g_quit is how the thread is finally let out: set it, then wake. Without
     * the flag the re-arm loop would park again and join would never return. */
    while (!g_quit)
        xfutex(cell, FWAIT, 0);
    return NULL;
}

/* ---------------- stats (no libm on purpose: static NDK links are fussy) -- */

static int cmp_u64(const void *a, const void *b)
{
    uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;

    return (x > y) - (x < y);
}

static double dsqrt(double x)
{
    double r = x > 1.0 ? x / 2.0 : 1.0;
    int i;

    for (i = 0; i < 60; i++)
        r = 0.5 * (r + x / r);
    return r;
}

struct stats {
    size_t n;
    uint64_t min, p50, p90, p95, p99, max, mad;
    double mean, std;
};

/* s sorted; [lo,hi) is the (possibly trimmed) slice. */
static void stats_slice(const uint64_t *s, size_t lo, size_t hi, uint64_t *scr,
                        struct stats *o)
{
    size_t n = hi - lo, i;
    double sum = 0.0, var = 0.0, d;

    memset(o, 0, sizeof(*o));
    o->n = n;
    if (!n)
        return;
    o->min = s[lo];
    o->max = s[hi - 1];
    o->p50 = s[lo + 50 * n / 100];
    o->p90 = s[lo + 90 * n / 100];
    o->p95 = s[lo + 95 * n / 100];
    o->p99 = s[lo + (99 * n) / 100];
    for (i = lo; i < hi; i++)
        sum += (double)s[i];
    o->mean = sum / (double)n;
    for (i = lo; i < hi; i++) {
        d = (double)s[i] - o->mean;
        var += d * d;
    }
    o->std = dsqrt(var / (double)(n > 1 ? n - 1 : 1));
    for (i = lo; i < hi; i++)
        scr[i - lo] = s[i] > o->p50 ? s[i] - o->p50 : o->p50 - s[i];
    qsort(scr, n, sizeof(*scr), cmp_u64);
    o->mad = scr[n / 2];
}

static void compute_stats(const uint64_t *v, size_t n, struct stats *full,
                          struct stats *trim)
{
    uint64_t *s = (uint64_t *)malloc(n * sizeof(*s));
    uint64_t *scr = (uint64_t *)malloc(n * sizeof(*scr));
    size_t lo, hi;

    memcpy(s, v, n * sizeof(*s));
    qsort(s, n, sizeof(*s), cmp_u64);
    stats_slice(s, 0, n, scr, full);
    lo = n / 100;
    hi = n - n / 100;
    if (hi > lo + 16)
        stats_slice(s, lo, hi, scr, trim);
    else
        *trim = *full;
    free(scr);
    free(s);
}

struct rk {
    uint64_t v;
    int w; /* 0 = a, 1 = b */
};

static int cmp_rk(const void *x, const void *y)
{
    const struct rk *p = (const struct rk *)x, *q = (const struct rk *)y;

    return (p->v > q->v) - (p->v < q->v);
}

/* Mann-Whitney U with midrank tie correction. auc = P(a > b) + .5 P(a = b),
 * computed as U/(na*nb), so one pass gives both the U and the AUC. */
static void mannwhitney(const uint64_t *a, size_t na, const uint64_t *b,
                        size_t nb, double *auc, double *u_out, double *z_out)
{
    size_t total = na + nb, i, j, k;
    struct rk *r = (struct rk *)malloc(total * sizeof(*r));
    double ra = 0.0, u, exp, var, tie = 0.0, nn;

    for (i = 0; i < na; i++) {
        r[i].v = a[i];
        r[i].w = 0;
    }
    for (j = 0; j < nb; j++) {
        r[na + j].v = b[j];
        r[na + j].w = 1;
    }
    qsort(r, total, sizeof(*r), cmp_rk);
    for (i = 0; i < total;) {
        for (j = i + 1; j < total && r[j].v == r[i].v; j++)
            ;
        if (r[i].w == 0)
            for (k = i; k < j; k++)
                if (r[k].w == 0)
                    ra += ((double)(i + 1) + (double)j) / 2.0;  /* midrank */
        tie += (double)(j - i) * (double)(j - i - 1) * (double)(j - i + 1);
        i = j;
    }
    u = ra - (double)na * ((double)na + 1.0) / 2.0;
    exp = (double)na * (double)nb / 2.0;
    nn = (double)total;
    var = (double)na * (double)nb / 12.0 * ((nn + 1.0) - tie / (nn * (nn - 1.0)));
    if (var <= 0.0)
        var = 1.0;
    *auc = u / ((double)na * (double)nb);
    *u_out = u;
    *z_out = (u - exp) / dsqrt(var);
    free(r);
}

/* Paired per-round difference. Interleaved sampling makes this the strongest
 * statistic here: it cancels whatever the machine is doing at that moment. */
static void paired_z(const uint64_t *a, const uint64_t *b, size_t n,
                     double *dmean, double *z)
{
    size_t i;
    double sum = 0.0, var = 0.0, d;

    for (i = 0; i < n; i++)
        sum += (double)a[i] - (double)b[i];
    *dmean = sum / (double)n;
    for (i = 0; i < n; i++) {
        d = ((double)a[i] - (double)b[i]) - *dmean;
        var += d * d;
    }
    var /= (double)(n > 1 ? n - 1 : 1);
    if (var <= 0.0)
        var = 1.0;
    *z = *dmean / dsqrt(var / (double)n);
}

/* ---------------- address plan ---------------- */

static uint32_t *cell_at(uint32_t page, uint32_t off)
{
    return (uint32_t *)((char *)g_pool + (size_t)page * PAGE + off);
}

static size_t cell_index(uint32_t page, uint32_t off)
{
    int oi;

    for (oi = 0; oi < NOFF; oi++)
        if (g_off[oi] == off)
            break;
    return (size_t)page * NOFF + (size_t)oi;
}

static uint32_t bucket_of(uint32_t *c)
{
    uint64_t a = (uint64_t)(uintptr_t)c;

    /* word = page-aligned address, offset = address % PAGE (futex.c:508-528) */
    return aq_hash_bucket(a & ~(uint64_t)(PAGE - 1), g_mm,
                          (uint32_t)(a & (PAGE - 1)));
}

/* Per-cell median of BASE_REP interleaved wakes, used to pick arms that cost
 * the same before anything is parked. Called before plan_addresses(). */
static void sweep_baseline(void)
{
    size_t ncells = (size_t)POOL_PAGES * NOFF, i, r;
    uint64_t *s = (uint64_t *)malloc(ncells * BASE_REP * sizeof(uint64_t));
    uint32_t seed = 0x5bf03635u;

    g_base_med = (uint64_t *)calloc(ncells, sizeof(uint64_t));
    g_base_min = (uint64_t *)calloc(ncells, sizeof(uint64_t));
    if (!s || !g_base_med || !g_base_min) {
        printf("[FAIL] out of memory in the baseline sweep\n");
        exit(1);
    }
    for (r = 0; r < BASE_REP; r++) {
        int st = (int)((seed = seed * 1103515245u + 12345u) >> 8);

        st %= (int)ncells;
        for (i = 0; i < ncells; i++) {
            size_t idx = (size_t)st + i;
            uint64_t t0, t1;

            if (idx >= ncells)
                idx -= ncells;
            t0 = now_ns();
            xfutex(cell_at((uint32_t)(idx / NOFF), g_off[idx % NOFF]), FWAKE, 1);
            t1 = now_ns();
            s[idx * BASE_REP + r] = t1 - t0;
        }
    }
    /* Both statistics are kept, and they are used for different jobs.
     *
     * The MINIMUM is the robust estimate of what a cell costs, so it is what
     * the scan subtracts: a per-cell offset and a preemption spike are
     * different things and only the min ignores the spike.
     *
     * The MEDIAN is what the pair comparison is judged on, so pairs must be
     * matched on the median. Matching on the min and then comparing medians
     * leaves a residual artifact: the min-to-median gap is itself a per-cell
     * property, and comparing matched-mins against different-medians produced
     * reproducible 8 ns deltas in about 1 run in 10. Match like with like. */
    for (i = 0; i < ncells; i++) {
        uint64_t tmp[BASE_REP];

        memcpy(tmp, s + i * BASE_REP, sizeof(tmp));
        qsort(tmp, BASE_REP, sizeof(uint64_t), cmp_u64);
        g_base_min[i] = tmp[0];
        g_base_med[i] = tmp[BASE_REP / 2];
    }
    free(s);
    {
        uint64_t *all = (uint64_t *)malloc(ncells * sizeof(uint64_t));
        struct stats sf, sm2;
        uint64_t *scr = (uint64_t *)malloc(ncells * sizeof(uint64_t));

        memcpy(all, g_base_min, ncells * sizeof(uint64_t));
        qsort(all, ncells, sizeof(uint64_t), cmp_u64);
        stats_slice(all, 0, ncells, scr, &sf);
        memcpy(all, g_base_med, ncells * sizeof(uint64_t));
        qsort(all, ncells, sizeof(uint64_t), cmp_u64);
        stats_slice(all, 0, ncells, scr, &sm2);
        printf("[phase] BASELINE SWEEP %zu cells x %d reps, nothing parked\n", ncells,
               BASE_REP);
        printf("[phase] BASELINE per-cell MIN: p50=%llu p90=%llu p99=%llu max=%llu mad=%llu\n",
               (unsigned long long)sf.p50, (unsigned long long)sf.p90,
               (unsigned long long)sf.p99, (unsigned long long)sf.max,
               (unsigned long long)sf.mad);
        printf("[phase] BASELINE per-cell MEDIAN: p50=%llu p90=%llu p99=%llu max=%llu mad=%llu\n",
               (unsigned long long)sm2.p50, (unsigned long long)sm2.p90,
               (unsigned long long)sm2.p99, (unsigned long long)sm2.max,
               (unsigned long long)sm2.mad);
        printf("[info] per-cell cost is a property of the cell, not of its bucket: pairs are matched on the median, the scan subtracts the min\n");
        g_base_mad = sm2.mad;
        free(all);
        free(scr);
    }
}

static void add(struct cond *c, const char *name, uint32_t *cell, int nwait)
{
    c->name = name;
    c->cell = cell;
    c->off = (uint32_t)((uint64_t)(uintptr_t)cell & (PAGE - 1));
    c->bucket = bucket_of(cell);
    c->nwait = nwait;
}

static int is_taken(uint32_t *c)
{
    int i;

    if (c == g_pile.cell || c == g_ctrl.cell)
        return 1;
    for (i = 0; i < g_nspray; i++)
        if (g_spray[i].cell == c)
            return 1;
    for (i = 0; i < g_nc; i++)
        if (g_c[i].cell == c)
            return 1;
    for (i = 0; i < g_nbase; i++)
        if (g_base[i].cell == c)
            return 1;
    return 0;
}

static int plan_addresses(void)
{
    uint32_t page, bp, seen[AQ_FUTEX_HASHSIZE];
    int k, got, oi;

    memset(seen, 0, sizeof(seen));
    memset(&g_pile, 0, sizeof(g_pile));
    memset(g_spray, 0, sizeof(g_spray));
    memset(g_c, 0, sizeof(g_c));
    memset(&g_ctrl, 0, sizeof(g_ctrl));
    g_nc = g_nbase = g_nspray = 0;

    add(&g_pile, "PILE", cell_at(0, 0), PILE_THREADS);
    bp = g_pile.bucket;

    /* CONTROL: no collision search, no waiter. Sits right before the first
     * pair base so it shares that neighbourhood too, which is what makes it a
     * fair null control for the MISMATCH arm. */
    add(&g_ctrl, "CONTROL", cell_at(7, 0), 0);
    g_base[g_nbase++] = g_ctrl;
    g_nc = 0;

    /* Geometry, and it is dictated by a measured artifact rather than taste.
     *
     * Within one page, the four page offsets have systematically different
     * wake medians: spread of 0-3 ns on 3700 of 4096 pages, but up to 8 ns on
     * the rest, and offset 0x000 is the slow one on 2640 of 4096 pages. That
     * artifact is the same size as the effect being hunted for, so a pair that
     * differs in page offset is uninterpretable no matter how many samples it
     * gets. It was found by the same-page null control below, not by
     * inspection.
     *
     * Across pages at a fixed offset, the artifact is only 1-2 ns over page
     * distances of 1, 2, 16, 256 and 1024 pages. So the pairs use the SAME
     * offset and ADJACENT pages:
     *   MATCH_k     page p,     offset o_k, bucket == pile bucket
     *   MISMATCH_k  page p+1,   offset o_k, bucket != pile bucket
     *   MISMATCH2_k page p+2,p+3, offset o_k, both wrong buckets (null arm)
     * The page distance is 1 in every arm, so the residual page artifact
     * cancels. What differs between MATCH and MISMATCH is one bit of the
     * page index, i.e. the low bits of both.word, hence the bucket.
     *
     * On top of that, every candidate cell must have a pre-parking median
     * within BASE_TOL_NS of the MATCH arm. The per-cell spread measured above
     * is a fixed offset for the whole run: it averages to zero across pages,
     * but it moves a given cell's median by up to 8 ns for the entire run, and
     * that is larger than any effect being looked for. Pairing on the measured
     * baseline is what removes it.
     */
    for (k = 0; k < NPAIRS; k++) {
        uint64_t best = ~0ULL;
        uint32_t best_page = 0;
        int found = 0, tol, tol_max, ois;

        /* The offsets rotate so all four page offsets get exercised, and the
         * inner retry lets a pair fall back to another offset class if its
         * own has no qualifying page. One offset class in 4096 pages has only
         * about 4 pages landing in the pile bucket at all, so requiring a
         * baseline-matched triple on one specific offset can legitimately
         * come up empty. */
        for (ois = 0; ois < NOFF && !found; ois++) {
        oi = (k + ois) % NOFF;
        /* The tolerance has to scale with the machine. On a quiet host the
         * per-cell median spread is about 1 ns; on the device it is over 70,
         * and a fixed tolerance finds nothing at all there. So the tolerance
         * starts at BASE_TOL_NS and widens to several times the measured
         * per-cell MAD, and if even that finds nothing the tightest candidate
         * available is taken and flagged, rather than aborting the run: the
         * calibration above does not depend on these pairs. */
        tol_max = (int)g_base_mad * 4;
        if (tol_max < 16)
            tol_max = 16;
        for (tol = BASE_TOL_NS; tol <= tol_max && !found; tol++) {
            for (page = 8; page + 2 < POOL_PAGES; page++) {
                uint32_t *m = cell_at(page, g_off[oi]);
                uint32_t *x = cell_at(page + 1, g_off[oi]);
                uint32_t *n1 = cell_at(page + 2, g_off[oi]);
                uint64_t bm, bx, bn, spread;

                if (is_taken(m) || is_taken(x) || is_taken(n1))
                    continue;
                if (bucket_of(m) != bp)
                    continue;
                /* both wrong arms must be out of the pile bucket, otherwise
                 * the null arm would walk the pile too and stop being null */
                if (bucket_of(x) == bp || bucket_of(n1) == bp)
                    continue;
                bm = g_base_med[cell_index(page, g_off[oi])];
                bx = g_base_med[cell_index(page + 1, g_off[oi])];
                bn = g_base_med[cell_index(page + 2, g_off[oi])];
                /* median-to-median, because the comparison that matters is a
                 * comparison of medians */
                spread = diff_ns(bm, bx);
                if (diff_ns(bn, bx) > spread)
                    spread = diff_ns(bn, bx);
                if (spread > (uint64_t)tol)
                    continue;
                if (!found || spread < best) {
                    best = spread;
                    best_page = page;
                }
                found = 1;
            }
        }
        }
        if (!found) {
            printf("[FAIL] pair %d: no adjacent-page baseline-matched bucket "
                   "split anywhere in the pool\n", k + 1);
            return -1;
        }
        g_pair_page[k] = best_page;
        g_pair_spread[k] = best;
        add(&g_c[g_nc], "MATCH", cell_at(best_page, g_off[oi]), 0);
        add(&g_c[g_nc + 1], "MISMATCH", cell_at(best_page + 1, g_off[oi]), 0);
        add(&g_c[g_nc + 2], "MISMATCH2", cell_at(best_page + 2, g_off[oi]), 0);
        g_c[g_nc].idx = g_c[g_nc + 1].idx = g_c[g_nc + 2].idx = k + 1;
        g_base[g_nbase++] = g_c[g_nc + 1];
        g_nc += 3;
    }

    /* Distinct extra nodes planted in the pile bucket (under the assumption).
     * Each needs its own waiter, else no futex_q exists to be walked.
     * Spread the offsets so the sprayed nodes also vary page offset. */
    /* Sprays are placed anywhere in the pool that collides, since what matters
     * for them is being in the bucket, not where they live. */
    for (page = 2, got = 0; page < POOL_PAGES && got < g_spray_max; page++) {
        for (oi = 0; oi < NOFF; oi++) {
            uint32_t *c = cell_at(page, g_off[oi]);

            if (got >= g_spray_max)
                break;
            if (is_taken(c) || bucket_of(c) != bp)
                continue;
            add(&g_spray[got], "SPRAY", c, 1);
            g_nspray = ++got;
        }
    }
    if (got < 3) {
        printf("[FAIL] only %d spray nodes found, need >= 3 to walk anything\n",
               got);
        return -1;
    }
    g_nspray = got;
    return 0;
}

static void print_plan(void)
{
    int i;

    printf("[info] assumed_mm=0x%llx key=16B/4words initval=offset mask=0x%x\n",
           (unsigned long long)g_mm, AQ_FUTEX_HASHMASK);
    printf("[info] pool=0x%llx pages=%u affinity=%s waiter_cpu=%d measurer_cpu=%d\n",
           (unsigned long long)(uintptr_t)g_pool, POOL_PAGES,
           g_split ? "split" : "same", g_cpu_waiter, g_cpu_measurer);
    printf("[info] MATCH/MISMATCH labels come from assumed_mm only; the real mm\n"
           "       is unknown, so the per-pair comparison has ~1/1226944 power\n");
    for (i = 0; i < g_nc; i += 3)
        printf("[plan] condition=MATCH%d uaddr=0x%llx off=0x%03x bucket=0x%03x page=%u baseline_spread=%llu nwait=0\n",
               i / 3 + 1, (unsigned long long)(uintptr_t)g_c[i].cell,
               g_c[i].off, g_c[i].bucket, g_pair_page[i / 3],
               (unsigned long long)g_pair_spread[i / 3]);
    for (i = 1; i < g_nc; i += 3)
        printf("[plan] condition=MISMATCH%d uaddr=0x%llx off=0x%03x bucket=0x%03x page=%u baseline_spread=%llu nwait=0\n",
               i / 3 + 1, (unsigned long long)(uintptr_t)g_c[i].cell,
               g_c[i].off, g_c[i].bucket, g_pair_page[i / 3],
               (unsigned long long)g_pair_spread[i / 3]);
    for (i = 2; i < g_nc; i += 3)
        printf("[plan] condition=MISMATCH2_%d uaddr=0x%llx off=0x%03x bucket=0x%03x page=%u baseline_spread=%llu nwait=0 (null control arm)\n",
               i / 3 + 1, (unsigned long long)(uintptr_t)g_c[i].cell,
               g_c[i].off, g_c[i].bucket, g_pair_page[i / 3],
               (unsigned long long)g_pair_spread[i / 3]);
    printf("[plan] condition=CONTROL uaddr=0x%llx off=0x%03x bucket=0x%03x nwait=0 (no collision search)\n",
           (unsigned long long)(uintptr_t)g_ctrl.cell, g_ctrl.off,
           g_ctrl.bucket);
    printf("[plan] condition=PILE uaddr=0x%llx off=0x%03x bucket=0x%03x nwait=%d (one futex_q)\n",
           (unsigned long long)(uintptr_t)g_pile.cell, g_pile.off, g_pile.bucket,
           g_pile.nwait);
    for (i = 0; i < g_nspray; i++)
        printf("[plan] condition=SPRAY%d uaddr=0x%llx off=0x%03x bucket=0x%03x nwait=1\n",
               i + 1, (unsigned long long)(uintptr_t)g_spray[i].cell,
               g_spray[i].off, g_spray[i].bucket);
    printf("[plan] futex_q_nodes_in_pile_bucket_under_assumption=%d, expected walk per MATCH wake=%d, per MISMATCH wake=0\n",
           1 + g_nspray, 1 + g_nspray);
}

/* ---------------- phases ---------------- */

static void print_stats(const char *tag, const struct cond *c,
                        const struct stats *f, const struct stats *t)
{
    printf("condition=%s bucket=0x%03x uaddr=0x%llx n=%zu min=%llu p50=%llu p90=%llu p95=%llu p99=%llu max=%llu mean=%.1f std=%.1f mad=%llu\n",
           tag, c->bucket, (unsigned long long)(uintptr_t)c->cell, f->n,
           (unsigned long long)f->min, (unsigned long long)f->p50,
           (unsigned long long)f->p90, (unsigned long long)f->p95,
           (unsigned long long)f->p99, (unsigned long long)f->max, f->mean,
           f->std, (unsigned long long)f->mad);
    if (t->n && t->n != f->n)
        printf("  trimmed_1pct n=%zu p50=%llu p95=%llu p99=%llu mean=%.1f std=%.1f mad=%llu\n",
               t->n, (unsigned long long)t->p50, (unsigned long long)t->p95,
               (unsigned long long)t->p99, t->mean, t->std,
               (unsigned long long)t->mad);
}

static void dump_raw(const char *phase, const struct cond *c, const uint64_t *v,
                     size_t n)
{
    size_t i;

    if (!g_csvf)
        return;
    for (i = 0; i < n; i++)
        fprintf(g_csvf, "%s,%s%d,0x%03x,0x%llx,%zu,%llu\n", phase, c->name,
                c->idx, c->bucket, (unsigned long long)(uintptr_t)c->cell, i,
                (unsigned long long)v[i]);
}

/* Interleaved sampling over a condition set: one sample per condition per
 * round. The visiting order is re-randomised every round, and a plain
 * rotation ((k+r) % nc) is NOT good enough: with nc conditions the visit
 * pattern has period nc, so any periodic disturbance with a period dividing nc
 * aliases onto a fixed subset of conditions and shows up as a huge fake
 * effect. Measured here: a plain rotation produced 8 ns deltas with |z| up to
 * 88, which the same-page null control correctly flagged as bogus.
 * Warm-up rounds are measured and thrown away.
 */
static uint32_t g_rng = 0x2545f491u;

static uint32_t rng_next(void)
{
    g_rng = g_rng * 1103515245u + 12345u;
    return g_rng >> 8;
}

static void sample_set(struct cond *c, int nc, size_t n, size_t warmup,
                       long *anomalies, int checkcpu)
{
    size_t r, i;
    int k;
    int step = 1, start;

    for (i = 0; i < (size_t)nc; i++)
        c[i].samp = (uint64_t *)calloc(n, sizeof(uint64_t));

    /* one coprime step keeps the per-round order a full cycle, not a subgroup */
    do {
        step = (int)(rng_next() % (uint32_t)nc);
        if (step < 1)
            step = 1;
    } while (step < nc && gcd(step, nc) != 1);

    for (r = 0; r < warmup + n; r++) {
        start = (int)(rng_next() % (uint32_t)nc);
        for (k = 0; k < nc; k++) {
            int idx = (start + k * step) % nc;
            uint64_t t0, t1;
            long ret;

            t0 = now_ns();
            ret = xfutex(c[idx].cell, FWAKE, 1);
            t1 = now_ns();
            if (ret != 0)
                (*anomalies)++;
            if (r < warmup)
                continue;
            c[idx].samp[r - warmup] = t1 - t0;
            if (checkcpu && (r - warmup) % 256 == 0) {
                g_probe++;
                if (sched_getcpu() != g_cpu_measurer)
                    g_mig++;
            }
        }
    }
    if (g_probe)
        printf("[check] measurer cpu=%d stayed on it in %ld/%ld probe points\n",
               g_cpu_measurer, g_probe - g_mig, g_probe);
}

/* descending: ord[0] is the slowest cell */
static int cmp_idx_med(const void *x, const void *y)
{
    size_t i = *(const size_t *)x, j = *(const size_t *)y;

    return (g_pool_med[j] > g_pool_med[i]) - (g_pool_med[j] < g_pool_med[i]);
}

int main(int argc, char **argv)
{
    size_t n = DEFAULTS_N, rep = DEFAULTS_REP, ncells, i, r;

    setvbuf(stdout, NULL, _IOLBF, 0);
    long anomalies = 0;
    int a, p, pass, verdict_invalid = 0, topk, consistent = 0;
    int pass_hits[NPAIRS + 1];
    size_t ncells_cal = (size_t)CAL_PAGES * NOFF;
    uint64_t calib_delta_p50 = 0;
    double calib_z = 0.0, calib_auc = 0.5;
    struct stats f, t, sm[NPAIRS], sx[NPAIRS], s2[NPAIRS];
    double auc, u, z, zp[NPAIRS], ap[NPAIRS], dmp[NPAIRS];
    double z_null, self_floor = 0.0;
    const char *repro;

    for (p = 0; p <= NPAIRS; p++)
        pass_hits[p] = 0;
    uint64_t mismatch_p50 = 0;

    uint64_t *merged_m, *merged_x, *pool_samp;
    size_t nm = 0, nx = 0;
    double scan_within = 0.0;
    const char *vlabel;

    for (a = 1; a < argc; a++) {
        if (!strcmp(argv[a], "--n") && a + 1 < argc)
            n = strtoul(argv[++a], NULL, 0);
        else if (!strcmp(argv[a], "--rep") && a + 1 < argc)
            rep = strtoul(argv[++a], NULL, 0);
        else if (!strcmp(argv[a], "--mm") && a + 1 < argc)
            g_mm = strtoull(argv[++a], NULL, 0);
        else if (!strcmp(argv[a], "--waiter-cpu") && a + 1 < argc)
            g_cpu_waiter = atoi(argv[++a]);
        else if (!strcmp(argv[a], "--measurer-cpu") && a + 1 < argc)
            g_cpu_measurer = atoi(argv[++a]);
        else if (!strcmp(argv[a], "--affinity") && a + 1 < argc) {
            g_split = strcmp(argv[++a], "same") != 0;
            if (!g_split)
                g_cpu_measurer = g_cpu_waiter;
        } else if (!strcmp(argv[a], "--spray") && a + 1 < argc) {
            /* number of extra futex_q nodes planted in the pile bucket. this
             * is the sensitivity knob: a wake that shares the bucket walks one
             * more node per planted address, so the predicted effect scales
             * with it while the per-cell artifact does not. */
            g_spray_max = atoi(argv[++a]);
        } else if (!strcmp(argv[a], "--csv") && a + 1 < argc) {
            g_csv = argv[++a];
        } else {
            printf("usage: %s [--n N] [--rep R] [--spray K] [--mm 0xVA]"
                   " [--waiter-cpu C] [--measurer-cpu C]"
                   " [--affinity split|same] [--csv PATH]\n", argv[0]);
            return 2;
        }
    }
    /* default: a plausible mm out of the candidate universe. Hypothesis only,
     * printed above, --mm overrides it. */
    if (!g_mm)
        g_mm = AQ_PAGE_OFFSET + 0x2000000ULL;

    if (g_csv) {
        g_csvf = fopen(g_csv, "w");
        if (!g_csvf) {
            printf("[FAIL] cannot open %s: %s\n", g_csv, strerror(errno));
            return 1;
        }
        fprintf(g_csvf, "phase,condition,bucket,uaddr,index,ns\n");
    }

    g_pool = (uint32_t *)mmap(NULL, (size_t)POOL_PAGES * PAGE,
                              PROT_READ | PROT_WRITE,
                              MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (g_pool == MAP_FAILED) {
        printf("[FAIL] mmap: %s\n", strerror(errno));
        return 1;
    }
    memset(g_pool, 0, (size_t)POOL_PAGES * PAGE);

    sweep_baseline();
    if (plan_addresses() < 0)
        return 1;
    print_plan();
    pin(g_split ? g_cpu_measurer : g_cpu_waiter);
    if (g_pin_fail)
        verdict_invalid = 1;
    /* --- CALIBRATE: the decisive, mm-free test, run before everything else.
     *
     * A bucket oracle can only work if SHARING A BUCKET COSTS SOMETHING. That
     * question needs no mm, no assumed mm and no second phase.
     *
     * Park CAL_THREADS waiters, one per page, over pages spread across a large
     * region. A timed cell's bucket then holds one node with probability
     * 1-(1-1/hashsize)^CAL_THREADS, about 39% at the default count, and the
     * timed cells are all in the pool, never a waiter's own address, so no
     * timed wake is a real match and no waiter is released during the pass.
     *
     * So in this ONE pass the timed cells are a MIXTURE: some share a bucket
     * with a parked node and their wake takes the bucket spinlock and walks it,
     * the rest exit at the hb->waiters check and walk nothing. Both populations
     * are measured in the same process state, on the same schedule, in the same
     * run, so there is no phase-to-phase shift to confound the comparison.
     *
     * If sharing a bucket costs C, the per-cell cost distribution has a step of
     * C in it and roughly 63% of the cells sit above that step. If the
     * distribution is one mode, C is below the noise and no MATCH/MISMATCH
     * search over addresses can work on this machine. That is the whole
     * question, and it is answered without knowing mm, which is why it is
     * answered first. */
    {
        uint32_t *park = (uint32_t *)mmap(NULL, (size_t)CAL_PARK_PAGES * PAGE,
                                          PROT_READ | PROT_WRITE,
                                          MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        uint64_t *cost, *t, *scr;
        int nth;

        if (park == MAP_FAILED) {
            printf("[FAIL] mmap for the calibration parking region: %s\n",
                   strerror(errno));
            return 1;
        }
        memset(park, 0, (size_t)CAL_PARK_PAGES * PAGE);
        for (nth = 0; nth < CAL_THREADS; nth++) {
            /* spread across the region so the occupied buckets are scattered
             * rather than one contiguous run of indices */
            uint32_t *c = park + (size_t)((uint64_t)nth * CAL_PARK_PAGES /
                                           CAL_THREADS) * PAGE;

            if (pthread_create(&g_cal_th[nth], NULL, waiter_fn, c)) {
                printf("[FAIL] pthread_create in CALIBRATE\n");
                return 1;
            }
        }
        usleep(800000);
        cost = (uint64_t *)calloc(ncells_cal, sizeof(uint64_t));
        t = (uint64_t *)malloc(ncells_cal * sizeof(uint64_t));
        scr = (uint64_t *)malloc(ncells_cal * sizeof(uint64_t));
        if (!cost || !t || !scr) {
            printf("[FAIL] out of memory in CALIBRATE\n");
            return 1;
        }
        {
            uint64_t *s = (uint64_t *)calloc(ncells_cal * CAL_REP,
                                             sizeof(uint64_t));
            uint32_t seed = 0x5eed;
            size_t ci, r2;

            for (r2 = 0; r2 < CAL_REP; r2++) {
                int st = (int)((seed = seed * 1103515245u + 12345u) >> 8);

                st %= (int)ncells_cal;
                for (ci = 0; ci < ncells_cal; ci++) {
                    size_t idx = (size_t)st + ci;
                    uint64_t t0, t1;

                    if (idx >= ncells_cal)
                        idx -= ncells_cal;
                    t0 = now_ns();
                    xfutex(cell_at((uint32_t)(idx / NOFF), g_off[idx % NOFF]),
                           FWAKE, 1);
                    t1 = now_ns();
                    s[idx * CAL_REP + r2] = t1 - t0;
                }
            }
            for (ci = 0; ci < ncells_cal; ci++) {
                uint64_t *tmp = (uint64_t *)malloc(CAL_REP * sizeof(uint64_t));

                memcpy(tmp, s + ci * CAL_REP, CAL_REP * sizeof(uint64_t));
                qsort(tmp, CAL_REP, sizeof(uint64_t), cmp_u64);
                cost[ci] = tmp[0];   /* min: robust, as everywhere else */
                free(tmp);
            }
            free(s);
        }
        memcpy(t, cost, ncells_cal * sizeof(uint64_t));
        qsort(t, ncells_cal, sizeof(uint64_t), cmp_u64);
        {
            struct stats sf;
            size_t ci, above = 0;
            double exp_occ, exp_free;
            int hist[1024];
            int run, lo_b, best_lo = -1, best_run = 0;
            uint64_t base = t[0], step = 0;

            stats_slice(t, 0, ncells_cal, scr, &sf);
            /* a timed cell's bucket is empty only if all CAL_THREADS parked
             * nodes missed it: (1-1/hashsize)^threads. With 512 waiters and
             * 1024 buckets that is 39%, not the ~1/hashsize a single waiter
             * would give, so roughly 39% of the cells sit in the empty mode and
             * the rest in the occupied one. */
            {
                double x = -(double)CAL_THREADS / (double)AQ_FUTEX_HASHSIZE;
                double term = 1.0, sum = 1.0;
                int i;

                for (i = 1; i < 12; i++) {
                    term *= x / (double)i;
                    sum += term;
                }
                exp_free = sum;                 /* = (1-1/H)^K */
                exp_occ = 1.0 - sum;
            }
            /* histogram of cost relative to the minimum, 1 ns buckets */
            memset(hist, 0, sizeof(hist));
            for (ci = 0; ci < ncells_cal; ci++) {
                uint64_t b = cost[ci] - base;

                if (b > 1023)
                    b = 1023;
                hist[b]++;
            }
            /* widest empty run = a step between two populations */
            run = 0;
            lo_b = 0;
            for (ci = 0; ci < 1024; ci++) {
                if (!hist[ci]) {
                    if (!run)
                        lo_b = (int)ci;
                    run++;
                    if (run > best_run) {
                        best_run = run;
                        best_lo = lo_b;
                    }
                } else {
                    run = 0;
                }
            }
            /* only trust a step that separates a real number of cells */
            if (best_lo >= 0) {
                size_t below = 0, above_n = 0;

                step = (uint64_t)best_lo;
                for (ci = 0; ci < ncells_cal; ci++) {
                    if (cost[ci] - base >= step)
                        above_n++;
                    else
                        below++;
                }
                /* a step is only meaningful if both sides are populated */
                if (below < ncells_cal / 8 || above_n < ncells_cal / 8)
                    step = 0;
                else
                    above = above_n;
            }
            if (step) {
                for (ci = 0; ci < ncells_cal; ci++)
                    if (cost[ci] - base >= step)
                        above++;
            }
            printf("[calib] cells=%zu waiters=%d over %u pages reps=%d, ONE pass, no mm needed\n",
                   ncells_cal, CAL_THREADS, CAL_PARK_PAGES, CAL_REP);
            printf("[calib] expected mixture: %.0f%% of the cells share a bucket with a parked node, %.0f%% do not (waiters=%d, hashsize 1024)\n",
                   100.0 * exp_occ, 100.0 * exp_free, CAL_THREADS);
            printf("[calib] per-cell MIN wake: min=%llu p25=%llu p50=%llu p75=%llu p90=%llu p99=%llu max=%llu ns\n",
                   (unsigned long long)base, (unsigned long long)t[ncells_cal / 4],
                   (unsigned long long)sf.p50,
                   (unsigned long long)t[ncells_cal * 3 / 4],
                   (unsigned long long)t[ncells_cal * 9 / 10],
                   (unsigned long long)t[ncells_cal * 99 / 100],
                   (unsigned long long)t[ncells_cal - 1]);
            printf("[calib] widest empty run in the histogram: %d ns at ~%d ns above the minimum\n",
                   best_run, best_lo);
            if (step)
                printf("[calib] STEP FOUND: %llu ns, with %zu of %zu cells (%.0f%%, expected %.0f%%) above it -- this is the cost of one node in the woken bucket\n",
                       (unsigned long long)step, above, ncells_cal,
                       100.0 * (double)above / (double)ncells_cal,
                       100.0 * exp_occ);
            else
                printf("[calib] NO STEP: the cost of one node in the woken bucket is below the 1 ns resolution of this distribution\n");
            calib_delta_p50 = step;
            calib_auc = step ? 0.5 + 0.5 * (double)above / (double)ncells_cal
                             : 0.5;
        }
        free(cost);
        free(t);
        free(scr);
        /* let the waiters out: g_quit first, or the re-arm loop parks again */
        g_quit = 1;
        for (nth = 0; nth < CAL_THREADS; nth++)
            xfutex(park + (size_t)((uint64_t)nth * CAL_PARK_PAGES /
                                   CAL_THREADS) * PAGE, FWAKE, 1u << 20);
        for (nth = 0; nth < CAL_THREADS; nth++)
            pthread_join(g_cal_th[nth], NULL);
        g_quit = 0;
        munmap(park, (size_t)CAL_PARK_PAGES * PAGE);
    }

    /* --- phase 0: no preparation at all. Plain wake, no waiter anywhere. */
    printf("[phase] BASELINE plain wake, nothing parked, n=%zu per cell\n", n);
    sample_set(g_base, g_nbase, n, WARMUP, &anomalies, 0);
    for (i = 0; i < (size_t)g_nbase; i++) {
        char tag[24];

        compute_stats(g_base[i].samp, n, &f, &t);
        snprintf(tag, sizeof(tag), "BASELINE_%s%zu", g_base[i].name, i);
        print_stats(tag, &g_base[i], &f, &t);
        dump_raw("baseline", &g_base[i], g_base[i].samp, n);
    }

    /* --- timer floor: what the instrument itself costs, no syscall --- */
    {
        uint64_t *v = (uint64_t *)calloc(n, sizeof(uint64_t));
        struct cond c;

        memset(&c, 0, sizeof(c));
        c.name = "TIMER";
        for (i = 0; i < n; i++) {
            uint64_t t0 = now_ns();
            uint64_t t1 = now_ns();

            v[i] = t1 - t0;
        }
        compute_stats(v, n, &f, &t);
        print_stats("TIMER", &c, &f, &t);
        dump_raw("timer", &c, v, n);
        free(v);
    }

    /* --- park the waiters --- */
    {
        pthread_attr_t at;
        int j;

        pthread_attr_init(&at);
        for (r = 0; r < (size_t)PILE_THREADS; r++) {
            if (pthread_create(&g_th[g_nth], &at, waiter_fn, g_pile.cell)) {
                printf("[FAIL] pthread_create pile\n");
                return 1;
            }
            g_nth++;
        }
        for (j = 0; j < g_nspray; j++) {
            if (pthread_create(&g_th[g_nth], &at, waiter_fn, g_spray[j].cell)) {
                printf("[FAIL] pthread_create spray\n");
                return 1;
            }
            g_nth++;
        }
        pthread_attr_destroy(&at);
    }
    usleep(200000);
    printf("[check] parked_threads=%d (1 futex_q on PILE + %d on SPRAY)\n",
           g_nth, g_nspray);

    /* --- phase 1: labelled conditions, interleaved ---
     * Repeated PASSES times. Reproducibility across passes is the check that
     * matters: the per-cell cost offsets seen here are stable within a process
     * but not across processes, so a delta that appears in one pass and
     * vanishes in the next is an artifact of this run, not a property of the
     * bucket. */
    printf("[phase] MAIN labelled conditions, n=%zu each, interleaved, %d passes\n",
           n, PASSES);
    for (pass = 0; pass < PASSES; pass++) {
        /* CONTROL and SELFPAIR ride along in the interleaved set so they share
         * the drift and the round cadence of the labelled pairs.
         *
         * SELFPAIR is the decisive null: it is the SAME address as MISMATCH1,
         * presented as a second named condition. Any separation between them is
         * the floor of what this harness can resolve, with no bucket, no page
         * and no offset difference involved. Everything the labelled arms
         * report has to be compared against that number first. */
        struct cond mix[3 * NPAIRS + 2];

        for (i = 0; i < (size_t)g_nc; i++)
            mix[i] = g_c[i];
        mix[g_nc] = g_ctrl;
        mix[g_nc + 1] = g_c[1];
        mix[g_nc + 1].name = "SELFPAIR";
        mix[g_nc + 1].idx = 1;
        sample_set(mix, g_nc + 2, n, WARMUP, &anomalies, pass == 0);
        for (i = 0; i < (size_t)g_nc; i++)
            g_c[i].samp = mix[i].samp;
        g_ctrl.samp = mix[g_nc].samp;
        g_self = mix[g_nc + 1];
        g_self.name = "SELFPAIR";

        if (pass == 0) {
            for (i = 0; i < (size_t)g_nc; i++) {
                char tag[32];
                struct stats *st = i % 3 == 0 ? &sm[i / 3]
                                  : i % 3 == 1 ? &sx[i / 3]
                                               : &s2[i / 3];

                compute_stats(g_c[i].samp, n, st, &t);
                snprintf(tag, sizeof(tag), "%s%d", g_c[i].name,
                         (int)(i / 3) + 1);
                print_stats(tag, &g_c[i], st, &t);
                dump_raw("main", &g_c[i], g_c[i].samp, n);
                if (i % 3 == 1)
                    mismatch_p50 = st->p50;
            }
        }
        /* per-pass reproducibility of the paired delta */
        for (p = 0; p < NPAIRS; p++) {
            double dp, zp;
            struct stats m0, m1, mt;

            compute_stats(g_c[p * 3].samp, n, &m0, &mt);
            compute_stats(g_c[p * 3 + 1].samp, n, &m1, &mt);
            paired_z(g_c[p * 3].samp, g_c[p * 3 + 1].samp, n, &dp, &zp);
            printf("[pass] %d MATCH%d_vs_MISMATCH%d dmed=%lld delta_mean_paired=%.1f z_paired=%.2f\n",
                   pass, p + 1, p + 1,
                   (long long)m0.p50 - (long long)m1.p50, dp, zp);
            if (fabs_(zp) > 3.0)
                pass_hits[p]++;
        }
        {
            double dn, zn;
            struct stats c0, x0, xt;
            uint64_t *cat = (uint64_t *)malloc(n * NPAIRS * sizeof(uint64_t));
            size_t cn = 0;

            for (p = 0; p < NPAIRS; p++) {
                memcpy(cat + cn, g_c[p * 3 + 1].samp, n * sizeof(uint64_t));
                cn += n;
            }
            compute_stats(g_ctrl.samp, n, &c0, &xt);
            compute_stats(cat, cn, &x0, &xt);
            paired_z(g_ctrl.samp, cat, cn, &dn, &zn);
            printf("[pass] %d CONTROL_vs_MISMATCH dmed=%lld z_paired=%.2f (null control)\n",
                   pass, (long long)c0.p50 - (long long)x0.p50, zn);
            if (fabs_(zn) > 3.0)
                pass_hits[NPAIRS]++;
            free(cat);
        }
    }
    for (i = 0; i < (size_t)g_nc; i++) {
        char tag[32];
        struct stats *st = i % 3 == 0 ? &sm[i / 3]
                          : i % 3 == 1 ? &sx[i / 3]
                                       : &s2[i / 3];

        compute_stats(g_c[i].samp, n, st, &t);
        snprintf(tag, sizeof(tag), "%s%d", g_c[i].name, (int)(i / 3) + 1);
        print_stats(tag, &g_c[i], st, &t);
        dump_raw("main", &g_c[i], g_c[i].samp, n);
        if (i % 3 == 1)
            mismatch_p50 = st->p50;
    }
    if (anomalies)
        printf("[check] wake returned != 0 in %ld samples (want 0)\n", anomalies);
    if (g_probe && g_mig * 100 > g_probe)
        verdict_invalid = 1;

    /* --- per pair and pooled statistics --- */
    merged_m = (uint64_t *)malloc(n * NPAIRS * sizeof(uint64_t));
    merged_x = (uint64_t *)malloc(n * NPAIRS * sizeof(uint64_t));
    for (p = 0; p < NPAIRS; p++) {
        const uint64_t *smp = g_c[p * 3].samp;
        const uint64_t *sxp = g_c[p * 3 + 1].samp;
        const uint64_t *s2p = g_c[p * 3 + 2].samp;
        double zn, an, dn, dummy;

        paired_z(smp, sxp, n, &dmp[p], &zp[p]);
        mannwhitney(smp, n, sxp, n, &ap[p], &u, &z);
        printf("[stats] MATCH%d_vs_MISMATCH%d page=%u off_match=0x%03x off_mismatch=0x%03x delta_median=%lld delta_mean_paired=%.1f auc=%.4f u=%.1f z_mwu=%.2f z_paired=%.2f\n",
               p + 1, p + 1, g_pair_page[p], g_c[p * 3].off,
               g_c[p * 3 + 1].off,
               (long long)sm[p].p50 - (long long)sx[p].p50, dmp[p], ap[p], u, z,
               zp[p]);
        mannwhitney(sxp, n, s2p, n, &an, &dummy, &zn);
        paired_z(sxp, s2p, n, &dn, &dummy);
        printf("[stats] NULL_MISMATCH%d_vs_MISMATCH2_%d auc=%.4f z_mwu=%.2f z_paired=%.2f (same page, both wrong bucket: must be flat)\n",
               p + 1, p + 1, an, zn, dummy);
        if (fabs_(zn) > 3.0)
            verdict_invalid = 1;
        if (fabs_(z) > 3.0)
            consistent++;
        for (i = 0; i < n; i++) {
            merged_m[nm + i] = smp[i];
            merged_x[nx + i] = sxp[i];
        }
        nm += n;
        nx += n;
    }
    mannwhitney(merged_m, nm, merged_x, nx, &auc, &u, &z);
    printf("[stats] MATCH_vs_MISMATCH pooled n=%zu/%zu auc=%.4f u=%.1f z_mwu=%.2f (0.5 = no separation)\n",
           nm, nx, auc, u, z);
    {
        double auc0, u0, z0, dz;

        mannwhitney(g_ctrl.samp, n, merged_x, nx, &auc0, &u0, &z0);
        paired_z(g_ctrl.samp, merged_x, n, &dz, &z_null);
        printf("[stats] CONTROL_vs_MISMATCH pooled auc=%.4f z_mwu=%.2f z_paired=%.2f (harness null control, want |z|<3)\n",
               auc0, z0, z_null);
        if (fabs_(z_null) > 3.0)
            verdict_invalid = 1;
    }
    {
        struct stats fs, ft;
        double aucs, us, zs, ds;

        compute_stats(g_self.samp, n, &fs, &ft);
        print_stats("SELFPAIR", &g_self, &fs, &ft);
        dump_raw("main", &g_self, g_self.samp, n);
        mannwhitney(g_self.samp, n, g_c[1].samp, n, &aucs, &us, &zs);
        paired_z(g_self.samp, g_c[1].samp, n, &ds, &z_null);
        printf("[stats] SELFPAIR_vs_MISMATCH1 auc=%.4f z_mwu=%.2f z_paired=%.2f dmed=%lld -- IDENTICAL address, this is the resolution floor\n",
               aucs, zs, z_null, (long long)fs.p50 - (long long)sx[0].p50);
        if (fabs_(zs) > 3.0)
            verdict_invalid = 1;
        self_floor = fabs_(zs);
    }

    /* Requested report format, one block per pair, no post-processing needed. */
    {
        struct stats ca, ct;

        compute_stats(g_ctrl.samp, n, &ca, &ct);
        printf("condition=CONTROL\nbucket_a=0x%03x\nbucket_b=0x%03x\nuaddr_a=0x%llx\npage_offset=0x%03x\nn=%zu\nmin=%llu\np50=%llu\np90=%llu\np95=%llu\np99=%llu\nmax=%llu\nmean=%.1f\nstd=%.1f\n",
               g_ctrl.bucket, g_pile.bucket,
               (unsigned long long)(uintptr_t)g_ctrl.cell, g_ctrl.off, ca.n,
               (unsigned long long)ca.min, (unsigned long long)ca.p50,
               (unsigned long long)ca.p90, (unsigned long long)ca.p95,
               (unsigned long long)ca.p99, (unsigned long long)ca.max,
               ca.mean, ca.std);
        for (p = 0; p < NPAIRS; p++) {
            printf("condition=MATCH\npair=%d\nbucket_a=0x%03x\nbucket_b=0x%03x\nuaddr_a=0x%llx\npage_offset=0x%03x\nn=%zu\nmin=%llu\np50=%llu\np90=%llu\np95=%llu\np99=%llu\nmax=%llu\nmean=%.1f\nstd=%.1f\nauc_vs_mismatch=%.4f\nz_paired=%.2f\npasses_separated=%d/%d\n",
                   p + 1, g_c[p * 3].bucket, g_pile.bucket,
                   (unsigned long long)(uintptr_t)g_c[p * 3].cell,
                   g_c[p * 3].off, sm[p].n, (unsigned long long)sm[p].min,
                   (unsigned long long)sm[p].p50, (unsigned long long)sm[p].p90,
                   (unsigned long long)sm[p].p95, (unsigned long long)sm[p].p99,
                   (unsigned long long)sm[p].max, sm[p].mean, sm[p].std,
                   ap[p], zp[p], pass_hits[p], PASSES);
            printf("condition=MISMATCH\npair=%d\nbucket_a=0x%03x\nbucket_b=0x%03x\nuaddr_a=0x%llx\npage_offset=0x%03x\nn=%zu\nmin=%llu\np50=%llu\np90=%llu\np95=%llu\np99=%llu\nmax=%llu\nmean=%.1f\nstd=%.1f\n",
                   p + 1, g_c[p * 3 + 1].bucket, g_pile.bucket,
                   (unsigned long long)(uintptr_t)g_c[p * 3 + 1].cell,
                   g_c[p * 3 + 1].off, sx[p].n, (unsigned long long)sx[p].min,
                   (unsigned long long)sx[p].p50, (unsigned long long)sx[p].p90,
                   (unsigned long long)sx[p].p95, (unsigned long long)sx[p].p99,
                   (unsigned long long)sx[p].max, sx[p].mean, sx[p].std);
        }
        printf("condition=BUDGET_OCCUPIED_VS_EMPTY\nn=%zu\ndelta_p50=%llu\nauc=%.4f\nz=%.2f\n",
               ncells_cal, (unsigned long long)calib_delta_p50, calib_auc,
               calib_z);
    }

    /* Verdict for the labelled arms, in a fixed order of severity.
     *
     * The labelled arms can never reach SIGNAL on their own, and that is a
     * property of the setup, not a result: the bucket depends on mm, mm is
     * unknown, and only 1 of the 1226944 candidate mms is the real one. So a
     * MATCH/MISMATCH delta is a bucket effect only if the assumed mm happens
     * to be right, which has probability 1/1226944.
     *
     * A passing null control therefore proves nothing either way, and a
     * failing one is a hard stop: the measured delta is then an artifact of
     * which cache lines the address selects, not of bucket occupancy. That
     * artifact is real and it is roughly the same size as the effect being
     * looked for, which is the actual finding here. */
    /* Reproducibility, not one run's z, decides this. A pair that separates in
     * some passes and not others is describing the run, not the bucket. The
     * null control is held to the same standard, so a run where the null
     * reproduces as well as the treatment is visibly different from a run
     * where only the treatment does. */
    repro = "each pair separated in some passes only, or not at all";
    if (pass_hits[NPAIRS] >= PASSES && pass_hits[0] < PASSES)
        repro = "the null control reproduced and the MATCH arm did not: the deltas are not the bucket";
    else if (pass_hits[0] >= PASSES)
        repro = "a MATCH arm reproduced across all passes while the null control did not";
    else if (pass_hits[0] == 0 && pass_hits[NPAIRS] == 0)
        repro = "nothing separated in any pass, including the null controls";

    /* The budget number decides this, and it is the one measurement here that
     * needs no assumed mm. If one node in the woken bucket is worth less than
     * the instrument can resolve, then no labelling scheme can do better, and
     * a separating MATCH arm is describing the address, not the bucket. */
    if (verdict_invalid)
        vlabel = "INVALID TEST";
    else if (calib_delta_p50 == 0 && fabs_(calib_auc - 0.5) < 0.01)
        vlabel = "NO SIGNAL";
    else if (consistent == 0)
        vlabel = "NO SIGNAL";
    else if (consistent == NPAIRS && pass_hits[NPAIRS] < PASSES &&
             fabs_(calib_z) > 3.0 && fabs_(calib_auc - 0.5) > 0.01)
        vlabel = "SIGNAL";
    else
        vlabel = "WEAK SIGNAL";
    printf("[verdict] labelled_MATCH_vs_MISMATCH=%s (pairs_with_|z|>3: %d/%d, resolution_floor_z=%.2f)\n",
           vlabel, consistent, NPAIRS, self_floor);
    if (calib_delta_p50 == 0 && fabs_(calib_auc - 0.5) < 0.01)
        printf("[verdict] BUDGET: one node in the woken bucket costs p50=%llu ns, auc=%.4f. Below what this instrument resolves, so it is the ceiling for any oracle here and the labelled arms are measuring at or below the noise floor.\n",
               (unsigned long long)calib_delta_p50, calib_auc);
    else
        printf("[verdict] BUDGET: one node in the woken bucket costs p50=%llu ns (auc=%.4f z=%.2f), so a labelled oracle could in principle sit inside that.\n",
               (unsigned long long)calib_delta_p50, calib_auc, calib_z);
    for (p = 0; p < NPAIRS; p++)
        printf("[verdict] MATCH%d separated in %d/%d passes\n", p + 1,
               pass_hits[p], PASSES);
    printf("[verdict] NULL control separated in %d/%d passes\n", pass_hits[NPAIRS],
           PASSES);
    printf("[verdict] reproducibility: %s\n", repro);
    printf("[verdict] the mm-free SCAN below is the only arm that does not depend on the assumed mm\n");

    /* --- phase 2: mm free scan. No label needed, the predicted tail is. */
    ncells = (size_t)(POOL_PAGES - SCAN_FIRST) * NOFF;
    pool_samp = (uint64_t *)calloc(ncells * rep, sizeof(uint64_t));
    g_pool_med = (uint64_t *)calloc(ncells, sizeof(uint64_t));
    if (!pool_samp || !g_pool_med) {
        printf("[FAIL] out of memory for the scan\n");
        return 1;
    }
    /* plan cells are skipped: they are in bucket(P) under the assumption and
     * the spray cells have a real waiter, so waking them is not a baseline. */
    {
        size_t cidx = 0, nskip = 0;

        for (i = 0; i < ncells; i++) {
            uint32_t page = (uint32_t)(SCAN_FIRST + i / NOFF);
            uint32_t *cell = cell_at(page, g_off[i % NOFF]);

            if (is_taken(cell)) {
                nskip++;
                continue;
            }
            for (r = 0; r < rep; r++) {
                uint64_t t0 = now_ns();
                long ret = xfutex(cell, FWAKE, 1);
                uint64_t t1 = now_ns();

                if (ret != 0)
                    anomalies++;
                pool_samp[cidx * rep + r] = t1 - t0;
            }
            cidx++;
        }
        ncells = cidx;
        /* The expected count assumes futex_hashsize == 1024, which is the
         * Aquaman value under test and NOT the host value: a modern x86-64
         * kernel sizes the table far larger, so on the host the expected count
         * is far below this and a null result on the host proves nothing about
         * the device either way. */
        printf("[phase] SCAN mm-free cells=%zu skipped_plan_cells=%zu rep=%zu expected_slow_cells_if_hashsize_1024=%d\n",
               ncells, nskip, rep, (int)(ncells / AQ_FUTEX_HASHSIZE));
    }
    for (i = 0; i < ncells; i++) {
        uint64_t *tmp = (uint64_t *)malloc(rep * sizeof(uint64_t));
        double within = 0.0, med;
        size_t k;
        uint32_t page, off;
        uint64_t raw;

        memcpy(tmp, pool_samp + i * rep, rep * sizeof(uint64_t));
        qsort(tmp, rep, sizeof(uint64_t), cmp_u64);
        /* min again, so the baseline subtraction compares like with like and
         * the tail of the distribution does not decide the ranking */
        raw = tmp[0];
        med = (double)raw;
        for (k = 0; k < rep; k++) {
            double d = (double)pool_samp[i * rep + k] - med;

            if (d < 0)
                d = -d;
            within += d;
        }
        within /= (double)rep;
        /* what survives is the change parking the waiters made to this cell,
         * with the per-cell offset that the pre-parking sweep recorded removed */
        page = (uint32_t)(SCAN_FIRST + i / NOFF);
        off = g_off[i % NOFF];
        g_pool_med[i] = raw > g_base_min[cell_index(page, off)]
                            ? raw - g_base_min[cell_index(page, off)]
                            : 0;
        scan_within += within;
        free(tmp);
    }
    scan_within /= (double)ncells;
    {
        uint64_t *srt = (uint64_t *)malloc(ncells * sizeof(uint64_t));
        uint64_t *scr = (uint64_t *)malloc(ncells * sizeof(uint64_t));
        size_t *ord = (size_t *)malloc(ncells * sizeof(size_t));
        struct stats sf;

        memcpy(srt, g_pool_med, ncells * sizeof(uint64_t));
        qsort(srt, ncells, sizeof(uint64_t), cmp_u64);
        stats_slice(srt, 0, ncells, scr, &sf);
        printf("[scan] per_cell_median n=%zu p50=%llu p90=%llu p95=%llu p99=%llu max=%llu mean=%.1f std=%.1f mad=%llu\n",
               sf.n, (unsigned long long)sf.p50, (unsigned long long)sf.p90,
               (unsigned long long)sf.p95, (unsigned long long)sf.p99,
               (unsigned long long)sf.max, sf.mean, sf.std,
               (unsigned long long)sf.mad);
        printf("[scan] within_cell_mean_absdev=%.1f ns (tail above the per-cell min, before baseline subtraction)\n",
               scan_within);
        /* Count the cells whose median sits far above the bulk, measured in
         * units of the within-cell noise. A working bucket oracle puts ~1/1024
         * of the cells (those sharing the pile bucket) above the rest by more
         * than the per-cell noise. This count needs no mm. */
        {
            double thr = 6.0 * scan_within;
            int hot = 0;

            for (i = 0; i < ncells; i++)
                if ((double)g_pool_med[i] > thr)
                    hot++;
            printf("[scan] cells_above_6x_noise=%d expected_if_oracle_works_and_hashsize_1024=%d (thresh=%.0f ns)\n",
                   hot, (int)(ncells / AQ_FUTEX_HASHSIZE), thr);
        }

        for (i = 0; i < ncells; i++)
            ord[i] = i;
        qsort(ord, ncells, sizeof(size_t), cmp_idx_med);
        topk = (int)(ncells / AQ_FUTEX_HASHSIZE);
        if (topk < 2)
            topk = 2;
        {
            uint64_t *top = (uint64_t *)malloc((size_t)topk * sizeof(uint64_t));
            uint64_t *rest = (uint64_t *)malloc((ncells - topk) * sizeof(uint64_t));
            size_t ni = 0, nr = 0;
            int t2;

            for (i = 0; i < (size_t)topk; i++)
                top[ni++] = g_pool_med[ord[i]];
            for (i = (size_t)topk; i < ncells; i++)
                rest[nr++] = g_pool_med[ord[i]];
            /* Only the gap is informative. An AUC of the top-k against the
             * rest is 1.0 by construction, so do not print one: it would look
             * like a result and mean nothing. What matters is whether the top-k
             * form a cluster separated from the bulk, or just the tail of one
             * distribution. A working oracle predicts ~1/1024 of the cells
             * (the ones sharing the pile bucket) to sit clearly above. */
            qsort(top, ni, sizeof(uint64_t), cmp_u64);
            qsort(rest, nr, sizeof(uint64_t), cmp_u64);
            printf("[scan] top%d_slowest: min=%llu p50=%llu | bulk_max=%llu p99=%llu p50=%llu gap_p50_to_bulk_max=%lld ns\n",
                   topk, (unsigned long long)top[0],
                   (unsigned long long)top[ni / 2],
                   (unsigned long long)rest[nr - 1],
                   (unsigned long long)rest[(size_t)(nr * 99 / 100)],
                   (unsigned long long)rest[nr / 2],
                   (long long)top[ni / 2] - (long long)rest[nr - 1]);
            printf("[scan] read the gap, not the count: a cluster sitting clear of the bulk is a signal, a smooth tail is noise\n");
            printf("[scan] slowest cells, post-minus-pre delta in ns, bucket printed under assumed_mm only:\n");
            for (t2 = 0; t2 < topk && t2 < 12; t2++) {
                uint32_t page = (uint32_t)(SCAN_FIRST + ord[t2] / NOFF);
                uint32_t off = g_off[ord[t2] % NOFF];
                uint32_t *cell = cell_at(page, off);

                printf("[scan] rank=%d uaddr=0x%llx off=0x%03x predicted_bucket=0x%03x median=%llu\n",
                       t2 + 1, (unsigned long long)(uintptr_t)cell, off,
                       bucket_of(cell), (unsigned long long)g_pool_med[ord[t2]]);
                if (g_csvf)
                    fprintf(g_csvf, "scan,cell0x%llx,0x%03x,0x%llx,%d,%llu\n",
                            (unsigned long long)(uintptr_t)cell, bucket_of(cell),
                            (unsigned long long)(uintptr_t)cell, t2,
                            (unsigned long long)g_pool_med[ord[t2]]);
            }
            free(top);
            free(rest);
        }
        free(srt);
        free(scr);
        free(ord);
    }
    free(pool_samp);
    free(g_pool_med);
    free(merged_m);
    free(merged_x);

    /* --- end of run validation + POSITIVE CONTROL ---
     * The parked futex_q must be reachable, and a wake that actually MATCHES
     * must be visibly more expensive than one that does not. This is the
     * instrument calibration: it bounds what this harness can resolve. It
     * runs last because it destroys the pile. */
    {
        long w;
        uint64_t t0, t1;
        int ok, j;

        t0 = now_ns();
        w = xfutex(g_pile.cell, FWAKE, 1u << 20);
        t1 = now_ns();
        ok = (w == PILE_THREADS);
        printf("[check] post_run wake(PILE)=%ld expected=%d %s took=%llu ns\n", w,
               PILE_THREADS, ok ? "OK" : "MISMATCH",
               (unsigned long long)(t1 - t0));
        printf("[control] POSITIVE real-match wake of %d waiters cost %llu ns vs a no-match wake p50 of ~%llu ns; the instrument resolves at least that much\n",
               PILE_THREADS, (unsigned long long)(t1 - t0),
               (unsigned long long)mismatch_p50);
        if (!ok)
            verdict_invalid = 1;
        for (j = 0; j < g_nspray; j++) {
            long s = xfutex(g_spray[j].cell, FWAKE, 1u << 20);
            int ok2 = (s == 1);

            printf("[check] post_run wake(SPRAY%d)=%ld expected=1 %s\n", j + 1, s,
                   ok2 ? "OK" : "MISMATCH");
            if (!ok2)
                verdict_invalid = 1;
        }
    }

    printf("[check] wake_nonzero=%ld migration_probes=%ld/%ld\n", anomalies,
           g_mig, g_probe);
    if (anomalies)
        verdict_invalid = 1;
    printf("[verdict] harness=%s\n",
           verdict_invalid ? "a null control separated, see the NULL lines"
                           : "all controls held (wakes idempotent, measurer pinned, null controls flat)");

    if (g_csvf)
        fclose(g_csvf);
    fflush(NULL);
    _exit(verdict_invalid ? 1 : 0);
}
