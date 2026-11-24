#include <linux/capability.h>
#include <linux/compiler.h>
#include <linux/fs.h>
#include <linux/gfp.h>
#include <linux/kernel.h>
#include <linux/list.h>
#include <linux/err.h>
#include <linux/namei.h>
#include <linux/printk.h>
#include <linux/slab.h>
#include <linux/types.h>
#include <linux/uaccess.h>
#include <linux/version.h>
#if LINUX_VERSION_CODE >= KERNEL_VERSION(4, 14, 0)
#include <linux/compiler_types.h>
#endif

#include "ksu.h"
#include "klog.h" // IWYU pragma: keep
#include "selinux/selinux.h"
#include "kernel_compat.h"
#include "allowlist.h"
#include "manager.h"

#define FILE_MAGIC 0x7f4b5355 // ' KSU', u32
#define FILE_FORMAT_VERSION 3 // u32
#define ALLOWLIST_HEADER_SIZE (sizeof(u32) + sizeof(u32))
#define ALLOWLIST_MAX_RECORDS 1024

#define KSU_APP_PROFILE_PRESERVE_UID 9999 // NOBODY_UID
#define KSU_DEFAULT_SELINUX_DOMAIN "u:r:su:s0"

static DEFINE_MUTEX(allowlist_mutex);

#ifdef CONFIG_KSU_ALLOWLIST_IO_VIA_KSUD
static bool allowlist_save_pending;
#endif

// default profiles, these may be used frequently, so we cache it
static struct root_profile default_root_profile;
static struct non_root_profile default_non_root_profile;

static int allow_list_arr[PAGE_SIZE / sizeof(int)] __read_mostly __aligned(PAGE_SIZE);
static int allow_list_pointer __read_mostly = 0;

static void remove_uid_from_arr(uid_t uid)
{
	int *temp_arr;
	int i, j;

	if (allow_list_pointer == 0)
		return;

	temp_arr = kmalloc(sizeof(allow_list_arr), GFP_KERNEL);
	if (temp_arr == NULL) {
		pr_err("%s: unable to allocate memory\n", __func__);
		return;
	}

	for (i = j = 0; i < allow_list_pointer; i++) {
		if (allow_list_arr[i] == uid)
			continue;
		temp_arr[j++] = allow_list_arr[i];
	}

	allow_list_pointer = j;

	for (; j < ARRAY_SIZE(allow_list_arr); j++)
		temp_arr[j] = -1;

	memcpy(&allow_list_arr, temp_arr, PAGE_SIZE);
	kfree(temp_arr);
}

static void init_default_profiles()
{
	kernel_cap_t full_cap = CAP_FULL_SET;

	default_root_profile.uid = 0;
	default_root_profile.gid = 0;
	default_root_profile.groups_count = 1;
	default_root_profile.groups[0] = 0;
	memcpy(&default_root_profile.capabilities.effective, &full_cap,
		sizeof(default_root_profile.capabilities.effective));
	default_root_profile.namespaces = 0;
	strcpy(default_root_profile.selinux_domain, KSU_DEFAULT_SELINUX_DOMAIN);

	// This means that we will umount modules by default!
	default_non_root_profile.umount_modules = true;
}

struct perm_data {
	struct list_head list;
	struct app_profile profile;
};

static struct list_head allow_list;

static uint8_t allow_list_bitmap[PAGE_SIZE] __read_mostly __aligned(PAGE_SIZE);
#define BITMAP_UID_MAX ((sizeof(allow_list_bitmap) * BITS_PER_BYTE) - 1)

#define KERNEL_SU_ALLOWLIST "/data/adb/ksu/.allowlist"

static struct work_struct ksu_save_work;
static struct work_struct ksu_load_work;

bool persistent_allow_list(void);

void ksu_show_allow_list(void)
{
	struct perm_data *p = NULL;
	struct list_head *pos = NULL;
	pr_info("ksu_show_allow_list\n");
	list_for_each (pos, &allow_list) {
		p = list_entry(pos, struct perm_data, list);
		pr_info("uid :%d, allow: %d\n", p->profile.current_uid,
			p->profile.allow_su);
	}
}

