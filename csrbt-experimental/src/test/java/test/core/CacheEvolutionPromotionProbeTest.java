package test.core;

import io.github.richeyworks.csrbt.control.MorphPolicy;
import io.github.richeyworks.csrbt.experimental.cache.CacheEvolutionLoop;
import io.github.richeyworks.csrbt.experimental.cache.CacheGenome;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Probe (bug audit 2026-08-12, deep sweep): on promotion, {@code endGeneration} swapped
 * the winning shadow into {@code primary} but left the same object in {@code onTrial}
 * (only cleared at the NEXT {@code beginGeneration}). In the gap, every {@code lookup()}
 * — the public data plane the external consumer (Brine) drives continuously — processed
 * the primary TWICE: once as primary, once as its own shadow. A fresh-key miss was
 * recorded as miss+hit (flooring the published hit rate near 50%), probation hits
 * double-counted (keys promoted after half the genome's {@code promoteAfter}), and
 * recency was double-bumped. Fix: remove the promoted body from {@code onTrial}.
 */
@DisplayName("CacheEvolutionLoop — a promoted champion must leave the trial pool")
class CacheEvolutionPromotionProbeTest {

    @Test
    @DisplayName("after a promoting endGeneration, the primary is no longer in onTrial")
    void promotedPrimaryLeavesTrialPool() throws Exception {
        CacheGenome weak = new CacheGenome(0, 1);   // no protected segment: scans evict hot keys
        CacheGenome strong = new CacheGenome(5, 1); // shielded hot keys survive the scans
        CacheEvolutionLoop loop = new CacheEvolutionLoop(
                10, List.of(weak, strong), 2, 2, new MorphPolicy(0, 0.0, 1), 42L);

        loop.beginGeneration();
        // Hot keys + cold scans: the shielded genome keeps the hot keys, the
        // unshielded one thrashes them — strong must out-score weak (the primary).
        int ops = 0;
        for (int round = 0; round < 40; round++) {
            loop.lookup(1); ops++;
            loop.lookup(2); ops++;
            for (int cold = 0; cold < 20; cold++) { loop.lookup(100 + round * 20 + cold); ops++; }
            loop.lookup(1); ops++;
            loop.lookup(2); ops++;
        }
        CacheEvolutionLoop.GenerationResult result = loop.endGeneration(ops);
        assertNotEquals(weak, loop.champion(),
                "precondition: the stronger genome must win and be promoted (got "
                + result + ")");

        // The defect: the promoted body stayed registered as its own shadow.
        Field onTrialField = CacheEvolutionLoop.class.getDeclaredField("onTrial");
        Field primaryField = CacheEvolutionLoop.class.getDeclaredField("primary");
        onTrialField.setAccessible(true);
        primaryField.setAccessible(true);
        Map<?, ?> onTrial = (Map<?, ?>) onTrialField.get(loop);
        Object primary = primaryField.get(loop);
        boolean primaryStillOnTrial = false;
        for (Object body : onTrial.keySet()) {
            if (body == primary) { primaryStillOnTrial = true; break; }
        }
        assertFalse(primaryStillOnTrial,
                "the promoted champion is still in onTrial — every lookup() between "
                + "generations processes it twice (miss recorded as miss+hit, probation "
                + "hits double-counted)");

        // And the data plane stays honest: fresh-key lookups after promotion are misses.
        double before = loop.primaryHitRate();
        for (int k = 0; k < 100; k++) loop.lookup(50_000 + k);   // brand-new keys
        assertTrue(loop.primaryHitRate() <= before,
                "100 lookups of never-seen keys must not RAISE the primary hit rate "
                + "(double-processing records each admit-then-shadow-get as a hit)");
    }
}
