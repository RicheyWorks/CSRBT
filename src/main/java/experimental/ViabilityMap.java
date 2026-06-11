package experimental;

import core.RedBlackTree;
import core.evolution.PolicyGenome;
import core.strategy.WeightBalancedStrategy;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.TreeSet;

/**
 * ADR-012 E1 — the <b>viability map</b>: the health gate's lethality oracle swept over the
 * whole (Δ, Γ) parameter plane. Pure instrument, no new mechanism.
 *
 * <p>For every cell — the search box {@code Δ ∈ [2, 8], Γ ∈ [1, Δ)} plus unboxed samples
 * out to {@link PolicyGenome#DELTA_STRUCTURAL_MAX} — run the <em>identical</em> seeded
 * delete-churn stream (the ADR-011 V1 recipe that discovered (5,3): 55% add / 45% remove
 * over 700 keys, invariant checked every 100 ops) and record the first op at which the
 * strategy's own {@code validateInvariant} — the exact hook the health gate calls —
 * reports a violation. Same streams across cells, so the only variable is the genome:
 * what dies, dies of its parameters. Contents are oracle-checked on every probe; an
 * unsound arm never loses data ({@code probe} throws if that ever stops being true,
 * which would be a correctness bug, not a map entry).</p>
 *
 * <p><i>Thesis (ADR-012 §4 E1):</i> the viable region has nontrivial structure — it is
 * not "everything in the box". Known landmarks: (3, 2) is the literature point and must
 * map clean; (5, 3) is V1's in-bounds-but-unsound finding; (2, 1) died on the record in
 * {@code docs/arena-search-session.json}. This is mutational robustness made literal.</p>
 *
 * <p>Run from the repo root after compiling (writes the heatmap artifact the visualizer
 * renders — drop the file onto {@code demo/visualizer.html}):</p>
 * <pre>{@code java -cp build/classes experimental.ViabilityMap [docs/viability-map.json]}</pre>
 */
public final class ViabilityMap {

    /** Ops per probe — generous: every death seen so far announced itself before op 1200. */
    public static final int OPS = 8_000;
    /** Invariant cadence (the V1 recipe's). */
    public static final int CHECK_EVERY = 100;
    /** Key range (the V1 recipe's). */
    public static final int KEY_RANGE = 700;
    /** Add percentage; the rest are removes (the V1 recipe's delete churn). */
    public static final int ADD_PCT = 55;
    /** The V5 seed convention. */
    public static final long[] SEEDS = { 11L, 2026L, 42L };
    /** Unboxed Δ samples (past {@link PolicyGenome#DELTA_MAX}, behind the V4 flag's bound). */
    public static final int[] UNBOXED_DELTAS = { 10, 12, 16, 20, 24, 32 };

    /** One probed cell: per-seed first-violation op ({@code -1} = clean for all {@code OPS}). */
    public record Cell(int delta, int ratio, boolean inBox, int[] firstViolationOp, String detail) {
        /** Unsound iff any seed tripped the invariant. */
        public boolean unsound() {
            for (int op : firstViolationOp) if (op >= 0) return true;
            return false;
        }
        /** Earliest death across seeds, or {@code -1} if clean. */
        public int earliest() {
            int e = -1;
            for (int op : firstViolationOp) if (op >= 0 && (e < 0 || op < e)) e = op;
            return e;
        }
    }

    private ViabilityMap() { }

