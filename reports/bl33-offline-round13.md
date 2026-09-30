# BL33 round 13: the relocated copy re-read on a fresh boot, and it is identical

date: 2026-09-29, round 13. one live read, then offline. no write, no `0x05`,
no eMMC, no `setenv`/`saveenv`, no reset, no bootrom, no ghostlock, nothing below
`0x00800000`. `set_usb_boot` not re-run.

headline: the stick was power-cycled and reconnected, and the band
`0x37800000..0x38000000` was read again. the new 8 MiB dump is **byte-identical**
to round 12, sha256 `3d2eca1d…`: the relocation is **deterministic**. the
relocated BL33 is at the same address (`0x37e18000`), with the same
`do_bootm`, the same `aml_sec_boot_check`, the same boot-path SMC. round 12's
addresses are confirmed across a cold boot, not an artifact of one session.

## 0. answer block

```text
read            = 0x37800000..0x38000000  (8 MiB)
sha256 round13  = 3d2eca1d7c4030250fef733272878c0ca0f3b798b9ae4ba54a110b7e1012b04e
sha256 round12  = 3d2eca1d7c4030250fef733272878c0ca0f3b798b9ae4ba54a110b7e1012b04e
cmp             = IDENTICAL, 0 differing bytes over 8 MiB
BL33 base       = 0x37e18000   (_start, b+0x28 + .quad 0x01000000)   confirmed
do_bootm        = 0x37e24c00   confirmed (same prologue, same sequence)
aml_sec_boot_check = 0x37e19ea8   confirmed
SMC site        = 0x37e19ed8   x0 = 0x820000ff (movz #0xff | movk #0x8200,lsl#16)
boot-path SMC   = unchanged, opcode-exact
confidence      = HIGH, and now also HIGH for reproducibility
```

## 1. the read

the gadget was already on the bus after the user's power-cycle
(`1b8e:c003`, identify `00 07 00 10`, stage 16 TPL/BL33-u-boot), so this was a
plain read with no re-entry.

| item | value |
|---|---|
| address / size | `0x37800000`, `0x00800000` |
| chunks | 128 upload transfers of 64 KiB |
| time / throughput | 0.570 s / 14.04 MiB/s |
| **sha256** | `3d2eca1d7c4030250fef733272878c0ca0f3b798b9ae4ba54a110b7e1012b04e` |
| `0x02` cross-check | MATCH on every ladder step and on the dump head |

`tools/reloc_read.py reports/round13-reloc-verify 0x37800000 0x800000`,
unchanged from round 12. the ladder (`0x200`, `0x1000`, `0x10000`) passed, so the
read is not a one-off success.

## 2. determinism: the two dumps are equal

```
cmp reports/round12-reloc/mread_37800000_00800000.bin \
    reports/round13-reloc-verify/mread_37800000_00800000.bin
  -> IDENTICAL, 0 differing bytes over 8388608
```

two independent boots, two independent reads, one hash. U-Boot's Amlogic
relocation is a fixed computation
(`gd->relocaddr = usable_top − PGTABLE_SIZE − gd->mon_len`) and this proves the
address is stable in practice: `0x37e18000` every time, not "near the top of RAM,
± something".

## 3. re-pinning the boot path on the fresh dump

`tools/reloc_analyze.py` over the new band reproduces round 12's markers:

| marker | round 13 evidence |
|---|---|
| `_start` | `0x37e18000` — `b+0x28`, `.quad 0x01000000` = `CONFIG_SYS_TEXT_BASE` |
| `AML_DATA_PROCESS` `0x820000ff` | `0x37e19ec4..0x37e19ec8` (the `movz`/`movk` pair) |
| `GXB_IMG_LOAD_ADDR` `0x01080000` | 19 sites, first `0x37e24ce0` (inside `do_bootm`) |
| secure-storage module | cluster `0x37e8bba0..0x37e8c144`, 4 stubs |
| `cmd_tbl` | 25 shaped slots, incl. `bootm`, `fastboot`, `imgread`, `update` |
| banner | `U-Boot 2015.01-g7ac5df7677-dirty (Sep 06 2022 - 12:48:55)` |
| `aml log : Sig Check` / `Wrong Image Format` / `set_usb_boot` | present |

the SMC census is opcode-exact and unchanged; the three relevant sites:

