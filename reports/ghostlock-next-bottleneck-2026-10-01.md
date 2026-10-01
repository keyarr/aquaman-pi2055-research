# ghostlock next bottleneck — disclosure check (2026-10-01)

Date: 2026-10-01. Question: existe disclosure no stock que entregue
`W_waiter` vivo + `[W_waiter+0x38]` atual + `&f_alt.pi_mutex` no mesmo
contexto do consumer? Resposta: nao na superficie auditada.

## Environment split

HOST/VM Linux (OFFLINE_ONLY, nunca evidencia de comportamento):

* grep / objdump / readelf / DWARF sobre `build-aq/vmlinux`
* `.src/linux-amlogic` (futex.c, rtmutex.c, sched, proc, net, binder, ashmem, ion)
* `tools/ghostlock_disclosure.py`, `ghostlock_emit_search.py`,
  `ghostlock_deref_chain.py`, `ghostlock_h16_target_search.py`
* parsing de logs em `out/logs/`, compilacao NDK estatica
* tudo abaixo marcado OFFLINE_ONLY e nada contado como hardware

DEVICE REAL (unico que conta para kernel behavior):

```text
DEVICE_BOOT_ID: 3ec336a5-439f-497f-b9f7-08fd7441b174
ADB_TARGET: 26919800005844922 (MiTV-AESP0 / aquaman)
KERNEL_VERSION: 4.9.113 #1 SMP PREEMPT 2022-09-06 armv8l
FINGERPRINT: Xiaomi/aquaman/aquaman:9/PI/2055:user/release-keys
SELINUX: Enforcing, shell u:r:shell:s0 uid 2000
```

Regra aplicada: sem BOOT_ID nao e hardware evidence. Sem run no
device e OFFLINE_ONLY. Nenhum resultado de VM escrito como reproduzido.

## Current state

Fechado anterior, preservado sem reabrir:

```text
RESULT: NO_EXACT_WRITER_FOUND
EXACT_WRITER: NOT_FOUND
EXACT_VALUE: NOT_FOUND
DURABLE_ACROSS_H16: UNPROVEN
REBOOTS: 0
TESTS: 126 OK
```

Matriz (mesmo boot 3ec336a5, historico recitado):

```text
base_t       TIMEOUT
occ_base     TIMEOUT
trg_inwin    TIMEOUT
occ_tgt      EDEADLK
alt_only     TIMEOUT
alt_tgt      EDEADLK
h16_static   TIMEOUT + TIMEOUT
```

Leitura: consumer segue `f_target` desde o nascimento.
`f_alt` so aparece quando configurado desde o nascimento
(`alt_base` TIMEOUT prova mutex valido e contendido, nao endereco).
`alt_only` vs `alt_tgt` prova fidelidade do consumer LEVEL_2,
nao escrita. `waiter->lock = lock` (rtmutex.c:998, H16.0
`stp x20,x19,[x21,#0x30]`) e o unico writer legitimo.
Nenhum writer grava `[W_waiter+0x38] = &f_alt.pi_mutex`.
H16.4 (`0x52fc ldr x25,[x0,#0x38]`) e H16.7
(`0x4df0 ldr x0,[x28,#0x38]` + `cmp @0x4df4`) sem mecanismo
demonstrado de escrita. LEVEL_2 mantido, LEVEL_3 nem tentado.

## Closed paths

Nao reabertos nesta rodada, citados com motivo:

* H16 writer depth<=3: 33 EXACT (9 KPTR heavy/priv/transient, 2 INT,
  1 DERIVED, 21 UNKNOWN spills), atomics 0, ioctl 0 exact,
  poll table/current GEOMETRY_ONLY valor errado (task/code/small-int),
  PI `+0x10` LEA register-only zero spills. Veredito: NOT_FOUND.
