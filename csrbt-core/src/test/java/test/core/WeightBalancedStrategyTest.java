package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.RedBlackTree;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.strategy.WeightBalancedStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-011 V1 — the parameterized weight-balanced strategy and the health gate's
 * strategy-supplied invariant hook. Discipline mirrors ADR-005's: oracle parity with the
 * strategy's own {@code validateInvariant} run every few hundred ops, degenerate inputs,
 * and — new here — the same proof repeated at several <em>grid points</em>, because each
 * (Δ, Γ) the search may try must be empirically sound, not assumed. Plus morph interop:
 * the health gate accepts a healthy parameterized candidate (through the hook) and the
 * full RB → WB → Splay round trip preserves contents and order statistics.
 */
@DisplayName("WeightBalancedStrategy(Δ,Γ) + invariant hook (ADR-011 V1)")
public class WeightBalancedStrategyTest {

    private static void assertValid(RedBlackTree<Integer> tree,
                                    WeightBalancedStrategy<Integer> ws, String when) {
        List<String> v = ws.validateInvariant(tree);
        assertTrue(v.isEmpty(), when + ": " + v);
    }

    @Nested
    @DisplayName("oracle parity + invariants, per grid point")
    class Grid {

        private void churnAt(int delta, int ratio) {
            WeightBalancedStrategy<Integer> ws = new WeightBalancedStrategy<>(delta, ratio);
            RedBlackTree<Integer> tree = RedBlackTree.withNaturalOrder(ws);
            TreeSet<Integer> oracle = new TreeSet<>();
            Random rnd = new Random(11_2026 + delta * 31 + ratio);

            for (int op = 1; op <= 4_000; op++) {
                int key = rnd.nextInt(700);
                if (rnd.nextInt(100) < 55) {
                    tree.add(key);
                    oracle.add(key);
                } else {
                    tree.remove(key);
                    oracle.remove(key);
                }
                if (op % 250 == 0) {
                    assertValid(tree, ws, "(" + delta + "," + ratio + ") op " + op);
                    assertEquals(new ArrayList<>(oracle), tree.inOrder(),
                            "(" + delta + "," + ratio + ") contents @op " + op);
                }
            }
            assertValid(tree, ws, "(" + delta + "," + ratio + ") final");
            assertEquals(oracle.size(), tree.size());
        }

        @Test
        @DisplayName("the verified default (3,2) matches a TreeSet oracle under churn")
        void verifiedDefault() { churnAt(3, 2); }

        @Test
        @DisplayName("candidate arm (4,2) is empirically sound under churn")
        void candidateArm42() {
            churnAt(4, 2);
        }

        @Test
        @DisplayName("the viability constraint, demonstrated: (5,3) is UNSOUND and self-disqualifies")
        void unsoundArmSelfDisqualifies() {
            // Discovered by this suite's own first run: at (5,3) the one-rotation-per-level
            // repair does not restore Δ-balance under delete churn — the strategy's own
            // invariant hook catches it (first seen: op 500, node with child sizes 2/0).
            // This is ADR-011's self-disqualification mechanism working before the bandit
            // exists: candidate arms are EMPIRICAL, and unsound ones announce themselves.
            // Only (3,2) carries a literature proof; everything else must earn its place.
            WeightBalancedStrategy<Integer> ws = new WeightBalancedStrategy<>(5, 3);
            RedBlackTree<Integer> tree = RedBlackTree.withNaturalOrder(ws);
            TreeSet<Integer> oracle = new TreeSet<>();
            Random rnd = new Random(11_2026 + 5 * 31 + 3);   // the discovering seed

            boolean violationSeen = false;
            for (int op = 1; op <= 4_000 && !violationSeen; op++) {
                int key = rnd.nextInt(700);
                if (rnd.nextInt(100) < 55) { tree.add(key); oracle.add(key); }
                else                       { tree.remove(key); oracle.remove(key); }
                if (op % 100 == 0) violationSeen = !ws.validateInvariant(tree).isEmpty();
            }
            assertTrue(violationSeen, "(5,3) must trip its own invariant — if this ever "
                    + "passes clean, the repair changed and the sound region needs re-mapping");
            assertEquals(new ArrayList<>(oracle), tree.inOrder(),
                    "even an unsound arm never loses data — only balance");
        }

