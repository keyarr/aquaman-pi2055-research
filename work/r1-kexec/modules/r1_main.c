/*
 * PREPARATION ONLY - DO NOT EXECUTE ON DEVICE
 *
 * r1_kexec: load an arm64 Image + DTB (+ optional initrd) from a file and
 * transfer control to it directly, bypassing U-Boot and the BL31 signature
 * gate. No CONFIG_KEXEC in the running kernel, so this is a self-contained
 * LKM: it stages the payload in CMA, builds a private identity map, tears down
 * the CPUs/MMU and branches to the new kernel at the current EL.
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/fs.h>
#include <linux/slab.h>
#include <linux/err.h>
#include <linux/cpu.h>
#include <linux/smp.h>
#include <linux/dma-contiguous.h>
#include <linux/amlogic/aml_cma.h>
#include <linux/vmalloc.h>
#include <linux/io.h>
#include <linux/kallsyms.h>

#include <asm/page.h>
#include <linux/byteorder/generic.h>

MODULE_LICENSE("GPL");
MODULE_AUTHOR("local research");
MODULE_DESCRIPTION("R1 kexec-style direct kernel boot (preparation only)");

static char *image_path;
module_param(image_path, charp, 0400);
MODULE_PARM_DESC(image_path, "path to raw arm64 Image on the device");

static char *dtb_path;
module_param(dtb_path, charp, 0400);
MODULE_PARM_DESC(dtb_path, "path to the patched DTB (with /chosen/bootargs)");

static char *initrd_path;
module_param(initrd_path, charp, 0400);
MODULE_PARM_DESC(initrd_path, "optional path to initramfs.cpio.gz");

static unsigned long cma_phys;
module_param(cma_phys, ulong, 0400);
MODULE_PARM_DESC(cma_phys, "0 = default CMA; else 2MB-aligned start PFN address");

static int fire;
module_param(fire, int, 0600);
MODULE_PARM_DESC(fire, "set to 1 to stage and jump during insmod");

static unsigned long read_crumb;
module_param(read_crumb, ulong, 0400);
MODULE_PARM_DESC(read_crumb, "1 = default crumb, else physical address to read");

static int panic_at;
module_param(panic_at, int, 0400);
MODULE_PARM_DESC(panic_at, "panic at this step number (persists in pstore)");

static int reenter_self;
module_param(reenter_self, int, 0400);
MODULE_PARM_DESC(reenter_self, "jump to the running kernel _text (diagnostic)");

static int skip_offline;
module_param(skip_offline, int, 0400);
MODULE_PARM_DESC(skip_offline, "leave secondary CPUs running before the jump");

/*
 * ramoops owns 0x7400000..0x7600000; offset 0x100000 is unused scratch.
 * A watchdog reset keeps DRAM self-refreshed, so the last step survives.
 */
/* ramoops rewrites only each record header; 4 KiB in survives a reset. */
#define R1_CRUMB_PHYS	0x07501000UL

extern void r1_dcache_clean_poc(void *addr, unsigned long len);

static void r1_step(u32 step)
{
	volatile u32 *p = (volatile u32 *)phys_to_virt(R1_CRUMB_PHYS);

	*p = step;
	dsb(sy);
	r1_dcache_clean_poc((void *)p, sizeof(step));
	if (panic_at == step)
		panic("r1: reached step %u", step);
}

static u32 r1_crumb_read_addr(unsigned long phys)
{
	volatile u32 *p = (volatile u32 *)phys_to_virt(phys);
	u32 v;

	asm volatile("dc ivac, %0\n\tdsb sy\n\t" : : "r"(p) : "memory");
	v = *p;
	return v;
}

static u32 r1_crumb_read(void)
{
	return r1_crumb_read_addr(R1_CRUMB_PHYS);
}

/* Assembled helpers (see r1_asm.S). */
extern void r1_dcache_clean_poc(void *addr, unsigned long len);
extern void r1_icache_inval_all(void);
extern void r1_install_idmap(unsigned long pgd_phys, unsigned long t0sz);
extern char r1_relocate_new_kernel[];
extern char r1_relocate_new_kernel_end[];

