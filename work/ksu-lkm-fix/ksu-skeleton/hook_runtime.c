#include <linux/errno.h>
#include <linux/kallsyms.h>
#include <linux/module.h>
#include <linux/printk.h>
#include <linux/string.h>
#include <linux/vmalloc.h>
#include <asm/cacheflush.h>
#include <asm/ptrace.h>

#include "arch.h"
#include "hook_runtime.h"
#include "klog.h" // IWYU pragma: keep

#define KSU_PATCH_WORDS 6
#define KSU_STUB_SIZE 0x100
#define KSU_DISPATCH_OFF 0x44
#define KSU_ORIG_OFF 0x78
#define KSU_CONT_OFF 0x98

#define KSU_LDR_X16_PC8 0x58000050U
#define KSU_BR_X16 0xd61f0200U

extern void ksu_stub_faccessat(void);
extern void ksu_stub_read(void);
extern void ksu_stub_newfstatat(void);
extern void ksu_stub_reboot(void);
extern void ksu_stub_prctl(void);
extern void ksu_stub_sysexecve(void);

extern int ksu_handle_faccessat(int *dfd, const char __user **filename_user,
				int *mode, int *flags);
extern int ksu_handle_stat(int *dfd, const char __user **filename_user,
			   int *flags);
extern int ksu_handle_execveat(int *fd, struct filename **filename_ptr,
			       void *argv, void *envp, int *flags);
extern int ksu_handle_prctl(int option, unsigned long arg2, unsigned long arg3,
			    unsigned long arg4, unsigned long arg5);
extern int ksu_handle_sys_read(unsigned int fd, char __user **buf_ptr,
			       size_t *count_ptr);
extern int ksu_handle_execve_sucompat(int *fd,
				      const char __user **filename_user,
				      void *argv, void *envp, int *flags);
extern int ksu_handle_execve_ksud(const char __user *filename_user,
				  const char __user *const __user *__argv);

struct ksu_hook_entry {
	const char *name;
	void *stub;
	unsigned long addr;
	u32 orig[KSU_PATCH_WORDS];
	bool installed;
};

/* do_execve is omitted: its argument layout does not match
 * ksu_handle_execveat (which expects fd/filename/argv/envp/flags), and the
 * real su path is covered by sys_execve below. */
static struct ksu_hook_entry hooks[] = {
	{ SYS_FACCESSAT_SYMBOL, ksu_stub_faccessat, 0, {}, false },
	{ SYS_READ_SYMBOL, ksu_stub_read, 0, {}, false },
	{ SYS_NEWFSTATAT_SYMBOL, ksu_stub_newfstatat, 0, {}, false },
	{ "sys_reboot", ksu_stub_reboot, 0, {}, false },
	{ PRCTL_SYMBOL, ksu_stub_prctl, 0, {}, false },
	{ SYS_EXECVE_SYMBOL, ksu_stub_sysexecve, 0, {}, false },
	/* 32-bit userspace reaches execve through the compat syscall; hooking
	 * only sys_execve leaves the su path invisible to every app on this
	 * device, since all of them are 32-bit. */
	{ "compat_sys_execve", ksu_stub_sysexecve, 0, {}, false },
};

static int (*ksu_patch_text)(void **addrs, u32 *insns, int cnt);
static void *stub_page;

static bool is_pc_relative(u32 insn)
{
	return (insn & 0xff000000U) == 0x10000000U ||
	       (insn & 0xff000000U) == 0x14000000U ||
	       (insn & 0xff000000U) == 0x54000000U ||
	       (insn & 0x3b000000U) == 0x18000000U;
}

int ksu_hook_dispatch(int id, struct pt_regs *regs)
{
	switch (id) {
	case 0: {
		int fd = -100;
		struct filename *filename = (struct filename *)regs->regs[1];
		int flags = (int)regs->regs[2];

		ksu_handle_execveat(&fd, &filename, NULL, NULL, &flags);
		regs->regs[0] = (unsigned long)filename;
		break;
	}
	case 1: {
		int dfd = (int)regs->regs[0];
		const char __user *filename = (const char __user *)regs->regs[1];
		int mode = (int)regs->regs[2];
		int flags = (int)regs->regs[3];

		ksu_handle_faccessat(&dfd, &filename, &mode, &flags);
		regs->regs[0] = (unsigned long)(unsigned int)dfd;
		regs->regs[1] = (unsigned long)filename;
		regs->regs[2] = (unsigned long)(unsigned int)mode;
		regs->regs[3] = (unsigned long)(unsigned int)flags;
		break;
	}
	case 2: {
		char __user *buf = (char __user *)regs->regs[1];
		size_t count = regs->regs[2];

		ksu_handle_sys_read((unsigned int)regs->regs[0], &buf, &count);
		regs->regs[1] = (unsigned long)buf;
		regs->regs[2] = (unsigned long)count;
		break;
	}
	case 3: {
		int dfd = (int)regs->regs[0];
		const char __user *filename = (const char __user *)regs->regs[1];
		int flags = (int)regs->regs[3];

		ksu_handle_stat(&dfd, &filename, &flags);
		regs->regs[0] = (unsigned long)(unsigned int)dfd;
		regs->regs[1] = (unsigned long)filename;
		regs->regs[3] = (unsigned long)(unsigned int)flags;
		break;
	}
	case 5:
		ksu_handle_prctl((int)regs->regs[0], regs->regs[1],
				 regs->regs[2], regs->regs[3], regs->regs[4]);
		break;
	case 6: {
		int fd = -100;
		const char __user *filename = (const char __user *)regs->regs[0];
		const char __user *const __user *argv =
			(const char __user *const __user *)regs->regs[1];

		/* The adapter builds a struct filename from the user pointer;
		 * it also drives track_throne(), which crowns the Manager. */
		ksu_handle_execve_ksud(filename, argv);
		ksu_handle_execve_sucompat(&fd, &filename, NULL, NULL, NULL);
		regs->regs[0] = (unsigned long)filename;
		break;
	}
	default:
		break;
	}
	return 0;
}

