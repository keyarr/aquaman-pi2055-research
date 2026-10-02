# BL33 campaign round 43: sinks, handlers, redirects x3, FILL, RUN wedge

date: 2026-10-01. live, no aparelho, stage `00 07 00 10` (TPL/BL33).
base: round39 (WRITE 0x01), round40 (consumo duplo), round41 (mapa 116),
round42 (false->true). nenhum flash/eMMC/efuse tocado. nenhum write
persistente deixado (tudo com restore, resto limpo por reboot).
sessoes: S1 recon + T1/T2 + MODIFY-crash, S2 re-entry + P1/P2/P3 + RUN-wedge.

## 0. resposta

```text
L0 read-only            PROVADO (0x02 + mread, cmd_tbl 0 diffs)
L1 arbitrary write      PROVADO (0x01 8/16/64B; FILL 0x03 espalhado)
L2 control-data         PROVADO (string round40; slots lidos)
L3 control-flow p/ cod  PROVADO x3 (false->true, test->true, envprint->true)
L4 exec arbitraria BL33 NAO (RUN pula mas trava USB, sem exec observada)
L5 fronteira secure     NAO (SMC 0x820000ff intacto)
L6/L7 root/persist      NAO
FILL_MEM 0x03           EXISTE, provado em arena (2a primitive de escrita)
MODIFY 0x04             handler vivo mas DESTRUTIVO (derruba sessao, sem readback)
RUN_IN_ADDR 0x05        handler vivo mas TRAVA USB mesmo p/ no-op + KEEP_POWER
sub-tabela redirect     PROVADO (env print -> true, cross-table)
WRITE 64B               PROVADO em 1 transferencia
```

## 1. recon read-only (S1, uma sessao)

```text
cmd_tbl 0x37f60eb0 0x15c0 mread: 0 diffs vs offline, sha 8c2f2b92...
call_cmd 0x37e5f664: ldr x4,[x19,#0x10] @0x37e5f6e8 + blr x4 @0x37e5f6fc, live==offline
handlers false/true/echo/version/help/run/bootm: live==offline (16-32B cada)
mmc disp 0x37e2ca3c / store 0x37e33900 / env 0x37e57d6c: live==offline
mmc tab 0x37ee5bc0 14 entries (info..test), store 0x37ee62f0 14 (init..mbr),
  env 0x37ee70f8 8 validas (default..set, entry 8 lixo = fim)
cipher ops 0x37f5e478 / block ops 0x37fbc940 / bss 0x37f60cc0 / usb 0x37f62550: live==offline
defenv 0x37eb65a0 bootcmd=run storeboot / banner / failed: string: live==offline
pagetable idx0 desc 0x411 idx1 0x20000411, AttrIdx 4 Normal-WB, AP 0 EL1-RW, XN 0
  => RAM 0x10200000 e BL33 0x37e18000 ambos RWX. observado no hardware.
BSS 0x37f80000 16K: zero (e instavel: mread repetido deu timeout 1x)
0x37f84000: 34B nonzero esparsos. 0x37f88000: 180B, contem
  0x37f8a388 'success' + 0x37f8a638 'upload mem ...' (residuo dos proprios comandos)
0x37f60000: strings de particao (pattern/Umagic/bootloader/AML_TABLE/fastboot_context)
  + blob 0x37f626e0+ (log-spam android, buffer de burning, nao env)
env vivo NAO localizado em 0x37f80000..0x37f83fff. hunt continua em 0x37f84000+.
```

bulk baselines (oracle failed:/success, sha 614bbb7c vs 1ca51e20):

```text
failed: false, test 1 = 2, test, env print foo, run foo1234, foo1234
success true, test 1 = 1, echo, version, help, ?, printenv, env print,
  mmc info/list/dev/rescan, store init/exit, env default -a
mmc info FLAKY: failed: numa sessao, success noutra. nao usar como discriminador.
false 1o bulk pos-leituras da timeout 1x e passa no retry. harness precisa retry+drain.
mread tamanho 8 flaky (timeout 2x, retry passa). usar >=0x40 p/ cross-check.
```

## 2. bateria S1: WRITE sizes + FILL + MODIFY-crash

```text
TEST T1-WRITE-8/16/64 ALVO 0x37800000 ANTES zero MID == pattern DEPOIS zero RESTORE ok STATUS PASS x3
  => 0x01 aceita >=64B por transferencia. 1 WRITE cobre 1 entry cmd_tbl (0x30).
TEST T2-FILL ALVO arena ANTES 0 MID 5a5aa5a5 (=0xA5A55A5A le, so low 4B) mread match True
  RESTORE ok STATUS PASS-FILL-EXISTS
  => 0x03 existe no build vivo. 2a primitive: pares (addr,val) 8B cada, *(u32*)addr=val.
TEST T3-MODIFY op0 (mem=arena data=0x12345678) => Errno 19 disconnect no rd seguinte.
  sessao morta. apos ~40s stick em 2717:4e40 adb android. REBOOT SOZINHO.
  => 0x04 atendido mas DESTRUTIVO (ou crash ou stall). semantica opcode NAO provada.
  nao repetir no meio da sessao: deixar p/ ultimo.
```

