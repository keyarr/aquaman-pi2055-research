# CURRENT_STATE - single source of truth (2026-11-24)

Read this first. It is the epistemological index. History is preserved in
individual reports; this file states what is currently believed and why.
Statuses only: PROVEN, HARDWARE_REPRODUCED, HARDWARE_OBSERVED, OFFLINE_ONLY,
PROBABLE, INCONCLUSIVE, REFUTED, SUPERSEDED. CONFIRMED is not used.

## R1 kexec via module (2026-11-23)

PENDING: no custom kernel booted. The LKM trampoline completes and the new
kernel's `stext` executes, but boot hangs at `__enable_mmu`, at the `msr sctlr_el1`
that enables the MMU; watchdog after ~50 s, no panic. Addresses and KASLR alignment
were checked and are correct. Details, ruled-out items and next step:
`reports/r1-kexec-pending-2026-11-23.md`.

HARDWARE_OBSERVED (2026-11-26): the "hang at `msr sctlr_el1`" reading is refuted.
Static address audit shows the next instruction after that `msr`/`isb` was
`R1_MARKV 0x5261`, a store to `0xffffff8007501000`. That VA is in the module
region (`VA_START + 0x7501000`, below `KIMAGE_VADDR`), not the linear map; its
PMD entry in `swapper_pg_dir` is zero before `paging_init`, so the store raises a
synchronous data abort. The same defect applies to `R1_MARKV 0x525f`, and
`r1_mark(0x5252)` at the top of `start_kernel` writes the linear-map VA
`0xffffffc007501000`, whose PGD entry is also still zero. The instrumented
source now has those three writes removed; the physical (`R1_MARKP`) crumbs and
the `r1_mark` calls after `setup_arch` are unchanged. Hardware run: with safe
crumbs the new kernel reached `start_kernel` and the `setup_arch` failure
branch, so the marker-fault claim is REFUTED. The DTB was being zeroed by
BSS clearing before `setup_machine_fdt`; the module now places it using the
Image header `image_size`. A boot to userspace was NOT observed. No exception
registers were captured. The device went off USB after one fire and came back
after a power cycle. `reports/r1-kexec-2026-11-26.md`.

HARDWARE_OBSERVED (2026-11-26, second round): with the DTB staging fix the new
kernel parses the FDT (`0x5283`), reaches `console_init` (`0x5254`) and
`rest_init` (`0x529c`), then stops inside `copy_process` just before
`dup_task_struct` (`0x52a9` seen, `0x52aa` absent). The first `kernel_thread`
never returns, so PID 1 is not created and userspace is not reached. Handoff
slots recorded `dt_phys=0x2c85f000`, `dtb_magic=0xd00dfeed`, `CurrentEL=1`,
`MPIDR=0x80000001`, `online_cpus=1`; Pstore stayed empty, so no panic was
observed. Persistent crumbs `0x07501000` and `0x075f0000..0x075fffff` survive
the watchdog reset; `0x2ac02000`/`0x2ac03000` do not and were rejected.
All diagnostic kernel edits were reverted and the clean Image rebuilt
(`a79349f84252a1f0eb1c94d920e54765bd04de1ca284173107ba3a7eed8255bb`). Module
`bdceba1420456040cff846efc104150e1ab2b228bf2945adde7d4eb7afc75ec0`, DTB
`35985354cf57ece3be678ca99666094921bcc2ffcc6f9e937a447edecb305f2d`. Details
and negative result in `reports/r1-kexec-2026-11-26.md`.

HARDWARE_OBSERVED (2026-11-26, third round): with per-round crumb sentinels,
the new kernel was traced through `rest_init`, `copy_process` (including a
successful `dup_task_struct` and all copy_* steps), `kernel_init`,
`kernel_init_freeable`, `free_initmem`, `run_init_process`, `do_execve` and
`getname_kernel`. The last markers were `0x5409` (run_init_process entry),
`0x5410` (do_execve entry) and `0x5420` (getname_kernel entry); no execve
return marker and no userspace were observed. Instrumentation in the SLUB hot
path after `free_initmem` shifted the frontier between rounds, so the exact
execve fault is INCONCLUSIVE. All instrumentation was removed and a clean
Image was rebuilt (`09e0016f360b87026ed612b83807eca9aaa48c17a67f799b7f436162c0b13978`).
One fire of that clean Image dropped USB and the device did not re-enumerate
after more than six minutes, so the stop condition was reached and hardware
work stopped. No new banner, no `r1probe=DEADBEEF`, no zygote and no pstore
panic. Module and DTB unchanged. See `reports/r1-kexec-2026-11-26.md`.

HARDWARE_OBSERVED (2026-11-26, fourth round): after a power cycle, sparse
single-write crumbs showed that `dm_run_setup()`, `mount_root()` and
`prepare_namespace()` all enter and return, so root mount is REFUTED as the
failure point. An initrd round with a 391-byte static AArch64 `/init` that
exits 42 bypassed dm-verity entirely and still hung in execve, so block I/O
on the init binary is also REFUTED. Execve markers reached
`do_execveat_common`, `load_elf_binary`, `exec_binprm`, `flush_old_exec` and
`setup_arg_pages`; no execve return marker and no panic appeared in any round.
Adding three more writes moved the frontier past `setup_arg_pages`, so the
exact stop inside execve is INCONCLUSIVE. `norandmaps` did not change it.
All instrumentation was removed and the clean Image rebuilt
(`479e879556811d4002aeab1cd4f462635a1e9c7e641637dffb96a087681b5d74`;
the hash differs from the earlier clean build only by the `UTS_VERSION`
build timestamp). Two P1 fixes were retained in `work/r1-kexec/`:
`r1_fdt_fixup_initrd()` now re-aligns the FDT struct block after node names
and checks offsets, and `patch_dtb.sh` emits 8-byte initrd properties.
Final module `5d228d18cfc1c8e799a339fb52f5aee1f5cea8961627110dc0f438cd6656917b`,
DTB unchanged at `35985354cf57ece3be678ca99666094921bcc2ffcc6f9e937a447edecb305f2d`.
Final clean fire returned to stock after about 123 s with no new banner, no
`r1probe`, no zygote and a corrupted crumb region, so the stop condition was
not reached again but no further fire was attempted. No flash or persistent
write; no commit or push. See `reports/r1-kexec-2026-11-26.md`.

