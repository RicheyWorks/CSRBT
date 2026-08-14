package io.github.richeyworks.csrbt.evolution;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.strategy.*;

import java.util.*;
import java.util.function.Supplier;

/**
 * StrategyBattleRunner
 *
 * Races Red-Black, AVL, Splay, and Hybrid on the same workload sequence
 * and produces a ranked performance report.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WORKLOAD TYPES
 *
 *   RANDOM_UNIFORM   — fully random inserts + searches (favors RB/AVL)
 *   SEQUENTIAL       — sorted inserts, random searches (worst case for naive BST)
 *   LOCALITY_BURST   — Zipf-distributed searches on a small hot key set (favors Splay)
 *   MIXED            — 40% insert, 40% search, 20% delete, random keys
 *   INSERT_HEAVY     — 80% insert, 20% search (favors strict balancers)
 *   SEARCH_HEAVY     — 10% insert, 90% search with locality (favors Splay/Hybrid)
 *   DELETE_HEAVY     — insert 500 then delete 80%, random order
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * METRICS PER COMPETITOR (methodology per ADR-022)
 *
 *   totalTimeNs     — MEDIAN wall time over TIMED_PASSES fresh runs, after one
 *                     untimed warmup pass (JIT paid off the clock; single-pass
 *                     cold-start timing used to hand the first competitor a 3.6×
 *                     penalty and reorder ranks on identical inputs)
 *   avgSearchDepth  — mean REALIZED search depth (nodes touched per search op),
 *                     not the root height it used to be (root height is the worst
 *                     case, guaranteed Splay last place regardless of locality)
 *   rotations       — total rotation count
 *   finalSize       — tree size at end
 *   searchHits      — how many searches found their key
 *
 * Search ops run in two steps: a measuring walk (realized depth + hit/miss), then
 * the STRATEGY'S OWN search — the engine-level path where a self-adjusting
 * strategy actually self-adjusts. OrderedSet.contains never splays by design
 * (ADR-004 R1 reserves splaying for the write path), so the old contains-driven
 * battle benchmarked Splay with its defining move disabled in the very workloads
 * documented to favor it. Every competitor pays the same two-walk cost, so
 * relative timing stays fair.
 * ─────────────────────────────────────────────────────────────────────────────
 */
public class StrategyBattleRunner {

    public enum WorkloadType {
        RANDOM_UNIFORM,
        SEQUENTIAL,
        LOCALITY_BURST,
        MIXED,
        INSERT_HEAVY,
        SEARCH_HEAVY,
        DELETE_HEAVY
    }

    // ── Competitor registry ───────────────────────────────────────────────────

    private static final LinkedHashMap<String, Supplier<TreeStrategy<Integer>>> COMPETITORS
            = new LinkedHashMap<>();

    static {
        COMPETITORS.put("RedBlack", RedBlackStrategy::new);
        COMPETITORS.put("AVL",      AVLStrategy::new);
        COMPETITORS.put("Splay",    SplayStrategy::new);
        COMPETITORS.put("Hybrid",   HybridStrategy::new);
    }

    // ── Result ────────────────────────────────────────────────────────────────

    public static class BattleResult {
        public final String      strategyName;
        public final WorkloadType workload;
        public final long        totalTimeNs;
        public final double      avgSearchDepth;
        public final int         rotations;
        public final int         finalSize;
        public final int         searchHits;
        public final int         totalOps;
        public       int         rank;            // set after all results collected

        // Hybrid-specific extras (null for non-hybrid competitors)
        public final HybridStrategy.HybridMetricsSnapshot hybridSnapshot;

        BattleResult(String strategyName, WorkloadType workload,
                     long totalTimeNs, double avgSearchDepth,
                     int rotations, int finalSize, int searchHits, int totalOps,
                     HybridStrategy.HybridMetricsSnapshot hybridSnapshot) {
            this.strategyName   = strategyName;
            this.workload       = workload;
            this.totalTimeNs    = totalTimeNs;
            this.avgSearchDepth = avgSearchDepth;
            this.rotations      = rotations;
            this.finalSize      = finalSize;
            this.searchHits     = searchHits;
            this.totalOps       = totalOps;
            this.hybridSnapshot = hybridSnapshot;
        }

