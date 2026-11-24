# round57 FDT final identity (offline only, 2026-10-02)

Scope: BL33 real `reports/round14-bl33-persist/bl33-37e18000.bin` + stock
`boot.img` header + `boot_unpack/kernel|second` + `artifacts/aquaman.dtb` +
`reports/round54-offline-fdt-path/running_config.gz` + round55/round56 artifacts.
No hardware. No boot. No `imgread`. No `bootm`. No WRITE. No env change.
No repeat of selinux/wificountrycode tests.

Question: where does the FDT modified by `fdt_chosen()` stop being the same
content Linux receives in `x2`?

Short answer: no static point found. Pointer identity is now closed as the
same field end to end. Content at handoff stays UNKNOWN for runtime reasons.
There is one real copy, it sits before `fdt_chosen`, not after, so it cannot
explain the revert. Everything after `fdt_chosen` is in place on the same blob.

## Executive conclusion

Is there a static point in BL33 that explains the FDT revert? NO.

What closed this round (all OFFLINE_ONLY, device binary):

* `0x37e5bda4` is `boot_relocate_fdt` (U-Boot standard shape, PROVEN by
  strings + call shape + tail stores). It loads `x19=[ft_addr]`,
  `x23=*ft_len_ptr`, `x21=fdt_high-or-size`, decides in place vs move,
  copies via `fdt_open_into`-family (`0x37ea3d28` / `0x37ea2bec`) or
  `lmb`-alloc move, then `str x19,[x25]` (`ft_addr`) + `str x21,[x24]`
  (`ft_len`) + `bl 0x37e28510` (publish to `fdtaddr`). Three callers only:
  `0x37e5b854` (Linux path), `0x37e26058` (do_bootm_states FIT path),
  `0x37e264ac` (bootvx path). Details in
  `reports/round57-fdt-final-identity/reloc_37e5bda4.txt`.
* `[images+0x100]` (`ft_addr`) and `[images+0x108]` (`ft_len`) are not
  constant across boot. They are first populated in `bootm_load_os`
  (`0x37e5ba90` / `0x37e5bac8` into global `0x37f723e8`), then rewritten by
  the reloc tail. After the reloc, the same field value is passed to
  `fdt_chosen` (`0x37e5b864 ldr x1,[x19+0x100]` -> `0x37e5c344`) and later
  loaded as `x2` (`0x37e21318 ldr x2,[x19+0x100]`). No store to that field
  exists between `fdt_chosen` return and the `x2` load in the static chain.
  Pointer identity post-reloc is PROVEN same field.
* After `fdt_chosen`, the same `x19` blob goes through `arch_fixup_fdt`
  (`0x37e211f8` -> `0x37e298c0`, memory banks only), board setup
  (`0x37e29ac8`, `/aliases` + `ethaddr`/`ethernet%d` only), totalsize/pack
  (`0x37ea3c38` + `0x37e29c70`, in place `str [x19+4]`), `0x37ea3d28`,
  `0x37e295e8` (mem reserve move, in place), `0x37e5c31c` (returns 1).
  No `memcpy`/`memmove`/decrypt/decompress/`fdt_setprop(bootargs)` in that
  tail. Scoped PROVEN negative by callee disasm + strings.
* No second writer of `/chosen/bootargs` exists in the Linux path. Census of
  `fdt_setprop@0x37ea28c4` (8 callers): 1x `fdt_chosen` bootargs, 1x `fdt`
  command handler (not in bootm path), 2x memrsv, 2x arch mem fixup
  (`device_type`/`reg`), 1x `libfdt fdt_setprop(): %s` error path, 1x other.
  `do_bootvx_fdt@0x37e2646c` writes the same env string, different path.
  No C code emits `enforcing`/`normal`/`US` into FDT. `d00dfeed` occurs 0x in
  BL33 (PROVEN, no embedded blob).
* `artifacts/aquaman.dtb` (58280 B, `d00dfeed`, totalsize==filelen, 0x `chosen`,
  0x `bootargs`) cannot be the final blob as dumped. Final must contain
  `/chosen` if fixup ran. Byte equality with handoff is UNKNOWN by construction.
* Three runtime values stay UNKNOWN, so bytes at `eret` stay UNKNOWN:
  `ft_len` at the `0x37e21248` gate on the `bootm 0x1080000` path,
  `fdt_setprop` return in `fdt_chosen` on that boot, reloc destination and
  lmb results. Error paths hang (`FDT creation failed`, `arch-specific fixup
  failed`, `/chosen node create failed`), so a successful stock boot is
  INFERRED success, never PROVEN statically.

