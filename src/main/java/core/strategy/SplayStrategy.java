package core.strategy;

import core.MutableTree;
import core.TreeNode1;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

/**
 * Splay Tree Strategy.
 *
 * Every access (insert, delete, search) splays the accessed node to the root,
 * giving amortized O(log n) per operation.
 *
 * Rotation cases:
 *   Zig        — parent is the root (single rotation)
 *   Zig-Zig    — x and parent are both left (or both right) children
 *   Zig-Zag    — x and parent are opposite children (double rotation)
 *
 * Implementation notes:
 *   - Parent == null means "is root" throughout this strategy.
 *   - Color is unused; every node is BLACK to suppress RB diagnostics.
 *   - fixInsert is a no-op — insert() splays during BST link.
 */
public class SplayStrategy implements TreeStrategy {

    private static final Logger logger = LogManager.getLogger(SplayStrategy.class);

    // ── Insert ────────────────────────────────────────────────────────────────

    @Override
    public void insert(MutableTree tree, TreeNode1 newNode) {
        newNode.setColor(TreeNode1.Color.BLACK);

        TreeNode1 y = null;
        TreeNode1 x = tree.getRoot();

        while (!x.isNil()) {
            y = x;
            if (newNode.getData() == x.getData()) {
                logger.warn("Splay duplicate insert skipped: {}", newNode.getData());
                splay(tree, x);
                return;
            }
            x = (newNode.getData() < x.getData()) ? x.getLeft() : x.getRight();
        }

        newNode.setParent(y);
        if (y == null) {
            tree.setRoot(newNode);
        } else if (newNode.getData() < y.getData()) {
            y.safeSetLeft(newNode);
        } else {
            y.safeSetRight(newNode);
        }

        splay(tree, newNode);
    }

    /** Splay already happened in insert — nothing left to do. */
    @Override
    public void fixInsert(MutableTree tree, TreeNode1 node) {
        // no-op
    }

    // ── Search ────────────────────────────────────────────────────────────────

    /**
     * BST search + splay the found node (or last-visited node on miss).
     * Splay-on-miss is the standard move-to-root heuristic; it keeps
     * recently-accessed paths short even when the key is absent.
     */
    @Override
    public TreeNode1 search(MutableTree tree, int value) {
        TreeNode1 current = tree.getRoot();
        TreeNode1 last    = tree.getNIL();

        while (!current.isNil()) {
            last = current;
            int cmp = value - current.getData();
            if (cmp == 0) {
                splay(tree, current);
                return current;
            }
            current = (cmp < 0) ? current.getLeft() : current.getRight();
        }

        if (!last.isNil()) splay(tree, last);   // move-to-root on miss
        return tree.getNIL();
    }

    // ── Delete ────────────────────────────────────────────────────────────────

    /**
     * Splay-tree deletion (split-and-join):
     *
     *  1. Splay z → root.
     *  2. Detach left and right subtrees.
     *  3a. If left is empty  → right becomes the new tree.
     *  3b. Otherwise splay the maximum of the left subtree to its root
     *      (guarantees max.right == NIL), then attach right as max's right child.
     *
     * This avoids any color/black-height bookkeeping.
     */
    @Override
    public void delete(MutableTree tree, TreeNode1 z) {
        splay(tree, z);

        TreeNode1 leftSub  = z.getLeft();
        TreeNode1 rightSub = z.getRight();

        // Detach subtrees from the node being removed
        if (!leftSub.isNil())  leftSub.setParent(null);
        if (!rightSub.isNil()) rightSub.setParent(null);

        // Sever z's own child pointers so it is fully isolated
        z.safeSetLeft(tree.getNIL());
        z.safeSetRight(tree.getNIL());

        if (leftSub.isNil()) {
            // No left subtree — right subtree becomes the tree
            tree.setRoot(rightSub);

        } else {
            // Install left subtree as the tree, splay its max to the root
            tree.setRoot(leftSub);
            TreeNode1 maxLeft = treeMaximum(leftSub, tree.getNIL());
            splay(tree, maxLeft);
            // maxLeft is now root and has no right child — attach right subtree
            maxLeft.safeSetRight(rightSub);
            if (!rightSub.isNil()) rightSub.setParent(maxLeft);
        }
    }

    // ── Splay ─────────────────────────────────────────────────────────────────

    /**
     * Splays {@code x} to the root using Sleator-Tarjan zig / zig-zig / zig-zag.
     *
     * "parent == null" is the root test — consistent with how insert/delete
     * null out the subtree root's parent before handing off to splay.
     */
    private void splay(MutableTree tree, TreeNode1 x) {
        while (x.getParent() != null && !x.getParent().isNil()) {
            TreeNode1 p = x.getParent();
            TreeNode1 g = p.getParent();

            boolean pIsRoot = (g == null || g.isNil());

            if (pIsRoot) {
                // ── Zig ──────────────────────────────────────────────────────
                if (x == p.getLeft()) rotateRight(tree, p);
                else                  rotateLeft(tree, p);

            } else if (x == p.getLeft() && p == g.getLeft()) {
                // ── Zig-Zig (LL): rotate grandparent first, then parent ───────
                rotateRight(tree, g);
                rotateRight(tree, p);

            } else if (x == p.getRight() && p == g.getRight()) {
                // ── Zig-Zig (RR) ─────────────────────────────────────────────
                rotateLeft(tree, g);
                rotateLeft(tree, p);

            } else if (x == p.getRight() && p == g.getLeft()) {
                // ── Zig-Zag (LR): rotate parent left, then grandparent right ──
                rotateLeft(tree, p);
                rotateRight(tree, g);

            } else {
                // ── Zig-Zag (RL): rotate parent right, then grandparent left ──
                rotateRight(tree, p);
                rotateLeft(tree, g);
            }
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    /** Rightmost (maximum) node in the subtree rooted at {@code node}. */
    private TreeNode1 treeMaximum(TreeNode1 node, TreeNode1 nil) {
        while (!node.getRight().isNil()) node = node.getRight();
        return node;
    }
}
