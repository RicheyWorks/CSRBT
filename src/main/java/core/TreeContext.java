package core;

import core.interfaces.AugmentedTree;
import core.interfaces.OrderedCollection;
import core.interfaces.SelfHealingTree;
import core.interfaces.TreePersistenceAdapter;
import core.persistence.FilePersistenceAdapter;
import core.strategy.AVLStrategy;
import core.strategy.TreeStrategy;
import core.util.*;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.*;

/**
 * Facade over a {@link RedBlackTree} engine adding metrics, persistence,
 * augmentation, history and adaptive strategy morphing.
 *
 * <h2>Concurrency contract</h2>
 * <p><strong>This class is designed for single-threaded use.</strong> The
 * backing {@link RedBlackTree}, the {@link core.strategy.TreeStrategy}
 * implementations, and the per-node {@link TreeNode1} state are all
 * <em>not</em> thread-safe.</p>
 *
 * <p>The state-changing operations — {@link #add(int)}, {@link #remove(int)},
 * {@link #setStrategy}, {@link #clear()} — serialize on a single internal lock,
 * which prevents two <em>writers</em> from interleaving and corrupting the tree.
 * That is the only guarantee. It is <strong>not</strong> sufficient for general
 * concurrent use, because:</p>
 * <ul>
 *   <li>Read operations ({@link #contains(int)}, {@link #size()},
 *       {@link #inOrder()}, {@link #selfRepair()}) take no lock and may observe a
 *       tree mid-mutation.</li>
 *   <li>Accessors such as {@link #getTree()} and the in-order traversals expose
 *       <em>live</em> internal structure and nodes; mutating them, or reading
 *       them while another thread writes, bypasses the lock entirely.</li>
 * </ul>
 *
 * <p>An application that needs concurrent access must provide its own external
 * synchronization around <em>all</em> access (reads, writes, and anything done
 * with objects returned from this facade).</p>
 */
public class TreeContext implements AugmentedTree, SelfHealingTree, OrderedCollection {

    private static final Logger logger = LogManager.getLogger(TreeContext.class);

    // ── Core state ────────────────────────────────────────────────────────────
    private RedBlackTree              tree;
    private int                       size;
    private TreeStrategy              strategy;
    private TreeNode1.Augmentor       augmentor         = TreeNode1.defaultAugmentor;
    private TreePersistenceAdapter    persistenceAdapter;

    // ── Utility delegates ─────────────────────────────────────────────────────
    private final TreeDiagnostics     diagnostics;
    private final TreeCloner          cloner;
    private final TreeHistory         history;

    // ── Metrics ───────────────────────────────────────────────────────────────
    private int  rotationCount    = 0;
    private long totalInsertTime  = 0;
    private long totalDeleteTime  = 0;
    private int  insertCount      = 0;
    private int  deleteCount      = 0;

    // ── Stress / adaptive morph ───────────────────────────────────────────────
    private static final int          STRESS_THRESHOLD  = 3;
    private static final int          MEMORY_LIMIT      = 50;
    private final Map<Integer, Integer> frequencyMap    = new HashMap<>();
    private final Deque<Integer>      recentInsertions  = new ArrayDeque<>();
    private final Map<String, Integer> stressEvents     = new HashMap<>();

    private final Object lock = new Object();

    /**
     * When true, the facade auto-morphs to AVL under sustained red-red stress.
     * Off by default so morph authority lives in one place (the control
     * plane); see {@link #morphIfStressed()}.
     */
    private boolean autoMorphEnabled = false;

    /**
     * Bounded-set / sliding-window capacity. 0 = unbounded (default). When &gt; 0,
     * a successful {@link #add} that pushes the set over capacity evicts the
     * oldest-inserted key (FIFO), keeping order statistics correct on the
     * survivors. {@link #liveOrder} tracks live keys in insertion order.
     */
    private int maxSize = 0;
    private final LinkedHashSet<Integer> liveOrder = new LinkedHashSet<>();

