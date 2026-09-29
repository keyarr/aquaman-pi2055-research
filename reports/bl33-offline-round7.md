# BL33 offline, round 7: the dumps we have are the wrong half of RAM

> **superseded by rounds 8 and 10.** two things in §3 changed:
> - §3.2/§3.4 predicted the BL33 image sits at `CONFIG_SYS_TEXT_BASE =
>   0x01000000`. **refuted**: that address holds the device tree. the
>   `/*16MB rsv*/` comment means "16 MiB reserved", not "U-Boot is linked
>   here". round 8 measured it.
> - §9's "one 16 MiB dump of 0x01000000..0x02000000" was done, and it contains
>   a U-Boot fragment at `0x01040000..0x0107ffff`
>   (`reports/bl33-offline-round10.md`).
> §3.3's `_TEXT_BASE` self-reference test is still the right idea and is still
> unrun against a copy that is actually U-Boot.

date: 2026-09-29, round 7. offline only. no usb, no device, no write, no
0x05, no eMMC, no reset, no ghostlock, no bootrom. the only thing that touched
the stick in the previous round was the mread path from round 6, and this round
did not even do that.

headline, and it is not good: **BL33 is not in any dump that exists on disk,
and the 64 MiB that the state sheet says was extracted was never written to a
file.** what is on disk is 1 MiB at 0x20000000, and that 1 MiB is the ART heap
of a running SmartTube process. no U-Boot, no code, not a single strong string.

the useful part is why. round 6 scanned the top of RAM because
`reports/mread-via-bulkcmd.md` §6 concluded "DDR starts around 0x20000000".
**that conclusion is wrong for this board.** the aquaman has 1 GiB with base
0x0, so 0x20000000 is the *middle* of DDR, and 0x3f000000 is the *top*. both
scans looked at the half where the running Android heap lives. U-Boot is at
`CONFIG_SYS_TEXT_BASE` = **0x01000000**, which is 512 MiB below the first byte
that was ever dumped. two wasted scans, one wrong assumption.

## 1. inventory (phase 1)

`python3 tools/bl33_offline.py inventory`, raw in
`reports/round7-bl33-offline/01_inventory.txt`.

| file | range | size | sha256 | source |
|---|---|---|---|---|
| `round6-mread/mread_20000000_000200.bin` | 0x20000000..0x200001ff | 512 | `54eda1c060b34a90…` | mread, cross-checked vs 0x02 |
| `round6-mread/mread_20000000_001000.bin` | 0x20000000..0x20000fff | 4 Ki | `e957a46b5e76afe7…` | mread, cross-checked vs 0x02 |
| `round6-mread/mread_20000000_010000.bin` | 0x20000000..0x2000ffff | 64 Ki | `7ceb4b6f00419e5a…` | mread, cross-checked vs 0x02 |
| `round6-mread/mread_20000000_100000.bin` | 0x20000000..0x200fffff | 1 Mi | `0b1b76d138721ca9…` | mread, cross-checked vs 0x02 |
| `round6-mread/13_scale.txt` line 1 | 0x20000000..0x23ffffff | 64 Mi | `da29df117b8cc7d2` (truncated, 8 bytes) | **not persisted** |
| `round6-mread/13_scale.txt` line 2 | 0x3f000000..0x3f0001ff | 512 | `c8c9de1736043361` (truncated) | **not persisted** |
| `round6-mread/13_scale.txt` line 3 | 0x3f000000..0x3f00ffff | 64 Ki | `b3bfdc496e19762f` (truncated) | **not persisted** |
| `round6-mread/14_scan.txt` | 0x20000000..0x21000000 | 16 Mi | none | **not persisted, hit list only** |
| `round6-mread/14_scan.txt` | 0x3f000000..0x40000000 | 16 Mi | none | **not persisted, hit list only** |
| `round6-mread/16_scan…txt` | 0x20000000..0x22000000 | 32 Mi | none | **not persisted, hit list only** |

the three nested files are byte exact prefixes of each other, verified with
`cmp`. the ladder in `12_ladder.txt` read the same address four times with
growing sizes, so 512 B + 4 KiB + 64 KiB + 1 Mi = **1 MiB of unique RAM**, not
1 MiB + 69 KiB. `mread_20000000_100000.bin` is the whole corpus.

