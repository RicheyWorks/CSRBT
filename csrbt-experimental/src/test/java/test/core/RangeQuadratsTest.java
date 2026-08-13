package test.core;

import io.github.richeyworks.csrbt.BPlusTreeEngine;
import io.github.richeyworks.csrbt.experimental.ecology.RangeQuadrats;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-016 §E3 — quadrat sampling over the key space: hand-oracle dispersion indices on
 * constructed patterns (regular, clumped, seeded random), the binning contract, and the
 * engine-family integration (one instrument, any {@code inOrder()}).
 */
@DisplayName("RangeQuadrats — grid dispersion statistics over engine key spaces")
class RangeQuadratsTest {

    private static final double EPS = 1e-9;

    // ── Binning contract ──────────────────────────────────────────────────────

    @Test
    @DisplayName("binning: top boundary inclusive, degenerate range collapses to bin 0, empty is zeros")
    void binningContract() {
        long[] c = RangeQuadrats.countsOfInts(List.of(0, 10), 2);
        assertEquals(1, c[0]);
        assertEquals(1, c[1]); // max key lands in the last bin, not out of range

        long[] degenerate = RangeQuadrats.countsOfInts(List.of(5, 5, 5), 4);
        assertEquals(3, degenerate[0]);
        assertEquals(0.25, RangeQuadrats.occupancy(degenerate), EPS);

        long[] empty = RangeQuadrats.countsOfInts(List.of(), 3);
        assertEquals(0, RangeQuadrats.total(empty));
        assertEquals(0.0, RangeQuadrats.occupancy(empty), EPS);
        assertEquals(0.0, RangeQuadrats.indexOfDispersion(empty), EPS);
        assertEquals(1.0, RangeQuadrats.morisita(empty), EPS); // N < 2 convention

        assertThrows(IllegalArgumentException.class,
                () -> RangeQuadrats.countsOfInts(List.of(1), 0));
    }

    // ── Dispersion oracles ────────────────────────────────────────────────────

    @Test
    @DisplayName("regular pattern: keys 0..99 over 10 quadrats → I = 0, Morisita = 0.909…")
    void regularOracle() {
        List<Integer> keys = new ArrayList<>();
        for (int i = 0; i < 100; i++) keys.add(i);
        long[] c = RangeQuadrats.countsOfInts(keys, 10);
        for (long n : c) assertEquals(10, n); // perfectly even grid

        assertEquals(0.0, RangeQuadrats.indexOfDispersion(c), EPS);
        // Iδ = Q·Σn(n−1)/(N(N−1)) = 10·(10·10·9)/(100·99)
        assertEquals(10.0 * 900 / 9900, RangeQuadrats.morisita(c), EPS);
        assertTrue(RangeQuadrats.morisita(c) < 1.0, "regular reads below 1");
        assertEquals(1.0, RangeQuadrats.occupancy(c), EPS);
    }

    @Test
    @DisplayName("clumped pattern: one dense patch → both indices far above 1")
    void clumpedOracle() {
        List<Integer> keys = new ArrayList<>();
        for (int i = 0; i < 100; i++) keys.add(i); // dense patch in [0,99]
        keys.add(999);                              // stretch the range
        long[] c = RangeQuadrats.countsOfInts(keys, 10);
        assertEquals(100, c[0]);
        assertEquals(1, c[9]);

        assertTrue(RangeQuadrats.indexOfDispersion(c) > 10.0);
        // Iδ = 10·(100·99)/(101·100) exactly
        assertEquals(10.0 * 9900 / 10100, RangeQuadrats.morisita(c), EPS);
        assertTrue(RangeQuadrats.morisita(c) > 1.0, "clumped reads above 1");
        assertEquals(0.2, RangeQuadrats.occupancy(c), EPS);
    }

    @Test
    @DisplayName("seeded random scatter reads near 1 on both indices (Poisson regime)")
    void randomRegime() {
        Random rng = new Random(13);
        TreeSet<Integer> distinct = new TreeSet<>();
        while (distinct.size() < 200) distinct.add(rng.nextInt(10_000));
        long[] c = RangeQuadrats.countsOfInts(new ArrayList<>(distinct), 20);

        double id = RangeQuadrats.indexOfDispersion(c);
        double im = RangeQuadrats.morisita(c);
        assertTrue(id > 0.3 && id < 2.0, "index of dispersion off Poisson regime: " + id);
        assertTrue(im > 0.8 && im < 1.25, "Morisita off Poisson regime: " + im);
    }

    @Test
    @DisplayName("non-finite positions are rejected, not silently binned")
    void nonFinitePositionsRejected() {
        assertThrows(IllegalArgumentException.class,
                () -> RangeQuadrats.counts(List.of("x"), s -> Double.NaN, 4));
        assertThrows(IllegalArgumentException.class,
                () -> RangeQuadrats.counts(List.of(1.0, 2.0), d -> 1.0 / (d - 1.0), 4));
    }

    @Test
    @DisplayName("generic position mapper: non-integer keys bucket by mapped position")
    void genericMapper() {
        List<String> words = List.of("a", "bb", "ccc", "dddddddddd");
        long[] c = RangeQuadrats.counts(words, String::length, 3);
        // lengths 1,2,3,10 over [1,10]: bins (width 3): 1,2→0; 3→0? (3−1)/9*3 = 0.66 → bin 0; 10→last
        assertEquals(3, c[0]);
        assertEquals(0, c[1]);
        assertEquals(1, c[2]);
    }

    // ── Engine-family integration ─────────────────────────────────────────────

    @Test
    @DisplayName("B+tree integration: clustered inserts read clumped, evenly spread inserts read regular")
    void bplusTreeIntegration() {
        BPlusTreeEngine<Integer> clustered = BPlusTreeEngine.withNaturalOrder(BPlusTreeEngine.MIN_FANOUT);
        for (int base : new int[]{ 0, 500, 990 }) {
            for (int i = 0; i < 30; i++) clustered.add(base + i); // 3 dense patches
        }
        long[] cc = RangeQuadrats.countsOfInts(clustered.inOrder(), 20);
        assertTrue(RangeQuadrats.indexOfDispersion(cc) > 1.0,
                "clustered data must read clumped, I=" + RangeQuadrats.indexOfDispersion(cc));

        BPlusTreeEngine<Integer> spread = BPlusTreeEngine.withNaturalOrder(BPlusTreeEngine.MIN_FANOUT);
        for (int i = 0; i < 100; i++) spread.add(i * 10); // even spacing
        long[] sc = RangeQuadrats.countsOfInts(spread.inOrder(), 10);
        assertEquals(0.0, RangeQuadrats.indexOfDispersion(sc), EPS);
        assertTrue(RangeQuadrats.morisita(sc) < 1.0);
    }

    @Test
    @DisplayName("determinism: identical inputs give bitwise-identical statistics and report")
    void determinism() {
        List<Integer> keys = List.of(3, 1, 4, 1, 5, 9, 2, 6, 53, 58);
        long[] a = RangeQuadrats.countsOfInts(keys, 5);
        long[] b = RangeQuadrats.countsOfInts(keys, 5);
        assertEquals(RangeQuadrats.indexOfDispersion(a), RangeQuadrats.indexOfDispersion(b));
        assertEquals(RangeQuadrats.morisita(a), RangeQuadrats.morisita(b));
        assertEquals(RangeQuadrats.report(a), RangeQuadrats.report(b));
    }
}
