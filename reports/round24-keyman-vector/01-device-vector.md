# round24 01: device vector (static, code-exact)

image `reports/round14-bl33-persist/bl33-37e18000.bin`, base `0x37e18000`.
method: capstone disasm + struct dump. no device, no SMC, no commands run.

## 1.1 the two static ops vectors

`device_lookup 0x37e73380` returns one of two pointers, never a per-key struct:

```text
w0 = 0x37e75590(name)          ; device class from DDR entry +0x54
w0 == 1 -> 0x37f5e4b8          ; efuse ops
w0 == 2,3 -> 0x37f5e478        ; secure/normal ops
else -> NULL                   ; 0, 4, >3
```

file dump (8 qwords each, all inside image):

```text
0x37f5e478 (secure/normal):
+0x00 0x37e75e44  init -> 0x37e8c1dc (secure storage init)
+0x08 0x37e75e74  stub -> mov w0,#0; ret
+0x10 0x37e75e7c  keymanage_secukey_write (-> amlkey_write, SMC 0x62)
+0x18 0x37e76078  b -> 0x37e8c374 (-> 0x37e8bfe0, SMC TELL 0x63)
+0x20 0x37e7607c  b -> 0x37e8c2ec (-> 0x37e8be98, SMC QUERY 0x60)
+0x28 0x37e76080  exist-bool (bl 0x37e8c35c, cset eq)
+0x30 0x37e7609c  keymanage_secukey_read (-> amlkey_read, SMC 0x61)
+0x38 0x00000001  flag: skip exist gate on write

0x37f5e4b8 (efuse):
+0x00 0x37e76154  keymanage_efuse_init
+0x08 0x37e761e8  stub (no strings, returns small int)
+0x10 0x37e761f0  efuse write (secure_boot_set special-cased, else 0x37e72ca4)
+0x18 0x37e76268  keymanage_efuse_size (-> 0x37e72c40 DTS cfg size)
+0x20 0x37e7637c  keymanage_efuse_exist
+0x28 0x37e762cc  exist-negation (strcmp secure_boot_set, cset ne)
+0x30 0x37e762f4  keymanage_efuse_read (-> 0x37e72d98 efuse backend)
+0x38 0x00000000  flag: run exist gate on write
```

SMC family mapping for the secure legs comes from the round14 census:
QUERY `0x82000060` @`0x37e8bf1c` in `0x37e8be98`,
READ `0x82000061` @`0x37e8be5c` in `0x37e8bdc8`,
WRITE `0x82000062` @`0x37e8bdb0` in `0x37e8bd10`,
TELL `0x82000063` @`0x37e8c064` in `0x37e8bfe0`,
VERIFY `0x82000064` @`0x37e8c108` in `0x37e8c084`.
efuse backend goes through `0x37e727a4` (DTS efuse node lookup) +
`0x37e725b8`/`0x37e726b0`; the single-exact SMC id on that leg is
EFUSE_USER_MAX `0x82000033` @`0x37e19e88` via `0x37e72770`, the
`0x82000030/0x31` read/write pair is FAMILY REFERENCE (wrapper-level,
not re-proven here).

## 1.2 exact dispatch: which register, which offset

`device_write 0x37e73880` (x0=name, x1=data, w2=len):

```
x20 = bl 0x37e73380(name)        ; ops vector or NULL
cbz x20 -> 0x107 fail
ldr w0,[x0,#0x38]                ; flag, x0==x20 here
cbnz -> [x20,#0x10] blr          ; secure: straight to write
else:
  x3=[x20,#0x20]; blr x3         ; efuse: exist gate first
  cbz w0 ok else 0x10f fail
  x3=[x20,#0x10]; blr x3         ; then write
```

`device_read 0x37e7394c` (x0=name, x1=caller_buf, w2=expected_len):

```
x20 = bl 0x37e73380(name)
cbz -> 0x128 fail
x1=[x0,#0x20]; blr (name)        ; query/exist, fail -> 0x12e
x1=[x20,#0x28]; blr (name)       ; exist-bool, fail -> 0x134
x1=[x20,#0x18]; blr (name)       ; tell/size -> x0=len
cmp x0,w21,uxtw; b.le ok         ; returned > expected and expected!=0
  -> 0x13a fail
x3=[x20,#0x30]; blr (name, buf, len) ; real read
```

