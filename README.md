# Aquaman PI.2055: research that led to root and permissive SELinux

Lab notebook for a Xiaomi Mi TV Stick 1080p (MiTV-AESP0, codename aquaman,
Amlogic S805Y/GXL), Android 9 PI.2055, stock kernel 4.9.113 built
2022-09-06 by jenkins@c5-mitv-cm-build06.bj.

The research started with two questions: which source tree built that
kernel, and what can still be executed on the device. Both stayed open on
the boot chain. The practical result came from a different direction: on
2026-11-23 the device got persistent root and Permissive SELinux through
the ODM partition and an init-loaded kernel module. No boot-chain bypass,
GhostLock exploit, custom kernel, efuse change or vbmeta change was used.

This is not a ROM, a root guide, or a kernel release. It is a lab
notebook. Most reports record negative results on purpose, so closed
leads stay closed.

## Result

| Outcome | Observed on device | How | Report |
| --- | --- | --- | --- |
| Persistent root | `uid=0(root) gid=0(root) groups=0(root) context=u:r:dumpstate:s0` on TCP 4444, survives reboot | ODM rc starts an init service; Android 9 init imports `/odm/etc/init/root.rc` | `reports/root-via-odm-2026-11-23.md` |
| SELinux Permissive | `getenforce` -> `Permissive`, `/sys/fs/selinux/enforce` -> `0` | The same ODM rc loads `seflip`, a kernel module that writes `selinux_enforcing = 0` from kernel mode | `reports/selinux-permissive-via-module-2026-11-23.md` |
| Actual boot state readable | `/proc/cmdline` and the `Kernel command line:` line in `dmesg` are byte-identical | root | `reports/root-read-surface-2026-11-23.md` |

Root here is not an unlocked bootloader. BL31 still rejects unsigned images
over SMC before Linux starts, and the rebuilt kernel is not ABI-compatible
with the stock modules. Flashing a custom kernel remains blocked. To revert
the device to stock, reflash stock ODM; rebooting alone does not restore
Enforcing. The root listener should not be left exposed to an untrusted
network.

## How the research got there

1. **Source provenance.** No exact source found in searched public
   material. The closest public tree, `McMCCRU/linux-amlogic` `3d4ab79e`,
   matches 98.1% of the expanded config but differs on 190 module CRCs and
   misses 13 symbols. It is a close family, not a reproduction.
2. **Boot chain.** Every RAM-only path ends in `bootm` -> SMC, and BL31
   rejects unsigned images before Linux. Env writes do reach the
   authoritative `htab` and `run storeargs` consumes them, but no mutated
   cmdline was ever shown to arrive at Linux.
3. **GhostLock.** Trigger, consumer and heap fidelity were reproduced, but
   no disclosure, reclaim or kernel R/W followed. It did not produce root.
4. **Pivot to ODM.** ODM is writable from fastboot and sits outside
   `vbmeta.parts` with no `avb`/`verify` flag. An rc file under
   `/odm/etc/init` is imported by Android 9 init. A service labelled into
   `dumpstate_exec` lands as uid 0 in `u:r:dumpstate:s0`, and the
   `vendor_init` domain that imports the rc can load a kernel module. That
   module flips `selinux_enforcing` without touching `setenforce`.

Each step above is a closed lead, not an open option. The evidence is in
`reports/INVALIDATED_HYPOTHESES.md`.

## Start here

Read in this order. Do not read `reports/` alphabetically.

1. `reports/CURRENT_STATE.md`: what is believed, at which evidence level,
   and what each claim supersedes. This file wins over every other page.
2. `reports/root-via-odm-2026-11-23.md`: the root construction and how to
   restore stock ODM.
3. `reports/selinux-permissive-via-module-2026-11-23.md`: current Permissive
   state, the module path and rollback.
4. `reports/root-read-surface-2026-11-23.md`: what uid 0 in `dumpstate` can
   and cannot read, and which old "unobservable" claims it supersedes.
5. `reports/EVIDENCE_MATRIX.md`: evidence by subsystem.
6. `reports/INVALIDATED_HYPOTHESES.md`: closed leads. Check here before
   proposing a theory.
7. `reports/MAP.md`: pointer to the reports that the main indexes do not
   name, grouped by track.

Two files from 2026-11-19 are not consolidated into the indexes above:
`reports/observations-new-angles-2026-11-19.md` (untested angles,
OFFLINE_ONLY) and `reports/plan-smc-gate-neutralize-magisk.md` (operational
plan, phase 0 only). Treat them as leads, not as current state.

## Terminology

