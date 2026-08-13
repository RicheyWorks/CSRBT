package test.core;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.evolution.GenomeDrivenTreeController;
import io.github.richeyworks.csrbt.evolution.TreeGenome;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Random;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Probes (bug audit 2026-08-12, genome-controller sweep) — each red on unfixed code.
 *
 * <p>G-A: {@code computeEntropy} bucketed the access window by ABSOLUTE key value over
 * the whole int range (bucket width 2^32/8 ≈ 5.4e8), so every realistic workload —
 * uniform-random and single-hot-key alike — landed in one bucket and read entropy 0.0:
 * the Splay locality signal was permanently blind. G-B: the controller took its
 * incumbent from the genome's preference instead of the tree's installed strategy, so
 * a genome/context mismatch reported "already optimal" forever and never morphed.
 * G-D: fragmentation and performance memory read the CACHED node height, which only
 * AVL/Hybrid maintain — under Red-Black a deep tree read fragmentation 0.0.</p>
 */
@DisplayName("GenomeDrivenTreeController — entropy, incumbent inference, real heights")
class GenomeControllerMetricsProbeTest {

    @Test
    @DisplayName("G-A: uniform-random access reads HIGH entropy; a single hot key reads LOW")
    void entropyMeasuresLocality() {
        // The legacy metrics path computes lastEntropy; adds drive its eval cadence.
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        GenomeDrivenTreeController c = new GenomeDrivenTreeController(ctx, TreeGenome.redBlackGenome());
        c.setUseControlPlane(false);
        Random rnd = new Random(7);
        for (int k = 0; k < 2_000; k++) c.add(rnd.nextInt(1_000_000));   // max-entropy access
        double uniform = c.getLastEntropy();
        assertTrue(uniform > 0.5,
                "uniform-random keys in [0, 1e6) are a maximally high-entropy window, "
                + "but entropy read " + uniform + " — absolute-range bucketing puts every "
                + "realistic workload in one bucket");

        TreeContext ctx2 = new TreeContext(new RedBlackStrategy<>());
        GenomeDrivenTreeController c2 = new GenomeDrivenTreeController(ctx2, TreeGenome.redBlackGenome());
        c2.setUseControlPlane(false);
        for (int i = 0; i < 2_000; i++) c2.add(500);                     // one hot key, tallied every op
        double hot = c2.getLastEntropy();
        assertTrue(hot < 0.2, "a single hot key is zero-entropy; read " + hot);
        assertTrue(uniform > hot + 0.4,
                "the two workloads must be distinguishable (uniform=" + uniform
                + ", hot=" + hot + ") — this is the Splay locality signal");
    }

    @Test
    @DisplayName("G-B: the incumbent is the tree's installed strategy, not the genome's wish")
    void incumbentInferredFromContext() {
        TreeContext rbContext = new TreeContext(new RedBlackStrategy<>());
        GenomeDrivenTreeController c =
                new GenomeDrivenTreeController(rbContext, TreeGenome.avlGenome());
        assertEquals(TreeGenome.StructureType.RED_BLACK, c.getActiveStrategyType(),
                "the context runs RedBlackStrategy — reporting the genome's AVL "
                + "preference as 'active' makes every evaluation HOLD ('already "
                + "optimal') on a strategy that is not installed");
    }

    @Test
    @DisplayName("G-D: fragmentation sees the REAL height under Red-Black (stale cache ignored)")
    void fragmentationUsesMeasuredHeight() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        GenomeDrivenTreeController c = new GenomeDrivenTreeController(ctx, TreeGenome.redBlackGenome());
        c.setUseControlPlane(false);                      // the legacy path computes the metric
        for (int k = 0; k < 500; k++) c.add(k);           // sequential: real height ≫ ideal
        double frag = c.getLastFragmentation();
        assertTrue(frag > 0.05,
                "a 500-key RB tree from sequential inserts is measurably taller than "
                + "ideal (real height ~15 vs ideal 9), but fragmentation read " + frag
                + " — the cached height RedBlackStrategy never maintains");
    }
}
