# MAP - reports with no pointer from the main indexes

100 files in `reports/` had no pointer from the main indexes. This page gives
each one a pointer. It changes no verdict: `CURRENT_STATE.md` wins and
`INVALIDATED_HYPOTHESES.md` still gates new theories.

101 entries below: the 100 pointerless files plus
`plan-smc-gate-neutralize-magisk.md`, which is named only by the observations
file. Both 2026-11-19 files are OFFLINE_ONLY and unconsolidated.

Counts: BL33 6, BL31/FIP/AMLSECU 27, SMC storage and keyman 41, provenance 10,
GhostLock 12, USB boot state 3, added 2026-11-19 2.

## BL33 / U-Boot (6)

- [bl33-bl31-interface-round14.md](bl33-bl31-interface-round14.md)
- [bl33-interface-round15.md](bl33-interface-round15.md)
- [bl33-offline-round12.md](bl33-offline-round12.md)
- [bl33-offline-round13.md](bl33-offline-round13.md)
- [bl33-write-primitive-round16.md](bl33-write-primitive-round16.md)
- [bl33-bootdelay-live-round45.md](bl33-bootdelay-live-round45.md)

## BL31, FIP and AMLSECU (27)

- [amlsecu-public-implementations.md](amlsecu-public-implementations.md)
- [bl31-aml-data-process-round17.md](bl31-aml-data-process-round17.md)
- [round18-bl31/01-artifact-inventory.md](round18-bl31/01-artifact-inventory.md)
- [round18-bl31/02-bl33-handoff.md](round18-bl31/02-bl33-handoff.md)
- [round18-bl31/04-bl31-candidates.md](round18-bl31/04-bl31-candidates.md)
- [round18-bl31/05-emmc-candidates.md](round18-bl31/05-emmc-candidates.md)
- [round18-bl31/06-bl31-analysis.md](round18-bl31/06-bl31-analysis.md)
- [round26-bl31-runtime-search.md](round26-bl31-runtime-search.md)
- [round27-bl31-layout.md](round27-bl31-layout.md)
- [round27-bl31/03-memory-layout.md](round27-bl31/03-memory-layout.md)
- [round27-bl31/04-protection.md](round27-bl31/04-protection.md)
- [round27-bl31/06-entry-handoff.md](round27-bl31/06-entry-handoff.md)
- [round28-fip-reconstruction.md](round28-fip-reconstruction.md)
- [round28-fip/02-fip-structure.md](round28-fip/02-fip-structure.md)
- [round28-fip/03-bl2-image-table.md](round28-fip/03-bl2-image-table.md)
- [round28-fip/04-bl31-header.md](round28-fip/04-bl31-header.md)
- [round28-fip/06-key-origin.md](round28-fip/06-key-origin.md)
- [round28-fip/07-aquaman-vs-family.md](round28-fip/07-aquaman-vs-family.md)
- [round28-fip/08-summary.md](round28-fip/08-summary.md)
- [round29-bootloader-crypto.md](round29-bootloader-crypto.md)
- [round29-fip-crypto/01-aml-encrypt-pipeline.md](round29-fip-crypto/01-aml-encrypt-pipeline.md)
- [round29-fip-crypto/02-user-key-package.md](round29-fip-crypto/02-user-key-package.md)
- [round29-fip-crypto/03-bootloader-image-pipeline.md](round29-fip-crypto/03-bootloader-image-pipeline.md)
- [round29-fip-crypto/04-fip-layout.md](round29-fip-crypto/04-fip-layout.md)
- [round29-fip-crypto/05-key-material-sources.md](round29-fip-crypto/05-key-material-sources.md)
- [round29-fip-crypto/06-record128-analysis.md](round29-fip-crypto/06-record128-analysis.md)
- [round29-fip-crypto/07-summary.md](round29-fip-crypto/07-summary.md)

## SMC storage and keyman (41)