    /**
     * When false, {@link #add}/{@link #remove} skip recording undo history.
     * {@link TreeHistory} flips this off while replaying inverse operations
     * during undo/redo so the replay does not itself generate new history.
     * Internal collaborator hook — not part of the public client API.
     */
    private boolean historyRecording = true;

    // ── Constructor ───────────────────────────────────────────────────────────
    public TreeContext(TreeStrategy strategy) {
        logger.info("=== TREE CONTEXT INITIALIZED [strategy={}] ===",
                strategy.getClass().getSimpleName());
        this.strategy          = strategy;
        this.tree              = new RedBlackTree(strategy);
        this.persistenceAdapter = new FilePersistenceAdapter();
        this.diagnostics       = new TreeDiagnostics(this);
        this.cloner            = new TreeCloner(this);
        this.history           = new TreeHistory(this);
    }

    // ── Core operations ───────────────────────────────────────────────────────

    public void add(int value) {
        synchronized (lock) {
            // Duplicate guard: every strategy silently skips an existing key, so
            // incrementing size/metrics/history unconditionally would drift the
            // counters and record a phantom ADD whose later undo deletes a key the
            // caller never inserted. Only proceed when the insert truly happens.
            if (tree.contains(value)) {
                logger.debug("Duplicate add ignored: {}", value);
                return;
            }
            long start = System.nanoTime();

            tree.add(value);
            size++;
            liveOrder.add(value);   // FIFO insertion order, for windowed eviction

            // Stamp the context's current augmentor onto the freshly inserted node
            // so non-default augmentation (e.g. interval max-hi) is maintained for
            // keys added after setAugmentor(). createNode always installs the
            // default (subtree-size) augmentor, so without this a later insert
            // silently reverts that node to size augmentation.
            if (this.augmentor != TreeNode1.defaultAugmentor) {
                TreeNode1 inserted = tree.getStrategy().search(tree, value);
                if (!inserted.isNil()) inserted.setAugmentor(this.augmentor);
            }

            totalInsertTime += System.nanoTime() - start;
            insertCount++;
            // Inverse-command undo: record only the value, not a full tree copy.
            // (Previously snapshotted the entire tree here → O(n) per insert,
            //  O(n^2) to build a tree. See docs/code-review-2026-05-29.md #3.)
            if (historyRecording) history.recordAdd(value);
            updateMetadata(value);

            // Sliding-window eviction: drop oldest-inserted keys until within
            // capacity. Done as a system action (not recorded in undo history).
            while (maxSize > 0 && size > maxSize) {
                if (!evictOldest()) break;
            }
        }
    }

    public void remove(int value) {
        synchronized (lock) {
            // Guard: only decrement size and record history if the value exists
            if (!tree.contains(value)) {
                logger.warn("Remove skipped — value={} not found", value);
                return;
            }
            long start = System.nanoTime();

            tree.remove(value);
            size--;
            liveOrder.remove(value);

            totalDeleteTime += System.nanoTime() - start;
            deleteCount++;
            if (historyRecording) history.recordRemove(value);
            frequencyMap.remove(value);
            morphIfStressed();
        }
    }

    public boolean contains(int value) {
        return tree.contains(value);
    }

    // ── AugmentedTree ─────────────────────────────────────────────────────────

    /** The augmentor currently applied to nodes in this context. */
    public TreeNode1.Augmentor getAugmentor() { return augmentor; }

    /** Enable/disable the legacy facade-driven stress auto-morph (default off). */
    public void setAutoMorphEnabled(boolean enabled) { this.autoMorphEnabled = enabled; }

    /** @return whether the facade auto-morphs under stress (default false). */
    public boolean isAutoMorphEnabled() { return autoMorphEnabled; }

