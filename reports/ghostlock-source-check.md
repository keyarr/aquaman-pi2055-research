# GhostLock source check — aquaman 4.9.113 (Fase 1)

Data: 2026-09-29. Analise offline, sem tocar no aparelho.

## Arvore analisada

`/tmp/kernel-src/linux-amlogic` (McMCCRU/linux-amlogic, HEAD 3d4ab79e,
base 2019-06). Makefile: VERSION=4 PATCHLEVEL=9 SUBLEVEL=113.

AVISO DE PROVENIENCIA: nao eh o source exato do aquaman. Ver
reports/exact-source.txt: nenhum source exato foi encontrado; o mais
proximo do oficial Xiaomi eh o dangal-p-oss (outro device, mesmo 4.9.113).
Tudo abaixo vale para "kernel Amlogic 4.9.113 adjacente", nao para o
binario PI.2055 byte-a-byte.

## Perguntas da Fase 1

1. remove_waiter() usa current? SIM.
   kernel/locking/rtmutex.c:1099-1111:
   raw_spin_lock(&current->pi_lock); rt_mutex_dequeue(lock, waiter);
   current->pi_blocked_on = NULL; raw_spin_unlock(&current->pi_lock);
   E na cauda: rt_mutex_adjust_prio_chain(..., NULL, current) (linha 1146).
   Eh exatamente o padrao que o patch 3bfdc63936dd troca por waiter->task.

2. waiter->task existe? SIM. kernel/locking/rtmutex_common.h:28,
   `struct task_struct *task`, preenchido em task_blocks_on_rt_mutex
   (rtmutex.c:997, waiter->task = task).

3. rt_mutex_start_proxy_lock() recebe task separado? SIM. rtmutex.c:1691,
   (lock, waiter, task). Chama task_blocks_on_rt_mutex(lock, waiter, task,
   FULL_CHAINWALK) e no erro faz remove_waiter(lock, waiter) (linha 1718).
   Nesse caminho waiter->task (a vitima em espera) != current (o requeuer).
   Condicao do CVE presente.

4. Existe rollback com remove_waiter()? SIM, dois sitios:
   rt_mutex_start_proxy_lock (1719) e rt_mutex_finish_proxy_lock (1777).
   O primeiro eh o gatilho do GhostLock via futex_requeue().

5. FUTEX_CMP_REQUEUE_PI implementado? SIM. futex.c:3283-3284, dispatch para
   futex_requeue(..., requeue_pi=1). futex_requeue faz proxy trylock +
   rt_mutex_start_proxy_lock com this->task da vitima (linhas 1955-1957).
   Cadeia requeue_pi completa presente.

6. FUTEX_WAIT_REQUEUE_PI implementado? SIM. futex.c:2853
   futex_wait_requeue_pi(), waiter na stack do chamador (rt_waiter local,
   linha 2858), caso classico de stack-UAF apos rollback errado.

7. CONFIG_FUTEX_PI habilitado no config real? SIM por construcao.
   4.9 nao tem simbolo CONFIG_FUTEX_PI separado (só existe
   CONFIG_HAVE_FUTEX_CMPXCHG); o suporte PI vem de
   CONFIG_FUTEX=y + CONFIG_RT_MUTEXES=y, ambos =y no aquaman-config,
   mais CONFIG_PREEMPT=y. init/Kconfig: FUTEX select RT_MUTEXES.
   futex.c desta arvore nao tem nenhum #ifdef que excluiria o caminho PI.

8. Patches vendor alterando o caminho? NAO ENCONTRADO nesta arvore.
   rtmutex.c e futex.c nao mostram hunks Amlogic/Xiaomi no caminho
   PI (sem git history util aqui para diff contra upstream, mas o codigo
   eh textualmente o 4.9.113 upstream nesse arquivo). O config traz
   CONFIG_AMLOGIC_SLUB_DEBUG (unset), irrelevante para rtmutex.
   Resta a ressalva: o binario PI.2055 pode conter patch vendor
   invisivel sem o source exato ou sem vmlinux.

## Classificacao Fase 1

VULNERABILIDADE PRESENTE (na arvore 4.9.113 analisada; binario aquaman
exato = INFERIDO, pendente de confirmacao por disassembly do kernel em
execucao ou source oficial).

Nao se concluiu vulneravel so pela versao: foi lido o corpo de
remove_waiter, do proxy lock e do requeue, e comparado com o diff do
patch upstream (current -> waiter_task nos tres pontos).
