# ADR-014: Build a balanced tree from a sorted run in O(n) — `OrderedSet.fromSorted`

**Status:** Accepted (2026-06-14 — `./gradlew build` green host-side; `BulkBuildTest` red-black
invariant + order-statistic parity checks and the jqwik oracle pass)
**Date:** 2026-06-14
**Deciders:** Richmond
**Builds on:** ADR-002 (intrinsic subtree `size` as the order-statistics source of truth — the field
this build maintains directly, independent of the pluggable augmentor) and ADR-009 P1 (O(1) size).
**Prompted by:** SuperBeefSort — an external sorting engine that feeds CSRBT and measured the feed
(repeated `add`) at roughly 8× its own sort time.

---

## 1. Context

`add(K)` is CSRBT's only population path: a `contains` precheck (which may splay on a Splay-backed
set), a BST insert, then `fixInsert` rotations — O(log n) per key, O(n log n) for a batch, plus the
rotation churn. That is the right and only general path for arbitrary insertion order.

But there is a common case it serves badly: bulk-loading an **already-sorted, distinct run**. Feeding
a sorted sequence through `add` one key at a time is the pathological shape for a self-balancing tree
— every key lands on the same spine and triggers fixups — and it discards the one fact that makes
bulk loading cheap: the data is already ordered. An external sort engine (SuperBeefSort) produces
exactly such runs.

The numbers that prompted this (SBS demo, 50,000 keys, ~39k distinct after de-dup): the sort itself
ran ~4 ms; feeding the sorted run via median-first `add` ran ~33–45 ms. **The feed, not the sort, was
the bottleneck** — and it was avoidable.

Constraints carried in: order statistics must keep working immediately (intrinsic `size`, ADR-002);
red-black invariants must hold (the health gate and `TreeDiagnostics` validate them); and the change
must be **purely additive** — no behavior change to `add` / `remove` / morph / `selfRepair`.

## 2. Options considered

### Option A: Keep `add`-only; callers feed median-first

| Dimension | Assessment |
|---|---|
| Complexity | None (no CSRBT change) |
| Cost | O(n log n), still rotates |
| API surface | Unchanged |

**Pros:** zero risk, works through the public API. **Cons:** leaves the measured bottleneck on the
table; every external caller re-implements the same median-first dance and still pays for rotations.
SBS already does this — it is the fallback this ADR keeps, not the goal.

### Option B: O(n) direct construction — `fromSorted` / `buildBalanced` *(chosen)*

| Dimension | Assessment |
|---|---|
| Complexity | Medium — internal node construction + a correct RB colouring |
| Cost | O(n), no rotations |
| API surface | Three additive entry points; no change to existing ones |

**Pros:** removes the rotations and the per-insert `contains`; the construction is linear and the win
is real (~2× measured). **Cons:** the colouring has to be *proved* correct, not hand-waved, or the
health gate rejects the tree.

### Option C: Expose the node model so callers build the tree themselves

Rejected without a table. It leaks `TreeNode1`, invites corruption, and makes every caller re-derive
the colouring proof. The whole point of an engine is to own its invariants.

## 3. Decision

Add, to `RedBlackTree`, `buildBalanced(List<K>)`; to `OrderedSet`, the static `fromSorted(...)` /
`fromSortedNatural(...)` factories and the instance `buildFromSorted(...)`.

**Structure.** Recursive median: index `(lo + hi) >>> 1` is each subtree's root. Built bottom-up with
`setLeftLocal` / `setRightLocal`, so each link recomputes *this* node's `size` / augment / height
locally in O(1) — never walking to the root (that is what would make it O(n log n)). Total O(n).

**Colouring — and why it is a valid RB tree.** Colour exactly the deepest level RED, every other node
BLACK, root forced BLACK. A median build places every leaf on depth `floor(log2 n)` or
`floor(log2 n) − 1`, and every node *at* the deepest level is a leaf. Colouring only that level red
gives: (a) no red node has a red child — the level above it is black; (b) red nodes' children are NIL,
which is black; and (c) every root→NIL path crosses the same number of black nodes, namely the black
levels sitting above the red leaves. This was checked **exhaustively for n = 1..3000** (a standalone
verifier: uniform black-height, no red-red, in-order == input, subtree sizes correct) before the code
was written, and is asserted in `BulkBuildTest` through the engine's own throwing `blackHeight()` and
`StrategyHealthCheck.validate`.

**Validation over speed-at-any-cost.** `buildFromSorted` requires the set be empty and the list
**strictly ascending** under the set's comparator (one O(n) pass), throwing `IllegalArgumentException`
rather than silently building a non-BST. Strictly-ascending also enforces distinctness — a Set's
contract — so the caller, not the engine, owns de-duplication.

**Size / window sync.** `buildFromSorted` sets the cached `size` directly from the list length (the
list *is* the in-order sequence, so no `inOrder()` traversal is needed) and only populates the FIFO
window when `maxSize > 0`. Unbounded sets — the default — never consult the window, so populating it
would be pure overhead; the `evictOldest` safety net still covers a later `setMaxSize` on a bulk-built
set.

**Strategy generality.** The build is RB-coloured but *structurally* a perfectly balanced BST, which
also satisfies AVL height-balance and is invariant-free for Splay. Non-RB strategies ignore the
colours, so `fromSorted` is valid for any strategy — RB is simply the one whose colours mean
something.

## 4. Consequences

**Easier:** bulk-loading a sorted run is O(n) and rotation-free. An external sort engine feeds CSRBT
at roughly **2× the previous balanced-add rate** (SBS demo, ~39k keys: ~45 ms → ~21 ms, then ~14 ms
after the `resyncFromEngine` trim below), the remaining cost being the irreducible n node allocations
plus order-statistic augmentation.

**Harder / sharp edges:** `buildFromSorted` trusts — and validates — its precondition; a caller who
routes around the check with unsorted data builds a broken tree. And the O(n) is on *construction*,
not a free lunch: allocating n nodes and maintaining augmentation are inherently linear, which is why
the win is ~2×, not ~10×.

**To revisit:** a package-private bulk `size` setter to fuse the size + augment recompute into a
single pass (drops the redundant default-augmentor call per link); and whether to offer a
`fromSortedWithDuplicates` that coalesces equal keys instead of rejecting them (SBS de-dups upstream
today, so this is unneeded until a caller wants otherwise).

**Follow-on (same ADR):** the `resyncFromEngine` → direct size/window trim landed as a refinement
*after* the first green build; it removes the extra `inOrder()` pass and the window population for
unbounded sets. Verify on the next `./gradlew build`.

## 5. Action items

1. [x] `RedBlackTree.buildBalanced` + private `buildBalancedNode` (deepest-level-red colouring, local links).
2. [x] `OrderedSet.fromSorted` / `fromSortedNatural` / `buildFromSorted` (validate empty + strictly ascending).
3. [x] `BulkBuildTest`: RB validity (`blackHeight`, `StrategyHealthCheck`), order-stat parity with repeated `add`, input rejection, jqwik oracle over random sizes.
4. [x] Consumer: SuperBeefSort feeds via `FeedMode.BULK` / `BulkBuildFeeder` (empty-`OrderedSet` fast path, balanced-add fallback for non-empty / ensemble targets).
5. [ ] Host-side: commit `OrderedSet.java`, `RedBlackTree.java`, `BulkBuildTest.java`, this ADR, and a `CHANGELOG-2026-06-14-adr014-bulk-build.md`; push so SuperBeefSort's CI sees the new methods.
6. [ ] If a JMH feed benchmark shows the build still augmentation-bound, do the single-pass size/augment fusion from §4.
