# mm reclaim probe: order-2 hardware round (2026-10-01)

Question: neste device, neste boot, o mecanismo atual produz `hits > 0`
de reclaim order-2?

Answer: FAIL. Reclaim order-2 nao reproduzido em hardware. Pressure e
plumbing funcionam perfeitamente; sinal valido de reclaim nao existe
unpriv neste stock, entao `hits` e 0 por construcao.

Raw logs: `out/logs/mm_reclaim_control_boot3ec336a5.log`,
`out/logs/mm_reclaim_A_boot3ec336a5.log`,
`out/logs/mm_reclaim_B_boot3ec336a5.log` (stdout integral, 1 exec/modo).

## 1. Static expectation

Repo previa (`hazel-mm-struct-aquaman.md` sec 3/11,
`root-path-reclaim-consumer-mali.md` sec 2/5):

- hold via `open(/proc/pid/mem)` em child forked, `mm_count` via
  `proc_mem_open` (`base.c:801`); counts 608/171/18/1/19 = 817 holds;
- free em ordem Hazel retorna slabs order-2 (19 x 0x340) ao buddy,
  com settle de 2 s para `cpu_partial` (`CONFIG_SLUB_CPU_PARTIAL=y`);
- spray: 512 socketpairs `AF_UNIX SOCK_STREAM`, `SO_SNDBUF=1MB`,
  1 send de 16384 B cada; kernel tenta `alloc_pages(order 2)` primeiro
  (`skbuff.c:4693-4699`, NOWARN/NORETRY) e cai para paginas
  espalhadas em falha silenciosa;
- sentinel `0x5A5A5A5A@0x3FFC` via `MSG_PEEK` era esperado PASS nos
  dois modos, e ja estava REFUTADO como prova de reclaim antes do run
  (prova plumbing apenas);
- `/proc/slabinfo` ausente (`SLABINFO=n`), `/proc/buddyinfo` e
  `/sys/kernel/slab/mm_struct/*` root-only: diagnostico BLOCKED
  esperado para shell.

## 2. Device setup

- Xiaomi Mi TV Stick 1080p (aquaman), S805Y, Android 9 PI.2055,
  kernel 4.9.113 `#1 SMP PREEMPT 2022-09-06`, armv8l, SELinux Enforcing,
  ctx `u:r:shell:s0`.
- boot/session: `3ec336a5-439f-497f-b9f7-08fd7441b174`, uptime 23764 s
  no baseline, mesmo boot nas 3 execs, sem power-cycle.
- memoria no baseline: MemTotal 1004412 kB, MemFree ~129 MB,
  MemAvailable ~301 MB.
- ADB via USB, device `26919800005844922`, ulimit -n 32768.
- Harness: `tools/mm_reclaim_probe.c` (ajustado nesta rodada),
  build `aarch64-linux-android28-clang -O2 -Wall -static`, sem warnings,
  push em `/data/local/tmp/mm_reclaim_probe`. One-shot por exec,
  sem UAF/futex/cred/fptr/SELinux-bypass/persistencia.
- Comandos:
  `adb shell /data/local/tmp/mm_reclaim_probe control` (baseline),
  `... A` (modo A), `... B` (modo B). Cada um com `timeout` no host
  (240/590/240 s, nenhum atingido).

## 3. Mode A result (principal: 817 holds + 512 pares 16K)

`P7 SUMMARY mode=A-full pid=14638 attempts=1 holds_req=817 holds_ok=817
freed=817 pairs_req=512 pairs_ok=512 sends_ok=512 pressure_obj=16384B
plumbing_hits=512 reclaim_hits=0 emfile=0 hold_blocked=0 hold_other=0
t_ms=3306`. Shape em 1203 ms, spray em 45 ms. Veredito: FAIL
(`hits == 0`). Pressao total, zero bloqueios, zero EMFILE, sem
reboot/hang (log integral no arquivo citado).

## 4. Mode B result (fallback reduzido: 20 holds + 16 pares 16K)

`P7 SUMMARY mode=B-fallback pid=15462 attempts=1 holds_req=20 holds_ok=20
freed=20 pairs_req=16 pairs_ok=16 sends_ok=16 pressure_obj=16384B
plumbing_hits=16 reclaim_hits=0 emfile=0 hold_blocked=0 hold_other=0
t_ms=2043`. Veredito: FAIL (`hits == 0`). Referencia control
(plumbing baseline, 1 hold + 512 pares): `plumbing_hits=512/512`,
`reclaim_hits=0`, FAIL. Os tres modos concordam.

## 5. Signal classification

| sinal | classe | motivo |
|---|---|---|
| `MSG_PEEK` retorna sentinel (512/512 A, 16/16 B, 512/512 control) | FALSE_POSITIVE como reclaim / AUXILIARY como plumbing | control sem shaping passa igual; bytes proprios ecoam via skb mesmo com paginas espalhadas (`skbuff.c:4708`); prova send/peek, zero info de slab reuse |
| hold 817/817 + free 817/817 | AUXILIARY | pressao do allocator funciona, mas nada diz sobre pagina order-2 contigua nem reuse do alvo |
| deltas MemFree/MemAvailable (~10 MB no spray A) | AUXILIARY | atividade de allocator, nao reuse do objeto-alvo |
| `/proc/buddyinfo` errno=13 (6/6 tentativas) | BLOCKED | negado para shell; delta order-2 nao observavel |
| `/proc/slabinfo` ausente | BLOCKED | `SLABINFO=n`, esperado |
| `/sys/kernel/slab/mm_struct/slab_size` negado | BLOCKED | root-only 0400, esperado |
| `reclaim_hits=0` (P6, criterio valido) | veredito (FAIL) | unico numero que conta para a hipotese |
| nenhum sinal | PROOF | nada observado qualifica como prova |

## 6. Failure reason

Gargalo observado: sinal valido de reclaim indisponivel unpriv.
Pressao (817 holds, 512 sends 16K), hold SELinux (0 bloqueios) e
EMFILE (0) estao todos verdes; o que falta nao e pressao, e
observabilidade. O fallback do kernel (order-2 -> paginas espalhadas)
e silencioso, entao `sends_ok=512` nao distingue captura order-2 de
espalhamento. Sem UAF read nem contadores privilegiados, a taxa de
reclaim por tentativa continua NAO PROVADA mesmo com plumbing 100%.

## 7. Next bottleneck

Um so: observabilidade da captura order-2 por tentativa. Fechar exige
o consumer `FUTEX_LOCK_PI(f_chain)` cronometrado contra slabs
shaped+sprayed (leitura via UAF, terminador VAR B apenas, sem
cred/fptr), ou contadores slab pos-foothold. Sem isso, repetir mais
spray no mesmo boot nao decide nada.
