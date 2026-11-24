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
	{ 0xd461c682, __VMLINUX_SYMBOL_STR(d_path) },
	{ 0xe53965df, __VMLINUX_SYMBOL_STR(kernel_write) },
	{ 0xb966afb4, __VMLINUX_SYMBOL_STR(kmalloc_caches) },
	{ 0x2e7fa5a5, __VMLINUX_SYMBOL_STR(set_groups) },
	{ 0xd2b09ce5, __VMLINUX_SYMBOL_STR(__kmalloc) },
	{ 0xf9a482f9, __VMLINUX_SYMBOL_STR(msleep) },
	{ 0x1fdc7df2, __VMLINUX_SYMBOL_STR(_mcount) },
	{ 0xa2dc59e, __VMLINUX_SYMBOL_STR(generic_file_llseek) },
	{ 0xf33847d3, __VMLINUX_SYMBOL_STR(_raw_spin_unlock) },
	{ 0x9ee98c7b, __VMLINUX_SYMBOL_STR(crypto_alloc_shash) },
	{ 0xd6ee688f, __VMLINUX_SYMBOL_STR(vmalloc) },
	{ 0x349cba85, __VMLINUX_SYMBOL_STR(strchr) },
	{ 0x98cf60b3, __VMLINUX_SYMBOL_STR(strlen) },
	{ 0x43a53735, __VMLINUX_SYMBOL_STR(__alloc_workqueue_key) },
	{ 0x62827bec, __VMLINUX_SYMBOL_STR(security_secctx_to_secid) },
	{ 0x685e31ca, __VMLINUX_SYMBOL_STR(groups_sort) },
	{ 0x31244bfc, __VMLINUX_SYMBOL_STR(commit_creds) },
	{ 0xb70789e, __VMLINUX_SYMBOL_STR(__might_fault) },
	{ 0x84bc974b, __VMLINUX_SYMBOL_STR(__arch_copy_from_user) },
	{ 0xa22c9f04, __VMLINUX_SYMBOL_STR(___might_sleep) },
	{ 0x79bd9f3b, __VMLINUX_SYMBOL_STR(filp_close) },
	{ 0x643d9ba1, __VMLINUX_SYMBOL_STR(groups_free) },
	{ 0xd45cc6ca, __VMLINUX_SYMBOL_STR(bin2hex) },
	{ 0x9156d1b1, __VMLINUX_SYMBOL_STR(mutex_unlock) },
	{ 0x85df9b6c, __VMLINUX_SYMBOL_STR(strsep) },
	{ 0x999e8297, __VMLINUX_SYMBOL_STR(vfree) },
	{ 0x892b26a0, __VMLINUX_SYMBOL_STR(set_memory_nx) },
	{ 0x24428be5, __VMLINUX_SYMBOL_STR(strncpy_from_user) },
	{ 0xc499ae1e, __VMLINUX_SYMBOL_STR(kstrdup) },
	{ 0x526c3a6c, __VMLINUX_SYMBOL_STR(jiffies) },
	{ 0xe2d5255a, __VMLINUX_SYMBOL_STR(strcmp) },
	{ 0x5d5ca1ee, __VMLINUX_SYMBOL_STR(kernel_read) },
	{ 0x2e84fdbf, __VMLINUX_SYMBOL_STR(kern_path) },
	{ 0xdcb764ad, __VMLINUX_SYMBOL_STR(memset) },
	{ 0x27e1a049, __VMLINUX_SYMBOL_STR(printk) },
	{ 0x20c55ae0, __VMLINUX_SYMBOL_STR(sscanf) },
	{ 0x305cec12, __VMLINUX_SYMBOL_STR(_raw_spin_trylock) },
	{ 0x449ad0a7, __VMLINUX_SYMBOL_STR(memcmp) },
	{ 0xfa1c1cad, __VMLINUX_SYMBOL_STR(crypto_shash_digest) },
	{ 0x9166fada, __VMLINUX_SYMBOL_STR(strncpy) },
	{ 0x8fa8f791, __VMLINUX_SYMBOL_STR(_raw_spin_unlock_irq) },
	{ 0x5a921311, __VMLINUX_SYMBOL_STR(strncmp) },
	{ 0x5792f848, __VMLINUX_SYMBOL_STR(strlcpy) },
	{ 0x6c91dc73, __VMLINUX_SYMBOL_STR(mutex_lock) },
	{ 0x8c03d20c, __VMLINUX_SYMBOL_STR(destroy_workqueue) },
	{ 0x1e6d26a8, __VMLINUX_SYMBOL_STR(strstr) },
	{ 0x233e1024, __VMLINUX_SYMBOL_STR(dentry_path_raw) },
	{ 0xe007de41, __VMLINUX_SYMBOL_STR(kallsyms_lookup_name) },
	{ 0x1377fab5, __VMLINUX_SYMBOL_STR(fput) },
	{ 0xa37e78b6, __VMLINUX_SYMBOL_STR(flex_array_get) },
	{ 0x5d55d955, __VMLINUX_SYMBOL_STR(prepare_creds) },
	{ 0x2ea8b4db, __VMLINUX_SYMBOL_STR(init_task) },
	{ 0x67d8d35, __VMLINUX_SYMBOL_STR(security_release_secctx) },
	{ 0xefdd70ce, __VMLINUX_SYMBOL_STR(security_secid_to_secctx) },
	{ 0xa916b694, __VMLINUX_SYMBOL_STR(strnlen) },
	{ 0xb35dea8f, __VMLINUX_SYMBOL_STR(__arch_copy_to_user) },
	{ 0x20ffa7f6, __VMLINUX_SYMBOL_STR(_raw_spin_lock_irq) },
	{ 0xbbec8c5, __VMLINUX_SYMBOL_STR(crypto_destroy_tfm) },
	{ 0x800fb92b, __VMLINUX_SYMBOL_STR(full_name_hash) },
	{ 0x634f3332, __VMLINUX_SYMBOL_STR(path_put) },
	{ 0x58894f4a, __VMLINUX_SYMBOL_STR(kmem_cache_alloc_trace) },
	{ 0x5cd885d5, __VMLINUX_SYMBOL_STR(_raw_spin_lock) },
	{ 0x7a4b576, __VMLINUX_SYMBOL_STR(flex_array_free) },
	{ 0x3e2b0ba6, __VMLINUX_SYMBOL_STR(groups_alloc) },
	{ 0x37a0cba, __VMLINUX_SYMBOL_STR(kfree) },
	{ 0xa46f2f1b, __VMLINUX_SYMBOL_STR(kstrtouint) },
	{ 0x2e1da9fb, __VMLINUX_SYMBOL_STR(probe_kernel_read) },
	{ 0x4829a47e, __VMLINUX_SYMBOL_STR(memcpy) },
	{ 0x37318c4c, __VMLINUX_SYMBOL_STR(abort_creds) },
	{ 0xdf73c83b, __VMLINUX_SYMBOL_STR(fget) },
	{ 0x13315729, __VMLINUX_SYMBOL_STR(flex_array_alloc) },
	{ 0x988ed85d, __VMLINUX_SYMBOL_STR(set_memory_x) },
	{ 0x57a7bd4b, __VMLINUX_SYMBOL_STR(iterate_dir) },
	{ 0x9bbe88b3, __VMLINUX_SYMBOL_STR(flex_array_put) },
	{ 0x2e0d2f7f, __VMLINUX_SYMBOL_STR(queue_work_on) },
	{ 0x28318305, __VMLINUX_SYMBOL_STR(snprintf) },
	{ 0xe95e00cf, __VMLINUX_SYMBOL_STR(flex_array_get_ptr) },
	{ 0x88db9f48, __VMLINUX_SYMBOL_STR(__check_object_size) },
	{ 0x9fd7cda1, __VMLINUX_SYMBOL_STR(flex_array_prealloc) },
	{ 0x509757a2, __VMLINUX_SYMBOL_STR(filp_open) },
};

static const char __module_depends[]
__used
__attribute__((section(".modinfo"))) =
"depends=";

