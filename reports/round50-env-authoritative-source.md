# round50: authoritative environment source (offline analysis, 2026-10-02)

## Scope

Single question only:

> Which copy/structure of the environment does the real BL33 use as the
> authoritative source for `env_get()` and Hush `${...}` expansion, and why did
> the `EnableSelinux` change not alter the `bootargs` observed in the
> `0x33e18000` blob?

No hardware was executed in this round. No E1, no E1-template, no boot, no
poke, no flash, no saveenv. All code claims are re-derived from the device
binary `reports/round14-bl33-persist/bl33-37e18000.bin` (sha `664fb34a…`,
base `0x37e18000`). All blob claims are re-derived from
`reports/round46-same-cycle/hunt_33e18000_32k.bin` and
`reports/round49-bootargs-template-selinux/hunt_33e18000_32k.bin`
(sha `1c5e262d…`).

The Khadas reference tree (`.src/u-boot-khadas`) is used ONLY for names and
layout comparison, always marked REFERENCE. Nothing in this report depends on
it as proof.

Status vocabulary: same as `reports/ROOT_FINAL_ANALYSIS.md`
(PROVEN / HARDWARE_REPRODUCED / HARDWARE_OBSERVED / OFFLINE_ONLY / INFERRED /
INCONCLUSIVE / REFUTED / EXTERNAL).

## Executive conclusion

The authoritative runtime store is a hash table object at **`0x37ee7278`**,
backed by heap (bucket array at **`0x33e2d650`** per the persisted image).
`env_get`, `setenv`, `run`/Hush expansion, `bootm`, `fdt_chosen` and
`do_bootvx_fdt` all resolve through it. The `0x33e18000` arena is heap
containing a **stale, non-authoritative copy** of the env strings: 90 of 91
parsed names have zero pointer references from inside the dumped window, no
code addresses that region by constant (zero `ADRP` into `0x33e1xxxx` in the
whole image), and `setenv` frees + re-allocates value strings, so any
fixed-address readback goes stale after the first `setenv` of that variable.

Round49 measured the wrong copy. `run storeargs` executes four sequential
`setenv bootargs`, each of which allocates a NEW heap string; re-reading the
old `bootargs` address (`0x33e1d73f`) afterwards observes freed bytes, not the
effective value. The E1 smoking gun needs no extra machinery either: no
`storeargs` ran in E1, yet Linux saw `reboot_mode=normal` while the arena
string said `fastboot` — the consumed string was never the arena string.

Category: **`SHADOW_COPY`** (arena = stale copy; htab = authority), with
`CONFIRMED_SHARED` as the proven sub-finding for the get/set pair (both use
the same htab object). Which heap bytes hold the live strdups is unmapped and
is exactly what the proposed one-session oracle decides.

## Runtime environment model

```text
flash env / default env (0x37eb65a0, len 0x1785)
     |
     |  himport_r (0x37eaa264) — one-way, at relocate/import only
     v
htab object @ 0x37ee7278 {table=0x33e2d650, size=0x209}   <-- AUTHORITY
     |  ENTRY nodes {used,key,data,flags} stride 0x28, heap
     +----> env_get  (0x37e58920, FIND)  -> entry->data
     +----> env_set  (0x37e58294, ENTER) -> free old + strdup new
     +----> Hush ${VAR} (0x37e2b144 -> b env_get, no local shadow)
     +----> run (0x37e5ea04: env_get script + parse_stream 0x37e5e968)
     +----> bootm / fdt_chosen / do_bootvx_fdt (env_get "bootargs")
     +----> test ${A} = ${B} (htab-reading oracle, see below)

0x33e18000 arena: malloc heap holding a STALE import-era copy
     x  env_get, env_set, Hush, bootm, fdt  (zero ADRP refs, zero ENTRY refs)
     +----> mread oracle only (valid for in-place reads; INVALID after setenv)
```

