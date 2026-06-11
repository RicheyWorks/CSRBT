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
statistics, persistence, undo/redo, and health-gated morphing — driven by a live
control plane that *decides* morphs automatically from the workload rather than on
explicit request (ADR-002 step 6). On top of that, the **multi-tree ensemble**
(ADR-003) keeps several members live over the same key set so adaptation becomes an
O(1) primary swap instead of an O(n) morph, with instant failover, quorum-verified
reads (with a tunable verification stride and lock-free unanimous votes, ADR-006/007),
two write-lean shadow modes, and memory ceilings. Members are no longer only
strategy-backed trees: the **engine family** adds a weight-balanced path-copying
persistent engine with wait-free readers and O(1) snapshots (ADR-005) and a
page-structured **B+tree** for large n (ADR-008), both first-class ensemble citizens
through the `RankedSet` seam. A `NavigableSet` adapter (ADR-009) makes the whole thing
a drop-in for `TreeSet` call sites. Adaptation decisions are observable end to end:
structured events, JSON tree export, and a session recorder feed a zero-dependency
visualizer (`demo/visualizer.html`) that **replays the controller's own decisions** —
load `docs/arena-session.json` and watch it morph RB → Splay → RB on a live workload,
or `docs/arena-search-session.json` and watch the evolution machine itself: genomes
born, gate-killed, culled, and one promoted.
**ADR-011, the evolution machine, is complete**: the strategy family gained its first
*parameterized* member (`WeightBalancedStrategy(Δ, Γ)`, validated against its own
parameters by the health gate), a UCB1 bandit and a (μ+λ) population search breed and
trial policies as live ensemble shadows — births, deaths, and promotions all replayable
in the arena — and the story ends in a falsifiable experiment, answered honestly:
**searched parameters do not beat the four fixed strategies** (≥10% on no family across
3 seeds, deterministic comparisons/op). The search converged to the literature's WB(3,·),
unsound points like (5,3) self-disqualified on the record, and the adaptive claim stays
where it belongs — with the controller that picks the right specialist per workload.
The target architecture is specified in
[`docs/DESIGN-adaptive-engine.md`](docs/DESIGN-adaptive-engine.md); **ADR-001 through
ADR-011 are all Accepted** (ADR-011's verdict:
[`docs/CHANGELOG-2026-06-10-adr011-v5-experiment.md`](docs/CHANGELOG-2026-06-10-adr011-v5-experiment.md)).

## Architecture

The design is organized in three layers, with each layer depending only on the
one below it through a narrow interface.

**Mechanics.** `RedBlackTree<K>` is a thin engine over a sentinel-`NIL` node
model (`TreeNode1<K>`, which carries color, height, and a pluggable augmentor). It
is generic over the key type, with all ordering routed through a pluggable
`Comparator` seam (`withNaturalOrder` is the convenience factory for `Comparable`
keys). Balancing behavior lives behind the `TreeStrategy<K>` interface, implemented by
`RedBlackStrategy`, `AVLStrategy`, `SplayStrategy`, `HybridStrategy` (AVL
rebalance plus an RB recolor pass), and `WeightBalancedStrategy(Δ, Γ)` — the first
*parameterized* strategy (ADR-011): BB[α] weight balance over the intrinsic subtree-size
augment, its (Δ, Γ) dials forming the genome dimension the evolution machine searches,
with a strategy-supplied invariant hook so the health gate validates each candidate
against its own parameters. Strategies no longer depend on the concrete
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
majority, quarantining dissenters (N-version programming against silent corruption) —
its cost is tunable on two axes: `verifyEvery(n)` votes on a deterministic stride of
reads instead of all of them (ADR-006), and a lock-free unanimous fast path serves
agreeing votes with no lock at all, escalating any dissent to the locked vote where
quarantine decisions stay race-free (ADR-007). `SAMPLED_SHADOW` is the memory-lean mode —
shadows receive only a sampled stride of writes (~1 + p·(K−1) cost) and pay an O(n)
sync-on-promote if elevated; `REBUILD_SHADOW` (ADR-003 Option C) is the write-lean one —
shadows take no live writes and are rebuilt wholesale from the primary on a cadence.
A soft memory ceiling (`memoryCeilingBytes`, observed and logged, never self-degrading)
and a hard cap on K (`maxMembers`) round out the memory controls. Snapshots persist the
primary only and rebuild members on load.

