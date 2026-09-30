# round26: BL31 / secmon runtime search (EXECUTED live)

date: 2026-09-30. entry `fastboot oem update 5000` only (3x, sanctioned).
stage 16 (TPL/BL33-u-boot) every session, `identify 00 07 00 10`.
read-only: `READ_MEM 0x02` + `mread 0x34/0x33` only.
zero writes, zero SMC, zero 0x05, zero bootm/flash/erase/env, zero ADB reads.
tooling added: `tools/round26_scan.py` (resumable 64K-chunk mread sweep).
dumps: `reports/round26-bl31-runtime/dumps/chunk_05*.bin` (16 x 64 KiB).

round25 closed keyman / 0x60-65 / key-permit / secure_boot_set / HDCP /
ddr_test_copy. none re-opened here: zero new edges found toward them.

## 1. runtime memory map (locators consolidated)

| source | value | range | meaning | runtime/static | confidence |
|---|---|---|---|---|---|
| DTB `/secmon reserve_mem_size` | `0x300000` | - | secmon reserved size | runtime DTB, header re-verified live | HIGH |
| DTB `linux,secmon alloc-ranges` | base `0x05000000` size `0x400000` | `0x05000000..0x05400000` | CMA pool container | runtime DTB | HIGH |
| DTB `linux,secos reg` + `no-map` + `status=disable` | base `0x05300000` size `0x2000000` | `0x05300000..0x07300000` | BL32 slot, kernel must not map | runtime DTB | HIGH |
| AO `0xC810024C` live | `0x0c008000` | - | packed: hi=`0x0c00` lo=`0x8000` | live MMIO `0x02`, this round | HIGH |
| AO `0xC8100250` live | `0x05300000` | - | bl32 start (rsvmem print order) | live MMIO `0x02` | HIGH |
| AO `0xC8100254` live | `0x05000000` | - | bl31 start (rsvmem print order) | live MMIO `0x02` | HIGH |
| decoded bl31 range | start `0x05000000` size `0x300000` | `0x05000000..0x05300000` | secure monitor reservation | live AO + rsvmem disasm | HIGH |
| decoded bl32 range | start `0x05300000` size `0x2000000` | `0x05300000..0x07300000` | secure OS reservation | live AO + rsvmem disasm | HIGH |
| BL33 `.bss 0x37f71480` live | `0x050fe000` | 1 page-ish | secmon IN (SMC 0x20) | live `0x02` (= round13 stale) | HIGH |
| BL33 `.bss 0x37f71488` live | `0x050ff000` | 1 page-ish | secmon OUT (SMC 0x21) | live `0x02` (= round13 stale) | HIGH |
| BL33 `.bss 0x37fbde60` live | `0x05000000` | - | storage IN (SMC 0x23) | live `0x02` | HIGH |
| BL33 `.bss 0x37fbde58` live | `0x05040000` | - | storage OUT (SMC 0x24) | live `0x02` | HIGH |
| BL33 `.bss 0x37fbde68` live | `0x05080000` | - | storage BLOCK (SMC 0x25) | live `0x02` | HIGH |
| BL33 `.bss 0x37fbde48/50` live | `0x40000` / `1` | `0x05080000..0x050c0000` | block size / init flag | live `0x02` | HIGH |
| SMC `0x82000020/21` | share-mem IN/OUT bases | runtime-only | queried via `0x37e19d70` family | static BL33, mechanism | HIGH |
| SMC `0x82000023/24/25/27` | storage IN/OUT/BLOCK/SIZE | runtime-only | queried via `0x37e8bbb8` init | static BL33, mechanism | HIGH |
| DTB `/secmon in/out_base_func` | `0x82000020/21` | - | kernel<->secmon ABI ids | runtime DTB | HIGH |
| DTB `/securitykey storage_*` | `0x60-65/67/68/6a/6b/6c` + `0x23/24/25/27` | - | key SMC surface | runtime DTB | HIGH |
| DTB `/efuse read/write/max` | `0x30/31/33` | - | efuse ABI | runtime DTB | context |
| DTB `/psci` + `/cpu_info` + `/aml_reboot` | `psci-0.2/smc`, `0x44`, `0x84000009/08` | - | PSCI/reboot ABI | runtime DTB | context |

