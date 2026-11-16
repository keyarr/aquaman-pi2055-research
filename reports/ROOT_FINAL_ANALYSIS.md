# Root Final Analysis

Date: 2026-10-02. Scope: repository state at `main` after the cleanup, plus the
uncommitted rounds 48 to 58 that the cleanup pass had not yet folded in. No
device was touched in this round. Every hardware statement cites an existing
artifact; the new code-level statements were re-derived offline from
`reports/round14-bl33-persist/bl33-37e18000.bin`,
`reports/round46-same-cycle/cmdtbl_37f60eb0.bin`,
`reports/round54-offline-fdt-path/running_config.gz` and `.src/linux-amlogic`.

Verdicts defer to `reports/CURRENT_STATE.md`. Nothing here supersedes it: the
`INCONCLUSIVE` rows stay `INCONCLUSIVE`. What this report adds is the root
boundary as it stands *after* rounds 48 to 58, three new offline results, and
the smallest experiment that discriminates the remaining fork.

Status vocabulary:

```text
PROVEN              logic/offline arithmetic, no hardware needed
HARDWARE_REPRODUCED executed on device, artifact in repo
HARDWARE_OBSERVED   read/measured on device, no mutation experiment
OFFLINE_ONLY        derived from a binary or a source tree, never executed
INFERRED            chain assembled from proven legs, chain itself never run
EXTERNAL            standard platform behaviour, no artifact in this repo
INCONCLUSIVE        missing or ambiguous evidence
REFUTED             evidence contradicts it
```

## Executive conclusion

```text
highest control demonstrated
    arbitrary RAM write with host-chosen address and bytes inside BL33's own
    RAM image (WRITE 0x01, FILL 0x03) plus a 64-bit function-pointer dispatch
    hijack (ldr x4,[x19,#0x10] ; blr x4) redirected to an existing legitimate
    handler, same-cycle oracle, verified restore, RAM-only, non-persistent.
    HARDWARE_REPRODUCED.

complete chain to root
    NO. Nothing in this repository shows an attacker-supplied byte executing at
    EL1, and nothing shows uid=0, euid=0, a root process, a capability change
    or a credential modification. `commit_creds` and `prepare_kernel_cred` do
    not appear in any report except as a plan.

the previous candidate is now closed
    the bootloader env -> kernel cmdline route was the shortest chain on the
    board. It has been executed four times and REFUTED every time: arena direct
    poke (round48), arena template leg (round49), authoritative htab
    (round53), and two inert-field controls (rounds 56 and 58). Three
    different inert same-length `androidboot.*` fields, each reverting
    whole-string. This is no longer "untested", it is a reproduced negative.

biggest technical gap
    one gap, on the bootloader side: the bytes of /chosen/bootargs between the
    moment `env_get("bootargs")` is called inside `fdt_chosen` and the moment
    they are read out of the running system. Everything on both sides of that
    gap is now closed:

      - the env side is proven. rounds 51 and 52 show `setenv` and a WRITE to
        the htab data pointer both land in the authoritative store and are
        read back by the parser.
      - the kernel side is now closed too, which it was not. The running
        kernel's own /proc/config.gz has CONFIG_CMDLINE="" and no
        CONFIG_CMDLINE_EXTEND / CONFIG_CMDLINE_FORCE, so on arm64
        /proc/cmdline is byte-for-byte the DT /chosen/bootargs string. There is
        no second cmdline source to lose the marker in.
      - the defenv re-import explanation is now closed for the tested path.
        bootm's direct-call closure is 236 functions and contains none of
        set_default_env, do_env_import, env_import or env_relocate.
        imgread's closure is 28 functions and touches no env function at all.

    so the loss is inside BL33's own runtime window, on a path nobody has
    observed executing. The one function that decides it, `fdt_chosen`
    (0x37e297b8), has never been watched with our env value in place. It has
    exactly two callers and one of them is a command we can type.

second gap, independent and larger
    on the kernel side: zero kernel-VA bytes disclosed on the audited surface,
    then no verified reclaim, then no write primitive, in that order. This one
    is not a gap that a single experiment closes.
```

Shortest evidence-based path from the demonstrated state to Linux-visible
attacker-controlled input, with each arrow's real status:

```text
WRITE 0x01 into the authoritative htab bootargs value          HARDWARE_REPRODUCED
  -> env_get("bootargs") inside fdt_chosen reads our bytes     INFERRED (code is
                                                                    in the device
                                                                    image, never run)
  -> fdt_setprop(/chosen, bootargs)                            INFERRED (same)
  -> boot_command_line == the DT property                      PROVEN (running
                                                                    config + arm64
                                                                    plumbing)
  -> /chosen/bootargs reaches EL1 with our bytes               INFERRED, and three
                                                                    hardware runs
                                                                    say the opposite
  -> init turns androidboot.X into ro.boot.X                   EXTERNAL (AOSP
                                                                    property_init,
                                                                    not in this repo)
  -> uid=0                                                      NEVER RUN
```

The third arrow down is the contradiction the current state sits on, and it is
the reason this report does not offer a "chain to root" narrative.

## Privilege boundary

