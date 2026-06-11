package test.core;

import core.ensemble.EnsembleMember;
import core.ensemble.EnsembleOrderedSet;
import core.strategy.AVLStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Random;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * EnsembleOrderedSet (ADR-003, step E1): MIRROR-mode fan-out keeps every member an exact copy of
 * the logical set, and the primary's answers match a {@link TreeSet} oracle. Covers membership,
 * ordering, size, effective-mutation return values, and the unambiguous order statistics
 * (select / rank / min / max), plus member agreement across a randomized op stream.
 */
@DisplayName("EnsembleOrderedSet — mirror fan-out (E1)")
public class EnsembleOrderedSetTest {

    private static EnsembleOrderedSet<Integer> rbAvlSplay() {
        return EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())   // initial primary
                .member(() -> new AVLStrategy<Integer>())
                .member(() -> new SplayStrategy<Integer>())
                .build();
    }

    @Test
    @DisplayName("every member tracks a TreeSet oracle across a randomized mixed op stream")
    void mirrorsAgreeWithOracle() {
        EnsembleOrderedSet<Integer> ens = rbAvlSplay();
        TreeSet<Integer> oracle = new TreeSet<>();
        Random rng = new Random(42);

        for (int i = 0; i < 4000; i++) {
            int v = rng.nextInt(500);          // bounded range -> real duplicates + absent removes
            if (rng.nextBoolean()) {
                assertEquals(oracle.add(v), ens.add(v), "add() effective-change parity at op " + i);
            } else {
                assertEquals(oracle.remove(v), ens.remove(v), "remove() effective-change parity at op " + i);
            }
        }

        List<Integer> sorted = new ArrayList<>(oracle);
        assertEquals(sorted, ens.inOrder(), "primary in-order matches the oracle");
        assertEquals(oracle.size(), ens.size(), "size matches the oracle");

        for (EnsembleMember<Integer> m : ens.members()) {
            assertEquals(sorted, m.set().inOrder(),
                    m.strategyName() + " must be an exact mirror of the logical set");
            assertEquals(oracle.size(), m.set().size(), m.strategyName() + " size matches");
        }
    }

    @Test
    @DisplayName("order statistics on the ensemble match the oracle (select / rank / min / max)")
    void orderStatisticsMatchOracle() {
        EnsembleOrderedSet<Integer> ens = rbAvlSplay();
        TreeSet<Integer> oracle = new TreeSet<>();
        for (int v : new int[]{50, 20, 80, 10, 30, 60, 90, 70, 40, 5}) { ens.add(v); oracle.add(v); }

        List<Integer> sorted = new ArrayList<>(oracle);
        for (int r = 1; r <= sorted.size(); r++) {
            assertEquals(sorted.get(r - 1), ens.select(r), "select(" + r + ") is the r-th smallest");
        }
        for (int idx = 0; idx < sorted.size(); idx++) {
            assertEquals(idx + 1, ens.rank(sorted.get(idx)), "rank() is the 1-based position");
        }
        assertEquals(oracle.first(), ens.minimum(), "minimum");
        assertEquals(oracle.last(), ens.maximum(), "maximum");
    }

    @Test
    @DisplayName("an ensemble requires at least two members")
    void rejectsTooFewMembers() {
        assertThrows(IllegalArgumentException.class, () ->
                EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                        .member(() -> new RedBlackStrategy<Integer>())
                        .build());
    }
}
