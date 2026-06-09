package core.ensemble;

import core.OrderedSet;
import core.interfaces.OrderedCollection;
import core.strategy.TreeStrategy;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import java.util.function.Supplier;

/**
 * EnsembleOrderedSet — a drop-in {@link OrderedCollection} backed by several independent strategy
 * members kept in exact sync (MIRROR mode), the foundation of the multi-tree ensemble in ADR-003.
 *
 * <p><b>Step E1 (this class):</b> every effective {@code add}/{@code remove} fans out to all active
 * members so each is an exact copy of the logical set; reads (membership, order, size, and order
 * statistics) are served by a fixed {@code primary}. Because switching the serving member will be a
 * pointer swap, adaptation can later become O(1) instead of an O(n) morph — but the controller that
 * does the swapping (E2), per-member health/quarantine/failover (E3), and read-quorum N-version
 * voting (E4) are not here yet. The primary never changes in E1.</p>
 *
 * <p>Members share no mutable state, so the write fan-out is embarrassingly parallel; E1 keeps it
 * sequential under a single writer lock (linearizable logical set) and parallelizes in E5.</p>
 */
public final class EnsembleOrderedSet<K> implements OrderedCollection<K> {

    private final List<EnsembleMember<K>> members;
    private final Comparator<? super K> keyOrder;
    private final Object writeLock = new Object();
    private volatile EnsembleMember<K> primary;

    private EnsembleOrderedSet(List<EnsembleMember<K>> members, Comparator<? super K> keyOrder) {
        this.members = members;
        this.keyOrder = keyOrder;
        this.primary = members.get(0);
    }

    // ── Construction ────────────────────────────────────────────────────────────

    public static <K> Builder<K> builder(Comparator<? super K> keyOrder) {
        return new Builder<>(keyOrder);
    }

    /** Fluent builder. The first member added is the initial primary. */
    public static final class Builder<K> {
        private final Comparator<? super K> keyOrder;
        private final List<Supplier<? extends TreeStrategy<K>>> specs = new ArrayList<>();

        private Builder(Comparator<? super K> keyOrder) {
            this.keyOrder = Objects.requireNonNull(keyOrder, "keyOrder cannot be null");
        }

        /** Add a member backed by a fresh strategy from {@code strategy}. */
        public Builder<K> member(Supplier<? extends TreeStrategy<K>> strategy) {
            specs.add(Objects.requireNonNull(strategy, "strategy cannot be null"));
            return this;
        }

        public EnsembleOrderedSet<K> build() {
            if (specs.size() < 2) {
                throw new IllegalArgumentException("an ensemble needs at least two members");
            }
            List<EnsembleMember<K>> ms = new ArrayList<>(specs.size());
            for (Supplier<? extends TreeStrategy<K>> s : specs) {
                ms.add(new EnsembleMember<>(new OrderedSet<>(s.get(), keyOrder)));
            }
            return new EnsembleOrderedSet<>(ms, keyOrder);
        }
    }

    // ── Writes: fan out to every active member (sequential in E1) ────────────────

    @Override
    public boolean add(K value) {
        synchronized (writeLock) {
            boolean changed = false;
            for (EnsembleMember<K> m : members) {
                if (!m.isActive()) continue;
                boolean c = m.set().add(value);
                if (m == primary) changed = c;
            }
            return changed;
        }
    }

    @Override
    public boolean remove(K value) {
        synchronized (writeLock) {
            boolean changed = false;
            for (EnsembleMember<K> m : members) {
                if (!m.isActive()) continue;
                boolean c = m.set().remove(value);
                if (m == primary) changed = c;
            }
            return changed;
        }
    }

    @Override
    public void clear() {
        synchronized (writeLock) {
            for (EnsembleMember<K> m : members) {
                if (m.isActive()) m.set().clear();
            }
        }
    }

    // ── Reads: served by the primary ──────────────────────────────────────────────

    @Override public boolean contains(K value) { return primary.set().contains(value); }
    @Override public int size()                { return primary.set().size(); }
    @Override public List<K> inOrder()         { return primary.set().inOrder(); }
    @Override public boolean isEmpty()         { return primary.set().isEmpty(); }

    // ── Order statistics (drop-in parity with OrderedSet), served by the primary ──

    public K select(int rank)             { return primary.set().select(rank); }
    public int rank(K value)              { return primary.set().rank(value); }
    public K successor(K value)           { return primary.set().successor(value); }
    public K predecessor(K value)         { return primary.set().predecessor(value); }
    public K minimum()                    { return primary.set().minimum(); }
    public K maximum()                    { return primary.set().maximum(); }
    public K median()                     { return primary.set().median(); }
    public K percentile(int pct)          { return primary.set().percentile(pct); }
    public int countInRange(K lo, K hi)   { return primary.set().countInRange(lo, hi); }
    public List<K> rangeQuery(K lo, K hi) { return primary.set().rangeQuery(lo, hi); }

    // ── Promotion: the O(1) atomic primary swap (ADR-003 E2) ─────────────────────

