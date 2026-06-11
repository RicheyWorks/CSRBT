package test.core;

import core.OrderedSet;
import core.control.CostModelStrategyScorer;
import core.control.MorphController;
import core.control.MorphPolicy;
import core.control.RollingWorkloadMonitor;
import core.control.StrategyId;
import core.ensemble.EnsembleMember;
import core.ensemble.EnsembleMode;
import core.ensemble.EnsembleOrderedSet;
import core.evolution.PolicyEvolutionController;
import core.evolution.PolicyGenome;
import core.strategy.AVLStrategy;
import core.strategy.HybridStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;
import core.strategy.TreeStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Random;
import java.util.TreeSet;
import java.util.function.Supplier;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-012 E3 — <b>the non-stationary harness</b>: the axis V5 skipped. One long run whose
 * workload shifts regime on a fixed schedule (hot-read → write-heavy → sequential-append →
 * delete-churn, twice around), served by eight contestants on byte-identical streams: the
 * four fixed strategies as plain sets, and two live evolution controllers — <b>elite</b>
 * (μ=1, sliver founders: E2's converged population) and <b>population</b> (μ=2, diverse
 * founders) — adapting <em>during</em> the run, generations caller-cadenced, promotions
 * through the morph gates, nothing pre-searched — plus <b>the ADR-002 selector</b>
 * (monitor → scorer → policy → health-gated morph among the fixed four, evaluated every
 * 10 ops like production): the contestant the first E3 run documented as missing, and
 * the place V5 said the adaptive claim lives. The selector pays per <em>morph</em> — an
 * O(n) rebuild only when the gates clear — not per generation.
 *
 * <p><b>Cost is honest about exploration.</b> Realized cost = comparisons/op at the
 * comparator seam (the V5 meter: deterministic, byte-identical across runs). For the
 * adaptive contestants the counting comparator is the <em>ensemble's</em>, so integrated
 * cost includes the nursery: shadows at {@code shadowSampleRate=0.25} are real work, and
 * "does adaptation pay?" is only answerable when exploration is on the bill. The fixed
 * four pay zero exploration — that asymmetry is the experiment, not a bug in it.</p>
 *
 * <p><b>Re-adaptation lag</b> (per regime shift): windowed cost (500-op windows); a block's
 * steady state = mean of its last 3 windows; lag = ops from the shift until the windowed
 * cost first enters 1.10× steady state. Mean over the 7 shifts is the contestant's lag.</p>
 *
 * <p>House discipline, V5 verbatim: hard assertions are correctness (positive costs, full
 * window series, adaptive contestants answer a 2k-key membership sample oracle-exactly at
 * the end); the verdict — <i>does any adaptive scheme beat the best fixed strategy by
 * ≥10% integrated cost, sustained across all 3 seeds?</i> — is printed rows plus one
 * {@code event=adr012_e3_verdict} line, published either way.</p>
 */
@DisplayName("ADR-012 E3 — the non-stationary experiment (regime shifts, live adaptation)")
public class NonStationaryExperimentTest {

    private static final String[] REGIMES = { "hot-read", "uni-write", "seq-append", "churn" };
    private static final int BLOCK_OPS = 6_000;
    private static final int CYCLES = 2;                  // 8 blocks, 7 shifts, 48k ops
    private static final int WINDOW = 500;
    private static final int GEN_OPS = 1_500;             // caller cadence for the controllers
    private static final long[] SEEDS = { 11L, 2026L, 42L };
    private static final double SUCCESS_MARGIN = 0.10;
    private static final double LAG_BAND = 1.10;

    private interface Ops {
        void add(int k);
        void remove(int k);
        void contains(int k);
    }

    /** The schedule: deterministic per seed, regime = block index mod 4, shared key universe. */
    private static final class RegimeStream {
        private final Random rnd;
        private final int hotBase;
        private int seq;

        RegimeStream(long seed) {
            this.rnd = new Random(seed);
            this.hotBase = rnd.nextInt(10_000);
        }

