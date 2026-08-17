package io.github.richeyworks.csrbt.augment;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.TreeNode1;

import java.util.ArrayList;
import java.util.List;
import java.util.Stack;

/**
 * Interval Tree augmentation and search.
 * CLRS 4th ed., Chapter 14.3 — "Interval trees", pp. 348–354.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * ENCODING CONVENTION (works within existing TreeNode1 structure):
 *
 *   node.getData()            = low endpoint of the interval  [lo, hi]
 *   node.getTag()             = String.valueOf(hi)  (high endpoint)
 *   node.getAugmentedValue()  = max(hi) across the entire subtree  ← augmentor
 *   node.getSize()            = subtree node count (intrinsic; independent of this
 *                               augmentor, so dynamic order statistics keep working
 *                               on the same interval tree — see ADR-002)
 *
 * To insert interval [lo, hi]:
 *   context.add(lo);
 *   tree.search(lo).setTag(String.valueOf(hi));  // set high endpoint
 *   // augmentor propagates max(hi) up automatically via recomputeAugment
 *
 * SETUP:
 *   context.setAugmentor(IntervalAugmentor.INSTANCE);
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * ADR-002 step 2: this is an INTEGER-interval augmentor — the high endpoint and
 * subtree max-hi are {@code int} (encoded via a parsed string tag and the int
 * {@code augmentedValue} slot). It therefore implements
 * {@code TreeNode1.Augmentor<Integer>} and is installed only on
 * {@code TreeNode1<Integer>} trees. Generic intervals (typed endpoints) landed
 * 2026-07-14 as {@link GenericIntervalAugmentor}, on the additive
 * {@code TreeNode1.augmentedRef} slot; this int/tag encoding stays as the
 * specialization and is untouched by it.
 * ─────────────────────────────────────────────────────────────────────────────
 * CLRS INTERVAL-SEARCH theorem:
 *   If tree contains an interval that overlaps [qlo, qhi], the algorithm
 *   finds one such interval in O(log n).
 *   If it terminates returning NIL, no overlapping interval exists.
 *
 * Overlap condition:  i.lo ≤ j.hi  AND  j.lo ≤ i.hi
 * ─────────────────────────────────────────────────────────────────────────────
 */
public class IntervalAugmentor implements TreeNode1.Augmentor<Integer> {

    public static final IntervalAugmentor INSTANCE = new IntervalAugmentor();

    /**
     * Augmentor: sets node.augmentedValue = max(hi) in the subtree.
     *
     * Called automatically on every setLeft / setRight (propagates upward
     * via recomputeAugmentAndPropagate in TreeNode1).
     *
     * CLRS p.349: "Each node x contains an interval x.int and a key x.int.lo.
     *  We also store x.max = maximum hi endpoint in subtree rooted at x."
     */
    @Override
    public void apply(TreeNode1<Integer> node) {
        if (node.isNil()) {
            node.setAugmentedValue(Integer.MIN_VALUE);
            return;
        }

        int ownHi    = parseHi(node);
        int leftMax  = node.getLeft().isNil()  ? Integer.MIN_VALUE : node.getLeft().getAugmentedValue();
        int rightMax = node.getRight().isNil() ? Integer.MIN_VALUE : node.getRight().getAugmentedValue();

        node.setAugmentedValue(Math.max(ownHi, Math.max(leftMax, rightMax)));
    }

    // ── INTERVAL-SEARCH ───────────────────────────────────────────────────────

    /**
     * INTERVAL-SEARCH(T, i) — CLRS 14.3, p.350
     *
     * Finds ONE interval in T that overlaps [qlo, qhi], or NIL.
     * O(log n).
     *
     * Algorithm:
     *   x ← root
     *   while x ≠ NIL and i doesn't overlap x:
     *     if x.left ≠ NIL and x.left.max ≥ i.lo:
     *       x ← x.left           // left subtree might contain an overlap
     *     else:
     *       x ← x.right          // no overlap possible in left subtree
     *
     * Correctness argument (CLRS Theorem 14.2):
     *   If we go left, either we find an overlap there, or the right subtree
     *   cannot contain any overlap either (because {@code max(left) < i.lo}).
     *   So we never miss a valid answer.
     */
    public static TreeNode1<Integer> intervalSearch(TreeContext context, int qlo, int qhi) {
        requireQuery(qlo, qhi);
        TreeNode1<Integer> x = context.getTree().getRoot();

        while (!x.isNil()) {
            if (overlaps(x, qlo, qhi)) return x;   // found an overlapping interval

            int leftMax = x.getLeft().isNil() ? Integer.MIN_VALUE
                                               : x.getLeft().getAugmentedValue();
            if (leftMax >= qlo) {
                x = x.getLeft();    // left subtree has potential overlap
            } else {
                x = x.getRight();   // left subtree cannot possibly overlap
            }
        }
        return context.getTree().getNIL(); // no overlap found
    }

