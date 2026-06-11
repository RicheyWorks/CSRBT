package core.evolution;

import core.TreeContext;
import core.strategy.*;

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
 * METRICS PER COMPETITOR
 *
 *   totalTimeNs     — wall time for the full workload
 *   avgSearchDepth  — mean tree height after all operations
 *   rotations       — total rotation count
 *   finalSize       — tree size at end
 *   searchHits      — how many searches found their key
 *
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

        /** Composite score: lower time + lower depth + fewer rotations = better. */
        double compositeScore() {
            double timeMs     = totalTimeNs / 1_000_000.0;
            double depthScore = avgSearchDepth;
            double rotScore   = (double) rotations / Math.max(1, totalOps);
            // Normalize each to roughly [0, 10] then sum; lower = better
            return (timeMs * 0.5) + (depthScore * 3.0) + (rotScore * 2.0);
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
            String name     = entry.getKey();
            TreeStrategy<Integer> st = entry.getValue().get();
            BattleResult r  = runCompetitor(name, st, ops, workload);
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

    private static BattleResult runCompetitor(String name, TreeStrategy<Integer> strategy,
                                               List<int[]> ops, WorkloadType workload) {
        TreeContext ctx       = new TreeContext(strategy);
        int         hits      = 0;
        int         totalOps  = ops.size();

        long start = System.nanoTime();

        for (int[] op : ops) {
            int type  = op[0];   // 0=insert, 1=search, 2=delete
            int value = op[1];

            switch (type) {
                case 0 -> ctx.add(value);
                case 1 -> { if (ctx.contains(value)) hits++; }
                case 2 -> ctx.remove(value);
            }
        }

        long elapsed = System.nanoTime() - start;

        // Measure avg search depth as tree height (proxy; real avg would require traversal)
        double avgDepth = ctx.getTree().getRoot().getHeight();

        // Capture hybrid-specific metrics if applicable
        HybridStrategy.HybridMetricsSnapshot hybridSnapshot = null;
        if (strategy instanceof HybridStrategy<?> hs) {
            hybridSnapshot = hs.snapshot(ctx.getSize(), avgDepth);
        }

        return new BattleResult(
                name, workload, elapsed, avgDepth,
                ctx.getRotationCount(), ctx.getSize(),
                hits, totalOps, hybridSnapshot
        );
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
                // Insert 0..n/2 in order, then search randomly
                int half = opCount / 2;
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
                // Insert 500, then delete most, then search survivors
                int inserts = Math.min(500, opCount / 3);
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
