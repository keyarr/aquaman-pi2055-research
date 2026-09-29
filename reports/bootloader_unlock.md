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

The device is currently:

unlocked: yes
secure:   no

This state is sufficient for the current RAM-only research path:

fastboot boot

A plaintext ARM64 payload without ANDROID! or AMLSECU! has already been
accepted and executed.

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