the 64 MiB run streamed into a hash and was dropped on the floor. `13_scale.txt`
prints `sha da29df117b8cc7d2` which is the first 8 bytes of the sha1, and
`mread_scan.py` had no `--save` used in that run, so the 64 MiB is gone. the
throughput number in `mread-via-bulkcmd.md` is real, the data is not.

nothing here is worth re-reading from the device as it stands. the address is
wrong, not the coverage.

## 2. what the 1 MiB actually is (phases 2 and 3)

`02_strings.txt`, `03_classify.txt`, `06_java_heap_proof.txt`.

**STRONG markers: 0 hits out of 24.** the list covers everything the brief
asked for plus a bit more. `U-Boot`, `2015.01`, `g7ac5df7677`,
`aml log : Sig Check`, `aml_sec_boot_check`, `Optimus`, `usb_pcd`,
`usb_burning`, `set_usb_boot`, `do_bootm`, `bootm\0`, `fastboot\0`,
`setenv\0`, `gd->`, `Amlogic`, `bl33\0`, `BL33\0`, `BL2\0`, `loadaddr=`,
`boot_delay`. not one.

what is there instead:

```
0x20006890  log_error                 next to client_side_batching
0x200218a1  http://www.slf4j.org/codes.html
0x2009d424  com.sebby.elitemotolog    next to com.samsung.android.spayx
```

and 16 java package paths including
`com/yuliskov/SmartTube/releases/download/latest/smarttube_stable_arm64`,
`com/youtubei/`, `com/auth/youtube`. that is an ART/Java heap holding a loaded
YouTube/SmartTube process. the two "hits" round 6 reported, `ro.bootmode` at
0x21ab7c99 and the base64 blob at 0x21cb17fa, are the same thing in a
neighbouring megabyte.

the classifier agrees it is not code, and the numbers are unambiguous:

```
0x20000000 ent  3.59  nop    0 ret    0 brk   0  ptr2xx  113 ptr01x 1104
0x20010000 ent  4.91  nop    0 ret    0 brk   0  ptr2xx  139 ptr01x  428
0x20040000 ent  0.18  nop    0 ret    0 brk   0  ptr2xx    0 ptr01x   27
```

**zero AArch64 `nop` (`d503201f`), zero `ret` (`d65f03c0`), zero `brk`
(`d4200000`) in the entire megabyte.** u-boot proper is thousands of `brk #N`
for the `PANIC`/`hang` arch fatal path and a `nop` sled after every trap
handler. a megabyte of u-boot code with zero `brk` is not a different
optimisation level, it is not code at all.

xref, `05_xref.txt`: 3 ADRP pages and 4 `bl` targets land inside the dump.
u-boot proper has hundreds to thousands. 7 in 1 MiB is noise from misaligned
data words.

`04_start_shape.txt`: no u-boot `_start` shape anywhere in the dump, at any
alignment.

## 3. the mistake in round 6, and where BL33 actually is (phase 6)

### 3.1 the device is 1 GiB with base 0x0

three independent sources agree:

| source | value |
|---|---|
| mainline `meson-gxl-s805y-xiaomi-aquaman.dts`, `memory@0` | `reg = <0x0 0x0 0x40000000>` |
| downstream 4.9 `linux,usable-memory` | `<0x0 0x100000 0x0 0x3ff00000>` = 1 MiB hole, 1023 MiB usable |
| `MemTotal 1004412 kB` | 1023 MiB minus 1 MiB hole |
| reference tree `PHYS_SDRAM_1_BASE` (arch-gxl/cpu.h:36) | `0x00000000UL` |

and the read evidence lines up: 0x20000000 and 0x3f000000 both return sensible
Android data, 0x0 removes the device from the bus. 0x20000000 is DDR offset
**512 MiB**, 0x3f000000 is offset **1023 MiB**. `mread-via-bulkcmd.md` §6
wrote "DDR starts around 0x20000000" and built both scans on it. both scans
covered the top 32 MiB and the top 16 MiB of the top half of RAM. the bottom
half, where u-boot lives, was never touched.

