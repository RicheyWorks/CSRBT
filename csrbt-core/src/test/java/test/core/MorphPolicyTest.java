package test.core;

import core.evolution.GenomeDrivenTreeController.MorphPolicy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Anti-thrash morph gating (DESIGN §3.3). The policy must require cooldown,
 * stability, AND a minimum improvement margin before allowing a morph.
 */
@DisplayName("MorphPolicy gating")
public class MorphPolicyTest {

    // cooldown=4000 ops, minImprovement=20%, stability=3 wins
    private final MorphPolicy policy = MorphPolicy.defaults();

    @Test
    @DisplayName("all gates satisfied → morph")
    void allGatesPass() {
        // candidate 0.90 vs current 0.50 = 80% improvement; 5000 ops; 3 wins
        assertTrue(policy.shouldMorph(0.50, 0.90, 5000, 3));
    }

    @Test
    @DisplayName("within cooldown → hold even with a big improvement")
    void cooldownBlocks() {
        assertFalse(policy.shouldMorph(0.50, 0.90, 1000, 5),
                "must not morph inside the cooldown window");
    }

    @Test
    @DisplayName("not yet stable → hold")
    void stabilityBlocks() {
        assertFalse(policy.shouldMorph(0.50, 0.90, 5000, 2),
                "candidate must win enough consecutive evals first");
    }

    @Test
    @DisplayName("improvement below the margin → hold")
    void marginBlocks() {
        // 0.55 vs 0.50 = 10% < 20% threshold
        assertFalse(policy.shouldMorph(0.50, 0.55, 5000, 3),
                "a marginal improvement must not trigger an O(n) morph");
    }

    @Test
    @DisplayName("candidate no better than incumbent → hold")
    void notBetterBlocks() {
        assertFalse(policy.shouldMorph(0.70, 0.70, 5000, 3));
        assertFalse(policy.shouldMorph(0.70, 0.60, 5000, 3));
    }

    @Test
    @DisplayName("custom policy thresholds are honored")
    void customThresholds() {
        MorphPolicy eager = new MorphPolicy(0, 0.05, 1);   // no cooldown, 5%, 1 win
        assertTrue(eager.shouldMorph(0.50, 0.55, 0, 1), "10% beats a 5% margin with no cooldown");
        MorphPolicy strict = new MorphPolicy(0, 0.50, 1);  // require 50% improvement
        assertFalse(strict.shouldMorph(0.50, 0.60, 100, 5), "20% < 50% margin");
    }
}
