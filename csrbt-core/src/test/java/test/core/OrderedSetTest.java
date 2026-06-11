package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.NavigableSet;
import java.util.Random;
import java.util.TreeSet;
import java.util.function.Supplier;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Generic-facade tests for {@link OrderedSet} (ADR-002 step 4).
 *
 * <p>Where the {@code int} {@code TreeContext} suite exercises the {@code Integer}
 * adapter, this suite proves the facade is genuinely key-type-agnostic: every test
 * here uses <em>non-{@code Integer}</em> keys — {@link String}s under natural order
 * and under a reverse {@link Comparator} — and cross-checks every ordered-set and
 * order-statistic answer against a {@link TreeSet} oracle built with the <em>same</em>
 * comparator. Coverage mirrors §1 of the step-4 plan: dedup-guarded add/remove with a
 * size counter, the full order-statistics surface, sliding-window eviction, the
 * health-gated strategy morph, self-repair, augmentation, and the accessors/metrics.</p>
 */
@DisplayName("OrderedSet<K> generic facade")
class OrderedSetTest {

    // ── strategy factories (each test gets fresh strategy instances) ────────────
    private static final List<Supplier<TreeStrategy<String>>> STRATEGIES = Arrays.asList(
            RedBlackStrategy::new, AVLStrategy::new, SplayStrategy::new);

    private static OrderedSet<String> rbNatural() {
        return OrderedSet.withNaturalOrder(new RedBlackStrategy<String>());
    }

    /** Assert the set agrees with the oracle on contents, size, and the whole order-stat surface. */
    private static void assertMatchesOracle(OrderedSet<String> set, NavigableSet<String> oracle) {
        List<String> expected = new ArrayList<>(oracle);
        assertEquals(oracle.size(), set.size(), "size");
        assertEquals(oracle.isEmpty(), set.isEmpty(), "isEmpty");
        assertEquals(expected, set.inOrder(), "inOrder must follow the comparator");

        for (String k : expected) assertTrue(set.contains(k), "contains " + k);

        int n = expected.size();
        for (int r = 1; r <= n; r++) {
            String key = expected.get(r - 1);
            assertEquals(key, set.select(r), "select(" + r + ")");
            assertEquals(r, set.rank(key), "rank(" + key + ")");
        }
        if (n > 0) {
            assertEquals(expected.get(0), set.minimum(), "minimum");
            assertEquals(expected.get(n - 1), set.maximum(), "maximum");
            assertEquals(expected.get((n - 1) / 2), set.median(), "median (lower)");
            assertEquals(set.minimum(), set.percentile(0), "percentile(0) == min");
            assertEquals(set.maximum(), set.percentile(100), "percentile(100) == max");
            // successor/predecessor against the oracle, for every present key
            for (String k : expected) {
                assertEquals(oracle.higher(k), set.successor(k), "successor(" + k + ")");
                assertEquals(oracle.lower(k), set.predecessor(k), "predecessor(" + k + ")");
            }
        } else {
            assertNull(set.minimum(), "minimum of empty");
            assertNull(set.maximum(), "maximum of empty");
            assertNull(set.median(), "median of empty");
            assertNull(set.percentile(50), "percentile of empty");
        }
    }

    @Nested
    @DisplayName("String keys, natural order")
    class NaturalOrder {

        @Test
        @DisplayName("add/remove are dedup-guarded and report whether they changed the set")
        void addRemoveBooleanContract() {
            OrderedSet<String> set = rbNatural();
            assertTrue(set.add("pear"), "first add inserts");
            assertFalse(set.add("pear"), "duplicate add is a no-op returning false");
            assertEquals(1, set.size());

            assertTrue(set.remove("pear"), "removing a present key returns true");
            assertFalse(set.remove("pear"), "removing an absent key returns false");
            assertTrue(set.isEmpty());
        }

