package core;

import core.interfaces.AugmentedTree;
import core.interfaces.OrderedCollection;
import core.interfaces.RankedSet;
import core.interfaces.SelfHealingTree;
import core.strategy.TreeStrategy;
import core.util.OrderStatisticsOps;
import core.util.StrategyHealthCheck;
import core.control.StrategyMorphTarget;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Deque;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
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

    // -- Core ordered-set operations --

    /** @return {@code true} if the key was inserted; {@code false} if already present. */
    public boolean add(K value) {
        synchronized (lock) {
            long ws = readGuard.writeLock();   // tree.contains may splay: the precheck mutates too
            try {
                if (tree.contains(value)) return false;
                long start = System.nanoTime();
                tree.add(value);
                size++;
                liveOrder.add(value);                          // FIFO order for windowed eviction
                // Non-default augmentation must be stamped onto the freshly created node, which
                // createNode installs with the default (subtree-size) augmentor.
                if (!isDefaultAugmentor()) {
                    TreeNode1<K> inserted = tree.getStrategy().search(tree, value);
                    if (!inserted.isNil()) inserted.setAugmentor(augmentor);
                }
                totalInsertTime += System.nanoTime() - start;
                insertCount++;
                while (maxSize > 0 && size > maxSize) {
                    if (!evictOldest()) break;
                }
                return true;
            } finally {
                readGuard.unlockWrite(ws);
            }
        }
    }

    /** @return {@code true} if the key was present and removed; {@code false} otherwise. */
    public boolean remove(K value) {
        synchronized (lock) {
            long ws = readGuard.writeLock();
            try {
                if (!tree.contains(value)) return false;
                long start = System.nanoTime();
                tree.remove(value);
                size--;
                liveOrder.remove(value);
                totalDeleteTime += System.nanoTime() - start;
                deleteCount++;
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
     */
    public boolean contains(K value) {
        if (!OPTIMISTIC_READS) return tree.contains(value);
        return guardedRead(
                () -> !findReadOnly(value, true).isNil(),
                () -> !findReadOnly(value, false).isNil());
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

    /** ith smallest key (1-indexed). @throws IndexOutOfBoundsException if out of [1,size]. */
    public K select(int rank) { return lockedRead(() -> os.select(rank).getData()); }

    /** 1-indexed rank of a key. @throws java.util.NoSuchElementException if absent. */
    public int rank(K value) { return lockedRead(() -> os.rank(value)); }

    /** Smallest key strictly greater than {@code value}, or {@code null} if none. @throws if absent. */
    public K successor(K value) { return lockedRead(() -> keyOrNull(os.successor(value))); }

    /** Largest key strictly less than {@code value}, or {@code null} if none. @throws if absent. */
    public K predecessor(K value) { return lockedRead(() -> keyOrNull(os.predecessor(value))); }

    public K minimum() { return lockedRead(() -> isEmpty() ? null : os.minimum().getData()); }

    public K maximum() { return lockedRead(() -> keyOrNull(os.maximum())); }

    public K median() { return lockedRead(() -> keyOrNull(os.median())); }

    /** kth-percentile key (0-100), or {@code null} if empty. */
    public K percentile(int pct) { return lockedRead(() -> keyOrNull(os.percentile(pct))); }

    /** Count of keys in the closed range [lo, hi]. */
    public int countInRange(K lo, K hi) { return lockedRead(() -> os.countInRange(lo, hi)); }

    /** Keys in [lo, hi], ascending. */
    public List<K> rangeQuery(K lo, K hi) { return lockedRead(() -> os.rangeQuery(lo, hi)); }

    private K keyOrNull(TreeNode1<K> node) { return (node == null || node.isNil()) ? null : node.getData(); }

    // -- Sliding window --

    /** Set the bounded-set capacity (0 = unbounded); evicts oldest-inserted keys down to it. */
    public void setMaxSize(int n) {
        synchronized (lock) {
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

    private boolean evictOldest() {
        if (liveOrder.size() != size) resyncLiveOrder();   // safety net after wholesale rebuilds
        java.util.Iterator<K> it = liveOrder.iterator();
        if (!it.hasNext()) return false;
        K oldest = it.next();
        it.remove();
        if (tree.contains(oldest)) {
            tree.remove(oldest);
            size--;
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
     * untouched. Per-node tags carry across so augmented data (e.g. interval max-hi)
     * survives. @return {@code true} if the morph was applied.
     */
    public boolean setStrategy(TreeStrategy<K> newStrategy) {
        synchronized (lock) {
            if (newStrategy == null
                    || newStrategy.getClass() == tree.getStrategy().getClass()) {
                return false;
            }
            Map<K, String> keyTags = captureKeyTags();
            List<K> elements = new ArrayList<>(keyTags.keySet());   // ascending, distinct

            RedBlackTree<K> candidate = new RedBlackTree<>(newStrategy, keyOrder);
            for (K v : elements) candidate.add(v);

            List<String> failures = StrategyHealthCheck.validate(candidate, newStrategy, elements);
            if (!failures.isEmpty()) return false;

            // Only the publish is stamped (ADR-004 R1): the candidate was built off to the
            // side, so concurrent readers keep reading the untouched incumbent until here.
            long ws = readGuard.writeLock();
            try {
                this.tree = candidate;
                this.os   = new OrderStatisticsOps<>(candidate);
                this.size = elements.size();
                if (!isDefaultAugmentor()) reapplyAugmentor();
                restoreTags(keyTags);
                resyncLiveOrder();
            } finally {
                readGuard.unlockWrite(ws);
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
            TreeStrategy<K> strategy = tree.getStrategy();
            TreeSet<K> sorted = new TreeSet<>(keyOrder);
            sorted.addAll(tree.inOrder());
            List<K> elements = new ArrayList<>(sorted);
            Map<K, String> keyTags = captureKeyTags();

            RedBlackTree<K> rebuilt = new RedBlackTree<>(strategy, keyOrder);
            for (K v : elements) rebuilt.add(v);

            long ws = readGuard.writeLock();   // publish only; the rebuild happened aside
            try {
                this.tree = rebuilt;
                this.os   = new OrderStatisticsOps<>(rebuilt);
                this.size = elements.size();
                if (!isDefaultAugmentor()) reapplyAugmentor();
                restoreTags(keyTags);
                resyncLiveOrder();
            } finally {
                readGuard.unlockWrite(ws);
            }
            return StrategyHealthCheck.validate(rebuilt, strategy, elements).isEmpty();
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
     */
    public void resyncFromEngine() {
        synchronized (lock) {
            long ws = readGuard.writeLock();
            try {
                List<K> keys = tree.inOrder();
                this.size = keys.size();
                liveOrder.clear();
                liveOrder.addAll(keys);
            } finally {
                readGuard.unlockWrite(ws);
            }
        }
    }

    public double avgInsertTimeMs() {
        return insertCount == 0 ? 0 : (totalInsertTime / 1_000_000.0) / insertCount;
    }

    public double avgDeleteTimeMs() {
        return deleteCount == 0 ? 0 : (totalDeleteTime / 1_000_000.0) / deleteCount;
    }

    // -- Internal --

    /** In-order snapshot of every key and its tag ({@link LinkedHashMap} keeps ascending order). */
    private Map<K, String> captureKeyTags() {
        Map<K, String> out = new LinkedHashMap<>();
        Deque<TreeNode1<K>> stack = new ArrayDeque<>();
        TreeNode1<K> cur = tree.getRoot();
        while (!stack.isEmpty() || !cur.isNil()) {
            while (!cur.isNil()) { stack.push(cur); cur = cur.getLeft(); }
            cur = stack.pop();
            out.put(cur.getData(), cur.getTag());
            cur = cur.getRight();
        }
        return out;
    }

    /** Re-apply captured tags after a rebuild, re-augmenting so tag-derived values propagate. */
    private void restoreTags(Map<K, String> keyTags) {
        for (Map.Entry<K, String> e : keyTags.entrySet()) {
            String tag = e.getValue();
            if (tag == null || tag.isEmpty()) continue;
            TreeNode1<K> n = tree.getStrategy().search(tree, e.getKey());
            if (!n.isNil()) {
                n.setTag(tag);
                n.reaugment();
            }
        }
    }
}
