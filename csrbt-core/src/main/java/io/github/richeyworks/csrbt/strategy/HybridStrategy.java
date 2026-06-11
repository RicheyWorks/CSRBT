package io.github.richeyworks.csrbt.strategy;

import io.github.richeyworks.csrbt.MutableTree;
import io.github.richeyworks.csrbt.TreeNode1;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;

/**
 * HybridStrategy v2 — AVL balance + RB color, fully self-instrumented.
 *
 * Every meaningful internal event is counted so the genome feedback loop
 * and diagnostics mode have real numbers to work with.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * METRICS TRACKED
 *
 *   avlRotationCount   — rotations fired by the AVL balance phase
 *   rbFixCount         — color flips fired by the RB recolor phase
 *   relaxedNodeCount   — nodes that received ±2 tolerance (depth > threshold)
 *   totalNodesSeen     — nodes visited across all fix passes (denominator for %)
 *   hotNodeFrequency   — access count per key (identifies hot nodes)
 *   insertCount        — total insertions processed
 *   deleteCount        — total deletions processed
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * GENOME FEEDBACK
 *
 * Call snapshot() to get a HybridMetricsSnapshot.
 * The GenomeDrivenTreeController feeds that into adjustHybridFitness().
 * Call resetMetrics() after each eval window to keep numbers per-window.
 * ─────────────────────────────────────────────────────────────────────────────
 */
public class HybridStrategy<K> implements TreeStrategy<K> {

    private static final Logger logger = LogManager.getLogger(HybridStrategy.class);

    /** Nodes accessed this many times or more are "hot". */
    public static final int HOT_NODE_THRESHOLD = 3;

    private final int depthThreshold;

    // ── Instrumentation counters ──────────────────────────────────────────────
    // Plain fields: a strategy is driven only through TreeContext, whose mutators
    // are serialized, and is otherwise single-threaded. The previous AtomicInteger
    // / ConcurrentHashMap types implied a thread-safety the surrounding tree
    // operations never provided, so they were misleading rather than protective.
    private int avlRotationCount = 0;
    private int rbFixCount       = 0;
    private int relaxedNodeCount = 0;
    private int totalNodesSeen   = 0;
    private int insertCount      = 0;
    private int deleteCount      = 0;

    /** key → access count; identifies hot nodes. */
    private final Map<K, Integer> hotNodeFrequency = new HashMap<>();

    public HybridStrategy() {
        this(Integer.MAX_VALUE);
    }

    public HybridStrategy(int depthThreshold) {
        this.depthThreshold = depthThreshold;
    }

    // ── Insert ────────────────────────────────────────────────────────────────

    @Override
    public void insert(MutableTree<K> tree, TreeNode1<K> newNode) {
        TreeNode1<K> nil = tree.getNIL();
        TreeNode1<K> y   = nil;
        TreeNode1<K> x   = tree.getRoot();

        while (!x.isNil()) {
            y = x;
            if (newNode.compareTo(x) == 0) {
                logger.warn("Hybrid duplicate insert skipped: {}", newNode.getData());
                recordAccess(newNode.getData());
                return;
            }
            x = (newNode.compareTo(x) < 0) ? x.getLeft() : x.getRight();
        }

        newNode.setColor(TreeNode1.Color.RED);
        newNode.setParent(y);

        if (y.isNil()) {
            tree.setRoot(newNode);
        } else if (newNode.compareTo(y) < 0) {
            y.safeSetLeft(newNode);
        } else {
            y.safeSetRight(newNode);
        }

        insertCount++;
        recordAccess(newNode.getData());
    }

    /**
     * Phase 1: AVL rebalance (counts every rotation).
     * Phase 2: RB recolor along the affected path (counts every color flip).
     */
    @Override
    public void fixInsert(MutableTree<K> tree, TreeNode1<K> node) {
        avlRebalanceUp(tree, node.getParent());
        rbRecolorPathUp(node);                       // O(log n), not a full-tree scan
        tree.getRoot().setColor(TreeNode1.Color.BLACK);
    }

    // ── Delete ────────────────────────────────────────────────────────────────

