# BL33 round 44: quais decisões de boot mudam com as primitivas já confirmadas

date: 2026-10-02. offline + síntese de live anterior. nenhum write novo,
nenhum RUN/MODIFY/reset/update/flash nesta sessão. nenhuma tentativa de
bypass do secure boot.

base:
- imagem `reports/round14-bl33-persist/bl33-37e18000.bin` (base 0x37e18000,
  `[0x37e18000,0x37ff0000)`, sha256 `664fb34a…`), disasm capstone nesta sessão.
- live herdado: round39 (WRITE 0x01), round40 (consumo duplo), round41 (mapa
  116 cmds), round42 (false->true), round43 (test->true, env print->true,
  FILL 0x03, RUN wedge, env vivo em `reports/round43-campaign/hunt_33e18000_32k.bin`).
- referência: round35 (mode 7 = `setenv bootdelay -1`, gate `cmn w19,#1`).

pergunta da sessão: qual a menor alteração reversível em RAM que muda o
comportamento do boot do BL33 antes do secure boot?

resposta: FILL 1 par (ou WRITE 8B) no slot `test` (`0x37f62180` low
`0x74->0x6c`, high já zero) redirecionando `test 0x37e36774` para
`true 0x37e3676c`. 1 byte efetivo, oracle `test 1 = 2` failed:->success,
restore confirmado (P2 round43). todo `if test` de storeboot/switch/init
muda junto, antes do primeiro `bl aml_sec_boot_check`.

## 1. Exp1: bootdelay como primeiro gate

`main_loop 0x37e22328`: `preboot` (0x37e22354) roda antes de
`bootdelay_process 0x37e24480` (0x37e22358), que roda antes de
`autoboot_command 0x37e244dc` (0x37e2235c).

`bootdelay_process 0x37e24480` (disasm nesta sessão):
`0x37e2448c add x0,#0xfbb` ("bootdelay") -> `bl env_get 0x37e58920` ->
`cbz` -> `simple_strtoul 0x37eac374` base 10 -> `str w19,[0x37f723d8]`.
sem env, `0x37e244b0 mov w19,#1`.

`autoboot 0x37e244dc`:
`0x37e244f8 ldr w19,[0x37f72000+0x3d8]` -> `0x37e24500 cmn w19,#1` ->
`0x37e24504 b.eq 0x37e245f4` (skip bootcmd, cai em cli_loop).

| campo | endereço | valor original | consumidor | instrução que decide |
|---|---|---|---|---|
| `bootdelay` env vivo | `0x33e1daa0` (`hunt_33e18000_32k.bin`) | `"1"` | `bootdelay_process` | `0x37e24498 cbz` / strtoul / default `mov w19,#1` |
| `bootdelay` default rodata | `0x37eb65b6`, nome `0x37ebffbb` | `"1"` | idem | idem |
| `stored_bootdelay` u32 | `0x37f723d8` | `1` (`-1` = `0xffffffff` pós mode 7) | `autoboot_command` | `0x37e24500 cmn` + `0x37e24504 b.eq` |
| `bootcmd` vivo | `0x33e1da88` | `"run storeboot"` | tail do autoboot (`b run_command_list`) | `0x37e24508 cbz x21` |

copiado (string -> u32), não direto. escritor do `-1`: `0x37e60618`
(`setenv bootdelay,"-1"`, só mode 7). formato: ASCII decimal.
status: código CONFIRMADO offline; valor vivo `1` CONFIRMADO no hunt dump.
poke NÃO PROVADO (não executado).

## 2. Exp2: oracle de mudança de fluxo

bulkcmd 512B já discrimina pelo retorno, sem printenv/RUN/MODIFY/reset.
baselines round43, mesma sessão:

```
failed: : false, `test 1 = 2`, `test`, `env print foo`, `run foo1234`, desconhecido
success : true, `test 1 = 1`, echo, version, help, ?, printenv, `env print`
```