AO decode (rsvmem `0x37e62eec` print path + `0x37e62f78` setter, capstone):
`[0x24c]=0x0c008000`: `(hi 0x0c00)<<10 = 0x300000` = bl31 size;
`(lo 0x8000)<<10 = 0x2000000` = bl32 size;
`[0x254]=0x05000000` = bl31 start; `[0x250]=0x05300000` = bl32 start.
no entrypoint in regs: start+size only. writer = BL2/secure (before BL33);
reader = BL33 rsvmem -> `run_command fdt set` (secmon reg/size/alloc-ranges,
secmon reserve_mem_size, secos reg/status). NO pointer/entry/vector in handoff.

## 2. DTB secure-memory map (runtime FDT at 0x01000000, primary source)

live header `0x02` @ `0x01000000`: `d00dfeed totalsize 0xe3a8 struct 0x38
strings 0xcaa4 rsvmap 0x28 version 17/16` = `artifacts/aquaman.dtb`
(`sha256 b00adaba...`) byte-exact on header. full node walk offline below.

| node | property | value | possible purpose |
|---|---|---|---|
| `/psci` | compatible/method | `arm,psci-0.2` / `smc` | PSCI via SMC, EL3 entry exists somewhere |
| `/secmon` | compatible | `amlogic, secmon` | secure monitor binding |
| `/secmon` | memory-region | phandle `0xf` -> `linux,secmon` | pool link |
| `/secmon` | in/out_base_func | `0x82000020/21` | share-mem ABI |
| `/secmon` | reserve_mem_size | `0x300000` | == AO bl31 size (NOT the 4M pool) |
| `/securitykey` | storage_query/read/write/tell/verify/status | `0x60/61/62/63/64/65` | key SMC (round25 closed) |
| `/securitykey` | storage_list/remove | `0x67/68` | key SMC, no BL33 setup site |
| `/securitykey` | storage_in/out/block/size | `0x23/24/25/27` | share-storage ABI |
| `/securitykey` | set/get_enctype/version | `0x6a/6b/6c` | key crypto switch |
| `/cpu_info` | cpuinfo_cmd | `0x82000044` | chip-id SMC |
| `/efuse` | read/write/max | `0x82000030/31/33` | efuse SMC |
| `/aml_reboot` | sys_reset/poweroff | `0x84000009/08` | PSCI reboot |
| `/defendkey` | reg / mem_size | `0xc8834500/4` / `0x100000` | key MMIO + carve; storage-adjacent, no boot consumer (round25 sweeps stand) |
| `/reserved-memory/linux,secmon` | size/align/alloc-ranges | `0x400000/0x400000/0x05000000+0x400000` | 4M container (pool, reusable) |
| `/reserved-memory/linux,secos` | reg/no-map/status | `0x05300000+0x2000000` / no-map / disable | 32M BL32 slot, dead code on this build |
| `/reserved-memory/ramoops` | reg | `0x07400000+0x200000` | pstore, unrelated |
| `/firmware/android` | vbmeta/fstab | `vbmeta,boot,system,vendor` | AVB chain, no BL31 data |
| `/partitions/tee` | size | `0x2000000` | eMMC secure-OS partition, NOT BL31 |
| `/__symbols__` | secmon/secos_reserved | paths to both nodes | phandle aliases only |

DTB carries no BL31 code address, entry, magic, or image reference.
only reserved ranges + SMC ids. `/secmon` has NO `reg` (pool-placed).

## 3. secmon mismatch map (RESOLVED)

