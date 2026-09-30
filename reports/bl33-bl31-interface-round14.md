# BL33 round 14: the BL33 → BL31 interface, and what else the host can reach

date: 2026-09-29, round 14. **strictly offline this round** — no USB, no device, no
read command at all. every number below comes from the round-13 DRAM dump
(`reports/round13-reloc-verify/mread_37800000_00800000.bin`, sha256 `3d2eca1d…`,
byte-identical to round 12) plus the reference source in `.src/u-boot-khadas`.
no `0x05`, no RAM write, no patch, no eMMC, no flash, no `setenv`/`saveenv`, no
reset, no BootROM, no GhostLock, no payload, no `set_usb_boot` re-run.

the brief's question, verbatim:

> o BL33 oferece algum caminho privilegiado além do `aml_sec_boot_check` que
> possa ser investigado estaticamente?

**answer: yes — four of them**, and the sharpest one is not a SMC at all: the
fastboot `oem` command is a host-driven `run_command()`, i.e. the whole U-Boot
CLI, and unlike `flash`/`erase`/`flashall`/`set_active` it does **not** consult
the device lock state. the SMC surface itself is small, fully enumerated (15
`smc #0` sites, 5 of them security-relevant) and every path that reaches
`aml_sec_boot_check` is a *verification* path, not a bypass.

## 0. answer block

```text
image                   0x37e18000 .. 0x37ff0000   (0x1d8000 = 1,933,312 B)
image sha256            664fb34a9c6d92cdcd576659fb5359bd5218841612dbf38c01426c5d3c1b7818
reloc_off               0x36e18000   (link base 0x01000000)
smc #0 sites (exact)    15            5 security-relevant
ids materialised        22 distinct 0x82xxxxxx + 1 x 0xb2000016 + PSCI 0x84000009
aml_sec_boot_check      15 call sites in 7 functions, all verification paths
fastboot commands       13 dispatch slots, 4 lock-gated, 'oem' NOT lock-gated
'oem' handler           0x37e95630: strnlen(cmd,32) -> memcpy -> strsep -> run_command
run_command             0x37e5e968
v2 burning entry        cmd 'update' 0x37e78ff8 -> 0x37e78f94 (host memory r/w protocol)
secure storage module   0x37e8bb78..0x37e8c1xx: key read/write SMCs, NO callers
live storage SMC        0x82000028 SET_STORAGE_INFO, on the mmc/storage init path
confidence              HIGH for every address and id above
```

## A. the BL33 image

### A.1 why the image is bigger than the brief assumed

the brief asked for `0x37e18000..0x37f80000` (0x180000). that window is real but
**short by 0x70000**: the end of a relocated U-Boot is a computation, not a
guess. `arch/arm/lib/board.c:255-437` (`setup_dest_addr`):

```c
gd->mon_len = (ulong)&__bss_end - (ulong)_start;
addr  = CONFIG_SYS_SDRAM_BASE + get_effective_memsize();   /* ram top */
addr -= PGTABLE_SIZE;  addr &= ~0xffff;                    /* page table */
addr -= gd->mon_len;   addr &= ~0xfff;                     /* = relocaddr */
```

with `PGTABLE_SIZE = 0x10000` (`arch/arm/include/asm/system.h:17`) and the
measured `relocaddr = 0x37e18000`, the two unknowns collapse: ram top must be
`0x38000000` and `mon_len ∈ (0x1d7000, 0x1d8000]`. two independent checks:

- the last non-zero byte inside `[0x37e18000, 0x37ff0000)` is `0x37feffff` — the
  top of that window — and the bytes below it are the relocated `.bss`;
- the 64 KiB *above* the window is the page table: `0x37ff0000` begins a run of
  **8192** descriptor-shaped words (`0x…0411`, `0x…0401`), i.e. a full
  `PGTABLE_SIZE`, ending exactly at `0x38000000`.

so the image is `[0x37e18000, 0x37ff0000)`, `0x1d8000` bytes, and it was cut out
of the round-13 band with `tools/bl33_persist.py` (offline; it reads the dump,
hashes, classifies pages, writes the image, opens no device). if a live re-read
is ever wanted, the same band is reachable with `tools/reloc_read.py`; there is
no evidence to expect a different result, because two independent boots already
produced one hash.

