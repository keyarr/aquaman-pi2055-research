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
	{ 0x2059b9e4, __VMLINUX_SYMBOL_STR(module_layout) },
	{ 0x7cb1ae69, __VMLINUX_SYMBOL_STR(cpu_down) },
	{ 0x1fdc7df2, __VMLINUX_SYMBOL_STR(_mcount) },
	{ 0xd6ee688f, __VMLINUX_SYMBOL_STR(vmalloc) },
	{ 0x7edcbba9, __VMLINUX_SYMBOL_STR(param_ops_int) },
	{ 0x736dbe2a, __VMLINUX_SYMBOL_STR(aml_cma_free) },
	{ 0xb678975d, __VMLINUX_SYMBOL_STR(irq_trace_stop) },
	{ 0xc0a3d105, __VMLINUX_SYMBOL_STR(find_next_bit) },
	{ 0xf0f2924e, __VMLINUX_SYMBOL_STR(filp_close) },
	{ 0x999e8297, __VMLINUX_SYMBOL_STR(vfree) },
	{ 0xe2d5255a, __VMLINUX_SYMBOL_STR(strcmp) },
	{ 0xfe7c4287, __VMLINUX_SYMBOL_STR(nr_cpu_ids) },
	{ 0x4a6b87d3, __VMLINUX_SYMBOL_STR(kernel_read) },
	{ 0x50dad30c, __VMLINUX_SYMBOL_STR(param_ops_charp) },
	{ 0x706c5a65, __VMLINUX_SYMBOL_STR(preempt_count_sub) },
	{ 0xee5e7ccb, __VMLINUX_SYMBOL_STR(dma_alloc_from_contiguous) },
	{ 0x27e1a049, __VMLINUX_SYMBOL_STR(printk) },
	{ 0x449ad0a7, __VMLINUX_SYMBOL_STR(memcmp) },
	{ 0x582a1d93, __VMLINUX_SYMBOL_STR(__cpu_online_mask) },
	{ 0xc917e655, __VMLINUX_SYMBOL_STR(debug_smp_processor_id) },
	{ 0x7c1372e8, __VMLINUX_SYMBOL_STR(panic) },
	{ 0xfadf2436, __VMLINUX_SYMBOL_STR(memstart_addr) },
	{ 0x228f4555, __VMLINUX_SYMBOL_STR(kimage_voffset) },
	{ 0xe007de41, __VMLINUX_SYMBOL_STR(kallsyms_lookup_name) },
	{ 0x43b0c9c3, __VMLINUX_SYMBOL_STR(preempt_schedule) },
	{ 0x9f46ced8, __VMLINUX_SYMBOL_STR(__sw_hweight64) },
	{ 0x763f63e5, __VMLINUX_SYMBOL_STR(dma_release_from_contiguous) },
	{ 0x93fca811, __VMLINUX_SYMBOL_STR(__get_free_pages) },
	{ 0xdb7305a1, __VMLINUX_SYMBOL_STR(__stack_chk_fail) },
	{ 0x4b6d6e0, __VMLINUX_SYMBOL_STR(aml_cma_alloc_range) },
	{ 0x4302d0eb, __VMLINUX_SYMBOL_STR(free_pages) },
	{ 0x4829a47e, __VMLINUX_SYMBOL_STR(memcpy) },
	{ 0x8f678b07, __VMLINUX_SYMBOL_STR(__stack_chk_guard) },
	{ 0x216daeee, __VMLINUX_SYMBOL_STR(irq_trace_start) },
	{ 0xf229424a, __VMLINUX_SYMBOL_STR(preempt_count_add) },
	{ 0x80b53dfb, __VMLINUX_SYMBOL_STR(param_ops_ulong) },
	{ 0xb1b9f47e, __VMLINUX_SYMBOL_STR(param_ops_uint) },
	{ 0x88df3864, __VMLINUX_SYMBOL_STR(filp_open) },
};

static const char __module_depends[]
__used
__attribute__((section(".modinfo"))) =
"depends=";

