# Ecology-layer bug audit — 2026-08-09 (post-ADR-015/016)

**Scope:** adversarial pass over the nine ecology classes landed today (`EcologyRecorder`,
`CommunityMetrics`, `BetaDiversity`, `LifeTable`, `LogisticGrowth`, `EnsembleCommunity`,
`SnapshotLineage`, `RangeQuadrats`, `CacheIsland`) and their eight test suites. Method:
re-derive each instrument's bookkeeping by hand looking for missed-event paths, degenerate
inputs, and accounting invariants; every suspected defect gets a probe test that must
FAIL against the unfixed code before the fix counts. Suite after: **681 green**
(608 core + 73 experimental), 0 failures.

---

## Confirmed defects (probe-verified, fixed)

### B-1 (Medium). CacheIsland silently dropped a residency on eviction + re-admission between sweeps.

`CacheIsland.admit` checked residency with `peek`, and for an absent key overwrote
`residentSince[key]` with the new birth op. If a tracked key was **evicted and re-admitted
between two `sample()` sweeps**, the first residency vanished: never closed as a lifespan,
never counted as an extinction — and the accounting invariant broke
(immigrations &#x2212; extinctions &#x2260; current residents; probe showed 7 &#x2212; 0 = 7 against 5 real
residents, plus a lost lifespan). Both probes (`rebirthBetweenSamples`,
`missClosesResidency`) failed against the unfixed code: **2 tests, 2 failed** — then
passed after the fix.

*Fix:* `closeStaleResidency` — an admission of an absent-but-tracked key first closes the
old residency (dated at the admit; the documented sampling-resolution convention), then
opens the new one; and a **lookup miss** on a tracked key now closes its residency too
(the miss itself is proof of eviction, and gives better dating than the next sweep).
The invariant immigrations &#x2212; extinctions = current residents is now asserted in tests.
This brings `CacheIsland` to the same honesty standard `EnsembleCommunity` already
documented for its cancelled-cycle blindness — except here the API offers evidence
(`peek`/`get`), so the blindness is closed rather than merely documented.

### B-2 (Low). RangeQuadrats binned non-finite positions silently into quadrat 0.

A position mapper returning NaN/&#xB1;Infinity poisoned min/max, and `(long) NaN == 0` dropped
every key into bin 0 — a garbage dispersion verdict with no error. *Fix:* non-finite
positions now throw `IllegalArgumentException` naming the key; probe test added (NaN and
a 1/(d&#x2212;1) Infinity mapper).

### B-3 (Low, test defect). The Levins "oracle" test asserted its own arithmetic.

`EnsembleCommunityTest.levinsRatioOracle` computed `p = 1 − 1/4` inside the test and
asserted that — a tautology touching no instrument code (the drive it wrapped can only
produce e = c). *Fix:* replaced with an instrument-driven test: balanced cycles pin
p* at 0 from real event counts, a fifth unhealed extinction exercises the clamp path
(e/c = 5/4 &#x2192; raw negative &#x2192; 0), and the direct occupancy measurement (2/3) is asserted
alongside — the model-vs-measurement comparison the instrument exists for.

## Documented, not fixed (correct scope decisions, now written down)

### B-4 (Low). SnapshotLineage compares keys by equals; engines deduplicate by comparator.

For a key type whose comparator is inconsistent with `equals`, cross-generation Jaccard
could report turnover the engine never performed. All current key types (Integer, String)
are consistent, so no live defect — but this is exactly the seam class ADR-002 exists for.
Caveat added to the class Javadoc with the named trigger: a custom-comparator key type
arrives &#x2192; thread the comparator through.

## Hygiene (fixed)

- **B-5.** `EcologyRecorder` mixed `HashMap` (initial window) and `LinkedHashMap` (rolled
  windows) — unified to `LinkedHashMap`. View-order consistency only; map equality was
  already order-independent, no behavioral change.
- **B-6.** `EnsembleCommunity.lastStateView()` — dead code (written for tests, used by
  none) — removed, with its lone `HashMap` import.

## Examined and verified clean (so the next audit needn't re-derive them)

- **LifeTable rectangular cohort:** all members dying at the same age classifies TYPE_I at
  any age (&#x3C1; = 1). Correct — rectangular survivorship *is* the Type I shape; the type is
  about curve shape, not absolute age.
- **LifeTable class width** (`maxAge/classes + 1`) can leave trailing empty classes when
  maxAge is near a multiple of the class count — conservative binning, all counts land,
  no misclassification path.
- **CommunityMetrics.bestFit** single-species and all-tied inputs resolve by the
  documented enum-order tie-break; `fitGeometricK` cannot divide by zero (ranks exclude
  non-positive counts).
- **LogisticGrowth** cannot produce a non-finite logit (K = maxN + 0.5 &#x2265; N + 0.5 for
  every usable sample); constant-N series yields r = 0, R&#xB2; = 1 by the ssTot = 0 branch;
  declining series fit through the same regression with r &lt; 0.
- **EcologyRecorder** boundary ordering (demography before the window-boundary population
  sample) — the ADR-015 same-day fix — re-verified; duplicate adds keep the original
  birth; removes without observed births tally but open no lifespan, as documented.
- **EnsembleCommunity** cancelled-cycle blindness (quarantine + heal entirely between
  samples is invisible) remains — documented and pinned by its own test; unlike B-1 the
  ensemble API offers no between-sample evidence, so documentation is the honest ceiling.
- **BetaDiversity / CommunityMetrics** generified signatures: all boundary conventions
  (empty-vs-empty, zero-count filtering) re-checked against their hand oracles post-B-1
  build; unchanged and green.