### A.2 artifact

| item | value |
|---|---|
| file | `reports/round14-bl33-persist/bl33-37e18000.bin` |
| load / run address | `0x01000000` (link) / `0x37e18000` (relocaddr) |
| relocation offset | `0x36e18000` |
| size | `0x1d8000` = 1,933,312 B |
| **sha256** | `664fb34a9c6d92cdcd576659fb5359bd5218841612dbf38c01426c5d3c1b7818` |
| source band | `reports/round13-reloc-verify/mread_37800000_00800000.bin`, sha256 `3d2eca1d7c4030250fef733272878c0ca0f3b798b9ae4ba54a110b7e1012b04e` |
| prior dumps | untouched; nothing overwritten |

> the artifact is 1.9 MiB. `.gitignore` currently excludes only the round-6 and
> round-8 `.bin` files, so whether this one is committed is the repo owner's call;
> `reports/round14-bl33-persist/00_persist.txt` carries the hash either way.

### A.3 region map (from `00_persist.txt`)

| range | content |
|---|---|
| `0x37e18000` | `_start` (`b +0x28`, `.quad 0x01000000`), `.text` begins |
| `0x37e19000..0x37e6a000` | dense code (`bl31_apis.c` wrappers at `0x37e19d00`, …) |
| `0x37ebe000..0x37ee3000` | `.rodata` — banners, `printf` formats, the fastboot strings |
| `0x37ee3000..0x37f5a000` | drivers' `.text`/`.data` interleaved (mmc, usb, xdma…) |
| `0x37f60000..0x37f61000` | the AML partition table, `fastboot_context`, `AML_TABLE` names |
| `0x37f60fd0..` | `.u_boot_list` — `cmd_tbl` (80 slots recovered, §C) |
| `0x37f73000..0x37fbe000` | `.bss`, 128 KiB of it still zero |
| `0x37f8a638` | **live `.bss`**: the USB-tool command buffer, still holding the literal the round-13 read left behind (`'upload mem 0x37800000 normal 0x800000'`) |
| `0x37fef000..0x37ff0000` | last data page, then the page table at `0x37ff0000` |

the `.bss` observation matters: a region that is zeroed at relocation and later
written by the burning protocol proves that (a) the window is inside the image
and (b) the image is the *live* copy, not another stale one.

## B. SMC inventory — every `smc #0` in the image

opcode-exact (`imm16 == 0`); five data words that decode as `smc #0x1234` were
rejected by that filter (`reports/round14-bl33-persist/02_smc.txt` has the
proof, and the raw table is in `01`…`19` files). x0 is reconstructed by constant
propagation over the containing function (`tools/bl33_audit.py smc`), and for
two-instruction stubs by asking each `bl` caller what it passes.

