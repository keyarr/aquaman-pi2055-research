#ifndef __KSU_COMPAT_SYMS_H
#define __KSU_COMPAT_SYMS_H

#include <linux/types.h>

/* Forward declarations: these helpers are resolved from kallsyms at init. */
struct cred;
struct key;
struct nsproxy;
struct policydb;
struct hashtab;
struct avtab;
struct avtab_key;
struct avtab_node;
struct ebitmap;
struct super_block;

extern int (*ksu_avc_ss_reset)(u32 seqno);
extern int (*ksu_ebitmap_set_bit)(struct ebitmap *e, unsigned long bit, int value);
extern int (*ksu_ebitmap_get_bit)(struct ebitmap *e, unsigned long bit);
extern void *(*ksu_hashtab_search)(struct hashtab *h, const void *key);
extern int (*ksu_hashtab_insert)(struct hashtab *h, void *key, void *data);
extern struct avtab_node *(*ksu_avtab_insert_nonunique)(struct avtab *h,
							struct avtab_key *key,
							void *data);
extern struct avtab_node *(*ksu_avtab_search_node)(struct avtab *h,
						   struct avtab_key *key);
extern struct avtab_node *(*ksu_avtab_search_node_next)(struct avtab_node *node,
							int specified);
extern void (*ksu_selnl_notify_policyload)(u32 seqno);
extern void (*ksu_selinux_status_update_policyload)(int seqno);
extern int *ksu_selinux_enforcing_ptr;
extern struct policydb *ksu_policydb_ptr;
extern struct nsproxy *ksu_init_nsproxy_ptr;
extern void (*ksu_ext4_unregister_sysfs)(struct super_block *sb);
extern int (*ksu_install_session_keyring_to_cred)(struct cred *cred,
						   struct key *keyring);
extern int (*ksu_install_user_keyrings)(void);

int ksu_compat_syms_init(void);

#endif
