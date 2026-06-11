package io.github.richeyworks.csrbt;

import io.github.richeyworks.csrbt.interfaces.TreeEngine;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Deque;
import java.util.List;
import java.util.NoSuchElementException;
import java.util.Objects;

/**
 * Persistent (immutable, path-copying) <b>weight-balanced</b> ordered set of {@code K} keys
 * (ADR-005, P1).
 *
 * <p>This is a genuinely new {@link TreeEngine} — not a {@code TreeStrategy} wrapped around
 * {@link RedBlackTree}. Its nodes are immutable; every mutation returns a new root that
 * structurally shares all untouched subtrees with the previous version (classic persistence,
 * path copying). The cost is O(log n) fresh nodes per update; the payoff is that any captured
 * {@link Snapshot} remains intact and queryable forever, and every read is wait-free.</p>
 *
 * <p><b>Balance (ADR-005 §2A):</b> Adams / BB[α] weight balance with the verified parameters
 * Δ=3, Γ=2, in the size-based formulation Haskell's {@code containers} has shipped since the
 * 2010 fix — past trivial sizes, neither child's subtree size may exceed Δ× the other's;
 * violations are repaired by single/double rotations on the freshly copied path. Height is O(log n) for
 * <em>any</em> input, including sorted replay. The {@code count} field that funds the invariant
 * also funds O(log n) order statistics ({@link #select}, {@link #rank}, {@link #countInRange},
 * {@link #rangeQuery}) with no extra per-node state.</p>
 *
 * <p><b>Versioning (ADR-005 §3):</b> explicit snapshots. {@link #snapshot()} is an O(1) capture
 * of the current tree; nothing is retained unless a caller holds a handle. The seed engine's
 * auto-history ({@code versionCount}/{@code inOrderOfVersion}) is gone — keep your own handles.</p>
 *
 * <p><b>Concurrency (ADR-005 §4):</b> single writer / wait-free readers, by construction.
 * Mutators serialize on an internal monitor, build the new path aside, and publish it with one
 * {@code volatile} store; node fields are all {@code final}, so the store is safe publication.
 * Every read — membership, traversal, order statistics, snapshots — is one {@code volatile} read
 * of the root plus a walk of nodes that can never change: no locks, no retries, no step bounds.</p>
 *
 * <p>Set semantics: duplicate inserts are ignored; null keys are rejected. {@link #inOrder()}
 * returns ascending keys per the comparator. All traversals are iterative (stack-safe by
 * paranoia; the balance invariant already bounds depth).</p>
 */
public final class PersistentTreeEngine<K> implements TreeEngine<K> {

    /** Weight-balance parameters — the Hirai–Yamamoto-verified pair (ADR-005 §2A). */
    private static final int DELTA = 3;
    private static final int RATIO = 2;

    /** Immutable node. Every field is {@code final} — safe publication depends on it (ADR-005 §7). */
    private static final class Node<K> {
        final K key;
        final Node<K> left;
        final Node<K> right;
        final int count;   // subtree size: balance info and order statistics, one field

        Node(K key, Node<K> left, Node<K> right) {
            this.key   = key;
            this.left  = left;
            this.right = right;
            this.count = 1 + sizeOf(left) + sizeOf(right);
        }
    }

    private static int sizeOf(Node<?> n) { return n == null ? 0 : n.count; }

    private final Comparator<? super K> keyOrder;

    /** Current root. Volatile: the single mutation a writer publishes; all readers start here. */
    private volatile Node<K> root;

    /** Mutators serialize here (one writer at a time, matching {@code OrderedSet}'s discipline). */
    private final Object writeLock = new Object();

    public PersistentTreeEngine(Comparator<? super K> keyOrder) {
        if (keyOrder == null) throw new IllegalArgumentException("keyOrder cannot be null");
        this.keyOrder = keyOrder;
        this.root = null;
    }