        /**
         * Composite score: lower time + lower realized depth = better. The rotation
         * term was REMOVED when the rotation meter came alive (T-1 + ADR-022's held
         * weight decision, fired 2026-08-12): rotations are work, and work is already
         * priced into wall time — charging them again double-counted Splay's
         * self-adjustment (~6 rotations per locality search) and flipped the locality
         * verdicts away from the workloads' documented intent. Rotations remain a
         * reported metric; they just don't score twice.
         */
        double compositeScore() {
            double timeMs     = totalTimeNs / 1_000_000.0;
            double depthScore = avgSearchDepth;
            return (timeMs * 0.5) + (depthScore * 3.0);
        }

        @Override
        public String toString() {
            return String.format(
                    "  #%d %-10s | time=%6.2fms | avgDepth=%5.2f | rots=%5d | hits=%4d/%4d",
                    rank, strategyName,
                    totalTimeNs / 1_000_000.0,
                    avgSearchDepth,
                    rotations,
                    searchHits, totalOps
            );
        }
    }

    // ── Run one battle ────────────────────────────────────────────────────────

    /**
     * Runs all four strategies on the given workload type and returns ranked results.
     *
     * @param workload  which workload pattern to use
     * @param opCount   total number of operations in the workload
     * @param seed      RNG seed for reproducibility (same seed = same workload for all)
     */
    public static List<BattleResult> run(WorkloadType workload, int opCount, long seed) {
        List<int[]> ops = generateWorkload(workload, opCount, seed);
        List<BattleResult> results = new ArrayList<>();

        for (Map.Entry<String, Supplier<TreeStrategy<Integer>>> entry : COMPETITORS.entrySet()) {
            BattleResult r = runCompetitor(entry.getKey(), entry.getValue(), ops, workload);
            results.add(r);
        }

        // Rank by composite score (ascending = better)
        results.sort(Comparator.comparingDouble(BattleResult::compositeScore));
        for (int i = 0; i < results.size(); i++) results.get(i).rank = i + 1;

        return results;
    }

    /**
     * Runs all workload types for a full tournament.
     * Returns a map of workload → ranked results.
     */
    public static Map<WorkloadType, List<BattleResult>> tournament(int opCount, long seed) {
        Map<WorkloadType, List<BattleResult>> tournament = new LinkedHashMap<>();
        for (WorkloadType wl : WorkloadType.values()) {
            tournament.put(wl, run(wl, opCount, seed));
        }
        return tournament;
    }

    // ── Competitor runner ─────────────────────────────────────────────────────

    /** Untimed warmup passes + timed passes per competitor (ADR-022). */
    private static final int TIMED_PASSES = 3;

    private static BattleResult runCompetitor(String name,
                                               Supplier<TreeStrategy<Integer>> strategyFactory,
                                               List<int[]> ops, WorkloadType workload) {
        // Warmup: one full untimed pass on a throwaway context, so the JIT is paid
        // before any clock starts (ADR-022; the first competitor used to run 3.6×
        // slower cold, reordering ranks on identical inputs).
        runPass(new TreeContext(strategyFactory.get()), ops);

        // Timed passes: fresh context each, median wall time. The non-timing metrics
        // are identical across passes (same ops, same strategy), so they come from
        // the last pass.
        long[] times = new long[TIMED_PASSES];
        PassResult last = null;
        TreeContext lastCtx = null;
        TreeStrategy<Integer> lastStrategy = null;
        for (int pass = 0; pass < TIMED_PASSES; pass++) {
            TreeStrategy<Integer> strategy = strategyFactory.get();
            TreeContext ctx = new TreeContext(strategy);
            long start = System.nanoTime();
            PassResult r = runPass(ctx, ops);
            times[pass] = System.nanoTime() - start;
            last = r;
            lastCtx = ctx;
            lastStrategy = strategy;
        }
        Arrays.sort(times);
        long medianElapsed = times[TIMED_PASSES / 2];

        double avgDepth = last.searchOps == 0 ? 0.0
                : (double) last.depthSum / last.searchOps;   // realized, not root height

        HybridStrategy.HybridMetricsSnapshot hybridSnapshot = null;
        if (lastStrategy instanceof HybridStrategy<?> hs) {
            hybridSnapshot = hs.snapshot(lastCtx.getSize(), avgDepth);
        }

        return new BattleResult(
                name, workload, medianElapsed, avgDepth,
                lastCtx.getRotationCount(), lastCtx.getSize(),
                last.hits, ops.size(), hybridSnapshot
        );
    }

    private record PassResult(int hits, long depthSum, int searchOps) { }

