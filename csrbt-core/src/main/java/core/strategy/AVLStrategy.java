package core.strategy;

import core.MutableTree;
import core.TreeNode1;

/**
 * AVL tree strategy backed by the shared MutableTree / TreeNode1 skeleton.
 *
 * Height is maintained automatically by TreeNode1.setLeft() / setRight(),
 * so we only need to read node.getHeight() here — no manual tracking.
 *
 * Balance factor:  bf = height(left) − height(right)
 *   bf ∈ {-1, 0, 1}  → balanced
 *   bf =  2          → left-heavy  (LL or LR fix)
 *   bf = -2          → right-heavy (RR or RL fix)
 *
 * Color is irrelevant for AVL; every node is set BLACK on insert so the
 * shared diagnostics don't flag spurious red-red violations.
 */
public class AVLStrategy<K> implements TreeStrategy<K> {

    // ── Insert ────────────────────────────────────────────────────────────────

    /**
     * Standard BST link.  fixInsert walks up and rebalances.
     */
    @Override
    public void insert(MutableTree<K> tree, TreeNode1<K> node) {
        TreeNode1<K> nil    = tree.getNIL();
        TreeNode1<K> parent = nil;
        TreeNode1<K> cur    = tree.getRoot();

        while (!cur.isNil()) {
            parent = cur;
            int cmp = node.compareTo(cur);
            if      (cmp < 0) cur = cur.getLeft();
            else if (cmp > 0) cur = cur.getRight();
            else return;   // duplicate — ignore
        }

        node.setColor(TreeNode1.Color.BLACK);   // AVL doesn't use red/black
        node.setParent(parent);

        if (parent.isNil()) {
            tree.setRoot(node);
        } else if (node.compareTo(parent) < 0) {
            parent.setLeft(node);
        } else {
            parent.setRight(node);
        }
    }

    /**
     * Walk from the newly inserted node upward, rebalancing as needed.
     */
    @Override
    public void fixInsert(MutableTree<K> tree, TreeNode1<K> node) {
        rebalanceUp(tree, node.getParent());
    }

    // ── Delete ────────────────────────────────────────────────────────────────

    @Override
    public void delete(MutableTree<K> tree, TreeNode1<K> node) {
        TreeNode1<K> rebalanceFrom;

        if (node.getLeft().isNil()) {
            // Case 1: no left child — promote right subtree
            rebalanceFrom = node.getParent();
            transplant(tree, node, node.getRight());

        } else if (node.getRight().isNil()) {
            // Case 2: no right child — promote left subtree
            rebalanceFrom = node.getParent();
            transplant(tree, node, node.getLeft());

        } else {
            // Case 3: two children — replace with in-order successor
            TreeNode1<K> successor = minimum(node.getRight());
            rebalanceFrom = (successor.getParent() == node) ? successor
                                                             : successor.getParent();

            if (successor.getParent() != node) {
                // Detach successor from its current position
                transplant(tree, successor, successor.getRight());
                // Local link: successor's parent pointer is still stale and points
                // into node.getRight()'s subtree here, so a propagating setRight
                // would walk a cyclic parent chain and loop forever. transplant
                // below fixes the parent; setLeft then propagates the augment up.
                successor.setRightLocal(node.getRight());
                successor.getRight().setParent(successor);
            }
            transplant(tree, node, successor);
            successor.setLeft(node.getLeft());
            successor.getLeft().setParent(successor);
            successor.setColor(TreeNode1.Color.BLACK);
        }

        rebalanceUp(tree, rebalanceFrom);
    }

    // ── Search ────────────────────────────────────────────────────────────────

    @Override
    public TreeNode1<K> search(MutableTree<K> tree, K value) {
        TreeNode1<K> cur = tree.getRoot();
        while (!cur.isNil()) {
            int cmp = cur.compareKeyTo(value);   // sign of (cur.key - value)
            if      (cmp == 0) return cur;
            else if (cmp >  0) cur = cur.getLeft();    // cur.key > value → go left
            else               cur = cur.getRight();
        }
        return tree.getNIL();
    }

    // ── Core AVL rebalance ────────────────────────────────────────────────────

    /**
     * Walk from {@code start} to the root, fixing any node whose balance
     * factor leaves {-1, 0, 1}.
     *
     * After a rotation the displaced node moved DOWN; we continue from its
     * new parent (the subtree root that took its place) and keep ascending.
     */
    private void rebalanceUp(MutableTree<K> tree, TreeNode1<K> start) {
        TreeNode1<K> cur = start;
        while (cur != null && !cur.isNil()) {
            // Refresh this node's height from its (already-correct, lower-on-path)
            // children before reading balance factors. Insertion/deletion only
            // updates the immediate parent's height, leaving ancestors stale; the
            // upward walk fixes each node so the parent's bf is computed correctly.
            cur.refreshHeight();
            int bf = balanceFactor(cur);

            if (bf > 1) {
                // Left-heavy
                if (balanceFactor(cur.getLeft()) < 0) {
                    // Left-Right case: first rotate left child left
                    rotateLeft(tree, cur.getLeft());
                }
                // Left-Left (or just-fixed LR) case
                rotateRight(tree, cur);
                // After rotateRight, cur slid DOWN — its new parent is the
                // subtree root; continue ascending from there.
                cur = cur.getParent();   // new subtree root

            } else if (bf < -1) {
                // Right-heavy
                if (balanceFactor(cur.getRight()) > 0) {
                    // Right-Left case: first rotate right child right
                    rotateRight(tree, cur.getRight());
                }
                // Right-Right (or just-fixed RL) case
                rotateLeft(tree, cur);
                cur = cur.getParent();   // new subtree root
            }

            // Move up one more level (past the current or newly placed subtree root)
            cur = cur.getParent();
        }
    }

    // ── Private helpers ───────────────────────────────────────────────────────

    /** AVL height: 0 for NIL, node.getHeight() otherwise. */
    private int height(TreeNode1<K> node) {
        return (node == null || node.isNil()) ? 0 : node.getHeight();
    }

    /** balance factor = h(left) − h(right). */
    private int balanceFactor(TreeNode1<K> node) {
        return height(node.getLeft()) - height(node.getRight());
    }

    /**
     * Replaces subtree rooted at {@code u} with subtree rooted at {@code v}.
     * Mirrors CLRS RB-TRANSPLANT — works for any BST variant.
     */
    private void transplant(MutableTree<K> tree, TreeNode1<K> u, TreeNode1<K> v) {
        TreeNode1<K> uParent = u.getParent();
        if (uParent == null || uParent.isNil()) {
            tree.setRoot(v);
        } else if (u == uParent.getLeft()) {
            uParent.setLeft(v);
        } else {
            uParent.setRight(v);
        }
        if (v != null && !v.isNil()) {
            v.setParent(uParent);
        }
    }

    /** Returns the leftmost (minimum) node in the subtree rooted at {@code node}. */
    private TreeNode1<K> minimum(TreeNode1<K> node) {
        while (!node.getLeft().isNil()) node = node.getLeft();
        return node;
    }
}
