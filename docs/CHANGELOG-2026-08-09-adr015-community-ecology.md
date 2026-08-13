# CHANGELOG 2026-08-09 — ADR-015: the community-ecology layer (audit + four slices)

Suite **652 green** (608 core + 44 experimental), `./gradlew build`, JDK 21 targeting
release 17. Everything below is additive; zero core changes; zero new javadoc warnings.

## The audit that started it

`docs/AUDIT-2026-08-09-ecology-module.md` — fresh-eyes pass over the ecology surface.
Headline (EC-1): four `TreeEcology` indices are **constants** on a duplicate-free BST —
H′ ≡ ln(S), J′ ≡ 1, empirical z ≡ 1, Pianka O_LR ≡ 0 (left/right subtrees are disjoint
by the BST invariant; the index measures the ordering property, not niche structure).
Also: EC-2 (wall-clock equilibrium, against the deterministic-meter rule), EC-4 (zero
test coverage), EC-5 (`getAugmentedValue` read unguarded), EC-6 (Integer-bound, noted).

## What landed (`io.github.richeyworks.csrbt.experimental.ecology`)

- **`EcologyRecorder`** — the abundance seam: implements `WorkloadMonitor` (chainable via
  delegate, `WorkloadFeatures.EMPTY` standalone), retains cumulative + windowed per-key
  touch tallies, per-key lifespans (birth op → death op), and a population series
  sampled at window boundaries. Op-clocked, bounded (`maxWindows`, oldest evicted).
  One ordering subtlety found by its own test and fixed same-slice: demography applies
  *before* the window-boundary sample, so a boundary op's birth is visible in that
  boundary's population sample.
- **`CommunityMetrics`** — Shannon/Pielou, Simpson family, Hill numbers (q=0/1/2 with
  the analytic q→1 limit), Whittaker rank–abundance with model comparison: geometric
  (preemption k fitted from mean successive ratio) vs broken stick vs uniform, SSE on
  ln-abundance, deterministic tie-break.
- **`BetaDiversity`** — Jaccard, Sørensen, Bray–Curtis, Pianka overlap re-founded on
  access distributions (temporal niche overlap between windows — the structural form is
  identically 0), Whittaker turnover over a window sequence.
- **`LifeTable`** — cohort life table in op time (d_x, n_x, l_x, q_x exact), Deevey
  I/II/III via the concentration diagnostic ρ = mean/median age at death (benchmark
  1/ln 2 ≈ 1.44, thresholds 1.2/1.8). Chosen over per-class mortality comparison
  because complete cohorts always show q = 1 in the terminal class — that comparison
  degenerates by construction.
- **`LogisticGrowth`** — Verhulst fit by the standard linearization (K = max N + 0.5
  continuity nudge, documented constant), R² reported; plus the EC-2 replacement:
  MacArthur–Wilson equilibrium S* = I/(I+E)·P on **op counts**.

## Tests (38 new, all hand-oracle)

`CommunityMetricsTest` (11), `BetaDiversityTest` (7), `LifeTableTest` (8),
`LogisticGrowthTest` (5), `EcologyRecorderTest` (7). The ADR's falsifiable hook is
`EcologyRecorderTest.indicesVaryOnLiveTree`: two live RB trees, uniform vs 90/5 hot-key
seeded access — access-founded H′ and J′ separate the regimes decisively (gap asserted
> 0.2) and consecutive hot-key windows show temporal Pianka > 0.9, where the structural
forms are provably identical across both regimes. EC-1's fix, demonstrated on the tree.

## Not touched, on purpose

`TreeEcology` is unchanged — its structural metrics stay legitimate; its degenerate
indices are documented in the audit and superseded by this package. Retiring them is a
separate decision. EC-5's guard and the Integer-bound note (EC-6) are held with the
audit as their record.
