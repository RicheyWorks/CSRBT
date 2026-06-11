package test.core;

import io.github.richeyworks.csrbt.PersistentTreeEngine;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.NoSuchElementException;
import java.util.Random;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Correctness, balance, snapshots, and order statistics for the weight-balanced
 * path-copying engine (ADR-005 P1).
 */
@DisplayName("PersistentTreeEngine")
public class PersistentTreeEngineTest {

    private static void assertHealthy(PersistentTreeEngine<?> eng, String when) {
        List<String> failures = eng.validateInvariants();
        assertTrue(failures.isEmpty(), when + ": " + failures);
    }

    @Test
    @DisplayName("ordered-set semantics match a TreeSet oracle over random ops (invariants checked)")
    void matchesOracle() {
        PersistentTreeEngine<Integer> eng = PersistentTreeEngine.withNaturalOrder();
        TreeSet<Integer> oracle = new TreeSet<>();
        Random rng = new Random(2026);

        for (int i = 0; i < 4000; i++) {
            int v = rng.nextInt(600);
            switch (rng.nextInt(3)) {
                case 0 -> { eng.add(v); oracle.add(v); }
                case 1 -> { eng.remove(v); oracle.remove(v); }
                default -> assertEquals(oracle.contains(v), eng.contains(v), "contains(" + v + ")");
            }
            if (i % 200 == 0) {
                assertEquals(new ArrayList<>(oracle), eng.inOrder());
                assertEquals(oracle.size(), eng.size());
                assertHealthy(eng, "after op " + i);
            }
        }
        assertEquals(new ArrayList<>(oracle), eng.inOrder());
        assertEquals(oracle.size(), eng.size());
        assertHealthy(eng, "at the end");
    }

    @Test
    @DisplayName("duplicate add is ignored")
    void duplicatesIgnored() {
        PersistentTreeEngine<Integer> eng = PersistentTreeEngine.withNaturalOrder();
        eng.add(5);
        eng.add(5);                              // no structural change
        assertEquals(1, eng.size());
        assertEquals(List.of(5), eng.inOrder());
    }

    @Test
    @DisplayName("snapshots remain intact after later mutations (explicit handles, ADR-005 §3)")
    void snapshotsArePersistent() {
        PersistentTreeEngine<Integer> eng = PersistentTreeEngine.withNaturalOrder();
        eng.add(10);
        eng.add(20);
        PersistentTreeEngine.Snapshot<Integer> afterTwo = eng.snapshot();
        eng.add(30);
        eng.remove(10);

        assertEquals(List.of(20, 30), eng.inOrder(), "current version reflects all ops");
        assertEquals(List.of(10, 20), afterTwo.inOrder(),
                "an earlier snapshot is unchanged by later mutations");
        assertEquals(2, afterTwo.size());
        assertTrue(afterTwo.contains(10) && !afterTwo.contains(30),
                "snapshot membership is frozen at capture time");

        PersistentTreeEngine.Snapshot<Integer> empty =
                PersistentTreeEngine.<Integer>withNaturalOrder().snapshot();
        assertTrue(empty.isEmpty() && empty.inOrder().isEmpty(), "empty snapshot is empty");
    }

    @Test
    @DisplayName("clear empties the live set; prior snapshots survive it")
    void clearLeavesSnapshotsIntact() {
        PersistentTreeEngine<Integer> eng = PersistentTreeEngine.withNaturalOrder();
        eng.add(1);
        eng.add(2);
        PersistentTreeEngine.Snapshot<Integer> before = eng.snapshot();
        eng.clear();
        assertEquals(0, eng.size());
        assertFalse(eng.contains(1));
        assertEquals(List.of(1, 2), before.inOrder(), "clear cannot reach a captured snapshot");
    }

