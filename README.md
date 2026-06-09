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

The current release is a correct, well-tested core — the four strategies, order
statistics, persistence, undo/redo, and health-gated morphing — now driven by a live
control plane that *decides* morphs automatically from the workload rather than on
explicit request (ADR-002 step 6). A workload monitor, a transparent cost-model scorer,
an anti-thrash policy, and the `MorphController` that runs them on a cadence are wired
into the live loop and **on by default**; the older genome-driven path is retained but
deprecated behind a one-switch flag. On top of that, the **multi-tree ensemble**
(ADR-003) keeps several strategy-backed members live over the same key set so adaptation
becomes an O(1) primary swap instead of an O(n) morph, with failover, quorum
verification, and a memory-lean sampled mode. The target architecture is specified in
[`docs/DESIGN-adaptive-engine.md`](docs/DESIGN-adaptive-engine.md); the migration that
closed the gap to it is tracked in
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

**Evolution (legacy decision path).** `TreeGenome` is a self-interpreting fitness model
that scores how well each structure fits a workload and recommends morphs, and
`GenomeDrivenTreeController` ran it as a per-strategy feedback loop gated by an anti-thrash
`MorphPolicy`. As of ADR-002 step 6 that genome path is deprecated — the controller now
decides through the control plane (below) by default, keeping the genome loop only as a
flagged fallback. `StrategyBattleRunner` benchmarks strategies head-to-head across workload
types. The biological-model analytics (`TreeEcology`)
and alien-seed/swarm theatrics (`TreeAgent`) live in a separate `experimental`
package that depends on core, keeping the core contract-bound. `TreeEngineRegistry` keeps
`TreeGenome.StructureType` honest — every declared type either maps to a working
engine or fails loudly as unsupported, rather than silently returning a no-op.

**Control plane (ADR-002 step 6).** The genome's successor is a pipeline of four small,
independently testable units in `core.control`, each a pure function over an immutable
input so every adaptation decision is explainable from a single log line.
`WorkloadMonitor` folds the op stream into an immutable `WorkloadFeatures` vector —
read/write mix, hot-key access skew, mean search depth, rotation rate, size, and growth —
in O(1) per op with no tree traversal. `StrategyScorer` (the `CostModelStrategyScorer`)
rebases the per-structure weighting onto that vector and emits a ranked, cost-annotated
list of `StrategyId`s. `MorphPolicy` applies the cooldown / stability / minimum-improvement
gates over a `MorphHistory`. The `MorphController` runs them on a cadence and drives the
existing health-gated `setStrategy` through a `StrategyMorphTarget` seam, emitting one
`event=morph_eval` line per evaluation. As of Phase D, `GenomeDrivenTreeController` decides
through this pipeline **by default** (`useControlPlane`, default ON): reads as well as writes
drive the eval cadence, and the genome's self-interpreting fitness path is `@Deprecated` but
retained behind the flag for one-switch rollback.

**Ensemble (ADR-003).** `EnsembleOrderedSet<K>` is a drop-in `OrderedCollection` backed by
several strategy members kept in exact sync: every effective write fans out to all ACTIVE
members (sequentially by default, or in parallel across a daemon pool via
`parallelFanOut()` — always under one writer lock, so the logical set stays linearizable),
while reads are served by a `volatile` *primary*. Because every member is already warm,
adaptation is `promote` — an O(1) pointer swap — instead of an O(n) morph;
`EnsembleController` generalizes `MorphController` to drive promotions from the same
control plane, gated by the same `MorphPolicy`. Members carry a health lifecycle
(ACTIVE / QUARANTINED / RETIRED): a member that fails its cadence check or throws
mid-write is quarantined and healed from the primary, and a failing *primary* fails over
instantly to a healthy member. `VERIFIED` mode fans reads to a quorum and serves the
majority, quarantining dissenters (N-version programming against silent corruption);
`SAMPLED_SHADOW` mode is the memory-lean inverse — shadows receive only a sampled stride
of writes (~1 + p·(K−1) cost), estimate strategy fitness, and pay an O(n) sync-on-promote
if elevated. Snapshots persist the primary only and rebuild members on load.

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

// The ensemble (ADR-003): several members live at once; adaptation is an O(1) swap.
EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(Comparator.naturalOrder())
        .member(RedBlackStrategy::new)      // member 0 — initial primary
        .member(AVLStrategy::new)           // warm standby / promotion candidate
        .parallelFanOut()                   // E5: writes fan to members in parallel
        .build();
