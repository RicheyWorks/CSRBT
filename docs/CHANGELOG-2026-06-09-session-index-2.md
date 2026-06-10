# CHANGELOG 2026-06-09 — session index 2: the open list, closed (ADR-006/007/008)

The first index ended with five "deliberately open" items. This session closed every one that
had a demand signal and scoped the rest into held slices. Three ADRs designed, landed, and
Accepted; suite 431 → 457, green throughout.

| Slice | What landed | Changelog |
|---|---|---|
| ADR-005 P3 tests | the feature commit had landed test-light: 12 tests for engine members, REBUILD_SHADOW, memory controls; ADR-003/005 doc reconcile | `CHANGELOG-2026-06-09-adr005-p3-engine-member.md` |
| ADR-006 V1 | `verifyEvery(n)` — VERIFIED amplification as a dial; stride-deterministic detection; benchmark 15× at n=16 | `CHANGELOG-2026-06-09-adr006-verified-sampling.md` |
| ADR-007 W1 | optimistic unanimous votes — the writer-lock ceiling decomposed (write half structural, read half removed); no-false-quarantine proof; benchmark 2.7× under a saturating writer | `CHANGELOG-2026-06-09-adr007-optimistic-votes.md` |
| ADR-008 D1 | `BPlusTreeEngine` — Phase 4 opens; page-structured `RankedSet` with full order statistics; `engineMember()` seam generalized; oracle + ensemble-unanimity proofs | `CHANGELOG-2026-06-09-adr008-bplus-engine.md` |

## State of the world after this session

- **ADRs:** 001–008 all Accepted.
- **Deliberately held (each inside its ADR, with its trigger):** ADR-006 V2 / ADR-007 W2
  (burst auto-escalation — real dissent bursts); ADR-008 D2 (disk pages — a working set that
  misses RAM); ADR-008 D3 (registry/genome integration — after D2).
- **Composition note:** ADR-006 + ADR-007 together make a healthy VERIFIED steady state
  lock-free end to end; ADR-008's engine joins ensembles through ADR-005 P3's seam, which
  `engineMember()` now exposes for any future `RankedSet`.
- **Suite:** every slice shipped green through `ant clean test` (sandbox JDK 17; host run
  per `CLAUDE.md` recommended before push).
