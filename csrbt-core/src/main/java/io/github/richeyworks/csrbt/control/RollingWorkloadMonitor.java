package io.github.richeyworks.csrbt.control;

/**
 * Default {@link WorkloadMonitor}: an O(1)-per-op, bounded-memory, exponentially
 * decayed summary of the op stream (DESIGN-adaptive-engine.md §3.1 / §9.2). It
 * formalizes the ad-hoc {@code stress / entropy / fragmentation} signals the legacy
 * {@code GenomeDrivenTreeController} computed over a fixed 50-op window into a single,
 * independently testable unit — with no tree traversal on the hot path.
 *
 * <h2>How each feature is measured</h2>
 * <ul>
 *   <li><b>op mix</b> — three exponentially decayed counters (add / remove / search).
 *       Each op decays all three by {@code decay = 1 - 1/W} and bumps the one that
 *       fired, so {@code readFraction} is the search share of the decayed window.</li>
 *   <li><b>access skew</b> — a Count-Min-style sketch ({@code d} rows × {@code w}
 *       columns) with <em>per-bucket lazy</em> exponential decay (only the {@code d}
 *       touched counters are updated per op, so ingest stays O(d)). At snapshot the
 *       per-row Simpson concentration {@code HHI = Σ pᵢ²} is computed, the least
 *       collision-biased row is taken ({@code min}, CM-style), and the uniform floor
 *       {@code 1/w} is removed: {@code skew = (HHI − 1/w)/(1 − 1/w)}. One hot key ⇒
 *       {@code HHI = 1 ⇒ skew = 1}; many keys spread evenly ⇒ {@code HHI ≈ 1/w ⇒
 *       skew ≈ 0}.</li>
 *   <li><b>meanSearchDepth</b> — EWMA of the path length reported per lookup.</li>
 *   <li><b>rotationsPerWrite</b> — EWMA of rotations reported per mutating op.</li>
 *   <li><b>size / growthRate</b> — {@code size} tracks add/remove deltas; growth is an
 *       EWMA of the per-op net size change scaled to the effective window
 *       ({@code growthRate ≈ Δsize per W ops}).</li>
 * </ul>
 *
 * <p>Memory is fixed at {@code d × w} counters plus a handful of scalars, independent
 * of tree size or stream length; the lazy decay keeps every counter bounded by
 * {@code 1/(1−decay) = W} so nothing overflows. Not thread-safe by design — see the
 * single-writer contract on {@link WorkloadMonitor}.</p>
 */
public final class RollingWorkloadMonitor implements WorkloadMonitor {

    // ── Configuration ───────────────────────────────────────────────────────────
    private final int    windowOps;   // W — effective rolling window, in ops
    private final int    rows;        // d — sketch hash functions
    private final int    cols;        // w — sketch columns per row
    private final double decay;       // 1 - 1/W, the per-op retention factor
    private final double alpha;       // 2/(W+1), EWMA smoothing for depth/rot/growth

    private static final int SEED_BASE = 0x9E3779B1; // golden-ratio odd constant

    // ── Op-mix (decayed counters) ────────────────────────────────────────────────
    private double addD;
    private double removeD;
    private double searchD;

    // ── Access-skew sketch (per-bucket lazy decay) ───────────────────────────────
    private final double[][] cnt;     // decayed weight as of lastOp[r][c]
    private final long[][]   lastOp;  // op-clock value at last update of [r][c]
    private long opClock;             // monotonic op counter (drives lazy decay)

    // ── Scalar EWMAs and size ────────────────────────────────────────────────────
    private double depthEwma;
    private boolean hasDepth;
    private double rotEwma;
    private boolean hasRot;
    private double growthEwma;        // per-op net size change, EWMA
    private long   liveSize;

    // ── Constructors ─────────────────────────────────────────────────────────────

    /** Defaults: a 4096-op window and a 4×256 skew sketch (DESIGN §3.1: "4–16k"). */
    public RollingWorkloadMonitor() { this(4096, 4, 256); }

    /** As {@link #RollingWorkloadMonitor()} with a custom window. */
    public RollingWorkloadMonitor(int windowOps) { this(windowOps, 4, 256); }

