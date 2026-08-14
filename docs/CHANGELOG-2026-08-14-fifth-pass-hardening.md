# Changelog — 2026-08-14 fifth-pass hardening

Companion to `AUDIT-2026-08-14-wiring-and-fifth-pass.md` (finding numbers F-1…F-11,
W-1…W-3 refer to it). Suite green before and after; three new probe test classes.

## csrbt-core

- `TreeNode1` — **F-1**: `recomputeAugmentAndPropagate` now refreshes height and
  black-height on the same walk as size/augment; `setLeft`/`setRight` fold their
  redundant local refreshes into it. Fixes stale heights after snapshot load, deep
  copy, and checkpoint restore (AVL/Hybrid invariant break, 30/30 seeds pre-fix).
- `adapter/NavigableOrderedSet` — **F-2**: `inRangeForBound(k, inclusive)` gets
  TreeMap parity (exclusive endpoints cannot be re-admitted inclusively).
  **F-3**: view snapshots ride the new one-acquisition `OrderedSet.rangeSnapshot`;
  base and view `first`/`last`/`pollFirst`/`pollLast` are single base calls; in-view
  `lower/floor/ceiling/higher` fold the view bound into the query pre-navigation;
  `descendingIterator().remove()` now delegates to the live set. **W-2**: dead
  `countUpTo` package helper removed.
- `OrderedSet` — **F-3**: new `rangeSnapshot(lo, loInc, hi, hiInc)`: pruned in-order
  walk under one guarded acquisition (inOrderReadOnly's step-budget/torn protocol).
- `strategy/RedBlackStrategy`, `SplayStrategy`, `HybridStrategy` — **F-4**:
  duplicate-insert WARN → DEBUG (hot path, battle fairness, M-3 precedent).
- `evolution/StrategyBattleRunner` — **F-4**: volatile search sink (anti-DCE);
  degenerate-opCount guards in SEQUENTIAL and DELETE_HEAVY workload generation.
- `evolution/GenomeDrivenTreeController` — **F-9**: `applyStructure` commits
  controller/genome state only when `setStrategy` reports the morph applied.
- `ensemble/ParallelMemberExecutor` — **F-10**: interrupt during fan-out collect no
  longer abandons in-flight members; collects uninterruptibly, restores the flag.
- `evolution/PolicyEvolutionController`, `PolicySearchController` — **F-11**:
  `emit()` hardened against throwing listeners (M-1 parity).
- New tests: `ReconstructionHeightProbeTest` (3), `ViewBoundsParityProbeTest` (4,
  incl. a 1-s concurrent clear/refill race probe).

## csrbt-experimental

- `ecology/EnsembleCommunity` — **F-5**: Levins p* from per-exposure rates
  (ê = ext/occupied patch-samples; ĉ = recol per empty patch-sample ÷ mean occupancy)
  instead of the degenerate event-total ratio; exposure counters added to `sample()`.
  `EnsembleCommunityTest` updated to the new arithmetic (5/6, 22/27 cases).
- `ecology/PhyloTree` — **F-6**: whitespace tolerated before '('; `trimmed()` falls
  back to `Double.toString` when `%.6f` would change the value.
- `ecology/FieldData` — **F-7**: `toEcoLine` hyphen-normalizes names containing
  whitespace/`=`; comma/tab lines with bad or empty counts are reported problems.
- `ecology/ExperimentSpec` — **F-8**: `note(Target)` target taken from the original
  (case-preserved) line; blank names in `expect:` args rejected at parse time.
- `ecology/LogisticGrowth` — plateau caveat documented on `fit`.
- `build.gradle.kts` — **W-1**: `viabilityMap` JavaExec task added; `ViabilityMap`
  javadoc run instruction updated from the stale Ant-era command.

## docs

- `ecology-lab.html` — `jsNewick` mirrors both PhyloTree fixes (whitespace, empty
  branch length); dichotomous-key walker gets a cycle guard; embedded sample session's
  levins value refreshed.
- `ecology-lab-session.json` — regenerated (`./gradlew :csrbt-experimental:ecologyFieldDay`);
  only the levins value changed (0 → 0.833333).
- `ADR-022` — follow-up note: rank claims are documentation (not test-pinned, by
  design); the two timed-path fairness leaks closed.

## Host-side follow-ups (git runs on your terminal, per CLAUDE.md)

- `git rm -r _to_delete` — **W-3**: ~1.7 MB of tracked tarballs in a directory named
  `_to_delete`.
- Held decision worth an ADR when convenient: `FilePersistenceAdapter.saveSnapshot`'s
  log-and-swallow `IOException` (callers get no failure signal; `boolean` return or
  `UncheckedIOException` are the candidates).