Classification: `SAME_OBJECT_UNKNOWN_BYTES` (defined below). Cases B/C/D as
asked are all negative in the static chain. Overall content divergence stays
`UNKNOWN` (Case E), narrowed to runtime-or-Linux, not to a BL33 copy/swap.

Artifacts: `reports/round57-fdt-final-identity/` (28 txt: disasm, xrefs,
callers, strings, provenance, markers). Reused round55 traces + `boot.img`
header + `aquaman.dtb` + `running_config.gz`.

## Pointer flow

Authoritative chain (all PROVEN disasm, OFFLINE_ONLY):

```text
bootm @0x37e24c00
 -> do_bootm_states @0x37e255c8 (x3=images stack, x5=global 0x37f723e8, w4=0x70f)
    -> bootm_load_os @0x37e5b880 region: str ft_len/ft_addr into 0x37f723e8
       0x37e5ba90 str x0,[x1+0x108], 0x37e5bac8 str x2,[x1+0x100] (x1=0x37f723e8)
       PROVEN, file load_os_store_37e5ba80.txt
    -> fdt selector @0x37e5bf48 (FIT multi vs legacy vs raw, strings 0x37ed147d/0x37ed133f/0x37ed14bb/0x37ed14f4)
       INFERRED name, PROVEN branches
    -> 0x37e21378 OS dispatch (via table 0x37eb5658 slot 0x37e21378, INFERRED edge, PROVEN slot)
       -> 0x37e2122c gate: env_get bootargs (result discarded) + ldr x0,[x19+0x108]; cbz hang
          PROVEN, file gate_37e2122c.txt
       -> 0x37e5b800 stage: ldr ft_len, ldr ft_addr, bl 0x37e5bd08, bl 0x37e5b6cc, bl 0x37e5bda4, bl 0x37e5c324
          PROVEN, file fixup_stage_37e5b800.txt
          -> 0x37e5c324 image_setup: mov x19,x1 (= [images+0x100] reloaded at 0x37e5b864)
             bl fdt_chosen@0x37e5c344, bl arch@0x37e5c35c, bl board@0x37e5c37c, pack/move tail
             PROVEN, file image_setup_37e5c324.txt
             -> fdt_chosen @0x37e297b8: check_header, add_subnode chosen, env_get bootargs,
                fdt_setprop(fdt,node,bootargs,s,len+1)@0x37e29840
                PROVEN, file fdt_chosen_37e297b8.txt
 -> 0x37e21284 entry: ldr x0,[x19+0xe8] (entry), ldr x2,[x19+0x100] (FDT), x1=0xf81
    PROVEN, file entry_37e21284.txt (ARM64 path only; 32-bit fallback blr x21 not taken for aquaman)
 -> 0x37e19264: x22=x2 preserved, spsr/elr set, x0=0, x1=x21, x2=x22, eret EL2->EL1
    PROVEN, file eret_37e19264.txt, no SMC on handoff
```

Graph asked for:

```text
[images+0x100]
  +-> bootm_load_os store (first population, global 0x37f723e8)
  +-> fdt selector read/write (0x37e5bf48 region, 0x37e5c024/0x37e5c02c)
  +-> reloc tail rewrite (0x37e5bf1c str x19,[x25], PROVEN update)
  +-> fdt_chosen arg (0x37e5b864 reload, PROVEN same field)
  +-> final handoff x2 (0x37e21318 reload, PROVEN same field, no store between)
```

Pointer constant? NO across whole boot (two PROVEN rewrites before fixup).
Pointer constant between `fdt_chosen` and `x2`? YES (PROVEN, no store in
between in static chain). If it changes at runtime it needs an unmapped
writer; none found in the audited chain.

Full `[images+0x100]/[0x108]` xref table (84 sites, STACK vs STRUCT marked)
is in `images_0x100_0x108_xrefs.txt`. STRUCT sites that matter are listed
above; the rest are stack slots `[x29/sp+0x100]` (not images), `ldrh/ldrb`
peripheral windows, or other structs. Callers census for all key functions is
in `callers_census.txt`.

`ft_addr=0x100` / `ft_len=0x108` offsets: PROVEN by FIT arithmetic + consistent
`ldr/str [x+0x100]/[x+0x108]` pairs across load/reloc/gate/handoff (same as
round55, re-verified here, not re-derived from reference tree alone).

