package io.github.richeyworks.csrbt.util;

import io.github.richeyworks.csrbt.RedBlackTree;
import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;

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
 *
 * <p>ADR-002 step 4: generic over the key type {@code K}. Every clause is
 * key-agnostic — contents/size via {@code inOrder()}/{@code size()}, ordering via
 * {@link TreeNode1#compareTo}, and the order-statistics spot check via
 * {@code select}/{@code rank} — so the same validator serves the generic
 * {@link io.github.richeyworks.csrbt.OrderedSet} and the {@code Integer} {@code TreeContext} adapter
 * (which calls it with {@code K = Integer}, inferred).</p>
 */
public final class StrategyHealthCheck {

    private StrategyHealthCheck() { }

    /** @return list of failure descriptions; empty means the candidate is healthy. */
    public static <K> List<String> validate(RedBlackTree<K> candidate,
                                            TreeStrategy<K> strategy,
                                            List<K> expectedSortedKeys) {
        List<String> failures = new ArrayList<>();

        // 1 + 2: contents and size.
        List<K> in = candidate.inOrder();
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
            case "AVLStrategy" -> {
                if (!isHeightBalanced(candidate.getRoot())) {
                    failures.add(name + " height-balance invariant violated");
                }
            }
            // HybridStrategy routes through the default branch (bug audit 2026-08-12,
            // H-2): its invariant is depth-relaxed (|bf| ≤ 2 below the threshold), so
            // the strict AVL check here branded every finite-threshold Hybrid unhealthy.
            // Hybrid now overrides validateInvariant with its own tolerance-aware walk.
            case "SplayStrategy" -> { /* no balance invariant */ }
            default -> failures.addAll(strategy.validateInvariant(candidate));
            // ^ ADR-011 V1: strategies outside the built-in switch supply their own
            //   invariant (parameterized strategies validate against their own Δ/Γ);
            //   the structural checks above still apply regardless.
        }

        // 5: order-statistics spot check (candidate carries subtree-size augment).
        if (failures.isEmpty() && !expectedSortedKeys.isEmpty()) {
            try {
                OrderStatisticsOps<K> os = new OrderStatisticsOps<>(candidate);
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

    /**
     * Range-bounded BST check (bug audit 2026-08-12): the old form compared each node
     * only to its immediate children, so a key violating an <em>ancestor's</em> range
     * passed — and with {@code selfRepair} feeding the tree's own {@code inOrder()} as
     * the expected keys (clause 1 a tautology), a globally-invalid tree was certified
     * healthy. Bounds are threaded down the recursion: every node must lie strictly
     * inside the (min, max) window its ancestors impose.
     */
    private static <K> boolean isBst(TreeNode1<K> n) {
        return isBst(n, null, null);
    }

    private static <K> boolean isBst(TreeNode1<K> n, TreeNode1<K> min, TreeNode1<K> max) {
        if (n.isNil()) return true;
        if (min != null && n.compareTo(min) <= 0) return false;
        if (max != null && n.compareTo(max) >= 0) return false;
        return isBst(n.getLeft(), min, n) && isBst(n.getRight(), n, max);
    }

    private static <K> boolean isRedBlackValid(TreeNode1<K> root) {
        if (root.isNil()) return true;
        if (root.isRed()) return false;        // root must be black
        return blackHeight(root) >= 0;          // -1 signals a violation
    }

    /** @return uniform black-height, or -1 if a red-red or black-height violation exists. */
    private static <K> int blackHeight(TreeNode1<K> n) {
        if (n.isNil()) return 1;
        if (n.isRed() && (n.getLeft().isRed() || n.getRight().isRed())) return -1;
        int lh = blackHeight(n.getLeft());
        int rh = blackHeight(n.getRight());
        if (lh < 0 || rh < 0 || lh != rh) return -1;
        return lh + (n.isBlack() ? 1 : 0);
    }

    private static <K> boolean isHeightBalanced(TreeNode1<K> n) {
        return balancedHeight(n) >= 0;
    }

    /** @return actual height, or -1 if any node's |balance factor| > 1. */
    private static <K> int balancedHeight(TreeNode1<K> n) {
        if (n.isNil()) return 0;
        int lh = balancedHeight(n.getLeft());
        if (lh < 0) return -1;
        int rh = balancedHeight(n.getRight());
        if (rh < 0) return -1;
        if (Math.abs(lh - rh) > 1) return -1;
        return 1 + Math.max(lh, rh);
    }
}
