# aquaman DTB extraction and validation

date: 2026-09-29. read only, nothing was written to the stick, no eMMC, no
`0x05`, no `AM_REQ_FILL_MEM`, no `setenv`, no flash. this session did one thing:
pull the aquaman's own device tree out of DRAM and turn it into something
readable, and check the claim that there is a second identical copy of it.

**why this extraction mattered.** everything the repo previously had about this
DTB was inference: `dt.img` is encrypted, no vendor `.dts` is public, and the
port map in `aquaman-dts-port.md` was written from `aquaman-config` plus the
2025 mainline file. this session replaced most of those inferences with data
from the device. the DTB is not stock and it is not a reconstruction — it is
what the vendor booted. what is still missing is the source tree behind it.

three files, all of them derived from one 16 MiB read that already existed:

```
artifacts/aquaman.dtb                     58280 bytes, the blob, unmodified
artifacts/aquaman.dts                     65052 bytes, dtc -I dtb -O dts
artifacts/aquaman-plus0x80000-clobbered.bin  the "second copy", kept as evidence
```

## 1. where the bytes came from

the read was not repeated. round 8
(`reports/bl33-offline-round8.md`, `reports/round8-bl33-read/00_session.txt`)
already pulled 16 MiB from `0x01000000` with the same optimus v2 path this repo
uses everywhere: `upload mem 0x01000000 normal 0x01000000` over the bulk IN
endpoint, cross checked byte for byte against `AM_REQ_READ_MEM` (0x02) in the
same burning window, gadget alive before and after. that dump is still on disk
and was not touched.

```
file      reports/round8-bl33-read/mread_01000000_01000000.bin
size      16777216 bytes, exact
sha256    f5e20c9e7952f73320819a13f474ac35d97882b46fbe0fc9d1d1d8d4830c3361
read at   2026-09-29 19:04, device 1b8e:c003, identify 00 07 00 10 (stage 16, TPL)
```

`artifacts/aquaman.dtb` is bytes `[0, 0xe3a8)` of that dump. the range end is
not a guess, it is the `totalsize` field of the FDT header at offset 0, see §2.
nothing was appended, padded, relocated or resaved.

```
artifacts/aquaman.dtb
size      58280 bytes (0xe3a8)
sha256    b00adabab0585aa2b946dd8730aa8e701049f661ae3004c8a16224ef4a445468
bytes received   58280 of 58280 asked, no short read
address   0x01000000, spans 0x01000000..0x0100e3a7 inclusive
```

where the address comes from, independently: the khadas u-boot tree in
`.src/u-boot-khadas/board/amlogic/configs/gxl_skt_v1.h:92` passes
`dtb_mem_addr=0x1000000` in the bootargs. that is U-Boot's staging address for
the tree, and it is exactly where the tree is. the round 8 report reached the
same address by a wrong route (it read a `/*16MB rsv*/` comment as a base
address, which it was not), but the two agree on the number and this one is the
right reason.

**a fresh confirmation read was not done this session.** the stick is still
enumerated as `1b8e:c003`, but claiming `1b8e:c003` needs root and no sudo
password was available in the environment, so the offline copy of the round 8
dump was used instead. re-running `tools/bl33_read.py` with credentials would
buy an independent second session; the bytes would be the same, the round 8
read was already cross checked against a second code path.

## 2. FDT validation

`dtc 1.7.2`, `fdtdump` from the same package. full transcript in
`reports/round9-dtb-extraction/00_fdt_validation.txt`.

| field | value | check |
|---|---|---|
| magic | `0xd00dfeed` | ok |
| totalsize | `0x0000e3a8` (58280) | ok, equals the file length |
| off_dt_struct | `0x00000038` (56) | ok |
| off_dt_strings | `0x0000caa4` (51876) | ok |
| off_mem_rsvmap | `0x00000028` (40) | ok |
| version | 17 | ok |
| last_comp_version | 16 | ok, v17 is compatible with v16 |
| boot_cpuid_phys | 0 | ok |
| size_dt_strings | `0x00001904` (6404) | ok |
| size_dt_struct | `0x0000ca6c` (51820) | ok |

the layout closes with no slack and no overlap:

```
0x28  mem_rsvmap, 16 bytes, one entry, immediately terminated
0x38  struct block, 0x38 + 0xca6c = 0xcaa4
0xcaa4 strings block, 0xcaa4 + 0x1904 = 0xe3a8 = totalsize
```

structural checks:

- `fdtdump` parses it and prints the tree, no error.
- `dtc -I dtb -O dts` exits 0, **zero errors**, 47 warnings, all of them style:
  38 `unit_address_vs_reg`, 4 `simple_bus_reg`, 3 `unit_address_format`, 1
  `resets_property`, 1 `gpios_property`. the full list is in
  `reports/round9-dtb-extraction/01_dtc_warnings.txt`. these are the usual
  complaints you get on any Amlogic vendor tree (`/timer_bc` has no unit name,
  `/memory@00000000` has a unit name and no `reg`, the `__symbols__` node
  stores a path string in a property called `gpio`). **not one of them is a
  parse failure and not one of them is fixed in the artifact.**
- no truncation: the file length equals `totalsize` and every offset in the
  header lands inside it.
- re-compiling the generated `.dts` gives a tree that is **value identical**,
  1798 nodes, 1798 properties, zero differences. `artifacts/aquaman.dts` is
  therefore complete, not a lossy rendering.

the FDT memory reservation map at `0x28` is **empty**: one entry,
`addr = 0, size = 0`, which is the terminator. every static reservation on this
board comes from `/reserved-memory` instead, see §6.

tree size: 376 nodes carrying at least one property, 1798 properties total, 108
top level children, 208 entries in `/__symbols__`.

## 3. the second copy: the claim does not hold

this is the one place where the hypothesis this session started from is wrong,
so it gets its own section.

the brief said there is an identical second copy at `0x01000000 + 0x80000` and
asked for a `sha256` equality check. measured:

| | address | bytes | sha256 |
|---|---|---|---|
| copy 1 | `0x01000000` | 58280 | `b00adabab0585aa2b946dd8730aa8e701049f661ae3004c8a16224ef4a445468` |
| copy 2 | `0x01080000` | 58280 | `5cd819ff3f55df2b17b87630e7ca47df7859520684ce221c7c7b8a2543b55ce7` |

**`sha256(copy1) != sha256(copy2)`.** 3543 bytes differ. they are not scattered,
they occupy one contiguous band:

```
differing bytes   3543 of 58280, all inside file offsets 0x0000..0x1fff
copy1[0x2000:0xe3a8] == copy2[0x2000:0xe3a8]   True   (50120 bytes, exact)
```

and the 8 KiB that differ is not device tree data. it is an Amlogic resource
container:

