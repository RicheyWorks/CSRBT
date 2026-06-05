package test.core;

import core.control.RollingWorkloadMonitor;
import core.control.WorkloadFeatures;
import core.control.WorkloadMonitor;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Phase-A control-plane unit (ADR-002 step 6): the {@link RollingWorkloadMonitor}
 * must turn a raw op stream into the DESIGN §9.2 feature vector with O(1)/op ingest
 * and no tree traversal. These tests drive synthetic streams and assert the resulting
 * {@link WorkloadFeatures}; the thresholds were derived from a numeric model of the
 * monitor's math and carry wide margins so they pin behaviour, not exact constants.
 *
 * <p>All monitors use a short window (256 ops) and a 4×512 sketch so a few thousand
 * synthetic ops fully exercise steady state.</p>
 */
@DisplayName("RollingWorkloadMonitor feature extraction")
public class WorkloadMonitorTest {

    private static final int W = 256, ROWS = 4, COLS = 512, N = 4000;

    private static RollingWorkloadMonitor monitor() {
        return new RollingWorkloadMonitor(W, ROWS, COLS);
    }

    // ── Access skew ──────────────────────────────────────────────────────────────

    @Test
    @DisplayName("uniform distinct-key access → skew ≈ 0")
    void uniformAccessLowSkew() {
        WorkloadMonitor m = monitor();
        for (int i = 0; i < N; i++) m.recordSearch(i, 10);
        double skew = m.snapshot().accessSkew();
        assertTrue(skew < 0.05, "uniform workload should look unskewed, was " + skew);
    }

    @Test
    @DisplayName("single hot key → skew ≈ 1")
    void singleHotKeyHighSkew() {
        WorkloadMonitor m = monitor();
        for (int i = 0; i < N; i++) m.recordSearch(42, 7);
        double skew = m.snapshot().accessSkew();
        assertTrue(skew > 0.9, "one hot key should saturate skew, was " + skew);
    }

    @Test
    @DisplayName("skew is monotonic: single > partially-hot > uniform")
    void skewIsMonotonic() {
        WorkloadMonitor hot = monitor();
        for (int i = 0; i < N; i++) hot.recordSearch(777, 6);

        WorkloadMonitor partial = monitor();
        java.util.Random rnd = new java.util.Random(1);
        for (int i = 0; i < N; i++) {
            if (rnd.nextDouble() < 0.8) partial.recordSearch(777, 6);
            else partial.recordSearch(rnd.nextInt(100_000), 11);
        }

        WorkloadMonitor uniform = monitor();
        for (int i = 0; i < N; i++) uniform.recordSearch(i, 10);

        double sHot = hot.snapshot().accessSkew();
        double sPartial = partial.snapshot().accessSkew();
        double sUniform = uniform.snapshot().accessSkew();
        assertTrue(sHot > sPartial && sPartial > sUniform,
                "expected hot > partial > uniform, got " + sHot + " > " + sPartial + " > " + sUniform);
        assertTrue(sPartial > 0.4 && sPartial < 0.85, "partial skew off range: " + sPartial);
    }

    @Test
    @DisplayName("two equally hot keys → moderate skew")
    void twoHotKeysModerateSkew() {
        WorkloadMonitor m = monitor();
        for (int i = 0; i < N; i++) m.recordSearch(i % 2, 5);
        double skew = m.snapshot().accessSkew();
        assertTrue(skew > 0.3 && skew < 0.7, "two-hot-key skew off range: " + skew);
    }

    // ── Op mix ───────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("search-only stream → readFraction ≈ 1")
    void allSearchesReadHeavy() {
        WorkloadMonitor m = monitor();
        for (int i = 0; i < N; i++) m.recordSearch(i, 8);
        WorkloadFeatures f = m.snapshot();
        assertTrue(f.readFraction() > 0.99, "readFraction=" + f.readFraction());
        assertTrue(f.writeFraction() < 0.01, "writeFraction=" + f.writeFraction());
    }

    @Test
    @DisplayName("add-only stream → writeFraction ≈ 1")
    void allAddsWriteHeavy() {
        WorkloadMonitor m = monitor();
        for (int i = 0; i < N; i++) m.recordAdd(i, 1);
        WorkloadFeatures f = m.snapshot();
        assertTrue(f.writeFraction() > 0.99, "writeFraction=" + f.writeFraction());
        assertTrue(f.readFraction() < 0.01, "readFraction=" + f.readFraction());
    }

