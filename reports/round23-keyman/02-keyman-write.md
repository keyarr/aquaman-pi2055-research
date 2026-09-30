# round23 02: do_keyman_write audit (static, code-exact)

chain:
```
do_keyman_write 0x37e749ac
 -> key_manage_write 0x37e7430c   (x0=name, x1=data, w2=len)
 -> per-type branch
 -> [generic] device_write 0x37e73880 -> device ops vector (blr, runtime)
 -> [hdcp]    amlkey_write 0x37e8c450 (x0=name, x1=data, w2=len, w3=0)
 -> low writer 0x37e8bd10 -> C1 -> SMC 0x62
```

## 2.1 gate 1: device/key init `0x37e73864`

`key_manage_write` first calls `0x37e73864` (via `0x37e73380` device
lookup + `0x37e75590` type-precheck). nonzero => print + return `0x192`.
then type resolve:

```
x0=name, x1=&type([x29,#0x64])
bl type_resolve 0x37e7414c -> w19
if w19: print + return 0x198        ; unknown name / no DTS cfg
```

so a name with no DTS entry never reaches any write. CONFIRMED gate.

## 2.2 gate 2: `type_resolve 0x37e7414c` (name -> type id)

- reads DTS key-type string for the name (`0x37e756e4`; missing cfg =>
  `0x2a` error path, nonzero return).
- compares against 4-entry list @`0x37eb5058`: `{mac, sha1, hdcp2, raw}`.
  match index => type 0..3.
- if DTS type is `raw` (index 3), name overrides apply:
  `name=="mac"|"mac_bt"@0x37ebf674|"mac_wifi"@0x37ebf67b` => type 0;
  `name=="hdcp2"@0x37ed72f7` => type 2 (`csel` at `0x37e74260`).
- stores type id to caller slot, returns 0.

type id is DERIVED (DTS + name), not host-free. CONFIRMED.

## 2.3 dispatch on type (jump table @`0x37ebea34`, `ldrh [base+w0*2]`)

```text
type 0 (mac)   -> 0x37e743d8
type 1 (sha1)  -> 0x37e74668
type 2 (hdcp2) -> 0x37e74790
type 3 (raw)   -> 0x37e74840
type >3        -> free + return w19 (==0 here; unreachable: resolve
                  only yields 0..3). dead edge, not a bypass.
```

### type 0 mac (`0x37e743d8`)

- `w22(len)` must `==0x11` (17, ascii `xx:xx:...`), else `w19=-0x16`,
  prints, return. CONFIRMED clamp.
- format loop `0x37e74420`: every 3rd char must be `:` (`cmp #0x3a`),
  others hex digits (table @`0x37eb5098`, mask `0x44`); violation =>
  `0x63/0x68` error returns. CONFIRMED.
- then `hdcp?-check 0x37e75590(name)` == 4 required, else `0x6f`.
- then `len_lookup 0x37e73aa0(name, &len)`; len must be `0x11` or `6`,
  else `0x7c`. then `device_write 0x37e73880(name, data, len)`.
- host controls name+data, but data must be a valid 17-char MAC
  (or 6-B form) and the name must be DTS-typed mac. constrained.

### type 1 sha1 (`0x37e74668`)

- `w22>0x14` (20) required, else `0xd2` print + return.
- `memcmp`-style check of trailing `0x14` bytes (`0x37e746b4..`)
  against caller tail; mismatch => hexdump prints + `0xe6` return.
- match => `device_write 0x37e73880(name, data, w22)`.
- constrained: 20-B suffix discipline, DTS-typed sha1 only.

### type 2 hdcp2 (`0x37e74790`)

- `w22>0x385` (901) required, else `0x126` print + return.
- LE magic at `data[0..3]` must `==0x02000000`, else `0x12a` print.
- loop `0x386` (902) bytes through `0x37e740d8` into malloc buf.
- three DIRECT `bl amlkey_write 0x37e8c450`:
  1. `0x37e748a0`: name=`"hdcp2lc128"`@`0x37ed74f4` FIXED,
     data=`buf+4`, len `0x24`, flags 0. want-ret `0x24`.
  2. `0x37e748f8`: name=`"hdcp2key"`@`0x37ed7535` FIXED,
     data=`buf+0x28`, len `0x35e`, flags 0. want-ret `0x35e`.
  3. `0x37e7494c`: name=`x21` CALLER name, data=`buf`, len `4`,
     flags 0. want-ret `4`.
- mismatch on any => `0x138/0x140/0x147` prints.
- this is the ONLY statically direct argv-name -> `amlkey_write` edge,
  and it fires only inside the hdcp2 flow (magic + 902-B shape +
  DTS hdcp2 typing). name FIXED for slots 1-2, CALLER for slot 3
  (4 bytes, transformed buffer, not raw argv bytes).

### type 3 raw (`0x37e74840`)

- straight `device_write 0x37e73880(x21=name, x20=data, w22=len)`.
- NO direct `bl amlkey_write`. CONFIRMED (disasm `0x37e74840..4c`).

## 2.4 `device_write 0x37e73880` (generic hop, runtime-resolved)

```
x20 = device_lookup 0x37e73380(name)   ; walks runtime list @[0x37f89fe0]
if !x20: print + return 0x107          ; head is DDR (0x33e35fc0): DTS-populated
if ![x20,#0x38]: print + return 0x10f
x3 = [x20,#0x20]?? -> blr x3           ; device write op (per-device)
```

the head pointer `0x33e35fc0` is outside the image: the device list is
populated at runtime from DTS. which device (secure/efuse/emmc) serves
a given name is therefore UNPROVEN statically. whether the secure
device's op wraps `amlkey_write` is UNPROVEN statically (no image edge;
only the hdcp direct sites are CONFIRMED).

correction to round22 02.1: the "generic third site ... the one the
shell path hits" is NOT a direct `bl amlkey_write` with raw argv. the
site at `0x37e7494c` is the hdcp-flow 4-B caller-name write (transformed
buf). the true generic hop is `0x37e73880 -> blr` (runtime vector).

## 2.5 field classification (write)

```text
name      | host-controlled (argv'[1] pointer) but GATED: DTS cfg +
          | type resolve must succeed; fixed "hdcp2lc128"/"hdcp2key"
          | for the two direct SMC writes
data      | host-controlled (hex-decoded / ascii / RAM-addr bytes) but
          | per-type format-checked (mac/sha1/hdcp2 shapes)
data_len  | host-influenced, bounded: hex strlen/2 (oem-truncated in
          | practice), ascii strlen, numeric <=0x10000; mac ==0x11,
          | sha1 >0x14, hdcp2 >0x385 enforced in key_manage
flags     | constant 0 (all three direct sites mov w3,#0). CONFIRMED
slot/idx  | internal (DTS device binding + SMC-side naming). host picks
          | the key NAME, not a numeric slot. no numeric slot parsing
          | anywhere on this path. CONFIRMED (no slot argv)
argv->SMC | TRANSFORMED, not raw: type resolve + format validators +
          | (generic) runtime device dispatch sit between argv and C1.
          | only hdcp fixed-name payloads reach C1 byte-identical after
          | the 0x386 transform loop.
```

verdict: `argv reaches SMC 0x62 without transformation` = REFUTED for
the generic path (validators + dispatch in between); direct untransformed
reach exists only for the two FIXED hdcp names (host does not control
the name there, only the payload shape).