| Stage | Primitive | Evidence | Privilege | Root relevance | Status |
|---|---|---|---|---|---|
| BootROM / BL1 | none | `adb reboot update` stayed in recovery (`custom-kernel-execution.md` §4); no eMMC-failure USB edge in BL2 (`round47-bl2-pre-bl33-fallback.md` §4) | above BL33 | none | INCONCLUSIVE, no path found |
| BL2 | FIP load + verify, BL2-USB mailbox | family `.src/u-boot-khadas/fip/gxl/bl2.bin` static map; device BL2 is ciphertext (`round28-fip/01-bootloader-layout.md`) | EL2, pre-BL33 | none reachable | OFFLINE_ONLY, family proxy |
| BL31 | `aml_sec_boot_check` wrapper `0x37e19ea8` = `mov x0,#0x820000ff` + `smc #0`; 15 `smc #0` sites, 22 ids | `tools/bl33_audit.py smc`; refusal measured by E7/M1a/M1b/E1/CTRL | EL3, secure-fused | the gate that kills every unsigned RAM-only boot | wrapper OFFLINE_ONLY, refusal HARDWARE_REPRODUCED |
| BL33 dispatch | WRITE 0x01 (8/16/64 B), FILL 0x03 scattered, 116-entry cmd_tbl, live == offline, consumer `ldr x4,[x19,#0x10]` + `blr x4` | `optimus-write-mem-round39.md`, `bl33-campaign-round43.md`, `bl33-same-cycle-round46.md`, `reports/round46-same-cycle/cmdtbl_37f60eb0.bin` | EL1/EL2 inside the bootloader | arbitrary RAM write plus control-flow hijack to existing code | HARDWARE_REPRODUCED |
| BL33 redirect | `false->true`, `test->true`, `env print->true` cross-table, oracle `failed:`->`success`, double restore, no reboot | `bl33-cmd-redirect-round42.md`, `bl33-campaign-round43.md` §3, round46 Exp1 | same | proves the dispatch edge is real | HARDWARE_REPRODUCED |
| BL33 env | live htab located, writable 1:1 with readback and intact neighbour; `setenv` and WRITE both reach `test ${VAR}` | `round51-env-htab-oracle.md`, `round52-write-htab-template.md` | same | the input side of the shortest chain | HARDWARE_REPRODUCED |
| BL33 env consumption by a script | `setenv`/WRITE -> htab -> `storeargs` -> htab `bootargs`, 832 B, single-field diffs both directions, pointer moves per rebuild | `round52-write-htab-template.md` A/B | same | parser consumption proven | HARDWARE_REPRODUCED |
| BL33 `bootm` internals | bootm runs 12 Hush command lines itself: `get_avb_mode;`, `setenv bootargs ${bootargs} defendkey=%x,%x,`, `store dtb decrypt ${dtb_mem_addr}`, `get_valid_slot;`, `store size`, `store read`, `setenv dtbo_mem_addr`, `dtbo_start`, `fdt apply`, `rsvmem check`. No `preboot`, no `storeargs`, no `bootcmd` | `reports/root-final-analysis/01-bootm-env-closure.txt`, new this report | same | the untested window is inside bootm, and it is now enumerated | OFFLINE_ONLY |
| BL33 FDT hand-off | `fdt_chosen` 0x37e297b8, two callers only: `0x37e293e4` (the `fdt chosen` subcommand) and `0x37e5c344` (image_setup_libfdt) | `reports/root-final-analysis/03-fdt-chosen-path.txt`, `bl33_audit.py callers` | same | the function that decides the delivered cmdline | OFFLINE_ONLY |
| BL33 -> Linux cmdline | three inert fields, byte-verified htab values, `imgread` success + `bootm`, stock Android returns with all three reverted | `round53-htab-transport.md`, `round56-inert-transport.md`, `round58-boardid-transport.md` | same | THE broken transition | REFUTED for every form tried |
| BL33 .text | page-table descriptors compatible with RWX for idx0/1 (`AP=EL1-RW`, `XN=0`); `dcache` idx 11 and `icache` idx 60 exist | `bl33-campaign-round43.md` §1/§7, `bl33-control-primitive-round38.md` §4 | same | would give arbitrary BL33 code execution | descriptor-compatible only, write to .text never tested |
| Linux kernel | GhostLock trigger + `FUTEX_LOCK_PI` consumer + `f_target`/`f_alt` fidelity | `ghostlock-consumer-futex-lock-pi-2026-10-01.md`, `out/logs/ghostlock_consumer_boot3ec336a5.log` | attacker uid 2000 shell, Enforcing | stale object inferred, zero controlled bytes | HARDWARE_REPRODUCED for trigger/consumer/fidelity |
| init / userspace | shell `uid=2000` `u:r:shell:s0`, SELinux Enforcing, no `su`, no root daemon; `/proc/cmdline` and `/proc/device-tree/chosen/bootargs` both Permission denied for shell | `dev-read-surface-census-2026-10-01.md` §1, `reports/round58-boardid-transport/proc_cmdline.txt` | unprivileged | the starting point, and the reason the in-kernel oracle does not exist | HARDWARE_OBSERVED |
| fastboot | download buffer overlap / bootm load region overlap | E5 vs E6, `fastboot-memory-flow.md` §4 | host to RAM | places host bytes where bootm reads | HARDWARE_REPRODUCED |
| vendor modules | 28 `.ko` in the OTA; presence only | `out/vendor/modules`, `vendor-modules.md` | none, files on disk | no primitive proven; `mali.ko` stateful audit negative | PROVEN presence / INCONCLUSIVE as a bug |
| boot / recovery / update | every load-and-run path passes `aml_sec_boot_check`; `booti`/`go` absent (E8, single method); `set_active:` sink real but calls the same `bootm` | `fastboot-memory-flow.md` §6-§7, `set-active-sink.md` | BL33 | no boot deviation demonstrated | HARDWARE_REPRODUCED for the gate |
| privileged execution | none. `RUN_IN_ADDR 0x05` wedges USB even for a no-op with KEEP_POWER; `MODIFY 0x04` kills the session with no readback | `bl33-campaign-round43.md` §§6-8 | — | L4 not reached | INCONCLUSIVE |

## Proven primitives

Only entries with an artifact. For each: what it allows, and what would be
needed to turn it into root.

1. **Arbitrary RAM write, host-chosen address and bytes, in-session.**
   `WRITE_MEM 0x01` (`ctrl OUT 0x01, wValue=addr>>16, wIndex=addr&0xffff`,
   payload at least 64 B per transfer) and `FILL_MEM 0x03` (8 B `(addr,val)`
   pairs). Addresses written on device include `0x37800000`, `0x37f616d0`
   (cmd_tbl), `0x37ee71c8` (sub-table), and htab data pointers read fresh each
   boot. All with readback and restore.
   *Allows:* change any 32-bit-addressable RAM word in the running bootloader.
   *Next step for root:* make a changed word reach Linux. Status
   HARDWARE_REPRODUCED. Artifacts: `optimus-write-mem-round39.md` §§1-2,
   `bl33-campaign-round43.md` §§2-3, `bl33-same-cycle-round46.md`,
   `round52-write-htab-template.md`.

2. **64-bit function-pointer dispatch hijack, same cycle, reversible.**
   `ldr x4,[x19,#0x10]` + `blr x4`, no transform in between, `x19` = the
   matched cmd_tbl entry. Redirected `false`->`true`, `test`->`true`, and the
   `env print` sub-table slot ->`true`, each with an oracle and a verified
   restore, no reboot.
   *Allows:* choose which existing BL33 handler a command dispatches to.
   *Next step for root:* point a slot at bytes the host controls. That needs
   host bytes in a fetchable region plus cache coherency, and neither is
   demonstrated. Status HARDWARE_REPRODUCED for redirect-to-existing,
   INCONCLUSIVE for arbitrary code execution.

3. **`cmd_tbl` fully mapped, live == offline.** 116 entries, stride `0x30`, base
   `0x37f60eb0`, layout `+0x00` name, `+0x08` maxargs/repeatable, `+0x10`
   handler. Re-verified this round from the live dump:
   `reports/root-final-analysis/04-cmdtbl-slots.txt`.

   ```text
   idx   6  bootm      0x37e24c00     idx  60  icache     0x37e27b18
   idx  11  dcache     0x37e27ba4     idx  62  imgread    0x37e356d0
   idx  38  env        0x37e57d6c     idx  65  keyman     0x37e74290
   idx  43  false      0x37e36764     idx  70  mmc        0x37e2ca3c
   idx  49  fdt        0x37e2852c     idx  84  run        0x37e5ea04
   idx  85  saveenv    0x37e57d3c     idx  91  setenv     0x37e58470
   idx  96  store      0x37e33900     idx 100  test       0x37e36774
   idx 101  true       0x37e3676c     idx 104  update     0x37e78ff8
   idx 108  usbboot    0x37e371f0     idx 110  version    0x37e26688
   ```

   No `booti`, no `go`, no `autoscr`. *Allows:* know exactly what any redirect
   hits and which commands are callable from the burning session. Status
   HARDWARE_OBSERVED.

4. **The authoritative environment store is a hash table, and the host can
   write the values the parser reads.** Object `0x37ee7278`, bucket array
   `0x33e2d650`, `env_get` 0x37e58920 and `setenv` sharing it. `setenv` flips a
   `test ${EnableSelinux}` oracle; a WRITE to the `0x33e18000` arena does not,
   which demoted the arena to a stale shadow copy. A WRITE to the htab *data*
   pointer does flip it. `storeargs` rebuilds the 832-byte `bootargs` from
   `initargs` plus template variables, reproducibly in both directions.
   *Allows:* rewrite any byte of the kernel command line U-Boot will build.
   *Next step for root:* prove those bytes reach the kernel. Status
   HARDWARE_REPRODUCED for the env side. Artifacts:
   `round51-env-htab-oracle.md`, `round52-write-htab-template.md`,
   `round50-env-authoritative-source.md`.