```text
0x05000000  bl31 start (AO) = storage IN (0x23) = C1 base
  |  DATA, readable, storage working set (this round, 1 MiB)
0x05040000  storage OUT (0x24): live usid-digit echo
0x05080000  storage BLOCK (0x25) size 0x40000: "AMLSECURITY" hdr + ~13 KiB crypto + zeros
0x05090000  192 KiB ZERO gap (3 x 64K, sha-identical)
0x050c0000  DATA resumes (high-entropy crypto pages)
0x050fe000  secmon IN (0x20): high-entropy blob, no struct/code
0x050ff000  secmon OUT (0x21): 6 zero bytes + high-entropy blob
0x05100000  FAULT BOUNDARY (0x02 Errno 5; 0x050fffc0 OK 64 B earlier)
  |  UNREADABLE 0x05100000..0x05400000 (0x05200000 Errno 5 this round,
  |  0x05300000 Errno 5/19 x2 round19)
0x05300000  bl32 start (AO) = secos base = round19 C2 fault addr
0x05400000  pool end (DTB container only, no HW meaning)
```

resolution: the 4M pool is a CONTAINER. HW truth (AO) = bl31 3M
`0x05000000..0x05300000` + bl32 32M from `0x05300000`. DTB
`reserve_mem_size 0x300000` == AO bl31 size exactly. the pool/secos 1M
overlap (`0x053..0x054`) is DTB-declared only; on HW it is bl32 `no-map`.
readable from TPL = first 1M of bl31 (`0x050..0x051`); remaining 2M of the
bl31 range faults. hypothesis "0x64 verifies boot" stays REFUTED (round25);
new fact: storage IN == bl31 base is address reuse of the readable
sub-window, not proof BL31 lives in readable bytes (bytes say otherwise, §6).

## 4. secmon range scan (controlled, chunks, no 4M single request)

`tools/round26_scan.py`, `mread` 64 KiB/chunk, 1 transfer each, per-chunk
sha256 on disk. session A: `0x05000000..0x05100000` OK (16 chunks).
session B: boundary probe `0x05100000` FAIL. session C: `0x05200000` FAIL.
round19: `0x05300000` FAIL x2 (both primitives). no chunk retried after a
fault in the same session (device leaves USB by design of the fault).

| chunk | sha256 | bytes |
|---|---|---|
| 05000000 | 061a21812257c83864ad1df7fb549c907465f664cf508f675ff1998238b1262c | 65536 |
| 05010000 | e43984972797452818e33eea7c733bb091564d6ceb011a8e1179b104e997b0a4 | 65536 |
| 05020000 | d8dd10869f3f0223f0029ac4514c42585684cc53ae70deee846f121c62f95629 | 65536 |
| 05030000 | f8f28bff02ca65d9594b841c29235ac3ae2d698c0f183c58880e29303d2013b1 | 65536 |
| 05040000 | 4f67d9de7e4e6769c5b51db75b31c7dd85b1002e6a6f20354f041631348a0038 | 65536 |
| 05050000 | cffdccc1d2145c1bcf774a0b988a955c76b33275458c52fa2ccd42f1096fd4f8 | 65536 |
| 05060000 | c85bf332fc180ae2e5cadf9b7bbca2682639be851d053655a864bbd8428d8a0a | 65536 |
| 05070000 | effdaaa62d90a64c9f5444fe45aebedfbb955446c6ae97e6600c8f9145cfdaaa | 65536 |
| 05080000 | a4b1f3a85043d1c3a21c854476de50b8b4cf0461fa5b629188bc8d47a9303250 | 65536 |
| 05090000 | de2f256064a0af797747c2b97505dc0b9f3df0de4f489eac731c23ae9ca9cc31 | 65536 |
| 050a0000 | de2f256064a0af797747c2b97505dc0b9f3df0de4f489eac731c23ae9ca9cc31 | 65536 |
| 050b0000 | de2f256064a0af797747c2b97505dc0b9f3df0de4f489eac731c23ae9ca9cc31 | 65536 |
| 050c0000 | a53066a214ec09ba205b7e4f869c40d94eb9ad6ce6176eb02c3f87d8561cd8f5 | 65536 |
| 050d0000 | 157ec55d3c3d1b375995292ce500fcf619c9656e268d970e367b15f831b6758e | 65536 |
| 050e0000 | 04634454be524f8e2012b670a67d6c672949a9b9d9d63994e673e1351e9fa557 | 65536 |
| 050f0000 | 588f6d6512473a6a55856ec4af6323ff93705e35d983b3ea6c187e2e60cd230b | 65536 |

