# round25: continuous investigation (keyman -> secure world -> boot, no early stop)

image `reports/round14-bl33-persist/bl33-37e18000.bin`, base `0x37e18000`.
method: `tools/bl33_audit.py` (smc/callers/refs/ptrs/fstrings/strrefs/table/cmds) + capstone disasm.
no device, no SMC executed, no writes. static only unless noted.

prior confirmed state (rounds 20-24, re-verified where touched here):
host -> fastboot oem -> cb_oem -> run_command -> keyman -> key_manage_read/write
-> secure/efuse backends -> SMC 0x61/0x62 -> secure world. C1 `0x05000000`,
C2 `0x05040000`, BLOCK `0x05080000`, SIZE `0x40000` (runtime `0x82000023/24/25/27`).
18 generic read, 19 generic write (secure_boot_set diverted), secure backend 15 keys,
efuse 3 keys, HDCP2 generic NO, secure-data-to-host-RAM sink CONFIRMED,
arbitrary write REFUTED. `0x820000ff` BL33 validation ABSENT, BL31 validation UNKNOWN,
exact aquaman BL31 NOT FOUND.

this round followed every edge 2-4 hops past each finding instead of stopping at it.

## 1. keyman surface

dispatcher `keyman 0x37e74290`: `cmp w2,#1`, `x0=[x3,#8]` (sub word),
`find_cmd 0x37e5eddc` over sub-table at `0x37f5e4f8` (stride `0x30`, NOT 16):
`init->0x37e74120`, `exit->0x37e74148`, `read->0x37e750c4`, `write->0x37e749ac`,
`query->0x37e75304` (qword dump verified this round: `0x37f5e4f8:init/0x37e74120`,
`0x37f5e528:exit`, `0x37f5e558:read/0x37e750c4`, `0x37f5e588:write/0x37e749ac`,
`0x37f5e5b8:query/0x37e75304`; maxargs 3/2/4/4/3, never enforced by dispatcher).
`blr x4` with `(argc-1, argv+1)`. `bl` callers of `0x37e74290`: none (cmd_tbl root).
`sibling `keyunify 0x37e73c84` (fstrings `do_keyunify/secure/exist/uninit`) shares
`key_unify_init 0x37e73694`, `device_read 0x37e7394c`, `len_lookup 0x37e73aa0`,
`_get_km_ops_by_name 0x37e73380` callees but is a separate command (not a keyman leg).

`do_keyman_write 0x37e749ac`: floor `argc'>3`. three fmts by strcmp on `argv'[2]`:
`hex` (strlen/2, malloc, `keyman_hex_ascii_to_buf 0x37e73404`), `str` (strlen, ascii `<0x80`
check), numeric (`strtoul len base 0`, `==0 -> 0x2bb`, `>0x10000 -> 0x2bf`,
`addr=strtoul(argv'[3],NULL,0x10)`). all converge to
`key_manage_write 0x37e7430c(name=x23, data, len)`. return `(w19!=0)`.

`do_keyman_read 0x37e750c4`: floor `argc'>2`. `x22=[x3,#8]` name,
`x20=strtoul(argv'[2],NULL,0x10)`, `==0 -> 0x263`. `key_info_query 0x37e74c0c` gate
(`->0x269`), `key_manage_read 0x37e74d18` (`->0x26e`). all 13 `bl` in the function
enumerated this round: `strtoul, printf x6, 0x37e74c0c, 0x37e74d18, strcmp x2,
hexdump 0x37e735c8, setenv_helper 0x37e5848c`. NO `run_command`, NO `run`, NO saveenv,
NO USB/MMC/SMC/fastboot `bl`. CONFIRMED.

`do_keyman_query 0x37e75304`: `dev_exist 0x37e74ba4 / 0x37e75254 / 0x37e74c0c` only,
zero `bl` to `amlkey_*`. no C1/C2 edge. CONFIRMED.

gates before any SMC (both paths): `0x37e73864` init + `type_resolve 0x37e7414c`
(DTS cfg `0x37e756e4` miss -> nonzero; 4-entry list `@0x37eb5058` mac/sha1/hdcp2/raw;
raw+name overrides `mac/mac_bt/mac_wifi->0`, `hdcp2->2` via csel `@0x37e74260`).
unknown name aborts `0x198` (write) / `0x269` (read) before any SMC. per-type shape
validators: mac `==0x11` + `:` + hexdigit; sha1 `>0x14` + 20-B suffix memcmp;
hdcp2 `>0x385` + LE magic `0x02000000` + 0x386 transform. raw straight to
`device_write/device_read`. jump table `@0x37ebea34`.

## 2. 19-key resolution (table + real consumers in BL33)

DTS ground truth unchanged (unifykey-num `0x13`, `/unifykey/key_0..18`,
stride `0x68`, array `[0x37f89fe0]`, count `[0x37f5e5e8]`, selector `0x37e73380`
class 1->`0x37f5e4b8` efuse / 2,3->`0x37f5e478` secure-normal / else NULL).
vectors dumped: `0x37f5e478` (secure/normal, flag +0x38=1, write `0x37e75e7c`,
read `0x37e7609c`, tell/query/exist slots) + `0x37f5e4b8` (efuse, flag 0,
write `0x37e761f0`, read `0x37e762f4`, size/exist slots). loaders of `0x37f5e478`:
`0x37e73380 @0x37e733f0` / `0x37e73694 @0x37e7371c` / `0x37e737d8 @0x37e737e0`
(adrp+add refs, this round). `secukey_write/read` have NO `bl` caller (table-only);
dispatch via `0x37e73880/0x37e7394c` (`bl 0x37e73380` then `blr`).

per-key `strrefs` + 1-2 hops up (this round, exhaustive):

```text
sn1                  : 0 refs (case-insensitive). generic argv only. device-identity/unknown, no BL33 consumer.
sn2      @0x37ebf6e6 : ref 0x37e21aa8 in setkeys 0x37e219f0 (see below). device-identity/environment.
hdcp (DTS key_2)     : NOT hdcp2*; fixed hdcp2key@0x37ed7535 refs 0x37e748e4 (write) + 0x37e74fc4 (read),
                       hdcp2lc128@0x37ed74f4 refs 0x37e7488c + 0x37e75018, hdcp2@0x37ed72f7 ref 0x37e7424c
                       (type probe). parents key_manage_write/read <- do_keyman + optimus USB. display/HDCP.
secure_boot_set      : refs 0x37e76200/0x37e762d8/0x37e7638c (efuse slots only, §6). boot-named, no boot consumer.
mn1/mn2              : 0 refs. generic only. factory-guess, unknown evidence.
hdcp2_rx @0x37edb89f : 0 refs (sibs hdcp22_rx_private/_rx_fw/_rprx_fw/_rp_private/_rprp_fw also 0).
                       indirect only via aml_hdcp_key2.2@0x37edb4d0 refs 0x37e8213c/0x37e825f8/0x37e82738
                       (optimus USB). display/HDCP, generic-only.
mac_bt   @0x37ebf674 : refs 0x37e21790 (0x37e2176c efuse-MAC helper), 0x37e21a14 (setkeys),
                       0x37e74224 (type_resolve). network/BT.
mac (bare)           : NO standalone string (0x37ebf6da/e2 hits are fmt/wifimac+4 tails). 0 refs. alias/unknown.
mac_wifi @0x37ebf67b : mirror triple 0x37e217ac/0x37e21a74/0x37e74238. network/WiFi.
widevinekeybox, PlayReadykeybox25, prpubkeybox, prprivkeybox, attestationkeybox,
netflix_mgkid, bt_rc_mac, hdcp22_fw_private : all 0 hits (CI substrings also 0).
                       generic argv only. crypto-DRM / network / display by NAME ONLY, unknown in BL33.
region   @0x37ebf704 : ref 0x37e21b54 in setkeys (+sibs serialno@0x37ebf6ea refs 0x37e21b24/34,
                       boardid@0x37ebf710 ref 0x37e21ba8). environment/bootargs.
```

extra consumers (followed past the string hit):

* `setkeys 0x37e219f0` (cmd_tbl command, NO `bl` caller = shell entry only).
  fstrings: `mac_bt/btmac/mac_wifi/wifimac/serialno/0123456789ABCDEF/region/boardid`.
  body: `bl 0x37e2176c` x3 (mac_bt@0x37e21a20, wifimac+4@0x37e21a48, mac_wifi@0x37e21a80),
  each followed by `bl setenv_helper 0x37e5848c` (btmac/wifimac env); `bl 0x37e21864` x2
  (@0x37e21ab8 sn2 path, @0x37e21b6c region path); serialno/region/boardid `bl setenv_helper`.
  `0x37e2176c` (efuse-MAC helper): strcmp name vs mac_bt/mac_wifi, `bl 0x37e7263c`
  (efuse read, same family as `0x37e72ca4/0x37e72d98` `efuse_usr_api_write/read_key`),
  ascii `%02x` format loop. does NOT call key_manage/device/amlkey (different backend:
  direct efuse API, not unifykey vector). so mac keys have TWO readers: keyman generic
  (secure/efuse vector) AND setkeys direct-efuse (env provisioning). convergence:
  mac_bt+mac_wifi share identical 3-site set; sn2+region+serialno+boardid converge on setkeys.
* `0x37e21864` (called only from setkeys): builds `keyman read %s 1080000 str @0x37ebf6bd`
  (ref @0x37e21878) via snprintf then `bl run_command 0x37e5e968`, then `getenv`.
  this is the ONLY `run_command("keyman ...")` constructor in the image. direction:
  setkeys -> run_command(keyman read ... str) -> setenv. static mechanism CONFIRMED,
  but trigger is the `setkeys` shell command (host types `setkeys`), not automatic boot.
  fixed dest `0x1080000`, fixed fmt `str`. does NOT cover arbitrary keys from host oem
  (name comes from setkeys locals: sn2/region path).
* `0x37e29ac8` DT `mac-address/ethaddr` fixup <- `0x37e5c324` <- `0x37e5b800` boot DT setup.
  distinct from keyman MAC (fdt fixup, not storage). recorded to avoid conflation.
* optimus USB family: `0x37e8212c` (fstrings `aml_hdcp_key2.2/optimus_download_key.c`)
  <- `0x37e7abe4` + `0x37e824a8`; `0x37e8240c` <- `0x37e79ff0` (`optimus_download.c`);
  `0x37e824a8` <- `0x37e79988` (`optimus_transform`). `0x37e824a8` builds
  `keyman read %s 0x%p str @0x37edb7e7` (ref @0x37e82a68) the same way. USB-burning path,
  DTB/usb structs as key material, NOT argv. HDCP provisioning lives here, not in shell.
* fastboot shim `0x37e94838` (no fstrings; fixed name `usid @0x37edec8d`):
  `bl amlkey_isexsit`, `bl amlkey_size` (gate `==0x1f`, `>0x1f` fail), `bl amlkey_read`
  into bss `0x37fbdf48`-ish. callers `0x37e948a8` (usb_dnload) + `cb_getvar 0x37e95ecc`
  (f_fastboot). fastboot-table dispatched, no `bl` caller. independent host path
  (fastboot, not run_command). fixed name `usid`, NOT a DTS key, NOT argv.

classification roll-up: boot 1 (secure_boot_set, name-only) / display-HDCP 3
(hdcp, hdcp2_rx, hdcp22_fw_private) / device-identity 3 (sn1, sn2, serialno-side) /
factory 2 (mn1, mn2, name-guess) / network 4 (mac_bt, mac, mac_wifi, bt_rc_mac) /
environment 2 (region, boardid-side) / crypto-DRM 5 (widevine, PlayReady, prpub, prpriv,
attestation, netflix) / unknown-evidence 8 keys with zero BL33 refs beyond generic argv.
no key resolves to UNKNOWN backend; every DTS device maps to a dumped vector slot.

## 3. SMC 0x60-65 callers (exhaustive, grouped)

shared stub `0x37e8bba0` (`smc #0; ret`). x0 set by `mov+movk #0x8200` at each site;
X1/X2/X3 never set (payload in `[[0x37fbde60]]`, response in `[[0x37fbde58]]`).
census re-ran this round: 15 opcode-exact `smc #0` sites, six are 0x60-65.

```text
0x60 QUERY  0x37e8be98 <- 0x37e8c324 in amlkey_isexsit 0x37e8c2ec
           <- 0x37e94850 in 0x37e94838 fastboot shim <- 0x37e948a8/0x37e95ecc (fastboot).
           NO bl path from any of 80 command handlers incl keyman query (which uses
           0x37e74ba4/0x37e75254/0x37e74c0c). group: fastboot-only. run_command: NO.
0x61 READ   0x37e8bdc8 <- 0x37e8c414 in amlkey_read 0x37e8c3e4
           <- 0x37e74f84/0x37e74fd8/0x37e7502c in key_manage_read 0x37e74d18 (hdcp branch
              fixed names + generic caller-name leg) + 0x37e760f8 in secukey_read 0x37e7609c
              (table-only) + 0x37e94888 in fastboot shim.
           <- do_keyman_read 0x37e750c4 (shell) + 0x37e8240c (USB burning).
           group: keyman + USB + fastboot. run_command: YES (keyman read).
0x62 WRITE  0x37e8bd10 <- 0x37e8c484 in amlkey_write 0x37e8c450
           <- 0x37e748a0/f8/4c in key_manage_write (hdcp2lc128 FIXED/hdcp2key FIXED/
              caller-name 4B) + 0x37e75f20 in secukey_write 0x37e75e7c (table-only).
           <- do_keyman_write 0x37e749ac (shell) + 0x37e8212c optimus_download_key (USB).
           group: keyman + USB. run_command: YES (keyman write).
0x63 TELL   0x37e8bfe0 <- 0x37e8c3ac in amlkey_size 0x37e8c374 <- 0x37e94864 fastboot shim.
           group: fastboot-only (+keyunify size helpers, no shell). run_command: NO.
0x64 VERIFY 0x37e8c084 (+tramp 0x37e8c508: `b 0x37e8c084`) <- 0x37e75f78 in secukey_write ONLY.
           0x37e8c084 itself: NO bl caller. ptrs scan for both addrs: empty.
           secukey_write: NO bl caller (ops-vector slot 0x37f5e488, loaded by 0x37e73380/
           0x37e73694/0x37e737d8). group: keyman-table-only. run_command: NO (table-gated).
0x65 STATUS 0x37e8bf3c <- 0x37e8c1a4 in amlkey_get_attr 0x37e8c16c <- 0x37e8c364 in 0x37e8c35c
           (and #1 gate) <- 0x37e76088 in 0x37e76080 (cset eq gate) <- 0x37e760b4 in
           secukey_read 0x37e7609c (table-only). group: keyman-table-only. run_command: NO.
```

control SMCs (contrast): `0x28 SET_STORAGE_INFO 0x37e8c138` sole caller `0x37e90614`
in `0x37e904ac` boot/state machine (X1=1, selector `[0x37f60878]=2`, scalar, no buffers);
`0x69 NOTIFY_EX 0x37e8bcfc` sole caller `0x37e8c2a0` in `amlkey_init-ish 0x37e8c1dc`;
`0x6a SET_ENCTYPE 0x37e8c14c` sole caller `0x37e8c264` in `0x37e8c1dc`; `0x26/0x66/0x67/
0x68/0x6b/0x6c` zero setup sites (never issued). BLOCK never touched on 0x60-65 paths.

0x64 verify chain, followed to terminus (disasm this round, subagent + main re-check):

```text
secukey_write 0x37e75e7c: bl 0x37e75590 (dev class) -> cset w21,eq (w21 = dev==2?)
 -> bl 0x37e75650, strlen, hash-shape prologue (0x37e75ec4..0x37e75ee4) -> bl 0x37e75650
 -> bl amlkey_write 0x37e8c450 @0x37e75f20; cmp x0,w20 else w20=0x34 ret (write-len mismatch)
 -> w20=0; cbz w21 ret (dev!=secure skips verify entirely: normal-class keys NEVER verify)
 -> x22=sp+0xf0; bl 0x37e8c508 @0x37e75f78 (= b 0x37e8c084)
0x37e8c084: init-gate (flag [0x37fbd...e50]==1 else bl 0x37e8bbb8 re-init; second flag !=1
 -> w19=-1 ret) -> C1 [IN+0]=namelen + name -> SMC 0x64 -> w19=X0
 -> cbnz X0 ret (SMC fail: NO copy, return code; 0x20B untouched)
 -> memcpy(caller=x21/sp+0xf0, OUT, 0x20) (result DISCARDED: no cmp here, both branches -> ret w19)
back in secukey_write: w21=w0; cbz else log + w20=0x3e ret (verify-SMC fail)
 -> memcmp(sp+0x110, sp+0xf0, 0x20) @0x37e75fc8 (0x37eaafac); cbz else 32x snprintf loop
    + log + w20=0x50 ret (post-verify mismatch)
 -> equal: log + ret w20==0 (success)
```

so the 0x64 OUT bytes ARE compared, but one hop up (not inside the SMC wrapper):
the wrapper copies 0x20 B unconditionally-on-success and returns status; the CALLER
compares them against `sp+0x110` (stack buffer staged in the `0x37e75ec4..0x37e75ee4`
prologue). what is verified = "what secure world echoes for this name matches the
just-written shape", not a boot image, not a signature over firmware. no caller outside
secukey_write (whole-image `b`+`bl` scan: only `0x37e75f78 -> 0x37e8c508 -> 0x37e8c084`).
verdict: `0x64 -> verify` = write-back self-check, storage-only. hypothesis "0x64 verifies
boot/firmware" REFUTED (code-exact negative: sole caller is the secure write path,
compared object is the write echo, both fail branches return codes only).

