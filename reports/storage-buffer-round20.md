# storage buffer round20: is 0x05000000 a storage/sharemem buffer?

static only. no live reads, no writes, no SMC, no 0x05 in this round.
base artifact: BL33 `reports/round14-bl33-persist/bl33-37e18000.bin`
(sha 664fb34a...); C1 dump `reports/round19-candidates/c1-5000000-64k.bin`
(sha 4cd2c04f...); DTB `artifacts/aquaman.dtb`.
detail: `reports/round20-storage-buffer/01..05`.

## main table

| buffer | source | writer (BL33) | reader (BL33) | SMC relation | exact/current | confidence |
|---|---|---|---|---|---|---|
| C1 0x05000000 (64K read) | DTB secmon window base (alloc-ranges 0x5000000/0x400000); stale [0x37fbde60] content | 6 fns stage requests into [[0x37fbde60]]: 0x37e8bd10/0x37e8bdc8/0x37e8be98/0x37e8bf3c/0x37e8bfe0/0x37e8c084 via memcpy 0x37eaaeec | none (BL31 consumes; BL33 never loads it back) | indirect: request staged -> SMC 0x60/61/62/63/64/65 with no register args | address DTB-exact, slot-link stale | UNKNOWN (staging plausible, unproven) |
| 0x05040000 stale out | 0x82000024 return -> [0x37fbde58] (init 0x37e8bbb8, proven) | BL31 (BL33 never stores) | 5 fns: 0x37e8bdc8 (len+memcpy), 0x37e8be98/0x37e8bf3c/0x37e8bfe0 (word), 0x37e8c084 (0x20 B) | indirect: response read after SMC 0x60/61/63/64/65 | stale | STALE BUT PLAUSIBLE |
| 0x05080000 stale block +0x40000 | 0x82000025/0x27 -> [0x37fbde68]/[0x37fbde48] (proven) | BL31 | 0x37e8bc84 returns base (+fresh 0x27), callers 0x37e8c238/0x37e8c2a8 | getbuffer helper, no direct SMC payload | stale (dup at 0x37f5fd68 is same snapshot, not 2nd source) | STALE BUT PLAUSIBLE |
| 0x050fe000/0x050ff000 stale secmon | 0x82000020/0x21 -> [0x37f71480]/[0x37f71488] (0x37e19d70, proven) | 0x37e19d70 memcpy 0x500 B in (efuse path 0x37e562e8 x4) | 0x37e19d70 memcpy out on reply | SMC 0x30/31/32 + 0x10/0x20/0x11/0x12 via 0x37e19ea8 | stale | STALE BUT PLAUSIBLE |
| control SMCs | - | - | - | 0x82000028 (0x37e8c138, 1 caller) + 0x8200006a (0x37e8c14c) scalar-only, no buffer | code-exact | HIGH (not staging) |

## SMC/return table (joint)

| SMC | meaning (DTB + use) | return reg | stored where | first subsequent use | likely region | confidence |
|---|---|---|---|---|---|---|
| 0x82000023 | storage_in_func | X0 | x21 -> [0x37fbde60] | 6 request builders load [slot] as staging base | stale 0x05000000 == C1 | HIGH (edge), UNKNOWN (address) |
| 0x82000024 | storage_out_func | X0 | x20 -> [0x37fbde58] | 5 response readers | stale 0x05040000 | HIGH (edge), UNKNOWN (address) |
| 0x82000025 | storage_block_func | X0 | x19 -> [0x37fbde68] | 0x37e8bc84 returns it | stale 0x05080000 | HIGH (edge), UNKNOWN (address) |
| 0x82000027 | storage_size_func | X0 | -> [0x37fbde48] (+refresh in getbuffer) | bounds callers, `*caller=size` | stale 0x40000 | HIGH (edge), UNKNOWN (address) |
| 0x82000028 | SET_STORAGE_INFO | X0 (status) | nowhere (compared/returned) | caller 0x37e90614 continues boot | n/a | HIGH (not a buffer) |

names: DTB `/securitykey storage_*_func` + `/secmon in/out_base_func`.
behavior matches the names (in=request, out=response, block=sized region),
so the table above is corroborated, not label-trusting.

## decisions (objective)

```text
C1 = storage/sharemem buffer?       UNKNOWN
0x82000023 -> C1?                   UNKNOWN (edge to global YES, global==C1 stale)
secure_storage -> C1?               UNKNOWN (writers to the slot YES, slot==C1 stale;
                                    live C1 bytes are not a plaintext request)
SMC consumer of C1?                 UNKNOWN (pattern proven: stage->SMC 0x60-65;
                                    address unproven; no SMC takes C1 as immediate)
C1 useful for understanding BL31?   NO as BL31 image (DATA_ONLY rules out
                                    resident code in first 64K); YES as negative
                                    constraint + staging context
```

## verdict

UNKNOWN. neither CONFIRMED storage/sharemem buffer nor REFUTED coincidence.

- for CONFIRMED we would need: current [0x37fbde60] == 0x05000000 (one 8 B
  read) plus a request-shaped or BL31-scratch explanation of the live
  bytes. we have neither: no current global read exists, and the live
  bytes do not parse as a plaintext request (namelen=4 vs `usidon2` len 7,
  absurd datalen, no ASCII past offset 11, entropy 7.9967, zero structure).
- for REFUTED we would need: current [0x37fbde60] != 0x05000000, or a
  second principal showing C1 belongs to someone else. we have neither:
  code has zero 0x05000000 literals, so nothing contradicts the stale
  equality either.
- what stands proven regardless: 0x23/24/25/27 -> globals dataflow, the
  six-writer / five-reader sharemem discipline around those globals, the
  DTB 0x05000000/0x400000 window containing every stale value without
  overlap, and C1 = DATA_ONLY (no BL31 at 0x05000000's first 64K).

## C2/C3 disposition (per brief, no pursuit)

C2 = not useful through current read path (deterministic fault x2, proves
nothing historical). C3 = UNKNOWN (caller graphs exact, addresses
runtime-only). unchanged.

## next (only if a live session is justified later)

seven 8 B `0x02` reads of 0x37f71480/0x37f71488/0x37fbde60/0x37fbde58/
0x37fbde68/0x37fbde48/0x37fbde50. read-only, no SMC, no 0x05. that single
step promotes or kills the whole table. nothing else in this round earns
a live probe: no new BL31 reason was found, and C1 gave no dispatcher,
no handler, no 0x820000ff edge.
