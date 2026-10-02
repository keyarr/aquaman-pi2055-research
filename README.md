aquaman PI.2055 kernel provenance research

Mi TV Stick 1080p (MiTV-AESP0, aquaman, S805Y/GXL), Android 9 PI.2055,
kernel 4.9.113 built 2022-09-06 by jenkins@c5-mitv-cm-build06.bj.
Question: which source tree built this kernel, and what can still run?

Start here: `reports/CURRENT_STATE.md` is the index of what is believed and why.
`reports/EVIDENCE_MATRIX.md` maps evidence by subsystem.
`reports/INVALIDATED_HYPOTHESES.md` lists 20 closed leads so they are not reopened.

Current state:
- McMCCRU 3d4ab79e is close family, not exact source. No exact source found
  in searched public material. That does not prove none exists.
- Rebuild is reproducible approximation (98.1% config, 190 CRC diffs, 13 missing
  symbols, DVB dropped at HEAD). Not a reproduction.
- 28 vendor .ko extracted from OTA. Presence only; runtime loading unproven.
  vermagic 4.9.y is flattened by vendor Makefile, CRCs are the real gate.
- DTB recovered from RAM at 0x01000000, valid 58280 B blob. Vendor DTS source
  still missing. RAM blob != Linux receipt.
- Fastboot download overlaps region bootm reads (E5/E6). Exact BUF unknown.
  max-download-size does not discriminate addresses.
- Unsigned boot blocked at BL31 SMC on all RAM-only paths. booti/go absent.
  No bypass demonstrated.
- BL33 cmd_tbl/handlers mapped, WRITE/FILL + same-cycle redirects in RAM
  demonstrated, live env writable. Semantic consumption by script not proven.
- GhostLock trigger + FUTEX_LOCK_PI consumer reproduced, f_target/f_alt
  distinguished. H16 live-retarget not demonstrated. Principal is now
  post-free stack reuse + disclosure (not demonstrated on Aquaman).
  Disclosure and verified reclaim remain missing. No R/W/root.

Real blockers:
1. BL31 secure-fused rejects unsigned images before kernel runs.
2. No exact source, so no CRC-compatible kernel, no exact DTS source.
3. No disclosure primitive, so no GhostLock forge target/value.
4. Env mutation is writable but never observed consumed by a safe script.

Links:
- state: `reports/CURRENT_STATE.md`
- evidence: `reports/EVIDENCE_MATRIX.md`
- closed leads: `reports/INVALIDATED_HYPOTHESES.md`
- provenance: `reports/provenance.md`
- fastboot: `reports/fastboot-memory-flow.md` (overlap, not `BUF == Y`)
- BL33: `reports/bl33-same-cycle-round46.md`, `reports/bl33-boot-decision-round44.md`
- GhostLock: `reports/ghostlock-reference-comparison-2026-10-01.md`
- audit: `reports/repo-state.md`

Invalidated hypotheses (see full file for evidence):
payload executed via fastboot boot; download != boot source; BUF is 0x10200000;
max-download-size proves position; vermagic proves origin; modules need device
root; baseline compiles with DVB=y; DTB inaccessible; 0x01040000 has no U-Boot;
old SMC count; scheduler-only consumer; free-f_chain preserves path; H16 live
retarget as principal; MSG_PEEK proves reclaim; dist=0 proves absolute offset;
page table equals active MMU; presence equals usage; 98% equals reproduction;
190 CRCs equal 190 source diffs.

What is proven / what is not:
- Proven (hardware): E5/E6 overlap, E7 SMC reject, BL33 WRITE/FILL/redirects,
  env writability, GhostLock trigger/consumer/fidelity, DTB blob validity.
- Offline only: static chain, disasm censuses, CRC/config arithmetic, H16 birth.
- Not proven: exact BUF, exact source non-existence, booti/go absence beyond
  single method, DTB Linux receipt, env semantic consumption, H16 write,
  disclosure, reclaim, R/W/root, active RWX MMU state.
- Never executed: flash/erase/saveenv/setenv persistence, BootROM USB burning,
  blind ioctls, fake object, cred/root.

Full writeup history is preserved in `reports/`. Old files carry
SUPERSEDED banners where they overstate. Do not cite them as current.