| Term | Meaning |
| --- | --- |
| `aquaman` | Internal codename for the MiTV-AESP0. |
| `PI.2055` | Android 9 firmware build this repo is scoped to. |
| BL2 / BL31 / BL33 | ARM trusted firmware boot stages. BL31 is the secure monitor; BL33 is U-Boot. |
| SMC | Secure monitor call. BL31 uses it to reject unsigned images. |
| `bootm` | U-Boot command that validates, relocates, and boots an image. |
| `env`, `htab` | U-Boot environment. The authoritative store is a hash table (`htab`), not the RAM arena at `0x33e18000`. |
| `storeargs` | U-Boot script that rebuilds `bootargs` from env. |
| `bootargs` / kernel cmdline | The string U-Boot intends to pass to Linux. Whether a mutated one arrives is the open question. |
| `BUF`, `Y` | Fastboot download buffer and `bootm` load address. Overlap is proven; `BUF == Y` is not. |
| E5 / E6 / E7 | Controlled device experiments: stock boot, raw boot without download, signed vs unsigned. |
| McMCCRU | Public Amlogic 4.9 tree, the closest source family found. |
| CRC / vermagic | Module ABI checks. Vendor `vermagic` is flattened; `__versions` CRCs are the real gate. |
| DTB / DTS | Compiled device tree blob vs original source. |
| GhostLock | Futex PI stack use-after-free targeted here. Trigger and consumer reproduced; no reclaim or disclosure. |
| H16 | The 16-byte GhostLock heap target. Live retarget was not demonstrated. |

## Status at a glance

| Question | Current answer | Details |
| --- | --- | --- |
| Is there root? | Yes, persistent via an ODM init service: uid 0 in `u:r:dumpstate:s0`, TCP 4444. Not via GhostLock and not via a boot-chain bypass. | `reports/root-via-odm-2026-11-23.md` |
| Is SELinux enforcing? | No. Since 2026-11-23 an ODM-loaded kernel module sets `selinux_enforcing` to 0 at boot. `setenforce` is still denied to shell and `dumpstate`. Reboot alone does not revert; reflash stock ODM. | `reports/selinux-permissive-via-module-2026-11-23.md` |
| Can the delivered cmdline be read? | Yes, from root: `/proc/cmdline` and the `Kernel command line:` line in `dmesg` are byte-identical. The DT node was denied in the enforcing-only snapshot. Marker transport has not been re-tested with this oracle. | `reports/root-read-surface-2026-11-23.md` |
| Exact stock source? | Not found in searched public material. `McMCCRU/linux-amlogic` `3d4ab79e` is close family, not exact. This does not prove none exists. | `reports/provenance.md` |
| Can the kernel be rebuilt? | Only as an approximation: 98.1% of the expanded config matches, 190 CRCs differ, 13 symbols are missing. Not a reproduction. | `reports/_archive/rebuilt-kernel.md` |
| Can vendor modules be reused? | 28 `.ko` were extracted from the OTA. Presence is proven; loading is not. CRCs are the gate, not vermagic. | `reports/vendor-modules.md` |
| Can an unsigned kernel boot? | No on every RAM-only path tested. BL31 rejects it over SMC before Linux runs. No bypass demonstrated. | `reports/bl31-exact-round18.md` |
| Can U-Boot pass a modified cmdline? | Not demonstrated. Env writes reach the authoritative htab and `run storeargs` consumes them. Transport to the kernel cmdline is refuted for every form tried. | `reports/CURRENT_STATE.md` |
| Is the DTS available? | The DTB was recovered from RAM (58,280 B, valid). The original DTS source is still missing. A RAM blob is not proof Linux received it. | `reports/aquaman-dtb-extraction.md` |
| Where does fastboot write? | Download overlaps the region `bootm` reads (E5/E6). Exact `BUF` remains unknown. | `reports/fastboot-memory-flow.md` |

## Evidence boundary

Hardware-proven: E5/E6 overlap, E7 SMC reject, BL33 WRITE/FILL and
same-cycle redirects, authoritative-htab writability and parser
consumption, the whole-string revert of three inert `androidboot.*`
fields, GhostLock trigger/consumer/fidelity, DTB blob validity, ODM write,
init-service root, and the module-driven switch to Permissive.

Offline only: static chain, disasm censuses, CRC/config arithmetic, H16
birth, the `bootm` Hush command census, the `himport_r` closure negative,
`fdt_chosen`'s second caller, the kernel cmdline source.

Not proven: exact `BUF`, source non-existence, `booti`/`go` absence beyond
one method, DTB Linux receipt, transport of a mutated cmdline to Linux,
H16 write, disclosure, reclaim, kernel R/W, GhostLock root, active RWX MMU
state.

Never executed: flash/erase/saveenv/setenv persistence, BootROM USB
burning, blind ioctls, fake object, kernel cred/root via GhostLock, any
`fdt` subcommand.

## Open problems

None of these block the current root or Permissive state.

