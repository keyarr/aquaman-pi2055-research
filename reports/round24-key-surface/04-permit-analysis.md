# round24-key-surface 04: key-permit audit

## 4.1 what is parsed

parser `0x37e757ec`, region `0x37e75d4c..0x37e75ddc` (disassembled this round):

```text
str wzr,[x19,#0x5c]            ; clear
... memmem-equivalent 0x37ea22e4 over the key-permit blob ...
cbz -> skip; else ldr w0,[x19,#0x5c]; orr #1; str (read)
cbz -> skip; else orr #2 (write)
cbz -> skip; else orr #4 (del)
str w25,[x19,#0x50]            ; index
```

bit assignment CONFIRMED: 1=read, 2=write, 4=del. DTS ground truth:
18 keys `read,write,del` or `read,write`; `secure_boot_set` = `write` only.

## 4.2 consumer search (scoped, not global grep noise)

scope: the exact path `keyman -> key_manage_* -> key entry`
(`0x37e74290, 0x37e749ac, 0x37e750c4, 0x37e75304, 0x37e7430c, 0x37e74c0c,
0x37e74d18, 0x37e73380, 0x37e73880, 0x37e7394c, 0x37e73aa0, 0x37e754b4,
0x37e75590, 0x37e75524, 0x37e75e7c, 0x37e7609c, 0x37e761f0, 0x37e762f4`
plus their callees). method: `ldr *,[*,#0x5c]` scan over the swept
instruction list (`tools/bl33_audit.py` Img, 483328 insns).

result: inside `0x37e73000..0x37e77000` (all key code) the ONLY `#0x5c`
loads are the three parser sites above (`0x37e75d88/0x37e75dac/0x37e75dd0`,
all inside `0x37e757ec`). zero loads in `do_keyman_read`,
`key_manage_read`, `device_read`, `key_info_query`, `type_resolve`,
`len_lookup`, both vector impls. no `tst/and/cbz` on a permit register,
no mask/compare/branch/dispatch keyed off `+0x5c` on the path.

the other `#0x5c` loads in the image (`0x37e2f298, 0x37e65c74, ...`)
are in unrelated functions (different structs, e.g. stack slots
`[x29,#0x5c]` or other objects); none is reached from the keyman path
(no bl edge). not counted as consumers; listing them as hits would be
the "global random reference" error the brief forbids.

additionally: `0x37e75524` (the `+0x58` gate used by `0x37e75590`)
loads `+0x54`/`+0x58`, never `+0x5c`. the `secure_boot_set` refusal is a
`strcmp(name,"secure_boot_set")` in `0x37e761f0/0x37e762cc/0x37e7637c`,
not a bit test. CONFIRMED distinct mechanism.

## 4.3 verdict

```text
key-permit enforcement in BL33 = ABSENT (scoped negative, HIGH confidence)
key-permit enforcement anywhere = UNKNOWN (secure-world side may check;
  BL31 image not audited here; DTS still ships the bits)
```

do NOT cite `key-permit` as a BL33 gate. the observable BL33 gates are:
DTS membership, type_resolve, per-type shape validators, device
exist/query/tell gates, exact want-ret on fixed slots. `secure_boot_set`
write-only is enforced by code name-checks (read refused, write diverted),
which happens to agree with its `write`-only permit but is not a
permit-bit check.