### 3.2 the candidate base

`.src/u-boot-khadas/arch/arm/include/asm/arch-gxl/cpu.h`:

```c
#define PHYS_SDRAM_1_BASE        0x00000000UL
#define CONFIG_SYS_TEXT_BASE     0x01000000 /*16MB rsv*/
#define CONFIG_SYS_LOAD_ADDR     (PHYS_SDRAM_1_BASE + CONFIG_SYS_TEXT_BASE)
```

`CONFIG_SYS_TEXT_BASE` is where the FIP and therefore BL33 land. 0x01000000,
16 MiB into DDR, just above the 16 MiB BL2 reservation that the `/*16MB rsv*/`
comment refers to. `DRAM_UBOOT_RESERVE = 0x01000000` in
`drivers/usb/gadget/f_fastboot.c:132` is the same 16 MiB from the other side.

**this is derived from the reference tree, not measured on the device.** the
tree is `khadas/u-boot @ khadas-vims-nougat` (2015.01), the device runs
`2015.01-g7ac5df7677-dirty`, and `bootloader.img` is encrypted (entropy
7.99988, no repeated 16-byte block, zero real strings) so there is no ground
truth binary in the repo. the 0x01000000 is a well-supported family value and
it is the first address to read, but it is not proven.

### 3.3 how one 64-byte read would confirm it, without any guessing

this is the part worth keeping. `arch/arm/cpu/armv8/start.S:22-38`:

```asm
.globl	_start
_start:
	b	reset
	.align 3
.globl	_TEXT_BASE
_TEXT_BASE:
	.quad	CONFIG_SYS_TEXT_BASE
_end_ofs:       .quad  _end - _start
_bss_start_ofs: .quad  __bss_start - _start
_bss_end_ofs:   .quad  __bss_end - _start
```

so at the base address there must be, in the first 8 bytes:

- `+0x00`: a 4-byte unconditional `b` (`0x1400000a`, target `+0x28`)
- `+0x08`: the 8-byte little-endian literal **`0x0000000100000000`**

and since `CONFIG_SYS_TEXT_BASE` *is* the base for a zero-based board, that
quad at `BASE+8` **equals BASE itself**. that is the self-referential relation
the phase 4 criterion asks for, and it is checkable from a single `AM_REQ_READ_MEM`
of 64 bytes. `tools/bl33_offline.py start FILE BASE` implements the test and
scans every 64-byte boundary, so it does not assume the image starts where the
dump starts.

the quad is a raw `.quad` constant, not a relocated symbol, so it reads
0x01000000 **whether or not the binary has been relocated**. that makes it an
identifier for the image rather than for the running code, which is the more
useful of the two. see §6 for what that does to the "running address" question.

three more constants land in the same 64 bytes and give a second and third
independent relation: `COUNTER_FREQUENCY = 0x1800000` (cpu.h:44) is loaded
right after the `switch_el` block, `_end_ofs` is a plausible `_end - _start`
in the 0x100000..0x200000 range, and `adr x0, vectors` + `msr vbar_el1, x0`
(`d51c1c40`) is a fixed opcode pair. that clears the phase 4 bar: three
relations, two of them in different regions (the literal pool and the
instruction stream), alignment trivially 8, relative distances consistent with
a real u-boot.

**caveat, and it is not small:** on GXL the FIP is a container. BL2 runs first
and the u-boot image is one item inside it, so 0x01000000 may be an `aml_image`
header rather than `_start`. if that is the case the `_TEXT_BASE` quad search
still finds it, just a few KiB further in, which is why the test scans rather
than probes one offset.

### 3.4 observed memory map

