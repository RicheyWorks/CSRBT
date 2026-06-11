package io.github.richeyworks.csrbt.adapter;

import io.github.richeyworks.csrbt.OrderedSet;

import java.util.AbstractSet;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Iterator;
import java.util.List;
import java.util.NavigableSet;
import java.util.NoSuchElementException;
import java.util.Objects;

/**
 * {@link NavigableSet} adapter over {@link OrderedSet} (ADR-009 P2) — the drop-in face for
 * code written against {@code java.util.NavigableSet}/{@code TreeSet}.
 *
 * <p>Navigation rides the order-statistics machinery the engine already funds:
 * {@code floor(x)} is "select the number of keys {@code <= x}", {@code ceiling}/{@code lower}/
 * {@code higher} are the same walk with the boundary nudged — all O(log n), no new engine
 * surface. Iteration is a torn-read-free snapshot (ADR-004 R1 semantics, like
 * {@code inOrder()}): weakly consistent, never throws {@code ConcurrentModificationException}.</p>
 *
 * <p><b>Views are deliberately read-only (the ADR's honesty clause):</b> {@code subSet}/
 * {@code headSet}/{@code tailSet}/{@code descendingSet} navigate, iterate, and count
 * correctly, but every mutator on a view throws {@link UnsupportedOperationException} with
 * instructions to mutate the base set — sub-range write-through is where {@code NavigableSet}
 * adapters traditionally rot, so this one refuses loudly instead of behaving subtly wrong.
 * The base adapter itself is fully mutable (add/remove/clear/pollFirst/pollLast/
 * iterator.remove all delegate).</p>
 *
 * <p>{@link #comparator()} always returns the base set's comparator, including for natural
 * ordering ({@code TreeSet} returns {@code null} there; returning the comparator is equally
 * contract-legal and more informative). Null elements are rejected with
 * {@link NullPointerException}, like {@code TreeSet} with natural ordering.</p>
 */
public final class NavigableOrderedSet<K> extends AbstractSet<K> implements NavigableSet<K> {

    private final OrderedSet<K> set;

    public NavigableOrderedSet(OrderedSet<K> set) {
        this.set = Objects.requireNonNull(set, "set cannot be null");
    }

    /** The backing {@link OrderedSet} — the mutation point for every read-only view. */
    public OrderedSet<K> base() { return set; }

    // ── Counting helpers (the whole adapter is these two + select) ───────────────

    /** Keys {@code <= key} (0 on empty; O(log n) via countInRange from the minimum). */
    private int countAtMost(K key) {
        if (set.isEmpty()) return 0;
        return set.countInRange(set.minimum(), key);   // lo > hi counts 0, so key < min is free
    }

    /** Keys {@code < key}. */
    private int countLess(K key) {
        return countAtMost(key) - (set.contains(key) ? 1 : 0);
    }

    int countUpTo(K key, boolean inclusive) {          // package: views size themselves with this
        return inclusive ? countAtMost(key) : countLess(key);
    }

    // ── Set ───────────────────────────────────────────────────────────────────────

    @Override public int size() { return set.size(); }
    @Override public boolean isEmpty() { return set.isEmpty(); }

    @Override
    @SuppressWarnings("unchecked")
    public boolean contains(Object o) {
        Objects.requireNonNull(o);
        return set.contains((K) o);
    }

    @Override
    public boolean add(K k) {
        Objects.requireNonNull(k);
        return set.add(k);
    }

    @Override
    @SuppressWarnings("unchecked")
    public boolean remove(Object o) {
        Objects.requireNonNull(o);
        return set.remove((K) o);
    }

    @Override public void clear() { set.clear(); }

    @Override
    public Iterator<K> iterator() {
        return new SnapshotIterator(set.inOrder());
    }

    /** Snapshot iterator; {@code remove()} delegates to the live base set. */
    private final class SnapshotIterator implements Iterator<K> {
        private final Iterator<K> it;
        private K last;
        SnapshotIterator(List<K> snapshot) { this.it = snapshot.iterator(); }
        @Override public boolean hasNext() { return it.hasNext(); }
        @Override public K next() { return last = it.next(); }
        @Override public void remove() {
            if (last == null) throw new IllegalStateException("next() not called");
            set.remove(last);
            last = null;
        }
    }

