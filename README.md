# CSRBT — Composable Self-Balancing Tree Engine

CSRBT is a Java ordered-set engine whose balancing strategy is pluggable and can
adapt to the workload hitting it. A single, generic ordered-set API
(`OrderedSet<K>`, over any `Comparable` key or a custom `Comparator`) is backed by
interchangeable strategies — Red-Black, AVL, Splay, and a Hybrid — and the engine
can morph between them at runtime. A morph builds the new tree off to the side,
validates it through a health gate (contents, size, the strategy's own structural
invariant, and order-statistics spot-checks), and only then swaps it in — a failed
validation keeps the incumbent untouched, so there is never data loss. On top of
the ordered set it provides O(log n) order statistics (rank, select, median,
percentile, range) over a subtree-size augmentation.

The current release is a correct, well-tested core: the four strategies, order
statistics, persistence, undo/redo, and health-gated morphing. The remaining
ambition — a live control plane that *decides* morphs automatically from the workload,
rather than on explicit request — is now landing incrementally (ADR-002 step 6): its
first units, a workload monitor, a transparent cost-model scorer, and an anti-thrash
policy, are built and independently tested in `core.control`, with the wiring that
re-points the live loop onto them still to come. The target architecture is specified in
[`docs/DESIGN-adaptive-engine.md`](docs/DESIGN-adaptive-engine.md), with the gap
between today's code and that target tracked in
[`docs/strategy-audit-and-feasibility-2026-05-30.md`](docs/strategy-audit-and-feasibility-2026-05-30.md).

## Architecture

The design is organized in three layers, with each layer depending only on the
one below it through a narrow interface.

**Mechanics.** `RedBlackTree<K>` is a thin engine over a sentinel-`NIL` node
model (`TreeNode1<K>`, which carries color, height, and a pluggable augmentor). It
is generic over the key type, with all ordering routed through a pluggable
`Comparator` seam (`withNaturalOrder` is the convenience factory for `Comparable`
keys). Balancing behavior lives behind the `TreeStrategy<K>` interface, implemented by
`RedBlackStrategy`, `AVLStrategy`, `SplayStrategy`, and `HybridStrategy` (AVL
rebalance plus an RB recolor pass). Strategies no longer depend on the concrete
engine: they operate against `MutableTree<K>`, a minimal structural interface
exposing `getRoot` / `setRoot` / `getNIL` / `rotateLeft` / `rotateRight` — the
only capabilities any balancing algorithm needs. `RedBlackTree<K> implements
MutableTree<K>`, so the engine and its strategies are decoupled without breaking
existing call sites.

**Orchestration.** `OrderedSet<K>` is the generic, client-facing facade: over
any key type it owns dedup-guarded add/remove, the size counter, order statistics,
the health-gated strategy morph, sliding-window eviction, pluggable augmentation,
and a self-repair rebuild. `TreeContext` is the `int` adapter over
`OrderedSet<Integer>`: it preserves the `int` public API and layers on the
genuinely `Integer`-bound machinery (undo/redo history, text-snapshot persistence,
cloning, and diagnostics/relic reporting) plus the utility delegates
`TreeDiagnostics`, `TreeCloner`, and `TreeHistory`. A morph never mutates the live tree in place — the candidate is
built aside, validated by `StrategyHealthCheck`, and swapped in only on a full
pass. Representation-neutral views are exposed through `OrderedCollection<K>` (add /
remove / contains / inOrder / size / clear) and `TreeEngine<K>`, so callers can
treat any backing structure uniformly.

**Evolution.** `TreeGenome` is a self-interpreting fitness model that scores how
well each structure fits a workload and recommends morphs.
`GenomeDrivenTreeController` runs a per-strategy feedback loop (gated by an
anti-thrash `MorphPolicy`), and `StrategyBattleRunner` benchmarks strategies
head-to-head across workload types. The biological-model analytics (`TreeEcology`)
and alien-seed/swarm theatrics (`TreeAgent`) live in a separate `experimental`
package that depends on core, keeping the core contract-bound. `TreeEngineRegistry` keeps
`TreeGenome.StructureType` honest — every declared type either maps to a working
engine or fails loudly as unsupported, rather than silently returning a no-op.

