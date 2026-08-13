package test.core;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.evolution.GenomeDrivenTreeController;
import io.github.richeyworks.csrbt.evolution.TreeGenome;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Probe (T-1, 2026-08-12, found while validating the ADR-022 re-scored tournament):
 * {@code TreeContext.getRotationCount()} read a legacy field that NOTHING increments
 * (its own comment: "strategies do not call it") — the real meter is the engine's
 * {@code onRotation()} counter. Every consumer was blind: the battle runner's
 * rotation score term was always 0, the genome controller's STRESS metric
 * (rotations-per-window) was identically 0 forever (the third blinded metric in that
 * family, after entropy G-A and fragmentation G-D), and {@code explainState}'s
 * rotation line always printed 0.
 */
@DisplayName("T-1 — the rotation meter is live, not a dead legacy field")
class RotationMeterProbeTest {

    @Test
    @DisplayName("sequential RB inserts report their rotations")
    void rotationCountIsLive() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        for (int k = 0; k < 200; k++) ctx.add(k);   // RB fixup rotates constantly here
        assertTrue(ctx.getRotationCount() > 0,
                "200 sequential red-black inserts perform many rotations; a count of "
                + ctx.getRotationCount() + " means the meter reads a dead field");
    }

    @Test
    @DisplayName("the stress metric sees rotation churn (legacy metrics path)")
    void stressMetricIsLive() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        GenomeDrivenTreeController c =
                new GenomeDrivenTreeController(ctx, TreeGenome.redBlackGenome());
        c.setUseControlPlane(false);                // the legacy path computes stress
        for (int k = 0; k < 500; k++) c.add(k);     // rotation-heavy stream
        assertTrue(c.getLastStress() > 0.0,
                "a rotation-heavy insert stream must register stress; 0.0 means the "
                + "rotations-per-window signal reads the dead counter");
    }
}
