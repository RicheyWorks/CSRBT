# ADR-017: The heredity seams — physical node-sharing and page occupancy

**Status:** Accepted (2026-08-09) — both seams landed, suite green (617 core + 99
experimental = 716, 0 failures).
**Date:** 2026-08-09
**Deciders:** Richmond
**Builds on:** ADR-016 §5, which held both of these behind named triggers. The owner
fired them by decision ("do them all") rather than by trigger — recorded as such.

---

## 1. Context

ADR-016 deliberately built the ecology layer with **zero core changes**, and held two
measurements that could not be honest without core seams: true structural inheritance in
the persistent engine (content-based lineage cannot see whether a surviving *key* kept
its *node*), and page-level occupancy in the B+tree (a key-range grid cannot see leaf
boundaries). These are the first core changes of the ecology program; both are
read-only, small, and tested in core before any consumer touched them.

## 2. Decision — two seams

**Seam 1: `PersistentTreeEngine.Snapshot.sharedNodeCount(Snapshot)`.** The count of
physically shared nodes between two snapshots — reference identity, not key equality —
which is exactly what path copying makes meaningful: an edit copies the root-to-site
path and shares everything else. Implementation detail worth naming: because nodes are
immutable, a shared node's entire subtree is shared, so the second walk **prunes** at
the first shared node and counts its subtree from the `count` field — the comparison
costs one full walk of one tree plus a frontier walk of the other, both iterative
(explicit stacks, safe at any height per the F-C1 discipline). The relation is
symmetric (identity-intersection cardinality). Node class stays private; the
computation lives inside core.

**Seam 2: `BPlusTreeEngine.leafKeyCounts()`.** Per-leaf key counts, left to right
along the existing leaf chain — the page-occupancy view. Synchronized like every other
B+tree read; empty tree returns an empty list; the occupancy floor it exposes is the
same one `validateStructure()` enforces.

## 3. What the consumers now measure

**Structural heredity (`SnapshotLineage`).** Generations now retain their snapshots
(memory note: retained snapshots pin their versions' nodes — the usual
persistent-structure cost, bounded by `maxGenerations`). New observables:
`structuralInheritance(g)` and the means over the retained window. The field day's
fossil record now reports the two kinds of heredity side by side, and the number is a
real finding about the engine: **at 20% key turnover per generation, 80% of keys
survive but only ~57% of physical nodes do** — the other 23 points are ancestors
rewritten by path copying. That gap *is* the write amplification of persistence,
measured, per generation, for free.

**Page ecology (field day station 5 + lab page).** The survey grid now shows the
engine's own pages next to the key-range quadrats: leaf count, fill factor, and a
graded reading (`FieldReport.pageOccupancyReading`: tight ≥ 0.85, healthy ≥ 0.6 —
the ln 2 ≈ 69% random-insertion steady state — else sparse). The demo's sequential
inserts read **51% fill — "sparse pages, a split-heavy history"**: the textbook
signature of sequential loading at small fanout, now visible instead of folklore.

## 4. Consequences

**Unlocked:** heredity claims about the persistent engine are now physical, not
inferential; page-level layout questions ("did sequential loading leave slack?") have
a measured answer; and the lab page shows both. The B-4 caveat (equals-vs-comparator)
still applies to *key*-based metrics only — node identity is comparator-free.

**Costs, honest:** `sharedNodeCount` is O(n + m) with an identity set of one tree's
nodes — an instrument cost, fine at snapshot cadence, not an every-op call.
`SnapshotLineage` memory grows with retained *versions*, not just key sets. Both
documented at the API.

**Core-change discipline:** two public read-only methods, no behavior touched, both
oracle-tested in core (`SnapshotSharingTest`: exact oracles — self = size, no-op twin
= size, rebuilt = 0 — plus path-copy bounds and symmetry; `BPlusLeafCountsTest`:
sum-to-size, occupancy floor, capacity ceiling, churn/drain invariants, fill band).

## 5. Verification & rollback

`./gradlew build` — 716 tests, 0 failures; 9 new core tests, 2 new experimental
assertions sets; sessions regenerated; lab page render-verified by screenshot.
Rollback: both methods delete cleanly; `SnapshotLineage.Generation` reverts to its
two-component form with the structural methods removed.
