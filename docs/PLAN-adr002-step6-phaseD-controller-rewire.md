# PLAN: ADR-002 step 6 Phase D — wire the control plane into the live loop

**Status:** Proposed (plan only — no code in this step)
**Date:** 2026-06-05
**Owner:** Richmond
**Implements:** the behaviour-sensitive remainder of ADR-002 action item 5, sequenced as
Phase D of [`PLAN-adr002-step6-control-plane.md`](PLAN-adr002-step6-control-plane.md).
**Builds on (landed, Phases A–C):** `core.control.WorkloadMonitor` /
`RollingWorkloadMonitor` + `WorkloadFeatures` (A); `StrategyId` + `StrategyScorer` /
`CostModelStrategyScorer` (B); `MorphPolicy` + `MorphHistory` (C). All three are
additive, unit-tested, and **not yet referenced** by the live loop.

> **Why this gets its own plan.** Phases A–C were additive type/logic that could not
> regress the running engine — they landed green by construction. Phase D is different:
> it is the one phase that **changes the behaviour of a working system**. It re-points
> `GenomeDrivenTreeController.evaluate()` off the genome's self-interpreting fitness and
> onto the new pipeline, and it adds a per-op monitor feed. The risk is not "will it
> compile" but "will the re-pointed loop make the same — or better — decisions, without
> thrashing, and never corrupt live data." This plan exists to (a) pin the
> `MorphController` contract, (b) map **current code → target** precisely, and (c)
> sequence the change as a **flag-gated strangler** so that at every sub-step the build
> is green and rollback is a single switch.

---

## 1. Goal and non-goals

**Goal.** Make adaptation run end-to-end on the four control-plane units —
`WorkloadMonitor → StrategyScorer → MorphPolicy → MorphController` — feeding off a real
O(1)-per-op event stream and driving the *already health-gated* `setStrategy`, emitting
exactly one `event=morph_eval` line per evaluation, with behaviour equal-or-better than
today's genome loop and no new thrash or per-op tree-wide work. The genome path stays
compiling and revertible until the new path is proven.

**In scope.**

- `core.control.MorphController<K>` — orchestrates one evaluation
  (`snapshot → score → policy.evaluate → on MORPH: setStrategy`), emits the DESIGN §12
  line, returns a `MorphResult`. The executor is the existing build-aside + validate +
  swap in `OrderedSet.setStrategy` (which already runs `StrategyHealthCheck<K>`), so the
  health gate is **reused, not rebuilt**.
- The **monitor feed**: op events (`recordAdd/recordRemove(keyHash, rotations)`,
  `recordSearch(keyHash, depth)`) wired from the live op path.
- The `StrategyId ↔ TreeGenome.StructureType` **bridge** deferred from Phase B (needed to
  read the incumbent and to keep the legacy controller interoperating during the cutover).
- **Re-point** `GenomeDrivenTreeController.evaluate()` to delegate to the `MorphController`
  pipeline, behind a flag; **demote** the genome's self-interpreting fitness / `mutate` /
  breeding from the live decision path.

**Non-goals (resist here).**

- **Generifying the controller stack to `<K>`.** The live controller drives `TreeContext`
  (`Integer`); `MorphController<K>` is generic, but rewiring the whole evolution package to
  `<K>` is later work.
- **Deleting `TreeGenome`.** Keep it compiling (and `TreeGenomeTest` / `StrategyBattleRunner`
  green); only stop the controller from *deciding* with it.
- **New engines** (Fibonacci / vEB / persistent as morph targets). The scorer ranks only the
  four implemented strategies.
- **Full facade instrumentation of all client traffic.** See decision 4.1 — Phase D feeds the
  monitor from the controller's existing op wrappers (parity with today); a facade-level hook
  that observes *all* `OrderedSet`/`TreeContext` traffic is a documented fast-follow.
- **Lock-free concurrency** and the **amortization gate** (size-based) — documented deferrals.

---

## 2. Current live loop → target (concrete map)

Today (`core.evolution.GenomeDrivenTreeController`):

