package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.BetaDiversity;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Between-community measures — hand-computed oracles for Jaccard, S&#xF8;rensen,
 * Bray–Curtis, Pianka overlap, and Whittaker turnover, plus the boundary conventions
 * (empty-vs-empty) pinned exactly as documented.
 */
@DisplayName("BetaDiversity — between-community comparison")
class BetaDiversityTest {

    private static final double EPS = 1e-9;

    // ── Presence-based ────────────────────────────────────────────────────────

    @Test
    @DisplayName("Jaccard: identical=1, disjoint=0, hand oracle 2/4, empty-empty=1")
    void jaccardOracles() {
        assertEquals(1.0, BetaDiversity.jaccard(Set.of(1, 2, 3), Set.of(1, 2, 3)), EPS);
        assertEquals(0.0, BetaDiversity.jaccard(Set.of(1, 2), Set.of(3, 4)), EPS);
        assertEquals(0.5, BetaDiversity.jaccard(Set.of(1, 2, 3), Set.of(2, 3, 4)), EPS);
        assertEquals(1.0, BetaDiversity.jaccard(Set.of(), Set.of()), EPS);
        assertEquals(0.0, BetaDiversity.jaccard(Set.of(1), Set.of()), EPS);
    }

    @Test
    @DisplayName("Sørensen: identical=1, disjoint=0, hand oracle 2·2/6")
    void sorensenOracles() {
        assertEquals(1.0, BetaDiversity.sorensen(Set.of(1, 2), Set.of(1, 2)), EPS);
        assertEquals(0.0, BetaDiversity.sorensen(Set.of(1), Set.of(2)), EPS);
        assertEquals(2.0 * 2 / 6, BetaDiversity.sorensen(Set.of(1, 2, 3), Set.of(2, 3, 4)), EPS);
        assertEquals(1.0, BetaDiversity.sorensen(Set.of(), Set.of()), EPS);
    }

    // ── Abundance-based ───────────────────────────────────────────────────────

    @Test
    @DisplayName("Bray–Curtis: identical=0, disjoint=1, hand oracle 1 − 22/30")
    void brayCurtisOracles() {
        Map<Integer, Long> a = Map.of(1, 10L, 2, 5L);
        assertEquals(0.0, BetaDiversity.brayCurtis(a, a), EPS);
        assertEquals(1.0, BetaDiversity.brayCurtis(a, Map.of(3, 7L)), EPS);

        Map<Integer, Long> b = Map.of(1, 6L, 2, 5L, 3, 4L);
        // shared min = min(10,6) + min(5,5) = 11; totals 15 + 15 = 30
        assertEquals(1.0 - 22.0 / 30.0, BetaDiversity.brayCurtis(a, b), EPS);
        assertEquals(0.0, BetaDiversity.brayCurtis(Map.of(), Map.of()), EPS);
    }

    @Test
    @DisplayName("Pianka: identical distribution=1, disjoint=0, hand oracle 0.6")
    void piankaOracles() {
        Map<Integer, Long> a = Map.of(1, 3L, 2, 1L);
        assertEquals(1.0, BetaDiversity.pianka(a, a), EPS);
        assertEquals(0.0, BetaDiversity.pianka(a, Map.of(3, 5L)), EPS);
        assertEquals(0.0, BetaDiversity.pianka(a, Map.of()), EPS);

        // p = (0.75, 0.25) vs q = (0.25, 0.75): num = 2·(0.75·0.25) = 0.375,
        // Σp² = Σq² = 0.625 → O = 0.375 / 0.625 = 0.6
        Map<Integer, Long> b = Map.of(1, 1L, 2, 3L);
        assertEquals(0.6, BetaDiversity.pianka(a, b), EPS);
    }

    @Test
    @DisplayName("Renkonen: size-fair — identical composition scores 1 regardless of totals")
    void renkonenOracles() {
        Map<Integer, Long> small = Map.of(1, 3L, 2, 1L);
        Map<Integer, Long> bigSameShape = Map.of(1, 300L, 2, 100L); // 5N vs N: same p
        assertEquals(1.0, BetaDiversity.renkonen(small, bigSameShape), EPS);
        // The motivating contrast: raw Bray–Curtis is inflated by the size gap alone.
        assertTrue(BetaDiversity.brayCurtis(small, bigSameShape) > 0.5);

        // Hand oracle: p = (0.75, 0.25) vs q = (0.25, 0.75) → Σmin = 0.25 + 0.25 = 0.5
        assertEquals(0.5, BetaDiversity.renkonen(small, Map.of(1, 1L, 2, 3L)), EPS);
        assertEquals(0.0, BetaDiversity.renkonen(small, Map.of(9, 4L)), EPS);
        assertEquals(1.0, BetaDiversity.renkonen(Map.of(), Map.of()), EPS);
        assertEquals(0.0, BetaDiversity.renkonen(small, Map.of()), EPS);
        assertEquals(BetaDiversity.renkonen(small, bigSameShape),
                BetaDiversity.renkonen(bigSameShape, small), EPS);
    }

    @Test
    @DisplayName("Pianka is symmetric")
    void piankaSymmetry() {
        Map<Integer, Long> a = Map.of(1, 9L, 2, 4L, 3, 1L);
        Map<Integer, Long> b = Map.of(2, 6L, 3, 6L, 4, 2L);
        assertEquals(BetaDiversity.pianka(a, b), BetaDiversity.pianka(b, a), EPS);
    }

    // ── Multi-community ───────────────────────────────────────────────────────

    @Test
    @DisplayName("Whittaker turnover: identical windows=0, fully distinct windows=1")
    void whittakerOracles() {
        Map<Integer, Long> w = Map.of(1, 5L, 2, 5L);
        assertEquals(0.0, BetaDiversity.whittakerTurnover(List.of(w, w, w)), EPS);

        // two windows, two unique species each: γ = 4, ᾱ = 2 → β = 1
        assertEquals(1.0, BetaDiversity.whittakerTurnover(
                List.of(Map.of(1, 3L, 2, 3L), Map.of(3, 3L, 4, 3L))), EPS);

        assertEquals(0.0, BetaDiversity.whittakerTurnover(List.of()), EPS);
        assertEquals(0.0, BetaDiversity.whittakerTurnover(List.of(Map.of())), EPS);
    }

    @Test
    @DisplayName("presence() drops non-positive counts")
    void presenceFilters() {
        assertEquals(Set.of(1, 3), BetaDiversity.presence(Map.of(1, 2L, 2, 0L, 3, 9L)));
    }
}
