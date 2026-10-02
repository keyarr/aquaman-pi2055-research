# Optimus WRITE consumption round 40: BL33 consumed host-written bytes, twice

date: 2026-10-01. live, no aparelho. BL33 em RAM, `1b8e:c003`, stage 16.
build: aquaman_9_PI_2055, U-Boot 2015.01. entrada: `fastboot oem update 5000`.
base: round39 (`reports/optimus-write-mem-round39.md`) provou WRITE_MEM 0x01
em arena. este round prova consumo: BL33 leu de volta por caminho proprio,
nao so readback 0x02. detalhe: `reports/round40-optimus-consumption/`.

## 0. resposta

```text
WRITE_MEM em arena: CONFIRMADO (round39, re-confirmado E1 BEFORE)
consumo via memcpy upload (0x34+0x33): CONFIRMADO, E1, restore ok
consumo via .rodata reply (bulk): CONFIRMADO, E2, restore ok
cmd_tbl live == offline 116 entradas: CONFIRMADO, E0, read-only
RUN_IN_ADDR / bootm / flash / eMMC: NAO TOCADOS
cmd_tbl / page table / BL31: NAO ESCRITOS
```

## 1. E0 mapa vivo, so leitura

probe 13 enderecos numa sessao + mread 0x37f60eb0 0x15c0.
`00_e0_probe.txt`, `01_cmdtbl_mread.txt`.

```text
_start 0x37e18000, aml_sec_boot_check 0x37e19ea8, SMC 0x37e19ed8,
do_bootm 0x37e24c00, banner 0x37ebdcc0: iguais ao offline
serialno 0x37edf398, product 0x37edf3b8: iguais
cmd_tbl 0x37f60eb0..0x37f62470, 5568B: 0 diffs vs offline
arena 0x37800000: zero, limpa
burning buf ~0x37f8a620: vivo, muda a cada comando por design
page table 0x37ff0000: descritores, NAO TOCAR
```

correcao: base cmd_tbl e 0x37f60eb0 (entry 0 aml_sysrecovery).
0x37f60fd0 e entry 6 bootm. 116 entradas, stride 0x30, consumer
ldr x4,[x19,#0x10] em 0x37e5f6e8 + blr x4 em 0x37e5f6fc, 64b.
os "80 slots" antigos eram filtro de nome curto que quebra em
ddr_dqs_window_step. round38 ja tinha fechado isso.

## 2. E1 loopback em arena, restore ok

`02_e1_loopback.txt`. uma sessao, um processo, so 0x37800000 4B.

```text
BEFORE 0x02: 00 *16, PRE mread: 00 *16, match02=True
WRITE 0x01 <- a5 a5 5a 5a
AFTER 0x02: a5 a5 5a 5a ..., POST mread: a5 a5 5a 5a ...
RESULT: CONSUMO CONFIRMADO via memcpy do BL33
RESTORE verify 0x02 OK, RESTORE mread verify OK
```

isso elimina alias USB sem CPU: 0x02 e 0x33 concordam.

## 3. E2 string .rodata display-only, restore ok

`04_e2_string.txt`. alvo 0x37ed8794 `failed:\0`, .rodata, alinhado,
display-only, fora das areas proibidas. trigger seguro `foo1234`
(unknown, erro imediato, sem armar upload).

```text
BEFORE: 66 61 69 6c 65 64 3a 00, PRE trigger -> b'failed:'
WRITE 0x01 <- 46 58 41 58 ('FXAX')
MID readback ok, POST trigger -> b'FXAXed:'
RESTORE verify OK, trigger -> b'failed:' OK
```

o log diz INCONCLUSIVO por constante esperada errada no script
(`FAXXed:` vs `FXAXed:`). evidencia e CONFIRMADO: reply acompanhou
os 4B escritos e voltou no restore.

## 4. wedge sem escrita, aviso

`03_bulk_probe.txt`. bulkcmd `upload` sem args derrubou 1b8e:c003
do barramento (Errno 19, disconnect no dmesg). `foo` sozinho e seguro.
regra: so comandos completos; `upload mem <addr> normal <size>` sempre
com drain via 0x33.

## 5. o que isso prova

CONFIRMADO:

* 0x01 escreve e BL33 consome por dois caminhos independentes
  (upload memcpy, bulk reply), com restore verificado nos dois.
* cmd_tbl vivo e o offline, 116 entradas, sem escrita.
* sessao incompleta de bulk derruba o gadget mesmo sem write.

NAO CONFIRMADO:

* escrita dentro de codigo, cmd_tbl, page table. nao tentado.
* alteracao de fluxo, RUN_IN_ADDR, bypass secure boot.
* persistencia apos reboot. so sessao.

## 6. proximo honesto

survey read-only de ponteiros 64b + gd/env live via 0x02/mread.
sem escrita ate o mapa de consumers estar fechado.

## 7. risco

aparelho em `1b8e:c003` stage 16 ao fim de E2, verificado com identify.
nada persistente deixado: arena restaurada a zero, `failed:` restaurado.
nao deixar host grudado em optimus; esperar timeout ou power-cycle.