```
add(v)      → context.add(v);     recordAccess(v); afterOperation()
remove(v)   → context.remove(v);                   afterOperation()
contains(v) → context.contains(v); recordAccess(v)
afterOperation(): if (++opCount % EVAL_INTERVAL == 0) evaluate()   // EVAL_INTERVAL = 10
evaluate():
   recordCurrentPerformance()
   stress/entropy/fragmentation = compute*()              // ad-hoc over recentValues[50]
   if (genome.shouldMorph(...)) {
       chosen = chooseStrategyWithMemory()                // genome.fitnessFor blended w/ memory
       if (chosen != active && morphPolicy.shouldMorph(currentScore, candScore, opsSince, streak))
           applyStructure(chosen)                         // context.setStrategy(...) — health-gated
   }
   emitMorphEval(decision, from, to)                      // event=morph_eval line
   rotationsAtLastWindow = context.getRotationCount()
```

Target (Phase D, flag ON):

```
add(v)      → context.add(v);     monitorFeed.add(hash(v),  rotDelta()); afterOperation()
remove(v)   → context.remove(v);  monitorFeed.remove(hash(v), rotDelta()); afterOperation()
contains(v) → context.contains(v);monitorFeed.search(hash(v), depthProxy()); (record access)
evaluate():                                               // body replaced by:
   MorphResult r = morphController.evaluateAndMaybeMorph()
   // morphController internally:
   //   f       = monitor.snapshot()
   //   ranked  = scorer.score(f)
   //   current = bridge(active strategy)                 // StrategyId
   //   decision= policy.evaluate(current, ranked, f, history)
   //   if MORPH: ok = orderedSet.setStrategy(best.newStrategy());  // health gate
   //             history = ok ? history.afterMorph() : history.observed(best, EVAL_INTERVAL)
   //   else:     history = history.observed(ranked.get(0).strategy(), EVAL_INTERVAL)
   //   emit event=morph_eval  (features + scores + decision + health/buildNanos)
```

| Today | Becomes | Disposition |
|---|---|---|
| `compute{Stress,Entropy,Fragmentation}` + `recentValues[50]` | `RollingWorkloadMonitor` feed + `snapshot()` | replaced; monitor is the single workload source |
| `genome.shouldMorph` + `chooseStrategyWithMemory` + `fitnessFor` | `StrategyScorer.score` + `MorphPolicy.evaluate` | replaced; decision = pure scorer + policy |
| nested `GenomeDrivenTreeController.MorphPolicy` | `core.control.MorphPolicy` | re-point to the promoted unit; retire/deprecate the nested duplicate |
| `applyStructure` → `context.setStrategy` | `MorphController` executor → `setStrategy` | **reused as-is** (health gate unchanged) |
| `emitMorphEval` | `MorphController` `event=morph_eval` line | keep the schema (DESIGN §12) |
| `genome.mutate` / generation / breeding / `ScoreCard` | demoted | dropped from the live path; genome keeps compiling |
| `performanceMemory` (per-strategy realized depth/rot) | optional post-morph feedback | retained for the line/diagnostics, **not** the primary signal |

---

## 3. The `MorphController<K>` contract

```java
public final class MorphController<K> {
    MorphController(OrderedSet<K> set,            // the facade (executor = setStrategy)
                   WorkloadMonitor monitor,       // snapshot source
                   StrategyScorer scorer,         // pure cost model
                   MorphPolicy policy);           // anti-thrash gate

    MorphResult evaluateAndMaybeMorph(StrategyId current, int opsElapsed); // run on cadence

    record MorphResult(boolean morphed, StrategyId from, StrategyId to,
                       boolean healthPassed, long buildNanos, String reason) { }
}
```

- `current` is the incumbent `StrategyId` (from the bridge, §4.3). `opsElapsed` advances the
  `MorphHistory` cooldown clock (= `EVAL_INTERVAL` per eval).
- On `Decision.MORPH`, the executor is `set.setStrategy(best.newStrategy())`, whose boolean
  return *is* the health-gate verdict (it builds aside, validates via `StrategyHealthCheck<K>`,
  and publishes only on pass). The controller never re-implements validation.