    // ── SortedSet ─────────────────────────────────────────────────────────────────

    @Override public Comparator<? super K> comparator() { return set.comparator(); }

    @Override
    public K first() {
        if (set.isEmpty()) throw new NoSuchElementException("empty set");
        return set.minimum();
    }

    @Override
    public K last() {
        if (set.isEmpty()) throw new NoSuchElementException("empty set");
        return set.maximum();
    }

    // ── NavigableSet navigation ───────────────────────────────────────────────────

    @Override
    public K lower(K k) {                              // greatest key < k
        Objects.requireNonNull(k);
        int c = countLess(k);
        return c > 0 ? set.select(c) : null;
    }

    @Override
    public K floor(K k) {                              // greatest key <= k
        Objects.requireNonNull(k);
        int c = countAtMost(k);
        return c > 0 ? set.select(c) : null;
    }

    @Override
    public K ceiling(K k) {                            // least key >= k
        Objects.requireNonNull(k);
        int c = countLess(k);
        return c < set.size() ? set.select(c + 1) : null;
    }

    @Override
    public K higher(K k) {                             // least key > k
        Objects.requireNonNull(k);
        int c = countAtMost(k);
        return c < set.size() ? set.select(c + 1) : null;
    }

    @Override
    public K pollFirst() {
        if (set.isEmpty()) return null;
        K k = set.minimum();
        set.remove(k);
        return k;
    }

    @Override
    public K pollLast() {
        if (set.isEmpty()) return null;
        K k = set.maximum();
        set.remove(k);
        return k;
    }

    // ── Views ─────────────────────────────────────────────────────────────────────

    @Override
    public Iterator<K> descendingIterator() {
        List<K> snap = new ArrayList<>(set.inOrder());
        Collections.reverse(snap);
        return Collections.unmodifiableList(snap).iterator();
    }

    @Override public NavigableSet<K> descendingSet() { return new Desc<>(this); }

    @Override
    public NavigableSet<K> subSet(K from, boolean fromInc, K to, boolean toInc) {
        Objects.requireNonNull(from);
        Objects.requireNonNull(to);
        if (set.comparator().compare(from, to) > 0) {
            throw new IllegalArgumentException("fromElement > toElement");
        }
        return new Range<>(this, from, fromInc, to, toInc);
    }

    @Override
    public NavigableSet<K> headSet(K to, boolean inclusive) {
        Objects.requireNonNull(to);
        return new Range<>(this, null, false, to, inclusive);
    }

    @Override
    public NavigableSet<K> tailSet(K from, boolean inclusive) {
        Objects.requireNonNull(from);
        return new Range<>(this, from, inclusive, null, false);
    }

    @Override public NavigableSet<K> subSet(K from, K to) { return subSet(from, true, to, false); }
    @Override public NavigableSet<K> headSet(K to)        { return headSet(to, false); }
    @Override public NavigableSet<K> tailSet(K from)      { return tailSet(from, true); }

    // ── Range view (read-only; ADR-009 P2 honesty clause) ─────────────────────────

    private static final class Range<K> extends AbstractSet<K> implements NavigableSet<K> {

        private static final String READ_ONLY =
                "read-only view (ADR-009 P2): mutate the base NavigableOrderedSet instead";

        private final NavigableOrderedSet<K> b;
        private final K lo, hi;                        // null = unbounded on that side
        private final boolean loInc, hiInc;

        Range(NavigableOrderedSet<K> b, K lo, boolean loInc, K hi, boolean hiInc) {
            this.b = b;
            this.lo = lo; this.loInc = loInc;
            this.hi = hi; this.hiInc = hiInc;
        }

        private int cmp(K a, K c) { return b.set.comparator().compare(a, c); }

        private boolean aboveLow(K k) {
            if (lo == null) return true;
            int c = cmp(k, lo);
            return loInc ? c >= 0 : c > 0;
        }

        private boolean belowHigh(K k) {
            if (hi == null) return true;
            int c = cmp(k, hi);
            return hiInc ? c <= 0 : c < 0;
        }

