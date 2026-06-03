package core.interfaces;

import core.TreeNode1;

public interface AugmentedTree {

    /**
     * Attach a custom augmentor that will be applied to every node
     * on insert and propagated upward on structural changes.
     *
     * <p>ADR-002 step 2 pins this client-facing facade to {@code Integer} keys
     * (the {@code TreeContext} adapter). The generic {@code OrderedSet<K>} facade
     * in step 4 will revisit whether this interface becomes {@code AugmentedTree<K>}.</p>
     */
    void setAugmentor(TreeNode1.Augmentor<Integer> augmentor);
}
