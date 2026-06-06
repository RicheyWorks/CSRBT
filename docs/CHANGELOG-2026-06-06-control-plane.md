# CHANGELOG 2026-06-06 -- ADR-002 step 6 Phase D: the control plane becomes the default

Completes ADR-002 action item 5. The four control-plane units scoped in
`PLAN-adr002-step6-control-plane.md` and built additively in Phases A–C (`WorkloadMonitor`,
`StrategyScorer`, `MorphPolicy`/`MorphHistory`) are now **wired into the live loop** and made
the controller's default decision path. `GenomeDrivenTreeController.evaluate()` runs the
pipeline `WorkloadMonitor → StrategyScorer → MorphPolicy → MorphController`, driving the
existing health-gated `setStrategy`; the genome's self-interpreting fitness loop is
`@Deprecated` but retained behind a one-switch flag for rollback.

This was sequenced as a flag-gated strangler (plan
`PLAN-adr002-step6-phaseD-controller-rewire.md`) so every sub-step shipped green: D1–D2 were
additive, D3 was decision-neutral, D4 added the re-point behind a default-OFF flag, and D5
flipped the default and demoted the genome.

## What changed

- **D1 — `core.control.MorphController<K>` + `StrategyMorphTarget<K>` seam.** The orchestrator
  runs one evaluation (`monitor.snapshot() → scorer.score → policy.evaluate`; on `MORPH`,
  `target.setStrategy(best.newStrategy())`), owns the `MorphHistory`, and returns a
  `MorphResult(morphed, from, to, healthPassed, buildNanos, reason)`. It executes through a
  narrow `StrategyMorphTarget<K>` seam (`setStrategy` / `getStrategy`) implemented by
  `OrderedSet<K>` and `TreeContext` — never a captured inner set — so a morph always routes to
  the *current* engine even after a snapshot load reassigns it (plan decision B1). The health
  gate is the unchanged build-aside + `StrategyHealthCheck` + publish path; a rejected or
  no-op candidate keeps the incumbent and counts as a hold.

- **D2 — `StrategyId ↔ StructureType` bridge** (`core.evolution.StrategyIdBridge`). The thin
  adapter the strangler needs to read the incumbent and interoperate during cutover: each of
  the four implemented types round-trips both ways; the three non-strategy types
  (Fibonacci / vEB / Persistent) throw.

- **D3 — monitor feed, observation-only.** The controller's `add` / `remove` / `contains`
  mirror each op into the `RollingWorkloadMonitor` (`recordAdd` / `recordRemove` /
  `recordSearch`) on **effective mutations only**, feeding constant `0` for depth and rotations
  so the hot path stays provably O(1) with no tree scan (plan decision 12.2.2). The genome
  still decided at this step.

- **D4 — re-point `evaluate()` behind `useControlPlane`.** When the flag is on, `evaluate()`
  delegates to the `MorphController` pipeline; otherwise the legacy genome body runs. Reads
  now advance the eval cadence under the flag (so a read-heavy skewed workload re-evaluates —
  plan decision B2), and `MorphHistory` advances by the ops actually counted per eval. Shipped
  **default OFF**.

- **D5 — flip the default ON; demote the genome.** `useControlPlane` now defaults to **true**.
  The genome's decision methods (`TreeGenome.shouldMorph`, `computeMorphPressure`,
  `fitnessFor`) and the controller's nested `MorphPolicy` (+ `get/setMorphPolicy`) are
  `@Deprecated`, pointing at `core.control`; they still compile and run behind the flag, so
  `TreeGenome` / `TreeGenomeTest` / `StrategyBattleRunner` stay green. A test seam — a
  `GenomeDrivenTreeController(TreeContext, TreeGenome, core.control.MorphPolicy)` constructor —
  lets tests inject an eager policy for bounded-runtime convergence.

## Behaviour

- **One auditable line per evaluation.** Each eval emits a single `event=morph_eval` line
  carrying the `WorkloadFeatures`, the ranked scores, the decision, and (on morph)
  `healthPassed` + `buildNanos`.
- **Decision = pure function of the workload.** The choice is `StrategyScorer` (a transparent
  cost model over read/write mix and hot-key skew) gated by `MorphPolicy` (cooldown /
  stability / minimum-improvement) — not blended genome state. Defaults are unchanged
  (`EVAL_INTERVAL = 10`, policy `4000 / 0.20 / 3`).
- **Intended divergence on the health-fail path.** Unlike the old `applyStructure` (which
  updated `activeStrategyType` / `morphCount` even when `setStrategy` rejected the candidate),
  the new path gates those updates on the boolean verdict — "better, not same."
- **Rollback is one switch.** `setUseControlPlane(false)` restores the byte-unchanged genome
  loop.

## Tests

- `MorphControllerTest` (D1) — orchestration, `MorphResult`, health-fail-keeps-incumbent (G6),
  exactly one `event=morph_eval` line per eval (G9). Its log-capture was hardened to
  `Configurator.setLevel` so it stays reliable now that the control-plane loggers are exercised
  elsewhere in the suite.
- `StrategyIdBridgeTest` (D2), `ControllerMonitorFeedTest` (D3).
- `ControllerControlPlaneFlagTest` (D4/D5) — control plane ON by default; reads drive the
  cadence; a skewed read stream morphs RB→Splay; the legacy path (flag off) does not.
- `ControllerConvergenceTest` (D5) — G3 skewed reads converge to Splay in ≤1 morph; G4 a steady
  write-heavy workload triggers 0 morphs and a regime change is followed back to RB; G5 the hot
  path feeds constant-0 depth/rotations (no per-op tree scan).

## Follow-ups (out of scope here)

- A facade-level monitor hook firing from `OrderedSet`/`TreeContext` so *all* client traffic is
  observed (D feeds from the controller's op wrappers — parity with the old genome).
- Real depth / rotation instrumentation once a scorer term consumes them.
- Generifying the controller stack to `<K>` (the live controller still drives `Integer`).
- ADR-002 item 6: the C5 clean-rebuild pass.