Concrete value at handoff: UNKNOWN. Depends on `bootm_load_os` header parse
of the stock AMLSECU container at `0x1080000` + `lmb` alloc + `fdt_high`
(`0x20000000`) handling. No static store chain yields a numeric address.
Not invented.

## FDT candidates

| id | address / blob | size | origin | writer | reader | relocated? | copied? | FIT payload? | final DTB? | relation to images+0x100 |
|----|---|---|---|---|---|---|---|---|---|---|
| FDT-A | runtime, from image at `0x1080000` header parse | UNKNOWN (header `0x959000` container, encrypted) | `bootm_load_os` computes from `x19` image header + alignment, stores to `0x37f723e8+0x100/0x108` | `0x37e5ba90/0x37e5bac8` | selector `0x37e5bf48`, reloc `0x37e5bda4` | no (source) | no | selected by `0x37e5bf48` FIT/legacy branch, INFERRED | no (pre-reloc) | initial value of the field |
| FDT-B | runtime, post-reloc blob (`x19` after `0x37e5bda4`, `str [x25]`) | `*ft_len` (`x21`), 0x1000-aligned via lmb | `boot_relocate_fdt` in-place (`Using in place`) or move (`Loading to %p`) per `fdt_high` | reloc tail + `0x37e28510` (`fdtaddr`) | `fdt_chosen`, arch/board/pack tail, `x2` | yes (this is the reloc product) | yes iff move path taken (`fdt_open_into`-family `0x37ea3d28`/`0x37ea2bec` + `memmove@0x37eaaf50`), else in place | no (already extracted) | YES, this is the blob `fdt_chosen` modifies and `x2` delivers (PROVEN same field) | the field after tail rewrite |
| FDT-C | `0x01000000` dump, `artifacts/aquaman.dtb` | 58280 B, totalsize==filelen | RAM read in session where `bootm` never ran | U-Boot `dtb_mem_addr` staging (env `0x1000000`, htab/arena agree per round54) | `dtc` offline only | UNKNOWN | UNKNOWN | no | NO as dumped (0x `chosen`, 0x `bootargs`; final must have `/chosen` if fixup ran) | not proven equal to A or B; do not use as oracle for final bytes |
| FDT-second | `boot.img` second `0xf000` @ `0xf00000`, `boot_unpack/second` 61440 B | 61440 B | boot image second area, ciphertext (`4db07057...`, no `d00dfeed`) | eMMC/imgread to RAM | `bootm_load_os` header parse (as candidate, not as FDT) | no | no | not FDT (PROVEN non-FDT ciphertext, not `dtbo` plaintext) | no | none (do not conflate with `ft_addr`) |
| FDT-fw | `dt.img` firmware | 59424 B | firmware partition | unknown (encrypted) | none offline | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | none proven |

No two blobs are claimed equal by address alone. A vs B differ by reloc by
design; B is the only one both modified and delivered. C vs B differ
structurally today (missing `/chosen`); C may equal pre-bootm A in content,
but that is UNKNOWN without runtime `ft_len`/dest read.

`d00dfeed` in BL33: 0 hits BE and LE (PROVEN full-image scan). No embedded
DTB. `/chosen`: 3 hits, all strings (`0x37ec09d0` `/chosen`,
`0x37ed1518` error suffix, `0x37ee5608` help text), no blob. `bootargs`: 31
hits, all defenv/scripts + `0x37ebf453` name, no blob. `totalsize`: 1 hit
(`0x37ec1de9` format string). Full census in `strings_census.txt`.

## Relocation / copy analysis (0x37e5bda4)

Function: `0x37e5bda4`..`0x37e5bf44` (`ret` at `0x37e5bf44`), PROVEN bounds.
U-Boot `boot_relocate_fdt` shape (name INFERRED, behavior PROVEN).
Callers (PROVEN via `bl` scan + `bl33_audit.py callers`): `0x37e5b854`
(inside `0x37e5b800`, the Linux path), `0x37e26058` (inside `0x37e255c8`
do_bootm_states FIT path), `0x37e264ac` (inside `0x37e2646c` bootvx path).
Callees: `fdt_check_header@0x37ea14e0` (PROVEN magic compare),
`env_get@0x37e58920` (`fdt_high@0x37ec060e`, PROVEN),
`simple_strtoul@0x37eac21c`-family, `lmb`-family (`0x37e5af14`/`0x37e5ae80`
read `bootm_mapsize`/`bootm_low`, `0x37ea3e54`/`0x37ea3ea0` alloc,
`0x37e5af44` memmove-wrapper guard), `fdt_open_into`-family
(`0x37ea3d28`/`0x37ea2bec`, INFERRED names, PROVEN copy semantics),
`memmove@0x37eaaf50` (PROVEN byte loop), `printf`-family
(`0x37e593c8`/`0x37e59378`), error helper `0x37e5bcd0`,
publish `0x37e28510` (`fdtaddr@0x37ec1b26` + global `0x37f72a90`).