## 4. C1/C2 dataflow (exact, re-disassembled)

slot addrs are triple-indirect (`adrp 0x37fbd000 + #0xe50 flag / #0xe58 OUT / #0xe60 IN`);
runtime `0x23->IN 0x05000000, 0x24->OUT 0x05040000, 0x25->BLOCK, 0x27->SIZE 0x40000`
via `0x37e8bbb8` (callers: all six 0x60-65 wrappers + `getbuffer 0x37e8bc84`).

WRITE `0x37e8bd10` (x0=name, x1=data, w2=datalen, w3=flags):
`strlen(name) -> str [IN+0]` (namelen); `str w2,[IN+4]` (datalen); `str w3,[IN+8]`
(flags, always 0 from the three direct sites `mov w3,#0`); `memcpy(IN+0xc, name, namelen)`;
`memcpy(IN+0xc+namelen, data, datalen)`; `SMC 0x62`; return SMC status path value.
no OUT parse (return code only). CONFIRMED bytes.

READ `0x37e8bdc8` (x0=name, x1=caller_buf, w2=hint, x3=caller_len_ptr):
`strlen(name) -> str [IN+0]`; `str w_hint,[IN+4]`; `memcpy(IN+8, name, namelen)`;
`SMC 0x61`; `cbnz X0 fail` (no touch); `w2=[OUT+0]` (secure-reported u32);
`x1=OUT+4`; `str w2,[len_ptr]`; `memcpy(caller_buf, OUT+4, w2)` NO clamp vs caller len.
returns secure len on ok, 0 on fail. CONFIRMED bytes. maximum = UNKNOWN (no IN/OUT
capacity in image; `0x10000` is key_manage staging malloc, `0x40000` is BLOCK, neither
is the C2 limit). staging `malloc(0x10000) @0x37e74dfc`: all secure reads land there
first on the key_manage path, then ascii/hdcp/generic legs copy to caller buf.

