# share-storage round21: BL33 protocol over IN/OUT/BLOCK (static, runtime-anchored)

base: BL33 `reports/round14-bl33-persist/bl33-37e18000.bin` (base 0x37e18000).
runtime anchor (round20 live, seven 8 B `0x02` reads, zero writes/SMC):
`[0x37fbde60]=0x05000000 IN`, `[0x37fbde58]=0x05040000 OUT`,
`[0x37fbde68]=0x05080000 BLOCK`, `[0x37fbde48]=0x40000`,
`[0x37fbde50]=1`. detail: `reports/round21-share-storage/01..06`.
no live reads in this round. no writes, no SMC, no `0x05`, no ADB.

DTB: `linux,secmon alloc-ranges <0x5000000 0x400000>` window holds all three
(IN/OUT/BLOCK non-overlapping, 0x40000-aligned); `/securitykey` gives
`storage_{in,out,block,size}_func = 0x23/24/25/27`,
`storage_{query,read,write,tell,verify,status} = 0x60/61/62/63/64/65`,
`set_enctype/get_enctype/version = 0x6a/6b/6c`; `/secmon` gives
`in/out_base_func = 0x20/21`. code behavior matches every name it uses.

## protocol (short)

init `0x37e8bbb8` (lazy, flag `[0x37fbde50]`-gated): 0x23/24/25/27 returns ->
globals. then per op: stage request into `[[0x37fbde60]]` via strlen+memcpy
(header variant per op), bare `smc #0` with 0x60-65 and no register args,
parse `[[0x37fbde58]]` (len+blob / word / 0x20 B). BLOCK via getbuffer
`0x37e8bc84` only in the init/backend path (base+fresh size to
`store_key_read/write`, one 0x100 memset). control SMCs 0x28 (one caller in
boot `0x37e904ac`, X1=1) and 0x69/0x6a (scalar, in `0x37e8c1dc`) never touch
buffers. 0x26 never issued.

## final answers

```text
C1 writers                  = 6 fns: 0x37e8bd10 (write/0x62) + 0x37e8bdc8 (read/0x61)
                              + 0x37e8be98 (query/0x60) + 0x37e8bf3c (status/0x65)
                              + 0x37e8bfe0 (tell/0x63) + 0x37e8c084 (verify/0x64);
                              all via strlen + memcpy into [[0x37fbde60]]  [CONFIRMED]
C1 controlled by host       = NO direct evidence (all six take BL33 caller
                              name/data pointers from shell/DTB/env layer;
                              write path has no fastboot/usb caller; host can
                              trigger reads but stages only key names)      [UNPROVEN as host-input]
C2 readers                  = 5 fns: 0x37e8bdc8 (len+blob copy-out) + 0x37e8be98/
                              0x37e8bf3c/0x37e8bfe0 (single word) + 0x37e8c084
                              (0x20-B copy) from [[0x37fbde58]]             [CONFIRMED]
C2 plaintext/status/etc.    = status word (0x60/65/63) CONFIRMED; len+key-blob
                              (0x61) shape CONFIRMED content UNKNOWN; 0x20-B
                              verify blob shape CONFIRMED meaning UNKNOWN;
                              plaintext-vs-encrypted UNKNOWN (0x6a exists but
                              never branches around OUT)                    [MIXED, see 03]
BLOCK role                  = opaque base+size handle for store backend
                              (getbuffer -> store_key_read/write + one 0x100
                              memset); not input/output, scratch handle;
                              0x40000 = BL31-reported capacity (refreshed per
                              getbuffer), max BL33-demonstrated use 0x100;
                              no index/sector/block-split in BL33           [CONFIRMED shape]
0x23..0x28 protocol         = 0x23/24/25/27 init -> flag gate -> stage IN ->
                              SMC 60-65 -> parse OUT; 0x28 scalar boot control
                              (X1=1, selector [0x37f60878]=2); 0x26 unused   [CONFIRMED]
secure_storage relation     = literal names absent (stripped); functional map:
                              init=0x37e8bbb8, getbuffer=0x37e8bc84,
                              read/write/...=0x37e8bdc8/0x37e8bd10/...,
                              set_info=0x37e8c138, set_enctype=0x37e8c14c;
                              IN edge (6 fns) + OUT edge (5 fns) + BLOCK edge
                              (getbuffer) via SMC-return globals CONFIRMED;
                              0x28/0x6a buffer use REFUTED                  [CONFIRMED functional]
AML_DATA_PROCESS relation   = NO (0x37e19ea8: own buf/len/opt registers +
                              post-flush, own callers; zero shared-buffer or
                              call edge with storage path)                  [REFUTED as link]
```

## risks / non-claims

- content of C1 at any moment (request remnant vs BL31 scratch) is UNKNOWN by
  design: static analysis cannot timestamp the buffer. round20 entropy (7.9967)
  only rules out code/plaintext-structure, not ciphertext vs scratch.
- OUT encryption state UNKNOWN; do not cite this round for key-extraction
  feasibility.
- C2 physical `0x05300000` stays out of scope (round19 fault, per brief).
- E3 / `0x820000ff` stays separate; no storage finding validates it.

## tests / checks

- `git diff --check`: clean (docs only, no code/tooling added, so no new tests).
- cross-checks: smc census (`bl33_audit.py smc`) lists exactly the 15 sites
  cited; caller census matches every edge above; word/movz/adrp scans confirm
  zero literal 0x05 bases in code.