Parameters (PROVEN by call sites + prologue moves):

* `x0` = scratch/lmb struct (`x20` at call sites: `x19+0x140` in Linux path,
  `x21` in FIT path, `x20` in bootvx path). Not the FDT itself.
* `x1` = pointer to `ft_addr` field (`&images+0x100`; at `0x37e5b84c` it is
  `add x1,x19,#0x100`, at `0x37e26050` same, at `0x37e264a0` it is
  `x21=x19+0x100`). Saved as `x25`.
* `x2` = pointer to `ft_len`/size input (`&images+0x108` or stack saved len;
  at `0x37e5b850` it is `add x2,x29,#0x20` after `str x0,[x29+0x20]` saved
  original `ft_len`). Saved as `x24`.

Key pointer flow inside (PROVEN disasm, file `reloc_37e5bda4.txt`):

| offset | instruction | base | destination | interpretation |
|---|---|---|---|---|
| `0x37e5bdb4` | `ldr x0,[x2]` | `x2`=len-ptr | `x0`=old len | load `*ft_len`; `cbz` empty-len path returns `w22=0` without rewrite |
| `0x37e5bdcc` | `ldr x19,[x1]` | `x1`=addr-ptr | `x19`=old FDT | load `ft_addr` value; this is the blob under test |
| `0x37e5bddc` | `bl fdt_check_header` | `x19` | `w22`=rc | `w22!=0` -> `image is not a fdt@0x37ed1279` -> `bl 0x37e5bcd0`, `w22=1`, return (no store) |
| `0x37e5bdf4` | `ldr x23,[x24]` | `x24`=len-ptr (saved `x2`) | `x23` | reload len/base for alloc math |
| `0x37e5be00` | `add x21,x23,#3,lsl#12` | `x23` | `x21` | candidate size/addr (page-rounding path); `x21` becomes new `ft_len`/dest-size downstream |
| `0x37e5be04` | `bl env_get(fdt_high)` | rodata `fdt_high` | `x0`=str or 0 | `cbz` -> no-`fdt_high` path (`bl 0x37e5af14`+`0x37e5ae80`, lmb-based alloc + `bl 0x37ea3e54`) |
| `0x37e5be14` | `bl simple_strtoul` | `x0`=str | `x0`/`x3` parsed addr | parse `fdt_high`; `cmn x3,#1` / `b.ne` selects in-place vs move |
| `0x37e5be30` | `bl 0x37ea3d28` | `x19`=old, `x21`=dest/size | `x0` | copy/open_into attempt on one branch (PROVEN copy call, name INFERRED) |
| `0x37e5be48`/`0x37e5be60` | `bl 0x37ea3e54` / `bl 0x37ea3ea0` | lmb + `x1`/`x2` | `x20`=new dest | alloc destination when `fdt_high` present or absent (two sub-branches) |
| `0x37e5bea8` | `str w0,[x19+4]` | `x19`=old FDT | header `totalsize` | in-place branch updates old header before publish (`rev w0,w21` first) |
| `0x37e5bef0` | `bl 0x37ea2bec` | `x0`=old, `x1`=new, `w2`=size | `w0`=rc | final open_into/move verify (PROVEN call, name INFERRED); `cbz` success continues, else `fdt move failed@0x37ed132f` -> `w22=1` |
| `0x37e5bf18` | `mov x19,x20` | `x20`=new dest | `x19`=new FDT | on move path, authoritative pointer switches to destination |
| `0x37e5bf1c` | `str x19,[x25]` | `x25`=`&ft_addr` | `*ft_addr`=new FDT | PROVEN field rewrite; this is the update round55 inferred, now PROVEN shape |
| `0x37e5bf20` | `str x21,[x24]` | `x24`=`&ft_len` | `*ft_len`=new size | PROVEN field rewrite |
| `0x37e5bf28` | `bl 0x37e28510` | `x19` | global `0x37f72a90` + env `fdtaddr` | publish (PROVEN store + `b setenv-hex` shape) |
| `0x37e5bf2c` | `mov w0,w22` | `w22` | return code | `0`=success, `1`=move/check failure; callers `cbnz` to error, else continue |

