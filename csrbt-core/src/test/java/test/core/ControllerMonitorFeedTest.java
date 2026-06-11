package test.core;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.control.WorkloadFeatures;
import io.github.richeyworks.csrbt.evolution.GenomeDrivenTreeController;
import io.github.richeyworks.csrbt.evolution.TreeGenome;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * GenomeDrivenTreeController monitor feed (ADR-002 step 6, Phase D / D3): every op routed
 * through the controller is mirrored into the control-plane WorkloadMonitor. The feed is
 * observation-only — the genome still decides — so this asserts the monitor sees the stream,
 * not that any decision changed.
 */
@DisplayName("GenomeDrivenTreeController monitor feed (Phase D / D3)")
public class ControllerMonitorFeedTest {

    private static GenomeDrivenTreeController rbController() {
        return new GenomeDrivenTreeController(new TreeContext(new RedBlackStrategy<>()),
                                              TreeGenome.redBlackGenome());
    }

    @Test
    @DisplayName("adds and searches reach the monitor; a read-heavy stream reads as read-heavy")
    void feedReflectsOpStream() {
        GenomeDrivenTreeController c = rbController();
        for (int i = 0; i < 50; i++)  c.add(i);        // 50 effective writes
        for (int i = 0; i < 200; i++) c.contains(7);   // 200 reads
        WorkloadFeatures f = c.getWorkloadMonitor().snapshot();
        assertEquals(50L, f.size(), "effective adds advance the monitor's size");
        assertTrue(f.readFraction() > f.writeFraction(),
                "200 reads vs 50 writes -> read-dominated, read=" + f.readFraction());
    }

    @Test
    @DisplayName("a hot search key is more skewed than a uniform read stream")
    void hotKeyRaisesSkew() {
        GenomeDrivenTreeController hot = rbController();
        for (int i = 0; i < 50; i++)  hot.add(i);
        for (int i = 0; i < 400; i++) hot.contains(7);            // one hot key
        double hotSkew = hot.getWorkloadMonitor().snapshot().accessSkew();

        GenomeDrivenTreeController uni = rbController();
        for (int i = 0; i < 50; i++)  uni.add(i);
        for (int i = 0; i < 400; i++) uni.contains(i % 50);       // spread across 50 keys
        double uniformSkew = uni.getWorkloadMonitor().snapshot().accessSkew();

        assertTrue(hotSkew > uniformSkew,
                "hot key should be more skewed than uniform: hot=" + hotSkew + " uniform=" + uniformSkew);
    }

    @Test
    @DisplayName("observation-only: duplicate adds and absent removes do not count")
    void effectiveMutationsOnly() {
        GenomeDrivenTreeController c = rbController();
        c.add(1); c.add(1); c.add(1);   // one effective insert + two duplicates
        c.remove(999);                   // absent
        assertEquals(1L, c.getWorkloadMonitor().snapshot().size(),
                "only the effective insert advances size");
    }
}