* reclaim / MSG_PEEK / buddyinfo / slab guessing: `mm_reclaim_probe`
  A/B/control FAIL `reclaim_hits=0`, plumbing 512/512 PASS nos 3 modos.
  PEEK e plumbing, nao reuse. buddyinfo errno=13, slabinfo ausente,
  slab attrs 0400. BLOCKED / REFUTED como prova.
* Mali: GET/QUERY read-only HARDWARE_REFUTED para disclosure;
  stateful 34 handlers BOUNDED_COPY+VALIDATED ou SCALAR/NO_EMIT,
  open/close e get/put balanceados. Zero OOB/UAF/KPTR provado.
  Blind ioctl sem source proibido, nao executado.
* geometry-only / stack coincidence / poll-select sem writer:
  `dist=0` prova reuso de pagina/SP, nao endereco absoluto nem valor
  rt_mutex. Nunca promovido a retarget.
* fake waiter / cred / R/W / root: fora de escopo ate H16 mover.
  Nao tentados, nao reivindicados.
* kallsyms / `%pK` / dmesg / debugfs / tracing / sys tunables:
  masked ou Permission denied para shell (ver Device experiments).
* ashmem/configfs: precisa fake fops + dentry tolerante; sem leak
  demonstrado, nao e disclosure.
* ge2d / vfm / ionvideo / amvideo / vndbinder / cec:
  shell-unreachable (errno=13) ou DISABLED (-EIO). INDEX/fd apenas.

## Disclosure candidates

Formato exigido: TARGET / VALUE / ENVIRONMENT / STATUS.
Runs-on-VM = analise estatica. Runs-on-DEVICE = probe real neste boot
ou historico com BOOT_ID. Todo resto OFFLINE_ONLY.

```text
candidate: S1 /proc/pid/stack
source: base.c:472 [%pK] %pB
runs on VM?: yes (format)
runs on DEVICE?: yes (T1 this boot)
target value: W_waiter stack address
status: MASKED zeros, NOT_FOUND

candidate: S2 /proc/pid/wchan
source: base.c:411 symbol-or-0
runs on VM?: yes
runs on DEVICE?: yes (T2)
target value: waiter/stack symbol
status: SYMBOL_ONLY "0", NOT_FOUND

candidate: S3 /proc/pid/syscall
source: base.c:642 user nr+args+sp/pc
runs on VM?: yes
runs on DEVICE?: yes (T3)
target value: kernel SP
status: USER_REGS_ONLY, NOT_FOUND

candidate: S4 stat kstkesp/kstkeip + S5 start_stack
source: array.c:436 PF_DUMPCORE-gated
runs on VM?: yes
runs on DEVICE?: yes (T4)
target value: kernel stack pointer
status: ZEROED 0 0 / USER stack, NOT_FOUND

candidate: S6 net sk + S15 diag + binder handles
source: unix/tcp/packet seq, diag.c ino/dev/qlen
runs on VM?: yes
runs on DEVICE?: yes (history emit_dev)
target value: any kptr
status: MASKED 0 / INDEX_ONLY, NOT_FOUND

candidate: S9 kallsyms + S10 dmesg/kmsg/pstore + S11-S13 slab/debugfs/sys
source: %pK kptr_restrict, dmesg_restrict, SELinux
runs on VM?: yes (config KALLSYMS=y mas gated)
runs on DEVICE?: yes (T5-T7 this boot)
target value: slide / symbol / slab addr
status: PERMISSION_DENIED, NOT_FOUND

candidate: C1 binder VERSION + NODE_DEBUG + WRITE_READ
source: binder.c ptr/cookie USER echo
runs on VM?: yes (dispatch audit)
runs on DEVICE?: yes (T9: proto 8, ptr 0 cookie 0)
target value: heap ptr via node
status: USER_ECHO_ZEROS is_kptr=0, NOT_FOUND

candidate: C2 ashmem SIZE + GET_NAME
source: ashmem.c:575 USER string
runs on VM?: yes (magic 0x77 corrigido via source)
runs on DEVICE?: yes (T9: size 0, name dev/ashmem)
target value: heap ptr
status: SCALAR + USER_STRING, NOT_FOUND

candidate: C3 ion HEAP_QUERY
source: ion.c:1221 name/type/id
runs on VM?: yes
runs on DEVICE?: yes (T9: cnt 3, ids 5/4/0)
target value: heap VA via heap id
status: INDEX + SCALAR is_kptr=0, NOT_FOUND

candidate: PI futex.c + rtmutex.c copy_to_user
source: grep 0 hits ambos
runs on VM?: yes
runs on DEVICE?: yes (emit_pi fstat index-only)
target value: pi_state / pi_mutex / waiter*
status: NO_POINTER, NOT_FOUND

candidate: robust/sched/signal/socket/ifconf
source: futex.c:3055 USER echo, UAPI scalars, si_ptr sender
runs on VM?: yes
runs on DEVICE?: yes (history disclose_stack probe)
target value: waiter* shortcut / kernel SP
status: USER_ECHO / SCALAR_ONLY, NOT_FOUND

candidate: pi_state+0x10 LEA carrier
source: attach 0x9614, requeue 0xabe4, lock_pi 0xb1b8/0xb238/0xb2a0
runs on VM?: yes (forward-spill zero KPTR spills)
runs on DEVICE?: no (register-only, sem slot para ler)
target value: &f_alt.pi_mutex via reg
status: REGISTER_ONLY OFFLINE_ONLY, NOT_FOUND como leak

candidate: mali ioctls beyond open + vendor f_op depth>3 + unaudited /dev
source: mali.ko out-of-tree, amlogic KOs unreachable
runs on VM?: partial (census 34 stateful OFFLINE_ONLY-negativo)
runs on DEVICE?: no (open census apenas; blind ioctl proibido)
target value: any kptr
status: UNKNOWN / NOT_COVERED, nao e candidato, e lacuna explicita

candidate: pagemap PFN / maps / smaps
source: USER VMAs, PFN precisa priv
runs on VM?: yes
runs on DEVICE?: partial (hexdump ausente no stock; maps = USER)
target value: kernel VA via PFN
status: PFN 0 / USER_ONLY, NOT_FOUND
```

