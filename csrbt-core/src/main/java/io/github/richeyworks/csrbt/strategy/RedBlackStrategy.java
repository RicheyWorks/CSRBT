package io.github.richeyworks.csrbt.strategy;

import io.github.richeyworks.csrbt.MutableTree;
import io.github.richeyworks.csrbt.TreeNode1;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

/**
 * Classic CLRS Red-Black Tree strategy.
 *
 * Insert  → CLRS 13.3  RB-INSERT + RB-INSERT-FIXUP
 * Delete  → CLRS 13.4  RB-DELETE + RB-DELETE-FIXUP
 * Rotations live as defaults in TreeStrategy and are inherited here.
 */
public class RedBlackStrategy<K> implements TreeStrategy<K> {

    private static final Logger logger = LogManager.getLogger(RedBlackStrategy.class);

    // ── Insert ────────────────────────────────────────────────────────────────

    @Override
    public void insert(MutableTree<K> tree, TreeNode1<K> newNode) {
        TreeNode1<K> nil = tree.getNIL();
        TreeNode1<K> y = nil;              // "no parent" is the sentinel, never null,
        TreeNode1<K> x = tree.getRoot();   // so the root's parent is NIL and fixInsert terminates cleanly

        int cmp = 0;                       // one comparison per step; the last one aims the link
        while (!x.isNil()) {
            y = x;
            cmp = newNode.compareTo(x);
            if (cmp == 0) {
                // DEBUG, not WARN: per-op logging on the insert hot path (hardening rule
                // M-3), and under the test config (root=WARN, console) a WARN here made
                // RB/Splay/Hybrid pay console-write cost per duplicate while AVL (silent
                // duplicate handling) paid nothing — a systematic timing bias in
                // duplicate-heavy battle workloads (ADR-022 fairness).
                logger.debug("Duplicate insert skipped for value: {}", newNode.getData());
                return;                    // abort UNLINKED — addIfAbsent reads this back
            }
            x = (cmp < 0) ? x.getLeft() : x.getRight();
        }

        newNode.setParent(y);
        if (y.isNil()) {
            tree.setRoot(newNode);
        } else if (cmp < 0) {
            y.linkLeft(newNode);        // ADR-028: height is repaired once, at the end of fixInsert
        } else {
            y.linkRight(newNode);
        }

        newNode.setColor(TreeNode1.Color.RED);
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
    public void fixInsert(MutableTree<K> tree, TreeNode1<K> node) {
        // ADR-028: the newly linked node is this write's height anchor. The BST link above
        // used linkLeft/linkRight (no height propagation) and the fixup below rotates through
        // the *Local primitives, so the whole write maintains height exactly once — the
        // repairHeightUpward() climb at the bottom of this method.
        final TreeNode1<K> anchor = node;
        TreeNode1<K> rotationMark = null;   // adopter of the highest rotation this fixup fires
        while (node != null && node.getParent() != null
                && !node.getParent().isNil() && node.getParent().isRed()) {
            TreeNode1<K> parent      = node.getParent();
            TreeNode1<K> grandparent = node.getGrandparent();

            if (parent == grandparent.getLeft()) {
                // ── LEFT branch ──────────────────────────────────────────────
                TreeNode1<K> uncle = grandparent.getRight();

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
                        rotateLeftLocal(tree, node);
                        rotationMark = rotationAdopter(node);
                        // refresh after rotation
                        parent      = node.getParent();
                        grandparent = node.getGrandparent();
                    }
                    // Case 3: outer grandchild → recolor + rotate grandparent
                    parent.setColor(TreeNode1.Color.BLACK);
                    grandparent.setColor(TreeNode1.Color.RED);
                    rotateRightLocal(tree, grandparent);
                    rotationMark = rotationAdopter(grandparent);
                }

            } else {
                // ── RIGHT branch (symmetric) ──────────────────────────────────
                TreeNode1<K> uncle = grandparent.getLeft();

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
                        rotateRightLocal(tree, node);
                        rotationMark = rotationAdopter(node);
                        // refresh after rotation
                        parent      = node.getParent();
                        grandparent = node.getGrandparent();
                    }
                    // Case 3: outer grandchild → recolor + rotate grandparent
                    parent.setColor(TreeNode1.Color.BLACK);
                    grandparent.setColor(TreeNode1.Color.RED);
                    rotateLeftLocal(tree, grandparent);
                    rotationMark = rotationAdopter(grandparent);
                }
            }
        }
        // Invariant: root is always BLACK
        tree.getRoot().setColor(TreeNode1.Color.BLACK);
        anchor.repairHeightUpward(rotationMark);   // ADR-028: the one height climb this write pays
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
    public void delete(MutableTree<K> tree, TreeNode1<K> z) {
        TreeNode1<K> nil            = tree.getNIL();
        TreeNode1<K> y              = z;
        TreeNode1.Color yOrigColor = y.getColor();
        TreeNode1<K> x;
        // Parent of x is tracked explicitly: the shared NIL sentinel refuses to
        // store a parent pointer (TreeNode1.setParent guards `this != nilSentinel`),
        // so fixDelete must not rely on x.getParent() when x is NIL. CLRS sets
        // T.nil.p; here we thread that value through instead.
        TreeNode1<K> xParent;
        // ADR-028: when the successor is spliced into z's place it becomes a SECOND origin of
        // height change — one the climb from xParent cannot see, because nothing between the
        // two writes a height. It gets its own (near-always one-level) repair below.
        TreeNode1<K> spliced = null;

        if (z.getLeft().isNil()) {
            // Case A: no left child
            x       = z.getRight();
            xParent = z.getParent();
            transplant(tree, z, z.getRight());

        } else if (z.getRight().isNil()) {
            // Case B: no right child
            x       = z.getLeft();
            xParent = z.getParent();
            transplant(tree, z, z.getLeft());

        } else {
            // Case C: two children — find in-order successor (minimum of right subtree)
            y = minimum(z.getRight(), nil);
            yOrigColor = y.getColor();
            x = y.getRight();

            if (y.getParent() == z) {
                // x's parent after the splice is y (which moves into z's place)
                xParent = y;
                x.setParent(y);   // harmless no-op when x is NIL; real link otherwise
            } else {
                xParent = y.getParent();
                transplant(tree, y, y.getRight());
                // Local link (no upward augment walk): at this point y's own
                // parent pointer is still stale and points INTO z.getRight()'s
                // subtree, so a propagating linkRight would walk a temporarily
                // cyclic parent chain (y → … → z.right → y) and loop forever.
                // transplant(z, y) below fixes y.parent, and the subsequent
                // linkLeft refreshes the augment up to the root.
                y.setRightLocal(z.getRight());
                y.getRight().setParent(y);
            }
            transplant(tree, z, y);
            y.linkLeft(z.getLeft());
            y.getLeft().setParent(y);
            y.setColor(z.getColor());
            spliced = y;
        }

        TreeNode1<K> rotationMark = null;
        if (yOrigColor == TreeNode1.Color.BLACK) {
            rotationMark = fixDelete(tree, x, xParent);
        }
        // ADR-028: xParent is the deepest node this write structurally touched, so one climb
        // from it — unconditional through the highest rotation the fixup fired, fixed-point
        // above that — restores every cached height this write disturbed.
        if (xParent != null) xParent.repairHeightUpward(rotationMark);
        if (spliced != null && spliced != xParent) spliced.repairHeightUpward(null);
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
     *
     * Every case assumes CLRS's precondition {@code w != T.nil}, which holds only on a
     * red-black-VALID tree; {@link #cannotRebalance} is the tripwire for trees that
     * arrived by another route. See its javadoc (audit 2026-08-17, finding 2).
     */
    private TreeNode1<K> fixDelete(MutableTree<K> tree, TreeNode1<K> x, TreeNode1<K> parent) {
        TreeNode1<K> rotationMark = null;   // ADR-028: adopter of the highest rotation fired
        // `parent` is x's parent, threaded in by the caller so this works even
        // when x is the shared NIL sentinel (whose own parent pointer is never
        // stored). Once x advances to a real node we re-read parent from it.
        while (x != tree.getRoot() && x.isBlack()) {

            if (x == parent.getLeft()) {
                // ── LEFT branch ──────────────────────────────────────────────
                TreeNode1<K> w = parent.getRight();   // sibling

                if (w.isRed()) {
                    // Case 1: sibling RED → recolor + rotate to get BLACK sibling
                    w.setColor(TreeNode1.Color.BLACK);
                    parent.setColor(TreeNode1.Color.RED);
                    rotateLeftLocal(tree, parent);
                    rotationMark = rotationAdopter(parent);
                    w = parent.getRight();   // new sibling after rotation (parent unchanged)
                }

                if (cannotRebalance(w)) { x = tree.getRoot(); break; }

                if (w.getLeft().isBlack() && w.getRight().isBlack()) {
                    // Case 2: sibling's children both BLACK → push black up
                    w.setColor(TreeNode1.Color.RED);
                    x      = parent;
                    parent = x.getParent();   // x is now a real node — safe

                } else {
                    if (w.getRight().isBlack()) {
                        // Case 3: far child BLACK, near child RED → straighten
                        w.getLeft().setColor(TreeNode1.Color.BLACK);
                        w.setColor(TreeNode1.Color.RED);
                        rotateRightLocal(tree, w);
                        rotationMark = rotationAdopter(w);
                        w = parent.getRight();
                    }
                    // Case 4: far child RED → absorb extra black via rotation
                    w.setColor(parent.getColor());
                    parent.setColor(TreeNode1.Color.BLACK);
                    w.getRight().setColor(TreeNode1.Color.BLACK);
                    rotateLeftLocal(tree, parent);
                    rotationMark = rotationAdopter(parent);
                    x = tree.getRoot();   // done
                }

            } else {
                // ── RIGHT branch (symmetric) ──────────────────────────────────
                TreeNode1<K> w = parent.getLeft();    // sibling

                if (w.isRed()) {
                    // Case 1
                    w.setColor(TreeNode1.Color.BLACK);
                    parent.setColor(TreeNode1.Color.RED);
                    rotateRightLocal(tree, parent);
                    rotationMark = rotationAdopter(parent);
                    w = parent.getLeft();
                }

                if (cannotRebalance(w)) { x = tree.getRoot(); break; }

                if (w.getRight().isBlack() && w.getLeft().isBlack()) {
                    // Case 2
                    w.setColor(TreeNode1.Color.RED);
                    x      = parent;
                    parent = x.getParent();

                } else {
                    if (w.getLeft().isBlack()) {
                        // Case 3
                        w.getRight().setColor(TreeNode1.Color.BLACK);
                        w.setColor(TreeNode1.Color.RED);
                        rotateLeftLocal(tree, w);
                        rotationMark = rotationAdopter(w);
                        w = parent.getLeft();
                    }
                    // Case 4
                    w.setColor(parent.getColor());
                    parent.setColor(TreeNode1.Color.BLACK);
                    w.getLeft().setColor(TreeNode1.Color.BLACK);
                    rotateRightLocal(tree, parent);
                    rotationMark = rotationAdopter(parent);
                    x = tree.getRoot();   // done
                }
            }
        }
        // x absorbed the extra black. Never write the sentinel: NIL is BLACK by
        // construction and is shared by every node in the tree, so a colour write
        // through it is a write to every "empty child" at once.
        if (!x.isNil()) x.setColor(TreeNode1.Color.BLACK);
        return rotationMark;
    }

    /**
     * Sentinel tripwire for the delete fixup (audit 2026-08-17, finding 2).
     *
     * <p>CLRS's fixup assumes the sibling {@code w} is a real node — guaranteed only
     * because a doubly-black {@code x} implies a non-empty sibling subtree <em>on a
     * valid red-black tree</em>. Nothing enforces validity here: a tree can arrive by
     * a structural route that never ran the RB fixups at all (a depth-truncated
     * {@code TreeCloner.shallowClone}, a hand-wired snapshot, a morph target built by
     * another strategy). With {@code w == NIL} the case-2 branch recoloured the shared
     * per-tree sentinel RED and the follow-on rotation wrote {@code NIL.left} /
     * {@code NIL.parent} and called {@code setRoot(NIL)} — emptying the whole tree with
     * no exception at the API boundary.</p>
     *
     * <p>So a NIL sibling is treated as "cannot rebalance further": there is no sibling
     * subtree to borrow blackness from, and the caller stops the loop instead of
     * recolouring or rotating the sentinel. Contents are untouched; only the colouring of
     * an already-invalid tree stays imperfect. On a valid tree this is one predictable,
     * never-taken branch — free on the hot path.</p>
     *
     * @return {@code true} when {@code w} is the sentinel and the fixup must stop.
     */
    private boolean cannotRebalance(TreeNode1<K> w) {
        if (!w.isNil()) return false;
        logger.warn("fixDelete: sibling is the NIL sentinel — this tree is not red-black "
                + "valid; ending the fixup without writing the sentinel.");
        return true;
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

    // ── Private helpers ───────────────────────────────────────────────────────

    /**
     * RB-TRANSPLANT — CLRS 13.4
     * Replaces subtree rooted at u with subtree rooted at v.
     * Does NOT update v's left/right children — caller's responsibility.
     */
    private void transplant(MutableTree<K> tree, TreeNode1<K> u, TreeNode1<K> v) {
        TreeNode1<K> uParent = u.getParent();
        if (uParent == null || uParent.isNil()) {
            tree.setRoot(v);
        } else if (u == uParent.getLeft()) {
            uParent.linkLeft(v);
        } else {
            uParent.linkRight(v);
        }
        // Always set v's parent (even if v is NIL — fixDelete needs the pointer)
        v.setParent(uParent);
    }

    /** Leftmost node in the subtree rooted at {@code node}. */
    private TreeNode1<K> minimum(TreeNode1<K> node, TreeNode1<K> nil) {
        while (!node.getLeft().isNil()) node = node.getLeft();
        return node;
    }
}
