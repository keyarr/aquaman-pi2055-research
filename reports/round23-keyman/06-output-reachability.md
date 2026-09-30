# round23 06: output reachability (static, code-exact)

question: does `keyman read` output land anywhere the existing host
RAM-read primitives (`AM_REQ_READ_MEM`, `mread 0x34+0x33`) can already see,
and does any of it come back over `fastboot oem` itself?

## 6.1 address chain (all links code-exact)

```
SMC 0x61
 -> C2 @[0x37fbde58] (=0x05040000): [OUT+0]=len, [OUT+4..]=blob
 -> low reader 0x37e8bdc8: memcpy(caller_buf, OUT+4, len)
    caller_buf = staging = malloc(0x10000) @0x37e74dfc (heap, ASLR-free
    U-Boot: deterministic-ish per boot, NOT a fixed address)
 -> key_manage leg:
    hdcp: transform loop -> caller RAM @x22
    mac:  ascii-format loop -> caller RAM @x22
    generic: device read op -> caller RAM @x22
    x22 = x20 = strtoul(argv[2], NULL, 16)  (do_keyman_read 0x37e75104)
 -> final RAM address = HOST-CHOSEN argv addr (any 64-bit RAM value != 0)
 -> return value only propagates to oem (w19 chain, 03.4)
```

so the FINAL address is not fixed/derivable by the image: the host
chooses it per invocation. that is stronger than a fixed address: the
host can aim the output at any RAM it can already read (e.g. a known
readable window) — IF such a window exists — but the image itself hands
no fixed address and no USB response. the blob's presence in RAM is
CONFIRMED; its host-readability through `mread`/Optimus is a property
of the RAM primitives' windows, not of keyman, and is UNKNOWN in this
static round (no live probe per the brief).

## 6.2 consumers per fmt word (do_keyman_read tail)

```text
no fmt  | blob at argv addr only. no print, no setenv, no USB.      | CONFIRMED (0x37e75234)
hex     | + hexdump to CONSOLE (UART): 0x37e735c8 prints
        | "[KM]Msg:key len is %d..." + %02x lines. NOT the oem USB
        | response (cb_oem never forwards handler stdout).          | CONFIRMED
str     | + ascii check, then setenv(name=x22, value=blob) via
        | 0x37e5848c -> do_setenv 0x37e58294. blob enters ENV store
        | (RAM). still no USB. env can later be printed/saved by OTHER
        | commands, but that stitching is mechanism-only, UNPROVEN as a
        | chain here (not executed, per static-only rule).          | CONFIRMED (edge) / UNPROVEN (chain)
other   | Err print, blob stays at argv addr.                       | CONFIRMED
```

## 6.3 stack vs heap vs chosen RAM

- C2 slots: fixed globals (`0x05000000/0x05040000` runtime) — secure
  world writes them, host cannot `mread` secure RAM, and BL33 never
  re-exposes the raw C2 after copying out. transient.
- staging: `malloc(0x10000)` heap, freed (`0x37e59cd4`) before return
  on every leg (`0x37e74854` / `0x37e75080`). use-after-free read via
  mread would be heap-grooming speculation: UNPROVEN, not claimed.
- caller buffer: argv-chosen RAM, persists after return (caller-owned).
  this is the ONLY output copy with a host-known address, precisely
  because the host picked it. CONFIRMED.
- stack: query/status words only (never reached via keyman); the
  `0x29+0x30/0x40/0x48/0x50` slots hold lens/types, not key bytes
  (the 4-B caller-name hdcp read stages through heap, not stack).
  no stack-resident blob to chase. CONFIRMED (negative).

## 6.4 verdict

```text
output destination      | caller RAM @argv[2] addr (+heap staging, freed) | CONFIRMED
fixed/derivable address | NO (host-chosen, not image-fixed)               | CONFIRMED
stack temporary         | NO blob on stack (lens/types only)              | CONFIRMED
in oem USB response     | NO (return code only)                           | CONFIRMED
on UART console (hex)   | YES with fmt word (needs UART tap, not host USB)| CONFIRMED (edge)
in env store (str)      | YES with fmt word (RAM env, no USB by itself)   | CONFIRMED (edge)
host-readable via mread | UNKNOWN (depends on RAM-primitive windows over
                        | the chosen addr; no live probe this round)      | UNPROVEN
```

bottom line: keyman read is a host-aimed RAM writer, not a host-facing
reader. it puts secure-reported bytes exactly where the host points,
and tells the host nothing back over USB. whether that RAM is then
readable is a question about the RAM primitives, answered elsewhere,
not here. no key extraction, no credential disclosure claimed.
