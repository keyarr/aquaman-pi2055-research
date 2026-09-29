# custom-kernel-execution — what can actually run our kernel, and what cannot

written after phases 1-6, so the addresses and the DTC situation are settled.
**no command was run on the device for this report.** the matrix is built
from `reports/fastboot-memory-flow.md` (static + E1-E8 runtime evidence),
`reports/rebuilt-kernel.md` (the artifacts exist), and
`reports/vendor-modules.md` (the stock `.ko` cannot be reused).

every cell is either measured, derived from the source, or marked unknown.
nothing is guessed.

## the matrix

| method | requires flash | requires root | RAM-only | proven | risk |
|---|---:|---:|---:|---:|---:|
| `fastboot boot` (unsigned) | no | no | **yes** | **no** | low (reboot only) |
| `fastboot boot` (stock signed image) | no | no | yes | **yes** (E5) | low |
| `set_active:` sink → `bootm X` | no | no | yes | no (E1/E3) | low |
| `booti` / `go` | no | no | yes | **absent** (E8) | low |
| `imgread` + `bootm` | reads eMMC | no | yes | **yes** (E4) | low |
| `autoscr` | no | no | yes | no | low |
| `adb reboot update` (ROM USB) | no | no | yes | **no** (never reached) | **high** |
| `fastboot flash` | **yes** | no | no | untested | **high, forbidden** |
| exploit (GhostLock) | no | **yes** | yes | no | **high** |

legend: "proven" = executed our code, or proven not to work.
"absent" = command does not exist in this build.

## 1. `fastboot boot` — the RAM-only path, and why it is closed

this is the only RAM-only path that would work if anything did, and it is
blocked. the mechanism, established in `fastboot-memory-flow.md` §6:

```text
do_bootm_on_complete → do_bootm(load_addr)
  → aml_sec_boot_check(AML_D_P_IMG_DECRYPT, load_addr, 24MiB, GXB_IMG_DEC_ALL)
       → SMC into BL31, which verifies and decrypts in place
```

BL31 is secure-fused on this device. `getvar secure:no` reports the *flash
lock*, not the eFuse, and the two disagree here. evidence:

- E4: stock-signed image at `load_addr` → SMC passes → Android boots.
- E7: plaintext at the **same** `load_addr`, same rails → rejected, ~18 s.
- E5 vs E6: the only difference between a working and a failing `bootm` is
  whether the bytes are AMLSECU-signed.

every unsigned image dies there, before format detection, before the DTB is
consulted, before any of our bytes run. this is why M1a, M1b, M2, E1 and the
raw control all returned to Android in 15-21 s with an empty bootreason: they
never got past the SMC.

**addresses are irrelevant here.** the download buffer and the boot address do
overlap (E5/E6), so the "download ≠ boot source" theory is dead, but fixing it
would not help, because the gate is upstream of it.

## 2. the unsigned legs that skip the SMC — and why they are not there

`booti` and `go` bypass `do_bootm` entirely, so they would skip the SMC. E8
ran both against a valid ARM64 Image at `load_addr`: instant FAIL in 0.0 s,
device stayed in fastboot, whereas a real command takes time and drops the
gadget. `go` cannot fail on valid input, so the commands are **not compiled
into this build**.

corroborating detail: `help` is useless as an oracle here because `cmd_usage`
always returns 1 (`common/command.c:139`).

so there is no unsigned boot entry point at all. this is the tight part of the
blocker: it is not "we have not found the right command", it is "the two
commands that would work are not in the binary".

## 3. the `set_active:` sink — a real RAM-only injection, still gated

`set_active:` dispatches to `cb_set_active`, which builds
`set_active_slot ;bootm <addr>` and hands it to `run_command` with
`FLAG_PARSE_SEMICOLON`. `set_active_slot` dies on `argc != 2` before touching
storage, and `;` does not short-circuit, so the second command runs anyway. it
is a genuine, RAM-only way to call `bootm` with an explicit address — the most
interesting thing in the whole U-Boot attack surface, and it is already fully
mapped offline in `reports/set-active-sink.md`.

it does not help: it calls `do_bootm`, which calls the same SMC. E1 and E3
confirm — instant FAIL on every candidate address.

**but it stays on the list** for one reason: it is the only sink that takes an
*address argument*. if the AMLSECU obstacle were ever lifted, or if a future
experiment finds a command that jumps to an address without SMC, the sink is
already characterised and RAM-only. worth keeping, not worth retrying.

## 4. paths that were not taken, and why

**BootROM / USB burning (`1b8e:c003`, WorldCup).** `adb reboot update` was
tested: the device re-enumerated as `18d1:4e41` (recovery, MTP, droidlogic)
and stayed there for the full 90 s poll. it never reached the BootROM. USB
burning is also explicitly out of scope and carries real flash risk (`bulkcmd`
can erase). **not pursued.**

**`fastboot flash`.** banned, persistent, and irrelevant: the U-Boot on the
eMMC path may require AMLSECU even with `secure:no`, so it could brick the
stick for no gain.

**exploit track (GhostLock).** the last commit in this repo is titled "ghostlock
port dead end documented, six panics for nothing". dispatch and the rollback
path were reached on the device, exploitability was not demonstrated. it is
also explicitly out of scope for this task. **not pursued.** one thing worth
carrying forward: `pstore_io_save` is missing from the rebuilt kernel
(`reports/vendor-modules.md`), so a custom kernel would not be able to write
compressed pstore records even with root — which weakens the post-mortem plan
in `ghostlock-risk.md`.

**UART / testpoint / disassembly.** banned by the task rules.

## 5. what a custom kernel would still need, once it can run

not to answer a question nobody asked — this is the honest list of what is
missing beyond the SMC:

1. **a DTB.** the only one built is `gxl_p241_1g.dtb`, the wrong board. the
   real one is sealed in `dt.img` (`dts-analysis.md`). this is a real blocker
   independent of the SMC, and it is why `fastboot-kernel-path.md` §4.5
   matters: U-Boot hands the kernel *its own* DTB, so a fastboot boot does not
   need one — but a real boot does.
2. **media drivers.** the stock `.ko` set cannot be reused (190 CRC mismatches),
   so a custom kernel needs its own video decode, or ships without it.
3. **Wi-Fi/BT.** `rtl8821cs` and `sdio_bt` are Realtek/vendor, and the W1 host
   symbols the modules import do not exist in this tree at all.
4. **DVB demux.** dropped from the baseline, because McMCCRU HEAD does not
   compile with it on (`rebuilt-kernel.md` §7).

items 2-4 are all downstream of "no exact source", which is the actual root
blocker for a *useful* custom kernel. the SMC is the blocker for *any* custom
kernel.

## 6. verdict

```text
EXECUTION: BLOCKED
```

blocked at **BL31**, on a **secure-fused** device, for **unsigned payloads**,
on **every** RAM-only fastboot path. not blocked by address confusion — that
question is settled — and not blocked by anything recoverable from the local
dumps.

what would change it, ranked by cost:

1. the `aml-user-key.sig` for aquaman/PI.2055, to sign a repack with
   `--imgsig`. never published; GPL request #11 open since 2025-01.
2. the unencrypted `u-boot.bin`, which would settle the `booti`/`go` question
   definitively. would **not** unlock execution on its own.
3. a BootROM vulnerability. explicitly out of scope, and the stick has no
   physical button, so it needs a cold reset.

none of these are cheap, and none of them are things this repo can do. the
research chain up to "Image + DTB + modules built reproducibly" is intact and
documented; the last link is blocked on a closed binary.
