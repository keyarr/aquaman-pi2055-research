# BL31 AML_DATA_PROCESS round 17: E3 closed on the BL33 side, unproven on the BL31 side

date: 2026-09-30. static only, no device, no USB, no execution.
image: reports/round14-bl33-persist/bl33-37e18000.bin (0x37e18000..0x37ff0000,
sha256 664fb34a9c6d92cdcd576659fb5359bd5218841612dbf38c01426c5d3c1b7818).
reference: .src/u-boot-khadas (bl31_apis.c/h, cmd_bootm.c, fip/gxl+gxb bl31.bin).
tool: tools/bl33_round17.py. detail: reports/round17-bl31/00..06.
tests: TestBl33Round17 in tools/run_tests.py (7 tests, pass; full suite 72 pass).

Round 16 confirmed ddr_test_copy is pattern-fill + tail, not arbitrary write.
This round does not revisit that as an exploit. It answers E3 from assembly.

## A. caller in BL33 (all 15 sites, one SMC site)

One `smc #0` sends 0x820000ff: 0x37e19ed8 inside wrapper 0x37e19ea8.
15 `bl 0x37e19ea8` in 7 functions. Wrapper shuffle (02-wrapper.txt):

```text
x7=x0(type) x6=x1(buf) x5=x2(len) x4=x3(opt preserved)
x0=0x820000ff (mov x0,#0xff; movk x0,#0x8200,lsl#16)
x1=x7 x2=x6 x3=x5 (x4 untouched); smc #0
add x1,x6,x5; mov x0,x6; bl 0x37e19310 (flush, wraps, no check)
return SMC x0
```

So BL(x0,x1,x2,x3)=(type,buf,len,opt) maps to
SMC(X0=0x820000ff,X1=type,X2=buf,X3=len,X4=opt). Full windows: 00-e3sites.txt.

| site | func | BL x0..x3 | SMC X1..X4 | origin |
|---|---|---|---|---|
| 0x37e24cf0 | 0x37e24c00 bootm | 0x40, argv-hex else 0x1080000, 0x1800000, 7 | 0x40, host-addr, 0x1800000, 7 | register <- argv via simple_strtoul 0x37eac21c, else immediate |
| 0x37e24f90 | 0x37e24c00 bootm | 0x100, 0x1080000, 0x500, 7 | same | immediates (bl 0x37e5b2f0 result goes to x19, not to the call) |
| 0x37e2a088 | 0x37e2a030 check_valid_dts | 0x40, x20, 0x3fe00, 0 | same | x20 = env/partition buffer (getenv 0x37e589a0 + memcpy) |
| 0x37e2a0c4 | 0x37e2a030 | 0x100, 0x1080000, 0x500, 7 | same | immediates |
| 0x37e33e94 | 0x37e33e00 store | 0x40, x20, 0x3fe00, 0 | same | x20 = argv hex via simple_strtoul, gated by 0x37ea14e0 (fail path skips call) |
| 0x37e33ec8 | 0x37e33e00 | 0x100, 0x1080000, 0x500, 7 | same | immediates |
| 0x37e34084 | 0x37e33e00 | 0x40, x21, 0x3fe00, 0 | same | x21 = argv hex, same gate shape |
| 0x37e340d4 | 0x37e33e00 | 0x100, 0x1080000, 0x500, 7 | same | immediates |
| 0x37e35ec4 | 0x37e35e7c imgread | 0x100, 0x1080000, 0x500, 7 | same | immediates |
| 0x37e3623c | 0x37e3601c imgread | 0x40, x19, 0x1800000, 4 | 0x40, image-buf, 0x1800000, 4 | argv hex or env default, gated by image-parse 0x37e351f8 (opt 4, not 7) |
| 0x37e36340 | 0x37e362e0 imgread | 0x100, 0x1080000, 0x500, 7 | same | immediates (argv parse goes to x19, not to the call) |
| 0x37e565e4 | 0x37e562e8 efuse | 0x10, x19, 0x500, 0 | same | x19 = sharemem input base from BL31 (get_sharemem_info 0x82000020 via 0x37e19d68) |
| 0x37e56664 | 0x37e562e8 | 0x20, x19, 0x500, 0 | same | same sharemem base |
| 0x37e566f4 | 0x37e562e8 | 0x11, x19, 0x500, 0 | same | same sharemem base |
| 0x37e56774 | 0x37e562e8 | 0x12, x19, 0x500, 0 | same | same sharemem base |