        private boolean inRange(K k) { return aboveLow(k) && belowHigh(k); }

        @Override
        public int size() {
            int upTo   = hi == null ? b.size() : b.countUpTo(hi, hiInc);
            int before = lo == null ? 0        : b.countUpTo(lo, !loInc);
            return Math.max(0, upTo - before);
        }

        @Override public boolean isEmpty() { return size() == 0; }

        @Override
        @SuppressWarnings("unchecked")
        public boolean contains(Object o) {
            Objects.requireNonNull(o);
            K k = (K) o;
            return inRange(k) && b.set.contains(k);
        }

        private List<K> snapshot() {
            if (b.set.isEmpty()) return List.of();
            K loEff = lo != null ? lo : b.set.minimum();
            K hiEff = hi != null ? hi : b.set.maximum();
            if (cmp(loEff, hiEff) > 0) return List.of();
            List<K> keys = b.set.rangeQuery(loEff, hiEff);     // inclusive both ends
            List<K> out = new ArrayList<>(keys.size());
            for (K k : keys) if (inRange(k)) out.add(k);
            return out;
        }

        @Override public Iterator<K> iterator() {
            return Collections.unmodifiableList(snapshot()).iterator();
        }

        @Override public Iterator<K> descendingIterator() {
            List<K> snap = new ArrayList<>(snapshot());
            Collections.reverse(snap);
            return Collections.unmodifiableList(snap).iterator();
        }

        @Override public Comparator<? super K> comparator() { return b.comparator(); }

        @Override
        public K first() {
            K k = lo == null ? (b.isEmpty() ? null : b.first())
                             : (loInc ? b.ceiling(lo) : b.higher(lo));
            if (k == null || !belowHigh(k)) throw new NoSuchElementException("empty view");
            return k;
        }

        @Override
        public K last() {
            K k = hi == null ? (b.isEmpty() ? null : b.last())
                             : (hiInc ? b.floor(hi) : b.lower(hi));
            if (k == null || !aboveLow(k)) throw new NoSuchElementException("empty view");
            return k;
        }

        private K firstOrNull() { try { return first(); } catch (NoSuchElementException e) { return null; } }
        private K lastOrNull()  { try { return last();  } catch (NoSuchElementException e) { return null; } }

        @Override
        public K lower(K k) {
            Objects.requireNonNull(k);
            K r = b.lower(k);
            if (r == null) return null;
            if (!belowHigh(r)) r = lastOrNull();       // largest in view is still < k here
            return (r != null && inRange(r)) ? r : null;
        }

        @Override
        public K floor(K k) {
            Objects.requireNonNull(k);
            K r = b.floor(k);
            if (r == null) return null;
            if (!belowHigh(r)) r = lastOrNull();
            return (r != null && inRange(r)) ? r : null;
        }

        @Override
        public K ceiling(K k) {
            Objects.requireNonNull(k);
            K r = b.ceiling(k);
            if (r == null) return null;
            if (!aboveLow(r)) r = firstOrNull();       // smallest in view is still > k here
            return (r != null && inRange(r)) ? r : null;
        }

        @Override
        public K higher(K k) {
            Objects.requireNonNull(k);
            K r = b.higher(k);
            if (r == null) return null;
            if (!aboveLow(r)) r = firstOrNull();
            return (r != null && inRange(r)) ? r : null;
        }

        // Mutators: refuse loudly rather than rot quietly.
        @Override public boolean add(K k)        { throw new UnsupportedOperationException(READ_ONLY); }
        @Override public boolean remove(Object o){ throw new UnsupportedOperationException(READ_ONLY); }
        @Override public void clear()            { throw new UnsupportedOperationException(READ_ONLY); }
        @Override public K pollFirst()           { throw new UnsupportedOperationException(READ_ONLY); }
        @Override public K pollLast()            { throw new UnsupportedOperationException(READ_ONLY); }

        @Override public NavigableSet<K> descendingSet() { return new Desc<>(this); }

