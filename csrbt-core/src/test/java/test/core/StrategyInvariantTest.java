package test.core;

import io.github.richeyworks.csrbt.RedBlackTree;
import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.HybridStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;
import io.github.richeyworks.csrbt.util.OrderStatisticsOps;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.TreeSet;
import java.util.function.Supplier;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Per-strategy invariant and property tests.
 *
 * <p>Each strategy is driven <em>directly</em> through {@link RedBlackTree}
 * (never through {@code TreeContext}) so the facade's stress auto-morph can't
 * silently swap the strategy out from under the test. Every test cross-checks
 * the tree against a {@link TreeSet} oracle for ordered-set correctness, then
 * asserts the strategy's own structural invariant.</p>
 *
 * <p>Shared coverage per strategy: randomized mixed insert/remove/contains vs
 * oracle; ascending and descending (degenerate) insertion; duplicate handling;
 * empty/single-element edge cases; and order-statistics exactness (select/rank)
 * which relies on the subtree-size augment being maintained through rotations.</p>
 */
@DisplayName("Per-strategy invariants")
public class StrategyInvariantTest {

    // ════════════════════════════════════════════════════════════════════════
    //  Shared helpers
    // ════════════════════════════════════════════════════════════════════════

    private static RedBlackTree<Integer> tree(TreeStrategy<Integer> s) { return RedBlackTree.withNaturalOrder(s); }

    /** Actual height by traversal — never trusts the cached field. */
    private static int height(TreeNode1<Integer> n) {
        if (n == null || n.isNil()) return 0;
        return 1 + Math.max(height(n.getLeft()), height(n.getRight()));
    }

    /** Assert in-order keys are strictly ascending and equal the oracle. */
    private static void assertMatchesOracle(RedBlackTree<Integer> t, TreeSet<Integer> oracle) {
        List<Integer> in = t.inOrder();
        for (int i = 1; i < in.size(); i++) {
            assertTrue(in.get(i - 1) < in.get(i),
                    "in-order not strictly ascending at " + i + ": " + in);
        }
        assertEquals(new ArrayList<>(oracle), in, "tree contents diverged from oracle");
        assertEquals(oracle.size(), t.size(), "size diverged from oracle");
    }

    /** Verify BST parent/child ordering invariant node-by-node. */
    private static void assertBstShape(RedBlackTree<Integer> t) {
        TreeNode1<Integer> root = t.getRoot();
        if (root.isNil()) return;
        checkBst(root);
    }

    private static void checkBst(TreeNode1<Integer> n) {
        if (n.isNil()) return;
        if (!n.getLeft().isNil()) {
            assertTrue(n.getLeft().getData() < n.getData(),
                    "left child " + n.getLeft().getData() + " >= parent " + n.getData());
            checkBst(n.getLeft());
        }
        if (!n.getRight().isNil()) {
            assertTrue(n.getRight().getData() > n.getData(),
                    "right child " + n.getRight().getData() + " <= parent " + n.getData());
            checkBst(n.getRight());
        }
    }

    /** Red-black validity: root black, no red-red, uniform black-height. */
    private static void assertRedBlackValid(RedBlackTree<Integer> t) {
        TreeNode1<Integer> root = t.getRoot();
        if (root.isNil()) return;
        assertTrue(root.isBlack(), "root must be black");
        blackHeight(root);          // throws via assertion on red-red / bh mismatch
    }

    private static int blackHeight(TreeNode1<Integer> n) {
        if (n.isNil()) return 1;
        if (n.isRed()) {
            assertFalse(n.getLeft().isRed(), "red-red: " + n.getData() + " / left");
            assertFalse(n.getRight().isRed(), "red-red: " + n.getData() + " / right");
        }
        int lh = blackHeight(n.getLeft());
        int rh = blackHeight(n.getRight());
        assertEquals(lh, rh, "black-height mismatch at " + n.getData());
        return lh + (n.isBlack() ? 1 : 0);
    }