Nenhuma linha acima entrega os 3 itens juntos no mesmo contexto
do consumer. Occupancy verdict (`alt_base` TIMEOUT) identifica o
objeto semanticamente e e mantido como SINGLE_SOURCE-adjacent
identity rule, deliberadamente NAO chamado de disclosure.

## Device experiments

Somente o que rodou no aparelho nesta rodada. Mesmo boot em todas.

```text
DEVICE_BOOT_ID: 3ec336a5-439f-497f-b9f7-08fd7441b174
ADB_TARGET: 26919800005844922
KERNEL_VERSION: 4.9.113 (jenkins@c5-mitv-cm-build06.bj 2022-09-06)
```

T1 STACK:

```text
COMMAND_EXECUTED_ON_DEVICE: adb -s 26919800005844922 shell 'cat /proc/self/stack'
RESULT: 9 linhas [<0000000000000000>] walk_stackframe/proc_pid_stack/seq_read/SyS_read/el0_svc_naked. Zero kptr. MASKED.
STATIC_ANALYSIS: base.c:472 %pK gating prediz zeros. DEVICE_TEST confirma. CONCLUSION: STACK_DISCLOSURE ausente aqui.
```

T2 WCHAN:

```text
COMMAND_EXECUTED_ON_DEVICE: adb -s 26919800005844922 shell 'cat /proc/self/wchan'
RESULT: "0". Sem simbolo, sem endereco.
STATIC_ANALYSIS: base.c:411 symbol-or-0. DEVICE_TEST confirma. CONCLUSION: nao e disclosure.
```

T3 SYSCALL:

```text
COMMAND_EXECUTED_ON_DEVICE: adb -s 26919800005844922 shell 'cat /proc/self/syscall'
RESULT: "3 0x3 0xb87cdc80 ..." user regs apenas.
STATIC_ANALYSIS: base.c:642 user sp/pc. DEVICE_TEST confirma. CONCLUSION: USER_ONLY.
```

