# kernel-baseline — meson64 → aquaman (4.9.113)

base: `meson64_defconfig` de `/tmp/kernel-src/linux-amlogic` (McMCCRU, ancestral,
NÃO source exato — ver `reports/provenance.md`). comparação feita contra o
`.config` expandido (`build-aq/.config`, 4469 opts) vs `aquaman-config`
(4447 opts): **98.12% match, 48 differs, 7 only-A, 29 only-B**.
(a comparação antiga contra o arquivo defconfig cru, 14.05%, media outra coisa:
defconfig é mínimo, `.config` do aparelho é expandido. o número honesto é este.)

## config reconstruído

`meson64_defconfig` + 2 ajustes locais (só no objdir `build-aq/.config`):

| ajuste | motivo |
|---|---|
| `AMLOGIC_MEDIA_VDEC_VP9=n` | tip 3d4ab79e quebrou o driver (`gvs` undeclared em vvp9.c:6894/7820); não compila |
| `AMLOGIC_VIDEOSYNC=y` | `video_sink/video.c:6566` chama `videosync_pcrscr_update` sem `#ifdef`; sem isso o link falha |

ambos os ajustes andam NA DIREÇÃO do aquaman (que não tem VP9 nem VIDEOSYNC —
a árvore Xiaomi tem layout de Kconfig da mídia diferente; ver "desconhecidas").

## 48 differs reais (A=aparelho, B=meson64 expandido)

- SoC/board errado no meson64 (A=n B=y, tirar): `PINCTRL_MESON_TL1`,
  `SND_CODEC_TL1_ACODEC`, `SND_SOC_TAS5805` (TL1 é outro chip), `EXFAT_FS`,
  `NTFS_FS`, `SLUB_DEBUG`.
- perfil TV do aparelho (A=y B=n, manter/por): 31 `USB_*` (rede USB, 3G, cdc…),
  `HID_APPLE`, `KSM`, `NLS_UTF8`, `CRYPTO_LZ4`, `PSTORE_FTRACE`.
- escalares: `HZ` 300 vs 250, `PANIC_TIMEOUT` 1 vs 5 (reboot mais rápido no stock),
  `CC_STACKPROTECTOR_STRONG` A=y / `NONE` B=y (meson64 resolveu para NONE;
  por STRONG no nosso).
- resto é ruído de expansão `=n` (nomes presentes num .config e ausentes no outro).

## only-A (7, tudo a preservar)

`AMLOGIC_DEBUG_ATRACE`, `AMLOGIC_DEBUG_FTRACE_PSTORE`, `AMLOGIC_WATCHPOINT`,
`AMREMOTE_BUTTONSLIGHT`, `BT_WAKE_CONTROL`, `LZ4_COMPRESS`,
`CC_STACKPROTECTOR_STRONG_AMLOGIC=n`.

## only-B com valor real (20, deltas de árvore, aquaman NÃO tem)

15 drivers `AMLOGIC_MEDIA_VDEC_*` (AVS/AVS2/H264×3/H265/MJPEG/MPEG12/MPEG2_MULTI/
MPEG4×2/REAL/VC1) + `VENC_H264/H265` =y, `AMLOGIC_WIFI_DUMMY=m`, `SLABINFO=y`
(EXFAT_* resto é consequência de EXFAT=n). o aparelho tem `MEDIA_VIDEO=y` e
`MEDIA_VIDEO_PROCESSOR=y` + `ENHANCEMENT/VECM/DOLBYVISION`, mas zero VDEC/VENC
e zero VIDEO_SINK no Kconfig. ou a Xiaomi removeu o subtree de decode da árvore
dela, ou renomeou. decode de vídeo no stock é incógnita aberta (vendor modules?).

## desconhecidas / riscos

1. de onde vem o decode de vídeo no stock (M5 depende disso para display real).
2. `HZ=300` + `PREEMPT`? verificado: checar `PREEMPT*` nos dois antes do M4.
3. `LOCALVERSION` vazio nos dois; `vermagic` dos `.ko` do vendor vai ditar o resto
   (Fase 9, pendente — precisa do vendor da eMMC, ainda não extraído).
4. `ARCH_MESON=n / MESON_SM=n` no aparelho com `AMLOGIC_MESON64_VERSION=y`:
   fork vendor, não upstream. nada a fazer, só não "modernizar".

## veredito Fase 3

baseline = meson64 + TV/DVB/CEC/CMA + cauda USB/HID + HZ 300 + PANIC 1 −
(TL1, TAS5805, EXFAT, NTFS) − VDEC/VENC (ausentes no aparelho) + ajustes de
build acima. compila (`Image` 26 MB ARM64 válido). NÃO é o source exato e nem
finge ser: é o ancestral mais próximo que compila com o gcc certo.
