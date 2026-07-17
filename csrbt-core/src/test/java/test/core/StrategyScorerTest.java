package test.core;

import io.github.richeyworks.csrbt.control.CostModelStrategyScorer;
import io.github.richeyworks.csrbt.control.StrategyId;
import io.github.richeyworks.csrbt.control.StrategyScorer;
import io.github.richeyworks.csrbt.control.StrategyScorer.Score;
import io.github.richeyworks.csrbt.control.WorkloadFeatures;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.EnumSet;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Phase-B control-plane unit (ADR-002 step 6): the {@link CostModelStrategyScorer} must
 * turn a {@link WorkloadFeatures} vector into an ascending-cost ranking that matches the
 * measured regimes (2026-06-10 calibration to realized comparisons/op) — Splay for skewed
 * reads, AVL everywhere else — with Hybrid scored but never winning a tie. The DESIGN
 * §3.2/§10 "RB for write-heavy/balanced" story was the rotation-priced reading; on the
 * house comparisons meter it is measurably false (see the calibration changelog).
 */
@DisplayName("CostModelStrategyScorer ranking")
public class StrategyScorerTest {

    private final StrategyScorer scorer = new CostModelStrategyScorer();

    /** Feature vector with the three signals that drive the model; the rest are unused by it. */
    private static WorkloadFeatures wf(double read, double write, double skew) {
        return new WorkloadFeatures(read, write, skew, 12.0, 0.4, 5_000L, 5.0);
    }

    private static int rankOf(List<Score> ranked, StrategyId id) {
        for (int i = 0; i < ranked.size(); i++) if (ranked.get(i).strategy() == id) return i;
        throw new AssertionError(id + " not in ranking");
    }

    @Test
    @DisplayName("DESIGN §10 trace: skew 0.71 + read 0.94 → Splay first, Red-Black last")
    void designSection10Trace() {
        List<Score> ranked = scorer.score(wf(0.94, 0.06, 0.71));
        assertEquals(StrategyId.SPLAY, ranked.get(0).strategy(),
                "high-skew read-heavy must rank Splay first");
        assertEquals(StrategyId.RED_BLACK, ranked.get(ranked.size() - 1).strategy(),
                "incumbent RB has no locality gain here → last");
        assertTrue(rankOf(ranked, StrategyId.AVL) < rankOf(ranked, StrategyId.RED_BLACK),
                "AVL (shallow reads) should beat RB here");
    }

    @Test
    @DisplayName("uniform read-heavy → AVL first (shallowest tree, skew unused)")
    void readHeavyLowSkewPicksAvl() {
        assertEquals(StrategyId.AVL, scorer.score(wf(0.95, 0.05, 0.03)).get(0).strategy());
    }

    @Test
    @DisplayName("write-heavy → Hybrid first (2026-07-14: best-fixed on every post-fix probe seed)")
    void writeHeavyPicksHybrid() {
        // Re-pinned by the 2026-07-14 recalibration: the 2026-06-10 "AVL beats RB on writes"
        // evidence was measured through the double-descent/double-compare write path (census
        // finding A). Post-fix, Hybrid is best-fixed on every E3/E3b seed (11.56-11.61 vs AVL
        // 11.84-11.90 vs RB 14.09-14.19 cmp/op) — writes fund its RB delete machinery.
        assertEquals(StrategyId.HYBRID, scorer.score(wf(0.15, 0.85, 0.05)).get(0).strategy());
    }

    @Test
    @DisplayName("balanced mix → Hybrid first (2026-07-14 recalibration, same evidence trail)")
    void balancedPicksHybrid() {
        assertEquals(StrategyId.HYBRID, scorer.score(wf(0.50, 0.50, 0.05)).get(0).strategy());
    }

    @Test
    @DisplayName("max skew + pure reads → Splay first by a clear margin")
    void maxSkewReadPicksSplay() {
        List<Score> ranked = scorer.score(wf(1.0, 0.0, 1.0));
        assertEquals(StrategyId.SPLAY, ranked.get(0).strategy());
        assertTrue(ranked.get(1).estimatedCost() - ranked.get(0).estimatedCost() > 0.1,
                "Splay should win clearly under maximal locality");
    }

    @Test
    @DisplayName("Hybrid wins exactly where writes fund it: the w ≈ 0.08 crossover vs AVL")
    void hybridCrossoverIsWriteFunded() {
        // 2026-07-14 recalibration: Hybrid replaced the old mean+tie-penalty line with its own
        // calibrated cost. It crosses under AVL at w ≳ 0.08 — pure-read diets stay AVL's (and
        // Splay's under skew), anything write-funded is Hybrid's. This replaces the retired
        // "Hybrid never ranks first" pin, which encoded the pre-fix write path.
        assertNotEquals(StrategyId.HYBRID, scorer.score(wf(0.95, 0.05, 0.03)).get(0).strategy(),
                "at w=0.05 Hybrid must not out-rank AVL");
        assertNotEquals(StrategyId.HYBRID, scorer.score(wf(1.0, 0.0, 1.0)).get(0).strategy(),
                "max-skew pure reads stay Splay's");
        assertEquals(StrategyId.HYBRID, scorer.score(wf(0.85, 0.15, 0.05)).get(0).strategy(),
                "at w=0.15 the write funding has crossed over");
        assertEquals(StrategyId.HYBRID, scorer.score(wf(0.50, 0.50, 0.05)).get(0).strategy());
        // And the ordering stays deterministic on either side of the crossover.
        assertTrue(scorer.score(wf(0.85, 0.15, 0.05)).get(0).estimatedCost()
                < scorer.score(wf(0.85, 0.15, 0.05)).get(1).estimatedCost() + 1e-12);
    }

    @Test
    @DisplayName("result is ascending by cost, complete, bounded, and each carries a rationale")
    void resultIsWellFormed() {
        List<Score> ranked = scorer.score(wf(0.7, 0.3, 0.4));
        assertEquals(4, ranked.size(), "all four strategies scored");

        EnumSet<StrategyId> seen = EnumSet.noneOf(StrategyId.class);
        double prev = Double.NEGATIVE_INFINITY;
        for (Score s : ranked) {
            assertTrue(s.estimatedCost() >= prev, "costs must be ascending");
            prev = s.estimatedCost();
            assertTrue(s.estimatedCost() >= 0.0 && s.estimatedCost() <= 1.0,
                    "cost out of [0,1]: " + s);
            assertFalse(s.rationale() == null || s.rationale().isBlank(),
                    "every score needs a rationale: " + s.strategy());
            seen.add(s.strategy());
        }
        assertEquals(EnumSet.allOf(StrategyId.class), seen, "every strategy scored exactly once");
    }
}
