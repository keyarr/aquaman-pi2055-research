# round22 01: command reachability (run_command universe vs storage)

image: `reports/round14-bl33-persist/bl33-37e18000.bin`, base `0x37e18000`
(sha `664fb34a...`). method: `tools/bl33_audit.py cmds/callers/refs/fstrings`
+ capstone disasm of bytes on disk. static only. no device, no reads, no SMC.

reused: 80-entry cmd_tbl census from round15 (`reports/round15-bl33-interface/01_cmdsurface.txt`).
not repeated here except the storage-relevant rows. full list stays in round15.

## 1.1 host entry point (proven, reused)

```
host
 -> fastboot oem <text>          (USB, f_fastboot.c)
 -> cb_oem 0x37e95630
 -> run_command 0x37e5e968       (bl at 0x37e956a0, code-exact)
 -> cmd_tbl dispatch (80 slots)  (find_cmd pattern in each dispatcher)
 -> handler (argc, argv)
```

`cb_oem` frame: `0x50` B, local buf `x29+0x20`, `0x30` B to frame end.
copy is `strnlen(cmd,0x20)+1` = max 33 B (`0x37e95654..0x37e9566c`).
consequence: every `oem <text>` longer than 32 chars is truncated before
`run_command`. short storage commands fit (see 1.4), long ones do not.
this is a transport constraint, not a lock gate.

lock gate: NONE on any U-Boot command. the `0x37e9593c` gate covers
fastboot `flash`/`erase` only (round15). no handler below branches on it.
`LOCK = no` for every row.

## 1.2 prioritized command table (storage-adjacent names first)

`handler` = cmd_tbl address. `sub` = dispatch target for the subcommand that
matters. `lock` is always `no` (see above). `reach` = does a `bl`-exact path
(+ one documented `find_cmd+blr` dispatch hop) reach a C1/C2 writer/reader.

```text
command    handler     sub-dispatch                  sub -> storage fn          reach via run_command
keyman     0x37e74290  find_cmd tbl 0x37f5e4f8       write 0x37e749ac -> 0x37e7430c -> 0x37e8c450 -> 0x37e8bd10 (SMC 0x62)  YES
keyman     0x37e74290  find_cmd tbl 0x37f5e4f8       read  0x37e750c4 -> 0x37e74d18 -> 0x37e8c3e4 -> 0x37e8bdc8 (SMC 0x61)  YES
keyman     0x37e74290  find_cmd tbl 0x37f5e4f8       query 0x37e75304 -> 0x37e74ba4/0x37e75254/0x37e74c0c (NOT amlkey_*)   NO (no C1/C2 edge)
store      0x37e33900  find_cmd tbl 0x37ee62f0       key   0x37e33a38 -> run_command("%s %s %s 0x%x") (amlnf fmt, NOT amlkey_*)  NO
keyunify   0x37e73c84  inline strcmp ladder          NO bl to key_manage_*/amlkey_* (backends 0x37e73694/0x37e73880/0x37e7394c/...)  NO (via bl)
efuse_user 0x37e72ef0  OTP sharemem path             efuse SMCs 0x30..0x33, never 0x60..65 / never [0x37fbde60/58]  NO
query      0x37e56224  soc-info helper               no SMC, no share-slot load (memcpy loop over local buf)  NO
env/run    0x37e57d6c / 0x37e5ea04  sub-dispatch / getenv+run_command  generic script composition, no direct storage edge  INDIRECT only (see 05)
mmc/store-write/gpt/update  various                 eMMC/nand paths, no C1/C2/SMC60..65 edge  NO
```

all other 60+ commands: no `bl` chain to any of
`0x37e8bd10/0x37e8bdc8/0x37e8be98/0x37e8bf3c/0x37e8bfe0/0x37e8c084`
within 10 `bl` hops (systematic BFS, section 2), and no `find_cmd` table
in their handlers points at a storage sub-handler. classified `NO`
(each individually `internal-only` / unrelated subsystem).

## 1.3 aliases

`keyman`, `keyunify`, `store`, `query`, `env`, `run` have no cmd_tbl aliases
(one slot each in the 80-entry census). subcommand names (`read`/`write`/
`query`/`key`) are second-argv tokens resolved by `find_cmd`, not separate
top-level commands. `env save` is the only persistence alias (`saveenv`
does not exist as a top-level command, round15 A.1).

## 1.4 argv shape on the two YES paths (summary, detail in 02)

```
oem keyman write <name> <hexdata> ...   (needs argc'<3 fail => original argc>=5 after strip)
  handler 0x37e74290: argc-1, argv+1 -> do_keyman_write 0x37e749ac
  0x37e749ac: argv'[1]=name(x23), argv'[2]=data(x20); hex/ascii ladder, then
  key_manage_write 0x37e7430c -> amlkey_write(name ptr, data ptr, datalen, flags=0)

oem keyman read <name> <addr> [<len>]   (argc'>2 required)
  handler 0x37e74290: argc-1, argv+1 -> do_keyman_read 0x37e750c4
  0x37e750c4: argv[1]=name(x22), argv[2]=simple_strtoul->addr(x20)
  key_manage_read(name, addr, ...) -> amlkey_read(name, buf=addr, ...)
```

fit check (33 B budget): `keyman read mac 1080000` = 25 chars after `oem `,
FITS. `keyman write ...` with hex payload quickly exceeds 32 chars and is
truncated: write is graph-reachable but argv-long writes are transport-cut.
recorded as constraint, not as refutation.

## 1.5 what this file does NOT claim

- no eMMC/nand `store write` / `mmc write` finding is a C1/C2 finding.
- `query` (0x37e56224) sharing a name with SMC `SECURITY_KEY_QUERY` is
  coincidence: the handler never issues SMC nor touches the share slots.
- `keyunify write` reaching storage via `bl` is REFUTED (no edge); any
  function-table path is UNKNOWN (section 2.5), not YES.