| # | site | wrapper | x0 | purpose | input source | conf |
|---|---|---|---|---|---|---|
| 1 | `0x37e19d68` | shared stub | argument | share-mem base getter (`get_sharemem_info`) | callers pass `0x82000020`, `0x82000021` | HIGH |
| 2 | `0x37e19e28` | `0x37e19d70` `meson_trustzone_efuse` | `{0x30,0x31,0x32}` (branch-selected) | efuse read / write / write-pattern (`EFUSE_READ/WRITE/WRITE_PATTERN`) | `struct efuse_hal_api_arg` from `cmd_efuse.c`/`efuse_user` | HIGH (id set) |
| 3 | `0x37e19e88` | `0x37e19e80` | `0x82000033` | `EFUSE_USER_MAX` | constant | HIGH |
| 4 | `0x37e19e9c` | `0x37e19e98` `aml_reboot` | argument | reboot / system-off | `aml_system_off` → `0x82000042`; `reboot` cmd → `0x84000009` (PSCI) | HIGH |
| **5** | **`0x37e19ed8`** | **`0x37e19ea8` `aml_sec_boot_check`** | **`0x820000ff`** | **`AML_DATA_PROCESS`** — image/efuse verify | **15 call sites, §D** | HIGH |
| **6** | **`0x37e19f08`** | **`0x37e19efc` `set_usb_boot_function`** | **`0x82000043`** | **`SET_USB_BOOT_FUNC`** | **`set_usb_boot` cmd argv[1], unvalidated; also constant `1`** | HIGH |
| 7 | `0x37e19fac` | `0x37e19f4c` `__get_chip_id` | `0x82000044` (+`0x21`) | `GET_CHIP_ID` | `chipid` cmd, out buffer = shared mem | HIGH |
| 8 | `0x37e1a148` | `0x37e1a0e0` | `0x82000018` | hdmitx reg read (`reg_ops.c`) | constant | HIGH |
| 9 | `0x37e1a164` | `0x37e1a150` | `0x82000019` | hdmitx reg write | constant + data | HIGH |
| 10 | `0x37e1c7d4` | `0x37e1ab44` | `0x82000012` | `SRAM_ACS_READ` (hdmitx20) | constant | HIGH |
| **11** | **`0x37e635a0`** | **`0x37e63534` `tee_log_level`** | **`0xb2000016`** | **second SMC family — TEE log level** | **argv[1] parsed as decimal** | **HIGH** |
| **12** | **`0x37e8bba0`** | **`0x37e8bba0` `bl31_storage_ops`** | **argument** | **secure storage ops** | **8 callers, §B.1** | **HIGH** |
| **13** | **`0x37e8bba8`** | **`0x37e8bba8` `bl31_storage_ops2`** | **argument** | **`0x8200006a` `SET_ENCTYPE`** | `0x37e8c14c` passes the constant | HIGH |
| 14 | `0x37e8bbb0` | `0x37e8bbb0` `bl31_storage_ops3` | argument | `NOTIFY_EX` by elimination (3-arg stub) | **no `bl` caller found** | MED |
| **15** | **`0x37e8c144`** | **`0x37e8c138` `secure_storage_set_info`** | **`0x82000028`** | **`SET_STORAGE_INFO`** | **constant; caller = mmc/storage init, §B.2** | **HIGH** |

### B.1 the secure-storage driver: which id each wrapper sends

`drivers/securestorage/securestorage.c` in the reference tree, matched to the
image (`tools/bl33_audit.py smc`, file `02_smc.txt`):

| wrapper in the image | reference function | id(s) sent |
|---|---|---|
| `0x37e8bbb8` | `secure_storage_init` | `0x23`, `0x24`, `0x25`, `0x27` |
| `0x37e8bc84` | `secure_storage_getbuffer` | `0x27` (`GET_SHARE_STORAGE_BLOCK_SIZE`) |
| `0x37e8bd10` | `bl31_storage_write` | `0x62` (`SECURITY_KEY_WRITE`) |
| `0x37e8bdc8` | `bl31_storage_read` | `0x61` (`SECURITY_KEY_READ`) |
| `0x37e8be98` | `bl31_storage_query` | `0x60` (`SECURITY_KEY_QUERY`) |
| `0x37e8bf3c` | `bl31_storage_status` | `0x65` (`SECURITY_KEY_STATUS`) |
| `0x37e8bfe0` | `bl31_storage_tell` | `0x63` (`SECURITY_KEY_TELL`) |
| `0x37e8c084` | `bl31_storage_verify` | `0x64` (`SECURITY_KEY_VERIFY`) |
| `0x37e8c14c` | `secure_storage_set_enctype` | `0x6a` |
| `0x37e8c138` | `secure_storage_set_info` | `0x28` |

**the module is complete and dormant.** every *public* entry point
(`secure_storage_read/write/query/status/tell/verify/list/remove`,
`amlkey_write`) has **zero** `bl`/`b`/`blr` callers and **zero** pointer-table
entries anywhere in the image (`reports/round14-bl33-persist/11_ss_api_callers.txt`,
plus an 8-byte pointer scan that found 0 hits for all of them). the only live
secure-storage SMC is `SET_STORAGE_INFO` (§B.2). `SECURITY_KEY_WRITE` — the
interface the brief cares about most — is reachable only from code that nothing
calls.

### B.2 what is actually live

- `0x37e905d8` → `secure_storage_set_info` (`0x82000028`), inside
  `0x37e904ac` ("mmc/storage init", strings `mmc_init`, `pattern`), which is
  itself called from 37 sites in the mmc/storage layer. so `SET_STORAGE_INFO` is
  on the storage init path, reachable at boot and from any `mmc`/`store`
  command — a real BL33→BL31 call, but its argument is a storage-geometry value,
  not a key.
