# round59 01: exact interface of candidate SMCs (offline, from reports)

Reading basis: `round23-keyman/*`, `round24-key-surface/*`,
`round20-storage-buffer/*`, `round21-share-storage/*`,
`round22-storage-reachability/*`, plus the disasm of `0x37e19ea8` in the
persisted BL33. No device touched. Where the reports diverge from each other,
the disasm rules.

## 1.1 the load-bearing correction: 0xff wrapper registers

The reports describe the wrapper `0x37e19ea8` as
`X0=0x820000ff, X1=buf, X2=len, X3=opt`. That is the INPUT interface of the
wrapper in BL33, not the SMC interface. Disasm of
`reports/round14-bl33-persist/bl33-37e18000.bin`:

```text
0x37e19ea8: mov x7,x0     ; cmd   (entrada BL33)
0x37e19eac: mov x6,x1     ; buf
0x37e19eb0: mov x5,x2     ; len
0x37e19eb4: mov x4,x3     ; opt
0x37e19ec4: mov x0,#0xff / movk x0,#0x8200,lsl#16
0x37e19ecc: mov x1,x7     ; cmd
0x37e19ed0: mov x2,x6     ; buf
0x37e19ed4: mov x3,x5     ; len
0x37e19ed8: smc #0
```

Therefore the SMC 0x820000ff receives:

```text
X0 = 0x820000ff
X1 = cmd      (0x40 = decrypt site1, 0x100 = query site2 on the device)
X2 = buf      (physical address chosen by the host)
X3 = len
X4 = opt
X5..X7 = residue
```

The host address enters EL3 via X2. It is the only candidate with this
property; all the other SMCs below receive the address from within BL31
itself or receive no address at all.

## 1.2 interface matrix

| SMC | name | registers in SMC | C1 (IN) | C2 (OUT) | where the host address goes |
| --- | --- | --- | --- | --- | --- |
| `0x820000ff` | AML_DATA_PROCESS | X0=id, X1=cmd, X2=buf, X3=len, X4=opt | none; payload in X2/X3/X4 | X0=status (via `[x6]` in BL33) | X2 -> raw EL3 (see 02) |
| `0x82000061` | SECURITY_KEY_READ | X0=id; X1/X2/X3 not set up | `[+0]` namelen u32, `[+4]` hint u32, `[+8..]` name | `[+0]` len u32, `[+4..]` blob | `keyman read <n> <addr>`: addr -> `argv[2]` -> `strtoul` -> x20 -> destination buffer of `memcpy` **in BL33**. BL31 only writes to fixed OUT. |
| `0x82000062` | SECURITY_KEY_WRITE | X0=id; X1/X2/X3 not set up | `[+0]` namelen, `[+4]` datalen, `[+8]` flags=0, `[+0xc..]` name + data | none (status in X0) | `keyman write <n> <len> <addr>`: addr -> data source pointer in BL33; copied to C1. Does not go to EL3. |
| `0x82000060` | SECURITY_KEY_QUERY | X0=id; X1/X2/X3 not set up | `[+0]` namelen (str post-inc), `[+4..]` name | `[+0]` u32 word | only via fastboot shim `0x37e94838`; fixed name, no host addr. |
| `0x82000063` | SECURITY_KEY_TELL | same as 0x60 | same as 0x60 | `[+0]` u32 word | same as 0x60. |
| `0x82000065` | SECURITY_KEY_STATUS | same as 0x60 | same as 0x60 | `[+0]` u32 word | table-only (`0x37e75e7c`); no host addr. |
| `0x82000064` | SECURITY_KEY_VERIFY | same as 0x60 | same as 0x60 | `[+0..0x20)` 0x20 B | table-only via trampoline `0x37e8c508`; no host addr. |
| `0x82000023` | GET_STORAGE_IN_BASE | X0=id; no args | - | return X0 = 0x05000000 | none; base read only. |
| `0x82000024` | GET_STORAGE_OUT_BASE | X0=id; no args | - | return X0 = 0x05040000 | none. |
| `0x82000025` | GET_STORAGE_BLOCK_BASE | X0=id; no args | - | return X0 = 0x05080000 | none. |
| `0x82000027` | GET_STORAGE_BLOCK_SIZE | X0=id; no args | - | return X0 = 0x40000 | none. |
| `0x82000020/21` | secmon in/out base | X0=id; no args | - | 0x050fe000 / 0x050ff000 | none. |
| `0x82000028` | SET_STORAGE_INFO | X0=id, X1=1 | - | X0 status | none; `[0x37f60878]=2`. |
| `0x82000069/6a` | NOTIFY_EX / SET_ENCTYPE | X0=id, X1=value | - | X0 status | none; scalar. |

## 1.3 chains and gates (consolidated from reports)

```text
fastboot oem -> cb_oem 0x37e95630 -> run_command 0x37e5e968
  -> keyman 0x37e74290 -> find_cmd tbl 0x37f5e4f8
     -> do_keyman_write 0x37e749ac -> key_manage_write 0x37e7430c
        -> amlkey_write 0x37e8c450 -> low writer 0x37e8bd10 -> C1 -> SMC 0x62
     -> do_keyman_read 0x37e750c4 -> key_info_query 0x37e74c0c (size gate)
        -> key_manage_read 0x37e74d18 -> amlkey_read 0x37e8c3e4
        -> low reader 0x37e8bdc8 -> C1 -> SMC 0x61 -> C2 -> caller RAM
```

Observed gates: DTS membership (19 names, `round24-key-surface/01`),
`type_resolve 0x37e7414c`, per-type validators (mac/sha1/hdcp2),
device exist/query/tell, exact want-ret in hdcp2 slots. `key-permit` is not
applied in BL33 (`round24-key-surface/04`). `secure_boot_set` is rejected
on read and diverted to `setenv` on write by strcmp, not by bit.

`keyman read` is a writer to host-chosen destination RAM with CONTENT and
SIZE controlled by the secure world (`round24-key-surface/05`,
`round23-keyman/06`): it is not an arbitrary write. `keyman write` is limited
by formats and by the 33 B truncation of `oem`.

## 1.4 what the reports do NOT prove

- C1/C2 content is opaque; plaintext vs ciphertext not decided.
- IN/OUT capacity does not exist in BL33; `0x10000` is heap staging,
  `0x40000` is the reported BLOCK. Do not cite as a C1/C2 limit.
- the SECURITY_KEY_* names come from DTB/bl31_apis.h; the semantics here come
  from callers and dataflow, not from the names.
- the BL31 handler itself was not audited in these rounds. That is what 02 does,
  using the family reference (with the version caveat).