HARDWARE_OBSERVED (2026-11-26, fifth round): the CMA-overlap hypothesis is
REFUTED offline. `linux,codec_mm_cma` in the DTB is 208 MiB with no `reg` and
no `alloc-ranges`, so its base is chosen at boot, not fixed at `0x2ac00000`.
`arm64_memblock_init()` reserves the new kernel at
`__pa_symbol(_text) = 0x2ac80000` before `early_init_fdt_scan_reserved_mem()`
and `dma_contiguous_reserve()`, so its CMA cannot cover the image. The module
places `text_off & (2M-1)` so the KASLR offset is 0; the self-reservation is
correct. No DTB change was made. A directed module change now pins the CPU
and masks IRQs across the per-CPU TTBR0/idmap swap
(`preempt_disable()`/`local_irq_disable()` before `r1_install_idmap()`, with
matching enable on the error path); module
`936aa4b7d0ac987dcb6104f726c2075b4e428612e2c49e90497a0bbf80bd0eae`.
Three fires with unique sentinels produced no userspace. The second fire used
an `__init` marker in `run_init_process` after `free_initmem` and faulted at
`r1_mark+0x0` (`ffffff800a3a0414`, `*pte=0`, `x0=0x5256`), panicking with
"Attempted to kill init"; that instrumentation is invalid for the execve
frontier. It did give the first fully readable new-kernel pstore log, which
PROVES the new kernel mounts root (`VFS: Mounted root (ext4 filesystem)
readonly on device 251:0`), mounts devtmpfs and reaches `Freeing unused
kernel memory: 5248K`. The third fire used a non-init inline marker but
returned only after about 290 s with a cold boot, empty pstore and a
corrupted crumb (`0x07501000=4631`); no conclusion. All instrumentation was
removed and the clean Image rebuilt
(`b099af09350a6c849907cd1f02c587af4f6c3633495df742908bf9709983d43f`, not
fired). Userspace is still NOT reached; the exact execve stop remains
INCONCLUSIVE, with no SLUB/execve-internal instrumentation this round. No
flash or persistent write, no commit or push. Risks: the last fire took about
290 s to restore USB, so the stop condition is close; a readable pstore log
appears only when the new kernel panics, not on a clean hang. Details in
`reports/r1-kexec-2026-11-26.md`.

HARDWARE_OBSERVED (2026-11-26, sixth round): the execve frontier was resolved
from the userspace side. With no kernel instrumentation, only the DTB cmdline
was changed (`loglevel=8 ignore_loglevel ramoops.console_size=0x20000`,
`r1probe=DEADBEEF` and the rest kept) and the clean Image was fired with
`cma_phys=0x2ac00000`: the device returned to stock in about 17 s with empty
pstore and crumb `0x5260`, no new banner. A static libc-free AArch64 `/init`
in a 646-byte initrd then wrote a unique marker and called `reboot` by raw
`svc`, falling back to `exit(42)`. With DTB
`733d20f53bf5b4b18781633a9b7cfc360666c43f6c372b933775c39af940e41c` the new
kernel panicked at 5.999 s with `Attempted to kill init!
exitcode=0x00002a00`, `CPU: 2 PID: 1 Comm: init Tainted: G S 4.9.113 #63`,
trace through `el0_svc_naked`, plus `Freeing unused kernel memory: 5248K`.
pstore had `console-ramoops-0` and `dmesg-ramoops-0`. This PROVES execve
succeeded and userspace ran in EL0; the probe's reboot call failed, so exit
42 supplied the evidence. Full Android userspace on the new kernel remains
NOT SHOWN, and the same-boot `r1probe` / new-banner / zygote checks were not
possible. A final no-initrd fire (rc=255) did not restore USB: serial
`26919800005844922` disappeared and only an unrelated network adb device
`192.168.0.6:5555` (9520, 3.18.79 armv7l) is visible. The stop condition is
met and hardware work stopped; nothing was flashed. Instrumentation is still
absent and clean rebuilds reproduced Image
`b099af09350a6c849907cd1f02c587af4f6c3633495df742908bf9709983d43f` and
module `936aa4b7d0ac987dcb6104f726c2075b4e428612e2c49e90497a0bbf80bd0eae`.
No commit or push. See `reports/r1-kexec-2026-11-26.md`.

