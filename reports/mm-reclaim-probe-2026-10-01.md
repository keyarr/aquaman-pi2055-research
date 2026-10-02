# mm reclaim probe: order-2 hardware round (2026-10-01)

> DIRECTION (2026-10-02, see `reports/CURRENT_STATE.md`): principal is
> post-free stack reuse + disclosure; H16 live retarget is secondary;
> reclaim without verifier, audited live H16 writer search, fake object,
> arbitrary R/W, cred/root are closed. Post-free reuse is not demonstrated
> on Aquaman. Live-retarget was audited and not demonstrated.

Question: on this device, on this boot, does the current mechanism produce
`hits > 0` of order-2 reclaim?

Answer: FAIL. Order-2 reclaim not reproduced in hardware. Pressure and
plumbing work perfectly; a valid reclaim signal does not exist
unpriv on this stock, so `hits` is 0 by construction.

Raw logs: `out/logs/mm_reclaim_control_boot3ec336a5.log`,
`out/logs/mm_reclaim_A_boot3ec336a5.log`,
`out/logs/mm_reclaim_B_boot3ec336a5.log` (stdout integral, 1 exec/modo).

## 1. Static expectation

Prior repo (`hazel-mm-struct-aquaman.md` sec 3/11,
`root-path-reclaim-consumer-mali.md` sec 2/5):

- hold via `open(/proc/pid/mem)` in forked child, `mm_count` via
  `proc_mem_open` (`base.c:801`); counts 608/171/18/1/19 = 817 holds;
- free in Hazel order returns order-2 slabs (19 x 0x340) to the buddy,
  with 2 s settle for `cpu_partial` (`CONFIG_SLUB_CPU_PARTIAL=y`);
- spray: 512 socketpairs `AF_UNIX SOCK_STREAM`, `SO_SNDBUF=1MB`,
  1 send of 16384 B each; kernel tries `alloc_pages(order 2)` first
  (`skbuff.c:4693-4699`, NOWARN/NORETRY) and falls back to scattered
  pages on silent failure;
- sentinel `0x5A5A5A5A@0x3FFC` via `MSG_PEEK` was expected PASS in
  both modes, and was already REFUTED as reclaim proof before the run
  (plumbing proof only);
- `/proc/slabinfo` missing (`SLABINFO=n`), `/proc/buddyinfo` and
  `/sys/kernel/slab/mm_struct/*` root-only: BLOCKED diagnostic
  expected for shell.

## 2. Device setup

- Xiaomi Mi TV Stick 1080p (aquaman), S805Y, Android 9 PI.2055,
  kernel 4.9.113 `#1 SMP PREEMPT 2022-09-06`, armv8l, SELinux Enforcing,
  ctx `u:r:shell:s0`.
- boot/session: `3ec336a5-439f-497f-b9f7-08fd7441b174`, uptime 23764 s
  no baseline, same boot in all 3 execs, no power-cycle.
- memory at baseline: MemTotal 1004412 kB, MemFree ~129 MB,
  MemAvailable ~301 MB.
- ADB via USB, device `26919800005844922`, ulimit -n 32768.
- Harness: `tools/mm_reclaim_probe.c` (adjusted this round),
  build `aarch64-linux-android28-clang -O2 -Wall -static`, no warnings,
  push to `/data/local/tmp/mm_reclaim_probe`. One-shot per exec,
  no UAF/futex/cred/fptr/SELinux-bypass/persistence.
- Commands:
  `adb shell /data/local/tmp/mm_reclaim_probe control` (baseline),
  `... A` (modo A), `... B` (modo B). Cada um com `timeout` no host
  (240/590/240 s, none hit).

## 3. Mode A result (main: 817 holds + 512 16K pairs)

`P7 SUMMARY mode=A-full pid=14638 attempts=1 holds_req=817 holds_ok=817
freed=817 pairs_req=512 pairs_ok=512 sends_ok=512 pressure_obj=16384B
plumbing_hits=512 reclaim_hits=0 emfile=0 hold_blocked=0 hold_other=0
t_ms=3306`. Shape in 1203 ms, spray in 45 ms. Verdict: FAIL
(`hits == 0`). Full pressure, zero blocks, zero EMFILE, no
reboot/hang (full log in cited file).

## 4. Mode B result (reduced fallback: 20 holds + 16 16K pairs)

`P7 SUMMARY mode=B-fallback pid=15462 attempts=1 holds_req=20 holds_ok=20
freed=20 pairs_req=16 pairs_ok=16 sends_ok=16 pressure_obj=16384B
plumbing_hits=16 reclaim_hits=0 emfile=0 hold_blocked=0 hold_other=0
t_ms=2043`. Verdict: FAIL (`hits == 0`). Control reference
(plumbing baseline, 1 hold + 512 pairs): `plumbing_hits=512/512`,
`reclaim_hits=0`, FAIL. All three modes agree.

## 5. Signal classification

| signal | class | reason |
|---|---|---|
| `MSG_PEEK` returns sentinel (512/512 A, 16/16 B, 512/512 control) | FALSE_POSITIVE as reclaim / AUXILIARY as plumbing | unshaped control passes the same; own bytes echo via skb even with scattered pages (`skbuff.c:4708`); proves send/peek, zero slab-reuse info |
| hold 817/817 + free 817/817 | AUXILIARY | allocator pressure works, but says nothing about contiguous order-2 page nor target reuse |
| MemFree/MemAvailable deltas (~10 MB in spray A) | AUXILIARY | allocator activity, not target-object reuse |
| `/proc/buddyinfo` errno=13 (6/6 attempts) | BLOCKED | denied for shell; order-2 delta not observable |
| `/proc/slabinfo` missing | BLOCKED | `SLABINFO=n`, expected |
| `/sys/kernel/slab/mm_struct/slab_size` denied | BLOCKED | root-only 0400, expected |
| `reclaim_hits=0` (P6, valid criterion) | verdict (FAIL) | only number that counts for the hypothesis |
| no signal | PROOF | nothing observed qualifies as proof |

## 6. Failure reason

Observed bottleneck: valid reclaim signal unavailable unpriv.
Pressure (817 holds, 512 16K sends), SELinux hold (0 blocks) and
EMFILE (0) are all green; what is missing is not pressure, it is
observability. The kernel fallback (order-2 -> scattered pages)
is silent, so `sends_ok=512` does not distinguish order-2 capture
from scattering. Without UAF read or privileged counters, the
per-attempt reclaim rate stays NOT PROVEN even with 100% plumbing.

## 7. Next bottleneck

Single one: per-attempt order-2 capture observability. Closing requires
the `FUTEX_LOCK_PI(f_chain)` consumer timed against
shaped+sprayed slabs (read via UAF, VAR B terminator only, no
cred/fptr), or post-foothold slab counters. Without that, repeating
more spray on the same boot decides nothing.
