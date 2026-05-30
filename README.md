# CSRBT — Composable Self-Balancing Tree Engine

CSRBT is a Java self-balancing-tree library that has grown into an *adaptive,
genome-driven* tree engine. A single ordered-set API is backed by interchangeable
balancing strategies (Red-Black, AVL, Splay, and a Hybrid), and an evolutionary
layer can score workloads and adaptively morph the active strategy at runtime.

## Architecture

The design is organized in three layers, with each layer depending only on the
one below it through a narrow interface.

**Mechanics.** `RedBlackTree` is a thin engine over a sentinel-`NIL` node model
(`TreeNode1`, which carries color, height, and a pluggable augmentor). Balancing
behavior lives behind the `TreeStrategy` interface, implemented by
`RedBlackStrategy`, `AVLStrategy`, `SplayStrategy`, and `HybridStrategy` (AVL
rebalance plus an RB recolor pass). Strategies no longer depend on the concrete
engine: they operate against `MutableTree`, a minimal structural interface
exposing `getRoot` / `setRoot` / `getNIL` / `rotateLeft` / `rotateRight` — the
only capabilities any balancing algorithm needs. `RedBlackTree implements
MutableTree`, so the engine and its strategies are decoupled without breaking
existing call sites.

**Orchestration.** `TreeContext` is the client-facing facade: it owns metrics,
adaptive strategy morphing, persistence, the locking contract, and the utility
delegates `TreeDiagnostics`, `TreeCloner`, `TreeAgent`, and `TreeHistory`.
Representation-neutral views are exposed through `OrderedCollection` (add /
remove / contains / inOrder / size / clear) and `TreeEngine`, so callers can
treat any backing structure uniformly.

**Evolution.** `TreeGenome` is a self-interpreting fitness model that scores how
well each structure fits a workload and recommends morphs.
`GenomeDrivenTreeController` runs a per-strategy feedback loop, `TreeEcology`
provides biological-model analytics, and `StrategyBattleRunner` benchmarks
strategies head-to-head across workload types. `TreeEngineRegistry` keeps
`TreeGenome.StructureType` honest — every declared type either maps to a working
engine or fails loudly as unsupported, rather than silently returning a no-op.

## Quick start

```java
// Pick a balancing strategy; the facade is the only class clients touch.
TreeContext tree = new TreeContext(new RedBlackStrategy());

tree.add(42);
tree.add(17);
tree.add(99);

tree.contains(17);     // true
tree.size();           // 3
tree.inOrder();        // [17, 42, 99]

// O(log n) order statistics over the augmented tree.
OrderStatisticsOps os = new OrderStatisticsOps(tree.getTree());
os.select(2).getData();      // 42  (2nd smallest)
os.rank(99);                 // 3
os.median().getData();       // 42

// Undo / redo (inverse-command history) and named checkpoints.
tree.getHistory().saveCheckpoint("baseline");
tree.remove(42);
tree.getHistory().undo();    // 42 is back

// Durable text snapshots.
new FilePersistenceAdapter().saveSnapshot("mytree", tree);
```

## Features

- **Pluggable balancing** — Red-Black, AVL, Splay, and a Hybrid strategy behind
  one interface, swappable (and auto-morphable) at runtime without data loss.
- **Order statistics** — `select`, `rank`, `median`, `percentile`, range count
  and range query in O(log n) via subtree-size augmentation.
- **Undo / redo + checkpoints** — O(1)-per-op inverse-command history with named
  save points.
- **Persistence** — human-readable text snapshots (no Java serialization).
- **Diagnostics & evolution** — RB-validity checks, self-repair, workload
  scoring, and head-to-head strategy benchmarking.

## Project layout

Every source file's package matches its directory, so the tree below is also the
package layout.

```
src/main/java/core/
  ├─ MutableTree.java          structural seam the strategies depend on
  ├─ RedBlackTree.java         the engine (implements TreeEngine, MutableTree)
  ├─ TreeNode1.java            node model (color, height, subtree-size augment)
  ├─ TreeContext.java          orchestration facade
  ├─ TreeEngineRegistry.java   structure-type → engine registry
  ├─ PersistentTreeEngine.java engine + persistence wiring
  ├─ strategy/                 TreeStrategy + RedBlack, AVL, Splay, Hybrid
  ├─ evolution/                TreeGenome, GenomeDrivenTreeController, StrategyBattleRunner
  ├─ augment/                  IntervalAugmentor
  ├─ interfaces/               TreeEngine, OrderedCollection, AugmentedTree, …
  ├─ persistence/              FilePersistenceAdapter (text snapshots)
  └─ util/                     diagnostics, cloner, agent, history,
                               order statistics, ecology
src/test/java/test/core/       JUnit 5 suite (incl. RegressionFixesTest)
docs/                          ADR, code review, NIL-refactor plan
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
`build/test-reports`. `RegressionFixesTest` covers the recent correctness and
performance fixes (RB deletion, AVL balance, order-statistics integrity,
undo/redo, snapshot loading) — run it after any change to the engine or
strategies.

## Concurrency

`TreeContext` is the sole synchronization point for mutations: `add`, `remove`,
`setStrategy`, and `clear` are serialized on a single internal lock. Read
operations are unlocked and may observe a tree mid-mutation, so applications that
need a read consistent with concurrent writers must provide their own external
synchronization. The underlying `RedBlackTree` and the strategy implementations
are **not** thread-safe on their own; all access goes through the facade.

## Design history

- [`docs/ADR-001-csrbt-review-optimization-expansion.md`](docs/ADR-001-csrbt-review-optimization-expansion.md)
  — architecture decision record: review, rationale, and roadmap.
- [`docs/code-review-2026-05-29.md`](docs/code-review-2026-05-29.md) — code
  review findings and the fixes applied for each.
- [`docs/PLAN-nil-sentinel-refactor.md`](docs/PLAN-nil-sentinel-refactor.md) —
  step-by-step plan for the remaining per-tree-NIL / parent-convention refactor.