    @Override
    public void delete(MutableTree<K> tree, TreeNode1<K> z) {
        TreeNode1<K> rebalanceFrom;

        if (z.getLeft().isNil()) {
            rebalanceFrom = z.getParent();
            transplant(tree, z, z.getRight());
        } else if (z.getRight().isNil()) {
            rebalanceFrom = z.getParent();
            transplant(tree, z, z.getLeft());
        } else {
            TreeNode1<K> successor = minimum(z.getRight());
            rebalanceFrom = (successor.getParent() == z) ? successor : successor.getParent();
            if (successor.getParent() != z) {
                transplant(tree, successor, successor.getRight());
                // Local link: successor's parent pointer is still stale and points
                // into z.getRight()'s subtree here, so a propagating setRight would
                // walk a cyclic parent chain and loop forever. transplant below
                // fixes the parent; setLeft then propagates the augment up.
                successor.setRightLocal(z.getRight());
                successor.getRight().setParent(successor);
            }
            transplant(tree, z, successor);
            successor.setLeft(z.getLeft());
            successor.getLeft().setParent(successor);
            successor.setColor(z.getColor());
        }

        avlRebalanceUp(tree, rebalanceFrom);
        rbRecolorPathUp(rebalanceFrom);              // O(log n), not a full-tree scan
        tree.getRoot().setColor(TreeNode1.Color.BLACK);
        deleteCount++;
    }

    // ── Search ────────────────────────────────────────────────────────────────

    @Override
    public TreeNode1<K> search(MutableTree<K> tree, K value) {
        TreeNode1<K> cur = tree.getRoot();
        while (!cur.isNil()) {
            int cmp = cur.compareKeyTo(value);   // sign of (cur.key - value)
            if (cmp == 0) {
                recordAccess(value);
                return cur;
            }
            cur = (cmp > 0) ? cur.getLeft() : cur.getRight();   // cur.key > value → go left
        }
        return tree.getNIL();
    }

    // ── AVL rebalance (Phase 1) ───────────────────────────────────────────────

    private void avlRebalanceUp(MutableTree<K> tree, TreeNode1<K> start) {
        TreeNode1<K> cur = start;
        while (cur != null && !cur.isNil()) {
            // Keep cached heights current along the path (see AVLStrategy note).
            cur.refreshHeight();
            totalNodesSeen++;
            int bf        = balanceFactor(cur);
            int depth     = cur.depth();
            int tolerance = (depth <= depthThreshold) ? 1 : 2;

            if (depth > depthThreshold) relaxedNodeCount++;

            if (bf > tolerance) {
                if (balanceFactor(cur.getLeft()) < 0) {
                    rotateLeft(tree, cur.getLeft());
                    avlRotationCount++;
                }
                rotateRight(tree, cur);
                avlRotationCount++;
                cur = cur.getParent();
            } else if (bf < -tolerance) {
                if (balanceFactor(cur.getRight()) > 0) {
                    rotateRight(tree, cur.getRight());
                    avlRotationCount++;
                }
                rotateLeft(tree, cur);
                avlRotationCount++;
                cur = cur.getParent();
            }

            cur = cur.getParent();
        }
    }

    // ── RB recolor pass (Phase 2) ─────────────────────────────────────────────

    /**
     * Recolor along the path from {@code start} up to the root: wherever a red node
     * sits under a red parent, blacken the parent. Only nodes on the just-modified
     * path can have acquired a new red-red adjacency, so an O(log n) walk suffices —
     * the previous full-tree O(n) DFS on every write violated the O(log n)-per-op
     * goal (audit finding S1). Colors here are cosmetic (Hybrid's balance comes from
     * the AVL pass), so this need not establish full red-black validity.
     */
    private void rbRecolorPathUp(TreeNode1<K> start) {
        TreeNode1<K> cur = start;
        while (cur != null && !cur.isNil()) {
            TreeNode1<K> parent = cur.getParent();
            if (cur.isRed() && parent != null && !parent.isNil() && parent.isRed()) {
                parent.setColor(TreeNode1.Color.BLACK);
                rbFixCount++;
            }
            cur = parent;
        }
    }

    // ── Metrics API ───────────────────────────────────────────────────────────

    public HybridMetricsSnapshot snapshot(int treeSize, double avgSearchDepth) {
        int totalSeen = totalNodesSeen;
        double relaxedPct = (totalSeen == 0) ? 0.0
                : (double) relaxedNodeCount / totalSeen;

        long hotNodeCount = hotNodeFrequency.values().stream()
                .filter(c -> c >= HOT_NODE_THRESHOLD)
                .count();

        // Balance quality: ratio of ideal height to actual — 1.0 is perfect
        double balanceQuality = computeBalanceQuality(treeSize, avgSearchDepth);

        return new HybridMetricsSnapshot(
                avlRotationCount,
                rbFixCount,
                relaxedPct,
                (int) hotNodeCount,
                balanceQuality,
                avgSearchDepth,
                insertCount,
                deleteCount        );
    }

    public void resetMetrics() {
        avlRotationCount = 0;
        rbFixCount = 0;
        relaxedNodeCount = 0;
        totalNodesSeen = 0;
        // Keep hotNodeFrequency — it accumulates across windows intentionally
    }

    public void fullReset() {
        resetMetrics();
        hotNodeFrequency.clear();
        insertCount = 0;
        deleteCount = 0;
    }

