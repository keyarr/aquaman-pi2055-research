# aquaman-dts-port — mainline 2025 → 4.9 downstream, node by node

sources, in the order they were used:

1. `aquaman-config` (4447 options extracted from the device) — what drivers
   actually exist on the stock build.
2. mainline `meson-gxl-s805y-xiaomi-aquaman.dts` (merged 2025-05, Ferass El
   Hafidi, based on p241) — the only aquaman DTS in existence anywhere.
3. `arch/arm64/boot/dts/amlogic/gxl_p241_1g.dts` + `mesongxl.dtsi` from
   McMCCRU 3d4ab79e, now at `.src/linux-amlogic` — the 4.9 target tree.
   (the old temporary clone path was on tmpfs and did not survive
   the session; all three source trees were re-cloned into `.src/`, which is
   gitignored. see `reports/kernel-build-env.md`.)
4. `vendor-module-compat.md` inventory (now with vermagic and real binaries,
   see `reports/vendor-modules.md`) — proves which hardware needs a `.ko`
   that the DTS alone cannot bring up.

**the headline: this DTS is not needed for anything currently reachable.**
`fastboot boot` hands the kernel the DTB U-Boot already holds
(`fastboot-kernel-path.md` §4.5), and every `fastboot boot` path is blocked
at BL31 anyway (`fastboot-memory-flow.md` §8). a reconstructed DTS only pays
off once a custom kernel actually boots, which is currently impossible.

it is worth writing down anyway, because it is the only artifact here that
documents the hardware. and because if the SMC blocker is ever lifted, the DTS
is the next thing needed.

## why the mainline file cannot just be copied

| mainline (2025) | 4.9 downstream (McMCCRU) |
|---|---|
| `meson-gxl-s805y.dtsi` + `meson-gxl.dtsi` | `mesongxl.dtsi` only (1440 lines, own layout) |
| `clkc` + `CLKID_MPLL*`, `clk81` absent | `clkc` with its own id set, no MPLL ids |
| `mmc-pwrseq-simple`, `mmc-pwrseq-emmc` | no pwrseq concept; power is `power_on_pin` in the `sd`/`emmc` child node |
| `regulator-fixed` nodes feeding `vmmc-supply` | no supply properties; voltages in `ocr_avail` |
| `gpio-leds` with `color`/`function` | plain gpio-leds, no color/function |
| `hdmi-connector` + `hdmi_tx` + endpoint graph | `amhdmitx` + `vend_data` + `tvmode` table, no endpoint |
| `amlogic,gx-sound-card` with dai-links | `aiu`/`ao-i2s` + `hdmitx` codec pairing, own bindings |
| `pwm-clock` for the 32 kHz WiFi clock | `pwm_ef` configured inline, no pwm-clock driver |
| no `amlogic-dt-id` | **`amlogic-dt-id` mandatory** — U-Boot selects the DTB by it |
| `memory@0 reg = <0 0 0 0x40000000>` | `linux,usable-memory = <0x0 0x100000 0x0 0x3ff00000>` + big `reserved-memory` |

the `amlogic-dt-id` line is the load-bearing one. without it U-Boot's
`get_multi_dt_entry` cannot pick a DTB at all.

## mapping table

status legend: **CONFIRMED** = mainline DTS with a driver author and on-device
test; **DERIVED** = present in mainline, format 4.9 must be rewritten;
**INHERITED** = p241's value kept, no aquaman-specific evidence either way;
**TODO** = cannot be written without inventing values.

### memory / reserved-memory

| mainline node | 4.9 equivalent | driver/Kconfig | status | notes |
|---|---|---|---|---|
| `memory@0 reg 0x0+0x40000000` | `linux,usable-memory = <0x0 0x100000 0x0 0x3ff00000>` | `CONFIG_ARCH_MESON64` (vendor fork) | CONFIRMED (1 GiB) | 1 GiB agrees with `MemTotal 1004412 kB`; p241's 0x100000 hole is the p241-specific part |
| — | `reserved-memory` (ion, ramoops, secmon, di_cma, vdin1_cma, codec_mm, logo) | `CONFIG_AMLOGIC_ION=y`, `CONFIG_PSTORE_RAM` | INHERITED | p241's layout; sizes tuned for p241's use, probably wrong for aquaman |
| `mmc-pwrseq-emmc` reset BOOT_9 | folded into the `emmc` child: `hw_reset = <&gpio BOOT_9 GPIO_ACTIVE_HIGH>` | `CONFIG_AMLOGIC_MMC=y` | DERIVED | p241 already does this, and mainline's own reset-gpios is the same pin |
| `regulator-fixed` × 5 | `ocr_avail` in the `sd`/`emmc` child + direct pinctrl | `CONFIG_AMLOGIC_MMC=y` | DERIVED | 4.9 has no supply graph for these |

### eMMC

