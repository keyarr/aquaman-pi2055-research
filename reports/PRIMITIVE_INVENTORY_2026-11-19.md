# Inventory of demonstrated primitives - 2026-11-19

Scope: USB gadget `1b8e:c003` bcdDevice `0007`, stage 16 (TPL/BL33-u-boot),
RAM-only. Nothing here is persistent. Status follows `CURRENT_STATE.md`:
HARDWARE_REPRODUCED (two or more sessions or oracle + restore),
HARDWARE_OBSERVED (one session), OFFLINE_ONLY, REFUTED.

This file is the inventory requested at the resumption of rounds 62-64. It does
NOT replace `CURRENT_STATE.md`; it records primitives that the 2026-10-02 index
has not yet captured (mainly those from 2026-11-19 in `/tmp/`).

## 1. Control primitives in BL33

| # | Primitive | Evidence | Status | Limitation |
| - | --------- | -------- | ------ | ---------- |
| P1 | `WRITE_MEM 0x01` / `FILL_MEM 0x03`: RAM write at address and bytes chosen by the host | `optimus-write-mem-round39.md`, `bl33-campaign-round43.md`, `bl33-same-cycle-round46.md` | HARDWARE_REPRODUCED | only 32-bit address; non-Secure RAM; returns to factory state on reboot |
| P2 | `ldr x4,[x19,#0x10]; blr x4`: `cmd_tbl` handler redirect to an existing handler, same-cycle, reversible | `bl33-cmd-redirect-round42.md`, round46 Exp1 | HARDWARE_REPRODUCED | only points to already-existing code until Phase 1 |
| P3 | **Execution of host bytes INSIDE BL33**: stub `mov w0,#0;ret` at `0x37800000`, `false` handler `0x37f616d0` redirected, `dcache flush`, `false: failed: -> success`, clean restore | `reports/plan-smc-gate-neutralize-magisk.md` section "Execution status", item Phase 1 GO (2026-11-19) | HARDWARE_REPRODUCED | was not in `CURRENT_STATE.md` (which says "never"); `icache flush` (idx 60) was never used together |
| P3b | **Hook at `0x37e265fc`** (`blr x4` in the `do_bootm_linux` wrapper): replace with `b 0x37800000`, stub writes to the decompressed image and returns with `blr x4` + `br 0x37e26600` | `/tmp/exec-toctou-2026-11-19.md`, `exec-toctou-v2-2026-11-19.md`, `diag-toctou-2026-11-19.md` | HARDWARE_REPRODUCED (hook executes, boot occurs, BOOT_ID changes) | evidence only in `/tmp/`, not consolidated until this file |
| P4 | `cmd_tbl` mapped: 116 entries, base `0x37f60eb0`, stride `0x30`, `+0x10` handler; `live == offline` | `root-final-analysis/04-cmdtbl-slots.txt`, round46 | HARDWARE_OBSERVED | stable across boots; htab is not |
| P5 | Bulk download `0x32` (`AM_REQ_DOWNLOAD`) armed by `bulkcmd "download mem ... normal ..."`; 16 MiB at `0x1080000` in 0.8 s with sha256 read back | `plan-smc-gate...` item 2; `tools/download_mem.py` | HARDWARE_REPRODUCED | requires 64 KiB/chunk payload and `OK!!` reply |
| P6 | `bulkcmd 0x34` as oracle: `false -> failed:`, `true -> success`; `mread 0x33` reads RAM | `optimus.py`, all BL33 rounds | HARDWARE_REPRODUCED | `fastboot oem <cmd>` only returns AMLOGIC+OKAY, not useful as oracle; `help` broken |
| P7 | `imgread kernel boot 0x1080000` + `bootm 0x1080000` (E4/E5) boots stock in-session, USB drops ~4.7 s | `reports/_archive/buffer-equals-loadaddr-proof.md` E4/E5 | HARDWARE_REPRODUCED | image still goes through the SMC |
| P8 | RAM read via `MREAD 0x02` and via `0x33/0x34`, with host-chosen address | `optimus.py`, `rdlarge-bulk-read.md`, `mread-via-bulkcmd.md` | HARDWARE_REPRODUCED | `0x12 RD_LARGE_MEM` dead in this build; MREAD of Secure memory (`0x05100000`) drops the gadget |

