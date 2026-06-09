package core.ensemble;

import core.OrderedSet;

import java.util.concurrent.atomic.AtomicInteger;

/**
 * One member of an {@link EnsembleOrderedSet}: a full strategy-backed {@link OrderedSet} over an
 * exact copy of the logical key set, plus the lifecycle state the ensemble manages (ADR-003).
 *
 * <p>Step E1 only uses {@link State#ACTIVE}. Health meters and {@code QUARANTINED}/{@code RETIRED}
 * transitions (quarantine + heal + failover) arrive in E2/E3; this class deliberately stays a thin
 * wrapper so the facade can be reasoned about on its own.</p>
 */
public final class EnsembleMember<K> {

    /** Lifecycle state. E1 only uses {@code ACTIVE}; the others are wired in E3. */
    public enum State { ACTIVE, QUARANTINED, RETIRED }

    private final OrderedSet<K> set;
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
        this.set = set;
        this.strategyName = set.getStrategy().getClass().getSimpleName();
    }

    /** The backing ordered set — an exact mirror of the logical set while {@code ACTIVE}. */
    public OrderedSet<K> set() { return set; }

    /** Class-name label for the backing strategy, e.g. {@code "SplayStrategy"}. */
    public String strategyName() { return strategyName; }

    public State state() { return state; }

    public boolean isActive() { return state == State.ACTIVE; }

    /**
     * True while this member is an exact mirror of the logical set. Always true in MIRROR/VERIFIED
     * operation; in SAMPLED_SHADOW mode (E5) a member drops to inexact the first time a sampled-out
     * write skips it, and only an O(n) rebuild from the primary (heal, or the sync-on-promote
     * catch-up) restores it. An inexact member never serves, fails over, or votes.
     */
    public boolean isExact() { return exact; }

    /** Package-private: the ensemble owns lifecycle transitions (E3). */
    void setState(State s) { this.state = s; }

    /** Package-private: the ensemble owns exactness (E5 sampled shadows). */
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