Strings proving branch identity (all PROVEN addrs): `fdt_high@0x37ec060e`,
`image is not a fdt@0x37ed1279`, `Failed using fdt_high@0x37ed128c`,
`allocation error@0x37ed12b8`, `Using in place@0x37ed12d8`,
`Loading to %p@0x37ed1305`, `fdt move failed@0x37ed132f`.
`bootm_low@0x37ed0af5` / `bootm_mapsize@0x37ed0b0a` only in the
`0x37e5b6cc` sibling (ramdisk reloc), not here.

Pre-reloc `0x37e5bd08` (called with `x0=x20` scratch, `x1=ft_addr` at all
three sites): `fdt_check_header` + `fdt_num_memrsv`-style loop
(`bl 0x37ea1a78` + `bl 0x37ea1a10`), error print on mismatch. No copy, no
field store. Not a divergence point. File `preloc_37e5bd08.txt`.
Sibling `0x37e5b6cc` is ramdisk/`initrd_high` reloc (PROVEN
`initrd_high@0x37ec05f9` + `Loading Ramdisk` strings), not FDT content.
File `ramdisk_reloc_37e5b6cc.txt`.

Consequence: the copy, when taken, happens BEFORE `fdt_chosen`. The blob
`fdt_chosen` modifies IS the product (`x19` after tail). A pre-copy cannot
revert a later `setprop` on the product. No copy exists after.

## Post-fdt_chosen transformations (to x2 load at 0x37e21284)

Caller `0x37e5c324` keeps `x19` (=`[images+0x100]` reloaded pre-call) in a
callee-saved slot across the whole tail (PROVEN: `mov x19,x1@0x37e5c340`,
never reloaded). Chain after `fdt_chosen` return (`w0` in `w19` scope):

```text
fdt_chosen return (w0, tbz bit31 @0x37e5c348)
 -> fail: ERROR /chosen node create failed@0x37ed1511 + printf + w20=-1 -> return -1
    -> 0x37e5b800 cbnz -> return nonzero -> 0x37e21258 nonzero -> printf + hang
    PROVEN static; boot success is INFERRED success, never PROVEN
 -> success (INFERRED on stock boot):
    arch_fixup_fdt(x19) @0x37e5c35c (=0x37e211f8: ldr [x18] + bl 0x37e298c0 memory-banks fixup)
      only memrsv/`memory@0x37ed47cd`/`device_type@0x37ec2113`/`reg@0x37ec146d`, no bootargs. PROVEN.
    -> board/system setup(x19) @0x37e5c37c (=0x37e29ac8: /aliases@0x37ec213e + ethaddr@0x37ec214a/usbethaddr/ethernet%d)
      no bootargs. PROVEN.
    -> ldr w2,[x19+4]; rev; bl 0x37ea3c38 (totalsize/pack family, INFERRED name, PROVEN in-place)
    -> bl 0x37e29c70 (pack/totalsize recompute, PROVEN in-place str [x19+4], file pack_37e29c70.txt)
    -> bl 0x37ea3d28 + bl 0x37e295e8 (reserve/move, PROVEN in-place on x19, file memrsv_37e295e8.txt)
    -> bl 0x37e5c31c (mov w0,#1; ret, PROVEN stub, always nonzero return path handled by caller)
    -> return w20 (=pack rc) to 0x37e5b800
 -> 0x37e5b800 returns w0 (0 on success path) to 0x37e2122c gate
 -> 0x37e2122c cbz w0 continues to 0x37e21278 ret
 -> 0x37e21378 dispatch returns (w19=0 path) to bootm full-states return
 -> 0x37e21284 loads x2 from same field, b 0x37e19264, eret
```

For each function, copy/reloc/decrypt/decompress/fixup/pointer-rewrite/size:

* copy: none in tail (no `bl memmove@0x37eaaf50`, no `bl fdt_open_into` with
  new dest; the two `bl 0x37ea3d28`/`0x37ea2bec`-shaped calls inside pack
  operate in place on `x19`, PROVEN by args `x0=x19`).
