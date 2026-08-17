package io.github.richeyworks.csrbt.strategy;

import io.github.richeyworks.csrbt.MutableTree;
import io.github.richeyworks.csrbt.TreeNode1;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.WeakHashMap;

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

    /** |balance factor| allowed at or above {@code depthThreshold} — plain AVL. */
    private static final int STRICT_TOLERANCE  = 1;
    /** |balance factor| allowed below {@code depthThreshold} — the documented ±2 relaxation. */
    private static final int RELAXED_TOLERANCE = 2;

    private final int depthThreshold;

    /**
     * Whether any depth can exceed {@link #depthThreshold} — false for the default unbounded
     * threshold, which is plain AVL and never relaxes anything. Lets the post-rotation grant
     * skip its {@code depth()} walk entirely in that (production-default) configuration.
     */
    private final boolean relaxesByDepth;

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

    /**
     * The nodes the balance pass last judged BELOW {@link #depthThreshold} — i.e. the ones
     * it actually granted the ±2 relaxation to (audit 2026-08-17, finding 15).
     *
     * <p>The relaxation is decided from {@code depth()} at WRITE time, but depths shift as
     * the tree grows and rotates, so re-deriving it from {@code depth()} at VALIDATION time
     * judged a legitimately relaxed node against strict tolerance: Hybrid reported
     * violations on trees it had built itself, {@code setStrategy(new HybridStrategy<>(7))}
     * was silently refused by the health gate, and {@code selfRepair()} failed its
     * short-circuit and paid a futile O(n) rebuild. Recording the grant makes the decision
     * recoverable, so {@link #validateInvariant} checks what the write path actually
     * permitted instead of re-guessing it from a depth that has since moved.</p>
     *
     * <p>A grant is not a permanent licence. Every write re-judges each node from the write
     * point up to the root, so a relaxed node that drifts up into the strict region loses
     * its grant the next time a write walks through it — and is rotated back to |bf| ≤ 1 on
     * that same visit, because it is then judged at tolerance 1. The invariant this leaves
     * is exact and still falsifiable: an unrecorded node must hold strict AVL balance, a
     * recorded one may hold |bf| = 2, and nothing may exceed 2.</p>
     *
     * <p>Weak, identity-keyed ({@link TreeNode1} hashes by identity), so deleted nodes drop
     * out on their own and this never retains a tree. It stays empty — and costs one
     * {@code isEmpty()} test per visited node — for the default unbounded threshold, which
     * relaxes nothing. Known limitation: the grants belong to the strategy INSTANCE, so a
     * clone built by {@code TreeCloner.freshStrategyLike} starts with none and a
     * finite-threshold clone may be judged strictly once, costing one rebuild that then
     * re-records the grants correctly.</p>
     */
    private final Set<TreeNode1<K>> relaxedNodes =
            Collections.newSetFromMap(new WeakHashMap<>());

    public HybridStrategy() {
        this(Integer.MAX_VALUE);
    }

    public HybridStrategy(int depthThreshold) {
        this.depthThreshold = depthThreshold;
        this.relaxesByDepth = depthThreshold != Integer.MAX_VALUE;
    }

    // ── Insert ────────────────────────────────────────────────────────────────

    @Override
    public void insert(MutableTree<K> tree, TreeNode1<K> newNode) {
        TreeNode1<K> nil = tree.getNIL();
        TreeNode1<K> y   = nil;
        TreeNode1<K> x   = tree.getRoot();

        int cmp = 0;                       // one comparison per step; the last one aims the link
        while (!x.isNil()) {
            y = x;
            cmp = newNode.compareTo(x);
            if (cmp == 0) {
                // DEBUG, not WARN — hot-path + battle-timing fairness (see RedBlackStrategy).
                logger.debug("Hybrid duplicate insert skipped: {}", newNode.getData());
                recordAccess(newNode.getData());
                return;                    // abort UNLINKED — addIfAbsent reads this back
            }
            x = (cmp < 0) ? x.getLeft() : x.getRight();
        }

        newNode.setColor(TreeNode1.Color.RED);
        newNode.setParent(y);

        if (y.isNil()) {
            tree.setRoot(newNode);
        } else if (cmp < 0) {
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
            boolean relax = depth > depthThreshold;
            int tolerance = relax ? RELAXED_TOLERANCE : STRICT_TOLERANCE;

            // Record (or revoke) the relaxation grant as it is made, so validateInvariant
            // can ask what this pass permitted rather than re-deriving it from a depth that
            // will have moved by then — see relaxedNodes.
            if (relax) {
                relaxedNodeCount++;
                relaxedNodes.add(cur);
            } else if (!relaxedNodes.isEmpty()) {
                relaxedNodes.remove(cur);
            }

            if (bf > tolerance) {
                if (balanceFactor(cur.getLeft()) < 0) {
                    rotateLeft(tree, cur.getLeft());
                    avlRotationCount++;
                }
                rotateRight(tree, cur);
                avlRotationCount++;
                cur = cur.getParent();
                grantOverRotatedTriangle(cur);
            } else if (bf < -tolerance) {
                if (balanceFactor(cur.getRight()) > 0) {
                    rotateRight(tree, cur.getRight());
                    avlRotationCount++;
                }
                rotateLeft(tree, cur);
                avlRotationCount++;
                cur = cur.getParent();
                grantOverRotatedTriangle(cur);
            }

            cur = cur.getParent();
        }
    }

    /**
     * Record the relaxation grant over the triangle a rotation just rewired — the new
     * subtree root and the two nodes now hanging under it. The pass resumes above the
     * triangle and never judges these three again on this walk, so the grant has to be
     * taken here or it is lost.
     *
     * <p>Two things are granted, and both are things the write path genuinely does:</p>
     * <ol>
     *   <li><b>the depth rule, at the depth the node now holds.</b> A rotation fired at a
     *       relaxed node moves its triangle around inside the relaxed region; each of the
     *       three is at or below the firing node's depth, so the rule grants all three.</li>
     *   <li><b>the residue a rotation cannot remove.</b> AVL's rotation lemma ("rotating a
     *       node with |bf| = 2 leaves both nodes within ±1") assumes the CHILD it rotates
     *       about is itself strictly balanced. Under a relaxation that assumption does not
     *       hold at the boundary: a strict node whose relaxed grandchild carries |bf| = 2
     *       comes out of its own rebalancing rotation at |bf| = 2. Removing that would mean
     *       strictly rebalancing the relaxed subtree below first — cascading exactly the
     *       rotations the relaxation exists to avoid — so the write path leaves it, and this
     *       records that it did.</li>
     * </ol>
     *
     * <p>The residue is bounded: with every input at |bf| &le; 2 (the tolerance ceiling),
     * both the single and the double rotation leave every rewired node at |bf| &le; 2, so
     * no grant can ever excuse |bf| &ge; 3 — {@link #validateInvariant} still reports that
     * as a violation wherever it appears. The grant is also temporary: the next pass that
     * walks through the node judges it at its current depth, revokes the grant if that depth
     * is strict, and rotates it back to |bf| &le; 1 on the same visit.</p>
     *
     * <p>Nothing here is reachable under the default unbounded threshold: with tolerance 1
     * everywhere no node is ever relaxed, so no rotation has a relaxed input and there is no
     * residue to record — plain AVL balance, validated strictly.</p>
     */
    private void grantOverRotatedTriangle(TreeNode1<K> subtreeRoot) {
        if (subtreeRoot == null || subtreeRoot.isNil()) return;
        grantAfterRotation(subtreeRoot);
        grantAfterRotation(subtreeRoot.getLeft());
        grantAfterRotation(subtreeRoot.getRight());
    }

    private void grantAfterRotation(TreeNode1<K> node) {
        if (node == null || node.isNil()) return;
        // Balance factor first: it is O(1), while depth() walks to the root — and an
        // unbounded threshold can never grant on depth, so it does not walk at all.
        if (Math.abs(balanceFactor(node)) > STRICT_TOLERANCE
                || (relaxesByDepth && node.depth() > depthThreshold)) {
            relaxedNodes.add(node);
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
        // Keep hotNodeFrequency — it accumulates across windows intentionally.
        // Keep relaxedNodes too: it is not a metric but the record of which nodes the
        // write path licensed to hold |bf| = 2, and dropping it would make
        // validateInvariant fail a tree this strategy legitimately built.
    }

    public void fullReset() {
        resetMetrics();
        hotNodeFrequency.clear();
        insertCount = 0;
        deleteCount = 0;
    }

    // ── Policy identity + invariant (bug audit 2026-08-12, C-2 / H-2) ─────────

    /**
     * Hybrid is parameterized by {@code depthThreshold}, so policy identity must
     * compare it — exactly the trap {@link TreeStrategy#samePolicyAs}'s javadoc
     * names (class identity alone made {@code Hybrid(4) → Hybrid(64)} a silent
     * no-op and refused a real re-parameterizing morph).
     */
    @Override
    public boolean samePolicyAs(TreeStrategy<K> other) {
        return other instanceof HybridStrategy<?> h && h.depthThreshold == depthThreshold;
    }

    /**
     * Hybrid's own structural invariant: strict AVL balance (|balance factor| &le; 1)
     * everywhere the balance pass judged the node at or above {@code depthThreshold},
     * and |bf| &le; 2 exactly where it granted the documented depth relaxation. The
     * generic health gate used to demand strict AVL balance from every Hybrid, so a
     * finite-threshold Hybrid with legitimate |bf| = 2 nodes was permanently "unhealthy"
     * (every selfRepair paid a futile O(n) rebuild and reported FAILURE).
     *
     * <p>The grant is read from {@link #relaxedNodes} rather than re-derived from
     * {@code depth()} (audit 2026-08-17, finding 15): the write path decides at the depth
     * a node had when it was last balanced, and re-deriving it from the depth the node has
     * NOW failed nodes that had since drifted upward through rotations — Hybrid reporting
     * violations on trees it built itself. Heights are recomputed here, not read from the
     * cache.</p>
     */
    @Override
    public java.util.List<String> validateInvariant(MutableTree<K> tree) {
        java.util.List<String> failures = new java.util.ArrayList<>();
        TreeNode1<K> root = tree.getRoot();
        if (root == null || root.isNil()) return failures;
        checkBalance(root, failures);
        return failures;
    }

    /** Post-order: returns actual height; appends a failure per out-of-tolerance node. */
    private int checkBalance(TreeNode1<K> n, java.util.List<String> failures) {
        if (n.isNil()) return 0;
        int lh = checkBalance(n.getLeft(), failures);
        int rh = checkBalance(n.getRight(), failures);
        int bf = lh - rh;
        int tolerance = relaxedNodes.contains(n) ? RELAXED_TOLERANCE : STRICT_TOLERANCE;
        if (Math.abs(bf) > tolerance && failures.size() < 8) {
            failures.add("hybrid balance: node " + n.getData() + " |bf|=" + Math.abs(bf)
                    + " exceeds tolerance " + tolerance + " at depth " + n.depth()
                    + (tolerance == RELAXED_TOLERANCE ? " (depth-relaxed)" : ""));
        }
        return Math.max(lh, rh) + 1;
    }

    /**
     * Whether the balance pass last judged {@code node} below {@code depthThreshold} and so
     * granted it the ±2 relaxation. Diagnostics seam for tests asserting that the relaxation
     * validateInvariant honours is one this strategy actually issued.
     */
    public boolean isDepthRelaxed(TreeNode1<K> node) {
        return relaxedNodes.contains(node);
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