**Control plane (ADR-002 step 6, landing).** The design's successor to the genome is a
pipeline of four small, independently testable units in `core.control`, each a pure
function over an immutable input so every adaptation decision is explainable from a
single log line. `WorkloadMonitor` folds the op stream into an immutable
`WorkloadFeatures` vector — read/write mix, hot-key access skew, mean search depth,
rotation rate, size, and growth — in O(1) per op with no tree traversal.
`StrategyScorer` (the `CostModelStrategyScorer`) rebases the genome's per-structure
weighting onto that vector and emits a ranked, cost-annotated list of `StrategyId`s.
`MorphPolicy` applies the cooldown / stability / minimum-improvement gates over a
`MorphHistory`. These units are landed and unit-tested but **not yet wired** into the
live loop: the `MorphController` that runs them on a cadence and drives the existing
health-gated `setStrategy` — retiring the `TreeGenome` path — is the final wiring step
(Phase D). Until then the genome-driven controller still runs unchanged.

## Quick start

```java
// Pick a balancing strategy; the facade is the only class clients touch.
TreeContext tree = new TreeContext(new RedBlackStrategy<>());

tree.add(42);
tree.add(17);
tree.add(99);

tree.contains(17);     // true
tree.size();           // 3
tree.inOrder();        // [17, 42, 99]

// O(log n) order statistics over the augmented tree.
OrderStatisticsOps<Integer> os = new OrderStatisticsOps<>(tree.getTree());
os.select(2).getData();      // 42  (2nd smallest)
os.rank(99);                 // 3
os.median().getData();       // 42

// Undo / redo (inverse-command history) and named checkpoints.
tree.getHistory().saveCheckpoint("baseline");
tree.remove(42);
tree.getHistory().undo();    // 42 is back

// Durable text snapshots.
new FilePersistenceAdapter().saveSnapshot("mytree", tree);

// The generic facade offers the same operations over any key type.
OrderedSet<String> words = OrderedSet.withNaturalOrder(new AVLStrategy<>());
words.add("pear"); words.add("apple"); words.add("fig");
words.inOrder();                            // [apple, fig, pear]
words.select(2);                            // "fig"  (2nd smallest)
words.setStrategy(new SplayStrategy<>());   // health-gated morph, contents preserved

// Snapshots work over any key type via a pluggable KeySerializer<K>.
FilePersistenceAdapter store = new FilePersistenceAdapter();
store.saveSnapshot("words", words, KeySerializer.string());
OrderedSet<String> restored = store.loadOrderedSet("words", KeySerializer.string());
```

## Features

- **Generic keys** — `OrderedSet<K>` orders any key type through a pluggable
  `Comparator` (or `withNaturalOrder` for `Comparable` keys); the `int`
  `TreeContext` is a thin adapter over `OrderedSet<Integer>`.
- **Pluggable balancing** — Red-Black, AVL, Splay, and a Hybrid strategy behind
  one interface, swappable at runtime without data loss.
- **Order statistics** — `select`, `rank`, `median`, `percentile`, range count
  and range query in O(log n) via subtree-size augmentation, kept exact across
  inserts, deletes, rotations, and strategy morphs.
- **Interval queries** — overlap and stabbing queries via a pluggable interval
  augmentor; tags survive morphs and snapshots.
- **Sliding-window / bounded set** — optional capacity (`setMaxSize`) that evicts
  the oldest-inserted key first, with order statistics kept exact on the
  survivors (streaming-percentile use case).
- **Undo / redo + checkpoints** — O(1)-per-op inverse-command history with named
  save points.
- **Persistence** — human-readable text snapshots (no Java serialization) over any key
  type through a pluggable `KeySerializer<K>` (`OrderedSet<K>` snapshots via
  `saveSnapshot`/`loadOrderedSet`; the `int` `TreeContext` path is the built-in
  `KeySerializer.INTEGER`, byte-identical to the legacy format).
