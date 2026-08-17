package io.github.richeyworks.csrbt.control;

/**
 * Control-plane ingest point: a cheap, bounded summary of "what is the data doing?"
 * (DESIGN-adaptive-engine.md §3.1 / §9.2). The data-plane facade pushes one tiny
 * event per operation; the monitor folds it into a rolling feature vector that the
 * {@link StrategyScorer} later reads via {@link #snapshot()}.
 *
 * <h2>Contract</h2>
 * <ul>
 *   <li><b>O(1) per op, bounded memory, no tree traversal.</b> Implementations must
 *       not do tree-wide work — that is exactly the per-op anti-pattern the engine
 *       was cleaned of (DESIGN §2).</li>
 *   <li><b>Key-agnostic.</b> Keys enter only as an {@code int} hash, so the monitor
 *       is independent of the engine's {@code <K>} type. Callers should pass a
 *       well-mixed hash (e.g. {@code Objects.hashCode(key)}); identical keys must map
 *       to identical hashes for skew detection to work.</li>
 *   <li><b>Single-writer.</b> Following the engine's concurrency model (DESIGN §4),
 *       implementations need not be thread-safe; record/snapshot are expected to run
 *       under the facade's single write lock.</li>
 *   <li><b>Effective mutations.</b> For {@link WorkloadFeatures#size()} accuracy, {@code recordAdd}/
 *       {@code recordRemove} should be called when a key is actually inserted/removed
 *       (not for no-op duplicate adds or absent removes). The op-mix, skew, depth and
 *       rotation features remain valid regardless.</li>
 * </ul>
 *
 * <p>The minimal three-method shape mirrors DESIGN §9.2; the {@code rotations}
 * arguments carry the per-write structural-churn signal the design feeds from the
 * engine's rotation counter, with no-rotation convenience overloads for callers that
 * do not track it.</p>
 */
public interface WorkloadMonitor {

    /**
     * Record an insertion of {@code keyHash} that incurred {@code rotations}
     * rebalancing rotations.
     */
    void recordAdd(int keyHash, int rotations);

    /**
     * Record a removal of {@code keyHash} that incurred {@code rotations}
     * rebalancing rotations.
     */
    void recordRemove(int keyHash, int rotations);

    /**
     * Record a lookup of {@code keyHash} that touched {@code depthTouched} nodes
     * (the path length walked), the primary signal for how good the current tree
     * shape is for this workload.
     */
    void recordSearch(int keyHash, int depthTouched);

    /** Cheap, immutable summary of the current decayed window (DESIGN §9.2). */
    WorkloadFeatures snapshot();

    // ── Convenience overloads matching the minimal DESIGN §9.2 signatures ────────

    /** Equivalent to {@link #recordAdd(int, int) recordAdd(keyHash, 0)}. */
    default void recordAdd(int keyHash) { recordAdd(keyHash, 0); }

    /** Equivalent to {@link #recordRemove(int, int) recordRemove(keyHash, 0)}. */
    default void recordRemove(int keyHash) { recordRemove(keyHash, 0); }
}
