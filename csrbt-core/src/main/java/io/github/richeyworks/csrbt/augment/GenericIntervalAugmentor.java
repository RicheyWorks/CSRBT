package io.github.richeyworks.csrbt.augment;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.TreeNode1;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Deque;
import java.util.List;
import java.util.Objects;

/**
 * Interval Tree augmentation and search over TYPED endpoints — the generic successor to the
 * {@code Integer}-bound {@link IntervalAugmentor} (outer-ring ADR, Phase 7: "generic interval
 * endpoints"). Same CLRS 14.3 algorithms, same tree; the encoding moves off the string tag and
 * the int augment slot onto {@link TreeNode1#getAugmentedRef()}, the additive generic slot:
 *
 * <pre>
 *   node.getData()          = low endpoint of the interval [lo, hi]     (the BST key, type E)
 *   node.getAugmentedRef()  = Ref{hi, maxHi}: this node's high endpoint + subtree max-hi
 *   node.getSize()          = intrinsic subtree count — order statistics keep working (ADR-002)
 *   node.getAugmentedValue(), node.getTag() = UNTOUCHED (the int path stays the specialization)
 * </pre>
 *
 * All ordering flows through one {@link Comparator} supplied at construction — epoch-millis
 * {@code Long}s, {@code Instant}s, {@code String}s, anything with a total order. Endpoint
 * values are stored as-is; the {@code Ref} payload is an immutable record, replaced on every
 * recompute and never mutated, which is what makes {@link TreeNode1#deepCopy}'s reference copy
 * of the slot safe (see the slot's field contract).
 *
 * <h2>Usage</h2>
 * <pre>
 *   OrderedSet&lt;Long&gt; set = OrderedSet.withNaturalOrder(new RedBlackStrategy&lt;&gt;());
 *   GenericIntervalAugmentor&lt;Long&gt; iv = GenericIntervalAugmentor.natural();
 *   iv.insertInterval(set, 1_720_000_000_000L, 1_720_000_060_000L);   // epoch-millis span
 *   iv.stabQuery(set, 1_720_000_030_000L);                            // intervals covering t
 * </pre>
 *
 * <p>Instances carry the comparator, so unlike the int version's static surface these are
 * instance methods; one augmentor instance serves one comparator and any number of trees.
 * {@code insertInterval} installs this augmentor on the set on first use (guarded, so repeat
 * inserts don't re-walk the tree). Duplicate {@code lo}: add-or-restamp, exactly like the int
 * version — the caller keeps one interval per distinct lo (a sidecar resolves duplicates, as
 * SmokeHouse's {@code IndexedStore} does today for int spans).</p>
 *
 * <p>Like the int version, queries walk the engine directly and follow the same read stance as
 * {@code TreeContext}: single-writer, quiescent reads. Payloads survive {@code setStrategy}
 * morphs and {@code selfRepair} (OrderedSet carries the ref slot across rebuilds exactly as it
 * carries tags), and {@code deepCopy}/clone (reference copy of immutable payloads). They do NOT
 * survive {@code FilePersistenceAdapter} round-trips — the ref slot is deliberately unserialized
 * in v1; rebuild interval indexes from their source after a load, the way SmokeHouse rebuilds
 * every index from the log.</p>
 *
 * <h2>CLRS INTERVAL-SEARCH theorem (unchanged)</h2>
 * If the tree contains an interval overlapping {@code [qlo, qhi]}, {@link #intervalSearch}
 * finds one in O(log n); if it returns {@code null}, no overlapping interval exists.
 * Overlap condition: {@code i.lo ≤ j.hi AND j.lo ≤ i.hi}, evaluated through the comparator.
 */
public final class GenericIntervalAugmentor<E> implements TreeNode1.Augmentor<E> {

    /** One interval, as returned by the query surface. */
    public record Interval<E>(E lo, E hi) { }

    /**
     * The per-node payload stored in {@link TreeNode1#getAugmentedRef()}. Immutable — the
     * augmentor replaces it on every recompute, never mutates it (the slot's contract).
     * {@code hi == null} means "not stamped yet": a node {@code add}ed but not yet through
     * {@link #insertInterval} reads as the degenerate point interval {@code [lo, lo]}, the
     * same fallback the int version's {@code parseHi} applies to a missing tag.
     */
    record Ref<E>(E hi, E maxHi) { }

