# CHANGELOG 2026-08-09 — ADR-016: ecology across the engine family (four slices)

Suite **678 green** (608 core + 70 experimental), `./gradlew build`, 0 failures, first
run. Additive throughout; zero core changes; the only touch to existing code is the
generification below.

## What landed (`io.github.richeyworks.csrbt.experimental.ecology`)

- **`EnsembleCommunity`** (§E1) — metapopulation over ensemble members: patches =
  members, extinction = quarantine/retire, recolonization = heal; sampled state diffs,
  occupancy vs Levins p* = 1 − e/c (ratio estimator, documented), species = strategy
  names → Shannon/Pielou over serving roles, functional redundancy. Identity-tracked
  members (survives list churn); sorted abundance map for deterministic iteration.
- **`SnapshotLineage`** (§E2) — generational record over `PersistentTreeEngine`
  snapshots: inherited fraction, gains/losses, pairwise Jaccard divergence, mean
  per-generation turnover. Bounded retention (default 64, oldest evicted, absolute
  numbering kept). Content-based; structural (node-sharing) lineage held with a named
  trigger.
- **`RangeQuadrats`** (§E3) — quadrat sampling over any engine's `inOrder()`: equal-width
  grid (generic keys via position mapper), index of dispersion I = s²/x̄ and Morisita Iδ
  with textbook readings. One spatial instrument for the whole engine family; B+tree
  leaf-level occupancy held with a named trigger.
- **`CacheIsland`** (§E4) — bounded-habitat observables over `SegmentedLruCache`:
  admissions = immigration, evictions = extinction discovered by non-mutating `peek`
  sweeps (dating resolution = sampling cadence, documented), richness/saturation,
  per-interval turnover (I+E)/2, and residencies as `LifeTable.Lifespan`s feeding
  ADR-015's demography layer directly.

## Supporting change

`CommunityMetrics` and `BetaDiversity` generified (`Map<Integer, Long>` → `Map<T, Long>`,
`Set<Integer>` → `Set<T>`) so strategy-name communities (E1) and generic-key generations
(E2) use the same toolkit. Source-compatible; every ADR-015 test unchanged and green.

## Tests (26 new, all hand-oracle)

`EnsembleCommunityTest` (6), `SnapshotLineageTest` (6), `RangeQuadratsTest` (7),
`CacheIslandTest` (7). Highlights, each a §3 hook verdict:

- Ensemble: quarantine → occupancy 2/3, richness 2, extinction counted; heal restores;
  the honest negative pinned — a quarantine+heal cycle entirely between samples is
  invisible to state-diff sampling, asserted as such.
- Lineage: `clear()` after capture cannot rewrite the record; 25%-replacement edit
  sequence reproduces turnover 0.4/generation exactly; eviction keeps absolute indices
  and out-of-window queries throw.
- Quadrats: regular grid → I = 0, Iδ = 900/9900·10 exactly; one dense patch → both ≫ 1;
  seeded scatter in the Poisson band; live B+tree clustered-vs-spread separation.
- Cache: probation overflow evictions dated to the exact sweep op; the MacArthur–Wilson
  equilibrium signature over 10 waves (richness flat at 5, turnover > 0 every interval);
  the protected segment as refuge under a 20-key flood; re-immigration opens a new
  residency, not a resurrection.

## Notes

- The ensemble suite runs with default (sequential) fan-out — deterministic; nothing
  here samples from concurrent state.
- All four instruments follow the `WorkloadMonitor` convention: caller-driven, nothing
  records unless wired.
