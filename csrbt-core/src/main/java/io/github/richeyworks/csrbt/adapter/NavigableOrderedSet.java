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

    // ── Counting ─────────────────────────────────────────────────────────────────
    // ADR-021: every count is ONE guarded acquisition on the base set (views size
    // themselves with countBetween). The old compositions (countInRange-from-minimum,
    // then contains, then select) spanned multiple lock epochs, so a write landing
    // between them made read-only navigation throw or answer wrong under the
    // advertised concurrent-read model (deep-sweep audit 2026-08-12, D-1:
    // 399 exceptions / 1,870 contract violations in 3.7M calls).

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

    // first()/last()/pollFirst()/pollLast() each make ONE base-set call and branch on
    // its null result — the old isEmpty()-then-minimum() composition spanned two lock
    // epochs, so a writer emptying the set in between made first() return null
    // (SortedSet.first() must never return null; ADR-021 follow-up, 2026-08-14).

    @Override
    public K first() {
        K k = set.minimum();                           // null iff empty — one acquisition
        if (k == null) throw new NoSuchElementException("empty set");
        return k;
    }

    @Override
    public K last() {
        K k = set.maximum();
        if (k == null) throw new NoSuchElementException("empty set");
        return k;
    }

    // ── NavigableSet navigation ───────────────────────────────────────────────────

    // ADR-021: each navigation call is a single atomic descent on the base set —
    // no count/select composition, no lock-epoch gap for a writer to slip into.

    @Override
    public K lower(K k) {                              // greatest key < k
        Objects.requireNonNull(k);
        return set.lower(k);
    }

    @Override
    public K floor(K k) {                              // greatest key <= k
        Objects.requireNonNull(k);
        return set.floor(k);
    }

    @Override
    public K ceiling(K k) {                            // least key >= k
        Objects.requireNonNull(k);
        return set.ceiling(k);
    }

    @Override
    public K higher(K k) {                             // least key > k
        Objects.requireNonNull(k);
        return set.higher(k);
    }

    @Override
    public K pollFirst() {
        K k = set.minimum();
        if (k == null) return null;
        set.remove(k);
        return k;
    }

    @Override
    public K pollLast() {
        K k = set.maximum();
        if (k == null) return null;
        set.remove(k);
        return k;
    }

    // ── Views ─────────────────────────────────────────────────────────────────────

    @Override
    public Iterator<K> descendingIterator() {
        // Same snapshot semantics as iterator(), and remove() delegates to the live
        // base set the same way (TreeSet supports remove() on both directions).
        List<K> snap = new ArrayList<>(set.inOrder());
        Collections.reverse(snap);
        return new SnapshotIterator(snap);
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
            // ADR-021: both bound counts run under ONE guarded acquisition on the base.
            return b.set.countBetween(lo, loInc, hi, hiInc);
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
            // ONE guarded acquisition (ADR-021 follow-up, 2026-08-14). The old
            // isEmpty → minimum → maximum → rangeQuery composition spanned four lock
            // epochs; a writer emptying the set between the first two made minimum()
            // return null and the comparator NPE out of a read-only iterator.
            return b.set.rangeSnapshot(lo, loInc, hi, hiInc);
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

        // first/last and in-view navigation are each ONE base navigation call: the
        // view's bound is folded into the query BEFORE navigating (min/max of the two
        // constraints), instead of navigating first and patching out-of-view answers
        // with a second acquisition (ADR-021 follow-up, 2026-08-14 — the old
        // lastOrNull()/firstOrNull() fallback was a second lock epoch, so a writer
        // between the two could produce answers from two different tree states).

        @Override
        public K first() {
            K k = lo == null ? b.set.minimum()          // null iff empty — one acquisition
                             : (loInc ? b.ceiling(lo) : b.higher(lo));
            if (k == null || !belowHigh(k)) throw new NoSuchElementException("empty view");
            return k;
        }

        @Override
        public K last() {
            K k = hi == null ? b.set.maximum()
                             : (hiInc ? b.floor(hi) : b.lower(hi));
            if (k == null || !aboveLow(k)) throw new NoSuchElementException("empty view");
            return k;
        }

        @Override
        public K lower(K k) {                          // greatest view-key < k
            Objects.requireNonNull(k);
            K bound = k; boolean inc = false;          // request: (k, exclusive)
            if (hi != null) {
                int c = cmp(hi, k);
                if (c < 0) { bound = hi; inc = hiInc; }   // hi-bound is the tighter cap
                // c == 0: strict beats inclusive — keep (k, exclusive)
            }
            K r = inc ? b.floor(bound) : b.lower(bound);
            return (r != null && aboveLow(r)) ? r : null;
        }

        @Override
        public K floor(K k) {                          // greatest view-key <= k
            Objects.requireNonNull(k);
            K bound = k; boolean inc = true;           // request: (k, inclusive)
            if (hi != null) {
                int c = cmp(hi, k);
                if (c < 0)      { bound = hi; inc = hiInc; }
                else if (c == 0) { inc = hiInc; }      // equal caps: inclusive only if both are
            }
            K r = inc ? b.floor(bound) : b.lower(bound);
            return (r != null && aboveLow(r)) ? r : null;
        }

        @Override
        public K ceiling(K k) {                        // least view-key >= k
            Objects.requireNonNull(k);
            K bound = k; boolean inc = true;
            if (lo != null) {
                int c = cmp(lo, k);
                if (c > 0)      { bound = lo; inc = loInc; }   // lo-bound is the tighter floor
                else if (c == 0) { inc = loInc; }
            }
            K r = inc ? b.ceiling(bound) : b.higher(bound);
            return (r != null && belowHigh(r)) ? r : null;
        }

        @Override
        public K higher(K k) {                         // least view-key > k
            Objects.requireNonNull(k);
            K bound = k; boolean inc = false;
            if (lo != null) {
                int c = cmp(lo, k);
                if (c > 0) { bound = lo; inc = loInc; }
                // c == 0: strict beats inclusive — keep (k, exclusive)
            }
            K r = inc ? b.ceiling(bound) : b.higher(bound);
            return (r != null && belowHigh(r)) ? r : null;
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
            if (!inRangeForBound(from, fromInc) || !inRangeForBound(to, toInc)) {
                throw new IllegalArgumentException("sub-range bounds outside view range");
            }
            return new Range<>(b, from, fromInc, to, toInc);
        }

        /**
         * Bound admission for sub-view construction — {@code TreeSet}/{@code TreeMap}
         * parity ({@code NavigableSubMap.inRange(key, inclusive)}): an EXCLUSIVE new
         * bound may sit on the view's own endpoint (closed-range check), but an
         * INCLUSIVE new bound must lie inside the view's real range. Before 2026-08-14
         * this admitted endpoints unconditionally, so re-admitting an exclusive
         * endpoint inclusively (e.g. {@code headSet(10,false).headSet(10,true)}) let
         * the child view escape the parent's range instead of throwing.
         */
        private boolean inRangeForBound(K k, boolean inclusive) {
            if (inclusive) return inRange(k);
            boolean okLow  = lo == null || cmp(k, lo) >= 0;
            boolean okHigh = hi == null || cmp(k, hi) <= 0;
            return okLow && okHigh;
        }

        @Override
        public NavigableSet<K> headSet(K to, boolean inclusive) {
            Objects.requireNonNull(to);
            if (!inRangeForBound(to, inclusive)) {
                throw new IllegalArgumentException("toElement outside view range");
            }
            return new Range<>(b, lo, loInc, to, inclusive);
        }

        @Override
        public NavigableSet<K> tailSet(K from, boolean inclusive) {
            Objects.requireNonNull(from);
            if (!inRangeForBound(from, inclusive)) {
                throw new IllegalArgumentException("fromElement outside view range");
            }
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
