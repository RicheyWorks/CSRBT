# PLAN: ADR-002 step 6 — control-plane consolidation (`WorkloadMonitor` → `StrategyScorer` → `MorphPolicy` → `MorphController`)

**Status:** Proposed (plan only — no code in this step)
**Date:** 2026-06-04
**Owner:** Richmond
**Implements:** ADR-002 action item 5 ("Extract `StrategyScorer` from `TreeGenome`; add
`WorkloadMonitor` (O(1)/op rolling features); wire the controller to feed it and drive the
existing `MorphPolicy` + health-gated `setStrategy`") and `DESIGN-adaptive-engine.md` §2–§3,
§9.2, §13 (Phase 2 — control plane). Builds on the landed Phase-1 seams: `OrderedSet<K>`
(step 4), the generic engine + `StrategyHealthCheck<K>` (step 2), and the isolated
`experimental/` package.

> **Why this is a written plan.** This is the second of the two architectural gaps ADR-002
> set out to close, and unlike steps 2/4/5 it is a *refactor of working behaviour*, not an
> additive type change: the live adaptation loop already exists, inlined in
> `GenomeDrivenTreeController` and `TreeGenome` (1925 lines of self-interpreting "fitness"
> + breeding/mutation theatrics). The risk is not "will it compile" but "will the re-factored
> loop make the same — or better — decisions, without thrashing." So the plan's job is to (a)
> pin the **unit boundaries and interfaces** (the design's four units), (b) map **current code →
> target** precisely so nothing working is lost, and (c) sequence it as a **strangler**: land
> the four units additively and unit-tested, prove them, then re-point the controller behind
> the unchanged facade. The genome keeps running until the new path is proven.

---

## 1. Goal and non-goals

**Goal.** Replace the genome-driven adaptation machinery with the design's four small,
independently unit-testable control-plane units, feeding off an O(1)-per-op workload monitor
and driving the *already health-gated* `setStrategy`, with one structured observability line
per evaluation. Behaviour is equal-or-better than today's loop, with no thrashing and no
per-op tree-wide work.

```
 facade op events ─▶ WorkloadMonitor ─▶ StrategyScorer ─▶ MorphPolicy ─▶ MorphController
   (add/remove/        O(1)/op rolling     pure cost        hysteresis      build-aside +
    search hook)       feature vector      model (ranked)   + cooldown      health gate + swap
```

**In scope (new, behind the existing facade):**

- `WorkloadFeatures` — immutable feature vector (DESIGN §9.2): `readFraction`, `writeFraction`,
  `accessSkew`, `meanSearchDepth`, `rotationsPerWrite`, `size`, `growthRate`.
- `WorkloadMonitor` (interface) + `RollingWorkloadMonitor` (impl): `recordAdd/recordRemove/
  recordSearch(keyHash[,depth])` and `snapshot():WorkloadFeatures`. O(1)/op, bounded memory,
  no tree traversal. Key is taken as an `int` hash, so the monitor is key-type-agnostic.
- `StrategyId` — a lean enum of the *implemented* strategies (`RED_BLACK`, `AVL`, `SPLAY`,
  `HYBRID`), decoupled from `TreeGenome.StructureType`, with a mapping to `TreeStrategy<K>`
  via `TreeEngineRegistry`.
- `StrategyScorer` (interface) + `CostModelStrategyScorer` (impl): pure
  `WorkloadFeatures → List<Score>` (ascending `estimatedCost`, each with a `rationale`),
  extracting the genome's per-structure weighted formulas (`redBlackFitness/avlFitness/
  splayFitness/hybridFitness`) and rebasing them onto the feature vector.
- `MorphPolicy` — promote the existing `GenomeDrivenTreeController.MorphPolicy` (cooldown /
  min-improvement / stability-wins; already DESIGN §3.3-correct) to a top-level
  `core.control.MorphPolicy` with `evaluate(current, ranked, features, history): Decision`,
  plus a small `MorphHistory` value (ops-since-last-morph, recent winners).
- `MorphController<K>` — orchestrates `snapshot → score → policy.evaluate → (on MORPH)
  setStrategy`, emits the DESIGN §12 line, returns a `MorphResult`. The executor is the
  existing build-aside+validate+swap in `OrderedSet.setStrategy` (which already runs
  `StrategyHealthCheck<K>`), so the health gate is reused, not rebuilt.

**Explicitly out of scope (resist starting these here):**

- **A new `AdaptiveOrderedSet` facade.** `OrderedSet<K>` (+ the `TreeContext` Integer adapter)
  already is the facade; the monitor hook is added to it / the controller, not a new class.
- **Generifying the controller stack to `<K>`.** The live controller drives `TreeContext`
  (`Integer`); the new units are key-agnostic where natural (`WorkloadMonitor` on `int` hash,
  `StrategyScorer` on `WorkloadFeatures`) and `MorphController<K>` is generic, but rewiring
  the *whole* evolution package to `<K>` is separate, later work.
- **Deleting `TreeGenome`.** Demote its self-interpreting fitness + `mutate`/`generation`/
  breeding/lineage to `experimental/` (or behind a flag); keep it running until the new path
  is proven (strangler). `StrategyBattleRunner` is retained as the Phase-3 convergence harness.
- **New engines** (Fibonacci / vEB / persistent as live morph targets). The scorer ranks only
  the four implemented strategies; the genome's 7-type `ScoreCard` is not carried over.
- **Full lock-free concurrency.** Keep the single-writer + atomic engine-swap model; lock-free
  is a documented deferral.

---

## 2. Pivotal design decisions

### 2.1 Strangler, not big-bang — land the units additively, re-point last
Phases A–C add new, isolated, unit-tested classes that nothing depends on yet; the live
`GenomeDrivenTreeController` keeps working untouched. Only Phase D re-points the controller
to the new pipeline (or adds a `MorphController` it delegates to). If Phase D misbehaves on
the host, revert that one wiring change and the genome path is still there.

### 2.2 `WorkloadMonitor` is O(1)/op and key-agnostic
Ingest is `recordAdd/recordRemove(keyHash:int)` and `recordSearch(keyHash:int, depth:int)` —
counters only, no traversal. The current loop already approximates this (a fixed
`recentValues[50]` window + cached root height); the monitor makes it a first-class, bounded,
testable unit. **Access skew** uses a small Count-Min sketch with exponential decay (bounded
memory) reduced to a 0–1 concentration; **op mix** uses decayed add/remove/search counters;
**meanSearchDepth** and **rotationsPerWrite** are EWMAs fed by the facade (depth touched per
search; `rotationCount` delta per write); **size/growthRate** come from the facade's size and
its Δ per window. `snapshot()` returns an immutable `WorkloadFeatures` — the *only* thing the
scorer sees, which is what makes the scorer a pure function.

### 2.3 `StrategyScorer` is a transparent cost model, extracted from the genome kernel
The genome's `*Fitness()` methods are already weighted formulas — but over the genome's
internal *traits*, not the live workload, and they emit a 0–1 *fitness* (higher better) plus a
self-preference bonus and mutation noise. Extraction = take those weighting ideas, rebase them
to read `WorkloadFeatures`, drop the self-interpreting/mutating parts, and emit an
**estimated per-op cost** (lower better, ascending) with a one-line `rationale`. The mapping is
direct and matches DESIGN §3.2 / §10:
- **AVL** ← read-dominated, low skew (shallowest tree): cost ↓ as `readFraction`↑ and
  `accessSkew`↓.
- **Splay** ← high `accessSkew` + read-heavy (hot keys to root): cost ↓ sharply as skew↑.
- **Red-Black** ← balanced / write-heavy (fewer rotations/insert): cost ↓ as `writeFraction`↑
  or skew is mid; solid worst case.
- **Hybrid** ← optional middle ground; scored but weighted to lose ties (avoid churn).
Every weight is a named constant with a unit test, so each decision is explainable from the
log line. The scorer never reads the tree.

### 2.4 Reuse `MorphPolicy` and the health gate verbatim — only re-shape the seams
The existing `MorphPolicy.shouldMorph(currentScore, candidateScore, opsSinceLastMorph,
consecutiveWins)` is already the design's policy (cooldown 4000, margin 20%, 3 stability wins).
Promote it to `core.control.MorphPolicy` with the design's `evaluate(current, ranked, features,
history)` signature, internally deriving `currentScore`/`candidateScore` from `ranked` (cost →
desirability) and `consecutiveWins`/`opsSince*` from a `MorphHistory`. The **health gate is
already done**: `OrderedSet.setStrategy` builds the candidate aside, validates via
`StrategyHealthCheck<K>` (inorder==sorted, size, per-strategy invariant, select/rank spot
checks — exactly DESIGN §9.3), and publishes only on pass. `MorphController` calls it; it does
not re-implement validation. (Optionally wrap the `List<String>` failures as a
`HealthCheck.Report(ok, failures)` for the result line.)

### 2.5 `StrategyId` decouples the loop from `TreeGenome.StructureType`
`StructureType` lives in `TreeGenome` and names 7 types (3 with no engine). Introduce a clean
`core.control.StrategyId { RED_BLACK, AVL, SPLAY, HYBRID }` mapped to `TreeStrategy<K>` through
`TreeEngineRegistry`, so the control plane has no dependency on the genome. A thin
`StrategyId ↔ StructureType` adapter bridges the legacy controller during the strangler period.

### 2.6 The facade feeds the monitor; the controller becomes the cadence runner
`TreeContext`/`OrderedSet` gain an optional `WorkloadMonitor` hook fired from `add`/`remove`/
`contains` (the controller already wraps these via `recordAccess`). `MorphController.
evaluateAndMaybeMorph()` runs on the existing cadence (every `EVAL_INTERVAL` ops) and replaces
the body of `GenomeDrivenTreeController.evaluate()`: `snapshot → score → policy → maybe
setStrategy → emit line`. `performanceMemory` (per-strategy realized avg-depth / rotation-rate)
is retained as an optional *post-morph feedback* term, but is no longer the primary signal.

---

## 3. Current code → target (migration map, concrete)

| Today (in `core.evolution`) | Becomes | Disposition |
|---|---|---|
| `GenomeDrivenTreeController.computeStress/Entropy/Fragmentation` + `recentValues[50]` | `RollingWorkloadMonitor` → `WorkloadFeatures` | reimplement as O(1) counters/sketch; entropy≈accessSkew, height-ratio≈meanSearchDepth |
| `TreeGenome.fitnessFor/scoreCard/recommendedStructure` + `*Fitness()` | `CostModelStrategyScorer` | extract weighting; rebase onto features; emit cost+rationale |
| `GenomeDrivenTreeController.MorphPolicy` (nested) | `core.control.MorphPolicy` (top-level) | promote; same gates; new `evaluate(...)` signature + `MorphHistory` |
| `GenomeDrivenTreeController.evaluate/applyStructure` | `MorphController<K>.evaluateAndMaybeMorph` | split decide/execute; executor = `setStrategy` |
| `OrderedSet.setStrategy` + `StrategyHealthCheck<K>` | health gate (DESIGN §9.3) | **reused as-is** |
| `TreeGenome.mutate/generation/breeding/lineage`, `ScoreCard` 7-type | (demoted) | move to `experimental/` or drop from live path |
| `GenomeDrivenTreeController.emitMorphEval` | `MorphController` observability line | keep the `event=morph_eval` schema (DESIGN §12) |
| `StrategyBattleRunner` | convergence harness | retained; asserts G3/G4 |
| `TreeEcology` (experimental) | (fold any useful metric into the monitor) | otherwise stays experimental |

---

## 4. Execution order (each phase ships green; A–C are additive)

### Phase A — `WorkloadFeatures` + `WorkloadMonitor`
1. `core.control.WorkloadFeatures` (immutable record, JDK 17) and `WorkloadMonitor` interface
   + `RollingWorkloadMonitor` (decayed op-mix counters, Count-Min skew sketch, depth/rotation
   EWMAs, size/growth). 2. `WorkloadMonitorTest`: synthetic op streams → asserted features
   (uniform→skew≈0; single hot key→skew≈1; all-search→readFraction≈1; growth tracking).
   **Gate:** additive; nothing depends on it.

### Phase B — `StrategyId` + `StrategyScorer`
3. `core.control.StrategyId` (+ registry mapping). 4. `StrategyScorer` interface +
   `CostModelStrategyScorer` (named weight constants). 5. `StrategyScorerTest`: the DESIGN §10
   worked trace (skew 0.71 + read 0.94 → Splay first) and the boundary cases (low-skew
   read-heavy → AVL; write-heavy/balanced → RB; ties → Hybrid last). **Gate:** additive.

### Phase C — promote `MorphPolicy` + `MorphHistory`
6. `core.control.MorphPolicy implements evaluate(...)` reusing the existing gates;
   `MorphHistory` value object. Keep `GenomeDrivenTreeController.MorphPolicy` as a thin
   deprecated delegate (or migrate `MorphPolicyTest`). **Gate:** existing `MorphPolicyTest`
   semantics preserved.

### Phase D — `MorphController` + wire the facade (the behaviour-sensitive phase)
7. `core.control.MorphController<K>` (orchestrate + observability line + `MorphResult`).
8. Add the `WorkloadMonitor` hook to `TreeContext`/`OrderedSet` op methods. 9. Re-point
   `GenomeDrivenTreeController.evaluate()` to delegate to the `MorphController` pipeline; demote
   the genome's self-interpreting fitness/mutate to `experimental/` (or a flag). **Gate:** the
   existing controller tests (`TreeGenomeTest`, `MorphPolicyTest`, `HealthGatedMorphTest`) stay
   green; the loop still emits one `event=morph_eval` line per evaluation.

### Phase E — convergence tests + docs
10. Convergence/`StrategyBattleRunner` tests for G3/G4 (skewed→Splay within K ops, ≤1 morph;
    steady→0 morphs). 11. Flip ADR-002 item 5 → done; `CHANGELOG-2026-…-control-plane.md`;
    README "Evolution" paragraph. Item 6 (C5 clean-rebuild session) is the last item.

---

## 5. Verification, rollback, acceptance goals

- **Per-phase gate:** `ant clean test` on the host (JDK 17). A–C are additive and unit-tested
  in isolation (hand-built feature vectors / op streams), so they can't regress the live loop.
  Phase D is the only behaviour change; the controller/morph tests are its guard.
- **Behaviour-equivalence argument:** at the same inputs the new pipeline must make the same or
  a better decision than the genome loop and never thrash — proven by (a) the scorer worked-trace
  test matching DESIGN §10, (b) `MorphPolicy` reuse (identical gates), and (c) convergence tests.
- **Rollback:** Phases A–C are independently revertible; Phase D is one wiring change — revert it
  and the genome loop resumes unchanged.
- **Acceptance goals (DESIGN §15):** G3 (hot-key → Splay) = scorer skew weighting + convergence
  test; G4 (responsiveness + stability) = `MorphPolicy` cooldown/hysteresis + regime-change test
  (≤1 morph; steady→0); G5 (bounded cost) = O(1) monitor + a guard test asserting no per-op
  tree scan; G6 (safe reconfig) = the reused health gate (fault-injected invalid strategy is
  rejected, incumbent retained); G9 (observability) = the `event=morph_eval` line.

---

## 6. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Scorer weights mis-tuned → wrong/oscillating choices | Medium | named constants + unit tests on worked traces; `MorphPolicy` margin/stability absorbs noise; convergence harness |
| Re-point (Phase D) changes live behaviour subtly | Medium | strangler: genome path retained; controller/morph tests; revert one change to roll back |
| Skew sketch cost/accuracy | Low | Count-Min is O(1) bounded; tested against synthetic hot-key streams |
| `StrategyId`/`StructureType` duality causes drift | Low–Med | one adapter, single source of truth via `TreeEngineRegistry`; delete `StructureType` from live path only after Phase D |
| `WorkloadFeatures` record requires JDK 16+ | Low | build targets JDK 17 (records fine); a final-class fallback exists if needed |
| Demoting genome breaks `TreeGenomeTest`/`StrategyBattleRunner` | Low–Med | keep genome compiling in `experimental/`; adapt only the tests that assert the *live* path |
| Cannot compile/run in this sandbox (JRE only) | High (env) | plan-only this step; implementation lands on the host with `ant clean test` per phase |

---

## 7. First-edit checklist (when implementation is greenlit)
1. **Phase A:** `WorkloadFeatures` + `WorkloadMonitor`/`RollingWorkloadMonitor` + test.
2. **Phase B:** `StrategyId` + `StrategyScorer`/`CostModelStrategyScorer` + worked-trace test.
3. **Phase C:** promote `MorphPolicy` (+ `MorphHistory`); preserve `MorphPolicyTest`.
4. **Phase D:** `MorphController<K>`; monitor hook in the facade; re-point the controller;
   demote the genome's self-interpreting fitness to `experimental/`.
5. **Phase E:** G3/G4 convergence tests; ADR-002 item 5 → done; changelog; README. Then item 6
   (the C5 clean-rebuild pass) closes ADR-002.