    /**
     * JMH-blackhole stand-in: every strategy search result folds into this volatile,
     * so the JIT cannot dead-code-eliminate the pure descents (RedBlack/AVL searches
     * have no side effects; without a sink they could be optimized away, and the
     * "same extra cost for all" fairness claim would silently stop holding).
     */
    private static volatile long searchSink;

    /** One full workload pass. Search = measuring walk + the strategy's own search. */
    private static PassResult runPass(TreeContext ctx, List<int[]> ops) {
        int hits = 0;
        long depthSum = 0;
        int searchOps = 0;
        long sink = 0;
        for (int[] op : ops) {
            int type  = op[0];   // 0=insert, 1=search, 2=delete
            int value = op[1];
            switch (type) {
                case 0 -> ctx.add(value);
                case 1 -> {
                    // Realized depth + hit/miss in one measuring walk (pre-access cost)…
                    int d = ctx.getOrderedSet().searchDepth(value);
                    boolean hit = d >= 0;
                    depthSum += hit ? d : ~d;
                    searchOps++;
                    if (hit) hits++;
                    // …then the STRATEGY'S search, so a self-adjusting strategy adjusts
                    // (SplayStrategy splays the accessed key toward the root; a plain
                    // descent for everyone else — the same extra cost for all).
                    var found = ctx.getTree().getStrategy().search(ctx.getTree(), value);
                    sink += (found != null && !found.isNil()) ? 1 : 0;
                }
                case 2 -> ctx.remove(value);
            }
        }
        searchSink += sink;   // volatile write — the observable the JIT must preserve
        return new PassResult(hits, depthSum, searchOps);
    }

    // ── Workload generation ───────────────────────────────────────────────────

    private static List<int[]> generateWorkload(WorkloadType type, int opCount, long seed) {
        Random rng  = new Random(seed);
        List<int[]> ops = new ArrayList<>(opCount);

        switch (type) {

            case RANDOM_UNIFORM -> {
                // 50% insert, 50% search, fully random keys
                for (int i = 0; i < opCount; i++) {
                    int op  = rng.nextBoolean() ? 0 : 1;
                    ops.add(new int[]{op, rng.nextInt(10_000)});
                }
            }

            case SEQUENTIAL -> {
                // Insert 0..n/2 in order, then search randomly. Floor of 1 keeps
                // nextInt(half) legal for degenerate opCount (nextInt(0) throws).
                int half = Math.max(1, opCount / 2);
                for (int i = 0; i < half; i++) ops.add(new int[]{0, i});
                for (int i = half; i < opCount; i++) ops.add(new int[]{1, rng.nextInt(half)});
            }

            case LOCALITY_BURST -> {
                // Insert random universe, then search a small hot set repeatedly (Zipf-like)
                int universe = Math.max(1, opCount / 10);
                int[] hotKeys = new int[20];
                for (int i = 0; i < hotKeys.length; i++) hotKeys[i] = rng.nextInt(universe);

                // Insert phase
                for (int i = 0; i < universe; i++) ops.add(new int[]{0, i});

                // Locality-heavy search phase
                for (int i = universe; i < opCount; i++) {
                    int key = (rng.nextDouble() < 0.80)
                            ? hotKeys[rng.nextInt(hotKeys.length)]   // 80% hot
                            : rng.nextInt(universe);                  // 20% cold
                    ops.add(new int[]{1, key});
                }
            }

            case MIXED -> {
                // 40% insert, 40% search, 20% delete
                Set<Integer> inserted = new LinkedHashSet<>();
                for (int i = 0; i < opCount; i++) {
                    double r = rng.nextDouble();
                    if (r < 0.40) {
                        int v = rng.nextInt(5_000);
                        inserted.add(v);
                        ops.add(new int[]{0, v});
                    } else if (r < 0.80) {
                        ops.add(new int[]{1, rng.nextInt(5_000)});
                    } else {
                        if (!inserted.isEmpty()) {
                            int v = inserted.iterator().next();
                            inserted.remove(v);
                            ops.add(new int[]{2, v});
                        } else {
                            ops.add(new int[]{0, rng.nextInt(5_000)});
                        }
                    }
                }
            }

            case INSERT_HEAVY -> {
                // 80% insert, 20% search
                for (int i = 0; i < opCount; i++) {
                    int op = (rng.nextDouble() < 0.80) ? 0 : 1;
                    ops.add(new int[]{op, rng.nextInt(10_000)});
                }
            }

            case SEARCH_HEAVY -> {
                // Insert a small set, then search it heavily with locality
                int baseSize = Math.max(1, opCount / 20);
                for (int i = 0; i < baseSize; i++) ops.add(new int[]{0, rng.nextInt(baseSize)});
                for (int i = baseSize; i < opCount; i++) {
                    // 90% locality: 10 hot keys
                    int key = (rng.nextDouble() < 0.90) ? rng.nextInt(10) : rng.nextInt(baseSize);
                    ops.add(new int[]{1, key});
                }
            }

            case DELETE_HEAVY -> {
                // Insert 500, then delete most, then search survivors. Floor of 1
                // keeps nextInt(inserts) legal for degenerate opCount (< 3).
                int inserts = Math.max(1, Math.min(500, opCount / 3));
                List<Integer> pool = new ArrayList<>();
                for (int i = 0; i < inserts; i++) {
                    pool.add(i);
                    ops.add(new int[]{0, i});
                }
                Collections.shuffle(pool, rng);
                int deletes = (int) (inserts * 0.80);
                for (int i = 0; i < deletes && i < opCount - inserts; i++) {
                    ops.add(new int[]{2, pool.get(i)});
                }
                int remaining = opCount - inserts - deletes;
                for (int i = 0; i < remaining; i++) ops.add(new int[]{1, rng.nextInt(inserts)});
            }
        }

        return ops;
    }