```
01080000  a4 c7 55 37  02 00 00 00  41 4d 4c 5f  52 45 53 21   ....AML_RES!
01080010  80 fb 0d 00  08 00 00 00  10 00 00 00  00 00 00 00
01080040  56 19 05 27  00 00 00 00  68 bf 02 00  40 02 00 00   V..'....h...@.
01080060  75 70 67 72  61 64 65 5f  73 75 63 63  65 73 73 00   upgrade_success.
```

`AmlResImgHead_t` and eight `AmlResItemHead_t` entries, `magic 0x27051956` on
every one, the eight names being `upgrade_success`, `bootup`, `upgrade_error`,
`upgrade_fail`, `upgrade_upgrading`, `upgrade_bar`, `upgrade_logo`,
`upgrade_unfocus`. that is the boot and upgrade screen pack, and
`0x01080000` is `GXB_IMG_LOAD_ADDR` from `bl31_apis.h:118`, which round 8
already identified. `upgrade_success` is a 300x300 16bpp Windows BMP
(`42 4d` at `0x01080240`, declared size `0x2bf68`).

so what actually sits at `+0x80000` is a **partially overwritten second copy of
the tree**, not a clean one. the pieces that survive are exactly the parts the
resource image did not reach:

| region | copy 1 | copy 2 (+0x80000) | verdict |
|---|---|---|---|
| header, `0x0000..0x0027` | FDT header | clobbered by `AML_RES!` | gone |
| mem_rsvmap, `0x0028..0x0037` | empty | clobbered | gone |
| struct block, `0x0038..0xca6b` | struct | 3516 of 51820 bytes differ | broken |
| strings block, `0xcaa4..0xe3a7` | strings | **byte identical, 0 differences** | intact |
| whole blob | valid FDT | `fdtdump`: `FATAL ERROR: header is not valid` | **not a DTB** |

corroborating counts over the whole 16 MiB:

- `0xd00dfeed` appears **once**. at `0x01000000`. nowhere else.
- the 6404-byte strings block at `0x0108caa4` is byte identical to the one at
  `0x0100caa4`. 0 differences.
- the 51820-byte struct block at `0x01080038` differs from the one at
  `0x01000038` in 3516 bytes.

**the round 8 conclusion that there is a second identical copy is retracted.**
it was based on one duplicated string, `/thermal-zones/soc_thermal/trips/trip-point@0`
showing up at `0x0100c508` and `0x0108c508`. one string is not a copy, and
`0x01080000` is a resource image, not a tree. round 8 §3.3 got that address
right and §3.1 got it wrong at the same time.

the raw 58280 bytes from `+0x80000` are kept as
`artifacts/aquaman-plus0x80000-clobbered.bin` so the claim can be rechecked.
they are deliberately **not** named `.dtb`, because they are not one.

## 4. model and compatible

```
/  model            "Amlogic"
/  amlogic-dt-id    "gxl_aquaman_1g"
/  compatible       "amlogic, Gxl"
```

`model` is the generic Amlogic string, not a product string. the board identity
lives entirely in `amlogic-dt-id`, and the only other place the product name
appears is `cec_osd_string` on `/aocec` (§8, CEC).

`compatible = "amlogic, Gxl"` is identical to the reference gxl tree. the aquaman
does **not** claim an upstream compatible, there is no
`amlogic,p212` or `amlogic,khadas-v1` in the blob.

`#address-cells = <2>`, `#size-cells = <2>` at the root, `interrupt-parent =
<&gic>` where `&gic` is phandle 0x1, `/interrupt-controller@2c001000`.

## 5. memory map

`/memory@00000000` has **no `reg` and no `size`**. only:

```
/memory@00000000 {
        device_type = "memory";
        linux,usable-memory = <0x00 0x100000  0x00 0x3ff00000>;
};
```

| item | value | source |
|---|---|---|
| RAM | 1 GiB, `0x00000000..0x40000000` | derived from `linux,usable-memory`, matches `gxl_aquaman_1g` |
| usable window | base `0x00100000`, size `0x3ff00000` | measured, `/memory@00000000/linux,usable-memory` |
| lowest usable address | `0x00100000` (1 MiB reserved below) | measured |
| highest usable address | `0x40000000` (1 GiB) | measured |
| FDT rsvmap | empty | measured, §2 |

`linux,usable-memory` is a Linux-specific extension, and it is identical,
byte for byte, in the reference gxl_p212_1g tree. so it does not distinguish the
aquaman from a reference GXL board. it does say the DDR is 1 GiB with the
bottom 1 MiB kept out, which is the same shape p212_1g has.

address map declared in the tree:

| node | reg |
|---|---|
| `/soc/cbus@c1100000` | `0xc1100000` size `0x100000` |
| `/soc/aobus@c8100000` | `0xc8100000` size `0x100000` |
| `/soc/hiubus@c883c000` | `0xc883c000` size `0x2000` |
| `/soc/periphs@c8834000` | `0xc8834000` size `0x2000` |
| `/soc/apb@d0000000` | `0xd0000000` size `0x200000` |
| `/interrupt-controller@2c001000` | `0xc4301000` size `0x1000`, `0xc4302000` size `0x100` |
| `/codec_io/io_cbus_base` | `0xc1100000` size `0x100000` |
| `/codec_io/io_dos_base` | `0xc8820000` size `0x10000` |
| `/codec_io/io_hiubus_base` | `0xc883c000` size `0x2000` |
| `/codec_io/io_aobus_base` | `0xc8100000` size `0x100000` |
| `/codec_io/io_vcbus_base` | `0xd0100000` size `0x40000` |
| `/codec_io/io_dmc_base` | `0xc8838000` size `0x400` |
| `/cpu_iomap/io_apb_base` | `0xd0050000` size `0x50000` |
| `/cpu_iomap/io_vapb_base` | `0xd0100000` size `0x100000` |

## 6. reserved-memory

`/reserved-memory` has `#address-cells = <2>`, `#size-cells = <2>` and empty
`ranges`. eleven children.

**the important thing about this node: seven of the eleven entries have no
`reg` at all.** they are `shared-dma-pool` regions, which carry a `size` and
let the allocator pick the base. two carry an explicit `alloc-ranges`. only two
regions in this whole node have a fixed base address. anything that claims a
base for `linux,codec_mm_cma`, `linux,di_cma`, `linux,ion-dev`,
`linux,vdin1_cma` or `linux,meson-fb` is inventing it.

