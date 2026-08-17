package io.github.richeyworks.csrbt.strategy;

import io.github.richeyworks.csrbt.MutableTree;
import io.github.richeyworks.csrbt.TreeNode1;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;

/**
 * Weight-balanced (BB[α]) strategy — the first <em>parameterized</em> member of the
 * strategy family (ADR-011 V1), and the genome dimension the evolution machine searches.
 *
 * <p>The balance condition is ADR-005's size-based formulation, ported from the persistent
 * engine (where Δ=3, Γ=2 has run verified since it landed) to the mutable
 * {@code MutableTree}/{@code TreeNode1} seam: at every node with subtree sizes
 * {@code (sl, sr)}, if {@code sl + sr > 1} then neither side may exceed {@code Δ×} the
 * other. Repair is the standard single/double rotation, chosen by Γ: a heavy right child
 * is fixed by a single left rotation when its inner grandchild is light
 * ({@code size(r.left) < Γ × size(r.right)}), else by a double. The per-node subtree
 * {@code size} this reads is intrinsic metadata that {@code TreeNode1}'s structural
 * setters and the O(1) local rotation variants already maintain — the strategy adds no
 * bookkeeping of its own.</p>
 *
 * <p><b>Parameters.</b> {@code (Δ, Γ)} are constructor arguments. {@code (3, 2)} — the
 * default — is the literature-verified point (Haskell {@code containers}' post-2010
 * formulation, adopted verbatim by ADR-005). Other integer points inside the structural
 * bounds ({@code Δ ≥ 2}, {@code 1 ≤ Γ < Δ}) are <em>candidate arms</em> for the search,
 * not promises: soundness at a given point means the one-rotation-per-level repair
 * actually restores the invariant, and that is exactly what {@link #validateInvariant}
 * (run inside the health gate and the grid tests) checks empirically. An unsound point
 * fails its own invariant and is discarded — the evolution machine's viability constraint
 * working as designed.</p>
 *
 * <p>Like AVL, color is irrelevant: nodes are set BLACK so shared diagnostics stay quiet.
 * Worst-case height is O(log n) for any input at sound parameters; larger Δ tolerates
 * more skew (fewer rotations per write), smaller Δ keeps searches shorter.</p>
 */
public class WeightBalancedStrategy<K> implements TreeStrategy<K> {

    /** The literature-verified default (containers / ADR-005). */
    public static final int DEFAULT_DELTA = 3;
    public static final int DEFAULT_RATIO = 2;

    private final int delta;
    private final int ratio;

    public WeightBalancedStrategy() {
        this(DEFAULT_DELTA, DEFAULT_RATIO);
    }

    /**
     * @param delta balance tolerance Δ (≥ 2): neither subtree may exceed Δ× its sibling
     * @param ratio rotation chooser Γ (1 ≤ Γ &lt; Δ): single vs double rotation threshold
     */
    public WeightBalancedStrategy(int delta, int ratio) {
        if (delta < 2) throw new IllegalArgumentException("delta must be >= 2: " + delta);
        if (ratio < 1 || ratio >= delta) {
            throw new IllegalArgumentException("ratio must be in [1, delta): " + ratio);
        }
        this.delta = delta;
        this.ratio = ratio;
    }

    public int delta() { return delta; }
    public int ratio() { return ratio; }

    // ── Insert ────────────────────────────────────────────────────────────────

    /** Standard BST link (sizes propagate via the structural setters); fixInsert rebalances. */
    @Override
    public void insert(MutableTree<K> tree, TreeNode1<K> node) {
        TreeNode1<K> nil    = tree.getNIL();
        TreeNode1<K> parent = nil;
        TreeNode1<K> cur    = tree.getRoot();

        while (!cur.isNil()) {
            parent = cur;
            int cmp = node.compareTo(cur);
            if      (cmp < 0) cur = cur.getLeft();
            else if (cmp > 0) cur = cur.getRight();
            else return;                                   // duplicate — ignore
        }

        node.setColor(TreeNode1.Color.BLACK);              // weight balance doesn't use color
        node.setParent(parent);

        if (parent.isNil()) {
            tree.setRoot(node);
        } else if (node.compareTo(parent) < 0) {
            parent.setLeft(node);
        } else {
            parent.setRight(node);
        }
    }

    @Override
    public void fixInsert(MutableTree<K> tree, TreeNode1<K> node) {
        rebalanceUp(tree, node.getParent());
    }

    // ── Delete (CLRS transplant shape, identical to AVLStrategy's) ───────────────

