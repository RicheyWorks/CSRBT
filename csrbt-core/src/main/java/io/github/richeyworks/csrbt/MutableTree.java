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

    /** Left rotation about {@code x} (CLRS LEFT-ROTATE). */
    void rotateLeft(TreeNode1<K> x);

    /** Right rotation about {@code y} (CLRS RIGHT-ROTATE). */
    void rotateRight(TreeNode1<K> y);
}
