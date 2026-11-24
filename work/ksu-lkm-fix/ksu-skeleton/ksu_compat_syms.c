#include <linux/init.h>
#include <linux/kallsyms.h>
#include <linux/module.h>
#include <linux/printk.h>
#include <linux/string.h>

#include "kernel_compat.h"
#include "ksu_compat_syms.h"
#include "klog.h" // IWYU pragma: keep

int (*ksu_avc_ss_reset)(u32 seqno);
int (*ksu_ebitmap_set_bit)(struct ebitmap *e, unsigned long bit, int value);
int (*ksu_ebitmap_get_bit)(struct ebitmap *e, unsigned long bit);
void *(*ksu_hashtab_search)(struct hashtab *h, const void *key);
int (*ksu_hashtab_insert)(struct hashtab *h, void *key, void *data);
struct avtab_node *(*ksu_avtab_insert_nonunique)(struct avtab *h,
						 struct avtab_key *key,
						 void *data);
struct avtab_node *(*ksu_avtab_search_node)(struct avtab *h,
					    struct avtab_key *key);
struct avtab_node *(*ksu_avtab_search_node_next)(struct avtab_node *node,
						 int specified);
void (*ksu_selnl_notify_policyload)(u32 seqno);
void (*ksu_selinux_status_update_policyload)(int seqno);
int *ksu_selinux_enforcing_ptr;
struct policydb *ksu_policydb_ptr;
struct nsproxy *ksu_init_nsproxy_ptr;
void (*ksu_ext4_unregister_sysfs)(struct super_block *sb);
int (*ksu_install_session_keyring_to_cred)(struct cred *cred,
					   struct key *keyring);
int (*ksu_install_user_keyrings)(void);

#define KSU_RESOLVE(ptr, name)                                             \
	do {                                                               \
		(ptr) = (typeof(ptr))kallsyms_lookup_name(name);            \
		if (!(ptr)) {                                              \
			pr_err("ksu_compat: %s not found\n", name);        \
			return -ENOENT;                                    \
		}                                                          \
	} while (0)

int ksu_compat_syms_init(void)
{
	KSU_RESOLVE(ksu_avc_ss_reset, "avc_ss_reset");
	KSU_RESOLVE(ksu_ebitmap_set_bit, "ebitmap_set_bit");
	KSU_RESOLVE(ksu_ebitmap_get_bit, "ebitmap_get_bit");
	KSU_RESOLVE(ksu_hashtab_search, "hashtab_search");
	KSU_RESOLVE(ksu_hashtab_insert, "hashtab_insert");
	KSU_RESOLVE(ksu_avtab_insert_nonunique, "avtab_insert_nonunique");
	KSU_RESOLVE(ksu_avtab_search_node, "avtab_search_node");
	KSU_RESOLVE(ksu_avtab_search_node_next, "avtab_search_node_next");
	KSU_RESOLVE(ksu_selnl_notify_policyload, "selnl_notify_policyload");
	KSU_RESOLVE(ksu_selinux_status_update_policyload,
		    "selinux_status_update_policyload");
	KSU_RESOLVE(ksu_selinux_enforcing_ptr, "selinux_enforcing");
	KSU_RESOLVE(ksu_policydb_ptr, "policydb");
	KSU_RESOLVE(ksu_init_nsproxy_ptr, "init_nsproxy");
	KSU_RESOLVE(ksu_ext4_unregister_sysfs, "ext4_unregister_sysfs");
	KSU_RESOLVE(ksu_install_session_keyring_to_cred,
		    "install_session_keyring_to_cred");
	KSU_RESOLVE(ksu_install_user_keyrings, "install_user_keyrings");

	/* Old kernels kept this global; this 4.9 build does not, so a missing
	 * symbol is expected. kernel_compat.c falls back to init's cred and
	 * the uid session keyring. */
	init_session_keyring =
		(struct key *)kallsyms_lookup_name("init_session_keyring");
	if (!init_session_keyring) {
		pr_warn("ksu_compat: init_session_keyring not found\n");
	}

	return 0;
}
