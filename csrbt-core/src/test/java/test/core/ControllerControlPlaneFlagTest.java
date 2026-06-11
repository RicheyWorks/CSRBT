package test.core;

import core.TreeContext;
import core.control.MorphController;
import core.control.MorphPolicy;
import core.evolution.GenomeDrivenTreeController;
import core.evolution.TreeGenome;
import core.strategy.RedBlackStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * GenomeDrivenTreeController control-plane re-point (ADR-002 step 6, Phase D / D4): the
 * flag-gated cutover of {@code evaluate()} from the legacy genome body onto the
 * {@code WorkloadMonitor -> StrategyScorer -> MorphPolicy} pipeline (the {@link MorphController}).
 *
 * <p>These tests assert on <b>observable state</b> (the active strategy and morph count), not on log
 * output. The single {@code event=morph_eval} line per evaluation is the {@link MorphController}'s
 * contract and is covered by {@code MorphControllerTest} (G9); asserting it again here would mean
 * capturing logs across test classes, which is order-fragile under the shared Log4j context. The
 * re-point is instead proven end-to-end by the morph <em>outcome</em>: the same skewed read stream
 * morphs RB&rarr;Splay with the flag ON and does not morph with it OFF.</p>
 *
 * <p><b>Why the outcome is deterministic.</b> The control plane is given an eager
 * {@link MorphPolicy} (no cooldown, one stability win) so a morph can land without the 4000-op
 * default cooldown. The workload — a hot search key — reads as high {@code readFraction} + high
 * {@code accessSkew} through the controller ({@code ControllerMonitorFeedTest}), and that regime is
 * pinned to "Splay first" by {@code StrategyScorerTest}.</p>
 *
 * <p>Verified on the host via {@code ant clean test} (the dev sandbox is JRE-only; plan §8).</p>
 */
@DisplayName("GenomeDrivenTreeController control-plane flag (Phase D / D4)")
public class ControllerControlPlaneFlagTest {

    private static final int EVAL_INTERVAL = 10;   // mirrors the controller's private cadence

    /** A control plane that can morph promptly: no cooldown, 10% margin, one stability win. */
    private static MorphPolicy eager() { return new MorphPolicy(0, 0.10, 1); }

    /** Flag-ON controller over a Red-Black context + genome, with an eager control policy. */
    private static GenomeDrivenTreeController eagerControlController() {
        GenomeDrivenTreeController c = new GenomeDrivenTreeController(
                new TreeContext(new RedBlackStrategy<>()), TreeGenome.redBlackGenome(), eager());
        c.setUseControlPlane(true);
        return c;
    }

    @Test
    @DisplayName("flag ON: a skewed read stream morphs RB -> Splay on the control plane")
    void flagOnSkewedReadsMorphToSplay() {
        GenomeDrivenTreeController c = eagerControlController();
        assertTrue(c.isUseControlPlane(), "control plane is enabled");
        assertEquals(TreeGenome.StructureType.RED_BLACK, c.getActiveStrategyType(), "incumbent starts RB");

        for (int i = 0; i < 50; i++)   c.add(i);          // populate the tree
        for (int i = 0; i < 1500; i++) c.contains(7);     // one hot key -> high read + high skew

        assertEquals(TreeGenome.StructureType.SPLAY, c.getActiveStrategyType(),
                "skewed read-heavy workload selects Splay on the control plane");
        assertTrue(c.getMorphCount() >= 1, "at least one morph committed");
    }

    @Test
    @DisplayName("flag ON: reads alone advance the eval cadence enough to morph (plan §12.1 B2)")
    void flagOnReadsDriveCadence() {
        GenomeDrivenTreeController c = eagerControlController();
        // Fewer writes than one eval interval: with the flag ON, only the reads can carry the op
        // clock to an evaluation. If reads did not tick the cadence, no eval — hence no morph — ever fires.
        for (int i = 0; i < EVAL_INTERVAL - 1; i++) c.add(i);   // 9 writes: below the cadence, 0 evals so far
        for (int i = 0; i < 2000; i++)              c.contains(3);

        assertEquals(TreeGenome.StructureType.SPLAY, c.getActiveStrategyType(),
                "reads advanced the eval cadence and drove the morph");
        assertTrue(c.getMorphCount() >= 1, "the read-driven cadence produced a morph");
    }

    @Test
    @DisplayName("control plane is ON by default (D5 flips the flag)")
    void controlPlaneOnByDefault() {
        GenomeDrivenTreeController c = new GenomeDrivenTreeController(
                new TreeContext(new RedBlackStrategy<>()), TreeGenome.redBlackGenome());
        assertTrue(c.isUseControlPlane(), "D5 defaults the control-plane re-point ON");
    }

    @Test
    @DisplayName("flag OFF: legacy genome path; the same stream does NOT morph (control plane gated off)")
    void flagOffKeepsLegacyGenomePath() {
        GenomeDrivenTreeController c = new GenomeDrivenTreeController(
                new TreeContext(new RedBlackStrategy<>()), TreeGenome.redBlackGenome());
        c.setUseControlPlane(false);                     // opt out of the new default to exercise the legacy path
        assertFalse(c.isUseControlPlane(), "legacy genome path selected");

        for (int i = 0; i < 50; i++)   c.add(i);
        for (int i = 0; i < 1500; i++) c.contains(7);   // under the flag OFF, reads do not tick the cadence

        assertEquals(TreeGenome.StructureType.RED_BLACK, c.getActiveStrategyType(),
                "flag OFF: the control plane never runs and the legacy cooldown prevents a morph here");
        assertEquals(0, c.getMorphCount(), "no morph on the legacy path within its cooldown");
    }
}
