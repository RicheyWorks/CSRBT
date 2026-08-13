package test.core;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.control.WorkloadFeatures;
import io.github.richeyworks.csrbt.experimental.ecology.BetaDiversity;
import io.github.richeyworks.csrbt.experimental.ecology.CommunityMetrics;
import io.github.richeyworks.csrbt.experimental.ecology.EcologyRecorder;
import io.github.richeyworks.csrbt.experimental.ecology.LifeTable;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Random;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The abundance seam (audit EC-1's fix) — windowing, demography bookkeeping, bounded
 * retention, determinism, and the end-to-end demonstration the audit demanded: on a
 * real tree driven by uniform vs hot-key access streams, the diversity indices now
 * <em>separate</em>, where the structural versions were provably constant.
 */
@DisplayName("EcologyRecorder — deterministic abundance/demography/growth recorder")
class EcologyRecorderTest {

    // ── Windowing & tallies ───────────────────────────────────────────────────

    @Test
    @DisplayName("windows close every windowOps ops; the tail stays in the open window")
    void windowing() {
        EcologyRecorder rec = new EcologyRecorder(10, 8);
        for (int i = 0; i < 25; i++) rec.recordSearch(1, 3);

        assertEquals(25, rec.opCount());
        assertEquals(2, rec.closedWindows().size());
        assertEquals(10L, rec.closedWindows().get(0).get(1));
        assertEquals(5L, rec.currentWindowAbundance().get(1));
        assertEquals(25L, rec.cumulativeAbundance().get(1));
        assertEquals(2, rec.populationSeries().size());
    }

    @Test
    @DisplayName("closed-window retention is capped at maxWindows, oldest evicted")
    void boundedRetention() {
        EcologyRecorder rec = new EcologyRecorder(1, 3);
        for (int key = 1; key <= 10; key++) rec.recordSearch(key, 1);

        List<Map<Integer, Long>> windows = rec.closedWindows();
        assertEquals(3, windows.size());
        // Oldest surviving window is op 8's (keys 1..7 evicted).
        assertEquals(1L, windows.get(0).get(8));
        assertEquals(1L, windows.get(2).get(10));
    }

    @Test
    @DisplayName("adds open lifespans, removes close them; alive count tracks the difference")
    void demographyBookkeeping() {
        EcologyRecorder rec = new EcologyRecorder(100, 4);
        rec.recordAdd(7);            // op 1 → birth of 7
        rec.recordAdd(8);            // op 2 → birth of 8
        rec.recordSearch(7, 2);      // op 3
        rec.recordRemove(7, 0);      // op 4 → death of 7, age 3
        assertEquals(1, rec.aliveCount());
        assertEquals(1, rec.lifespans().size());

        LifeTable.Lifespan ls = rec.lifespans().get(0);
        assertEquals(7, ls.key());
        assertEquals(3, ls.age());
        assertTrue(rec.aliveBirthOps().containsKey(8));

        // A remove without an observed birth is tallied but opens no lifespan.
        rec.recordRemove(99, 0);
        assertEquals(1, rec.lifespans().size());
        assertEquals(1L, rec.cumulativeAbundance().get(99));
    }

    @Test
    @DisplayName("population series samples alive count at window boundaries")
    void populationSeries() {
        EcologyRecorder rec = new EcologyRecorder(4, 8);
        rec.recordAdd(1);
        rec.recordAdd(2);
        rec.recordAdd(3);
        rec.recordAdd(4);            // window closes at op 4 → population 4
        rec.recordRemove(2, 0);
        rec.recordAdd(5);
        rec.recordSearch(1, 1);
        rec.recordSearch(1, 1);      // window closes at op 8 → population 4
        List<long[]> series = rec.populationSeries();
        assertEquals(2, series.size());
        assertEquals(4, series.get(0)[0]);
        assertEquals(4, series.get(0)[1]);
        assertEquals(8, series.get(1)[0]);
        assertEquals(4, series.get(1)[1]);
    }

    @Test
    @DisplayName("standalone snapshot is EMPTY; constructor validates bounds")
    void seamContract() {
        assertEquals(WorkloadFeatures.EMPTY, new EcologyRecorder().snapshot());
        assertThrows(IllegalArgumentException.class, () -> new EcologyRecorder(0, 5));
        assertThrows(IllegalArgumentException.class, () -> new EcologyRecorder(5, 0));
    }

    @Test
    @DisplayName("determinism: identical op streams produce identical state, field for field")
    void determinism() {
        EcologyRecorder a = new EcologyRecorder(16, 8);
        EcologyRecorder b = new EcologyRecorder(16, 8);
        Random seedA = new Random(42), seedB = new Random(42);
        for (EcologyRecorder rec : List.of(a, b)) {
            Random rng = rec == a ? seedA : seedB;
            for (int i = 0; i < 500; i++) {
                int key = rng.nextInt(50);
                switch (rng.nextInt(3)) {
                    case 0 -> rec.recordAdd(key);
                    case 1 -> rec.recordRemove(key);
                    default -> rec.recordSearch(key, 1);
                }
            }
        }
        assertEquals(a.opCount(), b.opCount());
        assertEquals(a.cumulativeAbundance(), b.cumulativeAbundance());
        assertEquals(a.closedWindows(), b.closedWindows());
        assertEquals(a.lifespans(), b.lifespans());
        assertEquals(a.aliveBirthOps(), b.aliveBirthOps());
    }

    // ── The EC-1 demonstration ────────────────────────────────────────────────

    @Test
    @DisplayName("EC-1 fixed: on a live tree, uniform vs hot-key access now separates H' and J'")
    void indicesVaryOnLiveTree() {
        // Two identical trees, two access regimes, one seeded stream each.
        TreeContext uniformTree = new TreeContext(new RedBlackStrategy<>());
        TreeContext hotKeyTree  = new TreeContext(new RedBlackStrategy<>());
        EcologyRecorder uniform = new EcologyRecorder(256, 16);
        EcologyRecorder hotKey  = new EcologyRecorder(256, 16);

        for (int k = 0; k < 100; k++) {
            uniformTree.add(k);
            uniform.recordAdd(k);
            hotKeyTree.add(k);
            hotKey.recordAdd(k);
        }

        Random rng = new Random(7);
        for (int i = 0; i < 2000; i++) {
            int uKey = i % 100;                       // round-robin: perfectly even
            uniformTree.contains(uKey);
            uniform.recordSearch(uKey, 1);

            // 90% of lookups on a 5-key hot set, 10% uniform.
            int hKey = rng.nextInt(10) < 9 ? rng.nextInt(5) : rng.nextInt(100);
            hotKeyTree.contains(hKey);
            hotKey.recordSearch(hKey, 1);
        }

        double uniformH = CommunityMetrics.shannon(uniform.cumulativeAbundance());
        double hotKeyH  = CommunityMetrics.shannon(hotKey.cumulativeAbundance());
        double uniformJ = CommunityMetrics.pielouEvenness(uniform.cumulativeAbundance());
        double hotKeyJ  = CommunityMetrics.pielouEvenness(hotKey.cumulativeAbundance());

        // The audit's constants: structural H' ≡ ln(S), J' ≡ 1 for BOTH regimes.
        // Access-founded indices must separate them, decisively.
        assertTrue(uniformH > hotKeyH,
                "uniform H'=" + uniformH + " must exceed hot-key H'=" + hotKeyH);
        assertTrue(uniformJ - hotKeyJ > 0.2,
                "evenness gap too small: " + uniformJ + " vs " + hotKeyJ);

        // And the windows carry between-community signal: consecutive hot-key windows
        // overlap heavily (same hot set), so temporal Pianka is high, not degenerate-0.
        List<Map<Integer, Long>> windows = hotKey.closedWindows();
        assertTrue(windows.size() >= 2);
        double overlap = BetaDiversity.pianka(
                windows.get(windows.size() - 2), windows.get(windows.size() - 1));
        assertTrue(overlap > 0.9,
                "consecutive hot-key windows should overlap strongly, got " + overlap);
    }
}
