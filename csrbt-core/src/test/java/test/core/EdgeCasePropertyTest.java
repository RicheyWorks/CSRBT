package test.core;

import io.github.richeyworks.csrbt.BPlusTreeEngine;
import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.PersistentRankedSet;
import io.github.richeyworks.csrbt.interfaces.RankedSet;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.HybridStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;
import io.github.richeyworks.csrbt.strategy.WeightBalancedStrategy;
import io.github.richeyworks.csrbt.util.StrategyHealthCheck;

import net.jqwik.api.Arbitraries;
import net.jqwik.api.Arbitrary;
import net.jqwik.api.Combinators;
import net.jqwik.api.ForAll;
import net.jqwik.api.Property;
import net.jqwik.api.Provide;
import net.jqwik.api.Tuple;
import net.jqwik.api.Tuple.Tuple2;
import net.jqwik.api.constraints.IntRange;
import net.jqwik.api.constraints.Size;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.NoSuchElementException;
import java.util.TreeSet;
import java.util.function.Supplier;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Edge-case hardening pass, 2026-08-17 — the generated half.
 *
 * <p>{@link OrderedSetPropertyTest} already churns generated op sequences against a {@link TreeSet}
 * oracle for the four fixed strategies. This class covers the axes a hand-written case samples
 * badly: the <em>key domain</em> (generators are biased hard toward {@code Integer.MIN_VALUE} /
 * {@code MAX_VALUE} and zero, which a hand-written test reaches for exactly once), the
 * <em>range/order-statistic surface</em> at arbitrary bound pairs including inverted ones, and
 * <em>cross-implementation parity</em>, where {@code OrderedSet}, {@code BPlusTreeEngine} and
 * {@code PersistentRankedSet} must agree op for op — that agreement is the premise VERIFIED voting
 * rests on, and nothing generated was checking it.</p>
 *
 * <p>Generators stay modest (≤ 150 ops) so the whole class fits the suite's time budget.</p>
 */
class EdgeCasePropertyTest {

    private static final List<Supplier<TreeStrategy<Integer>>> STRATEGIES = List.of(
            RedBlackStrategy::new, AVLStrategy::new, SplayStrategy::new,
            WeightBalancedStrategy::new, HybridStrategy::new);

    /** Keys drawn from the whole int domain, with the extremes and zero heavily over-sampled. */
    @Provide
    Arbitrary<Integer> extremeKeys() {
        return Arbitraries.frequencyOf(
                Tuple.of(4, Arbitraries.of(Integer.MIN_VALUE, Integer.MIN_VALUE + 1, -1, 0, 1,
                        Integer.MAX_VALUE - 1, Integer.MAX_VALUE)),
                Tuple.of(3, Arbitraries.integers().between(-3, 3)),
                Tuple.of(3, Arbitraries.integers()));
    }

    /** Lists of the same extreme-biased keys — a named provider supplies the WHOLE parameter. */
    @Provide
    Arbitrary<List<Integer>> extremeKeyLists() {
        return extremeKeys().list().ofMinSize(0).ofMaxSize(80);
    }

    @Provide
    Arbitrary<List<Integer>> shortExtremeKeyLists() {
        return extremeKeys().list().ofMinSize(0).ofMaxSize(40);
    }

    @Provide
    Arbitrary<Tuple2<Integer, List<Integer>>> strategyAndExtremeOps() {
        return Combinators.combine(
                Arbitraries.integers().between(0, STRATEGIES.size() - 1),
                extremeKeys().list().ofMinSize(0).ofMaxSize(150)).as(Tuple::of);
    }

    @Property(tries = 250)
    void everyStrategyTracksTreeSetOverTheWholeIntDomain(
            @ForAll("strategyAndExtremeOps") Tuple2<Integer, List<Integer>> input) {
        TreeStrategy<Integer> strategy = STRATEGIES.get(input.get1()).get();
        OrderedSet<Integer> set = new OrderedSet<>(strategy, Comparator.<Integer>naturalOrder());
        TreeSet<Integer> oracle = new TreeSet<>();
        List<Integer> ops = input.get2();
        for (int i = 0; i < ops.size(); i++) {
            int key = ops.get(i);
            if (i % 3 == 2) {
                assertEquals(oracle.remove(key), set.remove(key), "remove " + key);
            } else {
                assertEquals(oracle.add(key), set.add(key), "add " + key);
            }
            assertEquals(oracle.size(), set.size());
        }
        assertEquals(new ArrayList<>(oracle), set.inOrder());
        assertEquals(List.of(), StrategyHealthCheck.validate(set.getEngine(), set.getStrategy(),
                set.inOrder()));
        if (!oracle.isEmpty()) {
            assertEquals(oracle.first(), set.minimum());
            assertEquals(oracle.last(), set.maximum());
        } else {
            assertNull(set.minimum());
            assertNull(set.maximum());
        }
    }

