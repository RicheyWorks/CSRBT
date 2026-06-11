package test.core;

import core.OrderedSet;
import core.control.MorphPolicy;
import core.control.RollingWorkloadMonitor;
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
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-011 V5 — <b>the acceptance experiment</b>. For each workload family and seed, the
 * evolution machine searches the verified box on the family's live stream (V4 controller,
 * 5 generations) and <em>selects</em> a policy; the selected policy then races the four
 * fixed strategies as plain single {@code OrderedSet}s on identical fresh streams, long
 * enough to amortize the build. Realized cost = <b>comparisons per op</b>, counted at the
 * comparator seam — deterministic, so the verdict reproduces on any machine. Wall-clock
 * ns/op is printed for context only: its run-to-run variance exceeded the 10% margin
 * (two runs, two verdicts), which is itself a documented finding of this experiment.
 *
 * <p><b>Success criterion (the ADR's, verbatim):</b> the selected policy beats the best
 * fixed strategy by ≥10% realized cost on ≥1 family, sustained across all 3 seeds.
 * Published as in-suite printed rows with soft assertions — house benchmark discipline:
 * hard assertions cover <em>correctness</em> (selected policies exist, are in-box, and
 * are oracle-exact on every family); the verdict is printed and documented in the ADR.
 * <b>The negative result is a legitimate finding</b> — ADR-011 flips to Accepted either
 * way.</p>
 */
@DisplayName("ADR-011 V5 — the acceptance experiment (evolved vs the fixed four)")
public class EvolutionAcceptanceExperimentTest {

    private static final String[] FAMILIES =
            {"uniform", "hot-key", "sequential", "delete-heavy", "regime-switching"};
    private static final long[] SEEDS = {11L, 2026L, 42L};
    private static final int SEARCH_GENERATIONS = 5;
    private static final int SEARCH_OPS_PER_GEN = 1_500;
    private static final int WARMUP_OPS = 8_000;
    private static final int MEASURE_OPS = 30_000;
    private static final double SUCCESS_MARGIN = 0.10;

    /** The op-sink seam: one stream definition drives controllers, sets, and oracles alike. */
    private interface Ops {
        void add(int k);
        void remove(int k);
        void contains(int k);
    }

    /** Deterministic per-(family, seed) op stream; stateful so a search can chop it into windows. */
    private static final class FamilyStream {
        private final String family;
        private final Random rnd;
        private final int hotBase;
        private int seq;
        private int regime;

        FamilyStream(String family, long seed) {
            this.family = family;
            this.rnd = new Random(seed);
            this.hotBase = rnd.nextInt(10_000);
        }

        void run(Ops t, int count) {
            for (int i = 0; i < count; i++) step(t);
        }

        private void step(Ops t) {
            int r = rnd.nextInt(100);
            switch (family) {
                case "uniform" -> {                              // balanced mix, no locality
                    int k = rnd.nextInt(20_000);
                    if (r < 30) t.add(k); else if (r < 45) t.remove(k); else t.contains(k);
                }
                case "hot-key" -> {                              // 80% of traffic on 100 keys
                    int k = rnd.nextInt(100) < 80 ? hotBase + rnd.nextInt(100) : rnd.nextInt(50_000);
                    if (r < 20) t.add(k); else if (r < 30) t.remove(k); else t.contains(k);
                }
                case "sequential" -> {                           // log-append, recent reads
                    if (r < 40 || seq == 0) t.add(seq++);
                    else if (r < 50 && seq > 2_000) t.remove(rnd.nextInt(seq - 2_000));
                    else t.contains(seq - 1 - rnd.nextInt(Math.min(64, seq)));
                }
                case "delete-heavy" -> {                         // churn-down after a prefill
                    if (seq < 6_000) { t.add(seq++); return; }
                    int k = rnd.nextInt(8_000);
                    if (r < 25) t.add(k); else if (r < 70) t.remove(k); else t.contains(k);
                }
                case "regime-switching" -> {                     // hot reads <-> uniform writes
                    if (++seq % 4_000 == 0) regime ^= 1;
                    if (regime == 0) {
                        int k = hotBase + rnd.nextInt(200);
                        if (r < 15) t.add(k); else t.contains(k);
                    } else {
                        int k = rnd.nextInt(20_000);
                        if (r < 50) t.add(k); else t.remove(k);
                    }
                }
                default -> throw new AssertionError(family);
            }
        }
    }

    private static Ops sink(OrderedSet<Integer> s) {
        return new Ops() {
            @Override public void add(int k)      { s.add(k); }
            @Override public void remove(int k)   { s.remove(k); }
            @Override public void contains(int k) { s.contains(k); }
        };
    }

    /** Phase 1: the machine searches the family's stream and selects a policy (V4 loop). */
    private static PolicyGenome searchPolicy(String family, long seed) {
        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new RedBlackStrategy<Integer>())
                .mode(EnsembleMode.SAMPLED_SHADOW)
                .shadowSampleRate(1.0)
                .build();
        try {
            PolicyEvolutionController<Integer> c = new PolicyEvolutionController<>(
                    ens, ens.members().subList(1, 4), new RollingWorkloadMonitor(),
                    MorphPolicy.defaults(),
                    List.of(PolicyGenome.weightBalanced(3, 2), PolicyGenome.weightBalanced(4, 2)),
                    2, false, seed);
            Ops stream = new Ops() {
                @Override public void add(int k)      { c.add(k); }
                @Override public void remove(int k)   { c.remove(k); }
                @Override public void contains(int k) { c.contains(k); }
            };
            FamilyStream fs = new FamilyStream(family, seed * 7 + 13);
            for (int gen = 0; gen < SEARCH_GENERATIONS; gen++) {
                c.beginGeneration();
                fs.run(stream, SEARCH_OPS_PER_GEN);
                c.endGeneration(SEARCH_OPS_PER_GEN);
            }
            return c.parents().get(0);
        } finally {
            ens.close();
        }
    }

    /** One contender's realized cost: deterministic comparisons/op + wall-clock ns/op. */
    private record Cost(double cmpPerOp, double nsPerOp) { }

    /**
     * Phase 2: race one contender — fresh set, fresh identical stream. The <b>verdict
     * metric is comparisons per op</b>, counted by the comparator seam itself: exact,
     * reproducible on any machine, and the dominant realized cost (path lengths of every
     * search, insert, and delete). Wall-clock ns/op is printed for context only — on
     * shared hardware its run-to-run variance exceeds the 10% margin, which this
     * experiment discovered the empirical way (two runs, two verdicts) before switching
     * to the deterministic meter. Rotation overhead is the documented gap (no rotation
     * counters on the mutable seam — ADR-009 §3 holds until a consumer demands them).
     */
    private static Cost race(Supplier<TreeStrategy<Integer>> strategy, String family, long seed) {
        new FamilyStream(family, seed)                            // JIT warmup, untimed, discarded
                .run(sink(OrderedSet.withNaturalOrder(strategy.get())), WARMUP_OPS);
        long[] cmp = {0L};
        Comparator<Integer> counting = (a, b) -> { cmp[0]++; return Integer.compare(a, b); };
        OrderedSet<Integer> set = new OrderedSet<>(strategy.get(), counting);
        FamilyStream fs = new FamilyStream(family, seed);
        long t0 = System.nanoTime();
        fs.run(sink(set), MEASURE_OPS);
        double ns = (System.nanoTime() - t0) / (double) MEASURE_OPS;
        return new Cost(cmp[0] / (double) MEASURE_OPS, ns);
    }

    @Test
    @DisplayName("five families × three seeds: search, race, and print the verdict")
    void theExperiment() {
        Map<String, Supplier<TreeStrategy<Integer>>> fixed = new LinkedHashMap<>();
        fixed.put("RB", RedBlackStrategy::new);
        fixed.put("AVL", AVLStrategy::new);
        fixed.put("SPLAY", SplayStrategy::new);
        fixed.put("HYBRID", HybridStrategy::new);

        List<String> winningFamilies = new ArrayList<>();
        System.out.println("=== ADR-011 V5: the acceptance experiment (cost = comparisons/op) ===");

        for (String family : FAMILIES) {
            int sustainedWins = 0;
            for (long seed : SEEDS) {
                PolicyGenome selected = searchPolicy(family, seed);
                assertNotNull(selected, family + "/" + seed + ": search selected nothing");
                assertTrue(selected.inVerifiedBox(), "flag off: selection must stay in-box");

                StringBuilder row = new StringBuilder(String.format(Locale.ROOT,
                        "family=%-16s seed=%-5d", family, seed));
                double bestFixed = Double.POSITIVE_INFINITY;
                String bestFixedName = "?";
                for (Map.Entry<String, Supplier<TreeStrategy<Integer>>> e : fixed.entrySet()) {
                    Cost c = race(e.getValue(), family, seed);
                    assertTrue(c.cmpPerOp() > 0.0);
                    row.append(String.format(Locale.ROOT, " %s=%.2f", e.getKey(), c.cmpPerOp()));
                    if (c.cmpPerOp() < bestFixed) { bestFixed = c.cmpPerOp(); bestFixedName = e.getKey(); }
                }
                Cost evolved = race(selected::toStrategy, family, seed);
                double improvement = (bestFixed - evolved.cmpPerOp()) / bestFixed;
                if (improvement >= SUCCESS_MARGIN) sustainedWins++;
                row.append(String.format(Locale.ROOT,
                        " | evolved[%s]=%.2f (%.0fns/op) bestFixed=%s improvement=%+.1f%%",
                        selected, evolved.cmpPerOp(), evolved.nsPerOp(), bestFixedName,
                        improvement * 100.0));
                System.out.println(row);
            }
            if (sustainedWins == SEEDS.length) winningFamilies.add(family);
        }

        boolean success = !winningFamilies.isEmpty();
        System.out.println(String.format(Locale.ROOT,
                "event=adr011_verdict success=%s margin=%.0f%% sustainedFamilies=%s "
                + "(criterion: >=10%% vs best fixed, all %d seeds, >=1 family)",
                success, SUCCESS_MARGIN * 100.0, winningFamilies, SEEDS.length));
        // The verdict is printed and documented, never hard-asserted: house benchmark
        // discipline, and the ADR accepts the negative result as a finding. Correctness
        // is asserted in the test below.
    }

    @Test
    @DisplayName("correctness floor: a searched policy is oracle-exact on every family")
    void selectedPoliciesAreExact() {
        for (String family : FAMILIES) {
            PolicyGenome selected = searchPolicy(family, SEEDS[0]);
            OrderedSet<Integer> set = OrderedSet.withNaturalOrder(selected.<Integer>toStrategy());
            TreeSet<Integer> oracle = new TreeSet<>();
            Ops both = new Ops() {
                @Override public void add(int k)      { set.add(k); oracle.add(k); }
                @Override public void remove(int k)   { set.remove(k); oracle.remove(k); }
                @Override public void contains(int k) {
                    assertEquals(oracle.contains(k), set.contains(k), family + " contains(" + k + ")");
                }
            };
            new FamilyStream(family, 5L).run(both, 8_000);
            assertEquals(new ArrayList<>(oracle), set.inOrder(), family + ": contents diverged");
            assertFalse(set.isEmpty(), family + ": stream produced an empty set (dead workload?)");
        }
    }
}
