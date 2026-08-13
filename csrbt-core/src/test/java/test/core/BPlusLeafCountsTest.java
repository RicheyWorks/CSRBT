package test.core;

import io.github.richeyworks.csrbt.BPlusTreeEngine;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Random;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The page-occupancy seam (ADR-017): {@code BPlusTreeEngine.leafKeyCounts} — per-leaf
 * fill along the leaf chain. Invariants: counts sum to size; every leaf holds at least
 * the occupancy floor (fanout/2) except a lone root leaf; nothing exceeds fanout; the
 * view stays consistent through splits, merges, and drain-to-empty.
 */
@DisplayName("BPlusTreeEngine.leafKeyCounts — page occupancy along the leaf chain")
class BPlusLeafCountsTest {

    private static final int FANOUT = BPlusTreeEngine.MIN_FANOUT; // 4: forces deep structure

    private static void assertLeafInvariants(BPlusTreeEngine<Integer> t) {
        List<Integer> counts = t.leafKeyCounts();
        long sum = counts.stream().mapToLong(Integer::longValue).sum();
        assertEquals(t.size(), sum, "leaf counts must sum to size");
        for (int c : counts) {
            assertTrue(c <= FANOUT, "leaf over capacity: " + c);
            if (counts.size() > 1) {
                assertTrue(c >= FANOUT / 2, "leaf under occupancy floor: " + c);
            }
        }
        assertTrue(t.validateStructure().isEmpty(), "structure gate must stay green");
    }

    @Test
    @DisplayName("empty tree and lone root leaf")
    void emptyAndRootLeaf() {
        BPlusTreeEngine<Integer> t = BPlusTreeEngine.withNaturalOrder(FANOUT);
        assertTrue(t.leafKeyCounts().isEmpty());
        t.add(1);
        t.add(2);
        assertEquals(List.of(2), t.leafKeyCounts()); // a lone root leaf may sit under the floor
        assertLeafInvariants(t);
    }

    @Test
    @DisplayName("sequential fill: invariants hold through every split")
    void sequentialFill() {
        BPlusTreeEngine<Integer> t = BPlusTreeEngine.withNaturalOrder(FANOUT);
        for (int k = 0; k < 500; k++) {
            t.add(k);
            if (k % 50 == 49) assertLeafInvariants(t);
        }
        assertLeafInvariants(t);
        assertTrue(t.leafKeyCounts().size() > 100, "500 keys at fanout 4 need many leaves");
    }

    @Test
    @DisplayName("random churn: invariants hold through splits, borrows, and merges")
    void randomChurn() {
        BPlusTreeEngine<Integer> t = BPlusTreeEngine.withNaturalOrder(FANOUT);
        Random rng = new Random(31);
        for (int i = 0; i < 3000; i++) {
            int k = rng.nextInt(400);
            if (rng.nextInt(100) < 60) t.add(k);
            else t.remove(k);
            if (i % 250 == 249) assertLeafInvariants(t);
        }
        assertLeafInvariants(t);
    }

    @Test
    @DisplayName("drain to empty: the chain view empties with the tree")
    void drainToEmpty() {
        BPlusTreeEngine<Integer> t = BPlusTreeEngine.withNaturalOrder(FANOUT);
        for (int k = 0; k < 100; k++) t.add(k);
        for (int k = 0; k < 100; k++) t.remove(k);
        assertTrue(t.leafKeyCounts().isEmpty());
        assertEquals(0, t.size());
    }

    @Test
    @DisplayName("fill factor lands in the textbook band for random insertion order")
    void fillFactorBand() {
        BPlusTreeEngine<Integer> t = BPlusTreeEngine.withNaturalOrder(FANOUT);
        Random rng = new Random(17);
        while (t.size() < 600) t.add(rng.nextInt(100_000));
        List<Integer> counts = t.leafKeyCounts();
        double fill = (double) t.size() / ((long) counts.size() * FANOUT);
        assertTrue(fill >= 0.5 && fill <= 1.0,
                "fill factor outside the possible band: " + fill);
    }
}
