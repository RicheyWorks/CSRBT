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
}
