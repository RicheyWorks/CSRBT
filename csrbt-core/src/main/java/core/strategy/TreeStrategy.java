package core.strategy;

import core.MutableTree;
import core.TreeNode1;

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

    // Rotations use the *Local link variants: a rotation rearranges a local
    // pair (x, y) but does not change the subtree-size of any ancestor, so the
    // augment must be recomputed only for the touched nodes, never propagated to
    // the root. The ancestor that adopts the new subtree root keeps the same set
    // of descendants (augment unchanged), so it is linked locally too. This is
    // what drops a rotation from O(height) to O(1) and an insert from O(height²)
    // to O(height). Insert/delete BST links still use the propagating
    // setLeft/setRight, which is where ancestor counts genuinely change.

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
    }
}
