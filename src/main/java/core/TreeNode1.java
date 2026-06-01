package core;

import java.util.Random;

public class TreeNode1 implements Comparable<TreeNode1>, Cloneable {
    public enum Color { RED, BLACK }
    enum Rotation { NONE, LEFT, RIGHT }

    @FunctionalInterface
    public interface Augmentor {
        void apply(TreeNode1 node);
    }

    public static final Augmentor defaultAugmentor = node -> {
        int leftSize = (node.left != null && !node.left.isNil()) ? node.left.augmentedValue : 0;
        int rightSize = (node.right != null && !node.right.isNil()) ? node.right.augmentedValue : 0;
        node.augmentedValue = 1 + leftSize + rightSize;
    };

    /**
     * Shared bootstrap sentinel. Retained for standalone node construction and
     * tests. Engines should NOT use this directly — each {@link core.RedBlackTree}
     * owns a per-instance sentinel via {@link #createNil()} so trees never share
     * mutable sentinel state. Never mix nodes built against a per-tree sentinel
     * with nodes built against this one (identity-based {@link #isNil()} relies
     * on every node in a tree sharing the same sentinel).
     */
    public static final TreeNode1 NIL = new TreeNode1(0, Color.BLACK);

    private final int data;
    private TreeNode1 left;
    private TreeNode1 right;
    private TreeNode1 parent;
    private Color color;
    private final TreeNode1 nilSentinel;
    private Rotation lastRotation = Rotation.NONE;
    private int augmentedValue = 0;   // pluggable augmentor payload (e.g. interval max-hi) — NOT subtree size; see `size` (ADR-002)
    private int blackHeight = 1;
    private int height = 1;
    /**
     * Intrinsic subtree node count (this node + both subtrees), maintained on
     * every structural link exactly like {@link #height} and {@link #blackHeight}
     * and independent of the pluggable {@link #augmentor}. This is the source of
     * truth for dynamic order statistics (CLRS 14.1).
     *
     * Giving subtree size its own field — rather than borrowing
     * {@code augmentedValue} — is what lets order statistics coexist with a custom
     * augmentor (e.g. {@code IntervalAugmentor}'s max-hi) on a single tree, instead
     * of the two fighting over one overloaded slot. See ADR-002.
     */
    private int size = 1;
    private String tag = "";
    private boolean pathCompressed = false;
    private Augmentor augmentor;

    public TreeNode1(int data, TreeNode1 nil) {
        this(data, nil, Color.RED, defaultAugmentor);
    }

    public TreeNode1(int data, TreeNode1 nil, Augmentor augmentor) {
        this(data, nil, Color.RED, augmentor);
    }

    private TreeNode1(int data, TreeNode1 nil, Color color, Augmentor augmentor) {
        if (nil == null) throw new IllegalArgumentException("nilSentinel cannot be null");
        this.data = data;
        this.nilSentinel = nil;
        this.left = this.right = nil;
        this.parent = null;
        this.color = color;
        this.augmentor = augmentor != null ? augmentor : defaultAugmentor; // Null-safe
        this.augmentor.apply(this);
    }

    private TreeNode1(int data, Color color) {
        this.data = data;
        this.nilSentinel = this;
        this.left = this.right = this;
        this.parent = null;
        this.color = color;
        this.augmentedValue = 0;
        this.size = 0;            // the sentinel is empty: a NIL subtree has 0 nodes
        this.blackHeight = 1;
        this.height = 0;
        this.augmentor = defaultAugmentor;
        this.augmentor.apply(this);
    }

    public static TreeNode1 createNode(int data, TreeNode1 nil) {
        return new TreeNode1(data, nil);
    }

    public static TreeNode1 createNodeWithAugment(int data, TreeNode1 nil, int augment) {
        TreeNode1 node = new TreeNode1(data, nil);
        node.augmentedValue = augment;
        return node;
    }

    /**
     * Create a FRESH, independent NIL sentinel. Each engine instance should own
     * its own sentinel (previously this returned the shared static {@link #NIL},
     * which let unrelated trees alias one mutable sentinel).
     */
    public static TreeNode1 createNil() {
        return new TreeNode1(0, Color.BLACK);
    }

    public static boolean isSharedNil(TreeNode1 node, TreeNode1 nil) {
        return node == nil;
    }

    public int getData() {
        return data;
    }

    public TreeNode1 getLeft() {
        return left;
    }