* reloc: none (reloc already done; `fdt_high` not re-read here).
* decrypt/decompress: none (decrypt-skip `tbz w22,#2@0x37e25d0c` is before FDT
  fixup in `do_bootm_states`, not after; PROVEN order).
* fixup: only mem/alias/ethaddr/initrd-start/end (`0x37e29980`/`0x37e29a4c`
  set `device_type`/`linux,initrd-start@0x37ec1ff2`-family, not bootargs).
* pointer rewrite: none (`x19` preserved; no `str [images+0x100]` in tail).
* size update: yes, `totalsize` (`str [x19+4]`) only, expected, not a revert.

`memcpy`/`memmove`/`fdt_move`/`fdt_open_into`/`fdt_pack`/`fdt_check_header`/
`fdt_setprop`/`fdt_delprop`/`fdt_add_subnode` census: names for libfdt
entrypoints are INFERRED except `fdt_check_header` (PROVEN magic) and
`fdt_setprop` (PROVEN callers+`libfdt fdt_setprop(): %s` string) and
`memmove` (PROVEN loop). Wrappers/indirect: `0x37e5af44` is a
`cmp x1,x0; b.eq ret; b memmove` guard (PROVEN wrapper); `0x37e5b6cc` and
`0x37e5bda4` are the only indirect-copy-capable paths with
`src=FDT,dst=other` (PROVEN args), both before fixup. No indirect `blr`
copy sits in the post-fixup tail (PROVEN: tail calls are all direct `bl`,
list in `image_setup_37e5c324.txt`).

## /chosen writers (complete census, Linux path scope)

* `fdt_chosen@0x37e297b8` (called at `0x37e5c344` in Linux path, PROVEN):
  `fdt_find_or_add_subnode(fdt,0,chosen)` + `env_get(bootargs)@0x37e29814` +
  `fdt_setprop@0x37e29840`. Null env -> return 0 no write. `setprop==0` ->
  return 0. Else WARNING + errno. This is the ONLY `/chosen/bootargs` writer
 in the Linux path.
* `do_bootvx_fdt@0x37e2646c` (called in bootvx dispatch, not Linux path):
  same env string (`0x37e264d8` adrp bootargs + `env_get`), writes under
  `/chosen@0x37ec09d0` via `0x37e294c0`-family. Same content even if taken,
  so not a revert source. PROVEN, file `bootvx_fdt_37e2646c.txt`.
* `fdt` command handler `0x37e2852c` (cmd idx 49): `0x37e293e4 bl fdt_chosen`
  on `ldr x0,[x21]` (command blob, `fdtaddr` global) + `0x37e293f4` memrsv.
  Mapped capability, PROVEN not in `bootm` path (subcommand parse, no caller
  from bootm). Not a runtime writer on the tested path.
* arch/board/mem fixups (`0x37e211f8`/`0x37e298c0`/`0x37e29ac8`/`0x37e295e8`):
  `fdt_setprop` callers at `0x37e296e0`/`0x37e2970c`/`0x37e29774`
  (inside `0x37e295e8` memrsv, values are addresses/sizes, PROVEN rev-pattern),
  `0x37e29980`/`0x37e29a4c` (inside `0x37e298c0`, `device_type`/`reg`/
  `linux,initrd-start/end`, PROVEN strings), `0x37e289f0` (inside `0x37e2852c`
  fdt cmd, not boot path). None writes `bootargs`. PROVEN by string+func
  attribution.
* `bootm`/`bootm_load_os` `setenv bootargs` appends (`verifiedbootstate`
  orange/green `0x37ec0060/0x37ec0085`, header `dtbo_idx/otg/buildvariant`,
  `defendkey` recovery-only, `0x%x` bookkeeping): append-only, none rewrites
  `selinux`/`reboot_mode`/`wificountrycode`. PROVEN by disasm + strings.
* `rpmb_state` fixup `0x37e57b5c`: dispatch-only, no callers, not on path.
  PROVEN absent from chain.

Result: no second `/chosen` builder that could reconstruct stock values was
found (OFFLINE_ONLY negative, scope: string+census+callers+callee disasm, not
a global proof). `fdt_delprop`/`fdt_add_subnode` beyond `chosen` creation:
no `delprop(bootargs)` site found in Linux path.

Branches for `fdt_setprop` return (PROVEN static):