    /**
     * Set the bounded-set capacity (0 = unbounded). When positive, the set keeps
     * at most {@code n} keys, evicting the oldest-inserted ones first — a
     * sliding window. Order statistics stay exact on the survivors. Setting a
     * positive capacity immediately evicts down to it.
     */
    public void setMaxSize(int n) {
        synchronized (lock) {
            this.maxSize = Math.max(0, n);
            while (maxSize > 0 && size > maxSize) {
                if (!evictOldest()) break;
            }
        }
    }

    /** @return the bounded-set capacity, or 0 if unbounded. */
    public int getMaxSize() { return maxSize; }

    /**
     * Evict the oldest-inserted live key (FIFO). System action: not recorded in
     * undo history. Returns false if there is nothing to evict.
     */
    private boolean evictOldest() {
        if (liveOrder.size() != size) resyncLiveOrder();   // safety net after bulk rebuilds
        java.util.Iterator<Integer> it = liveOrder.iterator();
        if (!it.hasNext()) return false;
        int oldest = it.next();
        it.remove();
        if (tree.contains(oldest)) {
            tree.remove(oldest);
            size--;
            frequencyMap.remove(oldest);
        }
        return true;
    }

    /**
     * Rebuild {@link #liveOrder} from the current contents. Used only as a safety
     * net when the backing tree was replaced wholesale (snapshot load) and true
     * insertion order is no longer known; falls back to ascending key order.
     */
    private void resyncLiveOrder() {
        liveOrder.clear();
        liveOrder.addAll(diagnostics.inOrderTraversal());
    }

    @Override
    public void setAugmentor(TreeNode1.Augmentor augmentor) {
        this.augmentor = (augmentor != null) ? augmentor : TreeNode1.defaultAugmentor;
        synchronized (lock) {
            // Re-apply augmentor to every existing node (iterative DFS)
            TreeNode1 root = tree.getRoot();
            if (root.isNil()) return;

            Deque<TreeNode1> stack = new ArrayDeque<>();
            stack.push(root);
            while (!stack.isEmpty()) {
                TreeNode1 current = stack.pop();
                current.setAugmentor(this.augmentor);
                if (!current.getRight().isNil()) stack.push(current.getRight());
                if (!current.getLeft().isNil())  stack.push(current.getLeft());
            }
        }
    }

    // ── SelfHealingTree ───────────────────────────────────────────────────────

    @Override
    public boolean selfRepair() {
        logger.warn("Initiating self-repair protocol…");
        if (diagnostics.isValidRedBlack()) {
            logger.info("Tree stable — no repair needed.");
            return true;
        }

        // Capture elements (with their per-node tags) BEFORE clearing — don't
        // wipe history/snapshots, and don't lose interval high endpoints.
        Map<Integer, String> keyTags = captureKeyTags();
        List<Integer> elements = new ArrayList<>(keyTags.keySet());
        logger.warn("Rebuilding from {} elements: {}", elements.size(), elements);

        // Only reset the structural state, not history or snapshots
        synchronized (lock) {
            tree.setRoot(tree.getNIL());
            size = 0;
            frequencyMap.clear();
            recentInsertions.clear();
            stressEvents.clear();
        }

        for (int value : elements) add(value);   // add() re-stamps the augmentor
        restoreTags(keyTags);

        boolean repaired = diagnostics.isValidRedBlack();
        logger.info("Self-repair: {}", repaired ? "SUCCESS" : "FAILURE");
        return repaired;
    }

    // ── Strategy swap (adaptive morph) ────────────────────────────────────────