QUERY/TELL/STATUS `0x37e8be98/0x37e8bfe0/0x37e8bf3c`: `strlen -> [IN+0] + name`;
`SMC 0x60/0x63/0x65`; `cbnz fail`; `str [OUT+0] word -> *caller`. one status word,
never key material. VERIFY `0x37e8c084`: `strlen -> [IN+0] + name`; `SMC 0x64`;
`cbnz fail`; `memcpy(caller, OUT, 0x20)` fixed 32 B.

WRITE format sent (host->secure): `[u32 namelen][u32 datalen][u32 flags][name][data]`.
READ format staged (host->secure): `[u32 namelen][u32 hint][name]`.
READ format returned (secure->host): `[u32 len][blob]` at C2, then blob-only copy to
caller RAM + len via out-param. no crypto/format evidence in BL33 around OUT
(`0x6a` enctype switch never branches on the read copy). plaintext-vs-cipher UNPROVEN.

## 5. output observability (read terminus)

shell path keeps blob at argv addr only by default. three fmt tails in `do_keyman_read`
(`0x37e75194..0x37e75234`, re-disassembled):

* no fmt word (`x21==NULL`): silent, `w19=0`. RAM ONLY. CONFIRMED.
* `fmt=hex` (strcmp `0x37ed7572`): `hexdump 0x37e735c8(addr, len, 0)` + print
  `[KM]Msg:key len is %d...`. hexdump body: `printf x4 + snprintf`, UART only.
  `cb_oem` never forwards handler stdout, no fastboot-send on path. UART ONLY.
  needs physical tap, not host USB. CONFIRMED edge, host-unobservable over USB.
