# BL33 round 37: `ddr_test_copy` as a control primitive — write, target, consumer, and the 3-character wall

date: 2026-09-30, round 37. **offline only.** no USB, no device, no command issued.
image: `reports/round14-bl33-persist/bl33-37e18000.bin` (sha256 `664fb34a…`).
page table + live DRAM: `reports/round12-reloc/mread_37800000_00800000.bin`.
tool: `tools/bl33_ctrl.py` (`prim`, `pgtable`, `ptrtab`, `dump`, `collateral`,
`reach`) and `tools/bl33_prov.py` (indirect-branch provenance).
tests: `TestBl33Round37` in `tools/run_tests.py` (10 new, 121 total, pass).

**verdict: B — WRITE → CONTROL DATA confirmed, the consumer is identified,
unambiguous and reachable; the one remaining obstacle is that the only
host-to-CLI channel in this firmware clamps the command to 28 characters and
the write needs 31.**

---

## 0. answer block

```text
primitive            4 x uint32 W at A = dst + L, W = *(u32*)(src + 4*ceil(N/8))
                     plus an unavoidable 0x12345678 fill over [A-L, A)
                     L = ((size>>2) & 0x7ffffff) << 4 * loop,  L >= 0x4000
A is host-chosen     yes, 32-bit, no clamp anywhere on the dst path
W is host-chosen     yes, it is a byte of the fastboot download buffer
value width          32 bits only, replicated 4x (one ldr, four str w)
DRAM executable      YES: live page table, 8192 blocks, XN=0 everywhere
                     AP=EL1-RW everywhere, same AttrIdx as .text
caches               SCTLR_EL1 C=1 I=0 -> D-cache on, I-cache off
                     `dcache flush` / `icache flush` exist in the cmd_tbl
payload address      0x10200000 (mov w0,#0x10200000 at 0x37e95498)
consumer             struct cmd_tbl[] at 0x37f60eb0, stride 0x30, 112 entries
                     ->cmd at +0x10, read at 0x37e5f6e8, called at 0x37e5f6fc
                     unconditionally, on every run_command
oem token budget     28 chars (strnlen(cmd,32)+1 = 33 B copied, 4 spent on "oem ")
tokens needed        31 (6-digit src, 8-digit dst, 1-digit size)  -> 3 over
                     35 (8-digit src, 8-digit dst, 4-digit size)  -> 7 over
other CLI sinks      none. cb_boot/cb_continue pass constants; do_run executes
                     each env value whole, no concatenation; the v2 optimus
                     command buffer takes 0xffff bytes but its dispatcher
                     matches a fixed 24-name list and has no run verb
verdict              B
```

---

## 1. Primitive

`do_ddr_test_copy` 0x37e3d1b0, cmd_tbl index 17 (`0x37f611e0`, maxargs 7).
Argument parse (`0x37e3d218..0x37e3d2cc`): `argv[1..5]` through the 32-bit
`strtoul32` 0x37e3cbb0 → `src`, `dst`, `size`, `loop`, `print`. `argc > 3`
required, else fixed defaults. One validity dance on `argv[3]`
(`0x37e3d254..0x37e3d26c`): a non-empty argv[3] with trailing junk forces
`size = 0x2000000`.

end state, phase by phase:

```text
0x37e3d348  bl 0x37e3aea0            copy loop, loop times, TRANSIENT
0x37e3d3c0  lsr w22, w20, #2         N = size >> 2
0x37e3d3d0  ubfiz x0, x22, #4, #0x1e stride = (N & 0x7ffffff) << 4
0x37e3d3d8  fill inner               4 x str 0x12345678, x3 += 0x10, N iters
0x37e3d428  add x19,#1 / cmp w25     outer, x4 += stride, loop times
0x37e3d440  mul x27, x0, x27         L = loop * stride
0x37e3d498  read loop                w19 = N; subs w19,w19,#8; ldr w1,[x3,#4]!
                                    -> ceil(N/8) iterations, x3 ends at
                                       src + 4*ceil(N/8), w1 = that word
0x37e3d4b8  str w1, [x23, x27]       A     = W
0x37e3d4c4  str w0, [x24, #4]        A + 4 = W     x24 = x23 + x27
0x37e3d4d0  str w0, [x24, #8]        A + 8 = W
0x37e3d4d8  str w0, [x24, #0xc]      A +12 = W     w0 = ldr w0,[x3] = w1
```