HARDWARE_OBSERVED (2026-11-26, seventh round): a source audit found residual
diagnostic crumbs in `.src/linux-amlogic` despite earlier reports claiming
removal (`R1_MARKP` 0x5251-0x5260 in `head.S`, `r1_mark` 0x5253/0x5254/0x5255
in `init/main.c`). All seven modified files were reverted and a genuinely
clean Image rebuilt as
`6c30b16ee7bdc99d62c08c86ef5c2212b736e7e6dab7bfaa1b1033e86e8ca045`; module
unchanged at `936aa4b7d0ac987dcb6104f726c2075b4e428612e2c49e90497a0bbf80bd0eae`.
Twelve fires were made; the first eleven restored USB in 41-70 s and Android
booted stock after each. Static userspace probes on the stock kernel showed
that `fork` (1079) and `mkdir` (1030) return ENOSYS on this arm64, while
`clone` (220), `mkdirat` (34), `execve` (221) and `mount` (40) work; the old
probe had used 104 instead of 142 for `reboot`. With a clone-based initrd
wrapper, a 32-bit userspace exec on the new kernel is PROVEN: magiskinit ran
as PID 1 and logged its layout probes before exiting 1. A root-mounting
wrapper then mounted `mmcblk0p18` at 9.297878 s and exec'd the real Android
init; PID 1 died at 9.313293 s with `synchronous external abort (0x82000010)
at 0x0000000000049104` and panic `Attempted to kill init!
exitcode=0x00000007` (SIGBUS). Full Android on the new kernel remains NOT
SHOWN: no new banner, no `r1probe`, no zygote and no root shell from the new
kernel. The final fire used the stock cmdline without verbose logging and no
initrd; the serial did not return after 300 s and `lsusb` shows no Amlogic
device, so the stop condition is MET and hardware work stopped. Nothing was
flashed; no commit or push. See `reports/r1-kexec-2026-11-26.md`.
HARDWARE_BLOCKED (2026-11-26, eighth round): after a user power cycle the
serial was back and the staged Image/module/DTB hashes matched. Static
analysis of fire 11 recovered the full console record locally and extracted
the real `/init` from `mmcblk0p18` with `dd` plus `debugfs`: ELF32 ARM,
1501480 B, `.text` `0x8160`-`0x132494`, and the fault address `0x49104` is
a valid Thumb function prologue inside that text. ESR `0x82000010` is EC
`0x20` (EL0 instruction abort) with FSC `0x10` (external abort, no
translation-table walk), so translation succeeded and the instruction fetch
itself got an external response. This makes a userspace page-table or
memory-attribute defect the best-fitting hypothesis; the direct ext4 mount
is weaker, and the missing `/dev`/`/proc`/`/sys` chroot is refuted as the
direct cause because that would be a data abort. A minimal static ARM EABI
`/init` with no clone, mount or chroot was built as a 456 B initrd
(`c15eeb16209d7b6aa78086f47b495d359a376dc901fdb014bbae68e5c17e9e14`) to
isolate 32-bit compat execution. One fire with the clean Image and console
initrd DTB returned rc=255 but the serial and USB never came back in 195 s;
no pstore was readable and no second fire was attempted. The 32-bit compat
question and full Android boot remain NOT SHOWN; stock decrypted and custom
image checks were not run. No flash, commit or push.
See `reports/r1-kexec-2026-11-26.md`.

HARDWARE_OBSERVED / OFFLINE_ONLY (2026-11-27): after a user power cycle the
serial `26919800005844922` is back and the read-only baseline is stock
`4.9.113 #1`, uid 0 in `u:r:su:s0`, Enforcing, `sys.boot_completed=1`, empty
pstore. The clean Image `6c30b16e...` (27,308,544 B) is still staged on the
device but has no host copy; the host `build-aq/Image` is `d1406478...`
(22,493,696 B), built with 36 tracing options removed and five diagnostic
kernel files still modified, so it is not comparable with rounds 7/8. Work
done after the eighth report and not reported there is consolidated in
`reports/r1-kexec-2026-11-27.md`: the secmon reservation fix in
`patch_dtb.sh` plus two unreported DTBs (`56e286c3...`, `3f50b0cd...`), the
pivot-root initrds (`630027e8...` is the valid candidate), and a diagnostic
build that captures ESR/FAR/PC/TTBR0/TCR/MAIR/PTE at `0x075fb100` on the next
EL0 IABT. The secmon hypothesis is plausible but UNPROVEN (no evidence ties
user VA `0x49104` to PFN `0x5307`); the pivot_root rationale is speculative
and lower priority; the compat32 initrd `c15eeb16...` remains the cheapest
test separating compat page tables from the mount/chroot path. Full Android
on the kexec'd kernel is still NOT SHOWN. The clean Image was recovered to
`out/r1-device/Image.clean`; a tracing-on instrumented rebuild
(`c9b4220d...`, module `202cbd51...`) is ready for PTE capture but is not
byte-identical to the round 7/8 Image. Offline fire packages are staged in
`out/r1-prep/{secmon,compat,usbdl}/`; none was executed. No fire, flash,
USB DL write or commit in this consolidation.

HARDWARE_OBSERVED (2026-11-27, after consolidation): with the instrumented
Image `c9b4220d...` the new kernel `#73` booted from R1 all the way to
userspace and system_server, but `sys.boot_completed` stayed empty because
`StartHdmiControlService` was blocked by a CEC HAL crash-loop (`-22` opening
the CEC device). The same Image over USB DL reproduced the identical hang, so
R1, the DTB and the handoff are excluded as the cause; the blocker is the
kernel build and its ABI with vendor modules, which the close-family source
cannot fix. A first timeout-wrapper fire produced no IABT and no valid PTE
capture, so the original SIGBUS cause stays INCONCLUSIVE. No power cycle was
needed; the device is back on stock `#1` with root. See
`reports/r1-kexec-2026-11-27.md`.

## Root via ODM (2026-11-23)

This supersedes every "no root" statement below. Root is persistent and was
obtained without a boot-chain or SMC bypass, without kernel exploitation, and
without touching boot, system, vendor or vbmeta. The final 2026-11-24 image
keeps the ODM load route but replaces the TCP 4444 listener and `seflip` with
the KernelSU LKM described at the end of this file.