* `fmt=str` (strcmp `0x37ebf6d4`): ascii loop (`ldrsb`+`tbz #31`; non-ascii -> print +
  return 1), then `setenv_helper 0x37e5848c(name=x22, value=addr-buf)` ->
  `{"setenv",name,value}` + `do_setenv 0x37e58294` (malloc/env-RAM write/free only,
  no persist). binary NUL truncates. INDIRECT ENV ONLY. saveenv is SEPARATE (never
  `bl`-called on path). USB/fastboot response: none (return code only). CONFIRMED edge.
* other word: `Err key dataFmt` print, blob stays. CONFIRMED.

answers: `read -> fmt=str -> run_command`: NO (no such `bl` between `0x37e750c4` and
return; consumer tables rounds 22-23 stand). `read -> setenv (RAM only)`: YES.
saveenv/USB/fastboot on this path: NONE (confirmed negatives). host-readable
automatically: NO (RAM ONLY default; UART ONLY with hex; INDIRECT ENV ONLY with str;
DIRECT FASTBOOT never on the oem path). the fastboot TWIN of the same low reader
(`0x37e948a8` tail: `bl 0x37e94838` then `bl 0x37e947d4` send) DOES forward bytes to USB,
but that path takes fixed name `usid`, not argv, and never goes through run_command.
do not conflate the two.