## 2. Decrypt and state primitives

| # | Primitive | Evidence | Status | Limitation |
| - | --------- | -------- | ------ | ---------- |
| P9 | Wrapper `0x37e19ea8` (`mov x0,#0x820000ff; smc #0`) with site1 args (`0x40,0x1080000,0x1800000,7`) returns `x0=0` and leaves plaintext kernel at `0x1080000` (`ANDROID!`, `0x959000`) without issuing `eret` | `plan-smc-gate...` item 1; `kernel-ram-patch-v2.md` section 9.2 | HARDWARE_OBSERVED (two sessions) | worked once via stub; repeating froze; likely cause `bl 0x37e19310` at `0x37e19ee8` (cache/TLB maintenance) without `icache flush` |
| P10 | Authoritative env htab (`0x37ee7278`): `setenv` and WRITE to the data pointer reach the parser (`test ${VAR}`); `run storeargs` rebuilds `bootargs` 832 B with 1-field diffs | `round51-env-htab-oracle.md`, `round52-write-htab-template.md` | HARDWARE_REPRODUCED | entry pointer changes on every rebuild; arena `0x33e18000` is stale shadow |
| P11 | DTB of 58,280 B at `0x01000000`, `d00dfeed`, clean `dtc` round-trip, 376 nodes/1798 props | `aquaman-dtb-extraction.md`, `artifacts/aquaman.dtb` | HARDWARE_REPRODUCED | pre-fixup blob, without `/chosen`; delivery to Linux not confirmed |
| P12 | GhostLock: FWRQ/FCRQ trigger -> EDEADLK 5/5; `FUTEX_LOCK_PI` consumer with differential; `f_target`/`f_alt` by occupancy/fidelity | `CURRENT_STATE.md` GhostLock section | HARDWARE_REPRODUCED | zero kernel VA bytes disclosed; reclaim FAIL; H16 write 0/33 |
| P13 | `keyman read` returns 3 ASCII blobs (`sn2`, `bt_rc_mac`, `netflix_mgkid`) in host-chosen RAM | `round61-bl31-plaintext-e-port.md` Phase A | HARDWARE_OBSERVED | not AES keys for `bootloader.img`/`boot.img` (Phase B: 0 hits/90 tests) |

## 3. Hypothetical primitives (not executed; prioritized candidates)

| # | Primitive | Basis | Risk | Value |
| - | --------- | ----- | ---- | ----- |
| H1 | `fdt addr <scratch>` + `fdt chosen` + MREAD of blob: observe the `env_get -> fdt_setprop` arrow without boot | `fdt_chosen 0x37e297b8` has 2 callers, one is typable subcommand `0x37e293e4`; bare `fdt chosen` is safe (`x22=x2=0` -> fixup `cmp x1,x2;b.ne` returns without touching) - `offline bootm-handoff analysis` | low | only discriminator of whole-string revert that does not require boot |
| H2 | `0x11 WR_LARGE_MEM`: `ctrl OUT 0x40/0x11, wValue=0x40,wIndex=1,wLength=8`, payload `<u32 addr><u32 len>`, data via bulk OUT; no denylist and no 64 B cap | `.src/u-boot-khadas/drivers/usb/gadget/v2_burning/usb_pcd.c:632-650` - `offline USB protocol analysis` | medium | speeds up large patches in BL33 |
| H3 | `read_raw_img <part> <addr> <off> <size>`: bring real FIP/BL31 from the device into RAM then MREAD | `offline USB protocol analysis` | low | enables binary diffing of BL31 without external key |
| H4 | cgroupfs `current_css_set` (`%llu`) and `cgroup_css_links` (raw `%p`; this 4.9.113 has no `ptr_to_id`) leak kernel heap pointer | `.src/linux-amlogic/kernel/cgroup.c:6548,6603,3570`, `CONFIG_CGROUP_DEBUG=y` - `offline kernel disclosure analysis` | zero (read-only) | first kernel VA anchor; unlocks GhostLock |
| H5 | NOP of `bl 0x37e19310` at `0x37e19ee8` stabilizes repeated calls to the wrapper (`0x820000ff`) | wrapper disasm - `offline SMC gate analysis` section 1.4 | medium | turns P9 into a repeatable oracle |
| H6 | `bpf()` does not require `CAP_SYS_ADMIN` in this kernel (`sysctl_unprivileged_bpf_disabled=0`); real gate is SELinux, never measured | `.src/linux-amlogic/kernel/syscall.c:977`, `hooks.c:6096` - `offline kernel disclosure analysis` | medium | possible map/leaker primitive via BPF |