    @Test
    @DisplayName("sorted, reverse, and organ-pipe input stay balanced (no degenerate chains)")
    void adversarialInputStaysBalanced() {
        int n = 10_000;

        PersistentTreeEngine<Integer> asc = PersistentTreeEngine.withNaturalOrder();
        for (int i = 0; i < n; i++) asc.add(i);
        assertEquals(n, asc.size());
        assertHealthy(asc, "ascending insert");

        PersistentTreeEngine<Integer> desc = PersistentTreeEngine.withNaturalOrder();
        for (int i = n - 1; i >= 0; i--) desc.add(i);
        assertHealthy(desc, "descending insert");

        // Organ pipe: outside-in, then delete every other key — exercises delete rebalancing.
        PersistentTreeEngine<Integer> pipe = PersistentTreeEngine.withNaturalOrder();
        for (int i = 0; i < n / 2; i++) { pipe.add(i); pipe.add(n - 1 - i); }
        for (int i = 0; i < n; i += 2) pipe.remove(i);
        assertEquals(n / 2, pipe.size());
        assertHealthy(pipe, "organ-pipe insert + alternating delete");
        assertTrue(pipe.contains(1) && !pipe.contains(0));
    }

    @Test
    @DisplayName("order statistics: select/rank/countInRange/rangeQuery agree with the oracle")
    void orderStatistics() {
        PersistentTreeEngine<Integer> eng = PersistentTreeEngine.withNaturalOrder();
        TreeSet<Integer> oracle = new TreeSet<>();
        Random rng = new Random(42);
        for (int i = 0; i < 1500; i++) {
            int v = rng.nextInt(5000);
            if (rng.nextInt(4) == 0) { eng.remove(v); oracle.remove(v); }
            else                     { eng.add(v);    oracle.add(v); }
        }

        List<Integer> sorted = new ArrayList<>(oracle);
        for (int r = 1; r <= sorted.size(); r += 97) {
            assertEquals(sorted.get(r - 1), eng.select(r), "select(" + r + ")");
            assertEquals(r, eng.rank(sorted.get(r - 1)), "rank(select(" + r + "))");
        }
        assertThrows(IndexOutOfBoundsException.class, () -> eng.select(0));
        assertThrows(IndexOutOfBoundsException.class, () -> eng.select(eng.size() + 1));
        assertThrows(NoSuchElementException.class, () -> eng.rank(-1));

        assertEquals(oracle.subSet(1000, true, 2000, true).size(),
                eng.countInRange(1000, 2000), "countInRange [1000,2000]");
        assertEquals(new ArrayList<>(oracle.subSet(1000, true, 2000, true)),
                eng.rangeQuery(1000, 2000), "rangeQuery [1000,2000]");
        assertEquals(0, eng.countInRange(2000, 1000), "inverted range counts nothing");
        assertTrue(eng.rangeQuery(2000, 1000).isEmpty(), "inverted range yields nothing");

        // Snapshots answer the same questions, frozen.
        PersistentTreeEngine.Snapshot<Integer> snap = eng.snapshot();
        eng.add(99_999);
        assertEquals(sorted.size(), snap.size(), "snapshot size frozen");
        assertEquals(sorted.get(0), snap.select(1), "snapshot select");
        assertEquals(new ArrayList<>(oracle.subSet(1000, true, 2000, true)),
                snap.rangeQuery(1000, 2000), "snapshot rangeQuery");
    }

    @Test
    @DisplayName("generic keys: comparator-ordered strings behave identically")
    void genericKeys() {
        PersistentTreeEngine<String> eng =
                new PersistentTreeEngine<>(Comparator.comparing(String::length)
                        .thenComparing(Comparator.naturalOrder()));
        for (String s : new String[]{"kiwi", "fig", "banana", "apple", "fig"}) eng.add(s);
        assertEquals(List.of("fig", "kiwi", "apple", "banana"), eng.inOrder(),
                "length-then-lexicographic order");
        assertEquals(4, eng.size(), "duplicate string ignored");
        assertTrue(eng.contains("kiwi"));
        eng.remove("kiwi");
        assertFalse(eng.contains("kiwi"));
        assertEquals("apple", eng.select(2));
        assertHealthy(eng, "string keys");
    }

    @Test
    @DisplayName("null keys are rejected loudly")
    void nullsRejected() {
        PersistentTreeEngine<Integer> eng = PersistentTreeEngine.withNaturalOrder();
        assertThrows(NullPointerException.class, () -> eng.add(null));
        assertThrows(NullPointerException.class, () -> eng.remove(null));
        assertThrows(NullPointerException.class, () -> eng.contains(null));
    }
}