| mainline | 4.9 | driver/Kconfig | status |
|---|---|---|---|
| `&sd_emmc_c` (8-bit, HS200, 200 MHz, `sd_emmc_c` @ 0xd0074000) | `sd_emmc_c: emmc@d0074000` identical reg/irq | `CONFIG_AMLOGIC_MMC=y` | INHERITED (near-verbatim; mainline and p241 agree) |
| `mmc-hs200-1_8v`, `mmc-ddr-1_8v` | same properties, p241 also has them | — | INHERITED |

this is the highest-confidence node in the whole port. mainline and p241 use the
same register base, the same 8-bit width, the same 200 MHz, the same HS200+1.8V.
aquaman is an eMMC board, and so is p241.

### SDIO / Wi-Fi

| mainline | 4.9 | driver/Kconfig | status |
|---|---|---|---|
| `&sd_emmc_b` sdio 4-bit, `mmc-pwrseq-simple` reset GPIOX_6, `pwm-clock` 32 kHz | `sd_emmc_b: sd@d0072000` `card_type = <3>` (sdio), pwrseq via inline `power_on_pin`/pinctrl | `CONFIG_AMLOGIC_MMC=y` + `CONFIG_AMLOGIC_WIFI=y` | DERIVED |
| `wifi@1 { reg = <1> }` | **no equivalent** — 4.9 has no per-function child for sdio | — | TODO |

`CONFIG_AMLOGIC_WIFI=y` in stock config. but the Wi-Fi chip is **RTL8821CS**
(`rtl8821cs.ko`, 4.7 MB, Realtek, `srcversion=F2CB4D2C35C53BE3A522AD8`, aliases
`sdio:c*v024CdC821*` / `sdio:c*v024CdB821*`). Realtek is not in this tree. a
DTS entry gets the SDIO host up; the chip needs the vendor module. **the DTS
alone cannot bring up Wi-Fi** — same conclusion the old report reached, now
with the module binary in hand as proof.

the 32 kHz clock: mainline uses `pwm-clock` on `pwm_ef`. 4.9 has no `pwm-clock`
driver, so it becomes a p241-style inline `pwm_channel2_conf` entry on `pwm_ef`
with `MESON_PWM_2`, period 30500, duty 15250. that reproduces 32.768 kHz
(30500/15250 = 2, and 15250/32768 ≈ 0.4655 duty). it is a plausible
translation but it is a translation, not a copy.

### Bluetooth UART / console UART

| mainline | 4.9 | driver/Kconfig | status |
|---|---|---|---|
| `&uart_A` rtscts, `serial1 = &uart_A` | `uart_A: serial@c11084c0` | `CONFIG_SERIAL_AMLOGIC` (under `CONFIG_SERIAL_CORE=y`) | INHERITED (p241 already has uart_A, alias serial3) |
| `&uart_AO` console, `stdout-path = "serial0:115200n8"` | `uart_AO: serial@c81004c0` | `CONFIG_SERIAL_EARLYCON=y`, `CONFIG_SERIAL_CORE_CONSOLE=y` | INHERITED (identical reg 0xc81004c0) |
| `uart-has-rtscts` | `uart_A` needs the CTS/RTS pinctrl group | — | TODO (p241 has no rtscts group; needs the pin group named, not guessed) |

`CONFIG_BT=y`, `CONFIG_BT_HCIUART=y`, `CONFIG_BT_HCIUART_H4=y` all present, and
`CONFIG_BT_HCIBTSDIO` explicitly **not** set. so BT is expected over UART H4 on
`uart_A`, which matches the mainline comment "This is connected to the Bluetooth
module". the driver is `sdio_bt.ko` (vendor), 13 versioned imports — a thin
shim. note mainline itself warns "there's no driver for the Bluetooth module of
some variants yet", so the module doing the real work is the vendor one.

### HDMI / CEC

| mainline | 4.9 | driver/Kconfig | status |
|---|---|---|---|
| `&hdmi_tx` + `hdmi-connector` | `amhdmitx: amhdmitx` + `vend_data` (vendor_name/vendor_id/product_desc) + `tvmode` table | `CONFIG_AMLOGIC_HDMITX=y` | DERIVED |
| `hdmi-supply = <&vcc_5v>` | no supply binding; pin group `hdmitx_hpd` + `hdmitx_ddc` | — | INHERITED |
| `&cec_AO` | `aocec: aocec` (reg 0xc810023c + 0xc8100000, irq 199) | `CONFIG_AMLOGIC_AOCEC=y`, `CONFIG_AMLOGIC_CEC=y` | INHERITED |
| — | `vend-data` product_desc "MBox Meson Ref" | — | TODO (p241's placeholder; aquaman's real OUI/desc is unknown) |

`CONFIG_AMLOGIC_HDMITX=y`, `CONFIG_AMLOGIC_AOCEC=y`, `CONFIG_AMLOGIC_CEC=y` in
the stock config, so the drivers exist. what `vend_data` should say for aquaman
is cosmetic (HDMI vendor string in the OSD/EDID) but unknown, so: TODO.

### USB