    /** Convenience factory for naturally-ordered {@link Comparable} keys. */
    public static <K extends Comparable<? super K>> PersistentTreeEngine<K> withNaturalOrder() {
        return new PersistentTreeEngine<>(Comparator.naturalOrder());
    }

    // ── TreeEngine ─────────────────────────────────────────────────────────────

    @Override
    public void add(K value) {
        Objects.requireNonNull(value, "key");
        synchronized (writeLock) {
            Node<K> next = insert(root, value, keyOrder);
            if (next != root) root = next;     // single volatile store publishes the new version
        }
    }

    @Override
    public void remove(K value) {
        Objects.requireNonNull(value, "key");
        synchronized (writeLock) {
            Node<K> next = delete(root, value, keyOrder);
            if (next != root) root = next;
        }
    }

    @Override
    public boolean contains(K value) {
        Objects.requireNonNull(value, "key");
        return findOf(root, value, keyOrder) != null;
    }

    @Override
    public List<K> inOrder() {
        return inOrderOf(root);
    }

    @Override
    public int size() { return sizeOf(root); }

    @Override
    public void clear() {
        synchronized (writeLock) {
            root = null;
        }
    }

    // ── Order statistics (count-funded, wait-free; ADR-005 P1c) ───────────────

    /** ith smallest key (1-indexed). @throws IndexOutOfBoundsException if out of [1,size]. */
    public K select(int rank) { return selectOf(root, rank); }

    /** 1-indexed rank of a key. @throws NoSuchElementException if absent. */
    public int rank(K value) {
        Objects.requireNonNull(value, "key");
        return rankOf(root, value, keyOrder);
    }

    /** Count of keys in the closed range [lo, hi] (0 if lo &gt; hi). */
    public int countInRange(K lo, K hi) { return countInRangeOf(root, lo, hi, keyOrder); }

    /** Keys in the closed range [lo, hi], ascending (empty if lo &gt; hi). */
    public List<K> rangeQuery(K lo, K hi) { return rangeQueryOf(root, lo, hi, keyOrder); }

    // ── Snapshots (the reason to choose this engine; ADR-005 §3) ──────────────

    /**
     * O(1) immutable capture of the current tree. The handle stays valid and unchanged forever,
     * regardless of later mutations; it pins the structure it shares with other versions until
     * dropped. Reading a snapshot never coordinates with anything.
     */
    public Snapshot<K> snapshot() {
        return new Snapshot<>(root, keyOrder);
    }

    /** An immutable version of the set: every read is a pure walk of frozen nodes. */
    public static final class Snapshot<K> {
        private final Node<K> root;
        private final Comparator<? super K> keyOrder;

        private Snapshot(Node<K> root, Comparator<? super K> keyOrder) {
            this.root = root;
            this.keyOrder = keyOrder;
        }

        public int size() { return sizeOf(root); }

        public boolean isEmpty() { return root == null; }

        public boolean contains(K value) {
            Objects.requireNonNull(value, "key");
            return findOf(root, value, keyOrder) != null;
        }

        /** @return all keys in ascending order. */
        public List<K> inOrder() { return inOrderOf(root); }

        /** ith smallest key (1-indexed). @throws IndexOutOfBoundsException if out of [1,size]. */
        public K select(int rank) { return selectOf(root, rank); }

        /** 1-indexed rank of a key. @throws NoSuchElementException if absent. */
        public int rank(K value) {
            Objects.requireNonNull(value, "key");
            return rankOf(root, value, keyOrder);
        }

        /** Count of keys in the closed range [lo, hi] (0 if lo &gt; hi). */
        public int countInRange(K lo, K hi) { return countInRangeOf(root, lo, hi, keyOrder); }

        /** Keys in the closed range [lo, hi], ascending (empty if lo &gt; hi). */
        public List<K> rangeQuery(K lo, K hi) { return rangeQueryOf(root, lo, hi, keyOrder); }
    }

    // ── Diagnostics ────────────────────────────────────────────────────────────