**Engine family (ADR-005, ADR-008).** Ensemble members need not be strategy-backed
trees: the `RankedSet` seam admits any engine honoring `OrderedSet`'s exact semantics
(the voting-parity contract), via `Builder.engineMember(...)` or the
`persistentMember()` shorthand. Two engines ship. `PersistentTreeEngine` is a generic
weight-balanced (Δ=3, Γ=2) path-copying structure: every read — including order
statistics — is a `volatile` root read plus a walk of immutable nodes, so readers are
**wait-free by construction**, and `snapshot()` is an O(1) immutable capture that stays
queryable forever; snapshots persist through `KeySerializer` as flat ascending keys.
`BPlusTreeEngine` is the large-n answer: keys live in fanout-sized leaf pages chained
for range scans, internal nodes are pure routing with per-child counts funding the full
order-statistics surface, and the in-memory layout is deliberately the on-disk page
layout for the held disk-backing slice. Engine members serve, vote, heal, and fail
over like any member; the cost-model scorer cannot rank them, so they are promoted
explicitly or by failover, never automatically.

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

// Engine-tier members (ADR-005/008): wait-free persistent reads, page-structured large-n.
EnsembleOrderedSet<Integer> mixed = EnsembleOrderedSet.<Integer>builder(Comparator.naturalOrder())
        .member(RedBlackStrategy::new)
        .persistentMember()                                   // wait-free reads when promoted
        .engineMember(BPlusTreeEngine::withNaturalOrder, "BPlusTreeEngine")
        .mode(EnsembleMode.VERIFIED).verifyEvery(16)          // quorum reads, 1-in-16 vote stride
        .build();

// Wait-free O(1) snapshots on the persistent engine: "the set as of now" is a handle.
PersistentTreeEngine<Integer> eng = PersistentTreeEngine.withNaturalOrder();
eng.add(1); eng.add(2);
PersistentTreeEngine.Snapshot<Integer> frozen = eng.snapshot();
eng.add(3);
frozen.size();                              // 2 — immutable, queryable forever

