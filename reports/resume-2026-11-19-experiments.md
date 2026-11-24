# Offensive resumption 2026-11-19 - experiments and result

Status: **root NOT obtained**. Nothing here is persistent. No flash/erase/saveenv/
efuse/BootROM was touched. An SoC hang required a power cycle, performed
by the user with authorization.

## 1. Updated inventory

New artifact: `reports/PRIMITIVE_INVENTORY_CONSOLIDATED_2026-11-19.md`.

New primitive demonstrated in this resumption:

| # | Primitive | Evidence | Status |
| - | --------- | -------- | ------ |
| P15 | `0x11 WR_LARGE_MEM`: control OUT `0x40/0x11` with payload `<u32 addr><u32 len>`, data via bulk OUT EP `0x02`, no reply, no denylist and no 64 B ceiling | `/tmp/wr_large_mem_test.py`: `0x37800000` <- `ABCD`, readback `41424344`, restore to zero, oracle `failed:`/`success` intact | HARDWARE_REPRODUCED |

Implementation: `usb_pcd.c:632-650`, `dwc_otg_read_packet` directly at the host
address, with the comment `@todo Check for buffer overflow?`. Replaces `0x01`
for large payloads. Does not solve the kernel consumption link.

## 2. Experiments executed

| Exp | Hypothesis | Result | Conclusion |
| --- | --- | --- | --- |
| N1 | Do CPU and USB see the same RAM? | `0x10800100` written `DEADBEEFCAFEBABE`; CPU stub read `deadbeefcafebabe` | SAME_VIEW. Alias M3 ruled out. |
| E2b-lite | is the executed copy at one of the 6 known bases? | markers `4.9.AAAA`..`FFFF` at `base+0xd4008e`, with magic check `ARMd`; `/proc/version` stock | REFUTED. Fixes the offset bug of the old `marker_spray.S` (`+0x8e`). |
| E2b+ | base `/0x02100000` (text_offset) too? | tag G at `0x2e4008e`; `/proc/version` stock | REFUTED. |
| N2-lite | is the relocated FDT via global `0x37f72a90` the one delivered? | stub replaced `androidboot.*` with `androidboot.scan=DEADBEEF`; `getprop ro.boot.scan` empty | NO-GO. No useful output via DTB. |
| ELR override | force `eret` to patched `0x1080000`? | `msr elr_el2,x20` at `0x37e192a0` replaced by branch to stub; banner `4.9.XYZ!`; `/proc/version` stock | REFUTED. |
| pagetrace | `/proc/pagetrace` leaks text VA (`%16lx`) | `Permission denied` (DAC/SELinux) | REFUTED for uid=2000. |
| modprobe/core_pattern | writable sysctl -> usermodehelper root | `Permission denied` | REFUTED. |
| boot partition | does the local image kernel match the device's? | first 0x1200 and full 0x959000: identical SHA | SAME IMAGE. |
| recovery decrypt via SMC | recovery kernel banner | SMC hung the SoC; gadget left the bus; power cycle by the user | INCONCLUSIVE. Do not repeat without NOP of `bl 0x37e19310`. |
| imgread recovery | does `imgread kernel recovery` decrypt? | returns the same ciphertext as `read_raw_img` | DOES NOT decrypt. |
| 0x11 | see above | GO | new primitive P15. |
| SMC cmd 0x100 + NOP | stabilize the wrapper with NOP of `bl 0x37e19310` at `0x37e19ee8` and query cmd 0x100 | gadget hung, left the bus, second power cycle | REFUTED in this form. NOP does not stabilize; SMC command matrix is not a low-risk experiment on this firmware. |

## 3. New unexplained finding

The `linux_banner` of the decrypted Image is at `Image+0xd40080`:

```
Linux version 4.9.113-g963f962d046a-dirty (jenkins@...) ...
```

The device's `/proc/version` is:

```
Linux version 4.9.113 (jenkins@c5-mitv-cm-build06.bj) ... #1 SMP PREEMPT Tue Sep 6 12:53:43 CST 2022
```

Same builder, same date, only the `-g963f962d046a-dirty` suffix absent. With
`CONFIG_LOCALVERSION_AUTO=y` in the config, the local Image should produce the suffix.
The device's `boot` partition is byte-for-byte identical to `firmware/boot.img`.
Therefore, either the executed kernel comes from another source (BL31/TEE or `recovery`) or the
banner is rewritten somewhere. There is no evidence to decide. This is the
central link still unresolved.

**Update 2026-11-23 (`reports/root-read-surface-2026-11-23.md`):** with root,
the live dmesg boot banner is
`Linux version 4.9.113-g963f962d046a-dirty ...`, i.e. the executing kernel's
own log carries the same suffix as the decrypted Image. `/proc/version`,
`/proc/sys/kernel/version` and `uname -a` omit it. The mismatch is therefore
in the userspace-visible version string, not proof that a different Image is
running.

## 4. Chain map (updated)

| Chain | State | Missing link |
| ----- | ----- | ------------ |
| A: BL33 hook -> kernel patched -> uid=0 | REFUTED in all tested forms | identity/address of the executed copy |
| B: env -> cmdline -> root | REFUTED | `fdt chosen` inert; DTB is not an output channel |
| C: GhostLock -> R/W -> cred | OPEN, stalled at disclosure | no heap VA; pagetrace blocked |
| D: SMC/gate -> custom boot | NOT TESTED in a useful form | wrapper not repeatable; no Secure read |
| E: 0x11 + P3 (large payload) | PRIMITIVE AVAILABLE | same as A: image consumer |

## 5. Prioritized next steps (not executed)

1. Resolve the origin of the executed copy WITHOUT additional SMC calls: the
   `imgread`/`read_raw_img` route has already proven that the `boot` partition is identical to the local one,
   so comparing the two kernels offline is the next step. The SMC
   wrapper is unstable (2 hangs with the SoC leaving the bus); do not reopen
   it without a new hypothesis that does not depend on EL3.
2. If the source is identified and reachable by BL33, repeat chain A with the
   `commit_creds` trampoline already ready (`/tmp/v2/tramp_v2.bin`).
3. Leverage P15 (`0x11`) to load larger stubs in a single transfer,
   if item 2 needs code larger than what fits in 64 B.
4. GhostLock: still without an anchor. Only resume if a heap leak surface
   (not just text) accessible to uid=2000 appears. `/proc/pagetrace` and
   `/proc/sys/kernel/modprobe` are refuted by permissions.

## 6. Device state

Recovered by a power cycle performed by the user. Final state: Android
`2717:4e40`, adb online, uid=2000, Enforcing, stock kernel 4.9.113. No
persistent writes in any experiment.
