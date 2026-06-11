package io.github.richeyworks.csrbt.interfaces;

public interface SelfHealingTree {

    /**
     * Detect and repair invariant violations.
     * Returns true if the tree is valid after repair.
     */
    boolean selfRepair();
}