5. **The `storeargs` template, verbatim.** New this round, from the compiled-in
   default env at `0x37eb65a0` (len `0x1785`, 58 entries):

   ```text
   storeargs=get_rebootmode;setenv bootargs ${initargs} ${fs_type}
     reboot_mode_android=${reboot_mode_android} androidboot.selinux=${EnableSelinux}
     logo=${display_layer},loaded,${fb_addr},${outputmode} maxcpus=${maxcpus}
     vout=${outputmode},enable hdmimode=${hdmimode} ... jtag=${jtag};
     setenv bootargs ${bootargs} androidboot.veritymode=enforcing
     androidboot.hardware=amlogic androidboot.btmacaddr=${btmac}
     androidboot.wifimac=${wifimac} androidboot.wificountrycode=${wifi_ccode}
     androidboot.bootloader=${bootloader} androidboot.serialno=${serialno}
     androidboot.boardid=${boardid} androidboot.product=aquaman
     androidboot.region=${region} androidboot.reboot_mode=${reboot_mode}
     androidboot.ffu_status=${ffu_status};
     setenv bootargs ${bootargs} page_trace=${page_trace};
     setenv bootargs ${bootargs} androidboot.rpmb_state=${rpmb_state};
   ```

   Three of the four fields that revert in rounds 53/56/58 are template
   variables with independent htab entries: `${EnableSelinux}`,
   `${wifi_ccode}`, `${boardid}`. That is why round58's control matters, and it
   is why the revert cannot be a single-field filter. Note also
   `androidboot.reboot_mode=${reboot_mode}`, and that `get_rebootmode` re-derives
   `reboot_mode` from hardware register `0xc810023c[15:12]`, so that one field is
   expected to be re-derived during boot regardless. Status OFFLINE_ONLY.
   Artifact: `reports/root-final-analysis/02-defenv-scripts.txt`.

6. **The boot path that passes the SMC.** E4:
   `imgread kernel boot 0x1080000 ; bootm 0x1080000` -> USB drops, Android
   boots. `storeboot` in the default env is exactly that pair, wrapped in
   `if imgread ...; then bootm ...; fi; run update;` so `run update` is only
   reached when `imgread` fails. Sending the two commands separately and
   checking the `imgread` reply first is what makes the E4 shape safe.
   *Allows:* boot the stock signed kernel from RAM, in-session, nothing flashed,
   nothing saved. Status HARDWARE_REPRODUCED. Artifact:
   `buffer-equals-loadaddr-proof.md` E4, `reports/root-final-analysis/02-defenv-scripts.txt`.

7. **GhostLock trigger + consumer + fidelity.** FWRQ/FCRQ trio -> EDEADLK 5/5;
   `FUTEX_LOCK_PI(f_chain)` differential (occupied+stale = EDEADLK, else
   TIMEOUT); `alt_tgt` EDEADLK vs `alt_only` TIMEOUT.
   *Allows:* distinguishing walk state, errno 35 vs 110, 0 ms vs 3000 ms.
   *Next step:* put controlled bytes under the walk. Status HARDWARE_REPRODUCED
   for the trigger and the signal, INCONCLUSIVE for anything beyond.

8. **DTB blob recovered and valid.** 58280 B at `0x01000000`, magic `d00dfeed`,
   `dtc` round-trip zero errors, 376 nodes / 1798 props, `gxl_aquaman_1g`, no
   `/chosen` and no `bootargs` in the recovered copy. Status
   HARDWARE_REPRODUCED for the blob, PROVEN for its validity, INCONCLUSIVE for
   Linux receipt.

9. **Unsigned payloads are refused before format detection.** E7a signed passes,
   E7b plaintext at the same address refused, E7c INVALID refused with the same
   timing, and a structurally valid Magisk image with a byte-identical kernel
   and a real ramdisk refused because `DEC_ALL` covers the whole 24 MiB window.
   Status HARDWARE_REPRODUCED.

### New offline results in this round

None of these existed in any report before. All are OFFLINE_ONLY, scoped as
stated, reproducible with the commands given.

**N1. `bootm` runs twelve Hush command lines, and none of them rebuilds the
environment.** Transitive `bl` closure of `0x37e24c00`: 236 functions, 16
indirect `blr` sites. `parse_stream` (`0x37e5e968`) is called from `bootm`
itself twelve times, and the resolved literals are:

```text
0x37e24d34  get_avb_mode;                                 (only if `avb2` is unset)
0x37e24f10  setenv bootargs ${bootargs} defendkey=%x,%x, (appends, keeps ours)
0x37e25110  store dtb decrypt ${dtb_mem_addr}             (decrypts the board DTB)
0x37e2515c  get_valid_slot;
0x37e251c4  store size %s 0x%p
0x37e2533c  store read %s 0x%p 0 0x%llx
0x37e2537c  setenv dtbo_mem_addr 0x%p
0x37e25528  dtbo_start
0x37e25560  fdt apply 0x%llx
0x37e256b4  get_avb_mode;                                 (only if `avb2` is unset)
0x37e26014  rsvmem check
0x37e63be0  get_valid_slot;                               (second state machine)
```

`preboot`, `storeargs` and `bootcmd` are **not** in that list, so the most
tempting explanation for the revert, bootm quietly re-running `storeargs`, is
REFUTED for the direct-call graph. `get_avb_mode`, `get_valid_slot` and
`get_rebootmode` are cmd_tbl commands with C handlers, which is why
`parse_stream("get_valid_slot;")` resolves. Reproduce with
`python3 tools/bootm_env_closure.py reports/round14-bl33-persist/bl33-37e18000.bin 0x37e18000`.

**N2. No env rebuild site is reachable from the tested boot path.**
`himport_r` (`0x37eaa264`) has exactly three callers in the whole image:
`0x37e581a0` (inside the `env_relocate` region), `0x37e58b9c` inside
`set_default_env` (`0x37e58b24`, imports the compiled-in defenv `0x37eb65a0`
len `0x1785`), and `0x37e58c9c` inside `do_env_import` (`0x37e58c10`). The
`env_relocate` itself is `0x37e58d94`, proven by its `!bad CRC` string, its
`env_get("silent")`/`strcmp("on")` tail and its `gd->flags |= 4`. Its only
caller is `0x37e24ad8`, inside a small late-init function with zero direct
callers, i.e. reached from the init function-pointer table, which runs long
before `main_loop` and long before the burning session attaches.

Of those three, none is in bootm's 236-function closure, and none is in
`imgread`'s 28-function closure, which contains no env function at all. So
"the environment was silently re-imported from the default env between our
verified read and `fdt_chosen`" is REFUTED for the direct-call graph of the
tested path. Scope limit: `blr` is counted but not followed, and the OS
dispatch into the FDT fixup stage is an indirect table edge, so this is a
scoped negative, not a global proof.

**N3. The kernel-side command line source is closed on this build.** The
running kernel's own `/proc/config.gz` (5691 lines, device artifact) has
`CONFIG_CMDLINE=""` and contains no `CONFIG_CMDLINE_EXTEND` and no
`CONFIG_CMDLINE_FORCE` at all. In the ancestral arm64 tree,
`boot_command_line` is a buffer (`init/main.c:124`) filled by
`early_init_dt_scan_chosen()` (`drivers/of/fdt.c:1089`), which does
`strlcpy(cmdline, config_cmdline, ...)` only when forcing, and otherwise
`strlcpy(cmdline, p, min(l, COMMAND_LINE_SIZE))` with `p` read straight out of
the DT `/chosen/bootargs` property. With both switches off, `/proc/cmdline` is
the DT property, byte for byte. Consequence, and it cuts against the
comfortable reading: if `ro.boot.selinux` reads `enforcing`, then `/chosen/bootargs`
held `androidboot.selinux=enforcing`. The marker was lost at or below the
hand-off, not re-derived by Linux. The last hop, init mapping
`androidboot.X` to `ro.boot.X`, is AOSP `property_init()` behaviour and is not
in this repository, so it is EXTERNAL; the inference above rests on it.
Artifact: `reports/root-final-analysis/05-kernel-cmdline-source.txt`.