- `bl31_storage_ops` is also called from two places inside `meson_trustzone_efuse`
  and `__get_chip_id` to obtain the *share-memory* bases (`0x82000020`/`0x82000021`),
  not key material.

### B.3 ids in the header that the image never materialises

`ABSENT` in the whole image (`19_id_census.txt`): `GET_REBOOT_REASON 0x82000022`,
`GET_SHARE_STORAGE_MESSAGE_BASE 0x26`, `JTAG_ON/OFF 0x40/0x41`,
`SECURITY_KEY_NOTIFY/LIST/REMOVE/GET_ENCTYPE/VERSION 0x66/0x67/0x68/0x6b/0x6c`,
`DEBUG_EFUSE_WRITE/READ_PATTERN 0xf0/0xf1`, `CALL_TRUSTZONE_HAL_API 0x5`.
present: `0x12, 0x18, 0x19, 0x20, 0x21, 0x23, 0x24, 0x25, 0x27, 0x28, 0x30-0x33,
0x42, 0x43, 0x44, 0x60-0x65, 0x69, 0x6a, 0xff`, `0xb2000016`, `0x84000009`.

that is the whole `0x820000xx` inventory of this firmware: nothing in the image
jumps into the secure world with an id that is not in the list above.

## C. Fastboot surface — host input as far as it goes

`rx_handler_command` is at `0x37e95738`: it walks a 13-entry `{char *cmd;
void (*cb)}` table at `0x37eb5bc8` (`cmp x20,#0xd`), compares with the
L1-prefix helper `0x37e94aa0`, and calls the callback. the table
(`09_fb_table.txt`):

| slot | command | callback | lock check? | backend (from `13_fb_backends.txt`) |
|---|---|---|---|---|
| `0x37eb5bc8` | `reboot` | `0x37e95204` | no | fastboot response + restart |
| `0x37eb5bd8` | `getvar:` | `0x37e95ecc` | yes (`0x37e9593c`) | env/partition/slot queries, `get_valid_slot` |
| `0x37eb5be8` | `download:` | `0x37e95408` | no | `simple_strtoul` size, `ddr_size_usable` check, then USB RX into the download buffer |
| `0x37eb5bf8` | `boot` | `0x37e94db0` | no | `run_command` (`0x37e5e968`) |
| `0x37eb5c08` | `continue` | `0x37e94d88` | no | `run_command` |
| `0x37eb5c18` | `flash` | `0x37e95d50` | **yes** | mmc write of the downloaded buffer |
| `0x37eb5c28` | `update` | `0x37e95408` | no | same as `download:` |
| `0x37eb5c38` | `flashall` | `0x37e95c90` | **yes** | mmc write |
| `0x37eb5c48` | `erase` | `0x37e95b20` | **yes** | mmc erase |
| `0x37eb5c58` | `devices` | `0x37e94de8` | no | prints `AMLOGIC` |
| `0x37eb5c68` | `reboot-bootloader` | `0x37e95204` | no | restart |
| `0x37eb5c78` | `set_active` | `0x37e95a14` | **yes** | `set_active_slot %s` |
| **`0x37eb5c88`** | **`oem`** | **`0x37e95630`** | **no** | **`run_command` — arbitrary U-Boot command** |

the lock helper is `0x37e9593c`; its callers are exactly
`set_active`, `erase`, `flashall`, `flash`, and `getvar` (twice, for the
`unlocked` variable). `cb_oem` is **not** among them, and its complete transfer
list contains no lock check — the strings `FAILlocked device` /
`ERROR: device is locked, can not run this cmd…` live in the other callbacks.

### C.1 the `oem` handler, instruction for instruction

