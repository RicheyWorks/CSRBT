# CHANGELOG 2026-06-09 -- session index: ADR-003 closed, ADR-004 designed and landed

One day, eleven slices, two ADRs flipped to **Accepted**. This entry is the map; each slice has
its own changelog with the details.

## ADR-003 — multi-tree ensemble (E1–E6, now Accepted)

| Slice | What landed | Changelog |
|---|---|---|
| E1+E2 | facade + mirror fan-out; controller-driven O(1) promotion | `CHANGELOG-2026-06-09-ensemble-e2.md` |
| E3 | health / quarantine / heal + instant failover | `CHANGELOG-2026-06-09-ensemble-e3.md` |
| E4 | VERIFIED quorum reads + dissenter quarantine | `CHANGELOG-2026-06-09-ensemble-e4.md` |
| E5a | adaptation benchmark (O(1) swap vs O(n) rebuild; AVL target to keep the recursive validator shallow) | `CHANGELOG-2026-06-09-ensemble-e5-benchmark.md` |
| E5b | `MemberExecutor` seam + parallel write fan-out + write-failure quarantine/failover | `CHANGELOG-2026-06-09-ensemble-e5-fanout.md` |
| E5c | `SAMPLED_SHADOW` — stride-sampled shadows, exactness, sync-on-promote | `CHANGELOG-2026-06-09-ensemble-e5-shadow.md` |
| E6 | primary-only snapshots + replay-on-load; README ensemble docs; ADR **Accepted** | `CHANGELOG-2026-06-09-ensemble-e6.md` |

## ADR-004 — lock-free multi-reader reads (designed today, R1+R2 landed, now Accepted)

| Slice | What landed | Changelog |
|---|---|---|
| ADR | options (StampedLock / seqlock / left-right / persistent engine), the splay-reads-are-writes constraint, phased decision | `ADR-004-lock-free-reads-2026-06-09.md` |
| R1 | torn-read-free reads everywhere: stamped optimistic walks (step-bounded), no-splay-on-read, locked order stats | `CHANGELOG-2026-06-09-adr004-r1.md` |
| R2 | `READ_REPLICA` — left-right epoch reads over mirrors; epoch-aware promote/heal; loud degradation | `CHANGELOG-2026-06-09-adr004-r2.md` |

## Housekeeping (this pass)

- ADR-002 flipped **Proposed → Accepted**; its stale item-2 `[~]` and item-6 `[ ]` checkboxes
  closed (C5, the generic-key migration, landed back on 2026-06-01/04 across steps 2–5).
- ADR-001's stale "(pending local build verification)" qualifier removed.
- `DESIGN-adaptive-engine.md` §4 concurrency bullet annotated: "full lock-free is explicitly
  deferred" → un-deferred by ADR-004 (R1 everywhere, R2 on the ensemble).
- `TreeContext`'s concurrency javadoc rewritten to the post-R1 contract (one writer / many
  torn-read-free readers; `getTree()` and the Integer-bound machinery remain single-threaded).

## State of the world after this session

- **ADRs:** 001 Accepted, 002 Accepted, 003 Accepted, 004 Accepted (R3 held as horizon).
- **Deliberately open:** ADR-004 R3 (balanced persistent engine); ADR-003 Option C
  (periodic-rebuild shadows); memory ceilings / cap-K metrics (ADR-003 "Revisit");
  VERIFIED read-amplification tuning; DESIGN doc's Phase-4 disk engine.
  _(Update, later same day: R3 cashed in as ADR-005 P1–P3; Option C landed as
  `REBUILD_SHADOW`; memory ceilings / cap-K landed. Still open: VERIFIED read-amplification
  tuning; Phase-4 disk engine. See the ADR-005 changelogs.)_
- **Suite:** every slice shipped through host `ant clean test` green, per `CLAUDE.md`.
