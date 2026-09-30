/*
 * test_aq_hash.c — host-only audit of the Aquaman futex hash.
 *
 * Aquaman hash_futex() (.src/linux-amlogic/kernel/futex.c:391-397) is:
 *   jhash2((u32*)&key->both.word,
 *          (sizeof(key->both.word)+sizeof(key->both.ptr))/4,
 *          key->both.offset)
 * on LP64: word u64 + ptr u64 = 16 bytes = 4 words, initval = offset.
 *
 * Layout (private futex, union futex_key):
 *   k[0] = word lo (user address low 32)
 *   k[1] = word hi (user address high 32, 0 for 32-bit uaddr)
 *   k[2] = mm lo   (mm_struct* low 32)
 *   k[3] = mm hi   (mm_struct* high 32, 0xffffff80.. on VA39)
 *   initval = both.offset = uaddr % PAGE_SIZE (+ FUT_OFF_* bits for shared)
 *   final bucket = hash & (futex_hashsize-1), hashsize 1024 -> mask 0x3ff.
 *
 * This test holds an INDEPENDENT reference transcribed from
 * include/linux/jhash.h (rol32/mix/final verbatim, renamed ref_*)
 * and checks it against the solver implementation in
 * ghostlock_mm_enum.h (aq_hash_private / aq_jhash2_u32).
 * It fails on any swap of mm/address/offset/high/low and on any
 * Hazel 3-word confusion. No ks_hash() is copied or used.
 *
 * Build: gcc -O2 -Wall -Wextra -o /tmp/test_aq_hash tools/test_aq_hash.c
 */
#include <stdio.h>
#include <stdint.h>

#include "ghostlock_mm_enum.h"

/* ---- Independent reference, transcribed from kernel jhash.h ---- */
static inline uint32_t ref_rol32(uint32_t v, unsigned n)
{
    return (v << n) | (v >> (32 - n));
}

static uint32_t ref_jhash2(const uint32_t *k, uint32_t length, uint32_t initval)
{
    uint32_t a, b, c;

    a = b = c = 0xdeadbeefu + (length << 2) + initval;
    while (length > 3) {
        a += k[0];
        b += k[1];
        c += k[2];
        a -= c; a ^= ref_rol32(c, 4);  c += b;
        b -= a; b ^= ref_rol32(a, 6);  a += c;
        c -= b; c ^= ref_rol32(b, 8);  b += a;
        a -= c; a ^= ref_rol32(c, 16); c += b;
        b -= a; b ^= ref_rol32(a, 19); a += c;
        c -= b; c ^= ref_rol32(b, 4);  b += a;
        length -= 3;
        k += 3;
    }
    switch (length) {
    case 3: c += k[2];
        /* fall through */
    case 2: b += k[1];
        /* fall through */
    case 1: a += k[0];
        c ^= b; c -= ref_rol32(b, 14);
        a ^= c; a -= ref_rol32(c, 11);
        b ^= a; b -= ref_rol32(a, 25);
        c ^= b; c -= ref_rol32(b, 16);
        a ^= c; a -= ref_rol32(c, 4);
        b ^= a; b -= ref_rol32(a, 14);
        c ^= b; c -= ref_rol32(b, 24);
        /* fall through */
    case 0:
        break;
    }
    return c;
}

static uint32_t ref_hash_private(uint64_t word, uint64_t mm, uint32_t offset)
{
    uint32_t k[4];

    k[0] = (uint32_t)(word & 0xffffffffu);
    k[1] = (uint32_t)((word >> 32) & 0xffffffffu);
    k[2] = (uint32_t)(mm & 0xffffffffu);
    k[3] = (uint32_t)((mm >> 32) & 0xffffffffu);
    return ref_jhash2(k, 4, offset);
}

static int fails = 0;
#define CHECK(cond, msg) do { \
    if (!(cond)) { printf("[FAIL] %s\n", msg); fails++; } \
    else { printf("[ok] %s\n", msg); } \
} while (0)

static uint32_t lcg_next(uint64_t *s)
{
    *s = *s * 6364136223846793005ULL + 1442695040888963407ULL;
    return (uint32_t)(*s >> 33);
}

