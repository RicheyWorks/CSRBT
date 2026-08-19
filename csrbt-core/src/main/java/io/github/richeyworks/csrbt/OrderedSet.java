package io.github.richeyworks.csrbt;

import io.github.richeyworks.csrbt.event.TreeEvent;
import io.github.richeyworks.csrbt.event.TreeEventListener;
import io.github.richeyworks.csrbt.interfaces.AugmentedTree;
import io.github.richeyworks.csrbt.interfaces.OrderedCollection;
import io.github.richeyworks.csrbt.interfaces.RankedSet;
import io.github.richeyworks.csrbt.interfaces.SelfHealingTree;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;
import io.github.richeyworks.csrbt.util.OrderStatisticsOps;
import io.github.richeyworks.csrbt.util.StrategyHealthCheck;
import io.github.richeyworks.csrbt.control.StrategyMorphTarget;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Deque;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.TreeSet;
import java.util.concurrent.locks.StampedLock;
import java.util.function.Supplier;

/**
 * Generic, client-facing ordered set of {@code K} keys over the strategy-driven
 * {@link RedBlackTree} engine (ADR-002 step 4, the {@code OrderedSet<K>} facade).
 *
 * <p>Ordering is supplied by a pluggable {@link Comparator}; {@link #withNaturalOrder}
 * is the convenience factory for {@link Comparable} keys. This is the key-type-agnostic
 * core of what {@code TreeContext} used to do inline: dedup-guarded add/remove with a
 * size counter, dynamic order statistics, a health-gated strategy morph, a sliding
 * window, and pluggable augmentation. Genuinely {@code Integer}-bound concerns -- undo
 * history, snapshot persistence, interval helpers, cloning -- deliberately stay on the
 * {@code TreeContext} adapter (step 4 keeps this facade dependency-light; persistence is
 * step 5).</p>
 *
 * <p><b>Concurrency (ADR-004 R1):</b> one writer at a time (mutators serialize on an internal
 * monitor), and concurrent reads are <em>torn-read-free</em>: every public read either runs
 * optimistically and is discarded unless a {@link StampedLock} stamp validates (no write
 * overlapped it), or holds the shared read lock. Public reads never splay — they descend the
 * tree through a strategy-independent lookup, so a Splay-backed set keeps its move-to-root
 * adaptivity on the write path only. The optimistic walk is step-bounded (a reader overlapping
 * a rotation can transiently chase a cycle), falling back to the locked path; legitimately deep
 * trees (e.g. a degenerate splay chain) simply take the locked path every time. Accessors such
 * as {@link #getEngine()} still expose live internal structure and bypass all of this — they
 * remain a single-threaded diagnostics seam. Set {@link #OPTIMISTIC_READS} to {@code false} to
 * restore the pre-R1 unguarded reads wholesale.</p>
 */