    private final Comparator<? super E> order;

    private GenericIntervalAugmentor(Comparator<? super E> order) {
        this.order = Objects.requireNonNull(order, "order");
    }

    /** An augmentor whose endpoint ordering is {@code order}. */
    public static <E> GenericIntervalAugmentor<E> over(Comparator<? super E> order) {
        return new GenericIntervalAugmentor<>(order);
    }

    /** An augmentor over naturally ordered endpoints ({@code Long} epoch-millis, etc.). */
    public static <E extends Comparable<? super E>> GenericIntervalAugmentor<E> natural() {
        return new GenericIntervalAugmentor<>(Comparator.naturalOrder());
    }

    /** The endpoint ordering this augmentor navigates and prunes by. */
    public Comparator<? super E> order() {
        return order;
    }

    // ── The augmentor: maintain subtree max-hi in the ref slot ───────────────────

    /**
     * Sets {@code node.augmentedRef = Ref(hi, max(hi) in subtree)}. Called automatically on
     * every structural link (via {@code recomputeAugment}) and propagated bottom-up, exactly
     * like the int version writes {@code augmentedValue} — CLRS p.349's {@code x.max}, typed.
     */
    @Override
    public void apply(TreeNode1<E> node) {
        if (node.isNil()) {
            node.setAugmentedRef(null);
            return;
        }
        Ref<E> ref = refOf(node);
        E stampedHi = (ref == null) ? null : ref.hi();
        E maxHi = (stampedHi != null) ? stampedHi : node.getData();   // unstamped: [lo, lo]
        maxHi = maxOf(maxHi, subtreeMaxHi(node.getLeft()));
        maxHi = maxOf(maxHi, subtreeMaxHi(node.getRight()));
        node.setAugmentedRef(new Ref<>(stampedHi, maxHi));            // replace, never mutate
    }

    // ── Mutation ─────────────────────────────────────────────────────────────────

    /**
     * Insert interval {@code [lo, hi]}: add {@code lo} as the BST key (no-op if present),
     * stamp this augmentor's ref with the high endpoint, and re-augment the root path so
     * every ancestor's max-hi sees it. Add-or-restamp on duplicate {@code lo}, like the int
     * version. Installs this augmentor on the set on first use (identity-guarded).
     */
    public void insertInterval(OrderedSet<E> set, E lo, E hi) {
        if (order.compare(lo, hi) > 0) {
            throw new IllegalArgumentException("Invalid interval: lo=" + lo + " > hi=" + hi);
        }
        if (set.getAugmentor() != this) {
            set.setAugmentor(this);
        }
        set.add(lo);
        TreeNode1<E> node = set.getEngine().getRoot();
        while (!node.isNil()) {
            int c = node.compareKeyTo(lo);
            if (c == 0) {
                node.setAugmentedRef(new Ref<>(hi, hi));   // maxHi provisional; reaugment fixes it
                node.reaugment();
                return;
            }
            node = (c > 0) ? node.getLeft() : node.getRight();
        }
        throw new IllegalStateException("added lo=" + lo + " but could not navigate back to it");
    }

    // ── Queries ──────────────────────────────────────────────────────────────────

    /**
     * INTERVAL-SEARCH (CLRS 14.3, p.350): ONE interval overlapping {@code [qlo, qhi]}, or
     * {@code null} if none exists. O(log n). Same pruning theorem as the int version: if we
     * descend left, either the answer is there or the right subtree cannot contain one either
     * (because {@code max(left) < qlo} would have sent us right).
     */
    public Interval<E> intervalSearch(OrderedSet<E> set, E qlo, E qhi) {
        requireQuery(set, qlo, qhi);
        TreeNode1<E> x = set.getEngine().getRoot();
        while (!x.isNil()) {
            E lo = x.getData();
            E hi = hiOf(x);
            if (order.compare(lo, qhi) <= 0 && order.compare(qlo, hi) <= 0) {
                return new Interval<>(lo, hi);
            }
            TreeNode1<E> left = x.getLeft();
            E leftMax = subtreeMaxHi(left);
            x = (leftMax != null && order.compare(leftMax, qlo) >= 0) ? left : x.getRight();
        }
        return null;
    }