    // ── Accessors for live counters (no snapshot needed) ──────────────────────

    public int getAvlRotationCount() { return avlRotationCount; }
    public int getRbFixCount()       { return rbFixCount; }
    public int getRelaxedNodeCount() { return relaxedNodeCount; }
    public int getTotalNodesSeen()   { return totalNodesSeen; }
    public int getInsertCount()      { return insertCount; }
    public int getDeleteCount()      { return deleteCount; }
    public int getDepthThreshold()   { return depthThreshold; }

    public Set<Map.Entry<K, Integer>> getHotNodeEntries() {
        return hotNodeFrequency.entrySet();
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private void recordAccess(K value) {
        hotNodeFrequency.merge(value, 1, Integer::sum);
    }

    private double computeBalanceQuality(int n, double avgDepth) {
        if (n < 2 || avgDepth <= 0) return 1.0;
        double ideal = Math.ceil(Math.log(n + 1) / Math.log(2));
        return Math.min(1.0, ideal / avgDepth);
    }

    private int height(TreeNode1<K> node) {
        return (node == null || node.isNil()) ? 0 : node.getHeight();
    }

    private int balanceFactor(TreeNode1<K> node) {
        return height(node.getLeft()) - height(node.getRight());
    }

    private void transplant(MutableTree<K> tree, TreeNode1<K> u, TreeNode1<K> v) {
        TreeNode1<K> uParent = u.getParent();
        if (uParent == null || uParent.isNil()) {
            tree.setRoot(v);
        } else if (u == uParent.getLeft()) {
            uParent.setLeft(v);
        } else {
            uParent.setRight(v);
        }
        v.setParent(uParent != null ? uParent : tree.getNIL());
    }

    private TreeNode1<K> minimum(TreeNode1<K> node) {
        while (!node.getLeft().isNil()) node = node.getLeft();
        return node;
    }

    // ── Snapshot data class ───────────────────────────────────────────────────

    /**
     * Immutable snapshot of one eval window's hybrid metrics.
     * Passed to GenomeDrivenTreeController → genome feedback loop.
     */
    public static class HybridMetricsSnapshot {
        public final int    avlRotations;
        public final int    rbFixes;
        public final double relaxedNodePct;   // 0.0 – 1.0
        public final int    hotNodeCount;
        public final double balanceQuality;   // 0.0 – 1.0 (1.0 = perfect)
        public final double avgSearchDepth;
        public final int    insertCount;
        public final int    deleteCount;

        public HybridMetricsSnapshot(int avlRotations, int rbFixes,
                                     double relaxedNodePct, int hotNodeCount,
                                     double balanceQuality, double avgSearchDepth,
                                     int insertCount, int deleteCount) {
            this.avlRotations   = avlRotations;
            this.rbFixes        = rbFixes;
            this.relaxedNodePct = relaxedNodePct;
            this.hotNodeCount   = hotNodeCount;
            this.balanceQuality = balanceQuality;
            this.avgSearchDepth = avgSearchDepth;
            this.insertCount    = insertCount;
            this.deleteCount    = deleteCount;
        }

        /**
         * Fitness signal for the genome's hybridFitness() — 0.0 to 1.0.
         *
         *   balanceQuality    → high is good (AVL phase doing its job)
         *   rbFix cost        → high ratio is bad (color thrash)
         *   avlRotation cost  → moderate is expected; very high = fragmented input
         */
        public double derivedFitness(int treeSize) {
            if (treeSize == 0) return 0.5;
            double rotCost  = Math.min(1.0, (double) avlRotations / Math.max(1, insertCount + deleteCount));
            double fixCost  = Math.min(1.0, (double) rbFixes       / Math.max(1, insertCount + deleteCount));

            return Math.max(0.0, Math.min(1.0,
                    (balanceQuality * 0.45) +
                    ((1.0 - rotCost)  * 0.25) +
                    ((1.0 - fixCost)  * 0.20) +
                    (relaxedNodePct   * 0.10)   // relaxed nodes = less churn = good
            ));
        }

        @Override
        public String toString() {
            return String.format(
                    "[HYBRID SNAPSHOT]\n" +
                    "  AVL rotations : %d\n"  +
                    "  RB fixes      : %d\n"  +
                    "  Relaxed nodes : %.1f%%\n" +
                    "  Hot nodes     : %d\n"  +
                    "  Balance qual  : %.3f\n" +
                    "  Avg srch depth: %.2f\n" +
                    "  Inserts/Del   : %d / %d",
                    avlRotations, rbFixes,
                    relaxedNodePct * 100.0, hotNodeCount,
                    balanceQuality, avgSearchDepth,
                    insertCount, deleteCount
            );
        }
    }
}