| Claim | Status | Evidence | Scope | Supersedes |
| ----- | ------ | -------- | ----- | ---------- |
| ODM is writable from fastboot via `set_active:;store write odm 10200000 0 1400000` | HARDWARE_REPRODUCED | 20 MB download + write, rc marker `debug.odm_marker=DEADBEEF` after reboot | hardware, partition write | - |
| Android 9 init imports `/odm/etc/init/root.rc` | HARDWARE_REPRODUCED | marker after reboot, label `init_exec:s0` on the rc | hardware | - |
| init exec requires a domain transition; it has no `execute_no_trans` on any exec type | HARDWARE_REPRODUCED | `execute_no_trans` denials for `shell_exec` and `init_exec`; policy dump has `type_transition init X:process` and no such allow | hardware + policy | - |
| init -> `dumpstate` via `dumpstate_exec` yields uid 0 in `u:r:dumpstate:s0` | HARDWARE_REPRODUCED | service `rootsh` running, `id` returns `uid=0(root) ... context=u:r:dumpstate:s0` | hardware | - |
| root shell on TCP 4444 | SUPERSEDED | `adb forward tcp:4444 tcp:4444`, `nc 127.0.0.1 4444`, `id` -> uid 0 | 2026-11-23 build only; final image has no listener | previous `no root` rows |

Full construction, failed attempts and restore procedure:
`reports/root-via-odm-2026-11-23.md`. The GhostLock row below remains scoped to
GhostLock; this root path is independent of it. The BL31 rows below also
stand: unsigned boot was never demonstrated here.

## Root read surface (2026-11-23)

This is the enforcing-only snapshot from 2026-11-23. Uid 0 runs in
`u:r:dumpstate:s0`; DAC is satisfied and SELinux was still enforcing in that
boot. Current root and enforcement are in the KernelSU section below. These rows supersede
"unobservable" statements that were written for `u:r:shell:s0`. Evidence:
`reports/root-read-surface-2026-11-23.md`, one boot, boot ID
`5639814c-0597-46a1-9650-4f191906f0bb`, read-only.

| Claim | Status | Evidence | Scope | Supersedes |
| ----- | ------ | -------- | ----- | ---------- |
| `/proc/cmdline` readable from root | HARDWARE_REPRODUCED | `cat`, mode `-r--r----- root radio`; denied for shell | one boot, current stock boot | shell-only "Permission denied" claims |
| dmesg readable from root via the syscall path | HARDWARE_REPRODUCED | 2334 lines, boot banner and `Kernel command line:`; `/dev/kmsg` itself still SELinux-denied | one boot | `dmesg blocked` / `klogctl not permitted` for shell |
| dmesg cmdline byte-identical to `/proc/cmdline` | HARDWARE_REPRODUCED | both 1643 B, sha256 `eabd9bc7f80c8db47ef9dd46fd71adeb3f89ee010f971db07a396dee0bc56523` | one boot | new; E2 oracle now exists, marker boot not re-run |
| live kernel VA layout readable from dmesg | HARDWARE_REPRODUCED | `.text` `0xffffff8009080000-0xffffff8009dc0000`, `.bss` end `0xffffff800ab43264`; matches `kernel-ram-patch-v2-2026-11-19.md` | one boot, no KASLR re-check across boots | "no VA anchor without pagetrace/kallsyms" |
| running banner carries `-g963f962d046a-dirty` in dmesg | HARDWARE_REPRODUCED | `/proc/version` and `uname -a` omit it | one boot | `resume-2026-11-19-experiments.md` section 3 "unexplained" |
| `/proc/buddyinfo`, `/proc/meminfo`, pstore console readable | HARDWARE_REPRODUCED | direct `cat` | one boot | shell-only blocked rows |
| `/proc/config.gz` readable from shell but not from root | HARDWARE_REPRODUCED | gzip magic via `adb shell`; SELinux denial via root listener | one boot | "root sees everything shell sees" |
| DT cmdline, `/sys/firmware/fdt`, `/proc/kallsyms`, slab attrs, debugfs, selinuxfs, `mali.ko`, sysctls still denied | HARDWARE_REPRODUCED | per-path `head -c 1` and avc records | one boot, before the permissive module | snapshot only; enforcement changed later |

## SELinux permissive (2026-11-23, SUPERSEDED)

The 2026-11-23 build was Permissive through `seflip`. The final 2026-11-24
image is Enforcing, with KernelSU applying its own sepolicy at module load;
see the KernelSU section below. The rows here are historical for that build.
They do not supersede the boot/cmdline refutations: those were about
transporting `androidboot.selinux` from U-Boot, which was never demonstrated.

| Claim | Status | Evidence | Scope | Supersedes |
| ----- | ------ | -------- | ----- | ---------- |
| `getenforce` returns Permissive and `/sys/fs/selinux/enforce` is 0 | HARDWARE_REPRODUCED | adb shell readback after ODM flash | 2026-11-23 build only; now Enforcing | enforcing state in root read surface |
| a kernel module can be loaded without boot-chain involvement | HARDWARE_REPRODUCED | `seflip` in `/proc/modules`, `lsmod` | ODM rc path only | "kernel module loading requires boot or kernel R/W" |
| `vendor_init`, not `init`, imports `/odm/etc/init/root.rc` | HARDWARE_REPRODUCED | avc denial for `system_file` label, `scontext=u:r:vendor_init:s0` | one boot, first attempt | assumption that ODM rc runs in `u:r:init:s0` |
| `vendor_init` has `sys_module` and `module_load` on `vendor_file`, not `system_file` | PROVEN | policy converted from `precompiled_sepolicy` with libsepol | offline policy | - |
| module writes `selinux_enforcing` to 0 from kernel mode | HARDWARE_REPRODUCED | enforcing went 1 -> 0 after `insmod`, no `Unknown symbol` or CRC error | one boot | "no way past setenforce without load_policy or kernel R/W" |
| `setenforce` remains denied to shell and `dumpstate` | PROVEN | policy has no `security:setenforce` allow; user's three-path test | policy + prior hardware | - |
| reboot alone does not restore enforcing | SUPERSEDED | `seflip` was loaded from ODM on every boot | 2026-11-23 build; final image boots Enforcing | - |

