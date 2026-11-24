# Round 65 - consolidation and new refutations (2026-11-19)

Resumption of rounds 62-64. Goal: turn demonstrated primitives into an
exploitation chain up to uid=0. Not achieved. But the round produced a
structural discovery that unifies four years of negative results.

Nothing here changes `CURRENT_STATE.md` (which remains the epistemological index
of 2026-10-02). Technical inventory in `reports/PRIMITIVE_INVENTORY_2026-11-19.md`.
TOCTOU evidence consolidated in `reports/toctou-delivery-2026-11-19.md`.
Freeze incident in `reports/incident-loop-scan-2026-11-19.md`.

## Central discovery: `fastboot boot` ignores the sent file

Experiments via `fastboot boot <file>` with USB watcher and reading
`/proc/version` after boot:

| File | USB OFF | Android ON | bootreason | kernel |
| ---- | ------- | ---------- | ---------- | ------ |
| `firmware/boot.img` stock | 1.20 s | 18.61 s | `reboot,fareboot` | 4.9.113 stock |
| stock with 1 byte flipped at `0x900` | 1.18 s | 18.42 s | `reboot,fareboot` | 4.9.113 stock |
| stock with 1 byte flipped at `0x580000` | 1.19 s | 18.70 s | `reboot,fareboot` | 4.9.113 stock |
| **stock with `XXXXXXXX` header** | 1.21 s | 18.70 s | `reboot,fareboot` | 4.9.113 stock |

The host fastboot reports `Sending ... OKAY` and even repackages the image
(`creating boot image - 16779264 bytes`), but the device **always boots the
stock kernel from eMMC**, regardless of the received content. This is
HARDWARE_REPRODUCED (4 boots, 4 identical signatures).

Consequences that unify previous results:
- The "SMC gate rejects unsigned payload" (E7/M1a/M1b/E1/CTRL) was never a test
  of the gate: the sent file simply was not used. The 15-21 s "rejection timing"
  is stock boot timing.
- The "rejected" patched Magisk was ignored, not rejected.
- The CBC oracle has no signal: there is no ciphertext-dependent rejection.
- RAM patches at `0x1080000` do not reach the kernel because the executed kernel
  does not come from that buffer.

This corrects the interpretation of `CURRENT_STATE.md` lines 38, 41, 81 and
`reports/_archive/ROOT_FINAL_ANALYSIS.md` chain 5. The gate may still exist, but it has not been
demonstrated by any `fastboot boot` experiment.

## Experiments executed in this round

### Chain A - hook 0x37e265fc -> patched kernel -> root: REFUTED

1. **`commit_creds` trampoline** (offline SMC gate analysis proposal
   5.1): hook `0x37e265fc` (`b 0x37800000`), 100 B stub copies `tramp_v2.bin`
   (80 B) to the cave `0x1dbbe00` and writes the addend `0xffffff8009dbbe00` at
   `0x2657828` (sys_call_table[92]). `dcache flush` + `icache flush` OK, boot
   occurred, BOOT_ID changed. `trigger` returned `personality=8 uid=2000
   euid=2000`. REFUTED. Artifacts: `/tmp/stub/kernel_root.{S,o,bin}`,
   `/tmp/root_try.{py,result.json,usb.log}`.
2. **Direct-consumption oracle** (`marker.bin`, 56 B): same write via hook
   replacing `4.9.113` with `4.9.XYZ!` at physical offset `0x1dc008e`. Boot
   occurred; `/proc/version` returned `4.9.113`. Decisively REFUTED: the patched
   image at `0x1080000` is not the one that executes. Artifacts:
   `/tmp/marker_try.py`, `marker_result.json`.
3. **Marker spray** (`marker_spray.bin`, 136 B): write of the same marker
   relative to six candidate bases (`0x1080000`, `0x1000000`, `0x2000000`,
   `0x30000000`, `0x31000000`, `0x4000000`). Boot occurred; `/proc/version`
   stock. REFUTED for all tested bases. Artifacts:
   `/tmp/stub/marker_spray.S`, `marker_spray_result.json`.
4. **`ARMd` scan at the hook** (to locate the real copy): the stub entered an
   infinite loop in BL33 to allow MREAD; the gadget dropped off the bus and did
   not re-enumerate. Recovered via user-authorized power cycle. See
   `reports/incident-loop-scan-2026-11-19.md`. **Do not repeat loops in BL33.**

Links already refuted before this round and not repeated: direct `br x20`, gzip
patched via CBZ, `cap_capable`/`avc_*` patches, constant return in personality
(`kernel-ram-patch-v2.md` section 9.4).

### Chain B - env -> cmdline: REFUTED at the observable arrow