    /**
     * Swaps strategy and rebuilds the tree in-place from an in-order traversal.
     * Without the rebuild the morph would produce an empty tree — silent data loss.
     */
    public boolean setStrategy(TreeStrategy newStrategy) {
        synchronized (lock) {
            if (newStrategy == null || newStrategy.getClass() == strategy.getClass()) return false;

            Map<Integer, String> keyTags = captureKeyTags();
            List<Integer> elements = new ArrayList<>(keyTags.keySet()); // ascending, distinct
            logger.info("Morphing strategy: {} → {} ({} elements) — building candidate aside",
                    strategy.getClass().getSimpleName(),
                    newStrategy.getClass().getSimpleName(),
                    elements.size());

            // ── Build the candidate OFF TO THE SIDE — the incumbent tree is never
            //    touched, so a failed validation costs nothing to roll back. ──────
            RedBlackTree candidate = new RedBlackTree(newStrategy);
            for (int value : elements) candidate.add(value);

            // ── Health gate: validate before publishing (DESIGN §3.4). The
            //    candidate carries the default subtree-size augment here, so the
            //    order-statistics clause is valid regardless of this context's
            //    augmentor (re-applied after the swap below). ───────────────────
            List<String> failures =
                    StrategyHealthCheck.validate(candidate, newStrategy, elements);
            if (!failures.isEmpty()) {
                logger.warn("Morph to {} REJECTED by health gate: {} — keeping {} (incumbent untouched)",
                        newStrategy.getClass().getSimpleName(), failures,
                        strategy.getClass().getSimpleName());
                return false;
            }

            // ── Publish: single reference swap under the write lock. ────────────
            this.strategy = newStrategy;
            this.tree     = candidate;
            this.size     = elements.size();

            // Restore non-default augmentation + per-node tags onto the published
            // tree so interval trees survive the morph instead of degrading.
            if (this.augmentor != TreeNode1.defaultAugmentor) {
                setAugmentor(this.augmentor);   // re-applies to every published node
            }
            restoreTags(keyTags);

            logger.info("Morph complete and health-validated. New size={}", size);
            return true;
        }
    }

    // ── Persistence ───────────────────────────────────────────────────────────

    public void saveSnapshot(String name) {
        persistenceAdapter.saveSnapshot(name, cloner.snapshot());
        logger.info("Snapshot saved: '{}'", name);
    }

    public void loadSnapshot(String name) {
        TreeContext snapshot = persistenceAdapter.loadSnapshot(name);
        if (snapshot == null) {
            logger.warn("Snapshot '{}' not found.", name);
            return;
        }
        synchronized (lock) {
            this.tree          = snapshot.tree;
            this.size          = snapshot.size;
            this.strategy      = snapshot.strategy;
            this.augmentor     = snapshot.augmentor;
            this.rotationCount = snapshot.rotationCount;
            this.frequencyMap.clear();
            this.frequencyMap.putAll(snapshot.frequencyMap);
            resyncLiveOrder();   // tree was replaced wholesale; rebuild FIFO order
            logger.info("Snapshot '{}' loaded. size={}", name, size);
        }
    }

    // ── Advanced (delegated) ──────────────────────────────────────────────────

    // Alien-seed / agent-swarm were experimental theatrics that could install a
    // non-BST into a live, contract-bound context; they now live in the
    // standalone `experimental` package (experimental.TreeAgent), which depends on
    // core rather than core depending on it. Use `new experimental.TreeAgent(ctx)`
    // directly if you want that behavior.
    public List<TreeContext> deployCloneArmy(int count)       { return cloner.deployCloneArmy(count); }
    public void emitRelicBeacon()                             { diagnostics.emitRelicBeacon(); }

    // ── Metrics getters ───────────────────────────────────────────────────────

    public RedBlackTree getTree()          { return tree; }
    public int          getSize()          { return size; }

    /** Undo/redo + checkpoint history for this context. */
    public TreeHistory  getHistory()       { return history; }

    // ── OrderedCollection: neutral client-facing views ────────────────────────
    // size()/inOrder() satisfy the interface; getSize() is retained for callers
    // already written against it.

    /** {@inheritDoc} */
    @Override
    public int size() { return size; }

    /** {@inheritDoc} Ascending keys, delegated to the backing engine. */
    @Override
    public List<Integer> inOrder() { return diagnostics.inOrderTraversal(); }
    public int          getRotationCount() { return rotationCount; }
    public void         incrementRotations(){ rotationCount++; }  // called by strategy

