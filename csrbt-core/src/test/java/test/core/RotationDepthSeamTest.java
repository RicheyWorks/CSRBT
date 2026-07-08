package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The workload-signal seams added for external feeders (SuperBeefSort et al.):
 * {@link OrderedSet#rotationCount()} — structural churn, the {@code rotationsPerWrite} source — and
 * {@link OrderedSet#searchDepth} — realized search depth, the {@code recordSearch(hash, depth)} source.
 * Both existed as concepts in {@code WorkloadFeatures} but had no public origin before this seam.
 */
class RotationDepthSeamTest {

    @Test
    void rotationCounterMetersAscendingInsertChurn() {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        for (int i = 0; i < 256; i++) {
            set.add(i);   // ascending inserts force RB fixups: rotations must occur
        }
        assertTrue(set.rotationCount() > 0,
                "256 ascending inserts must incur rebalancing rotations");
    }

    @Test
    void bulkBuildPerformsZeroRotations() {
        List<Integer> keys = new ArrayList<>();
        for (int i = 0; i < 1024; i++) {
            keys.add(i);
        }
        OrderedSet<Integer> set = OrderedSet.fromSortedNatural(keys, new RedBlackStrategy<Integer>());
        assertEquals(0, set.rotationCount(),
                "the O(n) balanced build is documented as rotation-free");
        assertEquals(1024, set.size());
    }

    @Test
    void searchDepthEncodesContainmentAndDepth() {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        for (int i = 0; i < 100; i++) {
            set.add(i);
        }
        int present = set.searchDepth(50);
        assertTrue(present >= 1, "present key: positive depth (nodes touched), was " + present);
        assertTrue(present <= 2 * 7 + 1, "RB height bound: depth <= 2*log2(n)+1, was " + present);

        int absent = set.searchDepth(1_000);
        assertTrue(absent < 0, "absent key: negative (complement-encoded), was " + absent);
        assertTrue(~absent >= 1, "absent key on a non-empty tree still walks >= 1 node");

        assertTrue(set.contains(50));
        assertFalse(set.contains(1_000));
    }

    @Test
    void searchDepthOnEmptySetIsComplementZero() {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        assertEquals(~0, set.searchDepth(42), "empty tree: zero nodes touched, absent");
    }

    @Test
    void searchDepthDoesNotMutate() {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        for (int i = 0; i < 64; i++) {
            set.add(i);
        }
        int first = set.searchDepth(7);
        int second = set.searchDepth(7);
        assertEquals(first, second, "the measuring read must not restructure the tree");
        assertEquals(64, set.size());
    }
}
