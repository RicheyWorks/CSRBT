package core.strategy;

import core.RedBlackTree;
import core.TreeNode1;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;

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
 *   hotNodeFrequency   — access count per data value (identifies hot nodes)
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
public class HybridStrategy implements TreeStrategy {

    private static final Logger logger = LogManager.getLogger(HybridStrategy.class);

    /** Nodes accessed this many times or more are "hot". */
    public static final int HOT_NODE_THRESHOLD = 3;

    private final int depthThreshold;

    // ── Instrumentation counters ──────────────────────────────────────────────
    private final AtomicInteger avlRotationCount = new AtomicInteger(0);
    private final AtomicInteger rbFixCount       = new AtomicInteger(0);
    private final AtomicInteger relaxedNodeCount = new AtomicInteger(0);
    private final AtomicInteger totalNodesSeen   = new AtomicInteger(0);
    private final AtomicInteger insertCount      = new AtomicInteger(0);
    private final AtomicInteger deleteCount      = new AtomicInteger(0);

    /** value → access count; identifies hot nodes */
    private final Map<Integer, Integer> hotNodeFrequency = new HashMap<>();

    public HybridStrategy() {
        this(Integer.MAX_VALUE);
    }

    public HybridStrategy(int depthThreshold) {
        this.depthThreshold = depthThreshold;
    }

    // ── Insert ────────────────────────────────────────────────────────────────

    @Override
    public TreeNode1 insert(RedBlackTree tree, TreeNode1 newNode) {
        TreeNode1 nil = tree.getNIL();
        TreeNode1 y   = nil;
        TreeNode1 x   = tree.getRoot();

        while (!x.isNil()) {
            y = x;
            if (newNode.getData() == x.getData()) {
                logger.warn("Hybrid duplicate insert skipped: {}", newNode.getData());
                recordAccess(newNode.getData());
                return x;
            }
            x = (newNode.getData() < x.getData()) ? x.getLeft() : x.getRight();
        }

        newNode.setColor(TreeNode1.Color.RED);
        newNode.setParent(y);

        if (y.isNil()) {
            tree.setRoot(newNode);
        } else if (newNode.getData() < y.getData()) {
            y.safeSetLeft(newNode);
        } else {
            y.safeSetRight(newNode);
        }

        insertCount.incrementAndGet();
        recordAccess(newNode.getData());
        return newNode;
    }

    /**
     * Phase 1: AVL rebalance (counts every rotation).
     * Phase 2: RB recolor pass (counts every color flip).
     */
    @Override
    public void fixInsert(RedBlackTree tree, TreeNode1 node) {
        avlRebalanceUp(tree, node.getParent());
        rbRecolorPass(tree, tree.getRoot());
        tree.getRoot().setColor(TreeNode1.Color.BLACK);
    }

    // ── Delete ────────────────────────────────────────────────────────────────

    @Override
    public void delete(RedBlackTree tree, TreeNode1 z) {
        TreeNode1 rebalanceFrom;

        if (z.getLeft().isNil()) {
            rebalanceFrom = z.getParent();
            transplant(tree, z, z.getRight());
        } else if (z.getRight().isNil()) {
            rebalanceFrom = z.getParent();
            transplant(tree, z, z.getLeft());
        } else {
            TreeNode1 successor = minimum(z.getRight());
            rebalanceFrom = (successor.getParent() == z) ? successor : successor.getParent();
            if (successor.getParent() != z) {
                transplant(tree, successor, successor.getRight());
                successor.setRight(z.getRight());
                successor.getRight().setParent(successor);
            }
            transplant(tree, z, successor);
            successor.setLeft(z.getLeft());
            successor.getLeft().setParent(successor);
            successor.setColor(z.getColor());
        }

        avlRebalanceUp(tree, rebalanceFrom);
        rbRecolorPass(tree, tree.getRoot());
        tree.getRoot().setColor(TreeNode1.Color.BLACK);
        deleteCount.incrementAndGet();
    }

    // ── Search ────────────────────────────────────────────────────────────────

    @Override
    public TreeNode1 search(RedBlackTree tree, int value) {
        TreeNode1 cur = tree.getRoot();
        while (!cur.isNil()) {
            int cmp = value - cur.getData();
            if (cmp == 0) {
                recordAccess(value);
                return cur;
            }
            cur = (cmp < 0) ? cur.getLeft() : cur.getRight();
        }
        return tree.getNIL();
    }

    // ── AVL rebalance (Phase 1) ───────────────────────────────────────────────