```text
w0==0 (tbz bit31==0): return 0 -> caller 0x37e5c348 tbz==0 -> arch_fixup. SUCCESS path.
w0!=0 (negative, tbnz bit31==1): WARNING could not set bootargs + return errno
  -> caller ERROR /chosen node create failed + w20=-1 -> return -1
  -> 0x37e5b800 cbnz nonzero -> return -> 0x37e21258 nonzero -> printf + hang (bl 0x37eaaae8).
env_get null: return 0 no write, caller treats as success (PROVEN, no WARNING).
```

No branch leads to a second FDT on success. `SUCCESS = INFERRED` only (boot
hung would have been observed otherwise; round53/56 booted stock in ~15 s).

Texts (PROVEN addrs): `WARNING: could not set bootargs %s.@0x37ec206f`,
`ERROR: /chosen node create failed@0x37ed1511`,
`ERROR: arch-specific fdt fixup failed@0x37ed1534`,
`fdt_chosen: %s@0x37ec205f`.

## Round56 explanation (ZZ -> US, permissiv -> enforcing, fastboot -> normal)

Storeargs template (PROVEN `0x37eb6adb`): `androidboot.selinux=${EnableSelinux}`,
`androidboot.wificountrycode=${wifi_ccode}`, `androidboot.reboot_mode=${reboot_mode}`.
Defenv stock (PROVEN): `EnableSelinux=enforcing@0x37eb6673`,
`wifi_ccode=US@0x37eb68f1`, `reboot_mode_android=normal@0x37eb6947`
(note: diverged field is `androidboot.reboot_mode` from `${reboot_mode}`,
not `reboot_mode_android`). `get_rebootmode@0x37e60478` sets `reboot_mode`
from HW reg `0xc810023c` bits `[15:12]` + jump table, fallback env.
`switch_bootmode` sets `reboot_mode_android normal` then `run storeargs` in
several branches, but it does not run between verify and `bootm` on the
tested path (no reboot, PROVEN script order + round53/56 procedure).

Literal census (PROVEN full-image strings scan, file `strings_census.txt`):

* `permissiv`/`permissive`: 0 hits. `ZZ`: 0 hits. No C literal can emit the
  pre-boot markers. They exist only in runtime htab (verified `e1e32443`).
* `enforcing`: 3 hits (`EnableSelinux=enforcing` defenv, storeargs template
  `${EnableSelinux}`, rodata `enforcing@0x37ee0ebe`). No `bl fdt_setprop`
  site uses rodata `enforcing` as value; all writers use `env_get` result.
* `normal`: defenv `active_slot=normal`, `reboot_mode_android=normal`,
  rodata `normal@0x37ec028c`, plus script literals. No FDT writer emits it.
* `US`: only `wifi_ccode=US` defenv. No other `US` FDT source.
* `fastboot`: only `switch_bootmode` script branch + `f_fastboot` driver
  strings, never as FDT literal.

Therefore: single C routine rebuilding all three stock values does not exist
in the static image (OFFLINE_ONLY negative, scoped). Three independent C
emitters also do not exist. The three stock values already exist in another
place: defenv + htab defaults + `get_rebootmode` HW path. Whole-string revert
(`ZZ->US` together with `fastboot->normal`, rest identical per round56
`getprop`) is consistent with FDT lost/substituted (different blob delivered)
or string rebuilt from defaults before `fdt_chosen`, not with selective
field filtering. `bootm`'s own rebuild (`%s %s %s` + `verifiedbootstate`
orange/green + header extras) is append-only and cannot produce
`enforcing`/`normal`/`US` from `permissiv`/`fastboot`/`ZZ` (PROVEN disasm).
No other rebuilder between htab verify and fixup was found statically.

This does not pick between (a) env re-derived before fixup with no static
trace, (b) FDT-B vs another blob delivered, (c) init/Linux deriving
`ro.boot.*` without verbatim `/chosen/bootargs`. All three stay UNKNOWN
offline. What is closed: it is not a BL33 field filter, and not a BL33 C
literal overwrite.

## Final identity

* `fdt_chosen` arg vs `x2`: SAME field (`[images+0x100]` post-reloc), PROVEN
  structural. `x0=x1=[images+0x100]` at `0x37e5c334/0x37e5c340` (x1 reloaded
  at `0x37e5b864`); `x2=[images+0x100]` at `0x37e21318`; no store between
  fixup return and handoff.
