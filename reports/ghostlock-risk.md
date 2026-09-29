# GhostLock risk + validacao offline (Fase 11 + Fase 12)

## Risco do teste no aparelho

- GhostLock real = UAF de stack com reclaim probabilistico. Taxa de
  falha limpa vs panic: no hazel, "pode falhar limpo ou panicar e
  rebootar". Sem UART, panic = tela congelada ate power cycle fisico.
- O que NAO corrompe: probe Fase 10 (sem waiter real), dnlid --dry-run
  e --race (param ate EDEADLK, para antes da corrupcao).
- O que PODE panicar: qualquer tentativa de completar o rollback com
  waiter divergente (trigger real), mesmo sem reclaim.
- Mitigacoes sem UART: pstore/last_kmsg para diagnostico post-mortem
  (checar /sys/fs/pstore apos reboot); bootreason; manter janela de
  observacao via adb (se adb morre = reboot ou hang).

## Escada de testes proposta (parar no primeiro vermelho)

1. reachability 7/7 (risco ~0). VERDE 2026-09-29 no aparelho.
2. dnlid --dry-run/--race: estatistica EDEADLK (risco ~0, so prova que
   o rollback eh atingido com frequencia). VERDE 2026-09-29:
   tools/ghostlock_race_stats.c, 5/5 EDEADLK, device vivo, sem reboot.
3. Trigger real sem reclaim (uma vez, sem pstore legivel p/ shell:
   diagnostico = adb vivo/morto + uptime). PENDENTE, decisao com o dono
   do hardware. Nota: pstore negado p/ shell reduz o post-mortem;
   rechecar como root depois.
4. Reclaim + read-only validation (ler de volta o proprio fake fops,
   como o hazel faz) antes de qualquer write. PENDENTE de offsets.
5. Write em cred so depois de 4 verde e repetivel.

## Fase 11 (lab offline)

Nao executada aqui: sem QEMU ARM64 montado neste workspace. Opcoes,
baratas primeiro:
a) harness userspace do trio futex (waiter/owner/CMP) contra kernel
   4.9.113 Amlogic compilado local com KASAN + DEBUG_RT_MUTEXES num
   QEMU virt ARM64 — prova o UAF logico com report do sanitizer.
b) compilacao do dangal com aquaman-config para pahole (tambem serve a
   Fase 3 e o primeiro perfil).
Nenhuma das duas exige o aparelho. Recomendado antes do passo 3 acima.

## Classificacao desta fase

- Reachability dispatch: PROVAVEL (pende so de rodar o binario).
- EDEADLK race: INFERIDO (codigo confirma o caminho; taxa real so no hw).
- Reclaim/stack-stamp no aquaman: NAO PROVADO.
- Panic sem UART: risco real, mitigavel com escada + pstore.
