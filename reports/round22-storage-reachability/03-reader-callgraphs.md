# round22 03: reader callgraphs (the five C2 readers)

slot: `[0x37fbde58]` = OUT base (`0x05040000` at runtime). BL33 never stores
into `[[slot]]` (zero stores, round21 03); BL31 fills it after SMC 60/61/63/
64/65. readers are the same five functions as writers 2-6 (write has no OUT
parse). handler/consumer/status/blob/return questions answered per reader.

## 3.1 reader 0x37e8bdc8 (read/0x61): len+blob -> caller buf

```
... SMC 0x61 ...; cbnz x0 -> fail (no parse, return SMC status)
x1 = [OUT slot] (loaded BEFORE the SMC at 0x37e8be24, reused after)
ldr w2,[x1],#4        ; w2 = [OUT+0] = len, x1 past it
str w2,[x22]          ; *caller_len_ptr (x22 = arg x3) = len
memcpy(x21, x1, w2)   ; x21 = arg x1 = caller buffer
return SMC status path value (0 on this path)
```

- handler: `amlkey_read 0x37e8c3e4` (`add x3,x29,#0x20` len slot), then
  `key_manage_read 0x37e74d18` (malloc `0x10000` buf at `0x37e74e00`, three
  `amlkey_read` sites for the hdcp/generic branches), then `do_keyman_read
  0x37e750c4` (shell) and the fastboot/burning readers.
- consumer of OUT: the caller's RAM buffer. shell path: `argv[2]`-parsed
  address (plus malloc staging inside `key_manage_read`). fastboot path:
  bss `0x37fbdf48`-ish buffer returned to `0x37e948a8`.
- use of status: `cbnz` on the SMC return register; buffer untouched on
  failure. upper wrappers (`key_manage_read`, `do_keyman_read`) print
  `[KM]Error` / `ERR` only on nonzero status, never dump the blob.
- use of blob: shell path keeps it in RAM (no `printf` of payload, no
  `setenv`, no file output traced). fastboot path (`0x37e948a8` tail:
  `bl 0x37e94838` then `bl 0x37e947d4` send + `0x37e5abc4` plumbing) forwards
  the buffer toward the USB response. so the SAME reader has two consumers:
  silent-RAM (oem/run_command) vs host-response (fastboot direct).
- eventual return to user: via `oem keyman read`: return code only (0/err);
  payload stays at the argv-chosen address. via fastboot download-key flow:
  payload is sent back (independent path, not via `run_command`).

reachability: YES via `run_command` (`keyman read`, same chain as 02.2).

## 3.2 readers 0x37e8be98 / 0x37e8bf3c / 0x37e8bfe0 (query/status/tell): word

```
... SMC 0x60/0x65/0x63 ...; cbnz x0 -> fail
ldr w1,[x21]     ; [OUT+0] word, x21 = [OUT slot]
str w1,[x20]     ; *caller (x20 = arg x1) = word
```

- handlers: `amlkey_isexsit 0x37e8c2ec` / `amlkey_get_attr 0x37e8c16c` /
  `amlkey_size 0x37e8c374` (each: `add x1,x29,#0x20` stack slot, error-print
  + `str wzr` on failure, `ldr w0,[x29,#0x20]` return).
- consumer: one stack word in the wrapper; returned as integer, never
  `memcpy`d as a blob, never stored to env/eMMC, never formatted beyond the
  `[KM]Error` / `do_keyunify` prints on failure.
- return to user: fastboot shim checks the word (`cbnz`/`cmp #0x1f`) to gate
  the subsequent read; the word itself is not printed or sent. shell paths:
  none demonstrated (no `bl` from any command handler).
- exposure: normal-world integer only (exists/attr/size). no key material.

reachability via `run_command`: NO (section 02.3-02.5). exposure to command
path: none demonstrated.

## 3.3 reader 0x37e8c084 (verify/0x64): fixed 0x20 B

```
... SMC 0x64 ...; cbnz x0 -> fail
memcpy(x21/caller, x22/OUT, 0x20)   ; x21 = arg x1, x22 = [OUT slot]
```

- handler: trampoline `0x37e8c508` <- `0x37e75e7c secukey_write` (offset
  `0x37e75f78`: `x0=name, x1=stack 0xf0 buf`; after the call the 0x20 B at
  `0x29+0xf0` is compared word-wise against `0x29+0x110` via `memcmp`
  (`0x37eaafac`) and hex-formatted on mismatch; match prints success).
- consumer: caller stack buffer, then an in-function `memcmp`, never leaves
  the function except as a return code.
- use of status/blob: status gates the copy; blob is 32 bytes compared
  locally (digest-sized, unnamed: do NOT call it hash/key without proof).
- return to user: return code only. no `printf` of the blob, no env, no file,
  no fastboot response on this path.

reachability via `run_command`: NO (table-only root, 02.6).

## 3.4 terminus audit (do any of these end in user-visible output?)

| reader | printf of payload | setenv/env | file/eMMC | fastboot response | command return |
|---|---|---|---|---|---|
| 0x37e8bdc8 shell (`keyman read`) | NO (errors only) | NO | NO | NO | YES (code) + RAM side-effect |
| 0x37e8bdc8 fastboot (`0x37e94838`) | NO | NO | NO | YES (via `0x37e948a8` USB send) | n/a (fastboot status) |
| 0x37e8be98/0x37e8bf3c/0x37e8bfe0 | NO (errors only) | NO | NO | NO (gate only) | YES (word) but unreachable via run_command |
| 0x37e8c084 | NO (errors only) | NO | NO | NO | YES (code) but unreachable via run_command |

bottom line: the only reader that is BOTH `run_command`-reachable AND moves
key-sized bytes is `0x37e8bdc8` via `keyman read`, and on that path the bytes
land in argv-chosen RAM without a print/send. the fastboot twin of the same
reader DOES send bytes back, but that path does not go through `run_command`.
do not conflate the two when answering "exposure to the command path".
