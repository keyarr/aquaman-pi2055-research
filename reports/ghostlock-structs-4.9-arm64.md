# GhostLock structs 4.9.113 ARM64 (Fase 3)

Fonte: /tmp/kernel-src/linux-amlogic (headers + .c). Offsets numericos
marcados INFERIDO: calculados pela ordem dos campos no source para
LP64, sem vmlinux/DWARF do aquaman para confirmar. Nao usar em exploit
sem validacao por runtime read ou pahole num vmlinux compativel.
Layouts marcados CONFIRMADO valem para a arvore analisada.

## struct rt_mutex_waiter — CONFIRMADO (rtmutex_common.h:25-37)

Sem CONFIG_DEBUG_RT_MUTEXES (unset no aquaman-config), o layout eh:

    0x00  struct rb_node tree_entry      (24B no LP64)
    0x18  struct rb_node pi_tree_entry   (24B)
    0x30  struct task_struct *task       (8B)
    0x38  struct rt_mutex *lock          (8B)
    0x40  int prio                       (4B + 4 pad)
    0x48  u64 deadline                   (8B)
    tamanho 0x50

Igual ao que o port aresin documenta para 4.14 ARM64. 4.9 e 4.14 usam
rb_node aqui (plist_node so aparece em futex_q). Hazel ARM32 difere
apenas pelo tamanho dos ponteiros (task em 0x18 no ARM32).

## struct futex_q — CONFIRMADO (futex.c:237-247)

    struct plist_node list; struct task_struct *task; spinlock_t *lock_ptr;
    union futex_key key; struct futex_pi_state *pi_state;
    struct rt_mutex_waiter *rt_waiter; union futex_key *requeue_pi_key;
    u32 bitset;

Relevante: q.rt_waiter aponta para o rt_waiter na stack do waiter
(futex_wait_requeue_pi). Eh o objeto que vira dangling.

## struct task_struct — campos usados, ordem CONFIRMADA (sched.h)

Posicoes relativas no source, nao offsets numericos:

- tasks (list_head) ............ sched.h:1703
- real_cred / cred (__rcu ptr) .. :1828/:1830, adjacentes
- comm[TASK_COMM_LEN=16] ........ :1832, logo apos cred
- pi_lock (raw_spinlock_t) ...... :1882
- pi_waiters (rb_root) .......... :1888
- pi_waiters_leftmost ........... :1889
- pi_blocked_on ................. :1891, logo apos pi_waiters_leftmost

Padrao util para validacao runtime (igual ao hazel faz): ler comm de
init_task ("swapper"), depois next/prev da task list. Referencia ARM64:
aresin mediu num 4.14 MTK real_cred=0x788 cred=0x790, pi_lock=0x85c,
pi_waiters=0x868, pi_blocked_on=0x880. Para 4.9 Amlogic os numeros VAO
DIFERIR — o task_struct 4.9 nao tem uclamp/cgroup v2/rseq e o config
vendor muda o tamanho. Nao copiar 0x788/0x790.

## struct cred — CONFIRMADO (cred.h)

Sem CONFIG_DEBUG_CREDENTIALS (checar no config antes de usar):

    usage(4) | uid(4) gid(4) suid(4) sgid(4) euid(4) egid(4) fsuid(4)
    fsgid(4) | securebits(4) | cap_inheritable(8) cap_permitted(8)
    cap_effective(8) cap_bset(8) cap_ambient(8) | ...

Hazel zera cred+0x04 por 0x20 (8 ids + securebits) — mesma aritmetica
vale no ARM64 se DEBUG_CREDENTIALS unset (uid em +4). Confirmar o unset
no aquaman-config antes de qualquer uso.

## struct configfs_buffer — CONFIRMADO (fs/configfs/file.c:45-56)

    count(8) pos(8) page(8) ops(8) mutex(0x18) needs_read_fill(4) ...

Hazel forja mutex em +0x18 (count=1 = unlocked) e page em +0x10.
No LP64 o mutex continua em +0x20? NAO: count 8 + pos 8 + page 8 +
ops 8 = mutex em +0x20 no ARM64, nao +0x18. Diferenca concreta ARM32->ARM64
que impede transplantar o blob do hazel. INCOMPATIVEL direto, precisa
recalcular (detalhe em ghostlock-port-comparison.md).

## struct ashmem_area — CONFIRMADO (ashmem.c:54-60)

    name[ASHMEM_FULL_NAME_LEN] + list_head(16) + file(8) + size(8) + prot(8)

ASHMEM_FULL_NAME_LEN difere por versao; ler ashmem.h da arvore antes de
assumir o prefixo "/dev/ashmem/". O truque do hazel (primeira word do
area como count gigante) depende desse prefixo literal — verificar.

## struct file / file_operations — padrao 4.9, sem surpresa

f_op em file+? , read/write em fops+? : extrair por pahole quando houver
vmlinux. Nao adivinhar.

## struct mm_struct — tamanho vendor-dependente

Hazel usa MM_OBJ_SIZE=0x1c0 (ARM32, config FireOS). No ARM64 4.9 com
MMU o mm_struct eh maior (rb_root + vmacache + mais campos 64-bit).
O grid 0x1c0 NAO se aplica. Tamanho real sai de pahole ou do leak
runtime (leaked_mm & mascara). Marcar como primeira diferenca de heap.

## Como fechar os offsets (ordem)

1. pahole num vmlinux 4.9.113 ARM64 compativel (dangal build local com
   aquaman-config aproximado);
2. validacao por runtime read apos kernel R/W (ancoras comm + task list);
3. nunca por copia de outro device.