Fallback layer (precedence): if `GD_FLG_ENV_READY` (`0x80` in `gd->flags`
at `[x18,#8]`) is clear, `env_get` uses a 32-byte linear path
(`gd->env_buf` at `[x18,#0xd0]`, cap `0x20`, error
`"env_buf [%d bytes] too small…"` at `0x37ed0532`). Any successful
`run <script longer than 31 chars>` proves the htab path was active.
Round49 `run storeargs` (965 B) -> `success` therefore proves the htab path
was active during round49 (OFFLINE_ONLY logic + HARDWARE_OBSERVED reply).

## `env_get` reverse engineering

Function `0x37e58920` (device binary, re-derived):

```text
0x37e58920  stp  x29, x30, [sp, #-0x70]!
0x37e58928  ldr  x2, [x18, #8]        ; gd->flags (x18 = global data ptr)
0x37e58930  and  x19, x2, #0x80
0x37e58934  tbz  w2, #7, 0x37e5897c   ; bit7 clear -> fallback
0x37e58944  adrp x3, #0x37ee7000
0x37e58958  mov  w1, #0               ; FIND
0x37e58960  add  x3, x3, #0x278       ; x3 = 0x37ee7278 (htab)
0x37e58968  bl   0x37ea9a58           ; hsearch_r(item, FIND, &out, htab, 0)
0x37e5896c  ldr  x0, [x29, #0x40]     ; ENTRY*
0x37e58970  cbz  x0, ret-NULL
0x37e58974  ldr  x0, [x0, #8]         ; ENTRY.data -> returned value pointer
```

Fallback (`0x37e58828` + `0x37e587a8` + char helper `0x37e58a74`):
copies at most `0x20` bytes from `[x18,#0xd0]` (`gd->env_buf[32]`,
REFERENCE name) or scans the compiled-in default env at `0x37eb65a0`
(`"bootcmd=run storeboot…"`, resolved at `0x37e58a90`: `0x37eb6000+0x5a0`).
The `'='` matcher at `0x37e587a8` (`cmp w0,#0x3d`) confirms the default blob
uses `name=value` serialisation, unlike the arena's `name\0value\0`.

Hash core `0x37ea9a58` (hsearch_r, re-derived signature from call sites):
`hsearch_r(key_struct, action, retval, htab=0x37ee7278, flag)`.
Hash loop (`ldrb` + `add w1,w2,w1,lsl#4`), modulo `size`, node stride
`0x28`, node layout `{+0x0 used/hash, +0x8 key, +0x10 data, +0x18 flags}`
(decoded from FIND/ENTER/callback sites `0x37e26e7c`, `0x37e2710c`,
`0x37ea9e78`). ENTER path frees the old data (`bl 0x37e59cd4` = free,
call-site semantics) and strdups the new one (`bl 0x37eaadc8` = strdup).

htab object contents from the persisted image (device artifact, not
reference): at file offset of `0x37ee7278`: `table = 0x33e2d650`
(heap, above the hunt window), `size = 0x209` (521), `filled = 0x4a`
(74, plausible var count). `env_id` counter at `0x37ee70f0` = `0x26`
(38 `setenv`s ran during boot — boot scripts do dozens).

162 `BL env_get` call sites in the image (census, device binary). Boot
consumers re-derived this round (all `adrp+add` resolving `0x37ebf453` =
`"bootargs"` immediately before `bl 0x37e58920`):

| site | function | evidence |
|---|---|---|
| `0x37e24dbc` | `bootm` (`0x37e24c00`) | `add x0,x22,#0x453; bl env_get`, NULL-fallback `0x37eb3018` |
| `0x37e24e88` | `bootm` | `add x0,x0,#0x453; bl env_get` |
| `0x37e29814` | `fdt_chosen` (`0x37e297b8`) | `env_get -> strlen -> fdt_setprop(/chosen,"bootargs")` |
| `0x37e264e0` | `do_bootvx_fdt` (`0x37e262d4`) | `env_get -> strlen -> /chosen` write, FDT from `[x19,#0x100]` |
| `0x37e5ea30` | `run` (`0x37e5ea04`) | `env_get(argv) -> parse_stream 0x37e5e968` |