    /**
     * @param windowOps    effective rolling window in ops ({@code W ≥ 2})
     * @param sketchDepth  number of independent hash rows ({@code d ≥ 1})
     * @param sketchWidth  columns per row ({@code w ≥ 2}); the uniform skew floor is {@code 1/w}
     */
    public RollingWorkloadMonitor(int windowOps, int sketchDepth, int sketchWidth) {
        if (windowOps   < 2) throw new IllegalArgumentException("windowOps must be >= 2");
        if (sketchDepth < 1) throw new IllegalArgumentException("sketchDepth must be >= 1");
        if (sketchWidth < 2) throw new IllegalArgumentException("sketchWidth must be >= 2");
        this.windowOps = windowOps;
        this.rows      = sketchDepth;
        this.cols      = sketchWidth;
        this.decay     = 1.0 - 1.0 / windowOps;
        this.alpha     = 2.0 / (windowOps + 1.0);
        this.cnt       = new double[rows][cols];
        this.lastOp    = new long[rows][cols];
    }

    // ── Ingest ───────────────────────────────────────────────────────────────────

    @Override public void recordAdd(int keyHash, int rotations) {
        advance();
        addD += 1.0;
        touchSketch(keyHash);
        updateRotations(rotations);
        liveSize++;
        growthEwma += alpha * (1.0 - growthEwma);   // sample = +1
    }

    @Override public void recordRemove(int keyHash, int rotations) {
        advance();
        removeD += 1.0;
        touchSketch(keyHash);
        updateRotations(rotations);
        if (liveSize > 0) liveSize--;
        growthEwma += alpha * (-1.0 - growthEwma);  // sample = -1
    }

    @Override public void recordSearch(int keyHash, int depthTouched) {
        advance();
        searchD += 1.0;
        touchSketch(keyHash);
        if (hasDepth) depthEwma += alpha * (depthTouched - depthEwma);
        else { depthEwma = depthTouched; hasDepth = true; }
        growthEwma += alpha * (0.0 - growthEwma);   // sample = 0 (search doesn't resize)
    }

    /** Advance the op clock and decay the op-mix counters by one step. */
    private void advance() {
        opClock++;
        addD    *= decay;
        removeD *= decay;
        searchD *= decay;
    }

    private void updateRotations(int rotations) {
        if (hasRot) rotEwma += alpha * (rotations - rotEwma);
        else { rotEwma = rotations; hasRot = true; }
    }

    /** Lazily decay then increment the {@code d} sketch buckets for {@code keyHash}. */
    private void touchSketch(int keyHash) {
        for (int r = 0; r < rows; r++) {
            int b = bucket(keyHash, SEED_BASE * (r + 1), cols);
            long gap = opClock - lastOp[r][b];
            cnt[r][b] = cnt[r][b] * Math.pow(decay, gap) + 1.0;
            lastOp[r][b] = opClock;
        }
    }

    // ── Snapshot ─────────────────────────────────────────────────────────────────

    @Override public WorkloadFeatures snapshot() {
        double total = addD + removeD + searchD;
        double read  = total > 0 ? searchD / total : 0.0;
        double write = total > 0 ? (addD + removeD) / total : 0.0;
        return new WorkloadFeatures(
                read,
                write,
                accessSkew(),
                depthEwma,
                rotEwma,
                liveSize,
                growthEwma * windowOps);
    }

    /** Min-across-rows Simpson concentration with the {@code 1/w} uniform floor removed. */
    private double accessSkew() {
        double rawHHI = Double.POSITIVE_INFINITY;
        boolean any = false;
        for (int r = 0; r < rows; r++) {
            double t = 0.0, sumSq = 0.0;
            for (int c = 0; c < cols; c++) {
                double v = cnt[r][c];
                if (v == 0.0) continue;
                v *= Math.pow(decay, opClock - lastOp[r][c]); // bring to "now"
                t += v;
                sumSq += v * v;
            }
            if (t > 0.0) {
                any = true;
                double hhi = sumSq / (t * t);
                if (hhi < rawHHI) rawHHI = hhi;
            }
        }
        if (!any) return 0.0;
        double floor = 1.0 / cols;
        double skew = (rawHHI - floor) / (1.0 - floor);
        return skew < 0.0 ? 0.0 : (skew > 1.0 ? 1.0 : skew);
    }

    // ── Helpers / introspection ──────────────────────────────────────────────────

    /** Effective rolling window in ops ({@code W}). */
    public int effectiveWindow() { return windowOps; }

    /** Total ops observed (monotonic; for the controller's "too few ops" gate). */
    public long opsObserved() { return opClock; }

    private static int bucket(int keyHash, int seed, int w) {
        int h = keyHash ^ seed;
        h *= 0x9E3779B1;
        h ^= (h >>> 16);
        h *= 0x85EBCA77;
        h ^= (h >>> 13);
        return (h & 0x7fffffff) % w;
    }
}
