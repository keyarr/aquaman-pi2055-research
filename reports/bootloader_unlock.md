Bootloader unlock: aquaman PI.2055

Device: Xiaomi Mi TV Stick 1080p, MiTV-AESP0, aquaman, S805Y/GXL.

Result

The following command does not unlock this firmware:

fastboot flashing unlock

It fails with:

FAILED (remote: 'missing partition name')

The following command returns OKAY but does not actually change the state:

fastboot oem unlock

This is a false positive from the vendor OEM handler.

The procedure that actually changed the state was:

fastboot oem setenv lock 10100000
fastboot oem saveenv

After setenv:

unlocked: yes
secure:   no

After saveenv, the state remained unlocked during a later bootloader check.

No userdata wipe was observed.

Observed lock values

Locked:

10101000

Unlocked:

10100000

The important empirical mapping is:

10101000 -> locked / secure
10100000 -> unlocked / secure=no
Why it works

The firmware behavior is consistent with the vendor fastboot OEM handler
passing the text after oem to the U-Boot command interpreter:

fastboot oem <command>
        |
        v
U-Boot OEM handler
        |
        v
run_command(<command>)

The handler returns OKAY unreliably, which explains why oem unlock appears
successful without changing the bootloader state.

oem setenv, however, has a real effect because it modifies the U-Boot
environment.

Current research state

> Note: the unlock is real. Android boot state went from green (locked) to
> orange (unlocked), confirming the flashing lock opened. `unlocked=yes /
> secure=no` reflects that U-Boot env / flash-lock state, not the eFuse.
> BL31 stays secure-fused and rejects unsigned via `aml_sec_boot_check` SMC.
> See `reports/fastboot-boot-verdict.md` (M1/M1b/M2 all rejected, 16-21 s)
> and `reports/fastboot-memory-flow.md` sec 6 (E7 same addr, signed passes,
> plaintext rejected). Do not use this file as proof of unsigned execution.

The device is currently:

unlocked: yes
secure:   no

This state opens the flashing lock (orange confirms it). It does not disable BL31
signature check and does not make `fastboot boot` execute unsigned payloads.

Scope

This procedure was observed on:

Android 9
PI.2055
U-Boot 2015.01-g7ac5df7677-dirty
U-Boot 0.4

Do not assume it applies unchanged to other revisions.

Also, unlocked=yes / secure=no does not establish that arbitrary images can
be permanently written to eMMC. Permanent flashing remains a separate
question.

Read-only verification
fastboot getvar unlocked
fastboot getvar secure
