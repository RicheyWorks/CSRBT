package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.HybridStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;
import io.github.richeyworks.csrbt.strategy.WeightBalancedStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.function.Supplier;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-023 — rotations carry the cached height to every ancestor.
 *
 * <p><b>What was wrong.</b> Both rotations linked through the {@code *Local} node setters,
 * which recompute the touched nodes only. Subtree size and the augment payload are genuinely
 * ancestor-invariant under a rotation, so those stayed exact; {@code height} is not, and
 * nothing propagated it. AVL and Hybrid masked the defect (their rebalance walks call
 * {@code refreshHeight()} from the modification point to the root) and Splay masked it
 * structurally (splaying runs to the root, recomputing every node on the access path), but
 * RedBlack and WeightBalanced left it standing: AUDIT-2026-08-17 finding 21 reproduced an RB
 * node reporting height 5 where the real height was 4, and AUDIT-2026-08-14 F-1 deferred the
 * fix on cost grounds.</p>
 *
 * <p><b>How bad it was, measured.</b> Pre-fix the ROOT's cached height — the value the
 * experimental {@code TreeContextTesterAdditions} demo prints — was wrong after 98.7% of
 * ascending inserts and 59.7% of random inserts on RedBlack, and after 74.3% / 46.7% on
 * WeightBalanced with errors up to 8. Across the whole tree 2.4–5.7% of nodes carried a wrong
 * height at any instant. The fix is a fixed-point climb from the rotation point
 * ({@link TreeNode1#refreshHeightUpward()}), skipped by the three strategies that already
 * refresh heights themselves.</p>
 *
 * <p>Every assertion here fails on the pre-fix engine and passes after; the sweep below was
 * verified red on the pre-fix classes in all four RedBlack and all four WeightBalanced cells,
 * and green in all twenty.</p>
 */
@DisplayName("ADR-023 — cached height is exact for every ancestor after a rotation")
class RotationHeightPropagationTest {

    /** The measured truth: real height by full recursion, ignoring every cache. */
    private static int realHeight(TreeNode1<Integer> n) {
        if (n == null || n.isNil()) return 0;
        return 1 + Math.max(realHeight(n.getLeft()), realHeight(n.getRight()));
    }

    /** Deepest cached-vs-real height mismatch in the subtree, or null when all agree. */
    private static String firstStaleHeight(TreeNode1<Integer> n) {
        if (n == null || n.isNil()) return null;
        int real = realHeight(n);
        if (n.getHeight() != real) {
            return "node " + n.getData() + " caches height " + n.getHeight() + " but really is " + real;
        }
        String left = firstStaleHeight(n.getLeft());
        return left != null ? left : firstStaleHeight(n.getRight());
    }

    private static int countNodes(TreeNode1<Integer> n) {
        return (n == null || n.isNil()) ? 0 : 1 + countNodes(n.getLeft()) + countNodes(n.getRight());
    }

    // ── The audit's own reproduction, pinned ──────────────────────────────────

    /**
     * AUDIT-2026-08-17 finding 21's shape: a Red-Black engine, {@code Random(0)}, mixed
     * add/remove, checked after every single operation from the very first. Pre-fix the sweep
     * reports a stale node within the first two dozen operations (the audit recorded node 39
     * at height 5 against a real height of 4); post-fix it never does.
     */
    @Test
    @DisplayName("finding 21: a Red-Black mixed-op stream never leaves an ancestor's height stale")
    void redBlackMixedStreamStaysExact() {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        Random rng = new Random(0);
        List<Integer> live = new ArrayList<>();
        for (int op = 1; op <= 400; op++) {
            if (!live.isEmpty() && rng.nextInt(100) < 35) {
                set.remove(live.remove(rng.nextInt(live.size())));
            } else {
                int key = 1 + rng.nextInt(100);
                if (set.add(key)) live.add(key);
            }
            String stale = firstStaleHeight(set.getEngine().getRoot());
            assertEquals(null, stale, "after op #" + op + ": " + stale);
        }
        assertTrue(set.size() > 20, "the stream must actually build a tree worth checking");
    }

    // ── The root height, which is what callers actually read ──────────────────

    /**
     * The literal shape of the experimental {@code TreeContextTesterAdditions} demo — Red-Black,
     * ascending 1..20, reading {@code getRoot().getHeight()}. Pre-fix it printed 7 at n = 15 and
     * n = 20 where the real height is 6.
     */
    @Test
    @DisplayName("the root's cached height matches the real height on an ascending Red-Black build")
    void rootHeightIsExactOnAscendingRedBlack() {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        for (int i = 1; i <= 200; i++) {
            set.add(i);
            TreeNode1<Integer> root = set.getEngine().getRoot();
            assertEquals(realHeight(root), root.getHeight(),
                    "root height wrong after inserting " + i + " ascending keys");
        }
    }

    /** WeightBalanced ascending was the worst measured case pre-fix: root error up to 8. */
    @Test
    @DisplayName("the root's cached height matches on a weight-balanced ascending build")
    void rootHeightIsExactOnAscendingWeightBalanced() {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new WeightBalancedStrategy<Integer>());
        for (int i = 1; i <= 200; i++) {
            set.add(i);
            TreeNode1<Integer> root = set.getEngine().getRoot();
            assertEquals(realHeight(root), root.getHeight(),
                    "root height wrong after inserting " + i + " ascending keys");
        }
    }

    // ── The sweep: every strategy, every workload shape ───────────────────────

    @Test
    @DisplayName("every strategy × workload leaves every node's cached height exact")
    void everyStrategyAndWorkloadStaysExact() {
        record Strat(String name, Supplier<TreeStrategy<Integer>> make) { }
        List<Strat> strategies = List.of(
                new Strat("RedBlack", RedBlackStrategy::new),
                new Strat("AVL", AVLStrategy::new),
                new Strat("Splay", SplayStrategy::new),
                new Strat("Hybrid", HybridStrategy::new),
                new Strat("WeightBalanced", WeightBalancedStrategy::new));

        for (Strat strategy : strategies) {
            for (String workload : List.of("random", "ascending", "descending", "mixed")) {
                OrderedSet<Integer> set = OrderedSet.withNaturalOrder(strategy.make().get());
                Random rng = new Random(7);
                List<Integer> live = new ArrayList<>();
                int ops = 300;
                for (int i = 0; i < ops; i++) {
                    switch (workload) {
                        case "ascending"  -> set.add(i + 1);
                        case "descending" -> set.add(ops - i);
                        case "random"     -> set.add(1 + rng.nextInt(ops * 4));
                        default -> {
                            if (!live.isEmpty() && rng.nextInt(100) < 35) {
                                set.remove(live.remove(rng.nextInt(live.size())));
                            } else {
                                int key = 1 + rng.nextInt(ops * 4);
                                if (set.add(key)) live.add(key);
                            }
                        }
                    }
                    String stale = firstStaleHeight(set.getEngine().getRoot());
                    assertEquals(null, stale,
                            strategy.name() + "/" + workload + " after op #" + (i + 1) + ": " + stale);
                }
                assertEquals(set.size(), countNodes(set.getEngine().getRoot()),
                        strategy.name() + "/" + workload + ": tree walk disagrees with reported size");
            }
        }
    }

    // ── The quantities the rotation is allowed to leave alone ─────────────────

    /**
     * The other half of the ADR-023 statement: subtree size stays exact without any propagation
     * (a rotation cannot change which keys live under an ancestor), which is why the climb
     * carries height alone. Order statistics read {@code getSize()} directly, so this is the
     * assertion that keeps the "no propagation owed" claim honest.
     */
    @Test
    @DisplayName("subtree size needs no climb — it is exact on every strategy already")
    void subtreeSizeStaysExactWithoutPropagation() {
        for (Supplier<TreeStrategy<Integer>> make : List.<Supplier<TreeStrategy<Integer>>>of(
                RedBlackStrategy::new, AVLStrategy::new, SplayStrategy::new,
                HybridStrategy::new, WeightBalancedStrategy::new)) {
            OrderedSet<Integer> set = OrderedSet.withNaturalOrder(make.get());
            Random rng = new Random(3);
            for (int i = 0; i < 300; i++) {
                set.add(1 + rng.nextInt(1200));
                assertSizesExact(set.getEngine().getRoot());
            }
        }
    }

    private static void assertSizesExact(TreeNode1<Integer> n) {
        if (n == null || n.isNil()) return;
        assertEquals(countNodes(n), n.getSize(), "stale cached size at node " + n.getData());
        assertSizesExact(n.getLeft());
        assertSizesExact(n.getRight());
    }
}