host-destination restrictions (argv base -> RAM): `base==0` rejected YES;
width 64-bit YES (strtoul x0 through x-registers, no narrowing); alignment NONE;
range checks NONE; size interaction NONE on the low copy (unclamped memcpy);
overflow checks NONE. so host-controlled destination HIGH, secure-controlled
length/content HIGH: secure-data-to-host-RAM sink, NOT arbitrary write (host controls
no content/length bit on read; write-path bytes face DTS+per-type validators).

## 6. env / run_command composition

`run 0x37e5ea04`: `getenv(argv[i]) -> run_command` per var, loop. `env 0x37e57d6c`:
8 subcommands, `env set` = setenv backend, `env run` = do_run, `env save` = persist.
mechanism lets host spell longer `keyman ...` across two <=31-char oem calls
(`setenv k <script>` + `run k`), dodging 33 B truncation. classification: INDIRECT
composition, static mechanism CONFIRMED, multi-call chaining POSSIBLE BUT UNPROVEN
by execution (same caveat as round15; not executed here).

static composition `oem -> keyman read -> setenv -> run -> command`: NO evidence.
`bootcmd=run storeboot @0x37eb65a0`, `storeboot @0x37eb71f2` (`get_system_as_root_mode;
echo; if test...`): no `keyman/keyunify/store key` token in script; boot flows through
`store` sub-handlers (`init/read/dtb`) + `0x37e904ac` state machine, NOT secure-key SMC.
`bootcmd` has 5 adrp refs all in env/hush (`0x37e27764/0x37e58a4c/0x37e58a90/0x37e58b7c/
0x37e58bf0`), zero in keyman fns; `storeboot` addr has zero code adrp refs (script-only).
`store key 0x37e33a38` CALLS `run_command` (`bl 0x37e33ba8`, `"%s %s %s 0x%x"` amlnf/
key_write/key_read fstrings) but the constructed command is amlnf/nand, not keyman
re-entry: EMITTER, not secure-storage path. `temp_triming/ddr_tune_dqs_step/get_rebootmode`
call run_command with CONSTANTS only. aliases for keyman: none. `source/go/booti` do not
exist in this build. `keyman read -> setenv` (RAM) is real but no static edge continues
to `run`/saveenv/USB from there.

`key-permit +0x5c`: parser `0x37e757ec` sets bits 1/2/4 (read/write/del) CONFIRMED;
`ldr [#0x5c]` scan over all 7 keyman-path functions (`0x37e74290/0x37e749ac/0x37e750c4/
0x37e7430c/0x37e74d18/0x37e73880/0x37e7394c` +0x700): ABSENT all 7. region-wide only 3
hits `0x37e75d88/ac/d0` inside parser block. verdict: BL33 enforcement ABSENT
(scoped negative, HIGH); anywhere-else UNKNOWN (secure side may check). `secure_boot_set`
write-only is enforced by strcmp name-checks (read refused via `0x37e762cc` cset-ne gate
at device_read `0x134` / len_lookup `0x150`, write diverted via `0x37e761f0` to
snprintf+run_command), NOT by a bit test. CONFIRMED distinct mechanism. during this
round no new `+0x5c` consumer appeared; closing as BL33-absent per rule §5 and continuing.

`secure_boot_set`: read REFUSED (above), write = `0x37e761f0` strcmp-divert to
`snprintf "efuse %s %p"` + `bl run_command` (env diversion, never reaches `0x37e72ca4`
efuse backend). consumers of the env var: 162 `bl getenv` sites scanned, NONE colocated
with `0x37ecfa08`; 4 refs total are the efuse slots + `0x37e56340` efuse-cmd strncmp
dispatch (password/customer/amlogic_set family). zero boot branch on it. verdict:
no BL33 consumer reads it as env toward boot. UNPROVEN beyond (secure-side use UNKNOWN).

## 7. boot relevance (bridge hunt, both directions)

`bootm 0x37e24c00` (cmd_tbl; sole `bl` caller `0x37e2501c` autostart wrapper):
callees `bootm_load_os 0x37e255c8` (fstrings `verify/Verifying Checksum/Loading/
COMP_NONE/Uncompressing`), `AML 0x40 @0x37e24cf0` (x0=0x40 IMG_DECRYPT x1=buf-or-
0x1080000 x2=0x1800000 x3=7), `AML 0x100 @0x37e24f90` (x1=0x1080000 x2=0x500 x3=7,
ret split lo==0x100 magic hi=count), avb `0x37e63b88/0x37e63b5c` (recovery/slot/
active_slot), `getenv/setenv/strcmp/strlen/printf` family, HW gate `0x37e72790`
(c8100228 bit4). NO verify/decrypt `bl` beyond the two AML calls + loader.

