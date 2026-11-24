# Rounds 62-64: instrumentation of the bootm handoff - 2026-11-19

Status: **NO-GO. uid=0 not obtained.** Nothing here supersedes `CURRENT_STATE.md`,
`INVALIDATED_HYPOTHESES.md`, `v1-direct-kernel-boot-2026-11-19.md` or
`kernel-ram-patch-v2-2026-11-19.md`. New record, not yet indexed in
`MAP.md`.

Scope: RAM-only on the `1b8e:c003` gadget at stage 16. No flash, erase, saveenv,
persistent setenv, efuse, BootROM, `RUN_IN_ADDR`, `MODIFY`, power cycle, or blind
ioctl. Re-entries into optimus via `adb reboot fastboot` +
`fastboot oem update 5000`. All volatile state discarded by reboot. Scripts in
`/tmp/handoff/`; logs `run1.log`..`run8.log`.

## Question

V1/V2 stopped without knowing (a) which entry/FDT address the kernel receives
and (b) why the DTB and the patch in RAM were not consumed. This cycle tried to
measure the handoff instead of inventing another patch variant.

## Experiments performed

| # | Intercept | Intent | Result |
| - | --------- | -------- | --------- |
| 1 | `eret` 0x37e19264 -> stub | capture x0/x1/x2 at the transfer point | gadget crashed at 4.77 s; no readback |
| 2 | idem, stub at 0x37900000 | rule out USB buffer clobber | gadget crashed at 4.76 s; pre-bootm readback OK |
| 3 | `boot_jump_linux` 0x37e21328 -> stub with original return | capture before the eret | gadget crashed at 4.74 s |
| 4 | `cbz` 0x37e24cf8 -> stub saves x25/x20, returns to epilogue 0x37e25000 | capture `images` | **SURVIVED**. `bootm -> success`, kernel plaintext confirmed |
| 5 | `bl do_bootm_linux` 0x37e25f68 -> stub | capture arguments | gadget crashed |
| 6 | `ldrb w0,[x19,#0xe3]` 0x37e21308 -> stub | capture `images` at the arch decision point | gadget crashed |
| 7 | `cbz` -> stub writes `images+0x100/+0x108` (DTB 0x30000000) and continues boot | test whether bootm consumes an external FDT | boot occurred; `ro.boot.selinux=enforcing`, `su: not found` |
| 8 | `cbz` -> stub saves x25, reads bootm globals | find the real FDT pointer | survived; see below |

## Findings

1. **Only the intercept at the cbz has a safe abort.** All later points
   (0x37e25f68, 0x37e21308, 0x37e21328, 0x37e19264) crashed the gadget due to
   an unbalanced stack or because the abort there is unreachable. The pattern
   of returning to the epilogue 0x37e25000 is only valid within the do_bootm
   function itself, before `do_bootm_states`. This closes off the path of
   instrumenting the handoff without boot: there is no safe point between the
   cbz and the eret.

2. **The value saved as x25 at the cbz is not stable.** run4 returned
   `0x0000000037f60fd0`; run8 returned `0x0000000033e0a360`. Fields read in
   run4 (`arch=0x37`, `entry=0`, `ft_addr=0x37e27ba4`, `ft_len=0x37ec113e`)
    are pre-populated state, not the final values. So the injection in
   experiment 7 probably wrote to a structure that was not `images`, or to a
   discarded copy. This explains the failure without requiring a new kernel
   theory.

3. **Globals read at the cbz (run8):**
    ```
    0x37f72a90 = 0
    0x37f723d8 = 0
    0x37f723e0 = 0x159440
    0x37f723e8 = 0
    0x37f723f0 = 0
    ```
    None of them points to an FDT at that moment. The blob at `0x01000000` is
    valid (`d00dfeed`, 0xe3a8 B) but contains no `bootargs`, `selinux`, or
    `linux,initrd` - it is the pre-fixup blob described in `round57`. Therefore
    there is nowhere to inject a cmdline into it before `fdt_chosen`.

4. **Boot with an injected external DTB still ignores the DTB.** Experiment 7
   loaded a DTB with `androidboot.selinux=permissive` and `linux,initrd-*` at
   0x30000000, a Magisk ramdisk at 0x31000000, and pointed the fields via the
   stub. Result identical to V1/V2:
    ```
    adb shell su -c id            -> su: not found
    adb shell getprop ro.boot.selinux -> enforcing
    adb shell getenforce          -> Enforcing
    adb shell ls -l /sbin/su      -> No such file or directory
    BOOT_ID 0ad4ff89-38f6-4b16-a2bc-0b10d0861e7b
    ```

## Success criteria

None passed. UID 0 was not proven. `getenforce` remained Enforcing. There was
no magiskd, `/sbin/su`, or initramfs. The levels are HARDWARE_REPRODUCED for
the gadget crash at the late points, HARDWARE_OBSERVED for survival at the cbz,
and REFUTED for the strategy of injecting the FDT via `images`.

## Recommendation

Do not reopen handoff instrumentation without new static evidence predicting a
safe abort point after `do_bootm_states`. The open questions from V1/V2 remain
open and now with an additional constraint: measuring the handoff by
interception is unfeasible in this firmware. Reasonable next tracks, in order
of cost: (1) probe the unclassified cmds of SMC 0x820000ff
(0x10/0x14/0x20/0x80) with real GO and icache flush, always with the buffer in
NS RAM, to look for a BL31 read primitive; (2) CBC oracle at the gate, which
requires rejection cycles and has not been tested; (3) port of the BootROM
USBDL to S805Y, speculative and high risk.