**N4. `fdt_chosen` is reachable from a command, in-session.** `fdt_chosen`
`0x37e297b8` has exactly two callers in the image: `0x37e5c344`
(`image_setup_libfdt`, the bootm path) and `0x37e293e4`, inside the `fdt`
command handler `0x37e2852c`, reached when `memcmp(argv[0], "cho", 3) == 0`,
i.e. the `chosen` subcommand. The handler reads its blob from the global
`0x37f72a90`, which is the same slot `boot_relocate_fdt` publishes to, and
`fdt addr` with an argument stores argv[1] into it via `simple_strtoul`.
Artifact: `reports/root-final-analysis/03-fdt-chosen-path.txt`.

Also worth recording because it corrects a stale row: **`bootm` runs
`store dtb decrypt ${dtb_mem_addr}`**, with `dtb_mem_addr=0x1000000` in the
default env. The board DTB is therefore decrypted into RAM *during* bootm, from
`dt.img`, and that is the blob the fixup stage and `fdt_chosen` operate on.
Round57's FDT-A row, "from image at `0x1080000` header parse", is wrong for the
DTB leg. This also explains why the recovered RAM copy at `0x01000000` has no
`/chosen`: it is the pre-fixup blob.

### Memory and MMU, four levels kept separate

| Level | Finding | Status |
|---|---|---|
| Descriptor compatible with RWX | yes for idx0/1: `AP=EL1-RW`, `XN=0`, `AttrIdx=4` Normal-WB, 512 MiB blocks in the `0x37ff0000` dump, 8192 descriptors | PROBABLE, descriptor level only |
| RWX effectively active at the execution point | not demonstrated. `SCTLR_EL1 = 0x300004516` (M=0 A=1 C=1 I=0) is a dump, not a live read; D-cache on, I-cache off at dump time | INCONCLUSIVE, and REFUTED as an automatic conclusion (`INVALIDATED_HYPOTHESES.md` #17) |
| Memory actually reachable by the primitives | any 32-bit address via WRITE 0x01 / FILL 0x03, demonstrated from `0x33e1xxxx` to `0x37800000` | HARDWARE_REPRODUCED |
| Code actually executed from attacker-written memory | never. No `.text` write was attempted. `RUN_IN_ADDR 0x05` wedges USB even for a no-op with KEEP_POWER; `MODIFY 0x04` kills the session with no readback | INCONCLUSIVE |

### Fastboot

With the consolidated terminology, and nothing older reused:

```text
fastboot input
  -> write to memory        memcpy straight into the download buffer, no staging
                             (reference tree) + download buffer overlap /
                             bootm load region overlap (HARDWARE_REPRODUCED, E5/E6)
  -> flow change            bootm reads the region the download changed
                             (HARDWARE_REPRODUCED, E5/E6)
  -> image / kernel / DTB   none. Every unsigned payload refused at
                             aml_sec_boot_check before format detection
                             (HARDWARE_REPRODUCED, E7a/b/c + the Magisk test)
  -> privileged execution   REFUTED for unsigned on every RAM-only path tested
```

`BUF == Y` as exact equality stays INCONCLUSIVE. `max-download-size
0x08000000` is not evidence of any address (`tools/fastboot_addr.py` inverts it
to `BUF = 0x2B000000`, which is neither candidate). `booti` / `go` absent by
E8's single method, scoped, not global.

### Environment and Hush, five levels kept separate

1. env bytes modifiable: **yes**, and on the authoritative object, not the
   arena. HARDWARE_REPRODUCED.
2. env parser reading the modified bytes: **yes**, proven twice and in both
   directions, with `test ${VAR}` as an htab-reading oracle. HARDWARE_REPRODUCED
   (round51 `setenv`, round52 WRITE to the htab data pointer).
3. a script consuming the modified value: **yes**, `run storeargs` rebuilds the
   832-byte `bootargs` from it, single-field diffs, pointer moves each rebuild,
   restore also proven. HARDWARE_REPRODUCED (round52 A/B). This level was
   INCONCLUSIVE until round52 and is no longer the gap.
4. the privileged flow altered: **mechanism only**. The `test`->`true` redirect
   flips `if test` branches, but `storeboot` and friends were never executed as
   a whole and their tails end in `bootm`, `update`, `recovery_from_flash` or
   `fastboot`.
5. boot or recovery deviated: **refuted for every form tried**. Four runs, four
   different mutation routes, all reverting whole-string.

So the gap is no longer levels 2 and 3. It is between level 3 and level 5, and
N2 plus N3 put that window inside `bootm`, past the htab, before or at
`fdt_chosen`.

## Candidate root chains

Format: `input -> primitive -> transition -> kernel -> userspace root`.

### Chain 1, env value to kernel command line, the shortest, now broken

```text
host bytes over Optimus bulk control
  -> WRITE 0x01 into the authoritative htab bootargs value
                                                      HARDWARE_REPRODUCED
  -> run storeargs rebuilds it from the template      HARDWARE_REPRODUCED
  -> bootm reads it: env_get("bootargs") at 0x37e29814 (fdt_chosen)
                                                      OFFLINE_ONLY
  -> fdt_setprop(/chosen, bootargs) at 0x37e29840    OFFLINE_ONLY
  -> x2 at the EL1 eret is the same field             PROVEN structurally
                                                      (round55/round57)
  -> /proc/cmdline == that DT property                PROVEN (N3)
  -> init maps androidboot.X to ro.boot.X            EXTERNAL
  -> marker visible in the running system             REFUTED, 3 hardware runs
  -> uid=0                                            NEVER RUN
```

Three inert fields were used as the marker: `androidboot.selinux`
`enforcing`->`permissiv`, `androidboot.wificountrycode` `US`->`ZZ`,
`androidboot.boardid` `3`->`7`. Each was verified byte-exact in a freshly
located htab entry immediately before `bootm`, each was handed to `bootm` after
`imgread` returned `success`, each came back stock. The revert is
whole-string, not field-selective, which rules out a filter and points at object
identity or a re-derivation inside BL33.

### Chain 2, env branch to which image gets loaded

```text
WRITE 0x01 into env
  -> test->true redirect flips every `if test`     HARDWARE_REPRODUCED (redirect)
  -> storeboot picks a different partition or slot INCONCLUSIVE (script never run;
     get_valid_slot and get_avb_mode re-derive active_slot and avb2 first)
  -> bootm -> aml_sec_boot_check                   HARDWARE_REPRODUCED refusal
```

Cannot reach an unsigned kernel: every branch still ends in `bootm` and the
SMC.

### Chain 3, write to .text to arbitrary BL33 code to patch the SMC check

```text
WRITE 0x01 into BL33's own code                    INFERRED, never attempted
  -> dcache (idx 11) / icache (idx 60) flush       commands exist, never run
  -> redirect a cmd_tbl slot at the injected bytes  mechanism proven for existing
                                                    code only
  -> patch the two aml_sec_boot_check call sites    OFFLINE_ONLY
  -> bootm accepts a plaintext image               INCONCLUSIVE, untested
  -> custom kernel at EL1 -> root                  needs DTB staging via
                                                    `store dtb decrypt`, a
                                                    plaintext container that
                                                    still passes BL33's
                                                    validators, and a kernel
                                                    without vendor modules
```

Strictly heavier than chain 1: multi-megabyte RAM staging plus an I/D-cache
story plus container reverse engineering.

### Chain 4, GhostLock

```text
user-controlled futex trio                           HARDWARE_REPRODUCED
  -> FUTEX_LOCK_PI consumer, differential walk       HARDWARE_REPRODUCED
  -> stale rt_mutex_waiter on the victim's stack     INFERRED, source-derived
  -> post-free reuse plus disclosure                 INCONCLUSIVE: zero
                                                     kernel-VA bytes, reclaim FAIL
  -> pointer corruption                              INCONCLUSIVE, never attempted
  -> kernel object / fops / cred / page table       INCONCLUSIVE
  -> kernel code execution -> root                   INCONCLUSIVE
```

### Chain 5, fastboot unsigned

```text
download -> overlap -> bootm(Y) -> aml_sec_boot_check -> REFUTED for unsigned
```

## GhostLock assessment

Assessed only as a possible route across the privilege boundary.

* **Disclosure.** `NO_DISCLOSURE_FOUND` on the audited surface, scoped, not
  global. Audited: `/proc` (`stack` masked by `%pK`, `wchan` "0", `syscall` user
  regs only, `stat` fields 29/30 = `0 0`), `/sys/kernel/slab` attrs 0400,
  `kallsyms` / `kmsg` / `dmesg` / `debugfs` / `tracing` denied, `/proc/slabinfo`
  absent (`SLABINFO=n`), `/proc/buddyinfo` errno 13, net unix/tcp/diag, futex PI
  path with zero `copy_to_user` in `.src/linux-amlogic/kernel/futex.c` and
  `kernel/locking/rtmutex.c`, binder, ashmem, ion, and a full `/dev` census (499
  paths probed, 18 shell-openable, `POINTER_BYTES_FOUND 0`, 18 tests). The
  conclusion the surface supports is "no kernel-VA byte found here", not "no
  disclosure exists". Still INCONCLUSIVE and explicitly unaudited: mali stateful
  ioctls without source, `f_op` walks beyond BFS depth 3, `/dev` nodes without
  auditable source. `CONFIG_RANDOMIZE_BASE=y` with `CONFIG_ARM64_VA_BITS=39` in
  the running config is why a fixed offset is not a substitute for a leak.
  Artifacts: `dev-read-surface-census-2026-10-01.md`,
  `ghostlock-stock-disclosure-2026-10-01.md`,
  `ghostlock-next-bottleneck-2026-10-01.md`.
* **Reclaim.** INCONCLUSIVE with a measured FAIL: `mm_reclaim_probe` modes A, B
  and control all `reclaim_hits=0` while plumbing passes 512/512. `MSG_PEEK` is
  REFUTED as proof of reclaim. Slab and buddy diagnostics are blocked for shell,
  so the per-attempt order-2 capture rate is unobservable unprivileged.
  Artifact: `mm-reclaim-probe-2026-10-01.md`.
* **H16 live retarget.** Secondary, and not demonstrated.
  `NO_EXACT_WRITER_FOUND` over the audited window: 411 8-byte stores, 33 exact,
  0 producers of the target value; the PI `+0x10` is a register-only `LEA` with
  zero spills; zero precedent in the five external ports. Do not resurrect it
  for elegance.
* **Post-free reuse plus disclosure.** The principal architectural candidate,
  PROBABLE by comparison, explicitly **not** demonstrated on Aquaman. Every
  external port replaces the whole object after the waiter returns and leaks an
  anchor first; none leaks `waiter->lock` directly. On Aquaman the carriers
  exist in source (`pselect` fd_set copy, `setsockopt` MCAST) but the overlap
  against the 0x50-byte waiter frame is unmeasured, `pselect` has an adverse
  history, and `PR_SET_MM_MAP` is unavailable (`CHECKPOINT_RESTORE=n`).
* **Impact on kernel or root.** None today. `commit_creds`,
  `prepare_kernel_cred`, `uid=0`, `euid`, `cred` and capability appear in this
  repository only as plan or as a port comparison, never as a hardware result.
  The one ceiling expectation cited anywhere is another device's `uid 0` inside
  `u:r:shell:s0` with Enforcing intact, which is an analogy and not a claim
  about this one. Artifacts: `ghostlock-aquaman-plan.md`,
  `ghostlock-port-comparison.md`, `hazel-mm-struct-aquaman.md`.

## Alternative chains

Included only where the current evidence supports the leg.

| candidate | evidence | verdict |
|---|---|---|
| U-Boot -> kernel modification | every unsigned image refused, including Magisk with a byte-identical kernel | no evidence |
| U-Boot -> DTB modification | the DTB in RAM is real and `fdt` can write to it in-session (N4). But `fdt_chosen` overwrites `/chosen/bootargs` from `env_get` at bootm time, so poking the property is the wrong lever, and no `fdt` subcommand has been run | mapped capability, not demonstrated |
| U-Boot -> initramfs modification | refused with the kernel byte-identical, `DEC_ALL` covers the 24 MiB window | REFUTED as tried |
| AVB bypass | `fastboot flashing unlock` fails with `missing partition name`; `oem unlock` is a false positive; `oem setenv lock 10100000` + `oem saveenv` gives orange/unlocked and does not touch the eFuse; the `avb2` env byte is writable but `get_avb_mode` re-derives it, and `get_avb_mode` is what bootm calls | no evidence |
| bootargs control or cmdline injection | the mechanism is mapped on the device binary, the authoritative store is writable, the parser consumption is proven. Delivery is REFUTED in every form tried | the open link, and it is the broken one |
| recovery path, update, slot manipulation | `preboot`, `storeboot`, `upgrade_check`, `switch_bootmode`, `recovery_from_flash`, `update` all read offline; `upgrade_step` byte writable but `run update` never triggered. Every one of those tails ends in `bootm` and the SMC | no evidence |
| privileged ioctl or vendor driver bug | `mali.ko` 34 stateful handlers all BOUNDED_COPY plus VALIDATED or SCALAR/NO_EMIT, open/close and get/put balanced; other Amlogic KOs return errno 13 for shell; blind ioctls prohibited and never run | OFFLINE_ONLY negative, not a proof of absence |
| vendor module ABI or runtime surface | presence only; `modules.dep` is metadata, `srcversion` on 2 modules, `/proc/modules` and init logs never collected | REFUTED as usage proof |
| userspace -> kernel outside GhostLock | no other UAF or corruption mapped anywhere in the repository | no evidence |
| BootROM USB burning | BL2 has no eMMC-failure USB edge; `set_usb_boot 2` selects a decision in BL2 and loses eMMC init, it does not reach the BootROM | OFFLINE_ONLY, no path found |
| `bcb uboot-command` | visible in the live `preboot` text: it executes a command string read from eMMC. Writing it needs a persistent storage write | out of scope by rule, no evidence |

KernelSU and APatch (`kernelsu-next.md`, `apatch.md`) need a modified kernel
actually running. Recovering the DTB removed the DTB problem, not the execution
problem.

## Root boundary

```text
BL33 arbitrary RAM write                                         HARDWARE_REPRODUCED
  -> authoritative env store mutated and read by the parser     HARDWARE_REPRODUCED
  -> storeargs rebuilds bootargs from the template              HARDWARE_REPRODUCED
  -> bootm consumes it, 12 Hush command lines, no defenv re-import
                                                                 OFFLINE_ONLY
  -> fdt_chosen writes /chosen/bootargs from env_get            OFFLINE_ONLY, never run
  -> x2 at the EL1 eret is the same field                       PROVEN structurally
  -> /proc/cmdline is that property                              PROVEN
  -> the bytes the kernel received                              REFUTED, 3 hardware runs
                                                                   ^ the chain breaks here
  -> cmdline effect observed in the running system              NEVER RUN
  -> privileged code execution                                  INCONCLUSIVE
  -> root                                                       INCONCLUSIVE
```

1. **Highest proven control.** Arbitrary RAM write inside the running
   bootloader, plus control-flow hijack of its command dispatch redirected to
   an existing handler, with a same-cycle oracle, verified restore, no reboot
   and no persistence. Everything above that, arbitrary BL33 code execution,
   anything outside BL33, and anything in userspace, is unproven.
2. **First required operation.** Observe what `fdt_chosen` actually writes when
   the htab holds a marker. Not "prove the marker reaches Linux", which three
   runs say it does not, but "find where in bootm's window it is lost". The
   cheapest instance is to run `fdt_chosen` on a RAM blob inside the burning
   session and read the blob back.
3. **Evidence that would prove it.** One session log with a `WRITE 0x01` marker
   into a fresh htab `bootargs`, `run storeargs` with the `test ${VAR}` oracle
   confirming, `fdt addr <scratch>`, `fdt chosen`, then an `mread` of the
   scratch blob showing either the marker or the stock string under
   `/chosen/bootargs`. No boot, no kernel, no `imgread`, no `bootm`, no
   persistence.
4. **Primitive that could do it.** WRITE 0x01 and FILL 0x03 for the blob, the
   `setenv` command (idx 91) for the marker, and the `fdt` command (idx 49) for
   the call. All three are already characterised.
5. **Not yet demonstrated.** Every arrow above the break. No kernel byte has
   been shown to change because of a host write. No `uid=0`, no `euid=0`, no
   root process, no capability change, no credential modification, anywhere in
   this repository, on any boot.

### A / B / C / D kept separate

**A. Privileged control inside BL33.** L0 read-only (`0x02` `mread`,
116-command map) HARDWARE_REPRODUCED. L1 write (WRITE 0x01, FILL 0x03)
HARDWARE_REPRODUCED. L2 control data HARDWARE_REPRODUCED. L3 control flow to
existing code HARDWARE_REPRODUCED. L4 arbitrary BL33 execution NOT
demonstrated. L5 crossing into secure world NOT, the SMC is intact. L6 and L7,
root and persistence, NOT: every write in every session was restored or wiped
by reboot.

**B. Modification of the image Linux will execute.** Kernel modification: no.
DTB modification: no, and `/chosen/bootargs` would be overwritten from `env_get`
anyway. Initramfs modification: no, and refused even with an unchanged kernel.
Bootargs or cmdline injection: mechanism mapped, value bytes writable in the
authoritative store, parser consumption proven, delivery REFUTED. Signature
bypass: none, BL31 internals closed.

**C. Execution of researcher-controlled bytes at EL1.** None. No artifact shows
a byte the researcher supplied running at EL1 or above. The closest is the
function-pointer redirect, whose target is always a pre-existing handler, and
the `fdt chosen` capability, which runs existing BL33 code on a RAM blob and
has never been executed.

**D. Escalation to root in userspace.** None. No `uid=0`, no `euid=0`, no root
shell, no root process, no capability escalation, no credential modification.
The Magisk test is the explicit negative: byte-identical kernel, valid ramdisk,
and the boot still fell back to stock Android with no `/sbin/su` and no
`init.svc.magiskd`.

## Minimal next experiments

Three, ranked by discriminating power per unit of risk. Nothing persistent
survives any of them; a power cycle restores stock behaviour. None was executed
in this round. Deliberately excluded: flash, erase, `saveenv`, factory reset,
`fastboot flash`, `run update`, `recovery_from_flash`, `usb_burning`, BootROM
USB burning, blind ioctls, `fake object`, credential overwrite.

### E1, run `fdt_chosen` inside the burning session and read the blob back

* **Objective.** Find out whether `fdt_chosen` consumes our env value at all,
  with the kernel, `imgread` and `bootm` all out of the picture.
* **Hypothesis.** `fdt_chosen` `0x37e297b8` is reached from the `fdt chosen`
  subcommand at `0x37e293e4` on the blob in the global `0x37f72a90`, which
  `fdt addr <address>` sets. It does `fdt_check_header`, adds `/chosen`,
  `env_get("bootargs")`, `fdt_setprop`. Therefore an inert marker in the htab
  `bootargs` must appear verbatim as the `/chosen/bootargs` property of that
  blob, and `mread` will show it.
* **Input.** One burning session (`adb reboot fastboot`, `fastboot oem update
  5000`, `1b8e:c003`, identify stage 16). Re-hunt the htab, addresses are
  per-boot. Then:
  1. `setenv EnableSelinux permissiv`, confirm with `test ${EnableSelinux} =
     permissiv` -> success and `= enforcing` -> `failed:`;
  2. `run storeargs`, then re-locate the `bootargs` entry and read 832 B, assert
     `androidboot.selinux=permissiv`;
  3. build a minimal valid FDT with slack at a scratch address with WRITE 0x01.
     Do not reuse the board DTB at `0x01000000`: it is 58280 B with
     `totalsize == filelen`, so `fdt_find_or_add_subnode` plus an 833-byte
     property would return `-FDT_ERR_NOSPACE` and teach nothing;
  4. `bulkcmd "fdt addr <scratch>"`, check the reply is not a usage error. If it
     is, try `fdt <scratch> chosen`, which is the other accepted spelling;
  5. `bulkcmd "fdt chosen"`. Read the reply: `fdt_setprop(): %s` or
     `/chosen node create failed` means the write was refused, and the oracle
     must move to a blob with more room, not to a boot;
  6. `mread <scratch> <len>` and search the dump for `permissiv` and for
     `/chosen`.
* **Expected result if the hypothesis holds.** The dump contains
  `/chosen/bootargs` with `androidboot.selinux=permissiv`. That isolates the
  break to `bootm`'s window between the htab read and the FDT fixup, and it makes
  the remaining work a bisect inside one session with `mread` as the oracle,
  instead of one boot per hypothesis.
* **Refuting result.** The dump contains `/chosen/bootargs` with the stock
  string. Then `fdt_chosen` on this build does not see the htab value we
  verified, which contradicts rounds 51 and 52 and would mean the htab we read
  is not the one `env_get` returns, despite sharing `env_get`. Either way it is
  a hard result obtained without booting.
* **Risk.** Low. RAM-only, no boot, no `imgread`, no `bootm`, no flash, no
  `saveenv`. `fdt` is a plain RAM command and never reaches `aml_sec_boot_check`.
  The only cost if the blob write goes wrong is that the session ends and a
  power cycle restores stock. This is the experiment round46 declined for
  "do not touch the DTB before mapping which `fdt` subcommands BL31 covers";
  the mapping now exists (N4) and the target is a scratch buffer, not the DTB
  in flash.

### E2, one boot with the one oracle that actually distinguishes

* **Objective.** Separate "BL33 delivered stock" from "Linux re-derived", which
  is the last untested pair in the transport, and which rounds 53/56/58 could
  not do because `/proc/cmdline` and `/proc/device-tree/chosen/bootargs` are
  both denied for `u:r:shell:s0`.
* **Hypothesis.** N3 says `/proc/cmdline` is the DT property verbatim, and the
  stock `ro.boot.*` values therefore imply BL33 delivered stock. The one
  reading that would contradict N3 is a `/proc/cmdline` that differs from
  `ro.boot.*`. Getting that reading needs either a readable path or a marker
  the kernel itself echoes, and the cheapest is a cmdline parameter the kernel
  prints and that does not go through init: `loglevel=8` would only change
  verbosity, while `panic=1` is destructive. `init=/nonexistent` is not inert.
  So this experiment is only worth running if E1 has already shown what the
  bootloader hands over.
* **Input.** Offline first: audit whether any `/proc` or `/sys` node on this
  build exposes the command line or the DT `/chosen` to shell without a new
  privilege, and whether `init`'s own handling of `/proc/cmdline` can be read
  from the OTA `system.new.dat.br` dump that is already in this repository
  without unpacking 647 MB. Deliverable: either a concrete readable oracle or a
  documented statement that none exists.
* **Expected result.** A readable node, which turns E2 into one cheap boot with
  a direct `cat` instead of an indirect `getprop`.
* **Refuting result.** No readable node. Then the "BL33 delivered versus Linux
  re-derived" pair is permanently unobservable from an unprivileged shell on
  this build, and the honest statement becomes that the transport question can
  only be settled from inside BL33, which is exactly what E1 does.
* **Risk.** The offline pass is zero risk. No boot is proposed here; if one is
  proposed later it is the E4 shape, RAM-only, marker dies with `bootm`.

### E3, host bytes executing inside BL33, which gates chain 3

* **Objective.** Decide whether the write primitive plus a cache flush produces
  execution of host-supplied instructions in the bootloader, the leg that would
  make patching `aml_sec_boot_check` reachable.
* **Hypothesis.** `dcache` (idx 11) and `icache` (idx 60) flush; the region is
  descriptor-compatible with EL1 execute (`XN=0`, idx0/1). So a write to an
  unused aligned word inside BL33's RAM image followed by a flush should show
  up as a behaviour change at the next execution of that word. E1 already
  produces a scratch buffer, and `fdt chosen` gives a way to point existing code
  at it, so the same session can host this test.
* **Input.** One session. Read-only first: pick a word on a path with a
  `bulkcmd`-visible effect, the cmd_tbl slots already qualify and have been used
  safely. Then the same word as an instruction-alignment target, then `dcache
  flush` and `icache flush`, then trigger. `0x04` and `0x05` stay excluded:
  each costs a power cycle and neither is needed.
* **Expected result.** A predicted, reversible behaviour change consistent with
  the bytes written, proving write then flush then fetch.
* **Refuting result.** No change after flush, which closes chain 3 for this
  build without ever touching the SMC path.
* **Risk.** Low to medium. All writes inside BL33's RAM image, restored or wiped
  by reboot. If a `.text` write wedges the session the cost is one power cycle,
  the same cost rounds 43 and 45 already accepted.

Note what E1 and E3 together buy: E1 tells us which side of `fdt_chosen` the
marker dies on, and E3 tells us whether we can stop caring about `bootm` and
patch the verifier instead. Chain 3 is the only remaining route that does not
require the cmdline to work at all.

## Evidence matrix

| Claim | Artifact | Hardware | Offline | Status |
|---|---|---|---|---|
| WRITE 0x01 / FILL 0x03 arbitrary RAM write, host address and bytes | `optimus-write-mem-round39.md`, `bl33-campaign-round43.md`, `bl33-same-cycle-round46.md`, `reports/round46-same-cycle/session_run.py` | yes | map | HARDWARE_REPRODUCED |
| BL33 consumes written bytes (upload memcpy, reply `.rodata`) | `optimus-write-consumption-round40.md` | yes | — | HARDWARE_REPRODUCED |
| 64-bit dispatch `ldr x4,[x19,#0x10]` + `blr x4` | `bl33-control-primitive-round38.md` §1, `bl33-cmd-redirect-round42.md` | yes | disasm | HARDWARE_REPRODUCED |
| Redirect to an existing handler, same cycle, restorable | `bl33-cmd-redirect-round42.md`, `bl33-campaign-round43.md` §3, round46 Exp1 | yes | — | HARDWARE_REPRODUCED |
| 116 cmd_tbl entries, live == offline, bootm 6 / imgread 62 / fdt 49 / run 84 / store 96 / dcache 11 / icache 60 | `reports/root-final-analysis/04-cmdtbl-slots.txt`, `bl33-map-round41.md` | read | disasm | HARDWARE_OBSERVED |
| Authoritative env is the htab; the `0x33e18000` arena is a stale shadow copy | `round51-env-htab-oracle.md`, `round50-env-authoritative-source.md` | yes, oracle run, restored | disasm + census | HARDWARE_OBSERVED (oracle), OFFLINE_ONLY (code) |
| WRITE to htab data and `setenv` both reach the parser | `round52-write-htab-template.md` phase A | yes | — | HARDWARE_REPRODUCED |
| `storeargs` rebuilds htab `bootargs` from the template, both directions | `round52-write-htab-template.md` A/B | yes, fresh-pointer reads | defenv | HARDWARE_REPRODUCED |
| `bootm` runs 12 Hush command lines, none of them `preboot`/`storeargs`/`bootcmd` | `reports/root-final-analysis/01-bootm-env-closure.txt`, `tools/bootm_env_closure.py` | — | disasm | OFFLINE_ONLY, new |
| No `set_default_env` / `do_env_import` / `env_import` / `env_relocate` in bootm's or imgread's `bl` closure | same | — | call graph | OFFLINE_ONLY scoped negative, new |
| `store dtb decrypt ${dtb_mem_addr}` runs inside bootm, so the delivered FDT comes from `dt.img` | same, plus `reports/root-final-analysis/02-defenv-scripts.txt` | — | disasm | OFFLINE_ONLY, new; corrects round57 FDT-A |
| `fdt_chosen` has exactly two callers, one of them the `fdt chosen` command | `reports/root-final-analysis/03-fdt-chosen-path.txt` | — | disasm | OFFLINE_ONLY, new |
| `/proc/cmdline` on this build is the DT `/chosen/bootargs` verbatim | `reports/root-final-analysis/05-kernel-cmdline-source.txt`, `reports/round54-offline-fdt-path/running_config.gz` | config read on device | source | PROVEN for the config, OFFLINE_ONLY for the ancestral source |
| FDT pointer identity `fdt_chosen` arg vs `x2` | `round55-fdt-identity-chain.md`, `round57-fdt-final-identity.md` | — | disasm | OFFLINE_ONLY structural, `SAME_OBJECT_UNKNOWN_BYTES` |
| Env bytes handed to `bootm` reappear in the running system | `round53-htab-transport.md`, `round56-inert-transport.md`, `round58-boardid-transport.md` | yes, 3 runs | 832 B verified handoff | REFUTED for every form tried |
| Kernel cmdline reflects a host-written arena byte | `round48-bootargs-selinux.md`, `round49-bootargs-template-selinux.md` | yes, 2 runs | — | REFUTED (stale arena form) |
| `imgread kernel boot 0x1080000 ; bootm 0x1080000` boots Android | `buffer-equals-loadaddr-proof.md` E4 | yes | — | HARDWARE_REPRODUCED |
| `uid=0` / root shell / capability / credential change | no artifact, anywhere | — | — | INCONCLUSIVE, non-existent |
| download buffer overlap / bootm load region overlap | `fastboot-memory-flow.md` §4, E5/E6 | yes | — | HARDWARE_REPRODUCED |
| `BUF == Y` as equality | same base | overlap only | reference tree | INCONCLUSIVE |
| `max-download-size` discriminates address | `tools/fastboot_addr.py` | — | arithmetic | REFUTED |
| Unsigned refused at `aml_sec_boot_check` | `fastboot-memory-flow.md` §6, E7a/b/c | yes | wrapper disasm | HARDWARE_REPRODUCED |
| Magisk, kernel byte-identical, refused | `magisk-boot-test-2026-10-01.md`, `out/logs/magisk_boot_test.log` | yes | image layout | HARDWARE_REPRODUCED |
| `booti` / `go` absent | E8 | yes, one method | — | PROBABLE, scoped |
| Page-table descriptors compatible with RWX | dump `0x37ff0000`, round43 §1, round38 §4 | dump | decode | PROBABLE, descriptor level; active state INCONCLUSIVE |
| Host bytes executed from BL33 RAM | none; `RUN 0x05` wedges, `MODIFY 0x04` kills the session | attempted, no proof | — | INCONCLUSIVE |
| DTB blob valid at `0x01000000` | `artifacts/aquaman.dtb`, `aquaman-dtb-extraction.md` | read | `dtc` | HARDWARE_REPRODUCED + PROVEN |
| DTB received by Linux | `/proc/device-tree` denied for shell | denied | — | INCONCLUSIVE |
| 28 vendor `.ko`, presence only, CRC gate real | `out/vendor/modules`, `vendor-modules.md`, `tools/ko_versions.py` | — | extract + CRC | PROVEN presence and gate |
| `mali.ko` yields no primitive | `root-path-reclaim-consumer-mali.md` §3 | open/poll/read only | 34-handler census | OFFLINE_ONLY negative, INCONCLUSIVE as a hardware claim |
| GhostLock trigger / consumer / fidelity | `ghostlock-consumer-futex-lock-pi-2026-10-01.md`, `out/logs/ghostlock_consumer_boot3ec336a5.log` | yes, BOOT_ID `3ec336a5` | birth/readers static | HARDWARE_REPRODUCED |
| H16 live retarget | census 411/33/0, `ghostlock-h16-durable-write-2026-10-01.md` | fidelity matrix | disasm BFS<=3 | INCONCLUSIVE, audited not demonstrated |
| Disclosure of a kernel VA as bytes | 22 tests + `/dev` census 499/18/0 | audited surface | PI zero-copy | PROBABLE absence on that surface, INCONCLUSIVE globally |
| Order-2 reclaim | `mm-reclaim-probe-2026-10-01.md`, `out/logs/mm_reclaim_*_boot3ec336a5.log` | yes, FAIL `hits=0` | mechanism static | INCONCLUSIVE, measured FAIL |
| Post-free reuse on Aquaman | no controlled byte ever landed | — | 5-port comparison | PROBABLE as direction, not demonstrated |

## Invalidated claims

Not usable as proof of root. Items 1 to 25 have their evidence in
`reports/INVALIDATED_HYPOTHESES.md`, scopes in `reports/CURRENT_STATE.md` and
`reports/EVIDENCE_MATRIX.md`. Items 26 and 27 were only ever claims of the
previous revision of this file, so they are recorded here and nowhere else.

1. test payload executed via `fastboot boot` - REFUTED (M1a and E7 timing).
2. `download != boot source` - REFUTED (E5/E6 prove overlap).
3. download buffer is `0x10200000` as a device fact - REFUTED, reference tree
   only, the device U-Boot is encrypted.
4. `max-download-size` proves buffer position - REFUTED, inverts to
   `BUF = 0x2B000000`, neither candidate.
5. `X = 0x10200000` as a device fact in the gate analyses - REFUTED, same as 3.
6. vermagic `4.9.y` proves module origin - REFUTED, `Makefile:1221` flattens it.
7. modules need device root to extract - REFUTED, they are in the OTA dumps here.
8. baseline compiles with `CONFIG_AMLOGIC_DVB=y` - REFUTED at HEAD,
   `3d4ab79e` breaks the UAPI, parent `17cef223` untried.
9. Aquaman DTB inaccessible - SUPERSEDED, the blob was recovered from DRAM; the
   vendor `.dts` source is still missing.
10. `0x01040000..0x01080000` contains no U-Boot - REFUTED, matches
    `.src/u-boot-khadas/drivers/securestorage/securestorage.c` plus 13 materialised BL31 ids.
11. old SMC count of 11 - REFUTED, 15 sites, 22 ids.
12. the scheduler path is the required consumer - REFUTED, the `FUTEX_LOCK_PI`
    differential works.
13. freeing `f_chain` before the consumer preserves `pi_blocked_on` - REFUTED,
    the frame must stay alive, `fwrq_alive=1`.
14. H16 live retarget as the principal mechanism - SUPERSEDED, secondary; the
    principal is post-free reuse plus disclosure, itself undemonstrated here.
15. `MSG_PEEK` plumbing proves reclaim - REFUTED, plumbing only.
16. `dist=0` proves the absolute waiter offset - REFUTED, page and SP-base reuse
    only.
17. a reconstructed page table proves the active MMU state - SUPERSEDED,
    descriptor-compatible only.
18. module presence proves runtime usage - REFUTED.
19. 98.1% config match equals reproduction - REFUTED.
20. 190 CRC differences equal 190 source differences - SUPERSEDED, upper bound.
21. template-side `EnableSelinux` reaches Linux via `storeargs` - REFUTED for the
    stale-arena observation, REPRODUCED through the htab, kernel transport then
    REFUTED for every form.
22. htab `bootargs` reaches Linux verbatim via `bootm` - REFUTED for this form,
    one run plus the full static map and three inert-field controls.

Added by this report:

23. `bootm` re-runs `storeargs`, which would explain the revert - REFUTED for the
    direct-call graph (N1). `preboot`, `storeargs` and `bootcmd` are not among
    the twelve command lines bootm executes.
24. the environment is silently re-imported from the default env between our
    verified read and `fdt_chosen` - REFUTED for the direct-call graph (N2).
    Zero `himport_r` call sites in bootm's 236-function closure or imgread's 28.
25. round57's FDT-A row, "FDT from image at `0x1080000` header parse" - wrong
    for the DTB leg. `bootm` runs `store dtb decrypt ${dtb_mem_addr}`, so the
    board DTB is decrypted from `dt.img` into `0x1000000` during bootm (N4).

Carried over from the previous revision of this file, now superseded by rounds
48 to 58:

26. "the root boundary is one unobserved arrow: a host-written byte in BL33 RAM
    becoming visible to the kernel" - stale. That experiment was run four times
    and refuted. The boundary is now inside BL33's bootm window, and the open
    question is no longer whether the marker reaches Linux.
27. experiments E1 and E2 as previously written, "write the live arena `bootargs`
    value and boot" - dead. That form is round48. The arena is a stale shadow
    copy and must not be used as an oracle after a `setenv`.

## Final assessment

**What exists.** Arbitrary RAM write and control-flow hijack inside the running
bootloader, over a fully mapped 116-command table whose consumer is a 64-bit
load with no transform in between, with a same-cycle oracle and verified
restore. A proven, fresh-pointer-verified write into the authoritative
environment hash table and a proven script consumption of it. A complete static
map of the fastboot memory flow with the operational gate measured. A recovered,
validated board DTB. A reproduced GhostLock trigger, consumer and object-fidelity
signal, plus a hard negative on order-2 reclaim and a scoped negative on
disclosure. Twenty-two closed leads so nobody re-spends a session on them.

**What is still missing.** On the bootloader side, one observation: what
`fdt_chosen` writes when the environment holds a marker. It has exactly two
callers, one of which is a command we can type in the burning session, and it
has never been executed by us. Three hardware runs say the marker does not
survive `bootm`; nothing yet says whether that is because `fdt_chosen` never saw
it, because a different FDT was delivered, or because the reading we have is one
step removed from the kernel's. On the kernel side, a first kernel-VA disclosure
byte, then verified reclaim, then reuse geometry, then a write primitive, in
that order.

**Why the gap exists.** The two boundaries fail for unrelated reasons and need
different kinds of evidence. Controlling BL33 does not equal controlling Linux
because a verifier in secure world sits between them, and it returns the same
timing for plaintext and for garbage, so no amount of address or format work
moves it. The one route that does not touch the verifier is the environment
value U-Boot itself feeds to the kernel, and that route is now closed too, not
because the mechanism is wrong but because something inside `bootm`'s window
discards the bytes: the store is proven, the parser is proven, the template
rebuild is proven, the FDT pointer identity is proven, the kernel cmdline source
is proven to have no alternative, and yet three independent inert fields come
back stock. That contradiction is the finding, and it is smaller than it was.
Controlling an errno does not equal controlling memory, because KASLR with 39-bit
VA, `%pK`, SELinux, `SLABINFO=n` and disabled tracing mask every audited channel.

**What evidence would close it.** For the bootloader side: one session log with
the marker in the htab, `fdt addr`, `fdt chosen`, and an `mread` of the scratch
blob showing what landed under `/chosen/bootargs`. No boot involved. For the
kernel side: a capture with `POINTER_BYTES_FOUND > 0` traced to a PI object
field. Until one of those exists, claiming root would be filling the gap with
hypothesis, which is exactly what the cleanup pass removed from this
repository.