        @Test
        @DisplayName("degenerate inputs stay logarithmic at (3,2)")
        void degenerateInputs() {
            for (int variant = 0; variant < 3; variant++) {
                WeightBalancedStrategy<Integer> ws = new WeightBalancedStrategy<>();
                RedBlackTree<Integer> tree = RedBlackTree.withNaturalOrder(ws);
                int n = 2_000;
                for (int i = 0; i < n; i++) {
                    int key = switch (variant) {
                        case 0 -> i;                              // sorted
                        case 1 -> n - i;                          // reverse
                        default -> (i % 2 == 0) ? i : 2 * n - i;  // organ pipe
                    };
                    tree.add(key);
                }
                assertValid(tree, ws, "variant " + variant);
                assertTrue(heightOf(tree) <= 24,
                        "variant " + variant + " height " + heightOf(tree) + " not logarithmic");
            }
        }

        @Test
        @DisplayName("parameter bounds are enforced")
        void bounds() {
            assertThrows(IllegalArgumentException.class, () -> new WeightBalancedStrategy<Integer>(1, 1));
            assertThrows(IllegalArgumentException.class, () -> new WeightBalancedStrategy<Integer>(3, 3));
            assertThrows(IllegalArgumentException.class, () -> new WeightBalancedStrategy<Integer>(3, 0));
            assertEquals(3, new WeightBalancedStrategy<Integer>().delta());
            assertEquals(2, new WeightBalancedStrategy<Integer>().ratio());
        }

        private int heightOf(RedBlackTree<Integer> tree) {
            return depth(tree, tree.getRoot());
        }

        private int depth(RedBlackTree<Integer> tree, io.github.richeyworks.csrbt.TreeNode1<Integer> n) {
            if (n == null || n.isNil()) return 0;
            return 1 + Math.max(depth(tree, n.getLeft()), depth(tree, n.getRight()));
        }
    }

    @Nested
    @DisplayName("the health gate hook + morph interop")
    class GateAndMorph {

        @Test
        @DisplayName("health-gated morphs RB → WB(3,2) → Splay preserve contents and order stats")
        void morphRoundTrip() {
            OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
            Random rnd = new Random(7);
            TreeSet<Integer> oracle = new TreeSet<>();
            for (int i = 0; i < 800; i++) {
                int k = rnd.nextInt(5_000);
                set.add(k);
                oracle.add(k);
            }

            assertTrue(set.setStrategy(new WeightBalancedStrategy<>()),
                    "the gate validates the WB candidate through the strategy-supplied hook");
            assertEquals(new ArrayList<>(oracle), set.inOrder());
            assertEquals(oracle.first(), set.minimum());
            assertEquals(oracle.size() / 2 + oracle.size() % 2,
                    set.rank(set.median()), "order statistics exact after the morph");

            assertTrue(set.setStrategy(new SplayStrategy<>()), "WB deposes cleanly too");
            assertEquals(new ArrayList<>(oracle), set.inOrder());
        }

        @Test
        @DisplayName("the hook reports violations: a Splay spine fails WB's own Δ check")
        void hookReportsViolations() {
            RedBlackTree<Integer> spine = RedBlackTree.withNaturalOrder(new SplayStrategy<Integer>());
            for (int i = 0; i < 64; i++) spine.add(i);    // sorted inserts: a 64-deep spine

            WeightBalancedStrategy<Integer> ws = new WeightBalancedStrategy<>();
            List<String> violations = ws.validateInvariant(spine);
            assertFalse(violations.isEmpty(), "a spine grossly violates Δ=3 weight balance");
            assertTrue(violations.get(0).contains("Δ=3"), violations.get(0));
        }

        @Test
        @DisplayName("the classic strategies' default hook stays silent (gate behavior unchanged)")
        void defaultHookSilent() {
            RedBlackTree<Integer> tree = RedBlackTree.withNaturalOrder(new RedBlackStrategy<Integer>());
            for (int i = 0; i < 100; i++) tree.add(i);
            assertTrue(new RedBlackStrategy<Integer>().validateInvariant(tree).isEmpty());
            assertTrue(new SplayStrategy<Integer>().validateInvariant(tree).isEmpty());
        }
    }
}
