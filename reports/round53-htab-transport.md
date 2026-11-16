# round53 htab bootargs transport (hardware run, 2026-10-02)

## Objective

Test whether the verified authoritative htab `bootargs` reaches the kernel, using the E1/E4 `imgread+bootm` shape with the oracle fixed (marker built via `setenv+storeargs`, never arena poke).

## Result

```text
REFUTED for this form: kernel saw enforcing+normal, htab held permissiv+fastboot (df6c9576)
```

Pre-boot (same boot as round51/52, re-hunted): `setenv permissiv` + `run storeargs` ->
fresh-ptr htab `bootargs` 832 B sha `df6c9576` with `androidboot.selinux=permissiv`,
`androidboot.reboot_mode=fastboot`. `imgread kernel boot 0x1080000` -> `success`,
`bootm 0x1080000` -> USB drop (E4 signature). Android returned in ~15 s stock.

Post-boot oracle: `ro.boot.selinux=enforcing`, `getenforce=Enforcing`,
`ro.boot.reboot_mode=normal`. Two fields differ from the verified RAM string:
the E1 double-field signature reproduced against the authoritative object.

## Reading

Round52 closed `WRITE/setenv -> htab -> parser`. This round shows the next arrow
breaks: `htab bootargs -> kernel cmdline` does not carry our bytes on this path.
Consumers after our verify-read are only `imgread` (eMMC-to-RAM copy) and `bootm`
(`env_get` + `fdt_chosen`/`do_bootvx_fdt` per round50 disasm, same htab), so the
competing source sits at or below `bootm`/handoff. Candidates, unordered and
untested: kernel builtin `CONFIG_CMDLINE*` override in the stock Image, a
DTB-baked `/chosen/bootargs` winning the merge, or an `imgread`/`bootm` rebuild
with no disasm evidence yet. Concrete offline test first: `strings` the stock
Image for `androidboot.selinux` / `reboot_mode=normal` literals. No more boots
until an offline candidate predicts the observed pair.

E2 (`cmdline -> uid=0`) is moot until a transport is found; it stays unaudited
and unattempted. Chain 1's open link moves one arrow right: parser consumption
is now proven, kernel receipt is refuted for every env form tried (arena direct,
arena template-stale, htab authoritative).

## Artifacts

* `reports/round53-htab-transport/session_run.log`
* `htab_bootargs_transport_832.bin` (df6c9576, what bootm was handed)
* `table_preboot.bin` (611cec85, entry proof)
* `getprop_ro_boot.txt`, `getprop_ro_boot_selinux.txt`, `getenforce.txt`

No saveenv/flash/erase/update/recovery; marker RAM-only, died with bootm. Device healthy stock Android.

## Validation

* `python3 tools/run_tests.py` -> `126 tests, OK`.
* `git diff --check` clean.
