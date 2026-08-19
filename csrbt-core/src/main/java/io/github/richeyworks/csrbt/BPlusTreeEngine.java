package io.github.richeyworks.csrbt;

import io.github.richeyworks.csrbt.interfaces.RankedSet;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.NoSuchElementException;
import java.util.Objects;

/**
 * Page-structured B+tree {@link RankedSet} — the Phase-4 large-n engine (ADR-008 D1).
 *
 * <p>Every key lives in a leaf; internal nodes are pure routing (separator keys + per-child
 * subtree counts). Leaves form an ascending chain, so {@code inOrder} and {@code rangeQuery}
 * are sequential walks; the subtree counts fund the full order-statistics surface
 * ({@code select}/{@code rank}/{@code countInRange}) the same way ADR-005's count field does.
 * Node capacity is the {@code fanout} (default {@value #DEFAULT_FANOUT}, floor
 * {@value #MIN_FANOUT} — tests run at the floor to force splits and merges constantly); a
 * node is a key-sorted array scan, cache-line friendly where a pointer BST is a miss per
 * level. This in-memory layout is deliberately the canonical on-disk page layout, so D2
 * (paged file backing via {@code KeySerializer}) is a serialization exercise, not a redesign.</p>
 *
 * <p><b>Semantics:</b> {@link OrderedSet} parity method-for-method — the VERIFIED voting
 * requirement on {@link RankedSet}: boolean add/remove report effective change; min/max/
 * median/percentile return {@code null} on empty; successor/predecessor throw
 * {@link NoSuchElementException} on an absent argument and return {@code null} at the
 * extremes; {@code select}/{@code rank} throw on out-of-range/absent; {@code percentile}
 * clamps to [1, n]; {@code countInRange}/{@code rangeQuery} are empty for {@code lo > hi}.
 * A {@code null} key argument is rejected with {@link NullPointerException} on <em>every</em>
 * method that takes one — the other engines all throw NPE (their comparators do), and VERIFIED
 * voting compares thrown-exception classes, so an engine that answered {@code false}/{@code 0}
 * where its peers threw would be voted down and quarantined for one bad caller argument
 * (audit 2026-08-17, finding 14).</p>
 *
 * <p><b>Concurrency:</b> every public method is {@code synchronized} — the coarsest correct
 * answer. Unlike {@code OrderedSet} (R1 stamped reads) or the persistent engine (immutable),
 * a paged tree mutates in place with no read guard, so unsynchronized concurrent reads could
 * tear; the monitor closes that under ADR-007's lock-free vote pass at the price of brief
 * per-member serialization. Finer machinery (page latching) is D2+ territory if ever demanded.</p>
 *
 * <p>Separator invariant: {@code seps[i]} routes — children {@code <= i} hold keys strictly
 * below it, children {@code > i} hold keys at or above it. After deletions a separator may
 * name a key no longer present; routing stays correct, and {@link #validateStructure()}
 * checks the routing bounds, occupancy floors, uniform leaf depth, counts, and chain order.</p>
 */
public final class BPlusTreeEngine<K> implements RankedSet<K> {

    public static final int MIN_FANOUT = 4;
    public static final int DEFAULT_FANOUT = 32;

    private final int fanout;                 // max children per internal; max keys per leaf
    private final Comparator<? super K> keyOrder;

    private Node root = null;                 // null = empty; Leaf or Internal otherwise
    private int size = 0;

    private long totalInsertTime = 0, totalDeleteTime = 0;
    private int insertCount = 0, deleteCount = 0;

    private boolean opChanged;                // per-op scratch; all ops run under the monitor

    public BPlusTreeEngine(Comparator<? super K> keyOrder) {
        this(DEFAULT_FANOUT, keyOrder);
    }

    public BPlusTreeEngine(int fanout, Comparator<? super K> keyOrder) {
        if (fanout < MIN_FANOUT) {
            throw new IllegalArgumentException("fanout must be >= " + MIN_FANOUT + ": " + fanout);
        }
        if (keyOrder == null) throw new IllegalArgumentException("keyOrder cannot be null");
        this.fanout = fanout;
        this.keyOrder = keyOrder;
    }

