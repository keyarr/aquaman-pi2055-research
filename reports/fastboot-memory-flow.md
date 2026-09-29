# fastboot-memory-flow — where the payload goes, static + arithmetic

scope: what `fastboot download` / `fastboot boot` actually touch on this
build, with every address labelled PROVEN / DERIVED / HYPOTHESIS.
no command was run on the device for this report.

reference tree: `khadas/u-boot` @ `khadas-vims-nougat` (4c6694f), 2015.01.
this is the closest public tree, NOT the device's U-Boot. the device runs
`2015.01-g7ac5df7677-dirty` and `bootloader.img` is encrypted (entropy 7.9999,
zero strings), so there is no ground truth from the binary. everything from the
tree below is family evidence, and is marked as such.

## 1. the chain, as read from the source

```text
host: fastboot boot <file>
  ↓ USB, host sends "download:<hex>"
drivers/usb/gadget/f_fastboot.c :: cb_download                (:541)
  download_size = simple_strtoul(cmd, NULL, 16)              (:545)
  gate: download_size > ddr_size_usable(BUF) -> "FAILdata too large"  (:556)
  else req->complete = rx_handler_dl_image                    (:558)
  ↓ payload bytes
drivers/usb/gadget/f_fastboot.c :: rx_handler_dl_image       (:490)
  memcpy(CONFIG_USB_FASTBOOT_BUF_ADDR + download_bytes,
         buffer, transfer_size)                               (:504)
  = DIRECT WRITE. no staging buffer, no second copy, no relocation.
  ↓ host sends "boot"
drivers/usb/gadget/f_fastboot.c :: cb_boot                    (:583)
  fastboot_func->in_req->complete = do_bootm_on_complete      (:585)
  fastboot_tx_write_str("OKAY")                               (:586)
  ↓ on next IN token
drivers/usb/gadget/f_fastboot.c :: do_bootm_on_complete       (:569)
  sprintf(boot_addr_start, "0x%lx", load_addr)               (:576)   ← the crux
  do_bootm(NULL, 0, 2, {"bootm", boot_addr_start, NULL})      (:577)
  do_reset(NULL, 0, 0, NULL)                                  (:580)   ← unconditional
  ↓
common/cmd_bootm.c :: do_bootm                                (:96)
  nLoadAddr = GXB_IMG_LOAD_ADDR (0x1080000)                   (:133)
  nLoadAddr = simple_strtoul(argv[0], 16)  → load_addr       (:137)
  aml_sec_boot_check(AML_D_P_IMG_DECRYPT, nLoadAddr,
                     GXB_IMG_SIZE /*24 MiB*/, GXB_IMG_DEC_ALL)      (:142)
    nonzero -> "aml log : Sig Check %d" + return nRet         (:143-147)
  ee_gate_off()                                               (:150)
  do_bootm_states(START|FINDOS|FINDOTHER|LOADOS|PREP|FAKE_GO|GO)  (:151-158)
  ee_gate_on()                                                (:159)
  ↓ on success the ARM64 kernel entry runs and never returns,
    so the do_reset at :580 is only reached when do_bootm FAILS
```

`aml_sec_boot_check` (arch/arm/cpu/armv8/gxl/bl31_apis.c:255-308) is a bare
SMC wrapper: x0=AML_DATA_PROCESS, x1=type, x2=buffer, x3=len, x4=option,
`smc #0`, then `flush_dcache_range` over the whole 24 MiB window. all parsing
and verification lives in BL31/BL32, which is closed.

## 2. addresses

| symbol | value | source | status |
|---|---|---|---|
| `CONFIG_USB_FASTBOOT_BUF_ADDR` | 0x10200000 | include/g_dnl.h:18 | DERIVED (reference tree) |
| `loadaddr` env default | 0x1080000 | board/amlogic/configs/gxl_p241_v1.h:90 | DERIVED (reference tree) |
| `GXB_IMG_LOAD_ADDR` | 0x1080000 | arch/arm/include/asm/arch-gxl/bl31_apis.h:119 | DERIVED (reference tree) |
| `GXB_IMG_SIZE` (SMC window) | 24 MiB | same header :118 | DERIVED (reference tree) |
| `dtb_mem_addr` env | 0x1000000 | gxl_p241_v1.h:101 | DERIVED (reference tree) |
| `CONFIG_SYS_MEM_TOP_HIDE` | 0x08000000 (128 MiB) | gxl_p241_v1.h:469 | DERIVED (reference tree) |
| `CONFIG_SYS_MALLOC_LEN` | 64 MiB | arch/arm/include/asm/arch-gxl/cpu.h:33 | DERIVED (reference tree) |
| `DRAM_UBOOT_RESERVE` | 0x01000000 (16 MiB) | f_fastboot.c:132 | DERIVED (reference tree) |
| BUF on THIS device | unknown | — | NOT PROVEN |
| `loadaddr` on THIS device | unknown | — | NOT PROVEN |

