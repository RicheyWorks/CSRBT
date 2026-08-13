package test.core;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.util.StrategyHealthCheck;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertFalse;

/**
 * Probe (bug audit 2026-08-12, deep sweep): {@code StrategyHealthCheck.isBst} compared
 * each node only to its immediate children, so a key violating an ANCESTOR's range
 * passed clause 3. Combined with {@code TreeContext.selfRepair} feeding the validator
 * the tree's own {@code inOrder()} as the expected keys (clause 1 becomes a tautology),
 * a globally-invalid BST was certified "healthy" and self-repair declined to repair it.
 * The fix threads min/max bounds down the recursion.
 */
@DisplayName("StrategyHealthCheck — global BST ordering, not just parent-child")
class HealthCheckGlobalBstProbeTest {

    @Test
    @DisplayName("an ancestor-range violation is detected even when expected = the tree's own inOrder")
    void ancestorRangeViolationDetected() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        for (int k = 1; k <= 100; k++) ctx.add(k);

        // Find a leaf in the ROOT'S RIGHT subtree that is a LEFT child of its parent.
        TreeNode1<Integer> nil = ctx.getTree().getNIL();
        TreeNode1<Integer> root = ctx.getTree().getRoot();
        TreeNode1<Integer> leaf = findLeftChildLeaf(root.getRight(), nil);

        // Replace it with a node keyed 0: less than its parent (local check passes),
        // but far below the right subtree's lower bound (global violation).
        TreeNode1<Integer> bogus = TreeNode1.createNode(0, nil);
        bogus.setColor(leaf.getColor());          // preserve RB coloring exactly
        leaf.getParent().setLeft(bogus);

        List<String> failures = StrategyHealthCheck.validate(
                ctx.getTree(), ctx.getTree().getStrategy(), ctx.getTree().inOrder());
        assertFalse(failures.isEmpty(),
                "a key of 0 inside the right subtree violates global BST order — the "
                + "validator must flag it even with tautological expected keys, but got: "
                + failures);
    }

    private static TreeNode1<Integer> findLeftChildLeaf(TreeNode1<Integer> start,
                                                        TreeNode1<Integer> nil) {
        // BFS for a leaf that is its parent's left child.
        java.util.ArrayDeque<TreeNode1<Integer>> queue = new java.util.ArrayDeque<>();
        queue.add(start);
        while (!queue.isEmpty()) {
            TreeNode1<Integer> n = queue.poll();
            if (n == nil || n.isNil()) continue;
            boolean isLeaf = n.getLeft().isNil() && n.getRight().isNil();
            if (isLeaf && n.getParent().getLeft() == n) return n;
            queue.add(n.getLeft());
            queue.add(n.getRight());
        }
        throw new AssertionError("no left-child leaf found in subtree");
    }
}