#ifdef CONFIG_KSU_DEBUG
static void ksu_grant_root_to_shell()
{
	struct app_profile profile = {
		.version = KSU_APP_PROFILE_VER,
		.allow_su = true,
		.current_uid = 2000,
	};
	strcpy(profile.key, "com.android.shell");
	strcpy(profile.rp_config.profile.selinux_domain, KSU_DEFAULT_SELINUX_DOMAIN);
	ksu_set_app_profile(&profile, false);
}
#endif

bool ksu_get_app_profile(struct app_profile *profile)
{
	struct perm_data *p = NULL;
	struct list_head *pos = NULL;
	bool found = false;

	list_for_each (pos, &allow_list) {
		p = list_entry(pos, struct perm_data, list);
		bool uid_match = profile->current_uid == p->profile.current_uid;
		if (uid_match) {
			// found it, override it with ours
			memcpy(profile, &p->profile, sizeof(*profile));
			found = true;
			goto exit;
		}
	}

exit:
	return found;
}

static inline bool forbid_system_uid(uid_t uid) {
	#define SHELL_UID 2000
	#define SYSTEM_UID 1000
	return uid < SHELL_UID && uid != SYSTEM_UID;
}

static bool profile_valid(struct app_profile *profile)
{
	if (!profile) {
		return false;
	}

	if (profile->version < KSU_APP_PROFILE_VER) {
		pr_info("Unsupported profile version: %d\n", profile->version);
		return false;
	}

	if (profile->allow_su) {
		if (profile->rp_config.profile.groups_count > KSU_MAX_GROUPS) {
			return false;
		}

		if (strlen(profile->rp_config.profile.selinux_domain) == 0) {
			return false;
		}
	}

	return true;
}

bool ksu_set_app_profile(struct app_profile *profile, bool persist)
{
	struct perm_data *p = NULL;
	struct list_head *pos = NULL;
	bool result = false;

	if (!profile_valid(profile)) {
		pr_err("Failed to set app profile: invalid profile!\n");
		return false;
	}

	list_for_each (pos, &allow_list) {
		p = list_entry(pos, struct perm_data, list);
		// both uid and package must match, otherwise it will break multiple package with different user id
		if (profile->current_uid == p->profile.current_uid &&
		    !strcmp(profile->key, p->profile.key)) {
			// found it, just override it all!
			memcpy(&p->profile, profile, sizeof(*profile));
			result = true;
			goto out;
		}
	}

	// not found, alloc a new node!
	p = (struct perm_data *)kmalloc(sizeof(struct perm_data), GFP_KERNEL);
	if (!p) {
		pr_err("ksu_set_app_profile alloc failed\n");
		return false;
	}

	memcpy(&p->profile, profile, sizeof(*profile));
	if (profile->allow_su) {
		pr_info("set root profile, key: %s, uid: %d, gid: %d, context: %s\n",
			profile->key, profile->current_uid,
			profile->rp_config.profile.gid,
			profile->rp_config.profile.selinux_domain);
	} else {
		pr_info("set app profile, key: %s, uid: %d, umount modules: %d\n",
			profile->key, profile->current_uid,
			profile->nrp_config.profile.umount_modules);
	}
	list_add_tail(&p->list, &allow_list);

out:
	if (profile->current_uid <= BITMAP_UID_MAX) {
		if (profile->allow_su)
			allow_list_bitmap[profile->current_uid / BITS_PER_BYTE] |= 1 << (profile->current_uid % BITS_PER_BYTE);
		else
			allow_list_bitmap[profile->current_uid / BITS_PER_BYTE] &= ~(1 << (profile->current_uid % BITS_PER_BYTE));
	} else {
		if (profile->allow_su) {
			/*
			 * 1024 apps with uid higher than BITMAP_UID_MAX
			 * registered to request superuser?
			 */
			if (allow_list_pointer >= ARRAY_SIZE(allow_list_arr)) {
				pr_err("too many apps registered\n");
				WARN_ON(1);
				return false;
			}
			allow_list_arr[allow_list_pointer++] = profile->current_uid;
		} else {
			remove_uid_from_arr(profile->current_uid);
		}
	}
	result = true;

	// check if the default profiles is changed, cache it to a single struct to accelerate access.
	if (unlikely(!strcmp(profile->key, "$"))) {
		// set default non root profile
		memcpy(&default_non_root_profile, &profile->nrp_config.profile,
		       sizeof(default_non_root_profile));
	}

	if (unlikely(!strcmp(profile->key, "#"))) {
		// set default root profile
		memcpy(&default_root_profile, &profile->rp_config.profile,
		       sizeof(default_root_profile));
	}

	if (persist)
		persistent_allow_list();

	return result;
}

