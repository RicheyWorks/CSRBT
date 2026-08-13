package test.core;

import io.github.richeyworks.csrbt.evolution.StrategyBattleRunner;
import io.github.richeyworks.csrbt.evolution.StrategyBattleRunner.BattleResult;
import io.github.richeyworks.csrbt.evolution.StrategyBattleRunner.WorkloadType;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Probe (ADR-022; fourth-pass audit 2026-08-12, V-C): the battle drove searches
 * through {@code TreeContext.contains}, which never splays (ADR-004 R1 reserves
 * splaying for the write path) — so in the very workloads the runner's header says
 * favor Splay, the competitor could never self-adjust, and the "avgSearchDepth"
 * metric was the ROOT HEIGHT (worst case, ×3 weight), locking Splay into last place
 * with depths in the thousands. Searches now run the strategy's own engine-level
 * search after a measuring walk, and the metric is the realized mean depth.
 */
@DisplayName("ADR-022 — the battle lets Splay splay and scores realized depth")
class BattleMethodologyProbeTest {

    @Test
    @DisplayName("LOCALITY_BURST: Splay's realized depth is small, not the chain height")
    void splaySelfAdjustsInItsOwnWorkload() {
        List<BattleResult> results =
                StrategyBattleRunner.run(WorkloadType.LOCALITY_BURST, 20_000, 7L);

        BattleResult splay = results.stream()
                .filter(r -> r.strategyName.equals("Splay")).findFirst().orElseThrow();
        assertTrue(splay.avgSearchDepth > 0, "searches happened and were measured");
        assertTrue(splay.avgSearchDepth < 100,
                "80%-hot locality searches over a splaying tree average a SMALL realized "
                + "depth; got " + splay.avgSearchDepth + " — the root-height proxy over a "
                + "never-repaired insert chain reads in the thousands");

        // With the rotation meter live (T-1), the score must not double-charge
        // self-adjustment: Splay's splaying is priced in its wall time, so it must
        // place on its depth advantage in its own workload, not be pushed last by a
        // second rotation charge.
        assertTrue(splay.rank <= 2,
                "Splay must contend in LOCALITY_BURST (rank " + splay.rank + ") — a "
                + "rotation term in the score double-counts the work its time already paid");
        assertTrue(splay.rotations > results.stream()
                        .filter(r -> !r.strategyName.equals("Splay"))
                        .mapToInt(r -> r.rotations).max().orElse(0),
                "the live meter must show Splay's self-adjustment as real rotations");

        // Fairness pin: every competitor replays the identical stream.
        long distinctHits = results.stream().map(r -> r.searchHits).distinct().count();
        assertEquals(1, distinctHits, "identical op stream ⇒ identical search hits");
        long distinctSizes = results.stream().map(r -> r.finalSize).distinct().count();
        assertEquals(1, distinctSizes, "identical op stream ⇒ identical final sizes");
    }

    @Test
    @DisplayName("realized depth is a per-search mean for every competitor, not a height")
    void depthIsRealizedForEveryone() {
        List<BattleResult> results =
                StrategyBattleRunner.run(WorkloadType.SEARCH_HEAVY, 10_000, 11L);
        for (BattleResult r : results) {
            assertTrue(r.avgSearchDepth > 0 && r.avgSearchDepth < 64,
                    r.strategyName + ": realized mean depth over a few hundred keys must "
                    + "be modest, got " + r.avgSearchDepth);
        }
    }
}