    @Override
    public void delete(MutableTree<K> tree, TreeNode1<K> node) {
        TreeNode1<K> rebalanceFrom;

        if (node.getLeft().isNil()) {
            rebalanceFrom = node.getParent();
            transplant(tree, node, node.getRight());

        } else if (node.getRight().isNil()) {
            rebalanceFrom = node.getParent();
            transplant(tree, node, node.getLeft());

        } else {
            TreeNode1<K> successor = minimum(node.getRight());
            rebalanceFrom = (successor.getParent() == node) ? successor
                                                            : successor.getParent();
            if (successor.getParent() != node) {
                transplant(tree, successor, successor.getRight());
                // Local link: successor's stale parent pointer would make a propagating
                // setRight walk a cyclic chain (see AVLStrategy for the full note).
                successor.setRightLocal(node.getRight());
                successor.getRight().setParent(successor);
            }
            transplant(tree, node, successor);
            successor.setLeft(node.getLeft());
            successor.getLeft().setParent(successor);
            successor.setColor(TreeNode1.Color.BLACK);
        }

        rebalanceUp(tree, rebalanceFrom);
    }

    // ── Search ────────────────────────────────────────────────────────────────

    @Override
    public TreeNode1<K> search(MutableTree<K> tree, K value) {
        TreeNode1<K> cur = tree.getRoot();
        while (!cur.isNil()) {
            int cmp = cur.compareKeyTo(value);
            if      (cmp == 0) return cur;
            else if (cmp >  0) cur = cur.getLeft();
            else               cur = cur.getRight();
        }
        return tree.getNIL();
    }

    // ── Core weight-balanced repair ───────────────────────────────────────────

    /**
     * Walk from {@code start} to the root, applying the (Δ, Γ) repair at every level —
     * the mutable mirror of ADR-005's {@code balance()} applied per rebuilt level.
     * Subtree sizes are already correct along the path (the propagating setters updated
     * them before this walk; rotations keep them correct as we go).
     *
     * <p>This walk steers by SIZE, not height, so — unlike AVL's and Hybrid's — it never
     * refreshes a height and owes every ancestor of every rotation it fires the ADR-023
     * height climb. Hence the height-carrying {@code rotateLeft}/{@code rotateRight} here
     * rather than the {@code *Local} primitives.</p>
     */
    private void rebalanceUp(MutableTree<K> tree, TreeNode1<K> start) {
        TreeNode1<K> cur = start;
        while (cur != null && !cur.isNil()) {
            int sl = size(cur.getLeft());
            int sr = size(cur.getRight());

            if (sl + sr > 1) {                             // both sides tiny: always balanced
                if (sr > delta * sl) {                     // right too heavy
                    TreeNode1<K> r = cur.getRight();
                    if (size(r.getLeft()) >= ratio * size(r.getRight())) {
                        rotateRight(tree, r);              // inner grandchild heavy: double
                    }
                    rotateLeft(tree, cur);
                    cur = cur.getParent();                 // cur slid down; new subtree root

                } else if (sl > delta * sr) {              // left too heavy (mirror)
                    TreeNode1<K> l = cur.getLeft();
                    if (size(l.getRight()) >= ratio * size(l.getLeft())) {
                        rotateLeft(tree, l);
                    }
                    rotateRight(tree, cur);
                    cur = cur.getParent();
                }
            }
            cur = cur.getParent();
        }
    }

    // ── Strategy-supplied invariant (the health gate's hook, ADR-011 V1) ─────────

    /**
     * Mechanical Δ-balance check against <em>this strategy's own parameters</em> — what
     * lets the health gate validate a parameterized candidate exactly, and what makes an
     * unsound (Δ, Γ) arm self-disqualifying. Iterative (a violating tree may be deep).
     */
    @Override
    public List<String> validateInvariant(MutableTree<K> tree) {
        List<String> failures = new ArrayList<>();
        TreeNode1<K> root = tree.getRoot();
        if (root == null || root.isNil()) return failures;

        Deque<TreeNode1<K>> stack = new ArrayDeque<>();
        stack.push(root);
        while (!stack.isEmpty() && failures.size() < 8) {
            TreeNode1<K> n = stack.pop();
            int sl = size(n.getLeft());
            int sr = size(n.getRight());
            if (sl + sr > 1 && (sl > delta * sr || sr > delta * sl)) {
                failures.add("weight balance: node " + n.getData() + " child sizes "
                        + sl + "/" + sr + " exceed Δ=" + delta);
            }
            if (!n.getLeft().isNil())  stack.push(n.getLeft());
            if (!n.getRight().isNil()) stack.push(n.getRight());
        }
        return failures;
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private int size(TreeNode1<K> n) {
        return (n == null || n.isNil()) ? 0 : n.getSize();
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
        if (v != null && !v.isNil()) {
            v.setParent(uParent);
        }
    }

    private TreeNode1<K> minimum(TreeNode1<K> node) {
        while (!node.getLeft().isNil()) node = node.getLeft();
        return node;
    }

    /** Policy identity includes the parameters: WB(3,2) and WB(4,2) are different policies. */
    @Override
    public boolean samePolicyAs(TreeStrategy<K> other) {
        return other instanceof WeightBalancedStrategy<K> w
                && w.delta == delta && w.ratio == ratio;
    }

    @Override
    public String toString() {
        return "WeightBalancedStrategy(Δ=" + delta + ", Γ=" + ratio + ")";
    }
}