Only 0x37e24cf0 passes a raw host address. Sustained pseudocode (matches
common/cmd_bootm.c:133-142 and the bytes at 0x37e24cc8..0x37e24cf0):

```text
nLoadAddr = 0x1080000
if (argc > 0) nLoadAddr = simple_strtoul(argv[0], &endp, 16) // w1=w0, 32-bit truncate
// subcommand check on *endp (':'/'#'/find_cmd) elided; non-subcommand falls through
nRet = aml_sec_boot_check(0x40, nLoadAddr, 0x1800000, 7)
// -> SMC X0=0x820000ff X1=0x40 X2=nLoadAddr X3=0x1800000 X4=7
if (nRet) printf("aml log : Sig Check %d"); // fails closed
```

No compare of nLoadAddr against RAM top 0x38000000, DTB, or image header
anywhere before the call. do_bootm truncates to 32 bits (mov w1,w0) then
zero-extends; high bits are dropped, not checked. No X2+X3 overflow check
in BL33 (wrapper `add x1,x6,x5` can wrap).

## B. BL31 dispatch: what exists, what does not

| artifact | class | note |
|---|---|---|
| .src/u-boot-khadas/fip/gxl/bl31.bin (0x2c3a8) | FAMILY REFERENCE | AMLSECU/secureboot strings present; no 0x820000ff word, no movz/movk 0x8200/0x00ff pair, no smc #0 (BL31 receives, does not execute) |
| .src/u-boot-khadas/fip/gxb/bl31.bin (0x16120) | FAMILY REFERENCE | same shape + `exceed max DMA SHA2/AES` strings (neighbor paths) |
| .src/u-boot-khadas/fip/gxl/bl31.img | FAMILY REFERENCE | FIP wrapper around the same |
| bootloader.img (aquaman, 0x148200) | EXACT AQUAMAN image | no AMLSECU/BL31/secureboot inside; not a BL31 source |
| round13 DRAM band (aquaman) | EXACT AQUAMAN BL33 | AMLSECU string there is BL33-side (imgread), not BL31 |
| reports/amlsecu-*.md, .src/.../bl31_apis.* | GENERIC / FAMILY REFERENCE | caller-side header + notes, not BL31 behavior |

No EXACT AQUAMAN BL31 binary, dump, symbol, map, objdump, or reversing log
exists in the repo. Reference BL31 is therefore comparative only.

## C. reference BL31, comparative (no handler isolated)

Flow as far as it is sustained:

```text
SMC #0 -> vector -> SiP/runtime-service dispatch (table-driven, no literal compare found)
 -> opcode 0x820000ff -> handler NOT isolated to a function
 -> validation: NOT FOUND linked to this opcode
 -> crypto/decrypt/memory access: AMLSECU/secureboot code present (~0x1c534..0x1cb14,
    DER-length cmp w0,#0xff loops at 0x20938/0x20a90, RSA-key fail strings),
    but no call edge from a 0x820000ff dispatch was established
 -> return: unknown for this opcode
```

Explicit check list for AML_DATA_PROCESS in reference: address lower/upper
bound, length lower/upper bound, X2+X3 overflow, alignment, memory
attributes, secure/non-secure, AMLSECU magic/version/block-count/enc-flag:
none found linked to the opcode. Neighbor strings that must NOT be cited
as validation of this path: `exceed max DMA SHA2/AES length` (gxb crypto
helpers), `flash size is too large`, `storage size is larger than flash`
(storage init). They prove size checks exist elsewhere, nothing more.

## D. BL33 vs BL31

BL33 passes (site 0x37e24cf0) a user-chosen buffer + fixed 0x1800000 with
no validation. What BL31 does with it is unproven: no
validate_range/decrypt/memcpy_to_secure/process sequence was recovered for
0x820000ff in reference, and the exact aquaman BL31 is absent. Both
directions ("validates correctly" / "does not validate") are unproven.

## E. address semantics

X2 is a DRAM buffer pointer used as physical==virtual (U-Boot identity
map): constants 0x1080000 / sharemem bases / image buffers are passed
raw, and the wrapper treats (buf, buf+len) as a flush range with no
translation. Length (X3) is bytes. This is sustained by the wrapper +
callers; "DMA handle" or "offset" readings have no support.