so, exactly:

```text
[src + 4*ceil(N/8)          .. +16)  ->  dst .. dst + 4*size*loop   (transient)
[dst, A)                                ->  0x12345678 repeated
[A, A+16)                               ->  4 x uint32  *(u32*)(src + 4*ceil(N/8))
```

worked examples (`tools/bl33_ctrl.py prim`):

```text
size=0x1000 loop=1   N=0x400    L=0x4000     A=dst+0x4000   W=src+0x200
size=0x1000 loop=2   N=0x400    L=0x8000     A=dst+0x8000   W=src+0x200
size=0x2000000 loop=1 N=0x800000 L=0x8000000  A=dst+0x8000000 W=src+0x400000
```

properties, each checked against the image and not only the source:

| question | answer | evidence |
|---|---|---|
| argument convention | `ddr_test_copy <src> <dst> <size> [loop] [print]`, hex, 32-bit | 0x37e3d218..0x37e3d2cc, matches `cmd_ddr_test.c:1667` |
| max length accepted | none; `size > 0xfff` kept verbatim | 0x37e3d26c `cmp w20,#0xfff` / 0x37e3d274 `csel` |
| min length | floor: `size <= 0xfff` → `0x2000000` | 0x37e3d270 `mov w0,#0x2000000` |
| granularity | 4 bytes, 16 B per iteration, no alignment requirement | 0x37e3aea0 `ldr/str w` |
| effective length | `(size & ~3) * 4 * loop` | 0x37e3aea0, 4x factor is in the source too (`m_len = size/4`) |
| `size < 0x1000` | replaced by 0x2000000, so L = 0x8000000 minimum for the short spellings | idem |
| `src == dst` | copy is a no-op, fill wins, W = the pattern itself | phases are ordered, no re-read of the original |
| effective direction | src → dst, `p_dest` first then `p_src`; forward only | 0x37e3aeb4..0x37e3aed8 |
| pattern fill after the copy | yes, same footprint, always 0x12345678 | 0x37e3d3f0..0x37e3d41c |
| cache maintenance | **none anywhere in 0x37e3d1b0..0x37e3d52c** | no `dc civac`, no `ic ivau`, no `dsb`, no flush_cache |
| error paths usable for different behaviour | no: `loop=0` underflows the copy loop to 2^64 iterations, `print=0` only gates `printf`, `*argv[3]==0` forces the default size | 0x37e3d364, 0x37e3d34c |
| extra 32-bit range | the tail address is a 64-bit `x23 + x27`, so `A` can exceed 4 GiB; unmapped there → synchronous translation fault | 0x37e3d4b8 |

**the one that matters:** the last store writes a 32-bit value four times. There
is no 64-bit store anywhere in the primitive. A 64-bit slot can still be built,
but only with two calls, and the second call's `W` has to be zero.

---

## 2. Memory map

from the live page table at 0x37ff0000 (8192 descriptors, 2 MiB blocks,
`reports/round12-reloc/…`, and the MMU builder at 0x37e19314..0x37e194fc):

```text
MAIR_EL1  = 0xff440c0400   (0x37e19450..0x37e1945c)
             attr0 = 0x00  Device-nGnRnE     <- the index every block uses
             attr1 = 0x04  Normal NC         (only VA 0..0x1fffff, 0x200000..0x201ffff)
             attr7 = 0xff  Normal WB
SCTLR_EL1 = 0x300004516   (0x37e193f0..0x37e193f8)  M=0 A=1 C=1 I=0
TCR_EL1   = 0x300004516   (0x37e193f0)              TG0=4K, 48-bit VA
```

