# GhostLock port comparison (Fase 4 + Fase 5)

Matriz: Hazel 4.9 ARM32 (dorlow, hw-tested PS7716) x Aresin 4.14 ARM64
(NothingFumo, em progresso, offsets TODO) x Aquaman 4.9 ARM64 (alvo).

Legenda: igual / mudou / nao-existe / precisa-adaptacao.

## Trigger futex

- Hazel: waiter LOCK_PI(chain) + WAIT_REQUEUE_PI(wait->target chain),
  owner LOCK_PI(target)+LOCK_PI(chain), main CMP_REQUEUE_PI(wake=1).
  EDEADLK esperado (ret errno 35).
- Aresin: mesmo trio waiter/owner/consumer, mesmos syscalls.
- Aquaman: igual. O trio eh versao-independente; reaproveitavel.
  Status: igual.

## PI rollback / stack UAF

- Mecanismo (remove_waiter com current no proxy rollback) eh o mesmo nas
  tres versoes: 4.9 e 4.14 tem o codigo vulneravel identico em estrutura.
- Diferenca: o objeto dangling eh rt_waiter na stack do waiter nos tres.
  O que muda eh quem carimba a stack depois:
  Hazel usa setsockopt IPV6 MCAST_JOIN_SOURCE_GROUP; Aresin usa
  pselect/sched_setattr route + pipe; dnlid so valida EDEADLK.
- Aquaman: precisa-adaptacao. O consumer (sched_setattr nice) deve
  funcionar igual (sched_setattr existe no 4.9), mas o stack stamper
  precisa de teste local; o offset do waiter na stack muda com o
  compilador/vendor.

## Address leak (mm kzhash / futex timing)

- Hazel: kernel address leak via futex hash timing (ks_measure +
  ks_solve_mm), assumindo futex key de 16 bytes [mm,pad,addr,off] e
  mm_struct 0x1c0 em slab de 8K. Codigo em hazel_reclaim.h.
- Aresin: slide.c com KASLR leak proprio (abordagem physmap/data-only).
- Aquaman: precisa-adaptacao, ponto de risco alto. O hash do futex e o
  formato da key precisam ser conferidos no 4.9 Amlogic (o comentario
  do hazel sobre "backported 16-byte futex key" eh especifico do kernel
  FireOS; o 4.9 upstream ja usa union futex_key com ptr+word+offset, mas
  o jmp_hash e os shifts precisam de confirmacao). O grid 0x1c0 NAO
  vale no ARM64 (mm_struct maior). Todo o ks_* precisa de recalibragem
  com o tamanho real do slab/mm do aquaman.

## Allocator primitive / reclaim

- Hazel: AF_UNIX SOCK_STREAM socketpair + SO_SNDBUF 1MB + send 8K
  (skb full-page) reclamando a pagina do slab mm. Cross-cache
  mm_struct -> skb page.
- Aresin: pipe_buffer (pipe.c) + physmap write, rota diferente.
- Aquaman: precisa-adaptacao. AF_UNIX existe (CONFIG_UNIX=y) e pipe
  existe, mas a geometria (slab size, objs por slab, freelist random —
  ausente, bom) precisa ser medida no alocado aquaman. SLUB sem
  FREELIST_RANDOM e sem HARDENED (checar) favorece reclaim deterministico.
  Nao assumir que socket reclaim funciona igual; alternativa pipe ja tem
  precedente no aresin.

## Fake object (lock + fops na pagina reclamada)

- Hazel: fake rt_mutex em page+0x100, fake waiter em +0x140, fake
  file_operations em +0x200 com read/write/ioctl/mmap/open/release
  apontando para configfs_* e ashmem_* reais.
- Aquaman: precisa-adaptacao total de offsets. rt_mutex_waiter 4.9 ARM64
  tem task em 0x30 (igual 4.14), mas os campos do fake task (prio,
  pi_lock, pi_blocked_on) e o layout do fake fops dependem dos offsets
  ainda nao medidos. Estrutura da ideia reaproveitavel, numeros nao.

## Kernel read/write

- Hazel: configfs read/write via ashmem fd com nome forjado
  (configfs_buffer page/pos/mutex), boundary-crossing fault trick no
  write (page = target-1, EFAULT controlado).
- Aresin: pipe physmap read/write (rota data-only, sem fops forjado).
- Aquaman: configfs=y e ashmem=y compilados (CONFIRMADO no config), mas
  runtime (mount configfs, /dev/ashmem acessivel ao shell) = NAO PROVADO.
  O blob ARM32 eh INCOMPATIVEL direto (mutex +0x18 -> +0x20 no LP64).
  Se configfs/ashmem falharem no runtime, a rota pipe do aresin eh o
  plano B documentado.

## Current task discovery

- Hazel: caminha task list de INIT_TASK_TASKS para tras comparando comm
  (prctl PR_GET_NAME), range check 0xc13/0xf00 ARM32.
- Aquaman: mesma tecnica serve, com range ARM64 VA39
  (0xffffff8000000000+, KIMAGE base por KASLR) e offsets tasks/comm do
  4.9 Amlinux. precisa-adaptacao mecanica.

## Cred patch

- Hazel: zera 0x20 em cred+4 (8 ids + securebits), verifica leitura.
- Aquaman: igual se DEBUG_CREDENTIALS unset (confirmar). Mecanica igual.

## SELinux handling

- Hazel: nenhum bypass — Enforcing continua, daemon roda como
  u:r:shell:s0 com uid 0. uid 0 sem dominio novo.
- Aresin: tenta setenforce/sid ( فرض ) — ainda em progresso.
- Aquaman (ro.debuggable=0, Enforcing): esperar o mesmo teto do hazel:
  uid 0 em contexto shell. Suficiente para coleta (Fase 16). Nao presumir
  bypass de SELinux.

## Primeira diferenca concreta que impede o port (resposta prioritaria)

O blob forjado do hazel nao eh transplantavel: configfs_buffer.mutex em
+0x18 (ARM32) vs +0x20 (ARM64 LP64), mm_struct 0x1c0 vs tamanho ARM64
desconhecido, e todos os enderecos/ancoras ARM32. Alem disso o leak
kzhash depende de geometria de slab nao medida. Ou seja: trigger
reaproveitavel, todo o resto precisa de re-derivacao com offsets reais.
