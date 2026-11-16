# round56 inert FDT identity (hardware run, 2026-10-02)

## Objective

Caso B do round55: testar identidade do FDT, nao SELinux. Trocar um campo
inerte que hoje concorda (`androidboot.wificountrycode` US->ZZ, mesmo
comprimento, sem efeito de boot) via `setenv`+`run storeargs`, verificar por
fresh-ptr htab + oracle, depois o par E4 `imgread`+`bootm`, oraculo
`getprop ro.boot.*`.

## Result

```text
REFUTED for transport, PROVEN for identity: inert ZZ reverted to US (whole-string revert, not selective)
```

Pre-boot (fresh boot via `fastboot oem update 5000`, re-hunted, nada reusado):
htab obj `0x37ee7278` table `0x33e2d650` size `0x209` filled `0x4a`.
`test 1=1 -> success`, `1=2 -> failed:`, `test ${wifi_ccode}=US -> success`.
Baseline htab `bootargs` 832 B sha `c5a4b5e3` (`enforcing`/`US`/`fastboot`).
`setenv wifi_ccode ZZ -> success`, `test ZZ -> success`, `test US -> failed:`.
`run storeargs -> success`, fresh entry514 data moveu
`0x33e0baf0 -> 0x33e0e4b0`, 832 B sha `e1e32443` com
`androidboot.wificountrycode=ZZ`, `androidboot.selinux=enforcing`,
`androidboot.reboot_mode=fastboot`. Assert ZZ+enforcing PASS.

`imgread kernel boot 0x1080000 -> success` (checado ANTES, abortaria se nao).
`bootm 0x1080000 -> USBError(19)` disconnect (assinatura E4). Sessao acabou
por desenho.

Android voltou stock. Oraculo: `ro.boot.wificountrycode=US`,
`ro.boot.selinux=enforcing`, `ro.boot.reboot_mode=normal`,
`getenforce=Enforcing`. Full `getprop | grep ro.boot` salvo.

Leitura: o inerte reverteu junto com `fastboot->normal`. Nao foi rewrite
seletivo de selinux. Foi a string inteira / FDT perdido-substituido.
Parar de testar selinux; o problema e identidade do blob, nao filtro de campo.

## Artifacts

* `reports/round56-inert-transport/session_run.log`
* `htab_bootargs_baseline_832.bin` (c5a4b5e3, stock)
* `htab_bootargs_ZZ_832.bin` (e1e32443, o que o bootm recebeu)
* `table_baseline.bin` (a1576484), `table_after_setenv.bin`, `table_after_storeargs.bin`
* `htab_obj_37ee7278.bin`
* `getprop_ro_boot.txt`, `getprop_ro_boot_wificountrycode.txt`, `getprop_ro_boot_selinux.txt`, `getprop_ro_boot_reboot_mode.txt`, `getenforce.txt`

RAM-only, sem saveenv/flash/erase/update/recovery. Marcador morreu com bootm.
Device healthy stock Android.

## Validation

* `python3 tools/run_tests.py` -> `126 tests, OK`.
* `git diff --check` clean.