    @Property(tries = 200)
    void navigationMatchesTreeSetOnEveryKeyIncludingTheExtremes(
            @ForAll("extremeKeyLists") List<Integer> content,
            @ForAll("extremeKeys") Integer probe) {
        OrderedSet<Integer> set = new OrderedSet<>(new RedBlackStrategy<>(),
                Comparator.<Integer>naturalOrder());
        TreeSet<Integer> oracle = new TreeSet<>();
        for (int k : content) { set.add(k); oracle.add(k); }
        assertEquals(oracle.floor(probe),   set.floor(probe),   "floor " + probe);
        assertEquals(oracle.lower(probe),   set.lower(probe),   "lower " + probe);
        assertEquals(oracle.ceiling(probe), set.ceiling(probe), "ceiling " + probe);
        assertEquals(oracle.higher(probe),  set.higher(probe),  "higher " + probe);
        assertEquals(oracle.headSet(probe, true).size(),  set.countUpTo(probe, true));
        assertEquals(oracle.headSet(probe, false).size(), set.countUpTo(probe, false));
        assertEquals(oracle.contains(probe), set.contains(probe));
    }

    @Property(tries = 200)
    void rangesMatchTreeSetForEveryBoundPairIncludingInvertedOnes(
            @ForAll("shortExtremeKeyLists") List<Integer> content,
            @ForAll("extremeKeys") Integer lo,
            @ForAll("extremeKeys") Integer hi,
            @ForAll boolean loInclusive,
            @ForAll boolean hiInclusive) {
        OrderedSet<Integer> set = new OrderedSet<>(new RedBlackStrategy<>(),
                Comparator.<Integer>naturalOrder());
        TreeSet<Integer> oracle = new TreeSet<>();
        for (int k : content) { set.add(k); oracle.add(k); }

        // Closed-range surface: hi < lo is empty by contract, on both sides of the comparison.
        List<Integer> expectedClosed = lo > hi ? List.of()
                : new ArrayList<>(oracle.subSet(lo, true, hi, true));
        assertEquals(expectedClosed, set.rangeQuery(lo, hi), "rangeQuery [" + lo + ", " + hi + "]");
        assertEquals(expectedClosed.size(), set.countInRange(lo, hi));

        // Inclusivity-parameterised surface, same rule.
        List<Integer> expectedOpen = lo > hi ? List.of()
                : new ArrayList<>(oracle.subSet(lo, loInclusive, hi, hiInclusive));
        assertEquals(expectedOpen, set.rangeSnapshot(lo, loInclusive, hi, hiInclusive),
                "rangeSnapshot " + (loInclusive ? "[" : "(") + lo + ", " + hi + (hiInclusive ? "]" : ")"));
        assertEquals(expectedOpen.size(), set.countBetween(lo, loInclusive, hi, hiInclusive));

        // A null bound means unbounded on that side, and never "everything".
        assertEquals(new ArrayList<>(oracle.headSet(hi, hiInclusive)),
                set.rangeSnapshot(null, true, hi, hiInclusive));
        assertEquals(new ArrayList<>(oracle.tailSet(lo, loInclusive)),
                set.rangeSnapshot(lo, loInclusive, null, true));
        assertEquals(new ArrayList<>(oracle), set.rangeSnapshot(null, true, null, true));
    }