- The controller owns the `MorphHistory` (advances with `observed`/`afterMorph`).
- It emits one structured line per call — HOLD or MORPH — carrying the `WorkloadFeatures`,
  the ranked scores, the decision, and (on morph) `healthPassed` + `buildNanos`.

---

## 4. Pivotal design decisions

### 4.1 Monitor feed: controller-fed now, facade-hook as a fast-follow
The live loop is driven *through the controller's* `add/remove/contains`; today's genome
already only "sees" that traffic (via `recordAccess`). To preserve behaviour parity and keep
the live `OrderedSet`/`TreeContext` op methods untouched during the cutover, **Phase D feeds
the monitor from the controller's existing op wrappers.** A facade-level hook (firing the
monitor from `OrderedSet.add/remove/contains` so *all* client traffic is observed — DESIGN
§2/§9.1) is the correct long-term home and is scoped as the immediate follow-on; it is held
out of D to keep the behaviour-sensitive change minimal. **Decision needed — confirm.**

### 4.2 Depth and rotation signals are cheap and not yet decision-bearing
`CostModelStrategyScorer` deliberately ignores `meanSearchDepth` and `rotationsPerWrite`
(they describe the incumbent's realized shape, reserved for post-morph feedback). That lowers
the bar for the feed:
- **rotationsPerWrite** — `context.getRotationCount()` delta around each write (the controller
  already tracks `rotationsAtLastWindow`); O(1).
- **meanSearchDepth** — feed the **cached root height** as a proxy per search (zero engine
  change), since depth does not affect the decision today. An instrumented "last search depth"
  on the engine (record path length during `contains`, O(1), no extra traversal) is the precise
  version and a clean later refinement. **Decision needed — proxy now vs instrument now.**

### 4.3 `StrategyId ↔ StructureType` bridge (the Phase-B deferral)
Introduce the thin adapter the strangler needs: `StrategyId.fromStructureType(StructureType)`
and `toStructureType()` for the four implemented types (RB/AVL/Splay/Hybrid), throwing for the
three non-strategy types (Fibonacci/vEB/Persistent). The controller reads its incumbent
`activeStrategyType` (a `StructureType`) and converts to `StrategyId` for `policy.evaluate`;
on morph it converts back to set `activeStrategyType`. This is the *only* new coupling from
`core.control` to `core.evolution`; keep it in one place so there is a single source of truth.

### 4.4 Flag-gated cutover (one-switch rollback)
Add a toggle on the controller (constructor arg / setter, e.g. `useControlPlane`). Default
**OFF** through D4 (genome path runs, monitor feeds in parallel but does not decide); flipped
**ON** in D5. If the re-pointed loop misbehaves on the host, flip the flag back — the genome
path is byte-unchanged behind it. This is the literal "revert one wiring change" rollback.

### 4.5 Genome demotion without breaking its tests
"Demote" means the controller stops *deciding* with the genome — not deleting it.
`TreeGenome` and `StrategyBattleRunner` keep compiling and their tests stay green; the
genome's `shouldMorph` / `fitnessFor` / `mutate` simply leave the live decision path (mark the
decision-facing methods `@Deprecated` pointing at `core.control`). Moving the theatrics
(`TreeEcology` / `TreeAgent`) is already done (they are in `experimental/`); no further move is
required for D. **Decision needed — deprecate-in-place (recommended) vs relocate.**

### 4.6 Cadence and cooldown stay as-is
Keep `EVAL_INTERVAL = 10` and `MorphPolicy.defaults()` (cooldown 4000 ops, 20% margin, 3
wins). `MorphHistory.opsSinceLastMorph` is in **ops**, advanced by `EVAL_INTERVAL` per eval, so
the 4000-op cooldown reaches readiness after ~400 evals — identical pacing to today. The
monitor's decay window (`W`, default 4096) is independent of the eval cadence.

---

## 5. Execution order (each sub-step compiles and ships green on the host)