    /** Convenience factory for naturally-ordered {@link Comparable} keys at the default fanout. */
    public static <K extends Comparable<? super K>> BPlusTreeEngine<K> withNaturalOrder() {
        return new BPlusTreeEngine<>(Comparator.naturalOrder());
    }

    /** Natural-order factory at an explicit fanout (tests use {@link #MIN_FANOUT}). */
    public static <K extends Comparable<? super K>> BPlusTreeEngine<K> withNaturalOrder(int fanout) {
        return new BPlusTreeEngine<>(fanout, Comparator.naturalOrder());
    }

    /**
     * This engine seen through the {@link io.github.richeyworks.csrbt.interfaces.TreeEngine}
     * seam — ADR-029 (fires ADR-008 D3): the registry builds {@code TreeEngine}s, but this
     * class implements {@link RankedSet}, whose {@code boolean add/remove} (the VERIFIED
     * voting requirement) collide with {@code TreeEngine}'s {@code void} signatures, so one
     * class cannot implement both. The view is a thin live delegate — same object, same
     * synchronization, no copying — mirroring how {@code PersistentRankedSet} carries the
     * persistent engine across the opposite seam.
     */
    public io.github.richeyworks.csrbt.interfaces.TreeEngine<K> asTreeEngine() {
        BPlusTreeEngine<K> self = this;
        return new io.github.richeyworks.csrbt.interfaces.TreeEngine<>() {
            @Override public void add(K value)         { self.add(value); }
            @Override public void remove(K value)      { self.remove(value); }
            @Override public boolean contains(K value) { return self.contains(value); }
            @Override public List<K> inOrder()         { return self.inOrder(); }
            @Override public int size()                { return self.size(); }
            @Override public void clear()              { self.clear(); }
            @Override public String toString()         { return "TreeEngine[" + self + "]"; }
        };
    }

    /** Node capacity in use. */
    public int fanout() { return fanout; }

    // ── Nodes ─────────────────────────────────────────────────────────────────────

    private abstract class Node { int count; }

    private final class Leaf extends Node {
        final ArrayList<K> keys = new ArrayList<>();
        Leaf next;
    }

    private final class Internal extends Node {
        final ArrayList<K> seps = new ArrayList<>();       // seps.size() == children.size() - 1
        final ArrayList<Node> children = new ArrayList<>();
    }

    private final class Split {
        final K sep; final Node right;
        Split(K sep, Node right) { this.sep = sep; this.right = right; }
    }

    private int maxLeafKeys()  { return fanout; }
    private int minLeafKeys()  { return fanout / 2; }
    private int minChildren()  { return (fanout + 1) / 2; }

    /** First index in {@code a} whose key is {@code >= key}. */
    private int lowerBound(List<K> a, K key) {
        int lo = 0, hi = a.size();
        while (lo < hi) {
            int m = (lo + hi) >>> 1;
            if (keyOrder.compare(a.get(m), key) < 0) lo = m + 1; else hi = m;
        }
        return lo;
    }

    /** First index in {@code a} whose key is {@code > key}. */
    private int upperBound(List<K> a, K key) {
        int lo = 0, hi = a.size();
        while (lo < hi) {
            int m = (lo + hi) >>> 1;
            if (keyOrder.compare(a.get(m), key) <= 0) lo = m + 1; else hi = m;
        }
        return lo;
    }

    /** Routing: the child that may hold {@code key} (= number of separators {@code <= key}). */
    private int childIndex(Internal n, K key) { return upperBound(n.seps, key); }

    private void recount(Internal n) {
        int c = 0;
        for (Node ch : n.children) c += ch.count;
        n.count = c;
    }

    // ── OrderedCollection ─────────────────────────────────────────────────────────

    @Override
    public synchronized boolean add(K value) {
        Objects.requireNonNull(value, "value cannot be null");   // NPE parity (finding 14)
        long start = System.nanoTime();
        if (root == null) root = new Leaf();
        Split s = insert(root, value);
        if (s != null) {
            Internal nr = new Internal();
            nr.children.add(root);
            nr.children.add(s.right);
            nr.seps.add(s.sep);
            recount(nr);
            root = nr;
        }
        if (opChanged) {
            size++;
            totalInsertTime += System.nanoTime() - start;
            insertCount++;
        }
        return opChanged;
    }