| node | base | size | reg | alignment | no-map | reusable | compatible | purpose |
|---|---|---|---|---|---|---|---|---|
| `/reserved-memory/ramoops@0x07400000` | **`0x07400000`** | **`0x200000`** (2 MiB) | `<0x0 0x7400000 0x0 0x200000>` | none | no | no | `ramoops` | pstore, `record-size 0x8000`, `console-size 0x8000`, `ftrace-size 0x20000` |
| `/reserved-memory/linux,secmon` | **not in the blob** | **`0x400000`** (4 MiB) | none | `0x400000` | no | yes | `shared-dma-pool` | `alloc-ranges = <0x0 0x5000000 0x0 0x400000>`, so the pool is confined to `0x05000000..0x05400000`. referenced by `/secmon` `memory-region`, which also sets `reserve_mem_size = 0x300000` |
| `/reserved-memory/linux,secos` | **`0x05300000`** | **`0x2000000`** (32 MiB) | `<0x0 0x5300000 0x0 0x2000000>` | none | **yes** | no | `amlogic, aml_secos_memory` | `status = "disable"`. the only `no-map` in the whole tree |
| `/reserved-memory/linux,meson-fb` | **not in the blob** | **`0x800000`** (8 MiB) | none | `0x400000` | no | yes | `shared-dma-pool` | `alloc-ranges = <0x0 0x3f800000 0x0 0x800000>`, pool confined to `0x3f800000..0x40000000`. framebuffer, `/meson-fb` `memory-region` and `logo_addr = "0x3f800000"` agree |
| `/reserved-memory/linux,di_cma` | **not in the blob** | **`0x2000000`** (32 MiB) | none | `0x400000` | no | yes | `shared-dma-pool` | deinterlace CMA, `/deinterlace` `memory-region` |
| `/reserved-memory/linux,ion-dev` | **not in the blob** | **`0x4c00000`** (76 MiB) | none | `0x400000` | no | yes | `shared-dma-pool` | `/ion_dev` `memory-region` |
| `/reserved-memory/linux,vdin1_cma` | **not in the blob** | **`0x1000000`** (16 MiB) | none | `0x400000` | no | yes | `shared-dma-pool` | `/vdin1` `memory-region` |
| `/reserved-memory/linux,ppmgr` | **not in the blob** | **`0x0`** | none | none | no | **no** | `shared-dma-pool` | size zero. `/ppmgr` `memory-region` points at it |
| `/reserved-memory/linux,codec_mm_cma` | **not in the blob** | **`0xd000000`** (208 MiB) | none | `0x400000` | no | yes | `shared-dma-pool` | `linux,contiguous-region`. the largest pool, `/codec_mm` first `memory-region` |
| `/reserved-memory/linux,picdec` | **not in the blob** | **`0x0`** | none | `0x0` | no | yes | `shared-dma-pool` | `linux,contiguous-region`, size zero. `/picdec` `memory-region` |
| `/reserved-memory/linux,codec_mm_reserved` | **not in the blob** | **`0x0`** | none | `0x100000` | no | **no** | `amlogic, codec-mm-reserved` | `/codec_mm` second `memory-region` |

regions with a fixed base, and only these three:

| region | base | end | size | flags |
|---|---|---|---|---|
| `ramoops@0x07400000` | `0x07400000` | `0x07600000` | 2 MiB | plain reserved, pstore only |
| `linux,secos` | `0x05300000` | `0x07300000` | 32 MiB | **`no-map`**, `status = "disable"` |
| `linux,secmon` pool | `0x05000000` | `0x05400000` | 4 MiB | reusable, base from `alloc-ranges` |
| `linux,meson-fb` pool | `0x3f800000` | `0x40000000` | 8 MiB | reusable, base from `alloc-ranges` |

these two overlap. `linux,secos` starts at `0x05300000` and the `linux,secmon`
pool is pinned to `0x05000000..0x05400000`. **`0x05300000` to `0x05400000` is
claimed by both.** that is what the blob says, it is not a typo on my side and
it is not something to correct. `secos` is `status = "disable"` in this tree, so
in practice the kernel should not create it and the collision may be dead code
on this build. recorded as an anomaly, §11.

`linux,secos` at `0x05300000` + 32 MiB ends exactly at `0x07300000`, and
`ramoops` starts at `0x07400000`. there is a 1 MiB hole at `0x07300000`. not
explained, not filled in.

sum of the declared pool sizes: 4 + 32 + 8 + 32 + 76 + 16 + 0 + 208 + 0 = 376 MiB
of DMA-pool demand out of a 1023 MiB usable window. the allocator picks the
bases and there is no way to say from the blob alone whether the pools actually
fit. **not verified, and the eMMC/`dmesg` was not touched to check.**

## 7. cpu, soc, peripherals

**cpu.** four cores, `arm,cortex-a53` / `arm,armv8`, `enable-method = "psci"`,
`/cpus/cpu-map/cluster0` with `core0..core3` mapped to `cpu@0..cpu@3` (phandles
0x09..0x0c), one `idle-states/system-sleep-0` at `arm,psci-suspend-param =
0x20000`, clock `&scpi_clocks 0` named `cpu-cluster.0`, all four cores on the
same clock cell. `/psci` is `arm,psci-0.2`, `method = "smc"`. `/timer` is
`arm,armv8-timer` with gic1/13, gic1/14, gic1/11, gic1/10. `/arm_pmu` is
`arm,armv8-pmuv3` at `0xc8834400`, gic0/137.

**clocks.** one clock provider, `/soc/hiubus@c883c000/clock-controller@0`,
`amlogic,gxl-clkc`, phandle `0x8`, `#clock-cells = <1>`. every `clocks` property
in the tree is `<&gxl_clkc ID>` except `/xtal-clk` (phandle `0x10`, a
`fixed-clock`, 24 MHz, `#clock-cells = <0>`) and the `scpi` cpu clock. 65
interrupt specifiers across 41 nodes, 0 to gic1 for arm timer, 0 to gic0 for
everything else.

**reset.** exactly one `resets` in the whole tree:
`/snd_dmic` `resets = <&gxl_clkc 0xd4>`, `reset-names = "pdm"`. and `/snd_dmic`
is `status = "disabled"`. the reset controller itself is
`/soc/cbus@c1100000/reset-controller@4404` (`amlogic,reset`, phandle 0xb4),
referenced by nobody else in the tree.

**regulators.** **zero.** no `regulator-*` node, no `regulator` property, no
`*-supply` property, anywhere in the 1798 properties. the gxl trees of this era
do voltage control in the pinctrl nodes and in vendor blobs, not in the DT. if a
reconstruction needs a rail map, this blob does not have one and a reference
tree would only be a guess.

**gpio.** two banks, both `#gpio-cells = <2>`, both declared as
`gpio-controller`:

| bank | node | phandle | compatible | reg windows |
|---|---|---|---|---|
| periphs / EE | `/pinctrl@4b0/bank@4b0` | **`0x11`** | `amlogic,meson-gxl-periphs-pinctrl` | mux `0xc88344b0`/0x28, pull `0xc88344e8`/0x14, pull-enable `0xc8834520`/0x14, gpio `0xc8834430`/0x40 |
| aobus / AO | `/pinctrl@14/bank@14` | `0x8f` | `amlogic,meson-gxl-aobus-pinctrl` | mux `0xc8100014`/8, pull `0xc810002c`/4, gpio `0xc8100024`/8 |