## `env_set` / `setenv` reverse engineering

`setenv` cmd_tbl idx 91, entry `0x37f61fc0`, handler `0x37e58470`
(cmd_tbl base `0x37f60eb0` stride `0x30`, handler at `+0x10` — re-derived
from the offline image; all ten spot-checked handlers match
`reports/ROOT_FINAL_ANALYSIS.md`).

Handler `0x37e58470` is an argc dispatcher into worker `0x37e58294`,
which: rejects `'='` in names (`"## Error: illegal character…"` at
`0x37ed0475`), builds the new value with malloc (`0x37e59f28`, NULL ->
`"## Can't malloc %d bytes"` at `0x37ed04ab`), increments the generation
counter at `0x37ee70f0`, then calls hsearch_r with the SAME htab and
`w1 = 1` (ENTER):

```text
0x37e58344  add  x1, x1, #0x278   ; x1 = 0x37ee7278 (same object as env_get)
0x37e58404  mov  w1, #1           ; ENTER
0x37e5841c  bl   0x37ea9a58       ; hsearch_r
```

Internal entry `0x37e5848c` (`do_env_set`-equivalent) is also called by
`get_rebootmode` (`0x37e60620`), i.e. boot scripts and C code share the
identical write path. The ENTER path frees the previous value string and
strdups the replacement: after any `setenv X`, the live value of `X`
resides at a NEW heap address. The old address keeps freed (stale) bytes.
This is the oracle-invalidating mechanism for round49. OFFLINE_ONLY
(call-site semantics for malloc/free/strdup).

`setenv` therefore never writes the `0x33e18000` arena by address — there is
not one `ADRP` into `0x33e1xxxx`/`0x33e2xxxx` in the whole image (census:
0 hits). This matches the round49 HARDWARE_OBSERVED side finding (`setenv`
did not rewrite the blob) and promotes it from "likely wall" to explained.

Import direction (one-way, boot/import time only): `himport_r 0x37eaa264`
(backslash-escape copy loop + ENTER) called from `0x37e581a0`
(`do_env_import`, `../common/cmd_nvedit.c` + `"bad CRC"` strings),
`0x37e58b9c` (relocate, `../common/env_common.c` + `"Using default
environment"`, imports `0x37eb65a0` len `0x1785`), `0x37e58bec`
(`set_default_env`-equivalent, tail-calls himport of the default env), and
`0x37e58c9c`. Every path ends with `orr x1,x1,#0x80; str [x18,#8]`
(setting `GD_FLG_ENV_READY`). Export direction: `hexport_r 0x37ea9f54`
serialises FROM the htab (used by `env print 0x37e57ddc` with `"%s=%s\n"`
at `0x37ebfdb3`, and by the `saveenv`-adjacent paths). So: blob -> htab at
import; htab -> text at print/saveenv; never htab -> the `0x33e18xxx` arena.

## Hush variable expansion

Two layers, both ending in `env_get` on the device binary:

1. `run` handler (`0x37e5ea04`): `env_get(name)` fetches the script text
   from the htab, then `parse_stream_outer`-equivalent (`0x37e5e968`).
   The script that runs is the htab copy, not the arena copy.
2. `${VAR}` expander at `0x37e2b144` (inside the `test`/`[]` evaluator
   `0x37e2b1ac`, called from dispatcher `0x37e2b348`, reachable from the
   `test` command handler `0x37e36774`): on `$`+`{` it skips 2, scans for
   `}`, truncates with NUL, and does a bare `b 0x37e58920` (tail-call to
   `env_get`). There is NO local-variable lookup on this path — it reads
   the global htab unconditionally. Only the `${VAR}` form is expanded
   here (bare `$VAR` returns NULL).

REFERENCE comparison only: Khadas `common/cli_hush.c` `lookup_param()`
calls `getenv()` first and `get_local_var()` second, and `getenv()` is
`env_get()`. The device binary is consistent with this (expansion reaches
`env_get`), but the proof cited is the device `b env_get`, not the tree.