    /**
     * ALL intervals overlapping {@code [qlo, qhi]} — the pruned DFS the int version uses:
     * a subtree whose max-hi sorts before {@code qlo} cannot contain an overlap and is
     * skipped whole. O(n) worst case (output size can be O(n)).
     */
    public List<Interval<E>> intervalSearchAll(OrderedSet<E> set, E qlo, E qhi) {
        requireQuery(set, qlo, qhi);
        List<Interval<E>> results = new ArrayList<>();
        Deque<TreeNode1<E>> stack = new ArrayDeque<>();
        TreeNode1<E> root = set.getEngine().getRoot();
        if (!root.isNil()) stack.push(root);

        while (!stack.isEmpty()) {
            TreeNode1<E> node = stack.pop();
            E maxHi = subtreeMaxHi(node);
            if (maxHi == null || order.compare(maxHi, qlo) < 0) continue;   // prune whole subtree

            E lo = node.getData();
            E hi = hiOf(node);
            if (order.compare(lo, qhi) <= 0 && order.compare(qlo, hi) <= 0) {
                results.add(new Interval<>(lo, hi));
            }
            if (!node.getRight().isNil()) stack.push(node.getRight());
            if (!node.getLeft().isNil())  stack.push(node.getLeft());
        }
        return results;
    }

    /** Stabbing query: all intervals containing point {@code p} — {@code intervalSearchAll(p, p)}. */
    public List<Interval<E>> stabQuery(OrderedSet<E> set, E p) {
        return intervalSearchAll(set, p, p);
    }

    /** All intervals, in-order (sorted by lo) — the generic {@code dump}, machine-readable. */
    public List<Interval<E>> intervals(OrderedSet<E> set) {
        requireInstalled(set);
        List<Interval<E>> out = new ArrayList<>();
        Deque<TreeNode1<E>> stack = new ArrayDeque<>();
        TreeNode1<E> cur = set.getEngine().getRoot();
        while (!stack.isEmpty() || !cur.isNil()) {
            while (!cur.isNil()) { stack.push(cur); cur = cur.getLeft(); }
            cur = stack.pop();
            out.add(new Interval<>(cur.getData(), hiOf(cur)));
            cur = cur.getRight();
        }
        return out;
    }

    // ── Helpers ──────────────────────────────────────────────────────────────────

    /** This node's effective high endpoint: the stamped hi, or {@code lo} if never stamped. */
    public E hiOf(TreeNode1<E> node) {
        Ref<E> ref = refOf(node);
        return (ref != null && ref.hi() != null) ? ref.hi() : node.getData();
    }

    /** Subtree max-hi, or {@code null} for NIL/unaugmented — the typed {@code x.max}. */
    public E subtreeMaxHi(TreeNode1<E> node) {
        if (node == null || node.isNil()) return null;
        Ref<E> ref = refOf(node);
        return (ref != null) ? ref.maxHi() : node.getData();   // transiently unaugmented: floor
    }

    @SuppressWarnings("unchecked")
    private static <E> Ref<E> refOf(TreeNode1<E> node) {
        Object ref = node.getAugmentedRef();
        return (ref instanceof Ref<?> r) ? (Ref<E>) r : null;
    }

    private E maxOf(E a, E b) {
        if (a == null) return b;
        if (b == null) return a;
        return order.compare(a, b) >= 0 ? a : b;
    }

    private void requireQuery(OrderedSet<E> set, E qlo, E qhi) {
        if (order.compare(qlo, qhi) > 0) {
            throw new IllegalArgumentException("Invalid query interval: lo=" + qlo + " > hi=" + qhi);
        }
        requireInstalled(set);
    }

    /**
     * Queries prune by max-hi values only THIS augmentor maintains; walking a tree whose
     * augmentor is someone else would silently return wrong answers off stale/absent refs —
     * fail loud instead. (An empty never-augmented set is fine: there is nothing to miss.)
     */
    private void requireInstalled(OrderedSet<E> set) {
        if (!set.isEmpty() && set.getAugmentor() != this) {
            throw new IllegalStateException(
                    "this GenericIntervalAugmentor is not installed on the set (augmentor="
                            + set.getAugmentor().getClass().getSimpleName()
                            + "); insert through insertInterval, or setAugmentor first");
        }
    }
}
