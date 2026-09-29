# vendor-module-compat — .ko stock vs kernel custom (v1, sem root)

extração bloqueada: shell adb (sem root) recebe `Permission denied` em
`/vendor/lib/modules/*.ko` (pull e cat negados pelo SELinux). sem os binários,
sem `modinfo`/vermagic. o que segue é inventário por nome + mapeamento para
CONFIGs, suficiente para definir o feature set mínimo. revisitar com root.

## inventário (`ls -R /vendor/lib/modules`, nomes via erro SELinux — 28+1)

- decode/vpu: `amvdec_avs/av2/h264/h264mvc/h265/mh264/mjpeg/mmjpeg/mmpeg12/
  mmpeg4/mpeg12/mpeg4/real/vc1/vp9`, `decoder_common`, `encoder`,
  `stream_input`, `firmware`, `media_clock`, `vpu`, `aml_hardware_dmx`
- gpu: `mali`
- conectividade: `rtl8821cs` (wifi SDIO), `aml_sdio`, `sdio_bt` (BT em uart_A)
- misc: `ddr_window_64`, `w1`
- fora de modules/: `/vendor/lib/optee.ko` (TEE)

## o que isso explica

aquaman-config não tem NENHUM `AMLOGIC_MEDIA_VDEC_*` (ver kernel-baseline.md):
porque decode inteiro é módulo vendor, não built-in. o kernel custom para M5
precisa, no mínimo: `ION`+CMA/reserved-memory compatível, `VIDEOBUF2`,
`SYNC`/`SW_SYNC`, `AMLOGIC_MEDIA_VIDEO/PROCESSOR`, v4l2-core, e vermagic
idêntico (`4.9.113 SMP preempt mod_unload aarch64` + LOCALVERSION vazio).
wifi/BT idem: `CFG80211`, `BT`, `TTY`, sdio stack + `MMC`.

## feature set mínimo (para validar quando houver root)

1. `uname -r` = `4.9.113` (LOCALVERSION vazio + AUTO=n no nosso build, ou o
   sufixo exato do stock);
2. `SMP PREEMPT` iguais (stock: `#1 SMP PREEMPT`);
3. `MODULE_UNLOAD`, `MODVERSIONS=n` (stock quase certamente sem modversions —
   checar via `strings amvdec_h264.ko | grep vermagic` quando der);
4. mesmos `ION`, `DMA_SHARED_BUFFER`, `SYNC` da baseline;
5. mali: versão do driver no kernel tem que casar com o userspace
   (`/vendor/lib/egl/*`); mismatch aqui = sem display acelerado mesmo com
   kernel bootando.

## bloqueado até root ou dump descriptografado

vermagic exato, `depends` (modules.dep legível? também negado — checar),
símbolos (`Module.symvers` não existe sem source), ABI de `mali`/`optee`.