| mainline | 4.9 | driver/Kconfig | status |
|---|---|---|---|
| `&usb` dr_mode otg, `vbus-supply` | `usb2_phy`/`usb3_phy` (`amlogic-new-usb2`/`-3`) + controller with `clock-src` | `CONFIG_USB_DWC3`, `CONFIG_USB_PHY_AMLOGIC_GXL`? | INHERITED |
| — | p241's 31-option `USB_*` tail | — | TODO (p241's exact set is not aquaman's; stock config has 31 `USB_*` =y that meson64 lacks — see `kernel-baseline.md`) |

### GPIO / LED

| mainline | 4.9 | driver/Kconfig | status |
|---|---|---|---|
| `leds` `GPIODV_24` active-high, default on, `panic-indicator` | `gpio-leds`, no `color`/`function`; `panic-indicator` needs `CONFIG_PANIC_ON_OOPS`-adjacent support in 4.9 | `CONFIG_LEDS_GPIO` | DERIVED |
| — | pin group for GPIODV_24 | — | TODO (p241 has no LED node at all; the group must be named) |

### ADC

| mainline | 4.9 | driver/Kconfig | status |
|---|---|---|---|
| `&saradc` vref-supply | `saradc` node + `amlogic, adc_keypads` | `CONFIG_AMLOGIC_ADC_KEYPADS=y` | DERIVED |
| `vref-supply = <&vddio_ao18>` | no supply binding; p241 does not declare saradc at all | — | TODO |

the remote control uses this. `CONFIG_AMLOGIC_ADC_KEYPADS=y` in stock config
confirms it matters. p241 has no saradc node, so there is no 4.9 template to
copy from within this tree — it has to be written from the mesongxl.dtsi
register definitions.

### sound

| mainline | 4.9 | driver/Kconfig | status |
|---|---|---|---|
| `amlogic,gx-sound-card` model "XIAOMI-AQUAMAN", 3 dai-links, MPLL clocks | `aiu`/`ao-i2s` + `hdmitx` codec, `clk_level` on the `vpu` node | `CONFIG_AMLOGIC_MEDIA_*`, `CONFIG_SND_SOC_*` | TODO |
| `assigned-clock-rates 294912000/270950400/393216000` | 4.9 has no `assigned-clocks`; rates come from `clkc` tables | — | TODO |

this is the least portable node. the mainline clock rates were derived from the
stock bootloader, not from the DTS, and 4.9's audio path is a different stack.
**do not port blind.** note also that `CONFIG_AMLOGIC_VIDEOSYNC` is `n` on the
device but has to be `y` to build this tree (`kernel-baseline.md`), which means
our audio/video stack already differs from stock in a way nobody has explained.

### clocks / regulators

| mainline | 4.9 | driver/Kconfig | status |
|---|---|---|---|
| `clkc` + `CLKID_MPLL*` | `clkc` with GXL gate ids; no MPLL ids in this tree | `CONFIG_COMMON_CLK_AMLOGIC` / `CONFIG_ARCH_MESON` (fork) | TODO |
| `regulator-fixed` × 5 | consumed via `ocr_avail` + pinctrl, no supply graph | — | DERIVED |

## the honest summary of coverage

| area | confidence |
|---|---|
| DRAM size, eMMC | high — mainline and p241 agree and both match the device |
| SoC, CPU | high — S805Y/GXL is not in dispute |
| console UART | high — same reg base in both trees |
| BT UART | medium — same node, pinctrl group name unknown |
| SDIO host | medium — p241 template exists, but the `card_type` and power sequencing need confirmation |
| Wi-Fi chip | proven present (`rtl8821cs.ko`), but **not portable via DTS** |
| HDMI | medium — driver exists, `vend_data` and tvmode unknown |
| CEC | medium-high — p241 node matches mainline's pin choice |
| LED | low — pin known, pin group unknown |
| ADC | low — no 4.9 template in this tree |
| sound | low — different stack entirely, needs real work |
| clocks | low — mainline ids do not exist in 4.9 |

roughly: 4 nodes high confidence, 5 medium, 4 low, and a dozen TODO. that is not
a bootable DTS. it is a map.

## what would finish it

1. the real aquaman DTB — sealed inside AMLSECU in `dt.img`
   (`dts-analysis.md`: no `d00dfeed` magic, entropy 7.9965). this is the single
   input that would settle every TODO above at once, and it is not available.
2. secondary sources that would help, none of them sufficient alone: the L1
   retail unit's UART log (banned here), mainline's git history for the
   rationale behind the derived pins, or a kernel built by Xiaomi that leaked
   (the MiBox GPL request #11, open since 2025-01).
3. without (1), the remaining path is empirical: boot a kernel, read
   `/proc/device-tree` off the stock device over adb, diff against the
   reconstruction. `/proc/device-tree` is world-readable on most Android
   builds. **that has not been tried and should be** — it is read-only, needs
   no root on many kernels, and it would replace half the TODO column with
   ground truth. recommend it as the next device session.

`reconstructed/aquaman.dts` was **not** created. with a dozen TODO nodes and
no access to the sealed DTB, writing it would mean inventing pinctrl group
names and clock ids, and a DTB that does not match the hardware is worse than
no DTB: it fails at boot with no diagnostic. the mapping above is the
deliverable.
