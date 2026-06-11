package io.github.richeyworks.csrbt.interfaces;

import java.util.List;

/**
 * Client-facing contract for an ordered collection of {@code K} keys.
 *
 * <p>This is the neutral handle that callers (and the evolutionary controller)
 * should program against instead of a concrete facade. It deliberately omits
 * everything specific to a particular backing structure -- metrics, persistence,
 * augmentation, self-repair -- so that a caller written against
 * {@code OrderedCollection} keeps working regardless of which {@link TreeEngine}
 * powers it underneath.</p>
 *
 * <p>ADR-002 step 4: generified from the original {@code int}-keyed contract to
 * {@code OrderedCollection<K>}. The generic {@link io.github.richeyworks.csrbt.OrderedSet} implements it
 * directly; the {@code int} {@code TreeContext} adapter implements the
 * {@code <Integer>} instantiation (its {@code add(int)} public API is preserved
 * alongside the {@code add(Integer)} the interface requires -- an {@code add(int)}
 * does not override {@code add(Integer)}; see the step-2 PersistentTreeEngine note).
 * {@code add}/{@code remove} now report whether the set changed, matching
 * {@link java.util.Collection} and the {@code OrderedSet} dedup contract.</p>
 */
public interface OrderedCollection<K> {

    /** Insert a key. @return {@code true} if the key was added (was not already present). */
    boolean add(K value);

    /** Remove a key if present. @return {@code true} if a key was removed. */
    boolean remove(K value);

    /** @return {@code true} if the key is present. */
    boolean contains(K value);

    /** @return number of keys currently stored. */
    int size();

    /** @return all keys in ascending order. */
    List<K> inOrder();

    /** Remove all keys. */
    void clear();

    /** @return {@code true} if no keys are stored. */
    default boolean isEmpty() {
        return size() == 0;
    }
}