```
0x37e95630  stp  x29,x30,[sp,#-0x50]!
0x37e95638  ldr  x1, [x1]              ; the received command string
0x37e9563c  adrp x0, #0x37ede000
0x37e95640  add  x0, x0, #0xf15        ; "oem cmd[%s]"
0x37e9564c  bl   #0x37e593c8           ; printf
0x37e95654  mov  x1, #0x20
0x37e9565c  bl   #0x37eaada0           ; strnlen(cmd, 32)      <- clamp
0x37e95660  add  x2, x0, #1            ; n = min(strlen,32)+1
0x37e95668  add  x0, x29, #0x20        ; local buffer, 0x30 B to frame end
0x37e9566c  bl   #0x37eaaeec           ; memcpy(buf, cmd, n)
0x37e95678  str  x0, [x29, #0x48]
0x37e9567c  add  x1, x1, #0xa0d        ; " "
0x37e95684  bl   #0x37eaae44           ; strsep(&p, " ")  -> token "oem"
0x37e95690  add  x0, x0, #0xf22        ; "[MSG]To run cmd[%s]"
0x37e95694  bl   #0x37e593c8           ; printf(p)
0x37e95698  ldr  x0, [x29, #0x48]      ; everything after "oem "
0x37e9569c  mov  w1, #0
0x37e956a0  bl   #0x37e5e968           ; run_command(p, 0)
```

`0x37eaada0` is `strnlen` (`end = s+n; while (p != end && *p) p++; return p-s`)
and `0x37e5e968` is `run_command` (`and w1,w1,#4; csel w1,#0xb,#3` then the shell
parser at `0x37e23438`; 261 call sites in 76 functions across the image,
including `do_run` at `0x37e5ea04`). `cb_boot` and `cb_continue` reach the same function,
which is why `fastboot boot` still ends at the verified path (§D).

so the host can run any U-Boot command through `oem`, truncated to 31
characters. the command set is the 80-entry `cmd_tbl` recovered in
`04_cmds.txt`: `bootm`, `store`, `unpackimg`, `dtimg`, `imgread`, `efuse`,
`efuse_user`, `keyman`, `keyunify`, `setenv`, `env`, `printenv`, `run`, `mmc`,
`amlmmc`, `gpt`, `rsvmem`, `update`, `ddrtest`, `ddr_tune_dqs`, `set_trim_base`,
`temp_triming`, `write_trim`, `write_version`, `systemoff`, `reset`, `reboot`,
`fastboot`, `usb`, `setkeys`, `set_usb_boot`, `ui`, `osd`, … — with each
command's own validation being the only thing between the host and it.

## D. Security surface

### D.1 the verified path (`0x820000ff`, 15 call sites in 7 functions)

every `bl aml_sec_boot_check` with its argument setup is in
`12_secboot_args.txt`. the 7 users and their families:

| function | command / layer | sites | x0 (type) | buffer / length |
|---|---|---|---|---|
| `0x37e24c00` | `bootm` (`do_bootm`) | `0x37e24cf0`, `0x37e24f90` | `0x40` `IMG_DECRYPT` | host/user argv address, or default `0x1080000`; `0x1800000` / `0x500` |
| `0x37e2a030` | DTB/partition validation (`check_valid_dts`) | `0x37e2a088`, `0x37e2a0c4` | `0x40` | partition buffer, `0x500` |
| `0x37e33e00` | `store` / `store_interface` (`do_store_dtb_ops`, `[store]Err`) | 4 sites | `0x40` | partition buffer, `0x500` / `0x3fe00` |
| `0x37e35e7c` | `imgread`/`unpackimg` (`AMLSECU!`, `Err imgread`) | 1 | `0x40` | `0x500` |
| `0x37e3601c` | `imgread`/`unpackimg` | 1 | `0x40` | `0x1800000` |
| `0x37e362e0` | `imgread`/`unpackimg` | 1 | `0x40` | `0x500` |
| `0x37e562e8` | `cmd_efuse.c` (`secure_boot_set`, `password_set`, `customer_id_set`, `amlogic_set`) | 4 | `0x10`, `0x11`, `0x12`, `0x20` | `0x500` each |

this is the whole verified set, and it matches `common/cmd_bootm.c`,
`common/store_interface.c`, `common/partitions.c`, `common/cmd_imgread.c` and
`common/cmd_efuse.c` from the reference tree — 8 source call sites expanded to
15 machine call sites. **key/efuse writes are inside this set** (types `0x10`,
`0x11`, `0x12`, `0x20`), i.e. the efuse-writing commands are gated by the same
SMC as boot.

