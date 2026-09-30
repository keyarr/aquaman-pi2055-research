# round23 01: keyman parser (static, code-exact)

image `reports/round14-bl33-persist/bl33-37e18000.bin`, base `0x37e18000`.
method: capstone disasm of bytes on disk + `bl33_audit.py`. no device.

helpers used below: `strcmp 0x37eaacac`, `strlen 0x37eaad30`,
`memcpy 0x37eaaeec`, `strtoul 0x37eac21c`, `printf 0x37e593c8`,
`malloc 0x37e59f28`, `free 0x37e59cd4`, `find_cmd 0x37e5eddc`
(entry stride `0x30`, exact/len match, ambiguous => NULL).

## 1.1 dispatcher `keyman 0x37e74290`

```
cmp w2,#1 / b.gt ok else w0=-1, ret        ; argc>1 required
x0=[x3,#8]              ; argv[1] = subcommand word
x1=tbl 0x37f5e4f8, w2=5 ; find_cmd(tbl, len 5)
bl find_cmd ; cbz => w0=-1, ret
x4=[x0,#0x10]           ; entry cb (stride 0x30 => +0x10 is cb)
blr x4 with (x0=orig x0, w1=orig flag, w2=argc-1, x3=argv+1)
```

sub-table `0x37f5e4f8` (48 B entries: name*, maxargs, cb, usage, help, pad):

```text
+0x00 "init"  maxargs 3 -> 0x37e74120
+0x30 "exit"  maxargs 2 -> 0x37e74148
+0x60 "read"  maxargs 4 -> 0x37e750c4 (do_keyman_read)
+0x90 "write" maxargs 4 -> 0x37e749ac (do_keyman_write)
+0xc0 "query" maxargs 3 -> 0x37e75304 (do_keyman_query)
```

maxargs is NOT enforced by the dispatcher (no check before `blr`);
each sub-handler enforces its own argc floor. CONFIRMED.

## 1.2 `do_keyman_write 0x37e749ac` (write parser)

entry: `w2=argc'`, `x3=argv'` (`argv'[0]="write"`).
floor: `cmp w2,#3 / b.le fail(-1)`. so `argc'>3`, i.e. original
`keyman write ...` needs `argc>=5` counting `keyman` itself... precisely:
`argv'=[write,name,X,Y?]`, minimum 4 tokens after dispatch.
`x23=[x3,#8]` = `argv'[1]` (name), `x20=[x3,#0x10]` = `argv'[2]`.

three formats, selected by `strcmp(argv'[2], ...)`:

### fmt A: hex

```
strcmp("hex"@0x37ed7572, argv'[2]) == 0
x22 = argv'[3] ([x19,#0x18])
len = strlen(x22)/2            (lsr #1, no cap in code)
buf = malloc(len)
err = keyman_hex_ascii_to_buf 0x37e73404(x22, buf, len)
if err: printf "Fail in change hex argv[3] to bin, err=%d"@0x37ed7576
        free(buf), return 1
key_manage_write(name=x23, buf, len) ; x20=buf freed after
```

syntax: `keyman write <name> hex <hexstring>`. CONFIRMED.

### fmt B: str (ascii)

```
strcmp("str"@0x37ebf6d4, argv'[2]) == 0
x19 = argv'[3]
len = strlen(x19)
loop over bytes: tbz bit7 else fail:
  printf "inputFmt is %s, but argv[3] contain non ascii"@0x37ed75a1
  return 1
key_manage_write(name=x23, data=x19, len) ; no malloc, x20=0
```

syntax: `keyman write <name> str <asciistring>` (bytes must be `<0x80`).
CONFIRMED.

### fmt C: numeric (addr+len)

```
len = strtoul(argv'[2], NULL, base 0)      ; 0x37e74ac8: x1=0, w2=0
if len==0: printf "dataLen err"@0x37ed75d0, return 0x2bb
if len>0x10000: printf "keylen 0x%x too large!"@0x37ed75dd, return 0x2bf
addr = strtoul(argv'[3], NULL, base 0x10)  ; 0x37e74b48
key_manage_write(name=x23, data=addr, len) ; no malloc
```

