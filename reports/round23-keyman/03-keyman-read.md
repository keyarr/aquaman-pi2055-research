# round23 03: do_keyman_read audit (static, code-exact)

chain:
```
do_keyman_read 0x37e750c4
 -> key_info_query 0x37e74c0c (name -> expected len; gate)
 -> key_manage_read 0x37e74d18 (x0=name, x1=caller_buf, w2=len)
 -> per-type branch
 -> [mac]     device_read 0x37e7394c -> device ops (blr, runtime)
 -> [hdcp]    amlkey_read 0x37e8c3e4 DIRECT (caller name 4 B +
              fixed "hdcp2key" 0x35e + fixed "hdcp2lc128" 0x24)
 -> [generic] device_read 0x37e7394c -> device ops (blr, runtime)
 -> low reader 0x37e8bdc8 -> C1 -> SMC 0x61 -> C2 -> caller buf
 -> optional fmt: hexdump | setenv | silent
```

## 3.1 gate: `key_info_query 0x37e74c0c(name, &len)`

- `dev_exist 0x37e74ba4(name)` (device lookup + exist op
  `blr [dev,#0x20]`): fail => `0x1f8`.
- `*len==0` => `0x1fc`. type resolve `0x37e7414c` fail => `0x202`.
- len assignment by type (`x20` = caller len ptr):
  type-magic-0 path: `*len = (len==0) ? 0x11 : (query...)`;
  `0x386` for the `2`-family; else `len_lookup 0x37e73aa0(name, lenptr)`.
- nonzero return aborts `do_keyman_read` (`0x269`) before any SMC.
  unknown names never reach `key_manage_read`. CONFIRMED gate.

## 3.2 `key_manage_read 0x37e74d18` body

- re-runs `0x37e74c0c`, then `cmp queried_len, arg_w19; b.le ok`
  else `0x1ca` (`keySz > bufLen` family). on the shell path the arg
  IS the queried len, so this always passes; a library caller passing
  a short buffer fails here. CONFIRMED clamp.
- re-runs type resolve `0x37e7414c`; fail => `0x1d0`.
- staging: `malloc(0x10000)` (`0x37e74dfc`); all secure reads land
  here first, never directly in the caller buffer. CONFIRMED.
- `ldr w0,[x29,#0x50]` (type):
  - 0 => mac-ascii path `0x37e74e20`: len cap `0x10` (`b.hi` fail
    `-0xa3`), `len_lookup`, `device_read 0x37e7394c(name, staging, len)`,
    then ascii-format loop into caller buf (`%s%02x:`@`0x37ed769e`).
  - 2 => hdcp path `0x37e74f3c`: `w23>0x385` else `0x156`;
    1. `amlkey_read(x21=CALLER name, staging, 4)` want-ret 4
       (`0x37e74f78`, DIRECT bl `0x37e8c3e4`), else `0x15f`.
    2. `amlkey_read("hdcp2key"@0x37ed7535, staging+0x28, 0x35e)`
       want-ret `0x35e` (`0x37e74fc4`), else `0x167`.
    3. `amlkey_read("hdcp2lc128"@0x37ed74f4, staging+4, 0x24)`
       want-ret `0x24` (`0x37e75018`), else `0x16f`.
    4. transform loop `0x386` (`0x37e75090`, via `0x37e740d8`)
       staging -> caller buf `x22`.
  - else => generic `0x37e7506c`: `device_read 0x37e7394c(x21=name,
    x22=caller_buf, w23=len)` -> runtime device vector. CONFIRMED
    no direct `amlkey_read` on this leg.
- `free(staging)`, return `w19` (0 ok).

## 3.3 requested name / lengths / buffers

```text
requested name | x22 = argv[1] pointer (host-controlled, DTS-gated)
requested len  | computed by 0x37e74c0c from DTS/device, NOT parsed
               | from argv (do_keyman_read takes no len arg). CONFIRMED:
               | there is no argv length input on the read path.
output buffer  | x20 = strtoul(argv[2], NULL, 16), arbitrary RAM addr,
               | host-chosen. zero-check only (==0 rejected).
output cap     | checked at key_manage level (queried>=arg, always true
               | on shell path) and inside device ops (runtime). the LOW
               | reader itself (0x37e8bdc8) copies [OUT+0] bytes with NO
               | clamp against the caller len (see 04). staging is
               | malloc(0x10000): secure-reported len >0x10000 would
               | overflow staging -- but len comes from secure world,
               | not from host. recorded, not claimed as host primitive.
returned len   | [OUT+0] -> *caller_len_ptr chain (see 04/C2).
status         | SMC X0; nonzero => no parse, no copy, error prints only.
metadata       | none returned to shell path besides rc. the
               | query/status/tell words (SMC 60/63/65) are NOT reachable
               | from keyman read (sole-caller census, round22 02.3-02.5).
```

## 3.4 return all the way to the caller (not stopping at SMC)

low reader `0x37e8bdc8` returns SMC status `w19` (0 ok).
`amlkey_read 0x37e8c3e4`: nonzero => print + return 0; zero =>
return `[x29,#0x20]` (secure-reported len).
`key_manage_read`: returns `w19` (0 ok / line-code error).
`do_keyman_read`: nonzero => `0x26e` print; zero => fmt handling:
- no fmt word: `w19=0`, silent. blob stays at argv addr only.
- `hex`: hexdump to console (UART), return 0.
- `str`: ascii-check, then `setenv(name, blob)` via `0x37e5848c`
  (builds `{"setenv",name,value,NULL}` + `do_setenv 0x37e58294`;
  argc 3, or 2/delete if value empty). return continues as `w19`.
- other: `Err key dataFmt` print.
final `w0=w19` to `run_command` to `cb_oem`. the blob NEVER enters
the `oem` USB response on this path (no fastboot-send call between
`0x37e750c4` and return; consumer table in round22 03.4 stands).

## 3.5 field classification (read)

```text
name      | host-controlled pointer, DTS-gated (unknown => 0x198/0x269,
          | no SMC). fixed names only inside hdcp leg.
addr      | host-controlled, full 64-bit RAM addr (base-16 parse).
len arg   | NONE on argv. derived from DTS/device query.
slot/idx  | internal. no numeric slot parsing on this path.
fmt word  | host-controlled {hex|str|other}: selects console hexdump /
          | setenv / error-print. no effect on C1/C2 bytes.
C1 bytes  | name only (namelen + hint + name). host picks WHICH key is
          | staged, never bulk payload. CONFIRMED.
C2 bytes  | secure-reported len+blob -> staging -> caller addr
          | (+optional console/setenv copy). content class: opaque blob
          | (see 04/07; plaintext-vs-cipher UNKNOWN).
```