ens.add(42); ens.add(17);                   // fans out to all ACTIVE members
ens.contains(17);                           // served by the primary
ens.promote(ens.members().get(1));          // O(1): the warm AVL member now serves

// Ensemble snapshots persist the primary (the logical set) and rebuild members on load.
store.saveSnapshot("ens", ens, KeySerializer.INTEGER);
store.loadEnsemble("ens", KeySerializer.INTEGER, ens);
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
- **Adaptive control plane** — an O(1)-per-op workload monitor, a transparent cost-model
  strategy scorer, an anti-thrash morph policy, and the `MorphController` that runs them on
  a cadence and drives the health-gated `setStrategy`. As of ADR-002 step 6 Phase D this is
  the controller's **default** decision path; the genome loop is deprecated behind a flag.
- **Multi-tree ensemble (ADR-003)** — `EnsembleOrderedSet<K>` keeps K strategy members in
  exact sync (parallel write fan-out under one writer lock) so adaptation is an **O(1)
  promote** instead of an O(n) morph, with instant failover, quarantine/heal/retire
  lifecycle, quorum-verified reads (`VERIFIED`), a memory-lean sampled mode
  (`SAMPLED_SHADOW`, ~1 + p·(K−1) cost, O(n) sync-on-promote), and primary-only snapshots
  that rebuild every member on load.

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
  │                            StrategyScorer, StrategyId, MorphPolicy, MorphHistory,
  │                            MorphController, StrategyMorphTarget
  ├─ ensemble/                 multi-tree ensemble (ADR-003): EnsembleOrderedSet,
  │                            EnsembleMember, EnsembleMode, EnsembleController,
  │                            MemberExecutor (sequential / parallel fan-out)
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
- `MorphControllerTest` / `StrategyIdBridgeTest` / `ControllerMonitorFeedTest` /
  `ControllerControlPlaneFlagTest` / `ControllerConvergenceTest` — the control-plane wiring
  (Phase D): one `event=morph_eval` line per evaluation and health-fail-keeps-incumbent, the
  `StrategyId`↔`StructureType` bridge, the O(1)-per-op monitor feed, the flag-gated re-point,
  and convergence (skewed reads → Splay in ≤1 morph, steady → 0 morphs, regime-following).
- `WindowingTest` / `PersistentTreeEngineTest` / `PersistentEngineConcurrencyTest` —
  bounded-set eviction; the weight-balanced path-copying persistent engine (ADR-005:
  oracle parity with invariants checked, adversarial-input balance, explicit snapshots,
  count-funded order statistics); and its wait-free-readers-under-churn proof plus the
  printed persistent-vs-R1-vs-READ_REPLICA read-throughput reference.
- `ConcurrentReadStressTest` / `EnsembleReplicaTest` — ADR-004 (R1/R2): torn-read-free
  optimistic reads on every strategy under write churn, and READ_REPLICA's left-right
  epoch reads (oracle exactness, churn with mid-stream promotions, loud degradation,
  printed read-throughput reference).
- `EnsembleOrderedSetTest` / `EnsembleControllerTest` / `EnsembleHealthTest` /
  `EnsembleVerifiedTest` / `EnsembleFanOutTest` / `EnsembleShadowTest` /
  `EnsemblePersistenceTest` / `EnsembleBenchmarkTest` — the ADR-003 ensemble (E1–E6):
  mirror fan-out against a `TreeSet` oracle, controller-driven O(1) promotion,
  quarantine/heal/failover, quorum voting, parallel fan-out (oracle equivalence,
  write-failure quarantine, linearizability under concurrent writers), sampled shadows
  (stride fraction, sync-on-promote, no-serve/no-vote), primary-only snapshot round-trips,
  and the O(1)-swap-vs-O(n)-rebuild benchmark.

Run the full suite after any change to the engine or strategies.

## Concurrency

`OrderedSet` (and the `TreeContext` adapter over it) supports **one writer, many readers**
(ADR-004 R1). Mutators serialize on an internal lock and stamp their mutations on a
`StampedLock`; public reads are **torn-read-free** — `contains`/`inOrder` run optimistically
with a step-bounded walk and are discarded unless the stamp validates, order statistics hold
the shared read lock, and facade reads never splay (Splay's move-to-root adaptivity lives on
the write path). Reads are safe, not lock-free — a read overlapping a write may briefly take
the shared lock (R2 of ADR-004 targets wait-free reads via the ensemble). Accessors such as
`getTree()`/`getEngine()` still expose live internal structure that bypasses the guard — they
remain a single-threaded diagnostics seam — and the `RedBlackTree`/strategy layer is **not**
thread-safe on its own.