bool __ksu_is_allow_uid(uid_t uid)
{
	int i;

	if (unlikely(uid == 0)) {
		// already root, but only allow our domain.
		return is_ksu_domain();
	}

	if (forbid_system_uid(uid)) {
		// do not bother going through the list if it's system
		return false;
	}

	if (likely(ksu_is_manager_uid_valid()) && unlikely(ksu_get_manager_uid() == uid)) {
		// manager is always allowed!
		return true;
	}

	if (likely(uid <= BITMAP_UID_MAX)) {
		return !!(allow_list_bitmap[uid / BITS_PER_BYTE] & (1 << (uid % BITS_PER_BYTE)));
	} else {
		for (i = 0; i < allow_list_pointer; i++) {
			if (allow_list_arr[i] == uid)
				return true;
		}
	}

	return false;
}

bool ksu_uid_should_umount(uid_t uid)
{
	struct app_profile profile = { .current_uid = uid };
	if (likely(ksu_is_manager_uid_valid()) && unlikely(ksu_get_manager_uid() == uid)) {
		// we should not umount on manager!
		return false;
	}
	bool found = ksu_get_app_profile(&profile);
	if (!found) {
		// no app profile found, it must be non root app
		return default_non_root_profile.umount_modules;
	}
	if (profile.allow_su) {
		// if found and it is granted to su, we shouldn't umount for it
		return false;
	} else {
		// found an app profile
		if (profile.nrp_config.use_default) {
			return default_non_root_profile.umount_modules;
		} else {
			return profile.nrp_config.profile.umount_modules;
		}
	}
}

struct root_profile *ksu_get_root_profile(uid_t uid)
{
	struct perm_data *p = NULL;
	struct list_head *pos = NULL;

	list_for_each (pos, &allow_list) {
		p = list_entry(pos, struct perm_data, list);
		if (uid == p->profile.current_uid && p->profile.allow_su) {
			if (!p->profile.rp_config.use_default) {
				return &p->profile.rp_config.profile;
			}
		}
	}

	// use default profile
	return &default_root_profile;
}

bool ksu_get_allow_list(int *array, int *length, bool allow)
{
	struct perm_data *p = NULL;
	struct list_head *pos = NULL;
	int i = 0;
	list_for_each (pos, &allow_list) {
		p = list_entry(pos, struct perm_data, list);
		// pr_info("get_allow_list uid: %d allow: %d\n", p->uid, p->allow);
		if (p->profile.allow_su == allow) {
			array[i++] = p->profile.current_uid;
		}
	}
	*length = i;

	return true;
}

#ifndef CONFIG_KSU_ALLOWLIST_IO_VIA_KSUD
void do_save_allow_list(struct work_struct *work)
{
	u32 magic = FILE_MAGIC;
	u32 version = FILE_FORMAT_VERSION;
	struct perm_data *p = NULL;
	struct list_head *pos = NULL;
	loff_t off = 0;

	struct file *fp =
		ksu_filp_open_compat(KERNEL_SU_ALLOWLIST, O_WRONLY | O_CREAT | O_TRUNC, 0644);
	if (IS_ERR(fp)) {
		pr_err("save_allow_list create file failed: %ld at jiffies=%lu\n",
		       PTR_ERR(fp), jiffies);
		return;
	}

	// store magic and version
	if (ksu_kernel_write_compat(fp, &magic, sizeof(magic), &off) !=
	    sizeof(magic)) {
		pr_err("save_allow_list write magic failed.\n");
		goto exit;
	}

	if (ksu_kernel_write_compat(fp, &version, sizeof(version), &off) !=
	    sizeof(version)) {
		pr_err("save_allow_list write version failed.\n");
		goto exit;
	}

	list_for_each (pos, &allow_list) {
		p = list_entry(pos, struct perm_data, list);
		pr_info("save allow list, name: %s uid :%d, allow: %d\n",
			p->profile.key, p->profile.current_uid,
			p->profile.allow_su);

		ksu_kernel_write_compat(fp, &p->profile, sizeof(p->profile),
					&off);
	}

exit:
	filp_close(fp, 0);
}

