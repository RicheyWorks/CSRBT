# CSRBT Code Audit — 2026-05-30

Static audit of the `core` source tree (~6,300 LOC main, ~1,400 LOC tests). The
codebase is a strategy-driven balanced-BST engine (RB / AVL / Splay / Hybrid)
with augmentation, persistence, undo/redo, and a genome-driven adaptive layer.

**Build note:** the suite could not be compiled or run in the audit sandbox — it
targets `release=17` and only a JDK 11 *JRE* (no `javac`) was available, with no
network access to fetch a JDK. All findings below are from static review. The
existing `RegressionFixesTest` suite shows prior review items (#1–#9) were
addressed and have coverage; the issues below are mostly *new* and uncovered.

Overall the core algorithms (CLRS RB insert/delete/fixup, AVL rebalance, Splay,
order statistics) are faithful and well-commented. The defects cluster in the
facade/integration layer and the augmentation model rather than the textbook
algorithms.

---

## High severity

### H1 — `TreeContext.size` drifts on duplicate inserts
`TreeContext.add()` calls `tree.add(value)` then `size++` **unconditionally**.
Every strategy's `insert()` silently skips duplicates (logs a warn and returns).
So inserting an existing key leaves the tree unchanged but increments `size`.

- `size()` / `getSize()` then over-report; `avgInsertTimeMs()` denominator also
  inflates (`insertCount++` likewise unconditional).
- Persistence "size mismatch" warnings and `forceSizeInternal` partly mask this
  on reload, but in-memory size is wrong until then.
- `remove()` is guarded by `contains()`, so the asymmetry is one-directional and
  the counter only ever drifts upward.

Fix: have the engine/strategy report whether an insert actually happened (e.g.
`boolean add`) and increment `size`/`insertCount`/history only on success — or
gate `TreeContext.add` on `!tree.contains(value)` (one extra O(log n) lookup).
`TreeHistory` has the matching problem: a skipped duplicate still records an
`ADD`, so a later undo `REMOVE`s a key the user never added — silent data loss.

### H2 — Interval augmentation is not maintained on inserted nodes
`IntervalAugmentor` stores `max(hi)` in `augmentedValue`, but two paths break it:

1. **`setTag` does not re-augment.** `insertInterval()` does `context.add(lo)`
   then `node.setTag(hi)`. At insert time the tag is empty, so `parseHi` returns
   `lo` and the subtree max is computed from `lo` values. `setTag()` only sets a
   string — it never calls `recomputeAugment`/propagate — so `max(hi)` is never
   refreshed up the tree. The doc comment ("augmentor propagates max(hi) up
   automatically") is incorrect.
2. **New nodes don't carry the interval augmentor.** `TreeNode1.createNode`
   always installs `defaultAugmentor` (subtree size). `TreeContext.setAugmentor`
   only re-applies to nodes that already exist; any key added *after* that call
   gets the size augmentor again. So `intervalSearch`'s `left.augmentedValue >=
   qlo` pruning reads size, not max-hi, and can return wrong results / miss
   overlaps.

Fix: set the high endpoint and augmentor atomically with insertion (e.g. an
`insertInterval` that creates the node with the interval augmentor and triggers
propagation), and make `TreeContext.add` stamp the context's current augmentor
onto each new node. `intervalSearchAll` is also affected (its prune uses
`augmentedValue < qlo`).

Note: `OrderStatisticsOps` and `IntervalAugmentor` both overload
`augmentedValue` for different meanings (size vs. max-hi). They can't be used on
the same tree simultaneously; this constraint is undocumented and unenforced.

---

## Medium severity

### M1 — Audit log grows without bound
`TreeHistory.auditLog` is an `ArrayList` that is appended on every recorded op
and never trimmed, even though `undoStack` is capped at `MAX_HISTORY = 200`. The
class Javadoc claims the unbounded-memory problem was fixed; it was fixed for the
undo stack but not the audit log. Long-running processes leak. Fix: cap or
ring-buffer the audit log, or make retention configurable.

### M2 — `PersistentTree`/`Hybrid` strategies lost on snapshot reload
`FilePersistenceAdapter.resolveStrategy` only maps `AVLStrategy` and
`SplayStrategy`, defaulting everything else (including `HybridStrategy`) to
`RedBlackStrategy`. A tree saved under Hybrid silently reloads as RB, changing
behavior. Also `loadSnapshot` reconstructs nodes but never restores the
augmentor or per-node tags, so interval trees can't round-trip. Add Hybrid to
the switch and persist/restore augmentor + tags (or document the limitation).

### M3 — Deserialization uses unbounded recursion
`deserializePreOrder` and `serializePreOrder` recurse per node; a deep/degenerate
snapshot (e.g. a Splay tree saved mid-skew) can `StackOverflowError`. The
in-memory traversals were deliberately made iterative for this reason — the
persistence path wasn't. Convert to an explicit stack, and validate token counts.

### M4 — `TreeContext.loadSnapshot` aliases the snapshot's live structures
On load it assigns `this.tree = snapshot.tree` and copies `frequencyMap` but
shares the same `RedBlackTree`/strategy instances as the returned snapshot
object, and does not reset `recentInsertions`/`stressEvents`. If the snapshot
object is retained elsewhere, mutations alias. Prefer deep-copying into the
existing context (as `TreeHistory.restoreFrom` does) and reset all derived state.

### M5 — Concurrency contract is partial and easy to violate
`TreeContext` documents itself as the sole synchronization point, but:
- It hands out the live `RedBlackTree` via `getTree()` and live nodes via
  traversals; callers can mutate structure outside the lock.
- Read methods (`contains`, `size`, `inOrder`, `selfRepair`) are unsynchronized
  by design and can observe a half-applied rotation — `blackHeight()` may then
  throw `IllegalStateException` mid-mutation.
- `HybridStrategy` uses `AtomicInteger`/`ConcurrentHashMap`, implying
  thread-safety it doesn't actually provide (the tree ops around them aren't
  safe). `TreeNode1.lock` is allocated per node but never used.

Either commit to single-threaded use (and drop the misleading atomics/lock) or
provide a genuinely guarded API that doesn't leak internal mutables.

---

## Low severity / code quality

### L1 — Dead computation in `HybridMetricsSnapshot.derivedFitness`
The local `depth = 1.0 - (avgSearchDepth / (avgSearchDepth*1.5))` always equals
`0.333…` regardless of input and is never used in the returned value. Either
incorporate a real depth term or remove the dead line.

### L2 — `O(height)` augment propagation on every BST link
`setLeft`/`setRight` call `recomputeAugmentAndPropagate` (walk to root). This is
intended (rotations use the `*Local` variants), but a single insert does the
propagating link once plus rotations, and `setColor` triggers `updateBlackHeight`
on each recolor. Fine asymptotically (insert stays O(log n)), but the constant
factor is high; worth a benchmark if perf matters.

### L3 — `TreeDiagnostics.toJson()` is a stub returning `"{}"`
Either implement or remove; currently a silent no-op that could mislead callers.

### L4 — Swallowed exception in `loadSnapshot`
`catch (Exception e)` logs and returns `null`, conflating "not found", "corrupt
file", and "bug" into one null. Callers can't distinguish. Consider typed
results or at least narrower catches.

### L5 — `selfRepair` rebuilds via `add()` and inherits H1
It re-inserts the in-order element list; since those are distinct keys this is
fine today, but it relies on the same `add` path and will mis-count if H1's fix
changes add semantics. Keep them consistent.

### L6 — Genome / evolution layer lightly reviewed
`TreeGenome` (1,925 LOC), `GenomeDrivenTreeController`, and
`StrategyBattleRunner` were skimmed, not line-audited. `StrategyBattleRunner`
seeds `new Random(seed)` deterministically (good for reproducibility). The
registry (`TreeEngineRegistry`) cleanly closes the prior "null strategy" gap by
making unsupported `StructureType`s throw with a reason — a good pattern. Recommend
a dedicated pass on `TreeGenome` given its size and central role in morph
decisions.

---

## Suggested priority order
1. H1 (size/history correctness) — small, high impact, currently untested.
2. H2 (interval augmentation) — feature is effectively broken as documented.
3. M2 + M3 (persistence: Hybrid mapping, recursion, augmentor/tags).
4. M1 (audit log memory), M5 (concurrency contract), M4 (load aliasing).
5. Low items as cleanup; add regression tests for H1/H2 (neither is covered).