AML_DATA_PROCESS `0x37e19ea8` (SMC `0x820000ff`, tail `bl 0x37e19310` memcpy from
share-mem): 15 `bl` sites in 7 parents (12 previously + 3 extra efuse sites found
this round), per-site x0 recovered:

```text
0x37e24c00 bootm            : 0x24cf0 x0=0x40 (decrypt) / 0x24f90 x0=0x100 (query)
0x37e2a030 dtb-verify helper: 0x2a088 x0=0x40 / 0x2a0c4 x0=0x100 (callers 0x37e26728 DT walker + 0x37e33428 dtb-load)
0x37e33e00 store-dtb ops   : 0x33e94 x0=0x40 / 0x33ec8 x0=0x100 / 0x34084 x0=0x40 / 0x340d4 x0=0x100 (store-table slot dtb@0x37ee6510, blr-dispatched from 0x37e33900)
0x37e35e7c amlsec-imgread  : 0x35ec4 x0=0x100 (fstrings AMLSECU!/Err imgread; callers 0x37e3601c/0x37e362e0)
0x37e3601c unpackimg kernel: 0x3623c x0=0x40 x3=4 (ONLY decrypt site with x3=4; store-table slot @0x37ee65d8)
0x37e362e0 unpackimg dtb   : 0x36340 x0=0x100 (slot kernel@0x37ee65a8)
0x37e562e8 efuse handler   : 0x565e4 x0=0x10 W_EFUSE_SECURE_BOOT / 0x56664 0x20 W_EFUSE_AMLOGIC / 0x566f4 0x11 W_EFUSE_PASSWORD / 0x56774 0x12 W_EFUSE_CUSTOMER_ID
```

grouping: decrypt-type (0x40): bootm, dtb-verify, store-dtb x2, kernel-imgread.
query-type (0x100): bootm, dtb-verify, store-dtb x2, amlsec-helper, dtb-imgread.
efuse-write-type (0x10/11/12/0x20): efuse only. no 0x80 observed. BL33 validation ABSENT
(no `bl` on AML return toward a BL33 compare except the 0x100 magic/count split and the
0x40 opaque pass-through); BL31 validation UNKNOWN (image not available).

verify/signature/decrypt/AMLSECU/secure_boot/auth sweeps: `verify*` rodata hits
(verify_check/verify_headers/verify_dtb_checksum/gpt-verify/verify_len/verifyType/
VERIFY in optimus burning) resolve only to burning fns (`0x37e7b07c/0x37e7f508/0x37e7fc54`);
header/dtb `verify_*` have NO adrp+add/`bl` refs (dead or BL31-side). `signature` only in
image-list printer `0x37e5c994` (+unreferenced RTK_VENDOR/`signature is wrong`).
`decrypt` only `@0x37e33e34` in `0x37e33e00` (+unreferenced env frag `decrypt ${dtb_mem_addr}`
+ keyman hexascii). `AMLSECU!@0x37ec6af6` only in `0x37e35e7c`; `secure_boot_kernel_size`
unreferenced; `secure_boot_set` only in efuse keymanage (NOT boot graph); `auth` zero hits.

bridge test (both directions, function-target + string sweeps over all 7 boot/AML parents):
zero targets in keyman ranges (`keyunify 0x37e73c84`, `0x37e73880/0x37e7394c`,
`0x37e7430c/0x37e74d18`, `0x37e8bbb8/0x37e8c084` family, `0x37e74290` dispatcher),
zero adrp+add to `0x37e73880/0x37e7394c/0x37e74290/0x37e8bbb8/C1-C2 slots 0x37fbde58/60`,
zero share-storage SMC `0x23-27` outside `0x37e8bbb8` family, zero key-name strings in
boot parents (bootm has avb2/get_avb_mode/verifiedbootstate/defendkey/reboot_mode/
upgrade_step only; dtb/store/imgread have loadaddr/decrypt/dtb_read/write/Err imgread/
AMLSECU! only; efuse has secure_boot_set family + cmd_efuse only). shared callees are
generic only (`0x37e19764` checksum helper, `0x37e72790` HW gate, printf/getenv/memcmp/
memcpy/malloc). verdict: NO DEMONSTRABLE BRIDGE between host->keyman->secure-world and
boot/secure-verification in BL33 static evidence. the two graphs share libc-level helpers
only; no key material, no device_read/write, no 0x60-65 SMC, no C1/C2/share base flows
into boot. classification of keyman vs boot: storage-only on demonstrated edges
(keyman provisions/reads device keys incl HDCP/MAC/DRM; boot decrypts/verifies images via
0x820000ff with BL31-side checks). indirect path (boot helper -> storage query -> key ->
verify) searched, not found; (boot -> secure SMC -> shared storage -> key) searched,
not found. per stop rule D, closing storage-only on static evidence and moving to next
material lead (§8 live-locators + setkeys/optimus provisioning below).