    /**
     * Tree height (empty = 0), by an iterative walk — O(n), intended for cadence diagnostics
     * (the ensemble's meters line), not hot paths. The weight invariant bounds it at O(log n).
     */
    public int height() {
        Node<K> r = root;
        if (r == null) return 0;
        Deque<Node<K>> nodes = new ArrayDeque<>();
        Deque<Integer> depths = new ArrayDeque<>();
        nodes.push(r);
        depths.push(1);
        int max = 0;
        while (!nodes.isEmpty()) {
            Node<K> n = nodes.pop();
            int d = depths.pop();
            if (d > max) max = d;
            if (n.left != null)  { nodes.push(n.left);  depths.push(d + 1); }
            if (n.right != null) { nodes.push(n.right); depths.push(d + 1); }
        }
        return max;
    }

    /**
     * Mechanical invariant check (ADR-005 §7): BST order, count correctness, and the Δ-weight
     * balance at every node. @return an empty list when healthy, else one message per violation
     * (capped — a corrupt tree need not produce a novel).
     */
    public List<String> validateInvariants() {
        List<String> failures = new ArrayList<>();
        Node<K> r = root;

        // Local checks (count + balance) via an explicit pre-order stack.
        Deque<Node<K>> stack = new ArrayDeque<>();
        if (r != null) stack.push(r);
        while (!stack.isEmpty() && failures.size() < 8) {
            Node<K> n = stack.pop();
            int expect = 1 + sizeOf(n.left) + sizeOf(n.right);
            if (n.count != expect) {
                failures.add("count: node " + n.key + " has count " + n.count + ", expected " + expect);
            }
            int sl = sizeOf(n.left), sr = sizeOf(n.right);
            if (sl + sr > 1 && (sl > DELTA * sr || sr > DELTA * sl)) {
                failures.add("balance: node " + n.key + " child sizes " + sl + "/" + sr
                        + " exceed Δ=" + DELTA);
            }
            if (n.left != null)  stack.push(n.left);
            if (n.right != null) stack.push(n.right);
        }

        // Global BST order via iterative in-order walk.
        K prev = null;
        Deque<Node<K>> walk = new ArrayDeque<>();
        Node<K> cur = r;
        while ((cur != null || !walk.isEmpty()) && failures.size() < 8) {
            while (cur != null) { walk.push(cur); cur = cur.left; }
            cur = walk.pop();
            if (prev != null && keyOrder.compare(prev, cur.key) >= 0) {
                failures.add("order: " + prev + " precedes " + cur.key);
            }
            prev = cur.key;
            cur = cur.right;
        }
        return failures;
    }

    // ── Path-copying mutation with weight-balanced repair ──────────────────────

    /**
     * Iterative path-copying insert. Descends to the insertion point recording the ancestor
     * path, then rebuilds that path bottom-up with fresh nodes, repairing the weight invariant
     * at every rebuilt level (one side grew by one, the regime Adams' balance handles). Every
     * untouched subtree is shared. Returns the original root unchanged if the key exists.
     */
    private static <K> Node<K> insert(Node<K> root, K key, Comparator<? super K> order) {
        Deque<Node<K>> path = new ArrayDeque<>();
        Node<K> cur = root;
        while (cur != null) {
            int cmp = order.compare(key, cur.key);
            if (cmp == 0) return root;             // set semantics: no duplicates
            path.push(cur);
            cur = cmp < 0 ? cur.left : cur.right;
        }
        Node<K> rebuilt = new Node<>(key, null, null);
        while (!path.isEmpty()) {
            Node<K> p = path.pop();
            rebuilt = order.compare(key, p.key) < 0
                    ? balance(p.key, rebuilt, p.right)
                    : balance(p.key, p.left, rebuilt);
        }
        return rebuilt;
    }

