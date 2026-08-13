package io.github.richeyworks.csrbt;

import io.github.richeyworks.csrbt.interfaces.AugmentedTree;
import io.github.richeyworks.csrbt.interfaces.OrderedCollection;
import io.github.richeyworks.csrbt.interfaces.SelfHealingTree;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter;
import io.github.richeyworks.csrbt.persistence.FilePersistenceAdapter;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;
import io.github.richeyworks.csrbt.control.StrategyMorphTarget;
import io.github.richeyworks.csrbt.util.*;
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
 * <p><strong>One writer, many readers</strong> (ADR-004 R1, inherited from the
 * {@link OrderedSet} delegate). State-changing operations -- {@link #add(int)},
 * {@link #remove(int)}, {@link #setStrategy}, {@link #clear()} -- serialize on a
 * single internal lock, and the delegated reads ({@link #contains(int)},
 * {@link #size()}, {@link #inOrder()} and the order statistics) are
 * torn-read-free under concurrent writes: optimistic, stamp-validated walks
 * with a locked fallback. Two caveats remain:</p>
 * <ul>
 *   <li>Accessors such as {@link #getTree()} and anything that hands out live
 *       {@link TreeNode1}s bypass the guard entirely -- the backing
 *       {@link RedBlackTree}, the {@link io.github.richeyworks.csrbt.strategy.TreeStrategy}
 *       implementations, and per-node state are <em>not</em> thread-safe. Treat
 *       these as a single-threaded diagnostics seam.</li>
 *   <li>The {@code Integer}-bound machinery layered on this adapter (undo/redo
 *       history, snapshot persistence, cloning, diagnostics) mutates the engine
 *       out-of-band and assumes a single thread.</li>
 * </ul>
 *
 * <p>An application doing anything beyond plain reads-under-writes must still
 * provide external synchronization (or use the ensemble's {@code READ_REPLICA}
 * mode for lock-free reads at member granularity).</p>
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
            // D-2 (consolidation 2026-08-12): with a sliding window active, this add may
            // evict the oldest key. Capture the victim BEFORE the add; if the insert
            // succeeded but the size did not grow, the eviction happened and the undo
            // command must carry it — recording only ADD(v) made undo drop the evicted
            // key permanently.
            int sizeBefore = set.size();
            Integer victim = historyRecording ? set.peekOldest() : null;
            if (!set.add(value)) {
                logger.debug("Duplicate add ignored: {}", value);
                return false;
            }
            // Inverse-command undo: record only the value, not a full tree copy.
            if (historyRecording) {
                history.recordAdd(value, set.size() == sizeBefore ? victim : null);
            }
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
        synchronized (lock) {
            // Cheap short-circuit on an already-healthy tree — validated against the
            // CURRENT strategy's invariant (ADR-010 X1). The old gate was
            // diagnostics.isValidRedBlack() regardless of strategy, so after a morph to
            // AVL/Splay/Hybrid a perfectly healthy tree failed RB color discipline and
            // every selfRepair() call paid a needless O(n) rebuild.
            if (StrategyHealthCheck.validate(set.getEngine(), set.getStrategy(),
                    set.inOrder()).isEmpty()) {
                logger.info("Tree stable -- no repair needed.");
                return true;
            }
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
    // non-BST into a live, contract-bound context; they were quarantined to the
    // experimental package (TreeAgent) and then removed entirely in the 2026-07-14
    // capability audit — zero tests, zero consumers, and a contract-violating tree
    // builder is exactly where the next audit's bug lives. Recover from git history
    // if the theatrics are ever wanted again.
    public List<TreeContext> deployCloneArmy(int count)       { return cloner.deployCloneArmy(count); }
    public void emitRelicBeacon()                             { diagnostics.emitRelicBeacon(); }

    // -- Metrics getters --

    public RedBlackTree<Integer> getTree() { return set.getEngine(); }
    public int          getSize()          { return set.size(); }

    /**
     * The backing {@link OrderedSet} — like {@link #getTree()}, a diagnostics/export seam
     * (event-listener registration, {@code TreeExport}, session recording — ADR-010 X2),
     * not a second mutation path.
     */
    public OrderedSet<Integer> getOrderedSet() { return set; }

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
    /**
     * Total primitive rotations the CURRENT engine has performed (T-1, 2026-08-12):
     * this used to read a legacy field nothing increments — the battle runner's
     * rotation term and the genome controller's stress metric (rotations per window)
     * were identically 0 forever. Now delegates to the engine's live
     * {@code onRotation()} meter. Note a strategy morph builds the engine aside, so
     * the count resets on morph — per-window deltas self-heal (one clamped-to-zero
     * window), cumulative readers should sample per engine generation.
     */
    public int          getRotationCount() { return (int) Math.min(Integer.MAX_VALUE,
                                                    set.getEngine().rotationCount()); }
    /** @deprecated dead legacy hook — the engine meters rotations itself via
     *  {@code onRotation()}; this no longer feeds {@link #getRotationCount()}. */
    @Deprecated
    public void         incrementRotations(){ rotationCount++; }

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
