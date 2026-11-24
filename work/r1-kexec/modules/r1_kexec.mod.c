#include <linux/module.h>
#include <linux/vermagic.h>
#include <linux/compiler.h>

MODULE_INFO(vermagic, VERMAGIC_STRING);

__visible struct module __this_module
__attribute__((section(".gnu.linkonce.this_module"))) = {
	.name = KBUILD_MODNAME,
	.init = init_module,
#ifdef CONFIG_MODULE_UNLOAD
	.exit = cleanup_module,
#endif
	.arch = MODULE_ARCH_INIT,
};

#ifdef RETPOLINE
MODULE_INFO(retpoline, "Y");
#endif

static const struct modversion_info ____versions[]
__used
__attribute__((section("__versions"))) = {
	{ 0xd5272b2f, __VMLINUX_SYMBOL_STR(module_layout) },
	{ 0x7cb1ae69, __VMLINUX_SYMBOL_STR(cpu_down) },
	{ 0x1fdc7df2, __VMLINUX_SYMBOL_STR(_mcount) },
	{ 0xd6ee688f, __VMLINUX_SYMBOL_STR(vmalloc) },
	{ 0x146c993c, __VMLINUX_SYMBOL_STR(param_ops_int) },
	{ 0x736dbe2a, __VMLINUX_SYMBOL_STR(aml_cma_free) },
	{ 0xc0a3d105, __VMLINUX_SYMBOL_STR(find_next_bit) },
	{ 0x79bd9f3b, __VMLINUX_SYMBOL_STR(filp_close) },
	{ 0x999e8297, __VMLINUX_SYMBOL_STR(vfree) },
	{ 0xe2d5255a, __VMLINUX_SYMBOL_STR(strcmp) },
	{ 0xfe7c4287, __VMLINUX_SYMBOL_STR(nr_cpu_ids) },
	{ 0x5d5ca1ee, __VMLINUX_SYMBOL_STR(kernel_read) },
	{ 0x898c8607, __VMLINUX_SYMBOL_STR(param_ops_charp) },
	{ 0xbe400752, __VMLINUX_SYMBOL_STR(dma_alloc_from_contiguous) },
	{ 0x27e1a049, __VMLINUX_SYMBOL_STR(printk) },
	{ 0x582a1d93, __VMLINUX_SYMBOL_STR(__cpu_online_mask) },
	{ 0xc917e655, __VMLINUX_SYMBOL_STR(debug_smp_processor_id) },
	{ 0x7c1372e8, __VMLINUX_SYMBOL_STR(panic) },
	{ 0xfadf2436, __VMLINUX_SYMBOL_STR(memstart_addr) },
	{ 0x228f4555, __VMLINUX_SYMBOL_STR(kimage_voffset) },
	{ 0xe007de41, __VMLINUX_SYMBOL_STR(kallsyms_lookup_name) },
	{ 0xd6631258, __VMLINUX_SYMBOL_STR(dma_release_from_contiguous) },
	{ 0x93fca811, __VMLINUX_SYMBOL_STR(__get_free_pages) },
	{ 0x4b6d6e0, __VMLINUX_SYMBOL_STR(aml_cma_alloc_range) },
	{ 0x4302d0eb, __VMLINUX_SYMBOL_STR(free_pages) },
	{ 0x4829a47e, __VMLINUX_SYMBOL_STR(memcpy) },
	{ 0x59e368f0, __VMLINUX_SYMBOL_STR(param_ops_ulong) },
	{ 0x509757a2, __VMLINUX_SYMBOL_STR(filp_open) },
};

static const char __module_depends[]
__used
__attribute__((section(".modinfo"))) =
"depends=";

