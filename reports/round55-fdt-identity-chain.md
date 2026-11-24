# round55 FDT identity chain (offline only, no hardware, 2026-10-02)

Scope: real BL33 `reports/round14-bl33-persist/bl33-37e18000.bin` + stock
`boot.img` header + `artifacts/aquaman.dtb` + `running_config.gz` from round54.
No boot, no WRITE, no `bootm`, no `imgread`.

Single question: does `fdt_chosen()` modify the same FDT that `bootm` delivers to
Linux, and is that FDT the same one pointed to in EL1?

Short answer: the `fdt` of `fdt_chosen` is proven offline to be
`[images+0x100]`, and `x2` at the `eret` is proven offline to be the same
`[images+0x100]`. The structural identity closes. What does not close offline is
the runtime value at three points: `ft_len` at the gate, the return of `fdt_setprop`,
and whether the post-reloc blob is byte-identical to the `0x01000000` dump. Therefore the
round53 divergence remains `UNKNOWN` with the boundary narrowed to one
link, not explained.

## Executive conclusion

Where the chain diverges: at no static point found. Every BL33 writer
of `/chosen/bootargs` uses the env string (`env_get`), no BL33 literal emits
`enforcing` or `normal` for those two fields, the kernel runs
with `CONFIG_CMDLINE=""` (bootloader-only), the target blob has free space, and
the kernel entry is `eret` with `x2=FDT` (no SMC in the handoff).

The static graph says the env string should win. The round53 hardware
says the stock pair won. Since a failure in `fdt_chosen` or the
`ft_len==0` gate hangs the boot (`FDT creation failed! hanging...` /
`FDT and ATAGS support not compiled in - hanging`), and round53 booted
stock Android in ~15 s, the strongest deduction is INFERRED, not PROVEN:
the fixup ran and returned 0, so `fdt_setprop` succeeded on the blob
`[images+0x100]`. If that holds, the divergence is after `fdt_setprop`
(blob swapped afterward) or outside BL33 (init/Linux deriving
`ro.boot.*` from another source), not in a wrong `env_get`.

Defensible statement at the end: we know which FDT `fdt_chosen` modifies
(`[images+0x100]`, post-reloc) and we know which FDT EL1 receives
(`[images+0x100]` via `x2`), and structurally they are the same field;
we do not know the runtime value of `ft_len`, the runtime return of
`fdt_setprop`, nor whether the final blob is byte-identical to the RAM dump.

## Bootm FDT flow

`bootm @ 0x37e24c00` (cmd_tbl idx 6, `OFFLINE_ONLY` re-derived):

```text
bootm @ 0x37e24c00
 -> SMC verify 0x37e24cf0 (aml_sec_boot_check wrapper 0x37e19ea8)   OFFLINE_ONLY
 -> env rebuild "%s %s %s" @ 0x37e24e64 (bootargs + header + verifiedbootstate orange|green) + setenv  PROVEN (strings 0x37ec015c/0x37ec0060/0x37ec0085, disasm 0x37e24dbc..0x37e24e78)
 -> defendkey gate @ 0x37e24e88..0x37e24f54 (recovery/update/factory_reset/upgrade_step==3 only)  OFFLINE_ONLY, not the fastboot path
 -> 0x37e5b2f0 (resolve loadaddr -> images*) + 2nd SMC @ 0x37e24f90  OFFLINE_ONLY
 -> do_bootm_states @ 0x37e255c8 with x5=global 0x37f723e8, w4=0x70f, x3=images stack  OFFLINE_ONLY
    -> inside: bootm_find_os / bootm_load_os / dtb_mem_addr init (default 0x1000000) / decrypt-skip tbz w22,#2 @ 0x37e25d0c  OFFLINE_ONLY
    -> boot_selected_os via OS table 0x37eb5658 -> 0x37e21378 (Linux dispatch)  INFERRED (no `bl`, only via pointer; slot 0x37eb5658 contains 0x37e21378, PROVEN by dump)
 -> 0x37e21378 dispatch by flag:
      0x37e2139c bl 0x37e2122c (fixup gate) + 0x37e213b0 bl 0x37e21284 (entry), or only one of the two  OFFLINE_ONLY
 -> 0x37e2122c gate: env_get("bootargs") @ 0x37e21244 (result discarded) + ldr x0,[x19+0x108]; cbz -> hang; else bl 0x37e5b800  PROVEN disasm
 -> 0x37e5b800 stage: ldr x0,[images+0x108] (ft_len), ldr x1,[images+0x100] (ft_addr), bl 0x37e5bd08 + bl 0x37e5b6cc + bl 0x37e5bda4 (reloc/open_into), then bl 0x37e5c324  PROVEN disasm
 -> 0x37e5c324 (image_setup_libfdt shape): bl fdt_chosen @ 0x37e5c344, then bl arch_fixup_fdt @ 0x37e5c35c (0x37e211f8), bl board setup @ 0x37e5c37c (0x37e29ac8), pack/fixups  PROVEN disasm + error strings
 -> 0x37e21284 (ARM64 entry): ldr x0,[x19+0xe8] (entry), ldr x2,[x19+0x100] (FDT), x1=0xf81, b 0x37e19264  PROVEN disasm
 -> 0x37e19264: x20=x0, x21=x1, x22=x2; x0=0; x1=x21; x2=x22; eret EL2->EL1  PROVEN disasm
```