**every single gpio reference in the aquaman tree uses phandle `0x11`, the
periphs/EE bank. the AO bank `0x8f` is referenced by nothing.** that includes
the eMMC `hw_reset` and `gpio_dat3`, which a reader would expect on the aobus
bank. the tree says otherwise and this report does not correct it. the same is
true in the p212 reference, so it is a family convention, not an aquaman
mistake. the full scan is in
`reports/round9-dtb-extraction/05_gpio_table.txt`:

| node | property | bank | pin/flags |
|---|---|---|---|
| `/@c1108d80` (the efuse node, unnamed) | `cs-gpios` | EE | `0x59`/0 |
| `/bt-dev` | `gpio_reset` | EE | `0x60`/0 |
| `/bt-dev` | `gpio_en` | EE | `0x55`/0 |
| `/btwakecontrol` | `bt_host_wake` | EE | `0x61`/0 |
| `/wifi` | `interrupt_pin` | EE | `0x56`/0 |
| `/wifi` | `power_on_pin` | EE | `0x55`/0 |
| `/emmc@d0074000/emmc` | `gpio_dat3` | EE | `0x1d`/0 |
| `/emmc@d0074000/emmc` | `hw_reset` | EE | `0x23`/0 |
| `/sd@d0072000/sd` | `gpio_dat3` | EE | `0x2e`/0 |
| `/sd@d0072000/sd` | `gpio_cd` | EE | `0x30`/0 |
| `/sd@d0072000/sd` | `jtag_pin` | EE | `0x2a`/0 |
| `/aml_sound_meson` | `mute_gpio-gpios` | EE | `0x15`/0 |
| `/sysled` | `led_gpio` | EE | `0x49`/0, node disabled |
| `/amremote_led` | `control_gpio` | EE | `0x49`/0 |
| `/jtag` | `jtagao-gpios` | EE | `0x16 0x17 0x18 0x19`/0 |
| `/jtag` | `jtagee-gpios` | EE | `0x2a 0x2b 0x2c 0x2d`/0 |

`jtagao-gpios` and `jtagee-gpios` both point at the same bank, so the ao/ee in
the property names does not reflect the phandle. family quirk, present in the
reference too.

**uart.** five nodes, `amlogic, meson-uart`, all with `fifosize`:

| alias | node | reg | irq | status | clocks | fifo |
|---|---|---|---|---|---|---|
| `serial0` | `/serial@c81004c0` | `0xc81004c0`/0x18 | gic0/193 | okay | `<&xtal>` | 0x40 |
| `serial1` | `/serial@c11084c0` | `0xc11084c0`/0x18 | gic0/26 | okay | **`<&xtal>`** | 0x80 |
| `serial2` | `/serial@c11084dc` | `0xc11084dc`/0x18 | gic0/75 | disabled | `<&gxl_clkc 0x40>` | 0x40 |
| `serial3` | `/serial@c1108700` | `0xc1108700`/0x18 | gic0/93 | disabled | `<&gxl_clkc 0x57>` | 0x40 |
| `serial4` | `/serial@c81004e0` | `0xc81004e0`/0x18 | gic0/197 | `disable` (not `disabled`) | `<&xtal>` | 0x40 |

`serial1` running off the xtal fixed clock instead of gxl-clkc 0x23 is a real
difference from the reference tree, see §10.

**mmc / storage.** three `amlogic, meson-mmc-gxl` controllers, all three
`okay`:

| node | reg | irq | bus-width | max-frequency | flags |
|---|---|---|---|---|---|
| `/emmc@d0074000` | `0xd0074000`/0x2000 | gic0/218 | 8 | 200 MHz | `non-removable`, `mmc-ddr-1_8v`, `mmc-hs200-1_8v`, `disable-wp` |
| `/sd@d0072000` | `0xd0072000`/0x2000 | gic0/217 | 4 | 100 MHz | removable, `disable-wp` |
| `/sdio@d0070000` | `0xd0070000`/0x2000 | gic0/216 | 4 | 100 MHz | `non-removable`, wifi |

note the sdio node: the top level `max-frequency` is `0x5f5e100` (100 MHz) while
its child `sdio/f_max` is `0xbebc200` (200 MHz). both are in the blob, they
disagree, and this report does not pick one.

the eMMC node carries `caps` with `MMC_CAP_HW_RESET` and `caps2` with
`MMC_CAP2_HS200` + `MMC_CAP2_HS400`, and `card_type = 0x1`.

`/mtd_nand` is present with a full nand_partition tree but is
`status = "disabled"`. its partitions are listed anyway in §9.

**ethernet: there is none.** no ethernet node anywhere in the aquaman tree. see
§10, this is the single biggest structural difference from the reference GXL
tree. a stick does not need it.

**audio.** `I2S`, `SPDIF`, `PCM` DAIs, `spdif_codec`, `pcm_codec`, a `dummy`
codec (`status = "okay"` on aquaman, `disable` on p212), `i2s_platform` at gic0/29,
`/aml_sound_meson` card named `AML-MESONAUDIO`, format `i2s`,
`aml,audio-routing = "Ext Spk","LOUTL","Ext Spk","LOUTR"`, mute on EE pin 0x15.
cpu dais and codecs, resolved through the phandles:

| list | entry | resolves to |
|---|---|---|
| `cpu_list` | 0 | `/I2S` |
| `cpu_list` | 1 | `/SPDIF` |
| `cpu_list` | 2 | `/PCM` |
| `codec_list` | 0 | `/dummy` |
| `codec_list` | 1 | `/spdif_codec` |
| `codec_list` | 2 | `/pcm_codec` |

`/t9015` (`amlogic, aml_codec_T9015`, `0xc8832000`) is `status = "disabled"` on
the aquaman and `okay` on p212, so the analog audio codec is not used.
`/snd_dmic` is `status = "disabled"`.

**thermal.** `/aml-sensor@0` (`amlogic, aml-thermal`, 3 cooling cells), four
cooling devices (`cpufreq_cool_cluster0`, `cpucore_cool_cluster0`,
`gpufreq_cool`, `gpucore_cool`) and four trips under
`/thermal-zones/soc_thermal/trips/trip-point@0..3`:

| trip | aquaman | p212 |
|---|---|---|
| trip-point@0 | `0x15f90` (90000) | `0x11170` (70000) |
| trip-point@1 | `0x17318` (95000) | `0x13880` (80000) |
| trip-point@2 | `0x19a28` (105000) | `0x14c08` (85000) |
| trip-point@3 | `0x1d4c0` (120000) | `0x3f7a0` (260000) |

all four are shifted, the aquaman is consistently hotter-running. see §10.

