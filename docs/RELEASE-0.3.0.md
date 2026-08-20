# CSRBT 0.3.0 — release notes

`csrbt-core` 0.3.0 · `csrbt-experimental` 0.3.0 · 1100 tests, 0 failures, 0 javadoc warnings.

## Why 0.3.0

ADR-029 declared it at decision time: the ensemble's `ScoreCard` now carries all **eight**
declared structures (`B_PLUS_TREE` joins), which changes its constructor — a source-breaking
change to a published type, so the minor version moves. Everything else in this release is
additive.

## Since 0.2.1

**The eighth pass (2026-08-18)**
- ADR-027 — `.eco` protocol **import** in the Workbench: the transfer box's held reverse
  path, closed. Round-trip is the oracle.
- ADR-028 — height maintained **once per write** (closing ADR-023's held bullet 1): one
  climb, not one per rotation plus one per write.
- ADR-026 amendment — `tryDeleteSnapshot` (delete signaling), opt-in fsync durability on
  saves; checksum deferred with its trigger intact.

**ADR-029 — B+ tree registry + genome slot** (fires ADR-008 D3 ahead of D2, owner's call)
- `StructureType.B_PLUS_TREE` gets its `TreeEngineRegistry` slot; disk pages (D2) stay held.
- `TreeGenome` gains the B+ tree fitness model; `GenomeDrivenTreeController` routes it.
- `BPlusTreeEngine.asTreeEngine()` — the live view across the TreeEngine seam.
- **Breaking:** `ScoreCard` carries eight structures (the reason this is 0.3.0).

**ADR-030 — native Office exports** (fires ADR-019 §2.6's held trigger)
- `OfficeExport` writes real `workbook.xlsx` / `report.pptx` via poi-ooxml 5.5.1 in
  csrbt-experimental — structure-pinned, not byte-pinned; wired into `ExperimentLab`'s
  export bundle (`runWithAllExports`).

**The 2026-08-19 correction** (see `CHANGELOG-2026-08-19-adr029-030.md` for the void list)
- The stale-clone batch that first shipped these slices misnumbered (ADR-023..026, colliding
  with the seventh pass) is voided; eighth-pass versions of the persistence surface restored;
  the stale `boolean saveSnapshot` re-implementation is dead (the additive
  `trySaveSnapshot`/`SaveResult` from 2026-08-17 is the real API); `BPlusTreeEngine` NPE
  parity (sixth pass, finding 14) and `ExperimentLab`'s J4/finding-28/S6-16 fixes restored.

## Compatibility

- Published 0.2.x surface is otherwise intact; the only break is `ScoreCard`'s constructor.
- Note on availability: **no CSRBT artifact has ever reached Maven Central** — the 0.2.0
  Central Portal upload was never completed (io/github/richeyworks 404s on repo1). 0.3.0 is
  therefore recommended as the FIRST Central release; do not backfill 0.2.x.
