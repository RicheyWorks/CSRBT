# CHANGELOG 2026-06-03 -- ADR-002 step 4: `OrderedSet<K>` facade + `TreeContext` adapter

Implements ADR-002 Option C, step 4: a generic, client-facing `OrderedSet<K>`
ordered-set facade over the step-2 generic engine, and the reduction of
`TreeContext` to an `Integer` adapter that delegates its ordered-set behaviour to
an internal `OrderedSet<Integer>`. The `int` `TreeContext` public API is unchanged.

## Phases

- **A -- `StrategyHealthCheck` generified to `<K>`.** `validate(RedBlackTree<K>,
  TreeStrategy<K>, List<K>)` and its private invariant helpers (`isBst`,
  `isRedBlackValid`, `blackHeight`, `isHeightBalanced`) now take `TreeNode1<K>`.
  Every clause was already key-agnostic (contents via `inOrder()`, ordering via
  `compareTo`, order-stats spot-check via `select`/`rank`). `TreeContext`'s call
  site infers `<Integer>`.

- **B -- `core.OrderedSet<K>` (new) + `OrderedSetTest` (new).** Wraps a
  `RedBlackTree<K>` plus a lazily-rebuilt `OrderStatisticsOps<K>`. Owns the
  key-type-agnostic behaviour that `TreeContext` used to inline: dedup-guarded
  `add(K)`/`remove(K)` (now returning `boolean`), the size counter, the full
  order-statistics surface, the health-gated strategy morph (build aside ->
  validate via `StrategyHealthCheck` -> publish, carrying per-node tags), the
  FIFO sliding window, pluggable augmentation, and a self-repair rebuild. A
  `withNaturalOrder(strategy)` factory mirrors `RedBlackTree`. `OrderedSetTest`
  exercises the whole surface on **non-`Integer`** keys (`String` natural order
  and a reverse `Comparator`), cross-checked against a `TreeSet` oracle.

- **C -- client interfaces generified.** `OrderedCollection<K>` (now
  `add`/`remove` return `boolean`, `contains(K)`, `inOrder():List<K>`) and
  `AugmentedTree<K>` (`setAugmentor(Augmentor<K>)`). `OrderedSet<K>` implements
  both; `TreeContext` implements the `<Integer>` instantiations. Because an
  `add(int)` does not override `add(Integer)` (the step-2 `PersistentTreeEngine`
  lesson), `TreeContext` gained `add(Integer)`/`remove(Integer)`/`contains(Integer)`
  alongside its `int` public API; the `int` methods delegate to them.

- **D -- `TreeContext` reduced to a delegating `Integer` adapter.** It now holds a
  `private OrderedSet<Integer> set` and routes add/remove/contains/size/inOrder/
  clear/setMaxSize/setAugmentor/setStrategy/selfRepair/metrics through it, firing
  its `Integer`-only side-effects (undo history via `TreeHistory`, the default-off
  stress signal) only on a real change (relying on `set.add/remove` returning
  `boolean`). It retains the genuinely `Integer`-bound machinery: persistence
  (`save/loadSnapshot`), cloning, diagnostics/relic reporting, undo/redo history,
  and the legacy stress auto-morph. `getTree()` returns `set.getEngine()`.

### Out-of-band engine rebuilds: `OrderedSet.resyncFromEngine()`

`FilePersistenceAdapter`, `TreeHistory` (checkpoint restore) and `TreeCloner`
rebuild the engine directly via `getTree().setRoot(...)` and then call
`TreeContext.forceSizeInternal(n)`. Since the engine now lives inside `OrderedSet`,
`forceSizeInternal` delegates to the new `OrderedSet.resyncFromEngine()`, which
recomputes the size counter and rebuilds the FIFO window from the engine's current
in-order contents (ascending fallback, since true insertion order is unknowable
after a wholesale rebuild). `loadSnapshot` adopts the deserialized context's `set`
outright. This makes `size() == inOrder().size()` an enforced invariant after any
out-of-band rebuild.

## Verification status -- IMPORTANT

**This work was verified by static analysis only; it has NOT been compiled or
run.** The build sandbox had no JVM compiler available (JRE only, and no reachable
source for a JDK/ECJ), so `ant clean test` could not be executed. Every call in
`OrderedSet`/`TreeContext` was checked against the actual signatures of the step-2
spine (`RedBlackTree`, `OrderStatisticsOps`, `TreeNode1`, `TreeStrategy`,
`StrategyHealthCheck`, the collaborators) and braces/EOL/UTF-8 were verified, but
**the ~295-test `int` suite plus the new `OrderedSetTest` must be run on a host
JDK 17 before relying on this change.**

### Watch-list (behavioural nuances to confirm on the host)

- `add`/`remove` fire `history.record*` + the stress signal only on a real change
  (via the `set.add/remove` boolean), not a pre-`contains`.
- `selfRepair` keeps the original "no-op when already valid" short-circuit (via
  `TreeDiagnostics`), then delegates the rebuild to `OrderedSet.selfRepair`
  (which validates via `StrategyHealthCheck`, per ADR-002 decision 2.5).
- The strategy morph now resyncs the FIFO window to ascending order inside
  `OrderedSet.setStrategy` (the old inline `TreeContext.setStrategy` did not).
  No existing test combines morph with windowing.
- Windowed eviction inside `OrderedSet` no longer prunes `TreeContext.frequencyMap`
  (only relevant to the default-off stress auto-morph).
- `forceSizeInternal(n)` now recomputes the size from the engine rather than
  trusting `n`; for all real callers `n` equals the engine's node count.

## Out of scope (still pending, per ADR-002)

Key (de)serialization is step 5: `FilePersistenceAdapter`, `save/loadSnapshot`
and `TreePersistenceAdapter` stay `int`/`TreeContext`. `TreeHistory`,
`IntervalAugmentor`, `TreeCloner`, `TreeDiagnostics`, and the evolution/control
plane remain `Integer`/`TreeContext`-bound.
