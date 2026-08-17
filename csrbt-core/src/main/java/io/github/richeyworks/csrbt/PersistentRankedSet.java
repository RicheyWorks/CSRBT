package io.github.richeyworks.csrbt;

import io.github.richeyworks.csrbt.interfaces.RankedSet;

import java.util.Comparator;
import java.util.List;
import java.util.concurrent.atomic.LongAdder;

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
 * READ_REPLICA its epoch machinery is simply belt over suspenders. Writes are the exception:
 * the engine reports change only as a size delta, and a delta read across two concurrent
 * mutators is not a delta at all (audit 2026-08-17, finding 13 — 4 threads x 20 000 adds
 * over-reported {@code true} by up to 42 %, and that boolean is what VERIFIED voting compares).
 * So the adapter's own {@code writeLock} makes each check-and-mutate atomic — one extra monitor
 * on top of the engine's, never held during a read — and the write meters are {@link LongAdder}s
 * so a concurrent {@link #avgInsertTimeMs()} sees consistent, non-torn totals.</p>
 */
public final class PersistentRankedSet<K> implements RankedSet<K> {

    /** Coarse per-node footprint: 4-field immutable node + a boxed key (see RankedSet docs). */
    private static final long NODE_BYTES = 56L;

    private final PersistentTreeEngine<K> engine;
    private final Comparator<? super K> keyOrder;

    /** Serializes this adapter's check-and-mutate pairs; never held across a read. */
    private final Object writeLock = new Object();

    private final LongAdder totalInsertTime = new LongAdder(), totalDeleteTime = new LongAdder();
    private final LongAdder insertCount = new LongAdder(), deleteCount = new LongAdder();

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

    /**
     * @return {@code true} iff this call is the one that inserted {@code value}. The engine
     *         publishes change only through its size, so the read-mutate-read triple runs under
     *         {@link #writeLock} — outside it, two concurrent inserters each see the other's
     *         delta and both claim the insert (finding 13).
     */
    @Override
    public boolean add(K value) {
        synchronized (writeLock) {
            int before = engine.size();
            long start = System.nanoTime();
            engine.add(value);
            long elapsed = System.nanoTime() - start;
            if (engine.size() == before) return false;
            totalInsertTime.add(elapsed);
            insertCount.increment();
            return true;
        }
    }

    /** @return {@code true} iff this call is the one that removed {@code value} (see {@link #add}). */
    @Override
    public boolean remove(K value) {
        synchronized (writeLock) {
            int before = engine.size();
            long start = System.nanoTime();
            engine.remove(value);
            long elapsed = System.nanoTime() - start;
            if (engine.size() == before) return false;
            totalDeleteTime.add(elapsed);
            deleteCount.increment();
            return true;
        }
    }

    @Override public boolean contains(K value) { return engine.contains(value); }
    @Override public int size()                { return engine.size(); }
    @Override public List<K> inOrder()         { return engine.inOrder(); }

    /** Under {@link #writeLock} too, so a concurrent add/remove still measures a true delta. */
    @Override public void clear() { synchronized (writeLock) { engine.clear(); } }

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
        long n = insertCount.sum();
        return n == 0 ? 0 : (totalInsertTime.sum() / 1_000_000.0) / n;
    }

    @Override
    public double avgDeleteTimeMs() {
        long n = deleteCount.sum();
        return n == 0 ? 0 : (totalDeleteTime.sum() / 1_000_000.0) / n;
    }

    @Override public int height() { return engine.height(); }

    @Override public List<String> validateStructure() { return engine.validateInvariants(); }

    @Override public long estimatedMemoryBytes() { return (long) size() * NODE_BYTES; }

    @Override
    public String toString() {
        return "PersistentRankedSet[n=" + size() + "]";
    }
}