void do_load_allow_list(struct work_struct *work)
{
	loff_t off = 0;
	ssize_t ret = 0;
	struct file *fp = NULL;
	u32 magic;
	u32 version;

#ifdef CONFIG_KSU_DEBUG
	// always allow adb shell by default
	ksu_grant_root_to_shell();
#endif

	// load allowlist now!
	fp = ksu_filp_open_compat(KERNEL_SU_ALLOWLIST, O_RDONLY, 0);
	if (IS_ERR(fp)) {
		pr_err("load_allow_list open file failed: %ld at jiffies=%lu\n",
		       PTR_ERR(fp), jiffies);
		return;
	}

	// verify magic
	if (ksu_kernel_read_compat(fp, &magic, sizeof(magic), &off) !=
		    sizeof(magic) ||
	    magic != FILE_MAGIC) {
		pr_err("allowlist file invalid: %d!\n", magic);
		goto exit;
	}

	if (ksu_kernel_read_compat(fp, &version, sizeof(version), &off) !=
	    sizeof(version)) {
		pr_err("allowlist read version: %d failed\n", version);
		goto exit;
	}

	pr_info("allowlist version: %d\n", version);

	while (true) {
		struct app_profile profile;

		ret = ksu_kernel_read_compat(fp, &profile, sizeof(profile),
					     &off);

		if (ret <= 0) {
			pr_info("load_allow_list read err: %zd\n", ret);
			break;
		}

		pr_info("load_allow_uid, name: %s, uid: %d, allow: %d\n",
			profile.key, profile.current_uid, profile.allow_su);
		ksu_set_app_profile(&profile, false);
	}

exit:
	ksu_show_allow_list();
	filp_close(fp, 0);
}
#endif /* !CONFIG_KSU_ALLOWLIST_IO_VIA_KSUD */

/* Parse and validate the whole blob before touching the live list. A
 * truncated tail or a bad record leaves the previous (possibly empty)
 * allowlist in place, which is the secure state. */
static int allowlist_validate_blob(const void __user *buf, u32 len, u32 *count)
{
	u32 magic, version, i;

	if (len < ALLOWLIST_HEADER_SIZE)
		return -EINVAL;
	if (copy_from_user(&magic, buf, sizeof(magic)))
		return -EFAULT;
	if (copy_from_user(&version, (const char __user *)buf + sizeof(u32),
			   sizeof(version)))
		return -EFAULT;
	if (magic != FILE_MAGIC || version != FILE_FORMAT_VERSION) {
		pr_err("allowlist: bad magic/version (%#x/%u)\n", magic, version);
		return -EINVAL;
	}
	if ((len - ALLOWLIST_HEADER_SIZE) % sizeof(struct app_profile)) {
		pr_err("allowlist: truncated record\n");
		return -EINVAL;
	}
	i = (len - ALLOWLIST_HEADER_SIZE) / sizeof(struct app_profile);
	if (i > ALLOWLIST_MAX_RECORDS)
		return -EINVAL;

	for (*count = 0; *count < i; (*count)++) {
		struct app_profile profile;
		const void __user *rec = (const char __user *)buf +
			ALLOWLIST_HEADER_SIZE +
			(*count) * sizeof(profile);

		if (copy_from_user(&profile, rec, sizeof(profile)))
			return -EFAULT;
		if (!profile_valid(&profile))
			return -EINVAL;
		if (profile.current_uid < 0 ||
		    strnlen(profile.key, KSU_MAX_PACKAGE_NAME) >=
			    KSU_MAX_PACKAGE_NAME)
			return -EINVAL;
	}
	return 0;
}

