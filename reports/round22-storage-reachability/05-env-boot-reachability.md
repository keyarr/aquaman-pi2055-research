# round22 05: env and boot-script reachability

question: does any `env`/`bootcmd`/`run`/`source` composition reach storage
without (or in addition to) an explicit host command? and is automatic boot
execution conflated with command reachability? answers are separated below.

## 5.1 `run` / `env` as composition primitives (INDIRECT, host-driven)

- `run 0x37e5ea04`: `getenv(argv[i])` -> `run_command` per variable, in a
  loop. host picks variable NAMES (argv), bytes come from env RAM.
  mechanism HIGH (round15 C). composed with `setenv` this chains two
  <=31-char `oem` calls into longer scripts:
  `oem setenv k <script>` + `oem run k` (each fits 33 B if the script chunk
  is short; longer scripts need several `setenv` appends, standard U-Boot
  behavior, not proven byte-by-byte here).
- `env 0x37e57d6c`: dispatcher to 8 subcommands; `env set` = same backend as
  `setenv` (env-RAM write, HIGH); `env run` = `do_run`; `env save` = eMMC
  persist. no direct C1/C2 edge in the dispatcher itself.
- consequence for storage: `run`/`env` do NOT add a NEW storage edge, they
  let the host SPELL a longer `keyman read/write ...` invocation across
  calls, dodging the 33 B `oem` truncation (1.4). classification: INDIRECT
  composition (B+C via two steps). static mechanism CONFIRMED, multi-call
  chaining POSSIBLE BUT UNPROVEN by execution (same caveat as round15).

## 5.2 bootcmd / boot scripts (D = automatic, NOT host argv)

- default env: `bootcmd=run storeboot` (rodata `0x37eb65a0`).
- `storeboot` script (`0x37eb71f2`): `get_system_as_root_mode; echo ...;
  if test ...; then ...` chain. no `keyman`/`keyunify`/`store key` token in
  the script. boot flows through `store` sub-handlers (`init/read/dtb`) and
  the `0x37e904ac` state machine, NOT through the secure-key SMC path.
- `store key 0x37e33a38` itself CALLS `run_command` (bl `0x37e33ba8`) with a
  constructed `"%s %s %s 0x%x"` string (`amlnf`/`key_write`/`key_read`
  fstrings, `do_store_key_ops`). the constructed command is an amlnf/nand
  op, not a `keyman` re-entry. so `store key` is a `run_command` EMITTER,
  not a storage-SMC path. recorded to avoid the "store contains key,
  therefore secure storage" misread.
- `temp_triming` / `ddr_tune_dqs_step` / `get_rebootmode` call `run_command`
  with CONSTANT strings (`write_trim`, `write_version 0xc0`, `read_temp`,
  `save`, cold_boot/normal/... dispatch). constants, not host argv; none
  resolves to `keyman`.

## 5.3 what runs automatically at boot (D) vs on command (B+C)

| edge | trigger | argv? | SMC? | class |
|---|---|---|---|---|
| `0x37e904ac` -> `0x37e8c138` (0x28, X1=1) + `[0x37f60878]=2` | boot state machine (many `bl` parents: mmc/store/init paths) | NO (struct field `[x19,#0xec]==1`) | 0x28 scalar | D |
| `0x37e8c1dc` amlkey_init-ish (getbuffer + 0x6a + 0x69 + backend check) | called via function pointer / init table (no `bl` caller; reached from boot/init context) | NO | 0x69/0x6a scalar | D |
| `0x37e8212c` optimus_download_key -> `key_manage_write` | USB burning / DTB key provisioning (`0x37e824a8` runner, `0x37e7abe4`/`0x37e79ff0` parents) | NO (DTB/usb structs) | 0x62 via the write fn | D (provisioning, not shell) |
| `keyman read/write` -> SMC 60-path | explicit `run_command("keyman ...")` (oem, run, bootcmd-if-edited) | YES | 0x61/0x62 | B+C |
| fastboot shim `0x37e94838` -> SMC 60/61/63 | explicit fastboot download-key/getvar flow | fastboot fields, not argv | 0x60/61/63 | host-via-fastboot (not run_command) |

rule applied: automatic boot/init execution (D) is NEVER counted as command
reachability (B+C). the two YES paths in 02 are B+C, not D. the 0x28 and
init paths are D, not B+C. no `bootcmd` default reaches any SMC 60..65 op.

## 5.4 aliases and compound commands

no shell aliases for `keyman` subcommands exist in the image. compound
execution (`;`, `&&` via `run_command` script semantics, `test`/`itest`
bounded dispatch) can sequence a storage command after other commands, but
that is generic `run_command` composition, not a separate storage edge.
`source`/`go`/`booti` do not exist in this build (round15 A.1), so no
script-from-address path needs auditing here.
