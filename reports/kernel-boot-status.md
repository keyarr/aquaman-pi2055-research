# kernel-boot-status — milestones (atualizado)

- M0 (fastboot boot entrega payload): REVOGADO. 4 formatos (raw, ANDROID!+stub,
  ANDROID!+stub 15×, kernel 26 MB, FIT+DTB) retornam em 15-21 s idênticos.
  bytes via `fastboot boot` não entram no caminho de boot neste build
  (ver `fastboot-boot-verdict.md`). a conclusão anterior ("stub executou")
  era reject-reset.
- M1 (payload nosso executa): FALHOU com evidência (M1b: delay 15×, shift zero).
- M2 (reset controlado observável): FALHOU junto (M2 retornou em 19 s; kernel
  real não iniciou — impossível nesse tempo com panic-timeout 5).
- M3 (assinatura persistente/read-only): candidatos: `ro.boot.bootreason`,
  `/sys/fs/pstore` (vazio agora?), ramoops do DTB stock. pendente M1.
- M4 (init/userspace stock): bloqueado em M1. pré-requisito técnico já
  mapeado: kernel precisa aceitar DTB do U-Boot + montar eMMC + vermagic dos
  28 .ko (`vendor-module-compat.md`).
- M5/M6: fora de alcance até M1. sem KernelSU/APatch antes disso.

## primeira falha conhecida (não é no aparelho, é no lab)

nenhuma no aparelho (nada foi rodado nele nesta sessão). no build: tip McMCCRU
com 2 drivers que não compilam/lincam (`VDEC_VP9`, `VIDEOSYNC`), contornados no
`.config` local em direção ao aquaman. detalhe em `kernel-build-env.md`.

## próximo menor experimento

M1a: `adb reboot bootloader` → `oem printenv loadaddr` → `fastboot boot
m1_boot.img` cronometrado → `adb wait-for-device` + bootreason. 1 reboot,
RAM-only, reversível por construção. Travis: se travar sem voltar, power cycle
físico (usuário presente).
