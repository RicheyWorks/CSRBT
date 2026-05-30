package core.strategy;

import core.MutableTree;
import core.TreeNode1;

public interface TreeStrategy {

    /**
     * BST insertion only — links node into tree, calls tree.setRoot() if needed.
     * Must NOT fix RB/AVL invariants; that belongs in fixInsert.
     */
    void insert(MutableTree tree, TreeNode1 node);

    /**
     * Restore invariants after insertion.
     * RB: recolor/rotate + force root BLACK.
     * AVL: recompute heights + rotate.
     * Splay: splay node to root.
     */
    void fixInsert(MutableTree tree, TreeNode1 node);

    void delete(MutableTree tree, TreeNode1 node);

    TreeNode1 search(MutableTree tree, int value);

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

    default void rotateLeft(MutableTree tree, TreeNode1 x) {
        TreeNode1 y      = x.getRight();
        TreeNode1 nil    = tree.getNIL();
        TreeNode1 parent = x.getParent();        // capture BEFORE relinking

        // Move y's left subtree to be x's right child, then recompute x.
        TreeNode1 yLeft = y.getLeft();
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

    default void rotateRight(MutableTree tree, TreeNode1 y) {
        TreeNode1 x      = y.getLeft();
        TreeNode1 nil    = tree.getNIL();
        TreeNode1 parent = y.getParent();        // capture BEFORE relinking

        TreeNode1 xRight = x.getRight();
        y.setLeftLocal(xRight);
        if (xRight != nil) xRight.setParent(y);

        x.setRightLocal(y);  // also sets y.parent = x

        x.setParent(parent);
        if      (parent == nil)               tree.setRoot(x);
        else if (y == parent.getRight())      parent.setRightLocal(x);
        else                                  parent.setLeftLocal(x);
    }
}