### D1 — `MorphController<K>` + `MorphResult` (additive)
Build the orchestrator + observability line against the real `OrderedSet` executor.
`MorphControllerTest`: with a hand-fed monitor/scorer/policy, assert HOLD vs MORPH, the
`MorphResult` fields, that a health-failing strategy keeps the incumbent (reuse the broken-
strategy fixture from `HealthGatedMorphTest`), and that exactly one line is emitted.
**Gate:** additive; nothing live depends on it yet.

### D2 — `StrategyId ↔ StructureType` bridge (additive)
Add the adapter (§4.3) + a tiny round-trip test (each implemented type maps both ways; the
three non-strategy types throw). **Gate:** additive.

### D3 — Monitor feed, decision-neutral
Wire `monitor.recordAdd/recordRemove/recordSearch` into the controller's `add/remove/contains`
(rotation delta + depth proxy), **without** changing who decides (genome still drives). Add a
feed test asserting the monitor's `snapshot()` reflects a synthetic op stream routed through
the controller. **Gate:** existing controller/genome tests unchanged and green; behaviour
identical (the feed is observation-only).

### D4 — Re-point `evaluate()` behind a flag (default OFF)
Replace the body of `evaluate()` with: if `useControlPlane`, run the `MorphController`
pipeline; else the legacy genome body. Default OFF. Add a flag-ON controller test that drives a
skewed stream and asserts a Splay morph + one `event=morph_eval` line. **Gate:** with the flag
OFF the entire existing suite is unchanged/green; the new path is exercised only under the flag.

### D5 — Flip default ON; demote genome; convergence tests
Default the flag ON; deprecate the genome's decision methods and the nested `MorphPolicy`
(now delegating to `core.control.MorphPolicy`). Add the convergence harness. **Gate:** full
suite green including convergence; the loop emits one line per eval; `TreeGenomeTest` /
`StrategyBattleRunner` still green (genome compiles, just not deciding).

### Phase E (separate, after D)
Flip ADR-002 item 5 → done; `CHANGELOG-2026-…-control-plane.md`; rewrite the README
"Evolution/Control plane" paragraph to past tense; then item 6 (the C5 clean-rebuild pass)
closes ADR-002.

---

## 6. Behaviour-equivalence argument

At the same inputs the re-pointed loop must decide the same or better, and never thrash:

- **Same/better choice** — the scorer's worked-trace test reproduces DESIGN §10 (skew 0.71 +
  read 0.94 → Splay first), and the regime tests pin AVL/RB/Splay winners (already green in
  Phase B). The decision is now a pure function of `WorkloadFeatures`, not blended genome state.
- **No thrash** — `MorphPolicy` is the same gate with the same defaults (4000 / 0.20 / 3);
  Phase C re-pinned `shouldMorph` parity and added `evaluate` tests. Hysteresis comes from
  `MorphHistory` (cooldown + win streak).
- **Safety unchanged** — the executor is the untouched `OrderedSet.setStrategy` +
  `StrategyHealthCheck`; a failed candidate is dropped and the incumbent retained.

---

## 7. Test strategy

**Existing guards (must stay green):** `TreeGenomeTest` (genome still compiles/scores),
`MorphPolicyTest` (legacy nested gate), `MorphPolicyControlTest` (promoted gate),
`StrategyScorerTest`, `WorkloadMonitorTest`, `HealthGatedMorphTest` (setStrategy validation +
rollback), `OrderedSetTest`, `StrategyInvariantTest`.

**New (Phase D), mapped to DESIGN §15 goals:**
- `MorphControllerTest` — orchestration + `MorphResult` + health-fail-keeps-incumbent (**G6**)
  + one line per eval (**G9**).
- monitor-feed test (D3) — the controller's op stream reaches the monitor.
- flag test (D4) — flag-ON path morphs; flag-OFF path is the legacy loop.
- convergence harness (D5): **G3** skewed workload converges to Splay within K ops with ≤1
  morph; **G4** a regime change reaches the expected strategy in ≤1 morph and a steady workload
  triggers 0 morphs; **G5** a guard asserting no per-op tree scan/snapshot on the hot path.
  (Convergence tests may use enough ops to clear the 4000-op cooldown, or an eager
  `MorphPolicy(small cooldown, …)` to keep runtime bounded.)

