package core.control;

/**
 * Immutable summary of the live workload — the <em>only</em> thing the
 * {@link StrategyScorer} (ADR-002 step 6, Phase B) is allowed to see, which is what
 * lets the scorer be a pure function and therefore unit-testable with hand-built
 * vectors. Produced by {@link WorkloadMonitor#snapshot()} on the control-plane
 * cadence (DESIGN-adaptive-engine.md §9.2).
 *
 * <p>All fields are derived by an O(1)-per-op monitor from a rolling, exponentially
 * decayed view of the op stream; none requires a tree traversal. The fractions are
 * complementary ({@code readFraction + writeFraction == 1} whenever any op has been
 * observed) and {@code accessSkew} is normalized so that {@code 0} is a uniform,
 * locality-free workload and {@code 1} is a single hot key.</p>
 *
 * @param readFraction      searches / total ops in the decayed window, in [0,1]
 * @param writeFraction     (adds + removes) / total ops in the decayed window, in [0,1]
 * @param accessSkew        hot-key concentration, in [0,1] (0 = uniform, 1 = one hot key)
 * @param meanSearchDepth   EWMA of nodes touched per lookup (how good the current shape is)
 * @param rotationsPerWrite EWMA of rotations incurred per mutating op (structural churn)
 * @param size              current element count as seen by the monitor
 * @param growthRate        expected net size change (keys) per effective window
 */
public record WorkloadFeatures(
        double readFraction,
        double writeFraction,
        double accessSkew,
        double meanSearchDepth,
        double rotationsPerWrite,
        long   size,
        double growthRate
) {

    /** The feature vector for a monitor that has observed no operations yet. */
    public static final WorkloadFeatures EMPTY =
            new WorkloadFeatures(0.0, 0.0, 0.0, 0.0, 0.0, 0L, 0.0);

    /**
     * Renders the vector in the field order used by the {@code event=morph_eval}
     * observability line (DESIGN §12), so the eventual {@code MorphController} can
     * splice it straight into the log.
     */
    @Override
    public String toString() {
        return String.format(
                "read=%.4f write=%.4f skew=%.4f depth=%.4f rotPerWrite=%.4f n=%d growth=%.4f",
                readFraction, writeFraction, accessSkew, meanSearchDepth,
                rotationsPerWrite, size, growthRate);
    }
}
