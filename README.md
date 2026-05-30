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

## Project layout

```
src/main/java/core/            engine, strategies, facade, evolution layer
  ├─ MutableTree.java          structural seam the strategies depend on
  ├─ RedBlackTree.java         the engine (implements TreeEngine, MutableTree)
  ├─ TreeContext.java          orchestration facade
  ├─ TreeGenome.java           fitness / recommendation model
  ├─ strategy/                 RedBlack, AVL, Splay strategies
  ├─ interfaces/               TreeEngine, OrderedCollection, AugmentedTree, …
  ├─ persistence/              FilePersistenceAdapter
  └─ util/                     diagnostics, cloner, agent, history
src/test/java/test/core/       JUnit 5 suite
docs/ADR-001-*.md              architecture decision record (review + roadmap)
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
`build/test-reports`. The current suite is green: **227 tests, 0 failures.**

## Concurrency

`TreeContext` is the sole synchronization point for mutations: `add`, `remove`,
`setStrategy`, and `clear` are serialized on a single internal lock. Read
operations are unlocked and may observe a tree mid-mutation, so applications that
need a read consistent with concurrent writers must provide their own external
synchronization. The underlying `RedBlackTree` and the strategy implementations
are **not** thread-safe on their own; all access goes through the facade.

## Design history

The full architectural review, the rationale for the phased approach, and the
record of every change are in
[`docs/ADR-001-csrbt-review-optimization-expansion.md`](docs/ADR-001-csrbt-review-optimization-expansion.md).
