# CHANGELOG 2026-08-09 — ADR-017: the heredity seams (first core changes of the ecology program)

Both held items from ADR-016 §5, fired by owner decision. Suite **716 green**
(617 core + 99 experimental, +11 tests), 0 failures.

## Core (read-only, oracle-tested before any consumer)

- **`PersistentTreeEngine.Snapshot.sharedNodeCount(Snapshot)`** — physical node sharing
  by reference identity; symmetric; iterative walks with subtree pruning at shared nodes
  (immutability ⇒ a shared node's whole subtree is shared, counted from `count`).
  `SnapshotSharingTest` (4): exact oracles (self/no-op twin = size; rebuilt-same-keys =
  0; empties = 0), single-edit bounds (size−1 ≥ shared ≥ size − 3·(height+1)), symmetry,
  and the headline gap (removing 1 of 100 keys: shared < 99).
- **`BPlusTreeEngine.leafKeyCounts()`** — per-leaf occupancy along the leaf chain.
  `BPlusLeafCountsTest` (5): counts sum to size; floor fanout/2 (lone root leaf
  excepted) and ceiling fanout through sequential fill, random churn, drain-to-empty;
  fill-factor band.

## Experimental consumers

- **`SnapshotLineage`** — generations retain snapshots (pinning documented, bounded);
  `structuralInheritance(g)` + `meanContentInheritance` / `meanStructuralInheritance`.
  Test: no-op twin inherits 100% physically; one edit opens the gap (structural <
  content, > 0.5); means ordered.
- **`FieldReport`** — `pageOccupancyReading` (tight ≥ 0.85 / healthy ≥ 0.6, the ln 2
  steady state / sparse), band-tested; lineage section now narrates both heredities.
- **Field day + lab page** — fossils: per-transition `structural` + means in JSON, the
  two-kinds-of-heredity reading and tiles on the page; survey grid: the engine's own
  pages (leaf-count chart, fill chip) beside the key-range quadrats. Sessions
  regenerated; render screenshot-verified.

## The two measured findings

1. **The price of path copying, per generation:** at 20% key turnover, 80% of keys
   survive a generation but only ~57% of physical nodes — the ~23-point gap is
   ancestors rewritten by edits whose keys persisted. Write amplification of
   persistence, measured.
2. **Sequential loading leaves sparse pages:** the demo's sequential inserts at fanout
   4 settle at 51% fill — "a split-heavy history left slack in the leaves" — the
   textbook signature, now a number on the page instead of folklore.