detalhe: T1-8 MID escreveu 0x37e3676c na arena e o mread-8 seguinte deu
timeout (retry com 0x40 passou no T2). cross-check de arena fica so no 0x02.

## 3. bateria S2 (fresh boot pos-crash): P1/P2/P3 + RUN-wedge

arena limpa pos-reboot. slots nos originais.

```text
TEST P1 ALVO 0x37f616d0 (false idx43) ANTES 6467e337 (=0x37e36764)
  ALTERACAO <- 6c67e337 trigger false: ANTES failed: DEPOIS success
  RESTORE orig, retrigger failed: STATUS PASS (re-confirma round42)
TEST P2 ALVO 0x37f62180 (test idx100 +0x10) ANTES 7467e337 (=0x37e36774)
  trigger 'test 1 = 2': ANTES failed: DEPOIS success (slot agora true)
  RESTORE, retrigger failed: STATUS PASS (2o par main-table, generaliza)
TEST P3 ALVO 0x37ee71c8 (env print sub-slot +0x10) ANTES a87ee537 (=0x37e57ea8)
  trigger 'env print foo': ANTES failed: DEPOIS success (handler true cross-table)
  RESTORE, retrigger failed: STATUS PASS (1a prova sub-dispatcher redirect)
TEST T7 RUN_IN_ADDR 0x05 addr=0x37e3676c(true) flags=0x10 KEEP_POWER
  => Errno 5 I/O error em tudo depois. STATUS WEDGE.
TEST T8 RUN addr=0x0 flags=0x10 => ja morto, SEND-EXC. ident morto.
pos: 1b8e:c003 enumerado mas surdo por 110s+ (descritores via lsusb ok,
  zero vendor req responde). usb reset => sumiu do bus. precisa power-cycle fisico.
```

P3 e o achado principal da S2: sub-tabela env tem o mesmo molde
`ldr x4,[x0,#0x10]+blr x4` e o slot aceita handler de outra tabela.
convencao de chamada compativel (cmdtp,flag,argc,argv).

## 4. sinks (estatico, capstone, 352 sitios)

total `ldr xN,[xM,#off]` + `blr/br xN` delta<=32B mesma func: 352 (blr 351,
br 1) em 199 funcs. lista completa no subagent ses_f063e628 (arquivada).
principais:

```text
cmd_tbl 0x37e5f664: [x19+#0x10] -> blr (consumer principal)
mmc 0x37e2ca3c: [x19+#0x10] tab 0x37ee5bc0 stride 0x30 14 entries
store 0x37e33900: [x0+#0x10] tab 0x37ee62f0 14 entries
env 0x37e57d6c: [x0+#0x10] tab 0x37ee70f8 8 entries
imgread/avb/keyman/fdt/usb: mesmo molde via find_cmd + blr x4
cipher ops 0x37f5e478 (34 slots) consumidos em 0x37e73730/50/ec
block ops 0x37fbc940 (24 ptrs 0x37e84xxx-0x37e85xxx)
bss 0x37f60cc0 (24 ptrs), usb state 0x37f62550/0x37f62638
hook 0x37ee2710 (blr x0 em 0x37e19848)
```

clusters >=4 slots (gap<=0x40): 39. regioes densas 0x37ee59a8..67d0 (mmc+store),
0x37ee70f8..7b10 (env+heap), 0x37f60df8..24e0 (cmd_tbl embutida, 475 ptrs).

## 5. handlers por capacidade (estatico, detalhe ses_f0638c36)

