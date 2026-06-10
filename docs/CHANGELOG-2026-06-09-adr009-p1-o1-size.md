# CHANGELOG 2026-06-09 — ADR-009 P1: O(1) size() via the size augment

The one genuinely-broken item from the external review's gap list
(`ADR-009-roadmap-reconciliation-2026-06-09.md`): `RedBlackTree.size()` walked all n nodes
with an explicit stack to count what the root already knew. `TreeNode1.size` is intrinsic
structural metadata, maintained on every structural change, and is the exact augment the
order-statistics walks (`select`/`rank`) have trusted since they existed — so `size()` is now
`root.getSize()`, with the NIL sentinel's size 0 handling the empty tree for free.

`OrderedSet.size()` was already an O(1) counter; only the engine path changes. Any drift
between augment and true count would always have been an order-statistics bug — the new tests
double as a regression floor for the augment itself.

## Tests (`SizeAugmentTest`, 4 tests; suite 461, green)

- Oracle parity on **every op** through 4k random churn ops (duplicates and misses included),
  plus agreement with `inOrder().size()` and reset-on-clear.
- Parity across strategy morphs (RB → AVL → Splay full rebuilds) on both facade and engine
  paths, and across undo/redo replay on the `TreeContext` adapter.
- The before/after row: 20k `size()` calls on a 50k-key tree in **1.41 ms** (sandbox) —
  the O(n) version would have been ~10⁹ node visits.

Next per ADR-009: P2 (`NavigableSet` adapter), P3 (event listener + JSON tree export), G0
(GitHub Actions on the existing Ant build).