`max-download-size` reported by the device: 0x08000000.

## 3. the arithmetic refutes the historical evidence for X != Y

`ddr_size_usable` (f_fastboot.c:133-142), transcribed exactly:

```c
return (ddr_size - DRAM_UBOOT_RESERVE - addr_start - CONFIG_SYS_MALLOC_LEN - CONFIG_SYS_MEM_TOP_HIDE);
```

and it is used for `max-download-size` (:424) and for the download gate (:556),
both with `addr_start = CONFIG_USB_FASTBOOT_BUF_ADDR`.

plugging aquaman's DRAM (1 GiB, `MemTotal 1004412 kB`):
`usable = 0x40000000 - 0x01000000 - BUF - 0x04000000 - 0x08000000`

| assumed BUF | implied max-download-size |
|---|---|
| 0x10200000 (khadas g_dnl.h) | 0x22E00000 (558 MiB) |
| 0x01080000 (loadaddr) | 0x31F80000 (799 MiB) |
| **device actually reported** | **0x08000000 (128 MiB)** |

neither known address produces the reported number. inverting the formula
gives `BUF = 0x2B000000`, which is neither candidate.

**consequence:** the argument in `reports/fastboot-boot-verdict.md` §root cause
("`max-download-size` is only 128 MB, incompatible with a buffer at 0x1080000,
which would leave ~900 MB free") does not hold. the number is not produced by
the formula that the argument assumes, so it cannot discriminate between
BUF=0x10200000 and BUF=loadaddr. it is not evidence for X != Y.

it is also not evidence for anything else. three explanations fit equally:

1. the device hardcodes `max-download-size` instead of computing it;
2. the device's `CONFIG_SYS_MALLOC_LEN` / `MEM_TOP_HIDE` differ from the
   reference (both are per-board values, and we only have p241's);
3. the device's `DRAM_UBOOT_RESERVE` differs.

note 0x08000000 is suspiciously equal to p241's `CONFIG_SYS_MEM_TOP_HIDE`.
that is a coincidence worth naming, not a conclusion.

reproducible: `python3 tools/fastboot_addr.py`.

## 4. what E5/E6 actually prove (and what they do not)

`reports/buffer-equals-loadaddr-proof.md` runs E5 and E6 and concludes
`BUF == Y == 0x1080000`. the reasoning is sound and it is the strongest
evidence in the repo. restated:

- E5: `fastboot boot boot.img` (stock, 16 MiB download, then boot) → USB dies
  in ~1 s, Android back in ~20 s.
- E6: identical rails, raw `boot` with NO download → FAIL fast, stays in fastboot.
- same `bootm(Y)`, different outcome, the only difference being that a download
  had happened. therefore the download changed the bytes `bootm(Y)` read,
  therefore the download buffer overlaps Y.

what this proves: BUF and Y overlap. what it does NOT prove: the exact value of
BUF, and it does not prove BUF == Y (overlap of one 16 MiB image into a 1 GiB
DRAM is compatible with a range of BUF values, including BUF just below Y).
E6 is consistent with any BUF whose range covers Y.

so the honest statement is: **BUF ∩ Y ≠ ∅ is PROVEN; BUF == Y == 0x1080000 is
still a hypothesis**, resting on the reference tree's `loadaddr=1080000` plus
overlap. that is good enough to act on, and it is the reason the E1-E8
experiments are shaped the way they are, but it is not the same claim.

## 5. is the Sept 2016 "fastboot bug" even live here?

upstream fixed `do_bootm_on_complete` to boot from the download buffer instead
of `load_addr` (Peter Chubb, Sept 2016). the khadas tree here is pre-fix: it
still uses `load_addr` (:576). so the code shape is the unfixed one. that is a
statement about the reference tree, not about `2015.01-g7ac5df7677-dirty`.

the runtime result does not depend on the answer. E5 booted, and E6 (same
`load_addr`, no download) did not. whatever `load_addr` is, it points at the
download buffer. so the bug, if present, is inert on this build. that is a
refutation of the historical root cause, and it is the reason the verdict report
retired it.

## 6. where the flow actually dies

E7 is the decisive one, and it is not about addresses at all:

- E7a: stock-encrypted bytes at Y, then `bootm Y` → passes, Android boots.
- E7b: plaintext bytes at the same Y, same rails → rejected, ~18 s, empty bootreason.
- E7c: INVALID control → same ~16 s, empty bootreason.

`getvar secure:no` describes the flash lock, not the eFuse. the SMC is the
only thing that differs between the two cases, and it is the only thing that
can tell them apart. conclusion: **BL31 is secure-fused and refuses unsigned
payloads**, regardless of which address they sit at.

this is consistent with, and explains, every earlier failure:

| experiment | why it returned to Android without running our bytes |
|---|---|
| M1a / M1b (delay stub) | SMC rejects plaintext before FINDOS; the 15x delay never runs |
| M2 (real 26 MB kernel) | same, plus a stock-encrypted image has a different header layout |
| E1 (FIT + own DTB) | same; a valid DTB does not help, the gate is earlier |
| CTRL (raw, no magic) | SMC reject, not even the format check |

and the ones that DO work, which is what makes the model non-vacuous:

| experiment | why it worked |
|---|---|
| E4 `imgread kernel boot 0x1080000; bootm 0x1080000` | real signed image from eMMC, SMC passes |
| E5 `fastboot boot boot.img` | stock signed image downloaded, SMC passes |
| E8 `booti` / `go` on valid input | absent from this build (see below) |

## 7. bypass surface, checked and empty

`booti` and `go` would skip `do_bootm` and therefore skip the SMC. E8 ran both
against a valid ARM64 Image at Y and got instant FAIL in 0.0 s while the
device stayed in fastboot, versus a real command which takes time and drops the
gadget. `go` cannot fail on valid input; absence is the only explanation.

corroboration: `help <cmd>` is a broken oracle here — `cmd_usage` always
returns 1 (common/command.c:139), so `help` cannot distinguish absent from
present. E8's method (valid input, instant fail) is the sound one.

so the remaining RAM-only surface is:

| path | reaches SMC? | usable |
|---|---|---|
| `fastboot boot` (bootm via load_addr) | yes | no, unsigned rejected |
| `set_active:` sink → `bootm X` | yes | no, same gate (E1/E3) |
| `booti` / `go` | no | command absent in this build (E8) |
| `imgread` | n/a (source, not sink) | reads eMMC only, cannot inject |
| `autoscr` | yes | re-runs the same gated command set |
| `fastboot flash` | n/a | banned, and persistent |

no bypass. the unsigned legs all die at BL31, and the two legs that would not
are not compiled in.

## 8. verdict

- the memory flow is mapped end to end, and it is the same flow for every
  fastboot path on this build. concrete addresses in §2 are reference-tree
  derivations, not device measurements.
- the historical "download != boot source" root cause is **retired**, on
  evidence stronger than the reasoning that originally supported it: E5/E6 show
  the download lands where `bootm` reads. the `max-download-size` argument that
  originally favoured X != Y is arithmetically void (§3).
- what is proven and what is not: BUF ∩ Y ≠ ∅ PROVEN (E5/E6); BUF == Y ==
  0x10800000 HYPOTHESIS; the true BUF value UNKNOWN and not statically
  recoverable, because the device's U-Boot binary is encrypted and the
  `ddr_size_usable` constants are per-board.
- the operative blocker is **not** an address problem. it is the SMC in
  `aml_sec_boot_check`, on a secure-fused BL31, which refuses unsigned images
  before any format check happens. addresses never mattered; that is why every
  timing experiment in the repo came back identical.
- `fastboot boot` on this build: **BLOCKED at BL31 for unsigned payloads.**

## 9. what would actually change the answer, and what would not

would help:

- the unencrypted `u-boot.bin` for this board (would settle BUF and
  `load_addr` definitively — but it does not unblock execution, per §6);
- the `aml-user-key.sig` for aquaman/PI.2055, to sign a repack.

would not help, and are worth naming so nobody spends a session on them:

- finding the right address (already shown irrelevant);
- finding the right image format (E1 tried FIT with its own DTB; the gate is
  before format detection);
- making the payload smaller or bigger (SMC window is 24 MiB, our 26 MB Image
  is already past it — a genuinely separate problem worth remembering for M2,
  but not the reason M1 failed);
- `booti`/`go` (E8: not in the build).
