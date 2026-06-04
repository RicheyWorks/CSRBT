package core.interfaces;

import core.TreeNode1;

public interface AugmentedTree<K> {

    /**
     * Attach a custom augmentor that will be applied to every node
     * on insert and propagated upward on structural changes.
     *
     * <p>ADR-002 step 4: generified to {@code AugmentedTree<K>}. The generic
     * {@link core.OrderedSet} implements it directly; the {@code TreeContext}
     * adapter implements the {@code <Integer>} instantiation (its existing
     * {@code setAugmentor(Augmentor<Integer>)} already matches).</p>
     */
    void setAugmentor(TreeNode1.Augmentor<K> augmentor);
}
