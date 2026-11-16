# round49 template selinux: EnableSelinux -> storeargs -> bootargs (hardware run, 2026-10-02)

## objective

single question, nothing else:

> is a change to EnableSelinux in the environment read by the U-Boot parser, consumed by storeargs, and reflected in the effective cmdline?

no root angle, no ghostlock, no avb, no smc. just this leg.

## pre-conditions (already proven before this run)

- WRITE 0x01 arbitrary BL33 RAM with readback (round39/43/46).
- live env at 0x33e18000, deterministic layout (round46, round48).
- E1 round48: direct bootargs poke REFUTED for that form, template side open.
- E4: imgread + bootm stock boots Android (not re-run here, see why below).

## session

- entry: device already at 1b8e:c003. identify ver 0.7, stage 16 (TPL/BL33-u-boot). adb/fastboot correctly empty in this mode.
- baseline oracle sane: false->failed:, true->success, test 1 = 2->failed:, test 1 = 1->success.
- re-hunt this session: mread 0x33e18000 0x8000, sha 1c5e262d (same as round46/48). historic addresses confirmed live, not reused blind:
  - EnableSelinux name@0x33e1d6b6 val@0x33e1d6c4 len 9 `enforcing`
  - bootargs val@0x33e1d73f len 832, selinux field at +210 (abs 0x33e1d811) `androidboot.selinux=enforcing`
  - initargs val@0x33e1e035 len 166
  - storeargs val@0x33e1e75b len 965, contains literally `androidboot.selinux=${EnableSelinux}`
  - storeboot val@0x33e1eb2b len 621 (never executed)
  - loadaddr `1080000`, boot_part `boot`, active_slot `normal`, avb2 `1`, bootdelay `1`
- baseline reads: EnableSelinux `enforcing` with NUL + neighbors (`,8bit\0EnableSelinux\0enforcing\0active_slot\0normal`) intact. bootargs head/tail/NUL intact.

## main experiment (WRITE path)

- WRITE 0x01: 9 B `permissiv` @ 0x33e1d6c4, exactly over `enforcing`, same length, NUL untouched. nothing else touched.
- readback: `permissiv\0active`, wide 48 B shows the single 9 B diff, neighbors identical.
- pre-storeargs state (the valuable one): EnableSelinux=permissiv, bootargs still `androidboot.selinux=enforcing`. so any later flip could only come from storeargs.
- bulkcmd `run storeargs` -> `success` (0.02 s). storeboot NOT run, update unreachable, no saveenv, nothing else sent.
- post-storeargs bootargs: `androidboot.selinux=enforcing`, full 832 B byte-identical to pre-run. no flip.

## control (functional setenv path, same session)

purpose per plan: separate WRITE-visibility problem from storeargs problem.

- bulkcmd `setenv EnableSelinux permissiv` -> `success`. raw blob already permissiv from WRITE so no visible change (expected).
- bulkcmd `run storeargs` -> `success`.
- bootargs after control: still `enforcing`, byte-identical again.

so it is NOT a WRITE-visibility issue. even the proper setenv route does not propagate. the storeargs leg itself does not deliver.

## minimal cause analysis (read-only)

- printenv/echo oracles return bare `success` (console invisible), no data. known limitation, confirms nothing either way.
- offline hunt census: `EnableSelinux` occurs exactly twice (definition + the ${} ref in storeargs). `enforcing` x4 (EnableSelinux value, bootargs selinux, veritymode field, storeargs veritymode literal). no second definition, no shadow var.
- restore finding: `setenv EnableSelinux enforcing` -> success, but raw blob still `permissiv`. the 0x33e18000 blob is the import image, not the hash store setenv writes to. blob restored afterwards with WRITE `enforcing`, readback verified, wide window stock, final bootargs stock-identical, oracle sane. session left clean, no reboot issued.
- probable (INFERRED, not proven): `${EnableSelinux}` expansion inside storeargs yields enforcing from another source on this path. candidate: `get_rebootmode` (first statement of storeargs) re-deriving, or expansion reading a store the blob poke never reaches. would need a parser oracle that does not exist on this build, so this stays a hypothesis, not a claim.

## why no imgread/bootm this round

storeargs returned success but bootargs is byte-identical stock. there is nothing new to transport: a boot now would re-run the E1/E4 stock shape and read back enforcing, answering nothing. skipped deliberately to avoid a reboot cycle with zero information gain. no imgread reply, no bootm, no adb oracle to report.

## result

```text
WRITE EnableSelinux enforcing -> permissiv: readback OK, neighbors + NUL intact
run storeargs -> success, bootargs still androidboot.selinux=enforcing (832 B identical)
control setenv EnableSelinux permissiv + run storeargs -> success, bootargs still enforcing (identical)
```

classification: REFUTED for the template leg `EnableSelinux -> storeargs -> bootargs` on this build via this route.

```text
ro.boot.selinux: not measured (no boot; nothing to transport)
getenforce: not measured
```

## root relevance

none. WRITE primitive unchanged (HARDWARE_REPRODUCED). direct bootargs poke stays REFUTED-for-that-form. template leg now REFUTED too. no uid/euid/capability claim, no selinux-bypass claim. the gap moves: env blob bytes are writable and readable back, but no script-consumption of a mutated value has ever been observed on this build (blob vs hash split is the likely wall).

## artifacts

- reports/round49-bootargs-template-selinux/hunt_33e18000_32k.bin (this session, sha 1c5e262d)
- reports/round49-bootargs-template-selinux/bootargs_after_storeargs.bin (832 B, enforcing)
- reports/round49-bootargs-template-selinux/bootargs_after_control.bin (832 B, enforcing)
- reports/round49-bootargs-template-selinux/session_run.log (full log: baseline, hunt, WRITE, readback, pre/post storeargs, control, restore, final verify)

RAM-only run: no saveenv, flash, erase, update, recovery, storeboot, DTB/kernel change. env restored to stock in-session; any residue dies with reboot.
