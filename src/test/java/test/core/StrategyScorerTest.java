package test.core;

import core.control.CostModelStrategyScorer;
import core.control.StrategyId;
import core.control.StrategyScorer;
import core.control.StrategyScorer.Score;
import core.control.WorkloadFeatures;

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
 * regimes DESIGN §3.2/§10 describe — Splay for skewed reads, AVL for uniform reads,
 * Red-Black for write-heavy/balanced — with Hybrid scored but never winning a tie.
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
    @DisplayName("write-heavy → Red-Black first (fewest rotations per insert)")
    void writeHeavyPicksRedBlack() {
        assertEquals(StrategyId.RED_BLACK, scorer.score(wf(0.15, 0.85, 0.05)).get(0).strategy());
    }

    @Test
    @DisplayName("balanced mix → Red-Black first (solid all-rounder)")
    void balancedPicksRedBlack() {
        assertEquals(StrategyId.RED_BLACK, scorer.score(wf(0.50, 0.50, 0.05)).get(0).strategy());
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
    @DisplayName("Hybrid is scored but never ranks first (anti-churn tie bias)")
    void hybridNeverRanksFirst() {
        double[][] regimes = {
                {0.94, 0.06, 0.71}, {0.95, 0.05, 0.03}, {0.15, 0.85, 0.05},
                {0.50, 0.50, 0.05}, {0.45, 0.55, 0.80}, {0.55, 0.45, 0.20}, {1.0, 0.0, 1.0}
        };
        for (double[] g : regimes) {
            List<Score> ranked = scorer.score(wf(g[0], g[1], g[2]));
            assertNotEquals(StrategyId.HYBRID, ranked.get(0).strategy(),
                    "Hybrid won regime r=" + g[0] + " w=" + g[1] + " s=" + g[2]);
        }
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
