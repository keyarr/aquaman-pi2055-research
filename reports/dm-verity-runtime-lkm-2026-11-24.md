# Runtime dm-verity neutralisation from an LKM (2026-11-24)

Scope: MiTV-AESP0 (aquaman), Android 9 PI.2055, `4.9.113-g963f962d046a-dirty`,
32-bit userspace on arm64. One device, boot ID
`a87db071-9e8a-4815-8a77-4859611e4fbf`. Device work was read-only: `adb shell`
and `su -c` reads only. No module was built, loaded, flashed or unloaded; no
reboot; no write to `/system`, ODM, boot, vendor or vbmeta.

Status: HARDWARE_REPRODUCED for the live measurements below, OFFLINE_ONLY for
the ELF/disassembly work. This report does not change any closed conclusion in
`CURRENT_STATE.md`: BL31 still rejects unsigned images, there is no exact
kernel source, and the U-Boot env/cmdline route stays refuted. Nothing here
touches boot, vbmeta or the cmdline.

## Live state measured in this boot

| Measurement | Result |
| --- | --- |
| `su -c id` | `uid=0(root) ... context=u:r:su:s0` |
| `/proc/modules` | `kernelsu` Live; no `seflip` |
| `getenforce` / `/sys/fs/selinux/enforce` | `Permissive` / `0`, from shell and from root |
| dmesg | `SELinux: Starting in permissive mode` at 0.000718 |
| `/proc/cmdline` | contains `androidboot.selinux=enforcing`, `ro`, `dm="1 vroot none ro 1,0 2926608 verity ... restart_on_corruption ... use_fec_from_device /dev/mmcblk0p18 ..."`, `root=/dev/dm-0` |
| `/proc/mounts` | `/dev/root / ext4 ro,...`; `/dev/block/dm-1 /vendor ext4 ro,...`; no separate `/system` |
| `/sys/devices/virtual/block/dm-{0,1}/ro` | `1` / `1` |
| `/dev/mapper/control`, `/dev/dm-*`, `/dev/root` | absent |
| `/proc/kallsyms` | 148586 lines, readable, all addresses `0000000000000000` (`/proc/sys/kernel/kptr_restrict=2`) |
| dmesg at 342.7 s | `EXT4-fs (dm-0): re-mounted. Opts: block_validity,delalloc,barrier,user_xattr,acl` (root still mounted ro) |

The live Permissive state differs from the Enforcing state recorded in
`reports/kernelsu-persist-2026-11-24.md`. It is reported here as a fact of this
boot only; this report does not supersede or amend that document. The earlier
remount line in dmesg is consistent with the already-known failed
`mount -o remount,rw /` attempt and left the mount ro.

Because kallsyms hides addresses from userspace, runtime resolution from a
module must use the exported `kallsyms_lookup_name` (CRC `e007de41`) or exported
DM entry points. Hardcoded KASLR offsets are unnecessary; `N=0` stays
inferred, not read live.

## Stock symbol inventory (synthetic ELF)

Source: `work/ksu-lkm-fix/stock_vmlinux.elf` (built by the same flow used for
the KernelSU module), crossed with `work/ksu-lkm-fix/kernel-obj/Module.symvers`
from `make_symvers.py`. The `Module.symvers` license column is hardcoded to
`EXPORT_SYMBOL` by that script; the CRCs are the useful part. `build-aq/System.map`
was not used.

There is no `verity_verify_bio`, `verity_verify_page` or `dm_verity_verify_*`
symbol in this vendor kernel. The 4.9 verification path here is
`verity_work` with `verity_verify_io` inlined into it, plus
`verity_verify_level`, `verity_hash_for_block`, `verity_for_bv_block`,
`verity_hash_final.isra.4`, `verity_fec_decode` and `verity_handle_err`.

