package core.util;

import core.RedBlackTree;
import core.TreeNode1;

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
 * WHY THIS WORKS (the core insight from Cormen):
 *   We don't sort or scan — we USE the stored subtree sizes as rank
 *   accumulators.  Every rotation in the RB strategy already maintains the
 *   intrinsic size through TreeNode1.setLeft / setRight → recomputeSize.
 *   The size maintenance cost per rotation is O(1), so insert/delete
 *   remain O(log n) even with augmentation.
 */
public class OrderStatisticsOps {

    private final RedBlackTree tree;

    public OrderStatisticsOps(RedBlackTree tree) {
        this.tree = tree;
    }

    // ── OS-SELECT ─────────────────────────────────────────────────────────────

    /**
     * OS-SELECT(root, i) — CLRS 14.1, p.341
     *
     * Returns the node with the ith smallest key (1-indexed).
     *
     * Algorithm:
     *   r ← x.left.size + 1       // rank of x within its own subtree
     *   if i = r  → x is the answer
     *   if i < r  → recurse into left subtree (same rank)
     *   if i > r  → recurse into right subtree (adjusted rank: i − r)
     *
     * The iterative version below is semantically identical to CLRS Fig 14.1
     * but avoids stack overhead.
     *
     * @param rank  1-indexed rank (1 = minimum, n = maximum)
     * @throws IndexOutOfBoundsException if rank < 1 or rank > n
     */
    public TreeNode1 select(int rank) {
        int n = subtreeSize(tree.getRoot());
        if (rank < 1 || rank > n) {
            throw new IndexOutOfBoundsException(
                    "OS-SELECT: rank=" + rank + " out of bounds [1," + n + "]");
        }
        return osSelect(tree.getRoot(), rank);
    }

    private TreeNode1 osSelect(TreeNode1 x, int i) {
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
     * with the given value.
     *
     * Algorithm:
     *   r ← x.left.size + 1      // x's rank within its own subtree
     *   y ← x
     *   while y ≠ root:
     *     if y is a right child:
     *       r ← r + y.parent.left.size + 1   // add left sibling and parent
     *     y ← y.parent
     *   return r
     *
     * Intuition: as you walk up the tree, every time you came from a right
     * child you "skip over" everything in the left subtree plus the parent.
     *
     * @throws NoSuchElementException if value is not in the tree
     */
    public int rank(int value) {
        TreeNode1 x = findNode(value);
        if (x.isNil()) throw new NoSuchElementException(
                "OS-RANK: value=" + value + " not found in tree");
        return osRank(x);
    }

    private int osRank(TreeNode1 x) {
        int r = subtreeSize(x.getLeft()) + 1;       // CLRS: r ← x.left.size + 1
        TreeNode1 y = x;
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
     *
     * This is the "free lunch" that augmented trees give you: once you have
     * OS-SELECT, median is just select(⌊(n+1)/2⌋) — no partitioning needed.
     */
    public TreeNode1 median() {
        int n = subtreeSize(tree.getRoot());
        if (n == 0) return tree.getNIL();
        return select((n + 1) / 2);
    }

    /**
     * kth percentile node (0–100).
     * percentile(50) == median().
     */
    public TreeNode1 percentile(int pct) {
        int n = subtreeSize(tree.getRoot());
        if (n == 0) return tree.getNIL();
        int rank = Math.max(1, Math.min(n, (int) Math.ceil(pct / 100.0 * n)));
        return select(rank);
    }

    /**
     * Minimum and maximum in O(log n) via OS-SELECT.
     * (Equivalent to walking left/right spine but expressed through the
     * order-statistics abstraction for consistency.)
     */
    public TreeNode1 minimum() { return select(1); }
    public TreeNode1 maximum() {
        int n = subtreeSize(tree.getRoot());
        return n == 0 ? tree.getNIL() : select(n);
    }

    /**
     * Successor of value x: the node with the smallest key > x.
     * Uses OS-RANK to find position, then OS-SELECT for rank+1.
     * O(log n).
     */
    public TreeNode1 successor(int value) {
        int r = rank(value); // throws if not found
        int n = subtreeSize(tree.getRoot());
        return r < n ? select(r + 1) : tree.getNIL();
    }

    /**
     * Predecessor of value x: the node with the largest key < x.
     * O(log n).
     */
    public TreeNode1 predecessor(int value) {
        int r = rank(value);
        return r > 1 ? select(r - 1) : tree.getNIL();
    }

    /**
     * Count of elements in closed range [lo, hi].
     * O(log n) — no scan, just two rank lookups.
     *
     * CLRS connection: this is the "interval stabbing" query on a rank space,
     * analogous to what augmented interval trees solve in key space (Ch 14.3).
     */
    public int countInRange(int lo, int hi) {
        if (lo > hi || subtreeSize(tree.getRoot()) == 0) return 0;
        int rankLo = rankCeiling(lo);   // rank of smallest element >= lo
        int rankHi = rankFloor(hi);     // rank of largest element  <= hi
        return Math.max(0, rankHi - rankLo + 1);
    }

    /**
     * Returns all elements in [lo, hi] as an ordered list.
     * O(log n + k) where k = count — enumerate by OS-SELECT from rankLo to rankHi.
     */
    public java.util.List<Integer> rangeQuery(int lo, int hi) {
        java.util.List<Integer> result = new java.util.ArrayList<>();
        if (lo > hi) return result;
        int rankLo = rankCeiling(lo);
        int rankHi = rankFloor(hi);
        for (int r = rankLo; r <= rankHi; r++) {
            result.add(select(r).getData());
        }
        return result;
    }

    // ── Internal helpers ──────────────────────────────────────────────────────

    /** Rank of the smallest element >= value (ceiling). */
    private int rankCeiling(int value) {
        TreeNode1 candidate = tree.getNIL();
        TreeNode1 x = tree.getRoot();
        while (!x.isNil()) {
            if (x.compareKeyTo(value) >= 0) { candidate = x; x = x.getLeft(); }
            else                            { x = x.getRight(); }
        }
        return candidate.isNil() ? subtreeSize(tree.getRoot()) + 1 : osRank(candidate);
    }

    /** Rank of the largest element <= value (floor). */
    private int rankFloor(int value) {
        TreeNode1 candidate = tree.getNIL();
        TreeNode1 x = tree.getRoot();
        while (!x.isNil()) {
            if (x.compareKeyTo(value) <= 0) { candidate = x; x = x.getRight(); }
            else                            { x = x.getLeft();  }
        }
        return candidate.isNil() ? 0 : osRank(candidate);
    }

    private int subtreeSize(TreeNode1 node) {
        // Reads the node's INTRINSIC subtree size, not the pluggable augment slot,
        // so order statistics work even when a custom augmentor (e.g.
        // IntervalAugmentor's max-hi) occupies augmentedValue. See ADR-002.
        return (node == null || node.isNil()) ? 0 : node.getSize();
    }

    private TreeNode1 findNode(int value) {
        TreeNode1 x = tree.getRoot();
        while (!x.isNil()) {
            if (x.compareKeyTo(value) == 0) return x;
            x = (x.compareKeyTo(value) > 0) ? x.getLeft() : x.getRight();
        }
        return tree.getNIL();
    }
}