## 4. Candidate chains and link status

### Chain A - BL33 hook -> patched kernel -> uid=0 (priority)

```
P1/P3  WRITE/FILL + exec of bytes in BL33              REPRODUCED
  -> P3b hook 0x37e265fc -> decompressed image         REPRODUCED (toctou v1/v2)
  -> exact physical addresses (cap_capable 0x13bbca8,  REPRODUCED (diag-toctou)
     cave 0x1dbbe00, addend 0x2657828, physical slide 0)
  -> trampoline commit_creds(prepare_kernel_cred(0))   OFFLINE_ONLY (tramp_v2.bin 80 B)
  -> trigger syscall 92 in running kernel              NOT EXECUTED in this combination
  -> uid=0                                            NOT DEMONSTRATED
```

Links already refuted in this chain: `cap_capable`/`avc_*` patches (v1/v2 gave
`setgid: EPERM`), direct `br x20` to `0x1080000`, gzip patched via CBZ, constant
`0x1234` return in personality (all in `kernel-ram-patch-v2.md` section 9.4 -
none executed the injected code because the boot chain was wrong; the
`0x37e265fc` hook fixed that).

### Chain B - env -> cmdline -> root (partially open)

```
P10 setenv/WRITE to htab                               REPRODUCED
  -> run storeargs rebuilds bootargs 832 B             REPRODUCED
  -> env_get("bootargs") inside fdt_chosen             INFERRED (never observed)
  -> fdt_setprop(/chosen,bootargs)                      INFERRED
  -> /proc/cmdline == DT property                      PROVEN (config)
  -> init androidboot.X -> ro.boot.X                   EXTERNAL
  -> 3 inert fields revert to stock                    REFUTED 3x (round53/56/58)
  -> uid=0                                             NOT EXECUTED
```

Only observable link missing: H1. If H1 gives NO-GO, chain B is dead at the first
arrow and does not justify another boot.

### Chain C - GhostLock (open at the disclosure bottleneck)

```
P12 trigger + consumer + fidelity                      REPRODUCED
  -> H4 kernel pointer leak                            HYPOTHETICAL
  -> forge of rt_mutex_waiter                          INCONCLUSIVE
  -> write 8B / R/W / cred                             INCONCLUSIVE
  -> uid=0                                             NOT EXECUTED
```

### Chain D - USB protocol / BL31

```
P7 imgread+bootm (stock passes the gate)                REPRODUCED
  -> H3 real FIP/BL31 read from the device              HYPOTHETICAL
  -> H5 stable wrapper + H2 bulk write                  HYPOTHETICAL
  -> H6/H4 kernel primitive                             HYPOTHETICAL
  -> uid=0                                             NOT EXECUTED
```

## 5. Limitations preventing promotion of primitives

