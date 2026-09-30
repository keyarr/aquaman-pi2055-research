# BL33 round 12: the relocated copy, and the whole boot path

date: 2026-09-29, round 12. one live read, then offline. no write, no `0x05`,
no eMMC, no `setenv`/`saveenv`, no reset, no bootrom, no ghostlock, nothing below
`0x00800000`.

headline: **BL33 is located.** round 11 derived that the executing U-Boot copy
had to sit near the top of usable RAM and that the `0x01000000` copy is a stale
load image. this round read `0x37800000..0x38000000` and found it at
**`0x37e18000`** — the `_start`, the version banner, the full command table, and
the two functions the whole research has been chasing:

```
do_bootm            = 0x37e24c00
aml_sec_boot_check  = 0x37e19ea8
SMC site            = 0x37e19ed8   (x0 = 0x820000ff, AML_DATA_PROCESS)
```

the secure-boot call path is now a concrete, named, disassembled sequence
instead of a line in a reference `.c` file.

## 0. answer block

```text
BL33 link/load base    = 0x01000000
BL33 relocated base    = 0x37e18000          (gd->relocaddr)   HIGH
relocation offset      = 0x36e18000          (gd->reloc_off)   HIGH
image span             = 0x37e18000..~0x37f80000 (~1.4 MiB)
_start                 = 0x37e18000          (b reset + .quad 0x01000000)
do_bootm               = 0x37e24c00          (cmd_tbl bootm.cmd)  HIGH
aml_sec_boot_check     = 0x37e19ea8          (bl31_apis.c wrapper) HIGH
SMC site               = 0x37e19ed8          (x0=0x820000ff)      HIGH
securestorage module   = 0x37e8bba0..0x37e8c160   (13 ids, 4 stubs)
version banner         = 0x37ebdcc0 "U-Boot 2015.01-g7ac5df7677-dirty (Sep 06 2022 - 12:48:55)"
"aml log : Sig Check %d\n"           = 0x37ec00d3
"Wrong Image Format for %s command"  = 0x37ec05b6
cmd_tbl                = 0x37f60fd0 (bootm), + fastboot, imgread, update
confidence             = HIGH for every address above
```

## 1. the read

round 11 derived `gd->relocaddr ~= 0x37d90000..0x37e10000` from the Amlogic
relocation policy (`0x38000000` usable top − `PGTABLE_SIZE` − `mon_len`). the
band read is `0x37800000..0x38000000`, 8 MiB, with margin below the estimate.

| item | value |
|---|---|
| identify | `00 07 00 10`, stage 16 (TPL/BL33 u-boot) |
| address / size | `0x37800000`, `0x00800000` |
| chunks | 128 upload transfers of 64 KiB |
| time / throughput | 0.561 s / 14.26 MiB/s |
| **sha256** | `3d2eca1d7c4030250fef733272878c0ca0f3b798b9ae4ba54a110b7e1012b04e` |
| `0x02` cross-check | MATCH on every ladder step and on the dump head |

entered via `fastboot oem update 5000`, read by the new
`tools/reloc_read.py` (generalized `bl33_read.py`: same one-process ladder,
save-before-anything, `0x02` cross-check). the first 64 bytes at `0x37800000`
were zero; the code starts at `0x37e18000`.

## 2. proving it is the relocated BL33

two independent measurements, in agreement.

**(a) the secure-storage module, byte for byte.** round 10/11 matched
`drivers/securestorage/securestorage.c` at `0x01073ba0` in the load copy. the
same module in the new dump is at `0x37e8bba0`, and the 2 KiB is **identical**,
0 differing bytes:

```
load  0x01073ba0..0x0107439f
reloc 0x37e8bba0..0x37e8c39f
identical: True   diffs: 0
=> reloc_off = 0x37e8bba0 - 0x01073ba0 = 0x36e18000
```

