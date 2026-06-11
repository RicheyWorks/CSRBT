package io.github.richeyworks.csrbt.interfaces;

import java.util.Comparator;
import java.util.List;

/**
 * The full surface an ensemble member's backing set must offer (ADR-005 P3): the
 * {@link OrderedCollection} contract plus {@code OrderedSet}'s order-statistics methods, the
 * realized write meters the controller logs, and two structural hooks (height, self-validation)
 * with conservative defaults.
 *
 * <p>This is the seam that lets {@link io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet} accept members that are
 * <em>not</em> strategy-driven {@code RedBlackTree}s — e.g. the weight-balanced persistent engine
 * via {@link io.github.richeyworks.csrbt.PersistentRankedSet}. {@link io.github.richeyworks.csrbt.OrderedSet} implements it with its existing
 * methods (no behavior change); the ensemble's fan-out, voting, healing, and promotion all speak
 * this interface and nothing more. Strategy-specific machinery — {@code getStrategy()},
 * {@code getEngine()}, {@code StrategyHealthCheck} — deliberately stays off this contract; the
 * controller reaches it only through {@code EnsembleMember.orderedSet()} after checking
 * {@code isStrategyBacked()}.</p>
 *
 * <p><b>Voting parity:</b> in VERIFIED mode answers are compared across members with
 * {@code Objects.equals}, so every implementation must match {@code OrderedSet}'s semantics
 * exactly — the same null returns on empty sets, the same exceptions on absent keys and
 * out-of-range ranks (see each method's contract).</p>
 */
public interface RankedSet<K> extends OrderedCollection<K> {

    // -- Order statistics (OrderedSet parity; positional arguments are 1-indexed) --

    /** ith smallest key. @throws IndexOutOfBoundsException if out of [1,size]. */
    K select(int rank);

    /** 1-indexed rank of a key. @throws java.util.NoSuchElementException if absent. */
    int rank(K value);

    /** Smallest key strictly greater than {@code value}, or {@code null} if none. @throws if absent. */
    K successor(K value);

    /** Largest key strictly less than {@code value}, or {@code null} if none. @throws if absent. */
    K predecessor(K value);

    /** Smallest key, or {@code null} if empty. */
    K minimum();

    /** Largest key, or {@code null} if empty. */
    K maximum();

    /** Lower median, or {@code null} if empty. */
    K median();

    /** kth-percentile key (0-100), or {@code null} if empty. */
    K percentile(int pct);

    /** Count of keys in the closed range [lo, hi] (0 if lo &gt; hi). */
    int countInRange(K lo, K hi);

    /** Keys in [lo, hi], ascending (empty if lo &gt; hi). */
    List<K> rangeQuery(K lo, K hi);

    // -- Meters & ordering authority --

    /** The set's key-ordering authority. */
    Comparator<? super K> comparator();

    /** Mean realized insert latency (ms) since construction; 0 with no inserts. */
    double avgInsertTimeMs();

    /** Mean realized delete latency (ms) since construction; 0 with no deletes. */
    double avgDeleteTimeMs();

    // -- Structural hooks (defaults for implementations without cheap answers) --

    /**
     * Tree height (empty = 0), or {@code -1} when the implementation does not expose one.
     * The controller's meters line prints whatever this returns.
     */
    default int height() { return -1; }

    /**
     * Implementation-specific structural self-check: an empty list when healthy, else one message
     * per violation. Used by the ensemble health pass for members whose structure
     * {@code StrategyHealthCheck} cannot see (non-strategy engines). The default reports nothing —
     * strategy-backed sets are validated externally instead.
     */
    default List<String> validateStructure() { return List.of(); }

    /**
     * Estimated live memory footprint in bytes (ADR-003 "Revisit": memory ceilings). A coarse
     * model — node count x a per-node constant — not a measurement; useful for trend and ceiling
     * checks, not accounting. The default assumes the pointer-based {@code TreeNode1} family
     * (~96 bytes/node with its parent/color/size/tag/augment slots, plus a boxed key).
     */
    default long estimatedMemoryBytes() { return (long) size() * 96L; }
}
