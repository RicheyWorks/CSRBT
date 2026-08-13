# CHANGELOG 2026-08-12 — post-ADR-020 audit: a theory-bench crash and a false bounds claim

Adversarial pass over the surface landed after the 2026-08-09 ecology audit (ADR-017
heredity seams, ADR-018 amortization frontier, ADR-019 classroom seam, ADR-020 student
seam), probe-first per house discipline; core engines differential-tested against
independent oracles. Full findings in `docs/AUDIT-2026-08-12-model-domain.md`. Suite
**772 green** (617 core + 155 experimental, +5 tests), 0 failures. Built and run on JDK 21.

## Fixed

- **M-1 (Medium) — `ExperimentSpec.parseModel`:** a `model:` line with a valid kind and
  arity but out-of-domain values parsed clean and then threw from `ExperimentLab.run`,
  crashing the entire report — while `cross:`, `tree:`, and `data:` all validate their
  content at parse time and report a bad one as a problem. Three kinds could sink a run:
  `markrecapture` with R > min(M, C), `hardyweinberg` with a negative or all-zero count,
  and `eulerlotka` with R₀ = 0. This broke the contract `ExperimentLabTest.badLinesReported`
  states ("never guesses or crashes"), which had only covered structurally-bad models.
  Now `parseModel` validates the domain of the value-sensitive models by invoking the
  underlying function (the `parseCross` pattern), so a bad model is dropped and reported
  as `⚠ spec:` while valid models beside it still run. Probe tests:
  `markRecaptureOutOfDomain`, `hardyWeinbergNegative`, `eulerLotkaZeroR0`,
  `goodModelSurvivesBadNeighbour` (all failed against the unfixed code).

## Corrected (contract, not semantics)

- **M-2 (Medium) — `EcologyRecorder`:** the `Bounded` Javadoc claimed the demography
  registers "grow with distinct keys." They don't — `lifespans` grows with observed
  deaths and `populationSeries` with closed windows, and neither is evicted, so a
  remove-heavy stream that reuses key hashes leaks without bound in the very ADR-002 §9.2
  production seam the class advertises. Demonstrated: one key hash, 50k add/remove cycles →
  `cumulative`/`birthOps`/`closedWindows` all flat, but `lifespans` = 50,000. The two
  registers are load-bearing (the `LifeTable` cohort and the `LogisticGrowth` series), so
  the Javadoc is corrected to state exactly what is bounded vs. what grows with events,
  with drain/reconstruct guidance; `EcologyRecorderBoundingTest` pins the true behaviour.
  True bounded memory (rolling caps) is left as a flagged design decision.

## Verified clean (worth not re-deriving)

MarkRecapture (LP/Chapman oracles, variance non-negativity, overflow-safe cast);
PhyloTree Newick parse/round-trip and malformed-input rejection; FieldData both entry
forms and inverses; PopulationGenetics HW χ² and Euler–Lotka bisection; MendelianGenetics
gamete/normalisation/phenotype and the graceful `Cross`-arity mismatch; TheoreticalModels
closed forms and clamps; CommunityMetrics (rarefaction log space, broken-stick sum-to-N,
bestFit tie-break); BetaDiversity boundary conventions; PersistentTreeEngine
`sharedNodeCount` (pruned identity walk, no double counting, `structural ≤ content`
invariant); SnapshotLineage indexing; ExperimentLab qualitative bands matching
FieldReport thresholds and the UNGRADEABLE paths; ExperimentExport CSV inverses;
BPlusTreeEngine `leafKeyCounts`.
