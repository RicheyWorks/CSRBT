package test.core;

import io.github.richeyworks.csrbt.control.MorphHistory;
import io.github.richeyworks.csrbt.control.MorphPolicy;
import io.github.richeyworks.csrbt.control.MorphPolicy.Decision;
import io.github.richeyworks.csrbt.control.StrategyId;
import io.github.richeyworks.csrbt.control.StrategyScorer.Score;
import io.github.richeyworks.csrbt.control.WorkloadFeatures;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Phase-C control-plane unit (ADR-002 step 6): the promoted {@link MorphPolicy} and the
 * {@link MorphHistory} it reads. {@link #evaluate} must implement the DESIGN §10 decision
 * over the scorer's ascending-cost ranking, while {@link MorphPolicy#shouldMorph} must
 * remain byte-identical to the legacy nested policy (parity is re-pinned here).
 */
@DisplayName("io.github.richeyworks.csrbt.control.MorphPolicy + MorphHistory")
public class MorphPolicyControlTest {

    private static Score sc(StrategyId id, double cost) { return new Score(id, cost, id + " @" + cost); }

    private static List<Score> ranked(Score... s) { return Arrays.asList(s); }

    /** Workload vector is unused by the current gates; any valid value works. */
    private static WorkloadFeatures feats() {
        return new WorkloadFeatures(0.94, 0.06, 0.71, 14.2, 0.3, 9_120L, 12.0);
    }

    @Nested
    @DisplayName("evaluate (cost-ranked, DESIGN §10)")
    class Evaluate {
        private final MorphPolicy policy = MorphPolicy.defaults();
        // DESIGN §10: incumbent RB 0.78, candidate Splay 0.41 → 47% cheaper.
        private final List<Score> s10 =
                ranked(sc(StrategyId.SPLAY, 0.41), sc(StrategyId.AVL, 0.55), sc(StrategyId.RED_BLACK, 0.78));

        @Test
        @DisplayName("all gates pass → MORPH to the cheapest")
        void morphsWhenAllGatesPass() {
            MorphHistory h = new MorphHistory(6_400, StrategyId.SPLAY, 3);
            assertEquals(Decision.MORPH, policy.evaluate(StrategyId.RED_BLACK, s10, feats(), h));
        }

        @Test
        @DisplayName("within cooldown → HOLD despite a big improvement")
        void holdsWithinCooldown() {
            MorphHistory h = new MorphHistory(1_000, StrategyId.SPLAY, 5);
            assertEquals(Decision.HOLD, policy.evaluate(StrategyId.RED_BLACK, s10, feats(), h));
        }

        @Test
        @DisplayName("candidate not yet stable → HOLD")
        void holdsWhenNotStable() {
            MorphHistory h = new MorphHistory(6_400, StrategyId.SPLAY, 2);
            assertEquals(Decision.HOLD, policy.evaluate(StrategyId.RED_BLACK, s10, feats(), h));
        }

        @Test
        @DisplayName("improvement below the 20% margin → HOLD")
        void holdsBelowMargin() {
            // Splay 0.70 vs RB 0.78 → ~10% cheaper, under the margin.
            List<Score> marginal = ranked(sc(StrategyId.SPLAY, 0.70), sc(StrategyId.RED_BLACK, 0.78));
            MorphHistory h = new MorphHistory(6_400, StrategyId.SPLAY, 3);
            assertEquals(Decision.HOLD, policy.evaluate(StrategyId.RED_BLACK, marginal, feats(), h));
        }

        @Test
        @DisplayName("incumbent is already the cheapest → HOLD")
        void holdsWhenIncumbentIsBest() {
            MorphHistory h = new MorphHistory(6_400, StrategyId.SPLAY, 9);
            assertEquals(Decision.HOLD, policy.evaluate(StrategyId.SPLAY, s10, feats(), h));
        }

        @Test
        @DisplayName("null history is treated as a fresh cooldown clock → HOLD")
        void nullHistoryHolds() {
            assertEquals(Decision.HOLD, policy.evaluate(StrategyId.RED_BLACK, s10, feats(), null));
        }
    }

    @Nested
    @DisplayName("shouldMorph parity with the legacy nested policy")
    class ShouldMorphParity {
        private final MorphPolicy policy = MorphPolicy.defaults();

        @Test void allGatesPass()    { assertTrue(policy.shouldMorph(0.50, 0.90, 5000, 3)); }
        @Test void cooldownBlocks()  { assertFalse(policy.shouldMorph(0.50, 0.90, 1000, 5)); }
        @Test void stabilityBlocks() { assertFalse(policy.shouldMorph(0.50, 0.90, 5000, 2)); }
        @Test void marginBlocks()    { assertFalse(policy.shouldMorph(0.50, 0.55, 5000, 3)); }

        @Test void notBetterBlocks() {
            assertFalse(policy.shouldMorph(0.70, 0.70, 5000, 3));
            assertFalse(policy.shouldMorph(0.70, 0.60, 5000, 3));
        }

        @Test void customThresholds() {
            assertTrue(new MorphPolicy(0, 0.05, 1).shouldMorph(0.50, 0.55, 0, 1));
            assertFalse(new MorphPolicy(0, 0.50, 1).shouldMorph(0.50, 0.60, 100, 5));
        }

        @Test
        @DisplayName("defaults are 4000 / 0.20 / 3")
        void defaultsMatchDesign() {
            MorphPolicy d = MorphPolicy.defaults();
            assertEquals(4000, d.cooldownOps());
            assertEquals(0.20, d.minImprovement());
            assertEquals(3, d.stabilityWins());
        }
    }

    @Nested
    @DisplayName("MorphHistory transitions")
    class History {
        @Test
        @DisplayName("initial is empty and credits no wins")
        void initialIsEmpty() {
            MorphHistory h = MorphHistory.initial();
            assertEquals(0, h.opsSinceLastMorph());
            assertEquals(0, h.consecutiveWins(StrategyId.SPLAY));
        }

        @Test
        @DisplayName("observing the same winner advances the streak and the clock")
        void observedIncrementsStreak() {
            MorphHistory h = MorphHistory.initial().observed(StrategyId.SPLAY, 10).observed(StrategyId.SPLAY, 10);
            assertEquals(20, h.opsSinceLastMorph());
            assertEquals(2, h.consecutiveWins(StrategyId.SPLAY));
        }

        @Test
        @DisplayName("a new winner restarts the streak at 1")
        void observedResetsOnNewWinner() {
            MorphHistory h = MorphHistory.initial().observed(StrategyId.SPLAY, 10).observed(StrategyId.AVL, 5);
            assertEquals(15, h.opsSinceLastMorph());
            assertEquals(1, h.consecutiveWins(StrategyId.AVL));
            assertEquals(0, h.consecutiveWins(StrategyId.SPLAY));
        }

        @Test
        @DisplayName("afterMorph clears the cooldown clock and the streak")
        void afterMorphResets() {
            MorphHistory h = new MorphHistory(5_000, StrategyId.SPLAY, 3).afterMorph();
            assertEquals(0, h.opsSinceLastMorph());
            assertEquals(0, h.consecutiveWins(StrategyId.SPLAY));
        }
    }
}