// Drop-in NavigableSet over any OrderedSet (ADR-009): floor/ceiling/views, TreeSet parity.
NavigableSet<String> navigable = new NavigableOrderedSet<>(words);
navigable.floor("grape");                   // "fig"
navigable.subSet("apple", true, "pear", false);   // live, read-only range view
```

## Features

- **Generic keys** — `OrderedSet<K>` orders any key type through a pluggable
  `Comparator` (or `withNaturalOrder` for `Comparable` keys); the `int`
  `TreeContext` is a thin adapter over `OrderedSet<Integer>`.
- **Pluggable balancing** — Red-Black, AVL, Splay, and a Hybrid strategy behind
  one interface, swappable at runtime without data loss.
- **Order statistics** — `select`, `rank`, `median`, `percentile`, range count
  and range query in O(log n) via subtree-size augmentation, kept exact across
  inserts, deletes, rotations, and strategy morphs; `size()` is O(1) off the same
  augment (ADR-009 P1).
- **`NavigableSet` adapter** — `NavigableOrderedSet<K>` is a drop-in for `TreeSet`
  call sites: floor/ceiling/higher/lower ride the rank machinery in O(log n), range
  and descending views are live and compose, and view mutators refuse loudly rather
  than rot quietly (ADR-009 P2).
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
- **Multi-tree ensemble (ADR-003)** — `EnsembleOrderedSet<K>` keeps K members in
  exact sync (parallel write fan-out under one writer lock) so adaptation is an **O(1)
  promote** instead of an O(n) morph, with instant failover, quarantine/heal/retire
  lifecycle, quorum-verified reads (`VERIFIED`), a memory-lean sampled mode
  (`SAMPLED_SHADOW`), a write-lean rebuild mode (`REBUILD_SHADOW`), memory ceiling and
  cap-K controls, and primary-only snapshots that rebuild every member on load.
- **Tunable verified reads (ADR-006/007)** — `verifyEvery(n)` makes VERIFIED's K× read
  amplification a dial (deterministic stride, default 1 = every read votes), and the
  optimistic unanimous fast path makes healthy votes **lock-free** (any dissent
  escalates to the locked vote, so quarantine stays race-free; sandbox rows: 15× at
  n=16, 2.7× under a saturating writer).
- **Engine family (ADR-005/008)** — beyond the strategy trees: `PersistentTreeEngine`
  (weight-balanced path-copying; wait-free readers, O(1) immutable snapshots,
  `KeySerializer` persistence) and `BPlusTreeEngine` (page-structured, leaf-chained,
  count-funded order statistics; the disk-ready layout). Both join ensembles as
  first-class members through the `RankedSet` seam (`engineMember(...)`).

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
  ├─ PersistentTreeEngine.java weight-balanced path-copying engine (ADR-005):
  │                            wait-free readers, O(1) immutable snapshots
  ├─ PersistentRankedSet.java  RankedSet adapter — the persistent engine as an
  │                            ensemble member
  ├─ BPlusTreeEngine.java      page-structured large-n engine (ADR-008): leaf
  │                            chain, count-funded order statistics
  ├─ adapter/                  NavigableOrderedSet — java.util.NavigableSet face
  │                            (ADR-009): TreeSet-parity navigation, live
  │                            read-only views
  ├─ strategy/                 TreeStrategy + RedBlack, AVL, Splay, Hybrid
  ├─ evolution/                TreeGenome, GenomeDrivenTreeController, StrategyBattleRunner
  ├─ control/                  adaptive control plane (ADR-002 step 6): WorkloadMonitor,
  │                            StrategyScorer, StrategyId, MorphPolicy, MorphHistory,
  │                            MorphController, StrategyMorphTarget
  ├─ ensemble/                 multi-tree ensemble (ADR-003): EnsembleOrderedSet,
  │                            EnsembleMember, EnsembleMode, EnsembleController,
  │                            MemberExecutor (sequential / parallel fan-out)
  ├─ augment/                  IntervalAugmentor
  ├─ interfaces/               TreeEngine, OrderedCollection, RankedSet (the
  │                            engine-member voting-parity seam), AugmentedTree, …
  ├─ persistence/              FilePersistenceAdapter (text snapshots)
  └─ util/                     diagnostics, cloner, history, order statistics,
                               strategy health check
src/main/java/experimental/    opt-in theatrics (TreeAgent alien-seed/swarm,
                               TreeEcology analytics) — depends on core, never
                               the reverse; core stays contract-bound
src/test/java/test/core/       JUnit 5 suite (strategy invariants, regressions)
docs/                          design, audits, ADRs, changelogs, code reviews
demo/visualizer.html           single-file animated tree visualizer over the
                               TreeExport contract — open in any browser; loads any
                               exported JSON, animates between states (morphs!)
build.xml                      Ant build (JUnit 5 console launcher)
.github/workflows/ci.yml       CI: ant clean test on a JDK 17/21 matrix (ADR-009 G0)
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
- `EnsembleEngineMemberTest` / `EnsembleRebuildShadowTest` — engine-tier membership
  (ADR-005 P3: mirror/serve/vote/heal through the `RankedSet` seam, no auto-promotion,
  persistent-snapshot round trips) and Option C (`REBUILD_SHADOW` cadence cycle,
  sync-on-promote, ceiling latch + cap-K).
- `EnsembleVerifiedSamplingTest` / `EnsembleVerifiedConcurrencyTest` — ADR-006/007:
  stride-deterministic detection (caught on exactly the nth read), the bounded
  divergent-primary window, no-false-quarantines under write churn (skew always
  escalates and adjudicates clean), and both printed benchmark rows.
- `BPlusTreeEngineTest` — ADR-008: oracle parity at the fanout floor with the invariant
  checker run throughout, degenerate inputs, OrderedSet-parity order statistics and
  edge semantics, and VERIFIED unanimity beside strategy members as the end-to-end
  parity proof.
- `SizeAugmentTest` / `NavigableOrderedSetTest` — ADR-009: O(1) `size()` parity per-op
  under churn/morph/undo, and `TreeSet`-parity navigation swept across every boundary
  class plus view composition and the read-only clause.

Run the full suite after any change to the engine or strategies. CI runs the same
`ant clean test` on a JDK 17/21 matrix (`.github/workflows/ci.yml`).

## Concurrency

`OrderedSet` (and the `TreeContext` adapter over it) supports **one writer, many readers**
(ADR-004 R1). Mutators serialize on an internal lock and stamp their mutations on a
`StampedLock`; public reads are **torn-read-free** — `contains`/`inOrder` run optimistically
with a step-bounded walk and are discarded unless the stamp validates, order statistics hold
the shared read lock, and facade reads never splay (Splay's move-to-root adaptivity lives on
the write path). Reads are safe, not lock-free — a read overlapping a write may briefly take
the shared lock; when reads must be wait-free, reach for the ensemble's `READ_REPLICA` mode
(ADR-004 R2) or the persistent engine (ADR-005), both below. Accessors such as
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

Two later refinements close the remaining gaps. VERIFIED votes no longer serialize
against writes in the healthy case (ADR-007): because writes are serialized, a lock-free
pass that comes back *unanimous* is a consistent cut and is served with no lock; any
disagreement — real divergence or read skew — escalates to the locked vote, where skew is
impossible and quarantine/failover decisions stay race-free. Combined with ADR-006's vote
stride, a healthy VERIFIED steady state takes no locks at all. `BPlusTreeEngine` takes
the opposite, deliberately coarse stance: every public method is synchronized, because a
paged tree mutates in place with no read guard and ensemble votes read members lock-free
— correctness first, page latching only if a workload ever demands it.

**The memory-model edges, named explicitly (ADR-010 X3).** Every cross-thread guarantee
above reduces to four standard happens-before mechanisms. (1) *Monitor edges:* each facade's
mutators serialize on one lock (`OrderedSet.lock`, the ensemble's `writeLock`, the engines'
internal monitors), so writer→writer ordering is total and anything a writer did is visible
to the next writer. (2) *Volatile publication:* the persistent engine's root, the ensemble's
`primary`, member lifecycle fields (`state`, `exact`), `mode`, and the kill switches are
`volatile` — a reader that observes the new reference/state also observes everything written
before its store, which is why an atomic swap is a complete publication. (3) *Stamp
validation:* R1's optimistic reads are speculative — the `StampedLock` validate supplies the
read fence, and a failed validation discards everything observed in the window. (4)
*`final`-field semantics:* the persistent engine's all-`final` nodes are safely published by
construction; no reader can see a partially built node. The one deliberate non-edge: ADR-007's
lock-free vote pass reads with no fence at all and is correct anyway, because writes are
serialized (edge 1) — at most one is in flight, so a unanimous answer is identical whether
each member was read before or after it; any skew shows up as disagreement and is
re-adjudicated under the lock, never served.

## The evolution machine: the story, told honestly

ADR-011 asked a falsifiable question: *if the balancing policy itself becomes searchable —
a genome, bred and trialed live behind the health gate — does the search find something
the four textbook strategies miss?* The machine was built in five slices in one day, and
the arc is worth telling because every twist is on the record.

**The first run drew blood.** The moment `WeightBalancedStrategy(Δ, Γ)` existed and the
health gate learned to ask a strategy for *its own* structural invariant, the very first
parameter sweep found that WB(5,3) — comfortably inside the documented bounds — is
**unsound**: under live delete churn its one-rotation-per-level repair fails to restore
its own Δ-balance, and the gate disqualified it by the strategy's own testimony (contents
stayed oracle-exact — only balance degrades; the gate is why nothing was ever at risk). Nobody
went looking for that; it's pinned as a regression now
([V1](docs/CHANGELOG-2026-06-10-adr011-v1-weight-balanced.md)).

**The search machinery never got to cheat.** Genomes are bounds-checked vectors with
seeded, pure perturbation ([V2](docs/CHANGELOG-2026-06-10-adr011-v2-genome-fitness.md));
the UCB1 bandit and the (μ+λ) population controller trial candidates only as live
ensemble shadows, and promotion goes through the same anti-thrash morph gates as every
other adaptation decision ([V3](docs/CHANGELOG-2026-06-10-adr011-v3-policy-bandit.md),
[V4](docs/CHANGELOG-2026-06-10-adr011-v4-evolution.md)). V3 also surfaced a real seam
bug the design predicted: the old class-identity guard silently refused WB(3,2)→WB(4,2)
morphs — parameterized strategies forced `samePolicyAs` into the strategy contract.

**The experiment answered no — twice, which is once more than it had to.** The
acceptance run ([V5](docs/CHANGELOG-2026-06-10-adr011-v5-experiment.md)) raced the
evolved policy against RB/AVL/Splay/Hybrid on five workload families × three seeds. The
first wall-clock run said *yes, ≥10%*; the second run said *no* — so the experiment
caught its own metric being weather (time on shared hardware) and was rebuilt on
**comparisons per op counted at the comparator seam**: deterministic, byte-identical
across runs. On that honest metric the evolved policy beats three of the four fixed
strategies almost everywhere (~15% fewer comparisons than RB on uniform) — but every
family already has a specialist within 10%. The search converged to the literature's
WB(3,·) on every family and seed: the machine independently confirmed the textbook
default is locally optimal. **The adaptive claim stays with the controller that picks
the right specialist, not with a fifth structure.**

**You can watch all of it.** Drop
[`docs/arena-search-session.json`](docs/arena-search-session.json) into
[`demo/visualizer.html`](demo/visualizer.html): founders enter the nursery, the unsound
WB(5,3) dies by its own invariant in generation 1 (V1's finding, replayed live), a
too-strict mutant follows it, and WB(3,2) takes the throne through the morph gates off a
splay primary. Nothing in the file is staged — every frame is the real controller's own
decision on a seeded stream, snapshotted the moment it committed.

**Where it pointed next** was [ADR-012, the ecology turn](docs/ADR-012-ecology-turn-2026-06-10.md):
V5 closed the *stationary* axis but never tested adaptation under a *changing* workload.
E1–E3 ran the same day, instruments before mechanisms, and every honest answer landed
harder than its thesis. The [viability map](docs/viability-map.json) (drop it on the
visualizer): the viable (Δ, Γ) region is a **sliver** — 2 cells of 46, (3,2) and (4,2),
the literature's narrowness result reproduced by the gate built to catch it, which
retroactively explains V5's convergence ([E1](docs/CHANGELOG-2026-06-10-adr012-e1-viability-map.md)).
The collapse, measured: **the viability filter, not selection, collapses diversity** —
one lineage from generation 1, every seed; the mutation walk to the sliver takes 6–7
generations ([E2](docs/CHANGELOG-2026-06-10-adr012-e2-diversity.md)). And the
regime-shift experiment, with exploration priced at the comparator seam: **no adaptive
scheme of any architecture — evolution, elite, or the ADR-002 selector — beats the best
fixed strategy**; live evolution pays O(n) candidate rebuilds per generation while
serving costs log n, and the selector's per-morph bill still runs ~1.5× hindsight-best
AVL ([E3](docs/CHANGELOG-2026-06-10-adr012-e3-nonstationary.md)). Three instruments,
three negative results, all reproducible, all replayable — the machine keeps earning
its keep by saying no with receipts. E4–E6 stay staged in the ADR, each with a now
*measured* bar to clear.

**The day's last two slices turned the no into a diagnosis, then a fix.** E3b
pre-registered a discriminating schedule from V5's own winners table (oracle gap
~13.5%, premise hard-asserted) and caught the selector red-handed: **it never morphed
once through a 36% opportunity**, because its Phase-B cost model predicted the wrong
meter — it told the controller RB was 30% *better* where the comparator seam measured
AVL winning every diet probed
([E3b](docs/CHANGELOG-2026-06-10-adr012-e3b-discriminating-schedule.md)). The fix was
perception, nothing else: the scorer's constants refit to the realized
comparisons-per-op tables already on the record — shape kept, gates and schedules
untouched ([calibration](docs/CHANGELOG-2026-06-10-scorer-calibration.md)). The
calibrated selector goes from never morphing to **tying hindsight-best AVL within ~1%
on E3 and ~3.5% on E3b, while paying its own morph rebuilds** — the selector rows
above are superseded, but both verdicts remain no: the registered bar is a ≥10% *win*
over best fixed, and tying isn't winning. The claim, precisely sized: *the calibrated
selector matches the best fixed choice without knowing it in advance; it does not yet
beat it.* The residual ~13% oracle gap lives in the sequential blocks (the oracle
rides Splay at 13.7 cmp/op where AVL pays 20.3) and is named and held — a
recency-aware locality feature, only if that gap ever needs claiming.

## Design history

**Design & direction**
- [`docs/DESIGN-adaptive-engine.md`](docs/DESIGN-adaptive-engine.md) — the target
  architecture: two-plane design, control loop, and acceptance goals (G1–G9).
- [`docs/ADR-012-ecology-turn-2026-06-10.md`](docs/ADR-012-ecology-turn-2026-06-10.md)
  — **Proposed**: the ecology turn, staged E1–E6 — the non-stationary axis V5 never
  tested, instruments before mechanisms, honest scope (general principles of adaptive
  informational systems, not biological claims).
- [`docs/ADR-011-evolution-machine-2026-06-10.md`](docs/ADR-011-evolution-machine-2026-06-10.md)
  — **Accepted, verdict negative**: the evolution machine, V1–V5 (see the story above);
  per-slice changelogs `CHANGELOG-2026-06-10-adr011-v*.md`.
- [`docs/ADR-010-second-reconciliation-2026-06-10.md`](docs/ADR-010-second-reconciliation-2026-06-10.md)
  — **Accepted**: second reconciliation pass — the repair gate (X1), session replay in
  the arena (X2), and the memory-model edges named explicitly (X3).
- [`docs/ADR-009-roadmap-reconciliation-2026-06-09.md`](docs/ADR-009-roadmap-reconciliation-2026-06-09.md)
  — **Accepted**: an external review's gap list audited against the code — what was stale,
  what was real (O(1) `size()`, the `NavigableSet` adapter, structured events + the
  `docs/visualizer-contract.json` export, CI — all landed), and what is held with explicit
  triggers (Gradle/JMH, jqwik).
- [`docs/ADR-008-bplus-tree-engine-2026-06-09.md`](docs/ADR-008-bplus-tree-engine-2026-06-09.md)
  — **Accepted**: the Phase-4 large-n engine — a page-structured B+tree, structure
  before disk (D1 landed; paged file backing and registry/genome integration held).
- [`docs/ADR-007-optimistic-votes-2026-06-09.md`](docs/ADR-007-optimistic-votes-2026-06-09.md)
  — **Accepted**: the writer-lock ceiling decomposed — unanimous VERIFIED votes go
  lock-free (a consistent cut by construction), dissent escalates to the locked vote.
- [`docs/ADR-006-verified-read-sampling-2026-06-09.md`](docs/ADR-006-verified-read-sampling-2026-06-09.md)
  — **Accepted**: `verifyEvery(n)` — VERIFIED's K× amplification as a deterministic
  stride dial; post-R1 the fault class is persistent, so sampling changes detection
  latency, not detection.
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
  count-funded order statistics. P3 (ensemble membership via the `RankedSet` seam +
  snapshot persistence) landed same day.
- [`docs/ADR-002-architecture-review-2026-05-30.md`](docs/ADR-002-architecture-review-2026-05-30.md)
  — architecture review + decisions: phased generic-key migration and control-plane
  consolidation.
- [`docs/system-design-audit-2026-05-30.md`](docs/system-design-audit-2026-05-30.md)
  — requirements scorecard, load/reliability analysis, and what to revisit as it grows.
- [`docs/ADR-001-csrbt-review-optimization-expansion.md`](docs/ADR-001-csrbt-review-optimization-expansion.md)
  — original architecture decision record: review, rationale, and roadmap.

**Audits & change log**
- [`docs/CHANGELOG-2026-06-09-session-index-2.md`](docs/CHANGELOG-2026-06-09-session-index-2.md)
  and [`docs/CHANGELOG-2026-06-09-session-index.md`](docs/CHANGELOG-2026-06-09-session-index.md)
  — the 2026-06-09 session maps: eleven ensemble/read-path slices (ADR-003/004/005),
  then ADR-006/007/008 closing the open list; each slice has its own changelog beside
  these.
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
