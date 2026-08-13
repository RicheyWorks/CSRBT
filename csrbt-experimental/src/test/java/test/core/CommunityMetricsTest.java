package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.CommunityMetrics;
import io.github.richeyworks.csrbt.experimental.ecology.CommunityMetrics.AbundanceModel;
import io.github.richeyworks.csrbt.experimental.ecology.CommunityMetrics.ModelFit;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Ecology audit 2026-08-09 follow-up — within-community indices on real abundance
 * distributions. Every assertion is a hand-computed oracle (house discipline: pure
 * functions, hand-built vectors), plus the discriminating checks EC-1 demanded:
 * these indices must <em>vary</em> — even vs skewed distributions must separate.
 */
@DisplayName("CommunityMetrics — diversity indices on abundance distributions")
class CommunityMetricsTest {

    private static final double EPS = 1e-9;

    // ── Shannon / Pielou ──────────────────────────────────────────────────────

    @Test
    @DisplayName("uniform community: H' = ln S, J' = 1, D = 1/S, all Hill numbers = S")
    void uniformOracles() {
        Map<Integer, Long> even = Map.of(1, 25L, 2, 25L, 3, 25L, 4, 25L);
        assertEquals(Math.log(4), CommunityMetrics.shannon(even), EPS);
        assertEquals(1.0, CommunityMetrics.pielouEvenness(even), EPS);
        assertEquals(0.25, CommunityMetrics.simpsonIndex(even), EPS);
        assertEquals(0.75, CommunityMetrics.simpsonDiversity(even), EPS);
        assertEquals(4.0, CommunityMetrics.inverseSimpson(even), EPS);
        assertEquals(4.0, CommunityMetrics.hillNumber(even, 0), EPS);
        assertEquals(4.0, CommunityMetrics.hillNumber(even, 1), EPS);
        assertEquals(4.0, CommunityMetrics.hillNumber(even, 2), EPS);
    }

    @Test
    @DisplayName("skewed community: hand-computed H' and D (70/20/10)")
    void skewedOracles() {
        Map<Integer, Long> skewed = Map.of(1, 70L, 2, 20L, 3, 10L);
        double expectedH = -(0.7 * Math.log(0.7) + 0.2 * Math.log(0.2) + 0.1 * Math.log(0.1));
        assertEquals(expectedH, CommunityMetrics.shannon(skewed), EPS);
        assertEquals(0.7 * 0.7 + 0.2 * 0.2 + 0.1 * 0.1,
                CommunityMetrics.simpsonIndex(skewed), EPS);
        assertEquals(expectedH / Math.log(3), CommunityMetrics.pielouEvenness(skewed), EPS);
    }

    @Test
    @DisplayName("EC-1's discriminating check: skew strictly lowers H', J', and Hill-1")
    void skewSeparatesFromUniform() {
        Map<Integer, Long> even   = Map.of(1, 25L, 2, 25L, 3, 25L, 4, 25L);
        Map<Integer, Long> skewed = Map.of(1, 85L, 2, 5L, 3, 5L, 4, 5L);
        assertTrue(CommunityMetrics.shannon(skewed) < CommunityMetrics.shannon(even));
        assertTrue(CommunityMetrics.pielouEvenness(skewed) < CommunityMetrics.pielouEvenness(even));
        assertTrue(CommunityMetrics.hillNumber(skewed, 1) < CommunityMetrics.hillNumber(even, 1));
    }

    @Test
    @DisplayName("degenerate communities: empty and single-species")
    void degenerateCommunities() {
        Map<Integer, Long> empty = Map.of();
        assertEquals(0, CommunityMetrics.richness(empty));
        assertEquals(0.0, CommunityMetrics.shannon(empty), EPS);
        assertEquals(0.0, CommunityMetrics.hillNumber(empty, 1), EPS);
        assertEquals(0.0, CommunityMetrics.inverseSimpson(empty), EPS);

        Map<Integer, Long> mono = Map.of(7, 100L);
        assertEquals(0.0, CommunityMetrics.shannon(mono), EPS);
        assertEquals(1.0, CommunityMetrics.pielouEvenness(mono), EPS);
        assertEquals(1.0, CommunityMetrics.simpsonIndex(mono), EPS);
        assertEquals(1.0, CommunityMetrics.inverseSimpson(mono), EPS);
    }

    @Test
    @DisplayName("zero and negative counts are ignored as non-species")
    void zeroCountsIgnored() {
        Map<Integer, Long> withZeros = Map.of(1, 50L, 2, 50L, 3, 0L);
        assertEquals(2, CommunityMetrics.richness(withZeros));
        assertEquals(100L, CommunityMetrics.total(withZeros));
        assertEquals(Math.log(2), CommunityMetrics.shannon(withZeros), EPS);
    }

    // ── Hill continuity ───────────────────────────────────────────────────────

    @Test
    @DisplayName("Hill q=1 equals exp(H') and sits between q=0 and q=2 on a skewed community")
    void hillOrdering() {
        Map<Integer, Long> skewed = Map.of(1, 70L, 2, 20L, 3, 10L);
        assertEquals(Math.exp(CommunityMetrics.shannon(skewed)),
                CommunityMetrics.hillNumber(skewed, 1), EPS);
        double h0 = CommunityMetrics.hillNumber(skewed, 0);
        double h1 = CommunityMetrics.hillNumber(skewed, 1);
        double h2 = CommunityMetrics.hillNumber(skewed, 2);
        assertTrue(h0 >= h1 && h1 >= h2, "Hill numbers must be non-increasing in q");
    }

    // ── Rank–abundance models ─────────────────────────────────────────────────