| range | class | evidence | confidence |
|---|---|---|---|
| 0x00000000..0x000FFFFF | DDR init / BL2 hole | `linux,usable-memory` first 1 MiB reserved | DERIVED, high |
| 0x00000000 | unmapped from TPL, fatal | PROVEN, round 6 `18_scan_low.txt`, device left the bus | PROVEN |
| 0x00100000..0x00FFFFFF | BL2 reservation, 15 MiB | `CONFIG_SYS_TEXT_BASE /*16MB rsv*/` | DERIVED, medium |
| **0x01000000..~0x011FFFFF** | ~~**BL33 image, link/load address**~~ **REFUTED.** it is the device tree at `0x01000000` (`gxl_aquaman_1g`), an `AML_RES!` resource image at `0x01080000`, and 256 KiB of U-Boot at `0x01040000` | round 8 §2, round 10 §2 | **measured, and not what this row predicted** |
| `gd->relocaddr` (unknown) | **BL33 as actually executing** | `board_r.c:293` prints "Now running in RAM - U-Boot at" | DERIVED, low, see §6 |
| `[relocaddr - 64 MiB, relocaddr)` | u-boot malloc arena | `malloc_start = gd->relocaddr - TOTAL_MALLOC_LEN`, board_r.c:262, `TOTAL_MALLOC_LEN = CONFIG_SYS_MALLOC_LEN` | DERIVED, high on size, low on start |
| 0x01000000 (dtb) | u-boot DTB staging | `CONFIG_DTB_MEM_ADDR 0x1000000`, cpu.h:47, **and measured: an FDT is there** | **PROVEN**, round 8 §2 |
| 0x01080000..0x0287FFFF | bootm image window, 24 MiB | `GXB_IMG_LOAD_ADDR 0x1080000` (offset 16 MiB) + `GXB_IMG_SIZE (24<<20)`, end at offset 40 MiB, bl31_apis.h:118-119 | DERIVED, high |
| 0x07500000..0x0B4FFFFF | optimus transfer buffer, 64 MiB | `DDR_MEM_ADDR_START (0x073<<20)` + 2 MiB + 2 MiB, optimus_download.h:64-78 | **board specific, probably wrong here** |
| 0x10200000..0x141FFFFF | fastboot download buffer, 64 MiB | `CONFIG_USB_FASTBOOT_BUF_ADDR 0x10200000` (offset 258 MiB), g_dnl.h:18 | DERIVED, medium |
| 0x20000000..0x200FFFFF | **running android userspace heap** | **PROVEN**, this round, 1 MiB dump, offset 512 MiB | PROVEN, high |
| 0x20000000..0x22000000 | running android userspace/kernel heap | PROVEN, round 6 scan hits, all android | PROVEN, high |
| 0x3f000000..0x40000000 | running android, offset 1008..1024 MiB | PROVEN, round 6 scan hits | PROVEN, high |
| 0x38000000..0x3FFFFFFF | top 128 MiB hidden from u-boot | `CONFIG_SYS_MEM_TOP_HIDE 0x08000000`, gxl_p241_v1.h:469 | DERIVED, medium |

all offsets are from DDR base 0x0. 0x20000000 is 512 MiB in, 0x3f000000 is
1008 MiB in, 0x01000000 is 16 MiB in. round 6 scanned offsets 512 to 544 and
1008 to 1024, the top sixth of the device. the bottom sixth has never been
read. **(round 8 read 16 MiB at offset 16 MiB. round 10 analysed it offline.)**

the optimus buffer line is a trap. `DDR_MEM_ADDR_START ( 0x073<<20 )` is
hardcoded in `optimus_download.h:64` for the KHADAS 128 MiB VIM, with the
comment "FIXME:Make sure [0x818<<20, 0x839<<20] not used by others". on a
1 GiB board either that constant is overridden in the device's own tree or the
optimus transfer buffer lands somewhere else entirely. do not plan a search
around 0x07300000 on the strength of the reference tree.

## 4. RUN_IN_ADDR, static only (phase 7)

nothing was executed. read out of
`drivers/usb/gadget/v2_burning/v2_usb_tool/usb_pcd.c`. the whole of it is the
`AM_REQ_RUN_IN_ADDR` case in `do_vendor_out_complete`, at :621:

```c
case AM_REQ_RUN_IN_ADDR:
	if (ctrl->bRequestType != (USB_DIR_OUT | USB_TYPE_VENDOR |
			USB_RECIP_DEVICE))
		break;
	value = (w_value << 16) + w_index;
	USB_DBG("run addr = 0x%08X\n",value);
	fp = (void(*)(void))value;
	dwc_otg_power_off_phy();
	fp();
	break;
```