```
0x37e19e88  smc #0    movz x0,#0x33 | movk x0,#0x8200,lsl#16
0x37e19ed8  smc #0    movz x0,#0xff | movk x0,#0x8200,lsl#16   <-- AML_DATA_PROCESS
0x37e19f08  smc #0    movz x0,#0x43 | movk x0,#0x8200,lsl#16   <-- SET_USB_BOOT_FUNC
```

### `_start` = 0x37e18000

```
0x37e18000  b    #0x37e18028
            .quad 0x0000000001000000      (CONFIG_SYS_TEXT_BASE)
```

### `do_bootm` = 0x37e24c00

real function, and the secure-boot sequence is instruction-for-instruction the
round-12 result:

```
0x37e24cc8  ldr  x0, [x19, #8]
0x37e24cd0  mov  w2, #0x10
0x37e24cd4  bl   #0x37eac21c        ; simple_strtoul(argv[0], &endp, 16)
0x37e24cd8  mov  w1, w0
0x37e24cdc  b    #0x37e24ce4
0x37e24ce0  mov  x1, #0x1080000     ; nLoadAddr = GXB_IMG_LOAD_ADDR (default)
0x37e24ce4  mov  x0, #0x40          ; AML_D_P_IMG_DECRYPT
0x37e24ce8  mov  x2, #0x1800000     ; GXB_IMG_SIZE
0x37e24cec  mov  x3, #7             ; GXB_IMG_DEC_ALL
0x37e24cf0  bl   #0x37e19ea8        ; aml_sec_boot_check(...)
0x37e24cf8  cbz  w0, #0x37e24d10
0x37e24d04  add  x0, x0, #0xd3      ; "\naml log : Sig Check %d\n"
0x37e24d08  bl   #0x37e593c8        ; printf(...)
```

### `aml_sec_boot_check` = 0x37e19ea8, SMC at 0x37e19ed8

```
0x37e19ea8  stp  x29, x30, [sp, #-0x20]!
...
0x37e19ec4  mov  x0, #0xff
0x37e19ec8  movk x0, #0x8200, lsl #16
0x37e19ecc  mov  x1, x7
0x37e19ed0  mov  x2, x6
0x37e19ed4  mov  x3, x5
0x37e19ed8  smc  #0                  ; <-- the secure-boot SMC
0x37e19edc  mov  x19, x0
0x37e19ee0  add  x1, x6, x5
0x37e19ee4  mov  x0, x6
0x37e19ee8  bl   #0x37e19310        ; flush_dcache_range(buf, buf+len)
0x37e19ef8  ret
```

identical to `arch/arm/cpu/armv8/gxl/bl31_apis.c`. the full path:

```
cmd_tbl 'bootm' -> do_bootm (0x37e24c00) -> bl 0x37e19ea8 -> smc #0 @0x37e19ed8
                                                             x0 = 0x820000ff
```

## 4. what this changes, and what it does not

**changes:** the round-12 map is now reproducible rather than a single-session
observation. same base, same functions, same SMC, on a different boot. the
relocation address can be treated as a fixed constant of this firmware.

**does not change: the secure boot blocker.** this is still a map, not a key.
BL31/BL32 does the signature verification behind `smc #0`; nothing in this dump
is BL31. `AML_DATA_PROCESS` is the request, the key and policy are in the closed
BL31, and `amlsecu-key-path.md` still holds — the plaintext key never appears in
U-Boot.

- **no RAM was written, nothing executed, nothing patched.** reads only, via the
  vendor `0x02` / `upload mem` path. `0x05`, `flash`, `erase`, `setenv`,
  `saveenv`, `reset`, burn, bootrom, ghostlock: none invoked.

## 5. files

- `tools/reloc_dis.py`, new: offline capstone viewer for named addresses in a
  band, plus a `--vs` byte-diff against another dump. no USB.
- `reports/round13-reloc-verify/00_session.txt` — the live window and the `cmp`.
- `…/01_reloc_analyze.txt` — the shape analyzer over the fresh band.
- `…/02_bootpath_dis.txt` — `--vs` byte-diff plus `_start`, `do_bootm`,
  `aml_sec_boot_check` disassembly.
- `…/mread_37800000_00800000.bin` — the 8 MiB band, sha256 `3d2eca1d…`
  (byte-identical to `reports/round12-reloc/mread_37800000_00800000.bin`).

do not go below `0x00800000`. do not re-run `set_usb_boot`.