Full construction, failed label, build command and rollback:
`reports/selinux-permissive-via-module-2026-11-23.md` (historical). Current
rollback: `reports/kernelsu-persist-2026-11-24.md`.

## Kernel provenance

| Claim | Status | Evidence | Scope | Supersedes |
| ----- | ------ | -------- | ----- | ---------- |
| McMCCRU `3d4ab79e` is ancestor / close family, not exact source | PROBABLE | same SUBLEVEL 113, same Amlogic base, 805Y package id; zero aquaman strings, zero aquaman DTS, 3 years older than 2022-09-06 build | source-tree comparison, offline | - |
| no exact source found in searched public material | HARDWARE_OBSERVED | MiCode dangal/machuca/venom checked, MiBox issue #11 open since 2025-01, no aquaman tree, fingerprint `c5-mitv-cm-build06.bj` zero hits | scope: searched public material only | - |
| this does not prove source does not exist publicly | PROVEN | negative search cannot prove non-existence | logic, scope guard | corrects `provenance.md` absolute wording |
| `aquaman-config` is 4447 options | PROVEN | `tools/config_fingerprint.py` parses to 4447; pinned in `tools/run_tests.py` | offline artifact | - |
| low config similarity vs defconfig does not mean low functional similarity | PROVEN | raw defconfig is minimum vs expanded device config: 14.05% raw, 98.10% expanded | offline arithmetic | - |
| vendor modules give better ABI fingerprint than config similarity | PROBABLE | 2507 versioned imports, CRC comparison vs Module.symvers | offline comparison | - |
| 190 CRCs different is upper bound, not proof 190 are source-level | PROVEN | config-derived CRCs (`kmalloc_caches`, `dev_err`) move with config; split not measured per-symbol | offline, `reports/vendor-modules.md` | corrects over-read of 190 |
| 13 missing symbols include real structural gaps | PROVEN | W1 Wi-Fi stack, `pstore_io_save` absent from tree entirely | offline, source + symvers | - |
| current build is reproducible approximation of ancestral tree with adaptations | OFFLINE_ONLY | `tools/build_aquaman_kernel.sh` + `tools/validate_artifacts.py`; 3 deltas documented | offline build, reproducible | supersedes `baseline compiles` |

## Fastboot

| Claim | Status | Evidence | Scope | Supersedes |
| ----- | ------ | -------- | ----- | ---------- |
| `loadaddr` live = `0x1080000` | HARDWARE_OBSERVED | live env `loadaddr=1080000` at `0x33e1e0ef` (round46 hunt); reference tree default same | live RAM read, one boot | - |
| download alters region read by `bootm` | HARDWARE_REPRODUCED | E5 (stock `fastboot boot boot.img` boots) vs E6 (raw `boot` no download FAILs), same `bootm(Y)` | hardware, RAM-only | - |
| this proves overlap between download buffer and region consumed by `bootm` | HARDWARE_REPRODUCED | E5/E6 differential | hardware | supersedes `download != boot source` |
| `BUF == Y` as exact equality | INCONCLUSIVE | overlap of 16 MiB image compatible with range of BUF values incl. just below Y | logic | corrects `reports/_archive/buffer-equals-loadaddr-proof.md` title |
| exact `BUF` remains unknown | INCONCLUSIVE | device U-Boot encrypted, per-board constants unknown | - | - |
| `max-download-size=0x08000000` does not discriminate address hypotheses | PROVEN | `ddr_size_usable` arithmetic: neither 0x10200000 nor 0x1080000 yields 0x08000000; `tools/fastboot_addr.py` | offline arithmetic | supersedes `reports/_archive/fastboot-boot-verdict.md` root cause |
| operational blocker is SMC / secure world, not address | HARDWARE_REPRODUCED | E7a stock passes, E7b plaintext same Y rejected, E7c INVALID same timing | hardware | - |

## BL31 / secure boot

| Claim | Status | Evidence | Scope | Supersedes |
| ----- | ------ | -------- | ----- | ---------- |
| unsigned payload passes normal path and is rejected before kernel execution | HARDWARE_REPRODUCED | E7/M1a/M1b/E1/CTRL all return to Android 15-21s empty bootreason; E4/E5 signed pass | hardware | - |
| `getvar secure:no` must not be read as absence of secure-boot eFuse | PROBABLE | orange/unlocked flashing coexists with fused verify (E7); lock state vs fuse are different signals | hardware + source | - |
| `booti` / `go` not available in this build | PROBABLE | E8 instant FAIL on valid ARM64 Image, device stays in fastboot; `help` broken oracle noted | hardware, single method | - |
| no secure-boot bypass demonstrated | PROVEN | no bypass path executed; `bootm` always SMCs, `imgread` eMMC-only, `autoscr` same gate | negative, scoped to tested surface | - |

## DTB

| Claim | Status | Evidence | Scope | Supersedes |
| ----- | ------ | -------- | ----- | ---------- |
| DTB Aquaman recovered from RAM | HARDWARE_REPRODUCED | 16 MiB read at 0x01000000, `artifacts/aquaman.dtb` 58280 B | hardware read | supersedes `DTB unavailable` |
| blob exists and is valid | PROVEN | magic `d00dfeed`, `dtc` round-trip zero errors, 376 nodes / 1798 props | offline validation | - |
| original DTS source still not available | INCONCLUSIVE | `dt.img` still encrypted, recovered blob is decompilation with no include/label structure | - | - |
| recovered blob does not equal original DTS source automatically | PROVEN | decompilation loses `#include` / `&label` / comments | logic | - |
| distinguish `DTB present in RAM` vs `DTB Linux received` | PROVEN | `/proc/device-tree` confirmation never collected; RAM blob is not receipt proof | scope guard | - |