- [storage-buffer-round20.md](storage-buffer-round20.md)
- [round20-storage-buffer/01-smc-storage-dataflow.md](round20-storage-buffer/01-smc-storage-dataflow.md)
- [round20-storage-buffer/03-c1-content.md](round20-storage-buffer/03-c1-content.md)
- [round20-storage-buffer/04-storage-callgraph.md](round20-storage-buffer/04-storage-callgraph.md)
- [share-storage-round21.md](share-storage-round21.md)
- [round21-share-storage/01-smc-dataflow.md](round21-share-storage/01-smc-dataflow.md)
- [round21-share-storage/02-c1-writers.md](round21-share-storage/02-c1-writers.md)
- [round21-share-storage/03-c2-readers.md](round21-share-storage/03-c2-readers.md)
- [round21-share-storage/04-block-buffer.md](round21-share-storage/04-block-buffer.md)
- [round21-share-storage/05-secure-storage-graph.md](round21-share-storage/05-secure-storage-graph.md)
- [round21-share-storage/06-protocol.md](round21-share-storage/06-protocol.md)
- [storage-reachability-round22.md](storage-reachability-round22.md)
- [round22-storage-reachability/01-command-reachability.md](round22-storage-reachability/01-command-reachability.md)
- [round22-storage-reachability/02-writer-callgraphs.md](round22-storage-reachability/02-writer-callgraphs.md)
- [round22-storage-reachability/03-reader-callgraphs.md](round22-storage-reachability/03-reader-callgraphs.md)
- [round22-storage-reachability/04-smc60-65.md](round22-storage-reachability/04-smc60-65.md)
- [round22-storage-reachability/05-env-boot-reachability.md](round22-storage-reachability/05-env-boot-reachability.md)
- [round22-storage-reachability/06-summary.md](round22-storage-reachability/06-summary.md)
- [keyman-interface-round23.md](keyman-interface-round23.md)
- [round23-keyman/01-keyman-parser.md](round23-keyman/01-keyman-parser.md)
- [round23-keyman/02-keyman-write.md](round23-keyman/02-keyman-write.md)
- [round23-keyman/03-keyman-read.md](round23-keyman/03-keyman-read.md)
- [round23-keyman/04-buffer-layouts.md](round23-keyman/04-buffer-layouts.md)
- [round23-keyman/05-name-slot-audit.md](round23-keyman/05-name-slot-audit.md)
- [round23-keyman/06-output-reachability.md](round23-keyman/06-output-reachability.md)
- [round23-keyman/07-summary.md](round23-keyman/07-summary.md)
- [keyman-vector-round24.md](keyman-vector-round24.md)
- [round24-keyman-vector/01-device-vector.md](round24-keyman-vector/01-device-vector.md)
- [round24-keyman-vector/02-dts-selection.md](round24-keyman-vector/02-dts-selection.md)
- [round24-keyman-vector/03-generic-read.md](round24-keyman-vector/03-generic-read.md)
- [round24-keyman-vector/04-generic-write.md](round24-keyman-vector/04-generic-write.md)
- [round24-keyman-vector/05-validator-map.md](round24-keyman-vector/05-validator-map.md)
- [round24-keyman-vector/06-output-sink.md](round24-keyman-vector/06-output-sink.md)
- [round24-keyman-vector/07-summary.md](round24-keyman-vector/07-summary.md)
- [round24-key-surface/01-19keys.md](round24-key-surface/01-19keys.md)
- [round24-key-surface/02-keyman-reachability.md](round24-key-surface/02-keyman-reachability.md)
- [round24-key-surface/03-backend-resolution.md](round24-key-surface/03-backend-resolution.md)
- [round24-key-surface/04-permit-analysis.md](round24-key-surface/04-permit-analysis.md)
- [round24-key-surface/05-output-path.md](round24-key-surface/05-output-path.md)
- [round24-key-surface/06-hdcp2.md](round24-key-surface/06-hdcp2.md)
- [round24-key-surface/07-summary.md](round24-key-surface/07-summary.md)

## Provenance and kernel baseline (10)

- [round25-continuous-investigation.md](round25-continuous-investigation.md)
- [round30-firmware-provenance.md](round30-firmware-provenance.md)
- [round30-provenance/01-public-firmware-sources.md](round30-provenance/01-public-firmware-sources.md)
- [round30-provenance/02-exact-build-matching.md](round30-provenance/02-exact-build-matching.md)
- [round30-provenance/03-userkey-public-search.md](round30-provenance/03-userkey-public-search.md)
- [round30-provenance/04-build-reuse.md](round30-provenance/04-build-reuse.md)
- [round30-provenance/05-pipeline-reproduction.md](round30-provenance/05-pipeline-reproduction.md)
- [round30-provenance/06-summary.md](round30-provenance/06-summary.md)
- [source-candidates.md](source-candidates.md)
- [kernel-boot-status.md](kernel-boot-status.md)

## GhostLock (12)

- [ghostlock-breakthrough.md](ghostlock-breakthrough.md)
- [ghostlock-chainwalk-predicate.md](ghostlock-chainwalk-predicate.md)
- [ghostlock-chainwalk-validation.md](ghostlock-chainwalk-validation.md)
- [ghostlock-deep-emit.md](ghostlock-deep-emit.md)
- [ghostlock-disclosure-stackreuse-gap-2026-10-01.md](ghostlock-disclosure-stackreuse-gap-2026-10-01.md)
- [ghostlock-emit-census.md](ghostlock-emit-census.md)
- [ghostlock-h16-control.md](ghostlock-h16-control.md)
- [ghostlock-h16-write.md](ghostlock-h16-write.md)
- [ghostlock-heap-consumption.md](ghostlock-heap-consumption.md)
- [ghostlock-null-stale-discriminator.md](ghostlock-null-stale-discriminator.md)
- [ghostlock-stock-disclosure.md](ghostlock-stock-disclosure.md)
- [ghostlock-targeted-write.md](ghostlock-targeted-write.md)

## USB boot state (3)

- [round33-doreset-watchdog-loop.md](round33-doreset-watchdog-loop.md)
- [round35-mode7-bootdelay.md](round35-mode7-bootdelay.md)
- [round36-force-usb-boot-state.md](round36-force-usb-boot-state.md)

## Added 2026-11-19 (2)

- [observations-new-angles-2026-11-19.md](observations-new-angles-2026-11-19.md)
- [plan-smc-gate-neutralize-magisk.md](plan-smc-gate-neutralize-magisk.md)

## Added 2026-11-19: EL3 arbitrary access audit (4)

- [round59-el3-arbitrary-access/01-smc-interface-matrix.md](round59-el3-arbitrary-access/01-smc-interface-matrix.md)
- [round59-el3-arbitrary-access/02-bl31-static-handler.md](round59-el3-arbitrary-access/02-bl31-static-handler.md)
- [round59-el3-arbitrary-access/03-test-matrix.md](round59-el3-arbitrary-access/03-test-matrix.md)
- [round59-el3-arbitrary-access/04-diag-stub.md](round59-el3-arbitrary-access/04-diag-stub.md)
