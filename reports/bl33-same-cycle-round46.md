# BL33 round 46: mesma-ciclo WRITE -> dispatch -> decisao -> observavel

date: 2026-10-02. live, uma sessao Optimus (`1b8e:c003`, stage 16).
entrada: `fastboot oem update 5000` a partir de fastboot (o `FAILED (Status
read failed)` e esperado, o gadget troca de modo). saida: sessao viva ao fim,
`1b8e:c003` ainda enumerado. nenhum flash/eMMC/efuse/saveenv/reset/reboot,
nenhum RUN/MODIFY, nenhum `bootm`, nenhum trigger de script com tail
destrutivo. tudo com save/restore/verify. logs e bins em
`reports/round46-same-cycle/`, script em `session_run.py`.

base: `reports/round14-bl33-persist/bl33-37e18000.bin` (base `0x37e18000`).
contexto: round44 (mapa decisoes), round45 (poke bootdelay com restore, efeito
pos-reset NAO PROVADO por RAM volatil).

## baseline (revalidado no inicio e no fim, 5/5 + 6/6)

failed:: `false`, `test 1 = 2`, `test`, `env print foo`, `run foo1234`.
success: `true`, `test 1 = 1`, `echo`, `version`, `help`.
nota: `fastboot oem <cmd>` nesta build retorna so `AMLOGIC`+`OKAY` para tudo,
sem discriminacao. oracle `failed:/success` so existe no bulkcmd Optimus
(`0x34`). `mmc info` FLAKY, nao usar. mread size 8 flaky, cross-check com
`0x02` ou `>=0x40`. so comando completo + drain `0x33`.

## Exp1: FILL 1 par test->true, com restore (PASS)

alvo `0x37f62180` (test idx100 +0x10). high 4B ja zero, 1 par FILL basta.

```text
SAVE    slot = 74 67 e3 37 00 00 00 00 (=0x37e36774)
FILL    (0x37f62180, 0x37e3676c) -> MID = 6c 67 e3 37 00 00 00 00
TRIGGER `test 1 = 2` -> success (antes failed:); `test 1 = 1` -> success
RESTORE FILL (0x37f62180, 0x37e36774) -> 74 67 e3 37 00 00 00 00
RE-TRIGGER `test 1 = 2` -> failed:
```

cadeia fechada sem reboot: FILL -> `cmd_tbl[i].cmd` -> handler legitimo ->
branch diferente -> reply bulkcmd. todo `if test` de
storeboot/switch/init muda junto, antes do primeiro `bl aml_sec_boot_check`.

## Exp2: WRITE 1B avb2 1->0, sem trigger, com restore (PASS)

hunt dinamico nesta sessao: `mread 0x33e18000 32k`, padrao
`active_slot normal avb2 1 baudrate` -> val @ `0x33e1d6e6` (mesmo endereco da
round43; hunt sha `1c5e262d...` identico, layout deterministico neste boot).

```text
SAVE    live 8B = 31 00 62 61 75 64 72 61 ('1' + inicio de 'baudrate')
WRITE   0x01 1B <- 0x30 -> MID = 30 00 62 61 75 64 72 61, vizinho intacto
RESTORE 0x01 1B <- 0x31 -> 31 00 62 61 75 64 72 61, oracle vivo (test 1 = 2 -> failed:)
```

writability do env provada por readback com vizinho intacto. decisao via
script (`run storeboot`, `run upgrade_check` com step=3, `run switch_bootmode`
fora de cold_boot) NAO disparada: todos tem tail destrutivo
(`bootm`/`update`/`recovery`/`fastboot`). trigger seguro de var arbitraria
segue PROVAVEL, nao provado. `test`/`itest` via bulkcmd nao fazem getenv
(expansao `${}` so no parser de script), entao nao servem de oracle direto
para valor de env.

## Exp3: dumps read-only (PASS)

* `cmdtbl_37f60eb0.bin` 5568B live==offline, 0 diffs.
* slots `false/run/fdt/get_rebootmode` nos originais (`64 67 e3 37`,
  `04 ea e5 37`, `2c 85 e2 37`, `78 04 e6 37`).
* `stored_bootdelay 0x37f723d8` = 0 (residuo da entrada via burning; `1` e
  default do boot normal, round44 corrigido pela round45).
* env vivo: `bootdelay=1` @`0x33e1daa0`, `bootcmd=run storeboot` @`0x33e1da88`,
  `active_slot=normal` @`0x33e1d6da`, `boot_part=boot` @`0x33e1d731`,
  `loadaddr=1080000` @`0x33e1e0ef`, `upgrade_step=2` @`0x33e1f1d8`,
  `reboot_mode=fastboot` @`0x33e1e1df`.
* `dtb_header_01000000.bin`: magic `d00dfeed`, totalsize 58280. DTB legivel
  em RAM, nunca poked. validacao propria existe em codigo (`0x37e2a030`:
  `Decrypt dtb: Sig Check`, `check_valid_dts`).

## veredito

CONFIRMADO nesta sessao: redirect mesma-ciclo com oracle (Exp1);
WRITE/FILL env 1:1 com restore e vizinho intacto (Exp2); mapa vivo == offline
(Exp3). NAO PROVADO: trigger seguro de script que observe mutacao de env via
return-code (tails destrutivos bloqueiam); qualquer bypass do
`SMC 0x820000ff` (15 sites, tipo fixo por call site: kernel
`0x100,0x1080000,0x500,7`, boot head `0x40,...,0x1800000,7`, dtb/store
`0x40,...,0x3fe00`, query/efuse `0x10/0x11/0x12/0x20`); `go`/`booti`/`autoscr`
ausentes do cmd_tbl (116 verificados, `autoscr` so em string de
`recovery_from_udisk`, branch morto); `usbboot` so print.

## resto

proximo honesto: achar um script (ou fragmento via `run` + argv) que
ramifique sobre env mutavel e retorne codigo distinto SEM cair em
bootm/update/recovery/fastboot; ou aceitar que oracle de env passa por
redirect, nao por trigger de script. nao repetir `run storeboot` cego, nao
repetir poke bootdelay pos-reset como novidade, nao tocar DTB sem antes
mapear quais subcomandos `fdt` o BL31 cobre.