Three things kept separate: (1) DTB stored in firmware (`dt.img`, encrypted),
(2) DTB recovered from RAM (`artifacts/aquaman.dtb`), (3) DTB effectively
consumed by Linux (unconfirmed, would need `/proc/device-tree`).

## Vendor modules

| Claim | Status | Evidence | Scope | Supersedes |
| ----- | ------ | -------- | ----- | ---------- |
| 28 `.ko` extracted from OTA | PROVEN | `vendor.new.dat.br` + `tools/sdat2img.py` + `debugfs`, `out/vendor/modules` | offline, reproducible | supersedes `reports/_archive/vendor-module-compat.md` root-blocked |
| presence in OTA does not prove all were loaded at boot | PROVEN | OTA presence vs `insmod` are different facts | scope guard | - |
| vermagic `4.9.y` is not strong fingerprint | PROVEN | vendor Makefile flattens stamp to `<major>.<minor>.y`; own build produces identical string | offline, `Makefile:1221` | corrects early misread |
| CRC mismatch is real barrier for reuse vs rebuilt kernel | PROVEN | 13 missing, 190 differ vs McMCCRU Module.symvers | offline measurement | - |
| `ddr_window_64.ko` is other generation / legacy | PROVEN | `3.14.29`, no modversions, distinguishable from `4.9.y` | offline | - |

## BL33

| Claim | Status | Evidence | Scope | Supersedes |
| ----- | ------ | -------- | ----- | ---------- |
| `cmd_tbl`, handlers, consumers strongly mapped | HARDWARE_OBSERVED | 116 cmds, live==offline 0 diffs, consumer `ldr x4,[x19,#0x10]` + `blr x4` | offline disasm + live read | - |
| WRITE / FILL and redirects in RAM demonstrated | HARDWARE_REPRODUCED | WRITE 8/16/64B, FILL scattered, `false->true`, `test->true`, env-print `->true` + restore, same-cycle oracle | hardware, Optimus stage 16 | - |
| live env located and writability in RAM demonstrated | HARDWARE_REPRODUCED | env hunt `0x33e18000` 32k, `bootdelay` / `avb2` WRITE 1:1 + readback + restore, neighbour intact | hardware | - |
| env mutation equals proof relevant script consumed new value | INCONCLUSIVE | no safe script trigger observes mutated env via return code; tails are destructive (`bootm`/`update`/`recovery`/`fastboot`) | scope guard | corrects `env mutation alters boot` |
| E1 direct bootargs-value poke reaches Linux cmdline | REFUTED for this form | round48: 9 B `enforcing`->`permissiv` @ `0x33e1d825` with readback, `imgread` success, `bootm` booted stock, but `ro.boot.selinux=enforcing` and `reboot_mode normal` vs written `fastboot` | hardware, RAM-only, one run | arena is the wrong object (round51 SHADOW_COPY); boot-time rebuilder is `preboot -> run storeargs` (round52 live read); transport of the *htab* value to Linux still untested |
| authoritative env store is htab @ `0x37ee7278`, not the `0x33e18000` arena | HARDWARE_OBSERVED | round51: `test ${EnableSelinux}` oracle calibrates (`enforcing` success / `permissiv` failed:), `setenv permissiv` flips oracle to `permissiv`, restore flips back, WRITE arena `permissiv` with readback leaves oracle at `enforcing`; entry 262 @ `0x33e2ff40` data `0x33e32910` vs arena `0x33e1d6c4` | device binary + hardware oracle, RAM-only, restored | round51 promotes round50 SHADOW_COPY from OFFLINE_ONLY to hardware-observed; E1 stays REFUTED for arena poke, round49 stale-oracle caveat confirmed (effective htab leg UNKNOWN, not claimed) |
| WRITE to live htab data reaches `env_get`/Hush | HARDWARE_REPRODUCED | round52 phase A: WRITE 9 B `permissiv` @ htab data `0x33e32910` with readback (NUL + tail intact, arena untouched) flips oracle to `permissiv`; `setenv enforcing` restores | hardware oracle, RAM-only, restored, same boot | proves host bytes -> authoritative store -> parser; transport to kernel still open |
| template leg `EnableSelinux -> storeargs -> htab bootargs` | HARDWARE_REPRODUCED | round52 A/B: `setenv permissiv` + `run storeargs` -> fresh-ptr htab `bootargs` 832 B sha `df6c9576` (`permissiv`); `setenv enforcing` + `run storeargs` -> 832 B sha `c5a4b5e3` (`enforcing`); single-field diff, pointer moves each rebuild; controlled-A bytes equal round49's leftover product | hardware, fresh-pointer reads + oracle, RAM-only, left coherent | parser consumption proven; kernel transport tested round53 and REFUTED (see next row) |
| transport `htab bootargs -> kernel cmdline` | REFUTED for this form | round53: verified htab 832 B `df6c9576` (`permissiv`+`fastboot`) handed to `imgread` success + `bootm`, Android returned stock in ~15 s, but `ro.boot.selinux=enforcing` + `reboot_mode normal` (E1 double-field signature vs authoritative bytes) | hardware, one run, E1/E4 shape with fixed oracle | round54 offline: 9/9 consumers use env string; entry is eret not SMC; running kernel is bootloader-cmdline-only; one link left (fixup ran+succeeded?); round55 offline: `fdt_chosen` arg and `x2` both proven as `[images+0x100]` structurally, error paths hang so boot implies fixup success (INFERRED), no BL33 emitter of `enforcing`/`normal`, stock Image encrypted (UNKNOWN), dump DTB has no `/chosen`; divergence stays UNKNOWN with narrowed boundary, no promotion without hardware |
| FDT identity `fdt_chosen` arg vs `x2` | OFFLINE_ONLY (structural) | round55: `0x37e5c344` passes `[images+0x100]` to `fdt_chosen`, `0x37e21284` passes `[images+0x100]` as `x2` to `0x37e19264` eret; `ft_addr=0x100`/`ft_len=0x108` proven by FIT arithmetic; byte-equality UNKNOWN (reloc copy in `0x37e5bda4`, runtime `ft_len`/`fdt_setprop` return unknown). round57: `0x37e5bda4` reconstructed as `boot_relocate_fdt` (PROVEN shape, 3 callers, tail `str [x25]/[x24]` rewrites the field before fixup); pointer post-reloc PROVEN same field to `x2` with no store between; post-fixup tail in-place only, no second writer; `d00dfeed` 0 hits; classification `SAME_OBJECT_UNKNOWN_BYTES`, content still UNKNOWN, no promotion without hardware | device binary static only, no boot | - |
| inert `wificountrycode` ZZ -> kernel | REFUTED (whole-string revert) | round56: verified htab 832 B `e1e32443` (`ZZ`/`enforcing`/`fastboot`) handed to `imgread` success + `bootm`, Android returned `US`/`enforcing`/`normal`; inert reverted with `fastboot`, not selective | hardware, one run, E1/E4 shape with fixed oracle | Case B proven for this form; stop testing selinux, problem is blob identity not field filter |
| inert `androidboot.boardid` 3->7 -> kernel | REFUTED (whole-string revert, second inert field) | round58: fresh-pointer htab 832 B `a69c9f7d` with `androidboot.boardid=7` (`selinux=enforcing`, `reboot_mode=fastboot`, single-byte diff vs baseline `c5a4b5e3` at offset 681) handed to `imgread` success + `bootm`, Android returned `ro.boot.boardid=3` / `selinux=enforcing` / `reboot_mode=normal` / `wificountrycode=US`, `getenforce=Enforcing` | hardware, one run, E1/E4 shape, boardid has independent env source (htab idx 57) | second inert field reverts identically to round56; signature is whole-string/whole-object, not field-specific. The shell-only oracle claim is superseded: root reads `/proc/cmdline` and the identical `Kernel command line:` line in dmesg, but the DT node stays SELinux-denied and no marker boot has been re-run with this oracle; BL33-delivered vs Linux-re-derived stays UNKNOWN |

