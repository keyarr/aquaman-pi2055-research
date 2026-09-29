# aquaman-dts-port — mainline (2025) → 4.9 downstream

mapa de hardware: `torvalds/linux` `meson-gxl-s805y-xiaomi-aquaman.dts`
(merge mai/2025, Ferass El Hafidi, base declarada p241, 1 GB).
alvo: `arch/arm64/boot/dts/amlogic/` de `/tmp/kernel-src/linux-amlogic`.
**não copiar e compilar**: os dois mundos não compartilham quase nenhum binding.

## por que cópia direta é impossível

| mainline usa | 4.9 downstream tem |
|---|---|
| `meson-gxl-s805y.dtsi` + `meson-gxl.dtsi` upstream | `mesongxl.dtsi` próprio (cbus `0xc1100000`, aobus `0xc8100000`, outro pinctrl, `unifykey`, `efuse`, `ion_dev`) |
| `clkc` + `CLKID_MPLLx`, `pwm-clock`, `mmc-pwrseq`, `hdmi-connector`, `gpio-leds` com `color/function`, `amlogic,gx-sound-card` | nada disso; clocks por `clk81`/tabelas, som por `audio_data`/codec próprio, LED por gpio cru, HDMI por `hdmitx`+`tvmode`, eMMC por `sd_emmc_c` com outro binding |
| `amlogic-dt-id` inexistente | `amlogic-dt-id` **obrigatório** (bootloader seleciona DTB por ele) |
| `memory@0 reg 0x0+0x40000000` | `memory@0 linux,usable-memory 0x100000+0x3ff00000` + `reserved-memory` (ion, ramoops, diag, codec_mm, cma) + `partition_*.dtsi` + `firmware_*.dtsi` |

## ponto de partida

`gxl_p241_1g.dts` (mesma familia GXL, 1 GB, `amlogic-dt-id "gxl_p241_1g"`).
diferenças reais p241 → aquaman, classificadas:

### CONFIRMADO NO HARDWARE (mainline, driver com autor + teste no aparelho)

- SoC S805Y/GXL, 1 GB, eMMC (`sd_emmc_c`, 8-bit, HS200), SDIO em `sd_emmc_b`,
  `uart_A` com rtscts (BT), `uart_AO` console, USB OTG, `cec_AO`, `hdmi_tx`+HPD,
  LED em `GPIODV_24`, `saradc`, `pwm_ef` gerando 32 kHz p/ wifi, som HDMI
  (`XIAOMI-AQUAMAN`).

### INFERIDO DO MAINLINE (formato 4.9 a escrever do zero)

- `sd_emmc_b` em modo sdio 4-bit + pwrseq em `GPIOX_6` + clock 32k (no 4.9:
  node `sdio` com `compatible "amlogic, aml_sdio"` + `pinctrl sdio_*`, não
  `mmc-pwrseq-simple`).
- wifi usa chip **RTL8821CS** (Realtek, fora da árvore; p241 usa `aml_wifi`):
  DTS 4.9 sozinho NÃO sobe wifi — vai depender de `.ko` vendor + firmware.
  idem BT em `uart_A` (sem driver do módulo BT de algumas variantes, nota do
  próprio autor mainline).
- reguladores fixos (VDDIO_BOOT 1.8, VDDAO_3V3, VCC_3V3/5V): traduzir para o
  binding `regulator-fixed` do 4.9 (nomes diferentes, mesma função).
- LED: gpio `GPIODV_24` active-high, default on (binding 4.9: `gpio-leds` simples
  ou `amlogic,led`; sem `color/function`).
- som: reescrever para o stack 4.9 (`aiu`+`hdmitx` downstream); dai-links do
  mainline não portam.

### HERDADO DE OUTRO DISPOSITIVO (p241, manter até prova em contrário)

- `linux,usable-memory`, todo `reserved-memory` (ion/ramoops/cma), `unifykey`
  com as keyboxes, `partition_mbox_p241.dtsi`, `firmware_normal.dtsi`,
  `efuse`, `gpu` tbl, tvmode/hdmitx defaults. nada disso é aquaman; é o que
  permite bootar e ir ajustando.

## decisão de caminho (importante)

para M1/M2/M3 **nenhum DTB custom é necessário**: `fastboot boot` entrega ao
kernel o DTB que o U-Boot já tem (control DTB / `dtb_mem_addr`, ver
`fastboot-kernel-path.md` §4.5). port de DTS só entra em cena se o DTB do
U-Boot se provar insuficiente (M4), ou para um boot eMMC futuro — que está
fora de escopo (sem flash). ordem: M1 com DTB do U-Boot → observar → só então
decidir se o port vale o esforço.

## arquivo alvo (quando chegar a hora)

`arch/arm64/boot/dts/amlogic/gxl_p241_1g_aquaman.dts` (nome novo, dt-id novo
só se for para eMMC; para teste via bootm o dt-id nem é consultado):
p241_1g + overrides acima, compilado pelo `scripts/dtc` da árvore.
estimativa honesta: 60% é renomear bindings, 30% é adivinhação de pinctrl/
clock 4.9, 10% é o que realmente importa (memória, sdio, uart, usb, hdmi).