no fastboot callback calls `aml_sec_boot_check` directly — the host's `boot` and
the burning tool's `bootm` both enter it *through* `bootm`, so the check is not
skipped by coming from USB.

### D.2 non-verified privileged paths

| path | reachable by | privileged operation | guarded by |
|---|---|---|---|
| `oem <cmd>` → `run_command` | USB host, any boot | any of the 80 U-Boot commands, 31 chars | nothing (no lock check) — each command's own checks |
| `set_usb_boot <val>` → `0x82000043` | host via `oem`, or the CLI | asks BL31 to set the USB-boot flag | no range validation in BL33 |
| `update <ms>` → `0x37e78f94` | host (fastboot `update`, or `oem update`) | enters the v2 usbburning protocol: RAM read/upload, download, image write, `bootm` | none in BL33; this is the interface rounds 7-13 used to read RAM at all |
| `keyman` / `keyunify` | host via `oem` | unifykey: reads `/unifykey` from the DTB and reads/writes keys (`key-name`, `key-type`, `key-device`, `key-permit`, `secure`, `normal`, `efuse`) | to be established (§D.3) |
| `secure_storage_set_info` → `0x82000028` | storage init, every `mmc`/`store` | tells BL31 the storage geometry | constant argument |
| `tee_log_level` → `0xb2000016` | host via `oem` | sets TEE log level (second SMC family) | none in BL33 |
| `efuse` / `efuse_user` / `mmc write` / `env save` | host via `oem` | efuse read, eMMC write, persistent env | efuse writes go through the verified path; `mmc write` and `env` do not |

### D.3 unknown / to be established

- the **persistence backend of unifykey**: `keyman`/`keyunify` call
  `keymanage_dts_*` (`0x37e75590`, `0x37e756e4`, `0x37e757ec`) and the storage
  stack at `0x37e7xxxx`; whether a key ends up in the `secure` eMMC area, the
  `normal` area, or efuse is not yet pinned from the code (`18_key_module.txt`).
- the **v2 burning protocol's command set** (parser functions `0x37e76aa4`,
  `0x37e77cf8`, global command buffer at `0x37f8a638`, literals `upload`,
  `download`, `identifyWaitTime`, `Enter v2 usbburning mode`): the endpoints and
  their validation were not enumerated this round. this is a legitimate target
  for round 15 because it is the surface that already gave RAM access.
- everything **behind** `smc #0`: the policy and the key live in BL31/BL32, which
  is still not in the dump. nothing here changes `amlsecu-key-path.md`.

## E. Static audit findings

severity: `informational` / `suspicious` / `strong candidate`. no payload was
built, nothing was executed, and none of these is claimed as an exploit.

**E1 — `oem` executes host-supplied U-Boot commands without the lock check
(strong candidate, interface)**
- evidence: dispatch slot `0x37eb5c88` `{ "oem", 0x37e95630 }`; the handler's
  `strnlen/memcpy/strsep/run_command` sequence (§C.1); the lock helper
  `0x37e9593c` is called by `flash`, `erase`, `flashall`, `set_active`, `getvar`
  and **not** by `cb_oem`; the strings `FAILlocked device` /
  `ERROR: device is locked, can not run this cmd. Please flashing unlock…`
  belong to the other callbacks.
- reason: whatever the lock state is meant to protect (`flash`/`erase`), the host
  can reach the same effect through `oem mmc write …`, `oem env`, `oem store`,
  `oem update`, `oem keyman`, subject only to each command's own checks. this is
  an asymmetry between two host interfaces, not a memory-safety bug.
- caveat: `oem` is the vendor's designated escape hatch and the device in this
  project is deliberately unlocked, so the *impact* of the missing check depends
  on the intended threat model. what is proven here is only the asymmetry.

**E2 — the `oem` copy can leave the local buffer unterminated (suspicious)**
- evidence: `n = strnlen(cmd, 32)`; `memcpy(buf, cmd, n+1)`; the destination is
  0x30 bytes (`x29+0x20`); then `strsep(&p, " ")` walks it.
