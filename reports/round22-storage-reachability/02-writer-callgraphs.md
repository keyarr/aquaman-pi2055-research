# round22 02: writer callgraphs (the six C1 writers)

slot: `[0x37fbde60]` = IN base (`0x05000000` at runtime, round20).
all six stage via `ldr xN,[slot]` + `strlen` (`0x37eaad30`) + `memcpy`
(`0x37eaaeec`), then bare `smc #0` with no register args (round21 01/02).
this file only climbs from each writer to a command handler.

notation: `A <- B` means `B` contains a `bl A` (code-exact site given).
`=>` means a `find_cmd` + `blr x4` dispatch hop (table entry given).

## 2.1 0x37e8bd10 (write -> SMC 0x82000062) : directly command-reachable

```
0x37e8bd10 (x0=name, x1=data, w2=datalen, w3=flags; header [IN+0]=namelen,
            [IN+4]=datalen, [IN+8]=flags, memcpy name+data; SMC 0x62)
 <- 0x37e8c484 in amlkey_write 0x37e8c450 (sole bl caller; args pass through:
     x19=x0 preserved into the bl, w20=w2 preserved; fail path prints, ok path
     continues to store_key_write backend at 0x37e8c4c8)
 <- 0x37e7430c key_manage_write at 3 sites + 0x37e75e7c secukey_write at 0x37e75f20
     sites in 0x37e7430c:
       0x37e748a0: x0=0x37ed74f4 "hdcp2lc128", x1=x23+4,  w2=0x24, w3=0 (FIXED name)
       0x37e748f8: x0=0x37ed7535 "hdcp2key",   x1=x23+0x28,w2=0x35e,w3=0 (FIXED name)
       0x37e7494c: x0=x21 (caller name),       x1=x23,    w2=4,   w3=0 (CALLER name)
     x21/x23 derive from key_manage_write args (x0=name-ish, x1=data-ish);
     the generic third site is the one the shell path hits with host argv.
 <- 0x37e749ac do_keyman_write (bl 0x37e74b6c: x0=x23=argv'[1] name,
     x1=x19=data buf, w2=w21=len)  [shell path]
    + 0x37e8212c optimus_download_key (bl 0x37e822d4 / 0x37e823b8: DTB/usb key
      material, NOT argv)  [burning/usb path]
 <- 0x37e74290 keyman (cmd_tbl) => tbl 0x37f5e4f8 "write"/maxargs 4/->0x37e749ac
     dispatcher proof: adrp x1,0x37f5e000 +0x4f8; mov w2,#5; bl find_cmd
     (0x37e5eddc); blr x4 with (argc-1, argv+1). table dump:
     +0x588 "write"/4/0x37e749ac, +0x558 "read"/4/0x37e750c4,
     +0x5b8 "query"/3/0x37e75304, +0x4f8 "init", +0x528 "exit".
 <- run_command 0x37e5e968 (cmd_tbl lookup of "keyman")
 <- cb_oem 0x37e95630 (bl 0x37e956a0) <- fastboot oem <- host
```

argv->C1 on this path: `argv'[1]` (name) -> `strlen` -> `[IN+0]` + memcpy;
`argv'[2]`-derived data ptr + len -> `[IN+4]` + memcpy. host controls name
pointer and data pointer/len (category C), subject to the hex/ascii ladder
in `0x37e749ac` (`"hex"` at 0x37ed7572 branch: `strlen/2` + `keyman_hex_ascii_to_buf`
0x37e73404; ascii branch; numeric branch with `simple_strtoul`) and the
`0x386`-loop cap. confidence: graph HIGH, argv-control MEDIUM (constrained,
truncated by oem 33 B).

classification: **directly command-reachable**. the "no fastboot/usb caller"
remark in round21 is true for `bl` callers but irrelevant: reachability runs
through `run_command`, not through fastboot/usb code references.

table-only extra edge (not command): `0x37e75e7c secukey_write -> 0x37e8c450`
has NO `bl` caller itself (function-table target, section 2.5). does not
affect the YES above.

## 2.2 0x37e8bdc8 (read -> SMC 0x82000061) : directly command-reachable

```
0x37e8bdc8 (x0=name, x1=caller_buf, w2=hint, x3=caller_len_ptr;
            header [IN+0]=namelen, [IN+4]=hint, memcpy name; SMC 0x61;
            OUT parse: len=[OUT+0], *caller_len=len, memcpy(caller_buf, OUT+4, len))
 <- 0x37e8c414 in amlkey_read 0x37e8c3e4 (sole bl caller; x3=sp+0x20 len slot)
 <- 0x37e74d18 key_manage_read at 3 sites (0x37e74f84/0x37e74fd8/0x37e7502c,
     fixed names "?" / "hdcp2key" 0x37ed7535 / "hdcp2lc128" 0x37ed74f4 for the
     hdcp branch; generic path passes caller name/buf through)
    + 0x37e7609c secukey_read at 0x37e760f8 (table path, no bl caller above it)
    + 0x37e94838 fastboot shim at 0x37e94888 (x0=fixed "secure" region name at
      0x37edec8d-ish, x1=0x37fbdf48 bss buf; read-side trigger, NOT run_command)
 <- 0x37e750c4 do_keyman_read (bl 0x37e75158: x0=x22=argv[1] name, x1=x20=argv[2]
     parsed addr)  [shell path]
    + 0x37e8240c download-key read (bl 0x37e8248c) <- 0x37e79ff0 <- burning/usb
 <- 0x37e74290 keyman => tbl 0x37f5e4f8 "read"/4/0x37e750c4 (same dispatcher)
 <- run_command <- cb_oem <- host   (same as 2.1)
```