    public TreeNode1 getRight() {
        return right;
    }

    public TreeNode1 getParent() {
        return parent;
    }

    public TreeNode1 getGrandparent() {
        return (parent != null) ? parent.parent : nilSentinel;
    }

    public TreeNode1 getUncle() {
        TreeNode1 gp = getGrandparent();
        if (gp == nilSentinel) return nilSentinel;
        return (parent == gp.left) ? gp.right : gp.left;
    }

    public TreeNode1 getSibling() {
        if (parent == null) return nilSentinel;
        return (this == parent.left) ? parent.right : parent.left;
    }

    public boolean isRed() {
        return color == Color.RED;
    }

    public boolean isBlack() {
        return color == Color.BLACK;
    }

    public boolean isNil() {
        return this == nilSentinel;
    }

    public boolean isLeaf() {
        return left.isNil() && right.isNil();
    }

    public int blackHeight() {
        if (isNil()) return 1;
        int leftBH = left.blackHeight();
        int rightBH = right.blackHeight();
        // Explicit check (not `assert`, which is disabled by default at runtime)
        // so this genuinely validates the invariant whenever it is called.
        if (leftBH != rightBH) {
            throw new IllegalStateException("Black-height violation at node " + data
                    + " (left=" + leftBH + ", right=" + rightBH + ")");
        }
        return (isBlack() ? 1 : 0) + leftBH;
    }

    public int getBlackHeight() {
        return blackHeight;
    }

    private void updateBlackHeight() {
        if (isNil()) {
            blackHeight = 1;
            return;
        }
        // Informational bookkeeping only. This is called from setLeft/setRight for
        // EVERY strategy, but only Red-Black trees maintain equal subtree
        // black-heights — AVL/Splay/Hybrid colour all nodes black and legitimately
        // have unequal black-heights. So we record a value without enforcing the
        // RB invariant here; RB validity is checked separately by TreeDiagnostics.
        int leftBH  = left.getBlackHeight();
        int rightBH = right.getBlackHeight();
        blackHeight = (isBlack() ? 1 : 0) + Math.max(leftBH, rightBH);
    }

    public int getHeight() {
        return height;
    }

    /**
     * Recompute this node's cached height from its children's cached heights.
     * Local and non-throwing — intended to be called while walking UP a path
     * (bottom-up) so that each ancestor's height is current before a parent's
     * balance factor is read. Unlike {@link #setLeft}/{@link #setRight}, this
     * does not propagate or re-augment; callers control the traversal.
     */
    public void refreshHeight() {
        if (isNil()) { height = 0; return; }
        int leftHeight  = (left  == null) ? 0 : left.getHeight();
        int rightHeight = (right == null) ? 0 : right.getHeight();
        height = 1 + Math.max(leftHeight, rightHeight);
    }

    private void updateHeight() {
        if (isNil()) {
            height = 0;
            return;
        }
        int leftHeight = left.getHeight();
        int rightHeight = right.getHeight();
        height = 1 + Math.max(leftHeight, rightHeight);
    }

    public int depth() {
        int depth = 0;
        TreeNode1 current = this;
        // "No parent" is either null (freshly created) or the sentinel (a root
        // under the unified convention); stop at both so a root has depth 0.
        while (current.getParent() != null && !current.getParent().isNil()) {
            depth++;
            current = current.getParent();
        }
        return depth;
    }

    public int compareTo(TreeNode1 other) {
        return Integer.compare(this.data, other.data);
    }

    /**
     * Identity equality. Nodes are mutable (color, children, augment change on
     * rotation/insert), so a structural {@code equals}/{@code hashCode} would be
     * O(n), would mutate its hash over a node's lifetime — violating the hash
     * contract — and would conflate distinct-but-similar nodes. Collections that
     * track nodes (e.g. ancestor sets for LCA, clone memos) want identity, so
     * that is what we provide. Use {@code inOrder()} / a structural comparator
     * when value-based tree comparison is actually needed.
     */
    @Override
    public boolean equals(Object obj) {
        return this == obj;
    }

    @Override
    public int hashCode() {
        return System.identityHashCode(this);
    }

    @Override
    public TreeNode1 clone() throws CloneNotSupportedException {
        return deepCopy(nilSentinel);
    }

    public Color getColor() {
        return color;
    }

    public void setColor(Color color) {
        this.color = color;
        updateBlackHeight();
    }

