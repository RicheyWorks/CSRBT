package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.control.CostModelStrategyScorer;
import io.github.richeyworks.csrbt.control.MorphController;
import io.github.richeyworks.csrbt.control.MorphPolicy;
import io.github.richeyworks.csrbt.control.RollingWorkloadMonitor;
import io.github.richeyworks.csrbt.control.StrategyId;
import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleMode;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.evolution.PolicyEvolutionController;
import io.github.richeyworks.csrbt.evolution.PolicyGenome;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.HybridStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

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
 * ADR-012 E3b — <b>the pre-registered discriminating schedule</b>. E3's verdict carried a
 * caveat: its schedule turned out AVL-dominated, so the adaptive premise (no single fixed
 * structure covers the run) was false there. This experiment closes that gap with a
 * registration protocol:
 *
 * <p><b>Registered before any adaptive contestant ran</b> (2026-06-10): the schedule
 * alternates ADR-011 V5's published <i>uniform</i> family (AVL's diet, per the V5 table)
 * and <i>sequential</i> family (Splay's diet) — generators verbatim from
 * {@code EvolutionAcceptanceExperimentTest}, sequential keyspace offset to 1e6, six
 * 6000-op blocks (u,s,u,s,u,s), seeds 11/2026/42. A fixed-strategies-only probe (allowed:
 * the discriminator is constructed from fixed costs, never from adaptive behavior)
 * confirmed non-dominance — block winners AVL×4 / SPLAY×2, best single fixed ≈ 17.3
 * cmp/op, per-block oracle ≈ 14.9, an oracle gap of ~13.7% — so the pre-registered
 * criterion is <em>reachable in principle</em> by a perfect switcher.
 * <b>Criterion (unchanged from E3):</b> an adaptive scheme (the ADR-002 selector, elite
 * evolution, or population evolution, configured exactly as in E3) beats the best single
 * fixed strategy by ≥10% integrated comparisons/op on all three seeds. Verdict published
 * either way; the adaptive contestants run once, below, after this paragraph was
 * written.</p>
 *
 * <p>House discipline: correctness hard (positive costs, full window series, ≥2 distinct
 * block winners — the registration's premise — and the adaptive contestants oracle-exact
 * on a 2k-key membership sample); the verdict is printed rows plus one
 * {@code event=adr012_e3b_verdict} line.</p>
 */
@DisplayName("ADR-012 E3b — the pre-registered discriminating schedule")
public class DiscriminatingScheduleExperimentTest {

    private static final int BLOCK_OPS = 6_000;
    private static final int BLOCKS = 6;                   // u,s,u,s,u,s
    private static final int WINDOW = 500;
    private static final int GEN_OPS = 1_500;
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

    /** The registered schedule: V5's uniform and sequential generators, alternating. */
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

    private static RunResult runEvolving(List<PolicyGenome> founders, int mu, int lambda,
                                         long seed, TreeSet<Integer> oracle) {
        long[] cmp = { 0L };
        Comparator<Integer> counting = (a, b) -> { cmp[0]++; return Integer.compare(a, b); };
        EnsembleOrderedSet.Builder<Integer> b = EnsembleOrderedSet.builder(counting)
                .member(() -> new RedBlackStrategy<Integer>());
        for (int i = 0; i < lambda; i++) b.member(() -> new RedBlackStrategy<Integer>());
        EnsembleOrderedSet<Integer> ens = b.mode(EnsembleMode.SAMPLED_SHADOW)
                .shadowSampleRate(0.25)
                .build();
        try {
            List<EnsembleMember<Integer>> nursery = ens.members().subList(1, 1 + lambda);
            PolicyEvolutionController<Integer> c = new PolicyEvolutionController<>(
                    ens, nursery, new RollingWorkloadMonitor(), MorphPolicy.defaults(),
                    founders, mu, false, seed);
            Ops sink = new Ops() {
                @Override public void add(int k)      { c.add(k); oracle.add(k); }
                @Override public void remove(int k)   { c.remove(k); oracle.remove(k); }
                @Override public void contains(int k) { c.contains(k); }
            };
            int[] opsInGen = { 0 };
            c.beginGeneration();
            RunResult r = drive(sink, cmp, seed, () -> {
                if (++opsInGen[0] == GEN_OPS) {
                    c.endGeneration(GEN_OPS);
                    c.beginGeneration();
                    opsInGen[0] = 0;
                }
            });
            c.endGeneration(opsInGen[0]);
            probeOracle(seed, oracle, ens::contains);
            return r;
        } finally {
            ens.close();
        }
    }

    private static RunResult runSelector(long seed, TreeSet<Integer> oracle) {
        long[] cmp = { 0L };
        Comparator<Integer> counting = (a, b) -> { cmp[0]++; return Integer.compare(a, b); };
        OrderedSet<Integer> set = new OrderedSet<>(new RedBlackStrategy<>(), counting);
        RollingWorkloadMonitor monitor = new RollingWorkloadMonitor();
        MorphController<Integer> mc = new MorphController<>(set, monitor,
                new CostModelStrategyScorer(), MorphPolicy.defaults());
        StrategyId[] current = { StrategyId.RED_BLACK };
        int[] sinceEval = { 0 };
        Ops sink = new Ops() {
            @Override public void add(int k) {
                if (set.add(k)) monitor.recordAdd(Integer.hashCode(k));
                oracle.add(k);
            }
            @Override public void remove(int k) {
                if (set.remove(k)) monitor.recordRemove(Integer.hashCode(k));
                oracle.remove(k);
            }
            @Override public void contains(int k) {
                set.contains(k);
                monitor.recordSearch(Integer.hashCode(k), 0);
            }
        };
        RunResult r = drive(sink, cmp, seed, () -> {
            if (++sinceEval[0] == 10) {
                MorphController.MorphResult res = mc.evaluateAndMaybeMorph(current[0], 10);
                if (res.morphed()) current[0] = res.to();
                sinceEval[0] = 0;
            }
        });
        probeOracle(seed, oracle, set::contains);
        return r;
    }

    @Test
    @DisplayName("registered schedule, eight contestants, oracle bound: the verdict")
    void theExperiment() {
        Map<String, Supplier<TreeStrategy<Integer>>> fixed = new LinkedHashMap<>();
        fixed.put("RB", RedBlackStrategy::new);
        fixed.put("AVL", AVLStrategy::new);
        fixed.put("SPLAY", SplayStrategy::new);
        fixed.put("HYBRID", HybridStrategy::new);

        System.out.println("=== ADR-012 E3b: the pre-registered discriminating schedule ===");
        System.out.println("schedule: uniform ↔ sequential (V5 generators), " + BLOCKS
                + " × " + BLOCK_OPS + " ops; criterion: >=10% vs best single fixed, all seeds");

        int sustainedWins = 0;
        for (long seed : SEEDS) {
            Map<String, RunResult> results = new LinkedHashMap<>();
            for (Map.Entry<String, Supplier<TreeStrategy<Integer>>> e : fixed.entrySet()) {
                results.put(e.getKey(), runFixed(e.getValue(), seed));
            }

            // The registration's premise, asserted: block winners are not one strategy.
            double oracle = 0;
            Set<String> blockWinners = new HashSet<>();
            StringBuilder winners = new StringBuilder();
            for (int bk = 0; bk < BLOCKS; bk++) {
                double best = Double.POSITIVE_INFINITY;
                String w = "?";
                for (String name : fixed.keySet()) {
                    double m = blockMean(results.get(name).windowCost(), bk);
                    if (m < best) { best = m; w = name; }
                }
                oracle += best;
                blockWinners.add(w);
                winners.append(' ').append(w);
            }
            oracle /= BLOCKS;
            assertTrue(blockWinners.size() >= 2,
                    "registration premise: no single fixed strategy may win every block");

            results.put("ELITE", runEvolving(
                    List.of(PolicyGenome.weightBalanced(3, 2), PolicyGenome.weightBalanced(4, 2)),
                    1, 2, seed, new TreeSet<>()));
            results.put("POP", runEvolving(
                    List.of(PolicyGenome.weightBalanced(3, 2), PolicyGenome.weightBalanced(4, 2),
                            PolicyGenome.weightBalanced(6, 1), PolicyGenome.weightBalanced(8, 7)),
                    2, 4, seed, new TreeSet<>()));
            results.put("SELECT", runSelector(seed, new TreeSet<>()));

            double bestFixedCost = Double.POSITIVE_INFINITY;
            String bestFixedName = "?";
            for (String name : fixed.keySet()) {
                double c = results.get(name).cmpPerOp();
                assertTrue(c > 0.0);
                if (c < bestFixedCost) { bestFixedCost = c; bestFixedName = name; }
            }
            double bestAdaptive = Math.min(results.get("SELECT").cmpPerOp(),
                    Math.min(results.get("ELITE").cmpPerOp(), results.get("POP").cmpPerOp()));
            double improvement = (bestFixedCost - bestAdaptive) / bestFixedCost;
            if (improvement >= SUCCESS_MARGIN) sustainedWins++;

            System.out.println("-- seed " + seed + " --");
            for (Map.Entry<String, RunResult> e : results.entrySet()) {
                assertEquals(WINDOWS, e.getValue().windowCost().length);
                StringBuilder blocks = new StringBuilder();
                for (int bk = 0; bk < BLOCKS; bk++) {
                    blocks.append(String.format(Locale.ROOT, " %6.2f",
                            blockMean(e.getValue().windowCost(), bk)));
                }
                System.out.println(String.format(Locale.ROOT,
                        "%-6s cmp/op=%7.2f | blocks:%s", e.getKey(),
                        e.getValue().cmpPerOp(), blocks));
            }
            System.out.println(String.format(Locale.ROOT,
                    "seed %d: bestFixed=%s (%.2f) oracle=%.2f (gap %.1f%%) winners:%s "
                    + "bestAdaptive=%.2f improvement=%+.1f%%",
                    seed, bestFixedName, bestFixedCost, oracle,
                    (bestFixedCost - oracle) / bestFixedCost * 100.0, winners,
                    bestAdaptive, improvement * 100.0));
        }

        boolean success = sustainedWins == SEEDS.length;
        System.out.println(String.format(Locale.ROOT,
                "event=adr012_e3b_verdict success=%s sustainedSeeds=%d/%d margin=%.0f%% "
                + "(pre-registered: discriminating schedule, oracle gap ~13.7%%, criterion "
                + "reachable in principle)",
                success, sustainedWins, SEEDS.length, SUCCESS_MARGIN * 100.0));
        // Printed, never hard-asserted (V5 discipline): either answer publishes. If the
        // verdict is no on a schedule where an oracle switcher clears the margin, the
        // failure is the contestants' (detection + morph costs), not the premise's —
        // and that distinction is the entire point of E3b.
    }
}
