package test.core;

import io.github.richeyworks.csrbt.BPlusTreeEngine;
import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleMode;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.NoSuchElementException;
import java.util.Random;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-008 D1 — the page-structured B+tree engine. Oracle parity against {@code TreeSet}
 * under seeded random churn at the fanout floor (4 — maximal split/borrow/merge churn), with
 * {@code validateStructure()} run every few hundred ops per house style (ADR-005 §7);
 * degenerate inputs; the full order-statistics surface against {@code OrderedSet}'s answers
 * (the voting-parity contract, proven again end-to-end by a VERIFIED ensemble whose members
 * must reach unanimity); and the {@code OrderedSet}-parity edge semantics one by one.
 */
@DisplayName("BPlusTreeEngine — page-structured large-n engine (ADR-008 D1)")
public class BPlusTreeEngineTest {

    private static void assertValid(BPlusTreeEngine<Integer> t, String when) {
        List<String> v = t.validateStructure();
        assertTrue(v.isEmpty(), when + ": " + v);
    }

    @Nested
    @DisplayName("oracle parity + invariants")
    class Oracle {

        @Test
        @DisplayName("random churn at the fanout floor matches TreeSet; invariants hold throughout")
        void randomChurnParity() {
            BPlusTreeEngine<Integer> tree = BPlusTreeEngine.withNaturalOrder(BPlusTreeEngine.MIN_FANOUT);
            TreeSet<Integer> oracle = new TreeSet<>();
            Random rnd = new Random(8_2026);

            for (int op = 1; op <= 6_000; op++) {
                int key = rnd.nextInt(800);
                if (rnd.nextInt(100) < 55) {
                    assertEquals(oracle.add(key), tree.add(key), "add(" + key + ") @op " + op);
                } else {
                    assertEquals(oracle.remove(key), tree.remove(key), "remove(" + key + ") @op " + op);
                }
                if (op % 250 == 0) {
                    assertValid(tree, "op " + op);
                    assertEquals(oracle.size(), tree.size(), "size @op " + op);
                    assertEquals(new ArrayList<>(oracle), tree.inOrder(), "inOrder @op " + op);
                }
            }
            assertValid(tree, "final");
            assertEquals(new ArrayList<>(oracle), tree.inOrder());
        }

        @Test
        @DisplayName("sorted, reverse, and organ-pipe input stay shallow and valid")
        void degenerateInputs() {
            for (int variant = 0; variant < 3; variant++) {
                BPlusTreeEngine<Integer> tree =
                        BPlusTreeEngine.withNaturalOrder(BPlusTreeEngine.MIN_FANOUT);
                int n = 2_000;
                for (int i = 0; i < n; i++) {
                    int key = switch (variant) {
                        case 0 -> i;                                   // sorted
                        case 1 -> n - i;                               // reverse
                        default -> (i % 2 == 0) ? i : 2 * n - i;       // organ pipe
                    };
                    tree.add(key);
                }
                assertValid(tree, "variant " + variant);
                assertEquals(n, tree.size());
                // log_2(n) levels at the floor (fanout 4 => >= 2 children per internal node)
                assertTrue(tree.height() <= 12,
                        "variant " + variant + " height " + tree.height() + " not logarithmic");
            }
        }

        @Test
        @DisplayName("delete-heavy churn drains the tree through merges to empty, validly")
        void drainToEmpty() {
            BPlusTreeEngine<Integer> tree = BPlusTreeEngine.withNaturalOrder(BPlusTreeEngine.MIN_FANOUT);
            for (int i = 0; i < 1_000; i++) tree.add(i);
            Random rnd = new Random(42);
            List<Integer> keys = new ArrayList<>();
            for (int i = 0; i < 1_000; i++) keys.add(i);
            java.util.Collections.shuffle(keys, rnd);
            int removed = 0;
            for (int k : keys) {
                assertTrue(tree.remove(k));
                if (++removed % 200 == 0) assertValid(tree, "after " + removed + " removes");
            }
            assertEquals(0, tree.size());
            assertTrue(tree.isEmpty());
            assertValid(tree, "empty");
            assertEquals(0, tree.height());
        }
    }

    @Nested
    @DisplayName("order statistics — OrderedSet parity")
    class OrderStats {