/* 3-level translation for VA_BITS=39 with 4K pages. */
#define R1_PGD_SHIFT	30
#define R1_PMD_SHIFT	21
#define R1_PTRS		512
#define R1_T0SZ		(64 - 39)	/* 25 */

/* arm64 stage-2 block descriptor bits (normal, inner-shareable, EL1 RW, XN=0). */
#define R1_PMD_TYPE_SECT	(1UL << 0)
#define R1_PMD_SECT_AF		(1UL << 10)
#define R1_PMD_SECT_S		(3UL << 8)
#define R1_MT_NORMAL_IDX	4
#define R1_ATTRINDX(t)		((t) << 2)
#define R1_BLOCK_FLAGS	(R1_PMD_TYPE_SECT | R1_PMD_SECT_AF | \
			 R1_PMD_SECT_S | R1_ATTRINDX(R1_MT_NORMAL_IDX))
#define R1_TABLE_DESC		3UL	/* PMD_TYPE_TABLE */

#define R1_2M		(1UL << 21)

struct r1_payload {
	char *image;
	size_t image_size;
	char *dtb;
	size_t dtb_size;
	char *initrd;
	size_t initrd_size;
};

static int r1_read_file(const char *path, char **out, size_t *out_size)
{
	struct file *f;
	loff_t size;
	char *buf;
	loff_t pos = 0;
	int ret;

	if (!path || !*path)
		return -EINVAL;

	f = filp_open(path, O_RDONLY | O_LARGEFILE, 0);
	if (IS_ERR(f)) {
		pr_err("r1_kexec: open %s failed: %ld\n", path, PTR_ERR(f));
		return PTR_ERR(f);
	}

	size = i_size_read(file_inode(f));
	if (size <= 0 || size > SZ_512M) {
		pr_err("r1_kexec: bad size %lld for %s\n", size, path);
		ret = -EINVAL;
		goto out_close;
	}

	buf = vmalloc(size);
	if (!buf) {
		ret = -ENOMEM;
		goto out_close;
	}

	while (pos < size) {
		ret = kernel_read(f, pos, buf + pos, size - pos);
		if (ret <= 0) {
			pr_err("r1_kexec: read %s failed at %lld: %d\n",
			       path, pos, ret);
			vfree(buf);
			ret = ret ? ret : -EIO;
			goto out_close;
		}
		pos += ret;
	}

	*out = buf;
	*out_size = size;
	ret = 0;

out_close:
	filp_close(f, NULL);
	return ret;
}

/* Minimal flat-DTB walker: rewrite /chosen/linux,initrd-{start,end} in place. */
#define R1_FDT_MAGIC		0xd00dfeed
#define R1_FDT_BEGIN_NODE	1
#define R1_FDT_END_NODE		2
#define R1_FDT_PROP		3
#define R1_FDT_END		9

