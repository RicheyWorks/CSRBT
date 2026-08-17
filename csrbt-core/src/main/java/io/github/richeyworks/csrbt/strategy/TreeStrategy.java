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
    //       height recomputes unchanged. ADR-023 measured it: 1–3 levels on uniform and
    //       mixed add/remove streams, a full-height climb on monotone inserts, where the
    //       BST link has just pushed +1 up the whole spine and the rebalancing rotation
    //       takes it straight back off.
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
    // Which pair to call, if you are writing a strategy: rotateLeft/rotateRight, always,
    // unless you can prove your rebalance pass already refreshes every node from the
    // rotation point to the root — the three strategies that call the *Local primitives
    // each carry that proof in a comment at the call site. The safe choice is the one
    // without the suffix, exactly as with TreeNode1.setLeft vs setLeftLocal.

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