| question | answer |
|---|---|
| 1. just `fp()`? | yes. bare `void (*)(void)` indirect call, no arguments, no return value, no register setup beyond what the compiler does. |
| 2. alignment check? | **none.** and `value = (w_value<<16) + w_index` is a 32-bit quantity, so the reachable address space is 0x00000000..0xFFFFFFFF only. anything at or above 4 GiB is simply not expressible in this request. |
| 3. EL change? | **none.** no SMC, no `CurrentEL`, no exception return. `fp()` executes in the EL that `dwc_otg_irq()` runs in, which is the DWC interrupt handler in u-boot proper, i.e. EL1 for a GXL board handed over by BL31. so `fp()` **cannot call into BL31/BL32 directly**, any secure check still has to go through an `smc #0`. |
| 4. cache maintenance? | **none before the call.** `dwc_otg_power_off_phy()` is one MMIO write, `dwc_write_reg32(DWC_REG_PCGCCTL, 0xF)` (dwc_pcd.c:633-636), it touches no memory and creates no coherency requirement of its own. but there is no `flush_dcache_range` and no icache invalidate before jumping. anything the device wrote into the target range has to be visible to the core already, or `fp()` executes stale bytes. |
| 5. does the address need to be in a specific region? | **no explicit check.** but `0xF` into PCGCCTL gates the PHY and the core clock. if `fp()` returns, the poll loop continues with a dead controller and the stick falls off the bus. it is one-way: `fp()` must not return, or it must bring the controller back. |
| 6. could it run code already in RAM? | **yes, mechanically.** nothing validates the target, and u-boot's flat mapping makes all of DDR data+exec. any address the host can put in wValue/wIndex is a valid function pointer. |

the setup side at :474 only parks `value` and the ep0 buffer, so nothing
happens until the status stage completes. that means the sequence is: send the
OUT control transfer, and the call fires inside the completion handler.

## 5. do_bootm and aml_sec_boot_check, from the tree (phase 5)

`common/cmd_bootm.c:133-147`, verbatim, this is the function the brief is
actually after:

```c
unsigned int nLoadAddr = GXB_IMG_LOAD_ADDR; //default load address
if (argc > 0) {
	char *endp;
	nLoadAddr = simple_strtoul(argv[0], &endp, 16);
}
int nRet = aml_sec_boot_check(AML_D_P_IMG_DECRYPT,nLoadAddr,GXB_IMG_SIZE,GXB_IMG_DEC_ALL);
if (nRet) {
	printf("\naml log : Sig Check %d\n",nRet);
	return nRet;
}
```

with `arch/arm/include/asm/arch-gxl/bl31_apis.h:109-123`:

| symbol | value |
|---|---|
| `AML_DATA_PROCESS` | `0x820000FF` |
| `AML_D_P_IMG_DECRYPT` | `0x40` |
| `GXB_IMG_SIZE` | `(24<<20)` |
| `GXB_IMG_LOAD_ADDR` | `0x1080000` |
| `GXB_IMG_DEC_ALL` | `0x7` (KNL\|RMD\|DTB) |

and `aml_sec_boot_check` at `arch/arm/cpu/armv8/gxl/bl31_apis.c:255-308`, which
is a bare SMC wrapper, `x0=AML_DATA_PROCESS x1=type x2=buf x3=len x4=option`,
`smc #0`, then `flush_dcache_range(pBuffer, pBuffer+nLength)`. all of the
parsing and the actual signature verification is inside BL31/BL32, which is a
closed binary and is the reason none of this has been bypassed in six rounds.

`do_bootm` itself is reachable two ways: the `bootm` command
(`U_BOOT_CMD(bootm, ...)`) and `do_bootm_on_complete` in
`drivers/usb/gadget/f_fastboot.c:569-580`, which is what `fastboot boot` hits:

```c
sprintf(boot_addr_start, "0x%lx", load_addr);
do_bootm(NULL, 0, 2, {"bootm", boot_addr_start, NULL});
do_reset(NULL, 0, 0, NULL);
```

