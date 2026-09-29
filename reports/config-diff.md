# config-diff — aquaman-config vs defconfigs

tool: tools/config_fingerprint.py (stdlib, parse CONFIG_X=val + "# CONFIG_X is not set" as n, union/match/%/only/differ, --rank)
raw: reports/config-diff/aquaman-vs-meson64.txt, aquaman-vs-smarthome.txt, aquaman-vs-defconfig.txt, ranking.txt

## numbers

aquaman-config: 4447 parsed options (1650 CONFIG_*=, 2797 not-set). Header "Linux/arm64 4.9.113".

| candidate | opts | union | match | % | differ | only-A (device only) | only-B (repo only) |
|---|---|---|---|---|---|---|---|
| McMCCRU meson64_defconfig | 631 | 4447 | 625 | 14.05% | 6 | 3816 | 0 |
| MiTV dangal meson64_defconfig | 633 | — | — | 14.07% | — | — | — |
| meson64_smarthome_defconfig | 547 | 4452 | 526 | 11.81% | 16 | 3905 | 5 |
| generic defconfig | 465 | 4599 | 119 | 2.59% | 194 | 4134 | 152 |

correct interpretation: low % because defconfig is minimal while .config is fully expanded. What matters: meson64_defconfig is a 100% subset of aquaman (0 only-B, 6 differs). Smarthome falls behind. Generic is irrelevant.

## 6 differs meson64 -> aquaman (only real divergences)

AMLOGIC_PINCTRL_MESON_TL1 y->n, AMLOGIC_SND_CODEC_TL1_ACODEC y->n, AMLOGIC_SND_SOC_TAS5805 y->n, EXFAT_FS y->n, NTFS_FS y->n, PANIC_TIMEOUT 5->1

## smarthome: what it removes (16 differs + 5 only-B)

removes TV features: AMAUDIO, ATV_DEMOD, DTV_DEMOD, HDMITX, CVBS_OUTPUT absent; ANDROID_LOGGER n->y etc. Confirms that aquaman is a TV/box variant, not smarthome-audio.

## device-only options (sample of what matters)

- 85 CONFIG_AMLOGIC_* present in aquaman and absent in meson64, mostly =n or TV extras: AO_CEC=y, CMA=y, MEMORY_EXTEND=y, DVB=y + DVB_COMPAT=y, VIDEOIN_MANAGER=y
- complete DVB stack absent in defconfigs: DVB_CORE, LGDT3305/3306A, MB86A20S, SI2165, TDA18271C2DD, DVB_NET, VIDEOBUF_DVB
- remainder (USB_GSPCA_*, SND_*, SENSORS_*, WLAN_VENDOR_*) is =n expansion noise, expected when comparing .config against defconfig

## device fingerprint (exact values)

AMLOGIC_SEC=y, AMLOGIC_TEE=y, AMLOGIC_EFUSE=y (WRITE_VERSION_PERMIT=n)
KPROBES=n (HAVE_KPROBES=y), KALLSYMS=y + ALL=y + BASE_RELATIVE=y, KEXEC=n, IKCONFIG=y + PROC=y
MODULES=y, BPF=y + SYSCALL=y + JIT=n, SECCOMP=y + FILTER=y
DM_VERITY=y + FEC=y, AVB=y, ANDROID=y (binder/hwbinder/vndbinder, LOW_MEMORY_KILLER=y, PARANOID_NETWORK=y, LOGGER=n)
SELINUX=y, MAGIC_SYSRQ=y, LOCALVERSION="" + AUTO=y, CROSS_COMPILE="", OVERLAY_FS=n
ARCH_MESON=n / MESON_SM=n / RESET_MESON=n but AMLOGIC_MESON64_VERSION=y (vendor fork, not upstream)

## conclusion

meson64_defconfig is the baseline. aquaman = meson64 + TV/DVB/CEC/CMA + =n tail. dangal ties (14.07% vs 14.05%), so config similarity alone proves nothing beyond "same vendor drop P". Do not call it an exact match.
