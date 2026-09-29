# fastboot-boot-verdict — payload never executes (M0 revoked, M1 failed)

date: test session, 4 `fastboot boot` cycles, all RAM-only, device
always came back to Android on its own. no flash/erase/setenv/saveenv.

## experiments (adb poll 2-5 s, T0 = `fastboot boot` send time)

| # | payload | format | back-to-Android time | expected if it executed |
|---|---|---|---|---|
| M1a | 112 B stub + ~5-15 s delay + PSCI reset (`m1_boot.img`) | ANDROID! v0, kernel_addr 0x1080000, ARM64 magic ok | t+16~21 s | reject+delay: ~25-35 s |
| CTRL | 20 B stub with no magic (`plain_boot.img`, certain rejection) | ANDROID! v0 | t+15~20 s | — (rejection baseline) |
| M1b | same stub, 15× delay (`m1b_boot.img`) | ANDROID! v0 | t+18 s | ~80-140 s |
| M2 | real 4.9.113 kernel, 26 MB (`m2_kernel_boot.img`) | ANDROID! v0, magic ok | t+19 s | ≥30 s (boot+panic+reboot) |
| E1 | 15× delay stub + p241 DTB (`m1b_fit.itb`) | FIT (own DTB) | t+18 s | ~80-140 s |

bootreason after all of them: `reboot,fareboot` (identical to stock).

## verdict

**none of our bytes executed.** 15× delay with zero shift (M1b) and a real
kernel returning in normal-boot time (M2) are incompatible with execution.
the "CRITICAL FINDING" about the plaintext stub is revoked: reboot-to-Android
after a raw payload is the rejection outcome, not proof of execution.
M0 goes back to FALSE; M1 FAILED with evidence; M2-M6 via `fastboot boot`
blocked on this build.

## root cause (best explanation; H1 favored)

download goes to `CONFIG_USB_FASTBOOT_BUF_ADDR` (HIGH — `max-download-size`
is only 128 MB: `0x08000000`, incompatible with a buffer at `0x1080000`,
which would leave ~900 MB free), but `do_bootm_on_complete` boots from
`load_addr` (0x1080000 tradition, LOW). it's the Sept 2016 fastboot bug
(Chubb), never backported to this 2015.01 fork: download ≠ boot source.
family evidence: `CONFIG_USB_FASTBOOT_BUF_ADDR == CONFIG_SYS_LOAD_ADDR`
on ODROID-C2 (same SoC/vintage), but the env `loadaddr=0x20000000` diverts
the boot — same likely pattern here, with no read primitive to confirm
(oem is a stub: answers `AMLOGIC` to everything).

live but disfavored alternative (H3): `aml_sec_boot_check` on the `do_bootm`
path rejects everything without `AMLSECU!` even with `secure=no`. FIT with
its own DTB (E1) kills the "missing FDT in fastboot context" theory (H2):
even with an embedded DTB, nothing changes — so the cutoff is before or at
the read point, not at the DTB.

note: there's a chance boot is consuming a *stale* image (decrypted, from
the last normal boot, retained in DRAM after warm reboot) instead of zeroes
— indistinguishable by timing and irrelevant to the verdict: either way,
bytes via `fastboot boot` never enter the boot path.

## what would unlock it (outside current rules)

- read `loadaddr`/env (oem is a stub; no UART; env on eMMC needs root);
- `setenv`/`oem setenv` (explicitly banned, even though RAM-only without saveenv);
- UART (banned), flash (banned), testpoint/soldering (banned);
- ROM USB burning mode (`adb reboot update` + pyamlboot): NOT TESTED,
  risky (bulkcmd can wipe flash), out of scope for this session;
- exploit track (userspace/kernel) for root first and inspection from the
  inside: another project, not started.