## F. 0x1800000

0x1800000 = GXB_IMG_SIZE = 24 MiB, arch/arm/include/asm/arch-gxl/bl31_apis.h.
It is a BL33-side constant (do_bootm site + imgread 0x37e3623c; note
different options 7 vs 4), equal by definition to the container max, not a
runtime value imposed by BL31. No evidence BL31 checks or requires it.
GXB_IMG_LOAD_ADDR 0x01080000 is the default buffer, not a proof of anything
beyond being the default.

## G. range check

```text
input range: [X2, X2 + X3)
BL33 check: none (no lower/upper bound, no overflow check, 32-bit truncate only)
BL31 check for 0x820000ff: no address check found (handler not isolated;
  unsigned/signed/overflow/truncation behavior therefore UNKNOWN, not "absent by proof")
```

## H. 16-byte tail, static

Order: copy (0x37e3aea0, transient) -> fill 0x12345678 over L bytes
(0x37e3d3bc..0x37e3d434, advancing per outer iter) -> strided src read
(0x37e3d49c..0x37e3d4b4) -> 4 tail stores (0x37e3d4b8..0x37e3d4dc):
`str w1,[x23,x27]` + 3x `str w0,[x24,#4/#8/#0xc]`, x27=L, x24=dst+L,
L=(clamped>>2)*16*loop, min 0x4000. Copy reuses the same dst each loop
iter while fill advances, so for loop=1 footprints match, for loop>1 the
fill extends past the copy region; tail sits at dst+L either way.

```text
dst            dst+L
 |              |
 +--------------+-----------+
 | 0x12345678 x L | 16B src |
 +--------------+-----------+
```

Tail words are src-derived (w1 = last strided word, w0 = word at final x3;
x3 rooted at src x26), so iff src is host-reachable the 16 bytes are
host-influenced. Classification: pattern + controlled-tail. Arbitrary
payload write stays REFUTED: the N-byte copy is destroyed before return.

## I. second SMC 0xb2000016

tee_log_level 0x37e63534: argc gate, decimal parse of argv[1] into w1,
`mov w0,#0x16; movk w0,#0xb200,lsl#16; smc #0`, compare/print only. No edge
to run_command, secure boot, or image verification. REFUTED AS RELEVANT.

## J. conclusion

### E3

```text
BL33 validation       ABSENT (site 0x37e24cf0; HIGH)
BL31 validation       UNKNOWN (exact aquaman BL31 absent; reference handler not isolated)
range validation      UNKNOWN (no linked check found; not proven absent either)
length validation     UNKNOWN (same)
AMLSECU validation    UNKNOWN (reference has AMLSECU/secureboot code, no linked call edge)
address semantics     buffer pointer phys==virt + length in bytes (HIGH, caller side)
```

### ddr_test_copy

```text
pattern write         CONFIRMED
controlled tail       CONFIRMED (16 B at dst+L src-derived; host-influenced iff src is)
arbitrary payload     REFUTED
```

### Decisao

```text
B: BL31 validation is absent in reference, aquaman still unproven
```

Strictly: the reference yields no linked validation evidence for
0x820000ff (handler not isolated, neighbor checks unlinked), and the exact
aquaman BL31 does not exist in the repo, so no claim about aquaman BL31
behavior is sustained. A is refused (nothing confirms validation), C is
refused (no exact-BL31 evidence by rule), D is too weak (BL33 side, tail
shape, and inventory are confirmed). Nothing was executed; no device state
changed.

## files and tests

```text
reports/round17-bl31/00-e3sites.txt   15 sites, 12-line windows (sustains table A)
reports/round17-bl31/01-e3table.txt   e3table verb
reports/round17-bl31/02-wrapper.txt   wrapper verb
reports/round17-bl31/03-bl31inv.txt   bl31inv verb
reports/round17-bl31/04-bl31ref.txt   bl31ref verb
reports/round17-bl31/05-tail.txt      tail verb
reports/round17-bl31/06-tee.txt       tee verb
tools/bl33_round17.py                 offline verbs (new)
tools/run_tests.py                    TestBl33Round17, 7 tests (new)
```

Run: python3 tools/run_tests.py (72 tests, pass). No device, no network.
