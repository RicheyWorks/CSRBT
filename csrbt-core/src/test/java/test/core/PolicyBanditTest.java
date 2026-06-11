package test.core;

import core.evolution.PolicyBandit;
import core.evolution.PolicyGenome;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-011 V3 — the bandit, as pure math. No trees here: the scoreboard's UCB1 arithmetic
 * is checked against hand-computed values, exploration provably revisits an under-pulled
 * arm, exploitation provably settles on the cheaper one, and disqualification is
 * permanent death with the search-exhausted case failing loudly.
 */
@DisplayName("PolicyBandit — UCB1 over the discretized box (ADR-011 V3)")
public class PolicyBanditTest {

    private static final PolicyGenome WB32 = PolicyGenome.weightBalanced(3, 2);
    private static final PolicyGenome WB42 = PolicyGenome.weightBalanced(4, 2);
    private static final PolicyGenome WB21 = PolicyGenome.weightBalanced(2, 1);

    @Nested
    @DisplayName("selection arithmetic")
    class Arithmetic {

        @Test
        @DisplayName("untried arms are selected first, in arm order")
        void untriedFirst() {
            PolicyBandit b = new PolicyBandit(List.of(WB32, WB42, WB21));
            assertEquals(WB32, b.select().arm());
            b.recordCost(WB32, 1.0);
            assertEquals(WB42, b.select().arm());
            b.recordCost(WB42, 1.0);
            assertEquals(WB21, b.select().arm());
        }

        @Test
        @DisplayName("hand-computed UCB1: value = meanCost − √(2·ln N / n), exactly")
        void exactUcbValue() {
            PolicyBandit b = new PolicyBandit(List.of(WB32, WB42), 1.0);
            b.recordCost(WB32, 0.50);
            b.recordCost(WB32, 0.70);   // mean 0.60, pulls 2
            b.recordCost(WB42, 0.80);   // mean 0.80, pulls 1; N = 3
            PolicyBandit.Selection sel = b.select();
            double bonus32 = Math.sqrt(2.0 * Math.log(3) / 2);   // ≈ 1.0481
            double bonus42 = Math.sqrt(2.0 * Math.log(3) / 1);   // ≈ 1.4823
            // 0.60 − 1.0481 = −0.4481 vs 0.80 − 1.4823 = −0.6823 → WB42 wins (optimism).
            assertEquals(WB42, sel.arm());
            assertEquals(0.80 - bonus42, sel.value(), 1e-12);
            assertEquals(bonus42, sel.bonus(), 1e-12);
            assertTrue(bonus32 < bonus42, "more pulls must mean a smaller bonus");
        }

        @Test
        @DisplayName("exploitation: with exploration 0, the cheapest mean always wins")
        void pureExploitation() {
            PolicyBandit b = new PolicyBandit(List.of(WB32, WB42), 0.0);
            b.recordCost(WB32, 0.9);
            b.recordCost(WB42, 0.3);
            for (int i = 0; i < 5; i++) {
                assertEquals(WB42, b.select().arm());
                b.recordCost(WB42, 0.3);
            }
        }

        @Test
        @DisplayName("exploration: a neglected arm's bonus grows until it is re-selected")
        void explorationRevisits() {
            PolicyBandit b = new PolicyBandit(List.of(WB32, WB42), 1.0);
            b.recordCost(WB32, 0.50);   // slightly worse arm, one pull
            b.recordCost(WB42, 0.40);
            boolean revisited = false;
            for (int i = 0; i < 200 && !revisited; i++) {
                PolicyGenome pick = b.select().arm();
                if (pick.equals(WB32)) revisited = true;
                b.recordCost(pick, pick.equals(WB42) ? 0.40 : 0.50);
            }
            assertTrue(revisited, "UCB1 must eventually revisit the under-pulled arm");
        }
    }

    @Nested
    @DisplayName("disqualification and lifecycle")
    class Lifecycle {

        @Test
        @DisplayName("a disqualified arm is never selected or scored again; exhaustion is loud")
        void disqualificationIsDeath() {
            PolicyBandit b = new PolicyBandit(List.of(WB32, WB42));
            b.disqualify(WB32, "health gate");
            assertEquals(WB42, b.select().arm());
            assertTrue(b.isDisqualified(WB32));
            assertEquals("health gate", b.disqualifyReason(WB32));
            assertThrows(IllegalStateException.class, () -> b.recordCost(WB32, 0.5));

            b.disqualify(WB42, "own invariant");
            assertThrows(IllegalStateException.class, b::select);
            assertTrue(b.statsLine().contains("DQ(health gate)"), b.statsLine());
        }

        @Test
        @DisplayName("bestArm is the lowest scored mean among live arms; null before any score")
        void bestArm() {
            PolicyBandit b = new PolicyBandit(List.of(WB32, WB42, WB21));
            assertNull(b.bestArm());
            b.recordCost(WB32, 0.6);
            b.recordCost(WB42, 0.2);
            b.recordCost(WB21, 0.4);
            assertEquals(WB42, b.bestArm());
            b.disqualify(WB42, "post-hoc");
            assertEquals(WB21, b.bestArm(), "a dead arm cannot be best");
        }

        @Test
        @DisplayName("construction validates; the box grid is the 28 in-box points")
        void constructionAndGrid() {
            assertThrows(IllegalArgumentException.class, () -> new PolicyBandit(List.of()));
            assertThrows(IllegalArgumentException.class,
                    () -> new PolicyBandit(List.of(WB32, WB32)));
            assertThrows(IllegalArgumentException.class,
                    () -> new PolicyBandit(List.of(WB32), -0.1));

            List<PolicyGenome> grid = PolicyBandit.boxGrid();
            assertEquals(28, grid.size());                       // Σ (Δ−1), Δ = 2..8
            assertTrue(grid.contains(PolicyGenome.verifiedDefault()));
            assertTrue(grid.contains(PolicyGenome.weightBalanced(5, 3)),
                    "the unsound point is an arm on purpose — it self-disqualifies on the record");
        }
    }
}
