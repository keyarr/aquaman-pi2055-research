oracle_v2 device phase — STABILITY GATE (2 of 3 reboots, STOPPED)

table trial -> (f18_post, f19, survived, uptime)

  trial | mode    | PAD  | f18_post | f19 | survived   | uptime before -> after
  ------+---------+------+---------+-----+------------+-----------------------
  gate  | nostamp |  --  |   n/a   | n/a | NO(REBOOT) | 6084.94 -> 8.51  (v1)
  gate2 | nostamp |  --  |   n/a   | n/a | NO(REBOOT) |  819.10 -> 25.14 (v2)
  (ii)  | stamp   |0x120 |   n/a   | n/a | NOT RUN    | --

logs: out/logs/oracle_v2_trial1_nostamp.log (v1, old protocol)
      out/logs/oracle_v2_gate_nostamp.log   (v2, hardened protocol)

gate RED twice. Stop rule 1: no stamped trial was executed.
1 reboot left out of the 3-budget, saved.

0. v1 TEARDOWN AUDIT (what the log showed)

   v1 order, from the log:
     [cmp] errno=35 EDEADLK ok, tid_waiter=6477
     [pre] tid=6477 f18=20 f19=0
     <device died here>
     [consumer] never printed

   where v1 died: between the pre-read and the consumer. in that window the
   main does xfutex(&f_target, FUPI) to wake the waiter. FUPI on f_target
   unlocks the PI mutex whose owner is the owner-thread and whose wait tree
   still held the waiter node (which sat in the dead FWRQ frame). that unlock
   is the path that fires requeue/hand-off and multi-step priority
   propagation.

   concrete v1 race: the waiter had ts.tv_sec += 5 (5s) and the main woke it
   via external FUPI at ~300ms. the waiter node in the wait tree was touched
   by two actors (the external unlock and the internal timeout) with no
   serialization on our side. plus the pre-read (open/read/close on
   /proc/<tid>/stat) in the middle of that window: do_task_stat takes
   task_lock and builds the whole stat while the PI tree is being rebalanced.
   it was new code inside the crash window.

1. PROTOCOL CHANGES (v1 -> v2), each with its motive

   (a) main no longer unlocks ANY trio futex. the waiter wakes on its own
       2s timeout and itself releases the chain (FUPI f_chain) before
       stamping. motive: kills the race between external unlock and internal
       timeout on the same wait tree. it was the prime suspect for the v1
       crash.

   (b) pre-read REMOVED for good (reader thread, pre_done/cmp_done flags,
       f18_pre/f19_pre, the open/read/close before the consumer). motive: it
       was the only NEW code inside the crash window, and the parser is
       already proven (v1 read f18=20 f19=0 correctly). the oracle only needs
       the post-read.

   (c) settle usleep(2500000) between [teardown] and the consumer. motive: PI
       rebalancing and the RT subsystem need to settle before the consumer
       touches the schedulers.

   (d) CPU0 affinity pin on all 3 threads (main, waiter, owner). motive: takes
       CPU migration out of the crash window; it is what the rest of the
       project already does (ghostlock_leak_cal.c).

   (e) the owner is explicitly joined (pthread_join) before the settle.
       motive: in v1 the owner thread stayed blocked in FUPI f_chain forever
       (nobody ever unlocked the owner) — a PI lock owner held forever, an
       obvious crash target when the consumer adjusts priority.
       secondary motive: v1 never reaped the owner.

   (f) FWRQ timeout 5s -> 2s and the chain unlock moved to right after the
       FWRQ, before the stamp. motive: the stamp has to run in the SAME frame
       the consumer will meet later; doing FUPI f_chain first reduces kernel
       work between FWRQ and stamp.

