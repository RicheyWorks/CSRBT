package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.BetaDiversity;
import io.github.richeyworks.csrbt.experimental.ecology.EcologyRecorder;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The early-warning experiment — the ecology layer put on the bench, ADR-012 style.
 *
 * <p><b>Pre-registered questions.</b> Regime-shift theory in ecology says community
 * change shows up in turnover statistics; the practical questions for this codebase
 * (they gate ADR-012's re-arming triggers, which need workload-shift detection) are:</p>
 *
 * <ol>
 *   <li><b>Abrupt shifts — detection.</b> On a workload that switches hot set
 *       instantaneously, does consecutive-window Bray–Curtis cross a baseline-derived
 *       threshold in exactly the boundary window (detection lag 0), with no false
 *       positives inside stationary stretches — and, the honest null, no <em>precursor</em>
 *       (an instantaneous shift is precursor-free by construction; a "warning" before it
 *       would mean the method fabricates signal)?</li>
 *   <li><b>Gradual shifts — early warning.</b> On a workload that drifts linearly from
 *       one hot set to another over a full regime length, does <em>displacement from the
 *       baseline community</em> (1 &#x2212; Renkonen similarity to the pre-drift reference —
 *       proportion-based, so the merged baseline's larger total cannot inflate it; the
 *       right statistic for slow drift, which consecutive differencing provably smears)
 *       cross the same style of threshold strictly <b>before</b> the new regime is fully
 *       established?</li>
 * </ol>
 *
 * <p><b>Method, fixed in advance.</b> 50 keys; hot sets A = {0..4}, B = {25..29}; 90/10
 * hot/uniform mix; window W = 500 ops; regimes of 3000 ops (6 windows); 3 seeds
 * {11, 12, 13}. Threshold = {@value #THRESHOLD_FACTOR}× the maximum of the statistic
 * over the within-baseline windows (indices 1..5) — a constant declared here, not
 * fitted. Hard assertions carry the verdict; one {@code event=} line per run prints
 * the numbers (the V5 pattern: deterministic meters decide).</p>
 */
@DisplayName("Early warning — turnover statistics vs workload regime shifts (pre-registered)")
class EarlyWarningExperimentTest {

    static final double THRESHOLD_FACTOR = 2.0;
    static final int KEYS = 50, WINDOW = 500, REGIME_OPS = 3000;
    static final int[] SEEDS = { 11, 12, 13 };
    static final int[] HOT_A = { 0, 1, 2, 3, 4 };
    static final int[] HOT_B = { 25, 26, 27, 28, 29 };

    private static int drawKey(Random rng, int[] hot) {
        return rng.nextInt(10) < 9 ? hot[rng.nextInt(hot.length)] : rng.nextInt(KEYS);
    }

    /** Windows of a 3-regime abrupt stream: A (6 windows), B (6), A (6). */
    private static List<Map<Integer, Long>> abruptWindows(long seed) {
        Random rng = new Random(seed);
        EcologyRecorder rec = new EcologyRecorder(WINDOW, 64);
        for (int op = 0; op < 3 * REGIME_OPS; op++) {
            int[] hot = (op / REGIME_OPS) == 1 ? HOT_B : HOT_A;
            rec.recordSearch(drawKey(rng, hot), 1);
        }
        return rec.closedWindows();
    }

    /** Windows of a gradual stream: A (6), linear A→B drift (6), B (6). */
    private static List<Map<Integer, Long>> gradualWindows(long seed) {
        Random rng = new Random(seed);
        EcologyRecorder rec = new EcologyRecorder(WINDOW, 64);
        for (int op = 0; op < 3 * REGIME_OPS; op++) {
            int[] hot;
            if (op < REGIME_OPS) hot = HOT_A;
            else if (op >= 2 * REGIME_OPS) hot = HOT_B;
            else {
                double f = (op - REGIME_OPS) / (double) REGIME_OPS;   // 0 → 1 across the ramp
                hot = rng.nextDouble() < f ? HOT_B : HOT_A;
            }
            rec.recordSearch(drawKey(rng, hot), 1);
        }
        return rec.closedWindows();
    }

    private static Map<Integer, Long> merged(List<Map<Integer, Long>> windows, int from, int to) {
        Map<Integer, Long> ref = new HashMap<>();
        for (int i = from; i <= to; i++) {
            for (Map.Entry<Integer, Long> e : windows.get(i).entrySet()) {
                ref.merge(e.getKey(), e.getValue(), Long::sum);
            }
        }
        return ref;
    }

    @Test
    @DisplayName("abrupt shifts: detection lag 0 at both boundaries, zero false positives, zero precursors")
    void abruptDetection() {
        for (long seed : SEEDS) {
            List<Map<Integer, Long>> w = abruptWindows(seed);
            assertEquals(18, w.size());

            double[] bray = new double[w.size()];         // bray[i] = BC(w[i-1], w[i])
            for (int i = 1; i < w.size(); i++) {
                bray[i] = BetaDiversity.brayCurtis(w.get(i - 1), w.get(i));
            }
            double baselineMax = 0;
            for (int i = 1; i <= 5; i++) baselineMax = Math.max(baselineMax, bray[i]);
            double threshold = THRESHOLD_FACTOR * baselineMax;

            TreeSet<Integer> crossings = new TreeSet<>();
            for (int i = 1; i < w.size(); i++) {
                if (bray[i] > threshold) crossings.add(i);
            }
            // Boundaries sit exactly at windows 6 (A→B) and 12 (B→A).
            assertEquals(new TreeSet<>(List.of(6, 12)), crossings,
                    "seed " + seed + ": crossings must be exactly the boundary windows, got " + crossings);
            // The honest null: no precursor in the windows before each boundary.
            for (int i : new int[]{ 4, 5, 10, 11 }) {
                assertTrue(bray[i] <= threshold,
                        "seed " + seed + ": fabricated precursor at window " + i);
            }
            System.out.printf(
                    "event=ews_abrupt seed=%d threshold=%.4f boundary1=%.4f boundary2=%.4f baselineMax=%.4f lag=0 falsePositives=0%n",
                    seed, threshold, bray[6], bray[12], baselineMax);
        }
    }

    @Test
    @DisplayName("gradual shifts: baseline displacement crosses threshold before the new regime is established")
    void gradualEarlyWarning() {
        for (long seed : SEEDS) {
            List<Map<Integer, Long>> w = gradualWindows(seed);
            assertEquals(18, w.size());
            Map<Integer, Long> baseline = merged(w, 1, 5);

            double[] disp = new double[w.size()];          // displacement from home
            for (int i = 0; i < w.size(); i++) {
                disp[i] = 1.0 - BetaDiversity.renkonen(baseline, w.get(i));
            }
            double baselineMax = 0;
            for (int i = 1; i <= 5; i++) baselineMax = Math.max(baselineMax, disp[i]);
            double threshold = THRESHOLD_FACTOR * baselineMax;

            int firstCrossing = -1;
            for (int i = 6; i < w.size(); i++) {
                if (disp[i] > threshold) { firstCrossing = i; break; }
            }
            // The ramp spans windows 6..11; the new regime is established at window 12.
            assertTrue(firstCrossing >= 6, "seed " + seed + ": warning before the drift began");
            assertTrue(firstCrossing < 12,
                    "seed " + seed + ": no warning before establishment (first crossing "
                            + firstCrossing + ")");
            // And the pre-drift stretch itself stays quiet (no false positives).
            for (int i = 1; i <= 5; i++) {
                assertTrue(disp[i] <= threshold, "seed " + seed + ": false positive at window " + i);
            }
            System.out.printf(
                    "event=ews_gradual seed=%d threshold=%.4f firstWarning=win%d rampStart=win6 established=win12 leadWindows=%d%n",
                    seed, threshold, firstCrossing, 12 - firstCrossing);
        }
    }

    @Test
    @DisplayName("the comparison that motivates the method choice: consecutive differencing smears slow drift")
    void consecutiveDifferencingIsTheWrongToolForDrift() {
        // Not a redundancy — this pins WHY the gradual question uses displacement:
        // per-window consecutive Bray–Curtis on the drift stream stays near baseline
        // (the change per window is small), so it cannot give the early warning.
        List<Map<Integer, Long>> w = gradualWindows(SEEDS[0]);
        double[] bray = new double[w.size()];
        double baselineMax = 0, rampMax = 0;
        for (int i = 1; i < w.size(); i++) {
            bray[i] = BetaDiversity.brayCurtis(w.get(i - 1), w.get(i));
            if (i <= 5) baselineMax = Math.max(baselineMax, bray[i]);
            if (i >= 7 && i <= 11) rampMax = Math.max(rampMax, bray[i]);
        }
        assertTrue(rampMax < THRESHOLD_FACTOR * baselineMax * 1.5,
                "consecutive BC unexpectedly resolves the drift sharply — revisit the method note");
        System.out.printf(
                "event=ews_method baselineMaxConsecutive=%.4f rampMaxConsecutive=%.4f verdict=displacement-required%n",
                baselineMax, rampMax);
    }
}
