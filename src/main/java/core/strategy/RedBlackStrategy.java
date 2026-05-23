package core.strategy;

import core.RedBlackTree;
import core.TreeNode1;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

/**
 * Classic CLRS Red-Black Tree strategy.
 *
 * Insert  → CLRS 13.3  RB-INSERT + RB-INSERT-FIXUP
 * Delete  → CLRS 13.4  RB-DELETE + RB-DELETE-FIXUP
 * Rotations live as defaults in TreeStrategy and are inherited here.
 */
public class RedBlackStrategy implements TreeStrategy {

    private static final Logger logger = LogManager.getLogger(RedBlackStrategy.class);

    // ── Insert ────────────────────────────────────────────────────────────────

    @Override
    public TreeNode1 insert(RedBlackTree tree, TreeNode1 newNode) {
        TreeNode1 y = null;
        TreeNode1 x = tree.getRoot();

        while (!x.isNil()) {
            y = x;
            if (newNode.getData() == x.getData()) {
                logger.warn("Duplicate insert skipped for value: {}", newNode.getData());
                return x;
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

        newNode.setColor(TreeNode1.Color.RED);
        return newNode;
    }

    /**
     * RB-INSERT-FIXUP — CLRS 13.3
     *
     * Two mirror-image cases depending on whether the parent is a left
     * or right child of the grandparent.  Each case has three sub-cases:
     *
     *   Case 1 — uncle is RED:
     *     Recolor parent, uncle BLACK; grandparent RED; move z up.
     *
     *   Case 2 — uncle is BLACK, z is the "inner" grandchild:
     *     Rotate parent toward the outer side → reduces to Case 3.
     *
     *   Case 3 — uncle is BLACK, z is the "outer" grandchild:
     *     Recolor + rotate grandparent away from z's side.
     *
     * Loop invariant: node is RED.
     * Terminates because either we stop (parent BLACK) or z moves up 2 levels.
     */
    @Override
    public void fixInsert(RedBlackTree tree, TreeNode1 node) {
        while (node != null && !node.getParent().isNil() && node.getParent().isRed()) {
            TreeNode1 parent      = node.getParent();
            TreeNode1 grandparent = node.getGrandparent();

            if (parent == grandparent.getLeft()) {
                // ── LEFT branch ──────────────────────────────────────────────
                TreeNode1 uncle = grandparent.getRight();

                if (!uncle.isNil() && uncle.isRed()) {
                    // Case 1: uncle RED → recolor, move up
                    parent.setColor(TreeNode1.Color.BLACK);
                    uncle.setColor(TreeNode1.Color.BLACK);
                    grandparent.setColor(TreeNode1.Color.RED);
                    node = grandparent;

                } else {
                    if (node == parent.getRight()) {
                        // Case 2: inner grandchild → rotate to straighten
                        node = parent;
                        tree.rotateLeft(node);
                        // refresh after rotation
                        parent      = node.getParent();
                        grandparent = node.getGrandparent();
                    }
                    // Case 3: outer grandchild → recolor + rotate grandparent
                    parent.setColor(TreeNode1.Color.BLACK);
                    grandparent.setColor(TreeNode1.Color.RED);
                    tree.rotateRight(grandparent);
                }

            } else {
                // ── RIGHT branch (symmetric) ──────────────────────────────────
                TreeNode1 uncle = grandparent.getLeft();

                if (!uncle.isNil() && uncle.isRed()) {
                    // Case 1: uncle RED → recolor, move up
                    parent.setColor(TreeNode1.Color.BLACK);
                    uncle.setColor(TreeNode1.Color.BLACK);
                    grandparent.setColor(TreeNode1.Color.RED);
                    node = grandparent;

                } else {
                    if (node == parent.getLeft()) {
                        // Case 2: inner grandchild → rotate to straighten
                        node = parent;
                        tree.rotateRight(node);
                        // refresh after rotation
                        parent      = node.getParent();
                        grandparent = node.getGrandparent();
                    }
                    // Case 3: outer grandchild → recolor + rotate grandparent
                    parent.setColor(TreeNode1.Color.BLACK);
                    grandparent.setColor(TreeNode1.Color.RED);
                    tree.rotateLeft(grandparent);
                }
            }
        }
        // Invariant: root is always BLACK
        tree.getRoot().setColor(TreeNode1.Color.BLACK);
    }

    // ── Delete ────────────────────────────────────────────────────────────────

    /**
     * RB-DELETE — CLRS 13.4
     *
     * Removes {@code z} and restores RB properties via fixDelete when the
     * removed (or moved) node was BLACK (black-height may have dropped by 1).
     *
     *   y = node actually removed from tree (z itself, or z's in-order successor)
     *   x = node that takes y's original position (may be NIL)
     *
     * We track y's original color: if BLACK, call fixDelete on x.
     */
    @Override
    public void delete(RedBlackTree tree, TreeNode1 z) {
        TreeNode1 nil            = tree.getNIL();
        TreeNode1 y              = z;
        TreeNode1.Color yOrigColor = y.getColor();
        TreeNode1 x;

        if (z.getLeft().isNil()) {
            // Case A: no left child
            x = z.getRight();
            transplant(tree, z, z.getRight());

        } else if (z.getRight().isNil()) {
            // Case B: no right child
            x = z.getLeft();
            transplant(tree, z, z.getLeft());

        } else {
            // Case C: two children — find in-order successor (minimum of right subtree)
            y = minimum(z.getRight(), nil);
            yOrigColor = y.getColor();
            x = y.getRight();

            if (y.getParent() == z) {
                // x might be NIL; give it a parent pointer so fixDelete can walk up
                x.setParent(y);
            } else {
                transplant(tree, y, y.getRight());
                y.setRight(z.getRight());
                y.getRight().setParent(y);
            }
            transplant(tree, z, y);
            y.setLeft(z.getLeft());
            y.getLeft().setParent(y);
            y.setColor(z.getColor());
        }

        if (yOrigColor == TreeNode1.Color.BLACK) {
            fixDelete(tree, x);
        }
    }

    /**
     * RB-DELETE-FIXUP — CLRS 13.4
     *
     * x has "extra black" that needs to be pushed up or absorbed.
     * Four cases per side (left / right mirror-images):
     *
     *   Case 1 — sibling w is RED:
     *     Recolor w + parent, rotate parent → reduces to Case 2/3/4.
     *
     *   Case 2 — w is BLACK, both of w's children BLACK:
     *     Remove black from x and w → push extra black up to parent.
     *     If parent was RED, it absorbs and we're done; otherwise loop.
     *
     *   Case 3 — w is BLACK, w's far child BLACK, near child RED:
     *     Recolor w's near child + w, rotate w → reduces to Case 4.
     *
     *   Case 4 — w is BLACK, w's far child RED:
     *     Recolor w = parent's color, parent + far child BLACK, rotate parent.
     *     Extra black is resolved — loop ends.
     */
    private void fixDelete(RedBlackTree tree, TreeNode1 x) {
        TreeNode1 nil = tree.getNIL();

        while (x != tree.getRoot() && x.isBlack()) {
            TreeNode1 parent = x.getParent();

            if (x == parent.getLeft()) {
                // ── LEFT branch ──────────────────────────────────────────────
                TreeNode1 w = parent.getRight();   // sibling

                if (w.isRed()) {
                    // Case 1: sibling RED → recolor + rotate to get BLACK sibling
                    w.setColor(TreeNode1.Color.BLACK);
                    parent.setColor(TreeNode1.Color.RED);
                    tree.rotateLeft(parent);
                    w = x.getParent().getRight();   // new sibling after rotation
                }

                if (w.getLeft().isBlack() && w.getRight().isBlack()) {
                    // Case 2: sibling's children both BLACK → push black up
                    w.setColor(TreeNode1.Color.RED);
                    x = x.getParent();

                } else {
                    if (w.getRight().isBlack()) {
                        // Case 3: far child BLACK, near child RED → straighten
                        w.getLeft().setColor(TreeNode1.Color.BLACK);
                        w.setColor(TreeNode1.Color.RED);
                        tree.rotateRight(w);
                        w = x.getParent().getRight();
                    }
                    // Case 4: far child RED → absorb extra black via rotation
                    w.setColor(x.getParent().getColor());
                    x.getParent().setColor(TreeNode1.Color.BLACK);
                    w.getRight().setColor(TreeNode1.Color.BLACK);
                    tree.rotateLeft(x.getParent());
                    x = tree.getRoot();   // done
                }

            } else {
                // ── RIGHT branch (symmetric) ──────────────────────────────────
                TreeNode1 w = parent.getLeft();    // sibling

                if (w.isRed()) {
                    // Case 1
                    w.setColor(TreeNode1.Color.BLACK);
                    parent.setColor(TreeNode1.Color.RED);
                    tree.rotateRight(parent);
                    w = x.getParent().getLeft();
                }

                if (w.getRight().isBlack() && w.getLeft().isBlack()) {
                    // Case 2
                    w.setColor(TreeNode1.Color.RED);
                    x = x.getParent();

                } else {
                    if (w.getLeft().isBlack()) {
                        // Case 3
                        w.getRight().setColor(TreeNode1.Color.BLACK);
                        w.setColor(TreeNode1.Color.RED);
                        tree.rotateLeft(w);
                        w = x.getParent().getLeft();
                    }
                    // Case 4
                    w.setColor(x.getParent().getColor());
                    x.getParent().setColor(TreeNode1.Color.BLACK);
                    w.getLeft().setColor(TreeNode1.Color.BLACK);
                    tree.rotateRight(x.getParent());
                    x = tree.getRoot();   // done
                }
            }
        }
        // x absorbed the extra black
        x.setColor(TreeNode1.Color.BLACK);
    }

    // ── Search ────────────────────────────────────────────────────────────────

    @Override
    public TreeNode1 search(RedBlackTree tree, int value) {
        TreeNode1 cur = tree.getRoot();
        while (!cur.isNil()) {
            int cmp = value - cur.getData();
            if      (cmp == 0) return cur;
            else if (cmp <  0) cur = cur.getLeft();
            else               cur = cur.getRight();
        }
        return tree.getNIL();
    }

    // ── Private helpers ───────────────────────────────────────────────────────

    /**
     * RB-TRANSPLANT — CLRS 13.4
     * Replaces subtree rooted at u with subtree rooted at v.
     * Does NOT update v's left/right children — caller's responsibility.
     */
    private void transplant(RedBlackTree tree, TreeNode1 u, TreeNode1 v) {
        TreeNode1 uParent = u.getParent();
        if (uParent == null || uParent.isNil()) {
            tree.setRoot(v);
        } else if (u == uParent.getLeft()) {
            uParent.setLeft(v);
        } else {
            uParent.setRight(v);
        }
        // Always set v's parent (even if v is NIL — fixDelete needs the pointer)
        v.setParent(uParent);
    }

    /** Leftmost node in the subtree rooted at {@code node}. */
    private TreeNode1 minimum(TreeNode1 node, TreeNode1 nil) {
        while (!node.getLeft().isNil()) node = node.getLeft();
        return node;
    }
}