public class OrderedSet<K> implements SelfHealingTree, OrderedCollection<K>, RankedSet<K>,
        AugmentedTree<K>, StrategyMorphTarget<K> {

    private RedBlackTree<K> tree;
    private final Comparator<? super K> keyOrder;
    private OrderStatisticsOps<K> os;            // rebuilt whenever the engine is replaced

    private int size = 0;
    private TreeNode1.Augmentor<K> augmentor = TreeNode1.defaultAugmentor();

    // -- sliding-window (0 = unbounded) --
    private int maxSize = 0;
    private final LinkedHashSet<K> liveOrder = new LinkedHashSet<>();

    // -- metrics --
    private long totalInsertTime = 0;
    private long totalDeleteTime = 0;
    private int  insertCount = 0;
    private int  deleteCount = 0;

    private final Object lock = new Object();

    // -- structured events (ADR-009 P3); null = unobserved, the allocation-free default --
    private volatile TreeEventListener<K> events;

    /**
     * Register a structured-event listener (ADR-009 P3); {@code null} unregisters. Events
     * mirror the {@code event=...} log lines: effective inserts/removes, window evictions,
     * morph attempts (with the health-gate verdict), and self-repairs. With no listener the
     * write path allocates nothing for events. See {@link TreeEventListener} for the
     * fast/non-reentrant contract.
     */
    public void setEventListener(TreeEventListener<K> listener) { this.events = listener; }

    /**
     * The registered structured-event listener, or {@code null} when this set is unobserved.
     *
     * <p>The reader half of {@link #setEventListener}, added so a caller that <em>replaces</em> a
     * set can carry its observer across (audit 2026-08-18, item A): {@code TreeContext.loadSnapshot}
     * adopts the deserialized context's set wholesale, and without a way to read the live
     * listener back it had no way to re-attach it — the registration was silently dropped and
     * every subsequent event went nowhere. The same shape as reading {@link #getMaxSize()} before
     * the adoption and re-applying it afterwards.</p>
     *
     * @return the listener registered by {@link #setEventListener}, or {@code null}
     */
    public TreeEventListener<K> getEventListener() { return events; }

    /**
     * The thread currently inside {@link #emit}, or {@code null}. Written and read only under
     * {@code lock} (every mutator and {@code emit} itself hold it), so no volatile is needed.
     * See {@link #refuseReentrantWrite}.
     */
    private Thread emittingThread;

    /**
     * Forward to the listener, swallowing anything it throws (hardening M-1): emit is called on the
     * write path under the write stamp, after the mutation has committed — a throwing listener must
     * not convert a successful insert into an apparent failure or poison every subsequent write.
     * Call only after a null check.
     *
     * <p>The listener runs with the write stamp still held, so the mutator's thread is recorded
     * for the duration — see {@link #refuseReentrantWrite} for what that buys.</p>
     */
    private void emit(TreeEvent<K> e) {
        Thread outer = emittingThread;
        emittingThread = Thread.currentThread();
        try {
            events.onEvent(e);
        } catch (RuntimeException listenerFault) {
            // Observability must never break the data plane; the listener contract says fast +
            // non-throwing, and a violation is the listener's bug, not this write's.
        } finally {
            emittingThread = outer;
        }
    }

    /**
     * Refuse a mutation issued from inside a {@link TreeEventListener} callback (edge-case pass
     * 2026-08-17). {@link TreeEventListener} already forbids reentry ("reentry can deadlock"), and
     * that is exactly what happened: {@link #emit} runs with {@code readGuard}'s write stamp held,
     * and a {@link StampedLock} is <em>not</em> reentrant, so a listener calling back into
     * {@code add}/{@code remove}/{@code clear}/… parked the mutating thread against itself
     * <b>forever</b> — no exception, no stack overflow, no progress, and the monitor still held so
     * every other writer blocked behind it.
     *
     * <p>Documented or not, a silent permanent hang is the worst way to report a contract
     * violation, and it is the one failure this class cannot recover from. The listener's own
     * exceptions are already swallowed (M-1); this makes its reentry equally survivable by naming
     * it. Costs one field read per mutator, inside the monitor the mutator already holds, and the
     * field is only ever non-null while a registered listener is actually running.</p>
     */
    private void refuseReentrantWrite(String op) {
        if (emittingThread == Thread.currentThread()) {
            throw new IllegalStateException(
                    op + ": a TreeEventListener must not call back into the set it is observing "
                    + "(the write lock is held for the callback and is not reentrant)");
        }
    }

    // -- ADR-004 R1: torn-read-free concurrent reads --

    /** Rollback constant: {@code false} restores the pre-R1 unguarded read walk verbatim. */
    static final boolean OPTIMISTIC_READS = true;

    /** Writers stamp mutations; readers validate optimistic walks or hold the shared lock. */
    private final StampedLock readGuard = new StampedLock();

    /** Thrown (stacklessly) when a step-bounded optimistic walk suspects a torn tree. */
    private static final class TornReadException extends RuntimeException {
        static final TornReadException INSTANCE = new TornReadException();
        private TornReadException() { super(null, null, false, false); }
    }

    public OrderedSet(TreeStrategy<K> strategy, Comparator<? super K> keyOrder) {
        if (strategy == null) throw new IllegalArgumentException("strategy cannot be null");
        if (keyOrder == null) throw new IllegalArgumentException("keyOrder cannot be null");
        this.keyOrder = keyOrder;
        this.tree = new RedBlackTree<>(strategy, keyOrder);
        this.os   = new OrderStatisticsOps<>(tree);
    }

    /** Convenience factory for naturally-ordered {@link Comparable} keys. */
    public static <K extends Comparable<? super K>> OrderedSet<K> withNaturalOrder(TreeStrategy<K> strategy) {
        return new OrderedSet<>(strategy, Comparator.naturalOrder());
    }

    /**
     * Build an ordered set directly from an ASCENDING, DISTINCT key list in O(n), bypassing the
     * O(n log n) repeated-insert path: a balanced, black-height-correct red-black tree is built
     * bottom-up with no rotations. Ideal for bulk-loading a known-sorted run (e.g. from an external
     * sort engine). The list must be strictly ascending under {@code keyOrder}; this is validated.
     */
    public static <K> OrderedSet<K> fromSorted(List<K> ascendingDistinct, TreeStrategy<K> strategy,
                                               Comparator<? super K> keyOrder) {
        OrderedSet<K> set = new OrderedSet<>(strategy, keyOrder);
        set.buildFromSorted(ascendingDistinct);
        return set;
    }

    /** {@link #fromSorted} convenience for naturally-ordered {@link Comparable} keys. */
    public static <K extends Comparable<? super K>> OrderedSet<K> fromSortedNatural(
            List<K> ascendingDistinct, TreeStrategy<K> strategy) {
        return fromSorted(ascendingDistinct, strategy, Comparator.naturalOrder());
    }

    /**
     * Populate this (empty) set in O(n) from an ASCENDING, DISTINCT key list — see {@link #fromSorted}.
     * Order statistics are correct immediately because the build maintains intrinsic subtree sizes.
     *
     * @throws IllegalStateException    if this set is not empty
     * @throws IllegalArgumentException if the list is not strictly ascending under this set's comparator
     * @throws NullPointerException     if the list, or any key in it, is null — checked here rather
     *         than left to the comparator (edge-case pass 2026-08-17): a ONE-element list never
     *         reaches the ascending comparison, so {@code buildFromSorted(List.of-with-null)} used
     *         to link a null key in as a real element and only blow up on some later read, far from
     *         the caller that caused it. That is the {@link #add} hole (audit 2026-08-17, item 1)
     *         on the bulk path.
     */
    public void buildFromSorted(List<K> ascendingDistinct) {
        java.util.Objects.requireNonNull(ascendingDistinct, "ascendingDistinct cannot be null");
        synchronized (lock) {
            refuseReentrantWrite("buildFromSorted");
            if (size != 0) {
                throw new IllegalStateException("buildFromSorted requires an empty set (size=" + size + ")");
            }
            for (int i = 0; i < ascendingDistinct.size(); i++) {
                java.util.Objects.requireNonNull(ascendingDistinct.get(i),
                        "buildFromSorted keys cannot be null; null at index " + i);
                if (i > 0 && keyOrder.compare(ascendingDistinct.get(i - 1), ascendingDistinct.get(i)) >= 0) {
                    throw new IllegalArgumentException(
                            "buildFromSorted requires a strictly ascending (sorted, distinct) list; "
                            + "violation at index " + i);
                }
            }
            long ws = readGuard.writeLock();
            try {
                tree.buildBalanced(ascendingDistinct);
                this.size = ascendingDistinct.size();
                // Reapply a non-default augmentor (bug audit 2026-08-12, C-3):
                // buildBalanced creates every node with the DEFAULT subtree-size
                // augmentor, so without this step a pre-installed custom augmentor
                // (e.g. interval max-hi) silently stopped being maintained — while
                // getAugmentor() still reported it installed, defeating the
                // fail-loud guards. setStrategy and selfRepair already do this.
                if (!isDefaultAugmentor()) {
                    reapplyAugmentor();
                }
                // The FIFO window is only consulted for sliding-window eviction (maxSize > 0); for an
                // unbounded set it is pure overhead, and resyncing through inOrder() would add a whole
                // extra O(n) traversal on top. The input list is already the in-order sequence, so when
                // the window IS active we populate it directly (no traversal) and evict down to bound.
                if (maxSize > 0) {
                    liveOrder.clear();
                    liveOrder.addAll(ascendingDistinct);
                    while (maxSize > 0 && size > maxSize) {
                        if (!evictOldest()) {
                            break;
                        }
                    }
                }
            } finally {
                readGuard.unlockWrite(ws);
            }
        }
    }

    // -- Core ordered-set operations --

    /**
     * @return {@code true} if the key was inserted; {@code false} if already present.
     * @throws NullPointerException if {@code value} is null — checked here, not left to the
     *         comparator (audit 2026-08-17, item 1): on an EMPTY set the insert descent stops at
     *         the root NIL without ever comparing, so a null key used to be linked in as a real
     *         element and only blew up on some later read, far from the caller that caused it.
     */
    public boolean add(K value) {
        java.util.Objects.requireNonNull(value, "value cannot be null");
        synchronized (lock) {
            refuseReentrantWrite("add");
            long ws = readGuard.writeLock();   // the insert descent may splay (duplicate touch): writes mutate
            try {
                long start = System.nanoTime();
                // Single descent (2026-07-14 census, finding A): the strategy's insert descent
                // discovers a duplicate itself and aborts unlinked — no contains precheck, and
                // the returned node spares the augmentor re-find below.
                TreeNode1<K> inserted = tree.addIfAbsent(value);
                if (inserted == null) return false;
                size++;
                liveOrder.add(value);                          // FIFO order for windowed eviction
                // Non-default augmentation must be stamped onto the freshly created node, which
                // createNode installs with the default (subtree-size) augmentor.
                if (!isDefaultAugmentor()) {
                    inserted.setAugmentor(augmentor);
                }
                totalInsertTime += System.nanoTime() - start;
                insertCount++;
                if (events != null) emit(new TreeEvent.Insert<>(value));
                while (maxSize > 0 && size > maxSize) {
                    if (!evictOldest()) break;
                }
                return true;
            } finally {
                readGuard.unlockWrite(ws);
            }
        }
    }

    /**
     * @return {@code true} if the key was present and removed; {@code false} otherwise.
     * @throws NullPointerException if {@code value} is null (see {@link #add}).
     */
    public boolean remove(K value) {
        java.util.Objects.requireNonNull(value, "value cannot be null");
        synchronized (lock) {
            refuseReentrantWrite("remove");
            long ws = readGuard.writeLock();
            try {
                long start = System.nanoTime();
                // Single descent (finding A): search finds the node, delete works on the node
                // reference — the contains precheck was a second full descent for nothing.
                if (!tree.removeIfPresent(value)) return false;
                size--;
                liveOrder.remove(value);
                totalDeleteTime += System.nanoTime() - start;
                deleteCount++;
                if (events != null) emit(new TreeEvent.Remove<>(value));
                return true;
            } finally {
                readGuard.unlockWrite(ws);
            }
        }
    }

    /**
     * Membership, torn-read-free (ADR-004 R1). Optimistic step-bounded descend validated by
     * stamp, locked retry on any suspicion. Never splays — the engine-level
     * {@code tree.contains} (which lets a splay strategy move the key to the root) is reserved
     * for the write path, where the monitor already serializes it.
     *
     * @throws NullPointerException if {@code value} is null (see {@link #add}) — on an empty set
     *         the descent answered {@code false} instead of throwing, and VERIFIED voting compares
     *         thrown-exception classes.
     */
    public boolean contains(K value) {
        java.util.Objects.requireNonNull(value, "value cannot be null");
        if (!OPTIMISTIC_READS) return tree.contains(value);
        return guardedRead(
                () -> !findReadOnly(value, true).isNil(),
                () -> !findReadOnly(value, false).isNil());
    }

    /**
     * Membership <em>with the realized search depth</em> — the measuring twin of {@link #contains}.
     * Returns the number of nodes touched on the descend (≥ 1 on any non-empty tree) when the key is
     * present, or the bitwise complement {@code ~depth} (always negative) when it is absent — so
     * {@code result >= 0} is containment and {@code result >= 0 ? result : ~result} is the depth
     * walked either way. One walk answers both questions, which is exactly what a
     * {@link io.github.richeyworks.csrbt.control.WorkloadMonitor} caller needs to feed
     * {@code recordSearch(keyHash, depthTouched)} honestly instead of with a zero. Same concurrency
     * contract as {@link #contains}: optimistic + validated, locked fallback, never splays — and
     * the same null contract, enforced here rather than by the comparator.
     *
     * @throws NullPointerException if {@code value} is null (see {@link #add}).
     */
    public int searchDepth(K value) {
        java.util.Objects.requireNonNull(value, "value cannot be null");
        if (!OPTIMISTIC_READS) return searchDepthReadOnly(value, false);
        return guardedRead(
                () -> searchDepthReadOnly(value, true),
                () -> searchDepthReadOnly(value, false));
    }

    // ── Atomic navigation (ADR-021) ───────────────────────────────────────────
    // The NavigableOrderedSet adapter used to compose navigation from 2–4
    // independently-guarded reads (countAtMost → contains → select); a write landing
    // between those epochs made read-only navigation throw or violate its contract
    // (floor(k) > k) under the R1 single-writer model this class advertises. These
    // primitives answer each navigation question in ONE guarded acquisition — a single
    // O(log n) descent under one optimistic stamp (locked fallback), same protocol as
    // contains(). Deep-sweep audit 2026-08-12, finding D-1.

    /** Greatest key {@code <= value}, or {@code null}. One guarded acquisition. */
    public K floor(K value) {
        java.util.Objects.requireNonNull(value, "value cannot be null");
        if (!OPTIMISTIC_READS) return navigateReadOnly(value, true, true, false);
        return guardedRead(() -> navigateReadOnly(value, true, true, true),
                           () -> navigateReadOnly(value, true, true, false));
    }

    /** Greatest key {@code < value}, or {@code null}. One guarded acquisition. */
    public K lower(K value) {
        java.util.Objects.requireNonNull(value, "value cannot be null");
        if (!OPTIMISTIC_READS) return navigateReadOnly(value, true, false, false);
        return guardedRead(() -> navigateReadOnly(value, true, false, true),
                           () -> navigateReadOnly(value, true, false, false));
    }

    /** Least key {@code >= value}, or {@code null}. One guarded acquisition. */
    public K ceiling(K value) {
        java.util.Objects.requireNonNull(value, "value cannot be null");
        if (!OPTIMISTIC_READS) return navigateReadOnly(value, false, true, false);
        return guardedRead(() -> navigateReadOnly(value, false, true, true),
                           () -> navigateReadOnly(value, false, true, false));
    }

    /** Least key {@code > value}, or {@code null}. One guarded acquisition. */
    public K higher(K value) {
        java.util.Objects.requireNonNull(value, "value cannot be null");
        if (!OPTIMISTIC_READS) return navigateReadOnly(value, false, false, false);
        return guardedRead(() -> navigateReadOnly(value, false, false, true),
                           () -> navigateReadOnly(value, false, false, false));
    }

    /** Keys {@code <=} (inclusive) or {@code <} (strict) {@code value}, one acquisition. */
    public int countUpTo(K value, boolean inclusive) {
        java.util.Objects.requireNonNull(value, "value cannot be null");
        if (!OPTIMISTIC_READS) return countUpToReadOnly(value, inclusive, false);
        return guardedRead(() -> countUpToReadOnly(value, inclusive, true),
                           () -> countUpToReadOnly(value, inclusive, false));
    }

    /**
     * Keys inside the given bounds — {@code null} bound = unbounded on that side —
     * computed in ONE guarded acquisition (both count descents run under the same
     * optimistic stamp, so no write can slip between them). This is the adapter's
     * view-sizing primitive (ADR-021).
     */
    public int countBetween(K lo, boolean loInclusive, K hi, boolean hiInclusive) {
        if (!OPTIMISTIC_READS) return countBetweenReadOnly(lo, loInclusive, hi, hiInclusive, false);
        return guardedRead(() -> countBetweenReadOnly(lo, loInclusive, hi, hiInclusive, true),
                           () -> countBetweenReadOnly(lo, loInclusive, hi, hiInclusive, false));
    }

    /**
     * In-order keys inside the given bounds — {@code null} bound = unbounded on that
     * side — collected in ONE guarded acquisition: the bound resolution and the whole
     * walk share a single optimistic stamp (locked fallback). This is the adapter's
     * view-iteration primitive (ADR-021 follow-up, 2026-08-14): view snapshots used to
     * compose {@code isEmpty → minimum → maximum → rangeQuery} across four lock epochs,
     * so a writer emptying the set between epochs made a read-only view iterator throw
     * NPE out of {@code iterator()} — violating the adapter's never-throws contract.
     */
    public List<K> rangeSnapshot(K lo, boolean loInclusive, K hi, boolean hiInclusive) {
        if (!OPTIMISTIC_READS) return rangeSnapshotReadOnly(lo, loInclusive, hi, hiInclusive, false);
        return guardedRead(() -> rangeSnapshotReadOnly(lo, loInclusive, hi, hiInclusive, true),
                           () -> rangeSnapshotReadOnly(lo, loInclusive, hi, hiInclusive, false));
    }

    /** Pruned in-order walk; same step budget and torn diversion as {@code inOrderReadOnly}. */
    private List<K> rangeSnapshotReadOnly(K lo, boolean loInclusive, K hi, boolean hiInclusive,
                                          boolean bounded) {
        List<K> out = new ArrayList<>();
        long budget = bounded ? 4L * Math.max(16, size) + 64 : Long.MAX_VALUE;
        Deque<TreeNode1<K>> stack = new ArrayDeque<>();
        TreeNode1<K> cur = tree.getRoot();
        while (cur != null && (!cur.isNil() || !stack.isEmpty())) {
            if (--budget < 0) throw TornReadException.INSTANCE;
            if (!cur.isNil()) {
                stack.push(cur);
                // Descend left only while this subtree can still hold in-range keys:
                // if cur <= lo, everything to the left is < lo and can be pruned.
                int cLo = (lo == null) ? 1 : cur.compareKeyTo(lo);   // >0 means cur > lo
                cur = cLo > 0 ? cur.getLeft() : tree.getNIL();
            } else {
                cur = stack.pop();
                int cLo = (lo == null) ? 1  : cur.compareKeyTo(lo);
                int cHi = (hi == null) ? -1 : cur.compareKeyTo(hi);
                boolean above = cLo > 0 || (cLo == 0 && loInclusive);
                boolean below = cHi < 0 || (cHi == 0 && hiInclusive);
                if (above && below) out.add(cur.getData());
                // Symmetric prune: if cur >= hi, everything to the right is > hi.
                cur = cHi < 0 ? cur.getRight() : tree.getNIL();
            }
        }
        if (cur == null) throw TornReadException.INSTANCE;   // torn pointer — divert
        return out;
    }

    /**
     * One navigation descent, {@link #findReadOnly}'s concurrency discipline: step-bounded
     * when optimistic, torn-pointer diversion, no mutation. {@code lessSide} picks
     * floor/lower vs ceiling/higher; {@code inclusive} picks floor/ceiling vs lower/higher.
     */
    private K navigateReadOnly(K value, boolean lessSide, boolean inclusive, boolean bounded) {
        TreeNode1<K> x = tree.getRoot();
        TreeNode1<K> best = null;
        int steps = bounded
                ? 2 * (32 - Integer.numberOfLeadingZeros(Math.max(1, size))) + 32
                : Integer.MAX_VALUE;
        while (x != null && !x.isNil()) {
            if (--steps < 0) throw TornReadException.INSTANCE;
            int cmp = x.compareKeyTo(value);          // >0: x > value; <0: x < value
            if (cmp == 0) {
                if (inclusive) return x.getData();
                x = lessSide ? x.getLeft() : x.getRight();
            } else if (cmp < 0) {                     // x < value
                if (lessSide) best = x;
                x = x.getRight();
            } else {                                  // x > value
                if (!lessSide) best = x;
                x = x.getLeft();
            }
        }
        if (x == null) throw TornReadException.INSTANCE;   // children are never null when consistent
        return best == null ? null : best.getData();
    }

    /** Rank descent over intrinsic subtree sizes; same step bound and torn diversion. */
    private int countUpToReadOnly(K value, boolean inclusive, boolean bounded) {
        TreeNode1<K> x = tree.getRoot();
        int count = 0;
        int steps = bounded
                ? 2 * (32 - Integer.numberOfLeadingZeros(Math.max(1, size))) + 32
                : Integer.MAX_VALUE;
        while (x != null && !x.isNil()) {
            if (--steps < 0) throw TornReadException.INSTANCE;
            int cmp = x.compareKeyTo(value);
            boolean counts = inclusive ? cmp <= 0 : cmp < 0;   // x is within the bound
            if (counts) {
                count += x.getLeft().getSize() + 1;
                x = x.getRight();
            } else {
                x = x.getLeft();
            }
        }
        if (x == null) throw TornReadException.INSTANCE;
        return count;
    }

    private int countBetweenReadOnly(K lo, boolean loInclusive, K hi, boolean hiInclusive,
                                     boolean bounded) {
        int upTo   = (hi == null) ? size : countUpToReadOnly(hi, hiInclusive, bounded);
        int before = (lo == null) ? 0    : countUpToReadOnly(lo, !loInclusive, bounded);
        return Math.max(0, upTo - before);
    }

    public int size() { return size; }

    public boolean isEmpty() { return size == 0; }

    /** @return all keys in ascending order (a torn-read-free snapshot under ADR-004 R1). */
    public List<K> inOrder() {
        if (!OPTIMISTIC_READS) return tree.inOrder();
        return guardedRead(() -> inOrderReadOnly(true), () -> inOrderReadOnly(false));
    }

    public void clear() {
        synchronized (lock) {
            refuseReentrantWrite("clear");
            long ws = readGuard.writeLock();
            try {
                tree.setRoot(tree.getNIL());
                size = 0;
                liveOrder.clear();
            } finally {
                readGuard.unlockWrite(ws);
            }
        }
    }

    // -- ADR-004 R1 read machinery --

    /**
     * Run {@code optimistic} under a {@link StampedLock#tryOptimisticRead} stamp and return its
     * result only if the stamp validates (no writer overlapped); otherwise run {@code locked}
     * under the shared read lock. The optimistic attempt may throw {@link TornReadException}
     * (step bound tripped) or any {@code RuntimeException} (torn pointers / null data) — both
     * simply divert to the locked path, where the tree is consistent by construction.
     */
    private <R> R guardedRead(Supplier<R> optimistic, Supplier<R> locked) {
        long stamp = readGuard.tryOptimisticRead();
        if (stamp != 0L) {
            try {
                R result = optimistic.get();
                if (readGuard.validate(stamp)) return result;
            } catch (RuntimeException torn) {
                // fall through to the locked read
            }
        }
        long rs = readGuard.readLock();
        try {
            return locked.get();
        } finally {
            readGuard.unlockRead(rs);
        }
    }

    /** Shared-lock read for the order-statistics walks (consistent tree, no step bound needed). */
    private <R> R lockedRead(Supplier<R> read) {
        if (!OPTIMISTIC_READS) return read.get();
        long rs = readGuard.readLock();
        try {
            return read.get();
        } finally {
            readGuard.unlockRead(rs);
        }
    }

    /**
     * Strategy-independent BST descend (never splays). When {@code bounded}, the walk gives up
     * after ~2·log2(size)+32 steps — an optimistic reader overlapping a rotation can transiently
     * chase a cycle, and a legitimately deep tree (degenerate splay chain) is indistinguishable
     * from one, so both divert to the locked path.
     */
    private TreeNode1<K> findReadOnly(K value, boolean bounded) {
        TreeNode1<K> x = tree.getRoot();
        int steps = bounded
                ? 2 * (32 - Integer.numberOfLeadingZeros(Math.max(1, size))) + 32
                : Integer.MAX_VALUE;
        while (x != null && !x.isNil()) {
            if (--steps < 0) throw TornReadException.INSTANCE;
            int cmp = x.compareKeyTo(value);
            if (cmp == 0) return x;
            x = (cmp > 0) ? x.getLeft() : x.getRight();
        }
        if (x == null) throw TornReadException.INSTANCE;   // children are never null when consistent
        return x;                                          // NIL — not present
    }

    /**
     * Depth-counting twin of {@link #findReadOnly}: same strategy-independent descend, same step
     * bound and torn-read diversion, but returns {@code depth} (nodes touched) when found and
     * {@code ~depth} when the walk ends at NIL.
     */
    private int searchDepthReadOnly(K value, boolean bounded) {
        TreeNode1<K> x = tree.getRoot();
        int steps = bounded
                ? 2 * (32 - Integer.numberOfLeadingZeros(Math.max(1, size))) + 32
                : Integer.MAX_VALUE;
        int depth = 0;
        while (x != null && !x.isNil()) {
            if (--steps < 0) throw TornReadException.INSTANCE;
            depth++;
            int cmp = x.compareKeyTo(value);
            if (cmp == 0) return depth;
            x = (cmp > 0) ? x.getLeft() : x.getRight();
        }
        if (x == null) throw TornReadException.INSTANCE;   // children are never null when consistent
        return ~depth;                                     // NIL — not present
    }

    /** Iterative in-order snapshot; when {@code bounded}, budgeted at ~4n+64 visited links. */
    private List<K> inOrderReadOnly(boolean bounded) {
        List<K> out = new ArrayList<>();
        long budget = bounded ? 4L * Math.max(16, size) + 64 : Long.MAX_VALUE;
        Deque<TreeNode1<K>> stack = new ArrayDeque<>();
        TreeNode1<K> cur = tree.getRoot();
        while (cur != null && (!cur.isNil() || !stack.isEmpty())) {
            if (--budget < 0) throw TornReadException.INSTANCE;
            if (!cur.isNil()) {
                stack.push(cur);
                cur = cur.getLeft();
            } else {
                cur = stack.pop();
                out.add(cur.getData());
                cur = cur.getRight();
            }
        }
        if (cur == null) throw TornReadException.INSTANCE;
        return out;
    }

    // -- Dynamic order statistics (delegated to OrderStatisticsOps<K>) --
    // Ranks/percentiles are positional ints; everything else is keyed by K.

    // All order-statistics reads hold the shared read lock (ADR-004 R1): the walks are pure
    // (OrderStatisticsOps never splays or mutates) but not step-bounded, so they run only on a
    // consistent tree. Their documented exceptions (out-of-range rank, absent key) propagate.

    // Keyed reads null-check up front (audit 2026-08-17, item 1): the walks reach a comparison
    // only on a non-empty tree, so on an empty set rank/successor/predecessor used to report
    // "absent key" (NoSuchElementException) for a null argument while a populated set reported
    // NullPointerException. Explicit checks make the thrown class size-independent, which is what
    // RankedSet's voting-parity clause and EnsembleOrderedSet.Thrown actually compare.

    /** ith smallest key (1-indexed). @throws IndexOutOfBoundsException if out of [1,size]. */
    public K select(int rank) { return lockedRead(() -> os.select(rank).getData()); }

    /**
     * 1-indexed rank of a key.
     * @throws java.util.NoSuchElementException if absent.
     * @throws NullPointerException if {@code value} is null (see {@link #add}).
     */
    public int rank(K value) {
        java.util.Objects.requireNonNull(value, "value cannot be null");
        return lockedRead(() -> os.rank(value));
    }

    /**
     * Smallest key strictly greater than {@code value}, or {@code null} if none. @throws if absent.
     * @throws NullPointerException if {@code value} is null (see {@link #add}).
     */
    public K successor(K value) {
        java.util.Objects.requireNonNull(value, "value cannot be null");
        return lockedRead(() -> keyOrNull(os.successor(value)));
    }

    /**
     * Largest key strictly less than {@code value}, or {@code null} if none. @throws if absent.
     * @throws NullPointerException if {@code value} is null (see {@link #add}).
     */
    public K predecessor(K value) {
        java.util.Objects.requireNonNull(value, "value cannot be null");
        return lockedRead(() -> keyOrNull(os.predecessor(value)));
    }

    public K minimum() { return lockedRead(() -> isEmpty() ? null : os.minimum().getData()); }

    public K maximum() { return lockedRead(() -> keyOrNull(os.maximum())); }

    public K median() { return lockedRead(() -> keyOrNull(os.median())); }

    /**
     * kth-percentile key (0-100), or {@code null} if empty. The resulting rank is <b>clamped</b> to
     * {@code [1, n]}, so {@code pct} outside 0-100 saturates at the minimum or the maximum rather
     * than throwing — the same rule {@code BPlusTreeEngine} and {@code PersistentRankedSet} state,
     * which is what keeps a VERIFIED vote unanimous on an out-of-range argument.
     */
    public K percentile(int pct) { return lockedRead(() -> keyOrNull(os.percentile(pct))); }

    /**
     * Count of keys in the closed range [lo, hi]. Both bounds are required — the unbounded-side
     * form is {@link #countBetween}, whose {@code null} means "unbounded" by contract.
     * @throws NullPointerException if either bound is null (see {@link #add}).
     */
    public int countInRange(K lo, K hi) {
        java.util.Objects.requireNonNull(lo, "lo cannot be null");
        java.util.Objects.requireNonNull(hi, "hi cannot be null");
        return lockedRead(() -> os.countInRange(lo, hi));
    }

    /**
     * Keys in [lo, hi], ascending. Both bounds are required — the unbounded-side form is
     * {@link #rangeSnapshot}, whose {@code null} means "unbounded" by contract.
     * @throws NullPointerException if either bound is null (see {@link #add}).
     */
    public List<K> rangeQuery(K lo, K hi) {
        java.util.Objects.requireNonNull(lo, "lo cannot be null");
        java.util.Objects.requireNonNull(hi, "hi cannot be null");
        return lockedRead(() -> os.rangeQuery(lo, hi));
    }

    private K keyOrNull(TreeNode1<K> node) { return (node == null || node.isNil()) ? null : node.getData(); }

    // -- Sliding window --

    /** Set the bounded-set capacity (0 = unbounded); evicts oldest-inserted keys down to it. */
    public void setMaxSize(int n) {
        synchronized (lock) {
            refuseReentrantWrite("setMaxSize");
            long ws = readGuard.writeLock();
            try {
                this.maxSize = Math.max(0, n);
                while (maxSize > 0 && size > maxSize) {
                    if (!evictOldest()) break;
                }
            } finally {
                readGuard.unlockWrite(ws);
            }
        }
    }

    public int getMaxSize() { return maxSize; }

    /**
     * The FIFO window's oldest live key — the next eviction victim — or {@code null}
     * when the window is empty. Read under the writer lock so it is consistent with
     * any in-flight mutation. Added for the undo seam (consolidation 2026-08-12,
     * D-2): {@code TreeContext.add} peeks the victim BEFORE the add so a
     * window-evicting insert can record what it displaced.
     */
    public K peekOldest() {
        synchronized (lock) {
            java.util.Iterator<K> it = liveOrder.iterator();
            return it.hasNext() ? it.next() : null;
        }
    }

    private boolean evictOldest() {
        if (liveOrder.size() != size) resyncLiveOrder();   // safety net after wholesale rebuilds
        java.util.Iterator<K> it = liveOrder.iterator();
        if (!it.hasNext()) return false;
        K oldest = it.next();
        it.remove();
        if (tree.removeIfPresent(oldest)) {                // one descent, not contains + remove
            size--;
            if (events != null) emit(new TreeEvent.Evict<>(oldest));
        }
        return true;
    }

    private void resyncLiveOrder() {
        liveOrder.clear();
        liveOrder.addAll(tree.inOrder());                  // ascending fallback when true FIFO is lost
    }

    // -- Augmentation --

    public void setAugmentor(TreeNode1.Augmentor<K> augmentor) {
        synchronized (lock) {
            refuseReentrantWrite("setAugmentor");
            long ws = readGuard.writeLock();
            try {
                this.augmentor = (augmentor != null) ? augmentor : TreeNode1.<K>defaultAugmentor();
                reapplyAugmentor();
            } finally {
                readGuard.unlockWrite(ws);
            }
        }
    }

    public TreeNode1.Augmentor<K> getAugmentor() { return augmentor; }

    private boolean isDefaultAugmentor() {
        return augmentor == TreeNode1.<K>defaultAugmentor();
    }

    private void reapplyAugmentor() {
        TreeNode1<K> root = tree.getRoot();
        if (root.isNil()) return;
        Deque<TreeNode1<K>> stack = new ArrayDeque<>();
        stack.push(root);
        while (!stack.isEmpty()) {
            TreeNode1<K> cur = stack.pop();
            cur.setAugmentor(this.augmentor);
            if (!cur.getRight().isNil()) stack.push(cur.getRight());
            if (!cur.getLeft().isNil())  stack.push(cur.getLeft());
        }
    }

    // -- Strategy morph (health-gated, builds the candidate aside) --

    /**
     * Swap the balancing strategy, rebuilding the tree from its in-order contents. The
     * candidate is built off to the side and validated by {@link StrategyHealthCheck};
     * it is published only on a clean pass, so a rejected morph leaves the incumbent
     * untouched. Per-node tags AND generic augment payloads ({@link TreeNode1#getAugmentedRef()})
     * carry across so augmented data (e.g. interval max-hi, int or typed) survives.
     * @return {@code true} if the morph was applied.
     */
    public boolean setStrategy(TreeStrategy<K> newStrategy) {
        synchronized (lock) {
            refuseReentrantWrite("setStrategy");
            // Same-policy no-op: parameter-aware (ADR-011 V3) — class identity alone would
            // make WB(3,2) -> WB(4,2) a silent refusal of a real morph.
            if (newStrategy == null || newStrategy.samePolicyAs(tree.getStrategy())) {
                return false;
            }
            List<CapturedNode<K>> captured = captureNodeState();
            List<K> elements = new ArrayList<>(captured.size());    // ascending, distinct
            for (CapturedNode<K> c : captured) elements.add(c.key());

            RedBlackTree<K> candidate = new RedBlackTree<>(newStrategy, keyOrder);
            for (K v : elements) candidate.add(v);

            List<String> failures = StrategyHealthCheck.validate(candidate, newStrategy, elements);
            if (!failures.isEmpty()) {
                if (events != null) {
                    emit(new TreeEvent.Morph<>(tree.getStrategy().getClass().getSimpleName(),
                            newStrategy.getClass().getSimpleName(), false));
                }
                return false;
            }

            String fromStrategy = tree.getStrategy().getClass().getSimpleName();
            // Only the publish is stamped (ADR-004 R1): the candidate was built off to the
            // side, so concurrent readers keep reading the untouched incumbent until here.
            long ws = readGuard.writeLock();
            try {
                this.tree = candidate;
                this.os   = new OrderStatisticsOps<>(candidate);
                this.size = elements.size();
                if (!isDefaultAugmentor()) reapplyAugmentor();
                restoreNodeState(captured);
                resyncLiveOrder();
            } finally {
                readGuard.unlockWrite(ws);
            }
            if (events != null) {
                emit(new TreeEvent.Morph<>(fromStrategy,
                        newStrategy.getClass().getSimpleName(), true));
            }
            return true;
        }
    }

    public TreeStrategy<K> getStrategy() { return tree.getStrategy(); }

    // -- Self-healing --

    /**
     * Rebuild the tree from a sorted, de-duplicated snapshot of its keys under the
     * current strategy, then report whether the rebuilt tree validates. A defensive
     * rebuild: cheap when the tree is already healthy, corrective when it is not.
     */
    @Override
    public boolean selfRepair() {
        synchronized (lock) {
            refuseReentrantWrite("selfRepair");
            TreeStrategy<K> strategy = tree.getStrategy();
            TreeSet<K> sorted = new TreeSet<>(keyOrder);
            sorted.addAll(tree.inOrder());
            List<K> elements = new ArrayList<>(sorted);
            List<CapturedNode<K>> captured = captureNodeState();

            RedBlackTree<K> rebuilt = new RedBlackTree<>(strategy, keyOrder);
            for (K v : elements) rebuilt.add(v);

            long ws = readGuard.writeLock();   // publish only; the rebuild happened aside
            try {
                this.tree = rebuilt;
                this.os   = new OrderStatisticsOps<>(rebuilt);
                this.size = elements.size();
                if (!isDefaultAugmentor()) reapplyAugmentor();
                restoreNodeState(captured);
                resyncLiveOrder();
            } finally {
                readGuard.unlockWrite(ws);
            }
            boolean healthy = StrategyHealthCheck.validate(rebuilt, strategy, elements).isEmpty();
            if (events != null) emit(new TreeEvent.Repair<>(healthy));
            return healthy;
        }
    }

    // -- Accessors / metrics --

    /** The tree's key-ordering authority. */
    public Comparator<? super K> comparator() { return keyOrder; }

    /** The live backing engine. Exposes internal structure; treat as read-mostly. */
    public RedBlackTree<K> getEngine() { return tree; }

    /**
     * Resynchronize the cached size and FIFO window from the backing engine after
     * its root was replaced out-of-band via {@link #getEngine()} (e.g. snapshot
     * load, undo/redo restore, or a clone rebuild that mutates the engine directly
     * and then resizes). True insertion order is unknowable after a wholesale
     * rebuild, so the window falls back to ascending key order -- the same safety
     * net {@code resyncLiveOrder} applies after a morph. Lets the {@code TreeContext}
     * adapter honour its {@code forceSizeInternal} contract while {@code OrderedSet}
     * owns the engine, size, and window.
     *
     * <p>An active window is <em>enforced</em>, not merely recorded (audit 2026-08-17,
     * finding 20): a rebuild that installed more than {@code maxSize} keys is evicted
     * down to the bound here, exactly as {@link #setMaxSize} and {@link #add} do. The
     * window caps what can exist, so a checkpoint restore or snapshot load can no more
     * exceed it than an insert can — before this, an over-bound restore survived until
     * the next single {@code add}, which then evicted the whole excess at once.</p>
     */
    public void resyncFromEngine() {
        synchronized (lock) {
            refuseReentrantWrite("resyncFromEngine");
            long ws = readGuard.writeLock();
            try {
                List<K> keys = tree.inOrder();
                this.size = keys.size();
                liveOrder.clear();
                liveOrder.addAll(keys);
                // FIFO order after a wholesale rebuild is the ascending fallback above, so
                // evicting the oldest keeps the LAST maxSize keys -- the same survivors an
                // undo's replay-in-ascending-order restore produces (D-2), keeping the two
                // restore paths consistent.
                while (maxSize > 0 && size > maxSize) {
                    if (!evictOldest()) break;
                }
            } finally {
                readGuard.unlockWrite(ws);
            }
        }
    }

    /**
     * Total primitive rotations performed by the <em>current</em> backing engine — the
     * {@code rotationsPerWrite} source signal for a {@link io.github.richeyworks.csrbt.control.WorkloadMonitor}.
     * Callers metering per-op churn should difference successive readings; a morph or self-repair swaps
     * the engine and resets the counter, so guard deltas with {@code Math.max(0, after - before)}.
     */
    public long rotationCount() { return tree.rotationCount(); }

    public double avgInsertTimeMs() {
        return insertCount == 0 ? 0 : (totalInsertTime / 1_000_000.0) / insertCount;
    }

    public double avgDeleteTimeMs() {
        return deleteCount == 0 ? 0 : (totalDeleteTime / 1_000_000.0) / deleteCount;
    }

    // -- Internal --

    /**
     * One node's non-structural state, captured in ascending key order: the key itself, its
     * {@link TreeNode1#getTag() tag}, and its generic augment payload
     * ({@link TreeNode1#getAugmentedRef()}). Either payload may be absent.
     */
    private record CapturedNode<K>(K key, String tag, Object ref) { }

    /**
     * In-order snapshot of every node's key, tag and generic augment payload — everything a
     * rebuild has to carry across.
     *
     * <p>A LIST in traversal order, not a map (audit 2026-08-17, finding 11). The morph used
     * to rebuild its candidate from a equals-keyed map's key set, i.e. keyed by
     * {@code equals}/{@code hashCode} rather than by this set's {@link #keyOrder}: keys that
     * are {@code equals} but compare non-zero collapsed into one entry and the extras were
     * silently dropped from the rebuilt tree — invisibly to the health gate, whose contents
     * clause compares the candidate against that same collapsed list. The in-order walk is
     * already ascending and comparator-distinct (it is the engine's own ordering), so a list
     * is both faithful and free: unlike a comparator-keyed map it adds no comparisons to the
     * morph, which is metered as the switching bill in ADR-018's amortization frontier.</p>
     */
    private List<CapturedNode<K>> captureNodeState() {
        List<CapturedNode<K>> out = new ArrayList<>(size);
        Deque<TreeNode1<K>> stack = new ArrayDeque<>();
        TreeNode1<K> cur = tree.getRoot();
        while (!stack.isEmpty() || !cur.isNil()) {
            while (!cur.isNil()) { stack.push(cur); cur = cur.getLeft(); }
            cur = stack.pop();
            out.add(new CapturedNode<>(cur.getData(), cur.getTag(), cur.getAugmentedRef()));
            cur = cur.getRight();
        }
        return out;
    }

    /**
     * Re-apply captured tags and generic augment payloads after a rebuild, re-augmenting each
     * touched node so tag- and ref-derived values propagate to the root.
     *
     * <p>Restoring a payload whose derived part (e.g. subtree max-hi) is stale for the NEW
     * tree shape is safe: {@code reaugment()} recomputes the derived part on every node up to
     * the root, and payloads carry their semantic part (e.g. this node's own hi) immutably, so
     * the propagation pass from each restored node leaves every derived value correct — the
     * same argument tag-derived int augments rely on. Nodes carrying neither payload are
     * skipped, so a tree that never used tags or the ref slot pays one traversal and nothing
     * else.</p>
     */
    private void restoreNodeState(List<CapturedNode<K>> captured) {
        for (CapturedNode<K> c : captured) {
            boolean hasTag = c.tag() != null && !c.tag().isEmpty();
            if (!hasTag && c.ref() == null) continue;
            TreeNode1<K> n = tree.getStrategy().search(tree, c.key());
            if (n.isNil()) continue;
            if (hasTag)         n.setTag(c.tag());
            if (c.ref() != null) n.setAugmentedRef(c.ref());
            n.reaugment();
        }
    }
}