| Symbol | Stock VA | Kind | Exported | CRC / note |
| --- | --- | --- | --- | --- |
| `verity_work` | `ffffff800979e5e0` | LOCAL func | no | full verifier, inlined |
| `verity_handle_err` | `ffffff800979cb78` | LOCAL func | no | 2 callers, no mid-function branches |
| `verity_hash_for_block` | `ffffff800979e288` | GLOBAL func | no | called from `verity_work` |
| `verity_for_bv_block` | `ffffff800979e3c8` | GLOBAL func | no | |
| `verity_hash_init` | `ffffff800979ca78` | LOCAL func | no | |
| `verity_hash_final.isra.4` | `ffffff800979d608` | LOCAL func | no | |
| `verity_finish_io` | `ffffff800979cd30` | LOCAL func | no | completes the bio |
| `verity_end_io` | `ffffff800979cd88` | LOCAL func | no | queues `verity_work` |
| `verity_verify_level` | `ffffff800979d7e0` | LOCAL func | no | metadata path |
| `verity_fec_decode` | `ffffff800979b988` | GLOBAL func | no | |
| `dm_verity_avb_error_handler` | `ffffff800979c920` | GLOBAL func | no | called only on restart path |
| `verity_map` | `ffffff800979d430` | GLOBAL func | yes | `382998bc`; rejects WRITE |
| `verity_ctr` / `verity_dtr` | `ffffff800979d978` / `ffffff800979d388` | GLOBAL func | yes | `06b34bff` / `fb2c16ba` |
| `verity_status` / `verity_io_hints` | `ffffff800979cf50` / `ffffff800979d318` | GLOBAL func | yes | `57b074d4` / `5911f8e6` |
| `verity_iterate_devices` / `verity_prepare_ioctl` | `ffffff800979ca28` / `ffffff800979c9b8` | GLOBAL func | yes | `d276136c` / `d958011c` |
| `verity_target` / `android_verity_target` | `ffffff800a8d9b10` / `ffffff800a8d9bf8` | LOCAL object | no | target_type structs |
| `dm_get_md` / `dm_put` | `ffffff8009788ad0` / `ffffff8009785748` | GLOBAL func | yes | `20b60493` / `1b027189` |
| `dm_disk` / `dm_table_get_md` / `dm_table_get_mode` | `ffffff8009785788` / `ffffff80097899c0` / `ffffff8009789958` | GLOBAL func | yes | `a16238e3` / `61a9e496` / `6d0f1f89` |
| `set_disk_ro` | `ffffff8009430b70` | GLOBAL func | yes | `a2efcb6a` |
| `kallsyms_lookup_name` | `ffffff8009145e68` | GLOBAL func | yes | `e007de41` |
| `aarch64_insn_patch_text` | `ffffff800908e3f0` | GLOBAL func | no | resolve via kallsyms |
| `kernel_restart` | `ffffff80090cdc70` | GLOBAL func | yes | `1e7bbcb3` |
| `dm_swap_table` | `ffffff8009788c98` | GLOBAL func | no | no `__ksymtab` |
| `dm_table_load` | absent | - | - | not a symbol in this build |

Only the seven `verity_*` target_ops methods are exported. The verification
itself is `LOCAL`/non-exported, so a module cannot link against it directly.

Struct offsets, derived from stock disassembly (not from the approximate
source tree):

- `struct dm_verity`: `hash_failed` `0x80`, `mode` `0x84`, `corrupted_errs`
  `0x88`, `verify_wq` `0x90`, `fec` `0x290`, `validated_blocks` `0x298`.
  `verity_work` reads `mode` via `[x26,#0x84]` only in `verity_handle_err`;
  `mode` values are 0 = EIO, 1 = LOGGING, 2 = RESTART.
- `struct mapped_device`: `map` `0x28` (`dm_get_live_table` loads `[x19,#0x28]`),
  `flags` `0x68`, `disk` `0xc0` (`dm_disk` loads `[x19,#0xc0]`).
- `struct dm_table`: `num_targets` `0xd0`, `targets` `0xe0`, `mode` `0xf4`,
  `sizeof(struct dm_target) == 0x58`.
- `struct dm_target`: `private` `0x40` (`verity_map` loads `[x21,#0x40]`).

## Feasible hook points

1. **Data-only, preferred.** `dm_get_md(MKDEV(253,0))` is exported. From the
   returned `md`, read `md->map` (`0x28`), then
   `table->targets[0].private` (`0xe0` + `0x40`) to get the live `struct
   dm_verity` of dm-0. Write `1` (LOGGING) to `v->mode` at `0x84`; call `dm_put`.
   This makes every verification failure return 0 in `verity_handle_err`
   (`ldr w0,[x19,#0x84]; cmp w0,#1; b.eq return_0`), both for data and metadata
   blocks. `restart_on_corruption` and the resulting `dm_verity_avb_error_handler`
   + `kernel_restart("dm-verity device corrupted")` are never reached. FEC is
   still attempted first, and `hash_failed`, `corrupted_errs`, DMERR and the
   uevent are still produced, so corruption remains visible. This needs no text
   patch, no kallsyms lookup for static symbols, and can be applied to dm-0
   only, leaving `/vendor` (dm-1) verified. `mode` lives in a kmalloc'd object,
   so a reboot restores `2` from the cmdline.

2. **Text patch, fallback.** Resolve `verity_handle_err` by name, save its
   first 8 bytes (`fd 7b b8 a9 fd 03 00 91`) and patch them to
   `mov w0,#0; ret` (`00 00 80 52 c0 03 5f d6`) with
   `aarch64_insn_patch_text`. The function has exactly two callers
   (`ffffff800979d968` in `verity_verify_level`, `ffffff800979e8ac` in
   `verity_work`) and no branch into its interior. At `verity_work+0x2cc` a
   zero return makes the code continue instead of calling `verity_finish_io`
   with `-EIO`. Simpler to implement if the module is already using the
   KernelSU trampoline machinery, but it affects dm-0 and dm-1 together,
   masks all failures including genuine hash-device I/O errors, and suppresses
   `hash_failed`/logging. Restore the saved bytes on module exit.