---

## 8. Verification and rollback

- **Sandbox limitation.** The dev sandbox is JRE-only and cannot run the controller/morph
  behaviour; every sub-step is verified by `ant clean test` **on the host**. Decision logic and
  any numeric thresholds are pre-checked with the Python mirror harness used for Phases A–B
  before fixing test expectations.
- **Per sub-step:** D1–D2 additive; D3 decision-neutral (observation only); D4 flag-gated with
  default OFF (no behaviour change); D5 is the only default-behaviour flip.
- **Rollback:** flip `useControlPlane` OFF → the genome loop resumes, byte-unchanged. D1–D3 are
  independently revertible; the genome path is retained until D5 is proven on the host.

---

## 9. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Re-point changes live behaviour subtly | Medium | flag-gated cutover; convergence + controller tests; revert = one flag |
| Controller-fed monitor misses direct-facade traffic | Medium | parity with today's genome (also controller-fed); facade-hook scoped as fast-follow (§4.1) |
| Genome demotion breaks `TreeGenomeTest` / `StrategyBattleRunner` | Low–Med | keep genome compiling; only remove it from the decision path; adapt only tests asserting the live decision |
| Depth/rotation feed adds hot-path cost | Low | O(1) (root-height read + rotation-count delta); depth not decision-bearing yet |
| Cooldown(4000) × cadence(10) makes morphs rare in tests | Low | convergence tests push enough ops or use an eager policy |
| `StrategyId`/`StructureType` drift | Low | one bridge, single source of truth; delete `StructureType` from the live path only after D5 |
| Cannot compile/run in sandbox (JRE only) | High (env) | plan-only; host `ant clean test` per sub-step; Python mirror for decision thresholds |

---

## 10. Open decisions (resolve before coding)

1. **Monitor feed location** — controller-fed (parity, minimal change) **[recommended for D]**
   vs facade-hook now (observes all traffic, DESIGN-correct, edits live `OrderedSet`).
2. **Depth signal** — root-height proxy **[recommended]** vs instrument engine search depth now.
3. **Genome demotion** — deprecate decision methods in place **[recommended]** vs relocate.
4. **Cutover** — flag, default OFF then flip in D5 **[recommended]** vs hard cutover.
5. **performanceMemory** — retain for the line/diagnostics, not the decision **[recommended]**
   vs drop entirely.

---

## 11. First-edit checklist (when greenlit)
1. **D1:** `core.control.MorphController<K>` + `MorphResult` + `MorphControllerTest`.
2. **D2:** `StrategyId ↔ StructureType` bridge + round-trip test.
3. **D3:** monitor feed in the controller's `add/remove/contains` (rotation delta + depth
   proxy) + decision-neutral feed test.
4. **D4:** re-point `evaluate()` behind `useControlPlane` (default OFF) + flag-ON test.
5. **D5:** flip default ON; deprecate genome decision methods + nested `MorphPolicy`
   (delegate to `core.control`); convergence tests (G3/G4 + G5/G6/G9). Then Phase E
   (ADR item 5 → done, changelog, README) and item 6 (C5 clean rebuild) to close ADR-002.

---

## 12. Review addendum — findings & resolved decisions (2026-06-05)

A source review cross-checked this plan against the live code
(`GenomeDrivenTreeController`, `OrderedSet`, `TreeContext`, the four `core.control`
units, `StrategyId`). The §3 contract and the §4.6 cadence math hold, and the control
units' public APIs match the contract almost exactly (the one nit is in 12.3 F7). Two
design assumptions need correcting before D1; the §10 open decisions are resolved below.

### 12.1 Blocking corrections (resolve before D1)