    /**
     * Promote {@code member} to primary — make it the member that serves reads and order
     * statistics. Because every member already mirrors the logical set, this is a single
     * {@code volatile} pointer publish: <b>O(1)</b>, with no tree rebuild, no traversal, and
     * no copy. It is the payoff ADR-003 trades the mirror's write fan-out for — adaptation
     * becomes a pointer swap instead of {@code OrderedSet.setStrategy}'s O(n) build-aside.
     *
     * <p>Serialized on the same write lock as the fan-out, so a swap never interleaves with a
     * mutation. The incoming member must be a live ({@code ACTIVE}) member of this ensemble —
     * serving reads from a quarantined member (E3) would read from a set that is no longer a
     * faithful mirror.</p>
     *
     * @param member the member to serve reads from; must belong to this ensemble and be {@code ACTIVE}
     * @return {@code true} if the primary changed; {@code false} if {@code member} was already primary
     * @throws IllegalArgumentException if {@code member} is not part of this ensemble
     * @throws IllegalStateException    if {@code member} is not {@code ACTIVE}
     */
    public boolean promote(EnsembleMember<K> member) {
        Objects.requireNonNull(member, "member cannot be null");
        synchronized (writeLock) {
            if (!members.contains(member)) {
                throw new IllegalArgumentException("member is not part of this ensemble: " + member);
            }
            if (!member.isActive()) {
                throw new IllegalStateException("cannot promote a non-active member: " + member);
            }
            if (member == primary) return false;
            this.primary = member;   // volatile publish — readers observe the swap atomically
            return true;
        }
    }

    // ── Introspection ────────────────────────────────────────────────────────────

    /** The member currently serving reads. */
    public EnsembleMember<K> primary() { return primary; }

    /** All members, in insertion order, unmodifiable. */
    public List<EnsembleMember<K>> members() { return Collections.unmodifiableList(members); }

    public Comparator<? super K> comparator() { return keyOrder; }

    @Override
    public String toString() {
        return "EnsembleOrderedSet[primary=" + primary.strategyName()
                + ", members=" + members.size() + ", n=" + size() + "]";
    }

    // -- Health lifecycle: quarantine / heal / retire (ADR-003 E3) --

    /**
     * Drop {@code member} from serving and write fan-out by marking it {@code QUARANTINED}
     * (E1's fan-out already skips non-{@code ACTIVE} members). The serving primary cannot be
     * quarantined directly -- {@link #promote} a healthy member first (failover), then quarantine
     * the deposed one. Serialized on the write lock.
     *
     * @return {@code true} if the member moved to {@code QUARANTINED}; {@code false} if already retired
     * @throws IllegalStateException if {@code member} is the serving primary
     */
    public boolean quarantine(EnsembleMember<K> member) {
        Objects.requireNonNull(member, "member cannot be null");
        synchronized (writeLock) {
            if (!members.contains(member)) {
                throw new IllegalArgumentException("member is not part of this ensemble: " + member);
            }
            if (member == primary) {
                throw new IllegalStateException("cannot quarantine the serving primary; fail over first");
            }
            if (member.state() == EnsembleMember.State.RETIRED) return false;
            member.setState(EnsembleMember.State.QUARANTINED);
            return true;
        }
    }

    /**
     * Heal {@code member} by rebuilding its backing set from the <em>current primary</em>'s
     * contents and returning it to {@code ACTIVE} -- the recover step after a quarantine
     * (ADR-003 E3). The primary is the source of truth, so the healed member becomes an exact
     * mirror again under its own strategy. O(n) in the live size; {@code member} must not be the
     * primary. Serialized on the write lock.
     *
     * @return {@code true} if the member was rebuilt and reactivated; {@code false} if retired
     * @throws IllegalStateException if {@code member} is the serving primary
     */
    public boolean healFromPrimary(EnsembleMember<K> member) {
        Objects.requireNonNull(member, "member cannot be null");
        synchronized (writeLock) {
            if (!members.contains(member)) {
                throw new IllegalArgumentException("member is not part of this ensemble: " + member);
            }
            if (member == primary) {
                throw new IllegalStateException("cannot heal the primary from itself");
            }
            if (member.state() == EnsembleMember.State.RETIRED) return false;
            List<K> truth = primary.set().inOrder();   // source of truth
            OrderedSet<K> set = member.set();
            set.clear();
            for (K k : truth) set.add(k);
            member.setState(EnsembleMember.State.ACTIVE);
            return true;
        }
    }

    /**
     * Permanently remove {@code member} from service ({@code RETIRED}) -- used when a heal still
     * fails its health check. A retired member is never served, fanned to, or promoted. The
     * primary cannot be retired directly. Serialized on the write lock.
     *
     * @throws IllegalStateException if {@code member} is the serving primary
     */
    public boolean retire(EnsembleMember<K> member) {
        Objects.requireNonNull(member, "member cannot be null");
        synchronized (writeLock) {
            if (!members.contains(member)) {
                throw new IllegalArgumentException("member is not part of this ensemble: " + member);
            }
            if (member == primary) {
                throw new IllegalStateException("cannot retire the serving primary; fail over first");
            }
            member.setState(EnsembleMember.State.RETIRED);
            return true;
        }
    }
}