    /**
     * Iterative path-copying delete. Finds the target (recording the ancestor path), builds the
     * replacement subtree (promoting a child, or splicing in the in-order successor for a
     * two-child node — that splice is itself path-copied and rebalanced), then rebuilds the
     * ancestor path bottom-up with the same repair. Returns the original root if absent.
     */
    private static <K> Node<K> delete(Node<K> root, K key, Comparator<? super K> order) {
        Deque<Node<K>> path = new ArrayDeque<>();
        Node<K> cur = root;
        int cmp = -1;
        while (cur != null && (cmp = order.compare(key, cur.key)) != 0) {
            path.push(cur);
            cur = cmp < 0 ? cur.left : cur.right;
        }
        if (cur == null) return root;              // not found — no change

        Node<K> replacement;
        if (cur.left == null) {
            replacement = cur.right;
        } else if (cur.right == null) {
            replacement = cur.left;
        } else {
            // Two children: splice out the in-order successor (min of right subtree) with path
            // copying, rebalancing each copied level (its left side shrank by one).
            Deque<Node<K>> succPath = new ArrayDeque<>();
            Node<K> s = cur.right;
            while (s.left != null) { succPath.push(s); s = s.left; }
            Node<K> sub = s.right;                 // promote successor's right child
            while (!succPath.isEmpty()) {
                Node<K> p = succPath.pop();        // we always descended left
                sub = balance(p.key, sub, p.right);
            }
            replacement = balance(s.key, cur.left, sub);
        }

        // Rebuild ancestors, repairing balance (one side shrank by one at each level). The slot
        // direction is how we descended to cur: comparing the target key to each ancestor's key.
        Node<K> rebuilt = replacement;
        while (!path.isEmpty()) {
            Node<K> p = path.pop();
            rebuilt = order.compare(key, p.key) < 0
                    ? balance(p.key, rebuilt, p.right)
                    : balance(p.key, p.left, rebuilt);
        }
        return rebuilt;
    }

    /**
     * Adams' balance step (Δ=3, Γ=2): given a key and its two (already immutable) children
     * where at most one side changed by one element, return a node satisfying the weight
     * invariant — verbatim, a single or double rotation built from fresh nodes.
     */
    private static <K> Node<K> balance(K key, Node<K> left, Node<K> right) {
        int sl = sizeOf(left), sr = sizeOf(right);
        if (sl + sr <= 1) {                                  // both sides tiny: always balanced
            return new Node<>(key, left, right);
        }
        if (sr > DELTA * sl) {                               // right too heavy
            return sizeOf(right.left) < RATIO * sizeOf(right.right)
                    ? singleLeft(key, left, right)
                    : doubleLeft(key, left, right);
        }
        if (sl > DELTA * sr) {                               // left too heavy
            return sizeOf(left.right) < RATIO * sizeOf(left.left)
                    ? singleRight(key, left, right)
                    : doubleRight(key, left, right);
        }
        return new Node<>(key, left, right);
    }

    private static <K> Node<K> singleLeft(K key, Node<K> l, Node<K> r) {
        return new Node<>(r.key, new Node<>(key, l, r.left), r.right);
    }

    private static <K> Node<K> singleRight(K key, Node<K> l, Node<K> r) {
        return new Node<>(l.key, l.left, new Node<>(key, l.right, r));
    }

    private static <K> Node<K> doubleLeft(K key, Node<K> l, Node<K> r) {
        Node<K> rl = r.left;
        return new Node<>(rl.key,
                new Node<>(key, l, rl.left),
                new Node<>(r.key, rl.right, r.right));
    }

    private static <K> Node<K> doubleRight(K key, Node<K> l, Node<K> r) {
        Node<K> lr = l.right;
        return new Node<>(lr.key,
                new Node<>(l.key, l.left, lr.left),
                new Node<>(key, lr.right, r));
    }

    // ── Shared read walks (live engine and snapshots use the same code) ───────

    private static <K> Node<K> findOf(Node<K> root, K key, Comparator<? super K> order) {
        Node<K> n = root;
        while (n != null) {
            int cmp = order.compare(key, n.key);
            if (cmp == 0) return n;
            n = cmp < 0 ? n.left : n.right;
        }
        return null;
    }