Consequence for `run storeargs`: `${EnableSelinux}` expands via
`env_get("EnableSelinux")` = htab value. The WRITE-poked arena bytes are
consulted if and only if the arena string IS the entry's live `data`
pointer — which the census below makes unlikely and the proposed oracle
decides.

## Why round49 failed

`storeargs` (live 965 B at `0x33e1e75b`, default 975 B at `0x37eb6adb`)
is:

```text
get_rebootmode;
setenv bootargs ${initargs} ... androidboot.selinux=${EnableSelinux} ...;
setenv bootargs ${bootargs} ... androidboot.reboot_mode=${reboot_mode} ...;
setenv bootargs ${bootargs} page_trace=...;
setenv bootargs ${bootargs} androidboot.rpmb_state=...;
```

i.e. FOUR sequential `setenv bootargs`, each reading the current htab
value and writing a NEW heap string. Round49's oracle re-read the OLD
address `0x33e1d73f` after `run storeargs`:

```text
WRITE arena EnableSelinux -> htab untouched (stale copy) -> storeargs
    rebuilds htab bootargs with enforcing at NEW address ->
    readback of OLD address: enforcing (byte-identical). EXPECTED either way.
setenv EnableSelinux permissiv -> htab = permissiv -> storeargs rebuilds
    htab bootargs with permissiv at NEW address ->
    readback of OLD address: enforcing (byte-identical). EXPECTED.
```

Both round49 observations are therefore consistent with a CORRECTLY
functioning `storeargs`. The `REFUTED` label on
`EnableSelinux -> storeargs -> bootargs` was measured through a stale
oracle and strictly only refutes "the OLD heap bytes change". Whether the
effective (htab) `bootargs` changed was never observed — that leg is
UNKNOWN, not refuted. (Verdicts in `CURRENT_STATE.md` /
`INVALIDATED_HYPOTHESES.md` #21 are kept as-is; this report records the
oracle caveat so the next run does not repeat the error.)

## Why E1 failed (same model, no new machinery)

E1 ran `imgread` + `bootm` with NO `storeargs`, yet Linux showed TWO fields
differing from the poked arena string: `selinux permissiv -> enforcing`
AND `reboot_mode fastboot -> normal`. Under "arena string == consumed
string", the second difference is inexplicable — nothing in that session
rewrote it. Under the htab model it is expected: the htab `bootargs` had
been (re)built during U-Boot boot (`get_rebootmode` reads AO register
`0xc810023c` bits[15:12] and setenvs `reboot_mode`; boot scripts run
before the Optimus session attaches), while the arena kept the import-era
bytes. The kernel received the htab string. No per-field FDT override code
was found (the string `"androidboot.selinux"` occurs exactly once in the
image, inside the default `storeargs` template at `0x37eb6b46`), so the
alternative "verbatim copy + field override" has no code evidence while
the stale-copy account uses only proven mechanisms.

## Authoritative copy

```text
SHADOW_COPY
```

Justification:

* `env_get` (FIND) and `env_set` (ENTER) provably share one htab object
  (`0x37ee7278`) — CONFIRMED_SHARED sub-finding, device binary.
* The `0x33e18000` arena is heap (absolute pointers, `list_head`
  self-links, dlmalloc size words `0xa1`/`0x41` in the first `0x56b6`
  bytes), not a serialised blob; code never addresses it by constant.
* 91 env names parsed in the arena; single definitions each
  (`EnableSelinux` x2 = def + `${}` ref, `bootargs` def x1, `storeargs`
  def x1, `enforcing` x4, `permissiv` x0 after restore); 90/91 names have
  zero in-window pointer references, so no ENTRY-node array lives there.
* `setenv` allocates new strings (free+strdup in ENTER path) instead of
  rewriting in place — matches the HARDWARE_OBSERVED non-rewrite.
* E1's double-field divergence without `storeargs` is incompatible with
  arena==live and fully compatible with arena==stale.
* Not promoted to fact: WHICH heap bytes are the live strdups (nodes +
  strings live outside the two 32k windows, near/above `0x33e2d650` or
  below `0x33e18000`). The minimal experiment below maps exactly this.