`len_lookup 0x37e73aa0` (x0=name, x1=len_ptr): same lookup, then
`[+0x28]` blr gate (`0x150` on fail), then `[+0x18]` blr, `str x0,[x21]`.

entry count: 2 vectors, 8 slots each, 6 slots used per path above
(+0x00 init and +0x08 stub excluded). CONFIRMED.

## 1.3 who populates the vector (writers)

the vectors themselves are LINK-TIME constants (in-image pointers,
dumped above). what is runtime-populated is the PER-KEY array they
index into:

* array base: `[0x37f89fe0]` = `0x33e35fc0` in this dump (DDR, outside image)
* stride: `0x68` (104: `mul w2,w0,0x68` @`0x37e759e8`, `madd ... #0x68` @`0x37e75abc`)
* count: `[0x37f5e5e8]` low word = `0x13` (19, matches DTS unifykey-num)
* entry lookup `0x37e754b4`: `ldr x19,[0x37f89fe0]`, loop `w20 < w21`,
  `strcmp(entry+0x00, name)`, step `0x68`. hit returns entry, miss NULL.

writer of the array: `0x37e757ec` (DTS parser, called once from
`key_unify_init 0x37e73694` @`0x37e736f8`):

```
getenv("dtb_mem_addr") -> strtoul(base 0)   ; fdt address
bl 0x37e757ec(fdt)                          ; parse /unifykey
  unifykey-num (cap 32, error 0x143 above)
  malloc(num * 0x68), memset, str [0x37f89fe0]
  per i: sprintf("/unifykey/key_%d")
    fdt_getprop key-name   -> entry+0x00 (<=0x2f, NUL)
    fdt_getprop key-device -> entry+0x54 class (1 efuse / 2 secure / 3 normal)
    fdt_getprop key-type   -> entry+0x30 (default "raw")
    fdt_getprop key-permit -> entry+0x5c bits (1 read / 2 write / 4 del)
    fdt_getprop key-encrypt-> entry+0x40 (<=0xf)
    str index -> entry+0x50
str 1 -> [0x37f5e5e8+8]                     ; init-done flag
```

then `key_unify_init` runs per-type init ops:
`[0x37f5e478]()` (secure init, w1=8) and `[0x37f5e4b8]()` (efuse init, w1=8).
first-use path: `do_keyunify 0x37e73c84` calls `key_unify_init` on "uninit".

so: NOBODY writes the function pointers at runtime. the vectors are
static; the DTS populates the KEY ARRAY that selects between them.
"who populates the vector" = the linker for the vectors,
`0x37e757ec` for the key array. CONFIRMED.

## 1.4 structure (probable, labeled as such)

```text
per-key entry (DDR, 0x68 bytes):
+0x00 char name[0x30]      ; key-name, strcmp target          CONFIRMED
+0x30 char ktype[0x10]     ; key-type, default "raw"          CONFIRMED
+0x40 char encrypt[0x10]   ; key-encrypt                      CONFIRMED
+0x50 u32 index            ; key_%d ordinal                   CONFIRMED
+0x54 u32 dev_class        ; 1 efuse / 2 secure / 3 normal    CONFIRMED
+0x58 u32 ???              ; read by 0x37e75524, cmp ==3; writer not
                           ; found in 0x37e757ec              UNKNOWN
+0x5c u32 permit_bits      ; 1/2/4 for read/write/del         CONFIRMED (parsed;
                           ; enforcement point NOT FOUND, see 05)
+0x60..0x67 padding?                                          UNKNOWN

ops vector (static, 0x40 bytes):
+0x00 init / +0x08 stub / +0x10 write / +0x18 tell-or-size /
+0x20 query-or-exist / +0x28 exist-bool / +0x30 read / +0x38 flag
```

+0x58 and the tail padding are the only UNKNOWNs in this layout.
permit enforcement is UNKNOWN (parsed, no BL33 consumer found).