| region | VA | AP | XN | AttrIdx | class |
|---|---|---|---|---|---|
| SoC low / boot ROM window | `0x00000000..0x001fffff` | EL1 **RO** | 0 | 1 | **R** (executable per XN, but not writable) |
| SoC device window | `0x00200000..0x003fffff` | EL1 **RO** | 0 | 1 | **R** |
| every other 2 MiB block, up to `0x03ffe0000000` | `0x00400000..0x3ffe0000000` | EL1 **RW** | **0** | 0 | **RWX** |
| BL33 image | `0x37e18000..0x37ff0000` | RW | 0 | 0 | **RWX** |
| page table | `0x37ff0000..0x38000000` | RW | 0 | 0 | RWX (self-modifying) |
| stack + `gd_t` | just under `0x37e18000`, growing down | RW | 0 | 0 | RWX |
| malloc arena | `0x33e18000..0x37e18000` (64 MiB, `CONFIG_SYS_MALLOC_LEN`) | RW | 0 | 0 | RWX |
| fastboot download buffer | `0x10200000..0x18200000` (128 MiB cap) | RW | 0 | 0 | **RWX, host bytes** |
| v2 burning transfer buffer | `0x07700000..0x0b700000` (64 MiB) | RW | 0 | 0 | RWX, host bytes |
| runtime DTB | `0x01000000..0x0100e3a8` | RW | 0 | 0 | RWX |

classification, honestly stated: **there is no RX or RO region anywhere above
`0x400000`.** nothing in this firmware marks code read-only or data
non-executable. `.text`, `.rodata`, `.data` and `.bss` all live in
`0x37e18000..0x37ff0000` and all share one page-table class.

`0x12345678` and every other pattern the fill produces is a legal pointer:
block `0x12345678 >> 21` = 145, AP = EL1-RW. `strncasecmp` on it reads the
host's own download buffer, so a destroyed table entry is walked, not crashed.

**self-modifying code is therefore possible in principle** (RWX + I-cache off),
but the primitive cannot express it: a surgical fill is 16 KiB, and the only
surgical target that would be interesting is code. Classified separately, as
asked, and **not** used by the chain below.

---

## 3. Candidate targets

search method: `tools/bl33_prov.py` walks every one of the **463** indirect
branch sites in the image, forward through each function, invalidating x0-x18
at every `bl`, and resolves the provenance of the target register. Results:

```text
463 br/blr sites
  0 fed by a 32-bit load (so a 32-bit code-pointer field does not exist)
 14 read the pointer from a single static image address
 13 read it through a global pointer variable (mem2)
330 read it from a register holding a struct pointer
 89 arithmetic / jump-table offsets
  6 unresolved
```

The 14 static slots (`target | address | writable | consumer | attacker-controlled`):

| target | address | writable | consumer | attacker-controlled | confidence |
|---|---|---|---|---|---|
| fastboot `{cmd,cb}` slot 4/5 | 0x37eb5020 / 0x37eb5028 | yes (RWX) | 0x37e68f78 / 0x37e68fa0 `blr` | yes, but both fields in one 16 B window | HIGH |
| `__reg_failure`-style hook | 0x37ee2710 | yes | 0x37e19848 `blr x0` | yes | HIGH |
| storage cipher ops ×4 | 0x37f5e478/80/b8/c0 | yes | 0x37e73730/50/ec/0x37e73828 | yes | HIGH |
| fastboot/partition state | 0x37f60cc0 | yes | 0x37e9b390 | yes | HIGH |
| usb dev state | 0x37f62638 | yes | 0x37e93b80 | yes | HIGH |
| video out ops ×3 | 0x37f716a0/a8/b8 | yes | 0x37e61514/6d0/758/7a4 | yes | HIGH |
| mmc/block ops ×2 | 0x37fbc940 / 0x37fbc978 | yes | 0x37e8608c / 0x37e86084 | yes | HIGH |
| **cmd_tbl[0].cmd** | **0x37f60ec0** | yes | **0x37e5f6e8 → 0x37e5f6fc `blr x4`** | **yes, 32-bit, unaligned window is harmless** | **HIGH** |
| cmd_tbl[k].cmd, k ≥ 1 | 0x37f60eb0 + k*0x30 + 0x10 | yes | same | yes | HIGH |