    @Test
    @DisplayName("broken-stick and geometric expectations both sum to N")
    void modelExpectationsSumToN() {
        double[] stick = CommunityMetrics.brokenStickExpected(5, 100);
        double sumStick = 0;
        for (double v : stick) sumStick += v;
        assertEquals(100.0, sumStick, EPS);

        double[] geo = CommunityMetrics.geometricExpected(5, 100, 0.4);
        double sumGeo = 0;
        for (double v : geo) sumGeo += v;
        assertEquals(100.0, sumGeo, EPS);
    }

    @Test
    @DisplayName("broken-stick rank 1 oracle: (N/S)·Σ 1/k")
    void brokenStickOracle() {
        double[] stick = CommunityMetrics.brokenStickExpected(4, 100);
        double harmonic = 1.0 + 1.0 / 2 + 1.0 / 3 + 1.0 / 4;
        assertEquals(25.0 * harmonic, stick[0], EPS);
        assertEquals(25.0 * (1.0 / 4), stick[3], EPS);
    }

    @Test
    @DisplayName("fitGeometricK recovers k from a perfect geometric series")
    void geometricKRecovery() {
        List<Long> ranks = List.of(160L, 80L, 40L, 20L, 10L); // successive ratio 0.5
        assertEquals(0.5, CommunityMetrics.fitGeometricK(ranks), EPS);
    }

    @Test
    @DisplayName("bestFit picks GEOMETRIC on geometric data and UNIFORM on flat data")
    void bestFitDiscriminates() {
        Map<Integer, Long> geometric = Map.of(1, 160L, 2, 80L, 3, 40L, 4, 20L, 5, 10L);
        ModelFit geoFit = CommunityMetrics.bestFit(geometric);
        assertEquals(AbundanceModel.GEOMETRIC, geoFit.best());

        Map<Integer, Long> flat = Map.of(1, 40L, 2, 40L, 3, 40L, 4, 40L);
        ModelFit flatFit = CommunityMetrics.bestFit(flat);
        assertEquals(AbundanceModel.UNIFORM, flatFit.best());
        assertEquals(0.0, flatFit.sse().get(AbundanceModel.UNIFORM), EPS);
    }

    // ── Richness estimation ───────────────────────────────────────────────────

    @Test
    @DisplayName("Chao1 oracles: classic form, bias-corrected F2=0 form, and the complete survey")
    void chao1Oracles() {
        // S=3, F1=2, F2=1 → 3 + 2²/(2·1) = 5
        assertEquals(5.0, CommunityMetrics.chao1(Map.of(1, 1L, 2, 1L, 3, 2L)), EPS);
        // S=3, F1=2, F2=0 → 3 + 2·1/2 = 4 (bias-corrected)
        assertEquals(4.0, CommunityMetrics.chao1(Map.of(1, 1L, 2, 1L, 3, 3L)), EPS);
        // no singletons → estimate = observed
        assertEquals(2.0, CommunityMetrics.chao1(Map.of(1, 5L, 2, 3L)), EPS);
        assertEquals(0.0, CommunityMetrics.chao1(Map.of()), EPS);
    }

    @Test
    @DisplayName("rarefaction oracles: E[S₁] = 1 always, E[S_N] = S, hand hypergeometric case")
    void rarefactionOracles() {
        Map<Integer, Long> two = Map.of(1, 2L, 2, 2L);
        assertEquals(1.0, CommunityMetrics.rarefiedRichness(two, 1), EPS);
        assertEquals(2.0, CommunityMetrics.rarefiedRichness(two, 4), EPS);
        // m=3 of {2,2}: neither species can be entirely absent from 3 of 4 draws
        assertEquals(2.0, CommunityMetrics.rarefiedRichness(two, 3), EPS);
        // {1,3}, m=1: P(see a) = 1/4, P(see b) = 3/4 → E = 1 exactly
        assertEquals(1.0, CommunityMetrics.rarefiedRichness(Map.of(1, 1L, 2, 3L), 1), EPS);
        assertEquals(0.0, CommunityMetrics.rarefiedRichness(two, 0), EPS);
    }

    @Test
    @DisplayName("rarefaction curve: monotone non-decreasing, ends at observed richness")
    void rarefactionCurveShape() {
        Map<Integer, Long> skewed = Map.of(1, 60L, 2, 25L, 3, 10L, 4, 4L, 5, 1L);
        double[][] curve = CommunityMetrics.rarefactionCurve(skewed, 10);
        assertEquals(10, curve.length);
        double prev = 0;
        for (double[] p : curve) {
            assertTrue(p[1] >= prev - EPS, "curve must be non-decreasing");
            prev = p[1];
        }
        assertEquals(100, (long) curve[9][0]);
        assertEquals(5.0, curve[9][1], EPS);
    }

    @Test
    @DisplayName("determinism: identical input maps give bitwise-identical index values")
    void determinism() {
        Map<Integer, Long> a = Map.of(1, 70L, 2, 20L, 3, 10L, 4, 3L);
        Map<Integer, Long> b = Map.of(4, 3L, 3, 10L, 2, 20L, 1, 70L); // same content
        assertEquals(CommunityMetrics.shannon(a), CommunityMetrics.shannon(b));
        assertEquals(CommunityMetrics.simpsonIndex(a), CommunityMetrics.simpsonIndex(b));
        assertEquals(CommunityMetrics.hillNumber(a, 2), CommunityMetrics.hillNumber(b, 2));
        assertEquals(CommunityMetrics.bestFit(a).best(), CommunityMetrics.bestFit(b).best());
    }
}
