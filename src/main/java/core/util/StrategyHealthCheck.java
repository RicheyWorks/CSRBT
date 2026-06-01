package core.util;

import core.RedBlackTree;
import core.TreeNode1;
import core.strategy.TreeStrategy;

import java.util.ArrayList;
import java.util.List;

/**
 * Validates a freshly-built candidate engine before a morph publishes it.
 *
 * <p>This is the concrete "health gate" from {@code DESIGN-adaptive-engine.md}
 * §3.4: a morph builds the candidate off to the side, runs these checks, and only
 * swaps it in on a full pass — otherwise the incumbent is kept untouched.</p>
 *
 * <p>The check is <em>total</em>: it returns a list of failure messages (empty =
 * healthy) and never throws into the caller. Clauses:</p>
 * <ol>
 *   <li>in-order keys equal the expected sorted key set;</li>
 *   <li>size matches;</li>
 *   <li>BST ordering holds node-by-node;</li>
 *   <li>the candidate strategy's own structural invariant holds (RB validity for
 *       Red-Black; height balance for AVL/Hybrid; Splay has no balance invariant);</li>
 *   <li>order-statistics (select/rank) agree at a sample of ranks — valid because
 *       the candidate is built with the default subtree-size augmentor.</li>
 * </ol>
 */
public final class StrategyHealthCheck {

    private StrategyHealthCheck() { }

    /** @return list of failure descriptions; empty means the candidate is healthy. */
    public static List<String> validate(RedBlackTree candidate,
                                        TreeStrategy strategy,
                                        List<Integer> expectedSortedKeys) {
        List<String> failures = new ArrayList<>();

        // 1 + 2: contents and size.
        List<Integer> in = candidate.inOrder();
        if (!in.equals(expectedSortedKeys)) {
            failures.add("in-order keys differ from expected (" + in.size()
                    + " vs " + expectedSortedKeys.size() + ")");
        }
        if (candidate.size() != expectedSortedKeys.size()) {
            failures.add("size " + candidate.size() + " != expected " + expectedSortedKeys.size());
        }

        // 3: BST ordering.
        if (!isBst(candidate.getRoot())) {
            failures.add("BST ordering violated");
        }

        // 4: per-strategy structural invariant.
        String name = strategy.getClass().getSimpleName();
        switch (name) {
            case "RedBlackStrategy" -> {
                if (!isRedBlackValid(candidate.getRoot())) {
                    failures.add("red-black invariant violated");
                }
            }
            case "AVLStrategy", "HybridStrategy" -> {
                if (!isHeightBalanced(candidate.getRoot())) {
                    failures.add(name + " height-balance invariant violated");
                }
            }
            case "SplayStrategy" -> { /* no balance invariant */ }
            default -> { /* unknown strategy: structural checks above still apply */ }
        }

        // 5: order-statistics spot check (candidate carries subtree-size augment).
        if (failures.isEmpty() && !expectedSortedKeys.isEmpty()) {
            try {
                OrderStatisticsOps os = new OrderStatisticsOps(candidate);
                int n = expectedSortedKeys.size();
                int step = Math.max(1, n / 16);
                for (int r = 1; r <= n; r += step) {
                    if (os.select(r).compareKeyTo(expectedSortedKeys.get(r - 1)) != 0) {
                        failures.add("select(" + r + ") mismatch");
                        break;
                    }
                    if (os.rank(expectedSortedKeys.get(r - 1)) != r) {
                        failures.add("rank(" + expectedSortedKeys.get(r - 1) + ") mismatch");
                        break;
                    }
                }
            } catch (RuntimeException e) {
                failures.add("order-statistics check threw: " + e.getMessage());
            }
        }

        return failures;
    }

    // ── Invariant helpers ──────────────────────────────────────────────────────

    private static boolean isBst(TreeNode1 n) {
        if (n.isNil()) return true;
        if (!n.getLeft().isNil()  && n.getLeft().compareTo(n)  >= 0) return false;
        if (!n.getRight().isNil() && n.getRight().compareTo(n) <= 0) return false;
        return isBst(n.getLeft()) && isBst(n.getRight());
    }

    private static boolean isRedBlackValid(TreeNode1 root) {
        if (root.isNil()) return true;
        if (root.isRed()) return false;        // root must be black
        return blackHeight(root) >= 0;          // -1 signals a violation
    }

    /** @return uniform black-height, or -1 if a red-red or black-height violation exists. */
    private static int blackHeight(TreeNode1 n) {
        if (n.isNil()) return 1;
        if (n.isRed() && (n.getLeft().isRed() || n.getRight().isRed())) return -1;
        int lh = blackHeight(n.getLeft());
        int rh = blackHeight(n.getRight());
        if (lh < 0 || rh < 0 || lh != rh) return -1;
        return lh + (n.isBlack() ? 1 : 0);
    }

    private static boolean isHeightBalanced(TreeNode1 n) {
        return balancedHeight(n) >= 0;
    }

    /** @return actual height, or -1 if any node's |balance factor| > 1. */
    private static int balancedHeight(TreeNode1 n) {
        if (n.isNil()) return 0;
        int lh = balancedHeight(n.getLeft());
        if (lh < 0) return -1;
        int rh = balancedHeight(n.getRight());
        if (rh < 0) return -1;
        if (Math.abs(lh - rh) > 1) return -1;
        return 1 + Math.max(lh, rh);
    }
}