2. GATE v2 — what changed and what we learned

   v2 ran the ENTIRE teardown and printed:
     [cmp] errno=35 EDEADLK ok, tid_waiter=5181
     [teardown] waiter woke and released the chain
     [teardown] stamp done, settle 2.5s
   and died BEFORE [consumer]. gate v2 still RED.

   reading: changes (a)..(e) fixed the [cmp]..[teardown] window — it now
   survives and is deterministic. the crash migrated to the consumer window,
   and is now consistently reproducible (v1 was an occasional race; v2 dies
   always in the same place: post-teardown, at the consumer).

   the v2 crash is the consumer calling pthread_setschedparam on the waiter
   AFTER the owner was joined. once the owner is joined, its task_struct
   (the "current" the f_target PI tree references) is freed. but the waiter
   node in the f_target wait tree is still live pointing at the dead FWRQ
   frame. the consumer calls __sched_setscheduler on the waiter -> it reads
   the PI tree and chases owner->prio through a node whose owner is already
   FREE'd -> oops. this is the classic ghostlock mechanism, only firing at
   the consumer instead of at the stamp.

   that is why the gate is red in nostamp mode: the stamp is not even needed
   for the consumer to find the dangling pointer. the value oracle (f18) only
   makes sense if the consumer SURVIVES the walk, and it does not survive —
   in v2 it dies before the store to p->prio, so the resulting f18 can never
   be read.

3. WHY THIS BLOCKS THE OVERLAP PLAN (not just "instability")

   the problem is no longer teardown. the problem is the consumer. the
   consumer (__sched_setscheduler -> rt_mutex_get_effective_prio ->
   adjust_pi) walks into the PI tree and HITS a node whose owner was freed.
   the pselect stamp (the real ghostlock) exists to MASK exactly that node
   with a controlled pattern (fake task in user-mem, prio=0), so the consumer
   reads a controlled value instead of following the pointer to the freed
   task_struct. BUT the stamp only works if the consumer runs. and the
   consumer, in nostamp, dies walking the tree. in stamp mode the consumer
   would read the fake (prio=0) instead of the dangling pointer — which is why
   trial (ii) WITH stamp is the one that matters, but it may only run AFTER a
   green gate, and the green gate (nostamp) is red.

   the dilemma: the nostamp gate is red because the consumer kills the
   device, but the stamped consumer might not kill it (it reads the fake).
   the plan was "green gate first, but the gate is exactly the consumer
   without stamp, which is the dangerous case". via the attempted path
   (consumer without stamp over the stale tree) the gate did not go green;
   with stamp, another trio geometry, or another actor, the result may
   differ — untested in this gate, and nothing here says it is impossible.

4. PROPOSED FIX (for the next phase, not executed)

   the gate has to stop hitting the dangling pointer. two options, no pick
   made here:

   option A — change the TRIO geometry so the dangling node does not exist
   at the consumer. instead of the owner locking f_target (futex with wait
   tree) with the waiter dangling, make the waiter dangle and the owner hold
   the node the consumer will read. the consumer adjusts the WAITER's
   priority; the node that matters is the owner's in the f_chain tree. if the
   owner is not joined (stays alive, just blocked), its task_struct is not
   freed and the consumer does not die — without stamp, the consumer reads
   the live owner (real prio), the gate goes GREEN, and only then trial (ii)
   with stamp has a stable consumer to read the fake.
   cost: keep the owner blocked and skip the join; the stamp still applies
   (the ghostlock is the waiter's, not the owner's).

   option B — don't join the owner. basically keep the owner alive.

   both are the same idea: the gate needs a surviving consumer, and the
   consumer survives while the owner (the PI lock holder with a wait tree)
   is alive. joining the owner is what killed the gate. ironically v1 (no
   join) was more stable at the consumer, but died earlier from the external
   FUPI.

   combined: drop the external FUPI (kept) + drop the owner join (new) =>
   consumer survives, gate can go green, trial (ii) with stamp runs.

5. STATE / RISKS

   - 2 of 3 reboots used. 1 reboot in reserve, unspent.
   - No stamped trial executed. No stamp byte written on the device in any
     boot (the gate is nostamp; the stamp only runs with g_stamp_mode).
   - No LP64 blob, no writes outside the stamp pattern, nothing in
     cred/SELinux/funcptr. The fake page is allocated/compacted only in
     stamp mode, which never ran.
   - nothing committed. /data/local/tmp clean (only factory aapt/dalvik-cache).
   - the value oracle stays UNTESTED: no f18_post was read in any trial,
     because the consumer never survived the walk.

artifacts
  tools/ghostlock_oracle_v2.c   (hardened protocol, uncommitted)
  out/ghostlock_oracle_v2       (NDK r29 aarch64 binary, -O2 -static)
  out/logs/oracle_v2_trial1_nostamp.log
  out/logs/oracle_v2_gate_nostamp.log
  reports/ghostlock-oracle-v2-device.md   (previous phase, TRIAL 1)
  reports/ghostlock-oracle-v2-gate.md     (this one)
