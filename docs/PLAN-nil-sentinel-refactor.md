# Implementation plan — #4 (per-tree NIL) + #7 (parent convention)

Status: **planned, not implemented.** Execute only after the build compiles and
the regression suite (`RegressionFixesTest`) is green, because the failure mode
is silent: a single node created against the wrong sentinel breaks `isNil()`
(an identity comparison) everywhere, with no exception thrown.

## Why these two together

`#4` (shared static `TreeNode1.NIL`) and `#7` (root's parent is `null` in
`SplayStrategy` but `NIL` elsewhere) are the same underlying problem: an
inconsistent, shared notion of "the absent node." Fixing one without the other
leaves a mixed convention that is its own bug source. Do them as one change.

## Target design

1. Each `RedBlackTree` owns a **private, per-instance** NIL sentinel.
2. "Absent node" is represented **only** by that sentinel — never by Java
   `null` — for both children and the root's parent.
3. The static `TreeNode1.NIL` is removed (or retained only as a deprecated
   bootstrap and never compared against).

## Current references to migrate (7)

```
RedBlackTree.java   this.NIL = TreeNode1.NIL;                 → TreeNode1.createNil()
TreeContext.java    tree.setRoot(TreeNode1.NIL);   (clear)    → tree.getNIL()
TreeContext.java    tree.setRoot(TreeNode1.NIL);   (selfRepair)→ tree.getNIL()
TreeAgent.java      <uses TreeNode1.NIL>                      → context.getTree().getNIL()
TreeNode1.java      public static final NIL  (definition)     → see step 1
TreeNode1.java      createNil() { return NIL; }               → return new sentinel
TreeNode1.java      isSharedNil(node, nil)                    → keep (already param-based)
```
Already correct (use `tree.getNIL()` / passed `nil`): `TreeCloner`,
`FilePersistenceAdapter`, `OrderStatisticsOps`, all strategies, `TreeDiagnostics`
(except its `blackHeight` helper — see step 5).

## Step-by-step

### 1. TreeNode1 — make sentinels per-instance
- Change `createNil()` to build a fresh sentinel each call:
  ```java
  public static TreeNode1 createNil() { return new TreeNode1(0, Color.BLACK); }
  ```
  (The private `TreeNode1(int,Color)` constructor already sets
  `nilSentinel = this`, `color = BLACK`, `left = right = this`.)
- Remove `public static final TreeNode1 NIL`. If a bootstrap constant is needed
  for tests, keep it but mark `@Deprecated` and never compare nodes to it.

### 2. RedBlackTree — own the sentinel
```java
public RedBlackTree(TreeStrategy strategy) {
    this.strategy = strategy;
    this.NIL      = TreeNode1.createNil();   // per-instance
    this.root     = NIL;
}
```
`getNIL()` already returns this field.

### 3. Route every NIL use through the tree
- `TreeContext.clear()` / `selfRepair()`: `tree.setRoot(tree.getNIL())`.
- `TreeAgent`: replace `TreeNode1.NIL` with `context.getTree().getNIL()`.
- Audit once more: `grep -rn "TreeNode1.NIL" src` must return **zero** hits in
  `main` after this step (other than an optional deprecated bootstrap constant).

### 4. #7 — unify the parent convention (root.parent == NIL, never null)
- `SplayStrategy.insert`: when `y == null` (empty tree), set
  `newNode.setParent(tree.getNIL())` instead of leaving it null; set root.
- `SplayStrategy.splay`: the loop test `x.getParent() != null && !x.getParent().isNil()`
  can become just `!x.getParent().isNil()` once parents are never null.
- `SplayStrategy.delete`: replace `setParent(null)` detach calls with
  `setParent(tree.getNIL())`.
- `TreeNode1`: `getParent()` for a detached/root node should return the tree's
  NIL. Since `TreeNode1` does not hold a tree reference, keep `parent` defaulting
  to `null` internally **but** have every strategy set it to NIL explicitly, and
  change root tests from `== null` to `.isNil()`. Audit the 9 `parent ... null`
  sites (`grep -rn "getParent() == null\|setParent(null)" src`).
- `getGrandparent()`/`getUncle()`/`getSibling()` already fall back to
  `nilSentinel`; once `parent` is NIL-not-null these stay correct.

### 5. TreeDiagnostics.blackHeight helper
- It compares `node == TreeNode1.NIL`. With per-tree NIL this is wrong. Change to
  `node.isNil()` (identity against the node's own sentinel).

## Test plan (add to RegressionFixesTest)
1. **Isolation:** build two `TreeContext`s, mutate A heavily, assert B unchanged
   and both valid — proves no shared-sentinel contamination.
2. **Cross-tree guard:** assert `ctxA.getTree().getNIL() != ctxB.getTree().getNIL()`.
3. **Splay parent convention:** after splay insert/delete, walk every node and
   assert `node.getParent() != null` (root's parent is NIL, not null).
4. Re-run all existing suites — RB validity, AVL balance, order statistics,
   undo/redo, persistence — to catch any missed sentinel route.

## Risk notes
- Highest-risk step is #3: a single missed `TreeNode1.NIL` leaves a node whose
  `nilSentinel` differs from its tree's, so `isNil()` returns false where it must
  return true → infinite loops or corruption, silently. The grep-to-zero gate in
  step 3 is mandatory.
- Persistence files are unaffected (text format references no sentinel identity).
- Do this on a branch; keep the commit isolated so it can be reverted cleanly if
  a test goes red.
