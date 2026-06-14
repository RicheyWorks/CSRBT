package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.util.StrategyHealthCheck;

import net.jqwik.api.Arbitraries;
import net.jqwik.api.Arbitrary;
import net.jqwik.api.ForAll;
import net.jqwik.api.Property;
import net.jqwik.api.Provide;

import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * O(n) {@code fromSorted} bulk-build: a balanced, black-height-correct red-black tree built directly
 * from a sorted distinct run, with correct order statistics and no rotations.
 */
class BulkBuildTest {

    @Test
    void buildsValidBalancedTreeWithCorrectOrderStats() {
        List<Integer> elems = new ArrayList<>();
        for (int i = 1; i <= 1000; i++) {
            elems.add(i);
        }
        OrderedSet<Integer> set = OrderedSet.fromSortedNatural(elems, new RedBlackStrategy<Integer>());

        assertEquals(elems, set.inOrder());
        assertEquals(1000, set.size());
        assertTrue(set.getEngine().getRoot().isBlack(), "root must be black");
        assertTrue(StrategyHealthCheck.validate(set.getEngine(), set.getStrategy(), elems).isEmpty(),
                "bulk-built tree must satisfy the red-black invariants");
        set.getEngine().getRoot().blackHeight(); // throws IllegalStateException on a black-height violation

        assertEquals(Integer.valueOf(1), set.minimum());
        assertEquals(Integer.valueOf(1000), set.maximum());
        assertEquals(Integer.valueOf(500), set.median());     // lower median of 1..1000
        assertEquals(Integer.valueOf(100), set.select(100));  // 1-indexed
        assertEquals(100, set.rank(100));
    }

    @Test
    void equivalentToRepeatedAdd() {
        List<Integer> elems = new ArrayList<>();
        for (int i = 1; i <= 500; i++) {
            elems.add(i * 3); // distinct, ascending
        }
        OrderedSet<Integer> bulk = OrderedSet.fromSortedNatural(elems, new RedBlackStrategy<Integer>());
        OrderedSet<Integer> incremental = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        for (Integer e : elems) {
            incremental.add(e);
        }

        assertEquals(incremental.inOrder(), bulk.inOrder());
        for (int r = 1; r <= elems.size(); r++) {
            assertEquals(incremental.select(r), bulk.select(r), "select(" + r + ") differs");
        }
        for (Integer e : elems) {
            assertEquals(incremental.rank(e), bulk.rank(e), "rank(" + e + ") differs");
        }
    }

    @Test
    void emptyBuildIsEmptySet() {
        OrderedSet<Integer> set = OrderedSet.fromSortedNatural(List.<Integer>of(), new RedBlackStrategy<Integer>());
        assertEquals(0, set.size());
        assertTrue(set.isEmpty());
        assertEquals(List.<Integer>of(), set.inOrder());
    }

    @Test
    void rejectsBadInput() {
        assertThrows(IllegalArgumentException.class,
                () -> OrderedSet.fromSortedNatural(List.of(1, 2, 2, 3), new RedBlackStrategy<Integer>()),
                "duplicates must be rejected");
        assertThrows(IllegalArgumentException.class,
                () -> OrderedSet.fromSortedNatural(List.of(3, 2, 1), new RedBlackStrategy<Integer>()),
                "descending input must be rejected");

        OrderedSet<Integer> nonEmpty = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        nonEmpty.add(1);
        assertThrows(IllegalStateException.class, () -> nonEmpty.buildFromSorted(List.of(2, 3)),
                "buildFromSorted on a non-empty set must be rejected");
    }

    @Property(tries = 200)
    void matchesOracleAndStaysValid(@ForAll("intLists") List<Integer> raw) {
        List<Integer> sortedDistinct = new ArrayList<>(new TreeSet<>(raw)); // sorted, de-duplicated
        OrderedSet<Integer> set = OrderedSet.fromSortedNatural(sortedDistinct, new RedBlackStrategy<Integer>());

        assertEquals(sortedDistinct, set.inOrder());
        assertEquals(sortedDistinct.size(), set.size());
        assertTrue(StrategyHealthCheck.validate(set.getEngine(), set.getStrategy(), sortedDistinct).isEmpty());
        set.getEngine().getRoot().blackHeight(); // throws on violation

        for (int i = 0; i < sortedDistinct.size(); i++) {
            assertEquals(sortedDistinct.get(i), set.select(i + 1));
        }
    }

    @Provide
    Arbitrary<List<Integer>> intLists() {
        return Arbitraries.integers().between(-5000, 5000).list().ofMaxSize(600);
    }
}
