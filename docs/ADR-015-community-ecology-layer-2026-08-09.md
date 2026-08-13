# ADR-015: The community-ecology layer — abundance from access, not membership

**Status:** Accepted (2026-08-09) — all four layers landed same day, suite green (608 core
+ 44 experimental, 0 failures).
**Date:** 2026-08-09
**Deciders:** Richmond
**Builds on:** ADR-012 (the ecology turn — instruments before mechanisms, falsifiable
hooks, deterministic meters). Motivated by `docs/AUDIT-2026-08-09-ecology-module.md`.

---

## 1. Context

The 2026-08-09 ecology-module audit (EC-1) found that `TreeEcology`'s distribution
indices are **constants** on this data structure: the tree is a set, every stored key has
abundance exactly 1, so Shannon H′ ≡ ln(S), evenness ≡ 1, empirical z ≡ 1, and Pianka
overlap between BST-disjoint subtrees ≡ 0. An index that cannot vary carries no
information. Separately (EC-2), `colonizationEquilibrium` reads wall-clock rates,
against the house rule that deterministic meters decide. And the module's one
substantial class had zero test coverage (EC-4).

The root cause is a category error, not a formula error: the abundance distribution of
this system is not *which keys are stored* but *how often the workload touches them*.
The per-key stream already flows through the ADR-002 §9.2 `WorkloadMonitor` seam; nothing
retained it.

## 2. Decision

Found abundance on access, and build the community-ecology toolkit on that footing —
four additive layers in `experimental.ecology`, no core changes, all op-clocked and
deterministic, each oracle-tested per house discipline:

1. **`EcologyRecorder`** — the seam. Implements `WorkloadMonitor` (optionally chaining
   to a real monitor), retains: cumulative and windowed per-key touch tallies (windows
   are the "communities"), per-key lifespans (birth op → death op), and a population
   series sampled at window boundaries. Bounded (window cap, oldest evicted); the clock
   is the op index.
2. **`CommunityMetrics`** — within-community indices on real abundances: richness,
   Shannon/Pielou, Simpson family, Hill numbers, and Whittaker rank–abundance curves
   with model comparison (geometric via fitted preemption k vs broken stick vs uniform,
   SSE on ln-abundance).
3. **`BetaDiversity`** — between-community measures: Jaccard, Sørensen, Bray–Curtis,
   Pianka overlap (re-founded on access distributions — temporal niche overlap between
   windows, where the structural form was identically 0), and Whittaker turnover across
   a window sequence (workload drift made measurable).
4. **`LifeTable` + `LogisticGrowth`** — demography and growth: cohort life tables in op
   time with Deevey I/II/III classification via the concentration diagnostic
   ρ = mean/median age at death (exponential benchmark 1/ln 2 ≈ 1.44; fixed thresholds
   1.2/1.8 — chosen because per-class mortality comparison degenerates on complete
   cohorts, where the terminal class always shows q = 1); Verhulst fit of the population
   series by the standard linearization (K = max N + 0.5 continuity nudge, documented),
   and the EC-2 replacement: MacArthur–Wilson equilibrium on op counts.

`TreeEcology` itself is left untouched: its structural metrics (broken-stick by depth,
r/K score, LCA bottleneck) still measure structure legitimately; the audit documents
which of its indices are degenerate and this layer supersedes them. Retiring or
re-pointing them is a separate, deliberate change.

## 3. The falsifiable hook (and its verdict)

*Thesis:* on a live tree under two access regimes — uniform round-robin vs 90/5 hot-key
— the access-founded indices separate the regimes that the structural indices provably
cannot (both regimes: structural H′ = ln 100, J′ = 1, O_LR = 0).

*Verdict (2026-08-09, `EcologyRecorderTest.indicesVaryOnLiveTree`, seeded):* confirmed —
uniform H′ > hot-key H′, evenness gap > 0.2, and consecutive hot-key windows show
temporal Pianka overlap > 0.9 where the structural form pins 0. The instrument now
measures something.

## 4. Consequences

**Unlocked:** workload character is now a first-class ecological observable — evenness
tracks hot-key concentration, window turnover tracks regime drift, life tables give the
churn profile a shape, and the growth fit summarizes ramp-to-plateau. These are the
observables ADR-012's re-arming triggers need (a real workload with long regime blocks
would show up as low window turnover with a shifted between-window Pianka).

**Costs, honest:** the recorder is caller-fed (like every `WorkloadMonitor`) — nothing
records unless wired; lifespans and cumulative tallies grow with distinct keys (same
lifetime discipline as the E2 ancestry map); the Deevey thresholds are defensible
constants, not fitted ones, and are documented as such.

**Out of scope, per the ADR-012 honesty boundary:** no biological claims. This is the
standard first-course toolkit applied to an informational system because the mappings
are structurally faithful and the questions (concentration, turnover, churn shape,
growth form) are real questions about workloads.

## 5. Verification & rollback

All-green gate: `./gradlew build` — 652 tests, 0 failures. New tests are hand-oracle
throughout (uniform → H′ = ln S exactly; Pianka 0.6 by hand; life-table d/n/l/q exact on
a constructed cohort; logistic recovery within stated tolerances on an exactly-generated
curve; determinism asserted bitwise wherever doubles flow). Rollback is trivial: the
package is additive and self-contained; deleting `experimental/ecology/` and its five
test classes restores the prior tree exactly.