    @Test
    @DisplayName("50/50 add+search → readFraction ≈ 0.5")
    void mixedOpMix() {
        WorkloadMonitor m = monitor();
        for (int i = 0; i < N; i++) {
            if ((i & 1) == 0) m.recordAdd(i, 1);
            else m.recordSearch(i, 9);
        }
        double read = m.snapshot().readFraction();
        assertTrue(read > 0.45 && read < 0.55, "readFraction should be ~0.5, was " + read);
    }

    // ── Size and growth ──────────────────────────────────────────────────────────

    @Test
    @DisplayName("size tracks effective adds minus removes")
    void sizeTracksMutations() {
        WorkloadMonitor m = monitor();
        for (int i = 0; i < 100; i++) m.recordAdd(i, 0);
        for (int i = 0; i < 30; i++) m.recordRemove(i, 0);
        assertEquals(70L, m.snapshot().size());
    }

    @Test
    @DisplayName("size never goes negative on over-removal")
    void sizeFloorsAtZero() {
        WorkloadMonitor m = monitor();
        for (int i = 0; i < 5; i++) m.recordAdd(i, 0);
        for (int i = 0; i < 50; i++) m.recordRemove(i, 0);
        assertEquals(0L, m.snapshot().size());
    }

    @Test
    @DisplayName("pure inserts → strongly positive growthRate")
    void growthPositiveUnderInserts() {
        WorkloadMonitor m = monitor();
        for (int i = 0; i < N; i++) m.recordAdd(i, 1);
        double growth = m.snapshot().growthRate();
        assertTrue(growth > 100.0, "expected growth ~W under pure inserts, was " + growth);
    }

    @Test
    @DisplayName("balanced add/remove → growthRate ≈ 0")
    void growthZeroWhenBalanced() {
        WorkloadMonitor m = monitor();
        for (int i = 0; i < N; i++) {
            if ((i & 1) == 0) m.recordAdd(i, 1);
            else m.recordRemove(i - 1, 1);
        }
        double growth = m.snapshot().growthRate();
        assertTrue(Math.abs(growth) < 10.0, "steady-state growth should be ~0, was " + growth);
    }

    // ── Depth and rotation EWMAs ─────────────────────────────────────────────────

    @Test
    @DisplayName("meanSearchDepth tracks the reported path length")
    void meanSearchDepthTracksInput() {
        WorkloadMonitor m = monitor();
        for (int i = 0; i < 2000; i++) m.recordSearch(i, 12);
        double depth = m.snapshot().meanSearchDepth();
        assertTrue(Math.abs(depth - 12.0) < 0.5, "meanSearchDepth=" + depth);
    }

    @Test
    @DisplayName("rotationsPerWrite tracks the reported rotations")
    void rotationsPerWriteTracksInput() {
        WorkloadMonitor m = monitor();
        for (int i = 0; i < 2000; i++) m.recordAdd(i, 2);
        double rot = m.snapshot().rotationsPerWrite();
        assertTrue(Math.abs(rot - 2.0) < 0.5, "rotationsPerWrite=" + rot);
    }

    // ── Contracts / edges ────────────────────────────────────────────────────────

    @Test
    @DisplayName("fresh monitor reports an all-zero vector")
    void emptyMonitorIsZero() {
        WorkloadFeatures f = monitor().snapshot();
        assertEquals(0.0, f.readFraction());
        assertEquals(0.0, f.writeFraction());
        assertEquals(0.0, f.accessSkew());
        assertEquals(0L, f.size());
        assertEquals(0.0, f.growthRate());
    }

    @Test
    @DisplayName("no-rotation overloads leave rotationsPerWrite at 0")
    void convenienceOverloadsDelegate() {
        WorkloadMonitor m = monitor();
        for (int i = 0; i < 500; i++) m.recordAdd(i);
        assertEquals(0.0, m.snapshot().rotationsPerWrite());
    }

    @Test
    @DisplayName("bounded under a flood of distinct keys (no per-op growth, skew stays low)")
    void boundedUnderManyDistinctKeys() {
        WorkloadMonitor m = monitor();
        for (int i = 0; i < 200_000; i++) m.recordSearch(i, 13);
        WorkloadFeatures f = m.snapshot();
        assertTrue(f.accessSkew() < 0.05, "distinct-key flood should stay unskewed: " + f.accessSkew());
        assertTrue(f.readFraction() > 0.99, "readFraction=" + f.readFraction());
    }
}