    /**
     * Find ALL intervals overlapping [qlo, qhi].
     * Not in CLRS but a natural extension — O(k · log n) where k = result count.
     *
     * Strategy: repeatedly call INTERVAL-SEARCH and remove found intervals
     * temporarily, collecting results, then restore. We avoid mutation by
     * doing a full DFS instead, which is O(n) but correct.
     *
     * The O(n) DFS is acceptable for "find all" since output size k can be O(n).
     */
    public static List<int[]> intervalSearchAll(TreeContext context, int qlo, int qhi) {
        requireQuery(qlo, qhi);
        List<int[]> results = new ArrayList<>();
        Stack<TreeNode1<Integer>> stack = new Stack<>();
        TreeNode1<Integer> root = context.getTree().getRoot();
        if (!root.isNil()) stack.push(root);

        while (!stack.isEmpty()) {
            TreeNode1<Integer> node = stack.pop();

            // Prune: if this subtree's max hi < qlo, no overlap possible
            if (node.getAugmentedValue() < qlo) continue;

            if (overlaps(node, qlo, qhi)) {
                results.add(new int[]{ node.getData(), parseHi(node) });
            }
            if (!node.getRight().isNil()) stack.push(node.getRight());
            if (!node.getLeft().isNil())  stack.push(node.getLeft());
        }
        return results;
    }

    // ── Interval point-stabbing query ─────────────────────────────────────────

    /**
     * "Stabbing query" — find all intervals containing a single point p.
     * {@code [lo, hi]} contains p iff {@code lo <= p <= hi}.
     * Equivalent to intervalSearchAll(p, p).
     */
    public static List<int[]> stabQuery(TreeContext context, int p) {
        return intervalSearchAll(context, p, p);
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    /**
     * Reject an inverted query range, the way {@link #insertInterval} rejects an inverted
     * <em>stored</em> one — and the way {@code GenericIntervalAugmentor.requireQuery} already
     * rejected both (edge-case pass 2026-08-17). {@code [qlo, qhi]} with {@code qlo > qhi} is not
     * an empty range here the way it is for {@code countInRange}: the overlap test
     * {@code lo <= qhi && qlo <= hi} is <em>satisfied</em> by exactly the intervals that straddle
     * the inversion, so {@code intervalSearchAll(9, 3)} answered with a subset of the tree rather
     * than with nothing or with a complaint. Same defect class as the parity findings the sixth
     * pass closed: two implementations of one operation, one of them right.
     *
     * @throws IllegalArgumentException if {@code qlo > qhi}
     */
    private static void requireQuery(int qlo, int qhi) {
        if (qlo > qhi) {
            throw new IllegalArgumentException("Invalid query interval: lo=" + qlo + " > hi=" + qhi);
        }
    }

    /**
     * Two intervals [a.lo, a.hi] and [qlo, qhi] overlap iff:
     *   a.lo ≤ qhi  AND  qlo ≤ a.hi
     * (They DON'T overlap only if one ends before the other begins.)
     */
    private static boolean overlaps(TreeNode1<Integer> node, int qlo, int qhi) {
        int lo = node.getData();
        int hi = parseHi(node);
        return lo <= qhi && qlo <= hi;
    }

    /**
     * Reads the high endpoint from the node's tag.
     * Falls back to lo (degenerate point interval) if tag is absent or invalid.
     */
    public static int parseHi(TreeNode1<Integer> node) {
        if (node.isNil()) return Integer.MIN_VALUE;
        String tag = node.getTag();
        if (tag == null || tag.isEmpty()) return node.getData();
        try {
            return Integer.parseInt(tag);
        } catch (NumberFormatException e) {
            return node.getData(); // safe fallback
        }
    }

    /**
     * Convenience: insert an interval [lo, hi] into the context.
     * Sets up both the BST key (lo) and the tag (hi) in one call.
     *
     * Usage:
     *   context.setAugmentor(IntervalAugmentor.INSTANCE);
     *   IntervalAugmentor.insertInterval(context, 15, 23);
     *   IntervalAugmentor.insertInterval(context,  6, 10);
     *   TreeNode1 hit = IntervalAugmentor.intervalSearch(context, 12, 14);
     */
    public static void insertInterval(TreeContext context, int lo, int hi) {
        if (lo > hi) throw new IllegalArgumentException(
                "Invalid interval: lo=" + lo + " > hi=" + hi);
        // Ensure the context (and therefore every node it creates) uses the
        // interval augmentor, so max-hi is maintained across this and all other
        // nodes on the root path during propagation below. Guarded so repeated
        // inserts don't trigger an O(n) whole-tree re-augment each time.
        if (context.getAugmentor() != INSTANCE) context.setAugmentor(INSTANCE);
        context.add(lo);
        // Navigate to the node just inserted and stamp the high endpoint, then
        // force a re-augmentation up the tree: setTag alone does NOT trigger the
        // augmentor, so without reaugment() the subtree max-hi would stay stale
        // (computed from lo while the tag was still empty).
        TreeNode1<Integer> node = context.getTree().getRoot();
        while (!node.isNil()) {
            if (node.compareKeyTo(lo) == 0) {
                node.setTag(String.valueOf(hi));
                node.reaugment();
                break;
            }
            node = (node.compareKeyTo(lo) > 0) ? node.getLeft() : node.getRight();
        }
    }

    /**
     * Prints all intervals in the tree (in-order = sorted by lo).
     */
    public static String dump(TreeContext context) {
        StringBuilder sb = new StringBuilder("Intervals (sorted by lo):\n");
        Stack<TreeNode1<Integer>> stack = new Stack<>();
        TreeNode1<Integer> curr = context.getTree().getRoot();
        while (!stack.isEmpty() || !curr.isNil()) {
            while (!curr.isNil()) { stack.push(curr); curr = curr.getLeft(); }
            curr = stack.pop();
            sb.append(String.format("  [%4d, %4d]  max=%d%n",
                    curr.getData(), parseHi(curr), curr.getAugmentedValue()));
            curr = curr.getRight();
        }
        return sb.toString();
    }
}