the whole 256 KiB fragment maps the same way: `0x01040000..0x0107ffff` ↔
`0x37e58000..0x37e9ffff`, identical except for **3 bytes** — relocation fixups
(`CONFIG_NEEDS_MANUAL_RELOC` patching absolute pointers), which is what a copied
image should show.

**(b) `_start`.** `tools/bl33_offline.py start` / `bl33_shape.py start` find it
at `0x37e18000`:

```
0x37e18000  b+0x28   quad=0x0000000001000000
            QUAD==CONFIG_SYS_TEXT_BASE (0x01000000)  STRONG
```

`b reset` (+0x28) followed by the raw `.quad CONFIG_SYS_TEXT_BASE`, exactly
`arch/arm/cpu/armv8/start.S:22`. the quad is a literal, so it reads the **link**
address `0x01000000` in both copies, and `_start`'s own address is `0x37e18000`
= `gd->relocaddr`.

so:
```
relocaddr = 0x37e18000        (where it runs)
reloc_off = 0x36e18000        (= relocaddr - CONFIG_SYS_TEXT_BASE)
load base = 0x01000000        (round 11, stale copy)
```

## 3. what the relocated image is

the image occupies `0x37e18000` upward; the non-zero content ends by
`~0x37f80000`, so `~1.4 MiB` — a full U-Boot 2015.01 with fastboot, optimus and
the Amlogic vendor commands, not the 256 KiB fragment:

| range | content |
|---|---|
| `0x37e18000` | `_start`, `reset` |
| `0x37e19d00..0x37e1a200` | `bl31_apis.c` wrappers (§5) |
| `0x37e24c00` | `do_bootm` (§4) |
| `0x37ea0000..0x37ee0000` | `.rodata` — banner, format strings, help text |
| `0x37e8bba0..0x37e8c160` | `securestorage.c` module |
| `0x37ee0000..0x37f50000` | more drivers |
| `0x37f60fd0..` | `.u_boot_list` — `cmd_tbl` |

every brief string is present and readable, after being **absent from all 16 MiB
of the load copy**:

| string | address |
|---|---|
| `U-Boot 2015.01-g7ac5df7677-dirty (Sep 06 2022 - 12:48:55)` | `0x37ebdcc0` |
| `aml log : Sig Check %d\n` | `0x37ec00d3` |
| `Wrong Image Format for %s command` | `0x37ec05b6` |
| `set_usb_boot` | `0x37ed260d` |
| `usb_pcd.c` | `0x37ed8021` |

the banner's build timestamp matches the kernel's (`Sep 06 2022`), i.e. this is
the firmware built with the device's own kernel.

## 4. do_bootm = 0x37e24c00

found two ways, both pointing at the same code.

**(a) the command table.** the relocated `.u_boot_list` is in the dump:

```
&slot 0x37f60fd0
  name    = 0x37ec01fe  'bootm'
  maxargs = 64   repeatable = 1
  cmd     = 0x37e24c00      <-- do_bootm
  usage   = 0x37ec0204  'boot application image from memory'
  help    = 0x37ee4808  '[addr [arg ...]] - boot application image stored in memory ...'
```

the neighbouring slots are `fastboot` (`0x37e3a840`), `imgread` (`0x37e356d0`) and
`update` (**`0x37e78ff8`, "Enter v2 usbburning mode"** — `do_v2_usbtool`).

**(b) the sequence**, and it is the reference source instruction for instruction.
`0x37e24c00` is a real function (`stp x29,x30,[sp,#-0x100]!`), and inside it:

```
0x37e24cd4  bl   #0x37eac21c        ; simple_strtoul(argv[0], &endp, 16)
0x37e24ce0  mov  x1, #0x1080000     ; nLoadAddr = GXB_IMG_LOAD_ADDR (default)
0x37e24ce4  mov  x0, #0x40          ; AML_D_P_IMG_DECRYPT
0x37e24ce8  mov  x2, #0x1800000     ; GXB_IMG_SIZE = 24 << 20
0x37e24cec  mov  x3, #7             ; GXB_IMG_DEC_ALL = KNL|RMD|DTB
0x37e24cf0  bl   #0x37e19ea8        ; aml_sec_boot_check(...)
0x37e24cf4  mov  x20, x0
0x37e24cf8  cbz  w0, #0x37e24d10    ; if (nRet) { ... }
0x37e24cfc  adrp x0, #0x37ec0000
0x37e24d00  mov  w1, w20            ; w1 = nRet
0x37e24d04  add  x0, x0, #0xd3      ; -> 0x37ec00d3 = "\naml log : Sig Check %d\n"
0x37e24d08  bl   #0x37e593c8        ; printf(...)
0x37e24d0c  b    #0x37e24db0        ; return nRet
```

against `common/cmd_bootm.c:133-147`:

```c
unsigned int nLoadAddr = GXB_IMG_LOAD_ADDR; //default load address
if (argc > 0) nLoadAddr = simple_strtoul(argv[0], &endp, 16);
int nRet = aml_sec_boot_check(AML_D_P_IMG_DECRYPT, nLoadAddr, GXB_IMG_SIZE, GXB_IMG_DEC_ALL);
if (nRet) { printf("\naml log : Sig Check %d\n", nRet); return nRet; }
```

`x0=0x40`, `x1=nLoadAddr` (default `0x1080000`), `x2=0x1800000`, `x3=7`, then the
`cbz w0` into the `"aml log : Sig Check %d"` print. **same constants, same
order, same error branch.** this is `do_bootm`.

## 5. aml_sec_boot_check = 0x37e19ea8, SMC at 0x37e19ed8

```
0x37e19ea8  stp  x29,x30,[sp,#-0x20]!
0x37e19eac  mov  x29, sp
0x37e19eb0  str  x19,[sp,#0x10]
0x37e19eb4  mov  x7, x0             ; save type
0x37e19eb8  mov  x6, x1             ; save buf
0x37e19ebc  mov  x5, x2             ; save len
0x37e19ec0  mov  x4, x3             ; option
0x37e19ec4  mov  x0, #0xff
0x37e19ec8  movk x0, #0x8200, lsl #16   ; x0 = 0x820000ff AML_DATA_PROCESS
0x37e19ecc  mov  x1, x7             ; x1 = type
0x37e19ed0  mov  x2, x6             ; x2 = buf
0x37e19ed4  mov  x3, x5             ; x3 = len
0x37e19ed8  smc  #0                  ; <-- the secure-boot SMC
0x37e19edc  mov  x19, x0
0x37e19ee0  add  x1, x6, x5          ; buf + len
0x37e19ee4  mov  x0, x6              ; buf
0x37e19ee8  bl   #0x37e19310        ; flush_dcache_range(buf, buf+len)
0x37e19eec  mov  x0, x19
0x37e19ef0  ldr  x19,[sp,#0x10]
0x37e19ef4  ldp  x29,x30,[sp],#0x20
0x37e19ef8  ret
```

`arch/arm/cpu/armv8/gxl/bl31_apis.c:255-308` is `x0=AML_DATA_PROCESS,
x1=type, x2=buf, x3=len, x4=option, smc #0, then flush_dcache_range(pBuffer,
pBuffer+nLength)`. **the compiled code is the source**, down to the
`movk #0x8200, lsl #16` id and the dcache flush on `buf+len`.

this is the site round 7 predicted from the tree and rounds 8-11 could not find
because the load copy's `bl31_apis.c` was overwritten. it is on the `bootm` path:

```
cmd_tbl 'bootm' -> do_bootm (0x37e24c00) -> bl 0x37e19ea8 -> smc #0 @ 0x37e19ed8
                                            x0 = 0x820000ff
```

`bl31_apis.c`'s SMC census in the image, for context (opcode-exact):

