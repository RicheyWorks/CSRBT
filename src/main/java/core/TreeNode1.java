package core;

import java.util.Random;
import java.util.Objects;

public class TreeNode1 implements Comparable<TreeNode1>, Cloneable {
    public enum Color { RED, BLACK }
    enum Rotation { NONE, LEFT, RIGHT }

    @FunctionalInterface
    public interface Augmentor {
        void apply(TreeNode1 node);
    }

    static final Augmentor defaultAugmentor = node -> {
        int leftSize = (node.left != null && !node.left.isNil()) ? node.left.augmentedValue : 0;
        int rightSize = (node.right != null && !node.right.isNil()) ? node.right.augmentedValue : 0;
        node.augmentedValue = 1 + leftSize + rightSize;
    };

    public static final TreeNode1 NIL = new TreeNode1(0, Color.BLACK); // Changed to public

    private final int data;
    private TreeNode1 left;
    private TreeNode1 right;
    private TreeNode1 parent;
    private Color color;
    private final TreeNode1 nilSentinel;
    private Rotation lastRotation = Rotation.NONE;
    private int augmentedValue = 0;
    private int blackHeight = 1;
    private int height = 1;
    private final transient Object lock = new Object();
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

    public static TreeNode1 createNil() {
        return NIL;
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
        assert leftBH == rightBH : "Black height violation";
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
        int leftBH = left.getBlackHeight();
        int rightBH = right.getBlackHeight();
        if (leftBH != rightBH) {
            throw new IllegalStateException("Black height mismatch: left=" + leftBH + ", right=" + rightBH);
        }
        blackHeight = (isBlack() ? 1 : 0) + leftBH;
    }

    public int getHeight() {
        return height;
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
        while (current.getParent() != null) {
            depth++;
            current = current.getParent();
        }
        return depth;
    }

    public int compareTo(TreeNode1 other) {
        return Integer.compare(this.data, other.data);
    }

    @Override
    public boolean equals(Object obj) {
        if (this == obj) return true;
        if (!(obj instanceof TreeNode1)) return false;
        TreeNode1 other = (TreeNode1) obj;
        if (this.isNil() && other.isNil()) return true;
        if (this.isNil() || other.isNil()) return false;
        return this.data == other.data &&
               this.color == other.color &&
               (this.left == null ? other.left == null : this.left.equals(other.left)) &&
               (this.right == null ? other.right == null : this.right.equals(other.right));
    }

    @Override
    public int hashCode() {
        if (isNil()) return 0;
        return Objects.hash(data, color, left, right);
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

    public int getAugmentedValue() {
        return augmentedValue;
    }

    public void setAugmentedValue(int value) {
        this.augmentedValue = value;
    }

    protected void recomputeAugment() {
        if (this.augmentor != null) {
            this.augmentor.apply(this);
        }
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

    public Object getLock() {
        return lock;
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

    public void assertValid() {
        if (isNil()) {
            assert isBlack() : "NIL nodes must be black!";
        }
        if (isRed()) {
            assert left.isBlack() : "Red node has red left child!";
            assert right.isBlack() : "Red node has red right child!";
        }
    }
}
