# storage reachability round22 (consolidated, static only)

image `reports/round14-bl33-persist/bl33-37e18000.bin` base `0x37e18000`
(sha `664fb34a...`). no device, no reads, no SMC, no `0x05`, no commands run.
detail: `reports/round22-storage-reachability/01..06`.

## chain (the round question, answered)

```text
host
 -> fastboot oem
 -> cb_oem 0x37e95630 (bl 0x37e956a0)
 -> run_command 0x37e5e968
 -> U-Boot command keyman 0x37e74290 (find_cmd tbl 0x37f5e4f8 + blr x4)
 -> do_keyman_write 0x37e749ac / do_keyman_read 0x37e750c4
 -> key_manage_write 0x37e7430c / key_manage_read 0x37e74d18
 -> amlkey_write 0x37e8c450 / amlkey_read 0x37e8c3e4
 -> storage handler 0x37e8bd10 / 0x37e8bdc8
 -> C1 [[0x37fbde60]] (= 0x05000000) stage [ + C2 [[0x37fbde58]] (= 0x05040000) parse on read ]
 -> SMC 0x82000062 / 0x82000061
```

## verdicts

```text
storage write reachable via run_command  = YES (keyman write -> SMC 0x62)
storage read reachable via run_command   = YES (keyman read -> SMC 0x61, OUT -> argv RAM)
storage query reachable                  = NO via run_command (SMC 0x60 fastboot-only)
storage verify reachable                 = NO via run_command (SMC 0x64 table-only; absolute UNKNOWN)
SECURITY_KEY_WRITE reachable             = YES
SECURITY_KEY_READ reachable              = YES
host -> oem -> run_command -> storage    = CONFIRMED (READ + WRITE; REFUTED for query/status/tell/verify via run_command)
```

round21's "no fastboot/usb caller" (true) is not "not reachable via oem"
(false for read/write): `oem` reaches storage through `run_command`, not
through fastboot/usb code references. B+C (host picks handler + argv)
counts as host-reachable even with zero USB mentions in the writer.

## per-writer classification

```text
0x37e8bd10 write/0x62  directly command-reachable    (keyman write)
0x37e8bdc8 read/0x61   directly command-reachable    (keyman read + fastboot twin path)
0x37e8be98 query/0x60  internal-only (fastboot-only) (amlkey_isexsit <- 0x37e94838 only)
0x37e8bf3c status/0x65 internal-only (table-gated)    (no command bl ancestor)
0x37e8bfe0 tell/0x63   internal-only (fastboot-only) (amlkey_size <- 0x37e94838 only)
0x37e8c084 verify/0x64 unknown (table-only root 0x37e75e7c, no bl caller) => NOT via run_command
```

## argv control (short)

- write: `argv'[1]` name -> `[IN+0]`+memcpy, `argv'[2]` data -> `[IN+4]`+memcpy
  (hex/ascii/numeric ladder, `0x386` cap, `oem` 33 B truncation). B+C YES,
  constrained (HIGH graph / MED argv).
- read: `argv[1]` name -> `[IN+0]` (which key is staged), `argv[2]` addr ->
  OUT dest (len+blob lands in argv-chosen RAM, return code only, no print).
  B+C YES (HIGH / MED-HIGH).
- query/status/tell/verify: no argv path from any command (sole-caller
  census). fastboot shim gates on the word but never prints/sends it;
  verify blob is `memcmp`d locally.

## SMC / env-boot / 0x28 (short)

- 60..65: all sharemem-arg (X1/X2/X3 unset), stub `0x37e8bba0`; BLOCK never
  touched on op paths; 0x26/0x66/0x67/0x68/0x6b/0x6c never issued.
- 0x28: `0x37e904ac` boot machine, `[x19,#0xec]==1` -> `[0x37f60878]=2`,
  `SMC 0x28(X1=1)`, scalar, no buffers, no link to IN/OUT globals.
- 0x69/0x6a: scalar, `0x37e8c1dc` init only, no sharemem.
- env/boot: `run`+`setenv` = INDIRECT stitching to dodge `oem` truncation
  (mechanism proven, chain unproven); default `bootcmd=run storeboot` never
  touches SMC 60..65; `store key` emits an amlnf `run_command`, not a secure
  op; D (auto) never counted as B+C.

## non-claims

OUT plaintext-vs-cipher UNKNOWN; no exploit; `git diff --check` clean.