**best target: `cmd_tbl[0].cmd` at 0x37f60ec0.** It is the only slot that is
(a) hit on *every* `run_command`, (b) reached with no condition other than
`argc <= maxargs`, and (c) sits in a table whose *other* 111 entries and the
whole `sconv` search stay intact if the 16 KiB fill is placed correctly.

structure, read from the image, not from a header:

```text
0x37f60eb0 : char *name          -> "aml_sysrecovery"
0x37f60eb8 : u32 maxargs         = 3
0x37f60ebc : u32 repeatable      = 0
0x37f60ec0 : int (*cmd)()        <-- THE SLOT
0x37f60ec8 : char *usage
0x37f60ed0 : char *help
0x37f60ed8 : struct cmd_tbl *next
0x37f60ee0 : next entry, "amlmmc"
...                                          stride 0x30, 116 slots, 112 named
0x37f62440 : last entry, "write_version"
0x37f62470 : end  (sconv 0x37e5ee9c: base 0x37f60eb0, end 0x37f62470,
                    count = ((end-base)>>4)*3 = 1044 slots scanned)
```

the 16 KiB collateral for `A = 0x37f60ec0` is `[0x37f5cec0, 0x37f60ec0)`:

```text
8753 / 16384 bytes already zero
154 words that currently hold BL33 code addresses (storage cipher ops)
15 printable runs: "pattern" "Umagic" "random" "bootloader" "reserved"
                  "bootloader-boot0" "bootloader-boot1" "AML_TABLE"
                  "fastboot_context" "uart_ao" ...
```

i.e. it lands entirely on runtime storage/key data, **not** on `.text`,
**not** on `.rodata`, **not** on the fastboot dispatch table (0x37eb5bc8, far
below the window) and **not** on any other `cmd_tbl` entry except entry 0's
`name`/`maxargs`. Cost of a successful write: `mmc`, `store`, `keyman` and
`keyunify` stop working until reboot. Code, printf, the fastboot table and
commands 1..111 keep working.

---

## 4. Best chain

```text
host
  fastboot download:<payload>          -> bytes at 0x10200000 (mov imm, 0x37e95498)
  oem ddr_test_copy 101FFE00 37f5cec0 1000
       argv[1] 0x101FFE00  src
       argv[2] 0x37f5cec0  dst
       argv[3] 0x1000     size
       N = 0x400, L = 0x4000, A = 0x37f60ec0
       fill  0x12345678 over [0x37f5cec0, 0x37f60ec0)   (16 KiB, runtime data)
       tail  16 bytes at 0x37f60ec0 = *(u32*)(0x101FFE00 + 0x200) x 4
             = 0x10200000 x 4   because the payload's word at 0x10200200 is 0x10200000
  oem amlmmc
       sconv 0x37e5ee9c -> find_cmd 0x37e5eddc
         entry 0 name = 0x12345678 -> string in our own buffer, no match, skipped
         entry 1 name = "amlmmc"  -> match
       call_cmd 0x37e5f664
         maxargs = 0x12345678 >= argc                    (0x37e5f6b4/0x37e5f6b8)
         ldr x4, [x19, #0x10]                            (0x37e5f6e8)
         blr x4            -> 0x10200000                 (0x37e5f6fc)
```

**why it works — the exact instruction sequence**

1. `cb_oem` 0x37e95630 hands the token to `run_command` 0x37e5e968 with no lock
   check (round 14 §C.1; the lock helper 0x37e9593c is called by `flash`,
   `erase`, `flashall`, `set_active` and `getvar` only).
2. `ddr_test_copy` writes the pattern and the tail exactly as in §1. No clamp
   on `dst` exists on the parse path (round 16 `03`, re-checked: the only
   `and`/`tst` between 0x37e3d218 and 0x37e3d348 is in `strtoul32`).
3. `sconv` 0x37e5ee9c is a three-instruction thunk that materialises the table
   base 0x37f60eb0, the end 0x37f62470 and the count 1044, then tail-calls
   `find_cmd`.
