oracle_v2 — HOLD round + variation (2 of 2 boots, BUDGET BLOWN again)

logs: out/logs/oracle_v2_holdA_nostamp.log       (BOOT A: nostamp + hold)
      out/logs/oracle_v2_holdB_stamp0120.log     (BOOT B: stamp 0x120 + hold)
      out/logs/*_runner.txt                       (run_leg.sh output + uptime)

1. RESULT

  trial | mode          | settle | last line    | f18_post | f19 | [hold] alive | reboot
  ------+---------------+--------+--------------+----------+-----+--------------+-------
  holdA | nostamp       | 2.5s   | [hb] +2000ms |  n/a     | n/a |     0        | YES
  holdB | stamp 0x120   | 250ms  | [hb] +0ms    |  n/a     | n/a |     0        | YES

  uptime: holdA 626.64 -> device off adb (reboot). holdB 74.09 -> 29.05.
  6 of 6 panics in the project. EDEADLK came back right both times (tid 5111
  and 4963). ZERO f18_post read to this day, ZERO f19, ZERO [hold] alive.
  nothing changed on the oracle.

2. WHAT WAS REFUTED THIS ROUND

  a) exit_pi_state at process exit: REFUTED. The log kills that hypothesis
     from gate3. In both boots the process died with all threads alive and
     the main inside usleep(settle), with no exit() ever called, no
     consumer, no hold. Death comes BEFORE process teardown, so process
     teardown cannot be it. "[hold] entered" never appeared because there
     was never time to get there — and irrelevant, the device was already
     dead.

  b) the actor is not the settle: the actor's upper latency bound fell from
     ~2.5s to <=250ms.
       holdA: 2.5s settle, died between +2000 and +2500ms of the settle.
       holdB: 250ms settle, died BEFORE the first hb after +0ms.
     any settle >= 250ms is already too late. "shorten the settle" was the
     right variation, 250ms still not enough. Cannot shrink further without
     changing the experiment order.

  c) the actor is not the stamp: holdA was nostamp, no pselect at all, and
     the device died the same way. BUT it cannot be claimed the stamp does
     not speed the actor up: in holdB (stamped) death came too early to
     measure latency. Two readings open, neither proven:
       - the same actor, with variable latency
       - the stamp wakes/speeds the actor
     2 data points do not separate that.

3. WHAT I STOPPED TRYING (and why)

  pstore: /sys/fs/pstore Permission denied for shell. dmesg blocked.
  no free backtrace. No way to catch the culprit without spending boot.

  A trial with ~0 settle (consumer glued to the stamp) is the only
  patch-shaped path. More honest alternative: invert the order — read
  f18_post BEFORE teardown and use teardown only as the trigger. Does not
  fit a small patch and touches the gate geometry.

4. VERDICT (only valid for the attempted path)

  Via the attempted path (waiter/owner trio + CMP->EDEADLK + setschedparam
  consumer + settle, with and without zombie/hold) it did not work: NOGO
  for a stamped trial with collection-before-death UNDER THESE conditions.
  The value oracle stays UNTESTED: no f18_post in 6 boots. Other paths
  (another stamper, another trio geometry, long FWRQ timeout, UART or a
  backtrace to identify the actor) were not tried, and nothing here says
  they are impossible.

5. CODE CHANGES (minimal diff, geometry intact)

  - tools/ghostlock_oracle_v2.c: `hold` flag (extra argv, "nostamp hold" or
    "stamp <pad> hold"), infinite loop after [result], hb_stop only set
    outside hold. Comment explains why: hold exists only so the process
    never exits.
  - settle: 2500000us -> 250000us. only number touched. PAD 0x120, GL_*,
    nfds 320, stamp_at/VLA, setbuf, EDEADLK check, 1 trial/execution: intact.

6. STATE

  - 2 of 2 boots spent. budget blown again. needs approval.
  - nothing committed. git diff --check clean.
  - /data/local/tmp clean (only factory aapt-arm-pie + dalvik-cache).
  - no leftover process on the device.
