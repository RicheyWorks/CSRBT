package core.strategy;

import core.RedBlackTree;
import core.TreeNode1;

public interface TreeStrategy {

    /**
     * BST insertion only — links node into tree, calls tree.setRoot() if needed.
     * Must NOT fix RB/AVL invariants; that belongs in fixInsert.
     */
    void insert(RedBlackTree tree, TreeNode1 node);

    /**
     * Restore invariants after insertion.
     * RB: recolor/rotate + force root BLACK.
     * AVL: recompute heights + rotate.
     * Splay: splay node to root.
     */
    void fixInsert(RedBlackTree tree, TreeNode1 node);

    void delete(RedBlackTree tree, TreeNode1 node);

    TreeNode1 search(RedBlackTree tree, int value);

    // ── Rotations: structurally identical across all three algorithms ─────────
    // AVLStrategy no longer needs to call `new RedBlackStrategy().rotateLeft()`

    default void rotateLeft(RedBlackTree tree, TreeNode1 x) {
        TreeNode1 y   = x.getRight();
        TreeNode1 nil = tree.getNIL();

        x.setRight(y.getLeft());
        if (y.getLeft() != nil) y.getLeft().setParent(x);

        y.setParent(x.getParent());
        if      (x.getParent() == nil)              tree.setRoot(y);
        else if (x == x.getParent().getLeft())      x.getParent().setLeft(y);
        else                                        x.getParent().setRight(y);

        y.setLeft(x);
        x.setParent(y);
    }

    default void rotateRight(RedBlackTree tree, TreeNode1 y) {
        TreeNode1 x   = y.getLeft();
        TreeNode1 nil = tree.getNIL();

        y.setLeft(x.getRight());
        if (x.getRight() != nil) x.getRight().setParent(y);

        x.setParent(y.getParent());
        if      (y.getParent() == nil)              tree.setRoot(x);
        else if (y == y.getParent().getRight())     y.getParent().setRight(x);
        else                                        y.getParent().setLeft(x);

        x.setRight(y);
        y.setParent(x);
    }
}