    /** AVL balance: |height(left) - height(right)| <= 1 at every node. */
    private static void assertAvlBalanced(RedBlackTree<Integer> t) {
        assertBalancedRec(t.getRoot());
    }

    private static void assertBalancedRec(TreeNode1<Integer> n) {
        if (n.isNil()) return;
        int bf = height(n.getLeft()) - height(n.getRight());
        assertTrue(Math.abs(bf) <= 1,
                "balance factor " + bf + " at node " + n.getData());
        assertBalancedRec(n.getLeft());
        assertBalancedRec(n.getRight());
    }

    /** Order-statistics exactness against the sorted key list. */
    private static void assertOrderStatistics(RedBlackTree<Integer> t, TreeSet<Integer> oracle) {
        if (oracle.isEmpty()) return;
        OrderStatisticsOps<Integer> os = new OrderStatisticsOps<>(t);
        List<Integer> sorted = new ArrayList<>(oracle);
        for (int r = 1; r <= sorted.size(); r++) {
            assertEquals(sorted.get(r - 1), os.select(r).getData(), "select(" + r + ")");
            assertEquals(r, os.rank(sorted.get(r - 1)), "rank(" + sorted.get(r - 1) + ")");
        }
        assertEquals(sorted.get((sorted.size() + 1) / 2 - 1), os.median().getData(), "median");
    }

    /** Drive a deterministic mixed workload through a strategy and validate. */
    private static void mixedWorkload(Supplier<TreeStrategy<Integer>> strat,
                                      long seed, int ops, int universe,
                                      java.util.function.BiConsumer<RedBlackTree<Integer>, TreeSet<Integer>> invariant) {
        RedBlackTree<Integer> t = tree(strat.get());
        TreeSet<Integer> oracle = new TreeSet<>();
        Random rng = new Random(seed);

        for (int i = 0; i < ops; i++) {
            int v = rng.nextInt(universe);
            int op = rng.nextInt(3);
            if (op == 0) {                      // add
                t.add(v); oracle.add(v);
            } else if (op == 1) {               // remove
                t.remove(v); oracle.remove(v);
            } else {                            // contains
                assertEquals(oracle.contains(v), t.contains(v), "contains(" + v + ")");
            }
            if (i % 25 == 0) {                  // periodic structural validation
                assertBstShape(t);
                invariant.accept(t, oracle);
            }
        }
        assertMatchesOracle(t, oracle);
        assertBstShape(t);
        invariant.accept(t, oracle);
        assertOrderStatistics(t, oracle);
    }

    // ════════════════════════════════════════════════════════════════════════
    //  Red-Black
    // ════════════════════════════════════════════════════════════════════════

    @Nested
    @DisplayName("RedBlackStrategy")
    class RedBlack {

        @Test @DisplayName("mixed workload keeps RB validity, order, size, order-stats")
        void mixed() {
            mixedWorkload(RedBlackStrategy::new, 11, 4000, 800,
                    (t, o) -> assertRedBlackValid(t));
        }

        @Test @DisplayName("ascending inserts stay RB-valid and log-height")
        void ascending() {
            RedBlackTree<Integer> t = tree(new RedBlackStrategy<>());
            int n = 1000;
            for (int i = 0; i < n; i++) t.add(i);
            assertRedBlackValid(t);
            assertEquals(n, t.size());
            // RB height bound: <= 2*log2(n+1).
            assertTrue(height(t.getRoot()) <= 2 * (Math.log(n + 1) / Math.log(2)) + 1,
                    "RB height exceeded 2log(n+1)");
        }

        @Test @DisplayName("descending inserts stay RB-valid")
        void descending() {
            RedBlackTree<Integer> t = tree(new RedBlackStrategy<>());
            for (int i = 1000; i > 0; i--) t.add(i);
            assertRedBlackValid(t);
            assertEquals(1000, t.size());
        }

