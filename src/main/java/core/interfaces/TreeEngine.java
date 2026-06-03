package core.interfaces;

import java.util.List;

/**
 * Representation-neutral backing structure for an ordered set of {@code K} keys.
 *
 * <p>This is the extension point that decouples the orchestration layer
 * ({@link core.TreeContext}) from any one concrete data structure. A
 * {@code TreeEngine} exposes only behaviour — insert, delete, membership,
 * ordered enumeration — and never leaks node representation (no colors, no
 * NIL sentinel, no rotations) across its boundary.</p>
 *
 * <p>The strategy-driven {@code RedBlackTree} is <em>one</em> implementation.
 * The strategy pattern (RB / AVL / Splay / Hybrid) is an internal detail of
 * that pointer-based-BST engine family — it is not part of this contract.
 * Future engines whose internals are <em>not</em> colored binary trees
 * (e.g. a persistent functional tree, a Fibonacci heap, a van&nbsp;Emde&nbsp;Boas
 * tree) implement this interface directly and need not involve
 * {@code TreeStrategy} or {@code TreeNode1} at all.</p>
 *
 * <p>Contract notes:</p>
 * <ul>
 *   <li>{@link #inOrder()} returns keys in ascending order.</li>
 *   <li>{@link #size()} equals {@code inOrder().size()}.</li>
 *   <li>Duplicate-key handling is engine-defined and not mandated here.</li>
 * </ul>
 */
public interface TreeEngine<K> {

    /** Insert a key. */
    void add(K value);

    /** Remove a key if present; a no-op otherwise. */
    void remove(K value);

    /** @return {@code true} if the key is present. */
    boolean contains(K value);

    /** @return all keys in ascending order. */
    List<K> inOrder();

    /** @return number of keys currently stored. */
    int size();

    /** Remove all keys, leaving an empty engine. */
    void clear();

    /** @return {@code true} if the engine holds no keys. */
    default boolean isEmpty() {
        return size() == 0;
    }
}
