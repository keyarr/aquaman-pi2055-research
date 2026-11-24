#ifndef __KSU_H_ALLOWLIST
#define __KSU_H_ALLOWLIST

#include <linux/compiler.h>
#include <linux/types.h>
#include "ksu.h"

void ksu_allowlist_init(void);

void ksu_allowlist_exit(void);

bool ksu_load_allow_list(void);

#ifdef CONFIG_KSU_ALLOWLIST_IO_VIA_KSUD
u32 ksu_allowlist_blob_size(void);
int ksu_allowlist_blob_read(void __user *buf, u32 len);
int ksu_allowlist_blob_write(const void __user *buf, u32 len);
bool ksu_allowlist_save_pending(void);
int ksu_allowlist_probe_open(void);
#endif

void ksu_show_allow_list(void);

bool __ksu_is_allow_uid(uid_t uid);
#define ksu_is_allow_uid(uid) unlikely(__ksu_is_allow_uid(uid))

bool ksu_get_allow_list(int *array, int *length, bool allow);

void ksu_prune_allowlist(bool (*is_uid_exist)(uid_t, char *, void *), void *data);

bool ksu_get_app_profile(struct app_profile *);
bool ksu_set_app_profile(struct app_profile *, bool persist);

bool ksu_uid_should_umount(uid_t uid);
struct root_profile *ksu_get_root_profile(uid_t uid);
#endif
