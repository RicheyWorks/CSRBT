# Code Review: CSRBT core engine

> **Update (fixes applied):** #1, #2, and #5 are fixed in the source. #3 and #9
> are intentionally **not** changed — they are intertwined with the undo-history
> and adaptive-morph features, so fixing them is a behavior-changing redesign
> rather than a mechanical fix, and could not be validated without a compiler in
> this environment. See "Fixes applied" at the bottom.


Scope: `src/main/java/core` — engine, strategies, orchestration, persistence,
clone/order-statistics utilities. Reviewed by inspection (no JDK available in
the review environment, so dynamic findings are traced by hand and flagged as
such).

## Summary

The architecture is clean — the `MutableTree` seam genuinely decouples
strategies from the engine, and the order-statistics layer is correct CLRS.
But there are two **correctness bugs that break red-black deletion and AVL
balancing**, plus several **O(n²) hot paths** in the facade that will dominate
real workloads. The concurrency contract documented on `TreeContext` is also
contradicted by the code.

## Critical Issues

| # | File | Line | Issue | Severity |
|---|------|------|-------|----------|
| 1 | TreeNode1.java / RedBlackStrategy.java | 227–231 / 165, 311 | `setParent` silently refuses to set NIL's parent; RB `fixDelete` then dereferences `x.getParent()` on a NIL `x` → NullPointerException on most black-node deletions | 🔴 Critical |
| 2 | TreeNode1.java / AVLStrategy.java | 233–251 / 162–163 | `setLeft/setRight` recompute height for the node only and never propagate height to ancestors; `recomputeAugmentAndPropagate` propagates *augment* but not *height*. AVL balance factors are read from stale ancestor heights → tree can fail to rebalance | 🔴 Critical |
| 3 | TreeContext.java | 87, 274–286 | `add()` calls `cloner.snapshot()` (full deep copy) on every insert, and `updateMetadata` runs full-tree diagnostics every insert → building n elements is O(n²) time and O(n²) memory (every snapshot retained in history) | 🔴 Critical |

### 1 — RB deletion NPE on black leaves (trace)

`TreeNode1.setParent` guards `if (this != nilSentinel)`, so NIL's parent is
never assignable. CLRS RB-DELETE-FIXUP relies on `T.nil.p` being set by
`transplant`. Trace of deleting a **black** node with a NIL replacement in a
non-trivial tree:

1. `delete` → `transplant(z, NIL)` → `v.setParent(uParent)` is a **no-op** (v is NIL).
2. `yOrigColor == BLACK` → `fixDelete(tree, x = NIL)`.
3. `while (x != root && x.isBlack())`: NIL is black and ≠ root → enter loop.
4. `parent = x.getParent()` → NIL.parent is `null` (never set) → `x == parent.getLeft()` throws **NPE**.

Deleting red leaves is fine (no fixup); deleting black leaves — which always
exist in an RB tree — will throw. Fix: give the engine a per-tree NIL whose
parent *is* writable during fixup (standard CLRS sentinel), or special-case the
parent pointer in `fixDelete`/`transplant` instead of relying on the shared
immutable NIL.

### 2 — AVL stale heights

`height` is stored on the node and recomputed inside `setLeft/setRight` for
*that node only*. Insertion calls `setLeft/setRight` on the immediate parent, so
grandparent-and-above heights stay stale. `balanceFactor` reads those stale
stored heights, so `rebalanceUp` can miss imbalances and the tree degrades
toward O(n). Either propagate height up the parent chain (as augment already is)
or compute height on demand from children in `balanceFactor`. The same stale-height
read affects `HybridStrategy.avlRebalanceUp`.

## Suggestions