int main(void)
{
    /* Fixed vectors spanning phys/virt words and offsets. */
    static const struct { uint64_t word, mm; uint32_t off; } vec[] = {
        { 0x00000000ULL, 0xffffff8001000000ULL, 0x000 },
        { 0x00001000ULL, 0xffffff8001000000ULL, 0x000 },
        { 0x12345000ULL, 0xffffff8001000000ULL, 0x010 },
        { 0x12345678ULL, 0xffffff803e000340ULL, 0x678 },
        { 0x0000abcdULL, 0xffffff8000100340ULL, 0xbcd },
        { 0xffffffffULL, 0xffffff80ffffffffULL, 0xfff },
        { 0x100000000ULL, 0x100000000ULL, 0x001 },
        { 0xdeadbeef12345678ULL, 0xffffff80deadbeefULL, 0xdead },
    };
    size_t i;

    printf("[info] key=16B/4words initval=offset mask=0x3ff (Aquaman LP64)\n");

    /* 1. Reference == solver on fixed vectors. */
    for (i = 0; i < sizeof(vec) / sizeof(vec[0]); i++) {
        char msg[128];
        uint32_t r = ref_hash_private(vec[i].word, vec[i].mm, vec[i].off);
        uint32_t a = aq_hash_private(vec[i].word, vec[i].mm, vec[i].off);
        snprintf(msg, sizeof(msg), "vec%zu ref==solver (w=0x%llx mm=0x%llx off=0x%x)",
                 i, (unsigned long long)vec[i].word,
                 (unsigned long long)vec[i].mm, vec[i].off);
        CHECK(r == a, msg);
    }

    /* 2. Randomized cross-check (deterministic LCG, 2000 cases). */
    {
        uint64_t s = 0x123456789abcdefULL;
        int bad = 0;
        for (i = 0; i < 2000; i++) {
            uint64_t w = ((uint64_t)lcg_next(&s) << 32) | lcg_next(&s);
            uint64_t m = ((uint64_t)0xffffff80 << 32) |
                         (lcg_next(&s) & 0x3fffffffu);
            uint32_t o = lcg_next(&s) & 0xfffu;
            if (ref_hash_private(w, m, o) != aq_hash_private(w, m, o))
                bad++;
        }
        CHECK(bad == 0, "2000 pseudo-random vectors ref==solver");
    }

    /* 3. Swap sensitivity: each transposition must change the hash,
     * proving the test would catch a mm/address/offset mixup. */
    {
        uint64_t w = 0x0000000012345000ULL;
        uint64_t m = 0xffffff8001000340ULL;
        uint32_t o = 0x340u;
        uint32_t base = aq_hash_private(w, m, o);
        uint32_t swapped_mm_addr = aq_hash_private(m, w, o);
        uint32_t swapped_off = aq_hash_private(w, m, o ^ 0x1u);
        uint64_t m_swap32 = ((m & 0xffffffffu) << 32) | ((m >> 32) & 0xffffffffu);
        uint64_t w_swap32 = ((w & 0xffffffffu) << 32) | ((w >> 32) & 0xffffffffu);
        uint32_t swapped_mm_hi_lo = aq_hash_private(w, m_swap32, o);
        uint32_t swapped_w_hi_lo = aq_hash_private(w_swap32, m, o);
        CHECK(base != swapped_mm_addr, "mm<->address swap changes hash");
        CHECK(base != swapped_off, "offset bit-flip changes hash");
        CHECK(base != swapped_mm_hi_lo, "mm high<->low swap changes hash");
        CHECK(base != swapped_w_hi_lo, "word high<->low swap changes hash");
        /* Reference agrees on the swapped values too (not just inequality). */
        CHECK(swapped_mm_addr == ref_hash_private(m, w, o),
              "swapped mm/addr ref==solver");
        CHECK(swapped_mm_hi_lo == ref_hash_private(w, m_swap32, o),
              "swapped mm halves ref==solver");
    }

    /* 4. Hazel 3-word confusion must NOT match: length 3 over the same
     * prefix is a different function. */
    {
        uint32_t k4[4] = { 0x12345000u, 0x00000000u, 0x01000340u, 0xffffff80u };
        uint32_t h4 = aq_jhash2_u32(k4, 4, 0x340u);
        uint32_t h3 = aq_jhash2_u32(k4, 3, 0x340u);
        uint32_t r4 = ref_jhash2(k4, 4, 0x340u);
        CHECK(h4 == r4, "4-word jhash ref==solver");
        CHECK(h4 != h3, "4-word != 3-word (Hazel model rejected)");
    }

    /* 5. Bucket mask. */
    {
        int bad = 0;
        uint64_t s = 0xabcdefULL;
        size_t j;
        for (j = 0; j < 500; j++) {
            uint64_t w = lcg_next(&s);
            uint64_t m = AQ_PAGE_OFFSET + (lcg_next(&s) & 0x3fffffffu);
            if (aq_hash_bucket(w, m, lcg_next(&s) & 0xfffu) >= AQ_FUTEX_HASHSIZE)
                bad++;
        }
        CHECK(bad == 0, "bucket always < 1024");
        CHECK(AQ_FUTEX_HASHMASK == 0x3ffu, "mask is 0x3ff");
    }

    if (fails) {
        printf("[summary] FAILS=%d\n", fails);
        return 1;
    }
    printf("[summary] hash audit passed\n");
    return 0;
}