static void allowlist_rebuild_indices(struct list_head *head)
{
	struct perm_data *p;
	int i;

	init_default_profiles();
	memset(allow_list_bitmap, 0, sizeof(allow_list_bitmap));
	for (i = 0; i < ARRAY_SIZE(allow_list_arr); i++)
		allow_list_arr[i] = -1;
	allow_list_pointer = 0;

	list_for_each_entry (p, head, list) {
		uid_t uid = p->profile.current_uid;

		if (!strcmp(p->profile.key, "$"))
			memcpy(&default_non_root_profile, &p->profile.nrp_config.profile,
			       sizeof(default_non_root_profile));
		if (!strcmp(p->profile.key, "#"))
			memcpy(&default_root_profile, &p->profile.rp_config.profile,
			       sizeof(default_root_profile));
		if (!p->profile.allow_su)
			continue;
		if (uid <= BITMAP_UID_MAX)
			allow_list_bitmap[uid / BITS_PER_BYTE] |=
				1 << (uid % BITS_PER_BYTE);
		else if (allow_list_pointer < ARRAY_SIZE(allow_list_arr))
			allow_list_arr[allow_list_pointer++] = uid;
	}
}

#ifdef CONFIG_KSU_ALLOWLIST_IO_VIA_KSUD
static u32 allowlist_blob_size_locked(void)
{
	struct perm_data *p;
	u32 count = 0;

	list_for_each_entry (p, &allow_list, list)
		count++;
	if (count > ALLOWLIST_MAX_RECORDS)
		count = ALLOWLIST_MAX_RECORDS;
	return ALLOWLIST_HEADER_SIZE + count * sizeof(struct app_profile);
}

u32 ksu_allowlist_blob_size(void)
{
	u32 size;

	mutex_lock(&allowlist_mutex);
	size = allowlist_blob_size_locked();
	mutex_unlock(&allowlist_mutex);
	return size;
}

int ksu_allowlist_blob_read(void __user *buf, u32 len)
{
	u32 magic = FILE_MAGIC, version = FILE_FORMAT_VERSION, off;
	struct perm_data *p;
	int ret = 0;

	mutex_lock(&allowlist_mutex);
	if (len < allowlist_blob_size_locked()) {
		mutex_unlock(&allowlist_mutex);
		return -ENOSPC;
	}
	if (copy_to_user(buf, &magic, sizeof(magic)) ||
	    copy_to_user((char __user *)buf + sizeof(u32), &version,
			 sizeof(version))) {
		ret = -EFAULT;
		goto out;
	}
	off = ALLOWLIST_HEADER_SIZE;
	list_for_each_entry (p, &allow_list, list) {
		if (copy_to_user((char __user *)buf + off, &p->profile,
				 sizeof(p->profile))) {
			ret = -EFAULT;
			break;
		}
		off += sizeof(p->profile);
	}
out:
	mutex_unlock(&allowlist_mutex);
	return ret;
}

int ksu_allowlist_blob_write(const void __user *buf, u32 len)
{
	struct perm_data *p, *n;
	LIST_HEAD(new_list);
	LIST_HEAD(old_list);
	u32 count, i;
	int ret;

	ret = allowlist_validate_blob(buf, len, &count);
	if (ret) {
		pr_err("allowlist: rejected blob (%d), keeping current list\n", ret);
		return ret;
	}

	for (i = 0; i < count; i++) {
		p = kmalloc(sizeof(*p), GFP_KERNEL);
		if (!p) {
			ret = -ENOMEM;
			goto free_new;
		}
		if (copy_from_user(&p->profile,
				   (const char __user *)buf + ALLOWLIST_HEADER_SIZE +
					   i * sizeof(p->profile),
				   sizeof(p->profile))) {
			kfree(p);
			ret = -EFAULT;
			goto free_new;
		}
		list_add_tail(&p->list, &new_list);
	}

	mutex_lock(&allowlist_mutex);
	list_replace_init(&allow_list, &old_list);
	list_replace_init(&new_list, &allow_list);
	allowlist_rebuild_indices(&allow_list);
	WRITE_ONCE(allowlist_save_pending, false);
	mutex_unlock(&allowlist_mutex);

	list_for_each_entry_safe (p, n, &old_list, list) {
		list_del(&p->list);
		kfree(p);
	}
	pr_info("allowlist: applied %u validated records at jiffies=%lu\n",
		count, jiffies);
	return 0;

free_new:
	list_for_each_entry_safe (p, n, &new_list, list) {
		list_del(&p->list);
		kfree(p);
	}
	return ret;
}

bool ksu_allowlist_save_pending(void)
{
	return READ_ONCE(allowlist_save_pending);
}