**B1 — Execute through a morph-target seam, not a captured `OrderedSet`.** The live
controller holds a `TreeContext`, whose inner `OrderedSet<Integer>` is private (no
getter) and is **reassigned** by `loadSnapshot` (`TreeContext.java:248`). A long-lived
`MorphController` (it owns the `MorphHistory`, so it persists across evals) that captured
the `OrderedSet` reference would morph a *stale* set after any snapshot load. **Decision:**
`MorphController<K>` executes through a narrow seam —
`interface StrategyMorphTarget<K> { boolean setStrategy(TreeStrategy<K> s); TreeStrategy<K> getStrategy(); }`
— implemented directly by `OrderedSet<K>` and by `TreeContext` (for `Integer`). The live
controller passes its `TreeContext`, so every morph routes to the *current* set via the
existing health-gated `setStrategy`. This supersedes the `OrderedSet<K> set` constructor
arg in §3 (the executor and health gate are otherwise unchanged).

**B2 — Reads must drive the eval cadence.** `contains()` does not call `afterOperation()`
(`GenomeDrivenTreeController.java:149-153`); only writes tick the eval clock. As written,
a read-heavy high-skew workload never re-evaluates, so the marquee "skewed reads → Splay"
convergence (goals G3/G4) cannot trigger — the §2 target still feeds the monitor from
`contains` but does not schedule an eval. **Decision:** in D3/D4, `contains()` advances the
eval cadence (counts toward `EVAL_INTERVAL`) in addition to feeding the monitor, and
`MorphHistory` advances by the ops actually counted per eval (writes **and** reads),
preserving the §4.6 cooldown pacing in op terms. The convergence harness (D5) must
therefore exercise reads against this cadence.

### 12.2 Resolved open decisions (§10)

1. **Monitor feed location** → controller-fed, via the B1 seam (parity; the facade hook
   stays the documented fast-follow).
2. **Depth signal** → **feed constant `0` for both `meanSearchDepth` and
   `rotationsPerWrite` in D3.** Both are decision-irrelevant in `CostModelStrategyScorer`
   today; feeding `0` keeps the hot path provably O(1) and removes any dependence on
   whether `TreeNode1.getHeight()` is cached. Instrument for real only when a future scorer
   term consumes them. (This also disposes of finding F4.)
3. **Genome demotion** → deprecate the decision methods in place (no relocation).
4. **Cutover** → flag, default OFF through D4, flip in D5.
5. **performanceMemory** → retain for the log line / diagnostics, not the decision.

### 12.3 Non-blocking findings (fold into the sub-steps)

- **F3 — Phase D fixes a latent drift bug; state it as intended.** Today `applyStructure`
  ignores `setStrategy`'s boolean (`:261`) and updates `activeStrategyType` / `morphCount`
  even on a health-*rejected* morph (`:264-267`). §3 correctly gates the update on the
  verdict — a deliberate "better, not same" divergence on the health-fail path. The §6
  equivalence argument should name it so a test pinning today's behaviour does not read it
  as a regression.
- **F4 — `getRotationCount()` is vestigial** (never incremented by the strategies;
  `TreeContext.java:72-73, 286`), so a rotation-delta feed is always `0`. Disposed of by
  decision 12.2.2.
- **F6 — feed effective mutations only.** Drive `recordAdd` / `recordRemove` off the
  effective-insert/remove boolean (which the current `void add(int)/remove(int)` path
  discards) so the monitor's `size` / `growthRate` do not drift on duplicate adds or absent
  removes (`WorkloadMonitor` contract, "Effective mutations").
- **F7 — `MorphResult` semantics.** `setStrategy` returns `false` for *both* a health-fail
  and a same-class/null no-op (`OrderedSet.java:231-242`); do not report a no-op as
  `healthPassed=false`. `buildNanos` is a wall-clock measurement *around* `setStrategy`
  (the executor reports no build time). The §2/§3 pseudocode `best.newStrategy()` is
  precisely `ranked.get(0).strategy().newStrategy()`.

### 12.4 Status

Plan remains **Proposed**. With B1, B2 and decision 12.2.2 incorporated, D1 is ready to
start. All findings are source-read only — **unverified by execution** (the dev sandbox is
JRE-only); host `ant clean test` + the Python decision mirror still govern every sub-step.
