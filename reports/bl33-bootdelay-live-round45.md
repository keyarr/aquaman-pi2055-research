# BL33 round 45: bootdelay poke live, com restore

date: 2026-10-02. live, stage 16 (TPL/BL33). entrada via
`adb reboot fastboot` + `fastboot oem update 5000` -> `1b8e:c003`.
saida via bulkcmd `reboot` (PSCI normal, nao `reset`) -> `2717:4e40`
em ~18 s, adb presente. nenhum flash/eMMC/efuse, nada persistente.

## oracle (10/10, revalidado no inicio e entre cada passo)

failed: `false`, `test 1 = 2`, `test`, `env print foo`, `run foo1234`.
success: `true`, `test 1 = 1`, `echo`, `version`, `help`.

## mapa (hunt 0x33e18000 32k, sha 1c5e262d...)

- env `bootdelay` valor `0x33e1daa0` = `1`
- `bootcmd` valor `0x33e1da88` = `run storeboot`
- `stored_bootdelay` `0x37f723d8` = `0` nesta entrada (correcao ao
  round44: o valor e path-dependent; `1` e default do boot normal,
  `0` e residuo da entrada via burning; alvo de codigo confirmado,
  valor medido)
- gate `0x37e24500 cmn` + `0x37e24504 b.eq`, dispatcher
  `0x37e5f6e8 ldr` + `0x37e5f6fc blr`, slots `test 0x37f62180`,
  `false`, `run` todos live==offline

## escritas (todas com restore imediato, oracle vivo entre passos)

1. arena `0x37800000` FILL `0 -> a5a55a5a -> 0`. PASS.
2. `stored 0x37f723d8` FILL `0 -> ffffffff -> 0`, mread `0x200`
   conferindo. PASS. alvo limpo, sem vizinho.
3. env `0x33e1daa0` WRITE `1 -> -1 -> 1`, restore byte-exato.
   PASS com ressalva: o mid comeu 1 byte do vizinho
   (`bootup_offset` -> `ootup_offset`). `-1` nao cabe limpo nessa
   string; troca limpa 1:1 seria `1`->`0`. FILL aqui seria pior (4B).

## limite medido

poke em RAM nao sobrevive ao reset necessario para observar o
efeito no boot (reset limpa heap+BSS antes de `bootdelay_process`
reler). writability + restore + liveness: CONFIRMADO em-janela.
desvio de boot observado pos-reset: NAO PROVADO, segue PROVAVEL
via codigo + precedente mode 7 (round35).

## resto

exp B/C/D so leitura, ver sessao. `test->true` nao repetido como
prova, slot verificado intacto. verificacao final: arena zero,
slots originais, env restaurado, stored 0, oracle 5/5.