note: C1 sha CHANGED across boots (round19 `4cd2c04f...` vs now
`061a2181...`, same `usidon2` head). volatile storage/crypto buffer, not code
(code would be boot-invariant). the old "code-like gate" would still have
failed here: first 64K are DATA in both boots.

fault log (exact): session A mread `0x05100000` -> Errno 19 + off-bus,
later self-reboot to ADB `2717:4e40`; session B `0x02 0x05100000` -> Errno 5,
then Errno 19 cascade (device gone); session C `0x02 0x05200000` -> Errno 5.
each fault cost one `adb reboot fastboot` + `oem update 5000` cycle.
no auto-retry inside a dead session; resume by base.

## 5. unreadable boundaries

| boundary | probe | result |
|---|---|---|
| `0x050fffc0` | `0x02` 64 B | OK (last readable 64 B) |
| `0x05100000` | `0x02` 64 B / mread 64K | FAIL Errno 5 / Errno 19, x2 sessions |
| `0x05200000` | `0x02` 64 B | FAIL Errno 5 |
| `0x05300000` | `0x02` + mread (round19) | FAIL Errno 5 + Errno 19, x2 sessions |

readable: `0x05000000..0x050fffff` (1 MiB, proven byte-for-byte).
unreadable: `0x05100000..0x05400000` (3 MiB hole, 3 sparse confirmations).
`0x05300000..` additionally explained by secos `no-map`.
cause UNDETERMINED: TrustZone protection vs TPL-MMU-unmapped vs device
hole are indistinguishable with `0x02`/mread alone (both memcpy in gadget,
both abort -> disconnect). NOT auto-interpreted as BL31.

## 6. dump classification by subregion

method: entropy + nonzero + strings + capstone AArch64 density/branches +
eret/`smc#0` word census + EL3 `msr/mrs` + `0x820000xx`/`0xb2000016` words.
density ~1.0 everywhere is a skipdata artifact on random bytes (round19 note
stands); branches ~1000/chunk with zero eret/SMC/EL3 = noise, not structure.

| range | entropy | nonzero | strings | AArch64 | SMC/vector | class |
|---|---|---|---|---|---|---|
| 05000000 IN head | 8.00 | 0.996 | none | noise | 0/0 | DATA |
| 05010000..05030000 | 8.00 | 0.996 | none | noise | 0/0 (+1 random `0x8200f0ee` singleton §8) | DATA |
| 05040000 OUT head | 8.00 | 0.996 | ascii digits `32363931...` (usid echo) | noise | 0/0 | DATA |
| 05050000..05070000 | 8.00 | 0.996 | none | noise | 0/0 (+1 random `0x82001f06`) | DATA |
| 05080000 BLOCK | 2.15 | 0.184 | `AMLSECURITY` x1 @0 | sparse hdr + 12 KiB crypto, rest zero | 0/0 | DATA |
| 05090000..050b0000 | 0.00 | 0.000 | none | none | 0/0 | ZERO (192 KiB) |
| 050c0000..050f0000 | 8.00 | 0.996 | none | noise | 0/0 (+1 random `0x8200da38`) | DATA |
| 050fe000 IN | high | dense | none | noise | 0/0 | DATA (blob, not struct) |
| 050ff000 OUT | high | dense | none | noise | 0/0 | DATA (6 zero bytes + blob) |
| 05100000..05400000 | - | - | - | - | - | UNREADABLE |

CODE: none in 1 MiB. MMIO-LIKE: none (no register patterns).
UNKNOWN: none (every readable chunk classified).

## 7. EL3 evidence: NONE in readable window

`eret` words 0, `smc #0` words 0, EL3 `msr/mrs` 0, `0xb2000016` 0,
`PSCI/optee/opteed/secmon/bl31/tee/AMLSECU` strings 0 (sole exception:
`AMLSECURITY` header in BLOCK, a storage-crypto tag, not a monitor).
no exception-vector table (no `b` at 0x0/0x80 slots; heads are
`usidon2`/random/digits/`AMLSECURITY`/zeros). no `VBAR/SCR/SPSR/ELR/ESR/
SP_EL3/CURRENTEL/DAIF/TTBR/MAIR/TCR` traffic. EL3 vector found = NO.