    /**
     * Directly overrides the cached size. Reserved for trusted utility
     * collaborators (TreeAgent / TreeCloner / TreeHistory) that rebuild the
     * backing tree out-of-band and must resync the facade's size counter.
     */
    public void forceSizeInternal(int n) { this.size = n; }

    /**
     * Enable/disable undo-history recording. Reserved for {@link TreeHistory}
     * to suppress re-recording while it replays inverse operations.
     */
    public void setHistoryRecording(boolean enabled) { this.historyRecording = enabled; }

    public double avgInsertTimeMs() {
        return insertCount == 0 ? 0 : (totalInsertTime / 1_000_000.0) / insertCount;
    }
    public double avgDeleteTimeMs() {
        return deleteCount == 0 ? 0 : (totalDeleteTime / 1_000_000.0) / deleteCount;
    }

    // ── Internal ──────────────────────────────────────────────────────────────

    /**
     * In-order snapshot of every key and its tag. {@link LinkedHashMap} keeps
     * ascending key order, which also gives a stable re-insertion order for
     * rebuilds (morph / self-repair).
     */
    private Map<Integer, String> captureKeyTags() {
        Map<Integer, String> out = new LinkedHashMap<>();
        Deque<TreeNode1> stack = new ArrayDeque<>();
        TreeNode1 cur = tree.getRoot();
        while (!stack.isEmpty() || !cur.isNil()) {
            while (!cur.isNil()) { stack.push(cur); cur = cur.getLeft(); }
            cur = stack.pop();
            out.put(cur.getData(), cur.getTag());
            cur = cur.getRight();
        }
        return out;
    }

    /**
     * Re-apply captured tags after a rebuild. Setting a tag does not itself
     * trigger augmentation, so each tagged node is re-augmented to propagate
     * tag-derived values (e.g. interval max-hi) back up the tree.
     */
    private void restoreTags(Map<Integer, String> keyTags) {
        for (Map.Entry<Integer, String> e : keyTags.entrySet()) {
            String tag = e.getValue();
            if (tag == null || tag.isEmpty()) continue;
            TreeNode1 n = tree.getStrategy().search(tree, e.getKey());
            if (!n.isNil()) {
                n.setTag(tag);
                n.reaugment();
            }
        }
    }

    private void updateMetadata(int value) {
        frequencyMap.merge(value, 1, Integer::sum);
        recentInsertions.addLast(value);
        if (recentInsertions.size() > MEMORY_LIMIT) recentInsertions.removeFirst();

        // Track red-red violations as a stress signal. A single insert can only
        // introduce a violation at the new node's local neighborhood, so check
        // there in O(log n) rather than scanning the whole tree (O(n)) per insert.
        if (!diagnostics.hasNoRedRedAt(value)) {
            stressEvents.merge("redRedViolations", 1, Integer::sum);
        } else {
            stressEvents.put("redRedViolations", 0); // reset on clean insert
        }
        morphIfStressed();
    }

    private void morphIfStressed() {
        // Disabled by default: TreeContext is a passive data plane, and morph
        // decisions belong to a single authority (the control plane /
        // GenomeDrivenTreeController, which calls setStrategy directly). When the
        // facade auto-morphed on its own it fought the controller and contaminated
        // benchmarks (a "RedBlack" run could silently become AVL). Opt in via
        // setAutoMorphEnabled(true) for the legacy self-morphing behavior.
        if (!autoMorphEnabled) return;
        int violations = stressEvents.getOrDefault("redRedViolations", 0);
        if (violations > STRESS_THRESHOLD) {
            logger.warn("STRESS THRESHOLD EXCEEDED (violations={}) — morphing to AVL.", violations);
            stressEvents.put("redRedViolations", 0);
            setStrategy(new AVLStrategy()); // health-gated; preserves data
        }
    }

    public void clear() {
        synchronized (lock) {
            tree.setRoot(tree.getNIL());
            size = 0;
            frequencyMap.clear();
            recentInsertions.clear();
            stressEvents.clear();
            liveOrder.clear();
        }
    }
}
