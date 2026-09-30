# round23 05: name / slot audit (static, code-exact)

no numeric slot parsing exists anywhere on the keyman path (no `strtoul`
of a slot, no `[slot]` table indexed by argv). the addressable unit is
the key NAME string. CONFIRMED.

## 5.1 exact hard-coded strings in keyman code

```text
name/slot    | source                         | host-controlled? | fixed? | read | write | size    | confidence
hdcp2lc128   | rodata 0x37ed74f4, direct bl   | NO (fixed)       | YES    | YES  | YES   | 0x24    | CONFIRMED
hdcp2key     | rodata 0x37ed7535, direct bl   | NO (fixed)       | YES    | YES  | YES   | 0x35e   | CONFIRMED
hex          | rodata 0x37ed7572 (fmt word)   | fmt selector     | n/a    | n/a  | n/a   | n/a     | CONFIRMED
str          | rodata 0x37ebf6d4 (fmt word)   | fmt selector     | n/a    | n/a  | n/a   | n/a     | CONFIRMED
mac          | 0x37ebf6e2 (type override)     | name probe       | n/a    | n/a  | n/a   | n/a     | CONFIRMED
mac_bt       | 0x37ebf674 (type override)     | name probe       | n/a    | n/a  | n/a   | n/a     | CONFIRMED
mac_wifi     | 0x37ebf67b (type override)     | name probe       | n/a    | n/a  | n/a   | n/a     | CONFIRMED
hdcp2        | 0x37ed72f7 (type override)     | name probe       | n/a    | n/a  | n/a   | n/a     | CONFIRMED
```

the four override probes only steer the DTS-`raw` type id (02.2);
they are strcmp targets, not an allowlist: any other name keeps its
DTS type. do NOT read them as "only these names work".

## 5.2 validated (DTS-bound) names: the real gate

every other name is validated, not enumerated, in the image:

1. `type_resolve 0x37e7414c` requires a DTS key-type cfg for the name
   (`0x37e756e4` lookup; missing => nonzero return, `0x198` abort).
2. `dev_exist 0x37e74ba4` requires a runtime device binding for the name
   (device list head `0x33e35fc0` is DDR-populated, outside the image).
3. per-type format validators (mac/sha1/hdcp2 shapes, 02.3).

consequence: the SET of usable names lives in the DTS + runtime device
list, neither of which is fully recoverable from the BL33 image alone.
any table of "supported names" beyond the two hdcp fixed strings would
be convention-based guessing. NOT done here. the auditable claim is the
VALIDATION SHAPE, not a name list:

```text
arbitrary caller string | DTS cfg? no  -> REJECT (0x198/0x269/0x2a paths) | CONFIRMED
arbitrary caller string | DTS cfg? yes -> per-type validator -> device op | CONFIRMED (mechanism)
fixed hdcp2*            | always bound  | direct amlkey edge               | CONFIRMED
prefix matching         | NONE found (all strcmp are exact/len match)      | CONFIRMED (negative)
numeric IDs             | NONE (no slot parsing)                           | CONFIRMED (negative)
```

## 5.3 per-name control summary

```text
caller-supplied name (argv[1]) | host picks string | DTS+format gated | read: stages C1 name, dest = argv addr | write: mac/sha1/raw via device vector (runtime), hdcp-flow direct | CONFIRMED (gated)
hdcp2lc128 / hdcp2key          | fixed             | exact sizes       | direct amlkey_read/write               | CONFIRMED
```

## 5.4 what was NOT found (negatives, code-exact)

- no wildcard/prefix compare on key names (`find_cmd` len-match is for
  SUBCOMMAND words `read/write/query`, not key names).
- no numeric slot/index argv on keyman read/write (the query path
  takes name words too).
- no allowlist array of key names in the image (only the 4-entry
  TYPE list `{mac,sha1,hdcp2,raw}` @`0x37eb5058`, which is types,
  not key names; and the DTS, which is data, not code).
- no length field parsed from argv on the read path at all.