## Minimal hardware validation

One session, no boot, no destructive tail, fully restored. Uses the
`test ${VAR} = value` oracle, which reads the htab directly
(`test` handler `0x37e36774` -> `0x37e2b348` (argc==4) -> `0x37e2b1ac` ->
`0x37e2b144` -> `b env_get`). Command length ~32 chars fits the 64-byte
`bulkcmd` buffer. `test X = Y` over bulkcmd is already baselined
(`test 1 = 1` -> `success`).

```text
1. enter burning session, identify stage 16 (per round46 procedure)
2. re-hunt env (addresses are per-boot, never reuse blind)
3. bulkcmd "test ${EnableSelinux} = enforcing"  -> expect success
      (calibrates the htab-reading oracle; also re-proves ENV_READY,
       since expansion + compare only succeed via env_get)
4. bulkcmd "setenv EnableSelinux permissiv"     -> expect success
   bulkcmd "test ${EnableSelinux} = permissiv"  -> success proves
      setenv -> htab -> expansion chain (the round49-effective leg)
5. bulkcmd "setenv EnableSelinux enforcing"     -> restore
   bulkcmd "test ${EnableSelinux} = enforcing"  -> expect success
6. WRITE 9 B permissiv @ re-hunted EnableSelinux value + readback
      (same 1:1 discipline as round49)
   bulkcmd "test ${EnableSelinux} = permissiv"
      -> success: arena string IS the live entry data (Case A for blob)
      -> failed:  arena is a stale copy (Case C confirmed for blob)
7. restore WRITE, readback verify, final oracle sane. No reboot issued.
```

Outcome table (decides the one open point, nothing else):

| setenv visible? | WRITE visible? | meaning |
|---|---|---|
| yes | yes | arena string is live entry data; round49 needs re-explanation |
| yes | no | SHADOW_COPY confirmed; round49 explained (stale oracle) |
| no | — | Case D/E: expansion reads elsewhere; remap required |

No `storeargs`, no `imgread`, no `bootm` in this session: the question is
oracle placement, not transport. Transport (htab `bootargs` -> kernel)
remains a separate, later experiment and is NOT claimed here.

## Alternative cmdline source

Not needed. The mapping shows the environment path is fully functional
code (import -> htab -> expansion -> bootm -> FDT); the failure was the
observation point, not the mechanism. No kernel-exploit investigation was
performed in this round (per scope).

The one related capability found and NOT proposed for use:
`do_env_import` (`env import`, `0x37e581a0`-region) re-imports a
serialised blob into the htab — documented only so a future round knows a
re-import path exists in-code.

## Root relevance

Explicit: this round does not seek root and demonstrates no root. The
bridge status is unchanged in verdicts, clarified in mechanism:

```text
BL33 arbitrary write (HARDWARE_REPRODUCED)
  -> control data actually consumed by boot path: htab content via
     env_get/bootm/fdt (OFFLINE_ONLY code path, device binary)
  -> Linux-visible input: NOT demonstrated (E1 REFUTED for arena poke;
     htab leg UNKNOWN due to stale oracle, never executed)
  -> root: not demonstrated
```

What changed: the next attempt must target the htab (via `setenv` or a
WRITE proven live by the `test ${}` oracle), never the arena bytes, and
must observe via an htab-reading oracle (`test ${}`, then boot), never via
fixed-address blob readback after a `setenv`.

## Artifacts

* This report: `reports/round50-env-authoritative-source.md`
* Analysis scripts: `/tmp/opencode/envptr_scan.py` (throwaway census;
  figures reproduced above, not a repo artifact)
* No binary artifacts created; no device state touched.

## Validation

* `python3 tools/run_tests.py` -> `126 tests, OK` (see session log tail).
* Cross-checked against `reports/CURRENT_STATE.md`,
  `reports/INVALIDATED_HYPOTHESES.md` (#21 kept), `reports/EVIDENCE_MATRIX.md`:
  no verdict flipped; additive notes only (see doc updates).
