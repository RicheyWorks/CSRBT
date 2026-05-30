package core.interfaces;

import java.util.List;

/**
 * Client-facing contract for an ordered collection of {@code int} keys.
 *
 * <p>This is the neutral handle that callers (and the evolutionary controller)
 * should program against instead of the concrete {@link core.TreeContext}.
 * It deliberately omits everything specific to a particular backing structure
 * — metrics, persistence, augmentation, self-repair — so that a caller written
 * against {@code OrderedCollection} keeps working regardless of which
 * {@link TreeEngine} powers it underneath.</p>
 */
public interface OrderedCollection {

    /** Insert a key. */
    void add(int value);

    /** Remove a key if present; a no-op otherwise. */
    void remove(int value);

    /** @return {@code true} if the key is present. */
    boolean contains(int value);

    /** @return number of keys currently stored. */
    int size();

    /** @return all keys in ascending order. */
    List<Integer> inOrder();

    /** Remove all keys. */
    void clear();

    /** @return {@code true} if no keys are stored. */
    default boolean isEmpty() {
        return size() == 0;
    }
}
