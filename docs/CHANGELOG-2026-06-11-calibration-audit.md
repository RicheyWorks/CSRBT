# CHANGELOG 2026-06-11 — fresh-eyes audit of the calibration slice (and the E3b protocol)

The handoff's standing option, exercised: the 2026-06-10 day landed ~10 slices ending in
a production-constants refit and two re-pinned tests, late in the session. This pass
re-derived the slice's claims from the code with fresh eyes and re-ran the suite
independently (clean shadow-tree build, javac 17.0.19 + JUnit console): **528/528 green,
twice** (before and after the fixes below).

## Verified, by re-derivation

- **Constants:** `CostModelStrategyScorer` matches the calibration changelog table
  exactly; shape (functional form) unchanged; scorer remains a pure function of
  (r, w, s).
- **Dominance algebra:** AVL's worst case (.46 + .04·1 = .50 at pure writes) beats RB's
  best case (.62 − .05·1 = .57) — **RB is strictly dominated everywhere** in the
  calibrated model. Intended on the comparisons meter (AVL won every diet probed) and
  documented in the class javadoc; RB regains a role only if rotation pricing gets a
  consumer (ADR-009 §3, held).
- **Surviving pins, recomputed:** §10 trace (r=.94, s=.71): Splay .264 < AVL .350 <
  Hybrid .418 < RB .579 — Splay first, RB last ✓. Max-skew margin: .34 − .10 = .24 >
  the asserted .1 ✓. Hybrid = mean + .02 can never rank first (mean strictly exceeds
  the minimum unless all tie, and then the penalty decides) ✓.
- **E3b protocol integrity:** premise hard-asserted (≥2 distinct block winners); the
  adaptive contestants race the **production** `MorphPolicy.defaults()`, not the eager
  harness policy; the verdict is printed, never hard-asserted (V5 discipline); fully
  seeded, no wall-clock anywhere in the meter.

## Fixed (three stale-doc nits, no behavior)

1. `StrategyScorerTest` class javadoc still told the pre-calibration story ("Red-Black
   for write-heavy/balanced") above tests that pin the opposite. Rewritten to the
   measured story, with the DESIGN §3.2/§10 reading named as the rotation-priced one.
2. `ControllerConvergenceTest` regime-change `@DisplayName` said "heavy writes return
   to RB" while the body asserts AVL. Display name now matches the assertion.
3. The "16–40%" RB-trails-AVL range (scorer javadoc + calibration changelog table)
   mixed conventions — churn is +16% RB-over-AVL but sequential is +67% (the 40% was
   AVL-under-RB). Replaced with the per-diet figures: **+16% churn, +22% uniform,
   +67% sequential**.

## Observed, recorded, no action

- **G4's margin headroom is thin by construction:** on pure writes the RB→AVL gap is
  (.57 − .50)/.57 ≈ **12.3%**, clearing the eager harness margin (10%) by 2.3 points —
  deterministic constants, so stable, but anyone re-tuning the harness margin past
  ~0.12 flips G4. Under the production 20% margin a *pure-write* diet would not morph
  at all; the E3/E3b mixed diets sit near 27%, which is why production morphs there.
  Named so nobody rediscovers it as a bug.
- The Splay crossover claim ("s·r ≳ 0.4") is approximate — the exact frontier also
  moves with w and s independently (near-ties appear from s·r ≈ 0.3). Doc claim, not a
  pin; left as is.

## Verdict

The calibration slice survives fresh eyes: constants faithful to the measured tables,
re-pins guarding the right properties (morph *count*, not incumbent name), experiment
protocol sound, suite independently green. The fixes are documentation truth-keeping
only. The day's honest claim stands as written: *the calibrated selector matches the
best fixed choice without knowing it in advance; it does not yet beat it.*