par recomendado: `test 1 = 2` vs `test 1 = 1`. binário, sem output, sem
storage. `false`/`true` é o reserva (round42). `echo`/`version`/`help`
descartados como discriminador: todos `success`. `mmc info` FLAKY, não usar.
`get_rebootmode` como oracle: PROVÁVEL, sem baseline anotado.

## 3. Exp3: reboot_mode

leitor `0x37e60478`: `ldr SD_CFG15 0xc810023c` (`0x37e604a4/a8/ac`),
`ubfx [15:12]` (`0x37e604b0`), jump via tabela `0x37ebe910`
(`ldrb` + `add sxtb #2` + `br`). 15 entradas (round35): 0 cold_boot,
1 normal, 2 factory_reset, 3 update, 4 fastboot, 5 suspend_off, 6 hibernate,
7 bootloader, 8 shutdown_reboot, 9 rpmbp, 10/14 recovery_quiescent,
11 crash_dump, 12 kernel_panic, 13 watchdog_reboot, >14 charging.

`switch_bootmode` (`0x37eb6eab`) tem 6 branches; `bootloader` não é um:

```
7 bootloader -> nenhum branch -> só setenv bootdelay -1 -> skip bootcmd -> cli_loop
4 fastboot   -> storeargs; fastboot (gadget 18d1:0d02)
0 cold_boot  -> storeargs, segue bootcmd
2/3          -> recovery_from_flash / update
```

RAM equivalente: env vivo `reboot_mode` (ex. valor `0x33e1e1df` naquela
sessão). heap `0x33e1xxxx`, varia por boot; re-huntar com
`mread 0x33e18000 32k` + grep. nunca escrever `0xc810023c`.

## 4. Exp4: storeboot

script rodata `0x37eb71f2` (vivo na arena). offsets live dessa sessão:

| var | valor vivo | escritor | consumidor/comparação | efeito |
|---|---|---|---|---|
| `active_slot` | `0x33e1d6da`=`normal` | `get_valid_slot 0x37e2bb7c` | `test != normal`, `= _a`, `= _b` (`test 0x37e36774`) | `slot_suffix`, `root=mmcblk0p23/24` |
| `avb2` | `0x33e1d6e6`=`1` | `get_avb_mode 0x37e2b820` | `test = 0` | escolhe `root=` quando 0 |
| `system_mode` | sem escalar no dump | `get_system_as_root_mode 0x37e2b7ac` (`setenv 0/1`, strs `0x37ec2dcd`,`0x37eccb38`,`0x37ecdd94`) | `test = 1` no head | `fs_type ro…` + `run storeargs` |
| `boot_part` | `0x33e1d731`=`boot` | default | `imgread kernel ${boot_part} ${loadaddr}` (`0x37e356d0`) | qual partição carrega |
| `loadaddr` | `0x33e1e0ef`=`1080000` | default | `imgread` dst + `bootm` src (`0x37e24c00`) | onde cai / de onde boota |
| `bootargs` | `0x33e1d73f` 832B | `storeargs` + `bootm` | concatenação | cmdline do kernel |
| `upgrade_step` | `0x33e1f1d8`=`2` | estado | `itest == 3` (`0x37e2b348`) em `upgrade_check`/`recovery_from_flash` | `==3` -> `run update` |

`test`/`itest` é o ponto comum. nada modificado aqui.

## 5. Exp5: redirects com objetivo de boot

consumer `0x37e5f6e8 ldr x4,[x19,#0x10]` + `0x37e5f6fc blr x4` (64-bit).