| `bootm` runs 12 Hush command lines, none of them env-rebuilding | OFFLINE_ONLY | `tools/bootm_env_closure.py`: `get_avb_mode;`, `setenv bootargs ${bootargs} defendkey=%x,%x,`, `store dtb decrypt ${dtb_mem_addr}`, `get_valid_slot;`, `store size`/`store read`, `setenv dtbo_mem_addr`, `dtbo_start`, `fdt apply`, `rsvmem check`. `preboot`/`storeargs`/`bootcmd` absent | device binary static only, no boot | new; closes the "bootm re-runs storeargs" explanation |
| no defenv re-import on the tested path | OFFLINE_ONLY (scoped negative) | `himport_r 0x37eaa264` has exactly 3 callers image-wide; none inside `bootm`'s 236-function `bl` closure or `imgread`'s 28-function closure, and `imgread` touches no env function at all. `env_relocate 0x37e58d94` has one caller, `0x37e24ad8`, a zero-direct-caller late-init function reached from the init function-pointer table before the burning session attaches | call graph over direct `bl` only; `blr` counted not followed, OS dispatch into fixup is an indirect table edge | new; indirect edges remain the open scope |
| `fdt_chosen` reachable from a command, in-session | OFFLINE_ONLY | exactly 2 callers image-wide: `0x37e5c344` (`image_setup_libfdt`, bootm path) and `0x37e293e4`, the `fdt chosen` subcommand (`memcmp argv[0],"cho",3`), blob from global `0x37f72a90` set by `fdt addr`; `reports/root-final-analysis/03-fdt-chosen-path.txt` | device binary static only, never executed | new; the cheapest untested oracle for the transport question |
| board DTB is decrypted by `bootm` itself, not parsed out of the boot image | OFFLINE_ONLY | `bootm` runs `store dtb decrypt ${dtb_mem_addr}` with defenv `dtb_mem_addr=0x1000000`; explains why the `0x01000000` dump has no `/chosen` | device binary static + defenv | new; corrects round57 FDT-A row for the DTB leg |
| `/proc/cmdline` on this build is the DT `/chosen/bootargs` verbatim | PROVEN (config) / OFFLINE_ONLY (source) | running `/proc/config.gz` 5691 lines: `CONFIG_CMDLINE=""`, no `CONFIG_CMDLINE_EXTEND`, no `CONFIG_CMDLINE_FORCE`; ancestral arm64 `early_init_dt_scan_chosen` (`drivers/of/fdt.c:1089`) `strlcpy`s the DT property into `boot_command_line` (`init/main.c:124`); `reports/root-final-analysis/05-kernel-cmdline-source.txt` | device config artifact + ancestral source tree | new; leaves only the AOSP `property_init` `androidboot.X`->`ro.boot.X` hop as EXTERNAL, so "Linux re-derived" is narrowed, not closed |

Direction after these rows: the store is proven, the parser is proven, the
template rebuild is proven, the FDT pointer identity is proven, and the kernel
cmdline source has no alternative, yet three inert fields revert whole-string.
The remaining break is inside `bootm`'s window, past the htab, before or at
`fdt_chosen`. `fdt_chosen` has never been executed by us.

## GhostLock