- reason: when the received command is ≥32 bytes, `buf[32] = cmd[32] != 0`, so
  the NUL terminator is never copied and `strsep` scans past the copied region
  into uninitialised stack before stopping. `run_command` then receives a string
  that can contain stack bytes. there is **no** overflow: the copy is clamped to
  33 bytes and the frame has 48. this is a parsing/robustness defect, and it is
  bounded, so it is *not* by itself a memory-corruption primitive.
- what would settle it: the size of the fastboot RX buffer (`req->buf`) and
  whether the RX path guarantees `length-1` bytes at most.

**E3 — `do_bootm` hands BL31 a user-chosen buffer address with a fixed 24 MiB
length (suspicious)**
- evidence: `0x37e24cc8 ldr x0,[x19,#8]` / `0x37e24cd4 bl simple_strtoul(…,16)` /
  `0x37e24ce0 mov x1,#0x1080000` (the default when `argc == 0`) /
  `0x37e24ce4 mov x0,#0x40` / `0x37e24ce8 mov x2,#0x1800000` /
  `0x37e24cf0 bl aml_sec_boot_check`. the address is accepted as-is; nothing
  compares it against RAM top, the DTB or the image header.
- reason: the host can reach this with `fastboot boot <addr>` (host-controlled
  string) or `oem bootm <addr>` (≤31 chars). the *type* and *length* are fixed
  (`0x40`, `0x1800000`), so this is not a length confusion; it is an
  unvalidated pointer at the BL33→BL31 boundary, and it also selects the range
  for the following `flush_dcache_range(buf, buf+len)` in the wrapper
  (`0x37e19ee0`). whether BL31 validates it is not observable from BL33 — that
  is a BL31 question, and this is the cleanest example of "the boundary takes an
  argument from the host".
- note: the same pattern exists in the `store`/`imgread` families, but there the
  address comes from the partition table, not from a command line.

**E4 — the secure-storage wrappers have no bounds check, and nothing calls them
(informational)**
- evidence: reference `bl31_storage_write`/`bl31_storage_read` build
  `{namelen, keylen, keyattr}` in the shared input block and `memcpy` the
  caller's name/key without comparing `namelen`/`keylen` to
  `storage_share_block_size`; the image's module is byte-identical (§B.1) and
  the public wrappers have **no callers** (§B.1).
- reason: real missing validation, zero reachability in this build. worth
  remembering only if a later firmware starts calling it.

**E5 — `set_usb_boot` passes an unvalidated 64-bit value to BL31 (informational)**
- evidence: `0x37e60810 ldr x0,[x3,#8]` / `0x37e60814 mov x1,#0` /
  `0x37e60818 mov w2,#0x10` / `0x37e6081c bl simple_strtoul` / `0x37e60838 bl
  0x37e19efc`; the wrapper (`0x37e19efc`) is `mov x1,x0; mov x0,#0x43; movk
  x0,#0x8200,lsl#16; smc #0; ret`.
- reason: the header names `1..4` (`CLEAR`, `FORCE`, `RUN_COMD`, `PANIC_DUMP`)
  but BL33 accepts any value. the accepted set is a BL31 property. no readback
  path exists in BL33, and the value is not stored in the environment, so
  persistence cannot be decided from BL33 — only the write site can be cited.
- the second caller `0x37e76588` sends `1` (`CLEAR_USB_BOOT`) and then re-enters
  the burning mode (`bl 0x37e7b8e4`, `bl 0x37e77210`, tail `b 0x37e78f94`).

**E6 — positive controls that do exist (informational, and worth as much as the
negatives)**
- `cb_download` validates the size (`0 → FAILdata invalid size`,
  `> ddr_size_usable(CONFIG_USB_FASTBOOT_BUF_ADDR) → FAILdata too large`) before
  accepting USB data (`13_fb_backends.txt`).
- `flash`, `erase`, `flashall`, `set_active` and `getvar` do check the lock
  state (E1).
- the 15 `aml_sec_boot_check` call sites use only the declared types
  (`0x10/0x11/0x12/0x20/0x40`) with lengths that match their buffers (`0x500`,
  `0x3fe00`, `0x1800000`), i.e. no length confusion found there.
- `rb`/`rc` handling: the boot path tests the full 64-bit return (`cbz w0`,
  `mov w1,w20`) and aborts the boot with `"aml log : Sig Check %d"` on non-zero
  — an error path that fails *closed*.