| candidato | original -> alt | slot | efeito | risco | oracle | status |
|---|---|---|---|---|---|---|
| `test` idx100 | `0x37e36774`->`true 0x37e3676c` | `0x37f62180` | todo `if test` vira true | baixo | `test 1 = 2` -> success | CONFIRMADO P2 |
| `run` idx84 | `0x37e5ea04`->`true` | `0x37f61e80` | `run` vira no-op | médio (quebra boot se sem restore) | `run foo1234` -> success | PROVÁVEL, não executado |
| `get_rebootmode` idx51 | `0x37e60478`->`true` | `0x37f61850` | `reboot_mode`/`bootdelay` congelam | médio | sem baseline | NÃO PROVADO |
| `fdt` idx49 | `0x37e2852c`->`true` | `0x37f617f0` | DTB edit vira no-op | baixo sozinho | fraco | NÃO PROVADO |

## 6. Exp6: barreira final

`aml_sec_boot_check 0x37e19ea8` = `mov x0,#0x820000ff` + `smc #0 0x37e19ed8`.
censo de `bl` até ele (disasm sessão): bootm 2 (`0x37e24cf0`,`0x37e24f90`),
unpackimg/imgread 3 (`0x37e35ec4`,`0x37e3623c`,`0x37e36340`), fdt 2,
store 4, query/efuse 4. `usbboot 0x37e371f0` 0 calls (só descriptor/print,
não boota kernel). `ext4load`/`fatload` 0 calls no load, mas não pulam para
kernel; boot exige `bootm`.

```
caminho            carrega imagem?  passa pelo SMC?  evidência
bootm              sim              sim             2 bl + smc 0x820000ff
unpackimg/imgread  sim (0x37e351f8) sim             3 bl
fdt                não (edita DTB)  sim (subpath)   2 bl
store              sim              sim             4 bl
ext4load/fatload   sim (file->RAM)  não no load, sim no boot via bootm  stubs 8B
usbboot            não              não             só print
update/usb_burn    flash, não boot  n/a             fora
```

nenhum caminho carrega-e-executa sem `aml_sec_boot_check`. verificação
estática; `bootm` nunca executado live.

## 7. ranking

### Caminho 1 — CONFIRMADO

```
FILL 1 par (ou WRITE 8B) -> test 0x37f62180 -> true
  -> ifs de storeboot/switch/init decidem diferente -> antes do SMC
  -> oracle failed:->success -> restore -> failed:
```

### Caminho 2 — PROVÁVEL

```
WRITE/FILL -> env vivo 0x33e1xxxx ou slot run/get_rebootmode
  -> script/boot decision muda antes de bootm
```

localização read-only CONFIRMADA; poke NÃO PROVADO.

### Caminho 3 — limite, BLOQUEADO

```
WRITE/FILL -> RUN 0x05 -> wedge USB (T7/T8 round43)
           -> MODIFY 0x04 -> sessão morta
handler -> SMC 0x820000ff -> secure boot segura
```

sem exec arbitrária, sem persistência (reboot limpa).

## 8. ledger

CONFIRMADO (hardware): WRITE 8/16/64B, FILL espalhado, redirects
false/test/env-print->true + restore duplo, oracle failed:/success, pagetable
RWX idx0/1, cmd_tbl live==offline, env vivo localizado (`bootdelay 1`,
`bootcmd run storeboot`, `upgrade_step 2`, `active_slot normal`, `avb2 1`).
CONFIRMADO (código): gate `cmn/b.eq`, tabela `0x37ebe910`, scripts
storeboot/switch/init/upgrade_check, barreira `bootm->sec_check->SMC`.
PROVÁVEL: `test->true` muda decisão de boot (mecanismo provado, `run
storeboot` nunca executado live por risco); env poke muda boot.
NÃO PROVADO: bypass do SMC, exec via RUN, qualquer persistência.

repro offline:
`python3 -c` + capstone sobre o bin (bootdelay_process, autoboot, do_bootm,
sec_check, get_rebootmode); `grep` do hunt `reports/round43-campaign/hunt_33e18000_32k.bin`.
regras: só comando completo + drain `0x33`; `mread` 8 flaky (usar `0x02` ou
`>=0x40`); 0x04/0x05 por último ou nunca sem UART; nunca saveenv/flash.
