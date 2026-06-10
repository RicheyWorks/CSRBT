# CHANGELOG 2026-06-09 — ADR-008 D1: the B+tree engine (Phase 4 opens, structure before disk)

The DESIGN doc's last held phase ("add a large-n engine once the loop is proven") opens. The
ADR (`ADR-008-bplus-tree-engine-2026-06-09.md`, Accepted; options: B+tree vs B-tree vs
cache-oblivious vs LSM) slices it deliberately: **D1 (this slice)** proves the page-structured
data structure against the codebase's contracts in memory; **D2 (held)** moves the pages to
disk via `KeySerializer`; **D3 (held)** adds registry/genome integration only once "recommend
the disk engine" can mean something. The evolution layer is untouched.

## The engine (`core/BPlusTreeEngine.java`, new — implements `RankedSet<K>`)

- **Shape:** every key in a leaf; internal nodes are pure routing (separators + per-child
  subtree counts); leaves chained ascending. Configurable fanout (default 32, floor 4); a
  node is a sorted-array scan — cache-line friendly where a pointer BST pays a miss per level.
  The in-memory layout *is* the D2 page layout by design.
- **Order statistics, count-funded:** `select`/`rank`/`countInRange` descend on the per-child
  counts (ADR-005's trick, paged); `rangeQuery`/`inOrder` walk the leaf chain.
- **OrderedSet parity** (the voting contract) method-for-method: effective-change booleans,
  null-on-empty extremes, throw-on-absent successor/predecessor/rank, clamped percentile,
  empty results for `lo > hi`. Realized write meters; ~40 bytes/key footprint model.
- **Delete rebalancing:** borrow-from-sibling (separator rotation) before merge, root
  collapse on the way out; the separator invariant is honest about deletions — a separator
  may name a departed key, routing bounds stay correct, and `validateStructure()` checks
  routing bounds, occupancy floors, uniform leaf depth, counts, and chain order.
- **Concurrency:** every public method synchronized — the coarsest correct answer, required
  because ADR-007's optimistic vote reads members lock-free and a paged tree mutates in place
  (unlike R1-guarded `OrderedSet` or the immutable persistent engine). Page latching is D2+
  territory if ever demanded.

## The seam (`EnsembleOrderedSet.Builder.engineMember`)

- `engineMember(Supplier<RankedSet<K>>, label)` — ADR-005 P3's `persistentMember()`,
  generalized; `persistentMember()` now delegates to it. Any parity-honoring `RankedSet` is
  one builder line from full ensemble citizenship.

## Tests (`BPlusTreeEngineTest`, 6 tests; suite 457, green)

- Oracle parity vs `TreeSet`: 6k seeded random ops at fanout 4 (maximal structural churn),
  `validateStructure()` every 250 ops; sorted/reverse/organ-pipe inputs stay logarithmic;
  delete-heavy shuffle drains 1k keys to a valid empty tree through the merge paths.
- Order-statistics parity vs `OrderedSet` across select/rank/successor/predecessor/median/
  percentile/countInRange/rangeQuery; the edge-semantics contract asserted case by case.
- Ensemble citizenship: a VERIFIED ensemble (RB + AVL + B+tree) where **every read is a
  3-way vote** — unanimity throughout under 1.8k mixed ops is the end-to-end parity proof —
  plus explicit promotion of the B+tree member to serving primary.

## Held

- D2 — paged file backing via `KeySerializer` (read path first), when a working set misses RAM.
- D3 — `StructureType.B_PLUS_TREE` + capability + fitness, after D2.
