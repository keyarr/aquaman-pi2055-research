# round22 06: summary (host reachability verdict)

static only. no device, no reads, no SMC, no `0x05`, no U-Boot commands run.
base image `reports/round14-bl33-persist/bl33-37e18000.bin` (`0x37e18000`).

## 6.1 final table: command -> handler -> storage -> SMC -> host?

```text
command              | handler  | host argv -> storage input                  | operation          | C1/C2/BLOCK      | SMC      | host controls args | reachable via run_command | conf
keyman write ...     | 0x37e74290 => 0x37e749ac -> 0x37e7430c -> 0x37e8c450 -> 0x37e8bd10 | argv'[1]=name -> [IN+0]+memcpy; argv'[2]-data -> [IN+4]+memcpy | SECURITY_KEY_WRITE | C1 stage | 0x82000062 | B+C (name+data+len, format-checked, oem-cut) | YES | HIGH (graph) / MED (argv)
keyman read ...      | 0x37e74290 => 0x37e750c4 -> 0x37e74d18 -> 0x37e8c3e4 -> 0x37e8bdc8 | argv[1]=name -> [IN+0]+memcpy; argv[2]=addr -> OUT dest | SECURITY_KEY_READ | C1 stage + C2 len+blob->RAM | 0x82000061 | B+C (name + dest addr) | YES | HIGH / MED-HIGH
keyman query ...     | 0x37e74290 => 0x37e75304 -> 0x37e74ba4/0x37e75254/0x37e74c0c | (does NOT reach amlkey_isexsit) | (no op) | - | - | - | NO | HIGH (negative: sole-caller census)
store key ...        | 0x37e33900 => 0x37e33a38 -> run_command(amlnf fmt) | nand/amlnf path, no share slots | (no op) | - | - | - | NO | HIGH (negative)
keyunify ...         | 0x37e73c84 inline ladder | no bl to key_manage/amlkey | (no op) | - | - | - | NO (via bl) | MED-HIGH (table path UNKNOWN)
query (top-level)    | 0x37e56224 | soc-info, no SMC/slots | (no op) | - | - | - | NO | HIGH (negative)
(fastboot) dl-key    | 0x37e94838 (NOT a U-Boot cmd; fastboot cb) -> 0x37e8c2ec/0x37e8c374/0x37e8c3e4 | fixed name -> C1; OUT -> bss/USB | QUERY/TELL/READ | C1+C2 | 0x60/0x63/0x61 | fastboot fields (not argv) | n/a (not run_command; host-via-fastboot YES) | HIGH
status/verify        | table-only (0x37e7609c/0x37e75e7c, no bl caller) -> 0x37e8bf3c/0x37e8c084 | name only | STATUS/VERIFY | C1+C2 | 0x65/0x64 | E (internal) | NO (UNKNOWN absolute) | MED-HIGH
boot/init (0x28 etc)| 0x37e904ac -> 0x37e8c138; 0x37e8c1dc init | struct/constant, no argv | SET_STORAGE_INFO/ENCTYPE/NOTIFY | none | 0x28/0x6a/0x69 | D (auto) | NO (not a command path) | HIGH
```

categories used: A = host controls data directly; B = host picks handler;
C = host controls argv; D = boot/init automatic; E = internal-only.
a `B + C -> storage` path is host-reachable even with zero `fastboot`/USB
references in the writer, which is exactly the `keyman` case.

## 6.2 required answers

```text
storage write reachable via run_command  = YES (keyman write -> SMC 0x62)
storage read reachable via run_command   = YES (keyman read -> SMC 0x61, OUT -> argv RAM)
storage query reachable                  = NO via run_command (only fastboot shim reaches SMC 0x60)
storage verify reachable                 = NO via run_command (table-only root, no bl caller; absolute UNKNOWN)
SECURITY_KEY_WRITE reachable             = YES (same as storage write)
SECURITY_KEY_READ reachable              = YES (same as storage read)
```

```text
host -> oem -> run_command -> storage = CONFIRMED (for READ + WRITE)
```

scope of CONFIRMED: the full `bl` chain plus the one documented
`find_cmd+blr` dispatch hop is demonstrated instruction-by-instruction
(`cb_oem 0x37e95630 -bl 0x37e956a0-> run_command -tbl-> keyman 0x37e74290
-find_cmd tbl 0x37f5e4f8-> do_keyman_{write,read} -> key_manage_{write,read}
-> amlkey_{write,read} -> low writer -> C1 -> SMC 0x62/0x61`, read additionally
`-> C2 -> caller RAM`). CONFIRMED covers READ and WRITE only. for
QUERY/STATUS/TELL/VERIFY via `run_command` the verdict is REFUTED on
demonstrated edges (no path), UNKNOWN only for undiscovered indirect calls.

## 6.3 the sentence being resolved

round21: "C1 controlled by host = NO direct evidence (write path has no
fastboot/usb caller)". that statement is TRUE as written and still true:
no writer takes raw USB bytes, and the staged bytes on every path are
caller name/data pointers, not a download buffer. but it is NOT equivalent
to "not reachable via fastboot oem", because `oem` reaches `run_command`
and `run_command` reaches `keyman write/read`, which reach C1/C2/SMC
60..65 with host-influenced argv. the missing link is now closed for two
ops and closed-negative for the other four.

## 6.4 0x28 note (section 9 answer)

caller `0x37e904ac` (boot/state machine), full path in 04.3/05.3:
`[x19,#0xec]==1` gate -> `[0x37f60878]=2` (store backend selector) ->
`SMC 0x82000028(X1=1)` -> boot continues regardless. semantics supported by
instructions: backend selector/mode flag (2 = secure-key backend in the
`store_key_read/write` jump tables), NOT IN/OUT/BLOCK setup. causal link to
`0x37fbde60/58/68/48/50`: NONE (those come from `0x37e8bbb8` via
0x23/24/25/27 + flag; `0x28` writes a different global). buffer use: REFUTED.

## 6.5 risks / non-claims

- OUT content (plaintext vs cipher) still UNKNOWN (round21 stands; 0x6a
  never gates the copy-out).
- `oem` 33 B truncation + `key_manage` format checks constrain WHICH
  names/lengths a host can push; graph YES does not mean arbitrary-write.
- `run`+`setenv` script stitching to dodge truncation is mechanism-PROVEN,
  chain-UNPROVEN (not executed, per static-only rule).
- no new exploit, no live probe, no device touched this round.
- checks: `git diff --check` clean (docs only); `bl33_audit.py smc/callers`
  censuses match every edge cited; `0x26` absence re-verified (zero sites).