**hdmi / display.** `/amhdmitx` `okay`, gic0/57 (`hdmitx_hpd`), `ic_type = 0x3`,
`vend_data` = phandle 0x52 which resolves to `vendor_name = "Amlogic"`,
`vendor_id = 0`, `product_desc = "MBox Meson Ref"`. **the HDMI vendor string is
still the generic Amlogic one on this board.** `/vout` `okay`,
`display_mode_default = "1080p60hz"`, `logo_addr = "0x3f800000"`. `/cvbsout`
is `status = "disabled"` on the aquaman, `okay` on p212. no analog output.

**cec.** `/aocec`, `amlogic, amlogic-aocec`, `okay`, gic0/199,
`reg = <0xc810023c/4  0xc8100000/0x200>`, `reg-names = "ao_exit","ao"`,
`cec_version = 0x5`, `port_num = 1`, `arc_port_mask = 0`,
`vendor_id = 0`, and:

```
cec_osd_string = "Mi TV Stick"
```

that string is the product name, in the blob, in plain text. see §8.

**ir / remote.** `/rc@c8100580`, `amlogic, aml_remote`, `dev_name =
"meson-remote"`, `okay`, `protocol = 0x2`, gic0/196, `max_frame_time = 0xc8`,
pinctrl `/pinctrl@14/remote_pin` (function `remote`, group `remote_input`).
`protocol` is `0x2` here and `0x1` on the reference tree, so the aquaman remote
is on a different IR protocol.

`/custom_maps` `mapnum = 5`, five keymaps:

| map | name | customcode | keys |
|---|---|---|---|
| map_0 | `amlogic-remote-1` | `0xfb04` | 50 |
| map_1 | `amlogic-remote-2` | `0xfe01` | 53 |
| map_2 | `amlogic-remote-3` | `0xbd02` | 17 |
| map_3 | **`xiaomi-ir-0`** | `0x86` | 12 |
| map_4 | **`xiaomi-ir-1`** | `0x3c` | 1, `0xcc0074` |

`map_3` and `map_4` do not exist in the reference tree. `xiaomi-ir-1` has
exactly one key, code `0xcc` mapped to `0x74`, which is `KEY_POWER` in the
linux input keycode set. the Xiaomi stick powers on from the remote over IR.

**video codec / vdec.** `/vdec` (`amlogic, vdec`, `dev_name = "vdec.0"`,
`okay`, 6 interrupts: gic0/3 vsync, 0x17 demux, 0x20 parser, 0x2b/0x2c/0x2d
mailbox), `/vcodec_dec` `okay`, `/amvenc_avc` `okay` gic0/45,
`/hevc_enc` (`cnm, HevcEnc`, `okay`, gic0/187 `wave420l_irq`, io window
`0xc8810000`/0x4000), `/deinterlace` gic0/46 and gic0/6, `/ge2d` gic0/150,
`/ionvideo`, `/amlvideo`, `/amlvideo2_0`, `/amlvideo2_1`, `/vdin0` gic0/83,
`/vdin1` gic0/85, `/picdec`, `/ppmgr`, `/canvas` (`0xc8838000`/0x400),
`/mesonstream` (7 clocks: `parser_top`, `demux`, `vdec`, `clk_81`,
`clk_vdec_mux`, `clk_hcodec_mux`, `clk_hevc_mux`), `/vpu` (`amlogic, vpu-gxl`,
6 clocks), `/meson-fb`.

**vdec memory is not a separate reserved region in this tree.** the only memory
pool the video path names is `linux,codec_mm_cma` at `0xd000000` (208 MiB) via
`/codec_mm`, plus `linux,ion-dev` 76 MiB, `linux,di_cma` 32 MiB,
`linux,vdin1_cma` 16 MiB. there is no node called vdec_mm or similar.

**wifi / bluetooth.** both present, both Amlogic-vendor, no realtek or broadcom
strings anywhere:

| node | compatible | status | detail |
|---|---|---|---|
| `/wifi` | `amlogic, aml_wifi` | okay | `dev_name = "aml_wifi"`, `dhd_static_buf`, EE pin 0x56 irq, EE pin 0x55 power, `wifi_32k_pins`, 2 pwm channels (0x774d and 0x7724 Hz, duty 0x3ba6 / 0x3b92, 8 / 12 slots) |
| `/bt-dev` | `amlogic, bt-dev` | okay | EE reset 0x60, EE en 0x55 |
| `/btwakecontrol` | `amlogic, btwakecontrol` | okay | EE wake 0x61, `GPIO_IRQ_RISING` |

the `dhd_static_buf` flag and the two 32.768 kHz pwm channels are the tell for
a Broadcom combo chip behind an Amlogic shim, but **that is an inference from
vendor naming, not a string in the blob.** the blob does not name the wifi chip.

**misc.** `/aml_pm` (amlogic pm, `debug_reg 0xc81000a8`, `exit_reg 0xc810023c`),
`/watchdog` (`amlogic, meson-wdt`, `0xc11098d0`/0x10), `/rtc`
(`amlogic, aml_vrtc`, `init_date = "2017/01/01"`), `/saradc` gic0/73,
`/efuse` (`amlogic, efuse`, gic-less, clock 0x4a, `key = 0x19`) with
`/efusekey` holding `mac`, `mac_bt`, `mac_wifi`, `usid`, `/unifykey` with 19
entries, `/aml_dma` gic0/188, `/ddr_bandwidth` gic0/52, `/dmc_monitor` gic0/51,
`/vcodec_dec`, `/secmon` (`in_base_func 0x82000020`, `out_base_func 0x82000021`,
`reserve_mem_size 0x300000`), `/securitykey` with 14 SMC command IDs,
`/defendkey`, `/jtag` (`select = "apao"`), `/ram-dump`, `/custom_maps`,
`/sysled` (disabled), `/amremote_led` (okay), `/efuse`.

**no `/chosen` node.** not one byte. a kernel that takes `bootargs`,
`stdout-path` or `initrd` from the DT will get nothing from this tree; U-Boot
passes them on the command line instead, which matches `gxl_skt_v1.h:92..109`.

## 8. GPU

```
/mali@d00c0000 {
        compatible     = "arm,mali-450";
        #cooling-cells = <2>;
        reg            = <0x0 0xd00c0000 0x0 0x40000
                            0x0 0xc1104440 0x0 0x1000
                            0x0 0xc8100000 0x0 0x1000
                            0x0 0xc883c000 0x0 0x1000
                            0x0 0xc1104440 0x0 0x1000>;
        interrupts     = gic0 160..169, all edge (0x4)
        interrupt-names= "IRQGP","IRQGPMMU","IRQPP","IRQPMU","IRQPP0","IRQPPMMU0",
                         "IRQPP1","IRQPPMMU1","IRQPP2","IRQPPMMU2"
        clocks         = <&gxl_clkc 0x97  &gxl_clkc 0x09>;
        clock-names    = "gpu_mux", "gp0_pll";
        num_of_pp      = <3>;
        def_clk        = <0x4>;
        sc_mpp         = <0x3>;
        pmu_domain_config = <1 2 4 4 0 0 0 0 0 1 2 0>;
        pmu_switch_delay  = <0xffff>;
        tbl            = <2 3 4 5 6 7 7>;
        control_interval  = <0xc8>;
};
```

