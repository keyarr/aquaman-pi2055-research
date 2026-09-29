# GhostLock reachability (Fase 10)

Probe: tools/ghostlock_reachability.c. Benigno por construcao: so testa
dispatch e validacao de argumentos, nunca monta par PI, nunca tenta
deadlock, nunca toca waiter alheio.

## O que cada check prova

1. WAIT_REQUEUE_PI uaddr==uaddr2 -> EINVAL: handler existe (senao ENOSYS)
   e barreira inicial de futex_wait_requeue_pi alcançada.
2. CMP_REQUEUE_PI uaddr1==uaddr2 -> EINVAL: barreira requeue_pi de
   futex_requeue alcançada.
3. CMP_REQUEUE_PI cmpval mismatch -> EAGAIN: get_futex_key dos dois lados
   + comparacao funcionam (caminho chega ate a fila hash).
4. CMP_REQUEUE_PI uaddr invalido -> EFAULT: sem crash em fault.
5. WAIT_REQUEUE_PI val mismatch -> EAGAIN: futex_wait_setup alcançado.
6-7. LOCK_PI/UNLOCK_PI proprio -> 0: rt_mutex PI operacional.

## Validacao host

Compilado com gcc e rodado em kernel 7.0.9 x86_64 (ja com o fix):
7/7 PASS. Esperado: esses checks sao pre-corrupcao, identicos em kernel
vulneravel e corrigido. O probe NAO distingue vulneravel de corrigido —
ele so diz "caminho alcançavel pelo shell". A distincao vem da Fase 1
(source) + race EDEADLK abaixo.

## Rodada no aparelho (2026-09-29, adb, static ARM64 API 28)

Kernel: 4.9.113 #1 SMP PREEMPT Tue Sep 6 12:53:43 CST 2022 armv8l
(gcc Linaro 6.3.1 20170109, jenkins@c5-mitv-cm-build06.bj).
Resultado: 7/7 PASS, exit 0. Device segue vivo.
Status: CAMINHO ALCANCAVEL — CONFIRMADO NO KERNEL AQUAMAN.

## Race EDEADLK (tools/ghostlock_race_stats.c, passo 2 da escada)

5 rounds, 5x errno=35 (EDEADLK). Todo round entrou em
rt_mutex_start_proxy_lock via CMP_REQUEUE_PI e voltou pelo rollback
remove_waiter com waiter->task != current. Device vivo, uptime
contínuo, sem reboot. Equivale ao --race/--dry-run do dnlid.
Status: ROLLBACK ATINGIVEL — CONFIRMADO NO KERNEL AQUAMAN.
Proximo: lab offline (Fase 11) antes de qualquer trigger com reclaim.

## Risco

Desprezivel. Nenhuma chamada cria waiter PI real (valores que nao casam,
timeouts zero, futexes privados anonimos). Pode rodar via adb shell sem
medo de panic. Nao deixa estado: sem threads persistentes, sem fds.

## Proximo passo no aparelho (quando autorizado)

adb push + run, guardar saida. 7/7 PASS => CAMINHO ALCANCAVEL
(CONFIRMADO NO KERNEL AQUAMAN para dispatch; vulnerabilidade em si segue
INFERIDO ate Fase 12).
Qualquer ENOSYS => CAMINHO INACESSIVEL, aborta tudo.