    public void flipColor() {
        if (color == Color.RED) color = Color.BLACK;
        else color = Color.RED;
        updateBlackHeight();
    }

    public void setParent(TreeNode1 p) {
        if (this != nilSentinel) { // Prevent NIL from getting a parent
            this.parent = p;
        }
    }

    public void setLeft(TreeNode1 child) {
        left = child;
        if (child != null && !child.isNil()) {
            child.parent = this;
        }
        recomputeAugmentAndPropagate();
        updateBlackHeight();
        updateHeight();
    }

    public void setRight(TreeNode1 child) {
        right = child;
        if (child != null && !child.isNil()) {
            child.parent = this;
        }
        recomputeAugmentAndPropagate();
        updateBlackHeight();
        updateHeight();
    }

    /**
     * Link {@code child} as the left child and recompute THIS node's augment,
     * black-height and height locally — without walking the augment up to the
     * root. Intended for rotations, which rearrange a local pair but never
     * change any ancestor's subtree size, so the O(height) propagation that
     * {@link #setLeft} performs is pure waste there (it made each rotation
     * O(height) and inserts O(height²)). Insert/delete BST links must still use
     * the propagating {@link #setLeft}/{@link #setRight}.
     */
    public void setLeftLocal(TreeNode1 child) {
        left = child;
        if (child != null && !child.isNil()) {
            child.parent = this;
        }
        recomputeAugment();
        updateBlackHeight();
        updateHeight();
    }

    /** Right-side counterpart of {@link #setLeftLocal}. */
    public void setRightLocal(TreeNode1 child) {
        right = child;
        if (child != null && !child.isNil()) {
            child.parent = this;
        }
        recomputeAugment();
        updateBlackHeight();
        updateHeight();
    }

    public void safeSetLeft(TreeNode1 child) {
        setLeft(child != null ? child : nilSentinel);
    }

    public void safeSetRight(TreeNode1 child) {
        setRight(child != null ? child : nilSentinel);
    }

    public void clear() {
        left = right = parent = nilSentinel;
        color = Color.RED;
        augmentedValue = 1;
        size = 1;                 // a cleared node is a standalone leaf: one node
        lastRotation = Rotation.NONE;
        blackHeight = 1;
        height = 1;
    }

    public boolean isLessThan(TreeNode1 other) {
        return this.data < other.data;
    }

    public boolean wasRotatedLeft() {
        return lastRotation == Rotation.LEFT;
    }

    public boolean wasRotatedRight() {
        return lastRotation == Rotation.RIGHT;
    }

    public Rotation getLastRotation() {
        return lastRotation;
    }

    public void setLastRotation(Rotation r) {
        this.lastRotation = r;
    }

    public boolean isPathCompressed() {
        return pathCompressed;
    }

    public void setPathCompressed(boolean pathCompressed) {
        this.pathCompressed = pathCompressed;
    }

    /**
     * Intrinsic subtree size (node count). Always maintained on structural links,
     * independent of the active {@link Augmentor}. This is what dynamic order
     * statistics reads — see {@link core.util.OrderStatisticsOps}. NIL reports 0.
     */
    public int getSize() {
        return isNil() ? 0 : size;
    }

    public int getAugmentedValue() {
        return augmentedValue;
    }

    public void setAugmentedValue(int value) {
        this.augmentedValue = value;
    }

    /**
     * Recompute this node's intrinsic subtree size from its children's sizes.
     * Always run (independent of the pluggable augmentor) so order statistics stay
     * correct no matter which augmentor is installed. NIL has size 0. Like the
     * augment recompute this is O(1) and rides the same bottom-up traversal, so
     * insert/delete/rotation stay O(log n).
     */
    private void recomputeSize() {
        if (isNil()) { size = 0; return; }
        int leftSize  = (left  == null || left.isNil())  ? 0 : left.size;
        int rightSize = (right == null || right.isNil()) ? 0 : right.size;
        size = 1 + leftSize + rightSize;
    }

    protected void recomputeAugment() {
        recomputeSize();                 // intrinsic structural metadata, always maintained
        if (this.augmentor != null) {
            this.augmentor.apply(this);
        }
    }

