/*
 * test_mm_enum.c — host-only validation for ghostlock_mm_enum.h.
 *
 * Build (host, no NDK, no device):
 *   gcc -O2 -Wall -Wextra -o /tmp/test_mm_enum tools/test_mm_enum.c
 *   /tmp/test_mm_enum
 *
 * Checks (task §16 + multi-order §11):
 *   a) slab_base AQ_MM_SLAB_SIZE-aligned
 *   b) AQ_MM_OBJS slots per slab, stride 0x340
 *   c) reserved-region exclusion (ramoops/secmon/fb)
 *   d) crossing-slab exclusion
 *   e) phys -> PAGE_OFFSET+phys
 *   f) final candidate count computed from regions (not hard-coded)
 *   g) no candidate in legacy 0xc0000000..0xf0000000 range
 *   h) generic order table 0..3 (stride 0x340): alignment, slab size,
 *      slot count, slot-in-slab, reserve intersection, phys->virt.
 *      Self-contained: does NOT read AQ_MM_ORDER/OBJS/SLAB_SIZE, so it
 *      validates every candidate order even if the header changes.
 * Plus: secos disabled NOT excluded, offset/slot guards, hash is 4-word.
 */
#include <stdio.h>
#include <stdint.h>

#include "ghostlock_mm_enum.h"

static int fails = 0;
#define CHECK(cond, msg) do { \
    if (!(cond)) { printf("[FAIL] %s\n", msg); fails++; } \
    else { printf("[ok] %s\n", msg); } \
} while (0)

/* Generic order geometry from calculate_order derivation (slub.c:3227):
 * stride 0x340 fixed; max_order=3/min_objects=16 selects order 2.
 * Rows for 0/1/3 pin the candidates the code would pick under
 * max_order=0/1 or nr_cpu_ids=8, so a header change stays testable. */
struct mm_order_case {
    int order;
    unsigned objs;
    uint64_t slab;
    unsigned rem;
};

static const struct mm_order_case order_cases[] = {
    { 0, 4,  0x1000ULL, 768 },
    { 1, 9,  0x2000ULL, 704 },
    { 2, 19, 0x4000ULL, 576 },
    { 3, 39, 0x8000ULL, 320 },
};
#define NORDERS (sizeof(order_cases) / sizeof(order_cases[0]))

/* Fixed reserves with known bases (mirrors aq_reserves, parametric slab). */
static const struct { uint64_t base, size; } fixed_rs[] = {
    { 0x07400000ULL, 0x200000ULL }, /* ramoops */
    { 0x05000000ULL, 0x400000ULL }, /* secmon */
    { 0x3f800000ULL, 0x800000ULL }, /* framebuffer */
};
#define NFIXED (sizeof(fixed_rs) / sizeof(fixed_rs[0]))

static int slab_hits_fixed(uint64_t slab_base, uint64_t slab_size)
{
    size_t i;

    for (i = 0; i < NFIXED; i++) {
        if (aq_ranges_overlap(slab_base, slab_size,
                              fixed_rs[i].base, fixed_rs[i].size))
            return 1;
    }
    return 0;
}

