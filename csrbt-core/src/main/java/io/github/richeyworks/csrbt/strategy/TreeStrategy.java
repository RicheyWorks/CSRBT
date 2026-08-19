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
    // The rotation PRIMITIVES (rotateLeftLocal / rotateRightLocal) link through the
    // *Local node setters, which recompute size, augment, height and black-height for
    // the TOUCHED nodes only — they never walk to the root. That is what keeps a
    // rotation O(1) and an insert O(height) instead of O(height²); insert/delete BST
    // links still use the propagating setLeft/setRight. Per cached quantity:
    //
    //   size / augmentedValue — CORRECT for every node after a primitive rotation. A
    //       rotation permutes a local pair (x, y) without changing which keys live under
    //       any ancestor, so no ancestor's subtree size or subtree augment can change.
    //       The ancestor that adopts the new subtree root keeps exactly the same
    //       descendants, which is why it too is linked locally. Order statistics stay
    //       exact, and no propagation is ever owed for them.
    //
    //   height — NOT ancestor-invariant. A rotation can change the height of the rotated
    //       subtree's root, and that genuinely propagates upward. rotateLeft/rotateRight
    //       (the ones without "Local") therefore run TreeNode1.refreshHeightUpward()
    //       when it does — a fixed-point climb that stops at the first ancestor whose
    //       height recomputes unchanged. That pair is the SELF-CONTAINED one: an
    //       out-of-band rotation through it leaves every ancestor exact on its own, with
    //       no help from a surrounding write, which is what MutableTree.rotateLeft
    //       promises. None of the five strategies here uses it any more (ADR-028): a
    //       whole write is cheaper to fix once at the end than a rotation at a time —
    //       ADR-023 measured the per-rotation climb at 22.7 levels per monotone Red-Black
    //       insert ON TOP OF the 27.7 the BST link had just walked in the opposite
    //       direction, for +22% of write time on that one cell.
    //
    //   blackHeight — MAY GO STALE for ancestors, and the climb deliberately does not
    //       carry it. Rotation is not even its main source: setColor/flipColor update the
    //       recoloured node alone, and the RB insert/delete fixups recolour O(log n) nodes
    //       per write, so chasing black-height exactly would mean a climb per recolour on
    //       the hottest path in the engine. The cached value is informational bookkeeping
    //       on every strategy anyway (AVL/Splay/WeightBalanced colour every node black);
    //       the exact, invariant-checking answer is TreeNode1.blackHeight(), and red-black
    //       validity is TreeDiagnostics' job. See TreeNode1.getBlackHeight().
    //
    // ── How the five strategies here maintain height, since ADR-028 ───────────────
    //
    // Once per write, never twice. The BST-descent links go through TreeNode1.linkLeft /
    // linkRight (size, augment and black-height to the root; no height anywhere), the
    // rotations go through the *Local primitives, and the write ends with ONE height pass:
    //
    //   RedBlack, WeightBalanced — TreeNode1.repairHeightUpward(mark) from the write's
    //       anchor (the newly linked node on insert; the parent of the spliced-out position
    //       on delete), with `mark` = rotationAdopter(...) of the highest rotation the
    //       rebalance fired, because a rotation is a second origin of height change that a
    //       climb from below cannot see. A delete that splices the in-order successor into
    //       the removed node's place adds a third origin and repairs it explicitly.
    //
    //   AVL, Hybrid, Splay — nothing extra. Their own passes already recompute every node
    //       from the modification point to the root (they steer by those heights, or, for
    //       Splay, rotate all the way to the root); the link no longer duplicates that walk.
    //
    // Which pair to call, if you are writing a strategy: rotateLeft/rotateRight and
    // setLeft/setRight, always, unless you can prove your write repairs height itself — the
    // strategies here each carry that proof in a comment at the call site. The safe choice
    // is the suffix-free, propagating one, exactly as with TreeNode1.setLeft vs setLeftLocal:
    // it costs a walk and is never wrong.

    /**
     * The ancestor that adopted the subtree a rotation about {@code rotated} has just
     * rearranged — the {@code unconditionalThrough} mark for the write's single
     * {@link TreeNode1#repairHeightUpward(TreeNode1)} (ADR-028).
     *
     * <p>Read it AFTER the rotation, when {@code rotated} has slid down and its parent is the
     * new subtree root: the adopter is that root's parent, and it is the highest node the
     * rotation wrote a height into. Returns {@code null} when the rotation was at the tree root
     * — the repair then climbs the anchor's whole ancestor path, which is both correct and the
     * shortest it can be, since a root rotation has no ancestors to leave stale.</p>
     *
     * <p>A strategy that keeps a running mark across a rebalance pass should overwrite it after
     * every rotation: the passes here all walk upward, so the last rotation is the highest one
     * and its adopter is the mark the repair needs.</p>
     */
    default TreeNode1<K> rotationAdopter(TreeNode1<K> rotated) {
        TreeNode1<K> subtreeRoot = rotated.getParent();
        if (subtreeRoot == null || subtreeRoot.isNil()) return null;
        TreeNode1<K> adopter = subtreeRoot.getParent();
        return (adopter == null || adopter.isNil()) ? null : adopter;
    }

    /**
     * Left rotation about {@code x} that leaves every ancestor's cached
     * {@linkplain TreeNode1#getHeight() height} exact (ADR-023).
     *
     * <p>Delegates to {@link #rotateLeftLocal} and then, only if the rotation actually moved
     * the height of the subtree {@code x}'s old parent adopts, carries the change up with
     * {@link TreeNode1#refreshHeightUpward()}. Subtree size and the augment payload need no
     * such walk — they are ancestor-invariant under rotation.</p>
     */
    default void rotateLeft(MutableTree<K> tree, TreeNode1<K> x) {
        TreeNode1<K> parent = x.getParent();                       // capture BEFORE relinking
        boolean carry = parent != null && !parent.isNil();         // a root rotation has no ancestors
        int wasHeight = carry ? parent.getHeight() : 0;
        rotateLeftLocal(tree, x);
        if (carry && parent.getHeight() != wasHeight) parent.refreshHeightUpward();
    }

    /**
     * Right rotation about {@code y} that leaves every ancestor's cached height exact —
     * {@link #rotateLeft}'s mirror image, same contract.
     */
    default void rotateRight(MutableTree<K> tree, TreeNode1<K> y) {
        TreeNode1<K> parent = y.getParent();
        boolean carry = parent != null && !parent.isNil();
        int wasHeight = carry ? parent.getHeight() : 0;
        rotateRightLocal(tree, y);
        if (carry && parent.getHeight() != wasHeight) parent.refreshHeightUpward();
    }

    /**
     * The left-rotation PRIMITIVE: relinks and recomputes the touched nodes only, never
     * walking to the root — the rotation counterpart of {@link TreeNode1#setLeftLocal}.
     *
     * <p>Leaves size and augment exact for every node (they cannot change) and every
     * ancestor's cached height <b>possibly stale</b>. Call it only from a rebalance pass
     * that itself refreshes heights from the rotation point to the root; otherwise call
     * {@link #rotateLeft}. See the note above this method for the full rule.</p>
     */
    default void rotateLeftLocal(MutableTree<K> tree, TreeNode1<K> x) {
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

    /** Right-side counterpart of {@link #rotateLeftLocal}; same staleness contract. */
    default void rotateRightLocal(MutableTree<K> tree, TreeNode1<K> y) {
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