```text
display-only, sem storage/reset/smc (alvos seguros p/ redirect):
  true 0x37e3676c (mov w0,#0;ret), false 0x37e36764 (mov w0,#1;ret),
  echo 0x37e28000, version 0x37e26688, help/? 0x37e26644
execucao/controle: run 0x37e5ea04 (loop getenv+run_command), fastboot 0x37e3a840
  (entra USB loop), bootm 0x37e24c00 (SMC 0x820000ff via 0x37e19ea8 + run_command x2),
  usbboot/usb (strtoul+memset, boot path), fdt (RAM DTB edit), imgread (dispatcher)
memoria: ddr_test_copy 0x37e3d1b0 (benchmark destrutivo, sem flush), mmc/store
  (dispatchers eMMC), ext4load/fatload (file->RAM arbitraria, L2 memcpy)
estado: env dispatcher, setenv (RAM, so persiste com saveenv), saveenv (flash!),
  set_active_slot (slot flip), set_usb_boot (strtoul->SMC 0x82000043), get_rebootmode
cripto: avb, keyman, keyunify, efuse 0x37e56804 (SMC, OTP!), efuse_user (SMC L3, OTP!)
reset: reboot (SMC reset), reset 0x37e21684 (MMIO watchdog loop, nunca retorna)
reuso como primitive: loadb/loadx/loady 0x37e2c1a0 (addr via argv + loop UART stores,
  melhor write-arbitrario como comando); ddr_test_copy inner 0x37e3aea0 (copiador limpo
  se registradores controlaveis); update/usb_burn/sdc_update (flash, nao usar).
nenhum handler chama smc direto no corpo; SMC so via callees
  (bootm, set_usb_boot, efuse*, reboot).
```

## 6. RUN_IN_ADDR (fonte + estatico + vivo)

fonte tiny (`usb_pcd.c`, NAO e o stack do BL33, que e v2):
setup 0x05 so arma buf; complete: addr=(wValue<<16)+wIndex,
flags=*(u32*)OUT[0], se !(flags&0x10) power_off_phy(), fp() incondicional.
WRITE 0x01: buf=(char*)addr direto. FILL 0x03: pares 8B. MODIFY 0x04:
opcodes 0-7, 7 = `while(data--)*mem++=*mem2++` (memcpy!).
password: need_password=1/password_ok=0 no init, mas live responde
`need_password=0` no identify => sem gate nesta fase. verify sempre-true p/ <=64B.
no binario BL33: path tiny ausente; so v2 (`v2_usb_tool/usb_pcd.c`,
strings BULKcmd/tplcmd/Enter v2 usbburning). padrao `(wValue<<16)+wIndex`
nao achado; KEEP_POWER 0x10 so como imediato generico.
vivo: 0x03 CONFIRMADO, 0x04 disruptivo, 0x05 wedge mesmo com 0x10 num no-op.
=> handler 0x05 existe mas NAO tem a semantica docil do tiny, ou o jump
corrompe o retorno USB. proxima rodada precisa UART + variantes de flags.
candidatos p/ 1o RUN (quando controlado): true/false (zero acesso, so provam
no-crash), version (print, precisa UART p/ observar). help/echo como RUN cru
= data abort provavel (argv lixo). nao usar.

## 7. pagetable / codigo / env (estatico + vivo)

builder 0x37e19314: OA=i<<29, identidade, TCR 0x300004516, MAIR ...ff440c0400.
so idx0,1 sao RAM Normal-WB; resto Device. AP 0 (EL1 RW), XN 0 em tudo.
=> BL33 e scratch 0x10200000 RWX no EL. SCTLR C/I nao determinavel offline.
WRITE em codigo NAO testado (sem hipotese reversivel ainda; I-cache off no
fonte mas D-cache on => precisaria flush via `dcache` idx11).
env default rodata ~0x37eb65a0 (bootcmd=run storeboot, bootdelay=1...);
env vivo em BSS sem offset fixo (zero no binario). hunt read-only:
`mread 0x37f84000+ + grep`, nunca poke ate achar consumidor.

## 8. cadeias

```text
PROVADA:  WRITE(0x01) -> cmd_tbl[i].cmd -> handler legitimo -> reply failed:/success
PROVADA:  WRITE -> sub-tabela env -> handler cross-table (P3)
PROVADA:  FILL(0x03) -> RAM (falta demo FILL->slot; mesmo slot, deve funcionar)
PLAUSIVEL: FILL 6 pares -> entry inteira 0x30 (nome+max+cmd) num WRITE logico
PLAUSIVEL: WRITE/FILL -> maxargs/usage/help (dado, display-only)
BLOQUEADA: WRITE/FILL -> RUN(0x05) -> exec (RUN trava USB antes de observar)
BLOQUEADA: handler -> SMC 0x820000ff -> boot nao-assinado (secure boot segura)
ABERTA:   WRITE -> env vivo (endereco desconhecido)
ABERTA:   WRITE -> codigo .text (RWX confirmado, sem teste; precisa flush+I-cache story)
MORTAS (nao repetir): ddr_test_copy como write (r38: 32b x4 vs ldr x64),
  RD_LARGE, setenv lock / set_usb_boot como bypass, magisk boot unsigned.
```

## 9. niveis L0-L7 (factual)

