package core.ensemble;

import core.OrderedSet;

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

    /** Package-private: the ensemble owns lifecycle transitions (E3). */
    void setState(State s) { this.state = s; }

    @Override
    public String toString() {
        return "EnsembleMember[" + strategyName + ", " + state + ", n=" + set.size() + "]";
    }
}