Mali-450 MP2, as the string says. the clock IDs `0x97` (gpu_mux) and `0x09`
(gp0_pll) are the only Amlogic gxl clock IDs in the whole tree above 0x8d, and
they match the reference `gxl_p212_1g` value for value.

eight DVFS bins as child nodes, all `voltage = 0x47e` (1150 mV), all
`keep_count` 1 to 5:

| node | phandle | clk_freq | parent | clkp_freq | threshold | keep_count |
|---|---|---|---|---|---|---|
| `clk125_cfg` | 0x02 | 125000000 | `fclk_div4` | 500000000 | `0x1efa` (7930) | 5 |
| `clk250_cfg` | 0x84 | 250000000 | `fclk_div4` | 500000000 | `0x73fa` (29690) | 5 |
| `clk285_cfg` | 0x03 | 285714285 | `fclk_div7` | 285714285 | `0x64fa` (25850) | 5 |
| `clk400_cfg` | 0x04 | 400000000 | `fclk_div5` | 400000000 | `0xa8fa` (43258) | 3 |
| `clk500_cfg` | 0x05 | 500000000 | `fclk_div4` | 500000000 | `0xbefa` (48890) | 2 |
| `clk666_cfg` | 0x06 | 666666666 | `fclk_div3` | 666666666 | `0xb1fa` (45562) | 1 |
| `clk750_cfg` | 0x07 | 750000000 | `gp0_pll` | 750000000 | `0xd5ff` (54783) | 1 |
| `clk800_cfg` | 0x85 | 800000000 | `gp0_pll` | 800000000 | `0xe6ff` (59135) | 1 |

`def_clk = 0x4` points at `clk400_cfg`, so the GPU boots at 400 MHz.

GPU memory: the mali node has no `memory-region` and the tree has no mali
specific reserved pool. it draws from `linux,codec_mm_cma` and `linux,ion-dev`
with the other video blocks.

the `interrupt-names` sequence is correct and matches the reference. I expected
a typo here and there is not one, the ten names line up with the ten interrupt
specifiers.

## 9. USB

| node | compatible | reg | irq | status | notes |
|---|---|---|---|---|---|
| `/dwc3@c9000000` | `synopsys, dwc3` | `0xc9000000`/0x100000 | gic0/30 | no `status` prop | `usb-phy = <&usb2phy &usb3phy>`, `cpu-type = "gxl"`, `clock-src = "usb3.0"` |
| `/usb2phy@d0078000` | `amlogic, amlogic-new-usb2` | `0xd0078000`/0x80 + `0xc1104408`/4 | none | no `status` prop | `portnum = 3` |
| `/usb3phy@d0078080` | `amlogic, amlogic-new-usb3` | `0xd0078080`/0x20 | none | no `status` prop | `portnum = 0` |
| `/dwc2_a` | `amlogic, dwc2` | `0xc9100000`/0x40000 | gic0/31 | okay | `port-id 0`, `port-type 2`, `phy-reg 0xd0078000`, `phy-reg-size 0xa0`, `usb-fifo 0x2d8`, `controller-type 1`, clocks `usb_general`(0x47) `usb1`(0x52) `usb1_to_ddr`(0x43) |

`dwc3` and both PHYs have **no `status` property at all**, so by the DT spec
they are enabled. the reference tree has the same, so this is the family norm
and not an aquaman quirk. only one dwc2 port is instantiated, `dwc2_a`.

the single USB host port on a stick is `dwc2_a` on `usb0` (`clock-src = "usb0"`,
`port-id = 0`, 2 ports of the `portnum = 3` declared by the USB2 PHY).

## 10. storage and partitions

`/partitions`, phandle 0xc2, `parts = <0x11>` and `part-0` .. `part-16` naming
the seventeen children. every child has `pname`, `size`, `mask`, `phandle`.

**no child has an `offset` property.** the blob gives sizes and an order, not
addresses. the offsets in the last column are **derived**, by accumulating the
sizes in `part-N` order from 0. do not read them as extracted values.

| # | node | `size` | size | `mask` | derived offset |
|---|---|---|---|---|---|
| 0 | `logo` | `0x800000` | 8 MiB | `0x1` | `0x00000000` |
| 1 | `recovery` | `0x1800000` | 24 MiB | `0x1` | `0x00800000` |
| 2 | `misc` | `0x800000` | 8 MiB | `0x1` | `0x02000000` |
| 3 | `dtbo` | `0x800000` | 8 MiB | `0x1` | `0x02800000` |
| 4 | `cri_data` | `0x800000` | 8 MiB | `0x2` | `0x03000000` |
| 5 | `param` | `0x1000000` | 16 MiB | `0x2` | `0x03800000` |
| 6 | `boot` | `0x1000000` | 16 MiB | `0x1` | `0x04800000` |
| 7 | `rsv` | `0x1000000` | 16 MiB | `0x1` | `0x05800000` |
| 8 | `tee` | `0x2000000` | 32 MiB | `0x1` | `0x06800000` |
| 9 | `vendor` | `0x6400000` | 100 MiB | `0x1` | `0x08800000` |
| 10 | `odm` | `0x1400000` | 20 MiB | `0x1` | `0x0ec00000` |
| 11 | `metadata` | `0x1000000` | 16 MiB | `0x1` | `0x10000000` |
| 12 | `vbmeta` | `0x200000` | 2 MiB | `0x1` | `0x11000000` |
| 13 | `system` | `0x5ac00000` | 1452 MiB | `0x1` | `0x11200000` |
| 14 | `product` | `0x6a00000` | 106 MiB | `0x1` | `0x6be00000` |
| 15 | `cache` | `0x10000000` | 256 MiB | `0x2` | `0x72800000` |
| 16 | `data` | `0xffffffffffffffff` | rest | `0x4` | rest |

the sixteen sized partitions total `0x82800000` = 2088 MiB. `mask` is recorded
as-is, this report does not interpret it.

nand, `/mtd_nand/nand_partition`, `status = "disabled"` on the parent. all
offsets are `0x0` except `data`, which is `0xffffffffffffffff`, so a
`shared-dma-pool`-style "rest of device" again:

| node | offset | size |
|---|---|---|
| `logo` | `0x0` | `0x200000` |
| `recovery` | `0x0` | `0x1000000` |
| `boot` | `0x0` | `0xc00000` |
| `system` | `0x0` | `0xdc40000` |
| `data` | `0xffffffffffffffff` | `0x0` |

`/firmware/android` carries the vbmeta chain and the fstab the bootloader hands
to the kernel:

