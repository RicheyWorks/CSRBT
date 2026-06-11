package test.core;

import core.OrderedSet;
import core.ensemble.EnsembleMember;
import core.ensemble.EnsembleMode;
import core.ensemble.EnsembleOrderedSet;
import core.strategy.AVLStrategy;
import core.strategy.HybridStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;
import core.strategy.TreeStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.TreeSet;
import java.util.function.Supplier;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-012 E3c — <b>the price of switching: is the oracle gap claimable at all?</b>
 *
 * <p>The calibration slice left one residue, named and held: on E3b's registered schedule
 * the selector ties hindsight-best AVL but leaves the ~13% oracle gap on the table — the
 * oracle rides Splay through the sequential blocks. The held fix was a <em>perception</em>
 * upgrade (a recency-aware locality feature). This experiment asks the question that must
 * come first (instruments before mechanisms): E3b's oracle switches strategies <b>for
 * free</b>, and no real architecture can. What does the gap look like after the switcher
 * pays its <em>actual</em> switching bill at the comparator seam?</p>
 *
 * <p><b>Registered before either contestant ran (2026-06-11):</b> the schedule, seeds,
 * meter, and fixed-probe machinery are E3b's verbatim ({@code
 * DiscriminatingScheduleExperimentTest}). Two <em>clairvoyant</em> contestants — both are
 * given the per-block winners table outright (an upper bound on any detector, so the
 * verdict can only be too generous to perception):</p>
 * <ul>
 *   <li><b>CV-MORPH</b> — one {@code OrderedSet}; at each block boundary it morphs to the
 *       coming block's winner via {@code setStrategy} (the real health-gated O(n)
 *       build-aside, every comparison counted).</li>
 *   <li><b>CV-PROMOTE</b> — a MIRROR ensemble with one exact member per distinct block
 *       winner; at each boundary it promotes the winner (the real O(1) swap), paying the
 *       standing K× write fan-out instead of rebuilds.</li>
 * </ul>
 *
 * <p><b>Criterion (E3b's, unchanged):</b> the gap is <em>claimable</em> iff a clairvoyant
 * beats the best single fixed strategy by ≥10% integrated comparisons/op on all three
 * seeds. If even clairvoyance cannot clear the bar, no detector can, and the held
 * recency-feature item is <b>retired with receipts</b>: the calibrated selector's hold on
 * AVL was the economically correct decision, not a perception failure. Verdict published
 * either way.</p>
 *
 * <p>House discipline: correctness hard (positive costs, full window series, ≥2 distinct
 * block winners, both clairvoyants oracle-exact on a 2k-key membership sample, CV-MORPH
 * actually switched); the verdict is printed rows plus one {@code event=adr012_e3c_verdict}
 * line.</p>
 */
@DisplayName("ADR-012 E3c — the price of switching (clairvoyant contestants)")
public class SwitchingCostExperimentTest {

    private static final int BLOCK_OPS = 6_000;
    private static final int BLOCKS = 6;                   // u,s,u,s,u,s — E3b verbatim
    private static final int WINDOW = 500;
    private static final long[] SEEDS = { 11L, 2026L, 42L };
    private static final double SUCCESS_MARGIN = 0.10;
    private static final int TOTAL_OPS = BLOCK_OPS * BLOCKS;
    private static final int WINDOWS = TOTAL_OPS / WINDOW;
    private static final int WINDOWS_PER_BLOCK = BLOCK_OPS / WINDOW;
    private static final int SEQ_BASE = 1_000_000;

    private interface Ops {
        void add(int k);
        void remove(int k);
        void contains(int k);
    }

    /** The registered schedule — generators verbatim from E3b (which took them from V5). */
    private static final class Schedule {
        private final Random uni;
        private final Random sq;
        private int seq;

        Schedule(long seed) {
            this.uni = new Random(seed);
            this.sq = new Random(seed * 7 + 13);
        }

        void step(Ops t, int block) {
            if (block % 2 == 0) {                          // V5 "uniform" — AVL's diet
                int r = uni.nextInt(100);
                int k = uni.nextInt(20_000);
                if (r < 30) t.add(k); else if (r < 45) t.remove(k); else t.contains(k);
            } else {                                       // V5 "sequential" — Splay's diet
                int r = sq.nextInt(100);
                if (r < 40 || seq == 0) t.add(SEQ_BASE + seq++);
                else if (r < 50 && seq > 2_000) t.remove(SEQ_BASE + sq.nextInt(seq - 2_000));
                else t.contains(SEQ_BASE + seq - 1 - sq.nextInt(Math.min(64, seq)));
            }
        }
    }

    private record RunResult(double cmpPerOp, double[] windowCost) { }

    private static RunResult drive(Ops sink, long[] cmp, long seed, Runnable perOpCadence) {
        Schedule s = new Schedule(seed);
        double[] windows = new double[WINDOWS];
        long last = cmp[0];
        int w = 0;
        for (int op = 0; op < TOTAL_OPS; op++) {
            s.step(sink, op / BLOCK_OPS);
            if (perOpCadence != null) perOpCadence.run();
            if ((op + 1) % WINDOW == 0) {
                windows[w++] = (cmp[0] - last) / (double) WINDOW;
                last = cmp[0];
            }
        }
        return new RunResult(cmp[0] / (double) TOTAL_OPS, windows);
    }

    private static double blockMean(double[] windows, int block) {
        double m = 0;
        for (int i = block * WINDOWS_PER_BLOCK; i < (block + 1) * WINDOWS_PER_BLOCK; i++) m += windows[i];
        return m / WINDOWS_PER_BLOCK;
    }

    private static RunResult runFixed(Supplier<TreeStrategy<Integer>> strategy, long seed) {
        long[] cmp = { 0L };
        Comparator<Integer> counting = (a, b) -> { cmp[0]++; return Integer.compare(a, b); };
        OrderedSet<Integer> set = new OrderedSet<>(strategy.get(), counting);
        Ops sink = new Ops() {
            @Override public void add(int k)      { set.add(k); }
            @Override public void remove(int k)   { set.remove(k); }
            @Override public void contains(int k) { set.contains(k); }
        };
        return drive(sink, cmp, seed, null);
    }

    private static void probeOracle(long seed, TreeSet<Integer> oracle,
                                    java.util.function.IntPredicate contains) {
        Random probe = new Random(seed ^ 0x5EEDL);
        for (int i = 0; i < 1_000; i++) {
            int k = probe.nextInt(20_000);
            assertEquals(oracle.contains(k), contains.test(k), "diverged at key " + k);
        }
        for (int i = 0; i < 1_000; i++) {
            int k = SEQ_BASE + probe.nextInt(40_000);
            assertEquals(oracle.contains(k), contains.test(k), "diverged at key " + k);
        }
    }

    /** CV-MORPH: starts on block 0's winner, morphs (real build-aside) at each boundary. */
    private static RunResult runClairvoyantMorph(String[] blockWinner,
                                                 Map<String, Supplier<TreeStrategy<Integer>>> strategies,
                                                 long seed, TreeSet<Integer> oracle, int[] morphsOut) {
        long[] cmp = { 0L };
        Comparator<Integer> counting = (a, b) -> { cmp[0]++; return Integer.compare(a, b); };
        OrderedSet<Integer> set = new OrderedSet<>(strategies.get(blockWinner[0]).get(), counting);
        Ops sink = new Ops() {
            @Override public void add(int k)      { set.add(k); oracle.add(k); }
            @Override public void remove(int k)   { set.remove(k); oracle.remove(k); }
            @Override public void contains(int k) { set.contains(k); }
        };
        int[] opsDone = { 0 };
        RunResult r = drive(sink, cmp, seed, () -> {
            if (++opsDone[0] % BLOCK_OPS == 0 && opsDone[0] < TOTAL_OPS) {
                int next = opsDone[0] / BLOCK_OPS;
                if (!blockWinner[next].equals(blockWinner[next - 1])) {
                    boolean ok = set.setStrategy(strategies.get(blockWinner[next]).get());
                    assertTrue(ok, "clairvoyant morph to " + blockWinner[next] + " must pass the health gate");
                    morphsOut[0]++;
                }
            }
        });
        probeOracle(seed, oracle, set::contains);
        return r;
    }

    /** CV-PROMOTE: MIRROR ensemble, one exact member per distinct winner, O(1) promote. */
    private static RunResult runClairvoyantPromote(String[] blockWinner,
                                                   Map<String, Supplier<TreeStrategy<Integer>>> strategies,
                                                   long seed, TreeSet<Integer> oracle) {
        long[] cmp = { 0L };
        Comparator<Integer> counting = (a, b) -> { cmp[0]++; return Integer.compare(a, b); };

        List<String> distinct = new ArrayList<>(new java.util.LinkedHashSet<>(List.of(blockWinner)));
        EnsembleOrderedSet.Builder<Integer> b = EnsembleOrderedSet.builder(counting);
        for (String name : distinct) b.member(() -> strategies.get(name).get());
        EnsembleOrderedSet<Integer> ens = b.mode(EnsembleMode.MIRROR).build();
        try {
            Map<String, EnsembleMember<Integer>> byName = new LinkedHashMap<>();
            for (int i = 0; i < distinct.size(); i++) byName.put(distinct.get(i), ens.members().get(i));

            ens.promote(byName.get(blockWinner[0]));
            Ops sink = new Ops() {
                @Override public void add(int k)      { ens.add(k); oracle.add(k); }
                @Override public void remove(int k)   { ens.remove(k); oracle.remove(k); }
                @Override public void contains(int k) { ens.contains(k); }
            };
            int[] opsDone = { 0 };
            RunResult r = drive(sink, cmp, seed, () -> {
                if (++opsDone[0] % BLOCK_OPS == 0 && opsDone[0] < TOTAL_OPS) {
                    ens.promote(byName.get(blockWinner[opsDone[0] / BLOCK_OPS]));
                }
            });
            probeOracle(seed, oracle, ens::contains);
            return r;
        } finally {
            ens.close();
        }
    }

    @Test
    @DisplayName("registered schedule, clairvoyant switchers, real switching costs: the verdict")
    void theExperiment() {
        Map<String, Supplier<TreeStrategy<Integer>>> fixed = new LinkedHashMap<>();
        fixed.put("RB", RedBlackStrategy::new);
        fixed.put("AVL", AVLStrategy::new);
        fixed.put("SPLAY", SplayStrategy::new);
        fixed.put("HYBRID", HybridStrategy::new);

        System.out.println("=== ADR-012 E3c: the price of switching ===");
        System.out.println("schedule: E3b verbatim; contestants are CLAIRVOYANT (winners table given);"
                + " criterion: >=10% vs best single fixed, all seeds");

        int claimableSeeds = 0;
        for (long seed : SEEDS) {
            Map<String, RunResult> results = new LinkedHashMap<>();
            for (Map.Entry<String, Supplier<TreeStrategy<Integer>>> e : fixed.entrySet()) {
                results.put(e.getKey(), runFixed(e.getValue(), seed));
            }

            // Per-block winners + free-switching oracle, exactly as E3b computed them.
            double oracle = 0;
            String[] blockWinner = new String[BLOCKS];
            Set<String> distinctWinners = new HashSet<>();
            for (int bk = 0; bk < BLOCKS; bk++) {
                double best = Double.POSITIVE_INFINITY;
                for (String name : fixed.keySet()) {
                    double m = blockMean(results.get(name).windowCost(), bk);
                    if (m < best) { best = m; blockWinner[bk] = name; }
                }
                oracle += best;
                distinctWinners.add(blockWinner[bk]);
            }
            oracle /= BLOCKS;
            assertTrue(distinctWinners.size() >= 2,
                    "premise: no single fixed strategy may win every block");

            int[] morphs = { 0 };
            results.put("CV-MORPH", runClairvoyantMorph(blockWinner, fixed, seed, new TreeSet<>(), morphs));
            assertTrue(morphs[0] >= 1, "the clairvoyant must have actually switched");
            results.put("CV-PROM", runClairvoyantPromote(blockWinner, fixed, seed, new TreeSet<>()));

            double bestFixedCost = Double.POSITIVE_INFINITY;
            String bestFixedName = "?";
            for (String name : fixed.keySet()) {
                double c = results.get(name).cmpPerOp();
                assertTrue(c > 0.0);
                if (c < bestFixedCost) { bestFixedCost = c; bestFixedName = name; }
            }
            double bestCv = Math.min(results.get("CV-MORPH").cmpPerOp(), results.get("CV-PROM").cmpPerOp());
            double improvement = (bestFixedCost - bestCv) / bestFixedCost;
            if (improvement >= SUCCESS_MARGIN) claimableSeeds++;

            System.out.println("-- seed " + seed + " --");
            for (Map.Entry<String, RunResult> e : results.entrySet()) {
                assertEquals(WINDOWS, e.getValue().windowCost().length);
                StringBuilder blocks = new StringBuilder();
                for (int bk = 0; bk < BLOCKS; bk++) {
                    blocks.append(String.format(Locale.ROOT, " %6.2f",
                            blockMean(e.getValue().windowCost(), bk)));
                }
                System.out.println(String.format(Locale.ROOT,
                        "%-8s cmp/op=%7.2f | blocks:%s", e.getKey(),
                        e.getValue().cmpPerOp(), blocks));
            }
            System.out.println(String.format(Locale.ROOT,
                    "seed %d: bestFixed=%s (%.2f) freeOracle=%.2f cvMorph=%.2f (%d morphs) "
                    + "cvPromote=%.2f improvement=%+.1f%%",
                    seed, bestFixedName, bestFixedCost, oracle,
                    results.get("CV-MORPH").cmpPerOp(), morphs[0],
                    results.get("CV-PROM").cmpPerOp(), improvement * 100.0));
        }

        boolean claimable = claimableSeeds == SEEDS.length;
        System.out.println(String.format(Locale.ROOT,
                "event=adr012_e3c_verdict claimable=%s claimableSeeds=%d/%d margin=%.0f%% "
                + "(clairvoyant switchers, real costs at the comparator seam; if clairvoyance "
                + "cannot clear the bar, no detector can)",
                claimable, claimableSeeds, SEEDS.length, SUCCESS_MARGIN * 100.0));
        // Printed, never hard-asserted (V5 discipline): either answer publishes. claimable=false
        // retires the held recency-feature item — the selector's hold was correct economics —
        // and re-prices E3b's "oracle gap" as a free-switching fiction at this block length.
    }
}