        @Test
        @DisplayName("select/rank/successor/predecessor/median/percentile/countInRange agree with OrderedSet")
        void parityWithOrderedSet() {
            BPlusTreeEngine<Integer> tree = BPlusTreeEngine.withNaturalOrder(BPlusTreeEngine.MIN_FANOUT);
            OrderedSet<Integer> reference =
                    new OrderedSet<Integer>(new RedBlackStrategy<Integer>(), Comparator.<Integer>naturalOrder());
            Random rnd = new Random(7);
            for (int i = 0; i < 700; i++) {
                int k = rnd.nextInt(5_000);
                tree.add(k);
                reference.add(k);
            }

            assertEquals(reference.size(), tree.size());
            for (int r = 1; r <= reference.size(); r += 13) {
                assertEquals(reference.select(r), tree.select(r), "select(" + r + ")");
            }
            for (int k : tree.inOrder().subList(0, 50)) {
                assertEquals(reference.rank(k), tree.rank(k), "rank(" + k + ")");
                assertEquals(reference.successor(k), tree.successor(k), "successor(" + k + ")");
                assertEquals(reference.predecessor(k), tree.predecessor(k), "predecessor(" + k + ")");
            }
            assertEquals(reference.minimum(), tree.minimum());
            assertEquals(reference.maximum(), tree.maximum());
            assertEquals(reference.median(), tree.median());
            for (int pct : new int[] {0, 1, 25, 50, 75, 99, 100}) {
                assertEquals(reference.percentile(pct), tree.percentile(pct), "percentile(" + pct + ")");
            }
            assertEquals(reference.countInRange(500, 2_500), tree.countInRange(500, 2_500));
            assertEquals(reference.rangeQuery(500, 2_500), tree.rangeQuery(500, 2_500));
            assertEquals(0, tree.countInRange(2_500, 500), "lo > hi counts zero");
            assertTrue(tree.rangeQuery(2_500, 500).isEmpty(), "lo > hi yields empty");
        }

        @Test
        @DisplayName("empty/absent edge semantics match the RankedSet voting-parity contract")
        void edgeSemantics() {
            BPlusTreeEngine<Integer> tree = BPlusTreeEngine.withNaturalOrder();
            assertNull(tree.minimum());
            assertNull(tree.maximum());
            assertNull(tree.median());
            assertNull(tree.percentile(50));
            assertThrows(IndexOutOfBoundsException.class, () -> tree.select(1));
            assertThrows(NoSuchElementException.class, () -> tree.rank(7));
            assertThrows(NoSuchElementException.class, () -> tree.successor(7));

            tree.add(10);
            tree.add(20);
            assertThrows(NoSuchElementException.class, () -> tree.successor(15),
                    "successor of an absent key throws, like OrderedSet");
            assertNull(tree.successor(20), "null at the top extreme");
            assertNull(tree.predecessor(10), "null at the bottom extreme");
            assertFalse(tree.contains(null), "contains(null) is false, never a throw");
            assertThrows(IllegalArgumentException.class, () -> tree.add(null));
            assertThrows(IllegalArgumentException.class, () ->
                    new BPlusTreeEngine<Integer>(3, Comparator.naturalOrder()));
        }
    }

    @Nested
    @DisplayName("ensemble citizenship (via the engineMember seam)")
    class Ensemble {

        @Test
        @DisplayName("a B+tree member reaches VERIFIED unanimity with strategy members — parity, end to end")
        void verifiedUnanimityWithStrategyMembers() {
            EnsembleOrderedSet<Integer> ens =
                    EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                            .member(() -> new RedBlackStrategy<Integer>())
                            .member(() -> new AVLStrategy<Integer>())
                            .engineMember(() -> BPlusTreeEngine.<Integer>withNaturalOrder(), "BPlusTreeEngine")
                            .mode(EnsembleMode.VERIFIED)
                            .build();
            Random rnd = new Random(11);
            for (int i = 0; i < 1_500; i++) ens.add(rnd.nextInt(10_000));
            for (int i = 0; i < 300; i++) ens.remove(rnd.nextInt(10_000));

            // Every read below is a 3-way vote; one dissent would quarantine somebody.
            int n = ens.size();
            for (int r = 1; r <= n; r += 97) ens.select(r);
            for (int k : ens.rangeQuery(0, 800)) assertTrue(ens.contains(k));
            ens.median();
            ens.percentile(90);
            ens.countInRange(100, 9_000);
            for (EnsembleMember<Integer> m : ens.members()) {
                assertEquals(EnsembleMember.State.ACTIVE, m.state(),
                        m.strategyName() + " — unanimity throughout is the parity proof");
            }

            EnsembleMember<Integer> bpt = null;
            for (EnsembleMember<Integer> m : ens.members()) {
                if (m.strategyName().equals("BPlusTreeEngine")) bpt = m;
            }
            assertFalse(bpt.isStrategyBacked());
            assertTrue(ens.promote(bpt), "explicitly promotable, like any engine member");
            assertEquals(n, ens.size(), "serves correctly as primary");
        }
    }
}