## F. Decision

**A) there is an additional BL33 → BL31 interface worth investigating — yes.**
concretely: (1) `oem` → `run_command` (no lock check), (2) the
`update` / v2-burning protocol — the surface that in practice already grants RAM
read/write from the host, (3) `set_usb_boot` → `0x82000043`, (4) the dormant
secure-storage key interface plus the live `SET_STORAGE_INFO`, and (5) the second
SMC family `0xb2000016`. the SMC surface is now fully enumerated; there are no
unknown `smc #0` sites left in the image.

**B) there is a possible validation gap at the BL33 → BL31 boundary — yes, two,
both without proof of impact:** the lock-state asymmetry between `oem` and
`flash`/`erase` (E1), and `do_bootm`'s unchecked load address handed to
`AML_DATA_PROCESS` (E3). neither is a demonstrated failure; E2 is a bounded
parsing defect.

**not C, and not D.** nothing here is "correctly protected" (`oem` proves that),
and the data are sufficient to answer the brief's question.

what is **not** claimed: no bypass of signature verification, no reachable key
material, no arbitrary-write primitive, and no BL31 vulnerability. secure boot is
still imposed in the secure world; this round only moved the *question* from "is
there another interface" to "which of the four, and can any of them change the
state the verifier uses".

## G. what this round does not establish

- whether any of the four interfaces can modify the state the verifier consumes
  (a BL31 property; BL33 only shows the request).
- the exact semantics of `0x82000043`, `0xb2000016`, `0x82000028` behind the SMC.
- the unifykey persistence backend (§D.3).
- whether the `oem`/`update` surface is reachable while the device is *locked*
  in a production unit — this unit is unlocked, so the gate's behaviour was not
  measured.

## H. files

new tools (offline, no device path):

- `tools/bl33_persist.py` — carve an image out of a DRAM band, hash it,
  classify its pages, and dump the page table above it to justify the end bound.
- `tools/bl33_audit.py` — `smc` (opcode-exact census + constant propagation for
  x0..x4 + stub callers), `callers`, `refs` (adrp+add / adrp+ldr / bl),
  `cmds` (`cmd_tbl` → handler), `table` (`{cmd,cb}` dispatch tables), `ptrs`,
  `fstrings`, `strrefs`.

new artifacts (`reports/round14-bl33-persist/`):

| file | content |
|---|---|
| `bl33-37e18000.bin` | the image, sha256 `664fb34a…` (see A.2) |
| `00_persist.txt` | extent, hashes, page map, page-table proof |
| `02_smc.txt` | every `smc #0` with wrapper, x0..x4 sets, stub callers |
| `03_callers.txt`, `07_callers2.txt`, `10_ss_callers.txt`, `11_ss_api_callers.txt` | call graphs of the security-relevant wrappers |
| `04_cmds.txt` | the 80 `cmd_tbl` slots (name → handler) |
| `05_fstrings.txt`, `14_cmd_backends.txt`, `15_usbboot_keyman.txt` | who each function/command is, and what it calls |
| `12_secboot_args.txt` | all 15 `aml_sec_boot_check` call sites with their argument setup |
| `08_fbtab.txt`, `09_fb_table.txt`, `13_fb_backends.txt` | the fastboot dispatch table and each callback's backend |
| `16_burning_refs.txt`, `17_burning_strings.txt` | the v2 burning/optimus host protocol surface |
| `18_key_module.txt`, `19_id_census.txt` | the unifykey module's callees; the full id census (present/absent) |

## I. next steps

1. round 15, first target: **the v2 burning protocol** (`0x37e76aa4`,
   `0x37e77cf8`, buffer `0x37f8a638`) — enumerate its commands and their
   validation. it is the only surface already proven to move data between host
   and BL33 RAM, and it is where the `bootm` literal lives.
2. second: `keyman`/`keyunify` down to the storage call, to answer whether a key
   written from the host lands in efuse (gated by `aml_sec_boot_check`) or in
   eMMC (not gated).
3. only after that, if at all: anything behind `smc #0`. the question there is
   BL31's, and this dump cannot answer it.

do not go below `0x00800000`. do not re-run `set_usb_boot`.