        @Test @DisplayName("delete every other key preserves RB validity")
        void deleteAlternating() {
            RedBlackTree<Integer> t = tree(new RedBlackStrategy<>());
            for (int i = 0; i < 500; i++) t.add(i);
            for (int i = 0; i < 500; i += 2) t.remove(i);
            assertRedBlackValid(t);
            assertBstShape(t);
            assertEquals(250, t.size());
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    //  AVL
    // ════════════════════════════════════════════════════════════════════════

    @Nested
    @DisplayName("AVLStrategy")
    class Avl {

        @Test @DisplayName("mixed workload keeps |bf|<=1, order, size, order-stats")
        void mixed() {
            mixedWorkload(AVLStrategy::new, 22, 4000, 800,
                    (t, o) -> assertAvlBalanced(t));
        }

        @Test @DisplayName("ascending inserts stay strictly AVL-balanced and near-optimal height")
        void ascending() {
            RedBlackTree<Integer> t = tree(new AVLStrategy<>());
            int n = 1000;
            for (int i = 0; i < n; i++) t.add(i);
            assertAvlBalanced(t);
            // AVL height bound: < 1.4405 * log2(n+2).
            assertTrue(height(t.getRoot()) <= 1.4405 * (Math.log(n + 2) / Math.log(2)) + 1,
                    "AVL height exceeded the 1.44 log bound");
        }

        @Test @DisplayName("descending inserts stay AVL-balanced")
        void descending() {
            RedBlackTree<Integer> t = tree(new AVLStrategy<>());
            for (int i = 1000; i > 0; i--) t.add(i);
            assertAvlBalanced(t);
            assertEquals(1000, t.size());
        }

        @Test @DisplayName("delete-heavy sequence stays balanced (regression for the splice-cycle fix)")
        void deleteHeavy() {
            RedBlackTree<Integer> t = tree(new AVLStrategy<>());
            for (int i = 0; i < 600; i++) t.add(i);
            Random rng = new Random(7);
            List<Integer> vals = new ArrayList<>();
            for (int i = 0; i < 600; i++) vals.add(i);
            java.util.Collections.shuffle(vals, rng);
            for (int i = 0; i < 450; i++) t.remove(vals.get(i));
            assertAvlBalanced(t);
            assertBstShape(t);
            assertEquals(150, t.size());
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    //  Splay
    // ════════════════════════════════════════════════════════════════════════

    @Nested
    @DisplayName("SplayStrategy")
    class Splay {

        @Test @DisplayName("mixed workload keeps BST order and size (no balance invariant)")
        void mixed() {
            mixedWorkload(SplayStrategy::new, 33, 4000, 800, (t, o) -> { /* BST only */ });
        }

        @Test @DisplayName("the accessed key is splayed to the root on a hit")
        void accessSplaysToRoot() {
            RedBlackTree<Integer> t = tree(new SplayStrategy<>());
            for (int i = 0; i < 200; i++) t.add(i);
            Random rng = new Random(5);
            for (int i = 0; i < 100; i++) {
                int k = rng.nextInt(200);
                assertTrue(t.contains(k));
                assertEquals(k, t.getRoot().getData(),
                        "splay tree must move the accessed key to the root");
            }
        }

        @Test @DisplayName("the inserted key becomes the root")
        void insertSplaysToRoot() {
            RedBlackTree<Integer> t = tree(new SplayStrategy<>());
            int[] xs = {50, 10, 90, 30, 70, 5};
            for (int x : xs) {
                t.add(x);
                assertEquals(x, t.getRoot().getData(), "insert must splay new key to root");
            }
        }

        @Test @DisplayName("sequential inserts + locality searches stay ordered")
        void localityOrdered() {
            RedBlackTree<Integer> t = tree(new SplayStrategy<>());
            TreeSet<Integer> oracle = new TreeSet<>();
            for (int i = 0; i < 500; i++) { t.add(i); oracle.add(i); }
            Random rng = new Random(9);
            for (int i = 0; i < 2000; i++) t.contains(rng.nextInt(20)); // hot set
            assertMatchesOracle(t, oracle);
            assertBstShape(t);
            assertOrderStatistics(t, oracle);
        }

        @Test @DisplayName("root's parent is the sentinel, never null")
        void rootParentSentinel() {
            RedBlackTree<Integer> t = tree(new SplayStrategy<>());
            for (int i = 0; i < 50; i++) t.add(i * 3);
            TreeNode1<Integer> root = t.getRoot();
            assertTrue(root.getParent() == null || root.getParent().isNil(),
                    "root parent must be null or the sentinel");
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    //  Hybrid
    // ════════════════════════════════════════════════════════════════════════

    @Nested
    @DisplayName("HybridStrategy")
    class Hybrid {

        // Default Hybrid uses depthThreshold = Integer.MAX_VALUE → tolerance 1
        // everywhere, so it should hold strict AVL balance plus its RB recolor pass.
        @Test @DisplayName("mixed workload keeps AVL balance, order, size, order-stats")
        void mixed() {
            mixedWorkload(HybridStrategy::new, 44, 3000, 600,
                    (t, o) -> assertAvlBalanced(t));
        }

        @Test @DisplayName("ascending inserts stay balanced and root is black")
        void ascending() {
            RedBlackTree<Integer> t = tree(new HybridStrategy<>());
            for (int i = 0; i < 800; i++) t.add(i);
            assertAvlBalanced(t);
            assertTrue(t.getRoot().isBlack(), "hybrid forces a black root");
        }

        @Test @DisplayName("delete-heavy sequence stays balanced and ordered")
        void deleteHeavy() {
            RedBlackTree<Integer> t = tree(new HybridStrategy<>());
            TreeSet<Integer> oracle = new TreeSet<>();
            for (int i = 0; i < 400; i++) { t.add(i); oracle.add(i); }
            Random rng = new Random(13);
            List<Integer> vals = new ArrayList<>(oracle);
            java.util.Collections.shuffle(vals, rng);
            for (int i = 0; i < 300; i++) { t.remove(vals.get(i)); oracle.remove(vals.get(i)); }
            assertMatchesOracle(t, oracle);
            assertAvlBalanced(t);
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    //  Cross-strategy edge cases
    // ════════════════════════════════════════════════════════════════════════

    @Nested
    @DisplayName("Edge cases (all strategies)")
    class EdgeCases {

        private final List<Supplier<TreeStrategy<Integer>>> strategies = List.of(
                RedBlackStrategy::new, AVLStrategy::new, SplayStrategy::new, HybridStrategy::new);

        @Test @DisplayName("empty tree: contains is false, size 0, inOrder empty")
        void empty() {
            for (Supplier<TreeStrategy<Integer>> s : strategies) {
                RedBlackTree<Integer> t = tree(s.get());
                assertFalse(t.contains(1));
                assertEquals(0, t.size());
                assertTrue(t.inOrder().isEmpty());
            }
        }

        @Test @DisplayName("duplicate inserts are ignored (set semantics)")
        void duplicates() {
            for (Supplier<TreeStrategy<Integer>> s : strategies) {
                RedBlackTree<Integer> t = tree(s.get());
                t.add(5); t.add(5); t.add(5);
                assertEquals(1, t.size(), s.get().getClass().getSimpleName() + " dedup");
                assertEquals(List.of(5), t.inOrder());
            }
        }

        @Test @DisplayName("remove of a missing key is a no-op")
        void removeMissing() {
            for (Supplier<TreeStrategy<Integer>> s : strategies) {
                RedBlackTree<Integer> t = tree(s.get());
                t.add(1); t.add(2);
                t.remove(99);
                assertEquals(2, t.size());
                assertEquals(List.of(1, 2), t.inOrder());
            }
        }

        @Test @DisplayName("insert then remove all empties the tree")
        void drain() {
            for (Supplier<TreeStrategy<Integer>> s : strategies) {
                RedBlackTree<Integer> t = tree(s.get());
                for (int i = 0; i < 100; i++) t.add(i);
                for (int i = 0; i < 100; i++) t.remove(i);
                assertEquals(0, t.size(), s.get().getClass().getSimpleName() + " drained");
                assertTrue(t.getRoot().isNil());
                assertFalse(t.contains(50));
            }
        }
    }
}
