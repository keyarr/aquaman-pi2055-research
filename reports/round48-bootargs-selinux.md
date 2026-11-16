# E1 hardware run: env value byte -> kernel cmdline (round48, 2026-10-02)

## Objective

Decide on hardware whether one host-written byte range in the live BL33 `bootargs` value reaches Linux, using `androidboot.selinux` as the observable marker.

## Pre-conditions (already proven before this run)

- WRITE 0x01 writes arbitrary BL33 RAM bytes with readback and restore (round39/43/46).
- Live env hunted at `0x33e18000`, `bootargs` 832 B expanded cmdline (round46).
- `imgread kernel boot 0x1080000` + `bootm 0x1080000` boots stock Android (E4).
- `bootm` calls `env_get("bootargs")`, `fdt_chosen` writes it to `/chosen/bootargs` (offline, device image).
- `/proc/cmdline` denied for shell; oracle is `getprop ro.boot.selinux`.
- Baseline this session (stock Android, before any write): `ro.boot.selinux=enforcing`, `getenforce=Enforcing`.

## Session

- Entry: `adb reboot fastboot` -> `fastboot oem update 5000` -> `1b8e:c003`, `identify` stage 16 (TPL/BL33-u-boot), ver 0.7.
- Baseline bulkcmd oracle sane: `false`->`failed:`, `true`->`success`, `test 1 = 2`->`failed:`, `test 1 = 1`->`success`.
- Re-hunt this session: `mread 0x33e18000 0x8000`, sha256 `1c5e262d...` (same deterministic layout as round46).
- `bootargs` value @ `0x33e1d73f`, len 832. `initargs` @ `0x33e1e035` len 166. `storeargs` @ `0x33e1e75b` len 965. `storeboot` @ `0x33e1eb2b` len 621, tail `if imgread kernel ${boot_part} ${loadaddr}; then bootm ${loadaddr}; fi;run update;`. `loadaddr=1080000`, `boot_part=boot`, `EnableSelinux=enforcing`, `reboot_mode=fastboot`.
- Marker `androidboot.selinux=enforcing` at `bootargs`+210, abs `0x33e1d811`. Pre-bytes `...mode_android=normal `, post-bytes ` logo=osd1,loaded,0x3d8...`. Single `selinux` occurrence in the 832 B value. Live value also held `androidboot.reboot_mode=fastboot`.
- Pre-write confirm: 32 B live read = `androidboot.selinux=enforcing lo`, 16 B before intact, NUL at `0x33e1da7f` intact (`...rpmb_state=0\0bootcmd...`).
- WRITE 0x01: 9 B `permissiv` @ `0x33e1d825` (exactly over `enforcing`, same length, no other byte touched).
- Readback: `androidboot.selinux=permissiv lo`, 16 B before identical, tail/NUL identical. No restore needed; integrity verified, proceeded.
- `bulkcmd "imgread kernel boot 0x1080000"` -> `success`. `run storeboot` NOT used; `run update` unreachable by construction.
- `bulkcmd "bootm 0x1080000"` sent; USB dropped immediately (same signature as E4). No fallback executed.
- ADB returned ~30 s later as stock Android (`2717:4e40`, `26919800005844922`), normal boot, no intervention needed.

Artifacts: `reports/round48-bootargs-selinux/e1_hunt_33e18000_32k.bin`, `e1_mutate_boot.log`.

## Result (literal)

```text
getprop ro.boot.selinux   -> enforcing
getenforce                -> Enforcing
ro.boot.reboot_mode       -> normal   (env string we wrote said fastboot)
ro.boot.veritymode        -> enforcing
ro.boot.vbmeta.device_state -> unlocked / verifiedbootstate orange (unchanged)
```

`getprop | grep ro.boot` otherwise identical to the pre-run baseline except `reboot_mode: cold_boot -> normal`.

`boot.img` header cmdline (offline, `boot.img` root artifact) is `androidboot.dtbo_idx=0 otg_device=1 buildvariant=user`: no `selinux` there, so the image header is not the competing source.

## Conclusion

`REFUTED` for this mutation form (in-place edit of the expanded `bootargs` value + direct `imgread`/`bootm`).

The FDT cmdline Linux parsed was not our verified RAM string: two independent fields differ (`selinux` permissiv->enforcing, `reboot_mode` fastboot->normal). The boot path rebuilt/merged the cmdline from other sources (`EnableSelinux=enforcing` still in env covers the selinux field; the reboot_mode field was resolved to `normal` by the boot path, not copied from our string). `storeargs` was never invoked by us, so the rebuild happened inside the `imgread`/`bootm`/fixup path itself, not via the shell script we bypassed.

Not tested and still open: mutating the template side (`EnableSelinux` + `run storeargs`) instead of the expanded value. That is a different experiment, not a retry of this one.

## Root relevance

Host control of the live `bootargs` value bytes is still HARDWARE_REPRODUCED as a write; what failed is the transport assumption that this exact string is what `bootm` hands to the kernel on this path. Chain stays:

```text
bootargs control
  ->
Linux-visible control   REFUTED for direct-value poke; template-side path untested
  ->
?????
  ->
root
```

No root claimed. No uid/euid/capability change observed. RAM-only run: no flash, erase, saveenv, update, recovery, or persistent change of any kind; the poke died with the `bootm` reboot.