```
/firmware/android/vbmeta   parts = "vbmeta,boot,system,vendor", by_name_prefix = "/dev/block"
/firmware/android/fstab/vendor   /dev/block/vendor  ext4  ro,barrier=1,inode_readahead_blks=8  wait,avb
/firmware/android/fstab/product  /dev/block/product ext4  ro,...  wait
/firmware/android/fstab/odm      /dev/block/odm     ext4  ro,...  wait
```

no `system` entry in the aquaman fstab (the reference has one, see §11).
`/firmware` has no `android,firmware` partitions list beyond this.

`boot.img`, `dt.img`, `dtbo.img`, `vbmeta.img` and `bootloader.img` from the
stock firmware are in the repo but **were not opened and the eMMC was not
touched.** `dt.img` (59424 bytes) is high entropy with no FDT magic at offset
0, i.e. still encrypted in the shipped form, which is why the RAM read was
worth doing in the first place.

## 11. strings: what is in the blob and what is not

**directly in the DTB, verbatim.** file offset of the bytes in
`artifacts/aquaman.dtb`:

| string | file offset | where | occurrences |
|---|---|---|---|
| `Amlogic` | `0x4c` | `/model` | 1 |
| `Amlogic` | `0x8a44` | `/amhdmitx/vend_data/vendor_name` | 1 |
| `gxl_aquaman_1g` | `0x60` | `/amlogic-dt-id` | 1 |
| `amlogic, Gxl` | `0x7c` | `/compatible` | 1 |
| `Mi TV Stick` | `0x8b04` | `/aocec/cec_osd_string` | 1 |
| `xiaomi-ir-0` | `0x54e8` | `/custom_maps/map_3/mapname` | 1 |
| `xiaomi-ir-1` | `0x558c` | `/custom_maps/map_4/mapname` | 1 |
| `amlogic-remote-1` | `0x5194` | `/custom_maps/map_0/mapname` | 1 |
| `amlogic-remote-2` | `0x52d8` | `/custom_maps/map_1/mapname` | 1 |
| `amlogic-remote-3` | `0x5428` | `/custom_maps/map_2/mapname` | 1 |
| `MBox Meson Ref` | `0x8a68` | `/amhdmitx/vend_data/product_desc` | 1 |
| `AML-MESONAUDIO` | `0x9a8c` | `/aml_sound_meson/aml_sound_card,name` | 1 |

totals over the whole blob: `Amlogic` 2, `xiaomi` 2, `aquaman` 1,
`gxl_aquaman_1g` 1, `Mi TV Stick` 1, `amlogic, Gxl` 1.

`aquaman` and `Mi TV Stick` each appear exactly once, and both are load-bearing:

- `gxl_aquaman_1g` is the only place the board name exists. `model` is the
  generic Amlogic string, `compatible` is the generic GXL string, the HDMI
  vendor block is still the generic `MBox Meson Ref`. a board identification
  routine that reads `/model` gets nothing useful here, it has to read
  `amlogic-dt-id`.
- `Mi TV Stick` is the only human readable product name, and it is on the CEC
  node, not on any identification node.
- `xiaomi-ir-0` and `xiaomi-ir-1` are the only lowercase `xiaomi` strings, and
  they are in the IR keymap, not in an identification node.

**inference from outside the blob, kept strictly separate:**

- "1 GB of RAM" is read off `linux,usable-memory` and the `1g` in
  `gxl_aquaman_1g`, not off any string.
- "the wifi chip is Broadcom" is an inference from `dhd_static_buf` and the two
  32.768 kHz pwm channels. there is no broadcom, realtek or any other vendor
  name in the blob.
- "the Wi-Fi combo is on SDIO" is from `/sdio@d0070000` being the only
  `non-removable` 4-bit non-eMMC controller and `/wifi` existing at all.
- "the p212 tree is the same SoC family" is from the identical
  `compatible`, the identical `cpu_iomap`/`codec_io` windows, and the identical
  clock IDs. it is a family claim, not an identity claim.
- `0x8` as the gxl-clkc phandle and the `MBOX` numbering are Amlogic driver
  conventions, not values this blob states about itself.

## 12. comparison with a public GXL tree

done **after** the extraction, and nothing from the reference was written into
`artifacts/aquaman.dtb` or `artifacts/aquaman.dts`. the aquaman blob is the
primary source; the reference only says what is *different*.

reference: `.src/linux-amlogic/arch/arm64/boot/dts/amlogic/gxl_p212_1g.dts`
plus `mesongxl.dtsi` and `partition_mbox_normal.dtsi`, preprocessed with
`cpp -nostdinc -undef -x assembler-with-cpp` and compiled with the same dtc
1.7.2. 376 nodes / 1798 properties on the aquaman side, 335 / 1471 on the
reference side. the full diff, phandle renumbering stripped, is in
`reports/round9-dtb-extraction/04_vs_gxl_p212_1g.txt`.

**absent from the aquaman, present in the reference, four nodes:**

| node | what it is |
|---|---|
| `/ethernet@0xc9410000` | `amlogic, gxbb-eth-dwmac` at `0xc9410000`, gic0/8, internal PHY, `external_eth_pins`, `rst_pin-gpios` EE 0x0e, `GPIOZ4/Z5` 0x04/0x05. **the stick has no wired ethernet, and the DT agrees** |
| `/gpio_keypad` | `amlogic, gpio_keypad`, `okay`, one key, `key_name = "power"`, `key_code = 0x74`, `key-gpios = <0x54 0x2>` (EE bank, 2). a hardware power button. the aquaman has no such node, its power key arrives over IR instead (§8) |
| `/pm` | `amlogic, pm` with `reg` windows. the aquaman has the newer `/aml_pm` node instead, same `0xc81000a8` / `0xc810023c` registers |
| `/firmware/android/fstab/system` | the aquaman fstab has vendor, product, odm but **no system entry** |

**enabled on the aquaman, disabled or absent on the reference:**

| item | aquaman | p212 |
|---|---|---|
| `/soc/aobus@c8100000/i2c@0500` | `okay` | `disabled` |
| `/t9015` analog audio codec | `disabled` | `okay` |
| `/cvbsout` analog video out | `disabled` | `okay` |
| `/dummy` audio codec | `okay` | `disable` |

that is the shape of the board in one table: no ethernet, no analog video, no
analog audio codec, no hardware power button, no real SPDIF/PCM path in use, the
one extra enabled peripheral is an I2C controller on AO. a stick.

**values that differ for real reasons:**