    private Split insert(Node n, K key) {
        if (n instanceof BPlusTreeEngine.Leaf) {
            Leaf leaf = (Leaf) n;
            int i = lowerBound(leaf.keys, key);
            if (i < leaf.keys.size() && keyOrder.compare(leaf.keys.get(i), key) == 0) {
                opChanged = false;
                return null;
            }
            leaf.keys.add(i, key);
            leaf.count = leaf.keys.size();
            opChanged = true;
            if (leaf.keys.size() <= maxLeafKeys()) return null;
            Leaf right = new Leaf();
            int mid = leaf.keys.size() / 2;
            right.keys.addAll(leaf.keys.subList(mid, leaf.keys.size()));
            leaf.keys.subList(mid, leaf.keys.size()).clear();
            leaf.count = leaf.keys.size();
            right.count = right.keys.size();
            right.next = leaf.next;
            leaf.next = right;
            return new Split(right.keys.get(0), right);
        }
        Internal in = (Internal) n;
        int ci = childIndex(in, key);
        Split s = insert(in.children.get(ci), key);
        if (opChanged) in.count++;
        if (s == null) return null;
        in.seps.add(ci, s.sep);
        in.children.add(ci + 1, s.right);
        if (in.children.size() <= fanout) return null;
        Internal right = new Internal();
        int midChild = in.children.size() / 2;             // children [midChild..) move right
        K upSep = in.seps.get(midChild - 1);               // promoted, not copied
        right.seps.addAll(in.seps.subList(midChild, in.seps.size()));
        in.seps.subList(midChild - 1, in.seps.size()).clear();
        right.children.addAll(in.children.subList(midChild, in.children.size()));
        in.children.subList(midChild, in.children.size()).clear();
        recount(in);
        recount(right);
        return new Split(upSep, right);
    }

    @Override
    public synchronized boolean remove(K value) {
        Objects.requireNonNull(value, "value cannot be null");   // NPE parity (finding 14)
        if (root == null) return false;
        long start = System.nanoTime();
        delete(root, value);
        if (opChanged) {
            size--;
            if (root instanceof BPlusTreeEngine.Internal && ((Internal) root).children.size() == 1) {
                root = ((Internal) root).children.get(0);   // height collapse
            }
            if (root.count == 0) root = null;
            totalDeleteTime += System.nanoTime() - start;
            deleteCount++;
        }
        return opChanged;
    }

    private void delete(Node n, K key) {
        if (n instanceof BPlusTreeEngine.Leaf) {
            Leaf leaf = (Leaf) n;
            int i = lowerBound(leaf.keys, key);
            if (i < leaf.keys.size() && keyOrder.compare(leaf.keys.get(i), key) == 0) {
                leaf.keys.remove(i);
                leaf.count = leaf.keys.size();
                opChanged = true;
            } else {
                opChanged = false;
            }
            return;
        }
        Internal in = (Internal) n;
        int ci = childIndex(in, key);
        Node child = in.children.get(ci);
        delete(child, key);
        if (!opChanged) return;
        in.count--;
        if (underflow(child)) rebalance(in, ci);
    }

    private boolean underflow(Node n) {
        if (n instanceof BPlusTreeEngine.Leaf) return n.count < minLeafKeys();
        return ((Internal) n).children.size() < minChildren();
    }