    /**
     * One (Δ, Γ, seed) probe: the V1 churn recipe, first violation op or {@code -1}.
     * Stops at the first violation (viability is decided; churning a known-unsound tree
     * further only spams the engine's WARN log) — but always oracle-checks contents at
     * exit. Throws if contents ever diverge: balance may degrade; data may not.
     */
    public static int probe(int delta, int ratio, long seed, String[] detailOut) {
        WeightBalancedStrategy<Integer> ws = new WeightBalancedStrategy<>(delta, ratio);
        RedBlackTree<Integer> tree = RedBlackTree.withNaturalOrder(ws);
        TreeSet<Integer> oracle = new TreeSet<>();
        Random rnd = new Random(seed);
        int firstViolation = -1;
        for (int op = 1; op <= OPS && firstViolation < 0; op++) {
            int key = rnd.nextInt(KEY_RANGE);
            if (rnd.nextInt(100) < ADD_PCT) { tree.add(key); oracle.add(key); }
            else                            { tree.remove(key); oracle.remove(key); }
            if (op % CHECK_EVERY == 0) {
                List<String> v = ws.validateInvariant(tree);
                if (!v.isEmpty()) {
                    firstViolation = op;
                    if (detailOut != null && detailOut[0] == null) detailOut[0] = v.get(0);
                }
            }
        }
        if (!new ArrayList<>(oracle).equals(tree.inOrder())) {
            throw new IllegalStateException("data loss at (" + delta + "," + ratio + ") seed "
                    + seed + " — this is a correctness bug, not a viability finding");
        }
        return firstViolation;
    }

    /** Sweep the box and the unboxed samples; identical streams per seed across cells. */
    public static List<Cell> sweep() {
        List<Cell> cells = new ArrayList<>();
        for (int delta = PolicyGenome.DELTA_MIN; delta <= PolicyGenome.DELTA_MAX; delta++) {
            for (int ratio = 1; ratio < delta; ratio++) {
                cells.add(probeCell(delta, ratio, true));
            }
        }
        for (int delta : UNBOXED_DELTAS) {
            for (int ratio : new int[]{ 1, delta / 2, delta - 1 }) {
                cells.add(probeCell(delta, ratio, false));
            }
        }
        return cells;
    }

    private static Cell probeCell(int delta, int ratio, boolean inBox) {
        int[] ops = new int[SEEDS.length];
        String[] detail = new String[1];
        for (int s = 0; s < SEEDS.length; s++) ops[s] = probe(delta, ratio, SEEDS[s], detail);
        return new Cell(delta, ratio, inBox, ops, detail[0]);
    }

    /** The artifact: {@code {"type":"ViabilityMap", ...}} — the shape the visualizer renders. */
    public static String toJson(List<Cell> cells) {
        StringBuilder sb = new StringBuilder();
        sb.append("{\"type\":\"ViabilityMap\",\"version\":1,")
          .append("\"ops\":").append(OPS)
          .append(",\"checkEvery\":").append(CHECK_EVERY)
          .append(",\"keyRange\":").append(KEY_RANGE)
          .append(",\"addPct\":").append(ADD_PCT)
          .append(",\"seeds\":[");
        for (int i = 0; i < SEEDS.length; i++) sb.append(i > 0 ? "," : "").append(SEEDS[i]);
        sb.append("],\"cells\":[");
        for (int i = 0; i < cells.size(); i++) {
            Cell c = cells.get(i);
            if (i > 0) sb.append(',');
            sb.append("{\"delta\":").append(c.delta())
              .append(",\"ratio\":").append(c.ratio())
              .append(",\"inBox\":").append(c.inBox())
              .append(",\"firstViolationOp\":[");
            for (int s = 0; s < c.firstViolationOp().length; s++) {
                sb.append(s > 0 ? "," : "").append(c.firstViolationOp()[s]);
            }
            sb.append(']');
            if (c.detail() != null) {
                sb.append(",\"detail\":\"").append(c.detail().replace("\\", "\\\\")
                        .replace("\"", "\\\"").replace("Δ", "\\u0394")).append('"');
            }
            sb.append('}');
        }
        sb.append("]}");
        return sb.toString();
    }

    public static void main(String[] args) throws java.io.IOException {
        List<Cell> cells = sweep();
        java.nio.file.Path out = java.nio.file.Path.of(
                args.length > 0 ? args[0] : "docs/viability-map.json");
        java.nio.file.Files.writeString(out, toJson(cells));
        int unsound = 0;
        for (Cell c : cells) if (c.unsound()) unsound++;
        System.err.println("wrote " + out + " — " + cells.size() + " cells, "
                + unsound + " unsound");
    }
}
