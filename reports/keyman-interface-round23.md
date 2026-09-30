# keyman interface round23 (consolidated, static only)

image `reports/round14-bl33-persist/bl33-37e18000.bin` base `0x37e18000`.
no device, no reads, no SMC, no commands run. detail: `reports/round23-keyman/01..07`.

round22 proved the CHAIN (`oem -> run_command -> keyman -> SMC 0x61/0x62`).
this round closes the CONTRACT: exact argv syntax, exact gates, exact
C1/C2 layouts, exact output destinations. three round22 statements are
corrected (see 7.3): the generic hop is a runtime device vector, read
takes no argv length, and two new output edges (console hexdump, setenv)
were found. nothing below executes anything.

## main table

```text
operation | command | name control | data control | length control | slot control | C1 | C2 | SMC | output location | host-readable | confidence
write/hex | keyman write <n> hex <hexdata> | argv gated (DTS) | hex-decoded, type-checked | strlen/2, oem-cut | none (name-keyed) | namelen+datalen+flags=0+name+data | - | 0x62 | secure store only | n/a (write) | HIGH (parser) / MED (generic hop runtime)
write/str | keyman write <n> str <ascii>   | argv gated (DTS) | ascii-only (<0x80), type-checked | strlen, oem-cut | none | same C1 | - | 0x62 | secure store only | n/a | HIGH / MED
write/num | keyman write <n> <len> <addr>  | argv gated (DTS) | RAM bytes @addr, type-checked | strtoul b0, <=0x10000 | none | same C1 | - | 0x62 | secure store only | n/a | HIGH / MED
write/hdcp| (type-2 flow, magic 0x02000000, >0x385 B) | fixed hdcp2lc128/hdcp2key + caller 4 B | 0x386 transform | exact 0x24/0x35e/4 | none | same C1, direct bl | - | 0x62 | secure store | n/a | HIGH (direct edge)
read      | keyman read <n> <addr> [hex|str] | argv gated (DTS) | n/a (no data in) | NO argv len (DTS-queried) | none | namelen+hint+name | len+blob | 0x61 | caller RAM @addr (+heap freed; +console/env w/ fmt) | UNKNOWN (RAM-primitive dependent) | HIGH (parser+C1/C2) / MED (generic hop runtime)
query     | keyman query ... | console words only | - | - | - | - | - | - | console | n/a | HIGH (negative: no amlkey edge)
```

## final conclusion

```text
keyman write:
  host controls name/data? YES, GATED (DTS cfg + per-type validators) — CONFIRMED
  reaches SMC 0x62? YES (direct for hdcp fixed names; runtime device
    vector otherwise) — CONFIRMED
  size bounded? YES (0x11 / >0x14 / >0x385+magic / <=0x10000 / exact
    0x24,0x35e,4) — CONFIRMED
  names restricted? YES (unknown name => reject before any SMC) — CONFIRMED

keyman read:
  host controls name? YES, GATED (DTS; no argv len exists) — CONFIRMED
  reaches SMC 0x61? YES (direct in hdcp leg; runtime vector otherwise) — CONFIRMED
  output type? opaque blob (len+bytes shape CONFIRMED, content UNPROVEN) — CONFIRMED
  output destination? caller RAM @argv[2] addr (host-chosen); heap staging
    freed; fmt=hex adds console hexdump, fmt=str adds setenv(name,blob) — CONFIRMED
  host-readable through existing RAM-read path? UNKNOWN — UNPROVEN
```

contract closed:

```text
host
 -> keyman read/write (DTS-validated, type-checked)
 -> C1[+0x00 namelen,+0x04 datalen/hint,+0x08 flags/name,data...]
 -> SMC 0x62 (status) / 0x61 (C2[+0x00 len,+0x04 blob] -> argv RAM)
 -> secure world
```

what enters and leaves is above, byte-exact. what the bytes mean on the
secure side is UNPROVEN. not key extraction, not credential disclosure,
not exploit. static only.
