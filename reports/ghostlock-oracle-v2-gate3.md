oracle_v2 device phase — GATE v3, zombie + heartbeat (3 of 3 reboots, BUDGET BLOWN)

table trial -> (final heartbeat, f18_post, f19, survived, uptime)

  trial | mode    | PAD  | last line        | f18_post | f19 | survived   | uptime
  ------+---------+------+----------------+---------+-----+------------+------------------
  gate1 | nostamp |  --  | [pre] f18=20   |   n/a   | n/a | NO(REBOOT) | 6084.94 -> 8.51
  gate2 | nostamp |  --  | [teardown]...  |   n/a   | n/a | NO(REBOOT) |  819.10 -> 25.14
  gate3 | nostamp |  --  | [hb] +2000ms   |   n/a   | n/a | NO(REBOOT) |  656.68 -> 25.32
  (ii)  | stamp   |0x120 |  not executed  |   n/a   | n/a | NOT RUN    | --

gate1 = v1 (old protocol, teardown with external FUPI + pre-read)
gate2 = v2 (a)-(f), WITH pthread_join(owner)
gate3 = v3 (a)-(f), WITHOUT pthread_join(owner) + heartbeat + markers  [THIS ONE]

logs: out/logs/oracle_v2_trial1_nostamp.log (gate1)
      out/logs/oracle_v2_gate_nostamp.log     (gate2)
      out/logs/oracle_v2_trial1_gate.log      (gate3, this one)

RED GATE 3x. Trial 2 (stamped 0x120) NOT executed (rule: no green gate, no
trial 2). Reboots: 3 of 3. Budget blown.

1. WHAT THE HEARTBEAT PROVED (the new datum this round)

   gate3 log, intact:
     [cmp] errno=35 EDEADLK ok, tid_waiter=5037
     [teardown] waiter woke and released the chain
     [teardown] owner became zombie (not joined), task_struct alive
     [teardown] stamp done, settle 2.5s with heartbeat
     [hb] +0ms
     [hb] +500ms
     [hb] +1000ms
     [hb] +1500ms
     [hb] +2000ms
     <reboot>

   NEVER printed [teardown] settle finished. NEVER printed [consumer-before].
   NEVER printed [consumer-after].

   death came between +2000ms and +2500ms of the settle. the heartbeat did
   its job: it localized the death in the middle of the settle, not around
   the consumer.

   this REFUTES the gate2 hypothesis. the gate2 hypothesis was "joining the
   owner frees the task_struct and the consumer walk (__sched_setscheduler ->
   adjust_pi) steps on freed heap". gate3 dropped the join (owner became a
   zombie, task_struct provably alive, printed by the binary itself) and the
   device died ANYWAY — 2 to 2.5s later, with the consumer never even called.
   the consumer walk was not the cause. it was the most obvious vector, not
   the only one.

2. WHY THIS CHANGES THE DIAGNOSIS

   in nostamp mode there IS NO stamp, there IS NO pselect, and the consumer
   NEVER RAN (it died before [consumer-before]). still the device dies ~2s
   after teardown ends. so the crash is ASYNC and goes through neither the
   consumer nor the stamp: it is the kernel, alone, walking some path that
   references the waiter stale node in the f_target wait tree (the dead FWRQ
   frame, which the v3 teardown deliberately leaves untouched).

   what runs alone in that 2.5s window and does not depend on us:
     - background RT rebalancing (rt_mutex_rebalance_locked)
     - the zombie owner process exit (exit_pi_state / cleanup)
     - the still-armed FWRQ timeout timer

   the owner became a zombie, but zombie on Android/glibc: the main thread
   calls exit(0) at the end and the whole process dies with the owner. the
   owner exit_pi_state runs at that exit, and it touches the f_chain/f_target
   PI tree. and the waiter stale node sits right there. this is now the
   strongest hypothesis: the crash comes from the PROCESS EXIT (which unlocks
   the zombie owner and walks the stale PI tree), not from the consumer.

   in other words: via the attempted path so far, the gate did not go green —
   the process's final teardown looked like part of the problem, not a
   cleanup. (LATER NOTE: the exit hypothesis was REFUTED by the HOLD round,
   where the process died alive with no exit() ever called; see
   ghostlock-oracle-v2-hold.md. What stands is: this path did not work;
   other paths are untested.)

3. CHANGES THIS ROUND (v2 -> v3), with motive

   (a) pthread_join(owner) REMOVED. the owner stays a deliberate zombie: its
       rt_mutex_waiter (the owner node in the f_chain wait tree) stays valid.
       motive: gate2 proved the join frees that memory; but gate3 proved the
       crash continues even with the node alive (only the window moved).
       the change was needed to isolate, and the isolation came back negative.

   (b) heartbeat every 500ms during the settle (dedicated thread, pinned to
       CPU0, prints [hb] +Nms). motive: localize the death. delivered:
       localized at +2000ms, inside the settle.

   (c) [consumer-before] and [consumer-after] markers around
       pthread_setschedparam. motive: separate "died in the walk" from "died
       async". delivered: NEVER printed [consumer-before], so no consumer
       walk is in play in this crash.

   (d) o_exited flag on the owner, main waits for it (15s) before the settle,
       to guarantee the owner was ALREADY a zombie when the consumer/heartbeat
       run. motive: the gate must not start the consumer before the owner
       becomes a zombie.

4. WHAT THIS MEANS FOR THE PLAN (read by someone who has stack-overflowed
   this kernel before)

   the value oracle (f18_post) can only be read if the process does NOT die
   during the trial. the gate is red because the process dies in ALL 3 tested
   configurations, and we now know it dies at teardown/exit, not at the
   consumer and not at the stamp. f18 was never read in any trial: the
   consumer dies before doing the store to p->prio, so there is no number.

   the 3-death pattern is always ~2s after teardown ends. there is a ~2s
   async actor. the FWRQ timeout in gate3 was 2s (ts.tv_sec += 2) and the
   waiter woke on it, but there may be a leftover FWRQ timer re-arming or the
   PI wake_rebalance. the next cheap experiment (ZERO reboots, just reasoning
   + maybe 1 boot if approved) is killing each async actor one at a time
   WITHOUT the stale tree:
     - if the FWRQ never dangles (no stale node), the timer has nothing to
       wake and the crash is gone? -> the stale node is guilty.
     - if the process exit is the trigger, the gate has to finish the trial
       without running the full process teardown: raw _exit(), or the trial
       running in a child process the parent only observes while the child is
       still alive.

5. RISK / STATE

   - 3 of 3 reboots used. BUDGET BLOWN. I will not spend more without approval.
   - no stamped trial executed. no stamp byte written on the device in any
     boot (all gates were nostamp).
   - no LP64 blob, nothing in cred/SELinux/funcptr, no writes outside the
     stamp pattern.
   - the value oracle stays UNTESTED (no f18_post read).
   - nothing committed. /data/local/tmp clean (only factory aapt/dalvik-cache).
   - diff --check clean.

artifacts
  tools/ghostlock_oracle_v2.c   (v3: zombie + heartbeat + markers)
  out/ghostlock_oracle_v2       (NDK r29 aarch64 binary, -O2 -static)
  out/logs/oracle_v2_trial1_nostamp.log
  out/logs/oracle_v2_gate_nostamp.log
  out/logs/oracle_v2_trial1_gate.log
  reports/ghostlock-oracle-v2-device.md   (gate1)
  reports/ghostlock-oracle-v2-gate.md     (gate2)
  reports/ghostlock-oracle-v2-gate3.md    (this one)
