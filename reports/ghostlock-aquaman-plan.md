# GhostLock aquaman plan (Fase 2 + Fase 13-17 + veredito)

## Fase 2 — config real (aquaman-config, 5381 linhas, arm64 4.9.113)

| Simbolo | aquaman | Hazel 4.9 ARM32 | Aresin 4.14 ARM64 | Efeito pratico |
|---|---|---|---|---|
| CONFIG_FUTEX / RT_MUTEXES | y / y | y / y | y / y | PI compilado nos 3; 4.9 nao tem CONFIG_FUTEX_PI separado |
| CONFIG_PREEMPT (nao RT) | y | y | y | preemptivel, race viavel |
| CONFIG_DEBUG_RT_MUTEXES | unset | unset | unset | waiter sem campos debug: layout 0x50 |
| CONFIG_SLUB | y | y | y | mesmo allocator family |
| CONFIG_SLUB_DEBUG | unset | unset | ? | sem redzone/poison por padrao |
| CONFIG_SLAB_FREELIST_RANDOM | unset | unset | n/a 4.14 | freelist deterministica: ajuda reclaim |
| CONFIG_SLAB_FREELIST_HARDENED | checar* | n/a 4.9 | ? | *grep nao achou unset nem set: ver linha exata antes do exploit |
| CONFIG_KASAN | unset | unset | unset | sem sanitizer no alvo |
| CONFIG_HARDENED_USERCOPY | y | y (nota hazel) | y | reads de kernel text via configfs rejeitados; usar lowmem addrs (hazel ja faz) |
| CONFIG_ARM64_VA_BITS | 39 | n/a (ARM32) | 39? (MTK) | PAGE_OFFSET 0xffffff8000000000 |
| CONFIG_KALLSYMS(_ALL,_BASE_REL) | y | y | y | existe mas bloqueado p/ shell; irrelevante ate uid 0 |
| CONFIG_MODULES | y | ? | y | irrelevante p/ exploit |
| CONFIG_ASHMEM | y | y | y/n? | hazel usa; aresin foi de pipe |
| CONFIG_CONFIGFS_FS | y | y | ? | hazel usa; plano B pipe existe |
| CONFIG_UNIX / IPV6 / NET | y / y / y | y / y / y | y | AF_UNIX spray + stamper IPV6 disponiveis por config |
| CONFIG_AMLOGIC_SLUB_DEBUG | unset | n/a | n/a | vendor nao endureceu SLUB |

Runtime (/dev/ashmem, configfs mount, pstore): pendente, checklist em
ghostlock-ashmem-configfs.md. Config diz "possivel", nao "presente".

## Fase 13 — plano de escalada especifico aquaman 4.9.113 ARM64

Ordem, cada item so apos o anterior verde:
1. Offsets: pahole em vmlinux dangal-buildado + validacao runtime
   (Fase 3). Proibido copiar hazel (ARM32) e aresin (4.14 MTK).
2. Symbols: sem kallsyms; ancora swapper + task list apos kernel read
   (Fase 8). Primeiro perfil nasce de build local + leak mm.
3. Heap: medir slab/mm reais no aparelho (leak), escolher AF_UNIX vs
   pipe; recalibrar ks_* (grid 0x1c0 morto no ARM64).
4. Kernel R/W: regenerar blob configfs p/ LP64 (+0x20 mutex) OU rota
   pipe do aresin se ashmem/configfs falharem no runtime.
5. Current: walk da task list com ranges VA39.
6. Cred: zero 0x20 em cred+4 apos confirmar DEBUG_CREDENTIALS unset.
7. SELinux: nenhum bypass planejado; teto = uid 0 em u:r:shell:s0
   (igual hazel). Suficiente para coleta.

## Fase 14 — SELinux