static int r1_fdt_fixup_initrd(char *fdt, unsigned long size,
			       unsigned long start, unsigned long end)
{
	u32 magic, totalsize, off_struct, off_strings;
	char *p, *strings, *limit;
	int depth = 0, chosen_depth = -1, found = 0;

	if (size < 40)
		return -EINVAL;
	magic = be32_to_cpu(*(u32 *)fdt);
	totalsize = be32_to_cpu(*(u32 *)(fdt + 4));
	if (magic != R1_FDT_MAGIC || totalsize > size)
		return -EINVAL;
	off_struct = be32_to_cpu(*(u32 *)(fdt + 8));
	off_strings = be32_to_cpu(*(u32 *)(fdt + 12));
	strings = fdt + off_strings;
	p = fdt + off_struct;
	limit = fdt + totalsize;

	while (p + 4 <= limit) {
		u32 tag = be32_to_cpu(*(u32 *)p);
		p += 4;

		switch (tag) {
		case R1_FDT_BEGIN_NODE: {
			const char *name = p;
			while (p < limit && *p)
				p++;
			p++;
			if (chosen_depth < 0 && depth == 1 &&
			    !strcmp(name, "chosen"))
				chosen_depth = depth + 1;
			depth++;
			break;
		}
		case R1_FDT_END_NODE:
			if (chosen_depth == depth)
				chosen_depth = -1;
			depth--;
			break;
		case R1_FDT_PROP: {
			u32 len, nameoff;
			const char *name;
			unsigned long val;

			if (p + 8 > limit)
				return -EINVAL;
			len = be32_to_cpu(*(u32 *)p);
			nameoff = be32_to_cpu(*(u32 *)(p + 4));
			p += 8;
			name = strings + nameoff;
			if (chosen_depth == depth &&
			    (!strcmp(name, "linux,initrd-start") ||
			     !strcmp(name, "linux,initrd-end"))) {
				val = strcmp(name, "linux,initrd-start") ?
					end : start;
				if (len == 8)
					*(u64 *)p = cpu_to_be64(val);
				else if (len == 4)
					*(u32 *)p = cpu_to_be32(val);
				else
					return -EINVAL;
				found++;
			}
			p += ALIGN(len, 4);
			break;
		}
		case R1_FDT_END:
			goto out;
		default:
			return -EINVAL;
		}
	}
out:
	if (found != 2) {
		pr_err("r1_kexec: DTB lacks /chosen initrd-start/end props\n");
		return -EINVAL;
	}
	return 0;
}

static void r1_free_payload(struct r1_payload *p)
{
	vfree(p->image);
	vfree(p->dtb);
	vfree(p->initrd);
}

static int r1_load_payload(struct r1_payload *p)
{
	int ret;

	memset(p, 0, sizeof(*p));

	ret = r1_read_file(image_path, &p->image, &p->image_size);
	if (ret)
		return ret;
	ret = r1_read_file(dtb_path, &p->dtb, &p->dtb_size);
	if (ret)
		goto err;
	if (initrd_path && *initrd_path) {
		ret = r1_read_file(initrd_path, &p->initrd, &p->initrd_size);
		if (ret)
			goto err;
	}

	pr_info("r1_kexec: image %zu B, dtb %zu B, initrd %zu B\n",
		p->image_size, p->dtb_size, p->initrd_size);
	return 0;

err:
	r1_free_payload(p);
	return ret;
}

/*
 * Reserve a physically contiguous CMA run. When cma_phys is 0 we ask the
 * default CMA area and align the kernel start up to 2M inside the allocation;
 * otherwise the caller pins an exact 2M-aligned range.
 */
static int r1_alloc_cma(unsigned long total, struct page **pages,
			unsigned long *nr_pages, unsigned long *base_phys)
{
	unsigned long count, extra = R1_2M >> PAGE_SHIFT;
	struct page *p;

	/* Extra 2M absorbs the alignment gap up to the trampoline block. */
	count = (PAGE_ALIGN(total) >> PAGE_SHIFT) + extra;

	if (!cma_phys) {
		p = dma_alloc_from_contiguous(NULL, count, get_order(R1_2M));
		if (!p) {
			pr_err("r1_kexec: default CMA allocation failed\n");
			return -ENOMEM;
		}
		*pages = p;
		*nr_pages = count;
		*base_phys = (unsigned long)page_to_phys(p);
		return 0;
	}

	if (cma_phys & (R1_2M - 1)) {
		pr_err("r1_kexec: cma_phys must be 2M aligned\n");
		return -EINVAL;
	}
	if (aml_cma_alloc_range(cma_phys >> PAGE_SHIFT,
				(cma_phys + (count << PAGE_SHIFT)) >> PAGE_SHIFT)) {
		pr_err("r1_kexec: aml_cma_alloc_range failed at 0x%lx\n",
		       cma_phys);
		return -EBUSY;
	}
	*pages = pfn_to_page(cma_phys >> PAGE_SHIFT);
	*nr_pages = count;
	*base_phys = cma_phys;
	return 0;
}