        @Test
        @DisplayName("matches a TreeSet oracle across order statistics and ranges")
        void orderStatisticsExact() {
            OrderedSet<String> set = rbNatural();
            TreeSet<String> oracle = new TreeSet<>();
            for (String k : Arrays.asList(
                    "mango", "apple", "fig", "cherry", "banana", "date", "kiwi", "lime", "guava")) {
                assertEquals(oracle.add(k), set.add(k), "add parity for " + k);
            }
            assertMatchesOracle(set, oracle);

            // closed-range queries
            assertEquals(oracle.subSet("banana", true, "guava", true).size(),
                    set.countInRange("banana", "guava"), "countInRange");
            assertEquals(new ArrayList<>(oracle.subSet("banana", true, "guava", true)),
                    set.rangeQuery("banana", "guava"), "rangeQuery");
            // range with no members
            assertEquals(0, set.countInRange("x", "z"));
            assertTrue(set.rangeQuery("x", "z").isEmpty());
        }

        @Test
        @DisplayName("clear empties the set; order stats on empty return null, not throw")
        void clearAndEmpty() {
            OrderedSet<String> set = rbNatural();
            set.add("a"); set.add("b"); set.add("c");
            set.clear();
            assertMatchesOracle(set, new TreeSet<>());
            // select is positional and must reject out-of-range on an empty set
            assertThrows(IndexOutOfBoundsException.class, () -> set.select(1));
        }

        @Test
        @DisplayName("randomized mixed ops stay in lockstep with the oracle")
        void randomizedAgainstOracle() {
            OrderedSet<String> set = rbNatural();
            TreeSet<String> oracle = new TreeSet<>();
            Random rnd = new Random(42);
            for (int i = 0; i < 4000; i++) {
                String key = "k" + rnd.nextInt(400);
                if (rnd.nextBoolean()) {
                    assertEquals(oracle.add(key), set.add(key), "add parity");
                } else {
                    assertEquals(oracle.remove(key), set.remove(key), "remove parity");
                }
            }
            assertMatchesOracle(set, oracle);
        }
    }

    @Nested
    @DisplayName("String keys, reverse comparator")
    class ReverseComparator {

        @Test
        @DisplayName("ordering, selection and neighbours honour the supplied comparator")
        void comparatorDrivesEverything() {
            Comparator<String> reverse = Comparator.reverseOrder();
            OrderedSet<String> set = new OrderedSet<>(new RedBlackStrategy<>(), reverse);
            TreeSet<String> oracle = new TreeSet<>(reverse);
            for (String k : Arrays.asList("delta", "alpha", "echo", "bravo", "charlie")) {
                set.add(k);
                oracle.add(k);
            }
            assertSame(reverse, set.comparator(), "comparator() returns the supplied authority");
            // inOrder is descending-natural because that is ascending under the comparator
            assertEquals(new ArrayList<>(oracle), set.inOrder());
            assertMatchesOracle(set, oracle);
            // concretely: the comparator-minimum is the largest natural string
            assertEquals("echo", set.minimum());
            assertEquals("alpha", set.maximum());
        }
    }

    @Nested
    @DisplayName("Sliding window (FIFO eviction)")
    class Windowing {

        @Test
        @DisplayName("bounded set evicts oldest-inserted keys to honour the cap")
        void evictsOldestFirst() {
            OrderedSet<String> set = rbNatural();
            set.setMaxSize(3);
            assertEquals(3, set.getMaxSize());
            for (String k : Arrays.asList("a", "b", "c", "d", "e")) set.add(k);
            // a and b (the two oldest) were evicted as c, d, e arrived
            assertEquals(3, set.size());
            assertEquals(Arrays.asList("c", "d", "e"), set.inOrder());
        }

        @Test
        @DisplayName("shrinking the cap after the fact evicts down to it, oldest-first")
        void shrinkAfterInsert() {
            OrderedSet<String> set = rbNatural();
            for (String k : Arrays.asList("a", "b", "c", "d", "e")) set.add(k);
            set.setMaxSize(2);
            assertEquals(2, set.size());
            assertEquals(Arrays.asList("d", "e"), set.inOrder());
        }