int main(void)
{
    uint64_t slab, phys, virt, lo, hi;
    uint64_t total_slabs = 0, eligible = 0, candidates = 0;
    uint64_t float_reserved = 0;
    size_t i, o;

    printf("[info] stride=0x%llx objs=%u slab=0x%llx offset=0x%llx order=%d\n",
           (unsigned long long)AQ_MM_STRIDE, (unsigned)AQ_MM_OBJS,
           (unsigned long long)AQ_MM_SLAB_SIZE,
           (unsigned long long)AQ_MM_OFFSET, AQ_MM_ORDER);
    printf("[info] phys=[0x%llx,0x%llx) virt_base=0x%llx\n",
           (unsigned long long)AQ_PHYS_START,
           (unsigned long long)AQ_PHYS_END,
           (unsigned long long)AQ_PAGE_OFFSET);

    /* Model constants: order 2 derivation, not Hazel reuse. */
    CHECK(AQ_MM_STRIDE == 0x340ULL, "stride is 0x340, not 0x1c0/0x338");
    CHECK(AQ_MM_OBJS == 19, "19 objs per slab, not 9/18");
    CHECK(AQ_MM_SLAB_SIZE == 0x4000ULL, "slab is 0x4000 order-2");
    CHECK(AQ_MM_ORDER == 2, "order is 2, not 1");

    /* a) alignment: every enumerated slab_base is 0x4000-aligned. */
    CHECK(AQ_PHYS_START % AQ_MM_SLAB_SIZE == 0, "phys_start 0x4000-aligned");
    CHECK(AQ_PHYS_END % AQ_MM_SLAB_SIZE == 0, "phys_end 0x4000-aligned");
    for (slab = AQ_PHYS_START; slab < AQ_PHYS_END; slab += AQ_MM_SLAB_SIZE) {
        if (slab % AQ_MM_SLAB_SIZE != 0) {
            CHECK(0, "all slab_bases 0x4000-aligned");
            break;
        }
        if (slab + AQ_MM_SLAB_SIZE < slab) {
            CHECK(0, "no overflow in slab iteration");
            break;
        }
    }
    CHECK(slab == AQ_PHYS_END, "slab walk covers full window contiguously");

    /* b) 19 slots per slab on the 0x340 grid. */
    {
        uint64_t s = 0x01000000ULL; /* arbitrary aligned slab */
        unsigned n;
        for (n = 0; n < AQ_MM_OBJS; n++) {
            uint64_t want = s + AQ_MM_OFFSET + (uint64_t)n * AQ_MM_STRIDE;
            uint64_t got = 0;
            char msg[128];
            snprintf(msg, sizeof(msg), "slot %u at slab+offset+n*0x340", n);
            CHECK(aq_slot_valid(s, AQ_MM_OFFSET, n, &got) && got == want, msg);
        }
        CHECK(!aq_slot_valid(s, AQ_MM_OFFSET, 19, NULL), "n=19 rejected");
        /* Last slot must fit: 18*0x340=0x3a80, +0x340=0x3dc0 <= 0x4000. */
        CHECK(18 * AQ_MM_STRIDE + AQ_MM_STRIDE <= AQ_MM_SLAB_SIZE,
              "19x0x340 fits in 0x4000 with leftover");
        CHECK(AQ_MM_SLAB_SIZE - 19 * AQ_MM_STRIDE == 576,
              "order-2 leftover is 576");
    }

    /* c) fixed reserves are excluded. */
    CHECK(aq_slab_excluded(0x07400000ULL), "ramoops slab excluded");
    CHECK(aq_slab_excluded(0x07500000ULL), "ramoops interior excluded");
    CHECK(aq_slab_excluded(0x05000000ULL), "secmon slab excluded");
    CHECK(aq_slab_excluded(0x053E0000ULL), "secmon tail excluded");
    CHECK(aq_slab_excluded(0x3f800000ULL), "framebuffer slab excluded");
    CHECK(aq_slab_excluded(0x3fffc000ULL), "framebuffer tail excluded");
    CHECK(!aq_slab_excluded(0x01000000ULL), "low usable slab kept");
    CHECK(!aq_slab_excluded(0x07600000ULL), "slab right after ramoops kept");
    CHECK(!aq_slab_excluded(0x05400000ULL), "slab right after secmon kept");

    /* secos disabled must NOT be excluded (pick point inside secos,
     * outside secmon/ramoops to isolate the secos decision). */
    CHECK(!aq_slab_excluded(0x06000000ULL), "secos-disabled interior kept");

    /* d) crossing slabs: overlap logic rejects straddlers. */
    {
        /* Synthetic unaligned reserve to prove crossing logic. */
        CHECK(aq_ranges_overlap(0x07400000ULL, 0x4000ULL,
                                0x07402000ULL, 0x4000ULL),
              "crossing overlap detected");
        CHECK(!aq_ranges_overlap(0x07600000ULL, 0x4000ULL,
                                 0x07400000ULL, 0x200000ULL),
              "touching-at-end is not overlap");
        CHECK(!aq_ranges_overlap(0x073FC000ULL, 0x4000ULL,
                                 0x07400000ULL, 0x200000ULL),
              "touching-at-start is not overlap");
        /* Real table: slab fully inside ramoops is out; neighbours are in. */
        CHECK(aq_slab_excluded(0x07400000ULL), "inside ramoops out");
        CHECK(!aq_slab_excluded(0x073FC000ULL), "slab ending at ramoops kept");
    }

    /* Defensive guards. */
    CHECK(!aq_slot_valid(0x01000000ULL, 0x4000ULL, 0, NULL),
          "object_offset >= 0x4000 rejected");
    CHECK(!aq_slot_valid(0x01000000ULL, 0x3E00ULL, 1, NULL),
          "slot exceeding slab rejected");
    {
        uint64_t out = 0;
        CHECK(aq_add_overflow_u64(0xffffffffffffffffULL, 1, &out),
              "overflow in base+size detected");
    }
    {
        /* slab_base + 0x4000 <= phys_end enforced by walk bound. */
        uint64_t last = AQ_PHYS_END - AQ_MM_SLAB_SIZE;
        uint64_t end = 0;
        CHECK(!aq_add_overflow_u64(last, AQ_MM_SLAB_SIZE, &end) &&
              end <= AQ_PHYS_END, "last slab fits before phys_end");
    }

    /* e) phys -> PAGE_OFFSET+phys, only after physical validation. */
    phys = 0x01000000ULL;
    virt = aq_phys_to_virt(phys);
    CHECK(virt == AQ_PAGE_OFFSET + phys, "virt = PAGE_OFFSET+phys");
    CHECK(aq_virt_in_linear(virt), "converted mm in linear range");
    lo = aq_phys_to_virt(AQ_PHYS_START);
    hi = aq_phys_to_virt(AQ_PHYS_END - 1);
    CHECK(aq_virt_in_linear(lo) && aq_virt_in_linear(hi),
          "window edges map into linear range");
    CHECK(!aq_virt_in_linear(AQ_PAGE_OFFSET - 1), "below linear rejected");
    CHECK(!aq_virt_in_linear(AQ_PAGE_OFFSET + AQ_PHYS_END),
          "at/above phys_end rejected");

    /* Hash is Aquaman 4-word, not Hazel 3-word: mm high word matters. */
    {
        uint32_t h0 = aq_hash_private(0x12345000ULL, 0xffffff8001000000ULL, 0x10);
        uint32_t h1 = aq_hash_private(0x12345000ULL, 0xffffff8001000000ULL, 0x11);
        uint64_t mm_lo_same = 0x01000000ULL;
        uint32_t ha = aq_hash_private(0x1000ULL, mm_lo_same, 0);
        uint32_t hb = aq_hash_private(0x1000ULL, mm_lo_same | 0x100000000ULL, 0);
        CHECK(h0 != h1, "offset feeds hash (initval)");
        CHECK(ha != hb, "mm high word feeds hash (4-word, not Hazel)");
        CHECK(aq_hash_bucket(0x1000ULL, mm_lo_same, 0) < AQ_FUTEX_HASHSIZE,
              "bucket within 1024");
        CHECK(AQ_FUTEX_HASHSIZE == 1024u, "hashsize 1024 for 4 CPUs");
    }

    /* f) counts computed from regions, never hard-coded. */
    total_slabs = (AQ_PHYS_END - AQ_PHYS_START) / AQ_MM_SLAB_SIZE;
    for (slab = AQ_PHYS_START; slab < AQ_PHYS_END; slab += AQ_MM_SLAB_SIZE)
        if (!aq_slab_excluded(slab))
            eligible++;
    candidates = eligible * AQ_MM_OBJS;
    printf("[count] total_slabs=%llu eligible_slabs=%llu candidates=%llu\n",
           (unsigned long long)total_slabs,
           (unsigned long long)eligible,
           (unsigned long long)candidates);
    CHECK(total_slabs == 65472ULL, "total order-2 slabs in 1023MiB window");
    CHECK(eligible + 896ULL == total_slabs,
          "fixed exclusions = 128+256+512 slabs");
    CHECK(candidates == eligible * 19, "candidates = slabs*19");
    /* Floating CMA cannot be address-excluded; report size-adjusted bound. */
    for (i = 0; i < AQ_NRESERVES; i++)
        if (!aq_reserves[i].has_base && !aq_reserves[i].excluded)
            float_reserved += aq_reserves[i].size;
    printf("[count] floating_CMA_reserved=0x%llx (%llu MiB), size-adjusted est=%llu\n",
           (unsigned long long)float_reserved,
           (unsigned long long)(float_reserved >> 20),
           (unsigned long long)(candidates - float_reserved / AQ_MM_SLAB_SIZE * AQ_MM_OBJS));
    CHECK(float_reserved == 0x14c00000ULL, "floating CMA total 332MiB");

    /* g) no candidate in legacy Hazel virtual range. */
    {
        int bad = 0;
        for (slab = AQ_PHYS_START; slab < AQ_PHYS_END; slab += AQ_MM_SLAB_SIZE) {
            unsigned n;
            if (aq_slab_excluded(slab))
                continue;
            for (n = 0; n < AQ_MM_OBJS; n++) {
                uint64_t p = 0, v = 0;
                if (!aq_slot_valid(slab, AQ_MM_OFFSET, n, &p))
                    continue;
                v = aq_phys_to_virt(p);
                if (!aq_virt_in_linear(v))
                    bad++;
                if (v >= 0xc0000000ULL && v < 0xf0000000ULL)
                    bad++;
            }
        }
        CHECK(bad == 0, "no candidate uses 0xc0000000..0xf0000000");
    }

    /* Solver grid check: every tested mm comes from the grid. */
    {
        uint64_t s = 0x02000000ULL, p = 0;
        unsigned n = 3;
        CHECK(aq_slot_valid(s, AQ_MM_OFFSET, n, &p) &&
              p == s + AQ_MM_OFFSET + (uint64_t)n * AQ_MM_STRIDE,
              "solver tests only grid phys");
    }

    /* h) generic order table 0..3: geometry holds for every candidate
     * order, independent of the AQ_* choice above. */
    for (o = 0; o < NORDERS; o++) {
        uint64_t slab_size = order_cases[o].slab;
        unsigned objs = order_cases[o].objs;
        char msg[160];
        uint64_t s = 0x02000000ULL; /* 0x8000-aligned: valid base for all */
        unsigned n;
        uint64_t last_phys, last_end, slab_end;

        snprintf(msg, sizeof(msg), "order %d slab size 0x%llx",
                 order_cases[o].order, (unsigned long long)slab_size);
        CHECK(slab_size == (0x1000ULL << order_cases[o].order), msg);

        /* objs*stride + rem == slab (pins the waste table). */
        snprintf(msg, sizeof(msg), "order %d objs*stride+rem == slab",
                 order_cases[o].order);
        CHECK((uint64_t)objs * AQ_MM_STRIDE + order_cases[o].rem == slab_size,
              msg);

        /* every enumerated base for this order is slab-aligned. */
        snprintf(msg, sizeof(msg), "order %d phys_start slab-aligned",
                 order_cases[o].order);
        CHECK(AQ_PHYS_START % slab_size == 0, msg);
        snprintf(msg, sizeof(msg), "order %d phys_end slab-aligned",
                 order_cases[o].order);
        CHECK(AQ_PHYS_END % slab_size == 0, msg);

        /* all n slots fit, slot objs is rejected. */
        for (n = 0; n < objs; n++) {
            uint64_t p = s + (uint64_t)n * AQ_MM_STRIDE;
            snprintf(msg, sizeof(msg), "order %d slot %u inside slab",
                     order_cases[o].order, n);
            if (!(aq_phys_in_usable(p) && p + AQ_MM_STRIDE <= s + slab_size)) {
                CHECK(0, msg);
                break;
            }
        }
        if (n == objs) {
            snprintf(msg, sizeof(msg), "order %d all %u slots inside slab",
                     order_cases[o].order, objs);
            CHECK(1, msg);
        }
        last_phys = s + (uint64_t)(objs - 1) * AQ_MM_STRIDE;
        snprintf(msg, sizeof(msg), "order %d last slot ends at slab end - rem",
                 order_cases[o].order);
        CHECK(!aq_add_overflow_u64(last_phys, AQ_MM_STRIDE, &last_end) &&
              !aq_add_overflow_u64(s, slab_size, &slab_end) &&
              last_end <= slab_end &&
              slab_end - last_end == order_cases[o].rem, msg);

        /* reserve intersection is order-aware (fixed reserves excluded,
         * secos-disabled interior kept). */
        snprintf(msg, sizeof(msg), "order %d ramoops slab excluded",
                 order_cases[o].order);
        CHECK(slab_hits_fixed(0x07400000ULL, slab_size), msg);
        snprintf(msg, sizeof(msg), "order %d secmon slab excluded",
                 order_cases[o].order);
        CHECK(slab_hits_fixed(0x05000000ULL, slab_size), msg);
        snprintf(msg, sizeof(msg), "order %d fb slab excluded",
                 order_cases[o].order);
        CHECK(slab_hits_fixed(0x3f800000ULL, slab_size), msg);
        snprintf(msg, sizeof(msg), "order %d low usable slab kept",
                 order_cases[o].order);
        CHECK(!slab_hits_fixed(0x01000000ULL, slab_size), msg);
        snprintf(msg, sizeof(msg), "order %d secos-disabled interior kept",
                 order_cases[o].order);
        /* secos-disabled overlaps are intentionally NOT excluded: the only
         * rejection source here is the fixed-reserve set. */
        CHECK(!slab_hits_fixed(0x06000000ULL, slab_size), msg);

        /* phys -> virt stays inside the linear window for edge slots. */
        snprintf(msg, sizeof(msg), "order %d edge slots map into linear range",
                 order_cases[o].order);
        CHECK(aq_virt_in_linear(aq_phys_to_virt(s)) &&
              aq_virt_in_linear(aq_phys_to_virt(last_phys)), msg);
    }

    if (fails) {
        printf("[summary] FAILS=%d\n", fails);
        return 1;
    }
    printf("[summary] all host checks passed\n");
    return 0;
}