    /** Repair an underfull {@code children[ci]}: borrow from a sibling with spare, else merge. */
    private void rebalance(Internal parent, int ci) {
        Node child = parent.children.get(ci);
        Node left  = ci > 0 ? parent.children.get(ci - 1) : null;
        Node right = ci < parent.children.size() - 1 ? parent.children.get(ci + 1) : null;

        if (child instanceof BPlusTreeEngine.Leaf) {
            Leaf c = (Leaf) child;
            if (left != null && left.count > minLeafKeys()) {            // borrow last from left
                Leaf l = (Leaf) left;
                c.keys.add(0, l.keys.remove(l.keys.size() - 1));
                l.count = l.keys.size(); c.count = c.keys.size();
                parent.seps.set(ci - 1, c.keys.get(0));
                return;
            }
            if (right != null && right.count > minLeafKeys()) {          // borrow first from right
                Leaf r = (Leaf) right;
                c.keys.add(r.keys.remove(0));
                r.count = r.keys.size(); c.count = c.keys.size();
                parent.seps.set(ci, r.keys.get(0));
                return;
            }
            if (left != null) {                                          // merge child into left
                Leaf l = (Leaf) left;
                l.keys.addAll(c.keys);
                l.count = l.keys.size();
                l.next = c.next;
                parent.seps.remove(ci - 1);
                parent.children.remove(ci);
            } else {                                                     // merge right into child
                Leaf r = (Leaf) right;
                c.keys.addAll(r.keys);
                c.count = c.keys.size();
                c.next = r.next;
                parent.seps.remove(ci);
                parent.children.remove(ci + 1);
            }
            return;
        }

        Internal c = (Internal) child;
        if (left != null && ((Internal) left).children.size() > minChildren()) {
            Internal l = (Internal) left;                                // rotate through parent sep
            c.seps.add(0, parent.seps.get(ci - 1));
            parent.seps.set(ci - 1, l.seps.remove(l.seps.size() - 1));
            Node moved = l.children.remove(l.children.size() - 1);
            c.children.add(0, moved);
            l.count -= moved.count;
            c.count += moved.count;
            return;
        }
        if (right != null && ((Internal) right).children.size() > minChildren()) {
            Internal r = (Internal) right;
            c.seps.add(parent.seps.get(ci));
            parent.seps.set(ci, r.seps.remove(0));
            Node moved = r.children.remove(0);
            c.children.add(moved);
            r.count -= moved.count;
            c.count += moved.count;
            return;
        }
        if (left != null) {                                              // merge child into left
            Internal l = (Internal) left;
            l.seps.add(parent.seps.get(ci - 1));
            l.seps.addAll(c.seps);
            l.children.addAll(c.children);
            l.count += c.count;
            parent.seps.remove(ci - 1);
            parent.children.remove(ci);
        } else {                                                         // merge right into child
            Internal r = (Internal) right;
            c.seps.add(parent.seps.get(ci));
            c.seps.addAll(r.seps);
            c.children.addAll(r.children);
            c.count += r.count;
            parent.seps.remove(ci);
            parent.children.remove(ci + 1);
        }
    }

    @Override
    public synchronized boolean contains(K value) {
        Objects.requireNonNull(value, "value cannot be null");   // NPE parity (finding 14)
        Node n = root;
        if (n == null) return false;
        while (n instanceof BPlusTreeEngine.Internal) {
            Internal in = (Internal) n;
            n = in.children.get(childIndex(in, value));
        }
        Leaf leaf = (Leaf) n;
        int i = lowerBound(leaf.keys, value);
        return i < leaf.keys.size() && keyOrder.compare(leaf.keys.get(i), value) == 0;
    }

    @Override public synchronized int size() { return size; }

    @Override
    public synchronized List<K> inOrder() {
        List<K> out = new ArrayList<>(size);
        for (Leaf l = leftmostLeaf(); l != null; l = l.next) out.addAll(l.keys);
        return out;
    }

    /**
     * Per-leaf key counts, left to right along the leaf chain — the page-occupancy
     * view: how full each leaf actually is against the {@link #fanout()} capacity.
     * Read-only, one chain walk; empty tree returns an empty list. Every count is in
     * {@code [fanout/2, fanout]} except a lone root leaf, which may hold fewer — the
     * same occupancy floor {@link #validateStructure()} enforces.
     */
    public synchronized List<Integer> leafKeyCounts() {
        List<Integer> out = new ArrayList<>();
        for (Leaf l = leftmostLeaf(); l != null; l = l.next) out.add(l.keys.size());
        return out;
    }

    @Override
    public synchronized void clear() {
        root = null;
        size = 0;
    }

    private Leaf leftmostLeaf() {
        Node n = root;
        if (n == null) return null;
        while (n instanceof BPlusTreeEngine.Internal) n = ((Internal) n).children.get(0);
        return (Leaf) n;
    }

    // ── Order statistics (count-funded; OrderedSet parity) ────────────────────────

    @Override
    public synchronized K select(int rank) {
        if (rank < 1 || rank > size) {
            throw new IndexOutOfBoundsException("rank " + rank + " out of [1, " + size + "]");
        }
        Node n = root;
        int r = rank;
        while (n instanceof BPlusTreeEngine.Internal) {
            for (Node ch : ((Internal) n).children) {
                if (r <= ch.count) { n = ch; break; }
                r -= ch.count;
            }
        }
        return ((Leaf) n).keys.get(r - 1);
    }

