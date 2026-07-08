package io.github.richeyworks.csrbt;

import io.github.richeyworks.csrbt.interfaces.TreeEngine;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;
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

    /**
     * Total primitive rotations this engine has performed, fed by {@link #onRotation()} (the
     * {@code MutableTree} hook the shared {@code TreeStrategy} rotation bodies fire). Monotonic for
     * the lifetime of <em>this engine instance</em>; a facade that swaps engines (morph, self-repair)
     * observes a reset. Written only on the write path, which the facade already serializes.
     */
    private long rotationCount;

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
        logger.debug("Inserting value={}", value);   // hardening M-3: per-op key values stay below INFO
        TreeNode1<K> newNode = TreeNode1.createNode(value, NIL);
        strategy.insert(this, newNode);   // strategy calls setRoot() internally if needed
        strategy.fixInsert(this, newNode); // fixInsert enforces root BLACK at the end
    }

    /**
     * Replace this tree with a perfectly balanced, black-height-correct red-black tree built
     * directly from an ascending, distinct key list in O(n) — no rotations, no per-insert fixups.
     * The structure is the recursive-median BST; the single deepest level is coloured RED and every
     * other node BLACK (root forced BLACK). Because a median build places all leaves on the bottom
     * one or two levels, colouring exactly the deepest level red keeps every root-to-NIL path's black
     * count equal, so the result satisfies the red-black invariants. Subtree sizes are maintained by
     * the local structural links, so dynamic order statistics are correct immediately.
     *
     * <p>The caller guarantees the list is sorted and distinct under this tree's comparator;
     * {@link OrderedSet#buildFromSorted} validates that before delegating here.</p>
     */
    public void buildBalanced(List<K> ascendingDistinct) {
        int n = ascendingDistinct.size();
        if (n == 0) {
            root = NIL;
            return;
        }
        int maxDepth = 31 - Integer.numberOfLeadingZeros(n); // floor(log2 n) = height of a median build
        root = buildBalancedNode(ascendingDistinct, 0, n - 1, 0, maxDepth);
        root.setParent(NIL);                   // a root has no real parent (matches post-fixInsert state)
        root.setColor(TreeNode1.Color.BLACK);  // RB root invariant (only changes anything for n == 1)
    }

    private TreeNode1<K> buildBalancedNode(List<K> keys, int lo, int hi, int depth, int maxDepth) {
        if (lo > hi) {
            return NIL;
        }
        int mid = (lo + hi) >>> 1;
        TreeNode1<K> node = TreeNode1.createNode(keys.get(mid), NIL);
        TreeNode1<K> left = buildBalancedNode(keys, lo, mid - 1, depth + 1, maxDepth);
        TreeNode1<K> right = buildBalancedNode(keys, mid + 1, hi, depth + 1, maxDepth);
        // Local links recompute this node's size/augment/height in O(1) (no walk to the root),
        // so the whole construction is O(n).
        if (!left.isNil()) {
            node.setLeftLocal(left);
        }
        if (!right.isNil()) {
            node.setRightLocal(right);
        }
        node.setColor(depth == maxDepth ? TreeNode1.Color.RED : TreeNode1.Color.BLACK);
        return node;
    }

    public void remove(K value) {
        logger.debug("Removing value={}", value);   // hardening M-3: per-op key values stay below INFO
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

    /** {@inheritDoc} Counts every primitive rotation — the {@code rotationsPerWrite} source signal. */
    @Override
    public void onRotation() { rotationCount++; }

    /** Total primitive rotations performed by this engine instance (see {@link #onRotation()}). */
    public long rotationCount() { return rotationCount; }

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