The ensemble facade extends the same model to member granularity: `EnsembleOrderedSet`
serializes all writers on one lock (concurrent callers are safe and linearizable),
parallelizes the *internal* fan-out across members — only one thread ever touches a
member's write path at a time — and publishes promotion/failover as a `volatile` primary
swap. Reads served by the primary inherit R1's torn-read-free guarantee, and
`EnsembleMode.READ_REPLICA` (ADR-004 R2) makes them **lock-free**: epoch readers
(enter / re-verify / exit on the serving member's counter) read a tree no writer shares,
while the writer updates the non-serving mirrors first, flips, drains the old side's
epoch, then updates it.

`PersistentTreeEngine` (ADR-005) gets the strongest guarantee with the least machinery:
**wait-free readers by construction**. Every read — membership, traversal, order
statistics, snapshots — is one `volatile` read of the root followed by a walk of immutable
(`final`-field) nodes that can never change; mutators serialize on an internal monitor,
path-copy O(log n) fresh nodes aside, and publish with a single `volatile` store. No
stamps, retries, step bounds, or epochs anywhere on the read path, ensemble or not.
`snapshot()` is an O(1) immutable capture that stays queryable forever. The price is paid
on the write side: O(log n) allocation per mutation (GC pressure scales with write rate).

## Design history

**Design & direction**
- [`docs/DESIGN-adaptive-engine.md`](docs/DESIGN-adaptive-engine.md) — the target
  architecture: two-plane design, control loop, and acceptance goals (G1–G9).
- [`docs/ADR-003-multi-tree-ensemble-2026-06-06.md`](docs/ADR-003-multi-tree-ensemble-2026-06-06.md)
  — **Accepted**: the multi-tree ensemble — O(1) promotion, failover, quorum verification,
  sampled shadows, parallel fan-out, persistence. Landed in steps E1–E6 (see the
  `CHANGELOG-2026-06-09-ensemble-*.md` series).
- [`docs/ADR-004-lock-free-reads-2026-06-09.md`](docs/ADR-004-lock-free-reads-2026-06-09.md)
  — **Accepted**: the torn-read caveat retired — optimistic step-bounded reads everywhere
  (R1, landed) and lock-free left-right epoch reads over ensemble mirrors
  (`READ_REPLICA`, R2, landed); the balanced persistent engine held as the horizon (R3,
  since cashed in by ADR-005).
- [`docs/ADR-005-balanced-persistent-engine-2026-06-09.md`](docs/ADR-005-balanced-persistent-engine-2026-06-09.md)
  — **Accepted**: `PersistentTreeEngine` rebuilt as a generic weight-balanced (Δ=3, Γ=2)
  path-copying engine — wait-free reads without an ensemble, O(1) explicit snapshots,
  count-funded order statistics (P1+P2 landed; ensemble membership held as P3).
- [`docs/ADR-002-architecture-review-2026-05-30.md`](docs/ADR-002-architecture-review-2026-05-30.md)
  — architecture review + decisions: phased generic-key migration and control-plane
  consolidation.
- [`docs/system-design-audit-2026-05-30.md`](docs/system-design-audit-2026-05-30.md)
  — requirements scorecard, load/reliability analysis, and what to revisit as it grows.
- [`docs/ADR-001-csrbt-review-optimization-expansion.md`](docs/ADR-001-csrbt-review-optimization-expansion.md)
  — original architecture decision record: review, rationale, and roadmap.

**Audits & change log**
- [`docs/CHANGELOG-2026-06-06-control-plane.md`](docs/CHANGELOG-2026-06-06-control-plane.md)
  — ADR-002 step 6, Phase D (D1–D5): the control plane is wired in via `MorphController` and
  made the controller's default decision path; the genome loop is deprecated behind a flag.
- [`docs/PLAN-adr002-step6-control-plane.md`](docs/PLAN-adr002-step6-control-plane.md)
  — ADR-002 step 6: the four-unit control plane (monitor → scorer → policy → controller)
  as a strangler over the genome loop. **Landed** (Phases A–E).
- [`docs/PLAN-adr002-step6-phaseD-controller-rewire.md`](docs/PLAN-adr002-step6-phaseD-controller-rewire.md)
  — ADR-002 step 6, Phase D: the behavior-sensitive wiring (MorphController, the monitor
  feed, and re-pointing the controller) that activated the control plane. **Done.**
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
