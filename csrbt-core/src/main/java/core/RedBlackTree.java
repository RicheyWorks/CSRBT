package core;

import core.interfaces.TreeEngine;
import core.strategy.TreeStrategy;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Deque;
import java.util.List;

public class RedBlackTree<K> implements TreeEngine<K>, MutableTree<K> {

    private static final Logger logger = LogManager.getLogger(RedBlackTree.class);

    private TreeNode1<K> root;
    private final TreeNode1<K> NIL;      // sentinel alias — never reassigned
    private final TreeStrategy<K> strategy;
    private final Comparator<? super K> keyOrder;   // the tree's ordering authority (also carried by NIL)

    public RedBlackTree(TreeStrategy<K> strategy, Comparator<? super K> keyOrder) {
        this.strategy = strategy;
        this.keyOrder = keyOrder;
        this.NIL      = TreeNode1.createNil(keyOrder);   // per-instance sentinel carries the ordering authority
        this.root     = NIL;
    }

    /**
     * Convenience factory for naturally-ordered keys (the common case, and what
     * the {@code int} {@link TreeContext} facade uses). Adds the
     * {@code Comparable} bound only here, leaving the class itself unbounded so
     * comparator-ordered non-Comparable keys remain supported.
     */
    public static <K extends Comparable<? super K>> RedBlackTree<K> withNaturalOrder(TreeStrategy<K> strategy) {
        return new RedBlackTree<>(strategy, Comparator.naturalOrder());
    }

    // ── Core operations ───────────────────────────────────────────────────────

    public void add(K value) {
        logger.info("Inserting value={}", value);
        TreeNode1<K> newNode = TreeNode1.createNode(value, NIL);
        strategy.insert(this, newNode);   // strategy calls setRoot() internally if needed
        strategy.fixInsert(this, newNode); // fixInsert enforces root BLACK at the end
    }

    public void remove(K value) {
        logger.info("Removing value={}", value);
        TreeNode1<K> node = strategy.search(this, value);
        if (node.isNil()) {
            // A remove of an absent key is a routine no-op, not a fault. At WARN this
            // line flooded ~43k entries per E1 viability sweep (2026-06-10 audit).
            logger.debug("Remove no-op — value={} not found", value);
            return;
        }
        strategy.delete(this, node);
    }

    public boolean contains(K value) {
        logger.debug("Search value={}", value);
        return !strategy.search(this, value).isNil();
    }

    // ── Structural operations (strategies call back through here) ─────────────
    // Keeping rotation on the tree lets the tree own its own structure,
    // while the strategy decides *when* to rotate.

    public void rotateLeft(TreeNode1<K> x)  { strategy.rotateLeft(this, x); }
    public void rotateRight(TreeNode1<K> y) { strategy.rotateRight(this, y); }

    // ── TreeEngine: representation-neutral views ──────────────────────────────
    // These expose behaviour only (ordered keys / size / clear) so callers can
    // treat any backing structure uniformly via the TreeEngine interface.

    /** {@inheritDoc} Keys in ascending order via iterative in-order walk. */
    @Override
    public List<K> inOrder() {
        List<K> out = new ArrayList<>();
        Deque<TreeNode1<K>> stack = new ArrayDeque<>();
        TreeNode1<K> cur = root;
        while (!stack.isEmpty() || !cur.isNil()) {
            while (!cur.isNil()) {
                stack.push(cur);
                cur = cur.getLeft();
            }
            cur = stack.pop();
            out.add(cur.getData());
            cur = cur.getRight();
        }
        return out;
    }

    /**
     * {@inheritDoc}
     *
     * <p>O(1) via the size augment (ADR-009 P1): every structural change already maintains
     * {@code TreeNode1.size} — it is the same intrinsic metadata the order-statistics walks
     * ({@code select}/{@code rank}) have trusted since they existed, and the NIL sentinel
     * carries size 0, so the empty tree falls out for free. The previous implementation
     * walked all n nodes with an explicit stack to count what the root already knew.</p>
     */
    @Override
    public int size() {
        return root.getSize();
    }

    /** {@inheritDoc} Detaches the whole tree by resetting the root to NIL. */
    @Override
    public void clear() {
        this.root = NIL;
    }

    // ── Accessors ─────────────────────────────────────────────────────────────

    public TreeNode1<K> getRoot()              { return root; }
    public void      setRoot(TreeNode1<K> r)   { this.root = r; }
    public TreeNode1<K> getNIL()               { return NIL; }    // strategies need this
    public TreeStrategy<K> getStrategy()       { return strategy; }

    /**
     * The tree's key-ordering authority. Exposed so collaborators that must
     * compare two <em>query</em> keys directly (not a node against a key) — e.g.
     * {@code OrderStatisticsOps.countInRange}'s {@code lo <= hi} guard — can do so
     * through the same order as everything else. Node-vs-key comparisons should
     * still go through {@link TreeNode1#compareKeyTo}.
     */
    public Comparator<? super K> comparator() { return keyOrder; }
}