    @Property(tries = 150)
    void allThreeImplementationsAgreeOnEveryOperation(
            @ForAll("extremeKeyLists") List<Integer> content,
            @ForAll("extremeKeys") Integer probe,
            @ForAll @IntRange(min = -50, max = 150) int pct) {
        OrderedSet<Integer> os = new OrderedSet<>(new RedBlackStrategy<>(),
                Comparator.<Integer>naturalOrder());
        BPlusTreeEngine<Integer> bp = BPlusTreeEngine.withNaturalOrder(BPlusTreeEngine.MIN_FANOUT);
        PersistentRankedSet<Integer> pr = PersistentRankedSet.withNaturalOrder();
        TreeSet<Integer> oracle = new TreeSet<>();
        for (int k : content) {
            boolean expected = oracle.add(k);
            assertEquals(expected, os.add(k), "OrderedSet.add " + k);
            assertEquals(expected, bp.add(k), "BPlusTreeEngine.add " + k);
            assertEquals(expected, pr.add(k), "PersistentRankedSet.add " + k);
        }
        List<Integer> expectedOrder = new ArrayList<>(oracle);
        for (RankedSet<Integer> s : List.<RankedSet<Integer>>of(os, bp, pr)) {
            String at = s.getClass().getSimpleName();
            assertEquals(expectedOrder, s.inOrder(), at);
            assertEquals(oracle.size(), s.size(), at);
            assertEquals(oracle.contains(probe), s.contains(probe), at + " contains " + probe);
            assertEquals(oracle.isEmpty() ? null : oracle.first(), s.minimum(), at);
            assertEquals(oracle.isEmpty() ? null : oracle.last(), s.maximum(), at);
            // percentile clamps to [1, n] on all three — including out-of-range pct.
            if (oracle.isEmpty()) {
                assertNull(s.percentile(pct), at + " pct=" + pct);
                assertNull(s.median(), at);
            } else {
                int rank = Math.max(1, Math.min(oracle.size(),
                        (int) Math.ceil(pct / 100.0 * oracle.size())));
                assertEquals(expectedOrder.get(rank - 1), s.percentile(pct), at + " pct=" + pct);
                assertEquals(expectedOrder.get((oracle.size() + 1) / 2 - 1), s.median(), at);
            }
            // rank/select at the ends, on the same key, with the same exception classes.
            if (oracle.contains(probe)) {
                int rank = expectedOrder.indexOf(probe) + 1;
                assertEquals(rank, s.rank(probe), at + " rank " + probe);
                assertEquals(probe, s.select(rank), at + " select " + rank);
                assertEquals(rank < oracle.size() ? expectedOrder.get(rank) : null,
                        s.successor(probe), at + " successor " + probe);
                assertEquals(rank > 1 ? expectedOrder.get(rank - 2) : null,
                        s.predecessor(probe), at + " predecessor " + probe);
            } else {
                assertThrows(NoSuchElementException.class, () -> s.rank(probe), at + " rank " + probe);
            }
            assertThrows(IndexOutOfBoundsException.class, () -> s.select(0), at);
            assertThrows(IndexOutOfBoundsException.class, () -> s.select(oracle.size() + 1), at);
        }
    }

    @Property(tries = 150)
    void aWindowedSetHoldsExactlyTheNewestBoundKeys(
            @ForAll @IntRange(min = 0, max = 12) int bound,
            @ForAll @Size(min = 0, max = 40) List<@IntRange(min = -5, max = 5) Integer> ops) {
        OrderedSet<Integer> set = new OrderedSet<>(new RedBlackStrategy<>(),
                Comparator.<Integer>naturalOrder());
        set.setMaxSize(bound);
        // A LinkedHashSet is the same FIFO-of-live-keys model the window maintains.
        java.util.LinkedHashSet<Integer> fifo = new java.util.LinkedHashSet<>();
        for (int k : ops) {
            set.add(k);
            fifo.add(k);
            while (bound > 0 && fifo.size() > bound) {
                java.util.Iterator<Integer> it = fifo.iterator();
                it.next();
                it.remove();
            }
            assertEquals(fifo.size(), set.size(), "after add " + k + " under bound " + bound);
            assertTrue(bound == 0 || set.size() <= bound, "the bound is a ceiling, never exceeded");
            assertEquals(new TreeSet<>(fifo).stream().toList(), set.inOrder(),
                    "after add " + k + " under bound " + bound);
        }
        assertEquals(List.of(), StrategyHealthCheck.validate(set.getEngine(), set.getStrategy(),
                set.inOrder()));
    }

    @Property(tries = 120)
    void theBPlusTreeStaysStructurallyValidAtTheFanoutFloor(
            @ForAll @IntRange(min = 4, max = 8) int fanout,
            @ForAll @Size(min = 0, max = 120) List<@IntRange(min = -20, max = 20) Integer> ops) {
        BPlusTreeEngine<Integer> b = BPlusTreeEngine.withNaturalOrder(fanout);
        TreeSet<Integer> oracle = new TreeSet<>();
        for (int i = 0; i < ops.size(); i++) {
            int k = ops.get(i);
            if (i % 3 == 2) assertEquals(oracle.remove(k), b.remove(k), "remove " + k);
            else            assertEquals(oracle.add(k), b.add(k), "add " + k);
            assertEquals(List.of(), b.validateStructure(), "after op " + i + " (fanout " + fanout + ")");
            assertEquals(oracle.size(), b.size());
        }
        assertEquals(new ArrayList<>(oracle), b.inOrder());
    }
}