| Claim | Status | Evidence | Scope | Supersedes |
| ----- | ------ | -------- | ----- | ---------- |
| trigger / requeue path reached | HARDWARE_REPRODUCED | FWRQ/FCRQ trio -> EDEADLK 5/5, LEVEL_2 matrix, BOOT_ID 3ec336a5 | hardware | - |
| consumer `FUTEX_LOCK_PI` shows differential behaviour | HARDWARE_REPRODUCED | occupied+stale=EDEADLK vs else TIMEOUT, alt negatives, pos_cycle control | hardware | - |
| `f_target` and `f_alt` distinguished by occupancy / fidelity | HARDWARE_REPRODUCED | `alt_tgt` EDEADLK, `alt_only` TIMEOUT, walk follows birth `f_target` | hardware | - |
| H16 live-retarget demonstrated | INCONCLUSIVE | no durable 8B `[W_waiter+0x38]` write ever landed; census empty of usable carriers | audited surface only | - |
| `NO_EXACT_WRITER_FOUND` | PROBABLE | 411 8B stores in window, 33 exact, 0 TARGET_RT_MUTEX producer; BFS depth<=3, all SyS roots | scope: audited surface, not whole kernel | corrects `NO_EXACT_WRITER` global |
| `NO_DISCLOSURE_FOUND` | PROBABLE | POINTER_BYTES_FOUND 0, 22 tests, proc/sys/net/futex/vendor sample | scope: audited surface | corrects `no disclosure path exists` global |
| post-free stack reuse is main comparative hypothesis | PROBABLE | every external port (canonical x86, Hazel, 5.10, OPPO 4.14, Shield 4.9) replaces whole object after waiter return, never live 8B retarget | comparative, offline | reclassifies GhostLock direction |
| disclosure is real bottleneck | PROBABLE | forging needs valid kernel VAs; none disclosed as bytes | - | - |
| reclaim proven | INCONCLUSIVE | `mm_reclaim_probe` FAIL `reclaim_hits=0`; MSG_PEEK is plumbing only | hardware | - |
| arbitrary R/W / root demonstrated | INCONCLUSIVE | out of scope until slot moves; never attempted, never claimed | - | - |

Direction: principal `post-free stack reuse + disclosure`; secondary `H16
live retarget`; closed: reclaim without verifier, audited live H16 writer
search, fake object, arbitrary R/W, cred/root. Post-free reuse is not
demonstrated on Aquaman. Live-retarget was audited and not demonstrated.
Future work prioritises reuse formulation, conditioned first on reproducible
disclosure and overlap.

## Unconsolidated 2026-11-19 additions

Two files were added after the 2026-10-02 consolidation. They are indexed in
`reports/MAP.md`, not merged into the rows above.

| File | Status | Scope |
| ---- | ------ | ----- |
| `reports/observations-new-angles-2026-11-19.md` | OFFLINE_ONLY | four untested angles: plaintext kernel dump through the BL33 wrapper, keyman blobs as AMLSECU key, CBC oracle at the SMC, bootm rebuild trace. The file explicitly does not change the rows above |
| `reports/plan-smc-gate-neutralize-magisk.md` | OFFLINE_ONLY | operational plan. Phase 0 read-only oracle PASS; phases 1-3 not executed. No bypass demonstrated, so the BL31 row above stands |

## KernelSU Next LKM (2026-11-24)

`reports/kernelsu-persist-2026-11-24.md` is the current state for this track.
It supersedes `reports/kernelsu-next-lkm-2026-11-23.md` on persistence,
SELinux mode, Manager crowning, the `su` path and network exposure. It also
supersedes the "VIABLE WITH SOURCE" verdict in `reports/kernelsu-next.md` for
the LKM route. KernelSU Next v1.1.1 runs as an unsigned LKM loaded from `/odm`
at `sys.boot_completed`, with `su -c id` as `u:r:su:s0`, Manager crowning, a
grant that survives reboot and SELinux Enforcing. No boot.img, BL31 or
source-tree rebuild is involved. The BL31 and custom-kernel rows above remain
unchanged.

| Claim | Status | Evidence | Scope | Supersedes |
| ----- | ------ | -------- | ----- | ---------- |
| grant/revoke through the Manager, survives reboot | HARDWARE_REPRODUCED | UI revoke -> `su` rc 127, grant -> uid 0, grant still present after reboot | final ODM image, one device | allowlist in memory only, `ENOKEY` on save |
| SELinux stays Enforcing with KernelSU loaded | HARDWARE_REPRODUCED | `getenforce` = Enforcing, no `seflip`, no Oops for >4 min | final ODM image, one device | global Permissive via `seflip` |
| KernelSU sepolicy applied at module load | HARDWARE_REPRODUCED | `vendor_init` can read `packages.list`, Manager crowning line in dmesg | final ODM image | `/odm/ksu_sepolicy.sh` exec with `permissive su;` |
| 32-bit `su` path works | HARDWARE_REPRODUCED | native + `compat_sys_execve` hooks, `su -c id` -> uid 0 | final ODM image, 32-bit userspace | 64-bit-only `sys_execve` hook |
| no network root listener | HARDWARE_REPRODUCED | no `:115c` in `/proc/net/tcp*`, `nc` refused | final ODM image | TCP 4444 listener on all interfaces |
| static symbol/CRC match of the rebuilt module | OFFLINE_ONLY | `work/ksu-lkm-fix/check-static.py` PASS against stock `Module.symvers` | build tree, not device | - |

Remaining gaps: the control build is source-close, not byte-identical; LSM
hooks (`vfs_rename`, `task_fix_setuid`, `inode_permission`, `key_permission`)
are absent and Manager discovery is a one-shot scan at init; symbol fidelity
is offline-derived; `rmmod` is not a validated rollback. Detailed evidence and
build recipe: `work/ksu-lkm-fix/PERSISTENCE.md`.
