# Aquaman PI.2055: kernel provenance and boot-chain research

Research on a Xiaomi Mi TV Stick 1080p (MiTV-AESP0, codename aquaman,
Amlogic S805Y/GXL), Android 9 PI.2055, stock kernel 4.9.113 built
2022-09-06 by jenkins@c5-mitv-cm-build06.bj.

Two questions drive the repo: which source tree built that kernel, and
what can still be executed on the device.

Short answer: the exact source has not been found. The closest public
tree rebuilds to a close but ABI-incompatible kernel, unsigned boot is
rejected before Linux starts, and no root or boot bypass has been
demonstrated.

This is not a ROM, a root guide, or a kernel release. It is a lab
notebook. Most reports record negative results on purpose, so closed
leads stay closed.

## Start here

Read in this order. Do not read `reports/` alphabetically.

1. `reports/CURRENT_STATE.md`: what is believed, at which evidence level,
   and what each claim supersedes. This file wins over every other page.
2. `reports/EVIDENCE_MATRIX.md`: evidence by subsystem.
3. `reports/INVALIDATED_HYPOTHESES.md`: closed leads. Check here before
   proposing a theory.
4. `reports/ROOT_FINAL_ANALYSIS.md`: the root boundary after rounds 48-58.

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
| Exact stock source? | Not found in searched public material. `McMCCRU/linux-amlogic` `3d4ab79e` is close family, not exact. This does not prove none exists. | `reports/provenance.md` |
| Can the kernel be rebuilt? | Only as an approximation: 98.1% of the expanded config matches, 190 CRCs differ, 13 symbols are missing. Not a reproduction. | `reports/rebuilt-kernel.md` |
| Can vendor modules be reused? | 28 `.ko` were extracted from the OTA. Presence is proven; loading is not. CRCs are the gate, not vermagic. | `reports/vendor-modules.md` |
| Can an unsigned kernel boot? | No on every RAM-only path tested. BL31 rejects it over SMC before Linux runs. No bypass demonstrated. | `reports/bl31-exact-round18.md` |
| Can U-Boot pass a modified cmdline? | Not demonstrated. Env writes reach the authoritative htab and `run storeargs` consumes them. Transport to the kernel cmdline is refuted for every form tried. | `reports/CURRENT_STATE.md` |
| Is the DTS available? | The DTB was recovered from RAM (58,280 B, valid). The original DTS source is still missing. A RAM blob is not proof Linux received it. | `reports/aquaman-dtb-extraction.md` |
| Where does fastboot write? | Download overlaps the region `bootm` reads (E5/E6). Exact `BUF` remains unknown. | `reports/fastboot-memory-flow.md` |
| Is there root? | No. GhostLock trigger and `FUTEX_LOCK_PI` consumer were reproduced, but there is no disclosure, reclaim, R/W, or root. | `reports/CURRENT_STATE.md` |

## Evidence boundary

Hardware-proven: E5/E6 overlap, E7 SMC reject, BL33 WRITE/FILL and
same-cycle redirects, authoritative-htab writability and parser
consumption, the whole-string revert of three inert `androidboot.*`
fields, GhostLock trigger/consumer/fidelity, DTB blob validity.

Offline only: static chain, disasm censuses, CRC/config arithmetic, H16
birth, the `bootm` Hush command census, the `himport_r` closure negative,
`fdt_chosen`'s second caller, the kernel cmdline source.

Not proven: exact `BUF`, source non-existence, `booti`/`go` absence beyond
one method, DTB Linux receipt, transport of a mutated cmdline to Linux,
H16 write, disclosure, reclaim, R/W/root, active RWX MMU state.

Never executed: flash/erase/saveenv/setenv persistence, BootROM USB
burning, blind ioctls, fake object, cred/root, any `fdt` subcommand.

## Open problems

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
Those trees are gitignored. See `reports/kernel-build-env.md`.

## Device work

Device-side tools expect a device already in fastboot or a live U-Boot
RAM session. They are not a flashing procedure. Flash, erase, `saveenv`,
and BootROM USB burning were never executed here. Read the corresponding
round report before running anything that writes.

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
- Keep negative results.

## FAQ

**Can I root my Mi TV Stick with this?**
No demonstrated path. GhostLock has a trigger and a consumer, not
disclosure or reclaim.

**Can I flash a custom kernel?**
No. BL31 rejects unsigned images, and the rebuild is not ABI-compatible
with the stock modules.

**My device is another Amlogic box. Does this apply?**
No. Claims are scoped to aquaman PI.2055. Other trees are family
evidence, not target truth.

**Why keep so many failed reports?**
Because closed leads get reopened without them. Check
`INVALIDATED_HYPOTHESES.md` before proposing a theory.

`reports/` preserves the full history. Old files carry SUPERSEDED banners
where they overstate; do not cite them as current.

Last consolidated: 2026-10-02. If this page and `reports/CURRENT_STATE.md`
disagree, `CURRENT_STATE.md` wins.
