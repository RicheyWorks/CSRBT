# ADR-009: Roadmap reconciliation — auditing the "polish gaps" list against the actual codebase

**Status:** Accepted (2026-06-09 — P1/P2/P3/G0 all landed; G1/G2 held with triggers)
**Date:** 2026-06-09
**Deciders:** Richmond
**Builds on:** ADR-001–008 (all Accepted), the external review/roadmap pasted 2026-06-09
(the "bonkers" plan), `DESIGN-adaptive-engine.md`.
**Goal:** turn an enthusiastic but **stale** external critique into an honest gap list —
closing on paper what is already closed in code, fixing what is genuinely broken, and
scoping what is genuinely missing — with the action order front-loading small, *visible*
wins (the review's one piece of process advice worth adopting wholesale).

---

## 1. Context — the audit

The proposed roadmap was written against a snapshot of CSRBT that predates most of the last
ten days. Verified against the code today:

| Claim in the review | Verified status |
|---|---|
| "TreeContext still Integer-hardcoded, mid-ADR-002" | **Stale.** ADR-002 completed (steps 2–6, Accepted). `OrderedSet<K>` is the generic facade; `TreeContext` is *deliberately* the Integer adapter over it (its javadoc says exactly this, citing step 4). Re-generifying it would undo a decision, not finish one. |
| "Readers can observe mid-mutation state" | **Stale.** ADR-004 R1 (torn-read-free reads everywhere) + R2 (wait-free `READ_REPLICA`) landed and Accepted. |
| "WorkloadMonitor, MorphPolicy, telemetry don't exist / aren't wired" | **Mostly stale.** `core.control` ships `WorkloadMonitor` + `RollingWorkloadMonitor`, `WorkloadFeatures`, `MorphPolicy` (hysteresis/cooldown — the requested anti-thrash), `CostModelStrategyScorer`, `MorphController`, `MorphHistory`; the ensemble has `EnsembleController.evaluateAndMaybePromote`. What does *not* exist is a background evaluation thread — **by design**: every controller is caller-cadenced, and this codebase has twice rejected background threads (ADR-006 Option C, ADR-008 Option D). "It decides and explains why" exists; "it wakes up on its own" is a non-goal. |
| "Persistent/immutable variant (path-copying)" — Phase 3 | **Done.** ADR-005: weight-balanced path-copying engine, O(1) snapshots, wait-free reads. |
| "Weight-Balanced BB[α] strategy" — Phase 3 | **Done** (the ADR-005 engine *is* BB[α], Δ=3/Γ=2). Treap remains unbuilt and undemanded. |
| "Benchmarks showing trade-offs" | **Partially done.** In-suite benchmark rows exist (E5 adaptation, R1/R2/persistent read throughput, ADR-006/007 deltas). No JMH. |
| "`RedBlackTree.size()` does a full O(n) traversal; nodes already carry size" | **TRUE — a real bug-class gap.** `size()` walks the tree with an explicit stack while `TreeNode1` maintains the `size` augment that `OrderStatisticsOps` already trusts for select/rank. (`OrderedSet.size()` keeps its own O(1) counter, so only the engine path is affected.) |
| No `NavigableSet` adapter | **True.** The library cannot be dropped into code written against `java.util.NavigableSet`. |
| No structured events / tree export / visualizer | **True.** Logging is log4j2 lines; there is no machine-readable event stream or tree-state export. |
| Ant + console-jar JUnit is brittle for JMH/coverage/CI | **True but priced wrong** — see G1. |
| No property-based testing | **True**, though oracle-vs-`TreeSet` churn tests + mechanical invariant checkers (`validateInvariants`, `validateStructure`) already occupy most of that ground. |

---

## 2. Options and decisions, by gap

### P1 — O(1) `size()` (adopt, first)

Replace the traversal with the augment the order-statistics path already trusts:
`root.isNil() ? 0 : root.getSize()`. One line plus tests asserting size correctness under
churn/morph/undo (the augment is already exercised by `select`/`rank` parity tests, so a
divergence would be a *pre-existing* bug worth catching anyway). Risk: near zero; the
strategy family routes every structural change through the same augment propagation.

### P2 — `NavigableSet<K>` adapter (adopt)

A `core.adapter.NavigableOrderedSet<K>` view over `OrderedSet<K>`: floor/ceiling/higher/
lower map onto the existing successor/predecessor/rank machinery; subSet/headSet/tailSet as
range views over `rangeQuery`/`countInRange`; iterator off `inOrder`. **Decision point
documented:** descending views and subset *mutation* are where such adapters rot — D1 ships
read-mostly views (mutating the base set, views throwing `UnsupportedOperationException` for
subset adds) and says so loudly, rather than shipping subtly-wrong semantics.

### P3 — Structured events + tree export (adopt — the visualizer's contract, not the visualizer)

The review's most actionable insight: morph decisions are currently *narrated* (log lines),
not *consumable*. Two additive pieces, no behavior change:

- `TreeEventListener` seam on `OrderedSet`/ensemble: `insert`, `remove`, `rotate`, `morph`
  (with the `MorphController`'s reason), `repair`, `quarantine`, `promote`, `failover` —
  records, sealed-interface style, no-op default. Micrometer/JSON become trivial layers.
- `TreeExport.toJson(set)` — nodes (key/color/size/depth), strategy, meters: the file format
  a p5.js/JavaFX visualizer consumes. The visualizer itself is a separate, UI-flavored
  project that should live outside the library (demo/), built when its consumer exists.

### G1 — Gradle/JMH/CI migration (hold, with trigger)

The review prices this as pure upside; the codebase disagrees. `CLAUDE.md`, the agent
sandbox workflow, and every changelog's "ships green through `ant clean test`" are wired to
Ant; the suite runs in ~16 s with zero plugin surface. Migration is high-churn, zero-feature
work whose real payoff — coverage badges, javadoc sites, JMH harness, matrix CI — arrives
when this becomes a *published artifact with external consumers*. **Trigger:** the decision
to publish to Maven Central (or the first external contributor). Until then, a GitHub
Actions workflow that runs the existing Ant build covers CI honestly. JMH specifically can
arrive as its own module at the same trigger; the in-suite benchmark rows keep the numbers
honest meanwhile.

### G2 — Property-based testing via jqwik (hold, cheap trigger)

The oracle-churn + invariant-checker pattern already *is* property testing with a fixed
generator. Adopting jqwik adds shrinking and generator variety at the cost of a new
dependency in an Ant build (see G1). **Trigger:** first invariant bug that the seeded oracle
tests fail to catch, or the G1 migration (jqwik rides in free once Gradle exists).

### Explicitly rejected

- **Re-generifying `TreeContext`** — it is the documented Integer compatibility adapter;
  generic callers use `OrderedSet<K>`. Reopening ADR-002 to satisfy a stale review is churn.
- **Background autonomous morph loop** — caller-cadenced control is a load-bearing house
  decision (no thread lifecycle, deterministic tests); `evaluateAndMaybePromote(opsElapsed)`
  driven by the application's own cadence *is* adaptive mode here.
- **Treap / composable strategies / TreeEcology dashboard / AI-agent bridge** — undemanded;
  each gets the ADR-005-P3 treatment (a one-line "Revisit when demanded" instead of
  speculative scaffolding). The `engineMember()` seam (ADR-008) is already the extension
  point most of them would need.

---

## 3. Consequences

**Easier:** `size()` stops being a benchmark embarrassment; `NavigableSet` makes the library
adoptable by code that has never heard of it; the event/export seam turns "self-adapting"
from a log line into something a demo, a dashboard, or a hiring manager can *watch*.

**Harder:** the listener seam touches hot paths (insert/rotate) — it must be allocation-free
when no listener is registered, asserted by a benchmark row; the NavigableSet contract has
sharp edges (comparator vs natural order, view semantics) that the tests must pin.

**Visibility (the review's career framing, taken seriously):** P1–P3 are each a small,
demoable, postable win — O(1) size with a before/after row; "drop-in NavigableSet"; a JSON
tree export feeding a first animation. That ordering is deliberate.

---

## 4. Action items

1. [x] **P1** — O(1) `size()` via the size augment + churn/morph/undo size-parity tests.
   _(Done 2026-06-09 — 20k calls on n=50k in 1.41 ms; see
   CHANGELOG-2026-06-09-adr009-p1-o1-size.md.)_
2. [x] **P2** — `NavigableOrderedSet<K>` adapter + contract tests (floor/ceiling/higher/
   lower parity vs `TreeSet`, view semantics pinned, loud unsupported ops). _(Done
   2026-06-09 — see CHANGELOG-2026-06-09-adr009-p2-navigableset.md.)_
3. [x] **P3** — `TreeEventListener` seam (allocation-free when absent, benchmark-asserted) +
   `TreeExport.toJson`; demo JSON checked into `docs/` as the visualizer contract. _(Done
   2026-06-09 — see CHANGELOG-2026-06-09-adr009-p3-events-export.md and
   docs/visualizer-contract.json.)_
4. [x] **G0** — GitHub Actions workflow running `ant clean test` on JDK 17 (CI without the
   migration). _(Done 2026-06-09 — `.github/workflows/ci.yml`, JDK 17+21 matrix, report
   artifacts.)_
5. [ ] **G1** — (held) Gradle multi-module + JMH + coverage/javadoc publishing. Trigger:
   publishing/external contributors.
6. [ ] **G2** — (held) jqwik property tests. Trigger: an oracle-missed invariant bug, or G1.

---

## 5. Verification & rollback

P1 is one expression guarded by the existing order-statistics parity suite. P2/P3 are
additive (new classes, a default-empty listener list); rollback is deletion. Each ships
green through host `ant clean test` per `CLAUDE.md`, one slice per commit, changelog each —
the house discipline is unchanged.
