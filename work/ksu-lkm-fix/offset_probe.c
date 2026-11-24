#include <linux/stddef.h>
#include <linux/sched.h>
char probe_cred[offsetof(struct task_struct, cred)];
char probe_nsproxy[offsetof(struct task_struct, nsproxy)];
char probe_fs[offsetof(struct task_struct, fs)];
char probe_session[offsetof(struct cred, session_keyring)];
char probe_user[offsetof(struct cred, user)];
char probe_user_session[offsetof(struct user_struct, session_keyring)];
