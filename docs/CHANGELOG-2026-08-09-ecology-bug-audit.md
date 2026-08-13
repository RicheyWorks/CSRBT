# CHANGELOG 2026-08-09 — ecology bug audit: one real bug, one guard, one honest test

Adversarial same-day pass over the ADR-015/016 ecology surface, probe-first per house
discipline (every claimed defect shown failing before its fix counts). Full findings in
`docs/AUDIT-2026-08-09-ecology-bug-audit.md`. Suite **681 green** (608 core + 73
experimental, +3 tests), 0 failures.

## Fixed

- **B-1 (Medium) — `CacheIsland`:** eviction + re-admission between sweeps silently
  dropped the first residency (birth op overwritten, no extinction counted), breaking
  immigrations &#x2212; extinctions = residents. Probes failed 2/2 against the unfixed code.
  Now: an admission of an absent-but-tracked key closes the old residency first (dated at
  the admit), and a lookup <em>miss</em> on a tracked key closes its residency at the miss
  (the miss is proof of eviction — better dating than the next sweep). Invariant asserted
  in tests. Regression tests: `rebirthBetweenSamples`, `missClosesResidency`.
- **B-2 (Low) — `RangeQuadrats`:** non-finite mapped positions were silently binned into
  quadrat 0 (`(long) NaN == 0`); now `IllegalArgumentException` naming the key. Test
  added.
- **B-3 (Low, test) — `EnsembleCommunityTest`:** the Levins "oracle" asserted arithmetic
  computed inside the test itself. Replaced with an instrument-driven version: balanced
  cycles pin p* = 0 from real event counts, an unhealed fifth extinction exercises the
  clamp, occupancy asserted alongside as the measurement the model is compared to.
- **B-5/B-6 (hygiene):** `EcologyRecorder` window maps unified to `LinkedHashMap`
  (order-consistency only); dead `EnsembleCommunity.lastStateView()` removed.

## Documented

- **B-4 (Low) — `SnapshotLineage`:** generation sets compare keys by `equals` while
  engines deduplicate by comparator; a comparator-inconsistent key type would misreport
  turnover. No live defect (Integer/String keys are consistent); Javadoc caveat added
  with the named trigger — custom-comparator key type arrives &#x2192; thread the comparator
  through (ADR-002 seam discipline).

## Verified clean (worth not re-deriving)

LifeTable's rectangular-cohort Type I call and conservative class widths; `bestFit`
tie-breaks and `fitGeometricK` division safety; LogisticGrowth's finite logit
(K = maxN + 0.5), constant-series and declining-series paths; EcologyRecorder boundary
ordering and duplicate-add/orphan-remove conventions; EnsembleCommunity's documented
cancelled-cycle blindness (the ensemble API offers no between-sample evidence, so unlike
B-1 documentation is the ceiling there); all generified metric boundary conventions.