so under fastboot the flow is `f_fastboot` → `do_bootm_on_complete` →
`do_bootm` → `aml_sec_boot_check` → `smc #0` → BL31, and the only interesting
branch on the whole path is the `if (nRet)` four lines above.

**the string `aml log : Sig Check ` does not exist in the 1 MiB dump.** per
the brief that is not proof the path is absent, and it is not: the dump is the
wrong 1 MiB of a 1 GiB device. it is, however, a perfect single 32-byte search
key for the 0x01000000 read, and it is unambiguous when it hits, because no
android process has that string.

## 6. what a future patch would need (phase 8)

no bytes proposed, nothing written, nothing run. just the prerequisites.

| question | answer |
|---|---|
| is BL33 in writable RAM? | yes by construction, it is loaded into DDR by BL2 and executes from there. whether the *optimizer* can write there is a different question and out of scope: 0x02 is read-only, and the write verbs (`FILL_MEM`, `MODIFY_MEM`, `WR_LARGE_MEM`) were not touched this round. |
| is the code in a readable, probably executable region? | **unknown, untested.** the reference tree maps all of DDR data+exec, and the mread path already proved the device can `memcpy` out of 0x20000000, so the read side is fine. whether 0x01000000 is readable through the same path is the one measurement this round was missing. |
| duplicate copy of BL33? | **possible, and that is a real possibility, not a guess.** `board_r.c:293` prints "Now running in RAM - U-Boot at: %08lx", so u-boot does relocate itself, and the link/load copy at `CONFIG_SYS_TEXT_BASE` and the executing copy at `gd->relocaddr` are different addresses. if the device's build relocates, there are two copies of the image in RAM, and the `_TEXT_BASE` quad reads 0x01000000 in *both* of them. which means one fingerprint read can find both. that is a side effect worth having, not a problem. |
| is there relocation? | yes, and this is the part that breaks the obvious method. `do_bootm` is wrapped in `#ifdef CONFIG_NEEDS_MANUAL_RELOC` (cmd_bootm.c:97-110) and does `cmd_bootm_sub[i].name += gd->reloc_off`, and `init_sequence_r[i] += gd->reloc_off` in board_r.c:892. so the `cmd_tbl` name pointers in RAM are already absolute and their values encode `gd->relocaddr`, not the link-time base. **you cannot solve for BASE from a string pointer without also knowing the relocation offset.** the `_TEXT_BASE` self-reference from §3.3 sidesteps this entirely, which is why it is the anchor to use. |
| first interesting point before `aml_sec_boot_check`? | the argument parse. `do_bootm:137` `nLoadAddr = simple_strtoul(argv[0], &endp, 16)`, and the sub-command dispatch at :120-131 above it. the value produced there is exactly what gets handed to BL31 as `x2`, so anything that changes what `nLoadAddr` is worth understanding before touching the check itself. |
| is there an instruction or branch to study later? | yes, one, and it is on the C side of the SMC. between :142 and :145, after `smc #0` returns into `x0`, there is a conditional branch that either falls into the error return or falls through to `ee_gate_off()`. it is the only branch between the SMC and the boot. the ADRP that materialises the `"\naml log : Sig Check %d\n"` address locates it. |

none of that is a plan, and none of it has been tested. the read at 0x01000000
has to come first.

## 7. phases, status

| phase | status |
|---|---|
| 1. inventory of existing dumps | **done**, §1. headline: 1 MiB of unique data, not 64 |
| 2. signature search | **done**, §2. 0/24 strong markers. weak hits are all java |
| 3. u-boot structure search | **done**, §2. 0 nop / 0 ret / 0 brk, no `_start` shape, 7 xrefs in 1 MiB |
| 4. base from internal references | **not applicable**, no candidate in the data. the test that would settle it is written, §3.3 |
| 5. do_bootm -> aml_sec_boot_check | **done from source**, §5. not found in RAM, RAM is the wrong megabyte |
| 6. memory model | **done**, §3.4 |
| 7. RUN_IN_ADDR static | **done**, §4. bare `fp()`, no alignment check, no EL change, no cache maintenance, 32-bit address space only |
| 8. future patch prerequisites | **done**, §6, no bytes |

## 8. what was written