T4 STAT:

```text
COMMAND_EXECUTED_ON_DEVICE: adb -s 26919800005844922 shell 'cat /proc/self/stat'
RESULT: campos 29/30 = 0 0 (kstkesp/kstkeip zerados).
STATIC_ANALYSIS: array.c:436 PF_DUMPCORE gate. DEVICE_TEST confirma. CONCLUSION: nao e disclosure.
```

T5-T7 DENIALS:

```text
COMMAND_EXECUTED_ON_DEVICE: cat /proc/kallsyms; ls /sys/kernel/slab/; ls /sys/kernel/debug/
RESULT: Permission denied / Permission denied / Permission denied (slab lista parcial sem attrs uteis).
STATIC_ANALYSIS: kptr_restrict + SELinux + DEBUG_FS gated. DEVICE_TEST confirma. CONCLUSION: unreachable para shell.
```

T9 EMIT C1/C2/C3 (re-run do binario ja presente, sem push novo):

```text
COMMAND_EXECUTED_ON_DEVICE: adb -s 26919800005844922 shell '/data/local/tmp/ghostlock_emit_probe all'
RESULT: C1 proto=8 ptr=0 cookie=0; C2 size=0 name="dev/ashmem"; C3 cnt=3 ids 5/4/0 rc=-EINVAL quirk com buffer cheio; is_kptr=0 em tudo. Identico ao historico 3x.
STATIC_ANALYSIS: binder USER echo, ashmem USER string, ion INDEX. DEVICE_TEST confirma classes. CONCLUSION: scalar/echo/index, nenhum kptr.
```

T10 LIVENESS:

```text
COMMAND_EXECUTED_ON_DEVICE: adb -s 26919800005844922 shell 'cat /proc/uptime; cat /proc/sys/kernel/random/boot_id'
RESULT: up 30255s, mesmo BOOT_ID 3ec336a5. Sem reboot/hang/panic em nenhum probe. Side effects: open+close de fds proprios + reads /proc apenas.
```

Historico recitado, nao re-executado aqui (mesmo BOOT_ID, logs em
`out/logs/`): `disclose_stack`/`disclose_heap` (zeros + robust USER
echo + sched scalar + sockaddr bytes), `emit_dev` open census
(262 nos, 6 shell-openable), `h16_static` TIMEOUT+TIMEOUT,
`alt_only` TIMEOUT / `alt_tgt` EDEADLK. Citados como HISTORY, nao
como prova nova desta rodada.

Nada nesta secao veio da VM. Nenhum numero de VM chamado de reproduzido.

## Verdict

```text
NO_DISCLOSURE_PATH_FOUND
```

Escopo: superficie auditada (proc/sys/net/futex/sched/signal/
socket/binder-sample/ge2d-vfm-sample/C1-C3). Ausencia aqui nao e
ausencia em todo kernel; lacunas explicitas (mali blind, f_op alem
de depth 3, /dev alem de C1-C3 com source) ficam INCONCLUSIVE,
nao promovidas a candidatas. Nenhum primitive nomeado. H16 segue
fechada como `NO_EXACT_WRITER_FOUND`.

## Next bottleneck

Um so: disclosure read-only de EITHER endereco com ruler duplo
antes de qualquer stamper. Fechar exige `/dev` emit census alem de
C1/C2/C3 so com source auditavel (mali precisa de source primeiro,
sem campanha blind), depois re-walk de f_op/indirect alem de BFS
depth 3 so para EMIT, e ao primeiro endereco rodar FASE 12
(`--disclosure`: H16 == x28 base em H16.7 com igualdade de valor
em H16.4) + FASE 13 (`--emit`: FIELD+LOAD+COPY+USER+MASK) antes de
qualquer pensamento de write. Sem isso: sem stamper, sem fake,
sem cred/RW/root, sem repetir o window depth<=3.