* Bytes at handoff vs bytes modified: UNKNOWN runtime (reloc dest + `ft_len`
  gate + `setprop` rc all runtime). In-place tail after fixup does not rewrite
  `/chosen` (PROVEN), pack only touches `totalsize`.
* Dump vs final: NOT equal as dumped (missing `/chosen`), UNKNOWN if dump
  equals pre-reloc source.

Classification: `SAME_OBJECT_UNKNOWN_BYTES`.

Not `SAME_OBJECT_SAME_BYTES` (pack changes header, runtime rc/dest unknown,
no byte-equality proof). Not `DIFFERENT_OBJECT` (no second delivered object
found; reloc product IS the delivered object). Not plain `UNKNOWN` (pointer
identity IS proven; only bytes/runtime remain open).

Case mapping asked for:

* Case A (`modified == final`, no copy/substitution): HOLDS for the
  post-`fdt_chosen` segment (no copy/swap found). Does not close runtime bytes.
* Case B (copy before, FDT-B misses change): copy exists but sits BEFORE
  `fdt_chosen`, so it is the modified object itself, not a missed fork.
  Negative as explanation.
* Case C (later routine rebuilds `/chosen`): none found. Negative (scoped).
* Case D (FDT-A modified, FDT-B delivered): no pointer swap after fixup found.
  Negative (scoped).
* Case E (all same offline): YES for content. `runtime UNKNOWN`, one minimal
  discriminator below.

## Root relevance

Only this bridge:

```text
BL33 arbitrary write -> effective FDT -> Linux
```

Nothing here advances to root. `WRITE -> HARDWARE_REPRODUCED`,
`env_htab -> HARDWARE_REPRODUCED`, `storeargs -> HARDWARE_REPRODUCED`,
`htab -> bootargs -> HARDWARE_REPRODUCED`,
`bootargs -> Linux -> REFUTED in this form` (round53 + round56 whole-string
revert), `FDT identity -> SAME_OBJECT_UNKNOWN_BYTES` (pointer PROVEN same
field, bytes UNKNOWN), `root -> NOT DEMONSTRATED`. No `uid=0`, no SMC bypass,
no init payload, no `.text` patch, no flash/saveenv. Do not promote.

## Next experiment (max one, NOT executed, only if hypothesis accepted)

None is recommended as proven, because numeric `ft_addr`/`ft_len` at handoff
are UNKNOWN and inventing them would violate the brief. The single minimal
discriminator that meets the bar (generic safe marker, predicts FDT/moment/
alteration/oracle without inventing an address) is:

* FDT: post-reloc blob delivered in `x2` (`[images+0x100]` after `0x37e5bda4`,
  whatever `lmb`/`fdt_high` chose at runtime), observed post-handoff via
  `/proc/device-tree`, not via invented RAM address.
* Moment: EL1 entry content, read after boot from the kernel's own FDT view.
* Alteration: inert same-length `androidboot.boardid` `3->7` (NOT selinux,
  NOT wificountrycode) via `setenv boardid 7` + `run storeargs` (never arena
  poke), verified pre-boot by fresh-ptr htab + `test` oracle, then the E4 pair
  `imgread kernel boot 0x1080000` (check `success` first, abort otherwise) +
  `bootm 0x1080000`, RAM-only, no saveenv/flash/update/recovery.
* Oracle (safe, read-only): primary `cat /proc/device-tree/chosen/bootargs`
  (+ `hexdump -C` if present); control `getprop ro.boot.boardid` +
  `getprop | grep ro.boot`.
* Prediction: if device-tree shows `boardid=7` but `ro.boot.boardid=3`, the
  fork is init-side derivation (BL33 delivered, Linux re-derived). If both
  show `3`, the fork is at/below BL33 handoff (blob swapped or string rebuilt
  before `fdt_chosen`). If both show `7`, transport holds for this form.
* Cost: one RAM-only reboot, marker dies with `bootm`. Do not run another
  `getprop`-only boot without this device-tree oracle; it would repeat
  round53/56 with no new bit.

If `/proc/device-tree/chosen/bootargs` is unreadable for shell on this build,
the experiment does not meet the oracle bar and must not run; fall back to
runtime `ft_addr` discovery via safe `printenv fdtaddr` + `md` before any
`bootm`, still offline-proposed only.

## Validation

* `python3 tools/run_tests.py` -> `126 tests, OK` (`skipped=1`, same as baseline).
* `git diff --check` clean.
* No hardware touched. No `WRITE`. No boot. No `imgread`/`bootm` executed.