| address | x0 | name (`bl31_apis.h`) |
|---|---|---|
| `0x37e19e88` | `0x82000033` | — |
| `0x37e19e9c` | `0x82000033` | — |
| **`0x37e19ed8`** | **`0x820000ff`** | **`AML_DATA_PROCESS`** |
| `0x37e19f08` | `0x82000043` | `SET_USB_BOOT_FUNC` (the `set_usb_boot` command, `cmd_reboot.c:165`) |
| `0x37e19fac` | `0x82000044` | — |
| `0x37e1a148` | `0x82000018` | — |
| `0x37e1a164` | `0x82000019` | — |
| `0x37e1c7d4` | `0x82000012` | — |

**15 BL callers of `aml_sec_boot_check`** exist in the image
(`0x37e24cf0` is `do_bootm`; the others are the efuse / `imgread` / vendor
commands that share the check).

the secure-storage module is also complete here, all 13 ids present at
`0x37e8bbc0..0x37e8c15c`, `AML_DATA_PROCESS` now **found** where round 11
reported it absent (it lives in `bl31_apis.c`, not `securestorage.c`).

## 6. what this changes, and what it does not

**changes:** the call graph the brief asked for is now complete and measured —
`cmd_tbl bootm -> do_bootm -> aml_sec_boot_check -> smc #0 -> BL31`, every hop at
a known address, every constant matching the reference source. the two functions
that were "not in the dump" for four rounds are located.

**does not change: the secure boot blocker.** BL31/BL32 still does the actual
signature verification behind the SMC, and none of it is reachable from this
dump. `AML_DATA_PROCESS` is the *request*; the key and the policy are in the
closed BL31. `amlsecu-key-path.md` still holds: the plaintext key never appears
in U-Boot. the path is fully mapped and still blocked. this is a map, not a key.

- **no RAM was written, nothing executed, nothing patched.** only
  `fastboot oem update 5000` + reads. `0x05`, `flash`, `erase`, `setenv`,
  `saveenv`, `reset`, burn, bootrom, ghostlock: none invoked.

## 7. the load copy, closing round 11

round 11's base is confirmed: `0x01000000` is the link/load address (the `_start`
quad says so, in both copies), the DTB at `0x01000000` is U-Boot's own
`CONFIG_DTB_MEM_ADDR` staging on top of the dead copy, and the surviving 256 KiB
fragment is at `+0x40000`. the executing copy is `gd->relocaddr = 0x37e18000`.

## 8. next steps

1. the BL33 map is complete for the boot path. anything further on the secure
   check is in **BL31**, not BL33: it is the closed binary behind `smc #0`, and
   there is no BL31 image in RAM to read (BL31 is at a secure address and is not
   in `0x00000000..0x40000000` user DRAM).
2. if BL33 itself is still wanted as an artifact, dump `0x37e18000..0x37f80000`
   (1.4 MiB) and it is a complete, relocate-corrected U-Boot 2015.01-GXL image.
3. `0x01f00000` (round 11 §6) and the unrelated tails remain open; neither is on
   the boot path.

do not go below `0x00800000`. do not re-run `set_usb_boot`.

## 9. files

- `tools/reloc_read.py`, new: read any DRAM band through optimus, read-only.
- `tools/reloc_analyze.py`, new: offline — stub triples, brief strings, BL31 ids,
  `_start`, census, `cmd_tbl`, SMC census for an arbitrary band.
- `reports/round12-reloc/00_session.txt` — the live window.
- `…/01_reloc_analyze.txt` — the analyzer over `0x37800000..0x38000000`.
- `…/02_bootm_hunt.txt` — relocation cross-check, strings, the SMC disassembly.
- `…/03_do_bootm.txt` — callers of the wrappers, the `do_bootm` sequence.
- `…/04_summary.txt` — extent, `cmd_tbl` for the boot commands.
- `…/05_verify.txt` — the mapping cross-check and the decoded `bootm` slot.
- `…/mread_37800000_00800000.bin` — the 8 MiB band, sha256 `3d2eca1d…`.