    /** Iterative in-order traversal (stack-safe regardless of shape). */
    private static <K> List<K> inOrderOf(Node<K> node) {
        List<K> out = new ArrayList<>(sizeOf(node));
        Deque<Node<K>> stack = new ArrayDeque<>();
        Node<K> cur = node;
        while (cur != null || !stack.isEmpty()) {
            while (cur != null) { stack.push(cur); cur = cur.left; }
            cur = stack.pop();
            out.add(cur.key);
            cur = cur.right;
        }
        return out;
    }

    /** Count-guided descend: ith smallest in O(log n), 1-indexed. */
    private static <K> K selectOf(Node<K> root, int rank) {
        if (rank < 1 || rank > sizeOf(root)) {
            throw new IndexOutOfBoundsException("rank " + rank + " of " + sizeOf(root));
        }
        Node<K> n = root;
        int r = rank;
        while (true) {
            int leftSize = sizeOf(n.left);
            if (r == leftSize + 1) return n.key;
            if (r <= leftSize) {
                n = n.left;
            } else {
                r -= leftSize + 1;
                n = n.right;
            }
        }
    }

    /** 1-indexed rank in O(log n); throws if the key is absent (matching {@code OrderedSet}). */
    private static <K> int rankOf(Node<K> root, K key, Comparator<? super K> order) {
        Node<K> n = root;
        int acc = 0;
        while (n != null) {
            int cmp = order.compare(key, n.key);
            if (cmp == 0) return acc + sizeOf(n.left) + 1;
            if (cmp < 0) {
                n = n.left;
            } else {
                acc += sizeOf(n.left) + 1;
                n = n.right;
            }
        }
        throw new NoSuchElementException("key not present: " + key);
    }

    /** Keys strictly less than {@code key}, in O(log n) via the count field. */
    private static <K> int countLessThan(Node<K> root, K key, Comparator<? super K> order) {
        Node<K> n = root;
        int acc = 0;
        while (n != null) {
            if (order.compare(key, n.key) <= 0) {
                n = n.left;
            } else {
                acc += sizeOf(n.left) + 1;
                n = n.right;
            }
        }
        return acc;
    }

    private static <K> int countInRangeOf(Node<K> root, K lo, K hi, Comparator<? super K> order) {
        Objects.requireNonNull(lo, "lo");
        Objects.requireNonNull(hi, "hi");
        if (order.compare(lo, hi) > 0) return 0;
        // |[lo,hi]| = |keys < hi| - |keys < lo| + (hi present ? 1 : 0)
        int below = countLessThan(root, hi, order) - countLessThan(root, lo, order);
        return below + (findOf(root, hi, order) != null ? 1 : 0);
    }

    /** Range-pruned iterative in-order walk: O(log n + |result|). */
    private static <K> List<K> rangeQueryOf(Node<K> root, K lo, K hi, Comparator<? super K> order) {
        Objects.requireNonNull(lo, "lo");
        Objects.requireNonNull(hi, "hi");
        List<K> out = new ArrayList<>();
        if (order.compare(lo, hi) > 0) return out;
        Deque<Node<K>> stack = new ArrayDeque<>();
        Node<K> cur = root;
        while (cur != null || !stack.isEmpty()) {
            while (cur != null) {
                cur = order.compare(cur.key, lo) < 0 ? cur.right : pushAndLeft(stack, cur);
            }
            if (stack.isEmpty()) break;
            Node<K> n = stack.pop();
            if (order.compare(n.key, hi) > 0) break;       // everything further is larger
            if (order.compare(n.key, lo) >= 0) out.add(n.key);
            cur = n.right;
        }
        return out;
    }

    private static <K> Node<K> pushAndLeft(Deque<Node<K>> stack, Node<K> n) {
        stack.push(n);
        return n.left;
    }
}