| # | File | Line | Suggestion | Category |
|---|------|------|------------|----------|
| 1 | TreeNode1.java | 312–319, 233–251 | `recomputeAugmentAndPropagate` walks to the root on *every* `setLeft/setRight`; a single rotation triggers several walks → per-op cost becomes O(log²n). Recompute only the two nodes a rotation actually changes. | Performance |
| 2 | TreeNode1.java | 188–205 | `equals`/`hashCode` are recursive over the whole subtree and depend on mutable fields (color, children). Using nodes as hash keys is O(n) and breaks the hashCode contract once a node mutates. Make identity-based or document "not a map key". | Correctness |
| 3 | TreeContext.java | 121–123, 241 | Doc says reads are unsynchronized "but safe when no writer active", yet `contains/size/inOrder` can NPE or infinite-loop during a concurrent rotation, and `getTree()` hands out the raw mutable engine, letting any caller bypass `lock` entirely. Tighten the contract or remove `getTree()`. | Concurrency |
| 4 | TreeNode1.java | 21, 57–68 | `public static final NIL` is shared across *all* trees and is mutable (color/augment/blackHeight). One tree's diagnostics or `setColor` can contaminate another; also a thread-safety hazard with `deployCloneArmy`. Prefer a per-tree sentinel. | Correctness |
| 5 | FilePersistenceAdapter.java | 175 | `snapshotPath(name)` does not sanitize `name`; `save/load/deleteSnapshot("../../x")` escapes the `snapshots` dir (path traversal). Validate/normalize and confirm the resolved path stays under DIR. | Security |
| 6 | TreeNode1.java | 135–141, 418–426 | `blackHeight()` and `assertValid()` enforce invariants only via `assert`, which is disabled by default at runtime — so these checks effectively never run in production. Use explicit checks where validation matters. | Correctness |
| 7 | SplayStrategy.java vs others | 47–48, 143 | "No parent" is represented as `null` in Splay but as NIL elsewhere; rotations set parent to `x.getParent()` (NIL) while splay tests `parent == null`. This mismatch is a latent bug source — pick one sentinel convention. | Maintainability |
| 8 | FilePersistenceAdapter.java | 98, 106 | `reader.readLine()` results are split without null/format guards; a truncated/empty file relies on the broad `catch (Exception)` to return null. Validate header arity and the data line explicitly. | Correctness |
| 9 | TreeContext.java | 280, HybridStrategy 271/171 | Per-insert full-tree work: `hasNoRedRed()` diagnostics each insert (#3), and `cur.depth()` called per node in `avlRebalanceUp` (O(depth) each) make otherwise-log operations linear. | Performance |

## What Looks Good

- The `MutableTree` interface is a real abstraction seam; strategies depend only
  on `getRoot/setRoot/getNIL/rotate*` and the engine stays swappable.
- `OrderStatisticsOps` is faithful CLRS Ch.14 (OS-SELECT/OS-RANK) with correct
  derived ops (median, percentile, range), assuming the augment is maintained.
- `TreeCloner.deepCopyTwoPass` correctly uses `IdentityHashMap` and a two-pass
  build to avoid the disconnected-tree bug it documents.
- Persistence uses a plain text format, so there is no Java-deserialization
  attack surface.

## Verdict

**Request Changes.** Issues #1 and #2 mean RB delete and AVL balance are not
correct as written, and #3 makes the facade quadratic. Recommend fixing the NIL
parent handling, AVL height propagation, and the per-op snapshot/diagnostics
before relying on this in any workload. I could not compile in this environment
— adding deletion and large-insert tests (and running them) should be the first
step to confirm #1–#3.

## Fixes applied

**#1 — RB delete NPE (FIXED).** `RedBlackStrategy.delete` now computes the
replacement node's parent (`xParent`) at the splice point and threads it into
`fixDelete(tree, x, parent)`. `fixDelete` uses that tracked `parent` instead of
`x.getParent()`, so it no longer dereferences the shared NIL sentinel's unset
parent. Once `x` advances to a real node, `parent` is re-read from it. Standard
CLRS fixup without requiring a writable sentinel.

**#2 — AVL/Hybrid stale heights (FIXED).** Added `TreeNode1.refreshHeight()`
(local, non-throwing recompute from children). `AVLStrategy.rebalanceUp` and
`HybridStrategy.avlRebalanceUp` call it on each node as they walk up, so an
ancestor's cached height is current before its parent's balance factor is read.
The nodes whose height changed on an op are exactly the path the walk visits.

**#5 — Path traversal (FIXED).** `FilePersistenceAdapter.snapshotPath` rejects
null/empty names and any name containing `/`, `\`, or `..`, and verifies the
normalized resolved path's parent is exactly the snapshots directory.

**#3 — snapshot-per-add (FIXED).** `TreeContext.add/remove` no longer deep-copy
the tree; they record a one-int inverse command. `TreeHistory` now undoes ADD
with REMOVE (and vice-versa) via a recording-suppression flag
(`setHistoryRecording`), so recording is O(1) time/memory instead of O(n) per op
(O(n²) to build). Named checkpoints still keep a real snapshot, but their undo
entry stores lightweight before/after key lists rather than a full tree copy.
Added `TreeContext.getHistory()` (undo/redo were previously unreachable).
**Semantics change:** undo now restores tree *contents* (the ordered key set),
not necessarily the exact prior node layout — documented in `TreeHistory`.

**#9 — per-insert O(n) diagnostic (FIXED).** `updateMetadata` now calls
`TreeDiagnostics.hasNoRedRedAt(value)` — an O(log n) check of the inserted
node's parent/children — instead of the whole-tree `hasNoRedRed()` scan. An
insertion can only introduce a red-red violation at the new node's
neighborhood, so the stress signal is unchanged in behavior (correct RB inserts
still never raise it) but the per-insert cost drops from O(n) to O(log n). The
whole-tree scan is retained for `isValidRedBlack` / `selfRepair`.

**#8 — snapshot load hardening (FIXED).** `loadSnapshot` now validates the
header (null/empty file, field count, version, numeric size) and the data line
with specific log messages instead of relying on the broad `catch`. It also
**fixes a latent bug**: a loaded context's `size` was never set (always 0); it
is now restored from the parsed node count, cross-checked against the header.

### Deferred (design change + tests required, not done)

**#6 — assert-only invariants (FIXED).** `TreeNode1.blackHeight()` and
`assertValid()` now perform explicit checks that throw `IllegalStateException`
instead of using `assert` (disabled by default at runtime), so the invariant
validation actually runs. Both methods were otherwise dead/near-dead, so this is
behavior-neutral unless a caller deliberately validates.

**#2 — mutable recursive `equals`/`hashCode` (FIXED).** `TreeNode1` now uses
identity equality (`this == obj`) and `System.identityHashCode`. The old
structural versions were O(n), mutated their hash as the node changed (violating
the `hashCode` contract), and conflated distinct nodes. Identity is also what
the only consumer — the LCA ancestor `HashSet` in `TreeEcology` — actually
needs, so this fixes a latent correctness issue there too.

**#1 — augment propagation O(log²n) (FIXED, most subtle change).** Rotations no
longer propagate the subtree-size augment to the root. New
`TreeNode1.setLeftLocal/setRightLocal` recompute only the touched node, and the
rotation primitives recompute strictly bottom-up (x → y → adopting parent) so no
stale value is read. A rotation drops from O(height) to O(1) augment work and an
insert from O(height²) to O(height). Insert/delete BST links keep the
propagating `setLeft/setRight`, which is where ancestor counts genuinely change.
Correctness is guarded by a new order-statistics test (`select`/`rank` exact
after rotation-heavy inserts and deletes). **This is the change most dependent on
an actual test run — verify before trusting it.**

**#4 (per-tree NIL) + #7 (parent convention) (FIXED).** Each `RedBlackTree` now
owns a per-instance sentinel via `TreeNode1.createNil()` instead of aliasing the
shared static `TreeNode1.NIL`; all engine/facade/util code routes through
`tree.getNIL()` (verified: zero `TreeNode1.NIL` references remain in `main`).
`SplayStrategy` no longer uses `null` for "no parent" — a root/detached subtree's
parent is the sentinel, matching every other strategy — and `TreeNode1.depth()`
now stops at null *or* sentinel so a root has depth 0 under the unified
convention. `TreeDiagnostics.blackHeight` compares via `isNil()` rather than
static identity. The static `TreeNode1.NIL` is retained (documented) only for
standalone/bootstrap and test use. Guarded by per-tree isolation and
splay-parent tests.

> All review items (#1–#9) are now addressed. The remaining open suggestions are
> hygiene/robustness, not correctness blockers.

> Fixes were verified for internal consistency (reference grep) but **not
> compiled or unit-tested** — no JDK was available here. Compile and run delete
> + large-insert tests before relying on them.