E1: `setenv EnableSelinux permissiv` + `run storeargs` (`test` oracle PASSED),
2184 B scratch FDT at `0x30000000` (sha `dba1f90b...`), `fdt addr` updated the
global `0x37f72a90` from 0 to `0x0000003000000000`, `fdt chosen` returned
`success`. MREAD of `0x888`: **marker intact**, no `permissiv` or `enforcing`
written. NO-GO.

E1b: four syntax variations (`fdt chosen 0 0`, `fdt chosen 0x0 0x0`,
`fdt 0x30000000 chosen`, `fdt chosen 0 0x888`) - all NO-GO, byte-identical blob.

This closes chain B: the only cheap observation of the `env_get -> fdt_setprop`
arrow does not work via subcommand in this build. The boots of rounds 53/56/58
need not be repeated.

### USB surface - new primitive, no plaintext gain

`read_raw_img <part> <addr> <off> <size>` works and brings real eMMC bytes into
host-chosen RAM (HARDWARE_REPRODUCED):
- `read_raw_img boot 0x37800000 0 0x100` -> `ANDROID!`, `kernel_size 0x959000`.
- `read_raw_img bootloader ...` -> ciphertext (zeros at the start, encrypted
  data from 0x1000).

Scan of 15 windows of 0x1000 in the `bootloader` partition (offsets 0 to
0x1c0000): **zero** occurrences of FIP magic, `@AML`, `AMLSECU!`, `BL31`,
`ARMd`. The ciphertext is already in `firmware/bootloader.img`; without a key
there is no plaintext. No gain over offline material.

## Kernel disclosure - two refuted hypotheses

- H4 cgroupfs: `find /sys -name current_css_set -o -name cgroup_css_links`
  returned empty. Only legacy cgroup mounted (`/acct`, `/dev/stune`,
  `/dev/cpuctl`, `/dev/cpuset`, `/dev/cg2_bpf`). No `debug` subsys. REFUTED.
- H6 BPF: `bpf(BPF_MAP_CREATE)` is reachable (kernel errno 22/9, not SELinux
  EACCES), but no attr type/size produced an fd. No leaker. `/proc/kallsyms` and
  `/proc/sys/kernel/kptr_restrict` denied to shell. INCONCLUSIVE as a capability,
  with no demonstrated disclosure value.

## Updated chain map

| Chain | Status this round | Critical missing link |
| ----- | ----------------- | --------------------- |
| A: BL33 hook -> patched kernel -> root | REFUTED | executed image is none of the writes; execution location unknown |
| B: env -> cmdline -> root | REFUTED | `fdt chosen` inert; `env_get -> fdt_setprop` arrow not observable |
| C: GhostLock -> disclosure -> R/W -> cred | OPEN | still zero kernel VA bytes; H4 and H6 did not deliver |
| D: fastboot/SMC -> custom boot | REFUTED in this form | `fastboot boot` ignores the file; gate was never exercised |
| E: USB 0x11 WR_LARGE_MEM / 0x820000ff unclassified | NOT TESTED | requires real GO + dcache/icache flush, no Secure MREAD |

## Paths that remain open

1. **Locate the executed copy of the kernel without a loop in BL33.** Use the
   `0x37e265fc` hook to write a marker in the DTB (`ro.boot.*` channel survives
   boot) instead of relying on MREAD after a freeze. If the DTB at `0x1000000`
   is the delivered one, `getprop ro.boot.scan` will work as a write oracle and
   can load the addresses from the `ARMd` scan.
2. **`0x820000ff` matrix with real GO**: cmds `0x10/0x14/0x20/0x80` and NOP of
   `bl 0x37e19310` at `0x37e19ee8` to stabilize the wrapper. No MREAD of
   `0x05100000`. One cmd per session, with `dcache`+`icache flush`.
3. **GhostLock**: without disclosure, nothing changes. Look for not-yet-audited
   read surface (f_op depth > 3; /dev outside C1-C3) with SELinux Enforcing and
   shell uid 2000.
4. **0x11 WR_LARGE_MEM** (`usb_pcd.c:632-650`): bulk write with no denylist and
   no 64 B cap. Useful for loading large stubs, does not solve the consumption
   link.

## Cheapest and most informative single next experiment

Test whether the DTB at `0x1000000` is the one delivered to the kernel: at the
`0x37e265fc` hook, write `androidboot.scan=DEADBEEF` to a free area of the DTB
and, after boot, read `getprop ro.boot.scan`. This (a) creates an output channel
from BL33 to Android without post-freeze MREAD and (b) allows, in the next round,
writing the results of the `ARMd` scan to that channel and finally locating the
executed copy of the kernel. Risk: a RAM-only boot, the same as the E4 control.

If this channel fails, there is no BL33 output oracle and chain A must be
considered dead; resources migrate entirely to the SMC matrix and GhostLock.

## Device state

Recovered via authorized power cycle. At the end of the round: Android
`2717:4e40`, `sys.boot_completed=1`, uid=2000, Enforcing, stock 4.9.113 kernel.
No persistent writes in any experiment.