1. BL31 secure-fused rejects unsigned images before the kernel runs.
2. No exact source, so no CRC-compatible kernel and no exact DTS source.
3. No disclosure primitive, so the GhostLock target/value cannot be forged.
4. The env marker dies inside `bootm`, past the htab and before or at
   `fdt_chosen`. `fdt_chosen` has never been executed by us; it is
   callable in-session via `fdt addr` + `fdt chosen`.

## Repository layout

| Path | Contents |
| --- | --- |
| `firmware/` | Stock `boot.img`, `bootloader.img`, `dt.img`, `dtbo.img`, `vbmeta.img`, plus `SHA256SUMS.txt`. `bootloader.img` and `dt.img` are encrypted. |
| `aquaman-config` | Kernel config extracted from the device (4,447 options). |
| `artifacts/` | DTB/DTS recovered from RAM and the `superbird` Amlogic user-key signature. |
| `reports/` | Dated investigation rounds and the three indexes above. |
| `reports/_archive/` | Reports whose conclusions were superseded or refuted. Do not cite as current. |
| `tools/` | Parsers, offline analysis, device probes, and the test suite. |
| `*.new.dat.br`, `*.transfer.list` | OTA sparse images for system, vendor, product, and odm. |
| `boot_unpack/`, `patched_unpack/`, `recovery_unpack/` | Unpacked stock, patched, and recovery boot images. |
| `.src/`, `build-aq/`, `out/` | Gitignored source trees, build output, and logs. |
| Top-level `*.img` | Scratch and test images. The stock set is in `firmware/`. |

## Quick start

Offline work needs Python 3 only. The suite has no network and no device:

```sh
python3 tools/run_tests.py
```

To rebuild and validate the approximation:

```sh
tools/build_aquaman_kernel.sh --clean
tools/validate_artifacts.py build-aq
```

The build needs `.src/linux-amlogic` at `3d4ab79e`, `.src/MiTV_OpenSource`
for the Linaro 6.3.1 toolchain, and `.src/u-boot-khadas` for BL33 work.
Those trees are gitignored. See `reports/_archive/kernel-build-env.md`.

## Device work

Device-side tools expect a device already in fastboot or a live U-Boot
RAM session. They are not a flashing procedure. Flashing boot/system/vendor/
vbmeta, erase, `saveenv` and BootROM USB burning were never executed here.
The only partition write performed was ODM, documented in its own report;
read it before running anything that writes.

## More reports

Topic entry points: `reports/provenance.md`,
`reports/fastboot-memory-flow.md`, `reports/bl33-same-cycle-round46.md`,
`reports/bl33-boot-decision-round44.md`,
`reports/ghostlock-reference-comparison-2026-10-01.md`,
`reports/repo-state.md`.

Common reopened leads, already closed: payload executed via `fastboot
boot`; download equals boot source; `BUF` is `0x10200000`;
`max-download-size` proves position; vermagic proves origin; 98% equals
reproduction; `env`-to-cmdline reaches Linux by any route tried. Full
list with evidence in `reports/INVALIDATED_HYPOTHESES.md`.

## Adding a round

- Read `CURRENT_STATE.md` first.
- Add a dated file under `reports/` instead of rewriting an old one.
- Record scope, evidence level, and the boot ID when the device was touched.
- Supersede, do not silently correct: note the old claim in `CURRENT_STATE`.
- Move files whose conclusions were superseded into `reports/_archive/` and
  update every reference to them.
- Keep negative results.

## FAQ

**Can I root my Mi TV Stick with this?**
Yes, persistently, by writing a modified ODM image with an init service that
starts a root shell on TCP 4444. It is not a GhostLock exploit and not a boot
bypass. See `reports/root-via-odm-2026-11-23.md`; restore stock ODM before
exposing the device to an untrusted network.

**Is SELinux still enforcing?**
No. The same ODM rc file loads a small kernel module that sets
`selinux_enforcing` to 0 in kernel mode. `setenforce` remains unavailable to
shell and to the root domain. Details and rollback:
`reports/selinux-permissive-via-module-2026-11-23.md`.

**Is the bootloader unlocked / can I flash a custom kernel?**
No. BL31 rejects unsigned images, and the rebuild is not ABI-compatible
with the stock modules. Root and Permissive SELinux do not change that.

**My device is another Amlogic box. Does this apply?**
No. Claims are scoped to aquaman PI.2055. Other trees are family
evidence, not target truth.

**Why keep so many failed reports?**
Because closed leads get reopened without them. Check
`INVALIDATED_HYPOTHESES.md` before proposing a theory. Files whose
conclusions were overturned live in `reports/_archive/` and must not be
cited as current.

Last consolidated: 2026-11-23. If this page and `reports/CURRENT_STATE.md`
disagree, `CURRENT_STATE.md` wins.