    // ── Report formatting ─────────────────────────────────────────────────────

    /**
     * Formats a single battle result list into a readable report string.
     */
    public static String formatBattle(List<BattleResult> results) {
        if (results.isEmpty()) return "(no results)";

        WorkloadType wl = results.get(0).workload;
        StringBuilder sb = new StringBuilder();
        sb.append("╔══════════════════════════════════════════════════════════╗\n");
        sb.append(String.format("║  BATTLE: %-47s║\n", wl));
        sb.append("╠══════════════════════════════════════════════════════════╣\n");
        sb.append("║  Rank  Strategy   │ Time(ms) │ AvgDepth │ Rots  │ Hits ║\n");
        sb.append("╠══════════════════════════════════════════════════════════╣\n");

        for (BattleResult r : results) {
            String medal = switch (r.rank) { case 1 -> "🥇"; case 2 -> "🥈"; case 3 -> "🥉"; default -> "  "; };
            sb.append(String.format("║ %s #%d %-9s│ %8.3f │ %8.2f │ %5d │%5d ║\n",
                    medal, r.rank, r.strategyName,
                    r.totalTimeNs / 1_000_000.0,
                    r.avgSearchDepth,
                    r.rotations,
                    r.searchHits));
        }
        sb.append("╚══════════════════════════════════════════════════════════╝\n");

        // Hybrid diagnostics block if present
        for (BattleResult r : results) {
            if (r.hybridSnapshot != null) {
                sb.append("\n[HYBRID DIAGNOSTICS]\n");
                sb.append(r.hybridSnapshot).append("\n");
                sb.append(String.format("  Derived fitness : %.4f\n",
                        r.hybridSnapshot.derivedFitness(r.finalSize)));
            }
        }

        return sb.toString();
    }

    /**
     * Formats a full tournament report with per-workload tables and
     * an overall win-count leaderboard.
     */
    public static String formatTournament(Map<WorkloadType, List<BattleResult>> tournament) {
        StringBuilder sb = new StringBuilder();

        Map<String, Integer> wins = new LinkedHashMap<>();
        COMPETITORS.keySet().forEach(k -> wins.put(k, 0));

        for (Map.Entry<WorkloadType, List<BattleResult>> entry : tournament.entrySet()) {
            sb.append(formatBattle(entry.getValue()));
            sb.append("\n");
            // Award win to rank-1
            entry.getValue().stream()
                    .filter(r -> r.rank == 1)
                    .findFirst()
                    .ifPresent(r -> wins.merge(r.strategyName, 1, Integer::sum));
        }

        // Leaderboard
        sb.append("╔══════════════════════════════════╗\n");
        sb.append("║     TOURNAMENT LEADERBOARD        ║\n");
        sb.append("╠══════════════════════════════════╣\n");

        wins.entrySet().stream()
                .sorted(Map.Entry.<String, Integer>comparingByValue().reversed())
                .forEach(e -> sb.append(String.format("║  %-12s  wins: %d / %d       ║\n",
                        e.getKey(), e.getValue(), tournament.size())));

        sb.append("╚══════════════════════════════════╝\n");
        return sb.toString();
    }
}