L0 read-only: SIM (0x02 ate 64B + mread + bulk oracle).
L1 arbitrary write: SIM (0x01 8/16/64B qq endereco testado; 0x03 espalhado).
L2 control-data: SIM (string round40 + slots).
L3 control-flow p/ codigo existente: SIM (P1/P2/P3 + restore duplo).
L4 exec arbitraria BL33: NAO (RUN pula mas sem exec controlada observada).
L5 fora do BL33 / secure: NAO. L6 root temp: NAO. L7 persistencia: NAO
(tudo RAM; reboot limpou S1->S2).

## 10. proximos 3 (maior valor)

1. DONE (S3): FILL->redirect demo PASS (F1 abaixo). Resta: entry inteira
   via 6 pares FILL (troca nome+max+cmd num WRITE logico).
2. RUN com UART + matriz flags (0x10 vs 0x00 vs len 0) p/ alvo no-op e p/
   funcao que escreve magic na arena; decide entre PHY-off (recuperavel) e
   fault de CPU. exige acesso fisico + serial. sem isso, RUN segue wedge.
   NAO repetir RUN/MODIFY sem UART: cada um custa 1 power-cycle.
3. DONE parcial (S3): env vivo LOCALIZADO (ver S12). Falta: formato do
   hash + teste com observavel desenhado (printenv nao sai no bulk reply;
   candidato: var consumida por `run`/`bootm`, perigoso; ou redirect que
   torne env observavel via return-code).

## 12. S3 pos-power-cycle (sessao nova, stage 16, viva ao fim)

health: arena zero, false/test/envprint slots nos originais (reboot limpa tudo).

```text
TEST F1 FILL->false->true (1 par 32b, high ja 0)
  ANTES failed: MID slot 6c67e33700000000 TRIGGER success RESTORE orig retrigger failed:
  STATUS PASS. 2o path independente p/ fluxo (0x01 desnecessario p/ slot <4GB).
TEST F2 FILL espalhado (3 pares 1 transferencia, gaps intocados)
  MID 11111111/00000000/22222222/00000000/33333333 RESTORE zero STATUS PASS
HUNT env: 0x37f50000/8c/90/94/98/9c + 0x37e10000 zero; 0x37f84000/88000
  deterministicos (mesmo sha entre boots: structs de firmware, nao residuo)
```

## 13. env vivo LOCALIZADO (read-only, sem escrita)

arena malloc 0x33e18000+ (`hunt_33e18000_32k.bin`, 32K de 0x33e18000):

```text
hash table   ~0x33e1d6e8: active_slot=normal avb2=1 baudrate=115200 bcb_cmd=...
             boardid=3 boot_part=... (28+ vars)
bootcmd      0x33e1da8c: run storeboot
bootdelay    0x33e1da8c+ : 1
bootargs     0x33e1d811+ (35 androidboot.*, 28 bootargs refs)
scripts      storeboot @0x33e1eb21, recovery/switch_bootmode/upgrade_check...
upgrade_step 0x33e1f1cb: 2
lock         outputmode ctx: 10100000
consumidores printenv/env-print (invisivel no bulk) + run/bootm/get_rebootmode
```

regioes densas sem strings (blobs, nao env): 0x37f00000..0x37f40000
(~15K nonzero cada, lixo curto); 0x37f70000 = tabelas unicode ICU (309 strs);
0x37f88000 = buffers de burning (residuo dos proprios uploads + descritores
0x37f89fxx-0x37f8abxx); 0x37f84000 = ptrs heap 0x33xxxxxx + BL33 0x37e1xxxx.
NAO ESCRITO: sem observavel USB p/ mudanca de env (bulk so da success),
qualquer poke aqui espera o teste do item 10.3.

## 11. riscos e regras de harness (aprendidas nesta rodada)

```text
0x04 e 0x05 matam a sessao. testar SEMPRE por ultimo, nunca no meio.
bulk incompleto derruba gadget mesmo sem write (round40). so comando completo + drain 0x33.
pos-timeout: drenar 0x33 ate n==0 antes do proximo bulkcmd.
mread size 8 flaky; cross-check com >=0x40 ou so 0x02.
false 1o bulk pos-rajada pode dar timeout 1x; retry 3x + drain.
arena restaurada a zero nas 2 sessoes; slots P1/P2/P3 restaurados e re-verificados.
S2 terminou wedged (RUN); S1 terminou em reboot-android (MODIFY). nada persistente.
```

logs: `reports/round43-campaign/` (battery.log, battery3.log, ro_cmdtbl_full.bin).
repro: `sudo python3 tools/optimus.py identify/mread/bulkcmd`,
scripts em `/tmp/opencode/{campaign_ro,bsshunt,dump_sub2,baseline,battery2,battery3}.py`.