argv->C1: `argv[1]` name -> `[IN+0]` + memcpy (host picks which key name is
staged; the staged bytes are the name, not bulk host payload). argv->C2:
`argv[2]` addr -> caller_buf; OUT `len+payload` lands at that RAM address.
OUT consumer: caller buffer only; no `printf` of payload on this path, no
`setenv`, no fastboot response. exfiltration off this path needs a second
primitive (out of scope). categories: B (host picks handler) + C (host picks
name + dest addr) => host-reachable. graph HIGH, control MEDIUM-HIGH.

classification: **directly command-reachable** (keyman read). the fastboot
shim is a second, independent host path (fastboot, not oem) documented in 03.

## 2.3 0x37e8be98 (query -> SMC 0x82000060) : NOT command-reachable

```
0x37e8be98 ([IN+0]=namelen + name; SMC 0x60; *caller=[OUT+0] word)
 <- 0x37e8c324 in amlkey_isexsit 0x37e8c2ec (sole bl caller)
 <- 0x37e94850 in 0x37e94838 fastboot shim (sole bl caller of amlkey_isexsit)
 <- 0x37e948a8 download-key dispatcher + 0x37e95ecc fastboot dispatcher
```

no `bl` path from any of the 80 command handlers. `keyman query 0x37e75304`
does NOT call this function: it calls `0x37e74ba4 / 0x37e75254 / 0x37e74c0c`
(exist/size helpers), none of which `bl` to `amlkey_isexsit` (caller census:
exactly one caller, the fastboot shim). `query 0x37e56224` (top-level) never
touches the share slots.

classification: **internal-only (fastboot-only)**. `unknown` only in the
trivial sense that an undiscovered indirect call could exist; `bl`-exact
verdict is NO for `run_command`.

## 2.4 0x37e8bf3c (status -> SMC 0x82000065) : NOT command-reachable

```
0x37e8bf3c ([IN+0]=namelen + name; SMC 0x65; *caller=[OUT+0])
 <- 0x37e8c1a4 in amlkey_get_attr 0x37e8c16c (sole bl caller)
 <- 0x37e8c364 in 0x37e8c35c (sole bl caller)
 <- 0x37e76088 in 0x37e76080 (sole bl caller)
 <- 0x37e760b4 in 0x37e7609c secukey_read (table target, no bl caller)
```

no command-handler ancestor via `bl`. classification: **internal-only
(table-gated)**. NOT reachable via `run_command` on demonstrated edges.

## 2.5 0x37e8bfe0 (tell -> SMC 0x82000063) : NOT command-reachable

```
0x37e8bfe0 ([IN+0]=namelen + name; SMC 0x63; *caller=[OUT+0])
 <- 0x37e8c3ac in amlkey_size 0x37e8c374 (sole bl caller)
 <- 0x37e94864 in 0x37e94838 fastboot shim (sole bl caller of amlkey_size)
 <- fastboot dispatchers (same as 2.3)
```

same verdict as query: **internal-only (fastboot-only)**, NO via `run_command`.

## 2.6 0x37e8c084 (verify -> SMC 0x82000064) : NOT command-reachable via bl

```
0x37e8c084 ([IN+0]=namelen + name; SMC 0x64; memcpy(caller, OUT, 0x20))
 <- NO bl caller in the image (caller census: none)
 <- 0x37e8c508 trampoline (b 0x37e8c084; reached by bl 0x37e75f78 in 0x37e75e7c)
 <- 0x37e75e7c secukey_write: NO bl caller (function-table target)
```

the only demonstrated caller chain is table-gated and its root has no `bl`
caller either. pointer scan finds no 8 B slot holding `0x37e8c084`
(`ptrs` empty); the trampoline `0x37e8c508` is referenced only by the `bl`
at `0x37e75f78`. the table that holds `0x37e75e7c/0x37e7609c` (secure-key
ops vector) was not resolved to a command handler via `bl`; treat as
**unknown (table-only)**, which for the round question counts as NOT
demonstrated via `run_command`.

## 2.7 closed-set note

`bl` callers above are exhaustive per `bl33_audit.py callers` (opcode-exact).
dispatch hops (`keyman => sub`) are proven by the `find_cmd` call + table
dump, not inferred. BFS depth 10 from every writer over pure `bl` edges
finds ZERO cmd_tbl handlers as ancestors precisely because the one real hop
is the `find_cmd+blr` dispatch; adding that single documented hop yields the
two YES paths and no others.