    private void avlRebalanceUp(RedBlackTree tree, TreeNode1 start) {
        TreeNode1 cur = start;
        while (cur != null && !cur.isNil()) {
            totalNodesSeen.incrementAndGet();
            int bf        = balanceFactor(cur);
            int depth     = cur.depth();
            int tolerance = (depth <= depthThreshold) ? 1 : 2;

            if (depth > depthThreshold) relaxedNodeCount.incrementAndGet();

            if (bf > tolerance) {
                if (balanceFactor(cur.getLeft()) < 0) {
                    rotateLeft(tree, cur.getLeft());
                    avlRotationCount.incrementAndGet();
                }
                rotateRight(tree, cur);
                avlRotationCount.incrementAndGet();
                cur = cur.getParent();
            } else if (bf < -tolerance) {
                if (balanceFactor(cur.getRight()) > 0) {
                    rotateRight(tree, cur.getRight());
                    avlRotationCount.incrementAndGet();
                }
                rotateLeft(tree, cur);
                avlRotationCount.incrementAndGet();
                cur = cur.getParent();
            }

            cur = cur.getParent();
        }
    }

    // ── RB recolor pass (Phase 2) ─────────────────────────────────────────────

    private void rbRecolorPass(RedBlackTree tree, TreeNode1 node) {
        if (node == null || node.isNil()) return;

        if (node.isRed()
                && node.getParent() != null
                && !node.getParent().isNil()
                && node.getParent().isRed()) {
            node.getParent().setColor(TreeNode1.Color.BLACK);
            rbFixCount.incrementAndGet();
        }

        rbRecolorPass(tree, node.getLeft());
        rbRecolorPass(tree, node.getRight());
    }

    // ── Metrics API ───────────────────────────────────────────────────────────

    public HybridMetricsSnapshot snapshot(int treeSize, double avgSearchDepth) {
        int totalSeen = totalNodesSeen.get();
        double relaxedPct = (totalSeen == 0) ? 0.0
                : (double) relaxedNodeCount.get() / totalSeen;

        long hotNodeCount = hotNodeFrequency.values().stream()
                .filter(c -> c >= HOT_NODE_THRESHOLD)
                .count();

        // Balance quality: ratio of ideal height to actual — 1.0 is perfect
        double balanceQuality = computeBalanceQuality(treeSize, avgSearchDepth);

        return new HybridMetricsSnapshot(
                avlRotationCount.get(),
                rbFixCount.get(),
                relaxedPct,
                (int) hotNodeCount,
                balanceQuality,
                avgSearchDepth,
                insertCount.get(),
                deleteCount.get()
        );
    }

    public void resetMetrics() {
        avlRotationCount.set(0);
        rbFixCount.set(0);
        relaxedNodeCount.set(0);
        totalNodesSeen.set(0);
        // Keep hotNodeFrequency — it accumulates across windows intentionally
    }

    public void fullReset() {
        resetMetrics();
        hotNodeFrequency.clear();
        insertCount.set(0);
        deleteCount.set(0);
    }

    // ── Accessors for live counters (no snapshot needed) ──────────────────────

    public int getAvlRotationCount() { return avlRotationCount.get(); }
    public int getRbFixCount()       { return rbFixCount.get(); }
    public int getRelaxedNodeCount() { return relaxedNodeCount.get(); }
    public int getTotalNodesSeen()   { return totalNodesSeen.get(); }
    public int getInsertCount()      { return insertCount.get(); }
    public int getDeleteCount()      { return deleteCount.get(); }
    public int getDepthThreshold()   { return depthThreshold; }

    public Set<Map.Entry<Integer, Integer>> getHotNodeEntries() {
        return hotNodeFrequency.entrySet();
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private void recordAccess(int value) {
        hotNodeFrequency.merge(value, 1, Integer::sum);
    }

    private double computeBalanceQuality(int n, double avgDepth) {
        if (n < 2 || avgDepth <= 0) return 1.0;
        double ideal = Math.ceil(Math.log(n + 1) / Math.log(2));
        return Math.min(1.0, ideal / avgDepth);
    }

    private int height(TreeNode1 node) {
        return (node == null || node.isNil()) ? 0 : node.getHeight();
    }

    private int balanceFactor(TreeNode1 node) {
        return height(node.getLeft()) - height(node.getRight());
    }

    private void transplant(RedBlackTree tree, TreeNode1 u, TreeNode1 v) {
        TreeNode1 uParent = u.getParent();
        if (uParent == null || uParent.isNil()) {
            tree.setRoot(v);
        } else if (u == uParent.getLeft()) {
            uParent.setLeft(v);
        } else {
            uParent.setRight(v);
        }
        v.setParent(uParent != null ? uParent : tree.getNIL());
    }

    private TreeNode1 minimum(TreeNode1 node) {
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
            double depth    = Math.min(1.0, 1.0 - (avgSearchDepth / Math.max(1.0, avgSearchDepth * 1.5)));

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