## 8. SMC dispatcher candidates: NONE in readable window

`0x820000ff` words: 0 in 1 MiB. `0x82000020/21/23/24/25/27` words: 0.
three `0x8200xxxx` singletons (`f0ee/1f06/da38`, one word each in 16K):
expected random hits = 16384 x 65536/2^32 ~= 0.25/chunk, so 3 across 16
chunks is noise, not a table. no compare/branch structure around them
(branches are uniformly distributed skipdata noise). no entry -> no ID
compare -> no handler to follow. SMC dispatcher found = NO.
reference: BL33 holds only `mov+movk` IDs, no `0x8200xxxx` word table
(round25 §8); the readable secmon window mirrors that: no table either.

## 9. eMMC firmware candidates (directed, metadata only, no dump)

BL33 strings: `boot0/boot1` names, `bootloader-boot0/boot1` env,
`amlmmc switch 1 boot%d/user`, full `store/mmc/gpt` command surface.
NO `FIP/BL31/bl30/bl32` image string, NO offset/size/partition/entry for
any secure image. at-rest layout (round18, unchanged): boot0/boot1 hw
partitions <- `bootloader.img` (1.3 MiB, encrypted FIP: BL2+BL30+BL31+BL33);
user GPT `tee` 32 MiB = secure OS (NOT BL31); `dt/logo/misc` no BL31
evidence. at-rest BL31 is ciphertext; no BL33 metadata points inside FIP,
so per brief no `mmc read` was taken (no indiscriminate dump).
eMMC BL31 candidate = boot0/boot1 FIP as a whole, UNKNOWN, unproven.

## 10. final BL31 status

readable bl31 sub-window (`0x05000000..0x050fffff`): PROVEN no BL31
(no code, no vectors, no dispatcher, volatile across boots, storage
layout byte-exact: IN/OUT/BLOCK/IN/OUT all land here).
unreadable remainder (`0x05100000..0x05400000` incl bl31 tail
`0x051..0x053` + pool/secos overlap): UNKNOWN, protection-class fault
with current primitives; the fault boundary is sharp at `0x05100000`.
exact BL31 image: NOT FOUND. runtime code copy: NOT FOUND.
`0xb2000016` (BL33 `tee_log_level` SMC, `0x37e635a0`): 0 hits in dump.

stop assessment: §1-10 exhausted with sanctioned primitives.
readable region closed (proven DATA/ZERO). hole closed as UNREADABLE
(needs a primitive that survives TrustZone/MMU abort: none of
`0x02`/`0x34+0x33`/`0x12`-dead qualify). eMMC closed as metadata-only
(ciphertext, no pointer). investigation stops per "provar que uma regiao
nao contem" (1 MiB) + "faltar primitive" (3 MiB hole + eMMC crypto).

```text
BL31 runtime candidate      = 0x05100000..0x05300000 (bl31 tail, PROTECTED/UNREADABLE, weakest-possible)
secmon code found           = NO
EL3 vector found            = NO
SMC dispatcher found        = NO
0x820000ff found            = NO (0 words in 1 MiB)
exact BL31 identified       = NO
eMMC BL31 candidate         = boot0/boot1 FIP as a whole (encrypted, UNKNOWN)
```

| candidate | verdict |
|---|---|
| readable 1M `0x05000000..0x050fffff` as BL31 code | REFUTED (DATA/ZERO, volatile, storage layout) |
| `0x05080000 AMLSECURITY` as monitor | REFUTED (storage-block crypto header, no code around it) |
| secmon IN/OUT `0x050fe000/0x050ff000` as code | REFUTED (high-entropy blobs, no vectors/dispatch) |
| unreadable `0x05100000..0x05300000` (bl31 tail) | POSSIBLE (only remaining bl31 bytes, fault-class unknown) |
| unreadable `0x05300000..0x05400000` (secos overlap) | UNKNOWN (no-map, round19+C2; bl32 slot, not bl31) |
| eMMC boot0/boot1 FIP | UNKNOWN (ciphertext, no BL33 pointer) |
| exact aquaman BL31 | NOT FOUND |
```

device left in: Android (`2717:4e40`), no writes performed all round.
