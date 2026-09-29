# kernel-smoke-test — M1: EXECUTADO, FALHOU (payload nunca executa)

status: M1a, CTRL, M1b, M2 e E1 rodados (ver `fastboot-boot-verdict.md`).
delay 15× sem shift no tempo de retorno; kernel real de 26 MB retornando em
19 s. conclusão: bootm nunca lê os bytes do download neste build.

## por que M1 existe

reboot-ao-Android após payload raw é o outcome de REJEIÇÃO (`Wrong Image
Format` → `do_reset`), não prova de execução (ver `fastboot-kernel-path.md`
§3). M1 troca "reset rápido" por "delay + reset": se o reboot atrasar, o
payload executou. se continuar rápido, foi rejeitado (ou §2 do outro relatório
mordeu: `load_addr` vs download addr).

## artefato

`m1_boot.img` (4096 bytes, gerado por `tools/mk_m1_boot.py` de
`tools/m1_delay_stub.S`, Linaro 6.3.1):

- header `ANDROID!` v0, `kernel_addr 0x1080000`, `page 2048`, sem ramdisk/second;
- kernel de 112 bytes = header Linux ARM64 válido (`b +0x40`, magic `0x644d5241`
  @0x38, `objdump` confere) + loop aninhado 4000×1M (~segundos, duas ordens de
  grandeza acima do reject) + `HVC PSCI SYSTEM_RESET` com o mesmo fid do stub
  original (`0x84000009`) + `wfi` de fallback.

## protocolo (1 reboot, RAM-only, nada persistente)

```sh
adb reboot bootloader            # único reboot da sessão
fastboot oem printenv loadaddr   # read-only; resolve §2 (load_addr real)
time fastboot boot m1_boot.img   # cronometrar até reenumeração USB
adb wait-for-device
adb shell getprop ro.boot.bootreason  # comparar com baseline stock
```

## leitura do resultado

| observado | veredito |
|---|---|
| reboot em ~1-2 s (igual ao stub raw) | rejeitado OU bootm leu outro endereço (§2). checar `loadaddr` e repetir |
| reboot em ~10-60 s | **M1 PASS**: Linux-Image-path executou até o payload |
| não volta (trava) | executou e o HVC não resetou (EL inesperado?) → power cycle físico, revisar stub para SMC Fid 32-bit ou `wfi`-only + timeout |

## baseline para comparar

antes do M1, registrar 1 boot stock: tempo `reboot`→`device` e
`ro.boot.bootreason`. sem isso o "atraso" não tem referência.

## o que M1 NÃO prova

que Linux boota (M2+), que o DTB serve (M4), nem que `load_addr` está certo em
geral. só que o caminho bootm→payload executa código nosso via `fastboot boot`.