ro.debuggable=0 + Enforcing: uid 0 nao vira permissivo sozinho e nao
muda de dominio. O hazel prova que uid 0 shell-domain basta para
diagnostico e coleta, e eh onde paramos (Fase 16). Desligar enforcement
ou virar init-domain = fora deste estagio.

## Fase 15/16 — root temporario e coleta

So apos escada da Fase 12 verde. Coleta read-only listada no brief
(kallsyms, config.gz, cmdline, devicetree, modules, iomem, pstore...).
Nada de flash, nada persistente.

## Fase 17 — sem KernelSU/APatch ainda

uid 0 temporario alimenta a reconstrucao do kernel 2022; persistencia
se avalia depois, com o kernel real na mao.

## Respostas finais (13 perguntas) — atualizadas 2026-09-29 com dados do aparelho

1. CONFIG_FUTEX_PI habilitado? SIM por construcao (FUTEX=y +
   RT_MUTEXES=y; sem simbolo separado no 4.9). CONFIRMADO NO KERNEL AQUAMAN (config).
2. Condicao exata do CVE no codigo? SIM na arvore 4.9.113 analisada;
   binario exato INFERIDO (sem source/vmlinux do PI.2055), mas rollback
   via EDEADLK confirmado 5/5 no aparelho.
3. CMP_REQUEUE_PI alcançavel? CONFIRMADO NO KERNEL AQUAMAN (probe 7/7 +
   race 5/5 EDEADLK, 2026-09-29).
4. Hazel aproveitavel como base estrutural? SIM para trigger, modelo de
   cadeia, validacao runtime e daemon; NAO para numeros. CONFIRMADO APENAS EM OUTRO DEVICE.
5. O que reescrever p/ ARM64? Blob configfs (LP64), grid mm/slab, leak
   kzhash, ranges de validacao, offsets task/cred, stamper stack.
6. Aresin ajuda onde? Rota pipe/physmap (plano B), mapa de diferencas
   4.9x4.14 (rb_node igual, task_struct diferente), metodo KASLR slide.
7. Structs/offsets necessarios? Lista na Fase 3; numeros finais so via
   pahole + runtime. NAO PROVADO.
8. Base/simbolos sem kallsyms? Via leak timing + ancora swapper apos
   kernel read (Fase 8). Nao precisa de kallsyms nem AMLSECU key.
9. Ashmem/configfs disponiveis? Compilados SIM; runtime CONFIRMADO
   (/dev/ashmem rw p/ shell, configfs montado rw). Dentry-tolerancia:
   NAO PROVADO.
10. Reclaim plausivel? AF_UNIX cross-cache (via hazel) ou pipe (via
    aresin); geometria a medir. INFERIDO/NAO PROVADO.
11. Reachability sem risco? SIM, probe pronto, 7/7 no aparelho.
    CONFIRMADO NO KERNEL AQUAMAN.
12. Caminho plausivel ate uid 0 temporario? SIM, com adaptacoes listadas;
    probabilidade real so apos Fase 11 (lab) + trigger com reclaim.
13. O que o root destrava? kallsyms, config, dt, modulos, iomem —
    pstore NAO (negado p/ shell; rechecar como root). Base para
    reconstruir o kernel 2022 e avaliar KernelSU depois.

## Classificacao geral — atualizada 2026-09-29

CVE presente + caminho alcançavel: CONFIRMADO NO KERNEL AQUAMAN
(probe 7/7, race EDEADLK 5/5, ashmem+configfs runtime OK).
Layouts compativeis: NAO PROVADO (offsets pendentes).
Primitive disponivel: NAO PROVADO (reclaim nao tentado).
Adaptacao possivel: SIM (plano acima).
Veredito: 4.9.113 NAO implica exploravel sozinho, mas aqui temos
CVE no source + rollback atingivel 5/5 + superficies runtime OK.
O que falta antes de qualquer teste com risco: offsets (pahole/lab) e
geometria de slab. Proximo passo fisico: lab offline, depois trigger
com reclaim read-only.