    @Override
    public synchronized int rank(K value) {
        Objects.requireNonNull(value, "value cannot be null");
        Node n = root;
        if (n == null) throw new NoSuchElementException("key not present: " + value);
        int acc = 0;
        while (n instanceof BPlusTreeEngine.Internal) {
            Internal in = (Internal) n;
            int ci = childIndex(in, value);
            for (int i = 0; i < ci; i++) acc += in.children.get(i).count;
            n = in.children.get(ci);
        }
        Leaf leaf = (Leaf) n;
        int i = lowerBound(leaf.keys, value);
        if (i >= leaf.keys.size() || keyOrder.compare(leaf.keys.get(i), value) != 0) {
            throw new NoSuchElementException("key not present: " + value);
        }
        return acc + i + 1;
    }

    @Override
    public synchronized K successor(K value) {
        int r = rank(value);                       // throws if absent, like OrderedSet
        return r < size ? select(r + 1) : null;
    }

    @Override
    public synchronized K predecessor(K value) {
        int r = rank(value);
        return r > 1 ? select(r - 1) : null;
    }

    @Override public synchronized K minimum() { return size == 0 ? null : select(1); }
    @Override public synchronized K maximum() { return size == 0 ? null : select(size); }
    @Override public synchronized K median()  { return size == 0 ? null : select((size + 1) / 2); }

    @Override
    public synchronized K percentile(int pct) {
        if (size == 0) return null;
        int rank = Math.max(1, Math.min(size, (int) Math.ceil(pct / 100.0 * size)));
        return select(rank);
    }

    @Override
    public synchronized int countInRange(K lo, K hi) {
        Objects.requireNonNull(lo, "lo");                        // NPE parity (finding 14)
        Objects.requireNonNull(hi, "hi");
        if (root == null || keyOrder.compare(lo, hi) > 0) return 0;
        return countAtMost(hi) - countBelow(lo);
    }

    /** Number of keys {@code <= key}. */
    private int countAtMost(K key) {
        int acc = 0;
        Node n = root;
        while (n instanceof BPlusTreeEngine.Internal) {
            Internal in = (Internal) n;
            int ci = childIndex(in, key);
            for (int i = 0; i < ci; i++) acc += in.children.get(i).count;
            n = in.children.get(ci);
        }
        return acc + upperBound(((Leaf) n).keys, key);
    }

    /** Number of keys {@code < key}. */
    private int countBelow(K key) {
        int acc = 0;
        Node n = root;
        while (n instanceof BPlusTreeEngine.Internal) {
            Internal in = (Internal) n;
            int ci = childIndex(in, key);
            for (int i = 0; i < ci; i++) acc += in.children.get(i).count;
            n = in.children.get(ci);
        }
        return acc + lowerBound(((Leaf) n).keys, key);
    }

    @Override
    public synchronized List<K> rangeQuery(K lo, K hi) {
        Objects.requireNonNull(lo, "lo");                        // NPE parity (finding 14)
        Objects.requireNonNull(hi, "hi");
        List<K> out = new ArrayList<>();
        if (root == null || keyOrder.compare(lo, hi) > 0) return out;
        Node n = root;
        while (n instanceof BPlusTreeEngine.Internal) {
            Internal in = (Internal) n;
            n = in.children.get(childIndex(in, lo));
        }
        Leaf leaf = (Leaf) n;
        int i = lowerBound(leaf.keys, lo);
        while (leaf != null) {
            for (; i < leaf.keys.size(); i++) {
                K k = leaf.keys.get(i);
                if (keyOrder.compare(k, hi) > 0) return out;
                out.add(k);
            }
            leaf = leaf.next;
            i = 0;
        }
        return out;
    }

    // ── Meters & hooks ────────────────────────────────────────────────────────────

    @Override public Comparator<? super K> comparator() { return keyOrder; }

    @Override
    public synchronized double avgInsertTimeMs() {
        return insertCount == 0 ? 0 : (totalInsertTime / 1e6) / insertCount;
    }

    @Override
    public synchronized double avgDeleteTimeMs() {
        return deleteCount == 0 ? 0 : (totalDeleteTime / 1e6) / deleteCount;
    }

