# CHANGELOG 2026-08-12 — T-1: the rotation meter was dead; the score stops double-charging

Found while validating the ADR-022 re-scored tournament: every competitor reported
**rotations = 0** in every workload. Suite **806 green** (648 core + 158
experimental), 0 failures.

## Fixed

- **T-1 (Medium) — `TreeContext.getRotationCount()`:** read a legacy field that
  nothing increments (its own comment: "strategies do not call it") — the real meter
  is the engine's `onRotation()` counter, live since the ADR-002 rotation seam. Every
  consumer was blind: the battle runner's rotation score term was always 0, the
  genome controller's STRESS metric (rotations per window) was identically 0 forever
  — the third blinded legacy metric after entropy (G-A) and fragmentation (G-D) —
  and `explainState`'s rotation line always printed 0. Now delegates to the engine's
  live count (documented: a strategy morph builds the engine aside, so the count
  resets per engine generation; per-window deltas self-heal). `incrementRotations()`
  is deprecated as the dead hook it was. Probes: `rotationCountIsLive`,
  `stressMetricIsLive` (both red pre-fix).

## Decided (ADR-022's held weight question, closed with data)

With the meter alive, the tournament numbers showed the composite score's rotation
term **double-charges self-adjustment**: Splay's ~178k locality-workload splaying
rotations are real work — work already priced into its wall time — and charging
them again at ×2.0 pushed Splay back to last place in the very workloads the runner
documents it should win. The rotation term is removed from `compositeScore`
(score = time×0.5 + realized-depth×3.0); rotations remain a reported metric column.
Verified across seeds: Splay now wins the locality workloads on realized depth
(4.6–7.5 vs ~10–11), the strict balancers win uniform/sequential/delete — the
tournament finally agrees with its own workload design. ADR-022's "Held" section is
updated to record the decision.

## Also

README refreshed for the day's changes: the ADR-021 navigation API and its
concurrency guarantee, persistence hardening, battle methodology, windowed-undo
semantics, the corrected arena narrative (RB → Hybrid → Splay → Hybrid), the
2026-08-12 hardening-day summary with links to all five audits, ADR-021/022 entries
in the design history, the ecology provenance range (ADR-015→020), and the test
count (583 → 806).