| item | aquaman | p212 | why it matters |
|---|---|---|---|
| `/serial@c11084c0/clocks` | `<&xtal>` (`#clock-cells 0`) | `<&gxl_clkc 0x23>` | the console UART is clocked from the 24 MHz xtal instead of the gxl clock tree. different clock path, worth knowing before touching earlyprintk |
| `/rc@c8100580/protocol` | `0x2` | `0x1` | the aquaman IR receiver is on a different protocol |
| `/custom_maps/mapnum` | 5 | 3 | +`xiaomi-ir-0` (12 keys) +`xiaomi-ir-1` (1 key) |
| `/aocec/cec_osd_string` | `Mi TV Stick` | `MBox` | product identity |
| `/aocec/pinctrl-names` | 3 states | 1 state | extra CEC pin states, `hdmitx_aocecb` and `cec_pin_sleep` |
| `/pinctrl@4b0/a_uart/mux/groups` | `uart_tx_a`,`uart_rx_a` | also `uart_cts_a`,`uart_rts_a` | the aquaman does not route CTS/RTS |
| `/partitions` | 17 children | 14 | +`metadata`, +`product`, +`vbmeta` |
| `system` size | `0x5ac00000` (1452 MiB) | `0x74000000` (1856 MiB) | smaller system |
| `vendor` size | `0x6400000` (100 MiB) | `0x10000000` (256 MiB) | much smaller vendor |
| `odm` size | `0x1400000` (20 MiB) | `0x10000000` (256 MiB) | much smaller odm |
| `cache` size | `0x10000000` (256 MiB) | `0x46000000` (1120 MiB) | |
| `/unifykey` | 19 keys | 17 keys | drops `deviceid` and `region_code`, adds `netflix_mgkid` and `region`, and reorders `hdcp2_rx`/`hdcp2_tx` |
| `/amlvecm` | `cfg_en_osd_100 0x3`, `tx_op_color_primary 0x1` | `0x1`, `0x0` | OSD 100% enabled, colour space set |
| `/firmware/android/vbmeta/parts` | `vbmeta,boot,system,vendor` | `boot,system,vendor` | the aquaman has a vbmeta partition and chains it |
| `/firmware/android/fstab/vendor/fsmgr_flags` | `wait,avb` | `wait` | AVB on vendor |
| thermal trips | 90000/95000/105000/120000 | 70000/80000/85000/260000 | aquaman runs its cooling curve hotter |
| `cpucore_cool_cluster0/min_state` | `3` | `1` | |
| `gpufreq_cool/min_state` | `500` | `400` | |
| `/ram-dump` | no `reg`, no `reg-names` | has both | |

**identical to the reference and therefore not board-specific:** `/model`,
`/compatible`, `linux,usable-memory`, the whole `cpu_iomap` and `codec_io`
window map, `/soc/*` bus layout, every `clock-names` string, the mali
`clocks`/`clock-names`/DVFS table, the mmc/usb/hdmi/codec topology, the
`unifykey` and `efusekey` structure, the `partitions` node shape.

**what the comparison cannot say:** it does not prove the aquaman tree is
derived from p212. it says the two agree on everything structural and differ
on the things a stick differs on. the aquaman is also not a khadas board, and
`amlogic-dt-id` in the khadas tree would have said so.

## 13. anomalies

1. **the "second identical copy" is not one.** §3. `sha256` differs, the head
   8 KiB is an `AML_RES!` resource image, `fdtdump` rejects the blob at
   `0x01080000` outright. the round 8 claim is retracted. only one `d00dfeed`
   exists in the 16 MiB.
2. **`/reserved-memory` overlap.** `linux,secos` `0x05300000..0x07300000`
   (`no-map`) and the `linux,secmon` pool `alloc-ranges 0x05000000..0x05400000`
   both claim `0x05300000..0x05400000`. `secos` is `status = "disable"` in this
   tree, so it is probably dead code here, but the blob does say it.
3. **three `shared-dma-pool` entries with `size = 0`** (`linux,ppmgr`,
   `linux,picdec`, `linux,codec_mm_reserved`), two of them still pointed at by a
   live `memory-region` (`/ppmgr`, `/picdec`). harmless if the driver checks,
   which is not verifiable from the blob.
4. **`/sdio@d0070000` disagrees with itself on the clock.**
   `max-frequency = 0x5f5e100` (100 MHz) at the node level,
   `sdio/f_max = 0xbebc200` (200 MHz) in the child. the child `f_min` is
   `0x61a80` (400 kHz) and `f_max` on the eMMC child is also `0x5f5e100`. the
   blob is internally inconsistent here and the driver picks. not resolved here.
5. **376 MiB of DMA pool demand against 1023 MiB of usable RAM**, with the
   allocator free to place them anywhere. whether they fit is not answerable
   from the blob. `/dmesg` was not consulted.
6. **`/reserved-memory/linux,secos` leaves a 1 MiB hole** at `0x07300000`
   before `ramoops` at `0x07400000`. unexplained.
7. **no `/chosen` node.** no `bootargs`, no `stdout-path` in the tree.
8. **zero regulators in the tree.** §7.
9. **every gpio reference points at the periphs/EE bank**, including the eMMC
   reset and dat3, and including `/jtag/jtagao-gpios` whose name says ao. the
   AO bank `0x8f` is referenced by nothing in the tree. present in the p212
   reference too, so family behaviour and not an aquaman error, but it will
   bite anyone who assumes the aobus bank. §7.
10. **dtc emits 47 warnings** on a perfectly valid blob, all style. §2. the file
    was not "fixed" to silence them, which is the correct call: the warnings
    describe the vendor's tree, not a defect in the extraction.
11. **a fresh device read was not performed this session**, only the round 8
    dump was reused. §1. it is the same bytes and it was already cross checked
    against a second read path, but it is one session, not two.

## 14. files

| file | what |
|---|---|
| `artifacts/aquaman.dtb` | 58280 bytes, `sha256 b00adaba...`, the blob as read, unmodified |
| `artifacts/aquaman.dts` | 65052 bytes, 2945 lines, `dtc -I dtb -O dts`, re-compiles value-identically |
| `artifacts/aquaman-plus0x80000-clobbered.bin` | the 58280 bytes at `0x01080000`, kept so §3 can be rechecked. not a valid FDT |
| `tools/dtb_dump.py` | walks the struct block and prints every property with its offset in the strings block, so any value in this report can be traced to a byte range of the blob |
| `reports/round9-dtb-extraction/00_fdt_validation.txt` | fdtdump header, dtc exit status, warning classes |
| `reports/round9-dtb-extraction/01_dtc_warnings.txt` | all 47 dtc warnings, verbatim |
| `reports/round9-dtb-extraction/02_second_copy.txt` | the §3 measurement |
| `reports/round9-dtb-extraction/03_full_inventory.txt` | every node and every property, 2185 lines |
| `reports/round9-dtb-extraction/04_vs_gxl_p212_1g.txt` | the full §12 diff |
| `reports/round9-dtb-extraction/05_gpio_table.txt` | the full gpio scan, aquaman and p212 |

nothing was written to the stick. the round 8 dump
`reports/round8-bl33-read/mread_01000000_01000000.bin` was read, never
overwritten, and still hashes to `f5e20c9e...`.