- SMC `0x820000ff` rejects unsigned payload before the kernel
  (`aml_sec_boot_check`). The gate is a content-check, not an EL3 barrier: the
  stock image passes and returns plaintext. Bypass is not necessary if the
  intervention is post-decrypt.
- Writing to Secure memory via MREAD drops the gadget (round60); draw no
  conclusions about the SMC from that drop.
- `RUN_IN_ADDR 0x05` wedges USB even for a no-op; `MODIFY 0x04` kills the
  session; `clear_halt` fails with errno 75. Do not use.
- Handoff instrumentation: only `cbz 0x37e24cf8` is abort-safe; x25 is unstable;
  globals do not point to FDT early; later points drop the gadget (`round62-64`).
  This closes instrumentation by intercept, not the `fdt chosen` subcommand.
- No root yet: uid=2000, Enforcing, `/proc/cmdline` and
  `/proc/device-tree/chosen/bootargs` denied to shell.
- Recovery I used: `dev.reset()` / `libusb_reset_device()` -> `sleep(0.6)` ->
  re-find `1b8e:c003`. Never power cycle, never VBUS off.

## 6. Next prioritized experiments

1. **Chain A with `commit_creds` trampoline** (hook `0x37e265fc` +
   `tramp_v2.bin` + addend `0x2657828` + trigger syscall 92). It is the only
   combination using two already-demonstrated ends and directly attacks
   `uid=0`.
2. **H1** (`fdt chosen` on scratch FDT with marker) - cheap, no boot, separates
   the three explanations of whole-string revert.
3. **H4** (`current_css_set`) - read via adb, zero risk, may unlock chain C.

Artifacts from 2026-11-19 still outside the repo as of this file:
`/tmp/exec-toctou*.md`, `/tmp/diag-toctou*.md`,
`/tmp/v2/tramp_v2.bin` (sha `d68fc82b...`),
`/tmp/v2/trigger` (sha `c6679e3d...`),
`/tmp/stub/kernel_patch_v3.bin` (sha `8ed0707b...`).

## 7. Round 65 update (2026-11-19, after execution)

New demonstrated primitive:

| # | Primitive | Evidence | Status |
| - | --------- | -------- | ------ |
| P14 | `read_raw_img <part> <addr> <off> <size>` reads real eMMC partition into host-chosen RAM | `read_raw_img boot 0x37800000 0 0x100 -> success` with `ANDROID!`; 15 windows of `bootloader` partition read | HARDWARE_REPRODUCED; ciphertext only, no FIP magic |

New refutations (see `reports/round65-2026-11-19-consolidation.md`):

- **`fastboot boot` ignores the sent file.** Stock, 2 one-byte flips and
  `XXXXXXXX` header produce the same signature (USB OFF 1.2 s, Android ON
  18.4-18.7 s, `reboot,fareboot`, stock 4.9.113 kernel). This disqualifies all
  conclusions based on "unsigned payload rejected by the gate".
- Chain A (hook `0x37e265fc` -> trampoline/marker/spray) REFUTED in all three
  forms: `commit_creds` gave `uid=2000`, marker `4.9.XYZ!` did not appear in
  `/proc/version`, spray across six bases did not appear. The executed kernel
  does not come from any written buffer.
- Chain B: E1 and E1b NO-GO - `fdt chosen` returns `success` but does not write
  bootargs to scratch FDT. Arrow `env_get -> fdt_setprop` not observable via the
  subcommand.
- H4 cgroupfs REFUTED (`current_css_set`/`cgroup_css_links` absent).
- H6 BPF INCONCLUSIVE as disclosure (syscall reachable, no fd created).
- `ARMd` scan with loop in BL33 froze the SoC; I recovered with a power
  cycle. Do not repeat loops in BL33 (`incident-loop-scan-2026-11-19.md`).

Prioritized open path: BL33 -> Android output channel via `androidboot.scan=` in
the DTB, to locate the executed copy of the kernel without relying on MREAD
after a freeze. Then, SMC matrix `0x820000ff` with real GO.