- **Diagnostics & evolution** — red-black validity checks, self-repair, workload
  scoring, and head-to-head strategy benchmarking.
- **Adaptive control plane (in progress)** — an O(1)-per-op workload monitor, a
  transparent cost-model strategy scorer, and an anti-thrash morph policy, each an
  independently unit-tested unit in `core.control`; the automatic morph-decision wiring
  is the remaining step (ADR-002 step 6, Phase D).

## Project layout

Every source file's package matches its directory, so the tree below is also the
package layout.

```
src/main/java/core/
  ├─ MutableTree.java          structural seam the strategies depend on
  ├─ RedBlackTree.java         the generic engine (implements TreeEngine, MutableTree)
  ├─ TreeNode1.java            node model (color, height, subtree-size augment)
  ├─ OrderedSet.java           generic ordered-set facade (OrderedSet<K>)
  ├─ TreeContext.java          int adapter over OrderedSet<Integer>
  ├─ TreeEngineRegistry.java   structure-type → engine registry
  ├─ PersistentTreeEngine.java engine + persistence wiring
  ├─ strategy/                 TreeStrategy + RedBlack, AVL, Splay, Hybrid
  ├─ evolution/                TreeGenome, GenomeDrivenTreeController, StrategyBattleRunner
  ├─ control/                  adaptive control plane (ADR-002 step 6): WorkloadMonitor,
  │                            StrategyScorer, StrategyId, MorphPolicy, MorphHistory
  ├─ augment/                  IntervalAugmentor
  ├─ interfaces/               TreeEngine, OrderedCollection, AugmentedTree, …
  ├─ persistence/              FilePersistenceAdapter (text snapshots)
  └─ util/                     diagnostics, cloner, history, order statistics,
                               strategy health check
src/main/java/experimental/    opt-in theatrics (TreeAgent alien-seed/swarm,
                               TreeEcology analytics) — depends on core, never
                               the reverse; core stays contract-bound
src/test/java/test/core/       JUnit 5 suite (strategy invariants, regressions)
docs/                          design, audits, ADR, code reviews, refactor plan
build.xml                      Ant build (JUnit 5 console launcher)
```

## Building and testing

The build targets **JDK 17** and runs the test suite through the JUnit 5
Platform Console Standalone jar. Place that jar in the project root (see the
comment at the top of `build.xml` for the download URL), alongside the bundled
`log4j-api` / `log4j-core` jars.

```
ant compile     # compile main + test sources (release 17)
ant test        # compile, then run the full JUnit 5 suite
ant clean       # remove the build/ directory
```

`ant test` fails the build if any test fails; reports are written to
`build/test-reports`. The suite includes:

- `StrategyInvariantTest` — per-strategy invariants (RB validity, strict AVL
  balance, splay-to-root, Hybrid balance) checked against a `TreeSet` oracle,
  driven directly through the engine to isolate each strategy.
- `OrderedSetTest` — the generic `OrderedSet<K>` facade over non-`Integer` keys
  (`String` and a reverse `Comparator`), cross-checked against a `TreeSet` oracle.
- `RegressionFixesTest` — the earlier correctness/performance fixes (RB deletion,
  AVL balance, order-statistics integrity, undo/redo, snapshot loading).
- `AuditFixesTest` / `TagPreservationTest` / `CloneAugmentorTest` — duplicate-insert
  and history integrity, interval augmentation, and tag/augmentor preservation
  across morph, snapshot, and clone.
- `HealthGatedMorphTest` / `MorphPolicyTest` — morph validation + rollback and the
  anti-thrash cooldown/stability/margin gates.
- `WorkloadMonitorTest` / `StrategyScorerTest` / `MorphPolicyControlTest` — the
  `core.control` units: O(1) workload-feature extraction, the cost-model strategy
  ranking (the DESIGN §10 trace and each workload regime), and the promoted morph
  policy + `MorphHistory` (with `shouldMorph` parity to the legacy gate).
- `WindowingTest` / `PersistentTreeEngineTest` — bounded-set eviction and the
  stack-safe path-copying persistent engine.