        @Test
        @DisplayName("maxSize 0 is unbounded")
        void zeroIsUnbounded() {
            OrderedSet<String> set = rbNatural();
            assertEquals(0, set.getMaxSize());
            for (int i = 0; i < 50; i++) set.add("k" + i);
            assertEquals(50, set.size());
        }
    }

    @Nested
    @DisplayName("Health-gated strategy morph")
    class Morph {

        @Test
        @DisplayName("morphing across RB/AVL/Splay preserves contents and order statistics")
        void morphPreservesContents() {
            OrderedSet<String> set = rbNatural();
            TreeSet<String> oracle = new TreeSet<>();
            for (int i = 0; i < 200; i++) {
                String k = String.format("k%03d", i);   // zero-padded: lexical == numeric
                set.add(k); oracle.add(k);
            }
            assertTrue(set.setStrategy(new AVLStrategy<>()), "RB -> AVL applied");
            assertMatchesOracle(set, oracle);
            assertTrue(set.getStrategy() instanceof AVLStrategy);

            assertTrue(set.setStrategy(new SplayStrategy<>()), "AVL -> Splay applied");
            assertMatchesOracle(set, oracle);

            assertTrue(set.setStrategy(new RedBlackStrategy<>()), "Splay -> RB applied");
            assertMatchesOracle(set, oracle);
        }

        @Test
        @DisplayName("morphing to the incumbent strategy class is a no-op returning false")
        void sameStrategyRejected() {
            OrderedSet<String> set = rbNatural();
            set.add("a"); set.add("b");
            assertFalse(set.setStrategy(new RedBlackStrategy<>()), "same class -> no morph");
            assertFalse(set.setStrategy(null), "null -> no morph");
        }
    }

    @Nested
    @DisplayName("Self-repair, augmentation, accessors")
    class Misc {

        @Test
        @DisplayName("selfRepair rebuilds a healthy tree and preserves its contents")
        void selfRepairKeepsContents() {
            for (Supplier<TreeStrategy<String>> factory : STRATEGIES) {
                OrderedSet<String> set = new OrderedSet<>(factory.get(), Comparator.naturalOrder());
                TreeSet<String> oracle = new TreeSet<>();
                for (int i = 0; i < 64; i++) {
                    String k = String.format("v%02d", i);
                    set.add(k); oracle.add(k);
                }
                assertTrue(set.selfRepair(), "a healthy tree validates after repair");
                assertMatchesOracle(set, oracle);
            }
        }

        @Test
        @DisplayName("setAugmentor swaps the augmentor and null restores the default singleton")
        void augmentorApiContract() {
            OrderedSet<String> set = rbNatural();
            for (String k : Arrays.asList("a", "b", "c")) set.add(k);

            TreeNode1.Augmentor<String> custom = node -> { /* no-op */ };
            set.setAugmentor(custom);
            assertSame(custom, set.getAugmentor(), "augmentor is the one we set");
            // structural reads are augment-independent and must stay correct
            assertEquals(Arrays.asList("a", "b", "c"), set.inOrder());
            assertTrue(set.contains("b"));

            set.setAugmentor(null);
            assertSame(TreeNode1.<String>defaultAugmentor(), set.getAugmentor(),
                    "null resets to the shared default augmentor");
            // with the size-augment restored, order statistics are exact again
            assertEquals("b", set.median());
            assertEquals(2, set.rank("b"));
        }

        @Test
        @DisplayName("accessors and metrics behave")
        void accessorsAndMetrics() {
            OrderedSet<String> set = rbNatural();
            for (int i = 0; i < 10; i++) set.add("k" + i);
            for (int i = 0; i < 5; i++) set.remove("k" + i);
            assertTrue(set.avgInsertTimeMs() >= 0.0);
            assertTrue(set.avgDeleteTimeMs() >= 0.0);
            assertEquals(5, set.getEngine().inOrder().size(), "engine view agrees with the facade");
            assertSame(set.getEngine().getStrategy(), set.getStrategy());
        }
    }
}
