oracle_v2 (device phase) — STOPPED AT FIRST DEVIATION, 1 of 3 reboots (2026-09-29)

table PAD -> (f18_pre, f18_post, f19, survived)

  trial | mode        | PAD   | f18_pre | f18_post | f19 | survived
  ------+-------------+-------+---------+----------+-----+------------
  (i)   | nostamp     |  --   |   20    |    ---   |  0  | NO (REBOOT)
  (ii)  | stamp+fake  | 0x120 |   n/a   |    n/a   | n/a | NOT EXECUTED
  (iii) | sweep 0x10  |0x120+ |   n/a   |    n/a   | n/a | NOT EXECUTED

  log: out/logs/oracle_v2_trial1_nostamp.log

stop rule 1 fired: reboot on any trial = report PAD + f18 history and stop.
The reboot budget was not what stopped us (only 1 of 3 used).

1. stamp() REWRITTEN — real SP displacement, proven in asm
   tools/ghostlock_oracle_v2.c:stamp_at(). Compiles under -O2 -Wall -Wextra
   with no warnings; no -O0 needed on the file because the VLA is already
   runtime-sized. The VLA became `volatile unsigned char vla[pad]` with
   runtime pad. llvm-objdump of out/ghostlock_oracle_v2, stamp_at @0x217ed4:
       217ef0: add  x9, x8, #0xf          ; x8 = pad (from caller, dynamic)
       217ef4: and  x9, x9, #0xfffffffffffffff0
       217ef8: sub  x19, x10, x9
       217efc: mov  sp, x19               ; <-- SP DROPS by pad, at runtime
       217f04: strb w9, [x19, x9]         ; touch every 64B to the end of the VLA
       217f20: sturb w9, [x8, #-0x1]      ; touch of the last byte
       217f24: bl   psel_with             ; pselect with SP = SP_frame - pad
       217f28: mov  sp, x29
   why SP varies now: in the old stamper the VLA had FIXED SIZE (MAX_PAD
   4096) and only the memset changed len — the frame was always identical
   and the pselect entry SP identical for every PAD. Here the VLA sizeof
   only exists at runtime, the compiler cannot constant-fold, so it emits
   a dynamic sub/mov sp in the prologue. Touch every 64B + barriers
   ("r"(vla) : "memory") stop the compiler dropping the object.
   The two pselects are pad and pad-0x78 (deep then shallow, order kept).

2. HW PAN: none. Real device config (via /proc/config.gz):
       # CONFIG_ARM64_SW_TTBR0_PAN is not set
       CONFIG_ARM64_PAN=y
       CONFIG_ARM64_UAO=y
   cpuinfo: 4x CPU implementer 0x41 part 0xd03 (A53), Features with no pan/uas.
   With software PAN off, TTBR0 stays write-enabled during user-space access,
   so dereferencing the fake task in paged user-mem is safe. going with
   inline anyway.

3. WHAT TRIAL (i) PROVED AND WHY IT ABORTED
   [cmp] errno=35 EDEADLK ok, tid_waiter=6477   -> CMP->EDEADLK works with
                                                   the trio, trial gate
                                                   passed
   [pre] tid=6477 f18=20 f19=0                    -> f18 reads 20 (prio 120,
                                                   nice 0). reader/parser
                                                   correct, tid-swap guard
                                                   already validated
   [consumer] NEVER PRINTED. the device vanished from adb between [pre] and
               the consumer. uptime 6084.94 -> 8.51, PANIC_TIMEOUT=1 = auto
               reboot.

   No panic handler, no pstore for shell, no dmesg (klogctl EPERM), no su:
   kernel panic vs. anything else cannot be told apart. boot.reason says
   reboot,userrequested, which on MIUI is the default value and worthless.

   IMPORTANT: this trial is nostamp mode. Not one stamp byte was written
   anywhere. The crash is NOT the stamp and NOT the overlap — it is the trio
   itself, during teardown. The exact path between [pre] and [consumer] is:
   FUPI on f_target (wakes the waiter), PI tree teardown, stamp (a no-op in
   nostamp mode), sleep(60), then the consumer.

   This matches the already-known "leg3 crash" and the note from the previous
   scan (out/logs/scan_pads.log: 0x138 killed between baseline and trial, 1
   in ~30, and 0x180 gave only 1 hit in 3 reps). So: the value oracle stays
   untested, but the device-phase base proved the trio teardown is unstable
   enough to kill the device for 1 reboot. Fixing that before any PAD is
   cheap: a stable trio (longer teardown time, or waking the waiter via
   WAKEUP instead of Unlock PI) can be reached on host/emulator before
   spending reboot budget on the device.

4. what was NOT done (and why)
   - trial (ii) PAD 0x120 with fake: not executed. Stop rule 1 says stop at
     the first deviation, and the deviation was a reboot.
   - sweep 0x120..0x1c0: not executed, same rule.
   - No LP64 blob, no writes outside the stamp pattern, nothing in
     cred/SELinux/funcptr. The fake page (4096, mlocked) was allocated but
     the stamp never ran this boot.

5. suggested next step (not executed)
   a) reach [consumer] without reboot: widen the FUPI->consumer gap, wake the
      waiter by timeout (ts.tv_sec+=5 already there) instead of Unlock PI
      when the trial is "stamp", and only then spend reboot on the device.
   b) only after that: PAD 0x120 with fake, and the mini-sweep only if
      f18_post==20.

artifacts
  tools/ghostlock_oracle_v2.c   (new, uncommitted)
  out/ghostlock_oracle_v2       (NDK r29 aarch64 binary, -O2 -static)
  out/logs/oracle_v2_trial1_nostamp.log
  nothing committed; reboots used = 1 of 3.
