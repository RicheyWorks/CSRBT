package test.core;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.control.MorphPolicy;
import io.github.richeyworks.csrbt.control.WorkloadFeatures;
import io.github.richeyworks.csrbt.evolution.GenomeDrivenTreeController;
import io.github.richeyworks.csrbt.evolution.TreeGenome;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * Control-plane convergence harness (ADR-002 step 6, Phase D / D5), mapped to the DESIGN §15 goals.
 * With the flag now ON by default, these drive real op streams through the controller and assert on
 * observable state — the active strategy and the morph count — not on logs.
 *
 * <p>The workloads are engineered to be unambiguous so the outcome is deterministic without the
 * production hysteresis: an <em>eager</em> {@link MorphPolicy} (no cooldown, one stability win)
 * keeps runtime bounded, and the tree is pre-populated <em>directly through the {@link TreeContext}</em>
 * so the monitor sees a pure read (or pure write) stream. The scorer reads only readFraction /
 * writeFraction / accessSkew, so a hot-key read stream is unambiguous Splay regardless of size.</p>
 */
@DisplayName("Control-plane convergence (Phase D / D5)")
public class ControllerConvergenceTest {

    /** No cooldown, 10% margin, one stability win — bounded runtime for the harness. */
    private static MorphPolicy eager() { return new MorphPolicy(0, 0.10, 1); }

    private static GenomeDrivenTreeController controllerOver(TreeContext ctx) {
        return new GenomeDrivenTreeController(ctx, TreeGenome.redBlackGenome(), eager());
    }

    @Test
    @DisplayName("G3: a skewed read workload converges to Splay in exactly one morph (no thrash)")
    void convergesToSplayInOneMorph() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        for (int i = 0; i < 64; i++) ctx.add(i);            // populate directly: the monitor sees only the reads
        GenomeDrivenTreeController c = controllerOver(ctx);

        for (int i = 0; i < 600; i++) c.contains(7);        // one hot key -> read≈1, skew≈1 -> Splay always top

        assertEquals(TreeGenome.StructureType.SPLAY, c.getActiveStrategyType(), "converges to Splay");
        assertEquals(1, c.getMorphCount(), "exactly one morph: RB -> Splay, then it holds (Splay stays optimal)");
    }

    @Test
    @DisplayName("G4: a steady write-heavy workload converges to Hybrid in one morph, then holds")
    void steadyWorkloadConvergesOnce() {
        GenomeDrivenTreeController c = controllerOver(new TreeContext(new RedBlackStrategy<>()));

        for (int i = 0; i < 600; i++) c.add(i);             // pure distinct writes, low skew

        // Re-pinned twice, both times by the meter. 2026-06-10: AVL over RB (the old pin
        // encoded rotation pricing). 2026-07-14: HYBRID over AVL — the earlier evidence was
        // measured through the double-descent write path (census finding A); post-fix, Hybrid
        // is best-fixed on every E3/E3b seed. Steady still means no thrash, not no decision:
        // the anti-thrash property this test guards is the morph *count*.
        assertEquals(TreeGenome.StructureType.HYBRID, c.getActiveStrategyType(),
                "the recalibrated scorer follows the post-fix meter to Hybrid");
        assertEquals(1, c.getMorphCount(), "exactly one morph on a steady workload — no thrash");
    }

    @Test
    @DisplayName("G4: a regime change is followed — skewed reads pick Splay, then heavy writes go to Hybrid")
    void regimeChangeIsFollowed() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        for (int i = 0; i < 64; i++) ctx.add(i);
        GenomeDrivenTreeController c = controllerOver(ctx);

        for (int i = 0; i < 600; i++) c.contains(7);        // regime 1: skewed reads -> Splay
        assertEquals(TreeGenome.StructureType.SPLAY, c.getActiveStrategyType(), "regime 1 selects Splay");

        for (int i = 64; i < 5064; i++) c.add(i);           // regime 2: heavy writes flush the window
        assertEquals(TreeGenome.StructureType.HYBRID, c.getActiveStrategyType(),
                "the write regime is followed to Hybrid (the 2026-07-14 post-fix pick)");
    }

    @Test
    @DisplayName("G5: the hot path feeds O(1) constants — no per-op tree scan for depth or rotations")
    void hotPathFeedsConstantsNoTreeScan() {
        GenomeDrivenTreeController c = controllerOver(new TreeContext(new RedBlackStrategy<>()));
        for (int i = 0; i < 300; i++) c.add(i);
        for (int i = 0; i < 300; i++) c.contains(i % 50);

        WorkloadFeatures f = c.getWorkloadMonitor().snapshot();
        assertEquals(0.0, f.meanSearchDepth(), 0.0,
                "search depth is fed as constant 0 — no per-op path probe (plan decision 12.2.2)");
        assertEquals(0.0, f.rotationsPerWrite(), 0.0,
                "rotations are fed as constant 0 — no per-op rotation scan (plan decision 12.2.2)");
    }
}
