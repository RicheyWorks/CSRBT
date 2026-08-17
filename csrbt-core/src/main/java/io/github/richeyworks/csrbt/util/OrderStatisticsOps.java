package io.github.richeyworks.csrbt.util;

import io.github.richeyworks.csrbt.RedBlackTree;
import io.github.richeyworks.csrbt.TreeNode1;

import java.util.NoSuchElementException;

/**
 * Dynamic Order-Statistics on an augmented Red-Black Tree.
 * CLRS 4th ed., Chapter 14.1 — "Dynamic order statistics", pp. 339–345.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * PREREQUISITE (now intrinsic — always satisfied):
 *   node.getSize() == size of subtree rooted at node
 *   i.e. x.size = x.left.size + x.right.size + 1
 *
 *   Subtree size is maintained as an intrinsic node attribute (like height and
 *   black-height), NOT via the pluggable augmentor. Order statistics therefore
 *   work regardless of which augmentor is installed — e.g. SELECT / RANK run
 *   correctly on a tree that is simultaneously using IntervalAugmentor for
 *   max-hi in augmentedValue. (See ADR-002: this resolved the prior overloading
 *   where one int field meant size OR max-hi, making the two mutually exclusive.)
 *
 * This gives us two O(log n) operations that would otherwise cost O(n):
 *
 *   OS-SELECT(x, i) — p.341  →  find the ith smallest key
 *   OS-RANK(T, x)   — p.342  →  find the rank of a given key
 *
 * Everything else below (median, percentile, countInRange, predecessor,
 * successor) is built on top of these two, and inherits O(log n).
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * NOTE on int-vs-K: ranks and percentiles are positional integers and stay
 * {@code int} ({@link #select(int)}, {@link #percentile(int)}); keys are {@code K}
 * ({@link #rank}, {@link #successor}, {@link #countInRange}, …). The {@code lo}/
 * {@code hi} range guards compare two query keys, so they route through the
 * engine's {@link RedBlackTree#comparator()} rather than a node.
 */
public class OrderStatisticsOps<K> {

    private final RedBlackTree<K> tree;

    public OrderStatisticsOps(RedBlackTree<K> tree) {
        this.tree = tree;
    }

    // ── OS-SELECT ─────────────────────────────────────────────────────────────

    /**
     * OS-SELECT(root, i) — CLRS 14.1, p.341
     *
     * Returns the node with the ith smallest key (1-indexed).
     *
     * @param rank  1-indexed rank (1 = minimum, n = maximum)
     * @throws IndexOutOfBoundsException if {@code rank < 1} or {@code rank > n}
     */
    public TreeNode1<K> select(int rank) {
        int n = subtreeSize(tree.getRoot());
        if (rank < 1 || rank > n) {
            throw new IndexOutOfBoundsException(
                    "OS-SELECT: rank=" + rank + " out of bounds [1," + n + "]");
        }
        return osSelect(tree.getRoot(), rank);
    }

    private TreeNode1<K> osSelect(TreeNode1<K> x, int i) {
        while (!x.isNil()) {
            int r = subtreeSize(x.getLeft()) + 1;  // CLRS: r ← x.left.size + 1
            if      (i == r) return x;
            else if (i <  r) x = x.getLeft();
            else           { x = x.getRight(); i -= r; }  // adjust i
        }
        return tree.getNIL(); // unreachable if preconditions hold
    }

    // ── OS-RANK ───────────────────────────────────────────────────────────────

    /**
     * OS-RANK(T, x) — CLRS 14.1, p.342
     *
     * Returns the rank (1-indexed position in sorted order) of the node
     * with the given key.
     *
     * @throws NoSuchElementException if value is not in the tree
     */
    public int rank(K value) {
        TreeNode1<K> x = findNode(value);
        if (x.isNil()) throw new NoSuchElementException(
                "OS-RANK: value=" + value + " not found in tree");
        return osRank(x);
    }

    private int osRank(TreeNode1<K> x) {
        int r = subtreeSize(x.getLeft()) + 1;       // CLRS: r ← x.left.size + 1
        TreeNode1<K> y = x;
        while (y.getParent() != null && !y.getParent().isNil()) {
            if (y == y.getParent().getRight()) {
                r += subtreeSize(y.getParent().getLeft()) + 1;
            }
            y = y.getParent();
        }
        return r;
    }

    // ── Derived operations (all O(log n) via OS-SELECT / OS-RANK) ────────────

    /**
     * Lower median — equivalent to CLRS Chapter 9 median but O(log n)
     * instead of the O(n) linear-time algorithm.
     */
    public TreeNode1<K> median() {
        int n = subtreeSize(tree.getRoot());
        if (n == 0) return tree.getNIL();
        return select((n + 1) / 2);
    }

