package io.github.richeyworks.csrbt.interfaces;

public interface SelfHealingTree {

    /**
     * Detect and repair invariant violations.
     * Returns true if the tree is valid after repair.
     *
     * <p><b>Cost warning (hardening I-1):</b> implementations typically rebuild the whole tree —
     * O(n) per call — and a rebuild discards adaptive structure (e.g. a splay tree's learned
     * layout). Calling this in a per-element loop turns an O(n log n) workload into O(n²);
     * prefer a batched cadence (validate every k operations), reserving per-op checks for
     * debugging and forensics.</p>
     */
    boolean selfRepair();
}