automatic (D) vs command (B+C) separation kept: `0x37e904ac -> 0x28` + `[0x37f60878]=2`,
`amlkey_init 0x37e8c1dc` (getbuffer x2 + 0x6a + 0x69 + backend check, NO `bl` caller =
init-table reached), optimus burning (`0x37e8212c/0x37e8240c`, DTB/usb material) are D,
never counted as command reachability. YES via run_command remains exactly: keyman read
(0x61) + keyman write (0x62). query/status/tell/verify are NO via run_command.

## 8. BL31 clues (what could locate the exact image)

* `rsvmem 0x37e62e84` (cmd_tbl): subfn reads AO `0xc810024c/0254/0250`, getenv, then
  snprintf+fdt-sets via `run_command 0x37e5e968`. rodata `[rsvmem] bl31 reserved memory
  start/size 0x%08x @0x37ed40f1/411e`, `fdt get/set /reserved-memory/linux,secmon ...
  reg/size/alloc-ranges`, `linux,secos`, ~15 `... set ... error` strings. after `rsvmem`
  runs, DTB `/reserved-memory/linux,secmon` holds the BL31 range. live locator #1.
* share-mem: `0x37e8bbb8` init seq `0x23->...e60(IN) 0x24->...e58(OUT) 0x25->...e68(BLOCK)
  0x27->...e48(SIZE)`, flag `...e50=±1`; `getbuffer 0x37e8bc84` (`bl 0x37e8bbb8`,
  `bl smc(0x27)`) callers `0x37e8c234/0x37e8c294` in `amlkey_init 0x37e8c1dc`
  (printf, getbuffer x2, `0x37e8c14c->0x6a`, `0x37e350e8`, memset, `0x37e8bcfc->0x69`).
  `0x37e19d70` dispatcher caches `0x20->0x37f71480, 0x21->0x37f71488`
  (efuse/other share-mem; callers `0x37e7258c/0x37e72610`). SMC IDs observed in image:
  `12,18,20,21,23,24,25,27,28,33,43,44,60,61,62,63,64,65,69,6a,ff`. live locator #2:
  `SMC 0x20/21` + `0x23/24/25/27` return the share + storage bases/sizes.
* `%s() %d: can't get buffer from bl31! @0x37edd6e7` near `0x37e350e8` (bl31-buffer
  getter); `amlkey_init/isexsit/get_attr/size/read/write` + `shared-dma-pool` +
  `aml-storage` rodata; no `shmem/smc/secmon` code symbols (only `secmon` in fdt path,
  `SecureBoot/Secure OS` UI strings). FW header `0x37e18000: b #0x37e18028; nop` = BL33
  reloc header, not BL31. no BL31 entry/vector/SMC-dispatcher/table in
  `0x37e18000..0x37feffff` (pagetable `0x37ff0000`, `0x37f5ae00..` udf filler;
  raw `D4000001` hits are filler, not SMC). all SMC IDs via `mov+movk`, no `0x8200xxxx`
  word table. exact-BL31 locator NOT static in BL33.
* next material leads (no new BL31 candidate this round): (a) run `rsvmem` live and read
  DTB `/reserved-memory/linux,secmon` (read-only `0x02/0x34+0x33` primitives, concrete
  question "which range is BL31 on this board"); (b) live `0x23/24/25/27` + `0x20/21`
  base queries to confirm share layout before any struct work; (c) AO regs
  `0xc8100250/24c/254`. none executed here (no live access this round); documented for
  a future authorized live round. static analysis cannot continue past this point for
  BL31 internals (stop rule B/C).

## 9. confirmed / unproven / refuted + stop nodes

CONFIRMED (code-exact): host->oem->run_command->keyman chain; 19-key table + backends
(15 secure-vector incl 8 normal + 7 secure, 3 efuse + 1 diverted); per-key read 18 YES /
1 NO (secure_boot_set refused) + write 19 accepted / 18 storage / 1 env-diverted;
C1/C2 byte layouts (§4); READ sink = argv-RAM + secure len/content (unclamped memcpy);
WRITE fmt validators + flags=0 + slot-internal; fmt tails (silent/UART-only/RAM-env-only);
0x60-65 caller census + grouping (§3); 0x64 = write-back self-check, sole caller
secukey_write, normal-class skips verify (cset w21); setkeys dual-backend (direct efuse
+ run_command-constructed keyman read) as shell-only provisioning; optimus USB as
DTB/usb-material provisioning; fastboot shim fixed-`usid` as independent USB path;
bootm callees + 15-site AML table + groupings; permit parsed but BL33-unenforced;
secure_boot_set strcmp-gated (not permit-gated) with no env/boot consumer.

UNPROVEN (explicit): C2 maximum bound; OUT plaintext-vs-cipher; secure-side permit/
secure_boot_set authorization; BL31-side validation of `0x820000ff` (UNKNOWN);
multi-call `setenv+run` chaining by execution; any post-`setenv(fmt=str)` exfil chain
(mechanism only); efuse SMC `0x30/31` single-site (family reference only).

REFUTED: arbitrary host write via keyman read (no content/length bit);
`argv reaches SMC 0x62 untransformed` (generic path); generic HDCP2 reachability on this
DTS (type-2 leg dead for 19 names); key-permit as BL33 gate; `0x28` as staging consumer;
`store key` as secure-storage path; `0x64 verifies boot/firmware`; boot<->keyman bridge
on static evidence; `0x37f5e478` writers at runtime (link-time constants; DTS populates
the KEY ARRAY, not the vectors); round23 "generic hop never touches amlkey" at impl
level (blr slot impls DO `bl amlkey_*`; dispatch stays runtime-selected).

