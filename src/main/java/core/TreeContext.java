package core;

import core.interfaces.AugmentedTree;
import core.interfaces.OrderedCollection;
import core.interfaces.SelfHealingTree;
import core.interfaces.TreePersistenceAdapter;
import core.persistence.FilePersistenceAdapter;
import core.strategy.AVLStrategy;
import core.strategy.TreeStrategy;
import core.control.StrategyMorphTarget;
import core.util.*;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.*;

/**
 * Facade over a {@link RedBlackTree} engine adding metrics, persistence,
 * augmentation, history and adaptive strategy morphing.
 *
 * <p>ADR-002 step 4: this is the {@code Integer} adapter over the generic
 * {@link OrderedSet} facade. Its public API stays {@code int}; internally it
 * holds an {@code OrderedSet<Integer>} that owns the ordered-set behaviour:
 * dedup-guarded add/remove, the size counter, order statistics, the
 * health-gated strategy morph, the sliding window, augmentation, and the
 * self-repair rebuild. {@code TreeContext} retains only the genuinely
 * {@code Integer}-bound machinery layered on top: undo/redo history, snapshot
 * persistence, cloning, diagnostics/relic reporting, and the legacy
 * facade-driven stress auto-morph (default off). The ~295-test {@code int}
 * suite is the regression harness for this delegation.</p>
 *
 * <h2>Concurrency contract</h2>
 * <p><strong>This class is designed for single-threaded use.</strong> The
 * backing {@link RedBlackTree}, the {@link core.strategy.TreeStrategy}
 * implementations, and the per-node {@link TreeNode1} state are all
 * <em>not</em> thread-safe.</p>
 *
 * <p>The state-changing operations -- {@link #add(int)}, {@link #remove(int)},
 * {@link #setStrategy}, {@link #clear()} -- serialize on a single internal lock,
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
public class TreeContext implements AugmentedTree<Integer>, SelfHealingTree, OrderedCollection<Integer>, StrategyMorphTarget<Integer> {

    private static final Logger logger = LogManager.getLogger(TreeContext.class);

    // -- Core state --
    // The ordered-set behaviour (engine, size, order statistics, morph, window,
    // augmentation, metrics) lives in this generic delegate. Not final: a snapshot
    // load adopts the deserialized context's set wholesale.
    private OrderedSet<Integer>       set;
    private TreePersistenceAdapter    persistenceAdapter;

    // -- Utility delegates --
    private final TreeDiagnostics     diagnostics;
    private final TreeCloner          cloner;
    private final TreeHistory         history;

    // -- Metrics --
    // Rotation count is a facade-level counter (incrementRotations is a legacy hook,
    // currently uncalled by the strategies); insert/delete timings live in the set.
    private int  rotationCount    = 0;

    // -- Stress / adaptive morph --
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
     * When false, {@link #add}/{@link #remove} skip recording undo history.
     * {@link TreeHistory} flips this off while replaying inverse operations
     * during undo/redo so the replay does not itself generate new history.
     * Internal collaborator hook -- not part of the public client API.
     */
    private boolean historyRecording = true;

    // -- Constructor --
    public TreeContext(TreeStrategy<Integer> strategy) {
        logger.info("=== TREE CONTEXT INITIALIZED [strategy={}] ===",
                strategy.getClass().getSimpleName());
        this.set                = OrderedSet.withNaturalOrder(strategy);
        this.persistenceAdapter = new FilePersistenceAdapter();
        this.diagnostics        = new TreeDiagnostics(this);
        this.cloner             = new TreeCloner(this);
        this.history            = new TreeHistory(this);
    }

    // -- Core operations --

    /** Public {@code int} API -- delegates to the {@code Integer} adapter method. */
    public void add(int value) { add(Integer.valueOf(value)); }

    /**
     * {@inheritDoc}
     *
     * <p>{@link OrderedSet#add} is the dedup guard: the size counter, FIFO window,
     * augmentor stamping and insert metrics all happen inside it, and it returns
     * {@code false} on a duplicate. So the {@code Integer}-only side-effects -- undo
     * history and the stress signal -- fire only on a real insert, keeping the undo
     * log and counters from drifting on a no-op add.</p>
     */
    @Override
    public boolean add(Integer value) {
        synchronized (lock) {
            if (!set.add(value)) {
                logger.debug("Duplicate add ignored: {}", value);
                return false;
            }
            // Inverse-command undo: record only the value, not a full tree copy.
            if (historyRecording) history.recordAdd(value);
            updateMetadata(value);
            return true;
        }
    }

    /** Public {@code int} API -- delegates to the {@code Integer} adapter method. */
    public void remove(int value) { remove(Integer.valueOf(value)); }

    /** {@inheritDoc} */
    @Override
    public boolean remove(Integer value) {
        synchronized (lock) {
            if (!set.remove(value)) {
                logger.warn("Remove skipped -- value={} not found", value);
                return false;
            }
            if (historyRecording) history.recordRemove(value);
            frequencyMap.remove(value);
            morphIfStressed();
            return true;
        }
    }

    /** Public {@code int} API. */
    public boolean contains(int value) { return set.contains(value); }

    /** {@inheritDoc} */
    @Override
    public boolean contains(Integer value) { return set.contains(value); }

    // -- AugmentedTree --

    /** The augmentor currently applied to nodes in this context. */
    public TreeNode1.Augmentor<Integer> getAugmentor() { return set.getAugmentor(); }

    /** Enable/disable the legacy facade-driven stress auto-morph (default off). */
    public void setAutoMorphEnabled(boolean enabled) { this.autoMorphEnabled = enabled; }

    /** @return whether the facade auto-morphs under stress (default false). */
    public boolean isAutoMorphEnabled() { return autoMorphEnabled; }

    /**
     * Set the bounded-set capacity (0 = unbounded). When positive, the set keeps
     * at most {@code n} keys, evicting the oldest-inserted ones first -- a
     * sliding window. Order statistics stay exact on the survivors. Setting a
     * positive capacity immediately evicts down to it.
     */
    public void setMaxSize(int n) { set.setMaxSize(n); }

    /** @return the bounded-set capacity, or 0 if unbounded. */
    public int getMaxSize() { return set.getMaxSize(); }

    @Override
    public void setAugmentor(TreeNode1.Augmentor<Integer> augmentor) {
        set.setAugmentor(augmentor);
    }

    // -- SelfHealingTree --

    @Override
    public boolean selfRepair() {
        logger.warn("Initiating self-repair protocol...");
        // Cheap short-circuit on an already-healthy tree (preserves the original
        // no-op-when-valid behaviour and avoids a needless rebuild).
        if (diagnostics.isValidRedBlack()) {
            logger.info("Tree stable -- no repair needed.");
            return true;
        }
        synchronized (lock) {
            // OrderedSet.selfRepair rebuilds from a sorted, de-duplicated snapshot
            // (carrying per-node tags) and validates via StrategyHealthCheck.
            boolean repaired = set.selfRepair();
            // The engine was rebuilt wholesale; reset the (default-off) stress signal
            // so a stale red-red counter cannot trip a spurious morph afterwards.
            frequencyMap.clear();
            recentInsertions.clear();
            stressEvents.clear();
            logger.info("Self-repair: {}", repaired ? "SUCCESS" : "FAILURE");
            return repaired;
        }
    }

    // -- Strategy swap (adaptive morph) --

    /**
     * Swap the balancing strategy. Delegates the health-gated morph (build the
     * candidate aside -> validate -> publish, carrying per-node tags) to
     * {@link OrderedSet#setStrategy}; a rejected or same-class morph leaves the
     * incumbent untouched and returns {@code false}.
     */
    public boolean setStrategy(TreeStrategy<Integer> newStrategy) {
        synchronized (lock) {
            return set.setStrategy(newStrategy);
        }
    }

    /** {@inheritDoc} The installed balancing strategy (delegated to the set). */
    @Override
    public TreeStrategy<Integer> getStrategy() { return set.getStrategy(); }

    // -- Persistence --

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
            // The snapshot was deserialized into its own TreeContext: its engine was
            // rebuilt wholesale and its set's size/window resynced via
            // forceSizeInternal. Adopt that set outright, then copy the Integer-only
            // extras. (frequencyMap is preserved; history/snapshots are not wiped.)
            this.set           = snapshot.set;
            this.rotationCount = snapshot.rotationCount;
            this.frequencyMap.clear();
            this.frequencyMap.putAll(snapshot.frequencyMap);
            logger.info("Snapshot '{}' loaded. size={}", name, set.size());
        }
    }

    // -- Advanced (delegated) --

    // Alien-seed / agent-swarm were experimental theatrics that could install a
    // non-BST into a live, contract-bound context; they now live in the
    // standalone `experimental` package (experimental.TreeAgent), which depends on
    // core rather than core depending on it. Use `new experimental.TreeAgent(ctx)`
    // directly if you want that behavior.
    public List<TreeContext> deployCloneArmy(int count)       { return cloner.deployCloneArmy(count); }
    public void emitRelicBeacon()                             { diagnostics.emitRelicBeacon(); }

    // -- Metrics getters --

    public RedBlackTree<Integer> getTree() { return set.getEngine(); }
    public int          getSize()          { return set.size(); }

    /** Undo/redo + checkpoint history for this context. */
    public TreeHistory  getHistory()       { return history; }

    // -- OrderedCollection: neutral client-facing views --
    // size()/inOrder() satisfy the interface; getSize() is retained for callers
    // already written against it.

    /** {@inheritDoc} */
    @Override
    public int size() { return set.size(); }

    /** {@inheritDoc} Ascending keys, delegated to the backing engine. */
    @Override
    public List<Integer> inOrder() { return set.inOrder(); }
    public int          getRotationCount() { return rotationCount; }
    public void         incrementRotations(){ rotationCount++; }  // legacy hook (strategies do not call it)

    /**
     * Resync the facade after the backing engine was rebuilt out-of-band through
     * {@link #getTree()} (snapshot deserialization, undo/redo restore, clone
     * rebuild). The {@code OrderedSet} recomputes its size and FIFO window from the
     * engine's current contents; the {@code n} argument is advisory. Reserved for
     * trusted utility collaborators (TreeCloner / TreeHistory / FilePersistenceAdapter).
     */
    public void forceSizeInternal(int n) { set.resyncFromEngine(); }

    /**
     * Enable/disable undo-history recording. Reserved for {@link TreeHistory}
     * to suppress re-recording while it replays inverse operations.
     */
    public void setHistoryRecording(boolean enabled) { this.historyRecording = enabled; }

    public double avgInsertTimeMs() { return set.avgInsertTimeMs(); }
    public double avgDeleteTimeMs() { return set.avgDeleteTimeMs(); }

    // -- Internal --

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
            logger.warn("STRESS THRESHOLD EXCEEDED (violations={}) -- morphing to AVL.", violations);
            stressEvents.put("redRedViolations", 0);
            setStrategy(new AVLStrategy<>()); // health-gated; preserves data
        }
    }

    public void clear() {
        synchronized (lock) {
            set.clear();
            frequencyMap.clear();
            recentInsertions.clear();
            stressEvents.clear();
        }
    }
}
