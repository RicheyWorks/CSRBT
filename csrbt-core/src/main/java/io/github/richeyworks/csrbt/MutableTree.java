package io.github.richeyworks.csrbt;

/**
 * Structural view of a node-based balanced tree, as seen by a
 * {@link io.github.richeyworks.csrbt.strategy.TreeStrategy}.
 *
 * <p>This is the seam that decouples the strategies from the concrete
 * {@link RedBlackTree}. A strategy needs only three structural capabilities to
 * implement any balancing algorithm (RB, AVL, Splay, Hybrid):
 *
 * <ul>
 *   <li>read and replace the root ({@link #getRoot()} / {@link #setRoot}),</li>
 *   <li>obtain the shared NIL sentinel ({@link #getNIL()}),</li>
 *   <li>perform the two primitive rotations ({@link #rotateLeft} /
 *       {@link #rotateRight}).</li>
 * </ul>
 *
 * <p>By depending on this interface rather than {@code RedBlackTree}, the
 * strategies no longer know (or care) which engine backs them, while existing
 * callers that pass a {@code RedBlackTree} continue to work unchanged since
 * {@code RedBlackTree implements MutableTree}.
 */
public interface MutableTree<K> {

    TreeNode1<K> getRoot();

    void setRoot(TreeNode1<K> root);

    /** The shared sentinel leaf. Never {@code null}; never reassigned. */
    TreeNode1<K> getNIL();

    /**
     * Left rotation about {@code x} (CLRS LEFT-ROTATE), height-carrying.
     *
     * <p>Routes to {@code TreeStrategy.rotateLeft}, the variant that leaves every ancestor's
     * cached {@code TreeNode1.getHeight()} exact by itself (ADR-023) — so an out-of-band rotation
     * through this engine-level seam is safe on any strategy, with no surrounding write to repair
     * after it. The strategies' own rebalance passes do not come through here: they call the
     * cheaper {@code rotateLeftLocal} primitive and settle height once per write instead
     * (ADR-028). This seam is for rotations fired from outside a write.</p>
     */
    void rotateLeft(TreeNode1<K> x);

    /** Right rotation about {@code y} (CLRS RIGHT-ROTATE); {@link #rotateLeft}'s mirror. */
    void rotateRight(TreeNode1<K> y);

    /**
     * Notification hook fired once per primitive rotation, from the shared
     * {@link io.github.richeyworks.csrbt.strategy.TreeStrategy} rotation bodies —
     * the single choke point every strategy's rotations flow through. Lets an
     * engine meter structural churn ({@code rotationsPerWrite} is a first-class
     * {@link io.github.richeyworks.csrbt.control.WorkloadFeatures} input that
     * callers previously had no way to source). Default: no-op, so existing
     * implementations and tests are untouched.
     */
    default void onRotation() { }
}