Run the full suite after any change to the engine or strategies.

## Concurrency

`TreeContext` and the underlying `OrderedSet` are designed for **single-threaded use**. Its mutators (`add`,
`remove`, `setStrategy`, `clear`) serialize on one internal lock, which only
prevents two *writers* from interleaving — it is not sufficient for general
concurrent access. Reads take no lock and may observe a tree mid-mutation, and
accessors such as `getTree()` expose live internal structure that bypasses the
lock entirely. The `RedBlackTree` and strategy implementations are **not**
thread-safe on their own. Applications needing concurrent access must provide
their own external synchronization around all access. (The design doc specifies a
future single-writer / multi-reader model via atomic root swap.)

## Design history

**Design & direction**
- [`docs/DESIGN-adaptive-engine.md`](docs/DESIGN-adaptive-engine.md) — the target
  architecture: two-plane design, control loop, and acceptance goals (G1–G9).
- [`docs/ADR-002-architecture-review-2026-05-30.md`](docs/ADR-002-architecture-review-2026-05-30.md)
  — architecture review + decisions: phased generic-key migration and control-plane
  consolidation.
- [`docs/system-design-audit-2026-05-30.md`](docs/system-design-audit-2026-05-30.md)
  — requirements scorecard, load/reliability analysis, and what to revisit as it grows.
- [`docs/ADR-001-csrbt-review-optimization-expansion.md`](docs/ADR-001-csrbt-review-optimization-expansion.md)
  — original architecture decision record: review, rationale, and roadmap.

**Audits & change log**
- [`docs/PLAN-adr002-step6-control-plane.md`](docs/PLAN-adr002-step6-control-plane.md)
  — ADR-002 step 6: the four-unit control plane (monitor → scorer → policy → controller)
  as a strangler over the genome loop; Phases A–C (monitor, scorer, policy) landed.
- [`docs/PLAN-adr002-step6-phaseD-controller-rewire.md`](docs/PLAN-adr002-step6-phaseD-controller-rewire.md)
  — ADR-002 step 6, Phase D: the behavior-sensitive wiring (MorphController, the monitor
  hook, and re-pointing the controller) that activates the control plane.
- [`docs/CHANGELOG-2026-06-04-key-serializer.md`](docs/CHANGELOG-2026-06-04-key-serializer.md)
  — ADR-002 step 5: a pluggable `KeySerializer<K>` so snapshots persist any key type.
- [`docs/CHANGELOG-2026-06-03-orderedset.md`](docs/CHANGELOG-2026-06-03-orderedset.md)
  — ADR-002 step 4: the `OrderedSet<K>` facade and the `TreeContext` `Integer` adapter.
- [`docs/CHANGELOG-2026-06-01-generic-keys.md`](docs/CHANGELOG-2026-06-01-generic-keys.md)
  — ADR-002 step 2: generifying the engine against `<K>` behind a `Comparator` seam.
- [`docs/CHANGELOG-2026-05-30.md`](docs/CHANGELOG-2026-05-30.md) — everything that
  changed in the latest hardening session.
- [`docs/strategy-audit-and-feasibility-2026-05-30.md`](docs/strategy-audit-and-feasibility-2026-05-30.md)
  — per-strategy correctness audit and a gap analysis vs the adaptive end goal
  (with resolution status).
- [`docs/code-audit-2026-05-30.md`](docs/code-audit-2026-05-30.md) — correctness,
  augmentation, persistence, and concurrency findings, with fixes applied.
- [`docs/backend-audit-2026-05-30.md`](docs/backend-audit-2026-05-30.md) —
  persistence/clone/agent infrastructure findings, with fixes applied.
- [`docs/code-review-2026-05-29.md`](docs/code-review-2026-05-29.md) — earlier code
  review findings and the fixes applied for each.
- [`docs/PLAN-nil-sentinel-refactor.md`](docs/PLAN-nil-sentinel-refactor.md) —
  step-by-step plan for the per-tree-NIL / parent-convention refactor.