    @Override
    public synchronized int height() {
        int h = 0;
        for (Node n = root; n != null; n = n instanceof BPlusTreeEngine.Internal
                ? ((Internal) n).children.get(0) : null) {
            h++;
        }
        return h;
    }

    /**
     * Coarse page-amortized footprint: keys ride in array pages, not per-key nodes — model
     * ~40 bytes/key (boxed key + array slot + amortized page headers) vs the pointer
     * families' 56–96.
     */
    @Override
    public synchronized long estimatedMemoryBytes() { return (long) size * 40L; }

    // ── Mechanical invariant check (ADR-008 D1) ───────────────────────────────────

    /**
     * Structural self-check: routing bounds (every key in child {@code <= i} below
     * {@code seps[i]}, every key in child {@code > i} at or above it), occupancy floors
     * (non-root), uniform leaf depth, per-node counts, ascending order within nodes, and the
     * leaf chain enumerating exactly {@code size} keys in ascending order.
     */
    @Override
    public synchronized List<String> validateStructure() {
        List<String> out = new ArrayList<>();
        if (root == null) {
            if (size != 0) out.add("empty tree but size=" + size);
            return out;
        }
        int leafDepth = height();
        check(root, null, null, 1, leafDepth, true, out);
        List<K> chain = inOrder();
        if (chain.size() != size) {
            out.add("leaf chain enumerates " + chain.size() + " keys, size=" + size);
        }
        for (int i = 1; i < chain.size(); i++) {
            if (keyOrder.compare(chain.get(i - 1), chain.get(i)) >= 0) {
                out.add("leaf chain out of order at index " + i);
                break;
            }
        }
        return out;
    }

    private void check(Node n, K min, K max, int depth, int leafDepth, boolean isRoot, List<String> out) {
        if (n.count <= 0 && !isRoot) out.add("non-root node with count " + n.count);
        if (n instanceof BPlusTreeEngine.Leaf) {
            Leaf leaf = (Leaf) n;
            if (depth != leafDepth) out.add("leaf at depth " + depth + ", expected " + leafDepth);
            if (leaf.count != leaf.keys.size()) {
                out.add("leaf count " + leaf.count + " != keys " + leaf.keys.size());
            }
            if (!isRoot && leaf.keys.size() < minLeafKeys()) {
                out.add("leaf underfull: " + leaf.keys.size() + " < " + minLeafKeys());
            }
            if (leaf.keys.size() > maxLeafKeys()) {
                out.add("leaf overfull: " + leaf.keys.size() + " > " + maxLeafKeys());
            }
            for (int i = 0; i < leaf.keys.size(); i++) {
                K k = leaf.keys.get(i);
                if (i > 0 && keyOrder.compare(leaf.keys.get(i - 1), k) >= 0) out.add("leaf keys out of order");
                if (min != null && keyOrder.compare(k, min) < 0) out.add("leaf key below routing bound");
                if (max != null && keyOrder.compare(k, max) >= 0) out.add("leaf key at/above routing bound");
            }
            return;
        }
        Internal in = (Internal) n;
        if (in.seps.size() != in.children.size() - 1) {
            out.add("internal: " + in.seps.size() + " seps for " + in.children.size() + " children");
            return;
        }
        if (!isRoot && in.children.size() < minChildren()) {
            out.add("internal underfull: " + in.children.size() + " < " + minChildren());
        }
        if (in.children.size() > fanout) {
            out.add("internal overfull: " + in.children.size() + " > " + fanout);
        }
        int sum = 0;
        for (Node ch : in.children) sum += ch.count;
        if (sum != in.count) out.add("internal count " + in.count + " != children sum " + sum);
        for (int i = 1; i < in.seps.size(); i++) {
            if (keyOrder.compare(in.seps.get(i - 1), in.seps.get(i)) >= 0) out.add("separators out of order");
        }
        for (int i = 0; i < in.children.size(); i++) {
            K lo = i == 0 ? min : in.seps.get(i - 1);
            K hi = i == in.seps.size() ? max : in.seps.get(i);
            check(in.children.get(i), lo, hi, depth + 1, leafDepth, false, out);
        }
    }

    @Override
    public synchronized String toString() {
        return "BPlusTreeEngine[fanout=" + fanout + ", n=" + size + ", height=" + height() + "]";
    }
}
