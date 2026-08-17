package io.github.richeyworks.csrbt.strategy;

import io.github.richeyworks.csrbt.MutableTree;
import io.github.richeyworks.csrbt.TreeNode1;

public interface TreeStrategy<K> {

    /**
     * BST insertion only — links node into tree, calls tree.setRoot() if needed.
     * Must NOT fix RB/AVL invariants; that belongs in fixInsert.
     */
    void insert(MutableTree<K> tree, TreeNode1<K> node);

    /**
     * Restore invariants after insertion.
     * RB: recolor/rotate + force root BLACK.
     * AVL: recompute heights + rotate.
     * Splay: splay node to root.
     */
    void fixInsert(MutableTree<K> tree, TreeNode1<K> node);

    void delete(MutableTree<K> tree, TreeNode1<K> node);

    TreeNode1<K> search(MutableTree<K> tree, K value);

    /**
     * Strategy-supplied structural invariant (ADR-011 V1): an empty list when the tree
     * satisfies <em>this strategy's</em> invariant, else one message per violation. The
     * health gate calls this for strategies its built-in switch doesn't know — which is
     * what lets a <em>parameterized</em> strategy (e.g. {@code WeightBalancedStrategy(Δ,Γ)})
     * be validated against its own parameters, and what makes an unsound parameter point
     * self-disqualifying instead of silently wrong. The default reports nothing: the
     * classic strategies are validated by the gate's built-in checks.
     */
    default java.util.List<String> validateInvariant(MutableTree<K> tree) {
        return java.util.List.of();
    }

    /**
     * Policy identity (ADR-011 V3): true when {@code other} encodes the <em>same balancing
     * policy</em>, parameters included — the test {@code OrderedSet.setStrategy} uses for
     * its same-strategy no-op guard. The default — class identity — is exact for the
     * classic, parameterless strategies; a parameterized strategy must override it
     * (class identity alone would make {@code WB(3,2) → WB(4,2)} look like a no-op and
     * silently refuse a real morph, which is how this seam was discovered).
     */
    default boolean samePolicyAs(TreeStrategy<K> other) {
        return other != null && getClass() == other.getClass();
    }

    // ── Rotations: structurally identical across all three algorithms ─────────
    // AVLStrategy no longer needs to call `new RedBlackStrategy().rotateLeft()`

    // ── Which caches a rotation refreshes, and which it does NOT ──────────────
    //
    // Both rotations link through the *Local setters, which recompute size, augment,
    // height and black-height for the TOUCHED nodes only — they never walk to the
    // root. That is what keeps a rotation O(1) and an insert O(height) instead of
    // O(height²); insert/delete BST links still use the propagating
    // setLeft/setRight. The consequences differ per cached quantity:
    //
    //   size / augmentedValue — CORRECT for every node afterwards. A rotation permutes
    //       a local pair (x, y) without changing which keys live under any ancestor, so
    //       no ancestor's subtree size or subtree augment can change. The ancestor that
    //       adopts the new subtree root keeps exactly the same descendants, which is why
    //       it too is linked locally. Order statistics therefore stay exact.
    //
    //   height / blackHeight — MAY GO STALE for ancestors. A rotation can change the
    //       height of the rotated subtree's root, and that genuinely propagates upward,
    //       but nothing here propagates it. AVLStrategy and HybridStrategy mask this:
    //       their rebalance passes call TreeNode1.refreshHeight() on every node from the
    //       modification point up to the root after rotating, so the cache is current by
    //       the time they read a balance factor. RedBlackStrategy and
    //       WeightBalancedStrategy do not rebalance by height and never refresh it, so on
    //       those strategies TreeNode1.getHeight() / getBlackHeight() on an ANCESTOR of a
    //       rotation can read high until the next propagating link refreshes that path.
    //       (Reproduced in AUDIT-2026-08-17 finding 21: an RB node reporting height 5
    //       where the real height is 4.) Callers wanting a trustworthy height on those
    //       strategies must recompute it — TreeNode1.refreshHeight() bottom-up, or an
    //       O(n) walk — rather than trust the cached accessor.
    //
    // Propagating heights from here was deliberately deferred (AUDIT-2026-08-14 F-1):
    // it would restore the O(height) rotation cost this design exists to remove, and no
    // in-tree consumer needs an ancestor height mid-rotation. The limitation is documented
    // rather than fixed; do not "fix" it by switching to the propagating setters without
    // re-measuring the insert path.

    default void rotateLeft(MutableTree<K> tree, TreeNode1<K> x) {
        TreeNode1<K> y      = x.getRight();
        TreeNode1<K> nil    = tree.getNIL();
        TreeNode1<K> parent = x.getParent();     // capture BEFORE relinking

        // Move y's left subtree to be x's right child, then recompute x.
        TreeNode1<K> yLeft = y.getLeft();
        x.setRightLocal(yLeft);
        if (yLeft != nil) yLeft.setParent(x);

        // Put x under y and recompute y (x is already correct → bottom-up order).
        y.setLeftLocal(x);   // also sets x.parent = y

        // Attach y under x's old parent and recompute that parent with correct y.
        y.setParent(parent);
        if      (parent == nil)               tree.setRoot(y);
        else if (x == parent.getLeft())       parent.setLeftLocal(y);
        else                                  parent.setRightLocal(y);

        tree.onRotation();   // meter structural churn (see MutableTree#onRotation)
    }

    default void rotateRight(MutableTree<K> tree, TreeNode1<K> y) {
        TreeNode1<K> x      = y.getLeft();
        TreeNode1<K> nil    = tree.getNIL();
        TreeNode1<K> parent = y.getParent();     // capture BEFORE relinking

        TreeNode1<K> xRight = x.getRight();
        y.setLeftLocal(xRight);
        if (xRight != nil) xRight.setParent(y);

        x.setRightLocal(y);  // also sets y.parent = x

        x.setParent(parent);
        if      (parent == nil)               tree.setRoot(x);
        else if (y == parent.getRight())      parent.setRightLocal(x);
        else                                  parent.setLeftLocal(x);

        tree.onRotation();   // meter structural churn (see MutableTree#onRotation)
    }
}