- `tools/bl33_offline.py`, new, offline only. `inventory` / `strings` /
  `classify` / `start` / `xref`. `start` is the `_TEXT_BASE` self-reference
  test from §3.3 and is the piece to reuse next round.
- `tools/mread_scan.py`, the marker list split into `MARKERS` (24 strings that
  only exist in a u-boot or optimus image) and `NOISE` (4 substring traps,
  counted and capped, never printed as an address list). the previous single
  list is why round 6 reported 210 "ddr" hits and 1 "bootm" hit and called it
  a scan. the missing strings the brief asked for (`2015.01`,
  `g7ac5df7677`, `aml log : Sig Check`, `usb_pcd`, `usb_burning`,
  `set_usb_boot`, `do_bootm`, `optimus_buf_manager`) are in there now.
  `bootm`, `setenv`, `fastboot`, `bl33`, `BL33` and `BL2` are matched **with
  their trailing NUL**, because that is how `cmd_tbl` stores them and it is
  exactly what separates u-boot `bootm` from android `ro.bootmode`, and u-boot
  `BL2` from the base64 blob round 6 tripped on. caveat: that fix cannot be
  self tested on what is left of round 6, the two false positives lived at
  0x21ab7c99 and 0x21cb17fa, in the megabytes that were never written to disk.
  what *is* verified is that the new list finds nothing in the 1 MiB we do
  have.
- `reports/round7-bl33-offline/`, the raw output.

## 9. next two steps, both read only

> **both steps were done, in rounds 8 and 10.** step 1 returned the FDT magic,
> step 2 produced `reports/round8-bl33-read/mread_01000000_01000000.bin`
> (`f5e20c9e...`), and analysing it offline found the U-Boot fragment at
> `0x01040000..0x0107ffff`. current next steps are in
> `reports/bl33-offline-round10.md` §8. the step 2 follow-up below, reading
> `0x02000000..0x03000000`, **has not been done.**

**step 1, one 64-byte read at 0x01000000.** not a scan, a probe. it answers
three questions at once: is the region mapped at all, is it reachable through
`0x02` or through mread, and does the `_TEXT_BASE` self reference land. do it
as a ladder like round 6 `12_ladder.txt`, 0x200 then 0x1000 then 0x10000, and
cross check every step against the other read verb. if `b reset` plus a quad
equal to the base address shows up, the base is confirmed in one read and
everything after this is mechanical. if 0x01000000 is unmapped the same way 0x0
was, that is also an answer, and it means the FIP is somewhere else and the
`CONFIG_SYS_TEXT_BASE` value does not transfer from the KHADAS tree.

**step 2, one 16 MiB dump of 0x01000000..0x02000000 with `--save`.** that is
the whole 16 MiB `/*16MB rsv*/` window, it is 1.1 s of transfer at 15 MiB/s,
and it is the region the `01000000` candidate plus `loadaddr 0x1080000` plus
`GXB_IMG_SIZE 24 MiB` all sit inside or next to. run `bl33_offline.py` on the
saved file, not on the stream. round 6 threw away 64 MiB of data it could not
re-search; do not do that again.

if 16 MiB is not enough, the next band up is 0x02000000..0x03000000, because
`GXB_IMG_SIZE` runs to 0x02880000 and the 24 MiB SMC window has to be clear of
u-boot for the check to be meaningful. but that is a scan and it should only
happen after step 1 says the region is mapped.

one thing to keep in mind for whichever band wins: if the device's build
relocates, there are **two** copies of the u-boot image, one at the link address
and one at `gd->relocaddr`. **the link address is not 0x01000000** — that is a
DTB. `bl33_offline.py start` scans rather than probing one offset, so it will
find both copies if they are in the dump; it found neither in the round 8 dump,
which is consistent with `_start` being in a part of BL33 that is not there.
see `bl33-offline-round10.md` §5, where the relocation delta is measured as a
smell and explicitly left **NOT PROVEN**.

explicitly **not** in either step: `0x05`, `setenv`, `saveenv`, `flash`,
`erase`, `burn`, `reset`, ghostlock, bootrom, and any address under 0x00800000.
the 0x0 result from round 6 stands, the stick does not come back from that.