static int patch_hook(struct ksu_hook_entry *hook, u32 *insns)
{
	void *addrs[KSU_PATCH_WORDS + 1];
	int i;

	for (i = 0; i < KSU_PATCH_WORDS; i++) {
		addrs[i] = (void *)(hook->addr + i * 4);
	}
	addrs[KSU_PATCH_WORDS] = (void *)(hook->addr + KSU_PATCH_WORDS * 4);

	return ksu_patch_text(addrs, insns, KSU_PATCH_WORDS);
}

int ksu_hook_init(void)
{
	int i, j, ret;

	ksu_patch_text = (void *)kallsyms_lookup_name("aarch64_insn_patch_text");
	if (!ksu_patch_text) {
		pr_err("ksu_hook: aarch64_insn_patch_text not found\n");
		return -ENOENT;
	}

	for (i = 0; i < ARRAY_SIZE(hooks); i++) {
		struct ksu_hook_entry *hook = &hooks[i];

		hook->addr = kallsyms_lookup_name(hook->name);
		if (!hook->addr) {
			pr_err("ksu_hook: symbol %s not found\n", hook->name);
			return -ENOENT;
		}
		ret = probe_kernel_read(hook->orig, (void *)hook->addr,
					sizeof(hook->orig));
		if (ret) {
			pr_err("ksu_hook: read %s failed: %d\n", hook->name, ret);
			return -EFAULT;
		}
		for (j = 0; j < KSU_PATCH_WORDS; j++) {
			if (is_pc_relative(hook->orig[j])) {
				pr_err("ksu_hook: PC-relative insn in %s\n",
				       hook->name);
				return -EINVAL;
			}
		}
		pr_info("ksu_hook: %s at %px\n", hook->name,
			(void *)hook->addr);
	}

	stub_page = vmalloc(PAGE_SIZE);
	if (!stub_page) {
		return -ENOMEM;
	}
	memset(stub_page, 0, PAGE_SIZE);

	for (i = 0; i < ARRAY_SIZE(hooks); i++) {
		void *stub = stub_page + i * KSU_STUB_SIZE;
		u64 *slot;

		/* The trampoline executes from this page, not from the module
		 * text: the assembled stubs have zero-filled dispatch slots. */
		memcpy(stub, hooks[i].stub, KSU_STUB_SIZE);
		memcpy(stub + KSU_ORIG_OFF, hooks[i].orig,
		       sizeof(hooks[i].orig));
		slot = stub + KSU_CONT_OFF;
		*slot = hooks[i].addr + KSU_PATCH_WORDS * 4;
		slot = stub + KSU_DISPATCH_OFF;
		*slot = (u64)ksu_hook_dispatch;
	}

	ret = set_memory_x((unsigned long)stub_page, 1);
	if (ret) {
		pr_err("ksu_hook: set_memory_x failed: %d\n", ret);
		return ret;
	}

	for (i = 0; i < ARRAY_SIZE(hooks); i++) {
		unsigned long stub_addr =
			(unsigned long)(stub_page + i * KSU_STUB_SIZE);
		u32 insns[KSU_PATCH_WORDS] = {
			KSU_LDR_X16_PC8,
			KSU_BR_X16,
			(u32)stub_addr,
			(u32)(stub_addr >> 32),
			0,
			0,
		};

		ret = patch_hook(&hooks[i], insns);
		if (ret) {
			pr_err("ksu_hook: patch %s failed: %d\n",
			       hooks[i].name, ret);
			return ret;
		}
		hooks[i].installed = true;
	}

	return 0;
}

void ksu_hook_exit(void)
{
	int i;

	for (i = 0; i < ARRAY_SIZE(hooks); i++) {
		if (!hooks[i].installed) {
			continue;
		}
		patch_hook(&hooks[i], hooks[i].orig);
		hooks[i].installed = false;
	}

	if (stub_page) {
		set_memory_nx((unsigned long)stub_page, 1);
		vfree(stub_page);
		stub_page = NULL;
	}
}
