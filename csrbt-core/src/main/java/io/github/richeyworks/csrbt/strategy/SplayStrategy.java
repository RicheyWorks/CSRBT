package io.github.richeyworks.csrbt.strategy;

import io.github.richeyworks.csrbt.MutableTree;
import io.github.richeyworks.csrbt.TreeNode1;
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
public class SplayStrategy<K> implements TreeStrategy<K> {

    private static final Logger logger = LogManager.getLogger(SplayStrategy.class);

    // ── Insert ────────────────────────────────────────────────────────────────

    @Override
    public void insert(MutableTree<K> tree, TreeNode1<K> newNode) {
        newNode.setColor(TreeNode1.Color.BLACK);

        TreeNode1<K> nil = tree.getNIL();
        TreeNode1<K> y = nil;                 // "no parent" is the sentinel, never null
        TreeNode1<K> x = tree.getRoot();

        int cmp = 0;                          // one comparison per step; the last one aims the link
        while (!x.isNil()) {
            y = x;
            cmp = newNode.compareTo(x);
            if (cmp == 0) {
                // DEBUG, not WARN — hot-path + battle-timing fairness (see RedBlackStrategy).
                logger.debug("Splay duplicate insert skipped: {}", newNode.getData());
                splay(tree, x);               // duplicate touch still bubbles — abort UNLINKED
                return;
            }
            x = (cmp < 0) ? x.getLeft() : x.getRight();
        }

        newNode.setParent(y);
        if (y.isNil()) {
            tree.setRoot(newNode);
        } else if (cmp < 0) {
            y.linkLeft(newNode);       // ADR-028: the splay below is the only height maintainer
        } else {
            y.linkRight(newNode);
        }

        splay(tree, newNode);
    }

    /** Splay already happened in insert — nothing left to do. */
    @Override
    public void fixInsert(MutableTree<K> tree, TreeNode1<K> node) {
        // no-op
    }

    // ── Search ────────────────────────────────────────────────────────────────

    /**
     * BST search + splay the found node (or last-visited node on miss).
     * Splay-on-miss is the standard move-to-root heuristic; it keeps
     * recently-accessed paths short even when the key is absent.
     */
    @Override
    public TreeNode1<K> search(MutableTree<K> tree, K value) {
        TreeNode1<K> current = tree.getRoot();
        TreeNode1<K> last    = tree.getNIL();

        while (!current.isNil()) {
            last = current;
            int cmp = current.compareKeyTo(value);   // sign of (current.key - value)
            if (cmp == 0) {
                splay(tree, current);
                return current;
            }
            current = (cmp > 0) ? current.getLeft() : current.getRight();   // current.key > value → go left
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
    public void delete(MutableTree<K> tree, TreeNode1<K> z) {
        splay(tree, z);

        TreeNode1<K> nil      = tree.getNIL();
        TreeNode1<K> leftSub  = z.getLeft();
        TreeNode1<K> rightSub = z.getRight();

        // Detach subtrees from the node being removed. A detached subtree root's
        // parent is the sentinel (the uniform "no parent" marker), not null.
        if (!leftSub.isNil())  leftSub.setParent(nil);
        if (!rightSub.isNil()) rightSub.setParent(nil);

        // Sever z's own child pointers so it is fully isolated
        z.safeSetLeft(tree.getNIL());
        z.safeSetRight(tree.getNIL());

        if (leftSub.isNil()) {
            // No left subtree — right subtree becomes the tree
            tree.setRoot(rightSub);

        } else {
            // Install left subtree as the tree, splay its max to the root
            tree.setRoot(leftSub);
            TreeNode1<K> maxLeft = treeMaximum(leftSub, tree.getNIL());
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
    private void splay(MutableTree<K> tree, TreeNode1<K> x) {
        // ADR-028: this loop is also the ONLY height maintainer on the splay write path —
        // insert links with linkLeft/linkRight, which propagate size and augment but no height.
        // The bottom-up argument below covers that too: the link parent is the first node the
        // first rotation recomputes, and every node above it follows.
        //
        // ADR-023: the *Local rotation primitives are correct here, by the structure of
        // splaying rather than by an explicit refresh pass. This loop runs until x is the tree
        // root; each zig / zig-zig / zig-zag recomputes the new subtree root and the parent
        // that adopts it, bottom-up, and the next iteration recomputes that parent again from
        // one level higher — so when the loop ends, every node on the original access path
        // (the only nodes whose subtrees changed) has been recomputed after all of its
        // descendants were final. Paying the height-carrying climb per rotation here would
        // also be the most expensive place to pay it: splaying fires ~20 rotations per
        // operation, and ADR-023 measured that variant at +25%/+30% on Splay alone.
        while (x.getParent() != null && !x.getParent().isNil()) {
            TreeNode1<K> p = x.getParent();
            TreeNode1<K> g = p.getParent();

            boolean pIsRoot = (g == null || g.isNil());

            if (pIsRoot) {
                // ── Zig ──────────────────────────────────────────────────────
                if (x == p.getLeft()) rotateRightLocal(tree, p);
                else                  rotateLeftLocal(tree, p);

            } else if (x == p.getLeft() && p == g.getLeft()) {
                // ── Zig-Zig (LL): rotate grandparent first, then parent ───────
                rotateRightLocal(tree, g);
                rotateRightLocal(tree, p);

            } else if (x == p.getRight() && p == g.getRight()) {
                // ── Zig-Zig (RR) ─────────────────────────────────────────────
                rotateLeftLocal(tree, g);
                rotateLeftLocal(tree, p);

            } else if (x == p.getRight() && p == g.getLeft()) {
                // ── Zig-Zag (LR): rotate parent left, then grandparent right ──
                rotateLeftLocal(tree, p);
                rotateRightLocal(tree, g);

            } else {
                // ── Zig-Zag (RL): rotate parent right, then grandparent left ──
                rotateRightLocal(tree, p);
                rotateLeftLocal(tree, g);
            }
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    /** Rightmost (maximum) node in the subtree rooted at {@code node}. */
    private TreeNode1<K> treeMaximum(TreeNode1<K> node, TreeNode1<K> nil) {
        while (!node.getRight().isNil()) node = node.getRight();
        return node;
    }
}
