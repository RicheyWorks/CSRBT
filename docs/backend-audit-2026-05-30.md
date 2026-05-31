# CSRBT — Backend / infrastructure audit (2026-05-30)

Scope: the non-strategy infrastructure layer — the persistence engine
(`PersistentTreeEngine`), the snapshot/clone backend (`TreeCloner`,
`FilePersistenceAdapter`), and the agent/ecology plumbing (`TreeAgent`,
`TreeEcology`). The four balancing strategies and the order-statistics /
augmentation surface are covered in `strategy-audit-and-feasibility-2026-05-30.md`
and `code-audit-2026-05-30.md`. (There is no network/DB/server backend in this
project; "backend" here means the data/storage/engine infrastructure.)

---

## High / medium findings

### B1 (MEDIUM) — `PersistentTreeEngine` is an *unbalanced* BST
The persistent engine does textbook path-copying, but the underlying tree is a
plain BST with **no balancing**. Consequences:

- **O(n) worst case.** Sorted or adversarial insertion produces a linear chain;
  `contains`/`add`/`remove` degrade to O(n), not the O(log n) the
  `TreeEngineRegistry` description ("Persistent ordered set — immutable,
  path-copying") implies.
- **Stack overflow risk.** `insert` and `delete` are recursive on tree depth, so
  a large sorted load (depth ≈ n) will `StackOverflowError`. The pointer-based
  engine deliberately uses iterative traversals for exactly this reason; the
  persistent engine wasn't given the same treatment.
- **Unbounded version retention.** `versions` keeps every root forever with no
  cap or prune API. That's inherent to persistence, but there's no way to bound
  memory for a long-lived instance.
- It also carries `count` (subtree size) on every node but exposes no
  order-statistics (`select`/`rank`) — a free O(log n) capability left on the table.

*Recommendation:* make it a balanced persistent structure (weight-balanced / red-
black with path copying) or document it explicitly as an unbalanced, demo-grade
engine not subject to the O(log n) contract. At minimum, make insert/delete
iterative or depth-guarded.

### B2 (MEDIUM) — `TreeCloner.snapshot` silently drops the augmentor
`deepCopyTwoPass` creates clone nodes via `TreeNode1.createNode`, which installs
the **default (subtree-size) augmentor**. `copyNodeFields` copies the numeric
`augmentedValue`, but pass 2 then calls the *propagating* `setLeft`/`setRight`,
which recompute `augmentedValue` from the clone's (default) augmentor — overwriting
any non-size augment such as interval `max-hi`. Net effect:

- Snapshots, checkpoints, and clone-army copies of an **interval-augmented** tree
  revert to size augmentation, so interval queries on a clone are wrong.
- `snapshot()` also copies only `tree` + `size`; it drops the context's augmentor
  field, `frequencyMap`, metrics, `recentInsertions`, and `stressEvents`. A
  restored checkpoint is therefore not a faithful context copy.

This is the same augmentor-preservation gap fixed for morph and snapshot
persistence; the clone path was missed. *Recommendation:* stamp the source
context's augmentor onto clone nodes (and re-augment), and copy the relevant
context-level state, mirroring the morph/snapshot fixes.

### B3 (MEDIUM, footgun) — `TreeAgent.alienSeed` installs a non-BST into a live context
`alienSeed` clears the context and builds a tree whose children are
`data ± random(variance)` at every level. This does **not** preserve BST ordering
or any strategy invariant, yet it sets the result as the context's live root and
forces the size counter. Afterward `inOrder()` is not sorted, `contains()` is
unreliable, and order statistics are meaningless — the ordered-set contract is
broken with no warning. `autoTag()` similarly overwrites every node's tag, which
would destroy interval high-endpoints on an interval tree.

These are the "theatrical" surface the design doc (`DESIGN-adaptive-engine.md`
§6, §13) explicitly says to move into an `experimental/` module that depends on
the core, never the reverse. They should not be reachable on a live, contract-
bound `TreeContext`.

---

## Low findings

### B4 (LOW) — `TreeAgent.runAgentSwarm` violates the single-threaded contract
It spins up an 8-thread pool that reads tree nodes concurrently and calls
`pool.shutdown()` without `awaitTermination`, so on a short-lived run the logging
tasks may not complete. The engine is documented single-threaded; concurrent
traversal (even read-only) is inconsistent with that. Experimental-module
material.

### B5 (LOW) — `TreeEcology` diversity metrics are degenerate on a set
`shannonDiversity` builds a frequency map over `inOrderTraversal()`, but the
structure is a **set** — every key count is exactly 1. So `H' = ln(n)` always and
`shannonEvenness` is always `1.0`; the metric can never signal anything about the
actual tree. The biological analytics are costume over a structure that doesn't
have the multiset abundances they assume — again, demote to `experimental/`.

### B6 (LOW) — `PersistentTreeEngine.clear()` records redundant empty versions
`clear()` appends a `null` root version unconditionally, even if the engine is
already empty, growing the version log with no information.

### B7 (LOW) — `FilePersistenceAdapter` does not persist the strategy-specific augmentor
(Already noted in the code audit.) Snapshots restore nodes and tags but not the
augmentor identity (augmentors are lambdas); a reloaded interval tree needs
`setAugmentor(INSTANCE)` re-applied. Acceptable given the constraint, but worth a
one-line note in the format doc.

---

## What's solid
- `FilePersistenceAdapter` path-traversal protection, header/version handling, and
  the now-iterative (de)serialization are correct and backward-compatible.
- `TreeCloner`'s two-pass BFS correctly rebuilds structure/parent links (the
  earlier disconnected-clone bug is fixed); the only gap is augmentor/context
  state (B2).
- `PersistentTreeEngine`'s persistence logic (structural sharing, version
  retention, set semantics, no-change-no-version) is correct — the issue is purely
  the lack of balancing (B1).

## Suggested priority
1. **B2** — small, and matches the augmentor-preservation work already done
   elsewhere; restores interval-clone correctness.
2. **B1** — either balance the persistent engine or relabel it; at minimum guard
   the recursion depth.
3. **B3 / B4 / B5** — move `TreeAgent` and `TreeEcology` to an `experimental/`
   module (per the design doc) so the contract-bound core can't be corrupted by
   the theatrical surface.
4. **B6 / B7** — trivial cleanups.

---

## Resolution status (updated 2026-05-30, later same day)

- **B1 — PARTIALLY DONE.** `PersistentTreeEngine` insert/delete/traversal are now
  iterative, so deep/sorted input no longer overflows the stack (`PersistentTreeEngineTest`
  inserts 10k sorted keys). It is still an *unbalanced* BST (O(n) worst case) —
  balancing it remains future work, now clearly documented in the class.
- **B2 — DONE.** `TreeCloner.snapshot`/`shallowClone` and `TreeHistory` checkpoint
  restore now preserve a non-default augmentor; interval clones/checkpoints keep
  correct max-hi (`CloneAugmentorTest`).
- **B3/B4/B5 — DONE.** `TreeAgent` and `TreeEcology` moved to a standalone
  `experimental` package; `TreeContext` no longer depends on them, so the
  alien-seed footgun can't be triggered on a live context.
- **B6 — DONE.** `PersistentTreeEngine.clear()` no longer records redundant empty
  versions.
- **B7 — DONE.** The snapshot header now carries the augmentor identity
  (`DEFAULT`/`INTERVAL`, 5th field, backward-compatible), and load re-applies it —
  interval trees round-trip without a manual `setAugmentor` (`TagPreservationTest`).
  Custom (non-built-in) augmentor lambdas are still recorded as `DEFAULT`.