4. `find_cmd` 0x37e5eddc walks `[base, base + 1044*0x30)` with
   `strncasecmp(name, cmd, len)` and an exact `strlen` tie-break. Entry 0's
   `name` is now 0x12345678, which points into the fastboot download buffer;
   if the payload leaves a NUL there the comparison fails in one cycle and the
   walk continues. No global list, no pointer chasing, no crash.
5. `call_cmd` 0x37e5f664 loads `->cmd` from `+0x10` and calls it with
   `(cmdtp, flag, argc, argv)`. No signature check, no return-value
   validation before the call.

**lifetime**

| step | when |
|---|---|
| table initialised | once, at link/relocation time; nothing rewrites it at runtime |
| table read | on every `run_command`, i.e. on every fastboot request and every `oem` |
| re-armable without reboot | yes, the write is repeatable, the table is not re-derived |
| benign trigger | `oem <any surviving command name>` — e.g. `oem amlmmc`, 8 characters, no args, `argc = 1` |
| no reboot needed between write and trigger | correct, the two are separate fastboot requests |

---

## 5. Why it might fail

| risk | assessment |
|---|---|
| **the 28-character budget** | **this is the blocker, and it is fatal today.** `cb_oem` does `strnlen(cmd, 32)`, `n = that + 1`, `memcpy(buf, cmd, n)` into `x29+0x20`, then one `strsep` and `run_command`. At `strlen(cmd) == 32` the NUL is copied and the token is 28 chars; at 33 the NUL is **not** copied and the token runs into 15 bytes of never-written frame plus the caller's frame. A correct chain needs 35. Reproduce with `python3 tools/bl33_ctrl.py reach` |
| the floor makes short spellings worse | a 1-digit size is replaced by 0x2000000, so `L` becomes 0x8000000 (128 MiB) and `dst` is pinned to `A - 0x8000000`; the only `A` that keeps the fill out of BL33 is one below `0x37e18000`, i.e. the `gd`/stack area, whose slot is a 64-bit `x30` and whose `W` comes from unproven low DRAM |
| two-call composition for a 64-bit slot | does work arithmetically (`A1 = P` then `A2 = P+4`, and `A2`'s fill stops at `P+4`), but needs `W2 == 0` and does not reduce the length |
| d-cache vs the fetch unit | D-cache is on, I-cache is off, so an instruction fetch goes to memory while our bytes may be dirty in L1D. Mitigations exist and are reachable: `dcache` is cmd_tbl index 11, `icache` index 60. Not exercised — the budget stops the chain earlier |
| D-cache coherency might just work | the descriptors are shareable (`SH=1`), so a snoop could serve the fetch from a dirty line. That would be a bonus, never a dependency. Assume the flush is needed |
| collateral | 16 KiB of storage/key runtime data. Code, `.rodata`, printf formats, the fastboot table and 111 of 112 commands survive. `mmc`/`store`/`keyman`/`keyunify` die until reboot |
| `strncasecmp` on a wild `name` | safe: 0x12345678 is mapped RW and inside the host's own buffer |
| `maxargs` gate | helps us: 0x12345678 ≥ any `argc` |
| `call_cmd` also ANDs `->repeatable` into the caller state at 0x37e5f714 | harmless, our code returns before that matters, and 0x12345678 is non-zero so the value is only set, never tested |
| watchdog | the fill is 16 KiB and the copy loop is 16 KiB; both finish in microseconds |
| 4x length factor and the 0x7ffffff `ubfiz` | the factor is modelled; the `ubfiz` only truncates above `size = 0x20000000`, far outside anything used here |
| eMMC | untouched by the whole chain |
| persistence | none: the table is in RAM, reset by relocation on the next boot |

---

## 6. Minimal experiment

**not a payload.** The right first question is binary and the answer is already
predicted, so the experiment is chosen to *falsify the model*, not to prove it.

> "does one `ddr_test_copy` really put 16 bytes of 0x10200000 at exactly
> 0x37f60ec0, and does `oem amlmmc` really branch there?"

and it cannot be asked today, for one reason: **there is no read-back primitive
on the fastboot surface.** `printenv` reads the env blob (0x37f8xxxx, not
reachable with a legal token), and `upload mem` only exists in the v2 optimus
protocol, which needs a reboot to enter. So the smallest honest experiment is
not a single fastboot command; it is one optimus session that owns both halves
of the loop, and optimus has no generic run verb either.

what to run, in order, and what each step decides:

```text
E0  read-only, no reboot:  upload mem 37f60eb0 40   (and 37e5f6e0 20)
    decides:  the live table base and the dispatch code are what the round-14
              image says.  If they are not, the whole target list is wrong.

E1  destructive but bounded, one reboot, no eMMC write, no persistence:
        oem ddr_test_copy 0 37e17f00 1        (26 chars, fits the budget)
    expects:  BL33 dies inside the fill, because L = 0x8000000 covers the
              whole image including do_ddr_test_copy itself.
    decides:  that the size floor really produces a 128 MiB fill at a
              host-chosen dst.  A single, unambiguous, cheap fact.

E2  the discriminating test, and it needs the budget raised first:
        whatever spelling makes the 16 KiB form expressible
        (a shorter command name that reaches the same loop, or a second host
         string sink into run_command), then
        oem ddr_test_copy 101FFE00 37f5cec0 1000
        oem amlmmc
    expects:  one fastboot OKAY per command and no output at all, i.e. the
              gadget ran.  A crash instead means the blr did not take the value.
```

E0 and E1 are reversible by reboot and touch no persistent state. E2 is the
first step that would be a real payload, and it is deliberately gated behind
"the budget problem has an answer".

---

## 7. Next step

**one step: establish whether a ≤10-character host command reaches a
host-controlled (src, dst, size) RAM write.**

That is the exact arithmetic of the blocker: with `len(dst) = 8` and a 1-digit
size, a command name of `n` characters needs `n + 3 + 6 + 8 + 1 ≤ 28`, i.e.
`n ≤ 10`. `ddr_test_copy` is 13. The `cmd_tbl` recovered in §3 has 112 names and
three of them are RAM writers with a host address — `mmc read` (8 with the
subcommand), `ext4load`/`fatload` (8) — but all of them take their **data**
from eMMC, and no local artifact contains the 8 bytes `0x0000000010200000`
anywhere in its first mebibyte. So the missing piece is one command of ≤10
characters that writes host bytes, or one host string sink longer than 28
bytes.

concretely, that means re-auditing these five candidates and nothing else:

```text
mmc      0x37e2d890   mmc read 0x37e2d890 writes (cnt&0x7fffff)*512 eMMC bytes
                       at a host dst and calls flush_cache — a cleaner primitive
                       than ddr_test_copy (no pattern, no 16 KiB floor) with the
                       same 28-char reach, and it composes with it
ext4load / fatload            eMMC file -> host-chosen RAM address
bmp     0x37e277f0            sub-dispatch, 3 subcommands, host address
ddrft / ddrtest / ddrtest_cmd shorter ddr spellings with host start_add
gpio    0x37e2a204            MMIO only, listed for completeness, expected dead
```

and this one question about them: **is there a 14-character-or-shorter command
whose handler performs a `ldr w`/store pair where both the stored word and the
stored address come from the command line, or from the fastboot download
buffer?**

---

## 8. What this round does not establish

- no device command was issued, no RAM was written, no payload exists
- the 28-character budget is derived from `cb_oem`'s copy length and the
  `strsep`, not from an observed truncation on hardware
- the content of the low DRAM at `0x400000..0x400fff` and `0x400000..0x40ffff`
  is unproven; the two dumps in the repo start at `0x01000000` and `0x37800000`
- the exact runtime value of the `gd`/stack pointer is unproven; `board_init_f`
  only shows `addr_sp = relocaddr - sizeof(gd_t)`, and the `sizeof` is not
  recoverable from the binary
- self-modifying `.text` was analysed and **not** used: it needs a surgical fill
  under `.text`, which the budget makes unreachable, and a `flush_cache` +
  `invalidate_icache_all` story that the chain never needed
- signature bypass, key material and anything behind `smc #0` are untouched
  (round 14/15 verdicts stand)
