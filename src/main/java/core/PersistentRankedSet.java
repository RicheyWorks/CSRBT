package core;

import core.interfaces.RankedSet;

import java.util.Comparator;
import java.util.List;

/**
 * {@link RankedSet} adapter over the weight-balanced {@link PersistentTreeEngine} (ADR-005 P3):
 * the shape that lets the persistent engine join an {@code EnsembleOrderedSet} as a first-class
 * member — fan-out writes, primary serving, VERIFIED voting, quarantine/heal — without the
 * ensemble knowing it is not a strategy-driven {@code RedBlackTree}.
 *
 * <p>Semantics mirror {@link OrderedSet} method-for-method (the VERIFIED voting parity
 * requirement on {@link RankedSet}): boolean add/remove report effective change, {@code minimum}/
 * {@code maximum}/{@code median}/{@code percentile} return {@code null} on empty,
 * {@code successor}/{@code predecessor} throw on an absent argument and return {@code null} at
 * the extremes, and {@code select}/{@code rank} throw the same exceptions the order-statistics
 * walks do. The write meters time the engine calls exactly as {@code OrderedSet}'s do.</p>
 *
 * <p>Concurrency is inherited, not added: the engine's readers are wait-free by construction, so
 * a member backed by this adapter is the one kind whose reads need no guard at all — under
 * READ_REPLICA its epoch machinery is simply belt over suspenders.</p>
 */
public final class PersistentRankedSet<K> implements RankedSet<K> {

    /** Coarse per-node footprint: 4-field immutable node + a boxed key (see RankedSet docs). */
    private static final long NODE_BYTES = 56L;

    private final PersistentTreeEngine<K> engine;
    private final Comparator<? super K> keyOrder;

    private long totalInsertTime = 0, totalDeleteTime = 0;
    private int insertCount = 0, deleteCount = 0;

    public PersistentRankedSet(Comparator<? super K> keyOrder) {
        if (keyOrder == null) throw new IllegalArgumentException("keyOrder cannot be null");
        this.keyOrder = keyOrder;
        this.engine = new PersistentTreeEngine<>(keyOrder);
    }

    /** Convenience factory for naturally-ordered {@link Comparable} keys. */
    public static <K extends Comparable<? super K>> PersistentRankedSet<K> withNaturalOrder() {
        return new PersistentRankedSet<>(Comparator.naturalOrder());
    }

    /** The backing engine — for snapshots and diagnostics; mutate only through this adapter. */
    public PersistentTreeEngine<K> engine() { return engine; }

    // -- OrderedCollection --

    @Override
    public boolean add(K value) {
        int before = engine.size();
        long start = System.nanoTime();
        engine.add(value);
        boolean changed = engine.size() != before;
        if (changed) {
            totalInsertTime += System.nanoTime() - start;
            insertCount++;
        }
        return changed;
    }

    @Override
    public boolean remove(K value) {
        int before = engine.size();
        long start = System.nanoTime();
        engine.remove(value);
        boolean changed = engine.size() != before;
        if (changed) {
            totalDeleteTime += System.nanoTime() - start;
            deleteCount++;
        }
        return changed;
    }

    @Override public boolean contains(K value) { return engine.contains(value); }
    @Override public int size()                { return engine.size(); }
    @Override public List<K> inOrder()         { return engine.inOrder(); }
    @Override public void clear()              { engine.clear(); }

    // -- Order statistics (OrderedSet parity) --

    @Override public K select(int rank)  { return engine.select(rank); }
    @Override public int rank(K value)   { return engine.rank(value); }

    @Override
    public K successor(K value) {
        int r = engine.rank(value);                    // throws if absent, like OrderedSet
        return r < engine.size() ? engine.select(r + 1) : null;
    }

    @Override
    public K predecessor(K value) {
        int r = engine.rank(value);
        return r > 1 ? engine.select(r - 1) : null;
    }

    @Override public K minimum() { return isEmpty() ? null : engine.select(1); }
    @Override public K maximum() { return isEmpty() ? null : engine.select(engine.size()); }
    @Override public K median()  { return isEmpty() ? null : engine.select((engine.size() + 1) / 2); }

    @Override
    public K percentile(int pct) {
        int n = engine.size();
        if (n == 0) return null;
        int rank = Math.max(1, Math.min(n, (int) Math.ceil(pct / 100.0 * n)));
        return engine.select(rank);
    }

    @Override public int countInRange(K lo, K hi)   { return engine.countInRange(lo, hi); }
    @Override public List<K> rangeQuery(K lo, K hi) { return engine.rangeQuery(lo, hi); }

    // -- Meters & hooks --

    @Override public Comparator<? super K> comparator() { return keyOrder; }

    @Override
    public double avgInsertTimeMs() {
        return insertCount == 0 ? 0 : (totalInsertTime / 1_000_000.0) / insertCount;
    }

    @Override
    public double avgDeleteTimeMs() {
        return deleteCount == 0 ? 0 : (totalDeleteTime / 1_000_000.0) / deleteCount;
    }

    @Override public int height() { return engine.height(); }

    @Override public List<String> validateStructure() { return engine.validateInvariants(); }

    @Override public long estimatedMemoryBytes() { return (long) size() * NODE_BYTES; }

    @Override
    public String toString() {
        return "PersistentRankedSet[n=" + size() + "]";
    }
}
