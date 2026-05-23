package core.interfaces;

import core.TreeNode1;

public interface AugmentedTree {

    /**
     * Attach a custom augmentor that will be applied to every node
     * on insert and propagated upward on structural changes.
     */
    void setAugmentor(TreeNode1.Augmentor augmentor);
}