`[images+0x108]` is not an "FDT field", it is `ft_len` (see Phase 2). The gate at
`0x37e21248` is `if (ft_len==0) hang`, not `if (fdt==0) skip`. A successful
boot implies `ft_len!=0` and `0x37e5b800==0` by hang logic,
but the runtime value of `ft_len` on the `bootm 0x1080000` path is `UNKNOWN`
(no runtime read).

Detail of the two calls to `0x37e255c8` in `bootm`: `0x37e24cc0` with
`w4=0,w6=0` (early, tbz w22,#0/#1 skip env/decrypt) and `0x37e24ff0` with
`w4=0x70f,w6=1` (full). `0x70f` = START+FINDOS+FINDOTHER+LOADOS +
PREP+FAKE_GO+GO per `include/bootm.h` (reference, `INFERRED` for the binary).
The FDT is only touched on the second path via OS dispatch.

## `fdt_chosen`

Entry `0x37e297b8`, `OFFLINE_ONLY` (trace in `fdt_chosen_37e297b8.txt`):

```text
mov x20,x0 (fdt) -> bl fdt_check_header (0x37ea14e0)
 -> tbz w0,#31 fail -> "fdt_chosen: %s"
 -> fdt_find_or_add_subnode(fdt,0,"chosen") (0x37e2956c, "chosen" @ 0x37ec09d1)
 -> env_get("bootargs") @ 0x37e29814 (0x37ebf453)
 -> null -> return 0 (no write, no error)
 -> strlen + fdt_setprop(fdt,node,"bootargs",s,len+1) @ 0x37e29840 (0x37ea28c4)
 -> tbz w0,#31 success -> return 0; fail -> "WARNING: could not set bootargs %s." + return errno
```

Relevant caller for normal boot: `0x37e5c344` inside `0x37e5c324`.
`PROVEN` by `callers(0x37e297b8) = {0x37e5c344, 0x37e293e4}` + shape of
`0x37e5c324` + error strings `ERROR: /chosen node create failed` /
`ERROR: arch-specific fdt fixup failed`. Record: `x0=x1=[images+0x100]`
(mov x0,x1 @ 0x37e5c334; mov x19,x1 @ 0x37e5c340; x1 came from
`ldr x1,[x19+0x100]` at `0x37e5b864`). So the `fdt` is the `ft_addr` field.

Another caller `0x37e293e4` is the handler of the `fdt` command (cmd_tbl idx 49,
func `0x37e2852c`), with `ldr x0,[x21]` (the command's blob) + `bl fdt_chosen`.
It is not on the `bootm` path; it is a mapped capability, not demonstrated. `PROVEN`
that it is not the normal path (disasm shows parsing of the `fdt chosen` subcommand).

Return/branch (`fdt_setprop`):

```text
fdt_setprop == 0 -> w19=0, tbz bit31==0 -> return 0 -> caller 0x37e5c348 tbz bit31==0 -> arch_fixup  PROVEN static
fdt_setprop != 0 (negative, bit31==1) -> WARNING + return errno -> caller prints ERROR /chosen + w20=-1 -> return -1 -> 0x37e5b800 propagates (no overwrite of w0) -> 0x37e21258 !=0 -> printf + hang  INFERRED (propagation proven by disasm, hang proven by strings/calls)
env_get null -> return 0 with no write, no WARNING; caller continues as success  PROVEN
```

There is no static indication of failure on the stock path: error strings exist
but are inaccessible without runtime. A successful boot is INFERRED (not
PROVEN) evidence of `return==0`, because the error path hangs instead of booting
stock.

## Post-fdt_chosen mutations

After `fdt_chosen`, the same pointer `x19` (=`[images+0x100]`) continues in
`0x37e5c324` without a copy:

```text
fdt_chosen (x19) -> arch_fixup_fdt(x19) @ 0x37e5c35c (0x37e211f8: ldr [x18] + bl 0x37e298c0, memory/reservation fixup)  OFFLINE_ONLY
 -> board/system setup(x19) @ 0x37e5c37c (0x37e29ac8: /aliases + ethaddr/ethernet%d, no bootargs)  OFFLINE_ONLY
 -> ldr w2,[x19+4]; rev; bl 0x37ea3c38 + bl 0x37e29c70 (pack/totalsize) + bl 0x37ea3d28 + bl 0x37e295e8 (mem reserve/move) + bl 0x37e5c31c  OFFLINE_ONLY, all in-place in the same blob
```

Broad search for `bootargs`/`reboot_mode`/`androidboot.selinux`/`/chosen`
in the binary: 9/9 round54 consumers confirmed again via
`refs(0x37ebf453)` (6 adrp+add + 2 bl already covered + gate). No other
`fdt_setprop(/chosen,bootargs)` besides `fdt_chosen` and `do_bootvx_fdt`
(`0x37e2646c`, bootvx path, same env content). `rpmb_state` fixup
(`0x37e57b5c`) is dispatch-only with no callers, off the path. `bootm_load_os`
(`0x37e5b880`) and `bootm` do append-only `setenv bootargs`
(header `dtbo_idx/otg/buildvariant` + `verifiedbootstate` orange/green +
`defendkey` recovery-only + bookkeeping `0x%x`), none rewrite
`selinux`/`reboot_mode`. `STATUS: no later routine replacing
/chosen found (OFFLINE_ONLY negative, scope: string+census, not
a global proof)`.

A copy prior to `fdt_chosen` exists: `0x37e5bda4` (reloc/open_into)
updates `[images+0x100]` and `[images+0x108]` (str x19,[x25] / str x21,[x24]
in the tail). So the blob modified by `fdt_chosen` is the post-reloc blob, not
necessarily the raw bytes of `0x01000000`. `INFERRED` that there is reloc;
`UNKNOWN` whether final `x2` is `0x01000000` in-place or a relocated copy (without
a runtime read it is not possible to close byte-equality).

Later `memcpy/memmove/decrypt/uncompress` on the FDT not
found in the Linux path after `0x37e5c324`. The decrypt-skip at
`0x37e25d0c` (tbz w22,#2) is before the FDT fixup in the
`bootm_load_os` flow, not after. `STATUS: UNKNOWN for runtime content,
PROVEN for absence of a second /chosen writer in the static view`.

## Reboot mode provenance

`storeargs = get_rebootmode;setenv bootargs ${initargs} ... androidboot.reboot_mode=${reboot_mode} ...` (`0x37eb6adb`, `PROVEN` by dump).
`get_rebootmode @ 0x37e60478` (cmd_tbl, `PROVEN`): reads `0xc810023c`
bits `[15:12]` + jump table to `setenv reboot_mode <val>` + `run`
related to `storeargs`; fallback reads env `reboot_mode`. Defensive
`reboot_mode` in `bootm @ 0x37e24eb4` (adrp 0x37ec016f) is only read in the
`defendkey` recovery-only gate, not rewritten on the fastboot path. Default
`reboot_mode_android=normal @ 0x37eb6947` (`PROVEN`), but the field that
diverged in round53 was `androidboot.reboot_mode` (from `${reboot_mode}`),
not `reboot_mode_android`.

Search for who forces `normal` in the FDT: zero hits besides defenv and the
`switch_bootmode` script (which sets `reboot_mode_android normal` before
`run storeargs` in several branches, but `switch_bootmode` does not run between
verify and `bootm` in round53, with no reboot). No C literal emits
`reboot_mode=normal` to `/chosen`. `STATUS: BL33 source of
reboot_mode=normal in the FDT not found (OFFLINE_ONLY negative)`.
The `normal` value observed in Android has no BL33 emitter; either it came from
another blob/FDT, or from an init default when the prop is absent/divergent
(`UNKNOWN`, Linux side, see Round53).

`reboot_mode` is useful as a discriminator: since `selinux` and `reboot_mode`
diverged together while everything else stayed the same, it was not "only selinux
treated specially". It was the whole pair, consistent with a lost/replaced FDT
or an entire string swapped, not with a single-field filter.

## Kernel Image

Stock `boot_unpack/kernel` (9.8 MiB) is an encrypted `AMLSECU!` container
(`PROVEN` by header `ver 0x0905 nblk 3`, no `Linux version`, no gzip).
A direct `grep` for `androidboot.selinux`/`reboot_mode=normal`/`bootargs`/
`/chosen` returns 0 hits, but this proves nothing about the real kernel:
the bytes are encrypted. `STATUS: UNKNOWN due to encryption (do not repeat grep as proof)`.

Rebuilt `build-aq/arch/arm64/boot/Image` (27 MiB, McMCCRU approximation, not
stock) has 9 `chosen` / 5 `bootargs` (OF core), 0 `androidboot.selinux`
(expected: `androidboot.*` is parsed by init, not by the kernel). Cited only as
a reference, not as evidence of the stock.

Ground truth that closes it: `/proc/config.gz` of the running kernel (5691
lines, saved in round54): `CONFIG_CMDLINE=""`, without FORCE/EXTEND.
So the kernel uses the bootloader cmdline verbatim. `STATUS: PROVEN
(artifact) for absence of a compiled-in override`. The `CONFIG_CMDLINE` of
`aquaman-config` agrees (approximation). No kernel routine that fabricates
`enforcing`/`normal` was audited here (out of scope for this round;
init not audited).

## DTB provenance

Three distinct blobs, do not treat as equal:

1. `dt.img` (firmware, 59424 B, encrypted, `PROVEN` by absent magic).
2. `artifacts/aquaman.dtb` (RAM `0x01000000`, 58280 B, magic `d00dfeed`,
   totalsize==filelen, `dtc` zero errors in round54, `PROVEN` valid).
   Search: 0 `chosen`, 0 `bootargs`, 0 `selinux`, 0 `reboot_mode`
   (`PROVEN` by count, artifact `dtb_provenance.txt`). Consistent with
   U-Boot creating `/chosen` at `bootm` (fdt_chosen/add_subnode).
3. `boot.img` second (61440 B @ `second_addr 0xf00000`, encrypted, non-FDT,
   `PROVEN` by dump; it is encrypted `dtbo`/second, not the boot FDT).
   `boot.img` header cmdline = `androidboot.dtbo_idx=0 otg_device=1
   buildvariant=user` (explains the kernel extra, `PROVEN`).

`dtb_mem_addr=0x1000000` (htab/arena agree in round54, previous
`HARDWARE_OBSERVED`). Dumped blob has free space (round54: 6404 B tail; here
totalsize==58280, without `/chosen`, space for `bootargs` ~832 B).
`STATUS: lack of space REFUTED`. `STATUS: DTB baked bootargs REFUTED
for the dump (no /chosen)`. `STATUS: second DTB delivered to Linux
UNKNOWN` (the encrypted second is not a readable FDT; if there is a dtbo overlay applied
via `0x37e5bac8`-style or `store dtbo`, it was not traced in this round and
does not touch `/chosen/bootargs` in the static view).

`DTB recovered from RAM != DTB actually passed to Linux` until proven
otherwise if `0x37e5bda4` relocates (INFERRED). Do not assume byte equality.

## EL2 -> EL1

`0x37e21284` ARM64 path (`PROVEN` disasm in `kernel_entry_37e21284.txt`):

```text
ldrb w0,[x19+0xe3]; cmp #2; b.ne fallback blr x21
ldr x0,[x19+0xe8] (entry = [images+0xe8])
ldr x2,[x19+0x100] (FDT = [images+0x100] = ft_addr)
x1 = 0xf81; b 0x37e19264
```

`0x37e19264` (`PROVEN` disasm in `eret_37e19264.txt`):

```text
mov x20,x0; mov x21,x1; mov x22,x2
sctlr_el2 clear; sctlr_el1 set; hcr=0; isb
spsr=0x1d3; elr=x20; x0=0; x1=x21; x2=x22; eret
```

So `x2_EL1 == [images+0x100]` post-fixup, with no SMC in the handoff (`PROVEN`
statically; SMC is only verify-time at `0x37e24cf0/0x37e24f90`). No other
`eret` in the Linux path. `STATUS: x2 == same field modified by
fdt_chosen (structural PROVEN)`. `STATUS: byte equality UNKNOWN`
(depends on runtime reloc + runtime return).

OS table `0x37eb5658 -> 0x37e21378 -> 0x37e2122c -> 0x37e5b800 ->
0x37e5c324 -> fdt_chosen` is the requested textual graph (`PROVEN` edges by
`bl`, `INFERRED` the edge via the OS table pointer for lack of a direct `bl`,
but the slot dump proves the pointer).

## Round53 explanation

Fact: authoritative 832 B htab `df6c9576` (`permissiv`+`fastboot`) delivered to
`imgread success` + `bootm`, stock Android with `enforcing`+`normal`.
Everything else equal + explained extras (`dtbo_idx` header, `verifiedbootstate`
orange bootm-append, `avb_version/vbmeta.*` AVB, `bootreason` plausible BCB/init
without a BL33 string, `fake_battery` origin open).

Vague explanations rejected without a transformation point:

* "Android changed" / "kernel sanitized": no routine located. `REFUTED`
  as a BL33 explanation; `UNKNOWN` as init behavior (not audited).
* "U-Boot ignored it": `REFUTED` statically (fdt_chosen exists, is called on the
  path, all writers use env).
* "bootargs overwritten by another builder": `REFUTED` statically (only
  known small appends; no emitter of `enforcing`/`normal`).

Classification: `UNKNOWN` (boundary narrowed). Main evidence: an independent
double pair diverges together, with no BL33 emitter, with a logical hang if
the fixup failed. Remaining candidates ranked, untested: (a) FDT
swapped/relocated after `fdt_chosen` (`x2 != modified blob`, `UNKNOWN`);
(b) env read in `fdt_chosen` already divergent from the verified one (rebuilder between
verify and fixup, `UNKNOWN` but with no static candidate); (c) init/Linux
deriving `ro.boot.*` without `/chosen/bootargs` verbatim (`UNKNOWN`,
requires a discriminating test, not a new grep).

## Root relevance

Chain in question is only:

```text
BL33 arbitrary write -> input -> effective FDT -> Linux
```

Nothing here advances toward root. `bootargs -> Linux` remains `REFUTED` in
this form (round53) with one `UNKNOWN` link (runtime fixup vs final FDT vs init).
No `uid=0`, no SMC bypass, no init payload audited. Do not
promote anything to `HARDWARE_REPRODUCED` in this round (no hardware).

## Next hardware experiment

Only one, and only if the prediction below is accepted. An FDT identity
test, not a SELinux test (Case B):

Change an inert field that currently agrees (e.g. `androidboot.wificountrycode`
`US`->`ZZ` or `boardid`) via `setenv`+`run storeargs` (never an arena poke),
with `bootargs` verified by fresh-ptr htab + oracle, then the E4 pair
`imgread kernel boot 0x1080000` (check `success` first) + `bootm 0x1080000`,
oracle `getprop ro.boot.wificountrycode` (+ `ro.boot.selinux` as
a control). Prediction: if the inert field also reverts, it is a lost/replaced FDT
(Case B proven, stop testing selinux); if the inert one passes and selinux/reboot_mode do not,
it is a later selective rewrite (Case D/E).
Cost: one RAM-only reboot, no flash/saveenv/update/recovery. Do not run
in this round.

## Artifacts

* `reports/round55-fdt-identity-chain.md` (this one)
* `reports/round55-fdt-identity-chain/`:
  `bootm_37e24c00.txt`, `do_bootm_linux_gate_37e2122c.txt`,
  `kernel_entry_37e21284.txt`, `eret_37e19264.txt`,
  `fixup_stage_37e5b800.txt`, `image_setup_37e5c324.txt`,
  `fdt_chosen_37e297b8.txt`, `bootvx_fdt_37e2646c.txt`,
  `os_dispatch_37e21378.txt`, `xrefs_bootargs.txt`,
  `strings_reboot_mode.txt`, `strings_chosen.txt`,
  `dtb_provenance.txt`, `bootimg_header.txt`,
  `kernel_config_cmdline.txt`
* Reused: `reports/round54-offline-fdt-path/running_config.gz`,
  `artifacts/aquaman.dtb`, `boot.img` header.

## Validation

* `python3 tools/run_tests.py` -> `126 tests, OK` (run before closing).
* `git diff --check` clean.
