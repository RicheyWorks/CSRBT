package core;

import core.interfaces.AugmentedTree;
import core.interfaces.SelfHealingTree;
import core.interfaces.TreePersistenceAdapter;
import core.persistence.FilePersistenceAdapter;
import core.strategy.AVLStrategy;
import core.strategy.TreeStrategy;
import core.util.*;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.*;

public class TreeContext implements AugmentedTree, SelfHealingTree {

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
    private final TreeAgent           agent;
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

    // ── Constructor ───────────────────────────────────────────────────────────
    public TreeContext(TreeStrategy strategy) {
        logger.info("=== TREE CONTEXT INITIALIZED [strategy={}] ===",
                strategy.getClass().getSimpleName());
        this.strategy          = strategy;
        this.tree              = new RedBlackTree(strategy);
        this.persistenceAdapter = new FilePersistenceAdapter();
        this.diagnostics       = new TreeDiagnostics(this);
        this.cloner            = new TreeCloner(this);
        this.agent             = new TreeAgent(this);
        this.history           = new TreeHistory(this);
    }

    // ── Core operations ───────────────────────────────────────────────────────

    public void add(int value) {
        synchronized (lock) {
            TreeContext snapshot = cloner.snapshot();
            long start = System.nanoTime();

            tree.add(value);
            size++;

            totalInsertTime += System.nanoTime() - start;
            insertCount++;
            history.addCommand(TreeHistory.Command.Action.ADD, value, snapshot);
            updateMetadata(value);
        }
    }

    public void remove(int value) {
        synchronized (lock) {
            // Guard: only decrement size and record history if the value exists
            if (!tree.contains(value)) {
                logger.warn("Remove skipped — value={} not found", value);
                return;
            }
            TreeContext snapshot = cloner.snapshot();
            long start = System.nanoTime();

            tree.remove(value);
            size--;

            totalDeleteTime += System.nanoTime() - start;
            deleteCount++;
            history.addCommand(TreeHistory.Command.Action.REMOVE, value, snapshot);
            frequencyMap.remove(value);
            morphIfStressed();
        }
    }

    public boolean contains(int value) {
        return tree.contains(value);
    }

    // ── AugmentedTree ─────────────────────────────────────────────────────────

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

        // Capture elements BEFORE clearing — don't wipe history/snapshots
        List<Integer> elements = diagnostics.inOrderTraversal();
        logger.warn("Rebuilding from {} elements: {}", elements.size(), elements);

        // Only reset the structural state, not history or snapshots
        synchronized (lock) {
            tree.setRoot(TreeNode1.NIL);
            size = 0;
            frequencyMap.clear();
            recentInsertions.clear();
            stressEvents.clear();
        }

        for (int value : elements) add(value);

        boolean repaired = diagnostics.isValidRedBlack();
        logger.info("Self-repair: {}", repaired ? "SUCCESS" : "FAILURE");
        return repaired;
    }

    // ── Strategy swap (adaptive morph) ────────────────────────────────────────

    /**
     * Swaps strategy and rebuilds the tree in-place from an in-order traversal.
     * Without the rebuild the morph would produce an empty tree — silent data loss.
     */
    public void setStrategy(TreeStrategy newStrategy) {
        synchronized (lock) {
            if (newStrategy == null || newStrategy.getClass() == strategy.getClass()) return;

            List<Integer> elements = diagnostics.inOrderTraversal();
            logger.info("Morphing strategy: {} → {} ({} elements to re-insert)",
                    strategy.getClass().getSimpleName(),
                    newStrategy.getClass().getSimpleName(),
                    elements.size());

            this.strategy = newStrategy;
            this.tree     = new RedBlackTree(newStrategy);
            this.size     = 0;

            for (int value : elements) {
                tree.add(value);
                size++;
            }
            logger.info("Morph complete. New size={}", size);
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
            logger.info("Snapshot '{}' loaded. size={}", name, size);
        }
    }

    // ── Advanced (delegated) ──────────────────────────────────────────────────

    public void alienSeed(int seedValue, int maxDepth, int variance) {
        agent.alienSeed(seedValue, maxDepth, variance);
    }

    public void runAgentSwarm()                               { agent.runAgentSwarm(); }
    public List<TreeContext> deployCloneArmy(int count)       { return cloner.deployCloneArmy(count); }
    public void emitRelicBeacon()                             { diagnostics.emitRelicBeacon(); }

    // ── Metrics getters ───────────────────────────────────────────────────────

    public RedBlackTree getTree()          { return tree; }
    public int          getSize()          { return size; }
    public int          getRotationCount() { return rotationCount; }
    public void         incrementRotations(){ rotationCount++; }  // called by strategy

    public double avgInsertTimeMs() {
        return insertCount == 0 ? 0 : (totalInsertTime / 1_000_000.0) / insertCount;
    }
    public double avgDeleteTimeMs() {
        return deleteCount == 0 ? 0 : (totalDeleteTime / 1_000_000.0) / deleteCount;
    }

    // ── Internal ──────────────────────────────────────────────────────────────

    private void updateMetadata(int value) {
        frequencyMap.merge(value, 1, Integer::sum);
        recentInsertions.addLast(value);
        if (recentInsertions.size() > MEMORY_LIMIT) recentInsertions.removeFirst();

        // Track red-red violations as a stress signal
        if (!diagnostics.hasNoRedRed()) {
            stressEvents.merge("redRedViolations", 1, Integer::sum);
        } else {
            stressEvents.put("redRedViolations", 0); // reset on clean insert
        }
        morphIfStressed();
    }

    private void morphIfStressed() {
        int violations = stressEvents.getOrDefault("redRedViolations", 0);
        if (violations > STRESS_THRESHOLD) {
            logger.warn("STRESS THRESHOLD EXCEEDED (violations={}) — morphing to AVL.", violations);
            stressEvents.put("redRedViolations", 0);
            setStrategy(new AVLStrategy()); // setStrategy now preserves data
        }
    }

    public void clear() {
        synchronized (lock) {
            tree.setRoot(TreeNode1.NIL);
            size = 0;
            frequencyMap.clear();
            recentInsertions.clear();
            stressEvents.clear();
        }
    }
}