int ksu_allowlist_probe_open(void)
{
	struct path data_path;
	struct file *fp;
	int data_err, ret = 0;

	data_err = kern_path("/data", 0, &data_path);
	if (!data_err)
		path_put(&data_path);
	fp = ksu_filp_open_compat(KERNEL_SU_ALLOWLIST, O_RDONLY, 0);
	if (IS_ERR(fp))
		ret = PTR_ERR(fp);
	else
		filp_close(fp, 0);
	pr_info("allowlist probe: jiffies=%lu pid=%d comm=%s data=%d open=%d wq=%d\n",
		jiffies, current->pid, current->comm, data_err, ret,
		!!(current->flags & PF_WQ_WORKER));
	return ret;
}
#endif /* CONFIG_KSU_ALLOWLIST_IO_VIA_KSUD */

void ksu_prune_allowlist(bool (*is_uid_valid)(uid_t, char *, void *), void *data)
{
	struct perm_data *np = NULL;
	struct perm_data *n = NULL;

	bool modified = false;
	// TODO: use RCU!
	mutex_lock(&allowlist_mutex);
	list_for_each_entry_safe (np, n, &allow_list, list) {
		uid_t uid = np->profile.current_uid;
		char *package = np->profile.key;
		// we use this uid for special cases, don't prune it!
		bool is_preserved_uid = uid == KSU_APP_PROFILE_PRESERVE_UID;
		if (!is_preserved_uid && !is_uid_valid(uid, package, data)) {
			modified = true;
			pr_info("prune uid: %d, package: %s\n", uid, package);
			list_del(&np->list);
			if (likely(uid <= BITMAP_UID_MAX)) {
				allow_list_bitmap[uid / BITS_PER_BYTE] &= ~(1 << (uid % BITS_PER_BYTE));
			}
			remove_uid_from_arr(uid);
			smp_mb();
			kfree(np);
		}
	}
	mutex_unlock(&allowlist_mutex);

	if (modified) {
		persistent_allow_list();
	}
}

// make sure allow list works cross boot
bool persistent_allow_list(void)
{
#ifdef CONFIG_KSU_ALLOWLIST_IO_VIA_KSUD
	/* The manager root service has a valid keyring; the kernel workqueue
	 * does not. ksud writes the blob instead of the kernel workqueue. */
	WRITE_ONCE(allowlist_save_pending, true);
	return true;
#else
	return ksu_queue_work(&ksu_save_work);
#endif
}

bool ksu_load_allow_list(void)
{
#ifdef CONFIG_KSU_ALLOWLIST_IO_VIA_KSUD
	/* ksud reads /data/adb/ksu/.allowlist and pushes it through
	 * CMD_ALLOWLIST_IO. Replaying a failed load never re-runs rc hooks. */
	pr_info("allowlist load delegated to ksud at jiffies=%lu\n", jiffies);
	return true;
#else
	return ksu_queue_work(&ksu_load_work);
#endif
}

void ksu_allowlist_init(void)
{
	int i;

#ifdef CONFIG_KSU_ALLOWLIST_IO_VIA_KSUD
	BUILD_BUG_ON(sizeof(struct app_profile) != 776);
#endif
	BUILD_BUG_ON(sizeof(allow_list_bitmap) != PAGE_SIZE);
	BUILD_BUG_ON(sizeof(allow_list_arr) != PAGE_SIZE);

	for (i = 0; i < ARRAY_SIZE(allow_list_arr); i++)
		allow_list_arr[i] = -1;

	INIT_LIST_HEAD(&allow_list);

#ifndef CONFIG_KSU_ALLOWLIST_IO_VIA_KSUD
	INIT_WORK(&ksu_save_work, do_save_allow_list);
	INIT_WORK(&ksu_load_work, do_load_allow_list);
#endif

	init_default_profiles();
}

void ksu_allowlist_exit(void)
{
	struct perm_data *np = NULL;
	struct perm_data *n = NULL;

#ifndef CONFIG_KSU_ALLOWLIST_IO_VIA_KSUD
	do_save_allow_list(NULL);
#endif

	// free allowlist
	mutex_lock(&allowlist_mutex);
	list_for_each_entry_safe (np, n, &allow_list, list) {
		list_del(&np->list);
		kfree(np);
	}
	mutex_unlock(&allowlist_mutex);
}
