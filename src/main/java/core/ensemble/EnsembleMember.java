package core.ensemble;

import core.OrderedSet;
import core.interfaces.RankedSet;

import java.util.concurrent.atomic.AtomicInteger;

/**
 * One member of an {@link EnsembleOrderedSet}: a backing set over an exact copy of the logical
 * key set, plus the lifecycle state the ensemble manages (ADR-003).
 *
 * <p><b>ADR-005 P3:</b> the backing set is any {@link RankedSet} — the strategy-driven
 * {@link OrderedSet} as always, or an ENGINE-tier set such as {@code PersistentRankedSet} over
 * the weight-balanced persistent engine. The ensemble's fan-out, voting, healing, and promotion
 * speak {@code RankedSet} only; the controller's strategy-specific machinery (StrategyId
 * indexing, {@code StrategyHealthCheck}) applies only to {@linkplain #isStrategyBacked()
 * strategy-backed} members and reaches the concrete facade through {@link #orderedSet()}.</p>
 */
public final class EnsembleMember<K> {

    /** Lifecycle state. E1 only uses {@code ACTIVE}; the others are wired in E3. */
    public enum State { ACTIVE, QUARANTINED, RETIRED }

    private final RankedSet<K> set;
    private final String strategyName;
    private volatile State state = State.ACTIVE;
    private volatile boolean exact = true;

    /**
     * Epoch reader count (ADR-004 R2, READ_REPLICA). A reader increments before verifying this
     * member is still the serving primary and reads only on success; the writer flips the
     * serving pointer away and then drains this count to zero before mutating. The invariant —
     * a member is mutated only while it is not primary AND its count is zero (modulo transient
     * holders who verified, failed, and are exiting without touching the tree) — is what makes
     * replica reads safe without the member's read lock ever being contended.
     */
    private final AtomicInteger epochReaders = new AtomicInteger();

    EnsembleMember(OrderedSet<K> set) {
        this(set, set.getStrategy().getClass().getSimpleName());
    }

    /** ADR-005 P3: any {@link RankedSet} backing, labeled (engine members have no strategy). */
    EnsembleMember(RankedSet<K> set, String label) {
        this.set = set;
        this.strategyName = label;
    }

    /** The backing set — an exact mirror of the logical set while {@code ACTIVE}. */
    public RankedSet<K> set() { return set; }

    /** True when the backing set is a strategy-driven {@link OrderedSet} (the RB-engine family). */
    public boolean isStrategyBacked() { return set instanceof OrderedSet; }

    /**
     * The backing {@link OrderedSet} for strategy-specific machinery (engine/strategy access,
     * {@code StrategyHealthCheck}). @throws IllegalStateException for ENGINE-tier members —
     * check {@link #isStrategyBacked()} first.
     */
    public OrderedSet<K> orderedSet() {
        if (!(set instanceof OrderedSet)) {
            throw new IllegalStateException(strategyName + " is an engine-tier member with no strategy facade");
        }
        return (OrderedSet<K>) set;
    }

    /** Label for the backing structure, e.g. {@code "SplayStrategy"} or {@code "PersistentTreeEngine"}. */
    public String strategyName() { return strategyName; }

    public State state() { return state; }

    public boolean isActive() { return state == State.ACTIVE; }

    /**
     * True while this member is an exact mirror of the logical set. Always true in MIRROR/VERIFIED
     * operation; in SAMPLED_SHADOW mode (E5) a member drops to inexact the first time a sampled-out
     * write skips it — and in REBUILD_SHADOW (ADR-003 Option C) on the first write after a rebuild —
     * and only an O(n) rebuild from the primary (heal, the cadence rebuild, or the sync-on-promote
     * catch-up) restores it. An inexact member never serves, fails over, or votes.
     */
    public boolean isExact() { return exact; }

    /** Package-private: the ensemble owns lifecycle transitions (E3). */
    void setState(State s) { this.state = s; }

    /** Package-private: the ensemble owns exactness (E5 sampled shadows / Option C rebuilds). */
    void setExact(boolean exact) { this.exact = exact; }

    // -- Epoch readers (ADR-004 R2) --

    void enterRead()      { epochReaders.getAndIncrement(); }
    void exitRead()       { epochReaders.getAndDecrement(); }
    int  activeReaders()  { return epochReaders.get(); }

    @Override
    public String toString() {
        return "EnsembleMember[" + strategyName + ", " + state + (exact ? "" : ", shadow")
                + ", n=" + set.size() + "]";
    }
}
