package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.experimental.ecology.BetaDiversity;
import io.github.richeyworks.csrbt.experimental.ecology.CommunityMetrics;
import io.github.richeyworks.csrbt.experimental.ecology.EcologyRecorder;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Random;
import java.util.function.Supplier;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-018 — the amortization frontier: perception meets economics.
 *
 * <p><b>Context.</b> E3c (ADR-012) proved switching cannot pay at 6k-op regime blocks —
 * the switching quantum exceeded the whole prize threefold — and its re-arming trigger
 * #1 asked for "a real workload with regime blocks long enough that the switching
 * quantum amortizes." E3b separately showed the old selector's <em>perception</em>
 * failed (it never morphed through a 36% opportunity). The early-warning experiment
 * fixed perception: lag-0 detection, zero false positives. This experiment closes the
 * loop — with perception solved, <b>at what block length do the economics turn?</b></p>
 *
 * <p><b>Pre-registered method.</b> 2000 keys (multiples of 3), ascending build
 * (uncounted). Two read regimes, alternating in blocks of B ops: <em>uniform scan</em>
 * (keys drawn over the full range including in-range misses) and <em>hot-small-key</em>
 * (90/10 on the 5 smallest keys). The comparator seam is the meter (V5's metric).
 * Premise (hard-asserted first, E3b-style): the best strategy <em>flips</em> between
 * regimes — ascending-built Red-Black holds the smallest keys shallow and wins the hot
 * regime; AVL's uniform depth wins the scan. Honesty note: the RB hot advantage is a
 * property of the ascending-rebuild shape ({@code setStrategy} rebuilds by ascending
 * insertion, reproducing it deterministically), not RB superiority in general.</p>
 *
 * <p>Contestants on identical seeded streams: FIXED-AVL, FIXED-RB, and the
 * <b>EWS-morpher</b> — perception entirely from the ecology layer (window Bray–Curtis
 * &gt; {@value #DETECT_BC} detects the shift; window evenness J&#x2032; &lt; {@value #HOT_EVENNESS}
 * classifies the regime), acting through the live morph seam ({@code setStrategy},
 * whose full rebuild-and-validate bill lands on the meter). Block lengths swept
 * {2k, 8k, 32k, 128k, 256k}; 3 seeds; 6 blocks per run.</p>
 *
 * <p><b>Verdict (2026-08-09, pinned below as regression):</b> the frontier is real and
 * monotone — integrated-cost ratio vs best fixed &#x2248; 2.24 &#x2192; 1.30 &#x2192; 1.06 &#x2192; 1.00 &#x2192;
 * <b>0.99</b> across the sweep. Perception is no longer the bottleneck (5/5 shifts
 * detected and correctly classified at every block length); the rebuild bill is.
 * Break-even sits at <b>B* &#x2248; 128k ops</b> — E3c's negative stands at short blocks
 * (ratio &gt; 1.2 at 2k) and its re-arming trigger #1 now has its number: regime blocks
 * of order 10&#x2075; ops make switching pay.</p>
 */
@DisplayName("ADR-018 — the amortization frontier: EWS-triggered morphing vs best fixed")
class AmortizationFrontierTest {

    static final int KEYS = 2000, WINDOW = 500, BLOCKS = 6;
    static final long[] SEEDS = { 21, 22, 23 };
    static final int[] BLOCK_LENGTHS = { 2_000, 8_000, 32_000, 128_000, 256_000 };
    static final double DETECT_BC = 0.5;      // hot↔uniform windows measure ~0.8; within-regime ~0.15
    static final double HOT_EVENNESS = 0.75;  // hot windows ~0.5, uniform ~0.99

    /** The meter: every comparison the engine makes, counted at the seam. */
    private static final class Meter implements Comparator<Integer> {
        long cmps = 0;
        @Override public int compare(Integer a, Integer b) { cmps++; return Integer.compare(a, b); }
    }

    private static int[] stream(long seed, int blockOps) {
        Random rng = new Random(seed);
        int[] ops = new int[blockOps * BLOCKS];
        int i = 0;
        for (int b = 0; b < BLOCKS; b++) {
            boolean hot = (b % 2 == 1);                       // uniform first, then alternating
            for (int j = 0; j < blockOps; j++, i++) {
                ops[i] = hot
                        ? (rng.nextInt(10) < 9 ? rng.nextInt(5) * 3 : rng.nextInt(KEYS) * 3)
                        : rng.nextInt(KEYS * 3);              // uniform incl. in-range misses
            }
        }
        return ops;
    }

    private static OrderedSet<Integer> build(TreeStrategy<Integer> s, Meter meter) {
        OrderedSet<Integer> set = new OrderedSet<>(s, meter);
        for (int k = 0; k < KEYS; k++) set.add(k * 3);        // ascending build
        return set;
    }

    private static long fixedCost(Supplier<TreeStrategy<Integer>> s, int[] ops) {
        Meter meter = new Meter();
        OrderedSet<Integer> set = build(s.get(), meter);
        meter.cmps = 0;                                       // build is uncounted, all contestants alike
        for (int k : ops) set.contains(k);
        return meter.cmps;
    }

    /** The EWS-morpher: ecology-layer perception, live morph seam, full bill on the meter. */
    private static long[] switcherCost(int[] ops) {           // {cmps, morphs}
        Meter meter = new Meter();
        OrderedSet<Integer> set = build(new AVLStrategy<>(), meter);
        EcologyRecorder rec = new EcologyRecorder(WINDOW, 4);
        meter.cmps = 0;
        long morphs = 0, windowsSeen = 0;
        Map<Integer, Long> prev = null;
        boolean rbNow = false;
        for (int k : ops) {
            set.contains(k);
            rec.recordSearch(k, 1);
            long closedCount = rec.opCount() / WINDOW;
            if (closedCount > windowsSeen) {                  // a window just closed
                windowsSeen = closedCount;
                List<Map<Integer, Long>> closed = rec.closedWindows();
                Map<Integer, Long> win = closed.get(closed.size() - 1);
                if (prev != null && BetaDiversity.brayCurtis(prev, win) > DETECT_BC) {
                    boolean wantRb = CommunityMetrics.pielouEvenness(win) < HOT_EVENNESS;
                    if (wantRb != rbNow) {
                        set.setStrategy(wantRb ? new RedBlackStrategy<>() : new AVLStrategy<>());
                        rbNow = wantRb;                       // rebuild + gate bill just hit the meter
                        morphs++;
                    }
                }
                prev = win;
            }
        }
        return new long[]{ meter.cmps, morphs };
    }

    // ── Premise (hard-asserted before the race means anything) ────────────────

    @Test
    @DisplayName("premise: the best strategy flips between regimes on the comparator meter")
    void premiseGapFlips() {
        for (long seed : SEEDS) {
            int[] hotOps = new int[6000], uniOps = new int[6000];
            Random rng = new Random(seed);
            for (int i = 0; i < 6000; i++) {
                hotOps[i] = rng.nextInt(10) < 9 ? rng.nextInt(5) * 3 : rng.nextInt(KEYS) * 3;
                uniOps[i] = rng.nextInt(KEYS * 3);
            }
            long rbHot  = fixedCost(RedBlackStrategy::new, hotOps);
            long avlHot = fixedCost(AVLStrategy::new, hotOps);
            long rbUni  = fixedCost(RedBlackStrategy::new, uniOps);
            long avlUni = fixedCost(AVLStrategy::new, uniOps);
            assertTrue(rbHot < avlHot,
                    "seed " + seed + ": ascending-built RB must win the hot-small-key regime");
            assertTrue(avlUni < rbUni,
                    "seed " + seed + ": AVL must win the uniform scan");
        }
    }

    // ── The frontier ──────────────────────────────────────────────────────────

    @Test
    @DisplayName("the frontier: monotone toward break-even; >1.2 at 2k (E3c stands); <1.0 at 256k (the crossing)")
    void frontier() {
        double prevRatio = Double.MAX_VALUE;
        for (int blockOps : BLOCK_LENGTHS) {
            double fixedAvl = 0, fixedRb = 0, switcher = 0;
            long morphs = 0;
            for (long seed : SEEDS) {
                int[] ops = stream(seed, blockOps);
                fixedAvl += fixedCost(AVLStrategy::new, ops);
                fixedRb  += fixedCost(RedBlackStrategy::new, ops);
                long[] s = switcherCost(ops);
                switcher += s[0];
                morphs += s[1];
            }
            double bestFixed = Math.min(fixedAvl, fixedRb);
            double ratio = switcher / bestFixed;
            double perOp = switcher / (3.0 * blockOps * BLOCKS);

            // Perception mechanics: every regime change after the first block is caught,
            // exactly once, at every block length — no misses, no morph storms.
            assertEquals(5L * SEEDS.length, morphs,
                    "B=" + blockOps + ": expected one morph per regime change");
            // The frontier is monotone (small tolerance for seed noise).
            assertTrue(ratio <= prevRatio + 0.02,
                    "B=" + blockOps + ": ratio " + ratio + " rose above " + prevRatio);
            prevRatio = ratio;

            if (blockOps == 2_000) {
                assertTrue(ratio > 1.2,
                        "at 2k blocks switching must still lose clearly (E3c stands): " + ratio);
            }
            if (blockOps == 256_000) {
                assertTrue(ratio < 1.0,
                        "at 256k blocks the crossing must hold: " + ratio);
            }
            System.out.printf(Locale.ROOT,
                    "event=adr018_frontier B=%d switcher=%.3f cmp/op ratioVsBestFixed=%.4f morphsPerRun=%.1f%n",
                    blockOps, perOp, ratio, morphs / (double) SEEDS.length);
        }
    }
}
