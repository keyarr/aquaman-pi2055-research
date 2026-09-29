# fastboot-boot-verdict — payload never executes (M0 revoked, M1 failed)

> **The verdict on this page is CORRECT. The root cause was INCORRECT and is
> corrected below.** The payload never executed; this was confirmed across four
> independent experiments. However, the "download ≠ boot source" explanation
> does not hold: the `max-download-size` argument is mathematically void, and
> E5/E6 show that download and boot source overlap. The real cause is the
> **secure-fused BL31** rejecting images without an AMLSECU signature.
> See `reports/fastboot-memory-flow.md` for the complete flow.

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
~~is only 128 MB: `0x08000000`, incompatible with a buffer at `0x1080000`,
which would leave ~900 MB free), but `do_bootm_on_complete` boots from
`load_addr` (0x1080000 tradition, LOW). it's the Sept 2016 fastboot bug
(Chubb), never backported to this 2015.01 fork: download ≠ boot source.~~

**THIS ROOT CAUSE IS INCORRECT, IN TWO RESPECTS.**

**(a) The `max-download-size` argument is mathematically void.**
`ddr_size_usable` (f_fastboot.c:133-142) is
`DRAM - 16M - addr - 64M - 128M`. With 1 GiB:

| Assumed BUF | Implied max-download-size |
|---|---|
| 0x10200000 (khadas g_dnl.h:18) | 0x22E00000 (558 MiB) |
| 0x01080000 (loadaddr) | 0x31F80000 (799 MiB) |
| **Reported by device** | **0x08000000 (128 MiB)** |

The reported number matches neither candidate. Inverting yields
`BUF = 0x2B000000`, which is neither of the two. Thus, the value **does not
discriminate** between the hypotheses it cited. Reproduce with
`python3 tools/fastboot_addr.py`.

**(b) The conclusion "download ≠ boot source" was refuted at runtime.**
E5 vs E6 (see `reports/buffer-equals-loadaddr-proof.md`): `fastboot boot boot.img`
with download passes and boots; the identical `bootm` at the same address
**without** download fails instantly. Same Y, same `bootm`, the only variable
is whether bytes were downloaded. The download altered what `bootm` read, therefore
the two **overlap**. The Sept 2016 bug, if present in this tree, is inert here.

Family evidence was `CONFIG_USB_FASTBOOT_BUF_ADDR == CONFIG_SYS_LOAD_ADDR`
on ODROID-C2, but with `loadaddr=0x20000000` redirecting boot — which does not
apply here, because `loadaddr` is precisely what the download covers.

**H3 (the SMC) is the actual cause, previously labeled "live but disfavored".**
`aml_sec_boot_check` rejects everything without `AMLSECU!`. E7 confirms: signed and
plaintext at the **exact same** address, same rails, and only signed passes. E7b/E7c
yield identical timings. The gate is the SMC, acting before any format checks.
FIT with its own DTB (E1) eliminates theory H2, as noted earlier.

note: there's a chance boot is consuming a *stale* image (decrypted, from
the last normal boot, retained in DRAM after warm reboot) instead of zeroes
— indistinguishable by timing and irrelevant to the verdict: either way,
bytes via `fastboot boot` never enter the boot path. E6 confirms: without
download, `bootm` fails at the exact same instant.

## what would unlock it (outside current rules)

- read `loadaddr`/env (oem is a stub; no UART; env on eMMC needs root);
- `setenv`/`oem setenv` (explicitly banned, even though RAM-only without saveenv);
- UART (banned), flash (banned), testpoint/soldering (banned);
- ROM USB burning mode (`adb reboot update` + pyamlboot): NOT TESTED,
  risky (bulkcmd can wipe flash), out of scope for this session;
- exploit track (userspace/kernel) for root first and inspection from the
  inside: another project, not started.