STOP NODES (per rule §12):

```text
last confirmed node : secukey_write memcmp(sp+0x110, sp+0xf0, 0x20) -> w20 (0 ok / 0x50 mismatch)
                      + do_keyman_read fmt tails (silent / UART hexdump / RAM setenv)
                      + bootm/AML caller table with zero keyman targets
next unresolved node: BL31 SMC dispatcher internals for 0x61/0x62/0x64/0xff
                      (what checks len/content, what 0x64 compares against secure-side,
                      what 0x40/0x100 validate inside secure world)
why static cannot continue: BL31 image absent from BL33 range + artifacts + repo;
  BL33 holds only mov+movk IDs + share-base queries, no secure-side code, no symbol,
  no header pointing to exact BL31. next step needs authorized live read of
  rsvmem DTB range / share-mem bases (primitives 0x02, 0x34+0x33 only), out of scope here.
```

GRAPHS:

```text
host
 |
 +-> fastboot oem (cb_oem 0x37e95630 -> run_command 0x37e5e968)
      |
      +-> run_command
           |
           +-> keyman 0x37e74290 (find_cmd tbl 0x37f5e4f8 + blr)
           |    |
           |    +-> key read 0x37e750c4 (argv[1]=name DTS-gated, argv[2]=dest RAM, no len arg)
           |    |    -> key_info_query 0x37e74c0c (len born here)
           |    |    -> key_manage_read 0x37e74d18 (malloc 0x10000 staging, type legs)
           |    |         -> mac leg: device_read -> efuse 0x37e762f4 (ascii-format)
           |    |         -> hdcp leg (dead on this DTS): 3x DIRECT amlkey_read + 0x386 transform
           |    |         -> generic leg: device_read 0x37e7394c -> blr vector 0x37f5e478
           |    |              -> secukey_read 0x37e7609c -> amlkey_read 0x37e8c3e4
           |    |                   -> C1 [namelen][hint][name] -> SMC 0x61 0x37e8bdc8
           |    |                   -> secure world -> C2 [len][blob]
           |    |                   -> memcpy(caller_buf, OUT+4, secure_len) UNCLAMPED
           |    |              -> output: silent RAM ONLY / hex=UART ONLY / str=RAM-env ONLY
           |    |
           |    +-> key write 0x37e749ac (argv[1]=name, argv[2]=hex|str|len + argv[3])
           |         -> key_manage_write 0x37e7430c (type_resolve + shape validators)
           |              -> mac/sha1/hdcp2 legs (clamped) / raw -> device_write 0x37e73880
           |              -> blr vector 0x37f5e478 -> secukey_write 0x37e75e7c
           |                   -> amlkey_write 0x37e8c450 -> C1 [namelen][datalen][flags=0][name][data]
           |                   -> SMC 0x62 -> status only
           |                   -> [secure-class only] SMC 0x64 verify (C1 name, C2 0x20B echo)
           |                   -> memcmp(sp+0x110, sp+0xf0, 0x20) -> 0 / 0x34 / 0x3e / 0x50
           |
           +-> outros comandos
                |
                +-> setkeys 0x37e219f0 (shell-only; direct efuse 0x37e7263c + setenv
                |    + run_command("keyman read %s 1080000 str") constructor 0x37e21864)
                +-> keyunify 0x37e73c84 (shares backends, separate cmd)
                +-> store key 0x37e33a38 (run_command EMITTER for amlnf, not secure SMC)
                +-> run/env (INDIRECT composition mechanism, no static chain to storage)
                +-> rsvmem (fdt secmon range setter, BL31 locator)
                +-> bootm (below, no keyman edge)

boot
 |
 +-> do_bootm 0x37e24c00 (<- autostart 0x37e2501c)
      |
      +-> bootm_load_os 0x37e255c8 (verify/checksum/loading/COMP_NONE)
      +-> avb 0x37e63b88/0x37e63b5c + getenv/setenv/printf family + HW gate 0x37e72790
      +-> AML_DATA_PROCESS 0x820000ff @0x37e19ea8
           |
           +-> 0x40 decrypt: bootm / dtb-verify 0x37e2a030 / store-dtb 0x37e33e00 x2 / kernel 0x37e3601c(x3=4)
           +-> 0x100 query: bootm / dtb-verify / store-dtb x2 / amlsec-helper 0x37e35e7c / dtb 0x37e362e0
           +-> 0x10/11/12/0x20 efuse-writes: efuse handler 0x37e562e8 only
           +-> BL31 UNKNOWN (validation side unobservable from BL33)
```

BRIDGE ANSWER: no demonstrable bridge between host->keyman->secure-world and
boot/secure-verification on static evidence (per-function negative over all 7 boot/AML
parents + string sweeps; only generic libc callees shared). keyman graph terminates at:
RAM sink (read), status codes (write/verify), RAM-env (fmt=str), UART (fmt=hex),
USB via INDEPENDENT fixed-name paths (fastboot `usid`, optimus HDCP八). boot graph
terminates at BL31 (`0x820000ff` with BL33-side validation absent). next material leads
in the same artifacts: setkeys/optimus provisioning flows (factory HDCP/MAC behavior)
and live rsvmem/share-mem locators for exact BL31 (§8). investigation continued past
every intermediate finding per the continuity rule; stopping here per A (bridge
hypothesis closed as storage-only on static evidence), B (BL31 internals unreachable
statically), D (no further plausible static edge).