        void step(Ops t, int block) {
            int r = rnd.nextInt(100);
            switch (REGIMES[block % REGIMES.length]) {
                case "hot-read" -> {                       // splay's diet: 85% reads on 200 keys
                    int k = rnd.nextInt(100) < 90 ? hotBase + rnd.nextInt(200) : rnd.nextInt(20_000);
                    if (r < 10) t.add(k); else if (r < 15) t.remove(k); else t.contains(k);
                }
                case "uni-write" -> {                      // write-heavy, no locality
                    int k = rnd.nextInt(20_000);
                    if (r < 50) t.add(k); else if (r < 90) t.remove(k); else t.contains(k);
                }
                case "seq-append" -> {                     // log-append, recent reads
                    if (r < 45 || seq == 0) t.add(20_000 + seq++);
                    else t.contains(20_000 + seq - 1 - rnd.nextInt(Math.min(64, seq)));
                }
                case "churn" -> {                          // delete pressure on a narrow range
                    int k = rnd.nextInt(4_000);
                    if (r < 30) t.add(k); else if (r < 85) t.remove(k); else t.contains(k);
                }
                default -> throw new AssertionError();
            }
        }
    }

    /** One contestant's run: per-window comparison costs + the total, streams identical. */
    private record RunResult(double cmpPerOp, double[] windowCost) { }

    private static final int TOTAL_OPS = BLOCK_OPS * REGIMES.length * CYCLES;
    private static final int WINDOWS = TOTAL_OPS / WINDOW;
    private static final int WINDOWS_PER_BLOCK = BLOCK_OPS / WINDOW;

    /** Drive one contestant through the whole schedule, sampling the comparator each window. */
    private static RunResult drive(Ops sink, long[] cmp, long seed, Runnable perOpCadence) {
        RegimeStream rs = new RegimeStream(seed);
        double[] windows = new double[WINDOWS];
        long last = cmp[0];
        int w = 0;
        for (int op = 0; op < TOTAL_OPS; op++) {
            rs.step(sink, op / BLOCK_OPS);
            if (perOpCadence != null) perOpCadence.run();
            if ((op + 1) % WINDOW == 0) {
                windows[w++] = (cmp[0] - last) / (double) WINDOW;
                last = cmp[0];
            }
        }
        return new RunResult(cmp[0] / (double) TOTAL_OPS, windows);
    }