syntax: `keyman write <name> <len> <addr>`. CONFIRMED.
this is the short form: no payload bytes on the command line,
so it fits the 33 B `oem` truncation budget (round22 01).

return: `key_manage_write` rc `w19`; free buf if any; `w0 = (w19!=0)`.
write errors never print the data, only lengths/codes.

## 1.3 `do_keyman_read 0x37e750c4` (read parser)

entry: `w2=argc'`, `x3=argv'`.
`x22=[x3,#8]` = `argv'[1]` (name).
`x21 = (argc'>3) ? argv'[3] : 0` (optional fmt word).
floor: `cmp w2,#2 / b.le fail(-1)`. so `read <name> <addr> [fmt]`.
`x20 = strtoul(argv'[2], NULL, 0x10)`; if 0:
printf "Fail in parse argv[2] to dataBuf"@0x37ed76f5, return `0x263`.
`rc = key_info_query 0x37e74c0c(name, &[x29+0x30])`; nonzero => `0x269`.
`rc = key_manage_read(name, addr=x20, len=[x29+0x30])`; nonzero =>
printf "Fail in read key[%s] at sz %zd"@0x37ed7717-ish, return `0x26e`.
optional 4th word `x21`:
- NULL => success 0, silent.
- `strcmp=="hex"@0x37ed7572` => `hexdump 0x37e735c8(addr, len, 0)`:
  prints `[KM]Msg:key len is %d, hex value in hexdump:`@0x37ed6f3b
  + per-line `[0x%04x]:` / `%02x ` to console. return 0.
- `strcmp=="str"@0x37ebf6d4` => ascii check loop (`ldrsb`+`tbz #31`;
  fail: `[KM]Msg:key value has non ascii, can't pr`@0x37ed7737,
  return 1), else `setenv_helper 0x37e5848c(name=x22, value=addr-buf)`.
  return value of setenv path (falls through to `w19`).
- anything else => printf `[KM]Msg:Err key dataFmt(%s)`@0x37ed7762.

syntax: `keyman read <name> <addr> [hex|str]`. CONFIRMED.
example in rodata: `keyman read %s 1080000 str`@0x37ebf6bd
(template used byາດownload-key code, not by the parser itself).

## 1.4 `do_keyman_query 0x37e75304` (query parser, no storage edge)

floor `argc'>2` else -1. `x20=argv'[1]`, `x19=argv'[2]`.
branch on `strcmp(argv'[1], ...)`:
- `"..."@0x37ed715f` ("exist"-family) => `dev_exist 0x37e74ba4(name)`
  + console print, return 0/1 as boolean, never SMC.
- second word family @`0x37ed713a` ("secure"-family) =>
  `0x37e75254` path, console print only.
- else => `key_info_query 0x37e74c0c` + console print of size.
uses `0x37e74ba4 / 0x37e75254 / 0x37e74c0c` only.
zero `bl` to any `amlkey_*`. CONFIRMED no C1/C2 edge (agrees round22).

## 1.5 summary table

```text
command                            | handler  | argc' floor | argv roles
keyman <sub> ...                   | 0x37e74290 | argc>1   | argv[1]=sub word
keyman write <n> hex <hex>         | 0x37e749ac | argc'>3  | [1]=name [2]="hex" [3]=hexdata
keyman write <n> str <ascii>       | 0x37e749ac | argc'>3  | [1]=name [2]="str" [3]=asciidata
keyman write <n> <len> <addr>      | 0x37e749ac | argc'>3  | [1]=name [2]=len(base0) [3]=addr(base16)
keyman read <n> <addr> [hex|str]   | 0x37e750c4 | argc'>2  | [1]=name [2]=addr(base16) [3]=fmt?
keyman query ...                   | 0x37e75304 | argc'>2  | console status only, no SMC
```

all syntax rows CONFIRMED by instruction-level branches above.
numeric bases: len base 0, addr base `0x10`. caps: hex none in code,
str ascii-only, numeric len `<=0x10000`, addr==0 rejected.