    /**
     * kth percentile node (0–100).
     * percentile(50) == median().
     *
     * <p>The derived rank is clamped to [1, n], so a {@code pct} outside 0–100 saturates at the
     * minimum or the maximum instead of throwing. That is deliberate and is the rule the other
     * two {@code RankedSet} implementations state explicitly — an out-of-range percentile must
     * not make one engine throw where its peers answer, because VERIFIED voting compares
     * thrown-exception classes.</p>
     */
    public TreeNode1<K> percentile(int pct) {
        int n = subtreeSize(tree.getRoot());
        if (n == 0) return tree.getNIL();
        int rank = Math.max(1, Math.min(n, (int) Math.ceil(pct / 100.0 * n)));
        return select(rank);
    }

    /**
     * Minimum and maximum in O(log n) via OS-SELECT.
     */
    public TreeNode1<K> minimum() { return select(1); }
    public TreeNode1<K> maximum() {
        int n = subtreeSize(tree.getRoot());
        return n == 0 ? tree.getNIL() : select(n);
    }

    /**
     * Successor of value x: the node with the smallest key > x.
     * Uses OS-RANK to find position, then OS-SELECT for rank+1.
     * O(log n).
     */
    public TreeNode1<K> successor(K value) {
        int r = rank(value); // throws if not found
        int n = subtreeSize(tree.getRoot());
        return r < n ? select(r + 1) : tree.getNIL();
    }

    /**
     * Predecessor of value x: the node with the largest key {@code < x}.
     * O(log n).
     */
    public TreeNode1<K> predecessor(K value) {
        int r = rank(value);
        return r > 1 ? select(r - 1) : tree.getNIL();
    }

    /**
     * Count of elements in closed range [lo, hi].
     * O(log n) — no scan, just two rank lookups.
     */
    public int countInRange(K lo, K hi) {
        if (compareKeys(lo, hi) > 0 || subtreeSize(tree.getRoot()) == 0) return 0;
        int rankLo = rankCeiling(lo);   // rank of smallest element >= lo
        int rankHi = rankFloor(hi);     // rank of largest element  <= hi
        return Math.max(0, rankHi - rankLo + 1);
    }

    /**
     * Returns all elements in [lo, hi] as an ordered list.
     * O(log n + k) where k = count — enumerate by OS-SELECT from rankLo to rankHi.
     */
    public java.util.List<K> rangeQuery(K lo, K hi) {
        java.util.List<K> result = new java.util.ArrayList<>();
        if (compareKeys(lo, hi) > 0) return result;
        int rankLo = rankCeiling(lo);
        int rankHi = rankFloor(hi);
        for (int r = rankLo; r <= rankHi; r++) {
            result.add(select(r).getData());
        }
        return result;
    }

    // ── Internal helpers ──────────────────────────────────────────────────────

    /** Order two query keys through the engine's ordering authority. */
    private int compareKeys(K a, K b) {
        return tree.comparator().compare(a, b);
    }

    /** Rank of the smallest element >= value (ceiling). */
    private int rankCeiling(K value) {
        TreeNode1<K> candidate = tree.getNIL();
        TreeNode1<K> x = tree.getRoot();
        while (!x.isNil()) {
            if (x.compareKeyTo(value) >= 0) { candidate = x; x = x.getLeft(); }
            else                            { x = x.getRight(); }
        }
        return candidate.isNil() ? subtreeSize(tree.getRoot()) + 1 : osRank(candidate);
    }

    /** Rank of the largest element <= value (floor). */
    private int rankFloor(K value) {
        TreeNode1<K> candidate = tree.getNIL();
        TreeNode1<K> x = tree.getRoot();
        while (!x.isNil()) {
            if (x.compareKeyTo(value) <= 0) { candidate = x; x = x.getRight(); }
            else                            { x = x.getLeft();  }
        }
        return candidate.isNil() ? 0 : osRank(candidate);
    }

    private int subtreeSize(TreeNode1<K> node) {
        // Reads the node's INTRINSIC subtree size, not the pluggable augment slot,
        // so order statistics work even when a custom augmentor (e.g.
        // IntervalAugmentor's max-hi) occupies augmentedValue. See ADR-002.
        return (node == null || node.isNil()) ? 0 : node.getSize();
    }

    private TreeNode1<K> findNode(K value) {
        TreeNode1<K> x = tree.getRoot();
        while (!x.isNil()) {
            if (x.compareKeyTo(value) == 0) return x;
            x = (x.compareKeyTo(value) > 0) ? x.getLeft() : x.getRight();
        }
        return tree.getNIL();
    }
}