    /** Mean re-adaptation lag in ops over the 7 shifts (block b ≥ 1 starts at a shift). */
    private static double meanLag(double[] windows) {
        double lagSum = 0;
        int shifts = 0;
        for (int b = 1; b < REGIMES.length * CYCLES; b++) {
            int start = b * WINDOWS_PER_BLOCK;
            double steady = 0;
            for (int i = start + WINDOWS_PER_BLOCK - 3; i < start + WINDOWS_PER_BLOCK; i++) {
                steady += windows[i];
            }
            steady /= 3;
            int lagWindows = WINDOWS_PER_BLOCK;            // worst case: never re-enters the band
            for (int i = start; i < start + WINDOWS_PER_BLOCK; i++) {
                if (windows[i] <= steady * LAG_BAND) { lagWindows = i - start; break; }
            }
            lagSum += lagWindows * (double) WINDOW;
            shifts++;
        }
        return lagSum / shifts;
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

    /** A live evolution contestant: ensemble + controller, generations on a fixed cadence. */
    private static RunResult runEvolving(List<PolicyGenome> founders, int mu, int lambda,
                                         long seed, TreeSet<Integer> oracle) {
        long[] cmp = { 0L };
        Comparator<Integer> counting = (a, b) -> { cmp[0]++; return Integer.compare(a, b); };
        EnsembleOrderedSet.Builder<Integer> b = EnsembleOrderedSet.builder(counting)
                .member(() -> new RedBlackStrategy<Integer>());        // the incumbent
        for (int i = 0; i < lambda; i++) b.member(() -> new RedBlackStrategy<Integer>());
        EnsembleOrderedSet<Integer> ens = b.mode(EnsembleMode.SAMPLED_SHADOW)
                .shadowSampleRate(0.25)                    // exploration priced, not free
                .build();
        try {
            List<EnsembleMember<Integer>> nursery = ens.members().subList(1, 1 + lambda);
            PolicyEvolutionController<Integer> c = new PolicyEvolutionController<>(
                    ens, nursery, new RollingWorkloadMonitor(), MorphPolicy.defaults(),
                    founders, mu, false, seed);
            Ops sink = new Ops() {
                @Override public void add(int k)      { c.add(k); if (oracle != null) oracle.add(k); }
                @Override public void remove(int k)   { c.remove(k); if (oracle != null) oracle.remove(k); }
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
            if (oracle != null) {                          // sampled membership, oracle-exact
                Random probe = new Random(seed ^ 0x5EEDL);
                for (int i = 0; i < 2_000; i++) {
                    int k = probe.nextInt(25_000);
                    assertEquals(oracle.contains(k), ens.contains(k),
                            "adaptive contestant diverged at key " + k);
                }
            }
            return r;
        } finally {
            ens.close();
        }
    }

    /** The ADR-002 selector: the control plane over one live set, production cadence. */
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
                if (oracle != null) oracle.add(k);
            }
            @Override public void remove(int k) {
                if (set.remove(k)) monitor.recordRemove(Integer.hashCode(k));
                if (oracle != null) oracle.remove(k);
            }
            @Override public void contains(int k) {
                set.contains(k);
                monitor.recordSearch(Integer.hashCode(k), 0);
            }
        };
        RunResult r = drive(sink, cmp, seed, () -> {
            if (++sinceEval[0] == 10) {                    // EVAL_INTERVAL, the production cadence
                MorphController.MorphResult res = mc.evaluateAndMaybeMorph(current[0], 10);
                if (res.morphed()) current[0] = res.to();
                sinceEval[0] = 0;
            }
        });
        if (oracle != null) {
            Random probe = new Random(seed ^ 0x5EEDL);
            for (int i = 0; i < 2_000; i++) {
                int k = probe.nextInt(25_000);
                assertEquals(oracle.contains(k), set.contains(k),
                        "selector contestant diverged at key " + k);
            }
        }
        return r;
    }

    @Test
    @DisplayName("eight contestants × three seeds: integrated cost + re-adaptation lag, verdict printed")
    void theExperiment() {
        Map<String, Supplier<TreeStrategy<Integer>>> fixed = new LinkedHashMap<>();
        fixed.put("RB", RedBlackStrategy::new);
        fixed.put("AVL", AVLStrategy::new);
        fixed.put("SPLAY", SplayStrategy::new);
        fixed.put("HYBRID", HybridStrategy::new);

        System.out.println("=== ADR-012 E3: the non-stationary experiment ===");
        System.out.println("schedule: " + String.join(" → ", REGIMES) + ", ×" + CYCLES
                + " (" + TOTAL_OPS + " ops, " + BLOCK_OPS + "-op blocks, " + WINDOW + "-op windows)");

        int sustainedWins = 0;
        for (long seed : SEEDS) {
            Map<String, RunResult> results = new LinkedHashMap<>();
            for (Map.Entry<String, Supplier<TreeStrategy<Integer>>> e : fixed.entrySet()) {
                results.put(e.getKey(), runFixed(e.getValue(), seed));
            }
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
                for (int bk = 0; bk < REGIMES.length * CYCLES; bk++) {
                    double mean = 0;
                    for (int i = bk * WINDOWS_PER_BLOCK; i < (bk + 1) * WINDOWS_PER_BLOCK; i++) {
                        mean += e.getValue().windowCost()[i];
                    }
                    blocks.append(String.format(Locale.ROOT, " %6.1f", mean / WINDOWS_PER_BLOCK));
                }
                System.out.println(String.format(Locale.ROOT,
                        "%-6s cmp/op=%7.2f meanLag=%6.0f ops | per-block:%s",
                        e.getKey(), e.getValue().cmpPerOp(),
                        meanLag(e.getValue().windowCost()), blocks));
            }
            System.out.println(String.format(Locale.ROOT,
                    "seed %d: bestFixed=%s (%.2f) bestAdaptive=%.2f improvement=%+.1f%%",
                    seed, bestFixedName, bestFixedCost, bestAdaptive, improvement * 100.0));
        }

        boolean success = sustainedWins == SEEDS.length;
        System.out.println(String.format(Locale.ROOT,
                "event=adr012_e3_verdict success=%s sustainedSeeds=%d/%d margin=%.0f%% "
                + "(criterion: an adaptive scheme beats the best fixed strategy by >=10%% "
                + "integrated cost — exploration included — on all seeds)",
                success, sustainedWins, SEEDS.length, SUCCESS_MARGIN * 100.0));
        // Printed, never hard-asserted: the negative result is a finding (ADR-012 §4 E3,
        // V5 discipline). Correctness is the hard floor above.
    }
}