3. **Instrumentation only.** With route 1, read `v->mode`, `v->hash_failed`,
   `v->corrupted_errs` at init and after a read workload, and log them. No
   kernel memory is written at all. This is the cheapest first test.

4. **Rejected.** Replacing the verity target with a linear target through
   `dm_swap_table`/`dm_table_load` is not a minimal route: `dm_swap_table` is
   not exported, `dm_table_load` is not a symbol, `/dev/mapper/control` does not
   exist, and swapping the live table of the mounted root is destructive. It
   also does not remove the disk `ro` flag by itself. Rebuilding the kernel and
   changing the cmdline remain closed by the existing conclusions.

## What neutralising verification does NOT do

`ro` is enforced in three independent places:

- the gendisk policy set by early boot from the `ro` field of the `dm=` cmdline
  (`set_disk_ro(dm_disk(md), 1)` in `init/do_mounts_dm.c`), which is what makes
  `bdev_read_only()` and `mount -o remount,rw` fail;
- the live table mode (`dm_table.mode` at `0xf4`, currently `FMODE_READ`), set
  from the same `ro` field;
- `verity_map` rejecting any WRITE with `-EIO` (`cbnz w0, ...` at
  `ffffff800979d4c0`), and `data_dev` having been opened with `FMODE_READ` only
  in `verity_ctr`.

Route 1 or 2 only removes integrity enforcement and the reboot-on-corruption
behaviour. The root stays mounted ro until all three items above are handled.
Clearing `set_disk_ro(dm_disk(md), 0)` alone is not enough.

## Risks

- No integrity guarantee for `/` and, if route 2 is used, `/vendor`. Corrupted
  or modified blocks are read as valid data. On an unmodified stock filesystem
  this should be inert, but a genuinely bad block could reach ext4.
- `restart_on_corruption` is neutralised; that is the intended effect and also
  the main hazard.
- A text patch on shared code affects both verity devices and must be exactly
  reverted on module exit. The data patch on dm-0 only does not.
- Pixel-level side effects: `ro.boot.veritymode` stays `enforcing` (read-only
  property); dm status may report logging instead of restart.
- The live Permissive SELinux state in this boot means an AVC-based detector is
  weaker than the Enforcing state described in the current-state documents.
- `rmmod` alone does not restore `mode`; the module exit path must write back
  the saved value, or a reboot restores it from the cmdline.

## Minimal test plan (NOT EXECUTED)

Phase 0 - instrument, no kernel write:

1. Build an LKM against `work/ksu-lkm-fix/kernel-obj/Module.symvers`, using
   only `dm_get_md`/`dm_put` imports (CRCs above). Module init logs, for
   `MKDEV(253,0)` and `MKDEV(253,1)`: resolved pointers, `mode`, `hash_failed`,
   `corrupted_errs`. It performs no writes and no patches.
2. Load and inspect:

   ```sh
   adb shell 'su -c "insmod /odm/dmverity_probe.ko"'
   adb shell 'su -c "dmesg | grep dmverity_probe"'
   adb shell 'su -c "cat /sys/devices/virtual/block/dm-0/ro /sys/devices/virtual/block/dm-1/ro"'
   ```

   Success: both targets report `mode=2`, `hash_failed=0`, `corrupted_errs=0`;
   both `ro` values stay `1`; no Oops, no reboot, enforce state unchanged.
   Failure: any nonzero counter or an unresolved symbol stops the test.

Phase 1 - neutralise dm-0 only, still no write to `/system`:

1. Same module with `WRITE_MODE=1`; it saves `mode` before writing `1` to
   dm-0's `v->mode` and restores it in module exit.
2. Load, then read only:

   ```sh
   adb shell 'su -c "insmod /odm/dmverity_nochk.ko"'
   adb shell 'su -c "dmesg | tail -80"'
   adb shell 'su -c "cat /sys/devices/virtual/block/dm-0/ro; grep \" / \" /proc/mounts"'
   ```

   Success: `mode=1` for dm-0, `mode=2` for dm-1; root still `ro`; `/` still
   readable; no `EXT4-fs error`, no `dm-verity device corrupted`, no restart,
   no Oops. Read a few known files twice and compare hashes to confirm the
   data path still works.
3. Rollback:

   ```sh
   adb shell 'su -c "rmmod dmverity_nochk"'
   ```

   Then re-run phase 0 and confirm `mode=2` again. A reboot also restores it.
   If the module cannot be unloaded, reflash stock ODM per
   `reports/kernelsu-persist-2026-11-24.md`; do not flash boot/system/vendor/
   vbmeta.

Phase 2 - only after phase 1 is clean:

Clearing the ro flag and allowing writes needs `set_disk_ro(dm_disk(md0), 0)`,
a writable table mode / reopened data device, and patching the WRITE rejection
in `verity_map`. That design is not validated here and is not part of this
report's test plan. Do not attempt `mount -o remount,rw /` until it is.
