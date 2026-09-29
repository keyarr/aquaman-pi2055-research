# config-diff — aquaman-config vs defconfigs

tool: tools/config_fingerprint.py (stdlib, parse CONFIG_X=val + "# CONFIG_X is not set" como n, union/match/%/only/differ, --rank)
raw: reports/config-diff/aquaman-vs-meson64.txt, aquaman-vs-smarthome.txt, aquaman-vs-defconfig.txt, ranking.txt

## numeros

aquaman-config: 4447 opcoes parseadas (1650 CONFIG_*=, 2797 not-set). header "Linux/arm64 4.9.113".

| candidato | opts | union | match | % | differ | only-A (so aparelho) | only-B (so repo) |
|---|---|---|---|---|---|---|---|
| McMCCRU meson64_defconfig | 631 | 4447 | 625 | 14.05% | 6 | 3816 | 0 |
| MiTV dangal meson64_defconfig | 633 | — | — | 14.07% | — | — | — |
| meson64_smarthome_defconfig | 547 | 4452 | 526 | 11.81% | 16 | 3905 | 5 |
| defconfig generico | 465 | 4599 | 119 | 2.59% | 194 | 4134 | 152 |

leitura correta: % baixo porque defconfig e minimo e .config e expandido. o que importa: meson64_defconfig e 100% subset do aquaman (0 only-B, 6 differs). smarthome fica atras. generico e irrelevante.

## 6 differs meson64 -> aquaman (unicas divergencias reais)

AMLOGIC_PINCTRL_MESON_TL1 y->n, AMLOGIC_SND_CODEC_TL1_ACODEC y->n, AMLOGIC_SND_SOC_TAS5805 y->n, EXFAT_FS y->n, NTFS_FS y->n, PANIC_TIMEOUT 5->1

## smarthome: o que ele tira (16 differs + 5 only-B)

tira TV: AMAUDIO, ATV_DEMOD, DTV_DEMOD, HDMITX, CVBS_OUTPUT ausentes; ANDROID_LOGGER n->y etc. confirma que aquaman e variante TV/box, nao smarthome-audio.

## so no aparelho (amostra do que importa)

- 85 CONFIG_AMLOGIC_* presentes no aquaman e ausentes no meson64, maioria =n ou extras TV: AO_CEC=y, CMA=y, MEMORY_EXTEND=y, DVB=y + DVB_COMPAT=y, VIDEOIN_MANAGER=y
- stack DVB completa ausente nos defconfigs: DVB_CORE, LGDT3305/3306A, MB86A20S, SI2165, TDA18271C2DD, DVB_NET, VIDEOBUF_DVB
- resto (USB_GSPCA_*, SND_*, SENSORS_*, WLAN_VENDOR_*) e ruido de expansao =n, normal em .config vs defconfig

## fingerprint do aparelho (valores exatos)

AMLOGIC_SEC=y, AMLOGIC_TEE=y, AMLOGIC_EFUSE=y (WRITE_VERSION_PERMIT=n)
KPROBES=n (HAVE_KPROBES=y), KALLSYMS=y + ALL=y + BASE_RELATIVE=y, KEXEC=n, IKCONFIG=y + PROC=y
MODULES=y, BPF=y + SYSCALL=y + JIT=n, SECCOMP=y + FILTER=y
DM_VERITY=y + FEC=y, AVB=y, ANDROID=y (binder/hwbinder/vndbinder, LOW_MEMORY_KILLER=y, PARANOID_NETWORK=y, LOGGER=n)
SELINUX=y, MAGIC_SYSRQ=y, LOCALVERSION="" + AUTO=y, CROSS_COMPILE="", OVERLAY_FS=n
ARCH_MESON=n / MESON_SM=n / RESET_MESON=n mas AMLOGIC_MESON64_VERSION=y (fork vendor, nao upstream)

## conclusao

meson64_defconfig e a base. aquaman = meson64 + TV/DVB/CEC/CMA + cauda de =n. dangal empata (14.07% vs 14.05%), entao similaridade de config sozinha nao prova nada alem de "mesmo vendor drop P". nao chamar de match exato.