    /**
     * Recompute this node's augment and propagate it to the root. Public hook for
     * callers that mutate augment-relevant state outside the structural setters —
     * e.g. {@code setTag}-based interval high endpoints, which the augmentor reads
     * but {@link #setTag} does not itself trigger. Requires every node on the path
     * to root to carry the same augmentor for the propagated values to be correct.
     */
    public void reaugment() {
        recomputeAugmentAndPropagate();
    }

    private void recomputeAugmentAndPropagate() {
        recomputeAugment();
        TreeNode1 current = this;
        while (current.parent != null) {
            current = current.parent;
            current.recomputeAugment();
        }
    }

    public void setAugmentor(Augmentor augmentor) {
        this.augmentor = augmentor != null ? augmentor : defaultAugmentor;
        recomputeAugmentAndPropagate();
    }

    public String getTag() {
        return tag;
    }

    public void setTag(String tag) {
        this.tag = tag;
    }

    public TreeNode1 deepCopy(TreeNode1 nil) {
        if (this.isNil()) return nil;
        TreeNode1 copy = new TreeNode1(this.data, nil);
        copy.setColor(this.color);
        copy.safeSetLeft(this.left.deepCopy(nil));
        copy.safeSetRight(this.right.deepCopy(nil));
        copy.lastRotation = this.lastRotation;
        copy.augmentedValue = this.augmentedValue;
        copy.size = this.size;
        copy.blackHeight = this.blackHeight;
        copy.height = this.height;
        copy.tag = this.tag;
        copy.pathCompressed = this.pathCompressed;
        return copy;
    }

    public String toIndentedString() {
        return toIndentedString(0);
    }

    private String toIndentedString(int level) {
        if (isNil()) return "";
        StringBuilder sb = new StringBuilder();
        sb.append("  ".repeat(level))
          .append(getData())
          .append(isRed() ? " [R]" : " [B]")
          .append("\n");
        sb.append(left.toIndentedString(level + 1));
        sb.append(right.toIndentedString(level + 1));
        return sb.toString();
    }

    public void alienSpawn(int depth, int maxDepth, int variance, Random rng) {
        if (depth >= maxDepth) return;

        int leftData = this.data - rng.nextInt(variance + 1);
        int rightData = this.data + rng.nextInt(variance + 1);

        TreeNode1 leftChild = TreeNode1.createNode(leftData, this.nilSentinel);
        TreeNode1 rightChild = TreeNode1.createNode(rightData, this.nilSentinel);

        this.safeSetLeft(leftChild);
        this.safeSetRight(rightChild);

        leftChild.setParent(this);
        rightChild.setParent(this);

        leftChild.setColor(rng.nextBoolean() ? Color.RED : Color.BLACK);
        rightChild.setColor(rng.nextBoolean() ? Color.RED : Color.BLACK);

        leftChild.alienSpawn(depth + 1, maxDepth, variance, rng);
        rightChild.alienSpawn(depth + 1, maxDepth, variance, rng);
    }

    public void mutateAugmentorByDepth(int depth) {
        if (this.isNil()) return;

        if (depth <= 1) {
            this.setAugmentor((node) -> node.augmentedValue = node.getData());
        } else if (depth <= 3) {
            this.setAugmentor((node) -> node.augmentedValue = node.getData() * 2);
        } else {
            this.setAugmentor((node) -> node.augmentedValue = node.getData() * node.getData());
        }

        this.getLeft().mutateAugmentorByDepth(depth + 1);
        this.getRight().mutateAugmentorByDepth(depth + 1);
    }

    public boolean isTripleRed() {
        if (!this.isRed()) return false;
        TreeNode1 p = this.getParent();
        TreeNode1 gp = (p != null) ? p.getParent() : null;
        return (p != null && p.isRed() && gp != null && gp.isRed());
    }

    @Override
    public String toString() {
        return (isNil() ? "NIL" : data + (isRed() ? "R" : "B"));
    }

    /**
     * Validate this node's local red-black invariants, throwing
     * {@link IllegalStateException} on violation. Uses explicit checks rather
     * than {@code assert} (which is disabled by default at runtime) so the
     * validation actually runs in production.
     */
    public void assertValid() {
        if (isNil() && !isBlack()) {
            throw new IllegalStateException("NIL nodes must be black");
        }
        if (isRed()) {
            if (!left.isBlack()) {
                throw new IllegalStateException("Red node " + data + " has a red left child");
            }
            if (!right.isBlack()) {
                throw new IllegalStateException("Red node " + data + " has a red right child");
            }
        }
    }
}