        @Override
        public NavigableSet<K> subSet(K from, boolean fromInc, K to, boolean toInc) {
            Objects.requireNonNull(from);
            Objects.requireNonNull(to);
            if (cmp(from, to) > 0) throw new IllegalArgumentException("fromElement > toElement");
            if (!inRangeForBound(from) || !inRangeForBound(to)) {
                throw new IllegalArgumentException("sub-range bounds outside view range");
            }
            return new Range<>(b, from, fromInc, to, toInc);
        }

        /** Bound checks admit the view's own endpoints, like {@code TreeSet} sub-views. */
        private boolean inRangeForBound(K k) {
            boolean okLow  = lo == null || cmp(k, lo) >= 0;
            boolean okHigh = hi == null || cmp(k, hi) <= 0;
            return okLow && okHigh;
        }

        @Override
        public NavigableSet<K> headSet(K to, boolean inclusive) {
            Objects.requireNonNull(to);
            if (!inRangeForBound(to)) throw new IllegalArgumentException("toElement outside view range");
            return new Range<>(b, lo, loInc, to, inclusive);
        }

        @Override
        public NavigableSet<K> tailSet(K from, boolean inclusive) {
            Objects.requireNonNull(from);
            if (!inRangeForBound(from)) throw new IllegalArgumentException("fromElement outside view range");
            return new Range<>(b, from, inclusive, hi, hiInc);
        }

        @Override public NavigableSet<K> subSet(K from, K to) { return subSet(from, true, to, false); }
        @Override public NavigableSet<K> headSet(K to)        { return headSet(to, false); }
        @Override public NavigableSet<K> tailSet(K from)      { return tailSet(from, true); }
    }

    // ── Descending view (read-only wrapper over any ascending view) ───────────────

    private static final class Desc<K> extends AbstractSet<K> implements NavigableSet<K> {

        private static final String READ_ONLY =
                "read-only view (ADR-009 P2): mutate the base NavigableOrderedSet instead";

        private final NavigableSet<K> asc;

        Desc(NavigableSet<K> asc) { this.asc = asc; }

        @Override public int size() { return asc.size(); }
        @Override public boolean isEmpty() { return asc.isEmpty(); }
        @Override public boolean contains(Object o) { return asc.contains(o); }
        @Override public Iterator<K> iterator() { return asc.descendingIterator(); }
        @Override public Iterator<K> descendingIterator() { return asc.iterator(); }
        @Override public NavigableSet<K> descendingSet() { return asc; }

        @Override public Comparator<? super K> comparator() {
            return Collections.reverseOrder(asc.comparator());
        }

        @Override public K first() { return asc.last(); }
        @Override public K last()  { return asc.first(); }

        @Override public K lower(K k)   { return asc.higher(k); }
        @Override public K floor(K k)   { return asc.ceiling(k); }
        @Override public K ceiling(K k) { return asc.floor(k); }
        @Override public K higher(K k)  { return asc.lower(k); }

        @Override public boolean add(K k)         { throw new UnsupportedOperationException(READ_ONLY); }
        @Override public boolean remove(Object o) { throw new UnsupportedOperationException(READ_ONLY); }
        @Override public void clear()             { throw new UnsupportedOperationException(READ_ONLY); }
        @Override public K pollFirst()            { throw new UnsupportedOperationException(READ_ONLY); }
        @Override public K pollLast()             { throw new UnsupportedOperationException(READ_ONLY); }

        @Override
        public NavigableSet<K> subSet(K from, boolean fromInc, K to, boolean toInc) {
            return new Desc<>(asc.subSet(to, toInc, from, fromInc));
        }

        @Override
        public NavigableSet<K> headSet(K to, boolean inclusive) {
            return new Desc<>(asc.tailSet(to, inclusive));
        }

        @Override
        public NavigableSet<K> tailSet(K from, boolean inclusive) {
            return new Desc<>(asc.headSet(from, inclusive));
        }

        @Override public NavigableSet<K> subSet(K from, K to) { return subSet(from, true, to, false); }
        @Override public NavigableSet<K> headSet(K to)        { return headSet(to, false); }
        @Override public NavigableSet<K> tailSet(K from)      { return tailSet(from, true); }
    }
}
