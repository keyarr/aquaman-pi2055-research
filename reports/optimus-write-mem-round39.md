# Optimus WRITE_MEM round 39: escrita real de RAM via 0x01

date: 2026-10-01. live, no aparelho. BL33 em RAM, `1b8e:c003`, stage 16.
build: aquaman_9_PI_2055, U-Boot 2015.01. entrada: `fastboot oem update 5000`.
verbo: `AM_REQ_WRITE_MEM` 0x01 (`ctrl OUT 0x01, wValue=addr>>16, wIndex=addr&0xffff, 4B`).
leitura: `AM_REQ_READ_MEM` 0x02. detalhe: `reports/round39-optimus-write/00_session1.txt`, `01_session2.txt`.
equivale a `tools/optimus.py poke` + `read`; o teste usou script one-process so para nao queimar a janela.

## 0. resposta

```text
WRITE_MEM existe no binario rodando: SIM, 0x01 responde e altera RAM
host altera RAM do BL33: SIM na arena 0x378xxxxx (abaixo da base); dentro de BL33 NAO TESTADO
readback confirmando: SIM, 2 enderecos, antes/depois/reread/restore
RUN_IN_ADDR / bootm / flash / eMMC: NAO TOCADOS
```

## 1. sessao 1: 0x37800000

arena vazia, abaixo de BL33 (`0x37e18000`), longe de cmd_tbl e page tables.

```text
BEFORE 0x37800000: 00 *16
WRITE  0x01 0x37800000 <- 41 42 43 44 (4B, `ABCD` no fio)
AFTER  0x37800000: 41 42 43 44 00 *12
RESTORE <- 00 00 00 00 ; verify 00 *16 OK
tempo: write ok imediato, readback +200ms, identify stage 16
estado: 1b8e:c003 segue enumerado e responsivo, sem travar
```

## 2. sessao 2: 0x37801000

```text
BEFORE2 0x37801000: 00 *16
WRITE2  0x37801000 <- 44 33 22 11
AFTER2  0x37801000: 44 33 22 11 00 *12
REREAD  +1s: igual, persistente-na-sessao
RESTORE2 verify 00 *16 OK
CHECK1  0x37800000: 00 *16 limpo (isolamento entre escritas)
```

## 3. o que isso prova

CONFIRMADO:

* 0x01 WRITE_MEM existe no firmware rodando, nao so na arvore. refuta a hipotese "comando so no fonte" (cf. caso RD_LARGE que divergiu).
* payload de 4B alinhado escreve e faz readback via 0x02 em 2 enderecos distintos.
* sem travar, sem wedge, sem precisar power-cycle. distinto do wedge por endereco nao-mapeado da round 4.
* arena restaurada a zero apos o teste. nada persistente deixado.

NAO CONFIRMADO:

* escrita dentro de `0x37e18000..0x37ff0000` (codigo, cmd_tbl, got). nao tentado.
* tamanho maximo, alinhamento nao-4, cache flush, aceita-qualquer-endereco. so 4B alinhado testado.
* RUN_IN_ADDR 0x05. nem enviado.
* persistencia apos reboot. so sessao.
* relacao com rounds 16/37/38: aquelas eram `ddr_test_copy` via `oem` (D: sem consumidor compativel). esta e escrita direta do host via USB. primitivas diferentes, vereditos independentes.

## 4. proximo passo honesto

1. mapear limites ainda na arena: 8B/16B/64B, 1B unaligned em `0x37800001`, endereco no teto `0x37e17ffc` (ultimo antes de BL33).
2. so depois: 4B em dado de controle inofensivo do BL33 com readback, sem executar.
3. RUN_IN_ADDR continua gated: nao enviar ate escrita em BL33 estar caracterizada.

## 5. risco

stick ficou em `1b8e:c003` ao fim das duas sessoes. ou espera o auto-burn timeout (volta sozinho a Android) ou power-cycle manual. nao deixar host grudado em optimus.