static void r1_free_cma(struct page *pages, unsigned long nr_pages)
{
	if (cma_phys)
		aml_cma_free(page_to_pfn(pages), nr_pages);
	else
		dma_release_from_contiguous(NULL, pages, nr_pages);
}

static int r1_offline_secondaries(void)
{
	unsigned int cpu;
	int ret;

	if (skip_offline)
		return 0;

	for_each_online_cpu(cpu) {
		if (cpu == smp_processor_id())
			continue;
		ret = cpu_down(cpu);
		if (ret) {
			/* cpu_down already used PSCI CPU_OFF on the successful path. */
			pr_err("r1_kexec: cpu_down(%u) failed: %d\n", cpu, ret);
			return ret;
		}
	}
	return 0;
}

/*
 * Populate a private 2M identity map for the trampoline and stage the payload.
 * Returns 0 only when the caller must not return (jump performed).
 */
static int r1_stage_and_jump(const struct r1_payload *p)
{
	unsigned long total, image_phys, entry_phys, dtb_phys, initrd_phys;
	unsigned long tramp_phys, stack_phys, base_phys, base_virt, cursor;
	unsigned long nr_pages, tramp_size, pgd_phys, pmd_phys;
	u64 text_off;
	struct page *pages, *idmap_pages;
	unsigned long *pgd, *pmd;
	unsigned long idmap_virt;
	int order, ret;

	total = PAGE_ALIGN(p->image_size) + PAGE_ALIGN(p->dtb_size) +
		PAGE_ALIGN(p->initrd_size) + 2 * R1_2M + 3 * PAGE_SIZE;
	ret = r1_alloc_cma(total, &pages, &nr_pages, &base_phys);
	if (ret)
		return ret;
	base_virt = (unsigned long)page_address(pages);
	r1_step(3);

	image_phys = ALIGN(base_phys, R1_2M);
	/* arm64 Image header: text_offset at byte 8; stext lives there, not at 0. */
	memcpy(&text_off, p->image + 8, sizeof(text_off));
	if (text_off >= p->image_size) {
		pr_err("r1_kexec: bad text_offset 0x%llx\n", text_off);
		ret = -EINVAL;
		goto out_cma;
	}
	/*
	 * head.S derives its KASLR offset as (base - text_offset) & (2M-1).
	 * Stock loads at text_offset so that is zero. Mirror it: give the
	 * image base the same 2M sub-alignment as text_offset.
	 */
	image_phys += text_off & (R1_2M - 1);
	entry_phys = image_phys;
	if (reenter_self) {
		unsigned long self = (unsigned long)kallsyms_lookup_name("_text");

		if (!self) {
			pr_err("r1_kexec: _text not found\n");
			ret = -ENOENT;
			goto out_cma;
		}
		entry_phys = virt_to_phys((void *)self);
		pr_info("r1_kexec: self _text=0x%lx -> entry=0x%lx\n",
			self, entry_phys);
	}
	cursor = image_phys + PAGE_ALIGN(p->image_size);
	dtb_phys = cursor;
	cursor += PAGE_ALIGN(p->dtb_size);
	initrd_phys = cursor;
	cursor += PAGE_ALIGN(p->initrd_size);
	tramp_phys = ALIGN(cursor, R1_2M);
	stack_phys = tramp_phys + R1_2M;	/* top of the last page in the block */

	if (tramp_phys + R1_2M > base_phys + (nr_pages << PAGE_SHIFT)) {
		pr_err("r1_kexec: staging does not fit in CMA allocation\n");
		ret = -ENOMEM;
		goto out_cma;
	}

	if (p->initrd_size) {
		ret = r1_fdt_fixup_initrd(p->dtb, p->dtb_size, initrd_phys,
					  initrd_phys + p->initrd_size);
		if (ret)
			goto out_cma;
	}
	r1_step(4);

	/* CMA pages are mapped in the linear map; raw phys is not a kernel VA. */
	memcpy((void *)(base_virt + image_phys - base_phys),
	       p->image, p->image_size);
	memcpy((void *)(base_virt + dtb_phys - base_phys),
	       p->dtb, p->dtb_size);
	if (p->initrd_size)
		memcpy((void *)(base_virt + initrd_phys - base_phys),
		       p->initrd, p->initrd_size);

	tramp_size = (unsigned long)(r1_relocate_new_kernel_end -
				     r1_relocate_new_kernel);
	memcpy((void *)(base_virt + tramp_phys - base_phys),
	       r1_relocate_new_kernel, tramp_size);
	r1_step(5);

	/* Two pages: PGD + single PMD; both zeroed before descriptor writes. */
	order = get_order(2 * PAGE_SIZE);
	idmap_virt = __get_free_pages(GFP_KERNEL | __GFP_ZERO, order);
	if (!idmap_virt) {
		pr_err("r1_kexec: idmap page allocation failed\n");
		ret = -ENOMEM;
		goto out_cma;
	}
	idmap_pages = virt_to_page(idmap_virt);
	pgd = (unsigned long *)idmap_virt;
	pmd = (unsigned long *)(idmap_virt + PAGE_SIZE);
	pgd_phys = (unsigned long)page_to_phys(idmap_pages);
	pmd_phys = (unsigned long)page_to_phys(idmap_pages + 1);

	/* One PMD covers the 2M block that holds the trampoline. */
	pgd[(tramp_phys >> R1_PGD_SHIFT) & (R1_PTRS - 1)] =
		pmd_phys | R1_TABLE_DESC;
	pmd[(tramp_phys >> R1_PMD_SHIFT) & (R1_PTRS - 1)] =
		(tramp_phys & ~(R1_2M - 1)) | R1_BLOCK_FLAGS;
	r1_step(6);

	/* Make staged bytes and new page tables visible with the MMU still on. */
	r1_dcache_clean_poc((void *)base_virt, nr_pages << PAGE_SHIFT);
	r1_dcache_clean_poc((void *)idmap_virt, 2 * PAGE_SIZE);
	r1_icache_inval_all();
	r1_step(7);

	pr_info("r1_kexec: image=0x%lx entry=0x%lx dtb=0x%lx initrd=0x%lx tramp=0x%lx\n",
		image_phys, entry_phys, dtb_phys, initrd_phys, tramp_phys);
	pr_info("r1_kexec: jumping (no return)\n");

	ret = r1_offline_secondaries();
	if (ret)
		goto out_idmap;
	r1_step(8);

	r1_install_idmap(pgd_phys, R1_T0SZ);
	r1_step(9);
	r1_step(10);
	((void (*)(unsigned long, unsigned long, unsigned long,
		   unsigned long))tramp_phys)(
		entry_phys, dtb_phys, stack_phys,
		(unsigned long)phys_to_virt(R1_CRUMB_PHYS));

	/* Unreachable; kept so the compiler does not warn. */
	BUG();
	return -EIO;

out_idmap:
	free_pages(idmap_virt, order);
out_cma:
	r1_free_cma(pages, nr_pages);
	return ret;
}

static int __init r1_init(void)
{
	struct r1_payload p;
	int ret;

	if (read_crumb) {
		unsigned long phys = (read_crumb == 1) ? R1_CRUMB_PHYS : read_crumb;

		pr_info("r1_kexec: crumb@0x%lx = %u\n",
			phys, r1_crumb_read_addr(phys));
		return 0;
	}
	if (!fire) {
		pr_info("r1_kexec: staged only, fire=0 (no jump)\n");
		return 0;
	}
	if (!image_path || !dtb_path) {
		pr_err("r1_kexec: image_path and dtb_path are required\n");
		return -EINVAL;
	}
	r1_step(1);

	ret = r1_load_payload(&p);
	if (ret)
		return ret;
	r1_step(2);
	ret = r1_stage_and_jump(&p);
	r1_free_payload(&p);
	return ret;
}

static void __exit r1_exit(void)
{
	/* No teardown: a successful load never returns to the old kernel. */
}

module_init(r1_init);
module_exit(r1_exit);
