/*
 * aq_hash_dist.c — host-only hash distribution over the physical universe.
 *
 * Usage:
 *   gcc -O2 -Wall -Wextra -o /tmp/aq_hash_dist tools/aq_hash_dist.c
 *   /tmp/aq_hash_dist [target_uaddr_hex] [hashsize]
 *   /tmp/aq_hash_dist --single <phys_mm_hex> <target_uaddr_hex> [hashsize]
 *
 * Single mode prints: phys_slab phys_mm slot virt_mm bucket.
 * Full mode enumerates every candidate via aq_enum_next() (physical walk,
 * conversion only after validation) and hashes each virt_mm against the
 * target address:
 *   word   = target & ~0xfff (page-aligned user address)
 *   offset = target & 0xfff  (initval)
 * then prints total / per-bucket min,max,mean,std (population).
 *
 * This validates distribution only. It does NOT prove a timing
 * side-channel works on the device.
 */
#include <math.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "ghostlock_mm_enum.h"

static void print_single(uint64_t phys_mm, uint64_t target, uint32_t hashsize)
{
    struct aq_candidate c;
    uint64_t virt;
    uint64_t word = target & ~(uint64_t)0xfff;
    uint32_t off = (uint32_t)(target & 0xfffu);
    uint32_t mask = hashsize - 1;
    uint32_t b;

    virt = aq_phys_to_virt(phys_mm);
    b = aq_hash_private(word, virt, off) & mask;
    if (aq_candidate_from_virt(virt, &c))
        printf("phys_slab=0x%llx phys_mm=0x%llx slot=%u virt_mm=0x%llx "
               "word=0x%llx off=0x%x bucket=%u/%u\n",
               (unsigned long long)c.phys_slab,
               (unsigned long long)c.phys_mm, c.slot,
               (unsigned long long)c.virt_mm,
               (unsigned long long)word, off, b, hashsize);
    else
        printf("phys_mm=0x%llx virt_mm=0x%llx word=0x%llx off=0x%x "
               "bucket=%u/%u (OFF-GRID)\n",
               (unsigned long long)phys_mm, (unsigned long long)virt,
               (unsigned long long)word, off, b, hashsize);
}

int main(int argc, char **argv)
{
    uint64_t target = 0x12345000ULL;
    uint32_t hashsize = AQ_FUTEX_HASHSIZE;
    uint64_t word;
    uint32_t off, mask;
    static uint64_t hist[4096];
    uint64_t total = 0, i;
    uint64_t mn = 0, mx = 0;
    double mean = 0, var = 0, std = 0;
    struct aq_enum e;
    struct aq_candidate c;

    if (argc >= 2 && strcmp(argv[1], "--single") == 0) {
        uint64_t phys_mm;
        uint64_t tgt = target;
        if (argc < 4) {
            fprintf(stderr, "usage: %s --single <phys_mm_hex> <target_hex> [hashsize]\n",
                    argv[0]);
            return 2;
        }
        phys_mm = strtoull(argv[2], NULL, 0);
        tgt = strtoull(argv[3], NULL, 0);
        if (argc >= 5)
            hashsize = (uint32_t)strtoul(argv[4], NULL, 0);
        print_single(phys_mm, tgt, hashsize);
        return 0;
    }
    if (argc >= 2)
        target = strtoull(argv[1], NULL, 0);
    if (argc >= 3)
        hashsize = (uint32_t)strtoul(argv[2], NULL, 0);
    if (hashsize == 0 || hashsize > 4096 || (hashsize & (hashsize - 1)) != 0) {
        fprintf(stderr, "hashsize must be a power of two <= 4096\n");
        return 2;
    }

    word = target & ~(uint64_t)0xfff;
    off = (uint32_t)(target & 0xfffu);
    mask = hashsize - 1;
    memset(hist, 0, sizeof(hist));

    aq_enum_init(&e);
    while (aq_enum_next(&e, &c)) {
        uint32_t b = aq_hash_private(word, c.virt_mm, off) & mask;
        hist[b]++;
        total++;
    }

    mn = hist[0];
    mx = hist[0];
    for (i = 0; i < hashsize; i++) {
        if (hist[i] < mn)
            mn = hist[i];
        if (hist[i] > mx)
            mx = hist[i];
        mean += (double)hist[i];
    }
    mean /= (double)hashsize;
    for (i = 0; i < hashsize; i++) {
        double d = (double)hist[i] - mean;
        var += d * d;
    }
    var /= (double)hashsize;
    std = sqrt(var);

    printf("[dist] target=0x%llx word=0x%llx off=0x%x hashsize=%u\n",
           (unsigned long long)target, (unsigned long long)word, off, hashsize);
    printf("[dist] total=%llu eligible_buckets=%u\n",
           (unsigned long long)total, hashsize);
    printf("[dist] per_bucket min=%llu max=%llu mean=%.2f std=%.2f\n",
           (unsigned long long)mn, (unsigned long long)mx, mean, std);
    printf("[dist] expected_mean=%.2f (total/buckets)\n",
           (double)total / (double)hashsize);
    /* Show first 8 + most loaded bucket, enough to eyeball uniformity. */
    {
        uint64_t top = 0;
        size_t j;
        for (j = 0; j < hashsize; j++)
            if (hist[j] > hist[top])
                top = j;
        printf("[dist] buckets[0..7]:");
        for (j = 0; j < 8 && j < hashsize; j++)
            printf(" %llu", (unsigned long long)hist[j]);
        printf("\n[dist] top bucket=%zu count=%llu\n",
               top, (unsigned long long)hist[top]);
    }
    return 0;
}
